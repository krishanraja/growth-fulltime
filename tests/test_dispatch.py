"""Codex task-card dispatch: card validation, the allowance guard, the argv and the diff check.
Synthetic cards only; nothing here starts a process, touches the network or writes a file."""
import datetime as dt
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
import unittest

import growth
from engine import control_center, dispatch, reporting, session

ROOT = Path(growth.HERE)
EXAMPLE = ROOT / 'tasks' / 'match-ad-v8-mix-port.json'
SCHEMA = ROOT / 'tasks' / 'card.schema.json'
NOW = dt.datetime(2026, 10, 27, 12, 0, tzinfo=dt.timezone.utc)


def card(**change):
    base = {'card_id': 'synthetic-build', 'kind': 'build', 'executor': 'codex', 'model': 'gpt-6.1-sol',
            'effort': 'medium', 'max_minutes': 30, 'max_calls': 60,
            'worktree': '../growth-fulltime-wt/synthetic-build',
            'write_allow': ['engine/example.py', 'tests/test_example*.py', 'formats/take_clip/**'],
            'read_files': ['docs/ENGINE.md'], 'never': list(dispatch.NEVER),
            'interface': 'def example(x) -> int', 'acceptance': ['python3 -m unittest tests.test_example -v'],
            'return_shape': {'files': 'paths written'}}
    base.update(change)
    return base


def production(**change):
    value = card(card_id='synthetic-production', kind='production', **change)
    value.pop('worktree')
    return value


def reading(pct=50, minutes_ago=10):
    return {'pct': pct, 'read_at': reporting.iso(NOW - dt.timedelta(minutes=minutes_ago))}


