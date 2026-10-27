"""The Measurement Analyst: the North Star count, brand-post arrivals and Google
Analytics landings by creative ID (engine/attribution.py, MEASUREMENT.md). Synthetic
fixtures only; no network."""
import copy
import datetime as dt
import inspect
import json
from pathlib import Path
import unittest

import growth
from engine import attribution, ga4, measurements, reporting
from engine.attribution import (by_creative, ga4_observations, ga4_rows, objectives, poisson_interval,
                                z_score)

ROOT = Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc
# A Monday in summer time: the week is 29 June to 5 July 2026, London days.
TODAY = dt.date(2026, 7, 6)
START, END = '2026-06-29', '2026-07-05'
TAKEN = '2026-07-06T06:00:00+00:00'
AS_OF = dt.datetime(2026, 7, 6, 9, 0, tzinfo=UTC)
CREATIVE = 'TT_CLASH_CLIP_C01_H01_V1_20261020'
OTHER = 'IG_CLASH_CLIP_C02_H01_V1_20261020'
# A contact-shaped value built at run time, so no address sits in this public file.
CONTACT = 'synthetic' + chr(64) + 'example.invalid'


def row(metric, value, **extra):
    base = {'metric': metric, 'value': value, 'source': 'synthetic-product-export',
            'query_ref': 'synthetic:share-token-first-listen-7d:v0', 'window_start': START,
            'window_end': END, 'observed_at': TAKEN, 'status': 'measured'}
    return {**base, **extra}


def landing(content=CREATIVE, source='tiktok', new_users=12, sessions=14, engaged=9):
    return {'utm_source': source, 'utm_medium': 'organic_video', 'utm_campaign': 'ft_growth_202610',
            'utm_content': content, 'new_users': new_users, 'sessions': sessions, 'engaged_sessions': engaged}


def export(rows=None, **extra):
    base = {'product': 'fulltime', 'source': 'ga4', 'property': 'G-W2QL8RKFJ1',
            'query_ref': 'synthetic:ga4-landings-by-creative:v0', 'window_start': START, 'window_end': END,
            'observed_at': TAKEN,
            'rows': rows if rows is not None else [landing(), landing(OTHER, 'instagram', 6, 7, 4),
                                                   landing('(not set)', '(direct)', 40, 55, 21)]}
    return {**base, **extra}


def by_key(result):
    return {item['key']: item for item in result}


