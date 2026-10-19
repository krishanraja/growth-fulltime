"""Reports. The version 2 envelope is the private local checkpoint; the protocol
report is what Control Center receives (docs/control-center/ENGINE-PROTOCOL.md).
This module builds and checks reports. It has no HTTP path: the transport is
engine/control_center.py."""
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from . import policy
from .policy import VERSION, holds
from .records import fingerprint

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / 'docs' / 'control-center' / 'engine-report.schema.json'
LONDON = ZoneInfo('Europe/London')
ENGINE_ID = 'growth-fulltime'
PRODUCT_SLUG = 'full-time'
SLUG = 'fulltime'
REPO_URL = 'https://github.com/krishanraja/growth-fulltime'
HOLD_ORDER = ['RAIL', 'RELEASE', 'CHANNEL', 'CONSENT', 'DATA', 'ASSETS', 'APPROVAL',
              'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7']
POSTABLE = policy.BRAND_CHANNELS | {'whatsapp'}


def envelope(pack, receipt):
    items = []
    for item in pack.get('items') or []:
        identifier = item.get('item_id') or item.get('creative_id') or 'item-' + fingerprint(item)[:20]
        items.append({**copy.deepcopy(item), 'item_id': identifier,
                      'holds': holds(item), 'readiness': 'held' if holds(item) else 'ready'})
    return {'contract_version': 2, 'engine_product': 'fulltime', 'product_slug': 'full-time',
            'venture': 'full_time', 'policy_version': VERSION,
            'report_id': receipt['id'], 'revision': receipt['digest'],
            'delivery': {'status': 'pending_handoff', 'write_attempted': False},
            'pack': {**copy.deepcopy(pack), 'items': items},
            'required_capabilities': ['product_isolation', 'stable_item_ids', 'holds',
                                      'provenance', 'typed_metrics', 'publication_receipts']}


def verify_receipt(bundle, receipt):
    """For the future integrator: GET success alone can never acknowledge a report."""
    if not isinstance(receipt, dict) or receipt.get('ok') is not True:
        return False
    stored = receipt.get('report') or {}
    return (stored.get('report_id') == bundle['report_id']
            and stored.get('revision') == bundle['revision']
            and stored.get('product_slug') == bundle['product_slug']
            and stored.get('venture') == bundle['venture']
            and stored.get('pack') == bundle['pack'])


