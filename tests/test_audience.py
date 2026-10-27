import copy
import datetime as dt
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

import growth
from engine import audience
from engine.audience import daily_plan, followers_check, gate, load_actions, profile_checklist

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / 'examples' / 'buffer-channels.example.json'
NOW = dt.datetime(2026, 10, 27, 12, 0, tzinfo=dt.timezone.utc)
AVATAR = 'a' * 64
SEED = {'reply_to_comments_on_own_posts', 'hide_or_report_abusive_comments_on_own_posts',
        'pin_best_comment_on_own_post', 'update_profile_bio_and_links', 'rotate_pinned_post',
        'add_post_to_playlist_or_highlight', 'schedule_story_or_community_post', 'crosslink_profiles'}
CID = {'tiktok': 'TT_TRIBE_POST_C01_H01_V1_20261101', 'instagram': 'IG_TRIBE_POST_C01_H01_V1_20261101',
       'youtube': 'YT_TRIBE_POST_C01_H01_V1_20261101', 'x': 'X_TRIBE_POST_C01_H01_V1_20261101'}
# Built at run time so no credential-shaped literal sits in the repository.
SECRET = 'gh' + 'p_' + 'Zq7' * 12
LOWER = 'gh' + 'p_' + 'zq7' * 12     # also matches the lowercase id and allowlist ref patterns


def registry():
    return json.loads(audience.ACTIONS_FILE.read_text(encoding='utf-8'))


def approve(data, aid, checked='2026-10-20', **extra):
    data['actions'][aid].update(status='approved', ruling={'date': '2026-10-27', 'words': 'yes, within the rules'},
                                rule_checked_on=checked, **extra)
    return data


def allowlist():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def write(folder, data):
    path = Path(folder) / 'engagement-actions.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def profile(platform, **extra):
    base = {'account_scope': 'brand', 'name': 'Full Time', 'handle': '@fulltimefm',
            'bio': 'AI Pundit takes on the weekend\'s big matches. Free pilot beta.',
            'link': growth.tracked(growth.SITE + '/', CID[platform]), 'pinned_post': None,
            'avatar_sha256': AVATAR, 'cross_links': [p for p in ('tiktok', 'instagram', 'youtube') if p != platform],
            'ai_disclosure': True, 'image_marks': []}
    base.update(extra)
    return base


def trio():
    return {p: profile(p) for p in ('tiktok', 'instagram', 'youtube')}


def post(channel, ref, hours_ago, **extra):
    return {'channel': channel, 'post_ref': ref, 'published_at': (NOW - dt.timedelta(hours=hours_ago)).isoformat(),
            **extra}


def reading(channel, metric, value, days_ago, source='platform_analytics', **extra):
    return {'channel': channel, 'metric': metric, 'value': value,
            'observed_at': (NOW - dt.timedelta(days=days_ago)).isoformat(), 'source': source, **extra}


