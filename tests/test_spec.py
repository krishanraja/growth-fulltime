"""The weekly campaign spec: validation, digest, compile gates and the G1 plan.
Synthetic fixtures only; nothing here writes into the repository or the network."""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

import growth
from engine import formats, reporting, spec

ROOT = Path(growth.HERE)
EXAMPLE = ROOT / 'specs' / 'examples' / 'synthetic-week.json'
SCHEMA = ROOT / 'specs' / 'campaign.schema.json'
LOCK = 'b' * 64
EXPIRES = '2026-11-08T23:59:00Z'


def example():
    return copy.deepcopy(spec.load(EXAMPLE))


def errors_for(change):
    value = example()
    change(value)
    return spec.validate(value)


def all_gates(value):
    return {'readiness': {f['format_id']: True for f in value['formats']}, 'organic_in_force': True,
            'd7_in_force': True, 'identity_verified': {c['channel']: True for c in value['channels']}}


def live(value=None):
    value = value or example()
    value['mode'] = 'live'
    for item in value['formats']:
        item['lock_version'] = LOCK
    return value


class VocabularyTests(unittest.TestCase):
    def test_channel_maps_cover_every_channel_as_the_card_says(self):
        self.assertEqual(spec.CHANNELS, ('tiktok', 'ig_reels', 'yt_shorts', 'ig_feed', 'threads', 'x', 'facebook',
                                         'whatsapp_channel'))
        self.assertEqual(set(spec.CHANNEL_PLATFORM), set(spec.CHANNELS))
        self.assertEqual(set(spec.CHANNEL_PREFIX), set(spec.CHANNELS))
        self.assertEqual(spec.CHANNEL_PLATFORM, {
            'tiktok': 'tiktok', 'ig_reels': 'instagram', 'ig_feed': 'instagram', 'yt_shorts': 'youtube',
            'threads': 'threads', 'x': 'x', 'facebook': 'facebook', 'whatsapp_channel': 'whatsapp_channel'})
        self.assertEqual(spec.CHANNEL_PREFIX, {
            'tiktok': 'TT', 'ig_reels': 'IG', 'ig_feed': 'IG', 'yt_shorts': 'YT', 'threads': 'TH', 'x': 'X',
            'facebook': 'FB', 'whatsapp_channel': 'WC'})
        for channel in ('tiktok', 'ig_reels', 'yt_shorts', 'x'):
            self.assertEqual(growth.PREFIX[spec.CHANNEL_PLATFORM[channel]], spec.CHANNEL_PREFIX[channel])
        self.assertEqual(spec.FORMATS, ('take_clip', 'morning_card', 'row', 'match_ad'))
        self.assertEqual(spec.MODES, ('proof', 'live'))
        self.assertEqual(spec.OBJECTIVE_KEYS, ('share_arrived_new_listeners', 'brand_post_new_listeners',
                                               'marketing_cash_gbp', 'attributed_new_completers'))
        self.assertEqual(set(spec.pundit_ids()), set(growth.PUNDITS))

    def test_the_schema_file_describes_the_same_shape(self):
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
        props = schema['properties']
        self.assertEqual(schema['$schema'], 'http://json-schema.org/draft-07/schema#')
        self.assertEqual(tuple(schema['required']), spec.TOP)
        self.assertEqual(set(props), set(spec.TOP))
        self.assertEqual(props['spec_version']['const'], spec.SPEC_VERSION)
        self.assertEqual(props['mode']['enum'], list(spec.MODES))
        nested = {'window': (props['window'], spec.WINDOW),
                  'objectives': (props['objectives']['items'], spec.OBJECTIVE),
                  'fixtures': (props['fixtures']['items'], spec.FIXTURE),
                  'formats': (props['formats']['items'], spec.FORMAT),
                  'channels': (props['channels']['items'], spec.CHANNEL),
                  'experiments': (props['experiments']['items'], spec.EXPERIMENT)}
        for name, (part, keys) in nested.items():
            self.assertFalse(part['additionalProperties'], name)
            self.assertEqual(set(part['required']), set(keys), name)
            self.assertEqual(set(part['properties']), set(keys), name)
        self.assertEqual(schema['definitions']['channel']['enum'], list(spec.CHANNELS))
        self.assertEqual(props['formats']['items']['properties']['format_id']['enum'], list(spec.FORMATS))
        self.assertEqual(set(props['formats']['items']['properties']['pundits_allowed']['items']['enum']),
                         set(growth.PUNDITS))
        self.assertEqual(props['objectives']['items']['properties']['key']['enum'], list(spec.OBJECTIVE_KEYS))
        self.assertEqual(props['experiments']['items']['properties']['metric']['enum'], list(spec.OBJECTIVE_KEYS))


