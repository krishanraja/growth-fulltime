import copy
import datetime as dt
import json
import unittest
from pathlib import Path
from unittest import mock

import growth
from engine import formats, reporting, spec
from engine.pack import build, check, proposal, review_urls

RUN = 'fulltime:2026-11-01:g2'
DAY = '2026-11-01'
SHA_A, SHA_B, SHA_C = 'a' * 64, 'b' * 64, 'c' * 64
LOCK = 'a' * 64
FIXTURE = 'synthetic-fixture-001'
EXPIRES = '2026-11-01T20:00:00+00:00'
EXAMPLE = Path(__file__).resolve().parent.parent / 'specs' / 'examples' / 'synthetic-week.json'


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


def every_channel():
    """The allowlist with all eight ruling-2 channels; the WhatsApp Channel is posted by hand."""
    allow = allowlist()
    allow['channels'].update({
        'fulltime-threads': entry('000000000000000000000004', 'threads', 'threads'),
        'fulltime-facebook': entry('000000000000000000000006', 'facebook', 'facebook'),
        'fulltime-whatsapp-channel': entry(None, 'whatsapp', 'whatsapp_channel')})
    return allow


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
            'fixture_ref': FIXTURE, 'lock_version': LOCK,
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


def zen(**over):
    """The Reporter's take on drop-full, from its own master."""
    cid = over.pop('creative_id', 'TT_CLASH_CLIP_C02_H01_V1_20261101')
    return take(creative_id=cid, pundit='zen', master_id='M_20261101_ROVERS_UNITED_ZEN',
                caption='The Reporter has seen this before. Hear the whole take from the AI Pundit.',
                media=[media('d' * 64, url='https://review.example.com/2026-11-01/take-02')], **over)


def ad(**over):
    """A match ad on TikTok, linking to Today."""
    cid = over.pop('creative_id', 'TT_CLASH_VIDEO_C02_H01_V1_20261101')
    item = {'creative_id': cid, 'master_id': 'M_20261101_REMOTE_AD', 'format_id': 'match_ad',
            'fixture_ref': FIXTURE, 'lock_version': LOCK,
            'channel': 'tiktok', 'channel_ref': 'fulltime-tiktok',
            'caption': 'Two AI Pundits, one remote, and a sofa that will not agree. Pick your AI Pundit.',
            'hashtags': ['#Football', '#MatchDay'], 'link': growth.tracked('https://fulltime.fm/', cid),
            'whole_match': False, 'media': [media(SHA_C, url='https://review.example.com/2026-11-01/ad-01')],
            'ai_label': {'platform_label_set': True, 'visible_ai_pundit': True},
            'scheduled_suggestion': '2026-11-01T11:00:00+00:00', 'review': review()}
    item.update(over)
    return item


def card(**over):
    """A morning card on Instagram feed: a format that may claim a whole match."""
    cid = over.pop('creative_id', 'IG_CLASH_POST_C04_H01_V1_20261101')
    drop, pundit = over.pop('drop_id', 'drop-full'), over.pop('pundit', 'zen')
    item = take(creative_id=cid, format_id='morning_card', channel='ig_feed', channel_ref='fulltime-ig-feed',
                master_id='M_20261101_MORNING_CARD', drop_id=drop, pundit=pundit,
                link=growth.tracked(f'https://fulltime.fm/?drop={drop}&pundit={pundit}', cid),
                caption='The Reporter is up first this morning. Pick your AI Pundit.',
                media=[media('e' * 64, kind='image', url='https://review.example.com/2026-11-01/card-01')])
    item.update(over)
    return item


def row(**over):
    """Pundit v Pundit on TikTok: The Reporter and The Gaffer on drop-full."""
    item = {'creative_id': 'TT_CLASH_CLIP_C03_H01_V1_20261101', 'format_id': 'row', 'master_id': 'M_ROW',
            'pundit': 'zen', 'pundits': ['zen', 'gaffer'],
            'caption': 'The Reporter v The Gaffer on Rovers v United. Pick your AI Pundit.',
            'media': [media('f' * 64, url='https://review.example.com/2026-11-01/row-01')], **over}
    return take(**item)