class ActionsFileTests(unittest.TestCase):
    def refused(self, data, words, today=NOW):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError) as caught:
                load_actions(write(folder, data), today)
        self.assertIn(words, str(caught.exception))
        return str(caught.exception)

    def test_the_public_file_seeds_every_action_pending_with_no_ruling(self):
        data = load_actions(audience.ACTIONS_FILE, NOW)
        self.assertEqual(set(data['actions']), SEED)
        for aid, entry in data['actions'].items():
            with self.subTest(action=aid):
                self.assertEqual(entry['status'], 'pending')
                self.assertEqual(entry['ruling'], {'date': '', 'words': ''})
                self.assertEqual(entry['rule_checked_on'], '')

    def test_every_code_ban_is_in_the_file_and_none_is_an_action(self):
        data = registry()
        self.assertTrue(set(audience.BANNED) <= set(data['banned']))
        self.assertFalse(set(data['banned']) & set(data['actions']))

    def test_official_api_is_named_only_where_one_supports_the_action(self):
        data = registry()['actions']
        for aid in ('pin_best_comment_on_own_post', 'rotate_pinned_post', 'crosslink_profiles'):
            self.assertIsNone(data[aid]['official_api'])
        self.assertIn('YouTube Data API', data['reply_to_comments_on_own_posts']['official_api'])
        self.assertIn('Instagram Graph API', data['reply_to_comments_on_own_posts']['official_api'])
        self.assertNotIn('x', data['reply_to_comments_on_own_posts']['platforms'])
        self.assertEqual(data['schedule_story_or_community_post']['daily_cap'], 0)

    def test_unknown_fields_are_refused(self):
        data = registry()
        data['extra'] = 1
        self.refused(data, 'unknown registry fields: extra')
        data = registry()
        data['actions']['rotate_pinned_post']['autopilot'] = True
        self.refused(data, 'unknown fields: autopilot')
        data = registry()
        data['actions']['rotate_pinned_post']['ruling'] = {'date': '', 'words': '', 'by': 'x'}
        self.refused(data, 'exactly date and words')

    def test_approved_needs_rulings_date_and_words(self):
        data = registry()
        data['actions']['reply_to_comments_on_own_posts'].update(status='approved', rule_checked_on='2026-10-20')
        self.refused(data, 'approved without a ruling')
        data = approve(registry(), 'reply_to_comments_on_own_posts')
        data['actions']['reply_to_comments_on_own_posts']['ruling']['words'] = ' '
        self.refused(data, "Krish's date (YYYY-MM-DD) and his words")

    def test_approved_needs_a_rule_check_within_90_days(self):
        self.refused(approve(registry(), 'reply_to_comments_on_own_posts', checked=''), 'without a dated platform rule')
        self.refused(approve(registry(), 'reply_to_comments_on_own_posts', checked='2026-07-28'),
                     'not within the last 90 days')
        self.refused(approve(registry(), 'reply_to_comments_on_own_posts', checked='2026-11-01'),
                     'not within the last 90 days')
        with tempfile.TemporaryDirectory() as folder:
            data = approve(registry(), 'reply_to_comments_on_own_posts', checked='2026-07-29')
            self.assertEqual(load_actions(write(folder, data), NOW)['actions']['reply_to_comments_on_own_posts']
                             ['status'], 'approved')

    def test_approved_needs_an_official_api(self):
        self.refused(approve(registry(), 'pin_best_comment_on_own_post'), 'no official API supports it')

    def test_a_banned_id_can_never_appear_in_actions(self):
        data = registry()
        data['actions']['automated_follow_or_unfollow'] = copy.deepcopy(data['actions']['rotate_pinned_post'])
        approve(data, 'automated_follow_or_unfollow', official_api='X API v2 follows')
        self.refused(data, 'automated_follow_or_unfollow is banned and can never be listed')

    def test_the_file_cannot_drop_a_code_ban(self):
        data = registry()
        del data['banned']['mass_liking']
        self.refused(data, 'banned must keep every id the code bans: mass_liking')

    def test_a_pending_action_keeps_its_ruling_empty(self):
        data = registry()
        data['actions']['rotate_pinned_post']['ruling'] = {'date': '2026-10-27', 'words': 'yes'}
        self.refused(data, 'is pending, so its ruling stays empty')

    def test_types_are_strict(self):
        for key, value, words in (('daily_cap', True, 'daily_cap'), ('daily_cap', -1, 'daily_cap'),
                                  ('platforms', ['myspace'], 'platforms'), ('platforms', [], 'platforms'),
                                  ('platforms', ['x', 'x'], 'platforms'), ('status', 'live', 'status'),
                                  ('needs_review_each_time', 'yes', 'needs_review_each_time'),
                                  ('rule_checked_on', '27/10/2026', 'rule_checked_on'),
                                  ('official_api', '', 'official_api'), ('rule_source', '', 'rule_source')):
            with self.subTest(key=key, value=value):
                data = registry()
                data['actions']['rotate_pinned_post'][key] = value
                self.refused(data, words)

    def test_a_missing_file_and_invalid_json_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'no action registry could be read'):
                load_actions(Path(folder) / 'none.json', NOW)
            bad = Path(folder) / 'bad.json'
            bad.write_text('{', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'not valid JSON'):
                load_actions(bad, NOW)


