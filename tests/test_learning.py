"""The What-Works Analyst's learning register (engine/learning.py). Every store lives
in a temporary directory; synthetic claims only; no network."""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import growth
from engine import learning, reporting
from engine.learning import (add, blocked_locks, export_csv, judge, kill_double_down, observe, read,
                             verdict_analysis)

# A contact-shaped value built at run time, so no address sits in this public file.
CONTACT = 'synthetic' + chr(64) + 'example.invalid'
CLEAN = {'matchweeks': 2, 'preregistered': True, 'overlapping': False, 'planned_matchweeks': 2}


def new(local, claim='Take clips with the score in the first second beat clips without it'):
    return add(local, claim, 'sends per asset on Full Time channels',
               'Refuted if the scoreless arm leads by z of 2 or more over two matchweeks', ['take_clip'])


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.local = Path(self.tmp.name)
        self.path = self.local / 'engine' / 'learning.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_writes_the_store_and_returns_an_id(self):
        self.assertFalse(self.path.exists())
        identifier = new(self.local)
        self.assertEqual(identifier, 'learning-001')
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        entry = stored['learnings'][identifier]
        self.assertEqual((stored['schema_version'], stored['product']), (1, 'fulltime'))
        self.assertEqual(entry['applied_to'], ['take_clip'])
        self.assertEqual(entry['revisions'], [])
        self.assertEqual(learning.status(entry), 'directional')
        self.assertEqual(read(self.local), stored)

    def test_the_same_definition_returns_the_same_id(self):
        first = new(self.local)
        self.assertEqual(new(self.local), first)
        self.assertEqual(new(self.local, 'Morning cards before 9 beat cards after 11'), 'learning-002')
        self.assertEqual(sorted(read(self.local)['learnings']), ['learning-001', 'learning-002'])

    def test_add_refuses_bad_definitions(self):
        for args in (('', 'signal', 'flip', []), ('claim', ' ', 'flip', []), ('claim', 'signal', None, []),
                     ('claim', 'signal', 'flip', 'take_clip'), ('claim', 'signal', 'flip', ['a', 'a']),
                     ('claim', 'signal', 'flip', ['']), ('x' * 1001, 'signal', 'flip', []),
                     ('Ask ' + CONTACT, 'signal', 'flip', [])):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    add(self.local, *args)
        self.assertFalse(self.path.exists())

    def test_observe_adds_a_revision_and_keeps_earlier_ones(self):
        identifier = new(self.local)
        first = observe(self.local, identifier, 12, 9, 1, True, False, 2)
        self.assertEqual((first['revision'], first['status']), (1, 'directional'))
        second = observe(self.local, identifier, 60, 30, **CLEAN)
        self.assertEqual((second['revision'], second['status']), (2, 'confirmed'))
        revisions = read(self.local)['learnings'][identifier]['revisions']
        self.assertEqual(revisions, [first, second])
        self.assertEqual(second['n'], 90)
        self.assertEqual(second['z'], 3.16)
        self.assertEqual(second['interval_a'], [44.5, 75.5])
        self.assertEqual(second['interval_b'], [19.0, 41.0])

    def test_the_same_evidence_twice_is_one_revision(self):
        identifier = new(self.local)
        first = observe(self.local, identifier, 60, 30, **CLEAN)
        again = observe(self.local, identifier, 60, 30, **CLEAN)
        self.assertEqual(again, first)
        self.assertEqual(len(read(self.local)['learnings'][identifier]['revisions']), 1)

    def test_every_change_keeps_an_immutable_backup(self):
        identifier = new(self.local)
        before = read(self.local)
        observe(self.local, identifier, 60, 30, **CLEAN)
        backups = self.local / 'engine' / 'learning-backups'
        saved = sorted(backups.glob('*.json'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(json.loads(saved[0].read_text(encoding='utf-8')), before)
        middle = read(self.local)
        observe(self.local, identifier, 30, 60, **CLEAN)
        contents = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(backups.glob('*.json'))]
        self.assertEqual(len(contents), 2)
        self.assertIn(before, contents)
        self.assertIn(middle, contents)
        observe(self.local, identifier, 30, 60, **CLEAN)   # no change, no new backup
        self.assertEqual(len(list(backups.glob('*.json'))), 2)
        self.assertFalse((self.local / 'engine' / '.learning-lock').exists())

    def test_observe_refuses_bad_evidence(self):
        identifier = new(self.local)
        for args in ((-1, 2, 2, True, False, 2), (1.5, 2, 2, True, False, 2), (True, 2, 2, True, False, 2),
                     (2, 2, -1, True, False, 2), (2, 2, 2, 'yes', False, 2), (2, 2, 2, True, 0, 2),
                     (2, 2, 2, True, False, 1)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    observe(self.local, identifier, *args)
        with self.assertRaisesRegex(ValueError, 'unknown learning'):
            observe(self.local, 'learning-099', 60, 30, **CLEAN)
        self.assertEqual(read(self.local)['learnings'][identifier]['revisions'], [])

    def test_a_hand_written_status_is_refused(self):
        identifier = new(self.local)
        observe(self.local, identifier, 12, 9, 1, True, False, 2)
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        stored['learnings'][identifier]['revisions'][0]['status'] = 'confirmed'
        self.path.write_text(json.dumps(stored), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unreadable'):
            read(self.local)
        with self.assertRaises(ValueError):
            observe(self.local, identifier, 60, 30, **CLEAN)

    def test_a_damaged_store_is_never_replaced(self):
        new(self.local)
        self.path.write_text('{not json', encoding='utf-8')
        with self.assertRaises(ValueError):
            new(self.local, 'Another synthetic claim')
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{not json')


class Judge(unittest.TestCase):
    def status(self, a, b, matchweeks=2, preregistered=True, overlapping=False, planned=2):
        return judge(a, b, matchweeks, preregistered, overlapping, planned)[0]

    def test_confirmed_needs_every_part_of_the_bar(self):
        self.assertEqual(self.status(60, 30), 'confirmed')
        self.assertEqual(self.status(60, 30, preregistered=False), 'directional')
        self.assertEqual(self.status(60, 30, overlapping=True), 'directional')
        self.assertEqual(self.status(60, 30, matchweeks=1), 'directional')
        self.assertEqual(self.status(40, 19), 'directional')
        self.assertEqual(self.status(19, 1), 'directional')
        self.assertEqual(self.status(30, 22, planned=4), 'directional')   # |z| 1.11, still running

    def test_the_boundaries_are_inclusive(self):
        self.assertEqual(self.status(60, 40), 'confirmed')     # z exactly 2
        self.assertEqual(self.status(40, 20), 'confirmed')     # 20 events in arm b
        self.assertEqual(self.status(60, 40, matchweeks=2, planned=6), 'confirmed')

    def test_refuted_is_the_same_bar_the_other_way(self):
        self.assertEqual(self.status(30, 60), 'refuted')
        self.assertEqual(self.status(40, 60), 'refuted')       # z exactly -2
        self.assertEqual(self.status(30, 60, preregistered=False), 'directional')
        self.assertEqual(self.status(30, 60, overlapping=True), 'directional')
        self.assertEqual(self.status(30, 60, matchweeks=1), 'directional')
        self.assertEqual(self.status(19, 60), 'directional')

    def test_no_difference_after_the_planned_duration(self):
        self.assertEqual(self.status(30, 25, matchweeks=4, planned=4), 'no_difference')
        self.assertEqual(self.status(30, 25, matchweeks=5, planned=4), 'no_difference')
        self.assertEqual(self.status(30, 25, matchweeks=3, planned=4), 'directional')
        self.assertEqual(self.status(30, 19, matchweeks=4, planned=4), 'directional')

    def test_directional_says_what_is_short(self):
        status, why = judge(12, 9, 1, False, True, 2)
        self.assertEqual(status, 'directional')
        for part in ('not pre-registered', 'overlaps another test', '1 of 2 matchweeks',
                     'arm a has 12 of 20 events', 'arm b has 9 of 20 events'):
            self.assertIn(part, why)


class Reading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.local = Path(self.tmp.name)
        self.ids = {}
        for name, claim, evidence in (
                ('confirmed', 'Score in the first second beats no score', (60, 30, 2, True, False, 2)),
                ('refuted', 'Gaffer takes beat Reporter takes', (30, 60, 2, True, False, 2)),
                ('directional', 'Morning cards before 9 beat cards after 11', (12, 9, 1, True, False, 2)),
                ('no_difference', 'Captions in white beat captions in yellow', (30, 25, 4, True, False, 4)),
                ('fresh', '=HYPERLINK("synthetic") beats plain text', None)):
            self.ids[name] = add(self.local, claim, 'sends per asset', 'Flips on z of 2 the other way',
                                 [f'{name}_lock'])
            if evidence:
                observe(self.local, self.ids[name], *evidence)
        self.register = read(self.local)

    def tearDown(self):
        self.tmp.cleanup()

    def test_kill_and_double_down_come_from_refuted_and_confirmed(self):
        result = kill_double_down(self.register)
        self.assertEqual([x['id'] for x in result['double_down']], [self.ids['confirmed']])
        self.assertEqual([x['id'] for x in result['kill']], [self.ids['refuted']])
        kill = result['kill'][0]
        self.assertTrue(kill['line'].startswith(f'Stop relying on {self.ids["refuted"]}'))
        self.assertIn('What flips it: Flips on z of 2 the other way', kill['line'])
        self.assertTrue(result['double_down'][0]['line'].startswith('Double down on'))
        proposal = reporting.kill_proposal(kill['line'])
        self.assertEqual(proposal['why'], kill['line'])
        self.assertEqual(kill_double_down(list(self.register['learnings'].values())), result)

    def test_the_csv_export(self):
        text = export_csv(self.register)
        self.assertNotIn('\r', text)
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(tuple(rows[0]), learning.CSV_FIELDS)
        self.assertEqual([r['id'] for r in rows], sorted(self.ids.values()))
        by_id = {r['id']: r for r in rows}
        confirmed = by_id[self.ids['confirmed']]
        self.assertEqual((confirmed['status'], confirmed['a'], confirmed['b'], confirmed['z']),
                         ('confirmed', '60', '30', '3.16'))
        self.assertEqual(confirmed['interval_a'], '44.5 to 75.5')
        self.assertEqual((confirmed['preregistered'], confirmed['overlapping']), ('yes', 'no'))
        self.assertEqual(by_id[self.ids['no_difference']]['status'], 'no_difference')
        fresh = by_id[self.ids['fresh']]
        self.assertEqual((fresh['status'], fresh['revision'], fresh['z']), ('directional', '0', ''))
        self.assertTrue(fresh['claim'].startswith("'="), 'a formula-like claim stays text')
        self.assertIn(self.ids['refuted'], text)
        self.assertNotIn('@', text)

    def test_blocked_locks_cite_a_refuted_learning(self):
        locks = [{'lock_version': 'a' * 64, 'learnings': [self.ids['refuted'], self.ids['confirmed']]},
                 {'lock_version': 'b' * 64, 'learnings': [self.ids['confirmed']]},
                 {'lock_version': 'c' * 64, 'learnings': []},
                 {'lock_version': 'd' * 64, 'learnings': [self.ids['directional'], self.ids['refuted']]}]
        self.assertEqual(blocked_locks(self.register, locks), ['a' * 64, 'd' * 64])
        self.assertEqual(blocked_locks(self.register, {'e' * 64: [self.ids['refuted']], 'f' * 64: []}),
                         ['e' * 64])
        self.assertEqual(blocked_locks(self.register, []), [])
        for bad in ('a' * 64, [{'lock_version': 'a' * 64}], [{'learnings': []}], [3]):
            with self.subTest(locks=bad):
                with self.assertRaises(ValueError):
                    blocked_locks(self.register, bad)

    def test_a_register_must_be_a_store_or_its_entries(self):
        with self.assertRaises(ValueError):
            kill_double_down('learning.json')


class Verdicts(unittest.TestCase):
    def verdicts(self):
        return [
            {'creative_id': 'TT_CLASH_CLIP_C01_H01_V1_20261020', 'verdict': 'edit', 'format_id': 'take_clip',
             'pundit': 'gaffer', 'note': 'Hook too long, cut the first line.'},
            {'creative_id': 'TT_CLASH_CLIP_C02_H01_V1_20261020', 'verdict': 'reject', 'format_id': 'take_clip',
             'pundit': 'gaffer', 'note': 'Too long and the hook is flat. Long long long.'},
            {'creative_id': 'IG_CLASH_POST_C01_H01_V1_20261020', 'verdict': 'reject',
             'format_id': 'morning_card', 'pundit': 'zen', 'note': 'Wrong score on the card.'},
            {'creative_id': 'IG_CLASH_POST_C02_H01_V1_20261020', 'verdict': 'post_it',
             'format_id': 'morning_card', 'pundit': 'zen', 'note': 'long long'},
            {'creative_id': 'YT_CLASH_SHORT_C01_H01_V1_20261020', 'verdict': 'edit', 'note': None},
        ]

    def test_counts_by_format_pundit_and_word(self):
        result = verdict_analysis(self.verdicts())
        self.assertEqual((result['edit'], result['reject']), (2, 2))
        self.assertEqual(result['by_format'], {'take_clip': {'edit': 1, 'reject': 1},
                                               'morning_card': {'edit': 0, 'reject': 1},
                                               'unknown': {'edit': 1, 'reject': 0}})
        self.assertEqual(result['by_pundit'], {'gaffer': {'edit': 1, 'reject': 1},
                                               'zen': {'edit': 0, 'reject': 1},
                                               'unknown': {'edit': 1, 'reject': 0}})
        self.assertEqual(result['by_word']['long'], {'edit': 1, 'reject': 1})
        self.assertEqual(result['by_word']['score'], {'edit': 0, 'reject': 1})
        self.assertNotIn('the', result['by_word'])
        self.assertNotIn('too', result['by_word'])

    def test_a_reason_seen_twice_is_flagged(self):
        repeated = verdict_analysis(self.verdicts())['repeated']
        self.assertEqual(repeated, [{'reason': 'hook', 'count': 2, 'edit': 1, 'reject': 1},
                                    {'reason': 'long', 'count': 2, 'edit': 1, 'reject': 1}])

    def test_a_word_counts_once_per_note_and_post_it_is_not_counted(self):
        result = verdict_analysis(self.verdicts())
        self.assertEqual(result['by_word']['long']['reject'], 1)
        self.assertEqual(verdict_analysis([{'verdict': 'post_it', 'note': 'flat flat'}] * 3)['repeated'], [])

    def test_unknown_verdicts_are_refused(self):
        for bad in ([{'verdict': 'maybe'}], ['edit'], [{'note': 'no verdict'}]):
            with self.assertRaises(ValueError):
                verdict_analysis(bad)
        self.assertEqual(verdict_analysis([])['repeated'], [])

    def test_the_example_verdicts_use_real_creative_ids(self):
        for verdict in self.verdicts():
            self.assertTrue(growth.CREATIVE_ID.match(verdict['creative_id']))


if __name__ == '__main__':
    unittest.main()
