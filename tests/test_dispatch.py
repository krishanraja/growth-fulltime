"""Codex task-card dispatch: card validation, the allowance guard, the argv and the diff check.
Synthetic cards only; nothing here starts a process, touches the network or writes a file."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import unittest

import growth
from engine import dispatch, reporting

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

    def test_a_spend_decision_naming_the_card_lets_it_through(self):
        decision = {'decision_id': 'dec-synthetic-1', 'approved': True, 'card_id': 'synthetic-build'}
        self.assertIsNone(dispatch.guard(card(), None, NOW, decision))
        self.assertIsNone(dispatch.guard(card(), reading(100), NOW, {**decision, 'amount_usd': 0}))
        refusals = [
            ({**decision, 'card_id': 'another-card'}, "names 'another-card', not this card"),
            ({**decision, 'approved': 'yes'}, 'is not an approval'),
            ({**decision, 'approved': False}, 'is not an approval'),
            ({k: v for k, v in decision.items() if k != 'approved'}, 'is not an approval'),
            ({**decision, 'decision_id': ''}, 'has no decision_id'),
            ('dec-synthetic-1', 'has no decision_id'),
        ]
        for value, words in refusals:
            with self.assertRaises(ValueError) as caught:
                dispatch.guard(card(), reading(95), NOW, value)
            self.assertIn(words, str(caught.exception))
            self.assertIn('over the 80% ceiling', str(caught.exception))

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
        self.assertLessEqual(len(SCHEMA.read_bytes()), 6 * 1024)


if __name__ == '__main__':
    unittest.main()