class GateTests(unittest.TestCase):
    def refused(self, *args, words, **kwargs):
        with self.assertRaises(ValueError) as caught:
            gate(*args, **kwargs)
        self.assertIn(words, str(caught.exception))
        return str(caught.exception)

    def ready(self):
        return approve(registry(), 'reply_to_comments_on_own_posts')

    def test_an_approved_action_on_its_brand_account_passes(self):
        self.assertIsNone(gate('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                               actions=self.ready(), allowlist=allowlist(), review_ref='cc-decision-1'))
        self.assertIsNone(gate('reply_to_comments_on_own_posts', 'instagram',
                               {'ref': 'fulltime-ig-reels', 'account_scope': 'brand'}, NOW.date(), 19,
                               actions=self.ready(), allowlist=allowlist(), review_ref='cc-decision-2'))

    def test_a_pending_action_is_refused(self):
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                     actions=registry(), allowlist=allowlist(), review_ref='r', words='is pending, not approved')

    def test_the_public_file_is_read_by_default_and_refuses_today(self):
        message = self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                               allowlist=allowlist(), words='is pending')
        self.assertIn('no ruling from Krish', message)
        self.assertIn('no dated platform rule check', message)
        self.assertIn('Krish reviews each one first', message)

    def test_an_action_without_a_ruling_is_refused(self):
        data = registry()
        data['actions']['reply_to_comments_on_own_posts'].update(status='approved', rule_checked_on='2026-10-20')
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data,
                     allowlist=allowlist(), review_ref='r', words='approved without a ruling')

    def test_a_stale_rule_check_is_refused(self):
        data = approve(registry(), 'reply_to_comments_on_own_posts', checked='2026-07-01')
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data,
                     allowlist=allowlist(), review_ref='r', words='rule check of 2026-07-01 is stale')

    def test_an_action_without_an_official_api_is_refused(self):
        message = self.refused('pin_best_comment_on_own_post', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                               actions=registry(), allowlist=allowlist(), review_ref='r',
                               words='has no official API, so it can only be a manual task for Krish')
        self.assertIn('any_action_without_official_api is banned', message)
        self.refused('pin_best_comment_on_own_post', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                     actions=approve(registry(), 'pin_best_comment_on_own_post'), allowlist=allowlist(),
                     review_ref='r', words='no official API supports it')

    def test_a_banned_id_is_refused_even_if_ruled(self):
        for aid in audience.BANNED:
            with self.subTest(action=aid):
                self.refused(aid, 'x', 'fulltime-x', NOW, 0, actions=self.ready(), allowlist=allowlist(),
                             review_ref='r', words=f'{aid} is banned')
        data = self.ready()
        data['actions']['mass_liking'] = copy.deepcopy(data['actions']['reply_to_comments_on_own_posts'])
        self.refused('mass_liking', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data, allowlist=allowlist(),
                     review_ref='r', words='mass_liking is banned')

    def test_a_personal_account_is_always_refused(self):
        for scope in ('personal', None, 'other_product'):
            with self.subTest(scope=scope):
                self.refused('reply_to_comments_on_own_posts', 'youtube',
                             {'ref': 'fulltime-yt-shorts', 'account_scope': scope}, NOW, 0, actions=self.ready(),
                             allowlist=allowlist(), review_ref='r', words='always refused: Full Time brand profiles')
        listed = allowlist()
        listed['channels']['fulltime-yt-shorts']['account_scope'] = 'personal'
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=self.ready(),
                     allowlist=listed, review_ref='r', words='any_personal_account_action is banned')
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'krish-personal', NOW, 0, actions=self.ready(),
                     allowlist=allowlist(), review_ref='r', words='not in the Full Time brand allowlist')

    def test_the_daily_cap_is_enforced(self):
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 20,
                     actions=self.ready(), allowlist=allowlist(), review_ref='r',
                     words='the daily cap is reached: 20 of 20 today')
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, True,
                     actions=self.ready(), allowlist=allowlist(), review_ref='r', words='today_count')

    def test_the_platform_must_be_listed_and_match_the_account(self):
        self.refused('reply_to_comments_on_own_posts', 'tiktok', 'fulltime-tiktok', NOW, 0, actions=self.ready(),
                     allowlist=allowlist(), review_ref='r', words='tiktok is not listed')
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-tiktok', NOW, 0, actions=self.ready(),
                     allowlist=allowlist(), review_ref='r', words='is the tiktok profile, not youtube')
        self.refused('reply_to_comments_on_own_posts', 'linkedin', 'fulltime-tiktok', NOW, 0, actions=self.ready(),
                     allowlist=allowlist(), review_ref='r', words='not a Full Time brand platform')

    def test_review_is_needed_each_time(self):
        self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                     actions=self.ready(), allowlist=allowlist(), words='Krish reviews each one first')
        playlist = approve(registry(), 'add_post_to_playlist_or_highlight')
        self.assertIsNone(gate('add_post_to_playlist_or_highlight', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                               actions=playlist, allowlist=allowlist()))

    def test_publishing_is_never_automated_even_if_ruled(self):
        data = approve(registry(), 'schedule_story_or_community_post', daily_cap=5)
        self.refused('schedule_story_or_community_post', 'instagram', 'fulltime-ig-reels', NOW, 0, actions=data,
                     allowlist=allowlist(), review_ref='r', words='publishing stays with Krish in Buffer')

    def test_an_unknown_action_and_a_missing_allowlist_are_refused(self):
        self.refused('boost_post', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=self.ready(),
                     allowlist=allowlist(), review_ref='r', words='boost_post is not in engagement-actions.json')
        with mock.patch.object(audience, 'ROOT', Path(tempfile.gettempdir()) / 'audience-no-local'):
            self.refused('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                         actions=self.ready(), review_ref='r', words='no Buffer allowlist')

    def test_every_reason_is_given_at_once(self):
        message = self.refused('pin_best_comment_on_own_post', 'x', 'fulltime-yt-shorts', NOW, 9,
                               actions=registry(), allowlist=allowlist(), words='is pending')
        for words in ('no ruling', 'no dated platform rule check', 'no official API', 'x is not listed',
                      'is the youtube profile', 'daily cap is reached', 'Krish reviews each one'):
            self.assertIn(words, message)


class ChecklistTests(unittest.TestCase):
    def checks(self, platform, **extra):
        profiles = trio()
        profiles[platform] = profile(platform, **extra)
        return [f['check'] for f in profile_checklist(platform, profiles[platform], profiles, now=NOW)]

    def test_a_findable_profile_needs_no_fix(self):
        profiles = trio()
        for platform, value in profiles.items():
            with self.subTest(platform=platform):
                self.assertEqual(profile_checklist(platform, value, profiles, now=NOW), [])

    def test_a_handle_that_does_not_exist_yet_is_a_create_fix(self):
        fixes = profile_checklist('threads', None)
        self.assertEqual([f['check'] for f in fixes], ['create'])
        self.assertIn('Create the Full Time Threads handle', fixes[0]['fix'])

    def test_each_check_finds_its_fix(self):
        long = 'AI Pundit ' + 'takes ' * 20
        cases = [
            ({'name': 'Fulltime FM'}, 'name'),
            ({'bio': 'Football takes, every weekend, by AI.'}, 'bio'),
            ({'bio': 'Big ai pundit takes.'}, 'bio'),
            ({'bio': long}, 'bio'),
            ({'bio': 'AI Pundit takes \u2014 every match.'}, 'bio'),
            ({'link': growth.SITE + '/'}, 'link'),
            ({'link': growth.tracked(growth.SITE + '/', CID['instagram'])}, 'link'),
            ({'link': 'https://fulltime.example/?utm_content=' + CID['tiktok']}, 'link'),
            ({'link': None}, 'link'),
            ({'handle': '@fulltime_pods'}, 'handle'),
            ({'handle': ''}, 'handle'),
            ({'avatar_sha256': 'b' * 64}, 'avatar'),
            ({'avatar_sha256': None}, 'avatar'),
            ({'cross_links': ['instagram']}, 'cross_links'),
            ({'bio': 'Pundit takes on every match.', 'ai_disclosure': False}, 'ai_disclosure'),
            ({'bio': 'AI Pundit takes, better than Match of the Day.'}, 'marks'),
            ({'name': 'Full Time Premier League'}, 'marks'),
            ({'image_marks': ['league lion in the banner']}, 'marks'),
        ]
        for extra, check in cases:
            with self.subTest(extra=extra):
                self.assertIn(check, self.checks('tiktok', **extra))

    def test_the_pinned_post_is_the_best_of_the_last_14_days(self):
        performance = [post('tiktok', 'tt-old-hit', 24 * 20, follows=900),
                       post('tiktok', 'tt-best', 30, follows=40, shares=10),
                       post('tiktok', 'tt-views', 5, follows=12, views=90000)]
        profiles = trio()
        fixes = profile_checklist('tiktok', profiles['tiktok'], profiles, performance, now=NOW)
        self.assertEqual([f['fix'] for f in fixes if f['check'] == 'pinned_post'],
                         ['Pin tt-best on TikTok: the best post of the last 14 days'])
        profiles['tiktok']['pinned_post'] = 'tt-best'
        self.assertEqual(profile_checklist('tiktok', profiles['tiktok'], profiles, performance, now=NOW), [])
        self.assertEqual(profile_checklist('youtube', profiles['youtube'], profiles, performance, now=NOW), [])

    def test_rule_fixes_come_first_then_most_points(self):
        profiles = trio()
        profiles['tiktok'] = profile('tiktok', name='Fulltime', bio='Pundit takes. Sky Sports style.',
                                     ai_disclosure=False, cross_links=[])
        fixes = profile_checklist('tiktok', profiles['tiktok'], profiles, now=NOW)
        self.assertEqual([f['check'] for f in fixes], ['marks', 'ai_disclosure', 'name', 'bio', 'cross_links'])
        self.assertTrue(all(f['must'] for f in fixes[:2]))
        self.assertTrue(all(set(f) == {'check', 'fix', 'points', 'minutes', 'must', 'action_id'} for f in fixes))

    def test_an_untrackable_channel_says_so(self):
        try:
            growth.tracked(growth.SITE + '/', 'TH_TRIBE_POST_C01_H01_V1_20261101')
        except (ValueError, KeyError):
            fixes = profile_checklist('threads', profile('tiktok', link=None), now=NOW)
            self.assertIn('growth.py has no TH creative ID code yet', ' '.join(f['fix'] for f in fixes))
        else:
            self.skipTest('growth.py tracks Threads creative IDs now')

    def test_a_personal_or_malformed_profile_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'personal accounts are never audited'):
            profile_checklist('tiktok', profile('tiktok', account_scope='personal'))
        with self.assertRaisesRegex(ValueError, 'unknown fields: followers_bought'):
            profile_checklist('tiktok', profile('tiktok', followers_bought=0))
        with self.assertRaisesRegex(ValueError, 'channel must be one of'):
            profile_checklist('linkedin', profile('tiktok'))
        with self.assertRaisesRegex(ValueError, 'avatar_sha256'):
            profile_checklist('tiktok', profile('tiktok', avatar_sha256='nope'))


