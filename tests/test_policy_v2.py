"""The 27 October rulings in code: the new brand channels, the rulings file, the
per-take ORGANIC gate, the RELEASE fix (R43) and UTF-8 reads (R35). Every
fixture is synthetic, nothing reaches the network, and every write goes to a
temporary folder."""
import ast
import contextlib
import copy
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import growth
from engine import pack as v2pack
from engine import policy

HEADING = '2026-10-27 - Organic brand posts may recruit pilot testers before release, per-take gate'
WORDS = 'Go now, per-take gate (Recommended). Reserve all, push three (Recommended).'
THIN = 'aaaaaaaa-0000-4000-8000-00000000000a'
FULL = 'bbbbbbbb-0000-4000-8000-00000000000b'
NEW = ('threads', 'facebook', 'whatsapp_channel')


def rail():
    return [{'drop': THIN, 'date': '2026-10-26', 'home': 'Fixture Rovers', 'away': 'Fixture United',
             'score': [2, 1], 'pundits': ['zen'], 'fill': 1},
            {'drop': FULL, 'date': '2026-10-25', 'home': 'Sample Town', 'away': 'Sample City',
             'score': [0, 0], 'pundits': ['zen', 'gaffer', 'stats', 'doomer'], 'fill': 4}]


def identity(platform, host):
    return {'verified': True, 'platform': platform, 'account_scope': 'brand',
            'source_url': f'https://{host}/example-fixture',
            'verified_at': dt.datetime.now(dt.timezone.utc).isoformat()}


def ago(hours):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).replace(microsecond=0).isoformat()


def state(organic=True, d7=True, thin_only=False, verified=True):
    rulings = {'D1': {'in_force': True}, 'D7': {'in_force': d7}}
    if organic:
        rulings['ORGANIC'] = {'in_force': True}
    hosts = {'tiktok': 'tiktok.com', 'threads': 'www.threads.net', 'facebook': 'www.facebook.com',
             'whatsapp_channel': 'www.whatsapp.com', 'youtube': 'www.youtube.com'}
    return {'sha': 'a' * 40, 'synced_at': ago(1), 'decisions': [], 'rail': rail()[:1] if thin_only else rail(),
            'rulings': rulings, 'brand_identities': {p: identity(p, h) for p, h in hosts.items()} if verified else {}}


def take(platform='tiktok', **changes):
    item = {'platform': platform, 'account_scope': 'brand', 'identity_ref': platform, 'drop_id': THIN,
            'pundits': ['zen'], 'whole_match': False, 'holds': []}
    item.update(changes)
    return item


def pack(item):
    return {'pack_date': '2026-10-27', 'kind': 'daily', 'venture': 'fulltime', 'fulltime_sha': 'a' * 40,
            'headline': 'A synthetic pack', 'items': [item]}