def week(mode='proof', **formats_over):
    """The synthetic week spec with every format pinned to LOCK; formats_over edits a format by id."""
    data = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    data['mode'] = mode
    # The packs here are for matchday 2026-11-01 (DAY), so the week is the London
    # week holding it, W44, with the example's fixtures moved back a week.
    data['run_id'], data['window'] = 'fulltime:2026-W44', {**data['window'], 'start': '2026-10-26', 'end': '2026-11-01'}
    for fixture in data['fixtures']:
        moved = dt.datetime.fromisoformat(fixture['kickoff']) - dt.timedelta(days=7)
        fixture['kickoff'] = moved.isoformat()
    for item in data['formats']:
        item['lock_version'] = LOCK
        item.update(formats_over.get(item['format_id'], {}))
    return data


def pack_of(*items, run=RUN, day=DAY):
    return {'run_id': run, 'matchday': day, 'items': list(items)}


def errors(*items, st=None, allow=None, live=False, campaign=None, earlier=None):
    return check(pack_of(*items), state() if st is None else st, allow or allowlist(), live, campaign, earlier)


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

    def test_fixture_ref_and_lock_version_are_required_and_exact(self):
        item = take()
        del item['fixture_ref'], item['lock_version']
        self.assertTrue(has(errors(item), 'missing fields: fixture_ref, lock_version'))
        self.assertTrue(has(errors(take(fixture_ref=' ')), 'fixture_ref must name the match'))
        for bad in ('A' * 64, 'a' * 63, 'a' * 64 + '\n', 'locked', None):
            with self.subTest(lock=bad):
                self.assertTrue(has(errors(take(lock_version=bad)), 'lock_version must be "unlocked" or'))
        self.assertEqual(errors(take(lock_version='unlocked')), [])

    def test_the_run_id_names_its_matchday(self):
        found = check(pack_of(take(), run='fulltime:2026-11-02:g2'), state(), allowlist(), False)
        self.assertTrue(has(found, 'run_id must name its matchday: fulltime:2026-11-01:g2'))

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


class EarlierAskTests(unittest.TestCase):
    """Never the same asset twice on one channel, and never one creative ID twice, across matchdays."""

    def next_week(self, **over):
        cid = over.pop('creative_id', 'TT_CLASH_VIDEO_C02_H01_V1_20261108')
        item = ad(creative_id=cid, link=growth.tracked('https://fulltime.fm/', cid),
                  scheduled_suggestion='2026-11-08T11:00:00+00:00', **over)
        return pack_of(item, run='fulltime:2026-11-08:g2', day='2026-11-08')

    def test_an_asset_already_asked_on_that_channel_is_refused(self):
        first = proposal(build([ad()], RUN, DAY, state(), allowlist(), True), EXPIRES)
        self.assertEqual(check(self.next_week(), state(), allowlist(), True), [])
        found = check(self.next_week(), state(), allowlist(), True, earlier=[first])
        self.assertTrue(has(found, 'the same asset (cccccccccccc) already went on tiktok in fulltime-g2-2026-11-01'))
        fresh = self.next_week(media=[media('9' * 64, url='https://review.example.com/2026-11-08/ad-01')])
        self.assertEqual(check(fresh, state(), allowlist(), True, earlier=[first]), [])

    def test_a_creative_id_already_asked_is_refused_but_a_revision_of_the_same_ask_is_not(self):
        first = proposal(build([ad()], RUN, DAY, state(), allowlist(), True), EXPIRES)
        again = self.next_week(creative_id='TT_CLASH_VIDEO_C02_H01_V1_20261101',
                               media=[media('9' * 64, url='https://review.example.com/2026-11-08/ad-01')])
        self.assertTrue(has(check(again, state(), allowlist(), True, earlier=[first]),
                            'was already asked in fulltime-g2-2026-11-01'))
        self.assertEqual(check(pack_of(ad()), state(), allowlist(), True, earlier=[first]), [])

    def test_an_unreadable_earlier_ask_is_refused_not_skipped(self):
        found = check(self.next_week(), state(), allowlist(), True,
                      earlier=[{'proposal_id': 'fulltime-g2-2026-10-25', 'exact_payload': 'not json'}])
        self.assertTrue(has(found, 'cannot be read'))


