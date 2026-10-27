"""The Control Center protocol client against a local in-process stand-in.
Nothing here reaches the network: the stand-in listens on 127.0.0.1 only."""
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import growth
from engine import control_center as cc
from engine import reporting
from engine.records import History

TOKEN = 'gen1_' + 'T' * 43
SCHEMA_PROPS = set(reporting.load_schema()['properties'])


def independent_digest(report):
    """The server's own computation, written separately from engine.reporting."""
    body = {k: v for k, v in report.items() if k != 'payload_sha256'}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


class StandIn:
    """A minimal Control Center for one engine: attempts, directive, reports, decisions."""

    def __init__(self):
        self.attempts, self.reports, self.calls = {}, {}, []
        self.decisions = []
        self.capabilities = {'schema_version': '1.1.0', 'schema_versions': ['1.0.0', '1.1.0', '1.2.0'],
                             'autonomy': 'handcrafted', 'engine_id': 'growth-fulltime', 'product_slug': 'full-time',
                             'idempotency': True}
        self.refuse = {}          # (method, route) -> status
        self.force_conflict = False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _route(self, method):
                prefix = '/api/growth/engines/fulltime/'
                path, _, query = self.path.partition('?')
                if not path.startswith(prefix):
                    return self._send(404, {'error': 'not_found'})
                route = path[len(prefix):]
                outer.calls.append((method, route, query, self.headers.get('Idempotency-Key')))
                if self.headers.get('Authorization') != 'Bearer ' + TOKEN:
                    return self._send(401, {'error': 'unauthorized'})
                key = route.split('/')[0]
                if (method, key) in outer.refuse:
                    return self._send(outer.refuse[(method, key)], {'error': 'refused'})
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                return getattr(outer, method.lower() + '_' + key)(self, route, query, body)

            def do_GET(self):
                self._route('GET')

            def do_POST(self):
                self._route('POST')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def post_attempts(self, h, route, query, body):
        old = self.attempts.get(body['attempt_id'])
        if old and old['status'] != 'started' and old != body:
            return h._send(409, {'error': 'attempt_terminal'})
        if body['status'] != 'started' and (not body.get('finished_at') or
                                            (body['status'] == 'failed' and not body.get('error_code'))):
            return h._send(400, {'error': 'finished_at'})
        if body['status'] == 'started' and 'finished_at' in body:
            return h._send(400, {'error': 'finished_at'})
        self.attempts[body['attempt_id']] = body
        return h._send(200, {'ok': True, 'attempt': body})

    def get_capabilities(self, h, route, query, body):
        if self.capabilities is None:
            return h._send(404, {'error': 'not_found'})
        return h._send(200, self.capabilities)

    def get_directive(self, h, route, query, body):
        return h._send(200, {'ok': True, 'chosen_by': 'rule', 'directive': {
            'schema_version': '1.0.0', 'directive_id': 'fulltime:2026-10-19', 'engine_id': 'growth-fulltime',
            'for_date': '2026-10-19', 'aim': 'fixture', 'objectives': [],
            'next_action': {'proposal_id': 'fulltime:action:rail', 'instruction': 'fixture', 'why': 'fixture',
                            'close_condition': None},
            'decisions_since': [], 'constraints': {'walls': 'fixture', 'spend_cap_usd': 0, 'max_actions': 5}}})

    def post_reports(self, h, route, query, body):
        if set(body) - SCHEMA_PROPS:
            return h._send(400, {'error': 'unknown_field'})
        if h.headers.get('Idempotency-Key') != body['run_id']:
            return h._send(400, {'error': 'idempotency_key'})
        if independent_digest(body) != body['payload_sha256']:
            return h._send(400, {'error': 'payload_sha256'})
        stored = self.reports.get(body['run_id'])
        if self.force_conflict or (stored and stored['payload_sha256'] != body['payload_sha256']):
            return h._send(409, {'error': 'conflict'})
        self.reports[body['run_id']] = body
        return h._send(200, {'accepted': True, 'run_id': body['run_id'],
                             'payload_sha256': body['payload_sha256'], 'replayed': stored is not None})

    def get_reports(self, h, route, query, body):
        from urllib.parse import unquote
        run_id = unquote(route.split('/', 1)[1])
        stored = self.reports.get(run_id)
        if not stored:
            return h._send(404, {'error': 'not_found'})
        return h._send(200, {'accepted': True, 'run_id': run_id, 'payload_sha256': stored['payload_sha256'],
                             'mode': stored['mode'], 'accepted_at': '2026-10-19T05:12:00Z', 'report': stored})

    def get_decisions(self, h, route, query, body):
        return h._send(200, {'ok': True, 'decisions': self.decisions})