class PlanTests(unittest.TestCase):
    def busy(self):
        profiles = trio()
        profiles['tiktok'] = profile('tiktok', name='Fulltime', cross_links=[])
        performance = [post('tiktok', 'tt-1', 0.5, follows=30, comments=12, comments_waiting=11),
                       post('instagram', 'ig-1', 20, follows=8, comments_waiting=3, comments=4),
                       post('youtube', 'yt-1', 40, views=500, in_playlist=False, comments=2)]
        trends = [{'platform': 'tiktok', 'kind': 'sound', 'name': 'Terrace drums', 'commercial_ok': True,
                   'observed_at': (NOW - dt.timedelta(hours=5)).isoformat(), 'source': 'tiktok_creative_center'},
                  {'platform': 'tiktok', 'kind': 'hashtag', 'name': '#matchday',
                   'observed_at': (NOW - dt.timedelta(hours=3)).isoformat(), 'source': 'tiktok_creative_center'},
                  {'platform': 'tiktok', 'kind': 'hashtag', 'name': '#football',
                   'observed_at': (NOW - dt.timedelta(hours=4)).isoformat(), 'source': 'tiktok_creative_center'}]
        return profiles, performance, trends

    def test_the_plan_stays_within_budget_ordered_by_expected_gain(self):
        profiles, performance, trends = self.busy()
        for budget in (0, 3, 10, 25, 60):
            with self.subTest(budget=budget):
                plan = daily_plan(profiles, performance, trends, budget, actions=registry(), now=NOW)
                self.assertLessEqual(sum(i['minutes'] for i in plan), budget)
                self.assertEqual([i['rank'] for i in plan], list(range(1, len(plan) + 1)))
                rest = [i['expected_gain'] for i in plan if not i['must']]
                self.assertEqual(rest, sorted(rest, reverse=True))
        plan = daily_plan(profiles, performance, trends, 10, actions=registry(), now=NOW)
        self.assertEqual(plan[0]['tactic'], 'create_profile')
        self.assertTrue(all(i['who'] == 'krish' and i['gain_basis'] == 'prior' for i in plan))

    def test_every_tactic_is_covered_when_time_allows(self):
        profiles, performance, trends = self.busy()
        plan = daily_plan(profiles, performance, trends, 500, actions=registry(), now=NOW)
        tactics = {i['tactic'] for i in plan}
        self.assertEqual(tactics, {'create_profile', 'profile_fix', 'first_hour_replies', 'replies', 'pin_comment',
                                   'playlist', 'cross_promotion', 'trend_sound', 'trend_hashtags', 'collab_prompt',
                                   'community', 'product_brief'})
        first = next(i for i in plan if i['tactic'] == 'first_hour_replies')
        later = next(i for i in plan if i['tactic'] == 'replies')
        self.assertLess(first['rank'], later['rank'])
        self.assertIn('inside its first hour', first['what'])
        collab = next(i for i in plan if i['tactic'] == 'collab_prompt')['what']
        for words in ('an ask only', 'never a DM', 'a cold pitch', 'a payment'):
            self.assertIn(words, collab)
        community = next(i for i in plan if i['tactic'] == 'community')['what']
        self.assertIn('read and log its written rules first', community)
        brief = next(i for i in plan if i['tactic'] == 'product_brief')['what']
        self.assertIn('never built here', brief)
        for item in plan:
            self.assertEqual(set(item), {'rank', 'tactic', 'platform', 'what', 'who', 'action_id', 'minutes',
                                         'expected_gain', 'gain_basis', 'must'})

    def test_creating_the_push_three_comes_first(self):
        plan = daily_plan({}, [], [], 15, actions=registry(), now=NOW)
        self.assertEqual([i['platform'] for i in plan], ['youtube', 'tiktok', 'instagram'])

    def test_trends_follow_the_platform_rules(self):
        profiles, performance, _ = self.busy()
        old = (NOW - dt.timedelta(days=5)).isoformat()
        fresh = (NOW - dt.timedelta(hours=1)).isoformat()
        trends = [{'platform': 'tiktok', 'kind': 'sound', 'name': 'Chart hit', 'commercial_ok': False,
                   'observed_at': fresh, 'source': 'manual'},
                  {'platform': 'instagram', 'kind': 'hashtag', 'name': '#onlyone', 'observed_at': fresh,
                   'source': 'manual'},
                  {'platform': 'youtube', 'kind': 'hashtag', 'name': '#stale', 'observed_at': old, 'source': 'manual'},
                  {'platform': 'youtube', 'kind': 'hashtag', 'name': '#motd', 'observed_at': fresh,
                   'source': 'manual'},
                  {'platform': 'youtube', 'kind': 'hashtag', 'name': '#goals', 'observed_at': fresh,
                   'source': 'manual'},
                  {'platform': 'threads', 'kind': 'hashtag', 'name': '#a', 'observed_at': fresh, 'source': 'manual'},
                  {'platform': 'threads', 'kind': 'hashtag', 'name': '#b', 'observed_at': fresh, 'source': 'manual'}]
        trends += [{'platform': 'tiktok', 'kind': 'hashtag', 'name': f'#tag{n}', 'source': 'manual',
                    'observed_at': (NOW - dt.timedelta(minutes=n)).isoformat()} for n in range(7)]
        plan = daily_plan(profiles, performance, trends, 500, actions=registry(), now=NOW)
        self.assertNotIn('trend_sound', {i['tactic'] for i in plan})
        tags = [i for i in plan if i['tactic'] == 'trend_hashtags']
        self.assertEqual([i['platform'] for i in tags], ['tiktok'])
        self.assertTrue(tags[0]['what'].endswith('#tag0 #tag1 #tag2 #tag3 #tag4'))
        with self.assertRaisesRegex(ValueError, 'commercial_ok'):
            daily_plan(profiles, [], [{'platform': 'tiktok', 'kind': 'sound', 'name': 'x', 'observed_at': fresh,
                                       'source': 'manual'}], actions=registry(), now=NOW)

    def test_an_approved_action_becomes_automated_inside_its_gate(self):
        profiles, performance, trends = self.busy()
        performance.append(post('youtube', 'yt-2', 0.2, comments_waiting=6))
        data = approve(approve(registry(), 'reply_to_comments_on_own_posts'), 'add_post_to_playlist_or_highlight')
        plan = daily_plan(profiles, performance, trends, 500, actions=data, allowlist=allowlist(), now=NOW)
        youtube = next(i for i in plan if i['tactic'] == 'first_hour_replies' and i['platform'] == 'youtube')
        self.assertEqual((youtube['who'], youtube['minutes']), ('automated', 1))
        self.assertIn('after Krish reviews it', youtube['what'])
        tiktok = next(i for i in plan if i['tactic'] == 'first_hour_replies' and i['platform'] == 'tiktok')
        self.assertEqual(tiktok['who'], 'krish')
        zero = daily_plan(profiles, performance, trends, 0, actions=data, allowlist=allowlist(), now=NOW)
        self.assertEqual([(i['tactic'], i['who'], i['minutes']) for i in zero], [('playlist', 'automated', 0)])
        capped = daily_plan(profiles, performance, trends, 500, actions=data, allowlist=allowlist(),
                            counts={'reply_to_comments_on_own_posts': 20}, now=NOW)
        self.assertTrue(all(i['who'] == 'krish' for i in capped if i['action_id'] == 'reply_to_comments_on_own_posts'))
        unlisted = daily_plan(profiles, performance, trends, 500, actions=data, now=NOW)
        self.assertTrue(all(i['who'] == 'krish' for i in unlisted))

    def test_the_product_brief_drops_once_sent(self):
        profiles, performance, trends = self.busy()
        plan = daily_plan(profiles, performance, trends, 500, actions=registry(), product_brief_sent=True, now=NOW)
        self.assertNotIn('product_brief', {i['tactic'] for i in plan})

    def test_bad_inputs_are_refused(self):
        for budget in (-1, '10', True):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, 'budget_minutes'):
                daily_plan({}, [], [], budget, actions=registry(), now=NOW)
        with self.assertRaisesRegex(ValueError, 'profiles must map brand platforms'):
            daily_plan({'linkedin': profile('tiktok')}, [], [], actions=registry(), now=NOW)
        with self.assertRaisesRegex(ValueError, 'null is missing, not zero'):
            daily_plan({}, [post('tiktok', 'p', 1, follows=-3)], [], actions=registry(), now=NOW)
        stale = approve(registry(), 'reply_to_comments_on_own_posts', checked='2026-06-01')
        with self.assertRaisesRegex(ValueError, 'not within the last 90 days'):
            daily_plan({}, [], [], actions=stale, now=NOW)


