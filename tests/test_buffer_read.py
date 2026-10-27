import copy
import json
from pathlib import Path
import tempfile
import unittest

import growth
from engine import buffer_read
from engine.buffer_read import allowlist_errors, load_allowlist, query, receipts

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / 'examples' / 'buffer-channels.example.json'
TIKTOK, INSTAGRAM, YOUTUBE = '000000000000000000000001', '000000000000000000000002', '000000000000000000000003'
PERSONAL = '999999999999999999999999'
TAKE = 'TT_CLASH_CLIP_C01_H01_V1_20261101'
REEL = 'IG_CLASH_SHORT_C01_H01_V1_20261101'
SECOND = 'TT_CLASH_CLIP_C02_H01_V1_20261101'
SAID = 'The AI Pundit Doomer has seen this before.'
REEL_SAID = 'The AI Pundit Zen saw it coming.'
TAGS = ['#football', '#aipundit']


def example():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def write(folder, data):
    (Path(folder) / 'buffer-channels.json').write_text(json.dumps(data), encoding='utf-8')


def item(creative_id, channel, ref, caption):
    return {'creative_id': creative_id, 'channel': channel, 'channel_ref': ref, 'caption': caption,
            'hashtags': list(TAGS), 'link': growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer',
                                                           creative_id)}


def pack():
    return {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01', 'items': [
        item(TAKE, 'tiktok', 'fulltime-tiktok', SAID), item(REEL, 'ig_reels', 'fulltime-ig-reels', REEL_SAID)]}


def words(caption=SAID):
    """The words that go out, as pack._copy_errors checks them: the caption and its hashtags."""
    return caption + '\n\n' + ' '.join(TAGS)


def records(data=None):
    """Buffer's own channel records for the allowlist, as list_channels returns them."""
    entries = (data or example())['channels'].values()
    found = {e['buffer_channel_id']: e for e in entries if e['buffer_channel_id']}
    return [{'id': i, 'service': e['service'], 'name': e.get('buffer_name', 'unnamed'), 'displayName': 'Full Time'}
            for i, e in sorted(found.items())]


def post(channel, text, status='sent', permalink='https://www.tiktok.example/@fulltime/video/1', **extra):
    return {'channelId': channel, 'text': text, 'status': status, 'sentAt': '2026-11-01T18:31:00Z',
            'permalink': permalink, **extra}


class Untouchable(dict):
    """A post whose fields other than channelId fail the test if anything reads them."""
    def _guard(self, key):
        if key != 'channelId':
            raise AssertionError(f'read {key} from a post outside the allowlist')

    def get(self, key, default=None):
        self._guard(key)
        return dict.get(self, key, default)

    def __getitem__(self, key):
        self._guard(key)
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        self._guard(key)
        return dict.__contains__(self, key)

    def __iter__(self):
        raise AssertionError('iterated a post outside the allowlist')

    def keys(self):
        raise AssertionError('listed a post outside the allowlist')

    def items(self):
        raise AssertionError('listed a post outside the allowlist')

    def values(self):
        raise AssertionError('listed a post outside the allowlist')


