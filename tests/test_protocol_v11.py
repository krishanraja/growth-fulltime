"""Control Center protocol 1.1.0: stages, amendments, one ask at a time, and
refusing another major version. Every fixture is synthetic, and nothing here
reaches the network: the stand-in listens on 127.0.0.1 only."""
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from urllib.parse import parse_qs
from unittest.mock import patch

import growth
from engine import control_center as cc
from engine import gates, reporting
from engine.records import instant
from tests.test_control_center import TOKEN, StandIn, sample_state

TODAY = dt.date(2026, 10, 27)
PLAN_ID = 'fulltime:plan:2026-W44'
RULINGS = {
    'D1': {'title': 'Synthetic ruling one', 'recommendation': 'Approve.', 'unlocks': ['youtube'],
           'requires': [], 'status': 'pending'},
    'D2': {'title': 'Synthetic ruling two', 'recommendation': 'Approve.', 'unlocks': [],
           'requires': [], 'status': 'pending'},
    'D4': {'title': 'Synthetic ruling four', 'recommendation': 'Approve.', 'unlocks': ['linkedin'],
           'requires': [], 'status': 'pending'},
}


def rulings(**status):
    out = copy.deepcopy(RULINGS)
    for rid, value in status.items():
        out.setdefault(rid, {'title': 'Synthetic ' + rid, 'recommendation': 'Approve.', 'unlocks': [],
                             'requires': []})['status'] = value
    return out