class ValidateCard(unittest.TestCase):
    def test_good_cards_pass(self):
        self.assertEqual(dispatch.validate_card(card()), [])
        self.assertEqual(dispatch.validate_card(production()), [])
        self.assertEqual(dispatch.validate_card(card(executor='claude', model='claude-opus-5-5')), [])
        self.assertEqual(dispatch.validate_card(card(never=list(dispatch.NEVER) + ['shell_downloads'])), [])
        self.assertEqual(dispatch.validate_card(card(read_files=[], goal='Port one builder.')), [])

    def assertRefused(self, value, words):
        errors = dispatch.validate_card(value)
        self.assertTrue(any(words in e for e in errors), f'{words!r} not in {errors}')

    def test_each_rule_is_refused_in_plain_words(self):
        no_never = card(never=[x for x in dispatch.NEVER if x != 'mcp'])
        cases = [
            (card(card_id='Synthetic_Build'), 'card.card_id'),
            (card(card_id=''), 'card.card_id'),
            (card(kind='research'), 'card.kind'),
            (card(executor='gemini'), 'card.executor'),
            (card(model=''), 'never inherits the default model'),
            (card(model=None), 'never inherits the default model'),
            (card(model='default'), 'never "default"'),
            (card(model='Default'), 'never "default"'),
            (card(model='gpt-6-astra'), 'is refused'),
            (card(executor='claude', model='gpt-6-astra'), 'is refused'),
            (card(model='gpt-6.2-sol'), 'a Codex card runs on gpt-6.1-sol'),
            (card(effort='max'), 'card.effort'),
            (card(max_minutes=0), 'card.max_minutes'),
            (card(max_minutes=121), 'card.max_minutes'),
            (card(max_minutes=True), 'card.max_minutes'),
            (card(max_minutes=30.0), 'card.max_minutes'),
            (card(max_calls=401), 'card.max_calls'),
            (card(max_calls=0), 'card.max_calls'),
            ({k: v for k, v in card().items() if k != 'worktree'}, 'its own worktree'),
            (card(worktree='../growth-fulltime-wt/another-card'), 'exactly ../growth-fulltime-wt/synthetic-build'),
            (card(worktree='/tmp/wt/synthetic-build'), 'its own worktree'),
            ({**production(), 'worktree': '../growth-fulltime-wt/synthetic-production'}, '--require-existing-history'),
            ({**production(), 'worktree': None}, '--require-existing-history'),
            (card(write_allow=[]), 'card.write_allow'),
            (card(write_allow='engine/example.py'), 'card.write_allow'),
            (card(write_allow=['/home/user/engine/x.py']), 'is absolute'),
            (card(write_allow=['C:/repo/x.py']), 'is absolute'),
            (card(write_allow=['~/x.py']), 'is absolute'),
            (card(write_allow=['engine/../growth.py']), 'contains ..'),
            (card(write_allow=['engine\\example.py']), 'forward slashes'),
            (card(write_allow=['.git/hooks/pre-commit']), 'touches .git'),
            (card(write_allow=['engine/.git/x']), 'touches .git'),
            (card(write_allow=['**']), '** is the whole repository'),
            (card(write_allow=['*']), 'touches .git'),
            (card(write_allow=['**/*.py']), 'touches .git'),
            (card(write_allow=['.g*/config']), 'touches .git'),
            (card(write_allow=['*hooks/post-checkout']), 'touches .git'),
            (card(write_allow=['*hooks/post-*']), 'touches .git'),
            (card(write_allow=['*refs/heads/main']), 'touches .git'),
            (card(write_allow=['*info/exclude']), 'touches .git'),
            (card(write_allow=['*ORIG_HEAD']), 'touches .git'),
            (card(write_allow=['*.lock']), 'touches .git'),
            (card(write_allow=['?git/config']), 'touches .git'),
            (card(write_allow=['[.]git/config']), 'touches .git'),
            (card(write_allow=['.GIT/hooks/pre-commit']), 'touches .git'),
            (card(write_allow=['.Git/config']), 'touches .git'),
            (card(write_allow=['.G*/hooks/*']), 'touches .git'),
            (card(write_allow=['.git./hooks/pre-commit']), 'touches .git'),
            (card(write_allow=['.git /config']), 'touches .git'),
            (card(write_allow=['GIT~1/hooks/pre-commit']), 'touches .git'),
            (card(read_files=['.GIT/config']), 'touches .git'),
            (card(card_id='synthetic-build\n', worktree='../growth-fulltime-wt/synthetic-build\n'), 'card.card_id'),
            (card(card_id='a' * 106, worktree='../growth-fulltime-wt/' + 'a' * 106), 'at most 105'),
            (production(max_minutes=31), 'at most 30 Codex minutes'),
            (production(max_minutes=120), 'at most 30 Codex minutes'),
            (card(write_allow=['engine/x.py', 'engine/x.py']), 'names one path twice'),
            (card(read_files=['a.md', 'b.md', 'c.md', 'd.md', 'e.md', 'f.md']), 'reads at most 5'),
            (card(read_files=['engine/*.py']), 'is a glob'),
            (card(read_files=['../secret.txt']), 'contains ..'),
            (card(read_files=['.git/config']), 'touches .git'),
            (card(read_files='docs/ENGINE.md'), 'card.read_files'),
            (no_never, 'must include mcp'),
            (card(never='git'), 'card.never'),
            (card(never=list(dispatch.NEVER) + ['git']), 'names one item twice'),
            (card(interface=''), 'card.interface'),
            (card(acceptance=[]), 'card.acceptance'),
            (card(acceptance=['']), 'card.acceptance'),
            (card(acceptance='make test'), 'card.acceptance'),
            (card(return_shape={}), 'card.return_shape'),
            (card(return_shape=['files']), 'card.return_shape'),
            (card(goal=''), 'card.goal'),
            (card(priority='high'), 'card.priority: unknown field'),
            ({k: v for k, v in card().items() if k != 'acceptance'}, 'card.acceptance: is required'),
            (card(interface='x' * (6 * 1024)), 'over the 6144-byte limit'),
            (card(return_shape={'nan': float('nan')}), 'must be plain JSON'),
            ('a card', 'must be an object'),
        ]
        for value, words in cases:
            self.assertRefused(value, words)

    def test_ordinary_globs_and_the_production_ceiling_still_pass(self):
        for allow in (['engine/*.py'], ['formats/take_clip/**'], ['tests/test_example*.py'], ['local/reference/a.mp3'],
                      ['engine/git_tools.py'], ['docs/.github-notes.md']):
            self.assertEqual(dispatch.validate_card(card(write_allow=allow)), [], allow)
        self.assertEqual(dispatch.validate_card(production(max_minutes=30)), [])
        self.assertEqual(dispatch.validate_card(card(max_minutes=120)), [], 'a build card keeps 120')
        self.assertEqual(dispatch.validate_card(card(card_id='a' * 105, worktree='../growth-fulltime-wt/' + 'a' * 105)),
                         [])

    def test_the_production_ceiling_is_the_production_budget(self):
        budget = session.load_budgets()['kinds']['production']['max_engine_minutes']
        self.assertEqual(dispatch.PRODUCTION_MAX_MINUTES, budget)

    def test_the_size_limit_is_canonical_utf8_bytes(self):
        base = len(reporting.canonical(card(interface='')).encode('utf-8'))
        room = dispatch.CARD_LIMIT - base
        self.assertEqual(dispatch.validate_card(card(interface='a' * room)), [])
        self.assertRefused(card(interface='a' * (room + 1)), 'over the 6144-byte limit')
        self.assertRefused(card(interface='é' * room), 'over the 6144-byte limit')