class ChannelTests(unittest.TestCase):
    def test_new_brand_channels_have_codes_sources_and_ids(self):
        for platform, code in zip(NEW, ('TH', 'FB', 'WC')):
            with self.subTest(platform=platform):
                self.assertIn(platform, growth.PLATFORMS)
                self.assertIn(platform, policy.BRAND_CHANNELS)
                self.assertEqual(growth.PREFIX[platform], code)
                self.assertEqual(growth.SOURCE[code], platform)
                cid = f'{code}_CLASH_CLIP_C01_H01_V1_20261027'
                self.assertTrue(growth.CREATIVE_ID.match(cid))
                self.assertIn(f'utm_source={platform}&utm_medium=organic_video', growth.tracked('https://fulltime.fm/', cid))

    def test_listener_whatsapp_keeps_its_rule_and_stays_apart(self):
        self.assertNotIn('whatsapp', policy.BRAND_CHANNELS)
        self.assertTrue(any('listener' in e for e in policy.errors({'platform': 'whatsapp'}, state())))
        self.assertEqual(policy.errors({'platform': 'whatsapp', 'distribution': 'listener_initiated'}, state()), [])
        self.assertFalse(any('listener' in e for e in policy.errors(take('whatsapp_channel'), state())))
        self.assertTrue(any('account_scope brand' in e for e in policy.errors(take('whatsapp_channel', account_scope=''), state())))
        self.assertEqual(growth.SOURCE['WA'], 'wa')

    def test_a_listener_creative_id_is_refused_on_the_brand_channel(self):
        errors = growth.problems({**take('whatsapp_channel'), 'creative_id': 'WA_TRIBE_INVITE_C01_H01_V1_20261027',
                                  'text': 'The Reporter, an AI Pundit, on the match.'}, state())
        self.assertTrue(any('platform is whatsapp_channel (WC)' in e for e in errors))

    def test_identity_hosts_for_the_new_channels(self):
        good = {'threads': ('threads.net', 'www.threads.com'), 'facebook': ('facebook.com', 'www.facebook.com'),
                'whatsapp_channel': ('whatsapp.com', 'www.whatsapp.com')}
        for platform, hosts in good.items():
            for host in hosts:
                with self.subTest(platform=platform, host=host):
                    self.assertTrue(policy.identity_verified(identity(platform, host), platform))
        for platform, host in (('threads', 'instagram.com'), ('facebook', 'facebook.com.example.test'),
                               ('whatsapp_channel', 'wa.me'), ('whatsapp', 'whatsapp.com')):
            with self.subTest(platform=platform, host=host):
                self.assertFalse(policy.identity_verified(identity(platform, host), platform))

    def test_new_channels_wait_on_d1_and_must_say_ai(self):
        for platform in NEW:
            with self.subTest(platform=platform):
                self.assertEqual([rid for rid, _ in growth.gates_for(platform, {})], ['D1'])
                errors = growth.problems({**take(platform), 'needs': 'D1', 'text': 'The Doomer has thoughts.'}, state())
                self.assertTrue(any('must say it is AI' in e for e in errors))

    def test_threads_posts_are_five_hundred_characters_at_most(self):
        text = 'An AI Pundit ' + 'x' * 500
        self.assertTrue(any('500 at most' in e for e in growth.problems({**take('threads'), 'text': text}, state())))


class RulingsFileTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path(growth.HERE, 'rulings.json').read_text(encoding='utf-8'))
        self.rulings = self.data['rulings']

    def test_d1_to_d7_keep_their_shape_beside_organic_and_release(self):
        self.assertEqual(list(self.rulings), [f'D{i}' for i in range(1, 8)] + ['ORGANIC', 'RELEASE'])
        fields = {'title', 'recommendation', 'unlocks', 'requires', 'status', 'date', 'words', 'evidence'}
        for rid, ruling in self.rulings.items():
            with self.subTest(rid=rid):
                self.assertEqual(set(ruling), fields)

    def test_d1_records_the_27_october_decision(self):
        d1 = self.rulings['D1']
        self.assertEqual((d1['status'], d1['date'], d1['words'], d1['evidence']), ('approved', '2026-10-27', WORDS, HEADING))
        self.assertEqual(d1['unlocks'], ['tiktok', 'youtube', 'instagram', 'x', 'reddit', 'threads', 'facebook',
                                         'whatsapp_channel'])

    def test_organic_and_release_entries(self):
        organic, release = self.rulings['ORGANIC'], self.rulings['RELEASE']
        self.assertEqual(organic['title'], 'Organic brand posts recruit pilot-beta testers before the December '
                                           'release, gated per take')
        self.assertEqual((organic['status'], organic['date'], organic['words'], organic['evidence']),
                         ('approved', '2026-10-27', WORDS, HEADING))
        self.assertEqual((organic['requires'], organic['unlocks']), (['D1'], []))
        self.assertEqual((release['title'], release['status'], release['requires'], release['unlocks'], release['evidence']),
                         ('The product release decision', 'pending', [], [], ''))
        self.assertIn('ORGANIC', self.data['_about'])
        self.assertIn('RELEASE', self.data['_about'])
        self.assertNotIn('\u2014', json.dumps(self.data, ensure_ascii=False))

    def test_approved_is_not_in_force_until_the_decision_log_carries_the_heading(self):
        before = growth.rulings_state('## Decision log\n\n### 2026-10-16 - A pilot beta\n', self.rulings)
        for rid in ('D1', 'ORGANIC'):
            self.assertEqual((before[rid]['status'], before[rid]['in_force']), ('approved', False))
        after = growth.rulings_state(f'## Decision log\n\n### {HEADING}\n\n### 2026-10-16 - A pilot beta\n', self.rulings)
        self.assertTrue(after['D1']['in_force'] and after['ORGANIC']['in_force'])
        self.assertFalse(after['RELEASE']['in_force'])
        alone = copy.deepcopy(self.rulings); alone['D1']['status'] = 'pending'
        self.assertFalse(growth.rulings_state(f'## Decision log\n\n### {HEADING}\n', alone)['ORGANIC']['in_force'])

    def test_the_self_test_passes_with_the_new_entries(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            growth.self_test()
        self.assertIn('self-test passed', out.getvalue())


class OrganicGateTests(unittest.TestCase):
    def test_in_force_a_published_take_needs_no_release_or_rail(self):
        for platform in ('tiktok',) + NEW:
            with self.subTest(platform=platform):
                self.assertEqual(policy.errors(take(platform), state(thin_only=True)), [])
        self.assertFalse(policy.release_open(state()))

    def test_not_in_force_nothing_changes(self):
        errors = policy.errors(take(), state(organic=False, thin_only=True))
        self.assertTrue(any('RELEASE' in e for e in errors))
        self.assertTrue(any('no eligible match exists' in e for e in errors))
        self.assertEqual(policy.errors(take(holds=['RELEASE', 'RAIL']), state(organic=False, thin_only=True)), [])
        full = policy.errors(take(), state(organic=False))
        self.assertTrue(any('RELEASE' in e for e in full))
        self.assertFalse(any('RAIL' in e for e in full))

    def test_in_force_rail_means_the_per_take_gate(self):
        for changes, words in (({'pundits': ['gaffer']}, 'from gaffer'), ({'pundits': ['zen', 'doomer']}, 'from doomer'),
                               ({'pundits': []}, 'must name'), ({'pundits': None}, 'must name'),
                               ({'drop_id': 'cccccccc-0000-4000-8000-00000000000c'}, 'not a match'),
                               ({'drop_id': None}, 'not a match')):
            with self.subTest(changes=changes):
                errors = policy.errors(take(**changes), state())
                self.assertTrue(any('per-take gate' in e and words in e for e in errors), errors)
                self.assertEqual(policy.errors(take(holds=['RAIL'], **changes), state()), [])
        blind = {**state(), 'rail': None}
        self.assertTrue(any('not read' in e for e in policy.errors(take(), blind)))

    def test_a_whole_match_post_still_needs_four_of_six(self):
        self.assertTrue(any('whole-match' in e for e in policy.errors(take(whole_match=True), state())))
        for pundits in (None, []):   # no pundits key and an empty list fail closed alike
            with self.subTest(pundits=pundits):
                errors = policy.errors(take(whole_match=True, drop_id=FULL, pundits=pundits), state())
                self.assertTrue(any('per-take gate' in e and 'must name' in e for e in errors), errors)
        missing = {k: v for k, v in take(whole_match=True, drop_id=FULL).items() if k != 'pundits'}
        self.assertTrue(any('must name' in e for e in policy.errors(missing, state())))
        self.assertEqual(policy.errors(take(whole_match=True, drop_id=FULL, pundits=['zen', 'stats']), state()), [])
        self.assertTrue(any('from banter' in e for e in policy.errors(take(whole_match=True, drop_id=FULL,
                                                                             pundits=['banter']), state())))
        self.assertTrue(any('true or false' in e for e in policy.errors(take(whole_match='yes'), state())))

    def test_consent_and_channel_stay_required(self):
        self.assertTrue(any('CONSENT' in e for e in policy.errors(take(), state(d7=False))))
        self.assertTrue(any('CHANNEL' in e for e in policy.errors(take(), state(verified=False))))
        self.assertEqual(policy.errors(take(holds=['CONSENT', 'CHANNEL']), state(d7=False, verified=False)), [])

    def test_a_take_may_link_its_own_published_show_on_a_thin_rail(self):
        cid = 'TT_CLASH_CLIP_C01_H01_V1_20261027'
        own = growth.tracked(f'https://fulltime.fm/?drop={THIN}&pundit=zen', cid)
        item = {**take(), 'creative_id': cid, 'text': f'The Reporter, an AI Pundit, on Fixture Rovers 2-1: {own}'}
        self.assertEqual(growth.check_pack(pack(item), state()), [])
        self.assertTrue(any('push only' in e for e in growth.check_pack(pack(item), state(organic=False))))
        other = growth.tracked(f'https://fulltime.fm/?drop={THIN}&pundit=zen', cid)
        elsewhere = {**item, 'drop_id': FULL, 'pundits': ['gaffer'], 'text': f'The Gaffer, an AI Pundit: {other}'}
        self.assertTrue(any('push only' in e for e in growth.check_pack(pack(elsewhere), state())))


class WholeMatchFlagTests(unittest.TestCase):
    """A missing whole_match fails closed: it is never read as a per-take post."""
    cid = 'TT_CLASH_CLIP_C02_H01_V1_20261027'

    def worded(self, drop=THIN, **changes):
        link = growth.tracked(f'https://fulltime.fm/?drop={drop}&pundit=zen', self.cid)
        return {**take(**changes), 'drop_id': drop, 'creative_id': self.cid,
                'text': f'Every AI Pundit on Fixture Rovers 2-1. Hear all six: {link}'}

    def test_whole_match_words_need_whole_match_true(self):
        omitted = {k: v for k, v in self.worded().items() if k != 'whole_match'}
        for item in (omitted, self.worded(whole_match=False)):
            with self.subTest(whole_match=item.get('whole_match', 'omitted')):
                errors = growth.check_pack(pack(item), state())
                self.assertTrue(any('whole' in e and 'per-take gate' in e for e in errors), errors)
                self.assertTrue(any('push only' in e for e in errors), errors)   # its thin link is refused too
        self.assertTrue(any('a whole-match post needs 4' in e for e in growth.check_pack(pack(self.worded(whole_match=True)), state())))
        full = self.worded(drop=FULL, whole_match=True, pundits=['zen'])
        self.assertEqual(growth.check_pack(pack({**full, 'text': full['text'].replace('Fixture Rovers 2-1', 'Sample Town 0-0')}), state()), [])

    def test_a_take_that_omits_whole_match_is_held_not_per_take(self):
        link = growth.tracked(f'https://fulltime.fm/?drop={THIN}&pundit=zen', self.cid)
        item = {k: v for k, v in take(creative_id=self.cid, text=f'The Reporter, an AI Pundit, on Fixture Rovers 2-1: {link}').items()
                if k != 'whole_match'}
        self.assertIn('whole_match, true or false', policy.take_gate(item, state()))
        errors = growth.check_pack(pack(item), state())
        self.assertTrue(any('per-take gate' in e and 'whole_match' in e for e in errors), errors)
        self.assertTrue(any('push only' in e for e in errors), errors)
        self.assertEqual(growth.check_pack(pack({**item, 'whole_match': False}), state()), [])

    def test_the_words_are_the_ones_engine_pack_reads(self):
        self.assertEqual(policy.WHOLE_MATCH_WORDS.pattern, v2pack.WHOLE_MATCH_WORDS.pattern)
        self.assertEqual(policy.WHOLE_MATCH_WORDS.flags, v2pack.WHOLE_MATCH_WORDS.flags)
        self.assertEqual(policy.claims_whole_match({'text': 'The Reporter, one of six AI Pundits.'}), '')
        self.assertEqual(policy.claims_whole_match({'text': 'All six AI Pundits on it.'}), 'All six AI Pundits')


class SyncAgeTests(unittest.TestCase):
    """The per-take gate and growth.py check refuse a rail from a sync over 26 hours old."""
    def test_the_per_take_gate_refuses_an_old_or_undated_sync(self):
        self.assertEqual(policy.take_gate(take(), {**state(), 'synced_at': ago(25)}), '')
        for synced, words in ((ago(27), '27 hours old (over 26)'), (ago(-1), 'in the future'), (None, 'RFC 3339'),
                              ('2026-10-27 05:00', 'RFC 3339'), ('2026-10-27T05:00:00', 'RFC 3339')):
            with self.subTest(synced=synced):
                old = {**state(), 'synced_at': synced}
                self.assertIn(words, policy.take_gate(take(), old))
                self.assertTrue(any('per-take gate' in e and words in e for e in policy.errors(take(), old)))
                self.assertEqual(policy.errors(take(holds=['RAIL']), old), [])

    def test_freshness_refuses_an_old_sync(self):
        synced = {'sha': 'a' * 40, 'rules_ok': True, 'canon': {}}
        head = lambda: 'a' * 40   # noqa: E731
        stale = growth.freshness({'fulltime_sha': 'a' * 40}, {**synced, 'synced_at': ago(27)}, head, None)
        self.assertEqual(len(stale), 1)
        self.assertIn('sync', stale[0])
        self.assertEqual(growth.freshness({'fulltime_sha': 'a' * 40}, {**synced, 'synced_at': ago(25)}, head, None), [])
        self.assertTrue(growth.freshness({'fulltime_sha': 'a' * 40}, synced, head, None))

    def test_check_refuses_a_pack_from_a_five_day_old_sync(self):
        cid = 'TT_CLASH_CLIP_C05_H01_V1_20261027'
        link = growth.tracked(f'https://fulltime.fm/?drop={THIN}&pundit=zen', cid)
        item = {**take(), 'identity_ref': 'tt', 'creative_id': cid, 'text': f'The Reporter, an AI Pundit, on Fixture Rovers 2-1: {link}'}
        old = {**state(), 'synced_at': ago(5 * 24), 'rules_ok': True, 'canon': {}}
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'state').mkdir()
            Path(root, 'state', 'fulltime.json').write_text(json.dumps(old), encoding='utf-8')
            Path(root, 'brand-identities.json').write_text(json.dumps(
                {'product': 'fulltime', 'identities': {'tt': identity('tiktok', 'www.tiktok.com')}}), encoding='utf-8')
            Path(root, 'pack.json').write_text(json.dumps(pack(item)), encoding='utf-8')
            out = io.StringIO()
            with patch.object(growth, 'LOCAL', root), patch.object(growth, 'head_sha', lambda: 'a' * 40), \
                    patch.object(growth, 'raw', lambda p, s: None), patch.object(sys, 'argv', ['growth.py', 'check', str(Path(root, 'pack.json'))]), \
                    contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
                growth.main()
        self.assertEqual(stopped.exception.code, 1)
        self.assertIn('120 hours old (over 26)', out.getvalue())