class ValidateTests(unittest.TestCase):
    def test_the_synthetic_week_is_valid_and_carries_the_ladder_target(self):
        value = example()
        self.assertEqual(spec.validate(value), [])
        self.assertEqual((value['run_id'], value['mode']), ('fulltime:2026-W45', 'proof'))
        self.assertEqual(value['window']['start'], '2026-11-02')
        targets = {o['key']: o['target'] for o in value['objectives']}
        self.assertEqual(targets['share_arrived_new_listeners'], 16)
        self.assertEqual(targets['marketing_cash_gbp'], 0)
        self.assertEqual([f['format_id'] for f in value['formats']], list(spec.FORMATS))
        self.assertEqual(len(value['fixtures']), 2)
        roles = {c['channel']: c['role'] for c in value['channels']}
        self.assertEqual({c for c, r in roles.items() if r == 'push'}, {'tiktok', 'ig_reels', 'yt_shorts'})
        self.assertTrue({c for c, r in roles.items() if r == 'derived'})

    def test_unknown_keys_are_refused_at_every_level(self):
        places = {'spec': lambda v: v,
                  'spec.window': lambda v: v['window'],
                  'spec.objectives[0]': lambda v: v['objectives'][0],
                  'spec.fixtures[1]': lambda v: v['fixtures'][1],
                  'spec.formats[2]': lambda v: v['formats'][2],
                  'spec.channels[3]': lambda v: v['channels'][3],
                  'spec.experiments[0]': lambda v: v['experiments'][0]}
        for path, part in places.items():
            errors = errors_for(lambda v: part(v).__setitem__('budget', 1))
            self.assertIn(f'{path}.budget: unknown field', errors)

    def test_missing_keys_are_refused(self):
        errors = errors_for(lambda v: v.pop('experiments'))
        self.assertIn('spec.experiments: is required', errors)
        errors = errors_for(lambda v: v['formats'][0].pop('lock_version'))
        self.assertIn('spec.formats[0].lock_version: is required', errors)

    def test_rule_words_are_refused_in_any_key_at_any_depth(self):
        for key in ('do_not_post', 'avoid_rivals', 'NEVER_on_sunday', 'captions_never'):
            for part in (lambda v: v, lambda v: v['window'], lambda v: v['formats'][1],
                         lambda v: v['experiments'][0]):
                errors = errors_for(lambda v: part(v).__setitem__(key, True))
                self.assertTrue(any(key in e and 'invariants/registry.json' in e for e in errors), (key, errors))
        errors = errors_for(lambda v: v['formats'][0].__setitem__('channels', [{'never': 1}]))
        self.assertTrue(any('channels[0].never' in e and 'invariants' in e for e in errors), errors)
        self.assertEqual(errors_for(lambda v: v['experiments'][0].__setitem__('stop_rule', 'never stop early')), [])

    def test_version_run_id_and_window(self):
        cases = [(lambda v: v.__setitem__('spec_version', '1.0.0'), 'spec.spec_version'),
                 (lambda v: v.__setitem__('run_id', 'fulltime:2026-45'), 'spec.run_id'),
                 (lambda v: v.__setitem__('run_id', 'heartside:2026-W45'), 'spec.run_id'),
                 (lambda v: v.__setitem__('run_id', 'fulltime:2026-W54'), 'not a real ISO week'),
                 (lambda v: v['window'].__setitem__('start', '2026/11/02'), 'spec.window.start'),
                 (lambda v: v['window'].__setitem__('end', '2026-11-31'), 'spec.window.end'),
                 (lambda v: v['window'].__setitem__('tz', 'UTC'), 'spec.window.tz'),
                 (lambda v: v['window'].__setitem__('end', '2026-11-02'), 'start must be before end'),
                 (lambda v: v['window'].__setitem__('end', '2026-11-10'), 'more than 7 days'),
                 (lambda v: v['window'].update(start='2026-11-09', end='2026-11-15'), 'not in the week')]
        for change, expected in cases:
            errors = errors_for(change)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        self.assertEqual(errors_for(lambda v: v['window'].__setitem__('end', '2026-11-09')), [])

    def test_mode_and_objectives(self):
        cases = [(lambda v: v.__setitem__('mode', 'test'), 'spec.mode'),
                 (lambda v: v['objectives'].append({'key': 'views', 'target': 1}), 'is not one of'),
                 (lambda v: v['objectives'].append({'key': 'share_arrived_new_listeners', 'target': 3}),
                  'named twice'),
                 (lambda v: v['objectives'][0].__setitem__('target', -1), '0 or more'),
                 (lambda v: v['objectives'][0].__setitem__('target', True), '0 or more'),
                 (lambda v: v['objectives'][0].__setitem__('target', '16'), '0 or more'),
                 (lambda v: v['objectives'][1].__setitem__('target', 5), 'exactly 0'),
                 (lambda v: v['objectives'][1].__setitem__('target', 0.5), 'exactly 0')]
        for change, expected in cases:
            errors = errors_for(change)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        self.assertEqual(errors_for(lambda v: v['objectives'].append({'key': 'brand_post_new_listeners',
                                                                        'target': 2.5})), [])

    def test_fixtures(self):
        cases = [(lambda v: v['fixtures'][0].__setitem__('kickoff', '2026-11-07T12:30:00'), 'UTC offset'),
                 (lambda v: v['fixtures'][0].__setitem__('kickoff', '2026-11-07'), 'UTC offset'),
                 (lambda v: v['fixtures'][0].__setitem__('home', ''), 'home'),
                 (lambda v: v['fixtures'][0].__setitem__('rivalry', 'yes'), 'true or false'),
                 (lambda v: v['fixtures'][0].__setitem__('rank', 0), '1 or more'),
                 (lambda v: v['fixtures'][0].__setitem__('rank', True), '1 or more'),
                 (lambda v: v['fixtures'][1].__setitem__('rank', 1), 'ranks are unique'),
                 (lambda v: v['fixtures'][1].__setitem__('fixture_ref', 'synthetic-fixture-001'), 'named twice')]
        for change, expected in cases:
            errors = errors_for(change)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        self.assertEqual(errors_for(lambda v: v['fixtures'][0].__setitem__('kickoff', '2026-11-07T12:30:00Z')), [])

    def test_formats(self):
        cases = [(lambda v: v['formats'][0].__setitem__('format_id', 'podcast'), 'is not one of'),
                 (lambda v: v['formats'][1].__setitem__('format_id', 'take_clip'), 'named twice'),
                 (lambda v: v['formats'][0].__setitem__('lock_version', 'abc'), 'lock_version'),
                 (lambda v: v['formats'][0].__setitem__('lock_version', 'B' * 64), 'lock_version'),
                 (lambda v: v['formats'][0].__setitem__('max_per_matchday', 0), '1 to 6'),
                 (lambda v: v['formats'][0].__setitem__('max_per_matchday', 7), '1 to 6'),
                 (lambda v: v['formats'][0].__setitem__('channels', []), 'non-empty list'),
                 (lambda v: v['formats'][0].__setitem__('channels', ['myspace']), 'not one of channels'),
                 (lambda v: v['formats'][0].__setitem__('channels', ['tiktok', 'tiktok']), 'twice'),
                 (lambda v: v['formats'][0].__setitem__('pundits_allowed', []), 'non-empty list'),
                 (lambda v: v['formats'][0].__setitem__('pundits_allowed', ['neville']), 'AI Pundit ids'),
                 (lambda v: v['formats'][1].__setitem__('channels', ['tiktok']), 'no cut for tiktok'),
                 (lambda v: v['formats'][3].__setitem__('channels', ['threads']), 'no cut for threads'),
                 (lambda v: v['formats'][2].__setitem__('pundits_allowed', ['zen']), 'at least 2 AI Pundits')]
        for change, expected in cases:
            errors = errors_for(change)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        registry = formats.load_registry()
        registry.pop('row')
        errors = spec.validate(example(), registry)
        self.assertTrue(any('row has no registered recipe' in e for e in errors), errors)
        self.assertEqual(errors_for(lambda v: v['formats'][0].__setitem__('lock_version', LOCK)), [])

    def test_channels(self):
        cases = [(lambda v: v['channels'][0].__setitem__('channel', 'myspace'), 'is not one of'),
                 (lambda v: v['channels'][1].__setitem__('channel', 'tiktok'), 'listed twice'),
                 (lambda v: v['channels'][0].__setitem__('role', 'main'), 'push or derived'),
                 (lambda v: v['channels'][0].__setitem__('identity_ref', ''), 'identity_ref'),
                 (lambda v: v['channels'][0].__setitem__('cap_per_day', 0), '1 to 5'),
                 (lambda v: v['channels'][0].__setitem__('cap_per_day', 6), '1 to 5'),
                 (lambda v: v.__setitem__('channels', [c for c in v['channels'] if c['channel'] != 'whatsapp_channel']),
                  'whatsapp_channel is named by a format but not listed here')]
        for change, expected in cases:
            errors = errors_for(change)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))

    def test_experiments_and_learnings(self):
        cases = [(lambda v: v['experiments'][0].__setitem__('arm_unit', 'sharer'), 'never a sharer'),
                 (lambda v: v['experiments'][0].__setitem__('metric', 'views'), 'spec.experiments[0].metric'),
                 (lambda v: v['experiments'][0].__setitem__('min_matchweeks', 1), '2 or more'),
                 (lambda v: v['experiments'][0].__setitem__('stop_rule', ''), 'stop_rule'),
                 (lambda v: v['experiments'].append(copy.deepcopy(v['experiments'][0])), 'named twice'),
                 (lambda v: v.__setitem__('learnings_applied', [3]), 'non-empty string'),
                 (lambda v: v.__setitem__('learnings_applied', ['a', 'a']), 'twice'),
                 (lambda v: v.__setitem__('learnings_applied', 'a'), 'must be a list')]
        for change, expected in cases:
            errors = errors_for(change)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))

    def test_malformed_input_is_reported_never_raised(self):
        for value in (None, [], 'spec', 3):
            self.assertEqual(spec.validate(value), ['spec: must be an object'])
        broken = {key: 'x' for key in spec.TOP}
        broken['window'] = []
        errors = spec.validate(broken)
        self.assertTrue(errors)
        mixed = example()
        mixed['formats'] = ['take_clip', {'format_id': ['x']}]
        mixed['fixtures'] = [{'fixture_ref': ['x'], 'kickoff': 5, 'home': 1, 'away': None, 'rivalry': 0,
                              'rank': [1]}]
        mixed['objectives'] = [{'key': ['x'], 'target': None}]
        mixed['channels'] = [{'channel': {'x': 1}, 'role': None, 'identity_ref': 3, 'cap_per_day': 'x'}]
        self.assertTrue(spec.validate(mixed))

    def test_load_refuses_non_finite_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'spec.json'
            path.write_text('{"target": NaN}', encoding='utf-8')
            with self.assertRaises(ValueError):
                spec.load(path)


