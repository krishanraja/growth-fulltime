"""The format registry, computed readiness (ruling 7) and the G2 verdict per item.
Synthetic fixtures only; registries under test live in temporary directories."""
import copy
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

import growth
from engine import formats, reporting, spec

LOCK_A = 'a' * 64
LOCK_B = 'c' * 64
TT = 'TT_CLASH_CLIP_C01_H01_V1_20261107'
IG = 'IG_CLASH_CLIP_C01_H01_V1_20261107'
YT = 'YT_CLASH_SHORT_C01_H01_V1_20261107'
X = 'X_CLASH_POST_C01_H01_V1_20261107'


def verdict(fixture, day, verdict_value='post_it', fmt='take_clip', lock=LOCK_A, **extra):
    return {'format_id': fmt, 'lock_version': lock, 'fixture_ref': fixture,
            'creative_id': f'TT_CLASH_CLIP_C01_H01_V1_202611{day:02d}', 'verdict': verdict_value,
            'prelive_checks_passed': True, 'unit_cost_recorded': True, 'unit_minutes_recorded': True,
            'decided_at': f'2026-11-{day:02d}T09:00:00Z', **extra}


def three_clean():
    return [verdict('synthetic-fixture-001', 2), verdict('synthetic-fixture-002', 3),
            verdict('synthetic-fixture-003', 4)]


class RegistryTests(unittest.TestCase):
    def test_all_four_recipes_are_registered_with_the_card_values(self):
        registry = formats.load_registry()
        self.assertEqual(set(registry), set(spec.FORMATS))
        self.assertEqual(formats.FORMATS_DIR, Path(growth.HERE) / 'formats')
        expected = {
            'take_clip': (None, 1, 'exact_show', False, (1080, 1920), 'zero_generation'),
            'morning_card': (None, 1, 'exact_show', True, (1080, 1350), 'zero_marginal'),
            'row': (None, 2, 'exact_show', False, (1080, 1920), 'zero_generation'),
            'match_ad': ('two_pundit_remote', 0, 'today', False, (1080, 1920), 'credits'),
        }
        for format_id, (system, least, links, whole, master, cost) in expected.items():
            data = registry[format_id]
            self.assertEqual(formats.recipe_errors(data, format_id), [])
            self.assertEqual(data['format_id'], format_id)
            self.assertEqual(data['creative_system_format'], system)
            self.assertEqual(data['published_pundits_min'], least)
            self.assertEqual(data['links_to'], links)
            self.assertEqual(data['whole_match_claims_allowed'], whole)
            self.assertEqual((data['master']['width'], data['master']['height']), master)
            self.assertEqual(data['cost_class'], cost)
            self.assertTrue(set(data['cuts']) <= set(spec.CHANNELS))
            self.assertTrue(set(data['render_steps']) <= set(formats.RENDER_STEPS))
        for format_id in ('take_clip', 'row', 'match_ad'):
            for channel in ('tiktok', 'ig_reels', 'yt_shorts'):
                self.assertEqual(registry[format_id]['cuts'][channel]['height'], 1920)

    def test_recipe_files_are_a_public_skeleton(self):
        for format_id in spec.FORMATS:
            text = (formats.FORMATS_DIR / format_id / 'recipe.json').read_text(encoding='utf-8')
            for private in ('http', '@', 'drive.google', 'local/creative-system', chr(0x2014)):
                self.assertNotIn(private, text, format_id)
            self.assertEqual(set(json.loads(text)), set(formats.RECIPE))

    def test_registered_and_recipe(self):
        self.assertTrue(formats.registered('take_clip'))
        self.assertFalse(formats.registered('podcast'))
        self.assertEqual(formats.recipe('match_ad')['links_to'], 'today')
        with self.assertRaises(ValueError):
            formats.recipe('podcast')

    def test_a_missing_recipe_is_not_registered_and_a_broken_one_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(formats.FORMATS_DIR / 'take_clip', Path(tmp) / 'take_clip')
            self.assertEqual(set(formats.load_registry(tmp)), {'take_clip'})
            self.assertFalse(formats.registered('row', tmp))
            self.assertTrue(formats.registered('take_clip', tmp))
            value = spec.load(Path(growth.HERE) / 'specs' / 'examples' / 'synthetic-week.json')
            errors = spec.validate(value, formats.load_registry(tmp))
            self.assertTrue(any('row has no registered recipe' in e for e in errors), errors)
            path = Path(tmp) / 'take_clip' / 'recipe.json'
            path.write_text('{not json', encoding='utf-8')
            with self.assertRaises(ValueError):
                formats.load_registry(tmp)
            data = copy.deepcopy(formats.recipe('take_clip'))
            data['render_steps'].append('build_liverpool_v9_mix')
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError) as caught:
                formats.load_registry(tmp)
            self.assertIn('not a registered step', str(caught.exception))

    def test_recipe_rules(self):
        base = formats.recipe('match_ad')
        cases = [(lambda d: d.__setitem__('script_text', 'x'), 'unknown field'),
                 (lambda d: d.pop('slots'), 'slots: is required'),
                 (lambda d: d.__setitem__('format_id', 'row'), 'must be match_ad'),
                 (lambda d: d.__setitem__('links_to', 'home'), 'exact_show or today'),
                 (lambda d: d.__setitem__('cost_class', 'free'), 'cost_class'),
                 (lambda d: d['cuts'].__setitem__('myspace', {'width': 1, 'height': 1, 'max_seconds': None}),
                  'cuts.myspace'),
                 (lambda d: d['cuts']['tiktok'].__setitem__('max_seconds', 0), 'max_seconds'),
                 (lambda d: d['cuts']['tiktok'].pop('max_seconds'), 'exactly {width, height, max_seconds}'),
                 (lambda d: d.__setitem__('master', {'width': 1080}), 'exactly {width, height}'),
                 (lambda d: d.__setitem__('slots', ['Hook Line']), 'lower_snake'),
                 (lambda d: d['prelive_checks'].remove('no_show_claim'), 'must run no_show_claim'),
                 (lambda d: d['prelive_checks'].remove('today_live'), 'must run today_live'),
                 (lambda d: d.__setitem__('whole_match_claims_allowed', True), 'whole_match_four_of_six'),
                 (lambda d: d.update(links_to='exact_show', prelive_checks=d['prelive_checks'] + ['show_published', 'link_live']),
                  'needs at least 1')]
        for change, expected in cases:
            data = copy.deepcopy(base)
            change(data)
            errors = formats.recipe_errors(data, 'match_ad')
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        self.assertEqual(formats.recipe_errors([], 'row'), ['formats/row/recipe.json: must be an object'])


