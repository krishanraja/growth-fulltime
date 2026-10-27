import copy
import json
import unittest
from unittest import mock

import growth
from engine import formats, reporting
from engine.pack import build, check, proposal, review_urls

RUN = 'fulltime:2026-11-01:g2'
DAY = '2026-11-01'
SHA_A, SHA_B, SHA_C = 'a' * 64, 'b' * 64, 'c' * 64


def state(rail=None):
    full = {'drop': 'drop-full', 'date': '2026-10-31', 'home': 'Rovers', 'away': 'United', 'score': [2, 1],
            'pundits': ['zen', 'gaffer', 'stats', 'doomer'], 'fill': 4}
    thin = {'drop': 'drop-thin', 'date': '2026-10-31', 'home': 'City', 'away': 'Athletic', 'score': [0, 0],
            'pundits': ['zen'], 'fill': 1}
    return {'rail': [full, thin] if rail is None else rail}


def entry(identifier, service, channel, scope='brand'):
    return {'buffer_channel_id': identifier, 'service': service, 'channel': channel,
            'account_scope': scope, 'identity_ref': 'fulltime-' + service}


def allowlist():
    return {'product': 'fulltime', 'channels': {
        'fulltime-tiktok': entry('000000000000000000000001', 'tiktok', 'tiktok'),
        'fulltime-ig-reels': entry('000000000000000000000002', 'instagram', 'ig_reels'),
        'fulltime-ig-feed': entry('000000000000000000000002', 'instagram', 'ig_feed'),
        'fulltime-yt-shorts': entry('000000000000000000000003', 'youtube', 'yt_shorts'),
        'fulltime-x': entry('000000000000000000000005', 'twitter', 'x'),
        'personal-tiktok': entry('999999999999999999999999', 'tiktok', 'tiktok', scope='personal')}}


def review(**over):
    return {'rubric_total': 40, 'ethics': 4, 'action': 4,
            'alternatives': ['A colder open on the scoreline', 'The Gaffer reading the same moment'],
            'doctrine_ref': 'COPY.md, rubric', 'why_wins': 'The line a fan would send to one mate.', **over}


def media(sha=SHA_A, kind='video', url='https://review.example.com/2026-11-01/take-01'):
    return {'kind': kind, 'sha256': sha, 'bytes': 1048576, 'review_url': url}


def take(**over):
    """A take clip on TikTok, linking to The Doomer's published show for drop-full."""
    cid = over.pop('creative_id', 'TT_CLASH_CLIP_C01_H01_V1_20261101')
    drop, pundit = over.pop('drop_id', 'drop-full'), over.pop('pundit', 'doomer')
    item = {'creative_id': cid, 'master_id': 'M_20261101_ROVERS_UNITED_DOOMER', 'format_id': 'take_clip',
            'channel': 'tiktok', 'channel_ref': 'fulltime-tiktok',
            'caption': 'The Doomer has seen this before. Hear the whole take from the AI Pundit.',
            'hashtags': ['#Football', '#AIPundit'],
            'link': growth.tracked(f'https://fulltime.fm/?drop={drop}&pundit={pundit}', cid),
            'drop_id': drop, 'pundit': pundit, 'whole_match': False, 'media': [media()],
            'ai_label': {'platform_label_set': True, 'visible_ai_pundit': True},
            'scheduled_suggestion': '2026-11-01T18:30:00+00:00', 'review': review()}
    item.update(over)
    return item


def reel(**over):
    cid = over.pop('creative_id', 'IG_CLASH_SHORT_C01_H01_V1_20261101')
    return take(creative_id=cid, channel='ig_reels', channel_ref='fulltime-ig-reels',
                media=[media(SHA_B, url='https://review.example.com/2026-11-01/take-01-reels')], **over)


