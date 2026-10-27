"""Commands for deterministic local execution, private exports and the Control Center loop."""
import argparse
import json
from pathlib import Path
import sys

from .records import History, atomic_json

V2 = ('spec', 'formats', 'pack', 'buffer', 'library', 'session', 'dispatch', 'audience')


def _json(path):
    """A JSON file read as UTF-8 (R35), refusing NaN and Infinity."""
    def refuse(constant):
        raise ValueError(f'{path}: {constant} is not a number')
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=refuse)


def _add_v2(commands):
    """Engine v2 verbs: each checks or prepares, offline-first, and none posts, sends or spends."""
    spec = commands.add_parser('spec', help='check, digest, compile or prepare the weekly campaign spec (G1)')
    spec.add_argument('operation', choices=['check', 'digest', 'compile', 'propose'])
    spec.add_argument('file'); spec.add_argument('--gates'); spec.add_argument('--expires-at')
    formats = commands.add_parser('formats', help='the format registry and readiness computed from verdicts')
    formats.add_argument('operation', choices=['list', 'readiness'])
    formats.add_argument('--verdicts'); formats.add_argument('--spec')
    formats.add_argument('--format'); formats.add_argument('--lock', default='unlocked')
    pack = commands.add_parser('pack', help='check or prepare one matchday pack (G2)')
    pack.add_argument('operation', choices=['check', 'propose'])
    pack.add_argument('file'); pack.add_argument('--offline', action='store_true')
    pack.add_argument('--expires-at')
    buffer = commands.add_parser('buffer', help='read-only Buffer receipts for the Full Time allowlist')
    buffer.add_argument('operation', choices=['query', 'receipts'])
    buffer.add_argument('--posts'); buffer.add_argument('--pack')
    library = commands.add_parser('library', help='the Growth Build library: names, reconcile, bundles')
    library.add_argument('operation', choices=['name', 'reconcile', 'bundle', 'assemble'])
    library.add_argument('paths', nargs='*'); library.add_argument('--index'); library.add_argument('--out')
    library.add_argument('--parts'); library.add_argument('--created-on')
    session = commands.add_parser('session', help='the 36 KB pack a fresh session starts from, and the ledger')
    session.add_argument('operation', choices=['pack', 'minutes'])
    session.add_argument('--kind'); session.add_argument('--crew', default='')
    session.add_argument('--spec'); session.add_argument('--check', action='store_true')
    session.add_argument('--date')
    dispatch = commands.add_parser('dispatch', help='check a task card and print, never run, its Codex command')
    dispatch.add_argument('card'); dispatch.add_argument('--plugin-root', required=True)
    dispatch.add_argument('--reading'); dispatch.add_argument('--spend-decision')
    audience = commands.add_parser('audience', help='brand-profile visibility: action rulings, the daily plan, followers')
    audience.add_argument('operation', choices=['actions', 'plan', 'followers'])
    audience.add_argument('--minutes', type=float, default=10)


def _rail(growth, offline):
    """Product Truth at pack time: the live rail unless offline, when the synced copy is
    used and Today counts as not live, so a match ad fails closed."""
    state = growth.load_state() or {}
    if offline:
        return state, False, 'synced'
    rail = growth.read_rail()
    return {**state, 'rail': rail}, any(m.get('pundits') for m in rail), 'live'