class LinkTests(unittest.TestCase):
    def threads(self, text, **changes):
        return growth.check_pack(pack({**take('threads', **changes), 'creative_id': 'TH_CLASH_POST_C03_H01_V1_20261027',
                                       'text': text}), state())

    def test_a_product_link_without_https_is_checked(self):
        bare = self.threads('The Reporter, an AI Pundit, on Fixture Rovers 2-1. Listen free at fulltime.fm')
        self.assertTrue(any('fulltime.fm is not tracked' in e for e in bare), bare)
        self.assertTrue(any('no https://' in e for e in bare), bare)
        www = self.threads(f'The Gaffer, an AI Pundit, rages: www.fulltime.fm/?drop={THIN}&pundit=gaffer')
        self.assertTrue(any('made no show' in e for e in www), www)
        self.assertTrue(any('not tracked' in e for e in www), www)

    def test_the_product_inbox_and_internal_notes_are_not_links(self):
        self.assertFalse(any('link' in e for e in self.threads('The Reporter, an AI Pundit. Feedback: krish@fulltime.fm')))
        note = {'platform': 'other', 'text': 'Check the rail at fulltime.fm before the morning run.'}
        self.assertEqual(growth.check_pack(pack(note), state()), [])
        self.assertTrue(growth.check_pack(pack({**note, 'text': 'See https://fulltime.fm/ first.'}), state()))

    def test_a_link_naming_drop_or_pundit_twice_is_refused(self):
        cid = 'TT_CLASH_CLIP_C04_H01_V1_20261027'
        for query in ('drop=' + THIN + '&pundit=gaffer&pundit=zen', 'drop=' + FULL + '&drop=' + THIN + '&pundit=zen'):
            with self.subTest(query=query):
                link = growth.tracked(f'https://fulltime.fm/?{query}', cid)
                errors = growth.check_pack(pack({**take(), 'creative_id': cid,
                                                 'text': f'The Reporter, an AI Pundit, on Fixture Rovers 2-1: {link}'}), state())
                self.assertTrue(any('more than once' in e for e in errors), errors)
                held = growth.check_pack(pack({**take(holds=['RAIL']), 'creative_id': cid,
                                               'text': f'The Reporter, an AI Pundit, on Fixture Rovers 2-1: {link}'}), state())
                self.assertTrue(any('more than once' in e for e in held), held)

    def test_a_draft_with_no_creative_id_keeps_its_channel_tracking(self):
        def errors(cid):
            link = growth.tracked(f'https://fulltime.fm/?drop={THIN}&pundit=zen', cid)
            return growth.check_pack(pack({**take(), 'text': f'The Reporter, an AI Pundit, on Fixture Rovers 2-1: {link}'}), state())
        other = errors('YT_CLASH_SHORT_C01_H01_V1_20261027')
        self.assertTrue(any('a YT creative, but the draft is on tiktok (TT)' in e for e in other), other)
        self.assertEqual(errors('TT_CLASH_CLIP_C01_H01_V1_20261027'), [])
        listener = growth.tracked(f'https://fulltime.fm/?drop={FULL}&pundit=zen', 'INV_TRIBE_INVITE_C01_H01_V1_20261027')
        self.assertFalse(any('creative, but' in e for e in growth.problems(
            {'platform': 'whatsapp', 'distribution': 'listener_initiated', 'text': f'An AI Pundit for you: {listener}'}, state())))


