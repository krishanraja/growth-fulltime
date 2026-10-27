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
        self.assertEqual([r['creative_id'] for r in rows if 'creative_id' in r], ['TT_CLASH_CLIP_C01_H01_V1_20261020'])
        self.assertEqual(result['brand_post_new_listeners']['value'], 2)     # the total row, never the breakdown


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


class GA4NeverEntersHistoryAsListeners(unittest.TestCase):
    """Review wave 2: a GA4 listener row was accepted at import, then blocked every later reading."""

    def test_the_import_refuses_a_ga4_listener_row(self):
        for metric in ('share_arrived_new_listeners', 'brand_post_new_listeners', 'untokenised_new_listeners'):
            forged = row(metric, 58, source='ga4', query_ref='ga4:landings:v1')
            with self.subTest(metric=metric):
                with self.assertRaisesRegex(ValueError, 'never listeners'):
                    measurements.validate(dict(forged))
                with self.assertRaisesRegex(ValueError, 'never listeners'):
                    measurements.validate_export({'schema_version': 1, 'product': 'fulltime',
                                                  'observations': [forged]})

    def test_every_spelling_of_google_analytics_is_refused(self):
        for source, ref in (('control-center', 'control-center:ga4_landings:v1'),
                            ('Google Analytics 4 Data API', 'landings-by-creative:v1'),
                            ('G-W2QL8RKFJ1', 'newUsers:v1'), ('GA-4', 'newUsers:v1'),
                            ('synthetic-product-export', 'analyticsdata.googleapis.com:landings'),
                            ('synthetic-product-export', 'runReport:newUsers'),
                            ('GA landings', 'synthetic:v1'), ('synthetic', 'gtag:page_view:v1')):
            with self.subTest(source=source, query_ref=ref):
                with self.assertRaisesRegex(ValueError, 'never listeners'):
                    objectives([row('share_arrived_new_listeners', 58, source=source, query_ref=ref)],
                               TODAY, as_of=AS_OF)

    def test_product_sources_and_ga4_landing_rows_still_pass(self):
        for source, ref in (('full-time-postgres', 'share-token-first-touch-7d:v2'),
                            ('posthog-product-analytics', 'first-finished-show:v1'),
                            ('synthetic-product-export', 'synthetic:share-token-first-listen-7d:v0')):
            with self.subTest(source=source):
                share = objectives([row('share_arrived_new_listeners', 5, source=source, query_ref=ref)],
                                   TODAY, as_of=AS_OF)[0]
                self.assertEqual(share['value'], 5)
        landing_row = row('ga4_landing_sessions', 76, source='ga4', query_ref='ga4:landings:v1')
        self.assertEqual(measurements.validate(dict(landing_row)), landing_row)

    def test_an_old_bad_row_never_blocks_a_clean_week(self):
        """A row imported before the import refused it stays in history; it must not
        stop every later reading."""
        old = row('brand_post_new_listeners', 58, source='ga4', query_ref='ga4:landings:v1',
                  window_start='2026-06-22', window_end='2026-06-28', observed_at='2026-06-29T06:30:00+00:00')
        late = row('share_arrived_new_listeners', 9, window_start='2026-06-22', window_end='2026-06-28',
                   observed_at='2026-06-28T10:00:00+00:00')
        result = by_key(objectives([old, late, row('share_arrived_new_listeners', 7)], TODAY, as_of=AS_OF))
        self.assertEqual(result['share_arrived_new_listeners']['value'], 7)
        self.assertTrue(result['brand_post_new_listeners']['reason'].startswith('No product export yet'))
        card = measurements.scorecard([old, late, row('share_arrived_new_listeners', 7)], START, END, as_of=AS_OF)
        self.assertEqual(card['share_arrived_new_listeners']['value'], 7)

    def test_a_bad_row_for_this_week_still_refuses_the_reading(self):
        with self.assertRaisesRegex(ValueError, 'never listeners'):
            objectives([row('share_arrived_new_listeners', 7),
                        row('untokenised_new_listeners', 3, source='ga4')], TODAY, as_of=AS_OF)


class WholeLondonWeeks(unittest.TestCase):
    """Review wave 2: a capture taken during the window's last day was accepted as the whole week."""

    def test_a_capture_during_the_last_london_day_is_refused(self):
        for taken in ('2026-07-05T10:00:00+00:00',      # 11:00 on Sunday 5 July in London
                      '2026-07-04T23:05:00Z',           # 00:05 on 5 July in London
                      '2026-07-06T09:30:00+14:00'):     # 20:30 on 5 July in London, dated the 6th locally
            with self.subTest(observed_at=taken):
                with self.assertRaisesRegex(ValueError, 'whole London days'):
                    measurements.validate(row('share_arrived_new_listeners', 3, observed_at=taken))
                with self.assertRaisesRegex(ValueError, 'whole London days'):
                    objectives([row('share_arrived_new_listeners', 3, observed_at=taken)], TODAY, as_of=AS_OF)

    def test_a_capture_after_the_last_london_day_passes(self):
        # 23:30 UTC on 5 July is 00:30 on 6 July in London: the week had ended.
        share = objectives([row('share_arrived_new_listeners', 3, observed_at='2026-07-05T23:30:00+00:00')],
                           TODAY, as_of=AS_OF)[0]
        self.assertEqual((share['value'], share['availability']), (3, 'measured'))
        # In winter London is on UTC: 00:05 UTC on Monday 12 January is past Sunday.
        winter = row('share_arrived_new_listeners', 4, window_start='2026-01-05', window_end='2026-01-11',
                     observed_at='2026-01-12T00:05:00Z')
        self.assertEqual(measurements.validate(dict(winter)), winter)