def ad(**over):
    """A match ad on TikTok, linking to Today."""
    cid = over.pop('creative_id', 'TT_CLASH_VIDEO_C02_H01_V1_20261101')
    item = {'creative_id': cid, 'master_id': 'M_20261101_REMOTE_AD', 'format_id': 'match_ad',
            'channel': 'tiktok', 'channel_ref': 'fulltime-tiktok',
            'caption': 'Two AI Pundits, one remote, and a sofa that will not agree. Pick your AI Pundit.',
            'hashtags': ['#Football', '#MatchDay'], 'link': growth.tracked('https://fulltime.fm/', cid),
            'whole_match': False, 'media': [media(SHA_C, url='https://review.example.com/2026-11-01/ad-01')],
            'ai_label': {'platform_label_set': True, 'visible_ai_pundit': True},
            'scheduled_suggestion': '2026-11-01T11:00:00+00:00', 'review': review()}
    item.update(over)
    return item


def pack_of(*items):
    return {'run_id': RUN, 'matchday': DAY, 'items': list(items)}


def errors(*items, st=None, allow=None, live=False):
    return check(pack_of(*items), state() if st is None else st, allow or allowlist(), live)


def has(found, text):
    return any(text in e for e in found)


class PackShapeTests(unittest.TestCase):
    def test_a_clean_take_builds_with_whole_match_explicit(self):
        item = take()
        del item['whole_match']
        built = build([item], RUN, DAY, state(), allowlist(), False)
        self.assertIs(built['items'][0]['whole_match'], False)
        self.assertEqual(check(built, state(), allowlist(), False), [])
        self.assertNotIn('whole_match', item)

    def test_build_refuses_with_every_error(self):
        with self.assertRaises(ValueError) as caught:
            build([take(caption='No label here.', hashtags=['#One'])], RUN, DAY, state(), allowlist(), False)
        self.assertIn('AI Pundit', str(caught.exception))
        self.assertIn('2 to 5', str(caught.exception))

    def test_unknown_fields_refused_at_every_level(self):
        self.assertTrue(has(check({**pack_of(take()), 'post_now': True}, state(), allowlist(), False),
                            'unknown pack fields: post_now'))
        self.assertTrue(has(errors(take(publish=True)), 'unknown fields: publish'))
        self.assertTrue(has(errors(take(media=[{**media(), 'url': 'https://x.example.com'}])), 'media 1 must have exactly'))
        self.assertTrue(has(errors(take(review={**review(), 'score': 1})), 'review must have exactly'))
        self.assertTrue(has(errors(take(ai_label={'platform_label_set': True, 'visible_ai_pundit': True, 'x': 1})),
                            'ai_label'))

    def test_required_fields_and_pack_header(self):
        item = take()
        del item['review']
        self.assertTrue(has(errors(item), 'missing fields: review'))
        self.assertTrue(has(check({**pack_of(take()), 'matchday': '2026-02-30'}, state(), allowlist(), False),
                            'matchday'))
        self.assertTrue(has(check({**pack_of(take()), 'run_id': 'bad id'}, state(), allowlist(), False), 'run_id'))
        self.assertTrue(has(check(pack_of(), state(), allowlist(), False), 'non-empty list'))

    def test_creative_id_follows_the_pattern_and_the_channel_prefix(self):
        self.assertTrue(has(errors({**take(), 'creative_id': 'TT_CLIP_1'}), 'does not follow'))
        wrong = take(creative_id='IG_CLASH_CLIP_C01_H01_V1_20261101')
        self.assertTrue(has(errors(wrong), 'creative_id starts IG, but tiktok takes TT'))
        self.assertTrue(has(errors(take(channel='myspace')), "channel 'myspace' is not one of"))

    def test_creative_id_never_repeats_and_a_master_once_per_channel(self):
        self.assertTrue(has(errors(take(), take(media=[media(SHA_B)])), 'appears twice in the pack'))
        second = take(creative_id='TT_CLASH_CLIP_C01_H01_V2_20261101', media=[media(SHA_B)])
        self.assertTrue(has(errors(take(), second), 'master M_20261101_ROVERS_UNITED_DOOMER appears twice on tiktok'))
        self.assertEqual(errors(take(), reel()), [])

    def test_the_same_asset_never_goes_twice_on_one_channel(self):
        second = take(creative_id='TT_CLASH_CLIP_C01_H01_V2_20261101', master_id='M_OTHER')
        self.assertTrue(has(errors(take(), second), 'the same asset'))