# ---------------------------------------------------------------------------
# The protocol digest: canonical JSON as Control Center computes it.
# ---------------------------------------------------------------------------
def _plain(value):
    """Whole floats become ints so Python writes what JavaScript writes (1, not 1.0)."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('non-finite numbers cannot be reported')
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    raise ValueError('unsupported value in a report: ' + type(value).__name__)


def canonical(value):
    """Keys sorted at every depth, no whitespace, arrays in order, no Unicode normalisation."""
    return json.dumps(_plain(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def seal(report):
    """The report with payload_sha256 over everything else, and whole numbers as ints."""
    body = _plain({k: v for k, v in report.items() if k != 'payload_sha256'})
    return {**body, 'payload_sha256': canonical_sha256(body)}


# ---------------------------------------------------------------------------
# A strict reading of the report schema: every property not named is refused,
# at every depth, because Control Center refuses unknown fields.
# ---------------------------------------------------------------------------
def load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def _is_datetime(value):
    try:
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None
    except (ValueError, AttributeError):
        return False


def schema_errors(value, schema=None, path='report'):
    schema = load_schema() if schema is None else schema
    out = []
    kinds = schema.get('type')
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        checks = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
                  'string': lambda v: isinstance(v, str), 'null': lambda v: v is None,
                  'integer': lambda v: type(v) is int,
                  'number': lambda v: type(v) in (int, float) and math.isfinite(v)}
        if not any(checks[k](value) for k in kinds):
            return [f'{path}: expected {"/".join(kinds)}']
    if 'const' in schema and value != schema['const']:
        out.append(f'{path}: must be {schema["const"]!r}')
    if 'enum' in schema and value not in schema['enum']:
        out.append(f'{path}: must be one of {schema["enum"]}')
    if isinstance(value, str):
        if 'maxLength' in schema and len(value) > schema['maxLength']:
            out.append(f'{path}: longer than {schema["maxLength"]}')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            out.append(f'{path}: does not match {schema["pattern"]}')
        if schema.get('format') == 'date-time' and not _is_datetime(value):
            out.append(f'{path}: not a date-time with a time zone')
    if type(value) in (int, float) and 'minimum' in schema and value < schema['minimum']:
        out.append(f'{path}: below {schema["minimum"]}')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for key in schema.get('required', []):
            if key not in value:
                out.append(f'{path}: {key} is required')
        for key in value:
            if key not in props:
                out.append(f'{path}: unknown field {key}')
            else:
                out += schema_errors(value[key], props[key], f'{path}.{key}')
    if isinstance(value, list):
        if 'maxItems' in schema and len(value) > schema['maxItems']:
            out.append(f'{path}: more than {schema["maxItems"]} entries')
        for i, item in enumerate(value):
            out += schema_errors(item, schema.get('items', {}), f'{path}[{i}]')
    return out


# ---------------------------------------------------------------------------
# Building the protocol report from what the engine already knows.
# ---------------------------------------------------------------------------
def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(moment):
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def london_today(moment=None):
    return (moment or utc_now()).astimezone(LONDON).date()


def week_window(today):
    """The seven complete London days ending yesterday, as dates and as instants."""
    end = today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=6)
    opens = dt.datetime.combine(start, dt.time(0), LONDON)
    closes = dt.datetime.combine(today, dt.time(0), LONDON)
    return start, end, opens.isoformat(), closes.isoformat()


def run_id_for(today, kind):
    return f'{SLUG}:{today.isoformat()}:{kind}'


def _objective(key, unit, value, availability, reason, window):
    _, _, opens, closes = window
    return {'key': key, 'value': value, 'unit': unit, 'window_start': opens, 'window_end': closes,
            'timezone': 'Europe/London', 'availability': availability, 'reason': reason}


def objectives(today, rows=None, runs=None, workspace=True):
    """The two registered objectives. Unknown is null with a reason, never zero."""
    window = week_window(today)
    start, end = window[0].isoformat(), window[1].isoformat()
    if not workspace:
        why = ('Measured only in the private workspace, from approved aggregate exports and the '
               'engine ledger; this clean runner cannot see them.')
        return [_objective('attributed_new_completers', 'people', None, 'missing', why, window),
                _objective('marketing_cash_gbp', 'GBP', None, 'missing', why, window)]
    from .measurements import scorecard
    card = scorecard(rows or [], start, end)
    completers = card['attributed_new_completers']
    if completers['status'] == 'measured':
        first = _objective('attributed_new_completers', 'people', completers['value'], 'measured', None, window)
    elif completers['status'] == 'stale':
        first = _objective('attributed_new_completers', 'people', completers['value'], 'stale',
                           'The newest approved aggregate for this window is older than 48 hours.', window)
    else:
        first = _objective('attributed_new_completers', 'people', None, 'missing',
                           'No approved whole-week aggregate exists; the attribution collector is not built '
                           'yet (briefs/GROWTH-FOUNDATIONS.md, MEASUREMENT.md).', window)
    cash = card['marketing_cash_gbp']
    if cash['status'] in ('measured', 'stale'):
        second = _objective('marketing_cash_gbp', 'GBP', cash['value'], cash['status'],
                            None if cash['status'] == 'measured' else 'The newest recorded usage is older than 48 hours.',
                            window)
    else:
        recorded = [r for r in (runs or {}).values()
                    if isinstance(r, dict) and start <= str(r.get('date', '')) <= end]
        amounts = [(r.get('usage') or {}).get('marketing_cash_gbp') for r in recorded]
        if not recorded or any(type(a) not in (int, float) for a in amounts):
            second = _objective('marketing_cash_gbp', 'GBP', None, 'missing',
                                'No engine run with recorded usage falls in this week.', window)
        else:
            second = _objective('marketing_cash_gbp', 'GBP', sum(amounts), 'measured',
                                f'Engine ledger: {len(recorded)} runs in the week recorded their marketing cash; '
                                'the engine has no spend path. Spend outside this engine is not visible to it.',
                                window)
    return [first, second]


def _proposal(proposal_id, title, why, kind, wall, payload, close_event, reference,
              objective_key='attributed_new_completers', channel=None, exact_payload=None,
              evidence=None, expires_at=None):
    return {'proposal_id': proposal_id, 'title': title[:160], 'why': why[:1000], 'kind': kind, 'wall': wall,
            'amount_usd': None, 'channel': channel, 'objective_key': objective_key,
            'exact_payload': exact_payload, 'payload_sha256': canonical_sha256(payload),
            'evidence': evidence or [], 'close_condition': {'event': close_event, 'reference': reference},
            'expires_at': expires_at}


def action_proposal(item):
    """A ready pack item. Public copy is behind the post wall with its exact words;
    an internal instruction is work inside the walls."""
    why = str(item.get('why') or '')
    key = (item.get('creative_id') or (why if re.fullmatch(r'[a-z0-9_-]{1,40}', why) else None)
           or item.get('item_id') or 'item-' + fingerprint(item)[:20])
    key = re.sub(r'[^A-Za-z0-9:._-]', '-', str(key))[:100]
    platform = item.get('platform')
    if platform in POSTABLE and item.get('creative_id'):
        target = item['creative_id']
        return _proposal(f'{SLUG}:post:{target}', f'{platform}: {target}',
                         'Ready under every gate: product, rail, release, identity, channel and consent.',
                         'prepared', 'post', {'channel': platform, 'exact_payload': item['text'], 'target': target},
                         'creative_published', target, channel=platform, exact_payload=item['text'])
    if platform == 'email':
        target = item.get('consent_ref') or item.get('item_id')
        return _proposal(f'{SLUG}:send:{item.get("item_id")}', 'Email to an opted-in cohort',
                         'Inbound or explicit opt-in basis recorded outside this repository.',
                         'prepared', 'send', {'channel': 'email', 'exact_payload': item['text'], 'target': target},
                         'message_sent', target, channel='email', exact_payload=item['text'])
    events = {'rail': ('rail_gate_open', 'newest match with 4 of 6 AI Pundits'),
              'measurement': ('aggregate_measured', 'unique_completers')}
    event, reference = events.get(key, ('constraint_closed', key))
    title = {'rail': 'Diagnose the thin rail from stored verdicts',
             'measurement': 'Build the completion and return queries'}.get(key, item['text'][:160])
    return _proposal(f'{SLUG}:action:{key}', title, item['text'], 'advice', 'none',
                     {'proposal_id': f'{SLUG}:action:{key}', 'instruction': item['text']}, event, reference)


def release_proposal():
    why = ('Public acquisition needs the product release decision, separately from D1. Until it is '
           'recorded in full-time docs/12-roadmap.md every public draft stays held for RELEASE.')
    return _proposal(f'{SLUG}:ruling:release', 'Make the Full Time release decision for public acquisition',
                     why, 'advice', 'strategy',
                     {'proposal_id': f'{SLUG}:ruling:release', 'decision': 'release', 'why': why},
                     'release_recorded', 'full-time docs/12-roadmap.md',
                     evidence=[{'label': 'Release gate, AGENTS.md rule 4', 'url': REPO_URL + '/blob/main/AGENTS.md'}])


def ruling_proposal(rid, ruling):
    payload = {'proposal_id': f'{SLUG}:ruling:{rid}', 'ruling': rid, 'title': ruling.get('title'),
               'recommendation': ruling.get('recommendation'), 'unlocks': ruling.get('unlocks', []),
               'requires': ruling.get('requires', [])}
    return _proposal(f'{SLUG}:ruling:{rid}', f'{rid}: {ruling.get("title", "")}', ruling.get('recommendation', ''),
                     'advice', 'strategy', payload, 'ruling_recorded', rid,
                     evidence=[{'label': 'rulings.json', 'url': REPO_URL + '/blob/main/rulings.json'},
                               {'label': 'The 1,000-user playbook, section 9',
                                'url': REPO_URL + '/blob/main/knowledge/full-time-1000-users-playbook.md'}])


def kill_proposal(line):
    pid = f'{SLUG}:kill:{canonical_sha256(line)[:12]}'
    return _proposal(pid, 'Weekly review: stop or keep stopped', line, 'advice', 'strategy',
                     {'proposal_id': pid, 'kill': line}, 'ruling_recorded', pid)


def gate_holds(state, rulings_file, identity_known):
    """Holds that apply to all public work, before any single draft."""
    state = state or {}
    gate = (state.get('push') or {})
    out = []
    if not gate.get('open'):
        out.append(('RAIL', gate.get('why') or 'the rail was not read'))
    if not policy.release_open(state):
        out.append(('RELEASE', 'No product release decision is recorded in full-time docs/12-roadmap.md.'))
    if identity_known is None:
        out.append(('CHANNEL', 'Brand identity proof is kept in the private workspace; this runner cannot confirm it.'))
    elif not identity_known:
        out.append(('CHANNEL', 'No verified Full Time brand identity for YouTube within thirty days.'))
    if not ((state.get('rulings') or {}).get('D7') or {}).get('in_force'):
        out.append(('CONSENT', 'D7, the analytics consent item, is not in force.'))
    for rid, ruling in sorted(rulings_file.items()):
        unlocks = set(ruling.get('unlocks') or [])
        if ruling.get('status') == 'pending' and unlocks and unlocks <= policy.EXCLUDED:
            out.append((rid, 'Not proposed: it unlocks only channels the owner excluded on 2026-10-17 ('
                        + ', '.join(sorted(unlocks)) + ').'))
    return out


def merge_holds(entries, held_items):
    """One hold per code: the gate's reason and the held items carrying it."""
    by_code = {}
    for code, detail in entries:
        by_code.setdefault(code, []).append(detail)
    for item in held_items:
        for code in holds(item):
            by_code.setdefault(code, [])
    counts = {}
    for item in held_items:
        label = item.get('creative_id') or item.get('item_id') or 'draft'
        for code in holds(item):
            counts.setdefault(code, []).append(label)
    order = {code: i for i, code in enumerate(HOLD_ORDER)}
    out = []
    for code in sorted(by_code, key=lambda c: (order.get(c, 99), c)):
        parts = list(by_code[code])
        labels = sorted(set(counts.get(code, [])))
        if labels:
            parts.append(f'{len(labels)} held: ' + ', '.join(labels[:8]) + (' and more' if len(labels) > 8 else ''))
        out.append({'reason': code[:200], 'detail': ' '.join(parts)[:1000] or None})
    return out[:40]


