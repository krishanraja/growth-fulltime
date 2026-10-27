"""The crew registry (docs/ENGINE-V2.md, section 3): the ten specialists in the plan's
order, then the Audience Builder, each with a runner, a lint and a measured check that
resolve to real code, and a card and lens within budget. Synthetic fixtures in temporary
folders only; nothing here writes into the repository."""
import copy
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

import growth
from engine import crew

ROOT = Path(growth.HERE)
IDS = ('product_truth', 'match_clock', 'take_writer', 'voice_lock', 'motion_maker', 'card_maker',
       'channel_steward', 'measurement_analyst', 'what_works', 'librarian')
NAMES = ('Product Truth', 'Match Clock', 'Take & Script Writer', 'Voice Lock', 'Motion Maker', 'Card Maker',
         'Channel & Pack Steward', 'Measurement Analyst', 'What-Works Analyst', 'Librarian', 'Audience Builder')
QUESTIONS = {
    'product_truth': 'Does every claim and link point at something live now?',
    'match_clock': 'Is this the match fans are arguing about?',
    'take_writer': 'Would a fan send this exact line to one named mate?',
    'voice_lock': 'Without the script, does each voice sound like itself and alive?',
    'motion_maker': 'Muted, then with sound: does the first second stop the thumb?',
    'card_maker': 'At thumbnail size, does a ten-year-old get it in one second?',
    'channel_steward': 'Is it native to its platform, or a cross-post?',
    'measurement_analyst': 'Would this number survive "how was it counted"?',
    'what_works': 'What would we stop doing tomorrow, and what evidence flips it?',
    'librarian': 'From START-HERE, can Krish find this in ten seconds?',
    'audience_builder': 'Would a fan who lands on this profile follow it within three seconds, and why?'}
RUNNERS = {'product_truth': ('CLI',), 'match_clock': ('CLI',), 'take_writer': ('Codex', 'Claude'),
           'voice_lock': ('Codex',), 'motion_maker': ('Codex', 'Claude', 'Higgsfield', 'Runway'),
           'card_maker': ('Claude', 'Canva'), 'channel_steward': ('Codex', 'Claude', 'Buffer'),
           'measurement_analyst': ('Claude',), 'what_works': ('Claude', 'fresh'), 'librarian': ('CLI', 'Claude'),
           'audience_builder': ('Claude', 'Codex', 'Krish')}
US = ('organiz', 'recogniz', 'behavior', 'color', 'favorite', 'analyz', 'catalog ')
HYPE = ('game-changing', 'game changer', 'revolutionary', 'world-class', 'world class', 'unlock', 'supercharge',
        'cutting-edge', 'best-in-class', 'seamless')


def text(path):
    return (ROOT / path).read_text(encoding='utf-8')


def synthetic(folder, members=None):
    """A temporary root holding a crew folder for each member, with small cards."""
    members = copy.deepcopy(members if members is not None else crew.CREW[:2])
    for member in members:
        (Path(folder) / 'crew' / member['id']).mkdir(parents=True, exist_ok=True)
        (Path(folder) / member['card']).write_text(f'# {member["name"]}\n', encoding='utf-8')
        (Path(folder) / member['lens']).write_text('**One question?**\n', encoding='utf-8')
    return members