class ChannelRefTests(unittest.TestCase):
    def test_ref_must_be_an_allowlisted_brand_entry_for_the_same_channel(self):
        self.assertTrue(has(errors(take(channel_ref='fulltime-unknown')), 'is not in the Full Time Buffer allowlist'))
        self.assertTrue(has(errors(take(channel_ref='000000000000000000000001')), 'raw platform ID'))
        self.assertTrue(has(errors(take(channel_ref='personal-tiktok')), 'is not a Full Time brand channel'))
        self.assertTrue(has(errors(take(channel_ref='fulltime-yt-shorts')), 'is the yt_shorts channel, not tiktok'))

    def test_allowlist_must_be_full_time(self):
        other = {**allowlist(), 'product': 'makeyourmindup'}
        self.assertTrue(has(errors(take(), allow=other), 'product "fulltime"'))


class CopyTests(unittest.TestCase):
    def test_hashtags_two_to_five_each_starting_hash(self):
        self.assertTrue(has(errors(take(hashtags=['#One'])), '2 to 5'))
        self.assertTrue(has(errors(take(hashtags=[f'#Tag{i}' for i in range(6)])), '2 to 5'))
        self.assertTrue(has(errors(take(hashtags=['#Football', 'AIPundit'])), 'starting "#"'))
        self.assertTrue(has(errors(take(hashtags=['#Football', '#football'])), 'listed twice'))
        self.assertEqual(errors(take(hashtags=['#A', '#B', '#C', '#D', '#E'])), [])

    def test_caption_must_say_ai_pundit_exactly(self):
        self.assertTrue(has(errors(take(caption='The Doomer has seen this before.')), '"AI Pundit", exactly'))
        lower = errors(take(caption='The Doomer, our ai pundit, has seen this before.'))
        self.assertTrue(has(lower, '"AI Pundit", exactly'))

    def test_growth_copy_rules_apply_to_the_caption_and_hashtags(self):
        self.assertTrue(has(errors(take(caption='The AI Pundit \u2014 back again.')), 'em dash'))
        self.assertTrue(has(errors(take(caption='The AI Pundit has the acca sorted.')), 'betting language'))
        self.assertTrue(has(errors(take(caption='The AI Pundit is a game-changer.')), 'marketing filler'))
        self.assertTrue(has(errors(take(hashtags=['#Football', '#BetOnIt', '#bookies'])), 'betting language'))
        score = errors(take(caption='Rovers 3-1 United. The AI Pundit saw it coming.'))
        self.assertTrue(has(score, 'is not the result of the match'))
        self.assertEqual(errors(take(caption='Rovers 2-1 United. The AI Pundit has seen this before.')), [])

    def test_caption_carries_no_link_and_no_hashtags(self):
        self.assertTrue(has(errors(take(caption='The AI Pundit at https://fulltime.fm/')), 'carries no link'))
        self.assertTrue(has(errors(take(caption='The AI Pundit, on fulltime.fm today.')), 'carries no link'))
        self.assertTrue(has(errors(take(caption='The AI Pundit #Football')), 'not the caption'))

    def test_a_channel_growth_does_not_list_still_gets_copy_rules(self):
        from engine.pack import _copy_errors
        item = take(channel='threads', caption='The AI Pundit \u2014 a game-changer.')
        found = _copy_errors(item, state())
        self.assertTrue(has(found, 'em dash'))
        self.assertTrue(has(found, 'marketing filler'))
        self.assertFalse(has(found, 'platform "threads"'))


