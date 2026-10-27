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
                     (2, 2, 2, True, False, 1), (2, 2, 2, True, False, 2, 0, 1), (2, 2, 2, True, False, 2, 1, 1.5),
                     (2, 2, 2, True, False, 2, True, 1)):
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


class Hand(unittest.TestCase):
    """A store in a temporary directory, and a way to hand-edit it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.local = Path(self.tmp.name)
        self.path = self.local / 'engine' / 'learning.json'
        self.id = new(self.local)

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, change):
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        change(stored['learnings'][self.id])
        self.path.write_text(json.dumps(stored), encoding='utf-8')

    def refused(self):
        with self.assertRaisesRegex(ValueError, 'unreadable'):
            read(self.local)


def recompute(revision):
    """Bring a hand-edited revision's computed fields into line with its evidence, so
    only the rule under test can catch the edit."""
    revision.update(learning._derived({k: revision[k] for k in learning.EVIDENCE}))


class NoDifferenceNeedsTheCleanBar(Hand):
    """Review wave 2: no_difference was called from overlapping, unregistered or one-matchweek evidence."""

    def test_judge(self):
        self.assertEqual(judge(30, 25, 4, True, True, 4)[0], 'directional')
        self.assertEqual(judge(30, 25, 4, False, False, 4)[0], 'directional')
        self.assertEqual(judge(30, 25, 4, False, True, 4)[0], 'directional')
        self.assertEqual(judge(30, 25, 1, True, False, 1)[0], 'directional')
        self.assertEqual(judge(30, 25, 0, True, False, 0)[0], 'directional')
        self.assertEqual(judge(30, 25, 4, True, False, 4)[0], 'no_difference')

    def test_observe(self):
        revision = observe(self.local, self.id, 30, 25, 4, False, True, 4)
        self.assertEqual(revision['status'], 'directional')
        self.assertIn('not pre-registered', revision['why'])

    def test_read_refuses_a_plan_under_two_matchweeks(self):
        observe(self.local, self.id, 30, 25, 4, True, False, 4)

        def shorten(entry):
            entry['revisions'][0].update(matchweeks=1, planned_matchweeks=1)
            recompute(entry['revisions'][0])
        self.edit(shorten)
        self.refused()


class FrozenAtTheFirstObservation(Hand):
    """Review wave 2: pre-registration and the planned duration could change after the data was seen."""

    def test_preregistration_cannot_be_added_later(self):
        observe(self.local, self.id, 60, 30, 3, False, False, 6)
        with self.assertRaisesRegex(ValueError, 'preregistered.*new ID'):
            observe(self.local, self.id, 60, 30, 3, True, False, 6)
        self.assertEqual(kill_double_down(read(self.local))['double_down'], [])

    def test_the_plan_cannot_be_cut_short(self):
        observe(self.local, self.id, 30, 25, 2, True, False, 6)
        with self.assertRaisesRegex(ValueError, 'planned_matchweeks.*new ID'):
            observe(self.local, self.id, 30, 25, 2, True, False, 2)
        self.assertEqual(learning.status(read(self.local)['learnings'][self.id]), 'directional')

    def test_an_overlap_cannot_be_cleared(self):
        observe(self.local, self.id, 60, 30, 3, True, True, 3)
        with self.assertRaisesRegex(ValueError, 'overlapping.*new ID'):
            observe(self.local, self.id, 60, 30, 3, True, False, 3)
        observe(self.local, self.id, 70, 30, 4, True, True, 3)     # more evidence, same experiment
        self.assertEqual(len(read(self.local)['learnings'][self.id]['revisions']), 2)

    def test_read_refuses_revisions_that_disagree(self):
        observe(self.local, self.id, 60, 30, 2, False, False, 2)
        observe(self.local, self.id, 70, 30, 3, False, False, 2)

        def register_late(entry):
            entry['revisions'][1]['preregistered'] = True
            recompute(entry['revisions'][1])
        self.edit(register_late)
        self.refused()

    def test_read_refuses_a_definition_changed_after_the_data(self):
        observe(self.local, self.id, 60, 30, 2, True, False, 2)
        self.edit(lambda entry: entry.update(claim='Clips without the score beat clips with it'))
        self.refused()


class UnequalExposure(Hand):
    """Review wave 2: z assumed equal exposure; it is now recorded per arm and scaled for."""

    def test_unequal_exposure_is_not_confirmed_on_raw_counts(self):
        status, why = judge(60, 30, 3, True, False, 3, 3, 1)
        self.assertNotEqual(status, 'confirmed')
        self.assertIn('|z| 1.82', why)
        self.assertEqual(judge(60, 30, 3, True, False, 3, 1, 1)[0], 'confirmed')
        self.assertEqual(judge(60, 30, 3, True, False, 3, 2, 2)[0], 'confirmed')
        self.assertEqual(judge(60, 20, 3, True, False, 3, 1, 3)[0], 'confirmed')     # 60 a post against 6.7
        lid = observe(self.local, self.id, 60, 20, 3, True, False, 3, exposure_a=1, exposure_b=3)
        line = kill_double_down(read(self.local))['double_down'][0]['line']
        self.assertIn('60 against 20 on exposures 1 and 3 over 3 matchweeks', line)
        self.assertEqual(lid['status'], 'confirmed')

    def test_observe_records_and_uses_exposure(self):
        revision = observe(self.local, self.id, 60, 30, 3, True, False, 3, exposure_a=3, exposure_b=1)
        self.assertEqual((revision['exposure_a'], revision['exposure_b'], revision['z']), (3, 1, -1.82))
        self.assertEqual(revision['status'], 'no_difference')       # the plan ran, clean, |z| under 2
        self.assertIn('over exposures 3 and 1', revision['why'])
        equal = observe(self.local, self.id, 60, 30, 3, True, False, 3)
        self.assertEqual((equal['exposure_a'], equal['exposure_b'], equal['z'], equal['status']),
                         (1, 1, 3.16, 'confirmed'))
        row = list(csv.DictReader(io.StringIO(export_csv(read(self.local)))))[0]
        self.assertEqual((row['exposure_a'], row['exposure_b']), ('1', '1'))


class ReadRecomputes(Hand):
    """Review wave 2: read() checked only the status, not types, derived fields or CSV-bound text."""

    def setUp(self):
        super().setUp()
        observe(self.local, self.id, 60, 30, 3, False, False, 3)

    def test_a_flag_written_as_text_is_refused(self):
        def forge(entry):
            entry['revisions'][0]['preregistered'] = 'false'
            entry['revisions'][0]['status'] = 'confirmed'
        self.edit(forge)
        self.refused()

    def test_forged_counts_and_z_are_refused(self):
        for field, value in (('z', 9.99), ('n', 5000), ('interval_a', [0.0, 1.0]), ('why', 'trust me'),
                             ('a', 60.0), ('matchweeks', True)):
            with self.subTest(field=field):
                self.edit(lambda entry: entry['revisions'][0].update({field: value}))
                self.refused()
                self.edit(lambda entry: entry['revisions'][0].update(
                    {field: learning._derived({k: entry['revisions'][0][k] for k in learning.EVIDENCE}).get(
                        field, {'a': 60, 'matchweeks': 3}.get(field))}))
                self.assertTrue(read(self.local))

    def test_text_fields_and_times_are_checked(self):
        for field, value in (('created_at', '=HYPERLINK("https://example.invalid","open")'),
                             ('created_at', '2026-10-27'), ('applied_to', [3]), ('applied_to', ['a', 'a']),
                             ('claim', ''), ('flip_rule', 7)):
            with self.subTest(field=field, value=value):
                original = read(self.local)['learnings'][self.id][field]
                self.edit(lambda entry: entry.update({field: value}))
                self.refused()
                self.edit(lambda entry: entry.update({field: original}))
        self.edit(lambda entry: entry['revisions'][0].update(observed_at='yesterday'))
        self.refused()

    def test_an_identifier_must_match_in_full(self):
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        entry = stored['learnings'].pop(self.id)
        entry['id'] = self.id + '\n'
        stored['learnings'][entry['id']] = entry
        self.path.write_text(json.dumps(stored), encoding='utf-8')
        self.refused()

    def test_csv_times_are_kept_as_text(self):
        register = read(self.local)
        register['learnings'][self.id]['created_at'] = '=HYPERLINK("https://example.invalid")'
        row = list(csv.DictReader(io.StringIO(export_csv(register))))[0]
        self.assertTrue(row['created_at'].startswith("'="))


class ShownZ(Hand):
    """Review wave 2: a stored z rounded to 2.0 beside a status that said |z| was under 2."""

    def test_z_is_cut_toward_zero(self):
        revision = observe(self.local, self.id, 91, 66, 2, True, False, 2)
        self.assertEqual((revision['z'], revision['status']), (1.99, 'no_difference'))
        self.assertTrue(revision['why'].startswith('|z| 1.99 under 2'))
        self.assertEqual(judge(66, 91, 2, True, False, 2), ('no_difference', revision['why']))
        self.assertEqual(learning._shown(-1.9952), -1.99)
        self.assertEqual(learning._shown(2.0), 2.0)
        self.assertIn('z 3.16 for a', judge(60, 30, 2, True, False, 2)[1])

    def test_no_shown_z_crosses_the_bar(self):
        for a in range(20, 400, 3):
            for b in range(20, 400, 7):
                z = learning.z_score(a, b)
                self.assertEqual(abs(learning._shown(z)) >= 2, abs(z) >= 2, (a, b))


class WeeklyProposals(Hand):
    """Review wave 2: a double-down line through kill_proposal was titled as a stop; long
    claims cut off the flip rule."""

    def test_double_down_is_titled_as_doing_more(self):
        observe(self.local, self.id, 60, 30, 3, True, False, 3)
        other = new(self.local, 'Morning cards before 9 beat cards after 11')
        observe(self.local, other, 30, 60, 3, True, False, 3)
        result = kill_double_down(read(self.local))
        more, stop = learning.proposal(result['double_down'][0]), learning.proposal(result['kill'][0])
        self.assertNotIn('stop', more['title'].lower())
        self.assertEqual(more['title'], 'Weekly review: do more of this')
        self.assertIn(':double-down:', more['proposal_id'])
        self.assertEqual(stop, reporting.kill_proposal(result['kill'][0]['line']))
        schema = reporting.load_schema()['properties']['proposals']
        self.assertEqual(reporting.schema_errors([more, stop], schema, 'proposals'), [])
        with self.assertRaises(ValueError):
            learning.proposal({'status': 'directional', 'line': 'x'})

    def test_a_long_claim_never_cuts_off_what_flips_it(self):
        long_id = add(self.local, 'c' * 990, 'sends per asset', 'FLIPRULE when the control leads', ['take_clip'])
        observe(self.local, long_id, 60, 30, 3, True, False, 3)
        item = [x for x in kill_double_down(read(self.local))['double_down'] if x['id'] == long_id][0]
        self.assertLessEqual(len(item['line']), 1000)
        self.assertIn('What flips it: FLIPRULE when the control leads', item['line'])
        self.assertEqual(item['claim'], 'c' * 990)


if __name__ == '__main__':
    unittest.main()