class DigestAndCompileTests(unittest.TestCase):
    def test_digest_is_the_canonical_sha256_and_ignores_key_order(self):
        value = example()
        self.assertEqual(spec.digest(value), reporting.canonical_sha256(value))
        reordered = json.loads(json.dumps(value, sort_keys=True))
        reordered['window'] = dict(reversed(list(value['window'].items())))
        self.assertEqual(spec.digest(reordered), spec.digest(value))
        value['fixtures'][0]['rank'] = 3
        self.assertNotEqual(spec.digest(value), spec.digest(example()))

    def test_proof_mode_compiles_without_any_gate(self):
        value = example()
        run = spec.compile(value, {})
        self.assertEqual(set(run), {'run_id', 'mode', 'formats', 'channels', 'payload_sha256'})
        self.assertEqual((run['run_id'], run['mode']), ('fulltime:2026-W45', 'proof'))
        self.assertEqual(run['payload_sha256'], spec.digest(value))
        self.assertEqual(run['formats'], value['formats'])
        run['formats'][0]['max_per_matchday'] = 6
        self.assertEqual(value['formats'][0]['max_per_matchday'], 3)

    def test_an_invalid_spec_does_not_compile_and_every_reason_is_named(self):
        value = example()
        value['mode'] = 'test'
        value['channels'][0]['cap_per_day'] = 9
        with self.assertRaises(ValueError) as caught:
            spec.compile(value, {})
        self.assertIn('spec.mode', str(caught.exception))
        self.assertIn('cap_per_day', str(caught.exception))

    def test_live_mode_compiles_only_with_every_gate(self):
        value = live()
        run = spec.compile(value, all_gates(value))
        self.assertEqual(run['mode'], 'live')
        missing = {
            'take_clip is not ready': lambda g: g['readiness'].__setitem__('take_clip', False),
            'match_ad is not ready': lambda g: g['readiness'].pop('match_ad'),
            'ORGANIC exception is not in force': lambda g: g.__setitem__('organic_in_force', False),
            'D7, the analytics consent item, is not in force': lambda g: g.pop('d7_in_force'),
            'identity on threads is not verified': lambda g: g['identity_verified'].__setitem__('threads', False),
            'identity on yt_shorts is not verified': lambda g: g['identity_verified'].pop('yt_shorts'),
        }
        for expected, change in missing.items():
            gates = all_gates(value)
            change(gates)
            with self.assertRaises(ValueError) as caught:
                spec.compile(value, gates)
            self.assertIn(expected, str(caught.exception))
        gates = all_gates(value)
        gates['organic_in_force'] = 'yes'
        with self.assertRaises(ValueError):
            spec.compile(value, gates)
        with self.assertRaises(ValueError) as caught:
            spec.compile(value, None)
        for expected in ('row is not ready', 'ORGANIC', 'D7', 'identity on tiktok'):
            self.assertIn(expected, str(caught.exception))