def _run_v2(args, growth):
    if args.command == 'spec':
        from . import spec
        data = spec.load(args.file)
        if args.operation == 'check':
            errors = spec.validate(data)
            if errors:
                raise ValueError('the spec is refused: ' + '; '.join(errors))
            return {'valid': True, 'run_id': data['run_id'], 'payload_sha256': spec.digest(data)}
        if args.operation == 'digest':
            errors = spec.validate(data)
            if errors:
                raise ValueError('the spec is refused: ' + '; '.join(errors))
            return {'payload_sha256': spec.digest(data)}
        if args.operation == 'compile':
            return spec.compile(data, _json(args.gates) if args.gates else {})
        if not args.expires_at:
            raise ValueError('propose needs --expires-at, an ISO date and time with its UTC offset')
        return {'prepared': True, 'sent': False, 'proposal': spec.proposal(data, args.expires_at)}
    if args.command == 'formats':
        from . import formats
        if args.operation == 'list':
            return {key: {'title': r['title'], 'links_to': r['links_to'],
                          'published_pundits_min': r['published_pundits_min'],
                          'creative_system_format': r['creative_system_format']}
                    for key, r in formats.load_registry().items()}
        if not args.verdicts:
            raise ValueError('readiness needs --verdicts, a JSON list of Krish\'s verdicts')
        verdicts = _json(args.verdicts)
        verdicts = verdicts.get('verdicts') if isinstance(verdicts, dict) else verdicts
        if args.spec:
            from . import spec
            campaign = spec.load(args.spec)
            return {item['format_id']: formats.readiness(verdicts, item['format_id'], item['lock_version'])
                    for item in campaign.get('formats') or []}
        if not args.format:
            raise ValueError('readiness needs --format or --spec')
        return formats.readiness(verdicts, args.format, args.lock)
    if args.command == 'pack':
        from . import buffer_read, pack
        data = _json(args.file)
        state, today_live, source = _rail(growth, args.offline)
        allowlist = buffer_read.load_allowlist(growth.LOCAL)
        errors = pack.check(data, state, allowlist, today_live)
        if errors:
            raise ValueError(f'the matchday pack is refused (rail {source}): ' + '; '.join(errors))
        if args.operation == 'check':
            return {'ok': True, 'items': len(data['items']), 'rail': source, 'today_live': today_live}
        return {'prepared': True, 'sent': False, 'proposal': pack.proposal(data, args.expires_at)}
    if args.command == 'buffer':
        from . import buffer_read
        allowlist = buffer_read.load_allowlist(growth.LOCAL)
        if args.operation == 'query':
            return {'list_posts': buffer_read.query(allowlist)}
        if not args.posts or not args.pack:
            raise ValueError('receipts needs --posts (what list_posts returned) and --pack')
        posts = _json(args.posts)
        posts = posts.get('posts') if isinstance(posts, dict) else posts
        return {'receipts': buffer_read.receipts(posts, _json(args.pack), allowlist)}
    if args.command == 'session':
        from . import session, spec
        if args.operation == 'minutes':
            if not args.date:
                raise ValueError('minutes needs --date YYYY-MM-DD')
            ledger = Path(growth.LOCAL) / 'engine' / 'sessions.jsonl'
            return {'date': args.date, 'krish_minutes': session.krish_minutes_on(ledger, args.date),
                    'over_budget': session.budget_errors(ledger, args.date)}
        if not args.kind:
            raise ValueError('pack needs --kind')
        crew = [name for name in args.crew.split(',') if name]
        text = session.pack(args.kind, Path(growth.HERE) / 'crew', crew,
                            spec=spec.load(args.spec) if args.spec else None)
        size = len(text.encode('utf-8'))
        return {'kind': args.kind, 'bytes': size, 'limit': session.PACK_LIMIT} if args.check else text
    if args.command == 'dispatch':
        import datetime as dt
        from . import dispatch
        card = _json(args.card)
        errors = dispatch.validate_card(card)
        if errors:
            raise ValueError('the card is refused: ' + '; '.join(errors))
        dispatch.guard(card, _json(args.reading) if args.reading else None,
                       dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                       _json(args.spend_decision) if args.spend_decision else None)
        prompt = Path(growth.LOCAL) / 'dispatch' / (card['card_id'] + '.md')
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(f'# Task card {card["card_id"]}\n\nDo exactly what this card says, inside its write_allow, '
                          'and nothing on its never list. Finish with the return shape it names.\n\n```json\n'
                          + json.dumps(card, indent=2, ensure_ascii=False) + '\n```\n', encoding='utf-8')
        return {'run_this': dispatch.command(card, args.plugin_root, prompt), 'prompt_file': str(prompt),
                'note': 'Printed, not run. Claude reruns the acceptance commands and checks the diff afterwards.'}
    if args.command == 'audience':
        from . import audience
        if args.operation == 'actions':
            registry = audience.load_actions()
            return {key: {'status': row['status'], 'platforms': row['platforms']}
                    for key, row in registry['actions'].items()}
        folder = Path(growth.LOCAL) / 'audience'

        def mine(name):
            path = folder / name
            return _json(path) if path.exists() else []
        if args.operation == 'followers':
            return audience.followers_check(mine('readings.json'))
        from . import buffer_read
        try:
            allowlist = buffer_read.load_allowlist(growth.LOCAL)
        except ValueError:
            allowlist = None            # no allowlist: nothing is automated, every item is Krish's
        return audience.daily_plan(mine('profiles.json') or {}, mine('performance.json'), mine('trends.json'),
                                   budget_minutes=args.minutes, allowlist=allowlist)
    from . import library
    if args.operation == 'name':
        return {path: library.name_errors(path) for path in args.paths}
    if args.operation == 'reconcile':
        document = _json(args.paths[0]) if len(args.paths) == 1 else None
        rows = (library.read_index(Path(args.index).read_text(encoding='utf-8')) if args.index
                else document.get('index') if isinstance(document, dict) else None)
        if document is None or rows is None:
            raise ValueError('reconcile needs one listing file and --index INDEX.csv (or a listing that holds its index)')
        listing = document.get('listing') if isinstance(document, dict) else document
        result = library.reconcile(listing, rows)
        return {**result, 'hold': library.hold(result)}
    if args.operation == 'bundle':
        if not args.paths or not args.out or not args.created_on:
            raise ValueError('bundle needs files, --out and --created-on YYYY-MM-DD')
        name, parts = library.bundle(args.paths, args.out, created_on=args.created_on)
        return {'bundle': name, 'parts': parts}
    if len(args.paths) != 1 or not args.parts or not args.out:
        raise ValueError('assemble needs one manifest, --parts DIR and --out DIR')
    return library.assemble(_json(args.paths[0]), args.parts, args.out)


def main(argv, growth):
    if argv[:1] == ['ga4']:
        from .ga4 import main as ga4
        code = ga4(argv[1:], growth)
        if code:
            raise SystemExit(code)
        return
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
    cc = commands.add_parser('cc', help='run the Control Center protocol loop')
    cc.add_argument('target', choices=['morning', 'weekly', 'dispatch'])
    cc.add_argument('--offline', action='store_true')
    cc.add_argument('--require-existing-history', action='store_true')
    cc.add_argument('--observations')
    cc.add_argument('--synthetic', action='store_true')
    _add_v2(commands)
    args = parser.parse_args(argv)
    journal = History(Path(growth.LOCAL) / 'engine')
    try:
        if args.command == 'cc':
            from .control_center import main as loop
            summary, code = loop(args, growth)
            print(json.dumps(summary, indent=2, allow_nan=False))
            if code:
                raise SystemExit(code)
            return
        if args.command in V2:
            result = _run_v2(args, growth)
            print(result if isinstance(result, str) else json.dumps(result, indent=2, allow_nan=False))
            return
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
                journal.experiment(_json(args.file))
            if args.operation == 'result':
                journal.result(args.id, _json(args.file))
            result = journal.read()['experiments']
        elif args.command == 'metrics':
            from .measurements import validate_export
            rows = validate_export(_json(args.file))
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
