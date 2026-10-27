"""The Phase 0 baseline for the 20x target (docs/ENGINE-V2.md, section 8).

Build and run are measured separately, from what this machine can see:
- build: git history in a repository (commits, merges, pull requests, first and
  last commit, active London days), and the build sessions' transcripts;
- run: GitHub Actions durations from an exported JSON file (completed successful
  runs only, timed from run_started_at where the export has it), and the run
  sessions' transcripts (orchestrator, production and review sessions);
- each transcript folder: Claude Code or Codex JSONL (files, model calls, input
  and output tokens, mean context per call, engine minutes from each transcript's
  first to last timestamp). Waiting minutes and outcomes are not in transcripts,
  so they are null with their reason; local/engine/sessions.jsonl records them.
Anything not measured is null with its reason and makes the whole result a lower
bound: with no reproduced run baseline there is no 20x claim. --sessions-dir is an
unsplit folder: counted, but never the run or build baseline. Standard library
only, no network. Writes JSON to --out (default local/baseline/<London date>.json)
and prints it.

  python3 scripts/baseline.py [--repo DIR] [--actions-json FILE] [--run-sessions-dir DIR]
                              [--build-sessions-dir DIR] [--sessions-dir DIR] [--out FILE]
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.clock import LONDON  # noqa: E402  (Windows has no zoneinfo data; this falls back to UK rules)
from engine.records import instant  # noqa: E402

NO_SESSIONS = 'session logs are not on this machine'
NO_ACTIONS = 'no Actions export was given (--actions-json)'
NO_FOLDER = 'no {} folder was given (--{}-sessions-dir)'
EMPTY_FOLDER = 'the {} folder given holds no .jsonl transcripts'
NO_WAITING = ('transcripts do not mark time spent waiting on Krish, so engine_minutes (first to last timestamp) '
              'includes it; local/engine/sessions.jsonl records waiting_minutes')
NO_OUTCOMES = 'transcripts do not record an outcome; local/engine/sessions.jsonl does'
CODEX_TYPES = ('session_meta', 'response_item', 'event_msg', 'turn_context')
PR_NUMBER = re.compile(r'(?:\(#(\d+)\)|Merge pull request #(\d+))')
TOKEN_KEYS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')


def _moment(value, where):
    """A strict RFC 3339 moment with its offset (engine.records.instant), the same on every Python."""
    try:
        return instant(value)
    except ValueError:
        raise ValueError(f'{where}: {value!r} is not an RFC 3339 date and time with its UTC offset')


def _iso(moment):
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def build_section(repo):
    """Commits, merges, pull requests and active days from git log in repo."""
    try:
        listing = subprocess.run(['git', '-C', str(repo), 'log', '--format=%H%x09%P%x09%cI%x09%s'],
                                 capture_output=True, text=True, encoding='utf-8', timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f'git log could not run in {repo}: {error}')
    if listing.returncode != 0:
        raise ValueError(f'git log failed in {repo}: {listing.stderr.strip() or "no history"}')
    commits, merges, numbers, days, moments = 0, 0, set(), set(), []
    for line in listing.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t', 3)
        if len(parts) < 3:
            raise ValueError(f'git log line is not readable: {line[:80]!r}')
        parents, subject = parts[1].split(), parts[3] if len(parts) > 3 else ''
        moment = _moment(parts[2], 'git log')
        commits += 1
        merges += len(parents) > 1
        for found in PR_NUMBER.finditer(subject):
            numbers.add(int(found.group(1) or found.group(2)))
        moments.append(moment)
        days.add(moment.astimezone(LONDON).date())
    if not commits:
        raise ValueError(f'{repo} has no commits')
    first, last = min(moments), max(moments)
    return {'commits': commits, 'merges': merges, 'pull_requests': len(numbers), 'first_commit_at': _iso(first),
            'last_commit_at': _iso(last), 'active_days': len(days),
            'span_days': (last.astimezone(LONDON).date() - first.astimezone(LONDON).date()).days + 1}


def run_section(path):
    """Count and mean seconds of completed, successful Actions runs. A run is timed from
    run_started_at when the export has it (so queue time and earlier attempts are left
    out), else from created_at, which includes queue time. Every run left out is counted
    by its reason."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path}: the Actions export is unreadable ({error})')
    if isinstance(data, dict) and isinstance(data.get('workflow_runs'), list):
        data = data['workflow_runs']
    if not isinstance(data, list):
        raise ValueError(f'{path}: must be a list of runs with created_at and updated_at')
    seconds, by_workflow, from_created = [], {}, 0
    excluded = {'not_completed': 0, 'not_successful': 0, 'rerun_without_run_started_at': 0}
    for i, run in enumerate(data):
        if not isinstance(run, dict) or 'created_at' not in run or 'updated_at' not in run:
            raise ValueError(f'{path}[{i}]: each run needs created_at and updated_at')
        started = run.get('run_started_at')
        start = _moment(started or run['created_at'], f'{path}[{i}].{"run_started_at" if started else "created_at"}')
        end = _moment(run['updated_at'], f'{path}[{i}].updated_at')
        if end < start:
            raise ValueError(f'{path}[{i}]: updated_at is before the run started')
        if run.get('status', 'completed') != 'completed':
            excluded['not_completed'] += 1
            continue
        if run.get('conclusion') != 'success':
            excluded['not_successful'] += 1
            continue
        if not started and type(run.get('run_attempt')) is int and run['run_attempt'] > 1:
            excluded['rerun_without_run_started_at'] += 1
            continue
        from_created += not started
        took = (end - start).total_seconds()
        seconds.append(took)
        name = run.get('workflow') or run.get('name')
        if isinstance(name, str) and name:
            by_workflow.setdefault(name, []).append(took)
    mean = round(sum(seconds) / len(seconds), 1) if seconds else None
    return {'count': len(seconds), 'mean_seconds': mean, 'total_seconds': round(sum(seconds), 1),
            'by_workflow': {name: {'count': len(values), 'mean_seconds': round(sum(values) / len(values), 1)}
                            for name, values in sorted(by_workflow.items())},
            'excluded': excluded, 'timed_from_created_at': from_created,
            'excludes': ('Only completed runs that concluded success count: in-progress, failed, cancelled and '
                         'skipped runs, and re-runs with no run_started_at, are left out. '
                         f'{from_created} of {len(seconds)} counted runs had no run_started_at, so their seconds '
                         'include queue time.')}


