"""Commands for deterministic local execution and reviewable handoff exports."""
import argparse
import json
from pathlib import Path
import sys

from .records import History, atomic_json


def main(argv, growth):
    parser = argparse.ArgumentParser(prog='growth.py')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('mode', choices=['morning', 'weekly'])
    run.add_argument('--offline', action='store_true')
    run.add_argument('--require-existing-history', action='store_true')
    run.add_argument('--observations'); run.add_argument('--date')
    history = commands.add_parser('history')
    history.add_argument('--restore'); history.add_argument('--backups', action='store_true')
    creative = commands.add_parser('creative')
    creative.add_argument('id'); creative.add_argument('--status', choices=['published', 'skipped'])
    creative.add_argument('--url'); creative.add_argument('--human-confirmed', action='store_true')
    experiment = commands.add_parser('experiment')
    experiment.add_argument('operation', choices=['add', 'result', 'list'])
    experiment.add_argument('file', nargs='?'); experiment.add_argument('--id')
    metrics = commands.add_parser('metrics'); metrics.add_argument('file')
    export = commands.add_parser('export'); export.add_argument('--output')
    assets = commands.add_parser('assets')
    assets.add_argument('operation', choices=['fetch', 'render'])
    assets.add_argument('file', nargs='?'); assets.add_argument('--drop'); assets.add_argument('--pundit')
    args = parser.parse_args(argv)
    journal = History(Path(growth.LOCAL) / 'engine')
    try:
        if args.command == 'run':
            if args.require_existing_history and not journal.path.exists():
                raise ValueError('persistent history is unavailable; refusing to start a fresh scheduled ledger')
            from .runner import run
            result = run(growth, args.mode, args.offline, args.observations, args.date)
        elif args.command == 'history':
            if args.restore:
                journal.restore(args.restore)
                result = {'restored': True, 'history': str(journal.path)}
            elif args.backups:
                result = [str(p) for p in sorted((journal.root / 'backups').glob('*.json'))]
            else:
                result = journal.read()
        elif args.command == 'creative':
            if args.status:
                journal.mark(args.id, args.status, args.url, args.human_confirmed)
            result = journal.read()['creatives'].get(args.id)
            if result is None:
                raise ValueError('unknown creative ID')
        elif args.command == 'experiment':
            if args.operation != 'list' and not args.file:
                raise ValueError('an experiment definition or result file is required')
            if args.operation == 'add':
                journal.experiment(json.loads(Path(args.file).read_text()))
            if args.operation == 'result':
                journal.result(args.id, json.loads(Path(args.file).read_text()))
            result = journal.read()['experiments']
        elif args.command == 'metrics':
            from .measurements import validate_export
            rows = validate_export(json.loads(Path(args.file).read_text()))
            result = {'valid': True, 'observations': len(rows), 'imported': False}
        elif args.command == 'assets':
            from .assets import fetch, render
            if args.operation == 'fetch':
                if not args.drop or not args.pundit:
                    raise ValueError('fetch requires --drop and --pundit')
                result = fetch(growth, args.drop, args.pundit)
            else:
                if not args.file:
                    raise ValueError('render requires a manifest file')
                result = render(growth, Path(args.file))
        else:
            saved = journal.read()
            from .reporting import envelope
            reports = []
            for identifier, record in sorted(saved['packs'].items()):
                latest = next(x for x in record['revisions'] if x['digest'] == record['latest_digest'])
                reports.append(envelope(latest['pack'], {'id': identifier, 'digest': record['latest_digest']}))
            result = {'contract_version': 2, 'product_slug': 'full-time', 'delivery': 'pending_handoff',
                      'reports': reports, 'run_reports': list(saved['runs'].values()),
                      'creative_history': saved['creatives'], 'experiments': saved['experiments']}
            target = Path(args.output) if args.output else Path(growth.LOCAL) / 'handoff' / 'reporting-bundle.json'
            if Path(growth.LOCAL).resolve() not in target.resolve().parents:
                raise ValueError('exports must stay under ignored local/')
            atomic_json(target, result)
            result = {'export': str(target), 'reports': len(result['reports']), 'delivery': 'pending_handoff'}
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('Not ready: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