class Interval(unittest.TestCase):
    def test_the_rough_95_percent_interval(self):
        self.assertIsNone(poisson_interval(None))
        self.assertEqual(poisson_interval(0), (0.0, 0.0))
        self.assertEqual(poisson_interval(1), (0.0, 3.0))
        self.assertEqual(poisson_interval(5), (0.5, 9.5))
        self.assertEqual(poisson_interval(49), (35.0, 63.0))
        self.assertEqual(poisson_interval(225), (195.0, 255.0))
        self.assertEqual(poisson_interval(1250), (1179.3, 1320.7))

    def test_the_low_end_is_floored_at_zero(self):
        for count in (1, 2, 3):
            self.assertEqual(poisson_interval(count)[0], 0.0)

    def test_a_count_must_be_a_count(self):
        for bad in (-1, True, '5', float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                poisson_interval(bad)


class ZScore(unittest.TestCase):
    def test_z_is_the_difference_over_the_root_of_the_total(self):
        self.assertAlmostEqual(z_score(30, 18), 12 / 48 ** 0.5)
        self.assertLess(z_score(30, 18), 2)    # the corpus example: not a result
        self.assertEqual(z_score(60, 40), 2.0)
        self.assertEqual(z_score(40, 60), -2.0)

    def test_two_empty_arms_give_zero(self):
        self.assertEqual(z_score(0, 0), 0.0)

    def test_arms_must_be_counts(self):
        for a, b in ((-1, 2), (2, -1), (True, 1), ('3', 1)):
            with self.assertRaises(ValueError):
                z_score(a, b)


class Metrics(unittest.TestCase):
    def test_the_six_metric_names_are_registered(self):
        for name in ('share_arrived_new_listeners', 'brand_post_new_listeners', 'untokenised_new_listeners',
                     'shares_created', 'ga4_landing_new_users', 'ga4_landing_sessions'):
            self.assertIn(name, measurements.METRICS)
            self.assertIn(name, measurements.COUNTS)

    def test_the_example_product_export_is_valid(self):
        data = json.loads((ROOT / 'examples' / 'attribution-export.example.json').read_text(encoding='utf-8'))
        rows = measurements.validate_export(data)
        self.assertEqual({r['metric'] for r in rows}, {'share_arrived_new_listeners', 'brand_post_new_listeners',
                                                       'untokenised_new_listeners', 'shares_created'})
        self.assertTrue(all('synthetic' in r['source'] and 'synthetic' in r['query_ref'] for r in rows))
        result = by_key(objectives(rows, dt.date(2026, 10, 26),
                                   as_of=dt.datetime(2026, 10, 26, 9, 0, tzinfo=UTC)))
        self.assertEqual(result['share_arrived_new_listeners']['availability'], 'measured')
        self.assertEqual(result['share_arrived_new_listeners']['value'], 7)


class Objectives(unittest.TestCase):
    def test_no_export_is_missing_with_a_reason_never_zero(self):
        result = objectives([], TODAY, as_of=AS_OF)
        self.assertEqual([o['key'] for o in result], ['share_arrived_new_listeners', 'brand_post_new_listeners'])
        for item in result:
            self.assertIsNone(item['value'])
            self.assertEqual(item['availability'], 'missing')
            self.assertTrue(item['reason'].startswith('No product export yet'))

    def test_the_shape_and_window_match_reporting(self):
        result = objectives([row('share_arrived_new_listeners', 5)], TODAY, as_of=AS_OF)
        _, _, opens, closes = reporting.week_window(TODAY)
        shape = reporting._objective('x', 'people', None, 'missing', None, reporting.week_window(TODAY))
        schema = reporting.load_schema()['properties']['objectives']
        self.assertEqual(reporting.schema_errors(result, schema, 'objectives'), [])
        for item in result:
            self.assertEqual(set(item), set(shape))
            self.assertEqual((item['window_start'], item['window_end']), (opens, closes))
            self.assertEqual(item['timezone'], 'Europe/London')
        self.assertEqual(opens, '2026-06-29T00:00:00+01:00')

    def test_a_measured_week_carries_its_interval(self):
        result = by_key(objectives([row('share_arrived_new_listeners', 5),
                                    row('brand_post_new_listeners', 49)], TODAY, as_of=AS_OF))
        share = result['share_arrived_new_listeners']
        self.assertEqual((share['value'], share['availability']), (5, 'measured'))
        self.assertIn('0.5 to 9.5', share['reason'])
        self.assertIn('35.0 to 63.0', result['brand_post_new_listeners']['reason'])

    def test_a_measured_zero_stays_zero(self):
        share = objectives([row('share_arrived_new_listeners', 0)], TODAY, as_of=AS_OF)[0]
        self.assertEqual((share['value'], share['availability']), (0, 'measured'))
        self.assertIn('0.0 to 0.0', share['reason'])

    def test_untokenised_arrivals_are_reported_apart(self):
        share = objectives([row('share_arrived_new_listeners', 3), row('untokenised_new_listeners', 11)],
                           TODAY, as_of=AS_OF)[0]
        self.assertEqual(share['value'], 3)
        self.assertIn('Untokenised new listeners, reported apart and never counted here: 11', share['reason'])

    def test_an_old_reading_is_stale_and_null(self):
        late = AS_OF + dt.timedelta(hours=60)
        share = objectives([row('share_arrived_new_listeners', 5)], TODAY, as_of=late)[0]
        self.assertEqual((share['value'], share['availability']), (None, 'stale'))
        self.assertTrue(share['reason'].startswith('Stale'))

    def test_a_row_marked_stale_is_stale(self):
        share = objectives([row('share_arrived_new_listeners', 5, status='stale')], TODAY, as_of=AS_OF)[0]
        self.assertEqual((share['value'], share['availability']), (None, 'stale'))

    def test_another_window_is_a_mismatch_never_added_into_the_week(self):
        daily = [row('share_arrived_new_listeners', 2, window_start=day, window_end=day)
                 for day in ('2026-07-04', '2026-07-05')]
        share = objectives(daily, TODAY, as_of=AS_OF)[0]
        self.assertEqual((share['value'], share['availability']), (None, 'missing'))
        self.assertTrue(share['reason'].startswith('Window mismatch'))
        self.assertIn('2026-07-05 to 2026-07-05', share['reason'])
        self.assertIn(f'{START} to {END}', share['reason'])

    def test_a_week_the_export_reports_missing_is_missing(self):
        share = objectives([row('share_arrived_new_listeners', None, status='missing')], TODAY, as_of=AS_OF)[0]
        self.assertEqual((share['value'], share['availability']), (None, 'missing'))
        self.assertIn('reports this count as missing', share['reason'])

    def test_the_newest_capture_wins(self):
        rows = [row('share_arrived_new_listeners', 4, observed_at='2026-07-06T05:00:00+00:00'),
                row('share_arrived_new_listeners', 6, observed_at='2026-07-06T07:00:00+00:00')]
        self.assertEqual(objectives(rows, TODAY, as_of=AS_OF)[0]['value'], 6)

    def test_rows_are_validated(self):
        with self.assertRaises(ValueError):
            objectives([row('share_arrived_new_listeners', 2.5)], TODAY, as_of=AS_OF)
        with self.assertRaises(ValueError):
            objectives([{**row('share_arrived_new_listeners', 2), 'client_id': 'x'}], TODAY, as_of=AS_OF)


class GA4Rows(unittest.TestCase):
    def test_the_example_export_is_valid(self):
        data = json.loads((ROOT / 'examples' / 'ga4-export.example.json').read_text(encoding='utf-8'))
        rows = ga4_rows(data)
        self.assertEqual(len(rows), 3)
        self.assertIn('synthetic', data['query_ref'])
        self.assertEqual(data['property'], attribution.GA4_PROPERTY)

    def test_a_valid_export_returns_its_rows(self):
        rows = ga4_rows(export())
        self.assertEqual([r['utm_content'] for r in rows], [CREATIVE, OTHER, '(not set)'])

    def test_the_reader_and_the_analyst_agree(self):
        """engine/ga4.py writes what this module reads, for the same property."""
        self.assertEqual(ga4.MEASUREMENT_ID, attribution.GA4_PROPERTY)
        raw = [{'sessionSource': 'tiktok', 'sessionMedium': 'organic_video',
                'sessionCampaignName': 'ft_growth_202610', 'sessionManualAdContent': CREATIVE,
                'newUsers': '12', 'sessions': '14', 'engagedSessions': '9'},
               {'sessionSource': '(direct)', 'sessionMedium': '(none)', 'sessionCampaignName': '(not set)',
                'sessionManualAdContent': '(not set)', 'newUsers': '3', 'sessions': '5', 'engagedSessions': '1'}]
        written = ga4.to_export(raw, START, END, TAKEN)
        self.assertEqual(len(ga4_rows(written)), 2)
        self.assertEqual(by_creative(written), {CREATIVE: {'new_users': 12, 'sessions': 14}})

    def test_unknown_fields_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'unknown: thresholded'):
            ga4_rows(export(thresholded=True))
        with self.assertRaisesRegex(ValueError, 'exactly'):
            ga4_rows(export([{**landing(), 'bounce_rate': 3}]))
        missing = landing()
        del missing['engaged_sessions']
        with self.assertRaises(ValueError):
            ga4_rows(export([missing]))

    def test_person_level_fields_are_refused(self):
        for field in ('client_id', 'clientId', 'user_id', 'userId', 'user_pseudo_id', 'ip', 'ip_address',
                      'email', 'hashed_email', 'device_id', 'deviceId', 'device id', 'session_id',
                      'advertising_id', 'cookie', 'phone', 'gclid'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, 'person-level'):
                    ga4_rows(export([{**landing(), field: 'synthetic'}]))
                with self.assertRaisesRegex(ValueError, 'person-level'):
                    ga4_rows(export(**{field: 'synthetic'}))

    def test_aggregate_count_names_are_not_mistaken_for_people(self):
        for field in attribution.GA4_LABELS + attribution.GA4_COUNTS + attribution.GA4_EXPORT:
            self.assertFalse(attribution._person(field), field)

    def test_contact_like_values_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'contact or credential'):
            ga4_rows(export([landing(source=CONTACT)]))

    def test_counts_must_be_whole_and_non_negative(self):
        for bad in (1.5, '3', True, None, -1):
            for key in attribution.GA4_COUNTS:
                with self.subTest(key=key, value=bad):
                    with self.assertRaisesRegex(ValueError, 'whole, non-negative'):
                        ga4_rows(export([{**landing(), key: bad}]))

    def test_engaged_sessions_never_exceed_sessions(self):
        with self.assertRaisesRegex(ValueError, 'engaged sessions'):
            ga4_rows(export([landing(sessions=3, engaged=4)]))

    def test_only_the_full_time_property(self):
        with self.assertRaisesRegex(ValueError, 'G-W2QL8RKFJ1'):
            ga4_rows(export(property='G-AAAAAAAAAA'))
        with self.assertRaises(ValueError):
            ga4_rows(export(product='other'))
        with self.assertRaises(ValueError):
            ga4_rows(export(source='posthog'))

    def test_windows_are_whole_london_days(self):
        with self.assertRaisesRegex(ValueError, 'whole London days'):
            ga4_rows(export(window_start='2026-06-29T00:00:00+01:00'))
        with self.assertRaisesRegex(ValueError, 'whole London days'):
            ga4_rows(export(window_end='2026-07-05T23:59:59+01:00'))
        with self.assertRaisesRegex(ValueError, 'starts after it ends'):
            ga4_rows(export(window_start='2026-07-06', window_end='2026-07-05'))
        # 23:30 UTC on 5 July is 00:30 on 6 July in London: the last day had ended.
        self.assertTrue(ga4_rows(export(observed_at='2026-07-05T23:30:00+00:00')))
        # 22:30 UTC on 5 July is 23:30 in London: the last day had not ended.
        with self.assertRaisesRegex(ValueError, 'had not ended in London'):
            ga4_rows(export(observed_at='2026-07-05T22:30:00+00:00'))
        with self.assertRaisesRegex(ValueError, 'time zone'):
            ga4_rows(export(observed_at='2026-07-06T06:00:00'))
        with self.assertRaisesRegex(ValueError, 'future'):
            future = (dt.datetime.now(UTC) + dt.timedelta(days=2)).isoformat()
            ga4_rows(export(observed_at=future))

    def test_utm_content_is_a_creative_id_or_not_set(self):
        self.assertTrue(growth.CREATIVE_ID.match(CREATIVE))
        for label in ('newsletter', '(redacted)', '(other)', 'tt_clash_clip_c01_h01_v1_20261020', ''):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    ga4_rows(export([landing(label)]))

    def test_one_campaign_tag_appears_once(self):
        with self.assertRaisesRegex(ValueError, 'repeats a campaign tag'):
            ga4_rows(export([landing(), landing()]))

    def test_the_export_is_an_object_with_a_list_of_rows(self):
        with self.assertRaises(ValueError):
            ga4_rows([landing()])
        with self.assertRaises(ValueError):
            ga4_rows(export(rows={'a': landing()}))
        with self.assertRaises(ValueError):
            ga4_rows(export(query_ref=' '))


