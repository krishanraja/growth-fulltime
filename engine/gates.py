"""Krish's two gates as files, so readiness is computed and never written.

G1 (the weekly spec) and G2 (one matchday pack) are prepared by `growth.py spec
propose --queue` and `growth.py pack propose --queue` into local/engine/gates/. Each
daily loop report carries every undecided gate until Krish answers it on its current
digest. His answer on a G2 becomes one verdict per item in local/engine/verdicts.jsonl
(engine/formats.py, g2_verdicts), and readiness is counted from that ledger alone. A
signed G1 is kept as local/specs/<run>.signed.json. Nothing here sends, posts or spends.
"""
import json
from pathlib import Path

from . import formats
from .records import atomic_json, now

GATES = Path('engine') / 'gates'
LEDGER = Path('engine') / 'verdicts.jsonl'
KINDS = ('g1', 'g2')
CONTEXT = ('format_id', 'lock_version', 'fixture_ref', 'unit_cost_recorded', 'unit_minutes_recorded')


def _folder(local):
    return Path(local) / GATES


def _path(local, proposal_id):
    if not isinstance(proposal_id, str) or not proposal_id or '/' in proposal_id or '\\' in proposal_id \
            or proposal_id.startswith('.'):
        raise ValueError('a gate needs a plain proposal_id')
    return _folder(local) / (proposal_id.replace(':', '_') + '.json')


def _context_errors(kind, proposal, context):
    if kind == 'g1':
        return [] if context in (None, {}) else ['a G1 gate carries no item context']
    items = json.loads(proposal['exact_payload'])['items']
    ids = [item['creative_id'] for item in items]
    if not isinstance(context, dict) or set(context) != set(ids):
        return ['a G2 gate needs context for exactly the creatives in its pack']
    out = []
    for cid, row in context.items():
        if not isinstance(row, dict) or set(row) != set(CONTEXT):
            out.append(f'{cid}: context must carry exactly ' + ', '.join(CONTEXT))
            continue
        if not isinstance(row['fixture_ref'], str) or not row['fixture_ref'].strip():
            out.append(f'{cid}: fixture_ref names the match')
        if not all(isinstance(row[k], bool) for k in ('unit_cost_recorded', 'unit_minutes_recorded')):
            out.append(f'{cid}: unit cost and minutes recorded are true or false')
    return out


def prepare(local, kind, proposal, context=None):
    """Queue one G1 or G2 proposal for the next loop report. An undecided gate with the
    same id is replaced (its earlier version is kept beside it); a settled one never is."""
    if kind not in KINDS:
        raise ValueError('a gate is g1 or g2')
    wanted = ('strategy', 'plan') if kind == 'g1' else ('post', None)
    if (proposal.get('wall'), proposal.get('stage')) != wanted:
        raise ValueError(f'a {kind.upper()} gate is a {"plan behind strategy" if kind == "g1" else "post ask"}')
    errors = _context_errors(kind, proposal, context)
    if errors:
        raise ValueError('; '.join(errors))
    path = _path(local, proposal['proposal_id'])
    if path.exists():
        old = json.loads(path.read_text(encoding='utf-8'))
        if old.get('settled_at'):
            raise ValueError(f'{proposal["proposal_id"]} was already decided; a new ask needs a new matchday or week')
        if old['proposal'].get('payload_sha256') != proposal.get('payload_sha256'):
            atomic_json(path.with_name(path.stem + '.replaced-' + old['proposal']['payload_sha256'][:12] + '.json'), old)
    gate = {'kind': kind, 'proposal': proposal, 'context': context or {}, 'prepared_at': now(), 'settled_at': None}
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


def settle(local, decided):
    """Record Krish's answers to queued gates from one loop's classified decisions.
    Returns the verdict rows written. An approval on an older digest, or an unverified
    amendment, settles nothing: the gate stays on his list."""
    written = []
    for path, gate in _gates(local):
        if gate.get('settled_at'):
            continue
        pid = gate['proposal']['proposal_id']
        decision = _decision(pid, decided or {})
        if decision is None:
            continue
        at = now()
        if gate['kind'] == 'g2':
            for row in formats.g2_verdicts(gate['proposal']['exact_payload'], decision):
                context = gate['context'][row['creative_id']]
                written.append({**row, **{k: context[k] for k in CONTEXT}, 'prelive_checks_passed': True,
                                'decided_at': at, 'proposal_id': pid,
                                'payload_sha256': gate['proposal']['payload_sha256']})
        elif decision['decision'] == 'approved':
            signed = json.loads(decision['exact_payload'])
            target = Path(local) / 'specs' / (signed['run_id'].split(':', 1)[1] + '.signed.json')
            atomic_json(target, {'spec': signed, 'proposal_id': pid, 'amended': decision['amended'],
                                 'signed_at': at})
        gate['settled_at'] = at
        gate['decision'] = decision['decision']
        atomic_json(path, gate)
    if written:
        ledger = Path(local) / LEDGER
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger, 'a', encoding='utf-8', newline='\n') as out:
            for row in written:
                out.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
    return written


def verdicts(local):
    """Every verdict Krish has given, oldest first."""
    ledger = Path(local) / LEDGER
    if not ledger.is_file():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines() if line.strip()]