class LinkTests(unittest.TestCase):
    def test_link_must_be_tracked_as_its_creative_id(self):
        cid = 'TT_CLASH_CLIP_C01_H01_V1_20261101'
        self.assertTrue(has(errors(take(link='https://fulltime.fm/?drop=drop-full&pundit=doomer')), 'not tracked'))
        other = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', 'TT_CLASH_CLIP_C09_H01_V1_20261101')
        self.assertTrue(has(errors(take(link=other)), f'not tracked as {cid}'))
        self.assertTrue(has(errors(take(link=growth.tracked('https://example.com/?drop=drop-full&pundit=doomer', cid))),
                            'https fulltime.fm link'))
        self.assertTrue(has(errors(take(link=growth.tracked('http://fulltime.fm/?drop=drop-full&pundit=doomer', cid))),
                            'https fulltime.fm link'))

    def test_link_must_open_the_items_own_drop_and_pundit(self):
        cid = 'TT_CLASH_CLIP_C01_H01_V1_20261101'
        elsewhere = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=zen', cid)
        self.assertTrue(has(errors(take(link=elsewhere)), 'the link must open drop drop-full with The Doomer'))


class PerTakeGateTests(unittest.TestCase):
    def test_a_take_on_a_thin_match_passes_when_its_own_show_is_published(self):
        # Ruling 1: the 4-of-6 rule applies only to a whole-match claim.
        self.assertEqual(errors(take(drop_id='drop-thin', pundit='zen')), [])

    def test_the_exact_show_must_be_published_on_the_rail(self):
        self.assertTrue(has(errors(take(drop_id='drop-gone', pundit='zen')), 'has no published show on the rail'))
        self.assertTrue(has(errors(take(pundit='romantic')), 'The Romantic has no published show for Rovers v United'))
        self.assertTrue(has(errors(take(), st={'rail': None}), 'the rail was not read'))
        self.assertTrue(has(errors(take(), st={}), 'the rail was not read'))

    def test_a_show_link_needs_drop_and_pundit(self):
        item = take()
        del item['drop_id']
        self.assertTrue(has(errors(item), 'needs drop_id and pundit'))
        self.assertTrue(has(errors(take(pundit='gary')), "pundit 'gary' is not one of"))

    def test_row_needs_its_published_pundits(self):
        row = take(format_id='row', creative_id='TT_CLASH_CLIP_C03_H01_V1_20261101', drop_id='drop-thin',
                   pundit='zen', master_id='M_ROW')
        self.assertTrue(has(errors(row), 'row needs 2 published AI Pundits on the match; City v Athletic has 1'))


def recipes(allowed):
    real = formats.recipe

    def fake(format_id, directory=None):
        out = copy.deepcopy(real(format_id, directory))
        out['whole_match_claims_allowed'] = allowed
        return out
    return mock.patch.object(formats, 'recipe', fake)


class WholeMatchGateTests(unittest.TestCase):
    def test_whole_match_needs_four_of_six(self):
        with recipes(True):
            self.assertEqual(errors(take(whole_match=True)), [])
            thin = errors(take(whole_match=True, drop_id='drop-thin', pundit='zen'))
        self.assertTrue(has(thin, f'a whole-match claim needs {growth.RAIL_MIN} of 6 AI Pundits; City v Athletic has 1'))

    def test_whole_match_needs_a_format_that_allows_it(self):
        with recipes(False):
            found = errors(take(whole_match=True))
        self.assertTrue(has(found, 'take_clip may not claim a whole match'))

    def test_whole_match_must_be_a_boolean(self):
        self.assertTrue(has(errors(take(whole_match='yes')), 'whole_match must be true or false'))


