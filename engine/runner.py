"""One cheap morning batch and one weekly review, with no outbound actions."""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import time

from . import policy
from .clock import LONDON
from .measurements import scorecard, validate_export
from .records import History, atomic_json, fingerprint, now


def constraints(gate, measures, state):
    """The current constraints in priority order, as (key, instruction). The
    morning batch and the clean-runner loop share this list, capped at three."""
    blockers = []
    if not gate['open']:
        blockers.append(('rail', 'Read the stored editorial verdicts for the newest drop; fix the refusal in a full-time session before another paid run.'))
    if measures['unique_completers']['status'] != 'measured':
        blockers.append(('measurement', 'Implement the aggregate completion and mature return queries in the existing source path; counts remain unknown.'))
    if policy.release_needed(state):
        blockers.append(('release', 'Public acquisition stays held until Krish makes the product release decision and a full-time session records it in its decision log.'))
    return blockers[:3]


def run(growth, mode, offline=False, observation_file=None, run_date=None):
    started = time.monotonic()
    today = dt.datetime.now(LONDON).date()
    day = dt.date.fromisoformat(run_date) if run_date else today
    if day != today:
        raise ValueError('operational runs use today in Europe/London; historical windows belong in observations')
    state = growth.load_state() if offline else growth.sync(quiet=True)
    if not state or not state.get('rules_ok'):
        raise ValueError('no verified source sync; run stops before producing a pack')
    age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(state['synced_at'])
    if age < dt.timedelta(minutes=-5) or age > dt.timedelta(hours=26):
        raise ValueError('source sync is stale or future-dated; refresh it before running')
    history = History(Path(growth.LOCAL) / 'engine')
    rows = history.read()['observations']
    if observation_file:
        incoming = validate_export(json.loads(Path(observation_file).read_text(encoding='utf-8')))
        with history.transaction() as journal:
            known = {fingerprint(x) for x in journal['observations']}
            journal['observations'] += [x for x in incoming if fingerprint(x) not in known]
        rows = history.read()['observations']
    end = today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=6) if mode == 'weekly' else end
    measures = scorecard(rows, start.isoformat(), end.isoformat())
    rail = state.get('rail')
    gate = growth.push_gate(rail, state)
    source = 'full-time ' + state['sha'][:10] + ', read ' + state['synced_at']
    items = [{'item_id': 'fulltime-' + key, 'platform': 'other', 'why': key,
              'text': text, 'estimated_minutes': 5} for key, text in constraints(gate, measures, state)]
    capture = now()
    run_key = f'fulltime:{today}:{mode}'
    usage = {'marketing_cash_gbp': 0, 'model_calls': 0, 'audio_generation_calls': 0,
             'model_spend_usd': 0, 'agent_spend_usd': None, 'hosting_spend_usd': None,
             'elapsed_seconds': round(time.monotonic() - started, 3)}
    raw_metrics = [row for row in rows if row['window_start'] == start.isoformat() and row['window_end'] == end.isoformat()]
    pack = {'schema_version': 2, 'policy_version': policy.VERSION, 'venture': 'fulltime',
            'pack_date': today.isoformat(), 'kind': 'report' if mode == 'weekly' else 'daily',
            'fulltime_sha': state['sha'], 'headline': 'Full Time: ' + ('OPEN' if gate['open'] else 'HOLD')
            + '; complete the current constraint before expanding acquisition',
            'items': items, 'source': source, 'run_id': run_key, 'metrics': raw_metrics}
    errors = growth.check_pack(pack, state)
    if errors:
        raise ValueError('generated pack failed validation: ' + '; '.join(errors))
    with contextlib.redirect_stdout(io.StringIO()):
        receipt = growth.store_pack(pack)
    week_start = today - dt.timedelta(days=today.weekday())
    native_review = {'product_slug': 'full-time', 'week_start': week_start.isoformat(),
                     'findings': {'headline': pack['headline'], 'source': source,
                                  'rail': gate['why'],
                                  'measurement': 'Completed and reachable listeners remain unknown.' if measures['reachable_completers']['status'] != 'measured'
                                  else 'Use the sourced scorecard and its complete observation window.',
                                  'delivery': 'Packs stay local; the run report reaches Control Center only through growth.py cc.'},
                     'kill_list': ['Keep personal social accounts, cold email and paid acquisition excluded.'],
                     'double_down': [item['text'] for item in items]}
    run_digest = fingerprint({'source_sha': state['sha'], 'rail': rail,
                              'observations': rows, 'policy': policy.VERSION})
    previous = history.read()['runs'].get(run_key)
    result = {'schema_version': 1, 'run_id': run_key, 'mode': mode, 'date': today.isoformat(),
              'source_sha': state['sha'], 'source_observed_at': state['synced_at'],
              'window': {'start': start.isoformat(), 'end': end.isoformat(), 'timezone': 'Europe/London'},
              'gate': gate, 'rail': rail, 'scorecard': measures, 'actions': items,
              'usage': usage, 'pack_receipt': receipt, 'native_weekly_review': native_review,
              'reporting_delivery': 'pending_handoff', 'input_digest': run_digest,
              'changed_since_same_run': not previous or previous['input_digest'] != run_digest,
              'finished_at': capture, 'offline': offline}
    with history.transaction() as journal:
        attempts = journal['runs'].get(run_key, {}).get('attempts', 0)
        journal['runs'][run_key] = {**result, 'attempts': attempts + 1}
    path = Path(growth.LOCAL) / 'runs' / (str(today) + '-' + mode + '.json')
    atomic_json(path, result)
    atomic_json(Path(growth.LOCAL) / 'outbox' / (str(today) + '-' + mode + '-review.json'), native_review)
    return {'run_id': run_key, 'gate': 'OPEN' if gate['open'] else 'HOLD',
            'actions': len(items), 'report': str(path), 'delivery': 'pending_handoff',
            'marketing_cash_gbp': 0, 'model_calls': 0,
            'changed_since_same_run': result['changed_since_same_run']}
