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
        # Was (0, 30): production uses Claude for connector calls, so 0 flagged every matchday.
        self.assertEqual((kinds['production']['max_tokens'], kinds['production']['max_engine_minutes']), (60000, 30))
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

    def test_a_review_pack_carries_lenses_the_rubric_and_the_contact_sheet(self):
        text = session.pack('review', self.crew, ['librarian'], contact_sheet='Drive 03_Runs/2026-W44/sheet.png')
        self.assertIn('LENS-librarian', text)
        self.assertNotIn('CARD-', text)
        self.assertIn('No spec for this session.', text)
        self.assertIn('## COPY.md: Rubric for packs', text)
        self.assertIn('38 and above', text)
        self.assertIn('## Contact sheet\n\nDrive 03_Runs/2026-W44/sheet.png', text)
        self.assertNotIn('## Test record', text, 'only the rubric section of COPY.md')
        self.assertIn('Not supplied to this pack', session.pack('review', self.crew, ['librarian']))

    def test_what_the_caller_did_not_supply_is_unknown_never_none(self):
        # Before the fix the defaults printed 'None open.', 'No gate status recorded.' and 'No report yet.'.
        text = session.pack('orchestrator', self.crew, ['librarian'])
        for head, pointer in (('## Open findings', 'docs/FAILURE-REGISTER.md'), ('## Gate status', 'Control Center'),
                              ('## Last report summary', 'local/control-center/last.json')):
            body = text[text.index(head):].split('\n\n')[1]
            self.assertIn('Not supplied to this pack, so unknown here, not none', body)
            self.assertIn(pointer, body)
        for words in ('None open.', 'No gate status recorded.', 'No report yet.'):
            self.assertNotIn(words, text)
        told = session.pack('orchestrator', self.crew, ['librarian'], findings=[], gates={}, last_report='')
        for words in ('None open.', 'No gate status recorded.', 'No report yet.'):
            self.assertIn(words, told)
        self.assertNotIn('Not supplied', told)

    def test_a_spec_is_called_signed_only_on_the_digest_krish_cleared(self):
        draft = {'mode': 'live', 'status': 'draft'}
        digest = session.reporting.canonical_sha256(draft)
        text = session.pack('orchestrator', self.crew, [], spec=draft)
        self.assertNotIn('Signed spec', text)
        self.assertIn('## Spec (not signed)\n\nsha256 ' + digest, text)
        signed = session.pack('orchestrator', self.crew, [], spec=draft, signed_sha256=digest)
        self.assertIn('## Signed spec\n\nsha256 ' + digest, signed)
        for call, words in ((lambda: session.pack('orchestrator', self.crew, [], spec=draft, signed_sha256='0' * 64),
                             'not the ' + '0' * 64),
                            (lambda: session.pack('orchestrator', self.crew, [], signed_sha256=digest), 'without the spec')):
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertIn(words, str(caught.exception))

    def test_a_build_pack_carries_its_task_card_and_read_files(self):
        from tests.test_dispatch import card
        task = card(read_files=['docs/ENGINE.md', 'engine/assets.py'])
        text = session.pack('build', self.crew, [], card=task)
        self.assertIn('## Task card synthetic-build', text)
        self.assertIn(session.reporting.canonical(task), text)
        self.assertIn('### Read these files, and only these\n\n- docs/ENGINE.md\n- engine/assets.py', text)
        self.assertIn('## Task card\n\nNot supplied', session.pack('build', self.crew, []))
        with self.assertRaises(ValueError) as caught:
            session.pack('build', self.crew, [], card=card(model='gpt-6-astra'))
        self.assertIn('the task card is refused', str(caught.exception))

    def test_a_production_pack_carries_its_instance_and_locks(self):
        text = session.pack('production', self.crew, ['librarian'], instance={'creative_id': 'tc-synthetic-1'},
                            locks={'take_clip': 'a' * 64})
        self.assertIn('## Instance\n\n{"creative_id":"tc-synthetic-1"}', text)
        self.assertIn('## Locks\n\n{"take_clip":"' + 'a' * 64 + '"}', text)
        self.assertIn('## Locks\n\nNot supplied', session.pack('production', self.crew, ['librarian']))

    def test_each_part_belongs_to_its_own_kind(self):
        from tests.test_dispatch import card
        cases = [
            (lambda: session.pack('review', self.crew, ['librarian'], card=card()), 'does not carry card'),
            (lambda: session.pack('orchestrator', self.crew, [], contact_sheet='x.png'), 'does not carry contact_sheet'),
            (lambda: session.pack('build', self.crew, [], locks={}), 'does not carry locks'),
            (lambda: session.pack('production', self.crew, [], instance=['x']), 'instance must be an object'),
            (lambda: session.pack('review', self.crew, ['librarian'], contact_sheet=' '), 'contact_sheet'),
            (lambda: session.pack('review', self.crew, ['librarian'], copy=Path(self.folder.name) / 'none.md'),
             'is missing'),
        ]
        for call, words in cases:
            with self.assertRaises(ValueError) as caught:
                call()
            self.assertIn(words, str(caught.exception))
        plain = Path(self.folder.name) / 'COPY.md'
        plain.write_text('# Copy\n\n## Something else\n', encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            session.pack('review', self.crew, ['librarian'], copy=plain)
        self.assertIn('Rubric for packs', str(caught.exception))

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
            (lambda: session.pack('build', self.crew, ['librarian\n']), 'not a crew folder name'),
            (lambda: session.pack('build', self.crew, 'librarian'), 'must be a list'),
            (lambda: session.pack('build', self.crew, ['nobody', 'nobody']), 'twice'),
            (lambda: session.pack('review', self.crew, []), 'at least one crew member'),
            (lambda: session.pack('build', self.crew, [], spec=['not', 'a', 'spec']), 'spec object'),
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

    def test_line_separators_inside_a_record_never_split_it(self):
        # Before the fix one outcome holding U+2028 made every later read of the ledger fail.
        outcome = 'rendered\u2028then\u2029held\x85again é'
        session.ledger_append(self.local, record(outcome=outcome))
        session.ledger_append(self.local, record(krish_minutes=3))
        raw = self.path.read_bytes()
        self.assertEqual(raw.count(b'\n'), 2)
        self.assertTrue(raw.isascii(), 'written with ASCII escapes')
        records = session.read_ledger(self.path)
        self.assertEqual([r['outcome'] for r in records], [outcome, 'ended at G2'])
        self.assertEqual(session.krish_minutes_on(self.path, '2026-10-27'), 7)
        self.assertEqual(session.budget_errors(self.path, '2026-10-28'), [])
        with open(self.path, 'a', encoding='utf-8', newline='\r\n') as handle:     # an older line, written raw
            handle.write(json.dumps(record(outcome='old\u2028line'), ensure_ascii=False) + '\n')
        self.assertEqual(session.read_ledger(self.path)[-1]['outcome'], 'old\u2028line')

    def test_a_production_session_may_use_claude_for_connector_calls(self):
        session.ledger_append(self.local, record(kind='production', tokens_in=3000, tokens_out=400, engine_minutes=25,
                                                 krish_minutes=None, outcome='pack ready; Canva exports by Claude'))
        self.assertEqual(session.budget_errors(self.path, '2026-10-27'), [])

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