class Guard(unittest.TestCase):
    def test_a_fresh_reading_at_or_under_80_percent_passes(self):
        self.assertIsNone(dispatch.guard(card(), reading(50), NOW))
        self.assertIsNone(dispatch.guard(card(), reading(80, minutes_ago=60), NOW))
        self.assertIsNone(dispatch.guard(card(), reading(0, minutes_ago=0), reporting.iso(NOW)))

    def test_only_codex_cards_are_guarded(self):
        self.assertIsNone(dispatch.guard(card(executor='claude', model='claude-opus-5-5'), None, NOW))
        with self.assertRaises(ValueError):
            dispatch.guard(card(executor='gemini'), reading(), NOW)

    def test_unknown_stale_future_or_high_readings_are_refused(self):
        cases = [
            (None, 'reading is unknown'),
            ('81%', 'unreadable'),
            ({'pct': 50}, 'no read_at'),
            ({'pct': 50, 'read_at': '2026-10-27T11:30:00'}, 'no read_at'),
            ({'read_at': reporting.iso(NOW)}, 'no usable pct'),
            ({'pct': '50', 'read_at': reporting.iso(NOW)}, 'no usable pct'),
            ({'pct': -1, 'read_at': reporting.iso(NOW)}, 'no usable pct'),
            ({'pct': float('nan'), 'read_at': reporting.iso(NOW)}, 'no usable pct'),
            (reading(50, minutes_ago=61), '61 minutes old'),
            (reading(50, minutes_ago=-1), 'in the future'),
            (reading(80.5), 'at 80.5%, over the 80% ceiling'),
            (reading(100), 'over the 80% ceiling'),
        ]
        for value, words in cases:
            with self.assertRaises(ValueError) as caught:
                dispatch.guard(card(), value, NOW)
            message = str(caught.exception)
            self.assertIn(words, message)
            self.assertIn('no spend decision names this card', message)

    def test_a_hand_written_or_raw_decision_is_refused(self):
        # Before the fix any {'decision_id', 'approved': True, 'card_id'} let a card through,
        # and the protocol's own decision shape was refused.
        raw = {'proposal_id': 'fulltime-codex-synthetic-build', 'decision': 'approved',
               'decided_at': '2026-10-27T11:00:00Z', 'payload_sha256': dispatch.spend_digest(card(), 0),
               'stage': 'go_live', 'amended': False, 'amount_usd': 0}
        for value in ({'decision_id': 'dec-synthetic-1', 'approved': True, 'card_id': 'synthetic-build'},
                      raw, 'dec-synthetic-1', {}):
            with self.assertRaises(ValueError) as caught:
                dispatch.guard(card(), reading(95), NOW, value)
            self.assertIn('not an approval Control Center classified', str(caught.exception))
            self.assertIn('over the 80% ceiling', str(caught.exception))
            self.assertIn('fulltime-codex-synthetic-build', str(caught.exception))

    def test_a_card_without_an_id_never_passes_on_a_decision(self):
        value = card()
        value.pop('card_id')
        with self.assertRaises(ValueError) as caught:
            dispatch.guard(value, reading(100), NOW, {'decision_id': 'x', 'approved': True})
        self.assertIn('the card is not valid', str(caught.exception))