class RegistryTests(unittest.TestCase):
    def test_the_registry_is_sound(self):
        self.assertEqual(crew.errors(), [])

    def test_the_ten_come_in_the_plans_order_then_the_audience_builder(self):
        self.assertEqual(tuple(m['id'] for m in crew.CREW), IDS + ('audience_builder',))
        self.assertEqual(tuple(m['name'] for m in crew.CREW), NAMES)
        index = text('docs/ENGINE.md')
        for name in NAMES:
            self.assertIn(name, index)

    def test_every_member_carries_the_same_fields(self):
        for member in crew.CREW:
            with self.subTest(member=member['id']):
                self.assertEqual(tuple(member), crew.FIELDS)
                self.assertEqual(member['card'], f'crew/{member["id"]}/card.md')
                self.assertEqual(member['lens'], f'crew/{member["id"]}/lens.md')

    def test_runners_follow_the_plan(self):
        for member in crew.CREW:
            with self.subTest(member=member['id']):
                for word in RUNNERS[member['id']]:
                    self.assertIn(word, member['runner'])

    def test_every_lint_and_check_is_real_code_in_this_repository(self):
        for member in crew.CREW:
            for key in ('lint', 'check'):
                with self.subTest(member=member['id'], key=key):
                    found = crew.resolve(member[key])
                    self.assertTrue(callable(found))
                    module = getattr(found, '__module__', '')
                    self.assertTrue(module == 'growth' or module.startswith('engine.'), module)

    def test_resolve_refuses_what_does_not_import(self):
        self.assertIs(crew.resolve('engine.pack.check'), __import__('engine.pack', fromlist=['check']).check)
        self.assertTrue(callable(crew.resolve('engine.creative_system.System.artifact_gate')))
        for bad, words in (('engine.pack.nowhere', 'has no nowhere'), ('nowhere_at_all.f', 'no module'),
                           ('pack check', 'not a dotted path'), ('engine', 'not a dotted path'),
                           (None, 'not a dotted path')):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as caught:
                    crew.resolve(bad)
                self.assertIn(words, str(caught.exception))

    def test_load_crew_returns_copies_in_order_and_refuses_strangers(self):
        everyone = crew.load_crew()
        self.assertEqual([m['id'] for m in everyone], [m['id'] for m in crew.CREW])
        everyone[0]['name'] = 'changed'
        self.assertEqual(crew.CREW[0]['name'], 'Product Truth')
        self.assertEqual([m['id'] for m in crew.load_crew(['librarian', 'measurement_analyst'])],
                         ['librarian', 'measurement_analyst'])
        with self.assertRaises(ValueError):
            crew.load_crew(['nobody'])
        with self.assertRaises(ValueError):
            crew.load_crew('librarian')
        with mock.patch.object(crew, 'CREW', crew.CREW + [dict(crew.CREW[0])]):
            with self.assertRaises(ValueError) as caught:
                crew.load_crew()
            self.assertIn('listed twice', str(caught.exception))


class CardTests(unittest.TestCase):
    def test_each_card_names_its_lint_and_check(self):
        for member in crew.CREW:
            card = text(member['card'])
            for key in ('lint', 'check'):
                with self.subTest(member=member['id'], key=key):
                    dotted = member[key]
                    short = '.'.join(dotted.split('.')[-2:])
                    self.assertTrue(f'`{dotted}()`' in card or f'`{short}()`' in card, dotted)
            self.assertIn('**Lint before acting', card)
            self.assertIn('**Measured check after acting', card)

    def test_each_card_has_its_parts(self):
        for member in crew.CREW:
            card = text(member['card'])
            with self.subTest(member=member['id']):
                self.assertTrue(card.startswith(f'# {member["name"]}\n'))
                for part in ('**Job.**', '**Runner.**', '**Owns.**', '**Never.**', '| Situation | Decision |',
                             f'**Lens.** `{member["lens"]}`.'):
                    self.assertIn(part, card)
                rows = [line for line in card.splitlines() if line.startswith('| ') and '---' not in line]
                self.assertGreaterEqual(len(rows) - 1, 4, 'a short decision table, four rows or more')

    def test_each_lens_asks_the_plans_question(self):
        for member in crew.CREW:
            lens = text(member['lens'])
            with self.subTest(member=member['id']):
                self.assertIn(f'**{QUESTIONS[member["id"]]}**', lens)
                bullets = [line for line in lens.splitlines() if line.startswith('- ')]
                self.assertTrue(2 <= len(bullets) <= 4, bullets)

    def test_cards_and_lenses_are_plain_uk_english_within_budget(self):
        for member in crew.CREW:
            for key, limit in (('card', crew.CARD_LIMIT), ('lens', crew.LENS_LIMIT)):
                path = ROOT / member[key]
                body = path.read_text(encoding='utf-8')
                with self.subTest(path=member[key]):
                    self.assertLessEqual(len(path.read_bytes().replace(b'\r\n', b'\n')), limit)
                    self.assertNotIn('\u2014', body)
                    low = body.lower()
                    for word in US + HYPE:
                        self.assertNotIn(word, low)
                    self.assertEqual([a for a in re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', body)
                                      if a != 'krish@fulltime.fm'], [])

    def test_the_measurement_analyst_carries_google_analytics(self):
        member = crew.load_crew(['measurement_analyst'])[0]
        card, lens = text(member['card']), text(member['lens'])
        for words in ('Measurement Specialist', 'Google Analytics 4', 'G-W2QL8RKFJ1', 'fulltime.fm',
                      'Control Center', 'ga4_landings', 'unused fallbacks', 'engine/ga4.py', 'never listeners',
                      'D7 is still open', 'creative ID', 'share-token export', 'brand_post_new_listeners',
                      'share_arrived_new_listeners', 'interval', 'engine.attribution.by_creative()',
                      'engine.control_center.measurement_lines()', 'Turn a GA4 row into a listener'):
            with self.subTest(words=words):
                self.assertIn(words, card)
        self.assertIn('Google Analytics 4', lens)
        self.assertIn('never as listeners', lens)
        self.assertEqual(member['lint'], 'engine.attribution.ga4_rows')
        self.assertEqual(member['check'], 'engine.attribution.objectives')


class ErrorsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_a_clean_synthetic_crew_passes(self):
        self.assertEqual(crew.errors(synthetic(self.root), self.root), [])

    def test_each_break_is_named(self):
        members = synthetic(self.root)
        cases = [(lambda m: m[0].__setitem__('lint', 'engine.pack.nowhere'), 'the lint does not resolve'),
                 (lambda m: m[0].__setitem__('check', 'engine.pack.MAX_PAYLOAD'), 'is not callable'),
                 (lambda m: m[1].__setitem__('id', m[0]['id']), 'listed twice'),
                 (lambda m: m[1].__setitem__('name', m[0]['name']), 'listed twice'),
                 (lambda m: m[0].__setitem__('runner', 'a person'), 'CLI, Claude or Codex'),
                 (lambda m: m[0].__setitem__('card', 'crew/elsewhere/card.md'), 'must be crew/'),
                 (lambda m: m[0].__setitem__('id', 'Product Truth'), 'lower_snake'),
                 (lambda m: m[0].update(extra=1), 'must carry exactly')]
        for change, words in cases:
            with self.subTest(words=words):
                broken = copy.deepcopy(members)
                change(broken)
                found = crew.errors(broken, self.root)
                self.assertTrue(any(words in e for e in found), found)
        self.assertEqual(crew.errors([], self.root), ['the crew must be a non-empty list of members'])

    def test_files_are_checked_for_presence_budget_and_encoding(self):
        members = synthetic(self.root)
        card, lens = self.root / members[0]['card'], self.root / members[1]['lens']
        card.write_bytes((b'x' * 99 + b'\r\n') * 30)          # 3,000 bytes with LF, 3,030 with CRLF
        self.assertEqual(crew.errors(members, self.root), [])
        card.write_bytes(b'x' * (crew.CARD_LIMIT + 1))
        self.assertTrue(any('over the 3072-byte budget' in e for e in crew.errors(members, self.root)))
        card.write_bytes(b'\xff\xfe not utf-8')
        self.assertTrue(any('is not UTF-8' in e for e in crew.errors(members, self.root)))
        lens.write_text('y' * (crew.LENS_LIMIT + 1), encoding='utf-8')
        self.assertTrue(any('over the 1024-byte budget' in e for e in crew.errors(members, self.root)))
        lens.unlink()
        self.assertTrue(any(f'{members[1]["lens"]} is missing' in e for e in crew.errors(members, self.root)))

    def test_a_crew_folder_outside_the_registry_is_named(self):
        members = synthetic(self.root)
        (self.root / 'crew' / 'social_wizard').mkdir()
        self.assertIn('crew/social_wizard/ is not in the crew registry', crew.errors(members, self.root))