def _assistant(entry):
    """A model call: a Claude Code assistant line, or a Codex response item with the assistant role."""
    message = entry.get('message') if isinstance(entry.get('message'), dict) else {}
    payload = entry.get('payload') if isinstance(entry.get('payload'), dict) else {}
    return 'assistant' in (entry.get('type'), entry.get('role'), message.get('role'), payload.get('role'))


def _entries(path):
    """The JSON objects in one JSONL file and how many lines were not JSON. Lines split on
    '\n' only: splitlines() also breaks at U+2028 and U+0085 inside a transcript's text."""
    entries, unreadable = [], 0
    for line in path.read_text(encoding='utf-8', errors='replace').split('\n'):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries, unreadable


def _codex(entries):
    """(calls, calls with usage, token sums) from one Codex rollout. Its tokens are in
    event_msg token_count lines; total_token_usage is cumulative, so the last one counts
    and each rise in total_tokens is one model call. Codex input_tokens include the
    cached ones, which are moved to cache_read_input_tokens to match Claude's meaning."""
    totals, lasts, messages = [], [], 0
    for entry in entries:
        payload = entry.get('payload') if isinstance(entry.get('payload'), dict) else {}
        info = payload.get('info') if isinstance(payload.get('info'), dict) else None
        if entry.get('type') == 'event_msg' and payload.get('type') == 'token_count' and info:
            if isinstance(info.get('total_token_usage'), dict):
                totals.append(info['total_token_usage'])
            elif isinstance(info.get('last_token_usage'), dict):
                lasts.append(info['last_token_usage'])
        elif _assistant(entry):
            messages += 1

    def number(usage, key):
        value = usage.get(key)
        return value if type(value) is int and value >= 0 else 0
    if totals:
        steps = sorted({number(t, 'total_tokens') or number(t, 'input_tokens') + number(t, 'output_tokens')
                        for t in totals} - {0})
        used, calls = [max(totals, key=lambda t: number(t, 'total_tokens'))], max(len(steps), 1)
    else:
        used, calls = lasts, len(lasts)
    if not used:
        return messages, 0, None
    cached = sum(number(u, 'cached_input_tokens') for u in used)
    return calls, calls, {'input_tokens': sum(number(u, 'input_tokens') for u in used) - cached,
                          'output_tokens': sum(number(u, 'output_tokens') for u in used),
                          'cache_creation_input_tokens': 0, 'cache_read_input_tokens': cached}


def _minutes(entries):
    """Minutes from a transcript's first to last RFC 3339 timestamp, or None."""
    moments = []
    for entry in entries:
        try:
            moments.append(instant(entry.get('timestamp')))
        except ValueError:
            continue
    return (max(moments) - min(moments)).total_seconds() / 60 if moments else None