class TodayGateTests(unittest.TestCase):
    def test_a_match_ad_links_to_today_while_it_is_live(self):
        self.assertEqual(errors(ad(), live=True), [])
        self.assertTrue(has(errors(ad(), live=False), 'Today has no published AI Pundit show right now'))
        self.assertTrue(has(errors(ad(), live=None), 'Today has no published AI Pundit show right now'))

    def test_a_match_ad_never_claims_a_show(self):
        for words in ('Our AI Pundit show is out.', 'The AI Pundit editions are in.', 'An AI Pundit Episode.'):
            with self.subTest(words=words):
                self.assertTrue(has(errors(ad(caption=words), live=True), 'never claims a show exists'))
        self.assertTrue(has(errors(ad(hashtags=['#Football', '#Shows']), live=True), 'never claims a show exists'))
        self.assertEqual(errors(ad(caption='The AI Pundit Showdown on the sofa.'), live=True), [])

    def test_a_match_ad_names_no_drop_or_pundit_and_links_to_the_home_page(self):
        self.assertTrue(has(errors(ad(drop_id='drop-full'), live=True), 'names no drop_id or pundit'))
        self.assertTrue(has(errors(ad(pundit='zen'), live=True), 'names no drop_id or pundit'))
        cid = 'TT_CLASH_VIDEO_C02_H01_V1_20261101'
        deep = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=zen', cid)
        self.assertTrue(has(errors(ad(link=deep), live=True), 'links to the Today home page'))
        self.assertTrue(has(errors(ad(whole_match=True), live=True), 'makes no whole-match claim'))
        self.assertEqual(errors(ad(drop_id=None, pundit=None), live=True), [])


class MediaReviewTests(unittest.TestCase):
    def test_media_is_bound_by_hash_and_size(self):
        self.assertTrue(has(errors(take(media=[])), 'at least one rendered file'))
        self.assertTrue(has(errors(take(media=[media(sha='A' * 64)])), 'sha256 must be 64 lowercase hex'))
        self.assertTrue(has(errors(take(media=[{**media(), 'bytes': 0}])), 'bytes must be a whole number above 0'))
        self.assertTrue(has(errors(take(media=[{**media(), 'bytes': True}])), 'bytes must be a whole number above 0'))
        self.assertTrue(has(errors(take(media=[media(kind='gif')])), 'kind must be one of'))
        self.assertTrue(has(errors(take(media=[media(url='http://review.example.com/x')])), 'review_url must be an https'))

    def test_ai_label_and_suggested_time(self):
        self.assertTrue(has(errors(take(ai_label={'platform_label_set': True, 'visible_ai_pundit': False})), 'ai_label'))
        self.assertTrue(has(errors(take(ai_label={'platform_label_set': 1, 'visible_ai_pundit': True})), 'ai_label'))
        self.assertTrue(has(errors(take(scheduled_suggestion='2026-11-01T18:30:00')), 'UTC offset'))
        self.assertEqual(errors(take(scheduled_suggestion='2026-11-01T18:30:00Z')), [])

    def test_review_bar(self):
        self.assertTrue(has(errors(take(review=review(rubric_total=37))), 'the bar is 38'))
        self.assertEqual(errors(take(review=review(rubric_total=38))), [])
        self.assertTrue(has(errors(take(review=review(rubric_total=49))), 'from 0 to 48'))
        self.assertTrue(has(errors(take(review=review(ethics=3))), 'review ethics must score 4'))
        self.assertTrue(has(errors(take(review=review(action=3))), 'review action must score 4'))
        self.assertTrue(has(errors(take(review=review(alternatives=['Only one']))), 'at least two'))
        self.assertTrue(has(errors(take(review=review(alternatives=['Same', 'Same']))), 'at least two'))
        self.assertTrue(has(errors(take(review=review(why_wins=''))), 'why_wins'))

    def test_note_is_optional_text(self):
        self.assertEqual(errors(take(note='Shorter open, please.')), [])
        self.assertTrue(has(errors(take(note=3)), 'note must be text'))

    def test_credential_urls_refused(self):
        found = errors(take(note='Review at https://review.example.com/x?token=abc'))
        self.assertTrue(has(found, 'credential or private-contact URL parameters'))