class GA4Observations(unittest.TestCase):
    def test_totals_become_two_measured_observations(self):
        rows = ga4_observations(export())
        self.assertEqual([r['metric'] for r in rows], ['ga4_landing_new_users', 'ga4_landing_sessions'])
        self.assertEqual([r['value'] for r in rows], [58, 76])
        for item in rows:
            self.assertEqual(measurements.validate(dict(item)), item)
            self.assertEqual((item['status'], item['source']), ('measured', 'ga4'))
            self.assertEqual(item['query_ref'], 'synthetic:ga4-landings-by-creative:v0')
            self.assertEqual((item['window_start'], item['window_end']), (START, END))
            self.assertIn('never listeners', item['note'])
            self.assertIn('55 sessions untagged', item['note'])
        measurements.validate_export({'schema_version': 1, 'product': 'fulltime', 'observations': rows})

    def test_an_empty_export_is_a_measured_zero(self):
        rows = ga4_observations(export([]))
        self.assertEqual([r['value'] for r in rows], [0, 0])
        self.assertTrue(all(r['status'] == 'measured' for r in rows))

    def test_a_refused_export_gives_no_observations(self):
        with self.assertRaises(ValueError):
            ga4_observations(export([{**landing(), 'client_id': 'synthetic'}]))


class NoPathToListeners(unittest.TestCase):
    """GA4 landings are web sessions, never listeners (MEASUREMENT.md)."""

    def test_ga4_metrics_are_never_listener_metrics(self):
        listeners = {m for m in measurements.METRICS if m.endswith('_listeners')}
        self.assertEqual(listeners, {'share_arrived_new_listeners', 'brand_post_new_listeners',
                                     'untokenised_new_listeners'})
        self.assertFalse(set(attribution.GA4_METRICS) & listeners)
        for exported in (export(), export([]), export([landing(new_users=500, sessions=900, engaged=10)])):
            produced = {r['metric'] for r in ga4_observations(exported)}
            self.assertEqual(produced, set(attribution.GA4_METRICS))
            self.assertFalse(produced & listeners)

    def test_ga4_rows_never_fill_a_listener_objective(self):
        result = objectives(ga4_observations(export()), TODAY, as_of=AS_OF)
        for item in result:
            self.assertIsNone(item['value'])
            self.assertTrue(item['reason'].startswith('No product export yet'))
        card = measurements.scorecard(ga4_observations(export()), START, END, as_of=AS_OF)
        for metric in ('share_arrived_new_listeners', 'brand_post_new_listeners', 'untokenised_new_listeners'):
            self.assertEqual(card[metric]['status'], 'missing')
        self.assertEqual(card['ga4_landing_sessions']['value'], 76)

    def test_a_ga4_row_relabelled_as_listeners_is_refused(self):
        for metric in ('share_arrived_new_listeners', 'brand_post_new_listeners', 'untokenised_new_listeners'):
            forged = dict(ga4_observations(export())[0], metric=metric)
            with self.assertRaisesRegex(ValueError, 'never listeners'):
                objectives([forged], TODAY, as_of=AS_OF)
            ref = dict(row(metric, 3), query_ref='ga4-data-v1beta:runReport:landings-by-creative:v1')
            with self.assertRaisesRegex(ValueError, 'never listeners'):
                objectives([ref], TODAY, as_of=AS_OF)

    def test_no_ga4_function_names_a_listener_metric(self):
        for name in ('ga4_rows', 'ga4_observations', 'by_creative'):
            source = inspect.getsource(getattr(attribution, name))
            self.assertNotIn('_listeners', source.replace("endswith('_listeners')", ''), name)