class FollowersTests(unittest.TestCase):
    def test_missing_is_never_zero(self):
        result = followers_check([], now=NOW)
        self.assertEqual([r['channel'] for r in result], list(audience.PLATFORMS))
        for row in result:
            for metric in audience.METRICS:
                self.assertEqual((row[metric]['status'], row[metric]['change']), ('missing', None))
                self.assertEqual(row[metric]['reason'], 'no reading')

    def test_a_measured_zero_is_measured(self):
        result = followers_check([reading('tiktok', 'followers', 0, 8), reading('tiktok', 'followers', 0, 1)], now=NOW)
        tiktok = result[1]['followers']
        self.assertEqual((tiktok['status'], tiktok['change'], tiktok['reason']), ('measured', 0, None))
        self.assertEqual(result[0]['followers']['status'], 'missing')

    def test_the_change_is_the_latest_against_a_week_before(self):
        readings = [reading('instagram', 'followers', 100, 9), reading('instagram', 'followers', 110, 7.5),
                    reading('instagram', 'followers', 140, 0.5, source='manual_entry', ref='insights screenshot 1'),
                    reading('instagram', 'profile_visits', 40, 7), reading('instagram', 'profile_visits', 55, 0)]
        row = followers_check(readings, now=NOW)[2]
        self.assertEqual((row['followers']['change'], row['followers']['week_before']), (30, 110))
        self.assertEqual(row['followers']['sources'], ['manual_entry', 'platform_analytics'])
        self.assertEqual((row['profile_visits']['change'], row['profile_visits']['latest']), (15, 55))

    def test_stale_and_missing_baselines_are_named(self):
        stale = followers_check([reading('x', 'followers', 50, 12), reading('x', 'followers', 58, 5)], now=NOW)[4]
        self.assertEqual((stale['followers']['status'], stale['followers']['change']), ('stale', 8))
        self.assertEqual(stale['followers']['reason'], 'the latest reading is 5 days old')
        gap = followers_check([reading('x', 'followers', 50, 3), reading('x', 'followers', 58, 0)], now=NOW)[4]
        self.assertEqual((gap['followers']['status'], gap['followers']['change'], gap['followers']['latest']),
                         ('missing', None, 58))
        self.assertEqual(gap['followers']['reason'], 'no reading about a week before the latest')

    def test_readings_are_validated(self):
        good = reading('tiktok', 'followers', 5, 1)
        cases = [({k: v for k, v in good.items() if k != 'source'}, 'a reading needs source'),
                 ({k: v for k, v in good.items() if k != 'observed_at'}, 'a reading needs observed_at'),
                 (dict(good, value=None), 'leave a missing reading out'),
                 (dict(good, value=2.5), 'whole number'),
                 (dict(good, channel='linkedin'), 'channel must be one of'),
                 (dict(good, metric='likes'), 'metric must be one of'),
                 (dict(good, source='a scraper'), 'source must be one of'),
                 (dict(good, account_scope='personal'), 'personal accounts are never read'),
                 (dict(good, observed_at='2026-10-26'), 'with its offset'),
                 (dict(good, observed_at=(NOW + dt.timedelta(hours=1)).isoformat()), 'in the future'),
                 (dict(good, handle='@someone'), 'unknown reading fields: handle')]
        for value, words in cases:
            with self.subTest(words=words), self.assertRaisesRegex(ValueError, words):
                followers_check([value], now=NOW)
        with self.assertRaisesRegex(ValueError, 'disagree'):
            followers_check([good, dict(good, value=6)], now=NOW)
        self.assertEqual(followers_check([good, dict(good)], now=NOW)[1]['followers']['latest'], 5)

    def test_the_north_star_is_unchanged(self):
        for text in (audience.__doc__, followers_check.__doc__):
            self.assertIn('North Star', text)
            self.assertIn('unchanged', text)
            self.assertIn('diagnostic of distribution capacity', text)