def build(run_id, mode, observed_at, state, items, rulings_file, objectives_list, activity,
          held_items=(), events=(), identity_known=None, kill_list=(), degraded=(), max_actions=3):
    """The whole protocol report, sealed. `degraded` names sources that were missing."""
    state = state or {}
    proposals, release_done = [], False
    for item in [x for x in items if not holds(x)][:max(0, min(3, max_actions))]:
        if item.get('why') == 'release':
            proposals.append(release_proposal()); release_done = True
        else:
            proposals.append(action_proposal(item))
    if not release_done and not policy.release_open(state):
        proposals.append(release_proposal())
    for rid, ruling in sorted(rulings_file.items()):
        unlocks = set(ruling.get('unlocks') or [])
        if ruling.get('status') == 'pending' and not (unlocks and unlocks <= policy.EXCLUDED):
            proposals.append(ruling_proposal(rid, ruling))
    proposals += [kill_proposal(line) for line in kill_list]
    entries = gate_holds(state, rulings_file, identity_known)
    entries += [('DATA', reason) for reason in degraded]
    hold_list = merge_holds(entries, list(held_items) + [x for x in items if holds(x)])
    status = 'degraded' if degraded else ('held' if hold_list else 'ready')
    source = {'revision': str(state.get('sha') or 'unknown')[:128],
              'captured_at': state.get('synced_at') or observed_at}
    report = {'schema_version': '1.0.0', 'engine_id': ENGINE_ID, 'product_slug': PRODUCT_SLUG,
              'run_id': run_id, 'mode': mode, 'observed_at': observed_at, 'source': source,
              'status': status, 'objectives': objectives_list,
              'activity': [{'line': a[0][:500], 'evidence_url': a[1]} if isinstance(a, tuple)
                           else {'line': a[:500], 'evidence_url': None} for a in activity][:40],
              'proposals': proposals[:10], 'events': list(events)[:40], 'holds': hold_list}
    return seal(report)