class MatchClockTests(unittest.TestCase):
    def test_fixtures_must_be_read_today_in_london(self):
        now = '2026-11-07T10:00:00+00:00'
        self.assertEqual(crew.fixtures_fresh('2026-11-07T06:15:00+00:00', now), [])
        self.assertEqual(crew.fixtures_fresh('2026-11-07T06:15:00Z', now), [])
        stale = crew.fixtures_fresh('2026-11-06T23:59:00+00:00', now)
        self.assertTrue(stale and 'not today (2026-11-07, London)' in stale[0], stale)
        self.assertIn('in the future', crew.fixtures_fresh('2026-11-07T11:00:00+00:00', now)[0])
        self.assertIn('UTC offset', crew.fixtures_fresh('2026-11-07T06:15:00', now)[0])
        self.assertIn('UTC offset', crew.fixtures_fresh('yesterday', now)[0])

    def test_the_london_day_follows_summer_time(self):
        # 23:30 UTC on 24 October 2026 is 00:30 on 25 October in London (summer time ends at 01:00 UTC).
        self.assertEqual(crew.fixtures_fresh('2026-10-24T23:30:00+00:00', '2026-10-25T10:00:00+00:00'), [])
        # 23:30 UTC on 25 October is still 25 October in London (winter time).
        self.assertTrue(crew.fixtures_fresh('2026-10-25T23:30:00+00:00', '2026-10-26T09:00:00+00:00'))

    def test_minutes_from_publish_to_pack(self):
        self.assertEqual(crew.publish_to_pack_minutes('2026-11-07T08:00:00+00:00', '2026-11-07T09:30:59+00:00'), 90)
        self.assertEqual(crew.publish_to_pack_minutes('2026-11-07T08:00:00Z', '2026-11-07T09:00:00+01:00'), 0)
        for published, ready, words in (('2026-11-07T09:00:00+00:00', '2026-11-07T08:59:00+00:00', 'before'),
                                        ('2026-11-07T08:00:00', '2026-11-07T09:00:00+00:00', 'UTC offset'),
                                        ('soon', '2026-11-07T09:00:00+00:00', 'UTC offset')):
            with self.subTest(words=words):
                with self.assertRaises(ValueError) as caught:
                    crew.publish_to_pack_minutes(published, ready)
                self.assertIn(words, str(caught.exception))


class CardMakerTests(unittest.TestCase):
    SLOT = "Full Time, AI Pundit: 2-1, £ ' ?"

    def test_glyph_readback_names_every_missing_character(self):
        self.assertEqual(crew.glyph_readback(self.SLOT, self.SLOT), [])
        self.assertEqual(crew.glyph_readback(self.SLOT, "Full Time, AI Pundit:\n2-1, £ ' ?"), [])
        lost = crew.glyph_readback(self.SLOT, "Full Time, AI Pundit: 2-1,  ' ?")
        self.assertEqual(len(lost), 1)
        self.assertIn('missing: £', lost[0])
        self.assertIn('not the slot text', crew.glyph_readback('The AI Pundit', 'The AI Pundlt')[0])
        no_glyph = crew.glyph_readback(self.SLOT, self.SLOT, font_glyphs=set(self.SLOT) - {'£'})
        self.assertEqual(no_glyph, ['the font has no glyph for: £'])
        self.assertEqual(crew.glyph_readback(self.SLOT, self.SLOT, font_glyphs=self.SLOT), [])

    def test_composed_and_decomposed_letters_read_the_same(self):
        self.assertEqual(crew.glyph_readback('Café AI Pundit', 'Café AI Pundit'), [])

    def test_bad_inputs_are_refused(self):
        for slot, back in (('', 'x'), ('   ', 'x'), (None, 'x'), ('AI Pundit', None), ('AI Pundit', 3)):
            with self.subTest(slot=slot, back=back):
                with self.assertRaises(ValueError):
                    crew.glyph_readback(slot, back)


if __name__ == '__main__':
    unittest.main()
