"""Reports. The version 2 envelope is the private local checkpoint; the protocol
report is what Control Center receives (docs/control-center/ENGINE-PROTOCOL.md).
This module builds and checks reports. It has no HTTP path: the transport is
engine/control_center.py.

Reports go as protocol 1.1.0, which adds a proposal's stage (plan, go_live,
check_in) and parent_proposal_id; 1.2.0 only when a proposal names a subject.
Krish sees one ask per engine at a time: an answered ruling is never asked
again, no second walled ask of a kind already waiting is added, and an ask he has
already answered on its digest takes no ask's place."""
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re

from . import policy
from .clock import LONDON
from .policy import VERSION, holds
from .records import fingerprint

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / 'docs' / 'control-center' / 'engine-report.schema.json'
ENGINE_ID = 'growth-fulltime'
PRODUCT_SLUG = 'full-time'
SLUG = 'fulltime'
REPO_URL = 'https://github.com/krishanraja/growth-fulltime'
HOLD_ORDER = ['LIBRARY', 'RAIL', 'RELEASE', 'CHANNEL', 'CONSENT', 'DATA', 'ASSETS', 'APPROVAL',
              'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7']
POSTABLE = policy.BRAND_CHANNELS | {'whatsapp'}
PROTOCOL_VERSION = '1.1.0'
STAGES = ('plan', 'go_live', 'check_in')
GO_LIVE_WALLS = ('send', 'post', 'spend')
ASK_KINDS = STAGES + GO_LIVE_WALLS + ('strategy',)
NEWER_FIELDS = {'stage': (1, 1), 'parent_proposal_id': (1, 1), 'subject_ref': (1, 2)}
PROPOSAL_ID = r'[A-Za-z0-9][A-Za-z0-9:._-]{0,119}'
RULING_PREFIX = SLUG + ':ruling:'
# The order the standing ruling asks reach Krish, one at a time: D7, the consent item,
# must close first (ruling 1 of 27 October), then D2 and D3, then the rest as built.
RULING_FIRST = ('D7', 'D2', 'D3')
GA4_COMPLETERS = 'A Google Analytics row is web landings, never people who finished a show; it is not counted.'


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
    return json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))


def version_numbers(version):
    """(major, minor) of a protocol version such as '1.1.0', or None when it is not one."""
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', version) if isinstance(version, str) else None
    return (int(match.group(1)), int(match.group(2))) if match else None


def report_version(proposals):
    """1.1.0, which carries stages, or 1.2.0 only when a proposal uses subject_ref.
    A version is raised only for a field in use."""
    used = any(isinstance(p, dict) and p.get('subject_ref') is not None for p in proposals or [])
    return '1.2.0' if used else PROTOCOL_VERSION


def protocol_errors(report):
    """The protocol rules the JSON schema cannot say: a field newer than the report's
    version is refused, and each stage sits behind the wall ENGINE-PROTOCOL.md gives it.
    A plan is behind a wall with the plan in exact_payload; a go-live is a send, post or
    spend naming its plan; a check-in is a strategy call naming its plan, with its
    progress in exact_payload. parent_proposal_id belongs on those two only."""
    if not isinstance(report, dict) or not isinstance(report.get('proposals'), list):
        return []
    out = []
    version = version_numbers(report.get('schema_version'))
    proposals = [p for p in report['proposals'] if isinstance(p, dict)]
    stage_of = {p['proposal_id']: p.get('stage') for p in proposals if isinstance(p.get('proposal_id'), str)}
    for i, p in enumerate(proposals):
        path = f'report.proposals[{i}]'
        for field, needs in NEWER_FIELDS.items():
            if field in p and version is not None and version < needs:
                out.append(f'{path}: {field} needs protocol {needs[0]}.{needs[1]}.0 or later, '
                           f'and this report is {report["schema_version"]}')
        stage, parent, wall = p.get('stage'), p.get('parent_proposal_id'), p.get('wall')
        if p.get('kind') == 'autonomous' and wall != 'none':
            out.append(f'{path}: an autonomous proposal cannot be behind a wall')
        if wall == 'spend' and p.get('amount_usd') is None:
            out.append(f'{path}: a spend needs amount_usd')
        if wall in ('send', 'post') and not p.get('exact_payload'):
            out.append(f'{path}: a {wall} needs its exact_payload')
        if stage == 'plan':
            if wall == 'none':
                out.append(f'{path}: a plan must be behind a wall')
            if not p.get('exact_payload'):
                out.append(f'{path}: a plan carries the plan itself in exact_payload, so Krish can amend it')
        elif stage == 'go_live' and wall not in GO_LIVE_WALLS:
            out.append(f'{path}: a go-live must be behind send, post or spend')
        elif stage == 'check_in':
            if wall != 'strategy':
                out.append(f'{path}: a check-in must be behind strategy')
            if not p.get('exact_payload'):
                out.append(f'{path}: a check-in carries its progress against the plan in exact_payload')
        if stage in ('go_live', 'check_in'):
            if not isinstance(parent, str) or not parent:
                out.append(f'{path}: a {stage.replace("_", "-")} needs parent_proposal_id, the plan it belongs to')
            elif not re.fullmatch(PROPOSAL_ID, parent):
                out.append(f'{path}: parent_proposal_id is not a proposal id')
            elif parent == p.get('proposal_id'):
                out.append(f'{path}: parent_proposal_id cannot name the proposal itself')
            elif parent in stage_of and stage_of[parent] != 'plan':
                out.append(f'{path}: parent_proposal_id must name a plan, and {parent} is not one')
        elif parent is not None:
            out.append(f'{path}: parent_proposal_id belongs only on a go-live or a check-in')
    return out