EXPIRES = '2026-10-28T12:00:00Z'


def approve(proposal, **decision):
    """Krish's yes as Control Center sends it, classified by the engine's own loop."""
    base = {'proposal_id': proposal['proposal_id'], 'decision': 'approved', 'decided_at': '2026-10-27T11:00:00Z',
            'payload_sha256': proposal['payload_sha256'], 'stage': None, 'amended': False}
    base.update(decision)
    return control_center.classify([base], [proposal])


class SpendApproval(unittest.TestCase):
    def test_the_spend_proposal_is_a_valid_prepared_spend_on_the_exact_card(self):
        proposal = dispatch.spend_proposal(card(), 2.5, EXPIRES)
        self.assertEqual((proposal['proposal_id'], proposal['kind'], proposal['wall'], proposal['amount_usd']),
                         ('fulltime-codex-synthetic-build', 'prepared', 'spend', 2.5))
        self.assertEqual(proposal['exact_payload'], reporting.canonical(card()))
        self.assertEqual(proposal['payload_sha256'], dispatch.spend_digest(card(), 2.5))
        self.assertEqual(proposal['expires_at'], EXPIRES)
        self.assertNotIn('stage', proposal)
        items = reporting.load_schema()['properties']['proposals']['items']
        self.assertEqual(reporting.schema_errors(proposal, items, 'proposal'), [])
        self.assertEqual(reporting.protocol_errors({'schema_version': '1.1.0', 'proposals': [proposal]}), [])
        changed = dispatch.spend_proposal(card(max_minutes=31), 2.5, EXPIRES)
        self.assertEqual(changed['proposal_id'], proposal['proposal_id'], 'the id is stable')
        self.assertNotEqual(changed['payload_sha256'], proposal['payload_sha256'], 'a changed card goes back to Krish')
        self.assertNotEqual(dispatch.spend_proposal(card(), 3, EXPIRES)['payload_sha256'], proposal['payload_sha256'])

    def test_the_spend_proposal_refuses_what_it_cannot_ask(self):
        cases = [
            (lambda: dispatch.spend_proposal(card(model='gpt-6-astra'), 1, EXPIRES), 'the card is refused'),
            (lambda: dispatch.spend_proposal(card(executor='claude', model='claude-opus-5-5'), 1, EXPIRES),
             'only a Codex card'),
            (lambda: dispatch.spend_proposal(card(), None, EXPIRES), 'amount_usd'),
            (lambda: dispatch.spend_proposal(card(), -1, EXPIRES), 'amount_usd'),
            (lambda: dispatch.spend_proposal(card(), True, EXPIRES), 'amount_usd'),
            (lambda: dispatch.spend_proposal(card(), float('nan'), EXPIRES), 'amount_usd'),
            (lambda: dispatch.spend_proposal(card(), 1, '2026-10-28 12:00'), 'expires_at'),
            (lambda: dispatch.spend_proposal(card(), 1, None), 'expires_at'),
        ]
        for call, words in cases:
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertIn(words, str(caught.exception))

    def test_his_classified_yes_lets_exactly_that_card_through_at_100_percent(self):
        proposal = dispatch.spend_proposal(card(), 0, EXPIRES)
        decided = approve(proposal)
        approval = decided['approved'][proposal['proposal_id']]
        self.assertEqual(set(approval), {'amended', 'stage', 'exact_payload', 'amount_usd', 'sha256'})
        self.assertIsNone(dispatch.guard(card(), reading(100), NOW, approval))
        self.assertIsNone(dispatch.guard(card(), None, NOW, approval))
        edited = card(max_minutes=120, max_calls=400, effort='high', write_allow=['engine/**', 'tests/**'])
        self.assertEqual(dispatch.validate_card(edited), [])
        with self.assertRaises(ValueError) as caught:
            dispatch.guard(edited, reading(100), NOW, approval)
        self.assertIn('was given on a different card', str(caught.exception))
        without_payload = {k: v for k, v in approval.items() if k != 'exact_payload'}
        with self.assertRaises(ValueError) as caught:
            dispatch.guard(edited, reading(100), NOW, without_payload)
        self.assertIn('was given on a different payload', str(caught.exception))
        other = dispatch.spend_proposal(card(card_id='another-card', worktree='../growth-fulltime-wt/another-card'),
                                        0, EXPIRES)
        with self.assertRaises(ValueError):
            dispatch.guard(card(), reading(100), NOW, approve(other)['approved'][other['proposal_id']])

    def test_a_decline_a_stale_digest_or_another_wall_gives_nothing(self):
        proposal = dispatch.spend_proposal(card(), 0, EXPIRES)
        self.assertEqual(approve(proposal, decision='declined')['approved'], {})
        self.assertEqual(approve(proposal, payload_sha256='0' * 64)['approved'], {})
        approval = approve(proposal)['approved'][proposal['proposal_id']]
        refusals = [
            ({**approval, 'proposal_id': 'fulltime-codex-another-card'}, 'not fulltime-codex-synthetic-build'),
            ({**approval, 'wall': 'post'}, 'is not a spend approval'),
            ({**approval, 'stage': 'plan'}, 'is not a spend approval'),
            ({**approval, 'amount_usd': None}, 'has no amount_usd'),
            ({**approval, 'amount_usd': 5}, 'different payload'),
            ({**approval, 'sha256': 'A' * 64}, 'not an approval Control Center classified'),
            ({**approval, 'amended': 'no'}, 'not an approval Control Center classified'),
            ({k: v for k, v in approval.items() if k != 'stage'}, 'not an approval Control Center classified'),
        ]
        for value, words in refusals:
            with self.assertRaises(ValueError) as caught:
                dispatch.guard(card(), reading(100), NOW, value)
            self.assertIn(words, str(caught.exception))

    def test_his_amended_card_is_the_one_that_runs(self):
        proposal = dispatch.spend_proposal(card(), 4, EXPIRES)
        tighter = card(max_minutes=20, effort='low')
        his = {'exact_payload': reporting.canonical(tighter), 'amount_usd': 1}
        decided = approve(proposal, amended=True, amended_sha256=control_center.amended_digest(his), **his)
        self.assertEqual(decided['approved_amended'], [proposal['proposal_id']])
        approval = decided['approved'][proposal['proposal_id']]
        self.assertEqual(approval['sha256'], dispatch.spend_digest(tighter, 1))
        self.assertIsNone(dispatch.guard(tighter, reading(100), NOW, approval))
        with self.assertRaises(ValueError):
            dispatch.guard(card(), reading(100), NOW, approval)

    def test_the_recorded_instruction_is_read_back_and_still_checked(self):
        proposal = dispatch.spend_proposal(card(), 0, EXPIRES)
        decided = approve(proposal)
        self.assertEqual(len(decided['instructions']), 1)
        with tempfile.TemporaryDirectory() as local:
            self.assertIsNone(dispatch.recorded_approval(local, card()))
            path = Path(local) / 'control-center' / 'instructions.jsonl'
            path.parent.mkdir(parents=True)
            path.write_text('not json\n' + json.dumps({'proposal_id': 'fulltime-codex-another-card'}) + '\n',
                            encoding='utf-8')
            self.assertIsNone(dispatch.recorded_approval(local, card()))
            control_center.record_instructions(local, decided['instructions'], '2026-10-27T11:05:00Z')
            row = dispatch.recorded_approval(local, card())
            self.assertEqual((row['proposal_id'], row['wall'], row['sha256']),
                             (proposal['proposal_id'], 'spend', proposal['payload_sha256']))
            self.assertIsNone(dispatch.guard(card(), reading(100), NOW, row))
            with self.assertRaises(ValueError):
                dispatch.guard(card(max_minutes=31), reading(100), NOW, row)