class PushGateTests(unittest.TestCase):
    def test_under_organic_per_take_is_open_while_whole_match_waits(self):
        thin = rail()[:1]
        gate = growth.push_gate(thin, state())
        self.assertEqual((gate['open'], gate['per_take']), (False, True))
        self.assertIn('no match has 4 of 6', gate['why'])
        self.assertIn('under ORGANIC a single take', gate['why'])
        self.assertEqual(growth.push_gate(thin), {'open': False, 'why': 'no match has 4 of 6 AI Pundits (newest: 1 of 6)'})
        self.assertNotIn('per_take', growth.push_gate(thin, state(organic=False)))
        self.assertFalse(growth.push_gate(None, state())['per_take'])
        self.assertFalse(growth.push_gate([{**thin[0], 'pundits': [], 'fill': 0}], state())['per_take'])
        self.assertTrue(growth.push_gate(rail(), state())['open'])

    def test_now_md_says_per_take_is_open_beside_the_hold(self):
        s = {'repo': 'krishanraja/full-time', 'sha': 'a' * 40, 'synced_at': ago(0), 'rules_ok': True, 'rules': {},
             'rail': rail()[:1], 'rulings': {}, 'decisions': [], 'changed_since_last_sync': [], 'canon_added': [],
             'canon_removed': [], 'feed': [], 'canon': {}, 'canon_from_index': True, 'commits': [], 'open_pulls': [],
             'notes': [], 'push': growth.push_gate(rail()[:1], state())}
        md = growth.now_md(s)
        self.assertIn('## Whole-match push gate: HOLD', md)
        self.assertNotIn('## Push gate: HOLD', md)
        self.assertIn('## Per-take gate (ORGANIC): OPEN', md)
        self.assertIn('Whole-match promotion still waits for 4 of 6.', md)
        self.assertNotIn('Per-take', growth.now_md({**s, 'push': growth.push_gate(rail()[:1])}))
        self.assertNotIn('\u2014', md)