def his_digest(amount, words):
    """amended_sha256 as Control Center computes it, written apart from the engine."""
    body = json.dumps({'amount_usd': amount, 'exact_payload': words}, sort_keys=True,
                      separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def post_item(letter):
    return {'platform': 'youtube', 'creative_id': f'YT_SYNTH_{letter}', 'text': f'Synthetic words {letter}.'}


def plan():
    return reporting._proposal(PLAN_ID, 'Weekly plan, 2026-W44', 'A synthetic plan.', 'prepared', 'strategy',
                               {'plan': 'take clips'}, 'campaign_week_closed', '2026-W44',
                               exact_payload='{"plan":"take clips"}', stage='plan')


def go_live(**changes):
    out = reporting._proposal('fulltime:post:YT_SYNTH_GO', 'youtube: YT_SYNTH_GO', 'Ready.', 'prepared', 'post',
                              {'channel': 'youtube', 'exact_payload': 'Engine words.', 'target': 'YT_SYNTH_GO'},
                              'creative_published', 'YT_SYNTH_GO', channel='youtube',
                              exact_payload='Engine words.', stage='go_live', parent_proposal_id=PLAN_ID)
    return {**out, **changes}


def check_in(**changes):
    out = reporting._proposal('fulltime:check-in:2026-W44', 'On track?', 'A synthetic check-in.', 'prepared',
                              'strategy', {'progress': 'two of three'}, 'campaign_week_closed', '2026-W44',
                              exact_payload='Two of three clips made; the third is next.', stage='check_in',
                              parent_proposal_id=PLAN_ID)
    return {**out, **changes}


def spend(amount=20):
    return reporting._proposal('fulltime:spend:2026-W44', 'Credits, 2026-W44', 'Synthetic credits.', 'prepared',
                               'spend', {'amount_usd': amount}, 'spend_recorded', '2026-W44', amount_usd=amount,
                               stage='go_live', parent_proposal_id=PLAN_ID)


def report(items=(), rulings_file=None, extra=(), waiting=None, kill_list=(), mode='synthetic',
           run_id='fulltime:2026-10-27:daily'):
    out = reporting.build(run_id, mode, '2026-10-27T05:12:00Z', sample_state(), list(items),
                          RULINGS if rulings_file is None else rulings_file,
                          reporting.objectives(TODAY, [], {}), ['A synthetic line.'], identity_known=False,
                          kill_list=kill_list, waiting=waiting)
    if extra:
        out = reporting.seal({**out, 'proposals': out['proposals'] + list(extra)})
    return out


def ids(value):
    return [p['proposal_id'] for p in value['proposals']]


def deferred(value):
    """The ids the 'One ask at a time' activity line names as waiting their turn."""
    line = next((a['line'] for a in value['activity'] if a['line'].startswith('One ask at a time')), '')
    return [pid.strip() for pid in line.split(': ', 2)[-1].rstrip('.').split(',')] if line else []


class StandIn11(StandIn):
    """The stand-in speaking 1.1.0: it takes reports of 1.0.0 to 1.2.0, refuses any
    other version and any field newer than the report's version, and serves its
    directive at whatever version a test sets."""

    def __init__(self, directive_version='1.1.0'):
        super().__init__()
        self.directive_version = directive_version

    def post_reports(self, h, route, query, body):
        version = body.get('schema_version')
        if version not in ('1.0.0', '1.1.0', '1.2.0'):
            return h._send(400, {'error': 'schema_version'})
        for proposal in body.get('proposals') or []:
            if (version == '1.0.0' and {'stage', 'parent_proposal_id'} & set(proposal)) or \
                    (version != '1.2.0' and 'subject_ref' in proposal):
                return h._send(400, {'error': 'field_newer_than_version'})
        return super().post_reports(h, route, query, body)

    def get_directive(self, h, route, query, body):
        return h._send(200, {'ok': True, 'chosen_by': 'rule', 'directive': {
            'schema_version': self.directive_version, 'directive_id': 'fulltime:2026-10-27',
            'engine_id': 'growth-fulltime', 'for_date': '2026-10-27', 'aim': 'synthetic', 'objectives': [],
            'next_action': {'proposal_id': 'fulltime:action:rail', 'instruction': 'synthetic', 'why': 'synthetic',
                            'close_condition': None},
            'decisions_since': [], 'constraints': {'walls': 'synthetic', 'autonomy': 'handcrafted',
                                                   'autonomy_rule': 'synthetic', 'spend_cap_usd': 0,
                                                   'max_actions': 5}}})


class ServedTests(unittest.TestCase):
    def setUp(self):
        self.server = StandIn11()

    def tearDown(self):
        self.server.close()

    def loop(self, value):
        client = cc.Client(self.server.url, TOKEN, loopback_for_tests=True)
        with contextlib.redirect_stdout(io.StringIO()):
            return cc.execute(client, 'morning', value['run_id'], lambda d: (value, {}), '2026-10-20T00:00:00Z')

    def report_posts(self):
        return [c for c in self.server.calls if c[0] == 'POST' and c[1] == 'reports']


class VersionTests(ServedTests):
    def test_reports_are_sent_as_1_1_0(self):
        value = report(items=[post_item('A')])
        self.assertEqual(value['schema_version'], '1.1.0')
        self.assertEqual(reporting.schema_errors(value), [])
        summary = self.loop(value)
        self.assertEqual(summary['status'], 'succeeded')
        self.assertEqual(self.server.reports[value['run_id']]['schema_version'], '1.1.0')

    def test_the_version_is_raised_only_for_a_field_in_use(self):
        self.assertEqual(reporting.report_version([plan(), go_live()]), '1.1.0')
        self.assertEqual(reporting.report_version([]), '1.1.0')
        self.assertEqual(reporting.report_version([{**plan(), 'subject_ref': 'contact:synthetic1'}]), '1.2.0')
        self.assertNotIn('stage', report()['proposals'][0])

    def test_a_field_newer_than_the_report_is_refused(self):
        staged = report(extra=[plan()])
        older = reporting.seal({**staged, 'schema_version': '1.0.0'})
        self.assertTrue(any('needs protocol 1.1.0' in e for e in reporting.schema_errors(older)))
        subject = reporting.seal({**staged, 'proposals': [{**plan(), 'subject_ref': 'contact:synthetic1'}]})
        self.assertTrue(any('needs protocol 1.2.0' in e for e in reporting.schema_errors(subject)))
        self.assertEqual(reporting.schema_errors(reporting.seal({**subject, 'schema_version': '1.2.0'})), [])
        self.assertEqual(self.loop(older)['error_code'], 'report_invalid')
        self.assertEqual(self.report_posts(), [])


class StageTests(ServedTests):
    def test_plan_go_live_and_check_in_are_valid_and_taken(self):
        value = report(extra=[plan(), go_live(), check_in(), spend()])
        self.assertEqual(reporting.schema_errors(value), [])
        summary = self.loop(value)
        self.assertEqual(summary['status'], 'succeeded')
        stored = {p['proposal_id']: p for p in self.server.reports[value['run_id']]['proposals']}
        self.assertEqual(stored[PLAN_ID]['stage'], 'plan')
        self.assertEqual((stored['fulltime:post:YT_SYNTH_GO']['stage'],
                          stored['fulltime:post:YT_SYNTH_GO']['parent_proposal_id']), ('go_live', PLAN_ID))
        self.assertEqual(stored['fulltime:check-in:2026-W44']['stage'], 'check_in')

    def test_a_go_live_may_name_a_plan_approved_in_an_earlier_report(self):
        self.assertEqual(reporting.schema_errors(report(extra=[go_live()])), [])

    def test_stages_out_of_place_are_refused_and_never_sent(self):
        cases = [
            ('go-live without its plan', [plan(), go_live(parent_proposal_id=None)], 'needs parent_proposal_id'),
            ('go-live behind strategy', [plan(), go_live(wall='strategy')], 'go-live must be behind send, post or spend'),
            ('check-in behind post', [plan(), check_in(wall='post')], 'check-in must be behind strategy'),
            ('check-in with no progress', [plan(), check_in(exact_payload=None)], 'progress against the plan'),
            ('plan with no wall', [{**plan(), 'wall': 'none'}], 'plan must be behind a wall'),
            ('plan with no words', [{**plan(), 'exact_payload': None}], 'plan itself in exact_payload'),
            ('parent on an unstaged ask', [plan(), {**go_live(), 'stage': None}], 'belongs only on a go-live'),
            ('parent that is not a plan', [plan(), check_in(), go_live(parent_proposal_id='fulltime:check-in:2026-W44')],
             'must name a plan'),
            ('parent naming itself', [go_live(parent_proposal_id='fulltime:post:YT_SYNTH_GO')], 'cannot name the proposal itself'),
            ('parent that is not an id', [go_live(parent_proposal_id='not an id')], 'not a proposal id'),
            ('an unknown stage', [go_live(stage='live')], 'must be one of'),
            ('a spend with no amount', [plan(), spend(amount=None)], 'a spend needs amount_usd'),
        ]
        for label, extra, expected in cases:
            with self.subTest(label):
                errors = reporting.schema_errors(report(extra=extra))
                self.assertTrue(any(expected in e for e in errors), errors)
        bad = report(extra=[plan(), go_live(parent_proposal_id=None)])
        self.assertEqual(self.loop(bad)['error_code'], 'report_invalid')
        self.assertEqual(self.report_posts(), [])


class AmendmentTests(ServedTests):
    def decision(self, proposal, **extra):
        return {'proposal_id': proposal['proposal_id'], 'decision': 'approved', 'decided_at': '2026-10-27T08:00:00Z',
                'payload_sha256': proposal['payload_sha256'], 'stage': proposal.get('stage'), 'amended': False,
                **extra}

    def test_an_amended_decision_is_verified_and_his_version_is_what_he_approved(self):
        value = report(extra=[plan(), go_live()])
        proposal = next(p for p in value['proposals'] if p['proposal_id'] == 'fulltime:post:YT_SYNTH_GO')
        self.server.decisions = [self.decision(proposal, amended=True, exact_payload='His words.', amount_usd=None,
                                               amended_sha256=his_digest(None, 'His words.'))]
        summary = self.loop(value)
        decided = summary['decisions']
        self.assertEqual(decided['approved_amended'], ['fulltime:post:YT_SYNTH_GO'])
        self.assertEqual(decided['approved_current'], [])
        approved = decided['approved']['fulltime:post:YT_SYNTH_GO']
        self.assertEqual((approved['exact_payload'], approved['amended']), ('His words.', True))
        self.assertNotEqual(approved['exact_payload'], proposal['exact_payload'])
        self.assertEqual(approved['sha256'], his_digest(None, 'His words.'))
        self.assertIn('amended version', decided['instructions'][0]['line'])

    def test_an_amended_amount_is_his_amount(self):
        proposal = spend(amount=20)
        decided = cc.classify([self.decision(proposal, amended=True, exact_payload=None, amount_usd=12.5,
                                             amended_sha256=his_digest(12.5, None))], [plan(), proposal])
        self.assertEqual(decided['approved'][proposal['proposal_id']]['amount_usd'], 12.5)
        self.assertIn('12.5 USD', decided['instructions'][0]['line'])

    def test_an_amended_digest_mismatch_counts_for_nothing(self):
        proposal = go_live()
        wrong = self.decision(proposal, amended=True, exact_payload='His words.', amount_usd=None,
                              amended_sha256=his_digest(None, 'Other words.'))
        missing = {k: v for k, v in wrong.items() if k != 'amended_sha256'}
        for decision in (wrong, missing):
            decided = cc.classify([decision], [plan(), proposal])
            self.assertEqual(decided['amended_unverified'], [proposal['proposal_id']])
            for key in ('approved_current', 'approved_amended', 'approved_changed', 'instructions'):
                self.assertEqual(decided[key], [])
            self.assertEqual(decided['approved'], {})

    def test_an_unamended_yes_still_binds_its_payload_digest(self):
        proposal = go_live()
        same = cc.classify([self.decision(proposal)], [proposal])
        self.assertEqual(same['approved_current'], [proposal['proposal_id']])
        self.assertEqual(same['approved'][proposal['proposal_id']]['exact_payload'], 'Engine words.')
        changed = cc.classify([self.decision(proposal, payload_sha256='f' * 64)], [proposal])
        self.assertEqual((changed['approved_changed'], changed['approved'], changed['instructions']),
                         ([proposal['proposal_id']], {}, []))

    def test_an_amendment_lapses_when_the_engine_changed_the_proposal(self):
        proposal = go_live()
        stale = self.decision(proposal, payload_sha256='e' * 64, amended=True, exact_payload='His words.',
                              amount_usd=None, amended_sha256=his_digest(None, 'His words.'))
        decided = cc.classify([stale], [proposal])
        self.assertEqual((decided['approved_changed'], decided['approved']), ([proposal['proposal_id']], {}))


class OneAskTests(ServedTests):
    def test_an_approved_ruling_is_never_asked_again(self):
        # One new strategy ask per report (the standing rulings included): D2 is asked and
        # release and D1 wait their turn, named in the One ask at a time line.
        first = report()
        self.assertEqual([p for p in ids(first) if p.startswith('fulltime:ruling:')], ['fulltime:ruling:D2'])
        self.assertEqual(deferred(first), ['fulltime:ruling:release', 'fulltime:ruling:D1'])
        ruled = report(rulings_file=rulings(D1='approved'))
        self.assertNotIn('fulltime:ruling:D1', ids(ruled) + deferred(ruled))
        self.assertNotIn('fulltime:ruling:release', ids(ruled) + deferred(ruled))
        self.assertIn('fulltime:ruling:D2', ids(ruled))
        organic = report(rulings_file=rulings(ORGANIC='approved'))
        self.assertNotIn('fulltime:ruling:release', ids(organic) + deferred(organic))
        for value in (report(), ruled):
            self.assertNotIn('fulltime:ruling:D4', ids(value))
            self.assertIn('D4', [h['reason'] for h in value['holds']])
            self.assertIn('RELEASE', [h['reason'] for h in value['holds']])

    def test_a_retired_release_item_is_not_turned_into_an_action(self):
        items = [{'item_id': 'fulltime-release', 'platform': 'other', 'why': 'release', 'text': 'Release decision.'}]
        asked = report(items=items)
        self.assertIn('fulltime:ruling:release', ids(asked) + deferred(asked))
        later = report(items=items, rulings_file=rulings(D1='approved'))
        retired = ids(later) + deferred(later)
        self.assertFalse([pid for pid in retired if 'release' in pid])

    def test_a_waiting_ask_is_kept_current_and_no_second_of_its_kind_is_added(self):
        items = [post_item('A'), post_item('B')]
        first = report(items=items)
        self.assertIn('fulltime:post:YT_SYNTH_A', ids(first))
        self.assertNotIn('fulltime:post:YT_SYNTH_B', ids(first))
        line = first['activity'][-1]['line']
        self.assertIn('One ask at a time', line)
        self.assertIn('fulltime:post:YT_SYNTH_B', line)
        kept = report(items=items, waiting={'fulltime:post:YT_SYNTH_B': 'post'})
        self.assertIn('fulltime:post:YT_SYNTH_B', ids(kept))
        self.assertNotIn('fulltime:post:YT_SYNTH_A', ids(kept))
        behind = report(items=items, waiting={'fulltime:post:YT_SYNTH_OLD': 'post'})
        self.assertFalse([pid for pid in ids(behind) if pid.startswith('fulltime:post:')])
        unwalled = report(items=[{'platform': 'other', 'why': 'rail', 'text': 'Read.'}],
                          waiting={'fulltime:action:other': 'none'})
        self.assertIn('fulltime:action:rail', ids(unwalled))

    def test_a_new_strategy_ask_waits_behind_one_already_on_his_list(self):
        # With no standing ruling to ask, the kill is the one strategy ask; with D2 pending,
        # the kill waits behind it like any other strategy ask.
        alone = report(kill_list=['Stop the synthetic thing.'], rulings_file=rulings(D1='approved', D2='approved'))
        self.assertEqual(len([p for p in ids(alone) if p.startswith('fulltime:kill:')]), 1)
        first = report(kill_list=['Stop the synthetic thing.'])
        self.assertIn('fulltime:ruling:D2', ids(first))
        self.assertFalse([p for p in ids(first) if p.startswith('fulltime:kill:')])
        self.assertTrue([p for p in deferred(first) if p.startswith('fulltime:kill:')])
        waiting = {'fulltime:ruling:D2': 'strategy'}
        behind = report(kill_list=['Stop the synthetic thing.'], waiting=waiting)
        self.assertIn('fulltime:ruling:D2', ids(behind))
        self.assertFalse([p for p in ids(behind) if p.startswith('fulltime:kill:')])
        self.assertNotIn('fulltime:ruling:D1', ids(behind))

    def test_a_stage_is_its_own_kind(self):
        kept, deferred = reporting.one_ask([plan(), go_live(), check_in()], {'fulltime:post:YT_SYNTH_OLD': 'post'})
        self.assertEqual([p['proposal_id'] for p in kept], [PLAN_ID, 'fulltime:post:YT_SYNTH_GO',
                                                            'fulltime:check-in:2026-W44'])
        self.assertEqual(deferred, [])
        kept, deferred = reporting.one_ask([go_live()], {'fulltime:post:YT_SYNTH_PREVIOUS': 'go_live'})
        self.assertEqual(([p['proposal_id'] for p in kept], len(deferred)), ([], 1))

    def test_what_waits_is_recorded_from_a_live_report_only(self):
        value = report(items=[post_item('A'), {'platform': 'other', 'why': 'rail', 'text': 'Read.'}], mode='live')
        d2 = next(p for p in value['proposals'] if p['proposal_id'] == 'fulltime:ruling:D2')
        self.server.decisions = [{'proposal_id': d2['proposal_id'], 'decision': 'declined',
                                  'decided_at': '2026-10-27T08:00:00Z', 'payload_sha256': d2['payload_sha256'],
                                  'stage': None, 'amended': False}]
        self.assertEqual(deferred(value), ['fulltime:ruling:release', 'fulltime:ruling:D1'])
        summary = self.loop(value)
        # D2 was the one strategy ask and he declined it, so only the post waits; release
        # and D1 were never on his list, so they wait for nothing yet.
        self.assertEqual(summary['waiting'], {'fulltime:post:YT_SYNTH_A': 'post'})
        self.assertIsNone(self.loop(report(run_id='fulltime:2026-10-27:other'))['waiting'])

    def test_the_ledger_carries_what_waits_into_the_next_run(self):
        real_client = cc.Client
        done = type('Done', (), {'returncode': 0, 'stdout': 'checks passed: 1\n'})
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root), \
                patch.object(growth, 'sync', return_value=sample_state()), \
                patch('engine.control_center.subprocess.run', return_value=done()), \
                patch.object(cc, 'Client', lambda base, token: real_client(self.server.url, token,
                                                                           loopback_for_tests=True)):
            ledger = Path(root) / 'control-center' / 'last.json'
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({'decisions_read_at': '2026-10-26T05:12:00Z',
                                          'waiting': {'fulltime:kill:synthetic': 'strategy'}}), encoding='utf-8')
            from engine.cli import main
            with patch.dict(os.environ, {cc.TOKEN_ENV: TOKEN}), contextlib.redirect_stdout(io.StringIO()):
                try:
                    main(['cc', 'dispatch', '--synthetic'], growth)
                except SystemExit:
                    pass
            saved = json.loads(ledger.read_text(encoding='utf-8'))
        self.assertEqual(saved['status'], 'succeeded')
        sent = next(iter(self.server.reports.values()))
        self.assertEqual(reporting.schema_errors(sent), [])
        self.assertEqual([p for p in sent['proposals'] if p['wall'] == 'strategy'], [])
        self.assertIn('One ask at a time', sent['activity'][-1]['line'])
        self.assertEqual(saved['waiting'], {'fulltime:kill:synthetic': 'strategy'})