class SafetyTests(unittest.TestCase):
    def test_the_module_never_names_the_network(self):
        source = Path(audience.__file__).read_text(encoding='utf-8').lower()
        for word in ('http', 'urllib', 'requests', 'socket', 'subprocess'):
            with self.subTest(word=word):
                self.assertNotIn(word, source)

    def test_no_function_opens_a_connection(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError('the Audience Builder opened a network connection')
        profiles = trio()
        data = approve(registry(), 'reply_to_comments_on_own_posts')
        with mock.patch.object(socket, 'socket', refuse), mock.patch.object(socket, 'create_connection', refuse), \
                mock.patch.object(socket, 'getaddrinfo', refuse):
            load_actions(audience.ACTIONS_FILE, NOW)
            gate('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data,
                 allowlist=allowlist(), review_ref='r')
            profile_checklist('tiktok', profiles['tiktok'], profiles, now=NOW)
            daily_plan(profiles, [post('youtube', 'yt-1', 0.2, comments_waiting=3)], [], 30, actions=data,
                       allowlist=allowlist(), now=NOW)
            followers_check([reading('tiktok', 'followers', 3, 1)], now=NOW)

    def test_a_credential_is_never_repeated(self):
        data = approve(registry(), 'reply_to_comments_on_own_posts')
        calls = [
            lambda: gate(SECRET, 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data, allowlist=allowlist()),
            lambda: gate('reply_to_comments_on_own_posts', SECRET, 'fulltime-yt-shorts', NOW, 0, actions=data,
                         allowlist=allowlist(), review_ref='r'),
            lambda: gate('reply_to_comments_on_own_posts', 'youtube', SECRET, NOW, 0, actions=data,
                         allowlist=allowlist(), review_ref='r'),
            lambda: gate('reply_to_comments_on_own_posts', 'youtube', {'ref': SECRET, 'account_scope': 'brand'}, NOW,
                         0, actions=data, allowlist=allowlist(), review_ref='r'),
            lambda: gate('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data,
                         allowlist=allowlist(), review_ref='Bearer ' + SECRET),
            lambda: gate('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0,
                         actions=dict(data, **{SECRET: 1}), allowlist=allowlist(), review_ref='r'),
            lambda: profile_checklist('tiktok', profile('tiktok', link=growth.SITE + '/?token=' + SECRET)),
            lambda: profile_checklist('tiktok', profile('tiktok', **{SECRET: 1})),
            lambda: daily_plan({}, [post('tiktok', SECRET, 1)], [], actions=data, now=NOW),
            lambda: daily_plan({}, [], [{'platform': 'tiktok', 'kind': 'hashtag', 'name': '#a', 'source': SECRET,
                                         'observed_at': NOW.isoformat()}], actions=data, now=NOW),
            lambda: followers_check([reading('tiktok', 'followers', 3, 1, ref=SECRET)], now=NOW),
            lambda: followers_check([dict(reading('tiktok', 'followers', 3, 1), **{SECRET: 1})], now=NOW),
        ]
        listed = allowlist()
        listed['channels'][LOWER] = dict(listed['channels']['fulltime-tiktok'])
        lower_id = registry()
        lower_id['actions'][LOWER] = copy.deepcopy(lower_id['actions']['rotate_pinned_post'])
        calls += [
            lambda: gate(LOWER, 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=data, allowlist=allowlist()),
            lambda: gate('reply_to_comments_on_own_posts', 'youtube', LOWER, NOW, 0, actions=data, allowlist=listed,
                         review_ref='r'),
            lambda: gate('reply_to_comments_on_own_posts', 'youtube', 'fulltime-yt-shorts', NOW, 0, actions=lower_id,
                         allowlist=allowlist(), review_ref='r'),
        ]
        for n, call in enumerate(calls):
            with self.subTest(call=n):
                with self.assertRaises(ValueError) as caught:
                    call()
                for leaked in (SECRET, SECRET[4:], LOWER, LOWER[4:]):
                    self.assertNotIn(leaked, str(caught.exception))
        with tempfile.TemporaryDirectory() as folder:
            leaked = registry()
            leaked['actions']['rotate_pinned_post']['rule_source'] = 'see Bearer ' + SECRET
            with self.assertRaises(ValueError) as caught:
                load_actions(write(folder, leaked), NOW)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_inputs_are_not_changed(self):
        profiles = trio()
        performance = [post('tiktok', 'tt-1', 0.5, follows=3, comments_waiting=2)]
        readings = [reading('tiktok', 'followers', 3, 8), reading('tiktok', 'followers', 5, 1)]
        data, listed = registry(), allowlist()
        before = copy.deepcopy((profiles, performance, readings, data, listed))
        daily_plan(profiles, performance, [], 30, actions=data, allowlist=listed, now=NOW)
        profile_checklist('tiktok', profiles['tiktok'], profiles, performance, now=NOW)
        followers_check(readings, now=NOW)
        self.assertEqual((profiles, performance, readings, data, listed), before)

    def test_the_public_files_are_plain_uk_english_within_size(self):
        card = ROOT / 'crew' / 'audience_builder' / 'card.md'
        lens = ROOT / 'crew' / 'audience_builder' / 'lens.md'
        self.assertLessEqual(len(card.read_bytes()), 3072)
        self.assertLessEqual(len(lens.read_bytes()), 1024)
        self.assertIn('Would a fan who lands on this profile follow it within three seconds, and why?',
                      lens.read_text(encoding='utf-8'))
        for path in (card, lens, audience.ACTIONS_FILE, Path(audience.__file__), Path(__file__)):
            with self.subTest(path=path.name):
                self.assertNotIn('\u2014', path.read_text(encoding='utf-8'))
        for path in (card, lens, audience.ACTIONS_FILE, Path(audience.__file__)):
            with self.subTest(path=path.name):
                text = path.read_text(encoding='utf-8').lower()
                for us in ('organiz', 'recogniz', 'behavior', 'color', 'favorite', 'center '):
                    self.assertNotIn(us, text)

    def test_the_public_surface(self):
        names = sorted(n for n in dir(audience) if not n.startswith('_') and callable(getattr(audience, n))
                       and getattr(getattr(audience, n), '__module__', '') == 'engine.audience')
        self.assertEqual(names, ['actions_errors', 'daily_plan', 'followers_check', 'gate', 'load_actions',
                                 'profile_checklist', 'refusals'])


if __name__ == '__main__':
    unittest.main()