class GuardTime(unittest.TestCase):
    def test_now_needs_its_utc_offset(self):
        for bad in (dt.datetime(2026, 10, 27, 12, 0), '2026-10-27T12:00:00', None):
            with self.assertRaises(ValueError) as caught:
                dispatch.guard(card(), reading(), bad)
            self.assertIn('UTC offset', str(caught.exception))


class Command(unittest.TestCase):
    def test_a_build_card_dispatches_into_its_worktree(self):
        argv = dispatch.command(card(), '/opt/codex-plugin', 'tasks/synthetic-build.md')
        self.assertEqual(argv, ['node', os.path.join('/opt/codex-plugin', 'scripts', 'codex-companion.mjs'),
                                'task', '--background', '--fresh', '--write', '--model', 'gpt-6.1-sol',
                                '--effort', 'medium', '--cwd', '../growth-fulltime-wt/synthetic-build',
                                '--prompt-file', 'tasks/synthetic-build.md'])

    def test_a_production_card_runs_in_the_main_checkout(self):
        argv = dispatch.command(production(effort='low'), Path('plugin'), Path('tasks') / 'p.md')
        self.assertEqual(argv[argv.index('--cwd') + 1], '.')
        self.assertEqual(argv[argv.index('--effort') + 1], 'low')
        self.assertEqual(argv[-1], str(Path('tasks') / 'p.md'))

    def test_claude_and_invalid_cards_never_get_an_argv(self):
        cases = [
            (lambda: dispatch.command(card(executor='claude', model='claude-opus-5-5'), 'p', 'x.md'), 'Claude card'),
            (lambda: dispatch.command(card(model='gpt-6-astra'), 'p', 'x.md'), 'the card is refused'),
            (lambda: dispatch.command(card(), '', 'x.md'), 'plugin_root'),
            (lambda: dispatch.command(card(), 'p', ''), 'prompt_file'),
        ]
        for call, words in cases:
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertIn(words, str(caught.exception))

    def test_the_module_never_starts_a_process(self):
        source = (ROOT / 'engine' / 'dispatch.py').read_text(encoding='utf-8')
        for needle in ('subprocess', 'os.system', 'Popen', 'os.exec', 'os.spawn', 'urllib', 'socket'):
            self.assertNotIn(needle, source)


