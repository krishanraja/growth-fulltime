"""The Librarian: the fixed tree, one name pattern, INDEX.csv, reconcile, filing, archiving
and the numbered-part backups. Synthetic fixtures only; every file written lives in a
temporary folder, and nothing touches Drive or the network."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

import growth
from engine import library

ROOT = Path(growth.HERE)
EXAMPLE = ROOT / 'examples' / 'library-listing.example.json'
WEEK = '2026-W44'
MATCH = '03_Runs/2026-W44/2026-10-31_reds-blues'
CLIP = MATCH + '/2026-10-31_take_clip_zen_reds-blues_tiktok_TT_CLASH_CLIP_C01_H01_V1_20261031.mp4'
SPEC_V1 = '01_Strategy/2026-W44/2026-W44_campaign-spec_v1.json'
SHA_A, SHA_B, SHA_C = 'a' * 64, 'b' * 64, 'c' * 64


def example():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def row(path, sha=SHA_A, size=10, status='draft', kind='note'):
    plan = library.file_plan([], path, sha, size, kind, 'repo commit 0000000', status=status)
    return plan['row']


class Names(unittest.TestCase):
    def test_the_tree_and_index_columns_are_fixed(self):
        self.assertEqual(library.TREE, ('00_START-HERE', '01_Strategy', '02_Formats', '03_Runs', '04_Learning',
                                        '05_Brand-Kit', '06_Reference', '99_Archive'))
        self.assertEqual(library.INDEX_FIELDS, ('path', 'kind', 'week', 'match', 'format', 'pundit', 'channel',
                                                'status', 'sha256', 'bytes', 'drive_file_id', 'source'))
        self.assertEqual(library.ADOPTED, '06_Reference/creative-handoff/')
        self.assertEqual(library.FORMATS, ('take_clip', 'morning_card', 'row', 'match_ad'))

    def test_every_allowed_layout_files_cleanly(self):
        good = [
            '00_START-HERE/START-HERE.md', '00_START-HERE/INDEX.csv',
            SPEC_V1, '01_Strategy/2026-W44/2026-W44_brief-share-attribution_v12.md',
            '02_Formats/take_clip/unlocked/lock-card.md', '02_Formats/row/v3/reference_cut-01.mp4',
            '02_Formats/match_ad/' + 'f' * 64 + '/lock-card.md',
            '02_Formats/take_clip/v1/2026-10-31_take_clip_zen_reds-blues_tiktok_TT_CLASH_CLIP_C01_H01_V1_20261031.mp4',
            CLIP, MATCH + '/pack.json', MATCH + '/review.json',
            MATCH + '/2026-10-31_row_zen-doomer_reds-blues_yt_shorts_YT_CLASH_SHORT_C01_H02_V1_20261031.mp4',
            '04_Learning/register.csv', '04_Learning/2026-W44/2026-W44_learning-report_v1.md',
            '05_Brand-Kit/2026-W44_canva-kit-receipt_v1.json',
            '06_Reference/baseline/2026-10-27_baseline_v1.json', '06_Reference/rulings/2026-10-27_rulings_v2.json',
            '06_Reference/backups/2026-10-27/fulltime-growth-backup-2026-10-27.zip.part01',
            '06_Reference/backups/2026-10-27/fulltime-growth-backup-2026-10-27.json',
            '99_Archive/2026-W45/' + SPEC_V1,
        ]
        for path in good:
            with self.subTest(path=path):
                self.assertEqual(library.name_errors(path), [])

    def test_each_break_names_the_rule_it_breaks(self):
        tree, names, depth = 'rule 2, fixed tree', 'rule 3, one name pattern', 'rule 2, depth'
        cases = {
            'Plan.md': tree,
            'New folder/plan.md': tree,
            '01_Strategy/plan_v1.md': tree,
            '01_Strategy/drafts/2026-W44_plan_v1.md': tree,
            '01_Strategy/2026-W54/2026-W54_plan_v1.md': tree,
            '01_Strategy/2026-W44/2026-W44_Campaign Spec_v1.json': names,
            '01_Strategy/2026-W44/2026-W45_campaign-spec_v1.json': names,
            '01_Strategy/2026-W44/2026-W44_campaign-spec.json': names,
            '01_Strategy/2026-W44/2026-W44_campaign-spec_v1.JSON': names,
            '02_Formats/reel/v1/lock-card.md': tree,
            '02_Formats/take_clip/latest/lock-card.md': tree,
            '02_Formats/take_clip/v1/Lock Card.md': names,
            '02_Formats/row/v1/2026-10-31_take_clip_zen_reds-blues_tiktok_TT_CLASH_CLIP_C01_H01_V1_20261031.mp4':
                names,
            '03_Runs/2026-W44/2026-11-02_reds-blues/pack.json': tree,
            '03_Runs/2026-W44/reds-blues/pack.json': tree,
            '03_Runs/2026-W44/2026-10-31_reds-blues.mp4': tree,
            MATCH + '/notes.txt': names,
            MATCH + '/2026-10-31_take_clip_zen_reds-blues_tiktok_tt_clash_clip_c01_h01_v1_20261031.mp4': names,
            MATCH + '/2026-10-31_take_clip_zen_reds-blues_tiktok_TT_CLASH_CLIP_C1_H01_V1_20261031.mp4': names,
            MATCH + '/2026-10-31_take_clip_zen_reds-blues_ig_reels_TT_CLASH_CLIP_C01_H01_V1_20261031.mp4': names,
            MATCH + '/2026-10-31_take_clip_zen_greens-blues_tiktok_TT_CLASH_CLIP_C01_H01_V1_20261031.mp4': names,
            MATCH + '/2026-10-31_Take_Clip_zen_reds-blues_tiktok_TT_CLASH_CLIP_C01_H01_V1_20261031.mp4': names,
            '04_Learning/notes.csv': names,
            '04_Learning/2026-W44/2026-W43_learning-report_v1.md': names,
            '05_Brand-Kit/receipt.json': names,
            '05_Brand-Kit/2026-W44/2026-W44_receipt_v1.json': tree,
            '06_Reference/notes.md': tree,
            '06_Reference/misc/notes.md': tree,
            '06_Reference/baseline/2026-10-27_rulings_v1.json': names,
            '06_Reference/backups/2026-10-27/Backup FINAL.zip': names,
            '06_Reference/backups/latest/backup.json': tree,
            '00_START-HERE/README.md': names,
            '00_START-HERE/old/START-HERE.md': tree,
            '99_Archive/plan.md': tree,
            '99_Archive/2026-W44/plan.md': tree,
            '99_Archive/2026-W44/99_Archive/2026-W43/' + SPEC_V1: tree,
            '02_Formats/take_clip/v1/a/b/lock-card.md': depth,
        }
        for path, rule in cases.items():
            with self.subTest(path=path):
                errors = library.name_errors(path)
                self.assertTrue(errors, path)
                self.assertIn(rule, ' '.join(errors))
                self.assertTrue(all(e.startswith(path) for e in errors))

    def test_unusable_paths_are_refused_in_plain_words(self):
        for path in ('', '/01_Strategy/x.md', '01_Strategy\\2026-W44\\x.md', '01_Strategy//x.md',
                     '../01_Strategy/x.md', '01_Strategy/2026-W44/a\nb.md', None):
            with self.subTest(path=path):
                self.assertTrue(library.name_errors(path))

    def test_adopted_handoff_files_keep_their_original_names(self):
        adopted = ['00-START-HERE-FULLTIME-CREATIVES-2026-10-27.md', 'assemble_fulltime_handoff.py',
                   'Synthetic Handoff Notes (final).md', 'fulltime-creative-system-2026-10-27-complete.zip.part01']
        for name in adopted:
            with self.subTest(name=name):
                self.assertEqual(library.name_errors(library.ADOPTED + '2026-10-27/' + name), [])
        for elsewhere in ('01_Strategy/2026-W44/', '06_Reference/backups/2026-10-27/', MATCH + '/'):
            with self.subTest(elsewhere=elsewhere):
                self.assertTrue(library.name_errors(elsewhere + adopted[0]))
        self.assertTrue(library.name_errors(library.ADOPTED + 'latest/' + adopted[0]))
        self.assertTrue(library.name_errors(library.ADOPTED + '2026-10-27/sub/' + adopted[0]))
        self.assertTrue(library.name_errors(library.ADOPTED + adopted[0]))

    def test_an_archived_copy_keeps_its_path_and_its_rules(self):
        self.assertEqual(library.name_errors('99_Archive/2026-W45/' + CLIP), [])
        self.assertEqual(library.folder_errors('99_Archive/2026-W45/' + MATCH), [])
        self.assertTrue(library.name_errors('99_Archive/2026-W45/01_Strategy/2026-W44/Plan.md'))
        self.assertTrue(library.name_errors('99_Archive/latest/' + SPEC_V1))

    def test_folders_outside_the_tree_are_named(self):
        for folder in ('00_START-HERE', '01_Strategy/2026-W44', '02_Formats/take_clip/v2', MATCH, MATCH + '/',
                       '04_Learning/2026-W44', '06_Reference/creative-handoff/2026-10-27', '99_Archive/2026-W45'):
            with self.subTest(folder=folder):
                self.assertEqual(library.folder_errors(folder), [])
        for folder in ('New folder', 'Growth', '01_Strategy/drafts', '03_Runs/2026-W44/reds-blues',
                       '05_Brand-Kit/templates', '06_Reference/backups/latest', '00_START-HERE/old'):
            with self.subTest(folder=folder):
                self.assertIn('rule 2', ' '.join(library.folder_errors(folder)))


class Index(unittest.TestCase):
    def test_written_index_has_the_exact_header_lf_endings_and_sorted_rows(self):
        rows = example()['index']
        text = library.write_index(list(reversed(rows)))
        self.assertTrue(text.startswith(','.join(library.INDEX_FIELDS) + '\n'))
        self.assertNotIn('\r', text)
        self.assertTrue(text.endswith('\n'))
        read = library.read_index(text)
        self.assertEqual([r['path'] for r in read], sorted(r['path'] for r in rows))
        self.assertEqual(read, sorted(rows, key=lambda r: r['path']))
        self.assertEqual(library.write_index(read), text)

    def test_a_spreadsheet_saved_copy_still_reads(self):
        rows = example()['index']
        text = library.write_index(rows)
        self.assertEqual(library.read_index('\ufeff' + text.replace('\n', '\r\n')), library.read_index(text))

    def test_the_header_must_be_exact(self):
        fields = list(library.INDEX_FIELDS)
        for header in (fields[:-1], fields[::-1], fields + ['note'], [f.upper() for f in fields]):
            with self.subTest(header=header):
                with self.assertRaisesRegex(ValueError, 'header'):
                    library.read_index(','.join(header) + '\n')
        with self.assertRaisesRegex(ValueError, 'header'):
            library.read_index('')

    def test_bad_rows_are_refused(self):
        good = library.write_index([row(SPEC_V1)])
        header, line = good.splitlines()
        with self.assertRaisesRegex(ValueError, 'more than one row'):
            library.read_index(good + line + '\n')
        with self.assertRaisesRegex(ValueError, 'fields'):
            library.read_index(header + '\n' + line + ',extra\n')
        for key, value in (('sha256', 'ABC'), ('status', 'final'), ('bytes', '1.5'), ('week', '2026-44'),
                           ('format', 'reel'), ('channel', 'myspace'), ('kind', '')):
            bad = dict(row(SPEC_V1), **{key: value})
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    library.write_index([bad])
        with self.assertRaises(ValueError):
            library.write_index([dict(row(SPEC_V1), note='x')])

    def test_whole_number_bytes_are_written_as_text(self):
        value = dict(row(SPEC_V1), bytes=42)
        self.assertEqual(library.read_index(library.write_index([value]))[0]['bytes'], '42')


class Reconcile(unittest.TestCase):
    def test_the_example_library_is_clean(self):
        data = example()
        result = library.reconcile(data['listing'], data['index'])
        self.assertTrue(result['clean'], result)
        self.assertEqual(len(result['pending_hashes']), 1)
        self.assertIsNone(library.hold(result))
        self.assertTrue(all(r['drive_file_id'] == '' for r in data['index']))

    def test_sprawl_is_reported_and_holds_the_report(self):
        data = example()
        listing, rows = data['listing'], data['index']
        listing += [{'path': 'New folder', 'bytes': None, 'is_folder': True},
                    {'path': 'New folder/campaign notes.docx', 'bytes': 120, 'is_folder': False},
                    {'path': '01_Strategy/2026-W44/Plan FINAL.docx', 'bytes': 300, 'is_folder': False},
                    {'path': '01_Strategy/2026-W44/2026-W44_campaign-spec_v2.json', 'bytes': 4100,
                     'is_folder': False}]
        first = next(r for r in rows if r['path'] == SPEC_V1)
        rows.append(dict(first, path='01_Strategy/2026-W44/2026-W44_campaign-spec_v2.json'))
        result = library.reconcile(listing, rows)
        self.assertFalse(result['clean'])
        self.assertIn('New folder', result['outside_tree'])
        self.assertIn('New folder/campaign notes.docx', result['outside_tree'])
        self.assertEqual([m['path'] for m in result['misnamed']], ['01_Strategy/2026-W44/Plan FINAL.docx'])
        self.assertIn('rule 3', ' '.join(result['misnamed'][0]['errors']))
        self.assertEqual(result['duplicates'], [{'sha256': first['sha256'], 'paths': [
            SPEC_V1, '01_Strategy/2026-W44/2026-W44_campaign-spec_v2.json']}])
        self.assertEqual(sorted(result['orphans']), ['01_Strategy/2026-W44/Plan FINAL.docx',
                                                     'New folder/campaign notes.docx'])
        entry = library.hold(result)
        self.assertEqual(entry['code'], 'LIBRARY')
        detail = entry['detail']
        for words in ('2 items outside the fixed tree', '1 misnamed file', '2 files with no index row',
                      '1 set of duplicates'):
            self.assertIn(words, detail)
        self.assertEqual(detail.count('.'), 1)
        self.assertTrue(detail.endswith('.'))
        self.assertNotIn('\u2014', detail)

    def test_orphans_missing_rows_and_sizes(self):
        data = example()
        listing, rows = data['listing'], data['index']
        rows = [r for r in rows if r['path'] != SPEC_V1]
        listing = [e for e in listing if e['path'] != '04_Learning/register.csv']
        for entry in listing:
            if entry['path'] == MATCH + '/pack.json':
                entry['bytes'] += 1
        result = library.reconcile(listing, rows)
        self.assertEqual(result['orphans'], [SPEC_V1])
        self.assertEqual(result['missing'], ['04_Learning/register.csv'])
        self.assertEqual(result['size_mismatch'], [{'path': MATCH + '/pack.json', 'listed_bytes': 6101,
                                                    'indexed_bytes': 6100}])
        self.assertFalse(result['clean'])
        self.assertIn('1 index row with no file', library.hold(result)['detail'])

    def test_pending_hashes_alone_keep_the_library_clean(self):
        data = example()
        for r in data['index']:
            r['sha256'] = library.PENDING
        result = library.reconcile(data['listing'], data['index'])
        self.assertTrue(result['clean'])
        self.assertEqual(len(result['pending_hashes']), len(data['index']))
        self.assertEqual(result['duplicates'], [])

    def test_one_path_listed_twice_is_a_duplicate(self):
        data = example()
        copy_of = next(e for e in data['listing'] if e['path'] == SPEC_V1)
        data['listing'].append(dict(copy_of))
        result = library.reconcile(data['listing'], data['index'])
        self.assertEqual(result['duplicates'], [{'sha256': None, 'paths': [SPEC_V1, SPEC_V1]}])
        self.assertFalse(result['clean'])

    def test_index_csv_needs_no_row_of_its_own(self):
        data = example()
        self.assertIn(library.INDEX_PATH, [e['path'] for e in data['listing']])
        self.assertNotIn(library.INDEX_PATH, [r['path'] for r in data['index']])
        self.assertNotIn(library.INDEX_PATH, library.reconcile(data['listing'], data['index'])['orphans'])

    def test_a_file_at_the_top_is_outside_the_tree(self):
        data = example()
        data['listing'].append({'path': 'growth-plan.md', 'bytes': 5, 'is_folder': False})
        self.assertIn('growth-plan.md', library.reconcile(data['listing'], data['index'])['outside_tree'])

    def test_a_malformed_listing_is_refused(self):
        for listing in ({'path': 'x'}, [{'path': 'x', 'bytes': 1}], [{'path': 'x', 'bytes': -1, 'is_folder': False}],
                        [{'path': 3, 'bytes': 1, 'is_folder': False}]):
            with self.subTest(listing=listing):
                with self.assertRaises(ValueError):
                    library.reconcile(listing, [])


class Filing(unittest.TestCase):
    def test_a_new_file_gets_one_row_with_columns_from_its_name(self):
        plan = library.file_plan([], CLIP, SHA_A, 2048, 'instance', 'TT_CLASH_CLIP_C01_H01_V1_20261031')
        self.assertEqual(plan['action'], 'file')
        self.assertEqual(plan['row'], {
            'path': CLIP, 'kind': 'instance', 'week': WEEK, 'match': 'reds-blues', 'format': 'take_clip',
            'pundit': 'zen', 'channel': 'tiktok', 'status': 'draft', 'sha256': SHA_A, 'bytes': '2048',
            'drive_file_id': '', 'source': 'TT_CLASH_CLIP_C01_H01_V1_20261031'})
        self.assertEqual(library.read_index(library.write_index([plan['row']])), [plan['row']])

    def test_the_same_bytes_link_the_copy_already_filed(self):
        rows = [row(SPEC_V1, sha=SHA_A)]
        plan = library.file_plan(rows, '01_Strategy/2026-W44/2026-W44_campaign-spec_v2.json', SHA_A, 10,
                                 'campaign_spec', 'repo commit 0000000')
        self.assertEqual(plan, {'action': 'link_existing', 'path': SPEC_V1})

    def test_a_pending_hash_is_never_taken_as_the_same_bytes(self):
        rows = [row(SPEC_V1, sha=library.PENDING)]
        plan = library.file_plan(rows, '01_Strategy/2026-W44/2026-W44_campaign-spec_v2.json', library.PENDING, 10,
                                 'campaign_spec', 'repo commit 0000000')
        self.assertEqual(plan['action'], 'file')

    def test_a_bad_name_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'rule 3'):
            library.file_plan([], '01_Strategy/2026-W44/Plan FINAL.docx', SHA_A, 10, 'plan', 'x')
        with self.assertRaisesRegex(ValueError, 'rule 2'):
            library.file_plan([], 'New folder/plan.md', SHA_A, 10, 'plan', 'x')

    def test_a_filed_path_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'rule 5'):
            library.file_plan([row(SPEC_V1, sha=SHA_A)], SPEC_V1, SHA_B, 10, 'campaign_spec', 'x')

    def test_bad_columns_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'its name gives week'):
            library.file_plan([], CLIP, SHA_A, 1, 'instance', 'x', week='2026-W45')
        with self.assertRaisesRegex(ValueError, 'unknown index columns'):
            library.file_plan([], CLIP, SHA_A, 1, 'instance', 'x', colour='red')
        with self.assertRaisesRegex(ValueError, 'status'):
            library.file_plan([], CLIP, SHA_A, 1, 'instance', 'x', status='final')
        with self.assertRaisesRegex(ValueError, 'sha256'):
            library.file_plan([], CLIP, 'not-a-hash', 1, 'instance', 'x')
        with self.assertRaisesRegex(ValueError, 'bytes'):
            library.file_plan([], CLIP, SHA_A, -1, 'instance', 'x')
        with self.assertRaisesRegex(ValueError, 'kind and a source'):
            library.file_plan([], CLIP, SHA_A, 1, '', 'x')


class Archive(unittest.TestCase):
    def rows(self):
        return [row(SPEC_V1, sha=SHA_A, status='superseded'), row(CLIP, sha=SHA_B, status='rejected'),
                row(MATCH + '/pack.json', sha=SHA_C, status='posted'),
                row('01_Strategy/2026-W44/2026-W44_campaign-spec_v2.json', sha='d' * 64, status='verdict'),
                row('99_Archive/2026-W43/01_Strategy/2026-W43/2026-W43_campaign-spec_v1.json', sha='e' * 64,
                    status='superseded')]

    def test_archive_plans_only_move_and_never_delete(self):
        plan = library.archive_plan(self.rows(), WEEK)
        self.assertEqual(plan, [{'move': SPEC_V1, 'to': '99_Archive/2026-W44/' + SPEC_V1},
                                {'move': CLIP, 'to': '99_Archive/2026-W44/' + CLIP}])
        for step in plan:
            self.assertEqual(set(step), {'move', 'to'})
            self.assertEqual(library.name_errors(step['to']), [])
        self.assertNotIn('delete', json.dumps(plan))

    def test_the_moved_library_still_reconciles(self):
        rows = self.rows()
        plan = library.archive_plan(rows, WEEK)
        moves = {step['move']: step['to'] for step in plan}
        moved = [dict(r, path=moves.get(r['path'], r['path'])) for r in rows]
        listing = [{'path': r['path'], 'bytes': int(r['bytes']), 'is_folder': False} for r in moved]
        result = library.reconcile(listing, moved)
        self.assertTrue(result['clean'], result)
        self.assertEqual(library.archive_plan(moved, WEEK), [])

    def test_a_move_onto_an_indexed_path_is_refused(self):
        rows = self.rows() + [row('99_Archive/2026-W44/' + SPEC_V1, sha='f' * 64, status='superseded')]
        with self.assertRaisesRegex(ValueError, 'rule 5'):
            library.archive_plan(rows, WEEK)

    def test_the_week_must_be_a_week(self):
        for week in ('2026-44', 'W44', '2026-W54', None):
            with self.subTest(week=week):
                with self.assertRaises(ValueError):
                    library.archive_plan(self.rows(), week)


class Backups(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = self.root / 'source'
        source.mkdir()
        self.files = {}
        for i, body in enumerate((bytes(range(256)) * 7, b'synthetic ledger line\n' * 40, b'{"week": "2026-W44"}\n')):
            path = source / f'member-{i}.bin'
            path.write_bytes(body)
            self.files[f'ledger/member-{i}.bin'] = path
        self.out = self.root / 'parts'

    def tearDown(self):
        self.temp.cleanup()

    def make(self, out=None, part_bytes=200):
        return library.bundle(self.files, out or self.out, part_bytes, created_on='2026-10-27')

    def test_bundle_then_assemble_round_trips_with_tiny_parts(self):
        manifest = self.make()
        self.assertEqual(manifest['schema_version'], 1)
        archive = manifest['archives'][0]
        self.assertEqual(set(archive), {'role', 'file_name', 'bytes', 'sha256', 'file_count', 'drive_file_id', 'parts'})
        self.assertEqual(archive['file_count'], 3)
        self.assertGreater(len(archive['parts']), 2)
        self.assertEqual([p['part_number'] for p in archive['parts']], list(range(1, len(archive['parts']) + 1)))
        self.assertEqual(sum(p['bytes'] for p in archive['parts']), archive['bytes'])
        for part in archive['parts']:
            self.assertEqual(set(part), {'file_name', 'part_number', 'bytes', 'sha256', 'md5', 'drive_file_id'})
            self.assertLessEqual(part['bytes'], 200)
            self.assertEqual((self.out / part['file_name']).stat().st_size, part['bytes'])
            self.assertEqual(library.name_errors('06_Reference/backups/2026-10-27/' + part['file_name']), [])
        written = json.loads((self.out / 'fulltime-growth-backup-2026-10-27.json').read_text(encoding='utf-8'))
        self.assertEqual(written, manifest)
        self.assertEqual(library.name_errors('06_Reference/backups/2026-10-27/fulltime-growth-backup-2026-10-27.json'),
                         [])
        self.assertFalse((self.out / archive['file_name']).exists())

        restored = self.root / 'restored'
        results = library.assemble(manifest, self.out, restored)
        self.assertEqual(results, [{'file_name': archive['file_name'], 'sha256': archive['sha256'],
                                    'bytes': archive['bytes'], 'zip_verified': True}])
        with zipfile.ZipFile(restored / archive['file_name']) as packed:
            self.assertEqual(sorted(packed.namelist()), sorted(self.files))
            for name, path in self.files.items():
                self.assertEqual(packed.read(name), path.read_bytes())

    def test_the_same_files_make_the_same_bytes(self):
        first = self.make(self.root / 'one')['archives'][0]['sha256']
        second = self.make(self.root / 'two')['archives'][0]['sha256']
        self.assertEqual(first, second)

    def test_a_tampered_part_is_refused_and_nothing_is_left_behind(self):
        manifest = self.make()
        part = self.out / manifest['archives'][0]['parts'][1]['file_name']
        data = bytearray(part.read_bytes())
        data[10] ^= 0xFF
        part.write_bytes(bytes(data))
        restored = self.root / 'restored'
        with self.assertRaisesRegex(ValueError, 'Part hash mismatch'):
            library.assemble(manifest, self.out, restored)
        self.assertEqual(list(restored.iterdir()), [])

    def test_a_missing_or_resized_part_is_refused(self):
        manifest = self.make()
        part = self.out / manifest['archives'][0]['parts'][0]['file_name']
        part.write_bytes(part.read_bytes() + b'x')
        with self.assertRaisesRegex(ValueError, 'wrong-size part'):
            library.assemble(manifest, self.out, self.root / 'restored')
        part.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or wrong-size part'):
            library.assemble(manifest, self.out, self.root / 'restored')

    def test_part_numbers_must_run_without_a_gap(self):
        manifest = self.make()
        for change in (lambda parts: parts.pop(1), lambda parts: parts.append(dict(parts[0])),
                       lambda parts: parts.clear()):
            broken = copy.deepcopy(manifest)
            change(broken['archives'][0]['parts'])
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, 'part number|no parts'):
                    library.assemble(broken, self.out, self.root / 'restored')

    def test_overwrite_is_refused_both_ways(self):
        manifest = self.make()
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
            self.make()
        self.assertEqual({p.name: p.read_bytes() for p in self.out.iterdir()}, before)
        restored = self.root / 'restored'
        library.assemble(manifest, self.out, restored)
        target = restored / manifest['archives'][0]['file_name']
        kept = target.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
            library.assemble(manifest, self.out, restored)
        self.assertEqual(target.read_bytes(), kept)

    def test_unknown_schema_and_unsafe_names_are_refused(self):
        manifest = self.make()
        for version in (2, None, '1'):
            broken = dict(manifest, schema_version=version)
            with self.assertRaisesRegex(ValueError, 'schema'):
                library.assemble(broken, self.out, self.root / 'restored')
        for name in ('../escaped.zip', 'sub/escaped.zip', '', None):
            broken = copy.deepcopy(manifest)
            broken['archives'][0]['file_name'] = name
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'plain file name'):
                    library.assemble(broken, self.out, self.root / 'restored')
        broken = copy.deepcopy(manifest)
        broken['archives'][0]['parts'][0]['file_name'] = '../' + broken['archives'][0]['parts'][0]['file_name']
        with self.assertRaisesRegex(ValueError, 'plain file name'):
            library.assemble(broken, self.out, self.root / 'restored')
        self.assertFalse((self.root / 'escaped.zip').exists())

    def test_matching_hashes_on_bytes_that_are_not_a_zip_are_refused_and_removed(self):
        import hashlib
        parts_dir = self.root / 'fake'
        parts_dir.mkdir()
        body = b'not a zip archive at all ' * 20
        (parts_dir / 'fake.zip.part01').write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        manifest = {'schema_version': 1, 'archives': [{'file_name': 'fake.zip', 'bytes': len(body), 'sha256': digest,
                    'parts': [{'file_name': 'fake.zip.part01', 'part_number': 1, 'bytes': len(body),
                               'sha256': digest}]}]}
        restored = self.root / 'restored'
        with self.assertRaisesRegex(ValueError, 'not a readable ZIP'):
            library.assemble(manifest, parts_dir, restored)
        self.assertFalse((restored / 'fake.zip').exists())

    def test_a_wrong_whole_archive_hash_is_refused(self):
        manifest = self.make()
        manifest['archives'][0]['sha256'] = '0' * 64
        restored = self.root / 'restored'
        with self.assertRaisesRegex(ValueError, 'Reassembled archive hash mismatch'):
            library.assemble(manifest, self.out, restored)
        self.assertEqual(list(restored.iterdir()), [])

    def test_bundle_refusals(self):
        with self.assertRaisesRegex(ValueError, 'part_bytes'):
            self.make(part_bytes=0)
        with self.assertRaisesRegex(ValueError, 'part_bytes'):
            self.make(part_bytes=library.UPLOAD_CAP + 1)
        self.assertLessEqual(library.PART_BYTES, library.UPLOAD_CAP)
        with self.assertRaisesRegex(ValueError, 'created_on'):
            library.bundle(self.files, self.out, created_on='27 October')
        with self.assertRaisesRegex(ValueError, 'at least one file'):
            library.bundle({}, self.out, created_on='2026-10-27')
        with self.assertRaisesRegex(ValueError, 'not a file'):
            library.bundle({'gone.bin': self.root / 'gone.bin'}, self.out, created_on='2026-10-27')
        with self.assertRaisesRegex(ValueError, 'archive member'):
            library.bundle({'../up.bin': next(iter(self.files.values()))}, self.out, created_on='2026-10-27')
        with self.assertRaisesRegex(ValueError, 'bundle name'):
            library.bundle(self.files, self.out, created_on='2026-10-27', name='Growth Backup')

    def test_a_list_of_paths_keeps_each_file_name(self):
        manifest = library.bundle(list(self.files.values()), self.out, created_on='2026-10-27')
        self.assertEqual(len(manifest['archives'][0]['parts']), 1)
        restored = self.root / 'restored'
        library.assemble(manifest, self.out, restored)
        with zipfile.ZipFile(restored / manifest['archives'][0]['file_name']) as packed:
            self.assertEqual(sorted(packed.namelist()), ['member-0.bin', 'member-1.bin', 'member-2.bin'])


class House(unittest.TestCase):
    def test_public_files_carry_no_em_dash_or_private_ids(self):
        for path in (ROOT / 'engine' / 'library.py', Path(__file__), EXAMPLE):
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                self.assertNotIn('\u2014', text)
                self.assertNotIn('drive.google' + '.com', text)
                emails = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}', text)
                self.assertEqual(set(emails) - {'krish@fulltime.fm'}, set())


if __name__ == '__main__':
    unittest.main()
