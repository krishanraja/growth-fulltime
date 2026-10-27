"""The Match Clock's fixtures reader and Krish's actions list (engine/fixtures.py,
engine/actions.py): replies are normalised to the rail's names, ranked derbies first
within the London week, read with a GET that never shows the token, and kept with a
read_at the Match Clock's lint checks; his actions close only on what the engine sees."""
import datetime as dt
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import actions, crew, fixtures, spec  # noqa: E402

FD = {'matches': [
    {'id': 1, 'utcDate': '2026-11-01T16:30:00Z', 'homeTeam': {'name': 'Liverpool FC'}, 'awayTeam': {'name': 'Everton FC'}},
    {'id': 2, 'utcDate': '2026-10-31T15:00:00Z', 'homeTeam': {'name': 'Brighton & Hove Albion FC'},
     'awayTeam': {'name': 'AFC Bournemouth'}},
    {'id': 3, 'utcDate': '2026-11-03T20:00:00Z', 'homeTeam': {'name': 'Arsenal FC'}, 'awayTeam': {'name': 'Tottenham Hotspur FC'}},
]}
AF = {'response': [
    {'fixture': {'id': 9, 'date': '2026-11-01T14:00:00+00:00'}, 'league': {'id': 39},
     'teams': {'home': {'name': 'Manchester City'}, 'away': {'name': 'Manchester United'}}},
    {'fixture': {'id': 10, 'date': '2026-11-01T14:00:00+00:00'}, 'league': {'id': 140},
     'teams': {'home': {'name': 'Barcelona'}, 'away': {'name': 'Girona'}}},
]}


