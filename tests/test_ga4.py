"""The read-only Google Analytics 4 reader against a local in-process stand-in.
Nothing here reaches the network: the stand-in listens on 127.0.0.1 only, and
every credential below is synthetic."""
import base64
import contextlib
import datetime as dt
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import ga4, reporting

CLIENT_ID = '000000000000-standin.apps.example.invalid'
CLIENT_SECRET = 'standin-client-secret-' + 'S' * 20
REFRESH = 'standin-refresh-' + 'R' * 40
NEW_REFRESH = 'standin-new-refresh-' + 'N' * 36
ACCESS = 'standin-access-' + 'A' * 40
PROPERTY_ID = '123456789'
SECRETS = (CLIENT_SECRET, REFRESH, NEW_REFRESH, ACCESS)
ENV = {'GA4_CLIENT_ID': CLIENT_ID, 'GA4_CLIENT_SECRET': CLIENT_SECRET,
       'GA4_REFRESH_TOKEN': REFRESH, 'GA4_PROPERTY_ID': PROPERTY_ID}
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ga4_row(source, medium, campaign, content, new_users, sessions, engaged):
    return {'dimensionValues': [{'value': v} for v in (source, medium, campaign, content)],
            'metricValues': [{'value': str(v)} for v in (new_users, sessions, engaged)]}


class GoogleStandIn:
    """Google's token endpoint and the Data API's runReport, for one synthetic property."""

    def __init__(self):
        self.calls, self.reports, self.host_checks = [], [], []
        self.rows = [ga4_row('tiktok', 'social', 'matchday', 'TT_CLASH_CLIP_C01_H01_V1_20261020', 3, 4, 2)]
        self.hosts = [('fulltime.fm', 4)]   # what the hostName check answers
        self.meta = {}                      # extra ResponseMetaData, such as subjectToThresholding
        self.page_cap = None          # serve fewer rows than asked, as a real server may
        self.refuse = {}              # route -> status
        self.redirect = set()         # routes answered with a 302
        self.oversize = False
        self.challenge = self.redirect_uri = None
        self.time_zone = 'Europe/London'
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, payload, headers=()):
                body = payload if isinstance(payload, bytes) else json.dumps(payload, separators=(',', ':')).encode()
                self.send_response(status)
                for name, value in headers:
                    self.send_header(name, value)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                path, _, query = self.path.partition('?')
                length = int(self.headers.get('Content-Length') or 0)
                raw = self.rfile.read(length).decode('utf-8') if length else ''
                route = 'token' if path == '/token' else 'report' if path.endswith(':runReport') else path
                outer.calls.append((route, path, query))
                if route in outer.redirect:
                    return self._send(302, {}, [('Location', '/elsewhere')])
                if route in outer.refuse:
                    return self._send(outer.refuse[route], {'error': 'refused'})
                if outer.oversize:
                    return self._send(200, b' ' * (ga4.LIMIT + 10))
                if route == 'token':
                    return outer.token(self, dict(urllib.parse.parse_qsl(raw)))
                if route == 'report':
                    return outer.report(self, path, json.loads(raw))
                return self._send(404, {'error': 'not_found'})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def token(self, h, form):
        if (form.get('client_id'), form.get('client_secret')) != (CLIENT_ID, CLIENT_SECRET):
            return h._send(401, {'error': 'invalid_client'})
        if form.get('grant_type') == 'refresh_token':
            if form.get('refresh_token') != REFRESH:
                return h._send(400, {'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'})
            return h._send(200, {'access_token': ACCESS, 'expires_in': 3599, 'token_type': 'Bearer', 'scope': ga4.SCOPE})
        if form.get('grant_type') == 'authorization_code':
            verifier = form.get('code_verifier', '')
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            if form.get('code') != 'standin-code' or challenge != self.challenge or form.get('redirect_uri') != self.redirect_uri:
                return h._send(400, {'error': 'invalid_grant'})
            return h._send(200, {'access_token': ACCESS, 'refresh_token': NEW_REFRESH, 'expires_in': 3599,
                                 'token_type': 'Bearer', 'scope': ga4.SCOPE})
        return h._send(400, {'error': 'unsupported_grant_type'})

    def report(self, h, path, body):
        if h.headers.get('Authorization') != 'Bearer ' + ACCESS:
            return h._send(401, {'error': {'code': 401, 'status': 'UNAUTHENTICATED'}})
        if path != f'/v1beta/properties/{PROPERTY_ID}:runReport':
            return h._send(404, {'error': {'code': 404}})
        hosts = [d['name'] for d in body['dimensions']] == ['hostName']
        (self.host_checks if hosts else self.reports).append(body)
        source = [{'dimensionValues': [{'value': name}], 'metricValues': [{'value': str(n)}]}
                  for name, n in self.hosts] if hosts else self.rows
        offset, limit = int(body.get('offset', 0)), int(body.get('limit', 10000))
        take = min(limit, self.page_cap or limit)
        page = source[offset:offset + take]
        answer = {'dimensionHeaders': [{'name': d['name']} for d in body['dimensions']],
                  'metricHeaders': [{'name': m['name'], 'type': 'TYPE_INTEGER'} for m in body['metrics']],
                  'rowCount': len(source), 'kind': 'analyticsData#runReport',
                  'metadata': {'currencyCode': 'GBP', 'timeZone': self.time_zone, **self.meta}}
        if page:
            answer['rows'] = page
        return h._send(200, answer)


