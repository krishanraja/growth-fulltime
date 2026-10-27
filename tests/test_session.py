"""Short fresh sessions: the session budgets, the 36 KB pack, docs/ENGINE.md and the ledger.
Synthetic fixtures in temporary folders only; nothing here writes into the repository."""
import json
from pathlib import Path
import tempfile
import unittest

import growth
from engine import session

ROOT = Path(growth.HERE)
ENGINE_MD = ROOT / 'docs' / 'ENGINE.md'
CREW = ('Product Truth', 'Match Clock', 'Take & Script Writer', 'Voice Lock', 'Motion Maker', 'Card Maker',
        'Channel & Pack Steward', 'Measurement Analyst', 'What-Works Analyst', 'Librarian', 'Audience Builder')


def record(**change):
    base = {'kind': 'orchestrator', 'started_at': '2026-10-27T09:00:00Z', 'ended_at': '2026-10-27T09:18:00Z',
            'tokens_in': 90000, 'tokens_out': 12000, 'calls': 40, 'engine_minutes': 18, 'waiting_minutes': 5,
            'krish_minutes': 4, 'outcome': 'ended at G2'}
    base.update(change)
    return base


class Budgets(unittest.TestCase):
    def test_the_tracked_budgets_load_with_the_agreed_numbers(self):
        budgets = session.load_budgets()
        kinds = budgets['kinds']
        self.assertEqual(set(kinds), set(session.KINDS))
        self.assertEqual((kinds['scheduled']['max_tokens'], kinds['scheduled']['max_engine_minutes']), (0, 2))
        self.assertEqual((kinds['orchestrator']['max_tokens'], kinds['orchestrator']['max_engine_minutes']), (150000, 20))
        self.assertEqual((kinds['production']['max_tokens'], kinds['production']['max_engine_minutes']), (0, 30))
        self.assertEqual((kinds['review']['max_tokens'], kinds['review']['max_engine_minutes']), (60000, 10))
        self.assertEqual((kinds['build']['max_tokens'], kinds['build']['max_engine_minutes']), (None, None))
        self.assertEqual(budgets['krish_minutes_per_day'], 20)

    def write(self, folder, data):
        path = Path(folder) / 'budgets.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def test_bad_budgets_are_refused_in_plain_words(self):
        good = session.load_budgets()
        cases = [
            (lambda d: d['kinds'].pop('review'), 'kinds.review: is required'),
            (lambda d: d['kinds'].__setitem__('ad_hoc', {'max_tokens': 1, 'max_engine_minutes': 1}), 'ad_hoc'),
            (lambda d: d['kinds']['orchestrator'].__setitem__('max_tokens', None), 'only build may be null'),
            (lambda d: d['kinds']['review'].__setitem__('max_engine_minutes', -1), 'whole number of 0 or more'),
            (lambda d: d['kinds']['review'].__setitem__('max_tokens', 1.5), 'whole number of 0 or more'),
            (lambda d: d['kinds']['review'].pop('max_tokens'), 'kinds.review.max_tokens: is required'),
            (lambda d: d.__setitem__('krish_minutes_per_day', 0), 'krish_minutes_per_day'),
            (lambda d: d.__setitem__('surprise', 1), 'surprise: unknown field'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for change, words in cases:
                data = json.loads(json.dumps(good))
                change(data)
                with self.assertRaises(ValueError) as caught:
                    session.load_budgets(self.write(folder, data))
                self.assertIn(words, str(caught.exception))
            with self.assertRaises(ValueError):
                session.load_budgets(Path(folder) / 'missing.json')


class EngineIndex(unittest.TestCase):
    def test_engine_md_is_an_index_of_at_most_6_kb(self):
        self.assertLessEqual(len(ENGINE_MD.read_bytes()), 6 * 1024)

    def test_engine_md_is_plain_and_complete(self):
        text = ENGINE_MD.read_text(encoding='utf-8')
        self.assertNotIn('\u2014', text)
        for name in CREW:
            self.assertIn(name, text)
        for needle in ('G1', 'G2', 'AGENTS.md', 'COPY.md', 'creative-system/README.md', 'ENGINE-V2.md',
                       'NOW.md', 'python3 growth.py', 'scripts/baseline.py', 'engine/config/budgets.json'):
            self.assertIn(needle, text)
        self.assertIn('Rulings of 27 October', text)
        for number in range(1, 12):
            self.assertIn(f'\n{number}. ', text)

    def test_the_measurement_analyst_reads_google_analytics(self):
        line = next(x for x in ENGINE_MD.read_text(encoding='utf-8').splitlines() if 'Measurement Analyst (' in x)
        self.assertIn('Google Analytics 4', line)
        self.assertIn('read-only', line)
        self.assertIn('apart from listener numbers', line)


class Pack(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.crew = Path(self.folder.name) / 'crew'
        for name in ('librarian', 'measurement-analyst'):
            (self.crew / name).mkdir(parents=True)
            (self.crew / name / 'card.md').write_text(f'# {name} card\n\nCARD-{name}\n', encoding='utf-8')
            (self.crew / name / 'lens.md').write_text(f'LENS-{name}: one question?\n', encoding='utf-8')
        self.spec = {'run_id': 'fulltime:2026-W44', 'mode': 'proof', 'b': [1, 2], 'a': 'é'}

    def tearDown(self):
        self.folder.cleanup()

    def test_an_orchestrator_pack_has_every_part_in_order(self):
        text = session.pack('orchestrator', self.crew, ['librarian', 'measurement-analyst'], spec=self.spec,
                            findings=['R43: RELEASE never opens', {'id': 'R44', 'status': 'open'}],
                            gates={'G2': 'waiting on Krish', 'G1': {'cleared': True}},
                            last_report='HOLD: rail thin, 1 of 6.')
        self.assertTrue(text.startswith(ENGINE_MD.read_text(encoding='utf-8').strip()))
        canonical = '{"a":"é","b":[1,2],"mode":"proof","run_id":"fulltime:2026-W44"}'
        self.assertIn(canonical, text)
        self.assertIn('sha256 ' + session.reporting.canonical_sha256(self.spec), text)
        self.assertIn('CARD-librarian', text)
        self.assertIn('CARD-measurement-analyst', text)
        self.assertNotIn('LENS-', text)
        self.assertIn('- R43: RELEASE never opens', text)
        self.assertIn('- {"id":"R44","status":"open"}', text)
        self.assertLess(text.index('- G1: {"cleared":true}'), text.index('- G2: waiting on Krish'))
        self.assertIn('HOLD: rail thin, 1 of 6.', text)
        order = [text.index(x) for x in ('# Session pack: orchestrator', canonical, 'CARD-librarian',
                                         '## Open findings', '## Gate status', '## Last report summary')]
        self.assertEqual(order, sorted(order))
        self.assertLessEqual(len(text.encode('utf-8')), session.PACK_LIMIT)

    def test_a_review_pack_carries_lenses_only(self):
        text = session.pack('review', self.crew, ['librarian'])
        self.assertIn('LENS-librarian', text)
        self.assertNotIn('CARD-', text)
        self.assertIn('No signed spec', text)
        self.assertIn('None open.', text)
        self.assertIn('No gate status recorded.', text)
        self.assertIn('No report yet.', text)

    def test_production_and_build_packs_carry_cards(self):
        for kind in ('production', 'build'):
            text = session.pack(kind, self.crew, ['librarian'], last_report={'status': 'held'})
            self.assertIn('CARD-librarian', text)
            self.assertIn('{"status":"held"}', text)
        self.assertIn('No crew member is in play.', session.pack('build', self.crew, []))

    def test_a_windows_checkout_keeps_the_same_card_budget(self):
        line = b'x' * 99 + b'\n'
        fits = line * 30                       # 3,000 bytes with LF, 3,030 with CRLF
        (self.crew / 'librarian' / 'card.md').write_bytes(fits.replace(b'\n', b'\r\n'))
        self.assertIn('librarian', session.pack('production', self.crew, ['librarian']))
        (self.crew / 'librarian' / 'card.md').write_bytes(line * 31)    # 3,100 bytes even with LF
        with self.assertRaises(ValueError):
            session.pack('production', self.crew, ['librarian'])

    def test_a_pack_over_36_kb_is_refused_with_its_size(self):
        findings = ['x' * 1000 for _ in range(40)]
        with self.assertRaises(ValueError) as caught:
            session.pack('orchestrator', self.crew, [], findings=findings)
        message = str(caught.exception)
        self.assertIn('bytes, over the 36864-byte limit', message)
        self.assertRegex(message, r'pack is \d+ bytes')

    def test_the_limit_counts_utf8_bytes_not_characters(self):
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / 'ENGINE.md'
            index.write_text('# Index\n', encoding='utf-8')
            fits = session.pack('build', self.crew, [], index=index)
            room = session.PACK_LIMIT - len(fits.encode('utf-8')) - 3
            text = session.pack('build', self.crew, [], findings=['a' * room], index=index)
            self.assertLessEqual(len(text.encode('utf-8')), session.PACK_LIMIT)
            with self.assertRaises(ValueError):
                session.pack('build', self.crew, [], findings=['é' * room], index=index)

    def test_bad_requests_are_refused(self):
        (self.crew / 'librarian' / 'card.md').write_text('x' * (3 * 1024 + 1), encoding='utf-8')
        (self.crew / 'measurement-analyst' / 'lens.md').write_text('y' * 1025, encoding='utf-8')
        cases = [
            (lambda: session.pack('scheduled', self.crew, []), 'no pack'),
            (lambda: session.pack('weekly', self.crew, []), 'not one of'),
            (lambda: session.pack('build', self.crew, ['librarian']), 'at most 3072 bytes'),
            (lambda: session.pack('review', self.crew, ['measurement-analyst']), 'at most 1024 bytes'),
            (lambda: session.pack('build', self.crew, ['nobody']), 'is missing'),
            (lambda: session.pack('build', self.crew, ['../crew']), 'not a crew folder name'),
            (lambda: session.pack('build', self.crew, 'librarian'), 'must be a list'),
            (lambda: session.pack('build', self.crew, ['nobody', 'nobody']), 'twice'),
            (lambda: session.pack('review', self.crew, []), 'at least one crew member'),
            (lambda: session.pack('build', self.crew, [], spec=['not', 'a', 'spec']), 'signed spec object'),
            (lambda: session.pack('build', self.crew, [], findings='one finding'), 'list of open findings'),
            (lambda: session.pack('build', self.crew, [], findings=['']), 'non-empty text'),
            (lambda: session.pack('build', self.crew, [], gates=['G1']), 'gates must be an object'),
            (lambda: session.pack('build', self.crew, [], index=Path(self.folder.name) / 'none.md'), 'is missing'),
        ]
        for call, words in cases:
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertIn(words, str(caught.exception))


class Ledger(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.local = Path(self.folder.name) / 'local'
        self.path = self.local / 'engine' / 'sessions.jsonl'

    def tearDown(self):
        self.folder.cleanup()

    def test_each_session_appends_one_json_line_in_field_order(self):
        self.assertEqual(session.ledger_append(self.local, record()), self.path)
        session.ledger_append(self.local, record(kind='review', tokens_in=None, tokens_out=None, calls=None,
                                                 engine_minutes=None, waiting_minutes=None, krish_minutes=None))
        lines = self.path.read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(list(first), list(session.LEDGER_FIELDS))
        self.assertIsNone(json.loads(lines[1])['krish_minutes'])
        self.assertEqual(len(session.read_ledger(self.path)), 2)

    def test_bad_records_are_refused_and_nothing_is_written(self):
        cases = [
            (record(colour='blue'), 'record.colour: unknown field'),
            ({k: v for k, v in record().items() if k != 'calls'}, 'record.calls: is required'),
            (record(kind='weekly'), 'record.kind'),
            (record(tokens_in=-1), 'record.tokens_in'),
            (record(calls=1.5), 'record.calls'),
            (record(calls=True), 'record.calls'),
            (record(engine_minutes=-0.5), 'record.engine_minutes'),
            (record(krish_minutes=float('nan')), 'record.krish_minutes'),
            (record(waiting_minutes='5'), 'record.waiting_minutes'),
            (record(ended_at='2026-10-27T08:00:00Z'), 'after started_at'),
            (record(ended_at='2026-10-27T09:00:00Z'), 'after started_at'),
            (record(started_at='2026-10-27T09:00:00'), 'record.started_at'),
            (record(started_at='yesterday'), 'record.started_at'),
            (record(outcome=''), 'record.outcome'),
            (record(outcome='x' * 201), 'record.outcome'),
            ('not a record', 'must be an object'),
        ]
        for bad, words in cases:
            with self.assertRaises(ValueError) as caught:
                session.ledger_append(self.local, bad)
            self.assertIn(words, str(caught.exception))
        self.assertFalse(self.path.exists())

    def test_a_bad_ledger_line_is_named(self):
        session.ledger_append(self.local, record())
        with open(self.path, 'a', encoding='utf-8') as handle:
            handle.write('{"kind": "orchestrator"\n')
        with self.assertRaises(ValueError) as caught:
            session.read_ledger(self.path)
        self.assertIn('sessions.jsonl:2', str(caught.exception))

    def test_krish_minutes_sum_by_london_date(self):
        self.assertIsNone(session.krish_minutes_on(self.path, '2026-07-01'))
        # 23:30 UTC on 30 June is 00:30 on 1 July in London (BST).
        session.ledger_append(self.local, record(started_at='2026-06-30T23:30:00Z', ended_at='2026-07-01T00:10:00Z',
                                                 krish_minutes=7))
        session.ledger_append(self.local, record(started_at='2026-07-01T10:00:00+01:00',
                                                 ended_at='2026-07-01T10:20:00+01:00', krish_minutes=5.5))
        session.ledger_append(self.local, record(started_at='2026-07-01T12:00:00Z', ended_at='2026-07-01T12:20:00Z',
                                                 krish_minutes=None))
        session.ledger_append(self.local, record(started_at='2026-06-30T12:00:00Z', ended_at='2026-06-30T12:20:00Z',
                                                 krish_minutes=3))
        self.assertEqual(session.krish_minutes_on(self.path, '2026-07-01'), 12.5)
        self.assertEqual(session.krish_minutes_on(self.path, session.dt.date(2026, 6, 30)), 3)
        self.assertIsNone(session.krish_minutes_on(self.path, '2026-07-02'))
        with self.assertRaises(ValueError):
            session.krish_minutes_on(self.path, 'first of July')

    def test_budget_errors_flag_a_day_over_20_minutes_and_sessions_over_budget(self):
        day = '2026-10-27'
        self.assertEqual(session.budget_errors(self.path, day), [])
        session.ledger_append(self.local, record(krish_minutes=12))
        session.ledger_append(self.local, record(started_at='2026-10-27T11:00:00Z', ended_at='2026-10-27T11:30:00Z',
                                                 krish_minutes=8))
        self.assertEqual(session.budget_errors(self.path, day), [], 'exactly 20 minutes is within budget')
        session.ledger_append(self.local, record(started_at='2026-10-27T13:00:00Z', ended_at='2026-10-27T13:05:00Z',
                                                 kind='review', tokens_in=70000, tokens_out=None, engine_minutes=4,
                                                 krish_minutes=0.5))
        session.ledger_append(self.local, record(started_at='2026-10-27T05:10:00Z', ended_at='2026-10-27T05:14:00Z',
                                                 kind='scheduled', tokens_in=0, tokens_out=0, engine_minutes=4,
                                                 krish_minutes=None))
        session.ledger_append(self.local, record(started_at='2026-10-27T15:00:00Z', ended_at='2026-10-27T17:00:00Z',
                                                 kind='build', tokens_in=900000, tokens_out=90000,
                                                 engine_minutes=120, krish_minutes=None))
        session.ledger_append(self.local, record(started_at='2026-10-28T09:00:00Z', ended_at='2026-10-28T10:00:00Z',
                                                 tokens_in=999999, engine_minutes=60, krish_minutes=60))
        errors = session.budget_errors(self.path, day)
        self.assertEqual(len(errors), 3, errors)
        self.assertIn('Krish spent 20.5 minutes', errors[0])
        self.assertIn('over his 20-minute daily budget', errors[0])
        self.assertIn('review session started 2026-10-27T13:00:00Z used 70000 Claude tokens', errors[1])
        self.assertIn('scheduled session started 2026-10-27T05:10:00Z ran 4 engine minutes', errors[2])
        tighter = session.load_budgets()
        tighter['krish_minutes_per_day'] = 30
        self.assertEqual(len(session.budget_errors(self.path, day, tighter)), 2)
        next_day = session.budget_errors(self.path, '2026-10-28')
        self.assertEqual(len(next_day), 3, next_day)


if __name__ == '__main__':
    unittest.main()
