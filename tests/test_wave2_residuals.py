"""Regressions for the residuals the second review wave left open: a declined post holds
no slot, a receipt closes only its own matchday's G2 from its own channel's host, an
unknown kind of automated action is refused whatever words it uses, and the engine's
gate reads ORGANIC everywhere it is computed."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import audience, control_center, gates, reporting  # noqa: E402
import test_integration_v2 as v2  # noqa: E402


def post(cid):
    return {'item_id': cid, 'creative_id': cid, 'platform': 'tiktok', 'why': 'take',
            'text': f'Take {cid}', 'estimated_minutes': 5}


class DeclinedPostsHoldNoSlot(unittest.TestCase):
    def build(self, items, answered=()):
        return reporting.build('fulltime:2026-10-27:daily', 'live', '2026-10-27T06:00:00Z', {}, items, {}, [],
                               ['test'], answered=answered)

    def test_three_declined_posts_never_block_the_fourth(self):
        first = self.build([post('TT_A'), post('TT_B'), post('TT_C')])
        done = {(p['proposal_id'], p['payload_sha256']) for p in first['proposals'] if ':post:' in p['proposal_id']}
        self.assertEqual(len(done), 1)      # one ask of a kind at a time
        all_three = set()
        for cid in ('TT_A', 'TT_B', 'TT_C'):
            p = reporting.action_proposal(post(cid))
            all_three.add((p['proposal_id'], p['payload_sha256']))
        later = self.build([post('TT_A'), post('TT_B'), post('TT_C'), post('TT_D')], answered=all_three)
        ids = [p['proposal_id'] for p in later['proposals'] if ':post:' in p['proposal_id']]
        self.assertEqual(ids, ['fulltime:post:TT_D'])
        self.assertTrue(any('Already answered, not asked again' in a['line'] for a in later['activity']))
        self.assertEqual(reporting.schema_errors(later), [])


class ReceiptsCloseOnlyTheirOwnMatchday(unittest.TestCase):
    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)
        _, self.proposal = v2.queued_pack(self.local, '2026-11-01', v2.take_on('drop-a', 1), drops=('drop-a',))
        report = v2.report_with_gates(self.local)
        self.sent = next(p for p in report['proposals'] if p['proposal_id'] == self.proposal['proposal_id'])
        self.item = json.loads(self.sent['exact_payload'])['items'][0]
        gates.settle(self.local, control_center.classify(
            [{'proposal_id': self.sent['proposal_id'], 'decision': 'approved',
              'payload_sha256': self.sent['payload_sha256']}], report['proposals']))

    def receipt(self, link, at):
        return {'creative_id': self.item['creative_id'], 'channel': self.item['channel'],
                'permalink': link, 'published_at': at}

    def test_a_post_from_before_the_matchday_never_closes_it(self):
        gates.record_receipts(self.local, [self.receipt('https://www.tiktok.com/@fulltime/video/1',
                                                        '2026-10-20T19:00:00Z')])
        self.assertEqual(gates.events(self.local, '2026-10-01'), [])
        gates.record_receipts(self.local, [self.receipt('https://www.tiktok.com/@fulltime/video/2',
                                                        '2026-11-01T19:00:00Z')])
        events = gates.events(self.local, '2026-10-01')
        self.assertEqual([e['evidence_url'] for e in events], ['https://www.tiktok.com/@fulltime/video/2'])

    def test_a_permalink_off_its_channels_host_or_carrying_contact_details_is_refused(self):
        for link in ('https://evil.example/@fulltime/video/1', 'https://tiktok.com.evil.example/v/1',
                     'https://user:pw@www.tiktok.com/v/1', 'https://www.tiktok.com/@someone@gmail.com'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                gates.record_receipts(self.local, [self.receipt(link, '2026-11-01T19:00:00Z')])
        self.assertFalse((self.local / 'engine' / 'receipts.jsonl').exists())


class UnknownActionKindsAreRefused(unittest.TestCase):
    def test_a_synonym_for_a_banned_tactic_is_refused_even_when_the_file_approves_it(self):
        import copy
        import datetime as dt
        root = Path(__file__).resolve().parents[1]
        allow = json.loads((root / 'examples' / 'buffer-channels.example.json').read_text(encoding='utf-8'))
        base = json.loads((root / 'engagement-actions.json').read_text(encoding='utf-8'))
        now = dt.datetime(2026, 11, 1, 12, tzinfo=dt.timezone.utc)
        for aid, title, platform, api, account in (
                ('react_to_fan_replies', 'React with a heart to every fan reply', 'x', 'X API v2', 'fulltime-x'),
                ('make_daily_reel_container', "Create the day's reel container", 'instagram',
                 'Instagram Graph API POST /{ig-user-id}/media', 'fulltime-ig-reels')):
            actions = copy.deepcopy(base)
            actions['actions'][aid] = {
                'title': title, 'platforms': [platform], 'official_api': api,
                'rule_source': 'https://help.x.com/en/rules-and-policies/x-automation',
                'rule_checked_on': '2026-10-30', 'status': 'approved',
                'ruling': {'date': '2026-10-31', 'words': 'yes'}, 'daily_cap': 400, 'needs_review_each_time': False}
            with self.subTest(aid=aid):
                self.assertEqual(audience.actions_errors(actions, now.date()), [])
                with self.assertRaisesRegex(ValueError, 'not a kind of action this engine knows'):
                    audience.gate(aid, platform, account, now, 0, actions=actions, allowlist=allow)

    def test_every_action_in_the_registry_is_a_known_kind(self):
        actions = json.loads((Path(__file__).resolve().parents[1] / 'engagement-actions.json')
                             .read_text(encoding='utf-8'))['actions']
        self.assertEqual(set(actions) - audience.KNOWN_ACTIONS, set())


class GateReadsOrganicEverywhere(unittest.TestCase):
    def test_runner_and_loop_pass_the_state_to_the_push_gate(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn('growth.push_gate(rail, state)', (root / 'engine' / 'runner.py').read_text(encoding='utf-8'))
        self.assertIn("growth.push_gate(state.get('rail'), state)",
                      (root / 'engine' / 'control_center.py').read_text(encoding='utf-8'))


class RenderReceiptsProveTheirChecks(unittest.TestCase):
    """A pack item whose video is a finished render takes that render's checks from its
    own receipt, so readiness never waits on hand-typed checks the engine already proved."""

    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)

    def receipt(self, holds):
        from engine import assets
        folder = self.local / 'renders' / 'TT_CLASH_CLIP_C01_H01_V1_20261101' / 'abcd'
        folder.mkdir(parents=True)
        (folder / 'render.json').write_text(json.dumps({
            'creative_id': 'TT_CLASH_CLIP_C01_H01_V1_20261101', 'video_sha256': 'a' * 64, 'holds': holds}),
            encoding='utf-8')
        return assets

    def test_a_clean_render_proves_its_four_checks(self):
        assets = self.receipt([])
        found = assets.render_checks(self.local, 'TT_CLASH_CLIP_C01_H01_V1_20261101',
                                     [{'kind': 'video', 'sha256': 'a' * 64}])
        self.assertEqual(found, {'exact_quote': True, 'dimensions': True, 'media_hashes': True,
                                 'captions_aligned': True})

    def test_other_bytes_or_another_creative_prove_nothing(self):
        # Caption alignment is Krish's verdict on these exact bytes in G2 (only a no-edit
        # "post it" counts), so an ASSETS hold before his review takes nothing away.
        assets = self.receipt(['ASSETS'])
        cid = 'TT_CLASH_CLIP_C01_H01_V1_20261101'
        self.assertTrue(assets.render_checks(self.local, cid, [{'kind': 'video', 'sha256': 'a' * 64}])
                        ['captions_aligned'])
        self.assertEqual(assets.render_checks(self.local, cid, [{'kind': 'video', 'sha256': 'b' * 64}]), {})
        self.assertEqual(assets.render_checks(self.local, 'TT_OTHER', [{'kind': 'video', 'sha256': 'a' * 64}]), {})


if __name__ == '__main__':
    unittest.main()