class OutsideWriteAllow(unittest.TestCase):
    def test_paths_no_glob_matches_are_returned_in_order(self):
        allow = ['engine/formats/match_ad/*.py', 'tests/test_match_ad_*.py', 'local/reference/v8.mix.json']
        changed = ['engine/formats/match_ad/tv_mix.py', './tests/test_match_ad_tv_mix.py', 'engine/formats.py',
                   'tests\\test_match_ad_tv_mix.py', 'local/reference/v8.mix.json', 'growth.py', 'growth.py',
                   '../growth-fulltime/growth.py', '/etc/passwd', '.git/config', 'engine/formats/match_ad/a/.git/x',
                   'Engine/formats/match_ad/tv_mix.py']
        self.assertEqual(dispatch.outside_write_allow(changed, allow),
                         ['engine/formats.py', 'growth.py', '../growth-fulltime/growth.py', '/etc/passwd',
                          '.git/config', 'engine/formats/match_ad/a/.git/x', 'Engine/formats/match_ad/tv_mix.py'])
        self.assertEqual(dispatch.outside_write_allow([], allow), [])
        self.assertEqual(dispatch.outside_write_allow(['a.py'], []), ['a.py'])
        with self.assertRaises(ValueError):
            dispatch.outside_write_allow('growth.py', allow)