def _is_datetime(value):
    try:
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None
    except (ValueError, AttributeError):
        return False


def schema_errors(value, schema=None, path='report'):
    """Every way a value breaks the schema. Called with the report schema itself (no
    schema given), it also applies protocol_errors, so a whole report is checked whole."""
    whole = schema is None
    schema = load_schema() if whole else schema
    out = protocol_errors(value) if whole else []
    kinds = schema.get('type')
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        checks = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
                  'string': lambda v: isinstance(v, str), 'null': lambda v: v is None,
                  'integer': lambda v: type(v) is int,
                  'number': lambda v: type(v) in (int, float) and math.isfinite(v)}
        if not any(checks[k](value) for k in kinds):
            return out + [f'{path}: expected {"/".join(kinds)}']
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


def _from_ga4(row):
    """True when a row's source or query reference names Google Analytics: measurements'
    own test where it has one, and GA4 or Google Analytics in any case always."""
    from . import measurements
    text = re.sub(r'[^a-z0-9]', '', f'{row.get("source", "")} {row.get("query_ref", "")}'.lower())
    check = getattr(measurements, 'from_ga4', None)
    return 'ga4' in text or 'googleanalytics' in text or bool(check and check(row))


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
    rows = list(rows or [])
    # A Google Analytics row is landings on fulltime.fm, never completers (ruling 8), so it
    # never enters this count, whatever its label; the product's own row still counts.
    landings = [r for r in rows if isinstance(r, dict) and r.get('metric') == 'attributed_new_completers'
                and _from_ga4(r)]
    card = scorecard([r for r in rows if not any(r is x for x in landings)], start, end)
    completers = card['attributed_new_completers']
    in_window = any((r.get('window_start'), r.get('window_end')) == (start, end) and 'creative_id' not in r
                    for r in landings)
    if completers['status'] == 'missing' and in_window:
        first = _objective('attributed_new_completers', 'people', None, 'missing', GA4_COMPLETERS, window)
    elif completers['status'] == 'measured':
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
              evidence=None, expires_at=None, amount_usd=None, stage=None, parent_proposal_id=None):
    """One proposal. stage and parent_proposal_id (1.1.0) are written only when used."""
    out = {'proposal_id': proposal_id, 'title': title[:160], 'why': why[:1000], 'kind': kind, 'wall': wall,
           'amount_usd': amount_usd, 'channel': channel, 'objective_key': objective_key,
           'exact_payload': exact_payload, 'payload_sha256': canonical_sha256(payload),
           'evidence': evidence or [], 'close_condition': {'event': close_event, 'reference': reference},
           'expires_at': expires_at}
    if stage is not None or parent_proposal_id is not None:
        out.update(stage=stage, parent_proposal_id=parent_proposal_id)
    return out


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
    if policy.release_needed(state):
        out.append(('RELEASE', 'No product release decision is recorded in full-time docs/12-roadmap.md, and the '
                               'ORGANIC per-take exception is not in force there yet.'))
    if identity_known is None:
        out.append(('CHANNEL', 'Brand identity proof is kept in the private workspace; this runner cannot confirm it.'))
    elif not identity_known:
        out.append(('CHANNEL', 'No verified Full Time brand identity on TikTok, Instagram or YouTube within '
                               'thirty days.'))
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


def ruled(rulings_file, rid):
    """True when rulings.json records Krish's yes on this ruling."""
    return ((rulings_file or {}).get(rid) or {}).get('status') == 'approved'


def release_retired(state, rulings_file):
    """The release ask is answered once the release is open, or once rulings.json
    approves ruling 1 of 27 October (D1, with ORGANIC) or a release entry. The RELEASE
    hold itself still lifts only on the product's own decision (policy.release_open)."""
    return policy.release_open(state) or any(ruled(rulings_file, r) for r in ('release', 'RELEASE', 'D1', 'ORGANIC'))


def ask_kind(proposal):
    """What Krish's one list orders an ask by: its stage, or else its wall."""
    return proposal.get('stage') or proposal.get('wall')


def answered_pairs(value):
    """(proposal_id, payload_sha256) pairs Krish has answered, from any iterable of pairs."""
    return {(pid, sha) for pid, sha in (value or ()) if isinstance(pid, str) and isinstance(sha, str)}


