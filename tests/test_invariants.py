"""The invariant registry (docs/ENGINE-V2.md, section 4), and the tests that rules from
the failure history had no test for until now. Synthetic fixtures in temporary folders
only; nothing here writes into the repository or reads the network."""
import ast
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import growth
from engine import formats, invariants, measurements
from engine.clock import LONDON
from scripts import verify_repository as verify

ROOT = Path(growth.HERE)
REGISTER = ROOT / 'docs' / 'FAILURE-REGISTER.md'
WORKFLOWS = ROOT / '.github' / 'workflows'
REQUIRED = ([f'R{n:02d}' for n in range(1, 51)] + [f'DOC{n:02d}' for n in range(1, 23)]
            + ['GG0', 'GG0.5', 'GG1', 'GG2', 'GG3', 'GG4', 'GG5'] + [f'LIB{n}' for n in range(1, 10)]
            + ['INV-NO-WRITE', 'INV-BUFFER-ALLOWLIST', 'INV-NO-PERSONAL-POSTS', 'INV-MEDIA-HASH',
               'INV-ONE-ASK', 'INV-READINESS-COMPUTED', 'INV-GA4-NOT-LISTENERS', 'INV-GA4-FROM-CONTROL-CENTER'])
KEPT = ('R02', 'R05', 'R06', 'R07', 'R09', 'R13', 'R14', 'R15', 'R18', 'R20', 'R22', 'R23', 'R25', 'R26',
        'R27', 'R36', 'R37', 'R38', 'R39', 'R40')
NOT_HERE = ('R08', 'R11', 'R12', 'R16', 'R17')
HUMAN = ('DOC15',)
PROBE = 'ftprobe_planted'
PROBE_ID = re.compile(r'^ftprobe_planted\.Probe\.test_[a-z_]+$')


def entry(eid='R01', **change):
    base = {'id': eid, 'rule': 'A planted rule.', 'origin': eid, 'status': 'enforced',
            'enforced_by': 'engine.pack.check', 'test': 'tests.test_invariants.CheckTests.test_never_runs_itself',
            'remains': None}
    base.update(change)
    return base