def sessions_section(folder):
    """Files, model calls, token sums and engine minutes from Claude Code and Codex JSONL
    transcripts, or None when there are none. Each gap that makes a sum a floor is named
    in lower_bound_reasons."""
    files = sorted(Path(folder).rglob('*.jsonl')) if folder and Path(folder).is_dir() else []
    if not files:
        return None
    calls, with_usage, unreadable, unrecognised, untimed, seen = 0, 0, 0, 0, 0, set()
    sums = {key: 0 for key in TOKEN_KEYS}
    spans = []
    for path in files:
        entries, bad = _entries(path)
        unreadable += bad
        span = _minutes(entries)
        if span is None:
            untimed += 1
        else:
            spans.append(span)
        if any(e.get('type') in CODEX_TYPES and isinstance(e.get('payload'), dict) for e in entries):
            made, priced, usage = _codex(entries)
            calls, with_usage = calls + made, with_usage + priced
            for key, value in (usage or {}).items():
                sums[key] += value
            unrecognised += not made
            continue
        found = 0
        for entry in entries:
            if not _assistant(entry):
                continue
            message = entry.get('message') if isinstance(entry.get('message'), dict) else {}
            ident = message.get('id')
            if isinstance(ident, str) and ident:
                # Claude Code writes one line per content block, each repeating the call's usage.
                if ident in seen:
                    continue
                seen.add(ident)
            calls += 1
            found += 1
            usage = message.get('usage') if isinstance(message.get('usage'), dict) else entry.get('usage')
            if not isinstance(usage, dict):
                continue
            for key in TOKEN_KEYS:
                value = usage.get(key)
                if type(value) is int and value >= 0:
                    sums[key] += value
                    with_usage += key == 'input_tokens'
        unrecognised += not found
    reasons = []
    if with_usage < calls:
        reasons.append(f'{calls - with_usage} of {calls} model calls carry no token usage, '
                       'so the token sums are a floor')
    if unrecognised:
        reasons.append(f'{unrecognised} of {len(files)} files hold no Claude or Codex model call')
    if unreadable:
        reasons.append(f'{unreadable} lines are not JSON')
    if untimed:
        reasons.append(f'{untimed} of {len(files)} files have no RFC 3339 timestamp, so engine_minutes is a floor')
    context = sums['input_tokens'] + sums['cache_creation_input_tokens'] + sums['cache_read_input_tokens']
    return {'files': len(files), 'assistant_calls': calls, 'calls_with_usage': with_usage,
            'input_tokens': sums['input_tokens'], 'output_tokens': sums['output_tokens'],
            'cache_creation_input_tokens': sums['cache_creation_input_tokens'],
            'cache_read_input_tokens': sums['cache_read_input_tokens'],
            'mean_context_tokens': round(sums['input_tokens'] / with_usage, 1) if with_usage else None,
            'mean_context_with_cache_tokens': round(context / with_usage, 1) if with_usage else None,
            'unreadable_lines': unreadable,
            'engine_minutes': round(sum(spans), 1) if spans else None,
            'engine_minutes_per_transcript': round(sum(spans) / len(spans), 1) if spans else None,
            'engine_minutes_reason': None if spans else 'no transcript line carries an RFC 3339 timestamp',
            'waiting_minutes': None, 'waiting_minutes_reason': NO_WAITING,
            'outcomes': None, 'outcomes_reason': NO_OUTCOMES,
            'lower_bound': bool(reasons), 'lower_bound_reasons': reasons}


def _transcripts(folder, label):
    """(section, reason) for one named transcript folder; the reason says why it is null."""
    if not folder:
        return None, NO_FOLDER.format(label, label)
    section = sessions_section(folder)
    return section, None if section is not None else EMPTY_FOLDER.format(label)


def measure(repo, actions_json=None, sessions_dir=None, now=None, run_sessions_dir=None, build_sessions_dir=None):
    """The baseline as a dict. Missing sections are null with their reason, never zero,
    and every reason the result is a floor is in lower_bound_reasons."""
    now = now or dt.datetime.now(dt.timezone.utc)
    sessions = sessions_section(sessions_dir)
    run_sessions, run_why = _transcripts(run_sessions_dir, 'run')
    build_sessions, build_why = _transcripts(build_sessions_dir, 'build')
    run = run_section(actions_json) if actions_json else None
    reasons = [why for why in (run_why, build_why) if why]
    reasons += [] if actions_json else [NO_ACTIONS]
    for name, section in (('run_sessions', run_sessions), ('build_sessions', build_sessions)):
        reasons += [f'{name}: {why}' for why in (section or {}).get('lower_bound_reasons', [])]
    return {'baseline_version': 2, 'measured_at': _iso(now), 'date': now.astimezone(LONDON).date().isoformat(),
            'repo': Path(repo).resolve().name, 'build': build_section(repo),
            'build_sessions': build_sessions, 'build_sessions_reason': build_why,
            'run': run, 'run_reason': None if actions_json else NO_ACTIONS,
            'run_sessions': run_sessions, 'run_sessions_reason': run_why,
            'sessions': sessions, 'sessions_reason': None if sessions is not None else NO_SESSIONS,
            'lower_bound': bool(reasons), 'lower_bound_reasons': reasons}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='baseline.py', description='Measure the Phase 0 baseline.')
    parser.add_argument('--repo', default=str(ROOT))
    parser.add_argument('--actions-json')
    parser.add_argument('--run-sessions-dir', help='transcripts of run sessions (orchestrator, production, review)')
    parser.add_argument('--build-sessions-dir', help='transcripts of build sessions (task cards, engine work)')
    parser.add_argument('--sessions-dir', help='an unsplit folder: counted, never the run or build baseline')
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    try:
        result = measure(args.repo, args.actions_json, args.sessions_dir,
                         run_sessions_dir=args.run_sessions_dir, build_sessions_dir=args.build_sessions_dir)
        out = Path(args.out) if args.out else ROOT / 'local' / 'baseline' / f'{result["date"]}.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
        out.write_text(text + '\n', encoding='utf-8')
    except (ValueError, OSError) as error:
        print('Not ready: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
    print(text)
    return result


if __name__ == '__main__':
    main()