class Captured:
    """Everything a run could leak through: stdout, stderr and the root logger."""

    def __enter__(self):
        self.out, self.err, self.log = io.StringIO(), io.StringIO(), io.StringIO()
        self.handler = logging.StreamHandler(self.log)
        logging.getLogger().addHandler(self.handler)
        self.level = logging.getLogger().level
        logging.getLogger().setLevel(logging.DEBUG)
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(contextlib.redirect_stdout(self.out))
        self.stack.enter_context(contextlib.redirect_stderr(self.err))
        return self

    def __exit__(self, *exc):
        self.stack.close()
        logging.getLogger().removeHandler(self.handler)
        logging.getLogger().setLevel(self.level)
        return False

    def text(self):
        return self.out.getvalue() + self.err.getvalue() + self.log.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.google = GoogleStandIn()
        self.root = tempfile.TemporaryDirectory()
        self.local = Path(self.root.name) / 'local'
        self.local.mkdir()
        self.creds = ga4.credentials(self.local, ENV)

    def tearDown(self):
        self.google.close()
        self.root.cleanup()

    def assertClean(self, text):
        for secret in SECRETS:
            self.assertNotIn(secret, text)
            self.assertNotIn(secret[-24:], text)

    def assertRaisesCode(self, code, call, *args, **kwargs):
        with self.assertRaises(ga4.GA4Error) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)
        self.assertClean(repr(caught.exception) + str(caught.exception.args))
        return caught.exception

    def write_file(self, data, mode=0o600):
        path = self.local / 'ga4' / 'oauth.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        os.chmod(path, mode)
        return path