def registry(folder, entries, **top):
    data = {'_about': 'A synthetic registry.', 'schema_version': 1, 'entries': entries}
    data.update(top)
    path = Path(folder) / 'registry.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def has(errors, words):
    return any(words in e for e in errors)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.entries = {e['id']: e for e in invariants.load()}

    def test_every_required_item_is_filed(self):
        missing = [eid for eid in REQUIRED if eid not in self.entries]
        self.assertEqual(missing, [])

    def test_every_test_exists_and_every_path_resolves(self):
        result = invariants.check(run_tests=False)
        self.assertEqual(result['missing_tests'], [])
        self.assertEqual(result['unresolved'], [])
        self.assertTrue(result['ok'])
        self.assertEqual(result['entries'], len(self.entries))
        self.assertEqual(result['ran'], 0)

    def test_kept_regressions_stay_enforced(self):
        for eid in KEPT:
            with self.subTest(eid=eid):
                self.assertEqual(self.entries[eid]['status'], 'enforced')

    def test_product_and_owner_items_are_not_claimed_as_enforced(self):
        for eid in NOT_HERE:
            with self.subTest(eid=eid):
                self.assertIn(self.entries[eid]['status'], ('product_item', 'owner_item'))
                self.assertTrue(self.entries[eid]['remains'])
        for eid in HUMAN:
            self.assertEqual(self.entries[eid]['status'], 'human_judgment')

    def test_an_open_entry_says_what_remains(self):
        for eid, item in self.entries.items():
            if item['status'] != 'enforced':
                with self.subTest(eid=eid):
                    self.assertTrue(item['remains'])

    def test_the_register_lists_every_entry_in_plain_uk_english(self):
        text = REGISTER.read_text(encoding='utf-8')
        self.assertNotIn('\u2014', text)
        rows = [line for line in text.splitlines() if line.startswith('| ')]
        for eid, item in self.entries.items():
            with self.subTest(eid=eid):
                row = next((r for r in rows if r.startswith(f'| {eid} |')), None)
                self.assertIsNotNone(row, f'{eid} has no row in docs/FAILURE-REGISTER.md')
                self.assertIn(item['test'] or item['status'].replace('_', ' '), row.lower() if not item['test'] else row)
                if item['status'] != 'enforced':
                    self.assertIn(item['status'].replace('_', ' '), row.lower())
        for us in ('organiz', 'recogniz', 'behavior', 'favorite', 'analyz'):
            self.assertNotIn(us, text.lower())

    def test_the_registry_file_is_plain(self):
        text = invariants.REGISTRY.read_text(encoding='utf-8')
        self.assertNotIn('\u2014', text)
        self.assertNotIn('@', text.replace('krish@fulltime.fm', ''))

    def test_load_refuses_a_broken_registry(self):
        cases = [
            ([entry(), entry()], 'listed twice'),
            ([entry(status='done')], 'status must be one of'),
            ([entry(test=None)], 'must name the test'),
            ([entry(test='test_engine.PolicyTests.test_x')], 'tests.test_x.ClassName.test_name'),
            ([entry(enforced_by='pack check')], 'dotted path'),
            ([entry(status='open', remains=None)], 'must say what remains'),
            ([entry(rule='A rule \u2014 with a dash.')], 'em dash'),
            ([{**entry(), 'note': 'x'}], 'must carry exactly'),
            ([entry(eid='X1')], 'the id must look like'),
            ([entry(rule='')], 'rule must be non-empty'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for entries, words in cases:
                with self.subTest(words=words):
                    with self.assertRaises(ValueError) as caught:
                        invariants.load(registry(folder, entries))
                    self.assertIn(words, str(caught.exception))
            with self.assertRaises(ValueError):
                invariants.load(registry(folder, [entry()], schema_version=2))
            path = Path(folder) / 'nan.json'
            path.write_text('{"_about": "x", "schema_version": 1, "entries": [NaN]}', encoding='utf-8')
            with self.assertRaises(ValueError):
                invariants.load(path)
            with self.assertRaises(ValueError):
                invariants.load(Path(folder) / 'none.json')


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        Path(self.folder.name, PROBE + '.py').write_text(
            'import unittest\n\n\nclass Probe(unittest.TestCase):\n'
            '    def test_passes(self):\n        pass\n\n'
            '    def test_fails(self):\n        self.fail("planted")\n\n'
            '    def test_errors(self):\n        raise RuntimeError("planted")\n\n'
            '    def test_skips(self):\n        self.skipTest("planted")\n\n'
            '    def test_prints(self):\n        print("noise")\n', encoding='utf-8')
        sys.path.insert(0, self.folder.name)
        self.pattern = mock.patch.object(invariants, 'TEST_ID', PROBE_ID)
        self.pattern.start()

    def tearDown(self):
        self.pattern.stop()
        sys.path.remove(self.folder.name)
        sys.modules.pop(PROBE, None)
        self.folder.cleanup()

    def probe(self, eid, name, **change):
        return entry(eid, test=f'{PROBE}.Probe.test_{name}', **change)

    def test_a_passing_registry_is_ok(self):
        path = registry(self.folder.name, [self.probe('R01', 'passes'), self.probe('R02', 'prints'),
                                           self.probe('R03', 'passes', status='open', remains='Half of it.')])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = invariants.check(path=path)
        self.assertEqual(out.getvalue(), '')
        self.assertEqual((result['entries'], result['enforced'], result['ran'], result['ok']), (3, 2, 2, True))
        self.assertEqual(result['by_status']['open'], 1)
        self.assertEqual((result['failing'], result['skipped'], result['missing_tests']), ([], [], []))

    def test_each_outcome_is_named(self):
        path = registry(self.folder.name, [self.probe('R01', 'passes'), self.probe('R02', 'fails'),
                                           self.probe('R03', 'errors'), self.probe('R04', 'skips'),
                                           self.probe('R05', 'nowhere'),
                                           self.probe('R06', 'passes', enforced_by='engine.pack.nowhere'),
                                           self.probe('R07', 'passes', enforced_by='engine.pack.MAX_PAYLOAD')])
        result = invariants.check(path=path)
        self.assertFalse(result['ok'])
        self.assertEqual(result['failing'], [f'R02: {PROBE}.Probe.test_fails', f'R03: {PROBE}.Probe.test_errors'])
        self.assertEqual(result['skipped'], [f'R04: {PROBE}.Probe.test_skips'])
        self.assertEqual(result['missing_tests'], [f'R05: {PROBE}.Probe.test_nowhere does not exist'])
        self.assertTrue(has(result['unresolved'], 'R06: engine.pack.nowhere'))
        self.assertTrue(has(result['unresolved'], 'R07: engine.pack.MAX_PAYLOAD is not callable'))
        self.assertEqual(result['ran'], 4)

    def test_without_running_only_existence_is_checked(self):
        path = registry(self.folder.name, [self.probe('R01', 'fails')])
        result = invariants.check(run_tests=False, path=path)
        self.assertEqual((result['ok'], result['ran'], result['failing']), (True, 0, []))

    def test_a_lookup_leaves_no_errors_on_the_shared_loader(self):
        before = list(unittest.defaultTestLoader.errors)
        path = registry(self.folder.name, [self.probe('R01', 'nowhere'),
                                           entry('R02', test=f'{PROBE}_absent.Probe.test_passes')])
        with mock.patch.object(invariants, 'TEST_ID', re.compile(r'^ftprobe_planted(?:_absent)?\.Probe\.test_\w+$')):
            result = invariants.check(run_tests=False, path=path)
        self.assertEqual(len(result['missing_tests']), 2)
        self.assertEqual(unittest.defaultTestLoader.errors, before)

    def test_never_runs_itself(self):
        with mock.patch.object(invariants, '_running', True):
            with self.assertRaises(ValueError) as caught:
                invariants.check()
        self.assertIn('never runs itself', str(caught.exception))


class NowStateTests(unittest.TestCase):
    """R31: the North Star state line in NOW.md is checked, not only written."""
    LADDER = '```yaml\nladder:\n  - [2026-10-26, 5]\n  - [2026-11-02, 16]\n```\n'

    def line(self, visible=' **North Star number: U4, unmeasured.**', **change):
        state = {'week_of': '2026-10-26', 'week_target': 5, 'current': None, 'current_as_of': '2026-10-27',
                 'current_source': 'No product export yet', 'urgency': 4, 'urgency_reason': 'unmeasured'}
        state.update(change)
        return f'# Now\n\n<!-- north-star-state {json.dumps(state)} -->{visible}\n'

    TODAY = dt.date(2026, 10, 27)

    def errors(self, text, today=TODAY):
        return invariants.now_state_errors(text, self.LADDER, today)

    def test_the_real_now_md_passes(self):
        # Its shape, ladder and urgency, as of the day it was read: CI never turns red on
        # a date. A line left over from an earlier week is the daily report's to raise.
        self.assertEqual(invariants.now_state_shape_errors(), [])

    def test_a_stale_line_is_found_by_the_dated_check_but_never_fails_the_shape_check(self):
        text = (invariants.ROOT / 'NOW.md').read_text(encoding='utf-8')
        later = dt.date(2099, 1, 5)
        self.assertTrue(any('not this week' in e for e in invariants.now_state_errors(text, today=later)))
        self.assertEqual(invariants.now_state_shape_errors(text), [])

    def test_a_good_line_passes_measured_or_not(self):
        self.assertEqual(self.errors(self.line()), [])
        # Contract bands: 7 of 5 is on pace (U1); 0 of 16 is under 40% (U4).
        self.assertEqual(self.errors(self.line(' U1, measured.', current=7, urgency=1)), [])
        self.assertEqual(self.errors(self.line(' U4.', week_of='2026-11-02', week_target=16,
                                               current_as_of='2026-11-08', current=0, urgency=4),
                                     dt.date(2026, 11, 8)), [])
        for current, urgency in ((5, 1), (4, 2), (2, 3), (1, 4), (5, 5)):
            with self.subTest(current=current):
                self.assertEqual(self.errors(self.line(f' U{urgency}.', current=current, urgency=urgency)), [])
        sunday_night = dt.datetime(2026, 11, 1, 23, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(self.errors(self.line(), sunday_night), [])

    def test_the_line_must_be_this_weeks_and_banded_by_the_contract(self):
        cases = [(self.line(' U1', current=0, urgency=1), 'at U4 or higher, not U1'),
                 (self.line(' U3', current=0, urgency=3), 'at U4 or higher, not U3'),
                 (self.line(' U2', current=1, urgency=2), 'puts 1 of 5 at U4'),
                 (self.line(' U1', current=4, urgency=1), 'puts 4 of 5 at U2'),
                 (self.line(' U3', current=2, urgency=3), 'not this week'),
                 (self.line(' U3', current=2, urgency=3), 'is 14 days old'),
                 (self.line(' U3', current=2, urgency=3), 'more than 7 days old is at least U4'),
                 (self.line(current_as_of='2026-10-28'), 'after today')]
        days = [self.TODAY] * 4 + [dt.date(2026, 11, 10)] * 3 + [self.TODAY]
        for (text, words), today in zip(cases, days):
            with self.subTest(words=words):
                self.assertTrue(has(self.errors(text, today), words), self.errors(text, today))
        with self.assertRaisesRegex(ValueError, 'today must be a date'):
            invariants.now_state_errors(self.line(), self.LADDER, '2026-10-27')
        with self.assertRaisesRegex(ValueError, 'today must be a date'):
            invariants.now_state_errors(self.line(), self.LADDER, dt.datetime(2026, 10, 27))

    def test_each_break_is_named(self):
        cases = [(self.line(urgency=2, visible=' U2'), 'at least U4'),
                 (self.line(urgency=6, visible=' U6'), 'from 1 to 5'),
                 (self.line(current=-1), 'whole number of 0 or more'),
                 (self.line(current=True), 'whole number of 0 or more'),
                 (self.line(week_target=49), 'the ladder says 5'),
                 (self.line(week_of='2026-10-27', current_as_of='2026-10-28'), 'not a Monday'),
                 (self.line(week_of='2026-11-09', current_as_of='2026-11-10'), 'not a week on the ladder'),
                 (self.line(current_as_of='2026-11-03'), 'outside the week'),
                 (self.line(current_source=''), 'current_source must say'),
                 (self.line(visible=' **North Star number: U3.**'), 'does not say U4'),
                 ('# Now\n\nno block here\n', 'exactly one north-star-state line'),
                 (self.line() + self.line(), 'it carries 2'),
                 ('<!-- north-star-state {"week_of": 1} --> U4\n', 'must carry exactly'),
                 ('<!-- north-star-state {not json} --> U4\n', 'not valid JSON')]
        for text, words in cases:
            with self.subTest(words=words):
                self.assertTrue(has(self.errors(text), words), self.errors(text))
        self.test_the_line_must_be_this_weeks_and_banded_by_the_contract()     # DOC17 names this test


class R01Tests(unittest.TestCase):
    """R01 has two halves: a published take goes on a thin rail (the per-take gate), and
    only a whole-match post needs four of six. Each half fails this test if it regresses."""

    def test_r01_a_published_take_goes_on_a_thin_rail_and_a_whole_match_post_needs_four(self):
        from engine import policy
        from tests import test_policy_v2 as organic
        for platform in ('tiktok',) + organic.NEW:
            with self.subTest(platform=platform):
                self.assertEqual(policy.errors(organic.take(platform), organic.state(thin_only=True)), [])
        self.assertTrue(any('whole-match' in e for e in policy.errors(organic.take(whole_match=True),
                                                                      organic.state())))
        for name in ('test_in_force_a_published_take_needs_no_release_or_rail',
                     'test_a_whole_match_post_still_needs_four_of_six'):
            with self.subTest(test=name):
                result = unittest.TestResult()
                organic.OrganicGateTests(name).run(result)
                self.assertTrue(result.wasSuccessful(), result.failures + result.errors)


def text_io_gaps(path):
    """Lines that read or write text, or run a process in text mode, without naming UTF-8."""
    out = []
    for node in ast.walk(ast.parse(Path(path).read_text(encoding='utf-8'))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''
        keywords = {k.arg: k.value for k in node.keywords}
        encoding = keywords.get('encoding')
        utf8 = isinstance(encoding, ast.Constant) and encoding.value in ('utf-8', 'utf-8-sig')
        if name in ('read_text', 'write_text') and not utf8:
            out.append(node.lineno)
        elif name == 'open' and isinstance(func, ast.Name):
            mode = node.args[1] if len(node.args) > 1 else keywords.get('mode')
            if not (isinstance(mode, ast.Constant) and 'b' in str(mode.value)) and not utf8:
                out.append(node.lineno)
        elif isinstance(keywords.get('text'), ast.Constant) and keywords['text'].value is True and not utf8:
            out.append(node.lineno)
    return out


def clean_root(root):
    """The smallest repository scripts/verify_repository.v2_errors passes on."""
    root = Path(root)
    (root / 'docs' / 'history').mkdir(parents=True)
    (root / 'README.md').write_text('# Readme\n', encoding='utf-8')
    (root / 'docs' / 'history' / 'LOG.md').write_text('# Log\n', encoding='utf-8')
    (root / 'NOW.md').write_text('---\nstate_doc: README.md\nhistory_log: docs/history/LOG.md\n---\n\n# Now\n',
                                 encoding='utf-8')
    for name in ('HANDOVER-2026-10-19.md', 'HANDOVER-2026-10-26.md'):
        (root / name).write_text('# Handover\n', encoding='utf-8')
    jobs = [{'name': 'morning', 'prompt': 'Read AGENTS.md and the newest HANDOVER-*.md file.'}]
    (root / 'automations.json').write_text(json.dumps({'automations': jobs}), encoding='utf-8')
    (root / '.github' / 'workflows').mkdir(parents=True)
    (root / '.github' / 'workflows' / 'check.yml').write_text(
        'jobs:\n  test:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 12\n'
        '    steps:\n      - run: sed -i s,http://azure,https://archive.ubuntu.com/ubuntu, sources\n',
        encoding='utf-8')
    (root / '.github' / 'workflows' / 'control-center.yml').write_text('permissions:\n  contents: read\n',
                                                                       encoding='utf-8')
    return root


class RuleTests(unittest.TestCase):
    """Rules from the failure history that had code and no test, each named for its entry."""

    def test_r03_a_ruling_that_needs_another_waits_for_it(self):
        rulings = {'D7': {'status': 'approved', 'evidence': '2026-10-27 - Consent', 'requires': []},
                   'D5': {'status': 'approved', 'evidence': '2026-10-27 - Creators', 'requires': ['D7']}}
        one = growth.rulings_state('## Decision log\n\n### 2026-10-27 - Creators\n', rulings)
        self.assertEqual((one['D5']['recorded'], one['D5']['in_force'], one['D7']['in_force']), (True, False, False))
        both = growth.rulings_state('## Decision log\n\n### 2026-10-27 - Creators\n\n### 2026-10-27 - Consent\n',
                                    rulings)
        self.assertTrue(both['D5']['in_force'] and both['D7']['in_force'])

    def test_r05_a_personal_invite_is_tagged_beta(self):
        link = growth.tracked('https://fulltime.fm', 'INV_CLASH_INVITE_C01_H01_V1_20261019')
        self.assertIn('utm_source=beta&', link)
        self.assertIn('utm_content=INV_CLASH_INVITE_C01_H01_V1_20261019', link)
        self.assertNotIn('utm_source=beta', growth.tracked('https://fulltime.fm', 'TT_CLASH_CLIP_C01_H02_V1_20261019'))

    def test_r06_wrong_case_and_too_many_emoji_are_refused(self):
        def problems(text):
            return growth.problems({'platform': 'tiktok', 'text': text}, {})
        self.assertTrue(has(problems('Six AI pundits argue the match.'), 'the term is "AI Pundit", exactly'))
        self.assertFalse(has(problems('Six AI Pundits argue the match.'), 'the term is "AI Pundit", exactly'))
        self.assertTrue(has(problems('The AI Pundit \U0001F525\U0001F525\U0001F525\U0001F525'), '4 emoji'))
        self.assertFalse(has(problems('The AI Pundit \U0001F525\U0001F525\U0001F525'), 'emoji'))

    def test_r10_only_the_product_inbox_appears_in_copy(self):
        def problems(text):
            return growth.problems({'platform': 'tiktok', 'text': text}, {})
        # Synthetic addresses on reserved test domains, built here so no other address sits in the file.
        for address in ('@'.join(('hello', 'example.invalid')), '@'.join(('growth', 'example.test'))):
            with self.subTest(address=address):
                self.assertTrue(has(problems(f'AI Pundit feedback to {address}'), 'the only address in Full Time'))
        self.assertFalse(has(problems('AI Pundit feedback to krish@fulltime.fm'), 'only address'))

    @unittest.skipUnless(shutil.which('git'), 'git is required')
    def test_r23_a_missing_relative_link_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True, capture_output=True)
            jobs = [{'name': 'm', 'job': 'jobs/morning.md', 'prompt': 'p'},
                    {'name': 'w', 'job': 'jobs/weekly.md', 'prompt': 'p'}]
            (root / 'automations.json').write_text(json.dumps({'schema_version': 2, 'timezone': 'Europe/London',
                                                               'automations': jobs}), encoding='utf-8')
            (root / 'present.md').write_text('# Present\n', encoding='utf-8')
            (root / 'protocol.md').write_text('See [ADR-038](adr/ADR-038.md) and [this](present.md).\n',
                                              encoding='utf-8')
            out = io.StringIO()
            with mock.patch.object(verify, 'ROOT', root), contextlib.redirect_stdout(out):
                with self.assertRaises(SystemExit):
                    verify.main()
            self.assertIn('protocol.md: missing relative link adr/ADR-038.md', out.getvalue())
            self.assertNotIn('missing relative link present.md', out.getvalue())

    def test_r32_to_r34_ci_hardening_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = clean_root(folder)
            self.assertEqual(verify.v2_errors(root), [])
            check = root / '.github' / 'workflows' / 'check.yml'
            text = check.read_text(encoding='utf-8')
            for needle, words in (('timeout-minutes: 12', 'need a timeout'),
                                  ('runs-on: ubuntu-24.04', 'pinned to Ubuntu 24.04'),
                                  ('https://archive.ubuntu.com/ubuntu', 'HTTPS mirror')):
                with self.subTest(needle=needle):
                    check.write_text(text.replace(needle, 'x'), encoding='utf-8')
                    self.assertTrue(has(verify.v2_errors(root), words))
            check.write_text(text, encoding='utf-8')
            self.assertEqual(verify.v2_errors(root), [])

    def test_r44_automations_name_the_newest_handover(self):
        with tempfile.TemporaryDirectory() as folder:
            root = clean_root(folder)
            jobs = [{'name': 'morning', 'prompt': 'Read HANDOVER-2026-10-19.md first.'}]
            (root / 'automations.json').write_text(json.dumps({'automations': jobs}), encoding='utf-8')
            self.assertTrue(has(verify.v2_errors(root), 'names HANDOVER-2026-10-19.md, not the newest handover'))
            jobs[0]['prompt'] = 'Read HANDOVER-2026-10-26.md first.'
            (root / 'automations.json').write_text(json.dumps({'automations': jobs}), encoding='utf-8')
            self.assertEqual(verify.v2_errors(root), [])

    def test_r45_front_matter_paths_must_exist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = clean_root(folder)
            (root / 'docs' / 'history' / 'LOG.md').unlink()
            self.assertTrue(has(verify.v2_errors(root), 'history_log points to docs/history/LOG.md'))
            (root / 'NOW.md').write_text('# Now, with no front matter\n', encoding='utf-8')
            self.assertTrue(has(verify.v2_errors(root), 'missing front matter'))

    def test_r35_no_new_text_read_or_write_without_utf8(self):
        known = {'engine/control_center.py', 'engine/runner.py', 'scripts/verify_repository.py'}
        files = sorted(ROOT.glob('engine/*.py')) + sorted(ROOT.glob('scripts/*.py')) + [ROOT / 'growth.py']
        found = {str(p.relative_to(ROOT)).replace('\\', '/'): text_io_gaps(p) for p in files}
        new = {name: lines for name, lines in found.items() if lines and name not in known}
        self.assertEqual(new, {}, 'name encoding="utf-8" on every text read, write and text-mode process')
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / 'sample.py'
            sample.write_text("from pathlib import Path\nPath('a').read_text()\nopen('b')\nopen('c', 'rb')\n"
                              "Path('d').read_text(encoding='utf-8-sig')\nrun(['x'], text=True)\n", encoding='utf-8')
            self.assertEqual(sorted(text_io_gaps(sample)), [2, 3, 6])

    def test_r42_a_switch_event_is_never_a_metric(self):
        row = {'metric': 'switch_intent', 'value': 3, 'source': 'synthetic', 'query_ref': 'fixture-v1',
               'window_start': '2026-10-19', 'window_end': '2026-10-25',
               'observed_at': '2026-10-26T07:30:00+00:00', 'status': 'measured'}
        for name in ('switch_intent', 'pundit_switch', 'switches'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    measurements.validate({**row, 'metric': name})
        self.assertFalse([m for m in measurements.METRICS if 'switch' in m])
        self.assertFalse([pair for pair in measurements.RATIOS.values() if any('switch' in m for m in pair)])

    def test_r50_only_registered_steps_and_no_code_under_formats(self):
        recipe = formats.recipe('match_ad')
        recipe['render_steps'] = recipe['render_steps'] + ['build_liverpool_v8_review_mix']
        self.assertTrue(has(formats.recipe_errors(recipe, 'match_ad'), 'render_steps'))
        with tempfile.TemporaryDirectory() as folder:
            root = clean_root(folder)
            (root / 'formats' / 'match_ad').mkdir(parents=True)
            (root / 'formats' / 'match_ad' / 'build_v8_mix.py').write_text('print(1)\n', encoding='utf-8')
            self.assertTrue(has(verify.v2_errors(root), 'per-run code is refused'))

    def test_doc14_scheduled_runs_commit_only_state(self):
        sync = (WORKFLOWS / 'sync.yml').read_text(encoding='utf-8')
        adds = re.findall(r'git add\s+(\S+)', sync)
        self.assertEqual(adds, ['state/'])
        self.assertNotIn('git add -A', sync)
        self.assertNotIn('git add .', sync)
        for name in ('check.yml', 'control-center.yml'):
            with self.subTest(name=name):
                text = (WORKFLOWS / name).read_text(encoding='utf-8')
                self.assertNotIn('git push', text)
                self.assertNotIn('contents: write', text)

    def test_doc20_no_workflow_uploads_an_artifact(self):
        for path in sorted(WORKFLOWS.glob('*.yml')):
            with self.subTest(workflow=path.name):
                self.assertNotIn('upload-artifact', path.read_text(encoding='utf-8'))

    def test_gg0_the_brief_status_line_names_the_live_run(self):
        lines = (ROOT / 'docs' / 'CONTROL-CENTER-BRIEF.md').read_text(encoding='utf-8').splitlines()
        status = next(line for line in lines if line.startswith('> **Status'))
        self.assertIn('live', status)
        self.assertIn('2026-10-19', status)
        self.assertNotIn('stand-in only', status)

    def test_inv_no_write_verb_or_platform_endpoint_in_engine_code(self):
        verbs = ('create_post', 'edit_post', 'delete_post', 'update_post', 'execute_mutation', 'create_idea',
                 'mcp__buffer', 'publish_video', 'media_publish', 'schedule_post')
        hosts = {'fulltime.fm', 'www.fulltime.fm', 'github.com', 'api.github.com', 'raw.githubusercontent.com',
                 'controlcenter.krishraja.com', 'accounts.google.com', 'oauth2.googleapis.com',
                 'analyticsdata.googleapis.com', 'www.googleapis.com', 'archive.ubuntu.com', '127.0.0.1'}
        files = sorted(ROOT.glob('engine/*.py')) + sorted(ROOT.glob('scripts/*.py')) + [ROOT / 'growth.py']
        for path in files:
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                self.assertEqual([v for v in verbs if v in text.lower()], [])
                named = set(re.findall(r'https?://([A-Za-z0-9.-]+)', text))
                self.assertEqual(sorted(named - hosts), [], 'a new host needs a reason and a read-only test')

    def test_lib6_the_librarian_has_no_network_or_sharing_verb(self):
        from engine import library
        tree = ast.parse(Path(library.__file__).read_text(encoding='utf-8'))
        imported = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {(node.module or '').split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertFalse(imported & {'urllib', 'http', 'socket', 'requests', 'subprocess', 'ssl'})
        calls = {node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
                 for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertFalse({c for c in calls if any(w in c.lower() for w in ('share', 'permission', 'trash'))})
        self.assertFalse({c for c in calls if c in ('rmtree', 'rmdir')})


if __name__ == '__main__':
    unittest.main()