def sample_state(**extra):
    return {'sha': 'a' * 40, 'rules_ok': True, 'synced_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'rail': [{'drop': 'drop1', 'pundits': ['zen'], 'fill': 1, 'home': 'Home', 'away': 'Away',
                      'score': [1, 0], 'date': '2026-10-11'}],
            'push': {'open': False, 'why': 'no match has 4 of 6 AI Pundits (newest: 1 of 6)'},
            'rulings': {}, 'decisions': [], **extra}


def rulings_on_19_october():
    """The rulings as they stood on 19 October, before ruling 1 of 27 October (D1 with
    ORGANIC, and the RELEASE entry) was recorded. These tests are about that day's asks,
    so they must not move when rulings.json does."""
    rulings = copy.deepcopy(growth.load_rulings())
    rulings['D1'] = {**rulings['D1'], 'status': 'pending', 'date': '', 'words': '', 'evidence': ''}
    for later in ('ORGANIC', 'RELEASE'):
        rulings.pop(later, None)
    return rulings


def sample_report(run_id='fulltime:2026-10-19:daily', mode='synthetic'):
    today = dt.date(2026, 10, 19)
    items = [{'item_id': 'fulltime-rail', 'platform': 'other', 'why': 'rail', 'text': 'Read the stored verdicts.'},
             {'item_id': 'fulltime-release', 'platform': 'other', 'why': 'release', 'text': 'Release decision.'}]
    held = [{'creative_id': 'YT_PROOF_SHORT_C01_H01_V1_20261017', 'holds': ['RAIL', 'RELEASE', 'D1']}]
    return reporting.build(run_id, mode, '2026-10-19T05:12:00Z', sample_state(), items, rulings_on_19_october(),
                           reporting.objectives(today, [], {}), ['Synced full-time aaaaaaaaaa.'], held_items=held,
                           identity_known=False)


