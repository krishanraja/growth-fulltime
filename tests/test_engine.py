import copy
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

import growth
from engine import policy
from engine.measurements import scorecard, validate, validate_export
from engine.records import History, atomic_json, fingerprint
from engine.reporting import envelope, verify_receipt
from engine.runner import run


def state():
    return {'sha': 'a'*40, 'rules_ok': True, 'synced_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'rail': [{'drop': 'drop1', 'pundits': ['zen'], 'fill': 1, 'home': 'Home', 'away': 'Away',
                      'score': [1, 0], 'date': '2026-10-11'}], 'rulings': {}, 'decisions': []}


def pack(item=None):
    return {'pack_date': '2026-10-17', 'kind': 'daily', 'venture': 'fulltime', 'fulltime_sha': 'a'*40,
            'headline': 'A private growth checkpoint', 'items': [item or {'platform': 'other', 'text': 'Read the current constraint.'}]}


def creative():
    return {'platform': 'youtube', 'creative_id': 'YT_CLASH_SHORT_C01_H01_V1_20261017',
            'account_scope': 'brand', 'identity_ref': 'fulltime-youtube',
            'text': 'Pick your AI Pundit.', 'holds': ['RELEASE', 'CHANNEL', 'D1', 'RAIL', 'CONSENT']}