class Reply:
    def __init__(self, body):
        self.body = json.dumps(body).encode('utf-8')

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FixturesTests(unittest.TestCase):
    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)

    def test_names_match_the_rail_and_derbies_lead_the_week(self):
        out = fixtures.save(self.local, FD, dt.date(2026, 10, 28), read_at='2026-10-28T07:00:00Z')
        data = fixtures.latest(self.local)
        self.assertEqual(out['fixtures'], 2)                                  # Arsenal v Spurs is next week
        self.assertEqual([(f['rank'], f['home'], f['away'], f['rivalry']) for f in data['fixtures']],
                         [(1, 'Liverpool', 'Everton', True), (2, 'Brighton', 'Bournemouth', False)])
        self.assertEqual(data['window'], {'start': '2026-10-26', 'end': '2026-11-01', 'timezone': 'Europe/London'})
        week = json.loads(Path(__file__).resolve().parents[1].joinpath('specs', 'examples', 'synthetic-week.json')
                          .read_text(encoding='utf-8'))
        week['fixtures'] = data['fixtures']
        week['window'] = {**week['window'], 'start': '2026-10-26', 'end': '2026-11-01'}
        self.assertEqual([e for e in spec.validate(week) if 'fixtures' in e], [])
        self.assertEqual(crew.fixtures_fresh(data['read_at'], '2026-10-28T09:00:00Z'), [])
        self.assertTrue(crew.fixtures_fresh(data['read_at'], '2026-10-29T09:00:00Z'))

    def test_api_football_keeps_the_premier_league_only(self):
        rows, source = fixtures.normalise(AF)
        self.assertEqual(source, 'API-Football v3')
        self.assertEqual([(r['fixture_ref'], r['rivalry']) for r in rows], [('af:9', True)])

    def test_a_bad_reply_is_refused_and_nothing_is_kept(self):
        for bad in ({}, {'matches': [{'id': 1, 'utcDate': '2026-11-01', 'homeTeam': {'name': 'A'},
                                      'awayTeam': {'name': 'B'}}]},
                    {'matches': [{'id': 1, 'utcDate': '2026-11-01T15:00:00Z', 'homeTeam': {'name': 'A FC'},
                                  'awayTeam': {'name': 'A'}}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                fixtures.save(self.local, bad, dt.date(2026, 10, 28))
        self.assertIsNone(fixtures.latest(self.local))

    def test_fetch_is_a_get_with_the_token_in_a_header_and_never_in_the_result(self):
        seen = {}

        def opener(request, timeout):
            seen['method'], seen['url'] = request.get_method(), request.full_url
            seen['token'] = request.get_header('X-auth-token')
            return Reply(FD)
        with mock.patch.dict(os.environ, {'FOOTBALL_DATA_TOKEN': 'secret-123'}):
            out = fixtures.fetch(self.local, dt.date(2026, 10, 28), opener=opener)
        self.assertEqual(seen['method'], 'GET')
        self.assertTrue(seen['url'].startswith('https://api.football-data.org/v4/competitions/PL/matches?'))
        self.assertEqual(seen['token'], 'secret-123')
        self.assertNotIn('secret-123', json.dumps(out) + (self.local / 'fixtures' / 'latest.json').read_text(encoding='utf-8'))

    def test_without_a_token_it_says_how_and_never_asks_for_one_in_chat(self):
        with mock.patch.dict(os.environ, {'FOOTBALL_DATA_TOKEN': ''}):
            with self.assertRaisesRegex(ValueError, 'import a reply saved from Control Center'):
                fixtures.fetch(self.local, dt.date(2026, 10, 28), opener=lambda *a, **k: None)


class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.local = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.local)
        self.owner = [{'id': 'handcrafted', 'text': 'Switch to handcrafted.', 'minutes': 1, 'done_when': 'handcrafted'},
                      {'id': 'listen', 'text': 'Listen once.', 'minutes': 3, 'done_when': 'manual'},
                      {'id': 'listened', 'text': 'Done already.', 'minutes': 3, 'done_when': 'manual',
                       'done_on': '2026-10-27'}]
        self.rulings = {'D2': {'status': 'pending', 'title': 'Cover every match'},
                        'D7': {'status': 'pending', 'title': 'Close consent'},
                        'RELEASE': {'status': 'pending', 'title': 'Release'}}

    def compute(self, **k):
        return actions.compute(self.local, dt.date(2026, 10, 28), {}, self.rulings, owner=self.owner, **k)

    def test_the_one_ruling_asked_is_d7_and_unseen_setup_shows_until_seen(self):
        result = self.compute()
        self.assertEqual([a['id'] for a in result['krish']], ['ruling-D7', 'handcrafted', 'listen'])
        self.assertEqual(result['minutes'], 2)                          # setup is never counted in the day
        self.assertIn('cannot see this yet', result['krish'][1]['text'])
        (self.local / 'control-center').mkdir()
        (self.local / 'control-center' / 'last.json').write_text(json.dumps({'autonomy': 'handcrafted'}),
                                                                   encoding='utf-8')
        self.assertEqual([a['id'] for a in self.compute()['krish']], ['ruling-D7', 'listen'])

    def test_engine_to_do_names_fixtures_and_lines_are_short(self):
        result = self.compute()
        self.assertIn('fixtures', [a['id'] for a in result['engine']])
        lines = actions.lines(result)
        self.assertTrue(lines[0].startswith('Your action 1 of 3 (2 min, decision): Rule on D7'))
        self.assertTrue(all(len(x) <= 500 and '—' not in x for x in lines))

    def test_the_list_says_how_many_steps_wait_and_all_shows_them(self):
        owner = [{'id': f'step-{n}', 'text': f'Step {n}.', 'minutes': 1, 'done_when': 'manual'} for n in range(5)]
        short = actions.compute(self.local, dt.date(2026, 10, 28), {}, {}, owner=owner)
        self.assertEqual(len(short['krish']), 3)
        self.assertTrue(any('2 more one-off steps wait' in x for x in actions.lines(short)))
        every = actions.compute(self.local, dt.date(2026, 10, 28), {}, {}, owner=owner, setup_shown=None)
        self.assertEqual(len(every['krish']), 5)
        self.assertFalse(any('more one-off' in x for x in actions.lines(every)))

    def test_a_ruling_carries_its_recommendation(self):
        rulings = {'D7': {'status': 'pending', 'title': 'Close consent',
                          'recommendation': "Approve, with counsel's check."}}
        first = actions.compute(self.local, dt.date(2026, 10, 28), {}, rulings, owner=[])['krish'][0]
        self.assertEqual(first['text'], "Rule on D7 in Control Center: Close consent. Approve, with counsel's check.")

    def test_the_owner_file_is_valid(self):
        self.assertTrue(actions.load_owner())


if __name__ == '__main__':
    unittest.main()