class DigestAndReportTests(unittest.TestCase):
    def test_digest_reproduces_the_worked_example(self):
        example = json.loads(Path(growth.HERE, 'docs/control-center/engine-report.example.json').read_text())
        self.assertEqual(reporting.canonical_sha256({k: v for k, v in example.items() if k != 'payload_sha256'}),
                         'f4351324e84aa1baf6afd1bc4d2ffadb3039ab6399b2309c2717b89a26a0a517')
        self.assertEqual(reporting.seal(example)['payload_sha256'], example['payload_sha256'])

    def test_whole_numbers_are_written_as_javascript_writes_them(self):
        self.assertEqual(reporting.canonical({'b': 1.0, 'a': [0.5, 2.0], 'c': 'é'}), '{"a":[0.5,2],"b":1,"c":"é"}')
        with self.assertRaises(ValueError):
            reporting.canonical({'x': float('nan')})

    def test_report_is_schema_valid_with_no_unknown_fields(self):
        report = sample_report()
        self.assertEqual(reporting.schema_errors(report), [])
        self.assertEqual(report['payload_sha256'], independent_digest(report))
        self.assertTrue(reporting.schema_errors({**report, 'revision': 'x'}))
        bad = copy.deepcopy(report); bad['activity'][0]['private'] = True
        self.assertTrue(any('unknown field' in e for e in reporting.schema_errors(bad)))

    def test_unknown_objectives_are_null_with_a_reason_and_zero_is_measured(self):
        objectives = {o['key']: o for o in sample_report()['objectives']}
        self.assertEqual(set(objectives), {'attributed_new_completers', 'marketing_cash_gbp'})
        for objective in objectives.values():
            self.assertIsNone(objective['value'])
            self.assertEqual(objective['availability'], 'missing')
            self.assertTrue(objective['reason'])
        today = dt.date(2026, 10, 19)
        runs = {'r': {'date': '2026-10-15', 'usage': {'marketing_cash_gbp': 0}}}
        cash = reporting.objectives(today, [], runs)[1]
        self.assertEqual((cash['value'], cash['availability']), (0, 'measured'))
        for objective in reporting.objectives(today, workspace=False):
            self.assertIsNone(objective['value'])
            self.assertIn('workspace', objective['reason'])

    def test_held_items_carry_their_codes_and_rulings_are_strategy(self):
        report = sample_report()
        reasons = [h['reason'] for h in report['holds']]
        for code in ('RAIL', 'RELEASE', 'CHANNEL', 'CONSENT', 'D1'):
            self.assertIn(code, reasons)
        self.assertIn('YT_PROOF_SHORT_C01_H01_V1_20261017', next(h for h in report['holds'] if h['reason'] == 'D1')['detail'])
        walls = {p['proposal_id']: p['wall'] for p in report['proposals']}
        self.assertEqual(walls['fulltime:action:rail'], 'none')
        # One ask at a time holds for the standing rulings too: one new strategy ask per
        # report, D7 (the consent item) first, and the rest named as waiting their turn.
        self.assertEqual([pid for pid, wall in walls.items() if wall == 'strategy'], ['fulltime:ruling:D7'])
        line = report['activity'][-1]['line']
        self.assertTrue(line.startswith('One ask at a time'), line)
        for rid in ('release', 'D1', 'D2', 'D3'):
            self.assertIn(f'fulltime:ruling:{rid}', line)
            self.assertNotIn(f'fulltime:ruling:{rid}', walls)
        rulings = rulings_on_19_october()
        for rid in ('D1', 'D2', 'D3', 'D7'):
            self.assertEqual(reporting.ruling_proposal(rid, rulings[rid])['wall'], 'strategy')
        self.assertEqual(reporting.release_proposal()['wall'], 'strategy')
        for rid in ('D4', 'D5', 'D6'):
            self.assertNotIn(f'fulltime:ruling:{rid}', walls)
            self.assertIn(rid, reasons)
        self.assertLessEqual(len(report['proposals']), 10)
        self.assertEqual(report['status'], 'held')

    def test_a_ready_post_carries_its_exact_payload_and_digest(self):
        item = {'platform': 'youtube', 'creative_id': 'YT_CLASH_SHORT_C01_H01_V1_20261019', 'text': 'Two AI Pundits.'}
        proposal = reporting.action_proposal(item)
        self.assertEqual((proposal['wall'], proposal['exact_payload'], proposal['channel']), ('post', 'Two AI Pundits.', 'youtube'))
        self.assertEqual(proposal['payload_sha256'], reporting.canonical_sha256(
            {'channel': 'youtube', 'exact_payload': 'Two AI Pundits.', 'target': item['creative_id']}))

    def test_ready_creatives_in_history_are_post_proposals_within_the_cap(self):
        ready = {'platform': 'youtube', 'creative_id': 'YT_CLASH_SHORT_C01_H01_V1_20261019',
                 'account_scope': 'brand', 'text': 'Two AI Pundits, one match.'}
        creatives = {ready['creative_id']: {'latest_version_status': 'ready', 'versions': [{'item': ready}]},
                     'YT_HELD': {'latest_version_status': 'held', 'versions': [{'item': {'text': 'x', 'holds': ['RAIL']}}]}}
        items = reporting.ready_creatives(creatives) + [
            {'item_id': f'fulltime-{k}', 'platform': 'other', 'why': k, 'text': 'An instruction.'}
            for k in ('rail', 'measurement', 'release')]
        report = reporting.build('fulltime:2026-10-19:daily', 'synthetic', '2026-10-19T05:12:00Z', sample_state(),
                                 items, {}, reporting.objectives(dt.date(2026, 10, 19), [], {}), ['A line.'],
                                 held_items=reporting.held_creatives(creatives), identity_known=True)
        self.assertEqual(reporting.schema_errors(report), [])
        post = report['proposals'][0]
        self.assertEqual((post['wall'], post['channel'], post['exact_payload']),
                         ('post', 'youtube', 'Two AI Pundits, one match.'))
        self.assertEqual([p['wall'] for p in report['proposals'] if p['wall'] != 'strategy'], ['post', 'none', 'none'])
        free_text = reporting.action_proposal({'platform': 'other', 'why': 'A sentence, not a key.', 'text': 'Do it.'})
        self.assertEqual(reporting.schema_errors({'proposals': [free_text]},
                                                 {'type': 'object', 'properties': {'proposals': reporting.load_schema()['properties']['proposals']}}), [])

    def test_publication_receipts_become_events(self):
        creatives = {'YT_A': {'status': 'published', 'publication': {'url': 'https://youtube.com/watch?v=proof',
                                                                     'recorded_at': '2026-10-15T10:00:00+00:00'}}}
        events = reporting.publication_events(creatives, '2026-10-12')
        self.assertEqual(events[0]['event'], 'creative_published')
        self.assertEqual(events[0]['evidence_url'], 'https://youtube.com/watch?v=proof')


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.server = StandIn()
        self.client = cc.Client(self.server.url, TOKEN, loopback_for_tests=True)
        self.log = io.StringIO()
        self.handler = logging.StreamHandler(self.log)
        logging.getLogger().addHandler(self.handler)
        logging.getLogger().setLevel(logging.DEBUG)

    def tearDown(self):
        logging.getLogger().removeHandler(self.handler)
        self.server.close()

    def loop(self, report=None, notes=None):
        report = report or sample_report()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            summary = cc.execute(self.client, 'morning', report['run_id'], lambda d: (report, notes or {}),
                                 '2026-10-12T00:00:00Z')
        text = out.getvalue() + err.getvalue() + self.log.getvalue() + json.dumps(summary) + repr(self.client)
        self.assertNotIn(TOKEN, text)
        self.assertNotIn(TOKEN[5:20], text)
        return summary

    def test_https_only_and_no_plain_http_outside_tests(self):
        with self.assertRaises(cc.ControlCenterError):
            cc.Client(self.server.url, TOKEN)
        with self.assertRaises(cc.ControlCenterError):
            cc.base_url('https://user:pw@controlcenter.krishraja.com')
        self.assertEqual(cc.base_url('https://controlcenter.krishraja.com/'), 'https://controlcenter.krishraja.com')

    def test_attempt_started_then_one_terminal_and_readback(self):
        summary = self.loop()
        self.assertEqual(summary['status'], 'succeeded')
        self.assertTrue(summary['readback'])
        self.assertFalse(summary['replayed'])
        posts = [c for c in self.server.calls if c[0] == 'POST' and c[1] == 'attempts']
        self.assertEqual(len(posts), 2)
        attempt = self.server.attempts[summary['attempt_id']]
        self.assertEqual(attempt['status'], 'succeeded')
        self.assertEqual(attempt['run_id'], 'fulltime:2026-10-19:daily')
        self.assertTrue(attempt['finished_at'])
        order = [c[1].split('/')[0] for c in self.server.calls]
        self.assertEqual(order[0], 'attempts')
        self.assertEqual(order[1], 'directive')
        self.assertEqual(order[-2:], ['decisions', 'attempts'])
        self.assertEqual(self.server.reports['fulltime:2026-10-19:daily']['payload_sha256'], summary['report_sha256'])
        self.assertEqual(summary['next_action'], 'fulltime:action:rail')

    def test_replay_answered_replayed_true(self):
        report = sample_report()
        first = self.client.post_report(report)
        second = self.client.post_report(report)
        self.assertEqual(first[0], 200)
        self.assertFalse(first[1]['replayed'])
        self.assertTrue(second[1]['replayed'])
        self.assertEqual(self.client.deliver(report)['replayed'], True)

    def test_rerun_with_changed_payload_reads_first_and_takes_a_revision(self):
        self.loop()
        changed = reporting.seal({**sample_report(), 'observed_at': '2026-10-19T09:00:00Z'})
        summary = self.loop(changed)
        self.assertEqual(summary['status'], 'succeeded')
        self.assertEqual(summary['run_id'], 'fulltime:2026-10-19:daily:r2')
        posts = [c for c in self.server.calls if c[0] == 'POST' and c[1] == 'reports']
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[-1][3], 'fulltime:2026-10-19:daily:r2')

    def test_conflict_is_read_back_never_retried_blindly(self):
        self.server.force_conflict = True
        summary = self.loop()
        self.assertEqual((summary['status'], summary['error_code']), ('failed', 'report_conflict'))
        posts = [c for c in self.server.calls if c[0] == 'POST' and c[1] == 'reports']
        self.assertEqual(len(posts), 1)
        self.assertEqual([c for c in self.server.calls if c[1].startswith('reports/')][-1][0], 'GET')
        self.assertEqual(self.server.attempts[summary['attempt_id']]['error_code'], 'report_conflict')

    def test_401_is_a_failed_attempt_with_a_code(self):
        self.server.refuse[('POST', 'reports')] = 401
        summary = self.loop()
        self.assertEqual((summary['status'], summary['error_code']), ('failed', 'unauthorized'))
        self.assertEqual(self.server.attempts[summary['attempt_id']]['status'], 'failed')
        self.assertEqual(self.server.attempts[summary['attempt_id']]['error_code'], 'unauthorized')

    def test_wrong_token_fails_locally_with_a_code_and_never_prints_it(self):
        wrong = 'gen1_' + 'W' * 43
        self.client = cc.Client(self.server.url, wrong, loopback_for_tests=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            summary = cc.execute(self.client, 'dispatch', 'fulltime:2026-10-19:dispatch',
                                 lambda d: (sample_report(), {}), None)
        self.assertEqual((summary['status'], summary['error_code']), ('failed', 'unauthorized'))
        self.assertNotIn(wrong, out.getvalue() + json.dumps(summary))
        self.assertEqual(self.server.attempts, {})

    def test_engine_inactive_is_named(self):
        self.server.post_reports = lambda h, *a: h._send(409, {'error': 'engine_inactive'})
        summary = self.loop()
        self.assertEqual((summary['status'], summary['error_code']), ('failed', 'engine_inactive'))
        self.assertEqual(len([c for c in self.server.calls if c[0] == 'POST' and c[1] == 'reports']), 1)

    def test_a_failure_before_the_report_still_shows(self):
        def broken(directive):
            raise cc.ControlCenterError('history_unavailable')
        summary = cc.execute(self.client, 'morning', 'fulltime:2026-10-19:daily', broken, None)
        self.assertEqual(self.server.attempts[summary['attempt_id']]['error_code'], 'history_unavailable')
        self.assertEqual(self.server.reports, {})

    def test_invalid_report_is_never_sent(self):
        report = {**sample_report(), 'send_now': True}
        summary = self.loop(report)
        self.assertEqual(summary['error_code'], 'report_invalid')
        self.assertEqual(self.server.reports, {})

    def test_decisions_count_only_on_the_same_payload(self):
        # D1, D2 and D3 wait their turn behind D7 in a fresh report, so they are put on
        # it here: an answer counts only for an ask in the report.
        rulings = rulings_on_19_october()
        base = sample_report()
        report = reporting.seal({**base, 'proposals': base['proposals'] + [
            reporting.ruling_proposal(rid, rulings[rid]) for rid in ('D1', 'D2', 'D3')]})
        d1 = next(p for p in report['proposals'] if p['proposal_id'] == 'fulltime:ruling:D1')
        self.server.decisions = [
            {'proposal_id': d1['proposal_id'], 'decision': 'approved', 'decided_at': '2026-10-18T20:00:00Z',
             'payload_sha256': d1['payload_sha256']},
            {'proposal_id': 'fulltime:ruling:D2', 'decision': 'approved', 'decided_at': '2026-10-18T20:00:00Z',
             'payload_sha256': 'f' * 64},
            {'proposal_id': 'fulltime:ruling:D3', 'decision': 'declined', 'decided_at': '2026-10-18T20:00:00Z',
             'payload_sha256': 'e' * 64}]
        summary = self.loop(report)
        self.assertEqual(summary['decisions']['approved_current'], ['fulltime:ruling:D1'])
        self.assertEqual(summary['decisions']['approved_changed'], ['fulltime:ruling:D2'])
        self.assertEqual(summary['decisions']['declined'], ['fulltime:ruling:D3'])
        self.assertIn('since=2026-10-12T00%3A00%3A00Z', [c[2] for c in self.server.calls if c[1] == 'decisions'][0])


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.server = StandIn()
        self.real_client = cc.Client
        server_url = self.server.url
        self.patch = patch.object(cc, 'Client', lambda base, token: self.real_client(server_url, token,
                                                                                    loopback_for_tests=True))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.server.close()

    def run_cli(self, argv, env):
        from engine.cli import main
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                main(argv, growth)
            except SystemExit as stop:
                code = stop.code
        text = out.getvalue() + err.getvalue()
        self.assertNotIn(TOKEN, text)
        return code, text

    def test_missing_token_says_so_and_exits_non_zero(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root):
            env = {k: v for k, v in os.environ.items() if k != cc.TOKEN_ENV}
            with patch.dict(os.environ, env, clear=True):
                code, text = self.run_cli(['cc', 'dispatch'], {})
        self.assertEqual(code, 2)
        self.assertIn('missing_token', text)
        self.assertEqual(self.server.calls, [])

    def test_morning_in_the_workspace_reports_the_saved_run(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root), \
                patch.object(growth, 'load_state', return_value=sample_state()):
            History(Path(root) / 'engine').checkpoint({'pack_date': '2026-10-17', 'kind': 'daily', 'venture': 'fulltime',
                                                       'fulltime_sha': 'a' * 40, 'headline': 'An earlier checkpoint',
                                                       'items': [{'platform': 'other', 'text': 'A note.'}]})
            code, text = self.run_cli(['cc', 'morning', '--offline', '--require-existing-history', '--synthetic'],
                                      {cc.TOKEN_ENV: TOKEN})
            self.assertEqual(code, 0, text)
            saved = json.loads((Path(root) / 'control-center' / 'last.json').read_text())
            self.assertEqual(saved['status'], 'succeeded')
            self.assertNotIn(TOKEN, json.dumps(saved))
        report = next(iter(self.server.reports.values()))
        self.assertEqual(report['mode'], 'synthetic')
        self.assertRegex(report['run_id'], r'^fulltime:\d{4}-\d{2}-\d{2}:daily$')
        self.assertEqual(reporting.schema_errors(report), [])
        self.assertLessEqual(sum(1 for p in report['proposals'] if p['wall'] == 'none'), 3)
        cash = next(o for o in report['objectives'] if o['key'] == 'marketing_cash_gbp')
        self.assertIn(cash['availability'], ('measured', 'missing'))

    def test_weekly_review_maps_its_kill_list_to_strategy(self):
        # Every standing ruling answered, so the kill is the one strategy ask this report.
        answered = {rid: {**r, 'status': 'approved'} for rid, r in growth.load_rulings().items()}
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root), \
                patch.object(growth, 'load_state', return_value=sample_state()), \
                patch.object(growth, 'load_rulings', return_value=answered):
            code, text = self.run_cli(['cc', 'weekly', '--offline', '--synthetic'], {cc.TOKEN_ENV: TOKEN})
        self.assertEqual(code, 0, text)
        report = next(iter(self.server.reports.values()))
        self.assertRegex(report['run_id'], r'^fulltime:\d{4}-\d{2}-\d{2}:report$')
        kills = [p for p in report['proposals'] if p['proposal_id'].startswith('fulltime:kill:')]
        self.assertEqual([p['wall'] for p in kills], ['strategy'])
        self.assertEqual(reporting.schema_errors(report), [])

    def test_scheduled_workspace_run_refuses_a_fresh_ledger(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root):
            code, _ = self.run_cli(['cc', 'morning', '--offline', '--require-existing-history'], {cc.TOKEN_ENV: TOKEN})
            self.assertFalse((Path(root) / 'engine' / 'history.json').exists())
        self.assertEqual(code, 1)
        attempt = next(iter(self.server.attempts.values()))
        self.assertEqual((attempt['status'], attempt['error_code']), ('failed', 'history_unavailable'))

    def test_dispatch_on_a_clean_runner_reports_workspace_objectives_missing(self):
        done = type('Done', (), {'returncode': 0, 'stdout': 'checks passed: 1\n'})
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root), \
                patch.object(growth, 'sync', return_value=sample_state()), \
                patch('engine.control_center.subprocess.run', return_value=done()):
            code, text = self.run_cli(['cc', 'dispatch', '--synthetic'], {cc.TOKEN_ENV: TOKEN,
                                                                         'CC_DIRECTIVE_ID': 'fulltime:2026-10-19'})
        self.assertEqual(code, 0, text)
        report = next(iter(self.server.reports.values()))
        self.assertRegex(report['run_id'], r'^fulltime:\d{4}-\d{2}-\d{2}:dispatch$')
        self.assertEqual(reporting.schema_errors(report), [])
        for objective in report['objectives']:
            self.assertEqual((objective['value'], objective['availability']), (None, 'missing'))
            self.assertIn('workspace', objective['reason'])
        self.assertEqual(report['status'], 'held')
        self.assertTrue(all(p['wall'] in ('none', 'strategy') for p in report['proposals']))

    def test_dispatch_for_another_engine_is_refused(self):
        code, text = self.run_cli(['cc', 'dispatch'], {cc.TOKEN_ENV: TOKEN, 'CC_DISPATCH_ENGINE_ID': 'growth-heartside'})
        self.assertEqual(code, 2)
        self.assertIn('wrong_engine', text)
        self.assertEqual(self.server.calls, [])


if __name__ == '__main__':
    unittest.main()