class AllowlistTests(unittest.TestCase):
    def test_the_example_loads_and_is_synthetic(self):
        with tempfile.TemporaryDirectory() as folder:
            write(folder, example())
            data = load_allowlist(folder)
        self.assertEqual(data['product'], 'fulltime')
        ids = [e['buffer_channel_id'] for e in data['channels'].values() if e['buffer_channel_id']]
        self.assertTrue(all(set(i) <= set('0123456789') and i.startswith('0' * 20) for i in ids))
        self.assertTrue(all(e['account_scope'] == 'brand' for e in data['channels'].values()))

    def test_a_missing_file_is_refused_with_the_fix(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError) as caught:
                load_allowlist(folder)
        self.assertIn('examples/buffer-channels.example.json', str(caught.exception))

    def test_invalid_json_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'buffer-channels.json').write_text('{', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_allowlist(folder)

    def test_a_personal_or_non_brand_entry_is_refused(self):
        for scope in ('personal', 'makeyourmindup', None):
            data = example()
            data['channels']['fulltime-tiktok']['account_scope'] = scope
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as folder:
                write(folder, data)
                with self.assertRaises(ValueError) as caught:
                    load_allowlist(folder)
                self.assertIn('not a Full Time brand channel', str(caught.exception))

    def test_another_product_is_refused(self):
        data = {**example(), 'product': 'makeyourmindup'}
        self.assertTrue(any('product "fulltime"' in e for e in allowlist_errors(data)))
        data = example()
        del data['product']
        self.assertTrue(any('product' in e for e in allowlist_errors(data)))

    def test_entries_are_strict(self):
        cases = {
            'raw ID as ref': lambda d: d['channels'].update({TIKTOK: d['channels'].pop('fulltime-tiktok')}),
            'unknown channel': lambda d: d['channels']['fulltime-tiktok'].update(channel='myspace'),
            'wrong service': lambda d: d['channels']['fulltime-tiktok'].update(service='instagram'),
            'bad Buffer ID': lambda d: d['channels']['fulltime-tiktok'].update(buffer_channel_id='12345'),
            'extra field': lambda d: d['channels']['fulltime-tiktok'].update(password='x'),
            'no identity': lambda d: d['channels']['fulltime-tiktok'].update(identity_ref=''),
            'extra top field': lambda d: d.update(personal={}),
            'no channels': lambda d: d.update(channels={}),
            'bad organisation': lambda d: d.update(organization_id='org'),
        }
        for name, change in cases.items():
            data = example()
            change(data)
            with self.subTest(case=name):
                self.assertTrue(allowlist_errors(data))
        self.assertEqual(allowlist_errors(example()), [])

    def test_a_channel_with_no_buffer_id_still_needs_its_own_service(self):
        data = example()
        data['channels']['fulltime-whatsapp-channel']['service'] = 'tiktok'
        self.assertTrue(any('posts through tiktok' in e for e in allowlist_errors(data)))

    def test_buffer_name_is_optional_text(self):
        data = example()
        del data['channels']['fulltime-tiktok']['buffer_name']
        self.assertEqual(allowlist_errors(data), [])
        for bad in ('', '  ', 3, 'two\nlines', 'x' * 101):
            data = example()
            data['channels']['fulltime-tiktok']['buffer_name'] = bad
            with self.subTest(bad=bad):
                self.assertTrue(any('buffer_name' in e for e in allowlist_errors(data)))

    def test_one_buffer_id_is_never_filed_under_two_services_or_identities(self):
        shared = example()
        shared['channels']['fulltime-yt-shorts']['buffer_channel_id'] = TIKTOK
        errors = allowlist_errors(shared)
        self.assertTrue(any('share one Buffer channel ID under different services' in e for e in errors), errors)
        self.assertTrue(all(TIKTOK not in e for e in errors))
        with self.assertRaises(ValueError):
            query(shared)          # before the fix, query dropped the real Shorts ID and kept going
        other = example()
        other['channels']['fulltime-ig-feed']['identity_ref'] = 'fulltime-other-instagram'
        self.assertTrue(any('different brand identities' in e for e in allowlist_errors(other)))
        named = example()
        named['channels']['fulltime-ig-feed']['buffer_name'] = 'fulltime-synthetic-other'
        self.assertTrue(any('different Buffer names' in e for e in allowlist_errors(named)))
        # Reels and feed post through one Instagram channel: sharing its ID is fine.
        self.assertEqual(example()['channels']['fulltime-ig-reels']['buffer_channel_id'],
                         example()['channels']['fulltime-ig-feed']['buffer_channel_id'])
        self.assertEqual(allowlist_errors(example()), [])


class QueryTests(unittest.TestCase):
    def test_query_names_only_allowlisted_channels(self):
        params = query(example())
        self.assertEqual(params['channelIds'], sorted({TIKTOK, INSTAGRAM, YOUTUBE, '000000000000000000000004',
                                                       '000000000000000000000005', '000000000000000000000006'}))
        self.assertEqual(params['status'], ['sent'])
        self.assertEqual(params['organizationId'], '000000000000000000000000')
        self.assertEqual(set(params), {'channelIds', 'status', 'first', 'organizationId'})

    def test_query_needs_the_organisation_list_posts_requires(self):
        data = example()
        del data['organization_id']
        self.assertEqual(allowlist_errors(data), [])      # the pack and audience checks need no organisation
        with self.assertRaises(ValueError) as caught:
            query(data)
        self.assertIn('organization_id', str(caught.exception))

    def test_an_organisation_wide_listing_is_refused(self):
        data = example()
        data['channels'] = {'fulltime-whatsapp-channel': data['channels']['fulltime-whatsapp-channel']}
        with self.assertRaises(ValueError) as caught:
            query(data)
        self.assertIn('organisation-wide', str(caught.exception))
        bad = example()
        bad['channels']['fulltime-tiktok']['account_scope'] = 'personal'
        with self.assertRaises(ValueError):
            query(bad)


class ReceiptTests(unittest.TestCase):
    def test_a_post_matches_by_its_caption_with_the_link_or_id_as_evidence(self):
        link = pack()['items'][0]['link']
        posts = [post(TIKTOK, words() + '\n' + link),
                 post(INSTAGRAM, words(REEL_SAID) + f' Ref {REEL}', permalink='https://www.instagram.example/reel/1',
                      sentAt=None, dueAt='2026-11-01T19:00:00Z')]
        found = receipts(posts, pack(), example())
        self.assertEqual(found, [
            {'creative_id': TAKE, 'channel': 'tiktok', 'permalink': 'https://www.tiktok.example/@fulltime/video/1',
             'published_at': '2026-11-01T18:31:00Z'},
            {'creative_id': REEL, 'channel': 'ig_reels', 'permalink': 'https://www.instagram.example/reel/1',
             'published_at': '2026-11-01T19:00:00Z'}])

    def test_external_link_is_read_when_there_is_no_permalink(self):
        item = post(TIKTOK, words())
        del item['permalink']
        item['externalLink'] = 'https://www.tiktok.example/@fulltime/video/2'
        self.assertEqual(receipts([item], pack(), example())[0]['permalink'], item['externalLink'])

    def test_a_personal_channel_post_is_ignored_even_with_a_creative_id(self):
        guarded = Untouchable(post(PERSONAL, f'{words()} {TAKE} {REEL}'))
        self.assertEqual(receipts([guarded], pack(), example()), [])
        other = Untouchable(post('ffffffffffffffffffffffff', words() + ' ' + TAKE))
        self.assertEqual(receipts([guarded, other, 'not a post', None], pack(), example()), [])

    def test_only_sent_posts_with_an_https_permalink_count(self):
        text = words()
        for name, item in {'draft': post(TIKTOK, text, status='draft'),
                           'sending': post(TIKTOK, text, status='sending'),
                           'error': post(TIKTOK, text, status='error'),
                           'http': post(TIKTOK, text, permalink='http://www.tiktok.example/v/1'),
                           'no link': post(TIKTOK, text, permalink=None),
                           'userinfo': post(TIKTOK, text, permalink='https://user:pass@localhost/v/1'),
                           'token': post(TIKTOK, text, permalink='https://tiktok.example/v/1?token=abc')}.items():
            with self.subTest(case=name):
                self.assertEqual(receipts([item], pack(), example()), [])

    def test_a_post_counts_only_on_its_items_own_channel(self):
        self.assertEqual(receipts([post(YOUTUBE, words())], pack(), example()), [])
        crossed = pack()
        crossed['items'][0]['channel_ref'] = 'fulltime-ig-reels'
        self.assertEqual(receipts([post(INSTAGRAM, words())], crossed, example()), [])
        self.assertEqual(receipts([post(TIKTOK, words())], 'not a pack', example()), [])

    def test_a_creative_id_must_appear_whole(self):
        # Two TikTok items with one caption: only a whole creative ID settles which one went out.
        twins = pack()
        twins['items'].append(item(SECOND, 'tiktok', 'fulltime-tiktok', SAID))
        longer = TAKE.replace('C01', 'C011')
        self.assertEqual(receipts([post(TIKTOK, words() + ' X' + TAKE), post(TIKTOK, words() + ' ' + longer)],
                                  twins, example()), [])
        found = receipts([post(TIKTOK, words() + f' (utm_content={TAKE})')], twins, example())
        self.assertEqual([r['creative_id'] for r in found], [TAKE])

    def test_one_receipt_per_item(self):
        found = receipts([post(TIKTOK, words()), post(TIKTOK, words(), permalink='https://www.tiktok.example/v/9')],
                         pack(), example())
        self.assertEqual([r['permalink'] for r in found], ['https://www.tiktok.example/@fulltime/video/1'])

    def test_a_receipt_is_accepted_by_history_mark(self):
        from engine.records import History
        found = receipts([post(TIKTOK, words())], pack(), example())[0]
        with tempfile.TemporaryDirectory() as folder:
            history = History(folder)
            history.checkpoint({'venture': 'fulltime', 'pack_date': '2026-11-01', 'kind': 'daily',
                                'items': [{'platform': 'tiktok', 'creative_id': TAKE, 'text': 'An AI Pundit take.'}]})
            history.mark(found['creative_id'], 'published', url=found['permalink'], human_confirmed=True)
            self.assertEqual(history.read()['creatives'][TAKE]['publication']['url'], found['permalink'])

    def test_inputs_are_not_changed(self):
        posts, items, allow, known = [post(TIKTOK, words())], pack(), example(), records()
        before = copy.deepcopy((posts, items, allow, known))
        receipts(posts, items, allow, known)
        self.assertEqual((posts, items, allow, known), before)


class CaptionTests(unittest.TestCase):
    """The plan's readback: the post carries the pack's approved caption (section 3, row 7)."""

    def test_the_approved_words_alone_give_a_receipt(self):
        # TikTok, Reels and Shorts posts carry no link, and Buffer may shorten one to buff.ly.
        for text in (words(), words() + ' https://buff.ly/3xYz', '  ' + SAID.replace(' ', '\n') + '\u00a0#football'):
            with self.subTest(text=text):
                self.assertEqual([r['creative_id'] for r in receipts([post(TIKTOK, text)], pack(), example())], [TAKE])

    def test_other_words_never_count_even_with_the_link_or_the_id(self):
        link = pack()['items'][0]['link']
        for text in ('Totally different words, never reviewed. ' + link, 'other words ' + TAKE,
                     SAID.replace('Doomer', 'Gaffer') + ' ' + TAKE, SAID.upper(), SAID[:-1] + 'n it all.'):
            with self.subTest(text=text):
                self.assertEqual(receipts([post(TIKTOK, text)], pack(), example()), [])

    def test_a_caption_must_appear_whole(self):
        short = pack()
        short['items'][0]['caption'] = 'AI Pundit Doomer: gone'
        self.assertEqual(receipts([post(TIKTOK, 'The AI Pundit Doomer: goners')], short, example()), [])
        self.assertEqual(len(receipts([post(TIKTOK, 'AI Pundit Doomer: gone. #football')], short, example())), 1)
        self.assertEqual(receipts([post(TIKTOK, SAID)], {'items': [dict(pack()['items'][0], caption='')]},
                                  example()), [])

    def test_one_post_is_the_receipt_for_one_item_at_most(self):
        both = pack()
        both['items'].append(item(SECOND, 'tiktok', 'fulltime-tiktok', 'The AI Pundit Doomer saw it twice.'))
        links = ' '.join(i['link'] for i in both['items'] if i['channel'] == 'tiktok')
        self.assertEqual(receipts([post(TIKTOK, words() + ' ' + links)], both, example()), [])
        two = words() + ' ' + words('The AI Pundit Doomer saw it twice.')
        self.assertEqual(receipts([post(TIKTOK, two)], both, example()), [])
        named = receipts([post(TIKTOK, two + ' ' + both['items'][2]['link'])], both, example())
        self.assertEqual([r['creative_id'] for r in named], [SECOND])

    def test_another_items_link_or_id_is_never_this_items_receipt(self):
        self.assertEqual(receipts([post(TIKTOK, words() + ' ' + REEL)], pack(), example()), [])
        self.assertEqual(receipts([post(TIKTOK, words() + ' ' + pack()['items'][1]['link'])], pack(), example()), [])

    def test_a_post_on_another_service_is_dropped_before_its_text_is_read(self):
        class Unread(dict):
            def get(self, key, default=None):
                if key == 'text':
                    raise AssertionError('read the text of a post on another service')
                return dict.get(self, key, default)
        wrong = Unread(post(TIKTOK, words(), channelService='instagram', permalink='https://www.instagram.example/p/x'))
        self.assertEqual(receipts([wrong], pack(), example()), [])
        nested = Unread(post(TIKTOK, words()), channel={'service': 'youtube'})
        self.assertEqual(receipts([nested], pack(), example()), [])
        right = post(TIKTOK, words(), channelService='tiktok')
        self.assertEqual(len(receipts([right], pack(), example())), 1)


class ChannelRecordTests(unittest.TestCase):
    """Buffer's own channel records (list_channels or get_channel) checked against the allowlist."""

    def test_matching_records_pass_in_every_shape_buffer_returns(self):
        listed = records()
        for shape in (listed, {'channels': listed}):
            with self.subTest(shape=type(shape).__name__):
                self.assertEqual(query(example(), shape), query(example()))
                self.assertEqual(len(receipts([post(TIKTOK, words())], pack(), example(), shape)), 1)
        one = example()
        one['channels'] = {'fulltime-tiktok': one['channels']['fulltime-tiktok']}
        for shape in (listed[0], {'channel': listed[0]}):
            self.assertEqual(query(one, shape)['channelIds'], [TIKTOK])

    def test_an_id_buffer_does_not_list_is_refused(self):
        known = [r for r in records() if r['id'] != TIKTOK]
        for call in (lambda: query(example(), known),
                     lambda: receipts([post(TIKTOK, words())], pack(), example(), known)):
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertIn('"fulltime-tiktok" is not among', str(caught.exception))

    def test_a_personal_id_filed_as_the_brand_channel_is_refused(self):
        data = example()
        data['channels']['fulltime-tiktok']['buffer_channel_id'] = PERSONAL
        self.assertEqual(allowlist_errors(data), [])         # the file alone cannot tell
        known = [r for r in records() if r['id'] != TIKTOK]
        wrong_service = known + [{'id': PERSONAL, 'service': 'instagram', 'name': 'personal-synthetic'}]
        with self.assertRaisesRegex(ValueError, 'is tiktok in the allowlist, but Buffer says instagram'):
            query(data, wrong_service)
        wrong_name = known + [{'id': PERSONAL, 'service': 'tiktok', 'name': 'personal-synthetic'}]
        with self.assertRaisesRegex(ValueError, 'Buffer names it "personal-synthetic"'):
            receipts([post(PERSONAL, words())], pack(), data, wrong_name)
        self.assertEqual(len(query(example(), [dict(r, name='@' + r['name'].upper()) for r in records()])
                             ['channelIds']), 6)          # a handle's case and @ are not a mismatch

    def test_malformed_records_are_refused(self):
        for bad in ([], {}, 'channels', [{'id': 'abc', 'service': 'tiktok'}], [{'id': TIKTOK}],
                    records() + [{'id': TIKTOK, 'service': 'youtube'}]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    query(example(), bad)


class ReadOnlyTests(unittest.TestCase):
    def test_the_module_has_no_write_capability(self):
        source = Path(buffer_read.__file__).read_text(encoding='utf-8')
        for word in ('create_post', 'edit_post', 'delete_post', 'execute_mutation', 'schedule'):
            with self.subTest(word=word):
                self.assertNotIn(word, source)
        for word in ('urllib.request', 'http.client', 'import socket', 'subprocess', 'requests'):
            with self.subTest(word=word):
                self.assertNotIn(word, source)
        self.assertEqual(sorted(n for n in dir(buffer_read) if not n.startswith('_') and callable(getattr(buffer_read, n))
                                and getattr(getattr(buffer_read, n), '__module__', '') == 'engine.buffer_read'),
                         ['allowlist_errors', 'channel_ids', 'load_allowlist', 'query', 'receipts'])


if __name__ == '__main__':
    unittest.main()