def observation(metric='unique_completers', value=5, **extra):
    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    return {'metric': metric, 'value': value, 'source': 'test-aggregate', 'query_ref': 'fixture-v1',
            'window_start': end.isoformat(), 'window_end': end.isoformat(),
            'observed_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'status': 'measured', **extra}


class PolicyTests(unittest.TestCase):
    def test_excluded_channels_refused_even_when_held(self):
        for platform in policy.EXCLUDED:
            with self.subTest(platform=platform):
                errors = growth.check_pack(pack({'platform': platform, 'text': 'An AI Pundit draft.', 'needs': 'D1'}), state())
                self.assertTrue(any('excluded' in x for x in errors))

    def test_personal_account_refused(self):
        self.assertTrue(any('personal' in e for e in policy.errors({**creative(), 'account_scope': 'personal'}, state())))

    def test_no_hidden_action_keys(self):
        self.assertTrue(growth.check_pack({**pack(), 'send': True}, state()))
        self.assertTrue(growth.check_pack(pack({'platform': 'other', 'text': 'A note.', 'send_email': True}), state()))

    def test_whatsapp_requires_listener_action(self):
        self.assertTrue(policy.errors({'platform': 'whatsapp'}, state()))
        self.assertEqual(policy.errors({'platform': 'whatsapp', 'distribution': 'listener_initiated'}, state()), [])

    def test_email_is_opt_in_and_non_identifying(self):
        item = {'platform': 'email', 'sender': 'krish@fulltime.fm', 'contact_basis': 'explicit_opt_in', 'consent_ref': 'source:opt-in-cohort'}
        self.assertEqual(policy.errors(item), [])
        self.assertTrue(policy.errors({**item, 'contact_basis': 'cold'}))
        self.assertTrue(policy.errors({**item, 'target_url': 'mailto:private@example.test'}))
        self.assertTrue(policy.errors({**item, 'target_name': 'A private person'}))

    def test_d1_does_not_open_release(self):
        s = state(); s['rulings']['D1'] = {'in_force': True}
        self.assertFalse(policy.release_open(s))
        self.assertTrue(any('RELEASE' in x for x in policy.errors({**creative(), 'holds': ['CHANNEL']}, s)))

    def test_multiple_holds_survive(self):
        item = creative()
        self.assertEqual(growth.check_pack(pack(item), state()), [])
        self.assertIn('RELEASE, CHANNEL, D1, RAIL, CONSENT', growth.render_md(pack(item)))

    def test_held_draft_still_requires_real_pundit(self):
        cid = creative()['creative_id']
        link = growth.tracked('https://fulltime.fm/?drop=drop1&pundit=doomer', cid)
        self.assertTrue(any('made no show' in e for e in growth.check_pack(pack({**creative(), 'text': 'AI Pundit: '+link}), state())))

    def test_money_non_finite_counts_and_dates_refused(self):
        self.assertTrue(growth.check_pack({**pack(), 'usage': {'marketing_cash_gbp': 1}}, state()))
        self.assertTrue(growth.check_pack({**pack(), 'pack_date': '2026-02-30'}, state()))
        for value in (True, float('nan'), float('inf'), -1):
            self.assertTrue(growth.check_pack({**pack(), 'kind': 'numbers', 'numbers': [{'platform': 'ga4', 'note': 'fixture', 'users': value}]}, state()))

    def test_malformed_inputs_report_errors(self):
        for value in ([], None, {'headline': []}, {**pack(), 'items': ['bad']}, pack({'platform':'other','text':1})):
            self.assertTrue(growth.check_pack(value, state()))

    def test_store_has_no_remote_side_effect_even_with_token(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth, 'LOCAL', root), patch('urllib.request.urlopen', side_effect=AssertionError('network write')), patch.dict('os.environ', {'GROWTH_ENGINE_TOKEN':'test-only-not-a-real-secret'}):
            receipt = growth.store_pack(pack())
            self.assertEqual(receipt['delivery'], 'pending_handoff')
            self.assertTrue((Path(root)/'outbox/2026-10-17-daily.json').exists())

    def test_private_contacts_in_metadata_are_refused(self):
        self.assertTrue(growth.check_pack(pack({'platform':'other','text':'An internal note.','why':'private@example.test'}),state()))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.history = History(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_reruns_and_restart_preserve_publication(self):
        self.history.checkpoint(pack(creative()))
        cid = creative()['creative_id']
        self.history.mark(cid, 'published', 'https://youtube.com/watch?v=proof', True)
        self.history.checkpoint(pack({**creative(), 'text': 'A revised AI Pundit caption.'}))
        restarted = History(self.root).read()
        self.assertEqual(len(restarted['packs']), 1)
        self.assertEqual(restarted['creatives'][cid]['status'], 'published')
        self.assertEqual(restarted['creatives'][cid]['publication']['url'], 'https://youtube.com/watch?v=proof')
        self.assertFalse(restarted['creatives'][cid]['current_version_published'])
        self.assertEqual(restarted['creatives'][cid]['latest_version_status'], 'held')

    def test_identical_revision_is_idempotent(self):
        self.history.checkpoint(pack()); self.history.checkpoint(pack())
        self.assertEqual(len(next(iter(self.history.read()['packs'].values()))['revisions']), 1)

    def test_creative_collision_rolls_back_whole_transaction(self):
        self.history.checkpoint(pack(creative())); before = self.history.path.read_bytes()
        with self.assertRaises(ValueError):
            self.history.checkpoint(pack({**creative(), 'drop_id': 'different'}))
        self.assertEqual(before, self.history.path.read_bytes())

    def test_manual_evidence_required(self):
        self.history.checkpoint(pack(creative()))
        with self.assertRaises(ValueError):
            self.history.mark(creative()['creative_id'], 'published', 'https://youtube.com/watch?v=proof')
        with self.assertRaises(ValueError):
            self.history.mark(creative()['creative_id'], 'published', 'javascript:bad', True)

    def test_damage_fails_closed_and_validated_backup_restores(self):
        self.history.checkpoint(pack())
        self.history.checkpoint({**pack(), 'headline':'A changed constraint'})
        backup = next((self.root/'backups').glob('*.json'))
        expected = json.loads(backup.read_text())
        self.history.path.write_text('{damaged')
        with self.assertRaises(ValueError): self.history.checkpoint(pack())
        self.assertEqual(self.history.restore(backup), expected)
        self.assertTrue(list(self.root.glob('before-restore-*.json')))

    def test_invalid_recovery_keeps_primary(self):
        self.history.checkpoint(pack()); before = self.history.path.read_bytes()
        invalid = self.root/'bad.json'; invalid.write_text('{"product":"another"}')
        with self.assertRaises(ValueError): self.history.restore(invalid)
        self.assertEqual(before, self.history.path.read_bytes())

    def test_tampered_backup_checksum_is_refused(self):
        self.history.checkpoint(pack())
        damaged=self.history.read()
        next(iter(damaged['packs'].values()))['revisions'][0]['pack']['headline']='tampered'
        candidate=self.root/'tampered.json';candidate.write_text(json.dumps(damaged))
        with self.assertRaises(ValueError):self.history.restore(candidate)

    def test_concurrent_writers_do_not_lose_records(self):
        def write(number):
            with History(self.root).transaction() as records:
                records['runs'][str(number)] = {'test':number}
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(write, range(15)))
        self.assertEqual(len(self.history.read()['runs']), 15)

    def test_corrupt_or_cross_product_schema_refused(self):
        atomic_json(self.history.path, {'schema_version':1,'product':'other'})
        with self.assertRaises(ValueError): self.history.read()

    def experiment(self):
        return {'id':'share-v1','hypothesis':'An exact-edition preview improves completion.',
                'audience':'Consenting beta cohort','changed_variable':'Preview title',
                'primary_metric':'finish_rate','guardrails':['No extra playback errors'],
                'duration_days':7,'min_sample':30,'stopping_rule':'Read after seven complete days; otherwise inconclusive.'}

    def test_experiment_definition_is_immutable(self):
        spec = self.experiment(); self.history.experiment(spec); self.history.experiment(spec)
        with self.assertRaises(ValueError): self.history.experiment({**spec,'min_sample':40})
        with self.assertRaises(ValueError): self.history.experiment({**spec,'id':'too-short','duration_days':1})

    def test_underpowered_result_cannot_scale(self):
        self.history.experiment(self.experiment())
        today = dt.datetime.now(dt.timezone.utc).date()
        result = {'started_on':str(today-dt.timedelta(days=8)), 'ended_on':str(today),
                  'sample':4,'value':0.4,'decision':'scale','evidence_ref':'query:fixture'}
        with self.assertRaises(ValueError): self.history.result('share-v1', result)
        self.history.result('share-v1',{**result,'decision':'hold'})
        self.assertEqual(self.history.read()['experiments']['share-v1']['status'], 'inconclusive')

    def test_negative_results_retained(self):
        self.history.experiment(self.experiment())
        today = dt.datetime.now(dt.timezone.utc).date()
        result = {'started_on':str(today-dt.timedelta(days=8)), 'ended_on':str(today),
                  'sample':40,'value':0.1,'decision':'kill','evidence_ref':'query:fixture'}
        self.history.result('share-v1', result); self.history.result('share-v1', result)
        self.assertEqual(len(self.history.read()['experiments']['share-v1']['results']), 1)
        self.assertEqual(self.history.read()['experiments']['share-v1']['status'], 'complete')


class MeasurementTests(unittest.TestCase):
    def score(self, rows):
        window = observation()
        return scorecard(rows, window['window_start'], window['window_end'])

    def test_missing_and_zero_are_different(self):
        self.assertEqual(self.score([])['unique_completers']['status'], 'missing')
        result = self.score([observation(value=0)])
        self.assertEqual(result['unique_completers']['value'], 0)
        self.assertEqual(result['unique_completers']['status'], 'measured')

    def test_zero_denominator_is_unknown(self):
        result = self.score([observation('unique_completers',0),observation('unique_players',0)])
        self.assertIsNone(result['finish_rate']['value'])

    def test_numeric_rate_has_denominator(self):
        result = self.score([observation(),observation('unique_players',10)])
        self.assertEqual(result['finish_rate']['value'],0.5)
        self.assertEqual(result['finish_rate']['denominator'],10)

    def test_numerators_cannot_exceed_denominator(self):
        with self.assertRaises(ValueError): self.score([observation(value=10), observation('unique_players',5)])

    def test_do_not_sum_daily_uniques_into_a_week(self):
        row = observation()
        start = str(dt.date.fromisoformat(row['window_end'])-dt.timedelta(days=6))
        result = scorecard([row],start,row['window_end'])
        self.assertIsNone(result['unique_completers']['value'])

    def test_duplicate_metric_window_refused(self):
        export = {'schema_version':1,'product':'fulltime','observations':[observation(),observation(value=6)]}
        with self.assertRaises(ValueError): validate_export(export)

    def test_cross_product_and_person_data_refused(self):
        with self.assertRaises(ValueError): validate_export({'schema_version':1,'product':'other','observations':[]})
        with self.assertRaises(ValueError): validate({**observation(),'email':'private@example.test'})

    def test_immature_retention_refused(self):
        day = dt.datetime.now(dt.timezone.utc).date()
        with self.assertRaises(ValueError):
            validate(observation('returners_7d',2,cohort_end=str(day-dt.timedelta(days=2)),follow_up_through=str(day)))

    def test_mature_retention_has_a_real_followup_window(self):
        day = dt.datetime.now(dt.timezone.utc).date()
        cohort = {'cohort_end':str(day-dt.timedelta(days=8)),'follow_up_through':str(day)}
        result = self.score([observation('returners_7d',4,**cohort),observation('mature_completers',10,**cohort)])
        self.assertEqual(result['return_rate_7d']['value'],0.4)

    def test_stale_counts_do_not_make_current_rates(self):
        old = dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=4)
        row = observation(observed_at=old.isoformat(),window_start=str(old.date()),window_end=str(old.date()))
        result = scorecard([row],row['window_start'],row['window_end'])
        self.assertEqual(result['unique_completers']['status'],'stale')

    def test_no_non_finite_or_fractional_counts(self):
        for value in (float('nan'),float('inf'),True,1.5,-1):
            with self.subTest(value=value), self.assertRaises(ValueError): validate(observation(value=value))