class StrictDates(unittest.TestCase):
    """Review wave 2: newer Pythons read more date and time spellings than 3.9 does."""

    def test_only_yyyy_mm_dd_windows(self):
        for start, end in (('20260629', '20260705'), ('2026-W27-1', '2026-W27-7'), ('2026-06-29', '2026-07-05 '),
                           (20260629, END)):
            with self.subTest(start=start, end=end):
                with self.assertRaisesRegex(ValueError, 'YYYY-MM-DD'):
                    measurements.validate(row('share_arrived_new_listeners', 3, window_start=start, window_end=end))

    def test_one_week_written_two_ways_cannot_pass_the_duplicate_check(self):
        with self.assertRaises(ValueError):
            measurements.validate_export({'schema_version': 1, 'product': 'fulltime', 'observations': [
                row('share_arrived_new_listeners', 3),
                row('share_arrived_new_listeners', 4, window_start='20260629', window_end='20260705')]})

    def test_only_rfc_3339_captures(self):
        for taken in ('2026-07-06 06:00:00+00:00', '2026-07-06T06:00+00:00', '2026-07-06T06:00:00',
                      '20260706T060000Z', '2026-07-06T06:00:00z'):
            with self.subTest(observed_at=taken):
                with self.assertRaisesRegex(ValueError, 'RFC 3339'):
                    measurements.validate(row('share_arrived_new_listeners', 3, observed_at=taken))
        self.assertTrue(measurements.validate(row('share_arrived_new_listeners', 3,
                                                  observed_at='2026-07-06T06:00:00.5Z')))

    def test_source_and_query_ref_are_text(self):
        for field, bad in (('source', 5), ('query_ref', ['x']), ('source', ' ')):
            with self.subTest(field=field, value=bad):
                with self.assertRaisesRegex(ValueError, 'non-empty text'):
                    measurements.validate(row('shares_created', 3, **{field: bad}))


class BreakdownByCreative(unittest.TestCase):
    """Review wave 2: the briefed per-creative brand-post breakdown could not be exported."""

    def test_a_total_and_one_row_per_creative_are_accepted(self):
        rows = measurements.validate_export({'schema_version': 1, 'product': 'fulltime', 'observations': [
            row('brand_post_new_listeners', 5), row('brand_post_new_listeners', 3, creative_id=CREATIVE),
            row('brand_post_new_listeners', 2, creative_id=OTHER), row('share_arrived_new_listeners', 7)]})
        self.assertEqual(len(rows), 4)
        result = by_key(objectives(rows, TODAY, as_of=AS_OF))
        self.assertEqual(result['brand_post_new_listeners']['value'], 5)
        self.assertEqual(measurements.scorecard(rows, START, END, as_of=AS_OF)['brand_post_new_listeners']['value'], 5)

    def test_a_breakdown_row_is_never_the_total(self):
        newer = row('brand_post_new_listeners', 3, creative_id=CREATIVE, observed_at='2026-07-06T07:00:00+00:00')
        rows = [row('brand_post_new_listeners', 5), newer]
        self.assertEqual(by_key(objectives(rows, TODAY, as_of=AS_OF))['brand_post_new_listeners']['value'], 5)
        self.assertEqual(measurements.scorecard(rows, START, END, as_of=AS_OF)['brand_post_new_listeners']['value'], 5)
        alone = by_key(objectives([newer], TODAY, as_of=AS_OF))['brand_post_new_listeners']
        self.assertEqual((alone['value'], alone['availability']), (None, 'missing'))

    def test_the_breakdown_is_refused_anywhere_else(self):
        for bad in (row('share_arrived_new_listeners', 3, creative_id=CREATIVE),
                    row('ga4_landing_sessions', 3, creative_id=CREATIVE),
                    row('brand_post_new_listeners', 3, creative_id=CREATIVE + '\n'),
                    row('brand_post_new_listeners', 3, creative_id='newsletter'),
                    row('brand_post_new_listeners', 3, creative_id=None)):
            with self.subTest(row=bad):
                with self.assertRaisesRegex(ValueError, 'creative_id'):
                    measurements.validate(bad)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            measurements.validate_export({'schema_version': 1, 'product': 'fulltime', 'observations': [
                row('brand_post_new_listeners', 3, creative_id=CREATIVE),
                row('brand_post_new_listeners', 2, creative_id=CREATIVE)]})