class CredentialTests(Base):
    def test_environment_credentials_and_a_redacted_printed_form(self):
        creds = ga4.credentials(self.local, ENV)
        self.assertIsInstance(creds, dict)
        self.assertEqual((creds['source'], creds['property_id']), ('environment', PROPERTY_ID))
        self.assertEqual(creds['refresh_token'], REFRESH)
        self.assertClean(repr(creds) + str(creds) + f'{creds}')

    def test_missing_credentials_are_none(self):
        self.assertIsNone(ga4.credentials(self.local, {}))
        partial = {k: v for k, v in ENV.items() if k != 'GA4_REFRESH_TOKEN'}
        self.assertIsNone(ga4.credentials(self.local, partial))
        self.assertRaisesCode('missing_ga4_credentials', ga4.access_token, None)

    def test_the_property_must_be_the_numeric_id_not_the_measurement_id(self):
        self.assertRaisesCode('ga4_property_id_invalid', ga4.credentials, self.local,
                              {**ENV, 'GA4_PROPERTY_ID': 'G-W2QL8RKFJ1'})
        self.assertEqual(ga4.credentials(self.local, {**ENV, 'GA4_PROPERTY_ID': 'properties/42'})['property_id'], '42')
        without = ga4.credentials(self.local, {**ENV, 'GA4_PROPERTY_ID': ''})
        self.assertIsNone(without['property_id'])
        self.assertRaisesCode('missing_ga4_property_id', ga4.run_report, without, '2026-10-20', '2026-10-26',
                              self.google.url, token_url=self.google.url + '/token')
        self.assertEqual(self.google.calls, [])

    @unittest.skipUnless(os.name == 'posix', 'file modes are POSIX')
    def test_a_file_others_can_read_is_refused_and_a_private_one_is_used(self):
        data = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': REFRESH,
                'property_id': PROPERTY_ID}
        path = self.write_file(data, 0o644)
        self.assertRaisesCode('ga4_credentials_exposed', ga4.credentials, self.local, {})
        os.chmod(path, 0o640)
        self.assertRaisesCode('ga4_credentials_exposed', ga4.credentials, self.local, {})
        os.chmod(path, 0o600)
        creds = ga4.credentials(self.local, {})
        self.assertEqual((creds['source'], creds['client_secret'], creds['property_id']),
                         ('file', CLIENT_SECRET, PROPERTY_ID))
        self.assertEqual(ga4.credentials(self.local, {'GA4_PROPERTY_ID': '987'})['property_id'], '987')

    def test_a_malformed_file_is_refused_without_its_contents(self):
        self.write_file({'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET})
        self.assertRaisesCode('ga4_credentials_malformed', ga4.credentials, self.local, {})
        path = self.local / 'ga4' / 'oauth.json'
        path.write_text('{"client_secret": "' + CLIENT_SECRET + '"', encoding='utf-8')
        self.assertRaisesCode('ga4_credentials_malformed', ga4.credentials, self.local, {})
        self.assertRaisesCode('ga4_credentials_malformed', ga4.credentials, self.local,
                              {**ENV, 'GA4_CLIENT_SECRET': 'has a space in it'})


class TransportTests(Base):
    def test_token_refresh_against_the_stand_in(self):
        with Captured() as seen:
            token = ga4.access_token(self.creds, self.google.url + '/token')
        self.assertEqual(token, ACCESS)
        self.assertEqual(self.google.calls[0][0], 'token')
        self.assertClean(seen.text())

    def test_a_refused_refresh_token_is_unauthorized(self):
        stale = ga4.credentials(self.local, {**ENV, 'GA4_REFRESH_TOKEN': 'standin-revoked-' + 'X' * 30})
        self.assertRaisesCode('unauthorized', ga4.access_token, stale, self.google.url + '/token')
        wrong_client = ga4.credentials(self.local, {**ENV, 'GA4_CLIENT_SECRET': 'standin-wrong-' + 'W' * 30})
        self.assertRaisesCode('unauthorized', ga4.access_token, wrong_client, self.google.url + '/token')

    def test_a_401_from_the_data_api_is_unauthorized(self):
        self.assertRaisesCode('unauthorized', ga4.run_report, self.creds, '2026-10-20', '2026-10-26',
                              self.google.url, access='standin-expired-access-' + 'E' * 20)
        self.google.refuse['report'] = 403
        self.assertRaisesCode('forbidden', ga4.run_report, self.creds, '2026-10-20', '2026-10-26',
                              self.google.url, access=ACCESS)

    def test_https_only_outside_the_loopback_stand_in(self):
        for url in ('http://example.invalid/token', 'http://localhost:9/token', 'ftp://example.invalid/token',
                    'https://user:pw@oauth2.googleapis.com/token', 'https://oauth2.googleapis.com/token?x=1',
                    'https:///token'):
            self.assertRaisesCode('bad_base_url', ga4.access_token, self.creds, url)
        for url in ('http://analyticsdata.googleapis.com', 'https://analyticsdata.googleapis.com/v1beta',
                    'https://analyticsdata.googleapis.com#x'):
            self.assertRaisesCode('bad_base_url', ga4.run_report, self.creds, '2026-10-20', '2026-10-26', url,
                                  access=ACCESS)
        self.assertEqual(self.google.calls, [])
        self.assertEqual((ga4.TOKEN_URL[:8], ga4.DATA_URL[:8], ga4.AUTH_URL[:8]), ('https://',) * 3)

    def test_redirects_are_refused_never_followed(self):
        self.google.redirect.add('token')
        self.assertRaisesCode('redirect_refused', ga4.access_token, self.creds, self.google.url + '/token')
        self.google.redirect = {'report'}
        self.assertRaisesCode('redirect_refused', ga4.run_report, self.creds, '2026-10-20', '2026-10-26',
                              self.google.url, access=ACCESS)
        self.assertNotIn('/elsewhere', [c[1] for c in self.google.calls])

    def test_unavailable_oversized_and_misshapen_answers_are_codes(self):
        self.google.refuse['token'] = 503
        self.assertRaisesCode('ga4_unavailable', ga4.access_token, self.creds, self.google.url + '/token')
        self.google.refuse = {'report': 429}
        self.assertRaisesCode('ga4_unavailable', ga4.run_report, self.creds, '2026-10-20', '2026-10-26',
                              self.google.url, access=ACCESS)
        self.google.refuse, self.google.oversize = {}, True
        self.assertRaisesCode('response_too_large', ga4.run_report, self.creds, '2026-10-20', '2026-10-26',
                              self.google.url, access=ACCESS)
        closed = self.google.url
        self.google.close()
        self.assertRaisesCode('ga4_unavailable', ga4.access_token, self.creds, closed + '/token')
        self.google = GoogleStandIn()
        self.google.rows = [{'dimensionValues': [{'value': 'x'}], 'metricValues': []}]
        self.assertRaisesCode('bad_response', ga4.run_report, self.creds, '2026-10-20', '2026-10-26',
                              self.google.url, access=ACCESS)


class ReportTests(Base):
    def test_the_request_is_aggregate_only_and_pages_until_row_count(self):
        self.google.rows = [ga4_row('tiktok', 'social', 'matchday', f'TT_TAKE_C{i:02d}', 1, 2, 1) for i in range(7)]
        self.google.page_cap = 3
        rows = ga4.run_report(self.creds, dt.date(2026, 10, 20), dt.date(2026, 10, 26), self.google.url,
                              token_url=self.google.url + '/token')
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows.pages, 3)
        self.assertEqual(rows.time_zone, 'Europe/London')
        self.assertEqual([r['offset'] for r in self.google.reports], [0, 3, 6])
        self.assertEqual(self.google.host_checks, [ga4.host_request('2026-10-20', '2026-10-26')])
        self.assertEqual(([d['name'] for d in self.google.host_checks[0]['dimensions']],
                          [m['name'] for m in self.google.host_checks[0]['metrics']]), (['hostName'], ['sessions']))
        for body in self.google.reports:
            self.assertEqual(body['limit'], 3500)
            self.assertEqual(body['dateRanges'], [{'startDate': '2026-10-20', 'endDate': '2026-10-26'}])
            self.assertEqual([d['name'] for d in body['dimensions']],
                             ['sessionSource', 'sessionMedium', 'sessionCampaignName', 'sessionManualAdContent'])
            self.assertEqual([m['name'] for m in body['metrics']], ['newUsers', 'sessions', 'engagedSessions'])
            text = json.dumps(body).lower()
            for personal in ('clientid', 'userid', 'device', 'pseudo', 'city', 'useragent', 'streamid'):
                self.assertNotIn(personal, text)
        self.assertEqual(rows[0], {'sessionSource': 'tiktok', 'sessionMedium': 'social',
                                   'sessionCampaignName': 'matchday', 'sessionManualAdContent': 'TT_TAKE_C00',
                                   'newUsers': '1', 'sessions': '2', 'engagedSessions': '1'})
        self.assertEqual([c[2] for c in self.google.calls if c[0] == 'report'], ['prettyPrint=false'] * 4)

    def test_full_pages_stay_under_the_size_cap(self):
        # 60-character campaign labels made a 10,000-row page 2.3 MB, over the 2 MB cap.
        self.google.rows = [ga4_row('newsletter.example.com', 'email', 'x' * 55 + f'{i:05d}', '(not set)', 12, 15, 9)
                            for i in range(10001)]
        rows = ga4.run_report(self.creds, '2026-10-20', '2026-10-26', self.google.url, access=ACCESS)
        self.assertEqual((len(rows), rows.pages), (10001, 3))
        self.assertEqual([r['offset'] for r in self.google.reports], [0, 3500, 7000])
        widest = [ga4_row(*['w' * 100] * 4, 9999999, 9999999, 9999999)] * ga4.PAGE
        answer = {'dimensionHeaders': [{'name': n} for n in ga4.DIMENSIONS],
                  'metricHeaders': [{'name': n, 'type': 'TYPE_INTEGER'} for n in ga4.METRICS],
                  'rows': widest, 'rowCount': ga4.MAX_ROWS, 'kind': 'analyticsData#runReport',
                  'metadata': {'currencyCode': 'GBP', 'timeZone': 'Europe/London'}}
        self.assertLessEqual(len(json.dumps(answer, separators=(',', ':')).encode()), ga4.LIMIT)
        self.assertLessEqual(ga4.report_request('2026-10-20', '2026-10-26')['limit'] * 560, ga4.LIMIT)

    def test_an_empty_window_is_zero_rows_not_an_error(self):
        self.google.rows = []
        rows = ga4.run_report(self.creds, '2026-10-20', '2026-10-26', self.google.url, access=ACCESS)
        self.assertEqual((list(rows), rows.pages), ([], 1))
        self.assertEqual(ga4.to_export(rows, '2026-10-20', '2026-10-26', '2026-10-27T06:00:00+00:00')['rows'], [])

    def test_mapping_to_the_export_shape(self):
        rows = [{'sessionSource': 'tiktok', 'sessionMedium': 'social', 'sessionCampaignName': 'matchday',
                 'sessionManualAdContent': 'TT_CLASH_CLIP_C02_H01_V1_20261020', 'newUsers': '5', 'sessions': '7', 'engagedSessions': '4'},
                {'sessionSource': '(direct)', 'sessionMedium': '(none)', 'sessionCampaignName': '(not set)',
                 'sessionManualAdContent': '', 'newUsers': '2', 'sessions': '3', 'engagedSessions': '1'},
                {'sessionSource': 'fan@example.invalid', 'sessionMedium': 'referral', 'sessionCampaignName': 'x',
                 'sessionManualAdContent': 'TT_CLASH_CLIP_C02_H01_V1_20261020', 'newUsers': '1', 'sessions': '1', 'engagedSessions': '0'},
                {'sessionSource': 'other@example.invalid', 'sessionMedium': 'referral', 'sessionCampaignName': 'x',
                 'sessionManualAdContent': 'TT_CLASH_CLIP_C02_H01_V1_20261020', 'newUsers': '1', 'sessions': '2', 'engagedSessions': '1'}]
        export = ga4.to_export(rows, dt.date(2026, 10, 20), '2026-10-26',
                               dt.datetime(2026, 10, 27, 6, 0, 5, 123, tzinfo=dt.timezone.utc))
        self.assertEqual(set(export), {'product', 'source', 'property', 'query_ref', 'window_start', 'window_end',
                                       'observed_at', 'rows'})
        self.assertEqual((export['product'], export['source'], export['property'], export['query_ref']),
                         ('fulltime', 'ga4', 'G-W2QL8RKFJ1', 'ga4-data-v1beta:runReport:landings-by-creative:v1'))
        self.assertEqual((export['window_start'], export['window_end'], export['observed_at']),
                         ('2026-10-20', '2026-10-26', '2026-10-27T06:00:05+00:00'))
        self.assertEqual(export['rows'], [
            {'utm_source': '(direct)', 'utm_medium': '(none)', 'utm_campaign': '(not set)',
             'utm_content': '(not set)', 'new_users': 2, 'sessions': 3, 'engaged_sessions': 1},
            {'utm_source': '(redacted)', 'utm_medium': 'referral', 'utm_campaign': 'x',
             'utm_content': 'TT_CLASH_CLIP_C02_H01_V1_20261020', 'new_users': 2, 'sessions': 3, 'engaged_sessions': 1},
            {'utm_source': 'tiktok', 'utm_medium': 'social', 'utm_campaign': 'matchday',
             'utm_content': 'TT_CLASH_CLIP_C02_H01_V1_20261020', 'new_users': 5, 'sessions': 7, 'engaged_sessions': 4}])
        self.assertNotIn('example.invalid', json.dumps(export))
        for row in export['rows']:
            self.assertTrue(all(type(row[k]) is int for k in ('new_users', 'sessions', 'engaged_sessions')))

    def test_content_that_is_not_a_creative_id_folds_into_not_set_and_passes_attribution(self):
        from engine import attribution
        row = lambda content, n: {'sessionSource': 'newsletter', 'sessionMedium': 'email', 'sessionCampaignName': 'x',
                                  'sessionManualAdContent': content, 'newUsers': str(n), 'sessions': str(n),
                                  'engagedSessions': '0'}
        rows = [row('someone-elses-tag', 1), row('(other)', 2), row('fan@example.invalid', 4),
                row('TT_CLASH_CLIP_C01_H01_V1_20261020', 8)]
        export = ga4.to_export(rows, '2026-10-20', '2026-10-26', dt.datetime(2026, 10, 27, 6, tzinfo=dt.timezone.utc))
        contents = {r['utm_content']: r['new_users'] for r in export['rows']}
        self.assertEqual(contents, {'(not set)': 7, 'TT_CLASH_CLIP_C01_H01_V1_20261020': 8})
        landings = attribution.by_creative(export)
        self.assertEqual(landings['TT_CLASH_CLIP_C01_H01_V1_20261020']['new_users'], 8)
        self.assertEqual(landings.untagged['new_users'], 7)

    def test_rows_outside_the_aggregate_shape_are_refused(self):
        good = {'sessionSource': 's', 'sessionMedium': 'm', 'sessionCampaignName': 'c',
                'sessionManualAdContent': 'a', 'newUsers': '1', 'sessions': '1', 'engagedSessions': '1'}
        for bad in ({**good, 'clientId': '123.456'}, {**good, 'sessions': '1.5'}, {**good, 'newUsers': '-1'},
                    {k: v for k, v in good.items() if k != 'engagedSessions'}):
            with self.assertRaises(ValueError):
                ga4.to_export([bad], '2026-10-20', '2026-10-26', '2026-10-27T06:00:00Z')
        with self.assertRaises(ValueError):
            ga4.to_export([good], '2026-10-20', '2026-10-26', '2026-10-27T06:00:00')
        with self.assertRaises(ValueError):
            ga4.to_export([good], '2026-10-27', '2026-10-26', '2026-10-27T06:00:00Z')

    def test_week_window_reuses_the_reporting_rule(self):
        today = dt.date(2026, 10, 27)
        self.assertEqual(ga4.week_window(today), (dt.date(2026, 10, 20), dt.date(2026, 10, 26)))
        self.assertEqual(ga4.week_window(today), reporting.week_window(today)[:2])
        self.assertEqual(ga4.days_window(1, today), (dt.date(2026, 10, 26),) * 2)
        with self.assertRaises(ValueError):
            ga4.days_window(0, today)


class CommandTests(Base):
    def run_main(self, argv, env, data_url=None):
        growth = types.SimpleNamespace(LOCAL=str(self.local))
        with patch.dict(os.environ, env, clear=True), \
                patch.object(ga4, 'TOKEN_URL', self.google.url + '/token'), \
                patch.object(ga4, 'DATA_URL', data_url or self.google.url), Captured() as seen:
            try:
                code = ga4.main(argv, growth)
            except SystemExit as stop:
                code = stop.code
        self.assertClean(seen.text())
        self.assertNotIn(CLIENT_ID, seen.text())
        return code, seen.out.getvalue(), seen.err.getvalue()

    def assertNoSecretOnDisk(self, allowed=()):
        for path in Path(self.root.name).rglob('*'):
            if path.is_file() and path.name not in allowed:
                self.assertClean(path.read_text(encoding='utf-8'))
                self.assertNotIn(CLIENT_ID, path.read_text(encoding='utf-8'))

    def test_doctor_names_presence_and_a_working_refresh_only(self):
        code, out, _ = self.run_main(['doctor'], ENV)
        summary = json.loads(out)
        self.assertEqual(code, 0, out)
        self.assertEqual((summary['credentials'], summary['token_refresh'], summary['property_id']),
                         ('environment', 'ok', 'set'))
        self.assertEqual(sorted(summary['environment_names_present']), sorted(ENV))
        code, out, _ = self.run_main(['ga4', 'doctor'], {**ENV, 'GA4_REFRESH_TOKEN': 'standin-revoked-' + 'X' * 30})
        self.assertEqual((code, json.loads(out)['token_refresh']), (1, 'unauthorized'))

    def test_doctor_without_credentials_reports_the_code(self):
        code, out, _ = self.run_main(['doctor'], {})
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['error_code'], 'missing_ga4_credentials')
        self.assertEqual(self.google.calls, [])
        code, out, _ = self.run_main(['report'], {})
        self.assertEqual((code, json.loads(out)['error_code']), (2, 'missing_ga4_credentials'))

    def test_keyless_github_token_comes_first_and_never_refreshes(self):
        keyless = {**ENV, 'GA4_ACCESS_TOKEN': ACCESS}
        creds = ga4.credentials(self.local, keyless)
        self.assertEqual((creds['source'], creds['property_id']), (ga4.KEYLESS, PROPERTY_ID))
        self.assertNotIn('refresh_token', creds)
        self.assertClean(repr(creds) + str(creds))
        code, out, _ = self.run_main(['doctor'], {'GA4_ACCESS_TOKEN': ACCESS, 'GA4_PROPERTY_ID': PROPERTY_ID})
        summary = json.loads(out)
        self.assertEqual((code, summary['credentials'], summary['token_refresh']), (0, ga4.KEYLESS, 'ok'), out)
        self.assertEqual((len(self.google.reports), len(self.google.host_checks)), (1, 1))
        self.assertNotIn('token', [call[0] for call in self.google.calls])
        target = self.local / 'ga4' / 'landings-latest.json'
        code, out, _ = self.run_main(['report', '--days', '7', '--out', str(target)],
                                     {'GA4_ACCESS_TOKEN': ACCESS, 'GA4_PROPERTY_ID': PROPERTY_ID})
        self.assertEqual(code, 0, out)
        self.assertTrue(target.is_file())
        self.assertNotIn('token', [call[0] for call in self.google.calls])
        self.assertNoSecretOnDisk()

    def test_a_refused_keyless_token_is_unauthorized_and_a_missing_property_stops_first(self):
        code, out, _ = self.run_main(['doctor'], {'GA4_ACCESS_TOKEN': 'standin-wrong-' + 'W' * 30,
                                                  'GA4_PROPERTY_ID': PROPERTY_ID})
        self.assertEqual((code, json.loads(out)['token_refresh']), (1, 'unauthorized'))
        calls = len(self.google.calls)
        code, out, _ = self.run_main(['doctor'], {'GA4_ACCESS_TOKEN': ACCESS})
        self.assertEqual((code, json.loads(out)['property_id']), (1, 'missing'))
        self.assertEqual(len(self.google.calls), calls)

    def test_report_writes_under_local_only_and_prints_counts_and_the_path(self):
        self.google.rows = [ga4_row('tiktok', 'social', 'matchday', 'TT_CLASH_CLIP_C01_H01_V1_20261020', 3, 4, 2),
                            ga4_row('youtube', 'social', 'matchday', 'YT_CLASH_SHORT_C01_H01_V1_20261020', 1, 2, 2)]
        target = self.local / 'ga4' / 'week.json'
        code, out, _ = self.run_main(['report', '--days', '7', '--out', str(target)], ENV)
        summary = json.loads(out)
        self.assertEqual(code, 0, out)
        self.assertEqual((summary['rows'], summary['new_users'], summary['sessions'], summary['engaged_sessions'],
                          summary['creatives'], summary['out']), (2, 4, 6, 4, 2, str(target)))
        export = json.loads(target.read_text(encoding='utf-8'))
        start, end = ga4.week_window()
        self.assertEqual((export['window_start'], export['window_end']), (start.isoformat(), end.isoformat()))
        self.assertRegex(export['observed_at'], r'[+-]\d{2}:\d{2}$')
        self.assertIn('never listeners', ' '.join(summary['notes']))
        outside = Path(self.root.name) / 'export.json'
        calls = len(self.google.calls)
        code, out, _ = self.run_main(['report', '--out', str(outside)], ENV)
        self.assertEqual(code, 1)
        self.assertIn('local/', json.loads(out)['message'])
        self.assertFalse(outside.exists())
        self.assertEqual(len(self.google.calls), calls)
        self.assertNoSecretOnDisk()

    def test_a_caveat_the_export_cannot_carry_keeps_no_export(self):
        # The export has no field for these, so an uncaveated file must never reach Control Center.
        target = self.local / 'ga4' / 'w.json'
        cases = (('ga4_time_zone_not_london', {'time_zone': 'America/Los_Angeles'}),
                 ('ga4_thresholded', {'meta': {'subjectToThresholding': True}}),
                 ('ga4_other_row', {'meta': {'dataLossFromOtherRow': True}}))
        for want, change in cases:
            with self.subTest(want):
                self.google.time_zone, self.google.meta = 'Europe/London', {}
                for name, value in change.items():
                    setattr(self.google, name, value)
                code, out, _ = self.run_main(['report', '--out', str(target)], {'GA4_ACCESS_TOKEN': ACCESS,
                                                                               'GA4_PROPERTY_ID': PROPERTY_ID})
                summary = json.loads(out)
                self.assertEqual((code, summary['error_code']), (1, want), out)
                self.assertEqual(summary['message'], ga4.MESSAGES[want])
                self.assertFalse(target.exists())
        rows = ga4.Rows([{'sessionSource': 's', 'sessionMedium': 'm', 'sessionCampaignName': 'c',
                          'sessionManualAdContent': 'a', 'newUsers': '1', 'sessions': '1', 'engagedSessions': '1'}])
        rows.time_zone = 'America/Los_Angeles'
        self.assertRaisesCode('ga4_time_zone_not_london', ga4.to_export, rows, '2026-10-20', '2026-10-26',
                              '2026-10-27T06:00:00Z')
        rows.time_zone = 'Europe/London'
        self.assertEqual(len(ga4.to_export(rows, '2026-10-20', '2026-10-26', '2026-10-27T06:00:00Z')['rows']), 1)

    def test_a_property_with_no_fulltime_fm_visits_is_refused(self):
        target = self.local / 'ga4' / 'w.json'
        keyless = {'GA4_ACCESS_TOKEN': ACCESS, 'GA4_PROPERTY_ID': PROPERTY_ID}
        self.google.hosts = [('othersite.example', 40), ('(not set)', 2)]
        code, out, _ = self.run_main(['report', '--out', str(target)], keyless)
        self.assertEqual((code, json.loads(out)['error_code']), (1, 'ga4_wrong_property'), out)
        self.assertFalse(target.exists())
        self.assertEqual(len(self.google.host_checks), 1)
        # Full Time's own property, with preview, local and translated-page hosts beside it.
        self.google.hosts = [('full-time-git-x.vercel.app', 9), ('www.fulltime.fm', 5), ('localhost', 3),
                             ('fulltime-fm.translate.goog', 1)]
        code, out, _ = self.run_main(['report', '--out', str(target)], keyless)
        self.assertEqual(code, 0, out)
        self.assertTrue(target.is_file())
        self.assertEqual(len(self.google.host_checks), 2)
        self.google.hosts = []   # an empty week has nothing to check against
        code, out, _ = self.run_main(['report', '--out', str(target)], keyless)
        self.assertEqual(code, 0, out)

    def test_a_malformed_http_reply_is_a_code_not_a_traceback(self):
        replies = {'chunked body cut off': b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                                           b'Transfer-Encoding: chunked\r\n\r\n400\r\n{"rows": [',
                   'garbage status line': b'HTTX/9 what\r\n\r\n',
                   'header over 64 KiB': b'HTTP/1.1 200 OK\r\nX: ' + b'a' * 70000 + b'\r\n\r\n'}
        target = self.local / 'ga4' / 'w.json'
        for name, reply in replies.items():
            with self.subTest(name):
                listener = socket.create_server(('127.0.0.1', 0))
                self.addCleanup(listener.close)

                def answer(listener=listener, reply=reply):
                    # Read the whole request and close cleanly, so the reader sees the reply, not a reset.
                    with contextlib.suppress(OSError):
                        connection, _ = listener.accept()
                        with connection:
                            connection.settimeout(5)
                            seen = b''
                            while b'\r\n\r\n' not in seen:
                                seen += connection.recv(65536)
                            head, _, body = seen.partition(b'\r\n\r\n')
                            length = int(dict(line.split(b': ', 1) for line in head.split(b'\r\n')[1:])
                                         .get(b'Content-Length', b'0'))
                            while len(body) < length:
                                body += connection.recv(65536)
                            connection.sendall(reply)
                            connection.shutdown(socket.SHUT_WR)
                            while connection.recv(65536):
                                pass
                threading.Thread(target=answer, daemon=True).start()
                code, out, err = self.run_main(['report', '--out', str(target)],
                                               {'GA4_ACCESS_TOKEN': ACCESS, 'GA4_PROPERTY_ID': PROPERTY_ID},
                                               data_url=f'http://127.0.0.1:{listener.getsockname()[1]}')
                self.assertEqual((code, json.loads(out)['error_code']), (1, 'ga4_unavailable'), out + err)
                self.assertNotIn('Traceback', err)
                self.assertFalse(target.exists())

    def test_a_mistyped_flag_is_never_echoed(self):
        code, out, err = self.run_main(['authorize', '--client-secrt', CLIENT_SECRET], {})
        self.assertEqual(code, 2)
        self.assertIn('not understood', err)
        self.assertEqual(self.google.calls, [])


