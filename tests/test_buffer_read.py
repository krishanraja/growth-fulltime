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


def example():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def write(folder, data):
    (Path(folder) / 'buffer-channels.json').write_text(json.dumps(data), encoding='utf-8')


def pack():
    return {'run_id': 'fulltime:2026-11-01:g2', 'matchday': '2026-11-01', 'items': [
        {'creative_id': TAKE, 'channel': 'tiktok', 'channel_ref': 'fulltime-tiktok',
         'link': growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', TAKE)},
        {'creative_id': REEL, 'channel': 'ig_reels', 'channel_ref': 'fulltime-ig-reels',
         'link': growth.tracked('https://fulltime.fm/?drop=drop-full&pundit=doomer', REEL)}]}


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


class QueryTests(unittest.TestCase):
    def test_query_names_only_allowlisted_channels(self):
        params = query(example())
        self.assertEqual(params['channelIds'], sorted({TIKTOK, INSTAGRAM, YOUTUBE, '000000000000000000000004',
                                                       '000000000000000000000005', '000000000000000000000006'}))
        self.assertEqual(params['status'], ['sent'])
        self.assertEqual(params['organizationId'], '000000000000000000000000')
        self.assertEqual(set(params), {'channelIds', 'status', 'first', 'organizationId'})

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
    def test_a_post_matches_by_tracked_link_or_creative_id(self):
        link = pack()['items'][0]['link']
        posts = [post(TIKTOK, 'The Doomer has seen this before. ' + link),
                 post(INSTAGRAM, f'Ref {REEL}', permalink='https://www.instagram.example/reel/1', sentAt=None,
                      dueAt='2026-11-01T19:00:00Z')]
        found = receipts(posts, pack(), example())
        self.assertEqual(found, [
            {'creative_id': TAKE, 'channel': 'tiktok', 'permalink': 'https://www.tiktok.example/@fulltime/video/1',
             'published_at': '2026-11-01T18:31:00Z'},
            {'creative_id': REEL, 'channel': 'ig_reels', 'permalink': 'https://www.instagram.example/reel/1',
             'published_at': '2026-11-01T19:00:00Z'}])

    def test_external_link_is_read_when_there_is_no_permalink(self):
        item = post(TIKTOK, TAKE)
        del item['permalink']
        item['externalLink'] = 'https://www.tiktok.example/@fulltime/video/2'
        self.assertEqual(receipts([item], pack(), example())[0]['permalink'], item['externalLink'])

    def test_a_personal_channel_post_is_ignored_even_with_a_creative_id(self):
        guarded = Untouchable(post(PERSONAL, f'{TAKE} {REEL}'))
        self.assertEqual(receipts([guarded], pack(), example()), [])
        other = Untouchable(post('ffffffffffffffffffffffff', TAKE))
        self.assertEqual(receipts([guarded, other, 'not a post', None], pack(), example()), [])

    def test_only_sent_posts_with_an_https_permalink_count(self):
        for name, item in {'draft': post(TIKTOK, TAKE, status='draft'),
                           'sending': post(TIKTOK, TAKE, status='sending'),
                           'error': post(TIKTOK, TAKE, status='error'),
                           'http': post(TIKTOK, TAKE, permalink='http://www.tiktok.example/v/1'),
                           'no link': post(TIKTOK, TAKE, permalink=None),
                           'userinfo': post(TIKTOK, TAKE, permalink='https://user:pass@localhost/v/1'),
                           'token': post(TIKTOK, TAKE, permalink='https://tiktok.example/v/1?token=abc')}.items():
            with self.subTest(case=name):
                self.assertEqual(receipts([item], pack(), example()), [])

    def test_a_post_counts_only_on_its_items_own_channel(self):
        self.assertEqual(receipts([post(YOUTUBE, TAKE)], pack(), example()), [])
        crossed = pack()
        crossed['items'][0]['channel_ref'] = 'fulltime-ig-reels'
        self.assertEqual(receipts([post(INSTAGRAM, TAKE)], crossed, example()), [])
        self.assertEqual(receipts([post(TIKTOK, TAKE)], 'not a pack', example()), [])

    def test_a_creative_id_must_appear_whole(self):
        longer = TAKE.replace('C01', 'C011')
        self.assertEqual(receipts([post(TIKTOK, 'X' + TAKE), post(TIKTOK, longer)], pack(), example()), [])
        self.assertEqual(len(receipts([post(TIKTOK, f'(utm_content={TAKE})')], pack(), example())), 1)

    def test_one_receipt_per_item(self):
        found = receipts([post(TIKTOK, TAKE), post(TIKTOK, TAKE, permalink='https://www.tiktok.example/v/9')],
                         pack(), example())
        self.assertEqual([r['permalink'] for r in found], ['https://www.tiktok.example/@fulltime/video/1'])

    def test_a_receipt_is_accepted_by_history_mark(self):
        from engine.records import History
        found = receipts([post(TIKTOK, TAKE)], pack(), example())[0]
        with tempfile.TemporaryDirectory() as folder:
            history = History(folder)
            history.checkpoint({'venture': 'fulltime', 'pack_date': '2026-11-01', 'kind': 'daily',
                                'items': [{'platform': 'tiktok', 'creative_id': TAKE, 'text': 'An AI Pundit take.'}]})
            history.mark(found['creative_id'], 'published', url=found['permalink'], human_confirmed=True)
            self.assertEqual(history.read()['creatives'][TAKE]['publication']['url'], found['permalink'])

    def test_inputs_are_not_changed(self):
        posts, items, allow = [post(TIKTOK, TAKE)], pack(), example()
        before = copy.deepcopy((posts, items, allow))
        receipts(posts, items, allow)
        self.assertEqual((posts, items, allow), before)


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