class ChannelRefTests(unittest.TestCase):
    def test_ref_must_be_an_allowlisted_brand_entry_for_the_same_channel(self):
        self.assertTrue(has(errors(take(channel_ref='fulltime-unknown')), 'is not in the Full Time Buffer allowlist'))
        self.assertTrue(has(errors(take(channel_ref='000000000000000000000001')), 'raw platform ID'))
        self.assertTrue(has(errors(take(channel_ref='personal-tiktok')), 'is not a Full Time brand channel'))
        self.assertTrue(has(errors(take(channel_ref='fulltime-yt-shorts')), 'is the yt_shorts channel, not tiktok'))

    def test_allowlist_must_be_full_time(self):
        other = {**allowlist(), 'product': 'makeyourmindup'}
        self.assertTrue(has(errors(take(), allow=other), 'product "fulltime"'))

    def test_the_entry_is_held_to_the_allowlist_rules(self):
        bare = {'product': 'fulltime', 'channels': {'fulltime-tiktok': {'account_scope': 'brand', 'channel': 'tiktok'}}}
        self.assertTrue(has(errors(take(), allow=bare), 'the allowlist entry is refused'))
        upper = allowlist()
        upper['channels']['UC_x5XG1OV2P6uZZ5FSM9Ttw'] = copy.deepcopy(upper['channels']['fulltime-tiktok'])
        found = errors(take(channel_ref='UC_x5XG1OV2P6uZZ5FSM9Ttw'), allow=upper)
        self.assertTrue(has(found, 'never a raw platform ID'))

    def test_a_buffer_channel_needs_its_buffer_id_and_only_whatsapp_is_by_hand(self):
        nulled = allowlist()
        nulled['channels']['fulltime-tiktok']['buffer_channel_id'] = None
        self.assertTrue(has(errors(take(), allow=nulled), "'fulltime-tiktok' has no Buffer channel ID"))
        cid = 'WC_CLASH_CLIP_C01_H01_V1_20261101'
        whatsapp = take(creative_id=cid, channel='whatsapp_channel', channel_ref='fulltime-whatsapp-channel',
                        link=growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', cid))
        self.assertEqual(errors(whatsapp, allow=every_channel()), [])


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

    def test_the_words_a_hashtag_or_handle_joins_get_the_copy_rules(self):
        for tag, rule in (('#SkySports', 'broadcaster'), ('#MatchOfTheDay', 'broadcaster'),
                          ('#BettingTips', 'betting language'), ('#AccaTips', 'betting language'),
                          ('#NeverMiss', 'every-match'), ('#EveryMatch', 'every-match'),
                          ('#GaryNeville', 'living pundit'), ('#GameChanger', 'marketing filler'),
                          ('#Sky_Sports', 'broadcaster')):
            with self.subTest(tag=tag):
                self.assertTrue(has(errors(take(hashtags=['#Football', tag])), rule))
        self.assertTrue(has(errors(take(caption='The AI Pundit answers @SkySportsPL.')), 'broadcaster'))
        self.assertTrue(has(errors(take(caption='The AI Pundit has the bet\u200bting tips.')), 'betting language'))
        self.assertEqual(errors(take(hashtags=['#Football', '#AIPundit', '#MatchDay', '#TheDoomer'])), [])

    def test_caption_carries_no_link_and_no_hashtags(self):
        self.assertTrue(has(errors(take(caption='The AI Pundit at https://fulltime.fm/')), 'carries no link'))
        self.assertTrue(has(errors(take(caption='The AI Pundit, on fulltime.fm today.')), 'carries no link'))
        for words in ('The AI Pundit, full take at bit.ly/3abcXYZ', 'The AI Pundit at tinyurl.com/ftfm',
                      'The AI Pundit: fulltime\u2024fm', 'The AI Pundit at x.com/fulltimefm'):
            with self.subTest(words=words):
                self.assertTrue(has(errors(take(caption=words)), 'carries no link'))
        self.assertTrue(has(errors(take(caption='The AI Pundit #Football')), 'not the caption'))

    def test_a_channel_growth_does_not_list_still_gets_copy_rules(self):
        from engine.pack import _copy_errors
        item = take(channel='threads', caption='The AI Pundit \u2014 a game-changer.')
        found = _copy_errors(item, state())
        self.assertTrue(has(found, 'em dash'))
        self.assertTrue(has(found, 'marketing filler'))
        self.assertFalse(has(found, 'platform "threads"'))

    def test_x_counts_the_link_too(self):
        cid = 'X_CLASH_CLIP_C01_H01_V1_20261101'
        base = 'The Doomer has seen this before. Hear the whole take from the AI Pundit.'
        tags = ['#Football', '#AIPundit']

        def on_x(length):
            caption = (base + ' Again.' * 40)[:length - len('\n\n' + ' '.join(tags))]
            return take(creative_id=cid, channel='x', channel_ref='fulltime-x', caption=caption, hashtags=tags,
                        link=growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', cid),
                        media=[media('e' * 64)])
        self.assertTrue(has(errors(on_x(279)), 'on x the post is 303 characters with its link'))
        self.assertEqual(errors(on_x(256)), [])
        self.assertFalse(has(errors(on_x(257)), '280 at most on x'))
        self.assertTrue(has(errors(on_x(257)), 'with its link'))


class LinkTests(unittest.TestCase):
    cid = 'TT_CLASH_CLIP_C01_H01_V1_20261101'

    def test_link_must_be_tracked_as_its_creative_id(self):
        cid = self.cid
        self.assertTrue(has(errors(take(link='https://fulltime.fm/?drop=drop-full&pundit=doomer')), 'not tracked'))
        other = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', 'TT_CLASH_CLIP_C09_H01_V1_20261101')
        self.assertTrue(has(errors(take(link=other)), f'not tracked as {cid}'))
        self.assertTrue(has(errors(take(link=growth.tracked('https://example.com/?drop=drop-full&pundit=doomer', cid))),
                            'https fulltime.fm link'))
        self.assertTrue(has(errors(take(link=growth.tracked('http://fulltime.fm/?drop=drop-full&pundit=doomer', cid))),
                            'https fulltime.fm link'))

    def test_link_must_open_the_items_own_drop_and_pundit(self):
        elsewhere = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=zen', self.cid)
        self.assertTrue(has(errors(take(link=elsewhere)), 'the link must open drop drop-full with The Doomer'))

    def test_a_repeated_key_is_read_as_a_browser_reads_it(self):
        # URLSearchParams.get, what the product reads, takes the first value.
        for query in ('drop=drop-gone&pundit=romantic&drop=drop-full&pundit=doomer',
                      'drop=&pundit=romantic&drop=drop-full&pundit=doomer'):
            with self.subTest(query=query):
                link = growth.tracked(f'https://fulltime.fm/?{query}', self.cid)
                self.assertTrue(has(errors(take(link=link)), 'the link must open drop drop-full with The Doomer'))
        doubled = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer&drop=drop-gone', self.cid)
        self.assertTrue(has(errors(take(link=doubled)), 'drop and pundit once each'))

    def test_a_show_link_carries_nothing_but_its_drop_pundit_and_tracking(self):
        for extra in ('s=fan-share-token-123', 'next=https://evil.example/', 'pundit_override=romantic'):
            with self.subTest(extra=extra):
                link = growth.tracked(f'https://fulltime.fm/?drop=drop-full&pundit=doomer&{extra}', self.cid)
                self.assertTrue(has(errors(take(link=link)), 'the link must be exactly'))
        for link in (growth.tracked('https://www.fulltime.fm/?drop=drop-full&pundit=doomer', self.cid),
                     growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer#top', self.cid)):
            with self.subTest(link=link):
                self.assertTrue(has(errors(take(link=link)), 'the link must be exactly'))


class PerTakeGateTests(unittest.TestCase):
    def test_a_take_on_a_thin_match_passes_when_its_own_show_is_published(self):
        # Ruling 1: the 4-of-6 rule applies only to a whole-match claim.
        self.assertEqual(errors(take(drop_id='drop-thin', pundit='zen',
                                     caption='The Reporter has seen this before. Hear the AI Pundit.')), [])

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
        thin = row(drop_id='drop-thin', pundits=['zen', 'gaffer'])
        self.assertTrue(has(errors(thin), 'row needs 2 published AI Pundits on the match; City v Athletic has 1'))

    def test_every_ai_pundit_the_item_names_or_lists_has_a_show_for_its_match(self):
        self.assertEqual(errors(row()), [])
        named = row(caption='The Reporter v The Romantic on Rovers v United. Pick your AI Pundit.')
        self.assertTrue(has(errors(named), 'The Romantic has no published show for Rovers v United'))
        listed = row(pundits=['zen', 'romantic'], caption='Who is right? Pick your AI Pundit.')
        self.assertTrue(has(errors(listed), 'The Romantic has no published show for Rovers v United'))
        unlisted = row()
        del unlisted['pundits']
        self.assertTrue(has(errors(unlisted), 'row names 2 AI Pundits: list every one in pundits'))
        self.assertTrue(has(errors(row(pundits=['gaffer', 'stats'])), "the item's own pundit among them"))
        thin = take(drop_id='drop-thin', pundit='zen',
                    caption='The Doomer and The Reporter fall out over City v Athletic. Hear the AI Pundit.')
        self.assertTrue(has(errors(thin), 'The Doomer has no published show for City v Athletic'))
        tagged = take(drop_id='drop-thin', pundit='zen', caption='The Reporter has seen this. Hear the AI Pundit.',
                      hashtags=['#Football', '#TheDoomer'])
        self.assertTrue(has(errors(tagged), 'The Doomer has no published show for City v Athletic'))


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

    def test_the_words_claim_the_whole_match_whatever_the_flag_says(self):
        words = 'City v Athletic this morning: all six AI Pundits have had their say. Pick your AI Pundit.'
        thin = card(drop_id='drop-thin', pundit='zen', caption=words)
        del thin['whole_match']
        with self.assertRaises(ValueError) as caught:
            build([thin], RUN, DAY, state(), allowlist(), False)
        self.assertIn(f'a whole-match claim needs {growth.RAIL_MIN} of 6', str(caught.exception))
        self.assertIn('whole_match must be set', str(caught.exception))
        self.assertTrue(has(errors(card(drop_id='drop-thin', pundit='zen', caption=words)),
                            'so whole_match must be true'))
        full = 'Rovers v United: four of the six AI Pundits have had their say. Pick your AI Pundit.'
        self.assertEqual(errors(card(caption=full, whole_match=True)), [])
        self.assertTrue(has(errors(take(caption='The whole match in one AI Pundit take.')),
                            'take_clip may not claim a whole match'))
        # The roster is not a claim: "one of six AI Pundits" says who he is, not who covered the match.
        roster = 'The Doomer is one of six AI Pundits. Hear his take from the AI Pundit.'
        self.assertFalse(has(errors(take(caption=roster)), 'whole match'))
        self.assertTrue(has(errors(take(caption='Six AI Pundits on Rovers v United. Hear the AI Pundit.')),
                            'take_clip may not claim a whole match'))

    def test_a_format_that_may_claim_a_whole_match_states_it_on_every_item(self):
        item = card()
        del item['whole_match']
        self.assertTrue(has(errors(item), 'whole_match must be set, true or false'))
        self.assertEqual(errors(card()), [])


class TodayGateTests(unittest.TestCase):
    def test_a_match_ad_links_to_today_while_it_is_live(self):
        self.assertEqual(errors(ad(), live=True), [])
        self.assertTrue(has(errors(ad(), live=False), 'Today has no published AI Pundit show right now'))
        self.assertTrue(has(errors(ad(), live=None), 'Today has no published AI Pundit show right now'))

    def test_a_match_ad_never_claims_a_show(self):
        for words in ('Our AI Pundit show is out.', 'The AI Pundit editions are in.', 'An AI Pundit Episode.',
                      'The AI Pundit podcast on Rovers v United is out.', 'Our AI Pundit sh\u200bow is out.',
                      'Listen to the AI Pundit on this match.', 'Hear the AI Pundit take, out now.'):
            with self.subTest(words=words):
                self.assertTrue(has(errors(ad(caption=words), live=True), 'never claims a show exists'))
        for tag in ('#Shows', '#AIPunditShow', '#NewEpisode', '#Podcast'):
            with self.subTest(tag=tag):
                self.assertTrue(has(errors(ad(hashtags=['#Football', tag]), live=True), 'never claims a show exists'))
        self.assertEqual(errors(ad(caption='The AI Pundit Showdown on the sofa.'), live=True), [])
        self.assertEqual(errors(ad(hashtags=['#Football', '#AIPunditShowdown']), live=True), [])

    def test_a_match_ad_names_no_drop_or_pundit_and_links_to_the_home_page(self):
        self.assertTrue(has(errors(ad(drop_id='drop-full'), live=True), 'names no drop_id, pundit or pundits'))
        self.assertTrue(has(errors(ad(pundit='zen'), live=True), 'names no drop_id, pundit or pundits'))
        self.assertTrue(has(errors(ad(pundits=['zen']), live=True), 'names no drop_id, pundit or pundits'))
        cid = 'TT_CLASH_VIDEO_C02_H01_V1_20261101'
        deep = growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=zen', cid)
        self.assertTrue(has(errors(ad(link=deep), live=True), 'links to the Today home page'))
        self.assertTrue(has(errors(ad(whole_match=True), live=True), 'makes no whole-match claim'))
        self.assertEqual(errors(ad(drop_id=None, pundit=None), live=True), [])


class SpecTests(unittest.TestCase):
    """The week spec binds the pack: its fixtures, locks, channels, AI Pundits and caps."""

    def test_a_pack_inside_the_week_spec_passes(self):
        self.assertEqual(spec.validate(week()), [])
        self.assertEqual(errors(take(), reel(), ad(), live=True, campaign=week()), [])

    def test_each_item_sits_inside_the_week_spec(self):
        self.assertTrue(has(errors(take(fixture_ref='synthetic-fixture-009'), campaign=week()),
                            "fixture_ref 'synthetic-fixture-009' is not a fixture in the week spec fulltime:2026-W44"))
        self.assertTrue(has(errors(take(lock_version='b' * 64), campaign=week()),
                            'is not the take_clip lock in the week spec'))
        self.assertTrue(has(errors(take(lock_version='unlocked'), campaign=week()), 'is not the take_clip lock'))
        cid = 'IG_CLASH_CLIP_C01_H01_V2_20261101'
        feed = take(creative_id=cid, channel='ig_feed', channel_ref='fulltime-ig-feed', media=[media(SHA_B)],
                    link=growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', cid))
        self.assertEqual(errors(feed), [])
        self.assertTrue(has(errors(feed, campaign=week()), 'allows take_clip on tiktok, ig_reels'))
        without_ads = week()
        without_ads['formats'] = [f for f in without_ads['formats'] if f['format_id'] != 'match_ad']
        self.assertTrue(has(errors(ad(), live=True, campaign=without_ads), 'match_ad is not a format in the week spec'))
        no_doomer = week(take_clip={'pundits_allowed': ['zen', 'gaffer']})
        self.assertTrue(has(errors(take(), campaign=no_doomer), 'does not allow The Doomer in take_clip'))
        self.assertTrue(has(errors(row(), campaign=week(row={'pundits_allowed': ['zen', 'stats']})),
                            'does not allow The Gaffer in row'))

    def test_caps_count_masters_per_matchday_and_items_per_channel_per_day(self):
        tight = week(take_clip={'max_per_matchday': 1})
        tight['channels'] = [{**c, 'cap_per_day': 1} if c['channel'] == 'tiktok' else c for c in tight['channels']]
        found = errors(take(), zen(), campaign=tight)
        self.assertTrue(has(found, 'take_clip: 2 masters on matchday 2026-11-01, and the week spec allows 1'))
        self.assertTrue(has(found, 'tiktok: 2 items on 2026-11-01, and the week spec allows 1 a day'))
        # One master on two channels is one take (ruling 2), so max_per_matchday counts it once.
        self.assertEqual(errors(take(), reel(), campaign=tight), [])
        # The next morning is another day for cap_per_day.
        later = zen(scheduled_suggestion='2026-11-02T08:00:00+00:00')
        self.assertFalse(has(errors(take(), later, campaign=tight), 'cap_per_day'))

    def test_caps_count_the_other_parts_of_a_split_matchday(self):
        tight = week(take_clip={'max_per_matchday': 1})
        first = proposal(build([take()], 'fulltime:2026-11-01:g2a', DAY, state(), allowlist(), False, tight),
                         EXPIRES)
        second = pack_of(zen(), run='fulltime:2026-11-01:g2b')
        self.assertEqual(check(second, state(), allowlist(), False, tight), [])
        found = check(second, state(), allowlist(), False, tight, [first])
        self.assertTrue(has(found, 'take_clip: 2 masters on matchday 2026-11-01'))

    def test_a_pack_outside_its_week_is_refused(self):
        outside = pack_of(take(), run='fulltime:2026-11-10:g2', day='2026-11-10')
        found = check(outside, state(), allowlist(), False, week())
        self.assertTrue(has(found, 'matchday 2026-11-10 is outside the week spec fulltime:2026-W44'))
        self.assertFalse(has(errors(take(), campaign=week()), 'is outside the week spec'))

    def test_a_refused_spec_checks_nothing(self):
        self.assertTrue(has(errors(take(), campaign={}), 'the week spec is refused'))
        self.assertTrue(has(errors(take(), campaign=[]), 'the week spec is refused'))


def minimal_report(proposals):
    return reporting.seal({'schema_version': '1.0.0', 'engine_id': reporting.ENGINE_ID,
                           'product_slug': reporting.PRODUCT_SLUG, 'run_id': RUN, 'mode': 'synthetic',
                           'observed_at': '2026-11-01T07:00:00Z',
                           'source': {'revision': 'a' * 40, 'captured_at': '2026-11-01T06:55:00Z'},
                           'status': 'held', 'proposals': proposals})


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

    def test_a_take_on_all_eight_channels_splits_into_parts_with_their_own_asks(self):
        cuts = [('tiktok', 'TT_CLASH_CLIP_C01_H01_V1', 'fulltime-tiktok'),
                ('ig_reels', 'IG_CLASH_SHORT_C01_H01_V1', 'fulltime-ig-reels'),
                ('yt_shorts', 'YT_CLASH_CLIP_C01_H01_V1', 'fulltime-yt-shorts'),
                ('ig_feed', 'IG_CLASH_CLIP_C01_H01_V2', 'fulltime-ig-feed'),
                ('threads', 'TH_CLASH_CLIP_C01_H01_V1', 'fulltime-threads'),
                ('x', 'X_CLASH_CLIP_C01_H01_V1', 'fulltime-x'),
                ('facebook', 'FB_CLASH_CLIP_C01_H01_V1', 'fulltime-facebook'),
                ('whatsapp_channel', 'WC_CLASH_CLIP_C01_H01_V1', 'fulltime-whatsapp-channel')]
        items = []
        for n, (channel, stem, ref) in enumerate(cuts, 1):
            cid = f'{stem}_20261101'
            url = f'https://review.example.com/2026-11-01/take-01-{channel}'
            items.append(take(creative_id=cid, channel=channel, channel_ref=ref, media=[media(f'{n:064x}', url=url)],
                              link=growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', cid)))
        whole = check(pack_of(*items), state(), every_channel(), False)
        self.assertTrue(has(whole, 'split the matchday into packs with their own run_id (fulltime:2026-11-01:g2a, '
                                   'fulltime:2026-11-01:g2b'))
        first = build(items[:4], 'fulltime:2026-11-01:g2a', DAY, state(), every_channel(), False)
        second = build(items[4:], 'fulltime:2026-11-01:g2b', DAY, state(), every_channel(), False)
        asks = [proposal(first, EXPIRES), proposal(second, EXPIRES)]
        self.assertEqual([a['proposal_id'] for a in asks], ['fulltime-g2-2026-11-01-g2a', 'fulltime-g2-2026-11-01-g2b'])
        self.assertEqual(reporting.schema_errors(minimal_report(asks)), [])


class ProposalTests(unittest.TestCase):
    def built(self, *items, live=True, campaign=None):
        return build(list(items), RUN, DAY, state(), allowlist(), live, campaign)

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
        ask = proposal(self.built(take()), EXPIRES)
        self.assertEqual(ask['channel'], 'tiktok')
        self.assertEqual(reporting.schema_errors(minimal_report([ask])), [])

    def test_the_id_is_stable_and_the_digest_follows_the_words(self):
        first = proposal(self.built(take()), EXPIRES)
        changed = proposal(self.built(take(caption='The Doomer called time early. Hear the AI Pundit.')), EXPIRES)
        self.assertEqual(first['proposal_id'], changed['proposal_id'])
        self.assertNotEqual(first['payload_sha256'], changed['payload_sha256'])

    def test_proposal_refuses_an_oversized_or_unchecked_pack(self):
        with self.assertRaises(ValueError):
            proposal(pack_of(take(note='x' * 8000)), EXPIRES)
        with self.assertRaises(ValueError):
            proposal({'run_id': RUN, 'matchday': DAY, 'items': []}, EXPIRES)
        with self.assertRaises(ValueError):
            proposal(self.built(take()), '2026-11-02T06:00:00')

    def test_every_g2_ask_expires(self):
        for expires in (None, '', 'tomorrow', '2026-11-02T06:00:00'):
            with self.subTest(expires=expires):
                with self.assertRaises(ValueError) as caught:
                    proposal(self.built(take()), expires)
                self.assertIn('every G2 ask expires', str(caught.exception))

    def test_a_proof_ask_is_a_verdict_ask_and_posts_nothing(self):
        ask = proposal(self.built(take(), ad()), EXPIRES)
        self.assertEqual(ask['title'], 'Matchday 2026-11-01, proof: verdicts only on 2 items, nothing to post (tiktok)')
        self.assertIn('a verdict ask only. Nothing is to be posted, and you do not post any item', ask['why'])
        self.assertIn('(post it, edit or reject) builds its format\'s readiness', ask['why'])
        self.assertNotIn('Buffer', ask['why'])
        self.assertNotIn('you post each item yourself', ask['why'])
        self.assertEqual(ask, proposal(self.built(take(), ad()), EXPIRES, mode='proof'))
        self.assertEqual(ask['why'], ask['why'][:1000])

    def test_only_a_live_ask_says_post_by_hand_in_buffer(self):
        ask = proposal(self.built(take(), ad(), campaign=week('live')), EXPIRES, mode='live')
        self.assertEqual(ask['title'], 'Matchday 2026-11-01: 2 posts to make by hand (tiktok)')
        self.assertIn('Live, under the signed spec fulltime:2026-W44', ask['why'])
        self.assertIn('you post each item yourself in Buffer', ask['why'])
        self.assertIn('Before posting a match ad, check Today carries a published AI Pundit show', ask['why'])
        self.assertEqual(ask['why'], ask['why'][:1000])
        self.assertEqual(reporting.schema_errors(minimal_report([ask])), [])
        self.assertNotIn('Before posting a match ad',
                         proposal(self.built(take(), campaign=week('live')), EXPIRES, mode='live')['why'])

    def test_the_mode_is_proof_or_live_and_follows_the_spec_it_was_checked_against(self):
        with self.assertRaises(ValueError):
            proposal(self.built(take()), EXPIRES, mode='draft')
        with self.assertRaises(ValueError) as caught:
            proposal(self.built(take()), EXPIRES, mode='live')
        self.assertIn('against the signed live spec', str(caught.exception))
        with self.assertRaises(ValueError):
            proposal(self.built(take(), campaign=week('proof')), EXPIRES, mode='live')
        with self.assertRaises(ValueError) as caught:
            proposal(self.built(take(), campaign=week('live')), EXPIRES, mode='proof')
        self.assertIn('so its ask is live', str(caught.exception))

    def test_the_why_claims_checks_only_for_a_pack_check_passed(self):
        built = self.built(take())
        self.assertIn('Checked when the pack was built: every item links', proposal(built, EXPIRES)['why'])
        spec_checked = proposal(self.built(take(), campaign=week()), EXPIRES)['why']
        self.assertIn('Checked when the pack was built against the week spec fulltime:2026-W44', spec_checked)
        unchecked = proposal(pack_of(take(channel_ref='personal-tiktok')), EXPIRES)['why']
        self.assertIn('Not checked: pack.check has not passed on exactly this pack', unchecked)
        self.assertNotIn('Checked when', unchecked)
        self.assertNotIn('passed the copy rules', unchecked)
        stale = copy.deepcopy(built)
        stale['items'][0]['caption'] = 'Changed after the check. The AI Pundit.'
        self.assertIn('Not checked', proposal(stale, EXPIRES)['why'])
        # A later check that refuses the same pack withdraws the claim.
        self.assertTrue(check(built, state(), allowlist(), True, None) == [])
        self.assertTrue(check(built, {'rail': None}, allowlist(), True))
        self.assertIn('Not checked', proposal(built, EXPIRES)['why'])

    def test_a_live_match_ad_expires_by_the_end_of_its_matchday(self):
        live = self.built(take(), ad(), campaign=week('live'))
        self.assertEqual(proposal(live, '2026-11-01T23:59:00Z', mode='live')['expires_at'], '2026-11-01T23:59:00Z')
        with self.assertRaises(ValueError) as caught:
            proposal(live, '2026-11-02T06:00:00Z', mode='live')
        self.assertIn('expires by the end of matchday 2026-11-01', str(caught.exception))
        takes = self.built(take(), campaign=week('live'))
        self.assertEqual(proposal(takes, '2026-11-02T06:00:00Z', mode='live')['expires_at'], '2026-11-02T06:00:00Z')


if __name__ == '__main__':
    unittest.main()
