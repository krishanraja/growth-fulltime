"""The Phase 0 baseline script: git, Actions and session sections, and the lower-bound mark.
A temporary git repository and synthetic JSONL only; nothing here writes into local/ or the network."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import growth

ROOT = Path(growth.HERE)
_spec = importlib.util.spec_from_file_location('baseline', ROOT / 'scripts' / 'baseline.py')
baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(baseline)

IDENTITY = ['-c', 'user.name=Synthetic Tester', '-c', 'user.email=krish@fulltime.fm', '-c', 'commit.gpgsign=false']


def git(repo, *args, when=None):
    env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'HOME': str(repo)}
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(['git', *IDENTITY, *args], cwd=repo, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()


def commit(repo, name, message, when):
    (Path(repo) / name).write_text(name + '\n', encoding='utf-8')
    git(repo, 'add', name)
    git(repo, 'commit', '-q', '-m', message, when=when)


def assistant(ident, tokens_in, tokens_out, timestamp=None, **cache):
    usage = {'input_tokens': tokens_in, 'output_tokens': tokens_out, **cache}
    line = {'type': 'assistant', 'message': {'id': ident, 'role': 'assistant', 'usage': usage}}
    if timestamp:
        line['timestamp'] = timestamp
    return json.dumps(line)


def codex_rollout(total_in, cached, total_out, start='2026-10-26T10:00:00Z', end='2026-10-26T10:30:00Z'):
    """A synthetic Codex rollout: tokens only in event_msg token_count lines, cumulative."""
    def count(at, tin, tout):
        usage = {'input_tokens': tin, 'cached_input_tokens': cached, 'output_tokens': tout,
                 'total_tokens': tin + tout}
        return {'timestamp': at, 'type': 'event_msg',
                'payload': {'type': 'token_count', 'info': {'total_token_usage': usage, 'last_token_usage': usage}}}
    lines = [{'timestamp': start, 'type': 'session_meta', 'payload': {'id': 'synthetic'}},
             {'timestamp': start, 'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant'}},
             count(start, total_in // 2, total_out // 2),
             count(end, total_in // 2, total_out // 2),            # the same total again, as rate-limit updates repeat it
             {'timestamp': end, 'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant'}},
             count(end, total_in, total_out)]
    return '\n'.join(json.dumps(line) for line in lines) + '\n'


def write(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding='utf-8')
    return folder


@unittest.skipUnless(shutil.which('git'), 'git is required')
class Baseline(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-q')
        commit(self.repo, 'a.txt', 'Start the engine', '2026-10-16T09:00:00+01:00')
        main = git(self.repo, 'rev-parse', '--abbrev-ref', 'HEAD')
        git(self.repo, 'checkout', '-q', '-b', 'feature')
        commit(self.repo, 'b.txt', 'Add the ledger', '2026-10-17T10:00:00+01:00')
        git(self.repo, 'checkout', '-q', main)
        git(self.repo, 'merge', '-q', '--no-ff', 'feature', '-m', 'Merge pull request #1 from synthetic/feature',
            when='2026-10-17T11:00:00+01:00')
        # 23:30 UTC on 26 October is still 26 October in London (GMT from 25 October).
        commit(self.repo, 'c.txt', 'Pin the dispatch model (#2)', '2026-10-26T23:30:00+00:00')
        self.out = self.root / 'out' / 'baseline.json'

    def tearDown(self):
        self.folder.cleanup()

    def test_build_counts_commits_merges_pull_requests_and_active_days(self):
        build = baseline.build_section(self.repo)
        self.assertEqual(build, {'commits': 4, 'merges': 1, 'pull_requests': 2,
                                 'first_commit_at': '2026-10-16T08:00:00Z', 'last_commit_at': '2026-10-26T23:30:00Z',
                                 'active_days': 3, 'span_days': 11})

    def test_build_refuses_a_folder_without_history(self):
        empty = self.root / 'empty'
        empty.mkdir()
        with self.assertRaises(ValueError):
            baseline.build_section(empty)

    def test_run_counts_actions_and_their_mean_seconds(self):
        # The fixture now names each run's conclusion: a run with none is no longer counted.
        runs = [{'created_at': '2026-10-19T05:10:00Z', 'updated_at': '2026-10-19T05:10:14Z', 'workflow': 'Control Center',
                 'conclusion': 'success'},
                {'created_at': '2026-10-20T05:10:00Z', 'updated_at': '2026-10-20T05:10:20Z', 'workflow': 'Control Center',
                 'conclusion': 'success', 'status': 'completed'},
                {'created_at': '2026-10-20T09:00:00Z', 'updated_at': '2026-10-20T09:02:00Z', 'workflow': 'check',
                 'conclusion': 'success'}]
        path = self.root / 'runs.json'
        path.write_text(json.dumps(runs), encoding='utf-8')
        run = baseline.run_section(path)
        self.assertEqual((run['count'], run['mean_seconds'], run['total_seconds']), (3, 51.3, 154))
        self.assertEqual(run['timed_from_created_at'], 3)
        self.assertIn('include queue time', run['excludes'])
        self.assertEqual(run['by_workflow'], {'Control Center': {'count': 2, 'mean_seconds': 17.0},
                                              'check': {'count': 1, 'mean_seconds': 120.0}})
        path.write_text(json.dumps({'workflow_runs': runs[:1]}), encoding='utf-8')
        self.assertEqual(baseline.run_section(path)['count'], 1)
        for bad in ([{'created_at': '2026-10-19T05:10:00Z'}],
                    [{'created_at': '2026-10-19T05:10:00Z', 'updated_at': '2026-10-19T05:09:00Z'}],
                    [{'created_at': '2026-10-19T05:10:00', 'updated_at': '2026-10-19T05:11:00Z'}],
                    {'runs': []}):
            path.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaises(ValueError):
                baseline.run_section(path)

    def test_sessions_sum_usage_once_per_call(self):
        folder = self.root / 'sessions' / 'project'
        folder.mkdir(parents=True)
        (folder / 'one.jsonl').write_text('\n'.join([
            json.dumps({'type': 'user', 'message': {'role': 'user', 'content': 'synthetic'}}),
            assistant('msg_1', 1000, 200, cache_read_input_tokens=5000),
            assistant('msg_1', 1000, 200, cache_read_input_tokens=5000),
            assistant('msg_2', 3000, 400),
            'not json at all',
            '']), encoding='utf-8')
        (folder / 'two.jsonl').write_text('\n'.join([
            json.dumps({'role': 'assistant', 'usage': {'input_tokens': 2000, 'output_tokens': 100}}),
            json.dumps({'type': 'assistant', 'message': {'id': 'msg_3', 'role': 'assistant'}})]), encoding='utf-8')
        (folder / 'notes.txt').write_text('ignored', encoding='utf-8')
        sessions = baseline.sessions_section(self.root / 'sessions')
        self.assertEqual(sessions, {'files': 2, 'assistant_calls': 4, 'calls_with_usage': 3,
                                    'input_tokens': 6000, 'output_tokens': 700,
                                    'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 5000,
                                    'mean_context_tokens': 2000.0, 'mean_context_with_cache_tokens': 3666.7,
                                    'unreadable_lines': 1, 'engine_minutes': None,
                                    'engine_minutes_per_transcript': None,
                                    'engine_minutes_reason': 'no transcript line carries an RFC 3339 timestamp',
                                    'waiting_minutes': None, 'waiting_minutes_reason': baseline.NO_WAITING,
                                    'outcomes': None, 'outcomes_reason': baseline.NO_OUTCOMES, 'lower_bound': True,
                                    'lower_bound_reasons': [
                                        '1 of 4 model calls carry no token usage, so the token sums are a floor',
                                        '1 lines are not JSON',
                                        '2 of 2 files have no RFC 3339 timestamp, so engine_minutes is a floor']})
        self.assertIsNone(baseline.sessions_section(self.root / 'nowhere'))
        self.assertIsNone(baseline.sessions_section(None))

    def test_without_session_logs_the_result_is_a_lower_bound(self):
        moment = dt.datetime(2026, 10, 27, 23, 30, tzinfo=dt.timezone.utc)
        result = baseline.measure(self.repo, now=moment)
        self.assertIsNone(result['sessions'])
        self.assertEqual(result['sessions_reason'], 'session logs are not on this machine')
        self.assertTrue(result['lower_bound'])
        self.assertIsNone(result['run'])
        self.assertIn('--actions-json', result['run_reason'])
        self.assertIsNone(result['run_sessions'])
        self.assertIsNone(result['build_sessions'])
        self.assertEqual(result['lower_bound_reasons'], [
            'no run folder was given (--run-sessions-dir)', 'no build folder was given (--build-sessions-dir)',
            'no Actions export was given (--actions-json)'])
        self.assertEqual((result['date'], result['measured_at'], result['repo']),
                         ('2026-10-27', '2026-10-27T23:30:00Z', 'repo'))

    def test_main_writes_and_prints_the_json(self):
        # Was one unsplit --sessions-dir reported as not a lower bound; run and build are now separate folders.
        run_logs = write(self.root / 'run-logs', 's.jsonl',
                         assistant('msg_9', 10, 5, '2026-10-26T10:00:00Z') + '\n'
                         + assistant('msg_10', 20, 5, '2026-10-26T10:06:00.250Z') + '\n')
        build_logs = write(self.root / 'build-logs', 'b.jsonl', assistant('msg_11', 900, 50, '2026-10-26T11:00:00Z')
                           + '\n' + assistant('msg_12', 100, 50, '2026-10-26T11:30:00Z') + '\n')
        runs = self.root / 'runs.json'
        runs.write_text(json.dumps([{'created_at': '2026-10-19T05:10:00Z', 'updated_at': '2026-10-19T05:10:10Z',
                                     'conclusion': 'success'}]), encoding='utf-8')
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            result = baseline.main(['--repo', str(self.repo), '--actions-json', str(runs),
                                    '--run-sessions-dir', str(run_logs), '--build-sessions-dir', str(build_logs),
                                    '--out', str(self.out)])
        self.assertEqual(json.loads(printed.getvalue()), result)
        self.assertEqual(json.loads(self.out.read_text(encoding='utf-8')), result)
        self.assertFalse(result['lower_bound'], result['lower_bound_reasons'])
        self.assertEqual((result['run_sessions']['input_tokens'], result['run_sessions']['engine_minutes']), (30, 6.0))
        self.assertEqual((result['build_sessions']['input_tokens'], result['build_sessions']['engine_minutes']),
                         (1000, 30.0))
        self.assertIsNone(result['sessions'])
        self.assertEqual(result['run']['count'], 1)
        self.assertEqual(result['build']['commits'], 4)

    def test_an_unsplit_folder_is_never_the_run_baseline(self):
        logs = write(self.root / 'logs', 's.jsonl', assistant('msg_9', 10, 5, '2026-10-26T10:00:00Z') + '\n')
        result = baseline.measure(self.repo, None, logs, dt.datetime(2026, 10, 27, tzinfo=dt.timezone.utc))
        self.assertEqual(result['sessions']['input_tokens'], 10)
        self.assertTrue(result['lower_bound'])
        self.assertIn('no run folder was given (--run-sessions-dir)', result['lower_bound_reasons'])

    def test_run_and_build_transcripts_are_counted_apart(self):
        run_logs = write(self.root / 'run', 'r.jsonl', assistant('msg_r', 700, 70, '2026-10-26T09:00:00Z') + '\n')
        build_logs = write(self.root / 'build', 'b.jsonl', assistant('msg_b', 5000, 500, '2026-10-26T09:00:00Z') + '\n')
        result = baseline.measure(self.repo, now=dt.datetime(2026, 10, 27, tzinfo=dt.timezone.utc),
                                  run_sessions_dir=run_logs, build_sessions_dir=build_logs)
        self.assertEqual((result['run_sessions']['input_tokens'], result['build_sessions']['input_tokens']), (700, 5000))
        self.assertEqual(result['run_sessions']['engine_minutes'], 0)
        missing = baseline.measure(self.repo, now=dt.datetime(2026, 10, 27, tzinfo=dt.timezone.utc),
                                   build_sessions_dir=build_logs, run_sessions_dir=self.root / 'empty-run')
        self.assertIsNone(missing['run_sessions'])
        self.assertEqual(missing['run_sessions_reason'], 'the run folder given holds no .jsonl transcripts')
        self.assertTrue(missing['lower_bound'])

    def test_codex_rollouts_report_their_tokens_and_minutes(self):
        # Before the fix a Codex rollout counted 0 tokens and was not marked a lower bound.
        logs = write(self.root / 'codex', 'rollout-1.jsonl', codex_rollout(80000, 20000, 10000))
        write(logs, 'claude.jsonl', assistant('msg_1', 500, 50, '2026-10-26T12:00:00Z') + '\n')
        sessions = baseline.sessions_section(logs)
        self.assertEqual((sessions['input_tokens'], sessions['cache_read_input_tokens'], sessions['output_tokens']),
                         (60500, 20000, 10050))
        self.assertEqual((sessions['assistant_calls'], sessions['calls_with_usage']), (3, 3))
        self.assertEqual(sessions['engine_minutes'], 30.0)
        self.assertFalse(sessions['lower_bound'], sessions['lower_bound_reasons'])

    def test_files_with_no_model_calls_or_no_usage_are_a_lower_bound(self):
        ledger = json.dumps({'kind': 'orchestrator', 'started_at': '2026-10-27T09:00:00Z', 'tokens_in': 1000})
        only = baseline.sessions_section(write(self.root / 'ledger', 'sessions.jsonl', ledger + '\n'))
        self.assertEqual(only['input_tokens'], 0)
        self.assertTrue(only['lower_bound'])
        self.assertIn('1 of 1 files hold no Claude or Codex model call', only['lower_bound_reasons'])
        bare = json.dumps({'timestamp': '2026-10-26T10:00:00Z', 'type': 'response_item',
                           'payload': {'type': 'message', 'role': 'assistant'}})
        codex = baseline.sessions_section(write(self.root / 'bare', 'rollout.jsonl', bare + '\n'))
        self.assertEqual((codex['assistant_calls'], codex['calls_with_usage']), (1, 0))
        self.assertTrue(codex['lower_bound'])

    def test_a_line_separator_inside_a_transcript_never_splits_its_line(self):
        line = json.loads(assistant('msg_1', 400, 40, '2026-10-26T10:00:00Z'))
        line['message']['content'] = 'said\u2028then\x85more'
        logs = write(self.root / 'sep', 's.jsonl', json.dumps(line, ensure_ascii=False) + '\n')
        sessions = baseline.sessions_section(logs)
        self.assertEqual((sessions['input_tokens'], sessions['unreadable_lines']), (400, 0))

    def test_actions_count_only_completed_successful_runs_from_their_start(self):
        runs = [{'workflow': 'check.yml', 'created_at': '2026-10-20T10:00:00Z', 'updated_at': '2026-10-20T10:03:00Z',
                 'conclusion': 'success'},
                {'workflow': 'check.yml', 'created_at': '2026-10-20T11:00:00Z', 'updated_at': '2026-10-23T11:03:00Z',
                 'conclusion': 'success', 'run_attempt': 2, 'run_started_at': '2026-10-23T11:00:00Z'},
                {'workflow': 'check.yml', 'created_at': '2026-10-20T12:00:00Z', 'updated_at': '2026-10-20T12:01:30Z',
                 'conclusion': None, 'status': 'in_progress'},
                {'workflow': 'check.yml', 'created_at': '2026-10-20T13:00:00Z', 'updated_at': '2026-10-20T13:21:40Z',
                 'conclusion': 'cancelled', 'status': 'completed'},
                {'workflow': 'check.yml', 'created_at': '2026-10-20T14:00:00Z', 'updated_at': '2026-10-20T14:02:00Z',
                 'conclusion': 'failure'},
                {'workflow': 'check.yml', 'created_at': '2026-10-20T15:00:00Z', 'updated_at': '2026-10-22T15:03:00Z',
                 'conclusion': 'success', 'run_attempt': 2},
                {'workflow': 'check.yml', 'created_at': '2026-10-20T16:00:00Z', 'updated_at': '2026-10-20T16:03:00Z'}]
        path = self.root / 'runs.json'
        path.write_text(json.dumps(runs), encoding='utf-8')
        run = baseline.run_section(path)
        self.assertEqual((run['count'], run['mean_seconds']), (2, 180.0))
        self.assertEqual(run['excluded'], {'not_completed': 1, 'not_successful': 3, 'rerun_without_run_started_at': 1})
        self.assertEqual(run['timed_from_created_at'], 1)
        for words in ('in-progress, failed, cancelled', 're-runs with no run_started_at', '1 of 2 counted runs'):
            self.assertIn(words, run['excludes'])
        runs[1]['run_started_at'] = '2026-10-23 11:00:00'
        path.write_text(json.dumps(runs), encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            baseline.run_section(path)
        self.assertIn('run_started_at', str(caught.exception))

    def test_main_refuses_in_plain_words(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                baseline.main(['--repo', str(self.root / 'missing'), '--out', str(self.out)])
        self.assertEqual(caught.exception.code, 1)
        self.assertIn('Not ready: ', errors.getvalue())
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