class SizeTests(unittest.TestCase):
    def test_exact_payload_at_most_8000_characters(self):
        found = errors(take(note='x' * 8000))
        self.assertTrue(has(found, 'Control Center takes at most 8000'))
        with self.assertRaises(ValueError):
            build([take(note='x' * 8000)], RUN, DAY, state(), allowlist(), False)

    def test_payload_counts_as_javascript_does(self):
        from engine.pack import payload_length
        self.assertEqual(payload_length('\U0001F600'), 2)

    def test_at_most_twelve_distinct_review_links(self):
        many = [media(f'{i:064x}', url=f'https://review.example.com/2026-11-01/{i}') for i in range(13)]
        found = errors(take(media=many))
        self.assertTrue(has(found, '13 distinct review links'))
        shared = [media(f'{i:064x}') for i in range(13)]
        self.assertFalse(has(errors(take(media=shared)), 'distinct review links'))


def minimal_report(proposals):
    return reporting.seal({'schema_version': '1.0.0', 'engine_id': reporting.ENGINE_ID,
                           'product_slug': reporting.PRODUCT_SLUG, 'run_id': RUN, 'mode': 'synthetic',
                           'observed_at': '2026-11-01T07:00:00Z',
                           'source': {'revision': 'a' * 40, 'captured_at': '2026-11-01T06:55:00Z'},
                           'status': 'held', 'proposals': proposals})


class ProposalTests(unittest.TestCase):
    def built(self, *items, live=True):
        return build(list(items), RUN, DAY, state(), allowlist(), live)

    def test_proposal_is_schema_valid_inside_a_report(self):
        built = self.built(take(), reel(), ad())
        ask = proposal(built, '2026-11-02T06:00:00Z')
        self.assertEqual(reporting.schema_errors(minimal_report([ask])), [])
        self.assertEqual(ask['proposal_id'], 'fulltime-g2-2026-11-01')
        self.assertEqual((ask['wall'], ask['kind'], ask['channel']), ('post', 'prepared', 'multi'))
        self.assertEqual(ask['exact_payload'], reporting.canonical(built))
        self.assertEqual(json.loads(ask['exact_payload']), built)
        self.assertEqual(ask['payload_sha256'], reporting.canonical_sha256(built))
        self.assertEqual(ask['close_condition'], {'event': 'creative_published', 'reference': RUN})
        self.assertEqual([e['url'] for e in ask['evidence']], review_urls(built))
        self.assertIn('tiktok', ask['title'])
        self.assertIn('ig_reels', ask['title'])
        self.assertNotIn('\u2014', ask['title'] + ask['why'])

    def test_a_single_channel_pack_names_its_channel(self):
        ask = proposal(self.built(take()), None)
        self.assertEqual(ask['channel'], 'tiktok')
        self.assertEqual(reporting.schema_errors(minimal_report([ask])), [])

    def test_the_id_is_stable_and_the_digest_follows_the_words(self):
        first = proposal(self.built(take()), None)
        changed = proposal(self.built(take(caption='The Doomer called time early. Hear the AI Pundit.')), None)
        self.assertEqual(first['proposal_id'], changed['proposal_id'])
        self.assertNotEqual(first['payload_sha256'], changed['payload_sha256'])

    def test_proposal_refuses_an_oversized_or_unchecked_pack(self):
        with self.assertRaises(ValueError):
            proposal(pack_of(take(note='x' * 8000)), None)
        with self.assertRaises(ValueError):
            proposal({'run_id': RUN, 'matchday': DAY, 'items': []}, None)
        with self.assertRaises(ValueError):
            proposal(self.built(take()), '2026-11-02T06:00:00')


if __name__ == '__main__':
    unittest.main()