class ByCreative(unittest.TestCase):
    def test_landings_by_creative_with_untagged_apart(self):
        result = by_creative(export())
        self.assertEqual(dict(result), {CREATIVE: {'new_users': 12, 'sessions': 14},
                                        OTHER: {'new_users': 6, 'sessions': 7}})
        self.assertNotIn('(not set)', result)
        self.assertEqual(result.untagged, {'new_users': 40, 'sessions': 55})
        self.assertEqual(json.loads(json.dumps(result)), dict(result))

    def test_one_creative_across_sources_is_summed(self):
        result = by_creative(export([landing(), landing(source='tiktok-app', new_users=1, sessions=2, engaged=0)]))
        self.assertEqual(result[CREATIVE], {'new_users': 13, 'sessions': 16})
        self.assertEqual(result.untagged, {'new_users': 0, 'sessions': 0})

    def test_only_untagged_traffic_names_no_creative(self):
        result = by_creative(export([landing('(not set)', '(direct)', 3, 4, 1)]))
        self.assertEqual(dict(result), {})
        self.assertEqual(result.untagged, {'new_users': 3, 'sessions': 4})

    def test_the_input_export_is_not_changed(self):
        original = export()
        kept = copy.deepcopy(original)
        by_creative(original)
        ga4_observations(original)
        self.assertEqual(original, kept)


if __name__ == '__main__':
    unittest.main()
