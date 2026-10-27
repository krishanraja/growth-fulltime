import contextlib
import io
import json
import shutil
import tempfile
import types
import unittest
from pathlib import Path

import growth
from engine import cli, dispatch
from tests.test_pack import allowlist, state, take

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / 'specs' / 'examples' / 'synthetic-week.json'
CARD = ROOT / 'tasks' / 'match-ad-v8-mix-port.json'


def brand_allowlist():
    """The pack fixture's allowlist without its planted personal channel, which load_allowlist
    refuses, and with the organisation Buffer's list_posts needs."""
    brand = allowlist()
    del brand['channels']['personal-tiktok']
    brand['organization_id'] = '0' * 24
    return brand


def buffer_records(allow):
    """Buffer's own channel records for every allowlisted ID, as list_channels returns them."""
    seen = {}
    for entry in allow['channels'].values():
        if entry['buffer_channel_id']:
            seen[entry['buffer_channel_id']] = {'id': entry['buffer_channel_id'], 'service': entry['service'],
                                                'name': entry.get('buffer_name') or 'fulltime'}
    return list(seen.values())


class CliV2(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.rail_reads = 0

        def read_rail():
            self.rail_reads += 1
            return state()['rail']
        self.growth = types.SimpleNamespace(LOCAL=str(self.tmp / 'local'), HERE=str(ROOT),
                                            load_state=lambda: state(), read_rail=read_rail)

    def write(self, name, value):
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return str(path)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                cli.main(list(argv), self.growth)
            except SystemExit as stop:
                code = stop.code
        text = out.getvalue()
        try:
            body = json.loads(text)
        except ValueError:
            body = text
        return code, body, err.getvalue()

    def test_spec_check_digests_the_same_way_twice(self):
        first = self.run_cli('spec', 'check', str(EXAMPLE))
        second = self.run_cli('spec', 'digest', str(EXAMPLE))
        self.assertEqual(first[0], 0)
        self.assertEqual(first[1]['payload_sha256'], second[1]['payload_sha256'])

    def test_spec_check_refuses_a_broken_spec(self):
        broken = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        broken['mode'] = 'yolo'
        code, _, err = self.run_cli('spec', 'check', self.write('broken.json', broken))
        self.assertEqual(code, 1)
        self.assertIn('spec.mode', err)

    def test_a_spec_relies_only_on_learnings_the_register_holds_and_never_a_refuted_one(self):
        from engine import learning
        campaign = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        campaign['learnings_applied'] = ['learning-001']
        path = self.write('learned.json', campaign)
        sign = ('spec', 'propose', path, '--expires-at', '2026-11-02T08:00:00+00:00')
        code, _, err = self.run_cli(*sign)
        self.assertEqual(code, 1)
        self.assertIn('not in the learning register', err)
        lid = learning.add(self.growth.LOCAL, 'Cold opens on the scoreline travel further', 'shares per post',
                           'Refuted if the control wins by |z| 2 over two matchweeks', ['take_clip'])
        self.assertEqual(lid, 'learning-001')
        code, body, err = self.run_cli(*sign)
        self.assertEqual((code, body['sent']), (0, False), err)
        self.assertEqual(self.run_cli('spec', 'check', path)[0], 0)     # structure alone never reads the register
        learning.observe(self.growth.LOCAL, lid, a=20, b=60, matchweeks=2, preregistered=True,
                         overlapping=False, planned_matchweeks=2)              # the control won clearly
        code, _, err = self.run_cli(*sign)
        self.assertEqual(code, 1)
        self.assertIn('was refuted', err)

    def test_spec_propose_prepares_and_never_sends(self):
        code, _, err = self.run_cli('spec', 'propose', str(EXAMPLE))
        self.assertEqual(code, 1)
        self.assertIn('--expires-at', err)
        code, body, _ = self.run_cli('spec', 'propose', str(EXAMPLE), '--expires-at', '2026-11-02T08:00:00+00:00')
        self.assertEqual(code, 0)
        self.assertIs(body['sent'], False)
        self.assertEqual((body['proposal']['stage'], body['proposal']['wall']), ('plan', 'strategy'))

    def test_live_spec_does_not_compile_without_gates(self):
        live = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        live['mode'] = 'live'
        code, _, err = self.run_cli('spec', 'compile', self.write('live.json', live))
        self.assertEqual(code, 1)
        self.assertIn('not ready', err)

    def test_formats_list_and_unlocked_readiness(self):
        code, body, _ = self.run_cli('formats', 'list')
        self.assertEqual(sorted(body), ['match_ad', 'morning_card', 'row', 'take_clip'])
        verdicts = self.write('verdicts.json', [])
        code, body, _ = self.run_cli('formats', 'readiness', '--verdicts', verdicts, '--spec', str(EXAMPLE))
        self.assertEqual(code, 0)
        self.assertFalse(any(row['ready'] for row in body.values()))

    def test_pack_check_reads_the_live_rail_and_offline_fails_closed(self):
        self.write('local/buffer-channels.json', brand_allowlist())
        pack = self.write('pack.json', {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01',
                                        'items': [take()]})
        code, body, err = self.run_cli('pack', 'check', pack)
        self.assertEqual(code, 0, err)
        self.assertEqual((body['rail'], body['today_live'], self.rail_reads), ('live', True, 1))
        code, body, _ = self.run_cli('pack', 'check', pack, '--offline')
        self.assertEqual((code, body['today_live'], self.rail_reads), (0, False, 1))
        code, body, _ = self.run_cli('pack', 'propose', pack, '--expires-at', '2026-11-01T20:00:00+00:00')
        self.assertEqual((code, body['sent'], body['proposal']['wall']), (0, False, 'post'))

    def week_44(self, lock):
        """The synthetic week moved to 26 October to 1 November, with take_clip pinned."""
        week = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        week.update(run_id='fulltime:2026-W44', window={'start': '2026-10-26', 'end': '2026-11-01', 'tz': 'Europe/London'})
        for n, fixture in enumerate(week['fixtures']):
            fixture['kickoff'] = f'2026-11-01T1{2 + n}:30:00+00:00'
        for item in week['formats']:
            if item['format_id'] == 'take_clip':
                item['lock_version'] = lock
        return self.write('week-44.json', week)

    def test_pack_propose_queue_waits_for_the_loop_and_readiness_reads_the_ledger(self):
        from engine import formats
        lock = formats.lock_of('take_clip')
        self.write('local/buffer-channels.json', brand_allowlist())
        item = take(fixture_ref='synthetic-fixture-001', lock_version=lock)
        pack = self.write('pack.json', {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01', 'items': [item]})
        context = self.write('context.json', {item['creative_id']: {'unit_cost_gbp': 0.0, 'unit_minutes': 6}})
        code, body, err = self.run_cli('pack', 'propose', pack, '--expires-at', '2026-11-01T20:00:00+00:00',
                                       '--queue', '--spec', self.week_44(lock), '--context', context)
        self.assertEqual((code, body['sent'], body['kind'], body['mode']), (0, False, 'g2', 'proof'), err)
        gate = json.loads(Path(body['path']).read_text(encoding='utf-8'))
        self.assertTrue(gate['checked'])
        recorded = gate['context'][item['creative_id']]
        self.assertEqual((recorded['unit_cost_gbp'], recorded['unit_minutes']), (0.0, 6))
        self.assertTrue(recorded['checks']['copy_checks'] and recorded['checks']['show_published'])
        self.assertNotIn('captions_aligned', recorded['checks'])     # only the producer can record that one
        self.assertIn('nothing', gate['proposal']['why'].lower())       # proof mode: a verdict ask, not a post
        code, body, _ = self.run_cli('formats', 'readiness', '--format', 'take_clip', '--lock', lock)
        self.assertEqual((code, body['ready'], body['streak']), (0, False, 0))

    def test_a_pack_item_outside_the_week_spec_is_refused(self):
        from engine import formats
        lock = formats.lock_of('take_clip')
        self.write('local/buffer-channels.json', brand_allowlist())
        item = take(fixture_ref='a-match-the-spec-never-named', lock_version=lock)
        pack = self.write('pack.json', {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01', 'items': [item]})
        code, _, err = self.run_cli('pack', 'check', pack, '--offline', '--spec', self.week_44(lock))
        self.assertEqual(code, 1)
        self.assertIn('fixture_ref', err)

    def test_pack_check_refuses_without_the_allowlist(self):
        pack = self.write('pack.json', {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01',
                                        'items': [take()]})
        code, _, err = self.run_cli('pack', 'check', pack, '--offline')
        self.assertEqual(code, 1)
        self.assertIn('no Buffer allowlist', err)

    def test_buffer_query_names_only_allowlisted_channels(self):
        records = self.write('channels.json', buffer_records(brand_allowlist()))
        self.write('local/buffer-channels.json', allowlist())
        code, _, err = self.run_cli('buffer', 'query', '--channels', records)
        self.assertEqual(code, 1)
        self.assertIn('refused', err)   # the fixture plants a personal channel, so the whole allowlist fails
        self.write('local/buffer-channels.json', brand_allowlist())
        code, body, err = self.run_cli('buffer', 'query', '--channels', records)
        self.assertEqual(code, 0, err)
        wrong = buffer_records(brand_allowlist())
        wrong[0]['service'] = 'instagram'                # Buffer says this ID is another service
        code, _, err = self.run_cli('buffer', 'query', '--channels', self.write('wrong.json', wrong))
        self.assertEqual(code, 1, err)
        self.assertNotIn('999999999999999999999999', json.dumps(body))
        self.assertEqual(body['list_posts']['status'], ['sent'])

    def test_library_reconcile_example_is_clean(self):
        code, body, _ = self.run_cli('library', 'reconcile', str(ROOT / 'examples' / 'library-listing.example.json'))
        self.assertEqual((code, body['clean'], body['hold']), (0, True, None))
        code, body, _ = self.run_cli('library', 'name', '03_Runs/Bad_Name.MP4')
        self.assertTrue(body['03_Runs/Bad_Name.MP4'])

    def test_library_bundle_round_trips_and_the_canva_and_stamp_checks_run(self):
        source = self.tmp / 'notes.md'
        source.write_text('A private note.\n', encoding='utf-8')
        out, back = self.tmp / 'parts', self.tmp / 'back'
        code, body, err = self.run_cli('library', 'bundle', str(source), '--out', str(out), '--created-on', '2026-10-27')
        self.assertEqual(code, 0, err)
        manifest = self.write('manifest.json', body['manifest'])
        code, body, err = self.run_cli('library', 'assemble', manifest, '--parts', str(out), '--out', str(back))
        self.assertEqual(code, 0, err)
        canva = self.write('canva.json', [{'path': 'Templates', 'is_folder': True},
                                          {'path': 'Random', 'is_folder': True}])
        code, body, _ = self.run_cli('library', 'canva', canva)
        self.assertEqual((code, body['clean'], body['hold']['code']), (0, False, 'LIBRARY'))
        stamped = self.tmp / 'copy.md'
        stamped.write_text('# Plan\n\nsource: docs/ENGINE-V2.md@' + 'a' * 40 + '\n', encoding='utf-8')
        code, body, _ = self.run_cli('library', 'stamp', str(stamped), '--repo-path', 'docs/ENGINE-V2.md')
        self.assertEqual((code, body['errors']), (0, []))

    def test_session_pack_stays_under_36_kb(self):
        code, body, _ = self.run_cli('session', 'pack', '--kind', 'orchestrator', '--spec', str(EXAMPLE), '--check')
        self.assertEqual(code, 0)
        self.assertLessEqual(body['bytes'], body['limit'])
        code, _, err = self.run_cli('session', 'pack', '--kind', 'scheduled')
        self.assertEqual(code, 1)
        self.assertIn('no pack', err)

    def test_session_pack_calls_a_spec_signed_only_from_the_g1_record(self):
        campaign = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        code, text, err = self.run_cli('session', 'pack', '--kind', 'orchestrator', '--spec', str(EXAMPLE))
        self.assertEqual(code, 0, err)
        self.assertIn('## Spec (not signed)', text)
        self.assertNotIn('Signed spec', text)
        self.assertIn('Not supplied to this pack', text)
        record = self.write('local/specs/2026-W44.signed.json', {'spec': campaign, 'proposal_id': 'fulltime-spec-2026-W44',
                                                                  'amended': False, 'signed_at': '2026-10-27T09:00:00Z'})
        code, text, err = self.run_cli('session', 'pack', '--kind', 'orchestrator', '--spec', record)
        self.assertEqual(code, 0, err)
        self.assertIn('## Signed spec', text)

    def test_session_pack_carries_the_build_card_and_the_review_contact_sheet(self):
        code, text, err = self.run_cli('session', 'pack', '--kind', 'build', '--card', str(CARD))
        self.assertEqual(code, 0, err)
        card = json.loads(CARD.read_text(encoding='utf-8'))
        self.assertIn('## Task card ' + card['card_id'], text)
        for path in card['read_files']:
            self.assertIn('- ' + path, text)
        code, text, err = self.run_cli('session', 'pack', '--kind', 'review', '--crew', 'librarian',
                                       '--contact-sheet', 'Drive 03_Runs/2026-W44/sheet.png')
        self.assertEqual(code, 0, err)
        self.assertIn('Rubric for packs', text)
        self.assertIn('Drive 03_Runs/2026-W44/sheet.png', text)

    def approve_spend(self, card, amount=0):
        """Krish's yes to the card's spend ask, classified and recorded by the engine's own loop."""
        from engine import control_center
        proposal = dispatch.spend_proposal(card, amount, '2026-10-28T12:00:00Z')
        decided = control_center.classify([{'proposal_id': proposal['proposal_id'], 'decision': 'approved',
                                            'decided_at': '2026-10-27T11:00:00Z', 'stage': None, 'amended': False,
                                            'payload_sha256': proposal['payload_sha256']}], [proposal])
        control_center.record_instructions(self.growth.LOCAL, decided['instructions'], '2026-10-27T11:05:00Z')
        return proposal

    def test_dispatch_needs_a_reading_or_krish_approval_of_this_exact_card_and_never_runs(self):
        code, _, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex')
        self.assertEqual(code, 1)
        self.assertIn('spend decision', err)
        self.assertIn('fulltime-codex-match-ad-v8-mix-port', err)
        card = json.loads(CARD.read_text(encoding='utf-8'))
        # Was --spend-decision FILE, which took any hand-written {'approved': true, 'card_id': ...}.
        decision = self.write('decision.json', {'decision_id': 'dec-1', 'approved': True, 'card_id': card['card_id']})
        code, _, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex', '--spend-decision', decision)
        self.assertEqual(code, 2)
        instructions = Path(self.growth.LOCAL) / 'control-center' / 'instructions.jsonl'
        instructions.parent.mkdir(parents=True)
        instructions.write_text(json.dumps({'proposal_id': 'fulltime-codex-' + card['card_id'], 'wall': 'spend',
                                            'amended': False, 'stage': None, 'amount_usd': 0,
                                            'sha256': 'f' * 64}) + '\n', encoding='utf-8')
        code, _, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex')
        self.assertEqual(code, 1)
        self.assertIn('was given on a different payload', err)
        older = dict(card, max_minutes=90)
        self.approve_spend(older)
        code, _, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex')
        self.assertEqual(code, 1, 'his yes to another version of the card does not carry over')
        proposal = self.approve_spend(card)
        code, body, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex')
        self.assertEqual(code, 0, err)
        self.assertEqual(body['spend_approval'], {'proposal_id': proposal['proposal_id'], 'amount_usd': 0,
                                                  'sha256': proposal['payload_sha256']})
        argv = body['run_this']
        self.assertEqual(argv[argv.index('--model') + 1], dispatch.PINNED_CODEX_MODEL)
        prompt = Path(body['prompt_file'])
        self.assertTrue(prompt.is_file())
        self.assertIn(Path(self.growth.LOCAL).resolve(), prompt.resolve().parents)

    def test_dispatch_with_a_fresh_low_reading_needs_no_approval(self):
        import datetime as dt
        moment = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        reading = self.write('reading.json', {'pct': 40, 'read_at': moment})
        code, body, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex', '--reading', reading)
        self.assertEqual(code, 0, err)
        self.assertIsNone(body['spend_approval'])
        code, _, err = self.run_cli('dispatch', str(CARD), '--reading', reading)
        self.assertEqual(code, 1)
        self.assertIn('--plugin-root', err)

    def test_dispatch_prepares_the_spend_ask_and_never_sends_it(self):
        code, body, err = self.run_cli('dispatch', str(CARD), '--propose-spend', '0', '--expires-at',
                                       '2026-10-28T12:00:00Z')
        self.assertEqual(code, 0, err)
        self.assertEqual((body['prepared'], body['sent']), (True, False))
        card = json.loads(CARD.read_text(encoding='utf-8'))
        self.assertEqual(body['proposal']['exact_payload'], dispatch.reporting.canonical(card))
        self.assertEqual(body['proposal']['wall'], 'spend')
        code, _, err = self.run_cli('dispatch', str(CARD), '--propose-spend', '0')
        self.assertEqual(code, 1)
        self.assertIn('--expires-at', err)

    def test_audience_plan_leaves_every_unruled_action_to_krish(self):
        code, body, _ = self.run_cli('audience', 'actions')
        self.assertEqual(code, 0)
        self.assertTrue(all(row['status'] == 'pending' for row in body.values()))
        code, body, err = self.run_cli('audience', 'plan')
        self.assertEqual(code, 0, err)
        self.assertTrue(body)
        self.assertTrue(all(item['who'] == 'krish' for item in body))
        code, body, _ = self.run_cli('audience', 'followers')
        self.assertTrue(all(row['followers']['change'] is None for row in body))

    def test_ga4_doctor_without_credentials_stops_before_any_read(self):
        code, body, _ = self.run_cli('ga4', 'doctor')
        self.assertEqual(code, 2)
        self.assertEqual(body['error_code'], 'missing_ga4_credentials')

    def test_growth_routes_every_v2_verb_to_the_engine(self):
        for verb in cli.V2 + ('ga4',):
            self.assertIn(verb, growth.ENGINE_COMMANDS)


if __name__ == '__main__':
    unittest.main()
