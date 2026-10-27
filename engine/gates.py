"""Krish's two gates as files, so readiness is computed and never written.

G1 (the weekly spec) and G2 (one matchday pack) are prepared by `growth.py spec
propose --queue` and `growth.py pack propose --queue` into local/engine/gates/. Each
daily loop report carries every undecided gate until Krish answers it on its current
digest. His answer on a G2 becomes one verdict per item in local/engine/verdicts.jsonl
(engine/formats.py, g2_verdicts), and readiness is counted from that ledger alone. A
signed G1 is kept as local/specs/<run>.signed.json. Krish posts by hand; the permalinks
read back from Buffer (engine/buffer_read.py, receipts) are kept in
local/engine/receipts.jsonl and on each G2 gate, and an approved G2 closes with a
creative_published event once every item he kept has one. Nothing here sends, posts
or spends.
"""
import json
from pathlib import Path
import re

from . import formats, reporting
from .clock import LONDON
from .records import atomic_json, instant, now

GATES = Path('engine') / 'gates'
LEDGER = Path('engine') / 'verdicts.jsonl'
RECEIPTS = Path('engine') / 'receipts.jsonl'
RECEIPT_FIELDS = ('creative_id', 'channel', 'permalink', 'published_at')
KINDS = ('g1', 'g2')
CONTEXT = ('unit_cost_gbp', 'unit_minutes', 'checks')   # measured per item; null while unknown, never guessed
# The pre-live checks pack.check itself performs. The rest of a recipe's checks (exact
# quote, captions, dimensions, media hashes, glyphs, listening, realism, spend) are
# recorded by the production run that did them; a check nobody recorded has not passed.
PACK_CHECKS = {'always': ('copy_checks', 'ai_label'),
               'live_rail': ('show_published', 'link_live', 'today_live', 'no_show_claim', 'two_pundits_published')}
BOUND = ('format_id', 'lock_version', 'fixture_ref')  # carried in each pack item, so in what Krish decides


def _folder(local):
    return Path(local) / GATES


GATE_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,119}', re.I)


def _path(local, proposal_id):
    """One file per gate, named by its id. Ids are letters, digits, - and _ only, so no two
    ids can share a file name, on Windows (case aside, checked in prepare) or anywhere."""
    if not isinstance(proposal_id, str) or not GATE_ID.fullmatch(proposal_id):
        raise ValueError(f'{proposal_id!r}: a gate id is letters, digits, - and _ only '
                         '(split a matchday with run_ids like fulltime:<day>:g2a, :g2b)')
    return _folder(local) / (proposal_id + '.json')


def _number(value):
    return value is None or (type(value) in (int, float) and value >= 0)


def _context_errors(kind, proposal, context):
    if kind == 'g1':
        return [] if context in (None, {}) else ['a G1 gate carries no item context']
    items = json.loads(proposal['exact_payload'])['items']
    ids = [item['creative_id'] for item in items]
    out = []
    for item in items:
        missing = [key for key in BOUND if not isinstance(item.get(key), str) or not item[key].strip()]
        if missing:
            out.append(f'{item["creative_id"]}: the pack item must carry ' + ', '.join(missing))
        elif item['lock_version'] == 'unlocked':
            out.append(f'{item["creative_id"]}: a verdict counts only under a pinned lock; set the format\'s '
                       'lock_version in the signed spec (growth.py formats lock --format ...)')
    if not isinstance(context, dict) or set(context) != set(ids):
        return out + ['a G2 gate needs context for exactly the creatives in its pack']
    for cid, row in context.items():
        if not isinstance(row, dict) or set(row) != set(CONTEXT):
            out.append(f'{cid}: context must carry exactly ' + ', '.join(CONTEXT))
        elif not all(_number(row[key]) for key in ('unit_cost_gbp', 'unit_minutes')):
            out.append(f'{cid}: unit cost (GBP) and unit minutes are numbers of 0 or more, or null when unknown')
        elif not isinstance(row['checks'], dict) or not all(
                isinstance(k, str) and isinstance(v, bool) for k, v in row['checks'].items()):
            out.append(f'{cid}: checks maps each pre-live check that ran to true or false')
    return out