class SinceStandIn(StandIn11):
    """The stand-in answering the decisions route as Control Center does: only decisions
    made after `since`, by its own clock, which may run `behind` the engine's."""

    def __init__(self):
        super().__init__()
        self.asked = []

    def get_decisions(self, h, route, query, body):
        since = (parse_qs(query).get('since') or [None])[0]
        self.asked.append(since)
        return h._send(200, {'ok': True, 'decisions': [
            d for d in self.decisions if since is None or instant(d['decided_at']) > instant(since)]})

    def decide(self, run_id, pid, verdict, at):
        proposal = next(p for p in self.reports[run_id]['proposals'] if p['proposal_id'] == pid)
        self.decisions.append({'proposal_id': pid, 'decision': verdict, 'decided_at': at, 'stage': proposal.get('stage'),
                               'payload_sha256': proposal['payload_sha256'], 'amended': False})


class LoopTests(unittest.TestCase):
    """The real cc.main, run after run, against a stand-in that honours since. The work it
    calls builds the report as workspace_work does, with what main hands it."""

    def setUp(self):
        self.server = SinceStandIn()
        self.addCleanup(self.server.close)
        self.local = tempfile.mkdtemp()
        self.addCleanup(__import__('shutil').rmtree, self.local)
        self.items, self.rulings, self.kills = [], rulings(D1='approved', D2='approved'), ()

    def work(self, report_mode, kind, waiting, answered):
        def run(directive):
            today = reporting.london_today()
            return reporting.build(
                reporting.run_id_for(today, kind), report_mode, reporting.iso(reporting.utc_now()), sample_state(),
                list(self.items), self.rulings, reporting.objectives(today, [], {}), ['A synthetic line.'],
                identity_known=False, waiting=waiting, kill_list=self.kills if kind == 'report' else (),
                gate_proposals=gates.pending(self.local) if kind != 'dispatch' else (),
                answered=reporting.answered_pairs(answered) | cc.answered_in(directive)), {}
        return run

    def main(self, moment, target='morning', synthetic=False):
        def workspace(growth_, mode, report_mode, offline, observations, require, waiting=None, answered=()):
            return self.work(report_mode, 'report' if mode == 'weekly' else 'daily', waiting, answered)

        def runner(growth_, report_mode, dispatched=None, waiting=None, answered=()):
            return self.work(report_mode, 'dispatch', waiting, answered)
        args = types.SimpleNamespace(target=target, synthetic=synthetic, offline=True, observations=None,
                                     require_existing_history=False)
        real = cc.Client
        with patch.object(reporting, 'utc_now', lambda: moment), patch.object(cc, 'workspace_work', workspace), \
                patch.object(cc, 'runner_work', runner), patch.dict(os.environ, {cc.TOKEN_ENV: TOKEN}), \
                patch.object(cc, 'Client', lambda base, token: real(self.server.url, token, loopback_for_tests=True)):
            cc.main(args, types.SimpleNamespace(LOCAL=self.local))
        saved = json.loads((Path(self.local) / 'control-center' / 'last.json').read_text(encoding='utf-8'))
        kind = {'weekly': 'report', 'dispatch': 'dispatch'}.get(target, 'daily')
        return saved, self.server.reports[reporting.run_id_for(reporting.london_today(moment), kind)]

    def day(self, n, hour=6, **kw):
        return self.main(dt.datetime(2026, 11, n, hour, 15, tzinfo=dt.timezone.utc), **kw)

    def test_an_answered_post_never_waits_again_and_the_next_post_is_asked(self):
        self.items = [post_item('A')]
        saved, sent = self.day(2)
        self.assertEqual(saved['waiting'], {'fulltime:post:YT_SYNTH_A': 'post'})
        self.server.decide(sent['run_id'], 'fulltime:post:YT_SYNTH_A', 'declined', '2026-11-02T12:00:00Z')
        self.items = [post_item('A'), post_item('B')]
        saved, _ = self.day(3)                                  # reads his decline
        self.assertEqual(saved['waiting'], {})
        for n in (4, 5):
            saved, sent = self.day(n)
            self.assertIn('fulltime:post:YT_SYNTH_B', ids(sent))
            self.assertNotIn('fulltime:post:YT_SYNTH_B', deferred(sent))
            self.assertNotIn('fulltime:post:YT_SYNTH_A', saved['waiting'])
            self.assertEqual(saved['waiting'], {'fulltime:post:YT_SYNTH_B': 'post'})
        history = (Path(self.local) / 'control-center' / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual([(json.loads(r)['proposal_id'], json.loads(r)['decision']) for r in history],
                         [('fulltime:post:YT_SYNTH_A', 'declined')])

    def test_an_answered_post_never_holds_back_a_queued_g2(self):
        self.items = [post_item('A')]
        _, sent = self.day(2)
        self.server.decide(sent['run_id'], 'fulltime:post:YT_SYNTH_A', 'approved', '2026-11-02T12:00:00Z')
        self.day(3)
        g2 = reporting._proposal('fulltime-g2-2026-11-08', 'G2 pack', 'A synthetic pack.', 'prepared', 'post',
                                 {'items': []}, 'creative_published', 'fulltime:2026-11-08:g2', channel='tiktok',
                                 exact_payload=json.dumps({'items': []}))
        with patch.object(gates, 'pending', lambda local: [g2]):
            saved, sent = self.day(4)
        self.assertIn('fulltime-g2-2026-11-08', ids(sent))
        self.assertNotIn('fulltime-g2-2026-11-08', deferred(sent))
        self.assertEqual(saved['waiting'], {'fulltime-g2-2026-11-08': 'post'})

    def test_answered_rulings_go_one_at_a_time_and_then_the_kill(self):
        self.rulings = growth.load_rulings()
        pending = [r for r in ('D7', 'D2', 'D3') if self.rulings.get(r, {}).get('status') == 'pending']
        self.kills = ('Stop the synthetic thing.',)
        n = 2
        for rid in pending:
            saved, sent = self.day(n)
            strategy = [p['proposal_id'] for p in sent['proposals'] if p['wall'] == 'strategy'
                        and (p['proposal_id'], p['payload_sha256']) not in cc.answered_before(self.local)]
            self.assertEqual(strategy, [f'fulltime:ruling:{rid}'])
            self.server.decide(sent['run_id'], f'fulltime:ruling:{rid}', 'approved', f'2026-11-{n:02d}T12:00:00Z')
            saved, _ = self.day(n + 1)
            self.assertEqual(saved['waiting'], {})
            n += 2
        saved, sent = self.day(n, target='weekly')
        self.assertEqual([k for k in saved['waiting']], [p for p in ids(sent) if p.startswith('fulltime:kill:')])
        self.assertEqual(len(saved['waiting']), 1)

    def g1(self):
        from engine import spec
        example = spec.load(Path(growth.HERE) / 'specs' / 'examples' / 'synthetic-week.json')
        proposal = spec.proposal(example, '2026-11-09T20:00:00+00:00')
        gates.prepare(self.local, 'g1', proposal)
        return proposal['proposal_id']

    def signed(self):
        return (Path(self.local) / 'specs' / '2026-W45.signed.json').is_file()

    def test_a_synthetic_run_or_a_dispatch_never_uses_up_his_answer(self):
        for target, synthetic in (('morning', True), ('dispatch', False), ('dispatch', True)):
            with self.subTest(target=target, synthetic=synthetic):
                self.setUp()
                pid = self.g1()
                saved, sent = self.day(2)
                read_at = saved['decisions_read_at']
                self.server.decide(sent['run_id'], pid, 'approved', '2026-11-02T12:00:00Z')
                saved, _ = self.day(3, target=target, synthetic=synthetic)
                self.assertEqual(saved['decisions_read_at'], read_at)
                self.assertFalse(self.signed())
                self.assertFalse((Path(self.local) / 'control-center' / 'decisions.jsonl').exists())
                saved, _ = self.day(4)
                gate = json.loads((Path(self.local) / 'engine' / 'gates' / f'{pid}.json').read_text(encoding='utf-8'))
                self.assertTrue(gate['settled_at'])
                self.assertEqual(gate['decision'], 'approved')
                self.assertTrue(self.signed())

    def test_a_server_clock_behind_the_engine_never_drops_an_answer(self):
        pid = self.g1()
        fast = dt.timedelta(minutes=3)                           # the engine runs three minutes fast
        real = dt.datetime(2026, 11, 2, 6, 15, tzinfo=dt.timezone.utc)
        saved, sent = self.main(real + fast)
        self.assertEqual(saved['decisions_read_at'], '2026-11-02T06:18:00Z')
        self.server.decide(sent['run_id'], pid, 'approved', '2026-11-02T06:16:30Z')   # 90 s after the real read
        saved, _ = self.main(real + dt.timedelta(days=1) + fast)
        self.assertEqual(self.server.asked[-1], '2026-11-02T06:03:00Z')
        self.assertTrue(self.signed())
        saved, _ = self.main(real + dt.timedelta(days=2) + fast)   # read again in the overlap: taken once
        lines = (Path(self.local) / 'control-center' / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 1)

    def test_the_read_window_overlaps_and_falls_back_to_seven_days(self):
        self.assertEqual(cc.read_from('2026-11-02T06:18:00Z'), '2026-11-02T06:03:00Z')
        moment = dt.datetime(2026, 11, 2, 6, 0, tzinfo=dt.timezone.utc)
        for value in (None, '', 'yesterday', '2026-11-02'):
            self.assertEqual(cc.read_from(value, moment), '2026-10-26T06:00:00Z')


class StandingRulingTests(unittest.TestCase):
    def test_one_standing_ruling_per_report_d7_first_and_a_waiting_one_kept(self):
        real = growth.load_rulings()
        pending = [rid for rid in ('D7', 'D2', 'D3') if (real.get(rid) or {}).get('status') == 'pending']
        first = report(rulings_file=real, kill_list=['Stop the synthetic thing.'], mode='live')
        walled = [p['proposal_id'] for p in first['proposals'] if p['wall'] == 'strategy']
        self.assertEqual(len(walled), 1)
        if pending:
            self.assertEqual(walled, [f'fulltime:ruling:{pending[0]}'])
            for rid in pending[1:]:
                self.assertIn(f'fulltime:ruling:{rid}', deferred(first))
        self.assertTrue([p for p in deferred(first) if p.startswith('fulltime:kill:')])
        two = rulings(D1='approved', D7='pending', D3='pending')
        value = report(rulings_file=two)
        self.assertEqual([p for p in ids(value) if p.startswith('fulltime:ruling:')], ['fulltime:ruling:D7'])
        self.assertEqual(deferred(value), ['fulltime:ruling:D2', 'fulltime:ruling:D3'])
        kept = report(rulings_file=two, waiting={'fulltime:ruling:D3': 'strategy'})
        self.assertEqual([p for p in ids(kept) if p.startswith('fulltime:ruling:')], ['fulltime:ruling:D3'])
        self.assertEqual(deferred(kept), ['fulltime:ruling:D7', 'fulltime:ruling:D2'])


class VersionRefusalTests(ServedTests):
    def test_any_1x_is_taken_and_another_major_is_refused(self):
        for value in (None, '1.0.0', '1.1.0', '1.12.3'):
            self.assertTrue(cc.version_supported(value), value)
        for value in ('2.0.0', '0.9.0', '10.0.0', '1.1', 'one', 1):
            self.assertFalse(cc.version_supported(value), value)

    def test_a_2x_directive_is_refused_with_a_code(self):
        self.server.directive_version = '2.0.0'
        summary = self.loop(report())
        self.assertEqual((summary['status'], summary['phase'], summary['error_code']),
                         ('failed', 'directive', 'protocol_version_unsupported'))
        self.assertEqual(self.report_posts(), [])
        self.assertEqual(self.server.attempts[summary['attempt_id']]['error_code'], 'protocol_version_unsupported')

    def test_a_later_1x_directive_is_taken(self):
        self.server.directive_version = '1.9.0'
        self.assertEqual(self.loop(report())['status'], 'succeeded')

    def test_a_2x_decision_is_refused_and_counts_for_nothing(self):
        value = report(extra=[reporting.ruling_proposal('D1', RULINGS['D1'])])
        d2 = next(p for p in value['proposals'] if p['proposal_id'] == 'fulltime:ruling:D2')
        d1 = next(p for p in value['proposals'] if p['proposal_id'] == 'fulltime:ruling:D1')
        self.server.decisions = [
            {'schema_version': '2.0.0', 'proposal_id': d2['proposal_id'], 'decision': 'approved',
             'decided_at': '2026-10-27T08:00:00Z', 'payload_sha256': d2['payload_sha256'], 'stage': None,
             'amended': False},
            {'schema_version': '1.4.0', 'proposal_id': d1['proposal_id'], 'decision': 'approved',
             'decided_at': '2026-10-27T08:00:00Z', 'payload_sha256': d1['payload_sha256'], 'stage': None,
             'amended': False}]
        decided = self.loop(value)['decisions']
        self.assertEqual(decided['refused'], [{'proposal_id': 'fulltime:ruling:D2',
                                               'code': 'protocol_version_unsupported'}])
        self.assertEqual(decided['approved_current'], ['fulltime:ruling:D1'])
        self.assertNotIn('fulltime:ruling:D2', decided['approved'])

    def test_a_2x_decisions_answer_is_refused_with_a_code(self):
        self.server.get_decisions = lambda h, *a: h._send(200, {'ok': True, 'schema_version': '2.0.0',
                                                                'decisions': []})
        summary = self.loop(report())
        self.assertEqual((summary['status'], summary['phase'], summary['error_code']),
                         ('failed', 'decisions', 'protocol_version_unsupported'))


class HandcraftedTests(ServedTests):
    def test_an_approved_go_live_is_an_instruction_never_an_action(self):
        value = report(extra=[plan(), go_live()])
        live = next(p for p in value['proposals'] if p['proposal_id'] == 'fulltime:post:YT_SYNTH_GO')
        planned = next(p for p in value['proposals'] if p['proposal_id'] == PLAN_ID)
        self.server.decisions = [
            {'proposal_id': pid, 'decision': 'approved', 'decided_at': '2026-10-27T08:00:00Z',
             'payload_sha256': p['payload_sha256'], 'stage': p['stage'], 'amended': False}
            for pid, p in ((PLAN_ID, planned), (live['proposal_id'], live))]
        summary = self.loop(value)
        decided = summary['decisions']
        self.assertEqual(decided['approved_current'], [PLAN_ID, live['proposal_id']])
        self.assertEqual(len(decided['instructions']), 1)
        instruction = decided['instructions'][0]
        self.assertEqual((instruction['proposal_id'], instruction['by'], instruction['sha256']),
                         (live['proposal_id'], 'krish', live['payload_sha256']))
        self.assertIn('post it yourself on youtube', instruction['line'])
        self.assertIn('does not post, send or spend', instruction['line'])
        routes = {(c[0], c[1].split('/')[0]) for c in self.server.calls}
        self.assertEqual(routes, {('POST', 'attempts'), ('GET', 'directive'), ('GET', 'capabilities'),
                                  ('GET', 'reports'), ('POST', 'reports'), ('GET', 'decisions')})
        self.assertEqual(len(self.report_posts()), 1)

    def test_instructions_are_recorded_once_each(self):
        instruction = cc.handcrafted_instruction(go_live(), {'amended': False, 'stage': 'go_live',
                                                             'amount_usd': None, 'sha256': 'a' * 64})
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(cc.record_instructions(root, [instruction, instruction], '2026-10-27T08:00:00Z'), 1)
            self.assertEqual(cc.record_instructions(root, [instruction], '2026-10-28T08:00:00Z'), 0)
            rows = (Path(root) / 'control-center' / 'instructions.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0])['recorded_at'], '2026-10-27T08:00:00Z')


if __name__ == '__main__':
    unittest.main()
