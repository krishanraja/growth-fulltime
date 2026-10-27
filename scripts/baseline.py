"""The Phase 0 baseline for the 20x target (docs/ENGINE-V2.md, section 8).

Build and run are measured separately, from what this machine can see:
- build: git history in a repository (commits, merges, pull requests, first and
  last commit, active London days);
- run: GitHub Actions run timestamps from an exported JSON file (count and mean
  seconds, overall and per workflow);
- sessions: Claude Code or Codex JSONL transcripts (files, assistant calls, input
  and output tokens, mean context per call).
When the transcripts are not on this machine, sessions is null with its reason and
the whole result is a lower bound: with no reproduced baseline there is no 20x claim.
Standard library only, no network. Writes JSON to --out (default
local/baseline/<London date>.json) and prints it.

  python3 scripts/baseline.py [--repo DIR] [--actions-json FILE] [--sessions-dir DIR] [--out FILE]
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LONDON = ZoneInfo('Europe/London')
NO_SESSIONS = 'session logs are not on this machine'
NO_ACTIONS = 'no Actions export was given (--actions-json)'
PR_NUMBER = re.compile(r'(?:\(#(\d+)\)|Merge pull request #(\d+))')
TOKEN_KEYS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')


def _moment(value, where):
    try:
        moment = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f'{where}: {value!r} is not an ISO date and time')
    if moment.tzinfo is None:
        raise ValueError(f'{where}: {value!r} has no UTC offset')
    return moment


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
    """Count and mean seconds of Actions runs from a list of {created_at, updated_at}."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path}: the Actions export is unreadable ({error})')
    if isinstance(data, dict) and isinstance(data.get('workflow_runs'), list):
        data = data['workflow_runs']
    if not isinstance(data, list):
        raise ValueError(f'{path}: must be a list of runs with created_at and updated_at')
    seconds, by_workflow = [], {}
    for i, run in enumerate(data):
        if not isinstance(run, dict) or 'created_at' not in run or 'updated_at' not in run:
            raise ValueError(f'{path}[{i}]: each run needs created_at and updated_at')
        start = _moment(run['created_at'], f'{path}[{i}].created_at')
        end = _moment(run['updated_at'], f'{path}[{i}].updated_at')
        if end < start:
            raise ValueError(f'{path}[{i}]: updated_at is before created_at')
        took = (end - start).total_seconds()
        seconds.append(took)
        name = run.get('workflow') or run.get('name')
        if isinstance(name, str) and name:
            by_workflow.setdefault(name, []).append(took)
    mean = round(sum(seconds) / len(seconds), 1) if seconds else None
    return {'count': len(seconds), 'mean_seconds': mean, 'total_seconds': round(sum(seconds), 1),
            'by_workflow': {name: {'count': len(values), 'mean_seconds': round(sum(values) / len(values), 1)}
                            for name, values in sorted(by_workflow.items())}}


def _assistant(entry):
    """A model call: a Claude Code assistant line, or a Codex response item with the assistant role."""
    message = entry.get('message') if isinstance(entry.get('message'), dict) else {}
    payload = entry.get('payload') if isinstance(entry.get('payload'), dict) else {}
    return 'assistant' in (entry.get('type'), entry.get('role'), message.get('role'), payload.get('role'))


def sessions_section(folder):
    """Files, assistant calls and token sums from JSONL transcripts, or None when there are none."""
    files = sorted(Path(folder).rglob('*.jsonl')) if folder and Path(folder).is_dir() else []
    if not files:
        return None
    calls, unreadable, seen = 0, 0, set()
    sums = {key: 0 for key in TOKEN_KEYS}
    with_input = 0
    for path in files:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                unreadable += 1
                continue
            if not isinstance(entry, dict) or not _assistant(entry):
                continue
            message = entry.get('message') if isinstance(entry.get('message'), dict) else {}
            ident = message.get('id')
            if isinstance(ident, str) and ident:
                # Claude Code writes one line per content block, each repeating the call's usage.
                if ident in seen:
                    continue
                seen.add(ident)
            calls += 1
            usage = message.get('usage') if isinstance(message.get('usage'), dict) else entry.get('usage')
            if not isinstance(usage, dict):
                continue
            for key in TOKEN_KEYS:
                value = usage.get(key)
                if type(value) is int and value >= 0:
                    sums[key] += value
                    with_input += key == 'input_tokens'
    context = sums['input_tokens'] + sums['cache_creation_input_tokens'] + sums['cache_read_input_tokens']
    return {'files': len(files), 'assistant_calls': calls, 'calls_with_usage': with_input,
            'input_tokens': sums['input_tokens'], 'output_tokens': sums['output_tokens'],
            'cache_creation_input_tokens': sums['cache_creation_input_tokens'],
            'cache_read_input_tokens': sums['cache_read_input_tokens'],
            'mean_context_tokens': round(sums['input_tokens'] / with_input, 1) if with_input else None,
            'mean_context_with_cache_tokens': round(context / with_input, 1) if with_input else None,
            'unreadable_lines': unreadable}


def measure(repo, actions_json=None, sessions_dir=None, now=None):
    """The baseline as a dict. Missing sections are null with their reason, never zero."""
    now = now or dt.datetime.now(dt.timezone.utc)
    sessions = sessions_section(sessions_dir)
    return {'baseline_version': 1, 'measured_at': _iso(now), 'date': now.astimezone(LONDON).date().isoformat(),
            'repo': Path(repo).resolve().name, 'build': build_section(repo),
            'run': run_section(actions_json) if actions_json else None,
            'run_reason': None if actions_json else NO_ACTIONS,
            'sessions': sessions, 'sessions_reason': None if sessions is not None else NO_SESSIONS,
            'lower_bound': sessions is None}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='baseline.py', description='Measure the Phase 0 baseline.')
    parser.add_argument('--repo', default=str(ROOT))
    parser.add_argument('--actions-json')
    parser.add_argument('--sessions-dir')
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    try:
        result = measure(args.repo, args.actions_json, args.sessions_dir)
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