class ReleaseEvidenceTests(unittest.TestCase):
    def rulings(self, status='approved', evidence='2026-12-01 - Full Time releases'):
        return {'RELEASE': {'title': 'The product release decision', 'status': status, 'evidence': evidence,
                            'requires': [], 'unlocks': []}}

    def test_written_only_when_approved_and_in_the_synced_decisions(self):
        heads = ['2026-12-01 - Full Time releases', '2026-10-16 - A pilot beta']
        record = growth.release_evidence(self.rulings(), heads, 'c' * 40)
        self.assertEqual(record, {'verified': True, 'fulltime_sha': 'c' * 40,
                                  'decision_heading': '2026-12-01 - Full Time releases',
                                  'source_path': 'docs/12-roadmap.md'})
        self.assertTrue(policy.release_open({'sha': 'c' * 40, 'decisions': heads, 'marketing_release': record}))
        self.assertFalse(policy.release_needed({'sha': 'c' * 40, 'decisions': heads, 'marketing_release': record}))
        for rulings, decided in ((self.rulings('pending'), heads), (self.rulings(), heads[1:]),
                                 (self.rulings(evidence=''), heads), ({}, heads), (None, None)):
            with self.subTest(rulings=rulings, decided=decided):
                self.assertIsNone(growth.release_evidence(rulings, decided, 'c' * 40))

    def synced(self, rulings, heading, newer=(), with_md=False):
        log = ''.join(f'### {h}\n\nx\n\n' for h in list(newer) + [heading])
        files = {'docs/README.md': '# Docs index', 'docs/12-roadmap.md': f'## Decision log\n\n{log}'}

        def http(url, accept_json=True, timeout=60):
            if 'fulltime.fm' in url:
                raise AssertionError('no product read in this test')
            return []
        with tempfile.TemporaryDirectory() as root, \
                patch.object(growth, 'LOCAL', root), patch.object(growth, 'head_sha', lambda: 'c' * 40), \
                patch.object(growth, 'raw', lambda path, sha: files.get(path)), patch.object(growth, 'http', http), \
                patch.object(growth, 'read_rail', rail), patch.object(growth, 'read_feed', lambda: []), \
                patch.object(growth, 'load_state', lambda published_only=False: None), \
                patch.object(growth, 'load_rulings', lambda: copy.deepcopy(rulings)), \
                patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            returned = growth.sync(quiet=True)
            saved = json.loads(Path(root, 'state', 'fulltime.json').read_text(encoding='utf-8'))
            md = Path(root, 'state', 'FULLTIME-NOW.md').read_text(encoding='utf-8')
        return (returned, saved, md) if with_md else (returned, saved)

    def test_release_stays_open_when_newer_decisions_are_logged(self):
        heading = '2026-12-01 - Full Time releases'
        newer = [f'2027-01-{day:02d} - A later decision {day}' for day in range(9, 2, -1)]   # seven newer headings
        _, saved, md = self.synced(self.rulings(evidence=heading), heading, newer, with_md=True)
        self.assertEqual(saved['decisions'], newer + [heading])
        self.assertEqual(saved['marketing_release']['decision_heading'], heading)
        self.assertTrue(policy.release_open(saved))
        self.assertFalse(policy.release_needed(saved))
        latest = md.split('## Latest decisions')[1].split('## The Reporter feed')[0]
        self.assertEqual(latest.count('\n- '), 6)
        self.assertNotIn(heading, latest)

    def test_release_stays_closed_when_its_heading_is_not_logged(self):
        heading = '2026-12-01 - Full Time releases'
        _, saved = self.synced(self.rulings(evidence=heading), '2026-10-16 - A pilot beta',
                               [f'2027-01-{day:02d} - A later decision {day}' for day in range(9, 2, -1)])
        self.assertNotIn('marketing_release', saved)
        self.assertFalse(policy.release_open(saved))
        self.assertFalse(policy.release_open({**saved, 'marketing_release': {
            'verified': True, 'fulltime_sha': 'c' * 40, 'decision_heading': heading, 'source_path': 'docs/12-roadmap.md'}}))

    def test_sync_records_the_per_take_gate_under_organic(self):
        returned, saved, md = self.synced(growth.load_rulings(), HEADING, with_md=True)
        self.assertTrue(policy.organic_in_force(saved))
        self.assertTrue(saved['push']['per_take'])
        self.assertIn('## Per-take gate (ORGANIC): OPEN', md)

    def test_sync_writes_marketing_release_from_the_decision_heading(self):
        heading = '2026-12-01 - Full Time releases'
        returned, saved = self.synced(self.rulings(evidence=heading), heading)
        self.assertEqual(saved['marketing_release'], {'verified': True, 'fulltime_sha': 'c' * 40,
                                                      'decision_heading': heading, 'source_path': 'docs/12-roadmap.md'})
        self.assertTrue(policy.release_open(saved))
        self.assertTrue(saved['rulings']['RELEASE']['in_force'])
        self.assertEqual(returned['marketing_release'], saved['marketing_release'])

    def test_sync_writes_nothing_while_release_is_pending_or_unrecorded(self):
        heading = '2026-12-01 - Full Time releases'
        for rulings, logged in ((self.rulings('pending', heading), heading),
                                (self.rulings(evidence=heading), '2026-10-16 - A pilot beta')):
            with self.subTest(rulings=rulings, logged=logged):
                _, saved = self.synced(rulings, logged)
                self.assertNotIn('marketing_release', saved)
                self.assertFalse(policy.release_open(saved))