class ReadinessTests(unittest.TestCase):
    def test_three_clean_post_its_on_three_matches_are_ready(self):
        result = formats.readiness(three_clean(), 'take_clip', LOCK_A)
        self.assertEqual(set(result), {'ready', 'streak', 'distinct_fixtures', 'reason'})
        self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (True, 3, 3))
        self.assertTrue(result['reason'].startswith('ready'))

    def test_two_post_its_on_one_match_count_once(self):
        verdicts = [verdict('synthetic-fixture-001', 2), verdict('synthetic-fixture-001', 3),
                    verdict('synthetic-fixture-002', 4)]
        result = formats.readiness(verdicts, 'take_clip', LOCK_A)
        self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (False, 3, 2))
        result = formats.readiness(verdicts + [verdict('synthetic-fixture-003', 5)], 'take_clip', LOCK_A)
        self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (True, 4, 3))

    def test_an_edit_or_reject_breaks_the_streak(self):
        for breaker in ('edit', 'reject'):
            newest = three_clean() + [verdict('synthetic-fixture-004', 5, breaker)]
            result = formats.readiness(newest, 'take_clip', LOCK_A)
            self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (False, 0, 0))
            self.assertIn('stopped by', result['reason'])
            oldest = [verdict('synthetic-fixture-000', 1, breaker)] + three_clean()
            self.assertTrue(formats.readiness(oldest, 'take_clip', LOCK_A)['ready'])
            middle = [verdict('synthetic-fixture-001', 2), verdict('synthetic-fixture-002', 3, breaker),
                      verdict('synthetic-fixture-003', 4), verdict('synthetic-fixture-004', 5)]
            result = formats.readiness(middle, 'take_clip', LOCK_A)
            self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (False, 2, 2))

    def test_a_failing_prelive_check_or_unmeasured_cost_breaks_the_streak(self):
        for field in ('prelive_checks_passed', 'unit_cost_recorded', 'unit_minutes_recorded'):
            for bad in (False, None, 'true'):
                failing = verdict('synthetic-fixture-004', 5, **{field: bad})
                result = formats.readiness(three_clean() + [failing], 'take_clip', LOCK_A)
                self.assertEqual((result['ready'], result['streak']), (False, 0), (field, bad))
            missing = verdict('synthetic-fixture-004', 5)
            missing.pop(field)
            self.assertFalse(formats.readiness(three_clean() + [missing], 'take_clip', LOCK_A)['ready'])
        unknown = verdict('synthetic-fixture-004', 5, 'maybe')
        self.assertEqual(formats.readiness(three_clean() + [unknown], 'take_clip', LOCK_A)['streak'], 0)

    def test_a_lock_change_restarts_the_streak(self):
        verdicts = three_clean() + [verdict('synthetic-fixture-004', 5, lock=LOCK_B)]
        result = formats.readiness(verdicts, 'take_clip', LOCK_B)
        self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (False, 1, 1))
        self.assertTrue(formats.readiness(verdicts, 'take_clip', LOCK_A)['ready'])
        other_format = [dict(v, format_id='morning_card') for v in three_clean()]
        self.assertEqual(formats.readiness(other_format, 'take_clip', LOCK_A)['streak'], 0)
        self.assertIn('no verdicts', formats.readiness(other_format, 'take_clip', LOCK_A)['reason'])

    def test_post_live_metrics_are_never_inputs(self):
        live_numbers = {'views': 10 ** 6, 'shares': 5000, 'completion_rate': 0.97, 'share_arrived_new_listeners': 900}
        boosted = [dict(v, **live_numbers) for v in three_clean()]
        self.assertEqual(formats.readiness(boosted, 'take_clip', LOCK_A), formats.readiness(three_clean(), 'take_clip', LOCK_A))
        edited = three_clean() + [verdict('synthetic-fixture-004', 5, 'edit', **live_numbers)]
        self.assertFalse(formats.readiness(edited, 'take_clip', LOCK_A)['ready'])
        two = [dict(v, **live_numbers) for v in three_clean()[:2]]
        self.assertFalse(formats.readiness(two, 'take_clip', LOCK_A)['ready'])

    def test_order_comes_from_decided_at_not_the_list(self):
        verdicts = three_clean() + [verdict('synthetic-fixture-004', 5, 'edit')]
        shuffled = list(verdicts)
        random.Random(7).shuffle(shuffled)
        self.assertEqual(formats.readiness(shuffled, 'take_clip', LOCK_A), formats.readiness(verdicts, 'take_clip', LOCK_A))
        offset = three_clean()
        offset.append(dict(verdict('synthetic-fixture-004', 4, 'edit'), decided_at='2026-11-04T08:30:00-01:00'))
        self.assertEqual(formats.readiness(offset, 'take_clip', LOCK_A)['streak'], 0)

    def test_unlocked_is_never_ready_and_bad_input_is_refused(self):
        unlocked = [dict(v, lock_version='unlocked') for v in three_clean()]
        result = formats.readiness(unlocked, 'take_clip', 'unlocked')
        self.assertEqual((result['ready'], result['streak'], result['distinct_fixtures']), (False, 3, 3))
        self.assertIn('unlocked', result['reason'])
        with self.assertRaises(ValueError):
            formats.readiness(three_clean(), 'podcast', LOCK_A)
        with self.assertRaises(ValueError):
            formats.readiness(three_clean(), 'take_clip', 'v2')
        with self.assertRaises(ValueError):
            formats.readiness([dict(verdict('synthetic-fixture-001', 2), decided_at='yesterday')], 'take_clip', LOCK_A)
        with self.assertRaises(ValueError):
            formats.readiness([dict(verdict('synthetic-fixture-001', 2), decided_at='2026-11-02T09:00:00')],
                              'take_clip', LOCK_A)
        self.assertEqual(formats.readiness([], 'row', LOCK_A)['streak'], 0)

    def test_readiness_feeds_the_compile_gates(self):
        campaign = spec.load(Path(growth.HERE) / 'specs' / 'examples' / 'synthetic-week.json')
        for item in campaign['formats']:
            item['lock_version'] = LOCK_A
        gate = formats.readiness_gate(three_clean(), campaign)
        self.assertEqual(gate, {'take_clip': True, 'morning_card': False, 'row': False, 'match_ad': False})


