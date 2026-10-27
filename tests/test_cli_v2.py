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
    """The pack fixture's allowlist without its planted personal channel, which load_allowlist refuses."""
    brand = allowlist()
    del brand['channels']['personal-tiktok']
    return brand


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

    def test_pack_check_refuses_without_the_allowlist(self):
        pack = self.write('pack.json', {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01',
                                        'items': [take()]})
        code, _, err = self.run_cli('pack', 'check', pack, '--offline')
        self.assertEqual(code, 1)
        self.assertIn('no Buffer allowlist', err)

    def test_buffer_query_names_only_allowlisted_channels(self):
        self.write('local/buffer-channels.json', allowlist())
        code, _, err = self.run_cli('buffer', 'query')
        self.assertEqual(code, 1)
        self.assertIn('refused', err)   # the fixture plants a personal channel, so the whole allowlist fails
        self.write('local/buffer-channels.json', brand_allowlist())
        code, body, _ = self.run_cli('buffer', 'query')
        self.assertEqual(code, 0)
        self.assertNotIn('999999999999999999999999', json.dumps(body))
        self.assertEqual(body['list_posts']['status'], ['sent'])

    def test_library_reconcile_example_is_clean(self):
        code, body, _ = self.run_cli('library', 'reconcile', str(ROOT / 'examples' / 'library-listing.example.json'))
        self.assertEqual((code, body['clean'], body['hold']), (0, True, None))
        code, body, _ = self.run_cli('library', 'name', '03_Runs/Bad_Name.MP4')
        self.assertTrue(body['03_Runs/Bad_Name.MP4'])

    def test_session_pack_stays_under_36_kb(self):
        code, body, _ = self.run_cli('session', 'pack', '--kind', 'orchestrator', '--spec', str(EXAMPLE), '--check')
        self.assertEqual(code, 0)
        self.assertLessEqual(body['bytes'], body['limit'])
        code, _, err = self.run_cli('session', 'pack', '--kind', 'scheduled')
        self.assertEqual(code, 1)
        self.assertIn('no pack', err)

    def test_dispatch_needs_a_reading_or_a_spend_decision_and_never_runs(self):
        code, _, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex')
        self.assertEqual(code, 1)
        self.assertIn('spend decision', err)
        card = json.loads(CARD.read_text(encoding='utf-8'))
        decision = self.write('decision.json', {'decision_id': 'dec-1', 'approved': True, 'card_id': card['card_id']})
        code, body, err = self.run_cli('dispatch', str(CARD), '--plugin-root', '/plugins/codex',
                                       '--spend-decision', decision)
        self.assertEqual(code, 0, err)
        argv = body['run_this']
        self.assertEqual(argv[argv.index('--model') + 1], dispatch.PINNED_CODEX_MODEL)
        prompt = Path(body['prompt_file'])
        self.assertTrue(prompt.is_file())
        self.assertIn(Path(self.growth.LOCAL).resolve(), prompt.resolve().parents)

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