FILES = ('growth.py', 'engine/policy.py', 'engine/assets.py')


def text_io_without_utf8(path):
    """Lines in a source file that read or write text without encoding='utf-8'."""
    out = []
    for node in ast.walk(ast.parse(Path(growth.HERE, path).read_text(encoding='utf-8'))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''
        keywords = {k.arg: k.value for k in node.keywords}
        encoding = keywords.get('encoding')
        utf8 = isinstance(encoding, ast.Constant) and encoding.value == 'utf-8'
        if name in ('read_text', 'write_text') and not utf8:
            out.append(node.lineno)
        elif name == 'open' and isinstance(func, ast.Name):
            mode = node.args[1] if len(node.args) > 1 else keywords.get('mode')
            if not (isinstance(mode, ast.Constant) and 'b' in str(mode.value)) and not utf8:
                out.append(node.lineno)
        elif isinstance(keywords.get('text'), ast.Constant) and keywords['text'].value is True and not utf8:
            out.append(node.lineno)
    return out


class Utf8Tests(unittest.TestCase):
    def test_every_text_read_and_write_names_utf8(self):
        for path in FILES:
            with self.subTest(path=path):
                self.assertEqual(text_io_without_utf8(path), [])

    def test_the_checker_finds_a_missing_encoding(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'sample.py').write_text("from pathlib import Path\nPath('a').read_text()\nopen('b')\n"
                                               "open('c', 'rb')\nPath('d').write_text('x', encoding='utf-8')\n",
                                               encoding='utf-8')
            with patch.object(growth, 'HERE', root):
                self.assertEqual(sorted(text_io_without_utf8('sample.py')), [2, 3])

    def test_reads_raise_no_default_encoding_warning(self):
        script = ('import json, os, sys, tempfile\n'
                  'from pathlib import Path\n'
                  'import growth\n'
                  'from engine import policy\n'
                  'root = tempfile.mkdtemp()\n'
                  "Path(root, 'brand-identities.json').write_bytes(json.dumps({'product': 'fulltime', "
                  "'identities': {'x': {'note': 'caf\\u00e9 \\u00a3'}}}, ensure_ascii=False).encode('utf-8'))\n"
                  "assert policy.load_identities(root)['x']['note'] == 'caf\\u00e9 \\u00a3'\n"
                  "assert 'ORGANIC' in growth.load_rulings()\n"
                  "os.makedirs(os.path.join(root, 'state'))\n"
                  "Path(root, 'state', 'fulltime.json').write_bytes(json.dumps({'sha': 'a' * 40, 'note': '\\u00e9'}, "
                  "ensure_ascii=False).encode('utf-8'))\n"
                  'growth.LOCAL = root\n'
                  "assert growth.load_state()['note'] == '\\u00e9'\n")
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run([sys.executable, '-X', 'warn_default_encoding', '-W', 'error::EncodingWarning',
                                 '-c', script], cwd=growth.HERE, capture_output=True, text=True, encoding='utf-8',
                                env=env, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