def one_ask(proposals, waiting=None, answered=()):
    """One ask at a time (ENGINE-PROTOCOL.md). `waiting` maps each proposal_id already on
    Krish's list and unanswered to its kind. `answered` holds (proposal_id, payload_sha256)
    for each ask he has already answered on that digest: Control Center keeps it off his
    list, so it is kept as it is, waits for nothing and holds no place. An ask that waits
    is kept, and so kept current. No ask is added beside another of its kind that waits,
    and only one new ask of each kind is added per report, the standing ruling asks
    included (build orders them D7, D2, D3, then the rest). Returns (kept, deferred)."""
    answered = answered_pairs(answered)
    digest = {p['proposal_id']: p.get('payload_sha256') for p in proposals}
    waiting = {pid: kind for pid, kind in (waiting or {}).items() if (pid, digest.get(pid)) not in answered}
    kinds_waiting = set(waiting.values())
    kept, deferred, added = [], [], set()
    for p in proposals:
        pid, kind = p['proposal_id'], ask_kind(p)
        if p.get('wall') == 'none' or pid in waiting or (pid, p.get('payload_sha256')) in answered:
            kept.append(p)
        elif kind in kinds_waiting or kind in added:
            deferred.append(p)
        else:
            kept.append(p)
            added.add(kind)
    return kept, deferred


def standing_order(proposals):
    """The standing ruling asks put in the order they reach Krish, D7, D2, D3, then the
    rest as built, each into a place one of them held; every other proposal stays put."""
    places = [i for i, p in enumerate(proposals) if p['proposal_id'].startswith(RULING_PREFIX)]
    rank = lambda p: (RULING_FIRST.index(p['proposal_id'][len(RULING_PREFIX):])
                      if p['proposal_id'][len(RULING_PREFIX):] in RULING_FIRST else len(RULING_FIRST))
    out = list(proposals)
    for i, p in zip(places, sorted((proposals[i] for i in places), key=rank)):
        out[i] = p
    return out


def build(run_id, mode, observed_at, state, items, rulings_file, objectives_list, activity,
          held_items=(), events=(), identity_known=None, kill_list=(), degraded=(), max_actions=3,
          waiting=None, gate_proposals=(), extra_holds=(), answered=()):
    """The whole protocol report, sealed. `degraded` names sources that were missing.
    `waiting` is what is already on Krish's list (proposal_id to kind), from the last
    live delivery; unknown is None, and then nothing is taken to be waiting.
    `answered` holds the (proposal_id, payload_sha256) pairs he has already answered.
    `gate_proposals` are the queued G1 and G2 asks (engine/gates.py); they lead, so
    one ask at a time keeps them ahead of others of their kind."""
    state = state or {}
    proposals, release_done = [copy.deepcopy(p) for p in gate_proposals], False
    retired = release_retired(state, rulings_file)
    ready = [x for x in items if not holds(x) and not (retired and x.get('why') == 'release')]
    for item in ready[:max(0, min(3, max_actions))]:
        if item.get('why') == 'release':
            proposals.append(release_proposal()); release_done = True
        else:
            proposals.append(action_proposal(item))
    if not release_done and not retired:
        proposals.append(release_proposal())
    for rid, ruling in sorted(rulings_file.items()):
        unlocks = set(ruling.get('unlocks') or [])
        # Only a pending ruling is asked: one approved in rulings.json is never asked again.
        # RELEASE is the product's own decision: its one ask is the release proposal above,
        # which ruling 1 retired, so it is never asked a second time under its own name.
        if rid == 'RELEASE':
            continue
        if ruling.get('status') == 'pending' and not (unlocks and unlocks <= policy.EXCLUDED):
            proposals.append(ruling_proposal(rid, ruling))
    proposals += [kill_proposal(line) for line in kill_list]
    proposals, deferred = one_ask(standing_order(proposals), waiting, answered)
    entries = gate_holds(state, rulings_file, identity_known)
    entries += [('DATA', reason) for reason in degraded]
    entries += list(extra_holds)       # e.g. the weekly LIBRARY reconcile (engine/library.py)
    hold_list = merge_holds(entries, list(held_items) + [x for x in items if holds(x)])
    status = 'degraded' if degraded else ('held' if hold_list else 'ready')
    source = {'revision': str(state.get('sha') or 'unknown')[:128],
              'captured_at': state.get('synced_at') or observed_at}
    lines = [{'line': a[0][:500], 'evidence_url': a[1]} if isinstance(a, tuple)
             else {'line': a[:500], 'evidence_url': None} for a in activity]
    if deferred:
        lines = lines[:39] + [{'line': ('One ask at a time: these wait until the ask of their kind already '
                                        "on Krish's list is answered: "
                                        + ', '.join(p['proposal_id'] for p in deferred) + '.')[:500],
                               'evidence_url': None}]
    proposals = proposals[:10]
    report = {'schema_version': report_version(proposals), 'engine_id': ENGINE_ID, 'product_slug': PRODUCT_SLUG,
              'run_id': run_id, 'mode': mode, 'observed_at': observed_at, 'source': source,
              'status': status, 'objectives': objectives_list, 'activity': lines[:40],
              'proposals': proposals, 'events': list(events)[:40], 'holds': hold_list}
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