def publication_events(creatives, since_date):
    """Human-confirmed publication receipts in the window, as creative_published events."""
    out = []
    for cid, creative in sorted((creatives or {}).items()):
        proof = creative.get('publication') or {}
        if creative.get('status') != 'published' or not proof.get('url', '').startswith('https://'):
            continue
        if str(proof.get('recorded_at', ''))[:10] < since_date:
            continue
        out.append({'event': 'creative_published', 'proposal_id': f'{SLUG}:post:{cid}',
                    'at': proof['recorded_at'], 'evidence_url': proof['url']})
    return out


def held_creatives(creatives):
    """The latest version of every creative still held, as items with their codes."""
    out = []
    for cid, creative in sorted((creatives or {}).items()):
        if creative.get('latest_version_status', creative.get('status')) != 'held' or not creative.get('versions'):
            continue
        item = creative['versions'][-1]['item']
        out.append({'creative_id': cid, 'holds': holds(item)})
    return out


def ready_creatives(creatives):
    """The latest version of every creative that passed every gate and is not yet
    published: proposed behind its wall with the exact words, never sent from here."""
    out = []
    for cid, creative in sorted((creatives or {}).items()):
        if creative.get('latest_version_status') != 'ready' or not creative.get('versions'):
            continue
        item = creative['versions'][-1]['item']
        if not holds(item) and item.get('text'):
            out.append({**item, 'creative_id': cid})
    return out
