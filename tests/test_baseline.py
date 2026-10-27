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


def assistant(ident, tokens_in, tokens_out, **cache):
    usage = {'input_tokens': tokens_in, 'output_tokens': tokens_out, **cache}
    return json.dumps({'type': 'assistant', 'message': {'id': ident, 'role': 'assistant', 'usage': usage}})


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
        runs = [{'created_at': '2026-10-19T05:10:00Z', 'updated_at': '2026-10-19T05:10:14Z', 'workflow': 'Control Center'},
                {'created_at': '2026-10-20T05:10:00Z', 'updated_at': '2026-10-20T05:10:20Z', 'workflow': 'Control Center'},
                {'created_at': '2026-10-20T09:00:00Z', 'updated_at': '2026-10-20T09:02:00Z', 'workflow': 'check'}]
        path = self.root / 'runs.json'
        path.write_text(json.dumps(runs), encoding='utf-8')
        run = baseline.run_section(path)
        self.assertEqual((run['count'], run['mean_seconds'], run['total_seconds']), (3, 51.3, 154))
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
                                    'unreadable_lines': 1})
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
        self.assertEqual((result['date'], result['measured_at'], result['repo']),
                         ('2026-10-27', '2026-10-27T23:30:00Z', 'repo'))

    def test_main_writes_and_prints_the_json(self):
        sessions = self.root / 'logs'
        sessions.mkdir()
        (sessions / 's.jsonl').write_text(assistant('msg_9', 10, 5) + '\n', encoding='utf-8')
        runs = self.root / 'runs.json'
        runs.write_text(json.dumps([{'created_at': '2026-10-19T05:10:00Z', 'updated_at': '2026-10-19T05:10:10Z'}]),
                        encoding='utf-8')
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            result = baseline.main(['--repo', str(self.repo), '--actions-json', str(runs),
                                    '--sessions-dir', str(sessions), '--out', str(self.out)])
        self.assertEqual(json.loads(printed.getvalue()), result)
        self.assertEqual(json.loads(self.out.read_text(encoding='utf-8')), result)
        self.assertFalse(result['lower_bound'])
        self.assertIsNone(result['sessions_reason'])
        self.assertEqual(result['sessions']['assistant_calls'], 1)
        self.assertEqual(result['run']['count'], 1)
        self.assertEqual(result['build']['commits'], 4)

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