def sent():
    return json.dumps({'items': [
        {'creative_id': TT, 'channel': 'tiktok', 'caption': 'The Gaffer is not having it.',
         'link': 'https://fulltime.fm/synthetic', 'media_sha256': 'd' * 64},
        {'creative_id': IG, 'channel': 'ig_reels', 'caption': 'The Gaffer is not having it.',
         'link': 'https://fulltime.fm/synthetic', 'media_sha256': 'd' * 64},
        {'creative_id': YT, 'channel': 'yt_shorts', 'caption': 'The Gaffer is not having it.',
         'link': 'https://fulltime.fm/synthetic', 'media_sha256': 'd' * 64}]})


def amended(change):
    data = json.loads(sent())
    change(data['items'])
    text = json.dumps(data)
    return {'proposal_id': 'fulltime:post:matchday', 'decision': 'approved', 'decided_at': '2026-11-07T10:00:00Z',
            'payload_sha256': 'e' * 64, 'stage': 'go_live', 'amended': True, 'exact_payload': text,
            'amount_usd': None,
            'amended_sha256': reporting.canonical_sha256({'amount_usd': None, 'exact_payload': text})}


class G2VerdictTests(unittest.TestCase):
    def test_clear_without_amendment_is_post_it_for_every_item(self):
        for value in ('approved', 'done'):
            out = formats.g2_verdicts(sent(), {'decision': value, 'amended': False, 'payload_sha256': 'e' * 64})
            self.assertEqual(out, [{'creative_id': c, 'verdict': 'post_it', 'note': None} for c in (TT, IG, YT)])

    def test_purge_rejects_every_item(self):
        out = formats.g2_verdicts(sent(), {'decision': 'declined', 'amended': False})
        self.assertEqual([v['verdict'] for v in out], ['reject'] * 3)
        self.assertEqual([v['creative_id'] for v in out], [TT, IG, YT])

    def test_an_amendment_is_judged_per_item_by_diff(self):
        def change(items):
            items[0]['caption'] = 'The Gaffer is fuming.'
            items[0]['note'] = 'Sharper verb.'
            del items[1]
            items[1]['note'] = 'This one is right.'
            items[1] = dict(reversed(list(items[1].items())))
        out = formats.g2_verdicts(sent(), amended(change))
        self.assertEqual(out, [{'creative_id': TT, 'verdict': 'edit', 'note': 'Sharper verb.'},
                               {'creative_id': IG, 'verdict': 'reject', 'note': None},
                               {'creative_id': YT, 'verdict': 'post_it', 'note': 'This one is right.'}])

    def test_an_unchanged_amendment_is_post_it_and_a_new_item_is_refused(self):
        out = formats.g2_verdicts(sent(), amended(lambda items: None))
        self.assertEqual([v['verdict'] for v in out], ['post_it'] * 3)
        out = formats.g2_verdicts(sent(), amended(lambda items: items.reverse()))
        self.assertEqual([v['verdict'] for v in out], ['post_it'] * 3)
        out = formats.g2_verdicts(sent(), amended(lambda items: items[2].__setitem__('media_sha256', 'f' * 64)))
        self.assertEqual([v['verdict'] for v in out], ['post_it', 'post_it', 'edit'])
        with self.assertRaises(ValueError) as caught:
            formats.g2_verdicts(sent(), amended(lambda items: items.append({'creative_id': X, 'channel': 'x'})))
        self.assertIn(X, str(caught.exception))
        out = formats.g2_verdicts(sent(), amended(lambda items: items.clear()))
        self.assertEqual([v['verdict'] for v in out], ['reject'] * 3)

    def test_malformed_payloads_and_decisions_are_refused(self):
        decision = amended(lambda items: None)
        decision['amended_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            formats.g2_verdicts(sent(), decision)
        decision = amended(lambda items: None)
        decision['exact_payload'] = 'post them all'
        decision.pop('amended_sha256')
        with self.assertRaises(ValueError):
            formats.g2_verdicts(sent(), decision)
        for bad_sent in ('not json', json.dumps({'posts': []}), json.dumps({'items': [{'channel': 'x'}]}),
                         json.dumps({'items': [{'creative_id': TT}, {'creative_id': TT}]})):
            with self.assertRaises(ValueError):
                formats.g2_verdicts(bad_sent, {'decision': 'approved', 'amended': False})
        for bad_decision in (None, {}, {'decision': 'bumped'}):
            with self.assertRaises(ValueError):
                formats.g2_verdicts(sent(), bad_decision)


if __name__ == '__main__':
    unittest.main()
