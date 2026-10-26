"""Synthetic regression fixtures only; no private creative or owner quotations."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from engine.creative_system import (Invalid, System, canonical, digest, export_bundle,
                                   file_hash, import_bundle, read, safe, validate, write_new, private_output, REPO)


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def fixture(root):
    root = Path(root)
    evidence = {'schema_version': 1, 'scope': 'Synthetic example', 'holdout_status': 'none',
                'creative_baseline': None, 'items': [{'id': 'e1', 'quote': 'Fixture requirement',
                'source_ref': 'fixture:e1', 'occurred_at': None, 'speaker': 'user',
                'situation': 'Synthetic fixture', 'classification': 'explicit_requirement',
                'artifact_ids': [], 'historical': False, 'superseded_by': None}]}
    save(root/'evidence/1.json', evidence)
    save(root/'archive-manifest.json', {'schema_version': 1, 'files': []})
    (root/'archive').mkdir(); (root/'archive/audio.wav').write_bytes(b'synthetic-locked-reference')
    (root/'archive/candidate.bin').write_bytes(b'synthetic-output')
    modules, characters, shared = [], [], []
    for mid in ['style.humour', 'character.one', 'character.two', 'character.three']:
        char = mid.startswith('character.')
        m = {'schema_version': 1, 'id': mid, 'version': '1.0.0',
             'kind': 'character' if char else 'shared', 'name': mid, 'surface': 'fictional_ad',
             'status': 'captured_requirements', 'summary': 'Synthetic module',
             'owns': [mid], 'depends_on': ['style.humour'] if char else [], 'canonical_ref': None,
             'rules': [{'id': mid+'.identity', 'instruction': 'Synthetic requirement',
                       'observable': 'Synthetic observation', 'media': ['audio','video'],
                       'state': 'owner_requirement', 'evidence_ids': ['e1'],
                       'regression_risk': 'Retain independent characters'}]}
        path = 'modules/'+mid+'/1.0.0.json'; save(root/path, m)
        modules.append({'id': mid, 'version': '1.0.0', 'path': path, 'sha256': file_hash(root/path)})
        (characters if char else shared).append(mid)
    cases = {'schema_version': 1, 'items': [{'id': 'case-'+str(i), 'modules': [mid],
             'criteria': [mid+'.identity'], 'prompt': 'Synthetic canary',
             'reference_asset_ids': [], 'always_run': True, 'evidence_class': 'synthetic_canary',
             'holdout': False} for i, mid in enumerate(characters)]}
    save(root/'cases/1.json', cases)
    r = {'schema_version': 1, 'id': 'fixture-v1', 'status': 'captured_baseline',
         'purpose': 'Synthetic project', 'modules': modules, 'characters': characters,
         'shared': shared, 'evidence': {'path': 'evidence/1.json', 'sha256': file_hash(root/'evidence/1.json')},
         'cases': {'path': 'cases/1.json', 'sha256': file_hash(root/'cases/1.json')},
         'archive': {'path': 'archive-manifest.json', 'sha256': file_hash(root/'archive-manifest.json')},
         'locks': [{'id': 'locked-audio', 'path': 'archive/audio.wav',
                    'sha256': file_hash(root/'archive/audio.wav'), 'approval_scope': 'Audio only', 'evidence_ids': ['e1']}],
         'addressed_feedback': [], 'limitations': ['Unmeasured fixture'], 'next_action': 'Review'}
    save(root/'releases/one.json', r)
    save(root/'CURRENT.json', {'schema_version':1, 'release':'releases/one.json','sha256':digest(r)})
    return r


class CreativeSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.base = Path(self.temp.name)
        self.root = self.base/'private'; self.root.mkdir()
        self.release = fixture(self.root); self.system = System(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, ids=('character.one',)):
        candidate = copy.deepcopy(self.release); candidate['id'] = 'fixture-v2'; candidate['status'] = 'candidate'
        for pin in candidate['modules']:
            if pin['id'] in ids:
                module = read(self.root/pin['path']); module['version'] = '1.0.1'
                module['summary'] = 'Changed synthetic performance'
                pin['version'] = '1.0.1'; pin['path'] = 'modules/'+pin['id']+'/1.0.1.json'
                save(self.root/pin['path'], module); pin['sha256'] = file_hash(self.root/pin['path'])
        save(self.root/'releases/two.json', candidate); return candidate

    def rewrite_release(self, release):
        save(self.root/'releases/one.json', release)
        save(self.root/'CURRENT.json', {'schema_version':1,'release':'releases/one.json','sha256':digest(release)})

    def production(self):
        return {'schema_version':1, 'id':'fixture-output', 'release_path':'releases/one.json',
                'release_sha256':digest(self.release), 'characters':['character.one'], 'medium':'video',
                'assets':[{'id':'output','path':'archive/candidate.bin','sha256':file_hash(self.root/'archive/candidate.bin')}],
                'technical_pass':True, 'addressed_feedback':[], 'external_holds':[]}

    def artifact_review(self, production, verdict='holds', kind='owner'):
        return {'schema_version':1,'id':'review-1','reviewer_kind':kind,'source_ref':'fixture:review',
                'release_sha256':digest(self.release),'production_sha256':digest(production),
                'assets_sha256':digest(production['assets']), 'findings':[
                    {'criterion':k+'.identity','verdict':verdict,'evidence':'fixture:sample'}
                    for k in ['style.humour','character.one']]}

    def regression_reviews(self):
        candidate = read(self.root/'releases/two.json')
        cases = read(self.root/'cases/1.json')['items']
        return [{'schema_version':1,'case_id':case['id'],'case_sha256':digest(case),
                 'baseline_sha256':digest(self.release),'candidate_sha256':digest(candidate),
                 'baseline_artifact_sha256':'1'*64,'candidate_artifact_sha256':'2'*64,
                 'reviewer_kind':'owner','source_ref':'fixture:owner-review',
                 'preference':'candidate' if case['id'] == 'case-0' else 'tie',
                 'reason':'Synthetic controlled comparison',
                 'findings':[{'criterion':k,'baseline':'holds','candidate':'holds',
                              'evidence':'fixture:compared-output'} for k in case['criteria']]}
                for case in cases]

    def test_selected_character_does_not_receive_siblings(self):
        p = self.system.compose(['character.one'])
        self.assertEqual([x['id'] for x in p['characters']], ['character.one'])
        self.assertNotIn('character.two', json.dumps(p))
        self.assertEqual(len(p['shared']), 1)

    def test_repeated_composition_is_identical(self):
        self.assertEqual(self.system.compose(['character.one']), self.system.compose(['character.one']))

    def test_missing_private_baseline_refuses_fallback(self):
        with self.assertRaisesRegex(Invalid,'restore'):
            System(self.base/'missing').load_release()

    def test_unknown_schema_fields_are_rejected(self):
        bad = self.production(); bad['automatic_approval'] = True
        with self.assertRaisesRegex(Invalid,'unknown field'):
            validate(bad,'production')

    def test_character_rule_budget_prevents_an_instruction_dump(self):
        m = read(self.root/self.release['modules'][1]['path'])
        m['rules'] *= 13
        with self.assertRaisesRegex(Invalid,'too many items'):validate(m,'module')

    def test_schema_boolean_cannot_masquerade_as_version_one(self):
        bad = self.production(); bad['schema_version'] = True
        with self.assertRaises(Invalid):validate(bad,'production')

    def test_module_integrity_is_verified_before_use(self):
        (self.root/self.release['modules'][0]['path']).write_text('{}')
        with self.assertRaisesRegex(Invalid,'integrity'):
            self.system.compose(['character.one'])

    def test_current_pointer_is_content_bound(self):
        p = read(self.root/'CURRENT.json'); p['sha256'] = '0'*64; save(self.root/'CURRENT.json',p)
        with self.assertRaisesRegex(Invalid,'digest'):
            self.system.load_release()

    def test_cross_character_rule_ownership_is_rejected(self):
        pin = self.release['modules'][1]; m = read(self.root/pin['path'])
        m['rules'][0]['id'] = 'character.two.identity'; save(self.root/pin['path'],m)
        pin['sha256'] = file_hash(self.root/pin['path']); self.rewrite_release(self.release)
        with self.assertRaisesRegex(Invalid,'cross-owner'):
            self.system.load_release()

    def test_character_inheritance_is_rejected(self):
        pin = self.release['modules'][1]; m = read(self.root/pin['path'])
        m['depends_on'] = ['character.two']; save(self.root/pin['path'],m)
        pin['sha256'] = file_hash(self.root/pin['path']); self.rewrite_release(self.release)
        with self.assertRaisesRegex(Invalid,'sibling'):
            self.system.load_release()

    def test_locked_audio_tamper_is_rejected(self):
        (self.root/'archive/audio.wav').write_bytes(b'changed')
        with self.assertRaisesRegex(Invalid,'locked artifact'):
            self.system.load_release()

    def test_archive_manifest_is_pinned(self):
        save(self.root/'archive-manifest.json',{'schema_version':1,'files':[],'changed':True})
        with self.assertRaisesRegex(Invalid,'manifest integrity'):
            self.system.startup()

    def test_unknown_provenance_is_rejected(self):
        pin = self.release['modules'][1]; m = read(self.root/pin['path'])
        m['rules'][0]['evidence_ids'] = ['imaginary']; save(self.root/pin['path'],m)
        pin['sha256'] = file_hash(self.root/pin['path']); self.rewrite_release(self.release)
        with self.assertRaisesRegex(Invalid,'provenance'):
            self.system.load_release()

    def test_undeclared_sibling_edit_is_rejected(self):
        self.candidate(('character.one','character.two'))
        with self.assertRaisesRegex(Invalid,'declared owners'):
            self.system.change_plan('releases/two.json',['character.one'])

    def test_one_character_change_keeps_siblings_and_runs_canaries(self):
        self.candidate(); plan = self.system.change_plan('releases/two.json',['character.one'])
        self.assertEqual(plan['affected'],['character.one'])
        self.assertIn('character.two',plan['untouched']); self.assertEqual(len(plan['required_cases']),3)

    def test_shared_change_invalidates_all_dependent_characters(self):
        self.candidate(('style.humour',)); p = self.system.change_plan('releases/two.json',['style.humour'])
        self.assertEqual(set(p['affected']),set(self.release['characters']+self.release['shared']))

    def test_review_absence_holds_change(self):
        self.candidate(); result = self.system.change_gate('releases/two.json',['character.one'],[])
        self.assertEqual(result['status'],'held'); self.assertEqual(len(result['holds']),4)

    def test_no_measured_improvement_cannot_replace_baseline(self):
        self.candidate(); reports = self.regression_reviews()
        for report in reports:report['preference'] = 'tie'
        result = self.system.change_gate('releases/two.json',['character.one'],reports)
        self.assertEqual(result['status'],'held')
        self.assertIn('no owner-observed improvement in an affected case',result['holds'])

    def test_model_review_cannot_promote_creative(self):
        self.candidate(); reports = self.regression_reviews(); reports[0]['reviewer_kind'] = 'model'
        result = self.system.change_gate('releases/two.json',['character.one'],reports)
        self.assertEqual(result['status'],'held')

    def test_stale_comparison_is_rejected(self):
        self.candidate(); reports = self.regression_reviews(); reports[0]['candidate_sha256'] = '0'*64
        with self.assertRaisesRegex(Invalid,'exact release'):
            self.system.change_gate('releases/two.json',['character.one'],reports)

    def test_regression_in_untouched_character_blocks_change(self):
        self.candidate(); reports = self.regression_reviews()
        reports[1]['findings'][0]['candidate'] = 'breaks'
        self.assertEqual(self.system.change_gate('releases/two.json',['character.one'],reports)['status'],'held')

    def test_cannot_delete_a_regression_canary(self):
        c = self.candidate(); data = read(self.root/'cases/1.json'); data['items'].pop()
        save(self.root/'cases/2.json',data); c['cases'] = {'path':'cases/2.json','sha256':file_hash(self.root/'cases/2.json')}; save(self.root/'releases/two.json',c)
        with self.assertRaisesRegex(Invalid,'cannot be removed'):
            self.system.change_plan('releases/two.json',['character.one'])

    def test_technical_pass_never_substitutes_for_owner_review(self):
        result = self.system.artifact_gate(self.production(),[])
        self.assertEqual(result['status'],'held'); self.assertFalse(result['creative_accepted'])

    def test_owner_rejection_holds_even_when_all_technical_checks_pass(self):
        p = self.production(); result = self.system.artifact_gate(p,[self.artifact_review(p,'breaks')])
        self.assertEqual(result['status'],'held')

    def test_asset_changes_invalidate_old_review(self):
        p = self.production(); review = self.artifact_review(p)
        (self.root/'archive/candidate.bin').write_bytes(b'updated')
        p['assets'][0]['sha256'] = file_hash(self.root/'archive/candidate.bin')
        with self.assertRaisesRegex(Invalid,'wrong inputs'):
            self.system.artifact_gate(p,[review])

    def test_not_assessed_and_not_applicable_are_not_passes(self):
        for verdict in ['not_assessed','not_applicable']:
            p = self.production()
            self.assertEqual(self.system.artifact_gate(p,[self.artifact_review(p,verdict)])['status'],'held')

    def test_even_passing_artifact_gate_never_authorizes_publication(self):
        p = self.production(); r = self.system.artifact_gate(p,[self.artifact_review(p)])
        self.assertEqual(r['status'],'ready_for_owner_release_review')
        self.assertFalse(r['publishing_authorized']); self.assertFalse(r['generation_authorized'])

    def test_old_artifact_cannot_bypass_new_standards(self):
        p = self.production(); self.candidate()
        c = read(self.root/'releases/two.json')
        save(self.root/'CURRENT.json',{'schema_version':1,'release':'releases/two.json','sha256':digest(c)})
        with self.assertRaisesRegex(Invalid,'superseded'):
            self.system.artifact_gate(p,[self.artifact_review(p)])

    def test_feedback_is_idempotent_and_does_not_rewrite_standards(self):
        before = file_hash(self.root/'CURRENT.json')
        event = {'schema_version':1,'id':'feedback-1','occurred_at':'2026-01-01',
                 'quote':'Synthetic correction','source_ref':'fixture:feedback','modules':['character.one'],
                 'artifact_ids':[],'scope':'Fixture output','effect':'rejected_dimensions','notes':'Fixture'}
        self.assertFalse(self.system.record_feedback(event)['duplicate'])
        self.assertTrue(self.system.record_feedback(event)['duplicate'])
        self.assertEqual(before,file_hash(self.root/'CURRENT.json'))
        self.assertEqual(self.system.compose(['character.one'])['pending_feedback'][0]['id'],'feedback-1')
        event['quote'] = 'Changed event'
        with self.assertRaisesRegex(Invalid,'ID reuse'):self.system.record_feedback(event)

    def test_owner_promotion_binds_exact_candidate_and_review_set(self):
        c = self.candidate(); reports = self.regression_reviews()
        d = {'schema_version':1,'id':'decision-1','reviewer_kind':'owner','decision':'approve',
             'candidate_sha256':digest(c),'review_set_sha256':digest(reports),'source_ref':'fixture:approval'}
        wrong = {**d,'candidate_sha256':'0'*64}
        with self.assertRaisesRegex(Invalid,'exact owner'):self.system.promote('releases/two.json',['character.one'],reports,wrong)
        self.system.promote('releases/two.json',['character.one'],reports,d)
        self.assertEqual(self.system.load_release()[0]['id'],'fixture-v2')
        self.assertTrue((self.root/'promotions/decision-1.json').exists())
        self.assertTrue(self.system.promote('releases/two.json',['character.one'],reports,d)['duplicate'])

    def test_promotion_lease_prevents_competing_writers(self):
        (self.root/'.promotion.lock').write_text('in progress')
        with self.assertRaisesRegex(Invalid,'owns the standards pointer'):
            self.system.promote('releases/none.json',[],[],{})
        self.assertEqual(self.system.load_release()[0]['id'],'fixture-v1')

    def test_immutable_writes_refuse_replacement(self):
        with self.assertRaises(FileExistsError):write_new(self.root/'CURRENT.json',{})

    def test_path_traversal_and_windows_paths_are_rejected(self):
        for rel in ['../outside','/absolute','C:/outside','..\\outside']:
            with self.assertRaises(Invalid):safe(self.root,rel)

    def test_private_packets_cannot_be_written_into_public_repo(self):
        with self.assertRaisesRegex(Invalid,'public repository'):
            private_output(REPO/'creative-system'/'private-draft.json')
        self.assertEqual(private_output(REPO/'local'/'packet.json'),REPO/'local'/'packet.json')

    def test_private_bundle_round_trip_verifies_every_byte(self):
        target = self.base/'bundle.zip'; result = export_bundle(self.root,target)
        restored = self.base/'restored'; import_bundle(target,restored,result['sha256'])
        for p in self.root.rglob('*'):
            if p.is_file():self.assertEqual(p.read_bytes(),(restored/p.relative_to(self.root)).read_bytes())
        self.assertEqual(System(restored).startup()['release'],self.release['id'])

    def test_bundle_tamper_and_existing_destination_are_refused(self):
        target = self.base/'bundle.zip'; result = export_bundle(self.root,target)
        with self.assertRaises(Invalid):import_bundle(target,self.base/'restore','0'*64)
        with self.assertRaises(Invalid):import_bundle(target,self.root,result['sha256'])

    def test_restore_refuses_zip_slip_before_any_write(self):
        target = self.base/'bad.zip'
        with zipfile.ZipFile(target,'w') as z:
            z.writestr('../escape',b'bad')
            z.writestr('BUNDLE-MANIFEST.json',json.dumps({'files':[{'path':'../escape','bytes':3,'sha256':digest('x')}]}))
        with self.assertRaises(Invalid):import_bundle(target,self.base/'restore',file_hash(target))
        self.assertFalse((self.base/'escape').exists())

    def test_clean_process_startup_is_reproducible(self):
        result = subprocess.run([sys.executable,'-m','engine.creative_system','--root',str(self.root),'startup'],
                                cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['release_sha256'],digest(self.release))


if __name__ == '__main__':
    unittest.main()