def prepare(local, kind, proposal, context=None, checked=False):
    """Queue one G1 or G2 proposal for the next loop report. `checked` says the pack
    passed pack.check against the signed spec when it was built; a verdict counts toward
    readiness only then. An undecided gate with the same id is replaced (its earlier
    version is kept beside it); a settled one never is."""
    if kind not in KINDS:
        raise ValueError('a gate is g1 or g2')
    wanted = ('strategy', 'plan') if kind == 'g1' else ('post', None)
    if (proposal.get('wall'), proposal.get('stage')) != wanted:
        raise ValueError(f'a {kind.upper()} gate is a {"plan behind strategy" if kind == "g1" else "post ask"}')
    errors = _context_errors(kind, proposal, context)
    if errors:
        raise ValueError('; '.join(errors))
    path = _path(local, proposal['proposal_id'])
    for other in _folder(local).glob('*.json') if _folder(local).is_dir() else ():
        if other.name.lower() == path.name.lower() and other.name != path.name:
            raise ValueError(f'{proposal["proposal_id"]} differs only in case from {other.stem}, '
                             'which Windows treats as the same file')
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        if old['proposal'].get('proposal_id') != proposal['proposal_id']:
            raise ValueError(f'{path.name} already holds {old["proposal"].get("proposal_id")}')
        if old.get('settled_at'):
            raise ValueError(f'{proposal["proposal_id"]} was already decided; a new ask needs a new matchday or week')
        if old['proposal'].get('payload_sha256') != proposal.get('payload_sha256'):
            atomic_json(path.with_name(path.stem + '.replaced-' + old['proposal']['payload_sha256'][:12] + '.json'), old)
    gate = {'kind': kind, 'proposal': proposal, 'context': context or {}, 'checked': checked is True,
            'prepared_at': now(), 'settled_at': None}
    atomic_json(path, gate)
    return {'queued': proposal['proposal_id'], 'kind': kind, 'path': str(path)}


def _gates(local):
    folder = _folder(local)
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob('*.json')):
        if '.replaced-' in path.name:
            continue
        out.append((path, json.loads(path.read_text(encoding='utf-8'))))
    return out


def pending(local):
    """Every undecided gate's proposal, G1 first, for reporting.build."""
    open_gates = [g for _, g in _gates(local) if not g.get('settled_at')]
    return [g['proposal'] for g in sorted(open_gates, key=lambda g: (g['kind'], g['proposal']['proposal_id']))]


def _decision(pid, decided):
    """The decision g2_verdicts reads, rebuilt from control_center.classify's output,
    which has already checked the digest and any amendment."""
    if pid in decided.get('approved', {}):
        approved = decided['approved'][pid]
        return {'decision': 'approved', 'amended': approved['amended'], 'exact_payload': approved['exact_payload']}
    if pid in decided.get('declined', []):
        return {'decision': 'declined'}
    if pid in decided.get('done', []):
        return {'decision': 'done'}
    return None


def _record(local, rows):
    ledger = Path(local) / LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, 'a', encoding='utf-8', newline='\n') as out:
        for row in rows:
            out.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')


def _settle_one(local, path, gate, decision):
    at, rows = now(), []
    pid = gate['proposal']['proposal_id']
    if gate['kind'] == 'g2':
        payload = gate['proposal']['exact_payload']
        for row in formats.g2_verdicts(payload, decision):
            cost = gate['context'][row['creative_id']]
            needed = formats.recipe(row['format_id'])['prelive_checks'] if row.get('format_id') else ['missing']
            passed = gate.get('checked') is True and all(cost['checks'].get(name) is True for name in needed)
            rows.append({**row, 'prelive_checks_passed': passed,
                         'prelive_checks_missing': [name for name in needed if cost['checks'].get(name) is not True],
                         'unit_cost_gbp': cost['unit_cost_gbp'], 'unit_minutes': cost['unit_minutes'],
                         'unit_cost_recorded': cost['unit_cost_gbp'] is not None,
                         'unit_minutes_recorded': cost['unit_minutes'] is not None,
                         'decided_at': at, 'proposal_id': pid, 'payload_sha256': gate['proposal']['payload_sha256']})
        gate['added_by_krish'] = formats.added_items(payload, decision)
        _record(local, rows)                      # the verdicts first: a crash after this never loses them
    elif decision['decision'] == 'approved':
        signed = json.loads(decision['exact_payload'])
        target = Path(local) / 'specs' / (signed['run_id'].split(':', 1)[1] + '.signed.json')
        atomic_json(target, {'spec': signed, 'proposal_id': pid, 'amended': decision['amended'], 'signed_at': at})
    gate['settled_at'] = at
    gate['decision'] = decision['decision']
    atomic_json(path, gate)
    return rows


def settle(local, decided):
    """Record Krish's answers to queued gates from one loop's classified decisions, one
    gate at a time, so one bad gate never stops the others. Returns the verdict rows
    written; a gate that could not be read keeps waiting and its error is kept on it.
    An approval on an older digest, or an unverified amendment, settles nothing."""
    written = []
    for path, gate in _gates(local):
        if gate.get('settled_at'):
            continue
        decision = _decision(gate['proposal']['proposal_id'], decided or {})
        if decision is None:
            continue
        try:
            written += _settle_one(local, path, gate, decision)
        except (ValueError, KeyError, TypeError) as error:
            gate['settle_error'] = str(error)[:300]
            atomic_json(path, gate)
    return written