class UntokenisedSideFigure(unittest.TestCase):
    """Review wave 2: the untokenised count ignored a newer missing capture and staleness."""

    def test_a_newer_missing_capture_is_reported_as_missing(self):
        share = objectives([row('share_arrived_new_listeners', 7),
                            row('untokenised_new_listeners', 40, observed_at='2026-07-06T05:00:00+00:00'),
                            row('untokenised_new_listeners', None, status='missing',
                                observed_at='2026-07-06T05:30:00+00:00')], TODAY, as_of=AS_OF)[0]
        self.assertEqual(share['value'], 7)
        self.assertNotIn(': 40.', share['reason'])
        self.assertIn('Untokenised new listeners, reported apart: missing.', share['reason'])

    def test_an_old_untokenised_count_is_reported_as_stale(self):
        later = dt.datetime(2026, 7, 8, 7, 0, tzinfo=UTC)
        share = objectives([row('share_arrived_new_listeners', 7, observed_at='2026-07-07T13:30:00+00:00'),
                            row('untokenised_new_listeners', 40, observed_at='2026-07-06T06:30:00+00:00')],
                           TODAY, as_of=later)[0]
        self.assertEqual((share['value'], share['availability']), (7, 'measured'))
        self.assertNotIn(': 40.', share['reason'])
        self.assertIn('Untokenised new listeners, reported apart: stale.', share['reason'])
        marked = objectives([row('share_arrived_new_listeners', 7),
                             row('untokenised_new_listeners', 40, status='stale')], TODAY, as_of=AS_OF)[0]
        self.assertIn('reported apart: stale.', marked['reason'])


class ExposureScaledZ(unittest.TestCase):
    """Review wave 2: z assumed equal exposure without recording it."""

    def test_equal_exposure_is_the_plain_test(self):
        self.assertEqual(z_score(60, 30, 1, 1), z_score(60, 30))
        self.assertAlmostEqual(z_score(60, 30, 3, 3), 30 / 90 ** 0.5)

    def test_unequal_exposure_scales_arm_b(self):
        # a: 60 over 3 posts (20 a post), b: 30 over 1 post (30 a post): b leads per post.
        self.assertAlmostEqual(z_score(60, 30, 3, 1), (60 - 90) / (3 * 90) ** 0.5)
        self.assertLess(z_score(60, 30, 3, 1), 0)
        self.assertAlmostEqual(z_score(30, 60, 1, 3), -z_score(60, 30, 3, 1))

    def test_exposure_must_be_above_zero(self):
        for bad in (0, -1, True, float('nan'), float('inf'), '2', None):
            with self.subTest(exposure=bad):
                with self.assertRaisesRegex(ValueError, 'exposure'):
                    z_score(60, 30, bad, 1)
                with self.assertRaisesRegex(ValueError, 'exposure'):
                    z_score(60, 30, 1, bad)


class GA4Labels(unittest.TestCase):
    """Review wave 2: a creative ID with a trailing newline split one creative in two;
    the documents told exporters to fold Google's (other) row into (not set)."""

    def test_utm_content_must_match_a_creative_id_in_full(self):
        with self.assertRaisesRegex(ValueError, 'creative ID'):
            ga4_rows(export([landing(), landing(CREATIVE + '\n', new_users=1, sessions=1, engaged=0)]))
        with self.assertRaises(ValueError):
            by_creative(export([landing(CREATIVE + '\n')]))

    def test_google_other_row_and_limitation_flags_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'not sent at all'):
            ga4_rows(export([landing('(other)')]))
        for flag in ('limited', 'thresholded', 'other_row'):
            with self.subTest(flag=flag):
                with self.assertRaisesRegex(ValueError, f'unknown: {flag}'):
                    ga4_rows(export(**{flag: True}))

    def test_the_contract_no_longer_folds_other_into_not_set(self):
        text = (ROOT / 'MEASUREMENT.md').read_text(encoding='utf-8')
        self.assertIn("but never Google's `(other)` row", text)
        self.assertIn('is not sent at all', text)
        self.assertNotIn('must fold other labels into `(not set)` first.', text)


class OneNorthStarDefinition(unittest.TestCase):
    """Review wave 2: MEASUREMENT.md and the product brief defined share-arrived differently."""

    RULE = ('A new listener counts as share-arrived when their first touch, stored once on their first visit and '
            'never overwritten, carried a valid share token `s` and their first finished show came within 7 days '
            'of it; they count in the London week of that first finished show.')

    def test_the_contract_and_the_brief_state_the_same_rule(self):
        contract = (ROOT / 'MEASUREMENT.md').read_text(encoding='utf-8')
        brief = (ROOT / 'briefs' / '2026-10-27-share-attribution.md').read_text(encoding='utf-8')
        for text in (contract, brief):
            self.assertIn(self.RULE, text)
            self.assertIn('two days later', text)     # the case the two used to answer differently
            self.assertNotIn('\u2014', text)
        self.assertNotIn('the earliest in the window gets the credit', contract)


if __name__ == '__main__':
    unittest.main()