class ExampleCard(unittest.TestCase):
    def setUp(self):
        self.raw = EXAMPLE.read_bytes()
        self.card = json.loads(self.raw.decode('utf-8'))

    def test_the_v8_mix_port_card_is_valid_and_within_6_kb(self):
        self.assertEqual(dispatch.validate_card(self.card), [])
        self.assertLessEqual(len(self.raw), dispatch.CARD_LIMIT)
        self.assertEqual(self.card['card_id'], EXAMPLE.stem)
        self.assertEqual((self.card['executor'], self.card['kind'], self.card['model']),
                         ('codex', 'build', dispatch.PINNED_CODEX_MODEL))
        self.assertEqual(self.card['worktree'], '../growth-fulltime-wt/match-ad-v8-mix-port')

    def test_it_ports_into_match_ad_and_proves_a_byte_for_byte_match_from_local_inputs(self):
        for pattern in self.card['write_allow']:
            self.assertTrue(pattern.startswith(('engine/formats/match_ad/', 'tests/test_match_ad', 'local/')), pattern)
        acceptance = ' '.join(self.card['acceptance'])
        self.assertIn('hashlib.sha256', acceptance)
        self.assertIn('local/reference/v8-tv-mix.mp3', acceptance)
        for found in re.findall(r'\S+\.(?:mp3|wav|json)\b', acceptance):
            self.assertTrue(found.startswith('local/'), found)

    def test_every_output_it_must_make_is_inside_its_write_allow(self):
        # Before the fix the card asked for v8-port.mp3 and its hash while forbidding the write.
        outs = []
        for command in self.card['acceptance']:
            words = shlex.split(command)
            outs += [words[i + 1] for i, word in enumerate(words[:-1]) if word == '--out']
        self.assertEqual(outs, ['local/reference/v8-port.mp3'])
        for path in outs + re.findall(r'local/\S+?\.mp3', self.card['return_shape']['port_sha256']):
            self.assertTrue(any(fnmatchcase(path, glob) for glob in self.card['write_allow']), path)
        self.assertEqual(dispatch.outside_write_allow(outs, self.card['write_allow']), [])
        self.assertIn('byte for byte', self.card['goal'])
        self.assertNotIn('engine/formats/__init__.py', self.card['write_allow'])

    def test_it_carries_no_private_content(self):
        text = self.raw.decode('utf-8')
        self.assertNotIn('\u2014', text)
        self.assertEqual(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text), [])
        self.assertNotRegex(text, r'\b[0-9a-f]{40,}\b')
        for word in ('Liverpool', 'Arsenal', 'drive.google', 'token'):
            self.assertNotIn(word, text)

    def test_its_argv_is_built_from_the_pinned_fields(self):
        argv = dispatch.command(self.card, 'plugin', 'tasks/match-ad-v8-mix-port.md')
        self.assertIn('gpt-6.1-sol', argv)
        self.assertEqual(argv[argv.index('--cwd') + 1], self.card['worktree'])


class Schema(unittest.TestCase):
    def test_the_schema_names_the_same_fields_as_the_validator(self):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        self.assertEqual(schema['required'], list(dispatch.REQUIRED))
        self.assertEqual(set(schema['properties']), set(dispatch.REQUIRED + dispatch.OPTIONAL))
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['effort']['enum'], list(dispatch.EFFORTS))
        self.assertEqual(schema['properties']['max_minutes']['maximum'], dispatch.MAX_MINUTES)
        self.assertEqual(schema['properties']['max_calls']['maximum'], dispatch.MAX_CALLS)
        self.assertEqual(schema['properties']['read_files']['maxItems'], dispatch.MAX_READ_FILES)
        contains = [rule['contains']['const'] for rule in schema['properties']['never']['allOf']]
        self.assertEqual(contains, list(dispatch.NEVER))
        self.assertIn(dispatch.PINNED_CODEX_MODEL, json.dumps(schema['allOf']))
        self.assertEqual(schema['properties']['card_id']['maxLength'], dispatch.CARD_ID_MAX)
        production = next(rule['then'] for rule in schema['allOf']
                          if rule['if']['properties'].get('kind', {}).get('const') == 'production')
        self.assertEqual(production['properties']['max_minutes']['maximum'], dispatch.PRODUCTION_MAX_MINUTES)

    def test_the_schema_patterns_refuse_the_same_git_paths(self):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        refused = [rule['pattern'] for rule in schema['properties']['write_allow']['items']['not']['anyOf']]
        for value in ('*hooks/post-checkout', '.GIT/config', '.Git/hooks/x', '.git./config', 'GIT~1/config', '*.lock'):
            self.assertTrue(any(re.search(p, value) for p in refused), value)
            self.assertTrue(dispatch.validate_card(card(write_allow=[value])), value)
        for value in ('engine/*.py', 'engine/git_tools.py', 'docs/.github-notes.md'):
            self.assertFalse(any(re.search(p, value) for p in refused), value)
            self.assertEqual(dispatch.validate_card(card(write_allow=[value])), [], value)
        self.assertLessEqual(len(SCHEMA.read_bytes()), 6 * 1024)


if __name__ == '__main__':
    unittest.main()