class AuthorizeTests(Base):
    def flow(self, answer, **kwargs):
        """Run authorize with a stand-in browser that answers the loopback redirect."""
        seen = {}

        def browser(url):
            parts = urllib.parse.urlsplit(url)
            query = dict(urllib.parse.parse_qsl(parts.query))
            seen.update(query)
            self.google.challenge, self.google.redirect_uri = query['code_challenge'], query['redirect_uri']

            def visit():
                base = query['redirect_uri']
                for extra in answer(query):
                    try:
                        DIRECT.open(base.rstrip('/') + extra, timeout=5).read()
                    except urllib.error.HTTPError as error:
                        error.close()
            threading.Thread(target=visit, daemon=True).start()

        out = io.StringIO()
        with Captured() as captured:
            try:
                result = ga4.authorize(self.local, CLIENT_ID, CLIENT_SECRET, False, on_url=browser, out=out,
                                       token_url=self.google.url + '/token', timeout=10, **kwargs)
            finally:
                text = captured.text() + out.getvalue()
        self.assertClean(text)
        self.assertNotIn(CLIENT_ID, text)
        return result, seen, out.getvalue()

    def test_loopback_flow_with_pkce_writes_a_private_file(self):
        result, seen, out = self.flow(lambda q: ['/favicon.ico', '/?' + urllib.parse.urlencode(
            {'state': q['state'], 'code': 'standin-code', 'scope': ga4.SCOPE})])
        self.assertEqual(seen['scope'], 'https://www.googleapis.com/auth/analytics.readonly')
        self.assertEqual((seen['code_challenge_method'], seen['response_type'], seen['access_type']),
                         ('S256', 'code', 'offline'))
        self.assertRegex(seen['redirect_uri'], r'^http://127\.0\.0\.1:\d+/$')
        self.assertGreaterEqual(len(seen['state']), 32)
        path = self.local / 'ga4' / 'oauth.json'
        saved = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(saved, {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
                                 'refresh_token': NEW_REFRESH, 'property_id': None})
        if os.name == 'posix':
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn('readable only by you', out)
        # Nothing tells Krish to copy a value anywhere: no secret names, no cloud secrets step.
        self.assertNotIn('GA4_', out)
        self.assertNotIn('secret', out.lower())
        self.assertEqual(set(result), {'saved', 'property_id_set'})
        self.assertFalse(result['property_id_set'])
        self.assertEqual(ga4.credentials(self.local, {})['refresh_token'], NEW_REFRESH)
        self.assertEqual([p.name for p in path.parent.iterdir()], ['oauth.json'])

    def test_an_existing_property_id_is_kept(self):
        self.write_file({'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': REFRESH,
                         'property_id': PROPERTY_ID})
        result, _, _ = self.flow(lambda q: ['/?state=' + q['state'] + '&code=standin-code'])
        self.assertTrue(result['property_id_set'])
        self.assertEqual(ga4.credentials(self.local, {})['property_id'], PROPERTY_ID)

    def test_a_state_mismatch_is_refused_and_nothing_is_saved(self):
        with self.assertRaises(ga4.GA4Error) as caught:
            self.flow(lambda q: ['/?state=forged-' + 'F' * 30 + '&code=standin-code'])
        self.assertEqual(caught.exception.code, 'state_mismatch')
        self.assertFalse((self.local / 'ga4' / 'oauth.json').exists())
        self.assertNotIn('token', [c[0] for c in self.google.calls])
        with self.assertRaises(ga4.GA4Error) as caught:
            self.flow(lambda q: ['/?code=standin-code&state=%C3%A9'])
        self.assertEqual(caught.exception.code, 'state_mismatch')

    def test_a_refusal_in_the_browser_saves_nothing(self):
        with self.assertRaises(ga4.GA4Error) as caught:
            self.flow(lambda q: ['/?state=' + q['state'] + '&error=access_denied'])
        self.assertEqual(caught.exception.code, 'access_denied')
        self.assertFalse((self.local / 'ga4').exists())

    def test_on_windows_it_never_claims_the_file_is_private(self):
        class Windows:
            name = 'nt'

            def __getattr__(self, attr):
                return getattr(os, attr)

        chmods = []
        windows = type('WindowsChmod', (Windows,), {'chmod': lambda self, *a: chmods.append(a)})()
        with patch.object(ga4, 'os', windows):
            _, _, out = self.flow(lambda q: ['/?state=' + q['state'] + '&code=standin-code'])
        self.assertNotIn('readable only by you', out)
        self.assertIn("folder's permissions", out)
        self.assertIn('inside your own user profile', out)
        self.assertEqual(chmods, [])
        self.assertTrue((self.local / 'ga4' / 'oauth.json').is_file())

    def test_an_idle_connection_cannot_hold_the_sign_in_past_its_deadline(self):
        idle = []
        self.addCleanup(lambda: [s.close() for s in idle])

        def connect(port):
            # Idle for 6 seconds, then closed, so a regression fails the timing below instead of hanging.
            idle.append(socket.create_connection(('127.0.0.1', port)))
            threading.Timer(6, idle[-1].close).start()

        def hold(url):
            connect(urllib.parse.urlsplit(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
                                          ['redirect_uri']).port)
        began = time.monotonic()
        with self.assertRaises(ga4.GA4Error) as caught:
            ga4.authorize(self.local, CLIENT_ID, CLIENT_SECRET, False, on_url=hold, out=io.StringIO(),
                          token_url=self.google.url + '/token', timeout=2)
        self.assertEqual(caught.exception.code, 'authorize_timeout')
        self.assertLess(time.monotonic() - began, 5)

        def preconnect(query):
            # A browser may open a speculative connection first and leave it idle.
            connect(urllib.parse.urlsplit(query['redirect_uri']).port)
            return ['/?state=' + query['state'] + '&code=standin-code']
        began = time.monotonic()
        result, _, _ = self.flow(preconnect)
        self.assertLess(time.monotonic() - began, 8)
        self.assertEqual(ga4.credentials(self.local, {})['refresh_token'], NEW_REFRESH)
        self.assertTrue(Path(result['saved']).is_file())

    def test_a_wrong_verifier_or_no_answer_saves_nothing(self):
        def wrong(q):
            self.google.challenge = 'not-the-challenge'
            return ['/?state=' + q['state'] + '&code=standin-code']
        with self.assertRaises(ga4.GA4Error) as caught:
            self.flow(wrong)
        self.assertEqual(caught.exception.code, 'unauthorized')
        with self.assertRaises(ga4.GA4Error) as caught:
            ga4.authorize(self.local, CLIENT_ID, CLIENT_SECRET, False, on_url=lambda url: None, out=io.StringIO(),
                          token_url=self.google.url + '/token', timeout=0.5)
        self.assertEqual(caught.exception.code, 'authorize_timeout')
        self.assertFalse((self.local / 'ga4' / 'oauth.json').exists())


if __name__ == '__main__':
    unittest.main()