class ProposalTests(unittest.TestCase):
    def test_the_spec_is_a_g1_plan_behind_strategy(self):
        value = example()
        plan = spec.proposal(value, EXPIRES)
        self.assertEqual((plan['stage'], plan['wall'], plan['kind']), ('plan', 'strategy', 'prepared'))
        self.assertEqual(plan['proposal_id'], 'fulltime-spec-2026-W45')
        self.assertEqual(plan['objective_key'], 'attributed_new_completers')
        self.assertEqual(plan['exact_payload'], reporting.canonical(value))
        self.assertEqual(json.loads(plan['exact_payload']), value)
        self.assertEqual(plan['payload_sha256'], spec.digest(value))
        self.assertEqual(plan['close_condition'], {'event': 'campaign_week_closed', 'reference': 'fulltime:2026-W45'})
        self.assertEqual(plan['expires_at'], EXPIRES)
        self.assertIsNone(plan['amount_usd'])
        self.assertEqual(spec.proposal(example(), EXPIRES), plan)

    def test_the_plan_passes_the_report_schema(self):
        report = reporting.build('fulltime:2026-11-02:weekly', 'synthetic', '2026-11-02T08:00:00Z',
                                 {'sha': 'a' * 40, 'synced_at': '2026-11-02T07:00:00Z'}, [], {},
                                 reporting.objectives(dt.date(2026, 11, 2), [], {}), ['Synthetic week.'],
                                 identity_known=False)
        report = reporting.seal({**report, 'schema_version': '1.1.0',
                                 'proposals': [spec.proposal(example(), EXPIRES)]})
        self.assertEqual(reporting.schema_errors(report), [])

    def test_a_spec_over_8000_characters_is_refused(self):
        value = example()
        size = len(reporting.canonical(value))
        filler = 'synthetic-learning-' + 'x' * 80
        count = 0
        while len(reporting.canonical(value)) <= spec.MAX_PAYLOAD:
            count += 1
            value['learnings_applied'].append(f'{filler}-{count}')
        self.assertGreater(len(reporting.canonical(value)), 8000)
        self.assertEqual(spec.validate(value), [])
        with self.assertRaises(ValueError) as caught:
            spec.proposal(value, EXPIRES)
        self.assertIn('8000', str(caught.exception))
        value['learnings_applied'].pop()
        self.assertLessEqual(len(reporting.canonical(value)), 8000)
        self.assertGreater(len(reporting.canonical(value)), size)
        self.assertLessEqual(len(spec.proposal(value, EXPIRES)['exact_payload']), 8000)

    def test_an_invalid_spec_or_expiry_is_refused(self):
        value = example()
        value['mode'] = 'test'
        with self.assertRaises(ValueError):
            spec.proposal(value, EXPIRES)
        for expiry in (None, '2026-11-08', '2026-11-08T23:59:00', 'soon'):
            with self.assertRaises(ValueError):
                spec.proposal(example(), expiry)


if __name__ == '__main__':
    unittest.main()