class ReportingAndRunnerTests(unittest.TestCase):
    def test_scheduled_job_cannot_silently_start_a_new_history(self):
        from engine.cli import main
        with tempfile.TemporaryDirectory() as root, patch.object(growth,'LOCAL',root), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):main(['run','morning','--require-existing-history'],growth)
            self.assertFalse((Path(root)/'engine/history.json').exists())

    def test_export_recovers_from_canonical_history_without_outbox_files(self):
        from engine.cli import main
        with tempfile.TemporaryDirectory() as root, patch.object(growth,'LOCAL',root), contextlib.redirect_stdout(io.StringIO()):
            History(Path(root)/'engine').checkpoint(pack(creative()))
            main(['export'],growth)
            exported=json.loads((Path(root)/'handoff/reporting-bundle.json').read_text())
            self.assertEqual(len(exported['reports']),1)
            self.assertIn(creative()['creative_id'],exported['creative_history'])
    def test_lossless_report_and_strict_receipt(self):
        original = pack({**creative(),'assets':['local/renders/clip.mp4']})
        bundle = envelope(original, {'id':'fulltime:2026-10-17:daily','digest':fingerprint(original)})
        self.assertEqual(bundle['pack']['items'][0]['holds'],creative()['holds'])
        self.assertEqual(bundle['pack']['items'][0]['assets'],['local/renders/clip.mp4'])
        report = {k:bundle[k] for k in ('report_id','revision','product_slug','venture','pack')}
        self.assertTrue(verify_receipt(bundle,{'ok':True,'report':report}))
        self.assertFalse(verify_receipt(bundle,{'ok':True,'ventures':['fulltime']}))
        altered = copy.deepcopy(report); altered['pack']['items'][0]['holds']=[]
        self.assertFalse(verify_receipt(bundle,{'ok':True,'report':altered}))
        altered = copy.deepcopy(report); altered['product_slug']='another'
        self.assertFalse(verify_receipt(bundle,{'ok':True,'report':altered}))

    def test_report_envelope_matches_the_published_schema_boundary(self):
        schema=json.loads(Path(growth.HERE,'contracts/reporting-v2.schema.json').read_text())
        original=pack(creative())
        bundle=envelope(original,{'id':'fulltime:2026-10-17:daily','digest':fingerprint(original)})
        self.assertEqual(set(bundle),set(schema['required']))
        for field,definition in schema['properties'].items():
            if 'const' in definition:self.assertEqual(bundle[field],definition['const'])
        self.assertIn(bundle['pack']['kind'],schema['properties']['pack']['properties']['kind']['enum'])

    def test_live_style_run_and_restart_are_idempotent(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth,'LOCAL',root), patch.object(growth,'load_state',return_value=state()):
            first = run(growth,'morning',offline=True)
            second = run(growth,'morning',offline=True)
            self.assertEqual(first['gate'],'HOLD')
            self.assertFalse(second['changed_since_same_run'])
            records = History(Path(root)/'engine').read()
            self.assertEqual(len(records['packs']),1)
            self.assertEqual(len(records['runs']),1)
            saved = json.loads(Path(second['report']).read_text())
            self.assertIsNone(saved['scorecard']['unique_completers']['value'])
            self.assertEqual(saved['usage']['model_calls'],0)
            self.assertEqual(saved['reporting_delivery'],'pending_handoff')
            self.assertEqual(len(saved['actions']),3)

    def test_changed_rules_stop_before_history_write(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth,'LOCAL',root), patch.object(growth,'load_state',return_value={**state(),'rules_ok':False}):
            with self.assertRaises(ValueError): run(growth,'morning',offline=True)
            self.assertFalse((Path(root)/'engine/history.json').exists())

    def test_stale_sync_stops(self):
        old = {**state(),'synced_at':(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=27)).isoformat()}
        with patch.object(growth,'load_state',return_value=old):
            with self.assertRaises(ValueError): run(growth,'weekly',offline=True)

    def test_weekly_review_keeps_human_decisions_untouched(self):
        with tempfile.TemporaryDirectory() as root, patch.object(growth,'LOCAL',root), patch.object(growth,'load_state',return_value=state()):
            result=run(growth,'weekly',offline=True)
            review=json.loads(Path(result['report']).read_text())['native_weekly_review']
            self.assertNotIn('krish_decision',review)
            self.assertNotIn('decided_at',review)
            self.assertEqual(set(review),{'product_slug','week_start','findings','kill_list','double_down'})


if __name__ == '__main__':
    unittest.main()