def verdicts(local):
    """Every verdict Krish has given, oldest first."""
    ledger = Path(local) / LEDGER
    if not ledger.is_file():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines() if line.strip()]


def _receipt(number, receipt):
    if not isinstance(receipt, dict) or set(receipt) != set(RECEIPT_FIELDS):
        raise ValueError(f'receipt {number} must carry exactly ' + ', '.join(RECEIPT_FIELDS))
    cid, channel, link, at = (receipt[key] for key in RECEIPT_FIELDS)
    if not (isinstance(cid, str) and cid.strip() and isinstance(channel, str) and channel.strip()):
        raise ValueError(f'receipt {number} needs a creative_id and a channel')
    if not isinstance(link, str) or not link.startswith('https://') or link != link.strip():
        raise ValueError(f'receipt {number}: the permalink must be an https link')
    if at is not None:
        try:
            instant(at)
        except ValueError:
            raise ValueError(f'receipt {number}: published_at must be an RFC 3339 time with its offset, '
                             'or null when Buffer gave none') from None
    return {key: receipt[key] for key in RECEIPT_FIELDS}


def _pack_items(gate):
    """(creative_id, channel) of each item in a G2 gate's pack, in pack order; none when
    the pack cannot be read, so one bad gate never stops another."""
    try:
        items = json.loads(gate['proposal']['exact_payload'])['items']
        return [(item['creative_id'], item.get('channel')) for item in items]
    except (ValueError, KeyError, TypeError):
        return []


def record_receipts(local, receipts):
    """Keep Krish's permalinks, as buffer_read.receipts returns them, once each (by
    creative, channel and permalink) in local/engine/receipts.jsonl, and copy each onto
    every G2 gate whose pack carries that creative on that channel; an item keeps the
    first one. Reading back a post only records it. Returns how many were new and which
    gates changed."""
    rows = [_receipt(n, r) for n, r in enumerate(receipts or [], start=1)]
    path = Path(local) / RECEIPTS
    kept = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()] if path.is_file() else []
    seen = {(r['creative_id'], r['channel'], r['permalink']) for r in kept}
    new = []
    for row in rows:
        if (row['creative_id'], row['channel'], row['permalink']) not in seen:
            seen.add((row['creative_id'], row['channel'], row['permalink']))
            new.append({**row, 'recorded_at': now()})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8', newline='\n') as out:
            for row in new:
                out.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
    changed = []
    for gate_path, gate in _gates(local):
        if gate.get('kind') != 'g2':
            continue
        items, held = _pack_items(gate), gate.setdefault('receipts', {})
        for row in kept + new:
            if (row['creative_id'], row['channel']) in items and row['creative_id'] not in held:
                held[row['creative_id']] = {k: row[k] for k in ('channel', 'permalink', 'published_at', 'recorded_at')}
                if gate['proposal']['proposal_id'] not in changed:
                    changed.append(gate['proposal']['proposal_id'])
        if gate['proposal']['proposal_id'] in changed:
            atomic_json(gate_path, gate)
    return {'recorded': len(new), 'gates': changed}


def events(local, since_date):
    """creative_published events for the report: one per approved G2 ask, once every item
    Krish kept (all but those he rejected) has his permalink, at the newest of their
    times, with the first kept item's permalink as evidence, when that day (in London)
    is on or after since_date. An ask he declined, or one still waiting, never closes."""
    ledger, out = verdicts(local), []
    for _, gate in _gates(local):
        if gate.get('kind') != 'g2' or not gate.get('settled_at') or gate.get('decision') != 'approved':
            continue
        pid, sha = gate['proposal']['proposal_id'], gate['proposal']['payload_sha256']
        rejected = {r.get('creative_id') for r in ledger if r.get('proposal_id') == pid
                    and r.get('payload_sha256') == sha and r.get('verdict') == 'reject'}
        kept = [cid for cid, _ in _pack_items(gate) if cid not in rejected]
        held = gate.get('receipts') or {}
        if not kept or not all(cid in held for cid in kept):
            continue
        at = max(instant(held[cid]['published_at'] or held[cid]['recorded_at']) for cid in kept)
        if at.astimezone(LONDON).date().isoformat() < since_date:
            continue
        out.append({'event': 'creative_published', 'proposal_id': pid, 'at': reporting.iso(at),
                    'evidence_url': held[kept[0]]['permalink']})
    return out
