"""The closeout fold (engine/closeout.py): a session's note in now-notes/ goes into NOW.md on main."""
import io
import contextlib
from pathlib import Path
import tempfile
import unittest

from engine import closeout

NOW = """---
repo: krishanraja/growth-fulltime
as_of: 2026-11-01
head: aaaaaaa
---

# Full Time growth engine: where it is right now

## Where it is right now (as of 2026-11-01)

<!-- north-star-state {"week_of": "2026-10-26"} --> **North Star number: U4, unmeasured.**

Held, with prose that stays.

- An older status. (2026-11-01)

## What changed recently

- 2026-11-01 Something with a [link](README.md).
- 2026-09-20 Something too old to stay.

## What is next and what is waiting on Krish

- Next (2026-11-01): the old next step.
- Waiting on Krish: a ruling.
- North Star check (2026-11-01): holds.

## Read next

- `README.md`.
"""

NOTE = """Status: The fold writes this note into NOW.md and deletes it.
Changed: A test proved the fold.
Next: Release the hold when Full Time is ready.
North Star check (2026-11-12): holds.
"""


def repo(root, now=NOW, notes=None):
    root = Path(root)
    (root / 'now-notes').mkdir()
    (root / 'NOW.md').write_text(now)
    for name, text in (notes or {'2026-11-12-proof.md': NOTE}).items():
        (root / 'now-notes' / name).write_text(text)
    return root


class FoldTests(unittest.TestCase):
    def test_a_note_lands_in_now_md_and_is_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp)
            result = closeout.fold(root, head='b' * 40, day='2026-11-12')
            text = (root / 'NOW.md').read_text()
            log = (root / 'docs/history/LOG.md').read_text()
            self.assertEqual(result['folded'], ['now-notes/2026-11-12-proof.md'])
            self.assertEqual(result['problems'], [])
            self.assertFalse((root / 'now-notes/2026-11-12-proof.md').exists())
        self.assertIn('as_of: 2026-11-12', text)
        self.assertIn('## Where it is right now (as of 2026-11-12)', text)
        self.assertIn('head: bbbbbbb', text)
        lines = text.split('\n')
        status = lines.index('- The fold writes this note into NOW.md and deletes it. (2026-11-12)')
        self.assertLess(lines.index('Held, with prose that stays.'), status)
        self.assertLess(status, lines.index('- An older status. (2026-11-01)'))
        self.assertIn('- 2026-11-12 A test proved the fold.', text)
        # One Next and one check: the note's replace the old ones; other items stay.
        self.assertEqual([l for l in lines if l.startswith('- Next')],
                         ['- Next (2026-11-12): Release the hold when Full Time is ready.'])
        self.assertEqual([l for l in lines if 'North Star check' in l], ['- North Star check (2026-11-12): holds.'])
        self.assertIn('- Waiting on Krish: a ruling.', text)
        # A recent item older than 30 days moves to the history log, verbatim, its link re-pointed.
        self.assertNotIn('2026-09-20', text)
        self.assertIn('- 2026-09-20 Something too old to stay.', log)
        self.assertIn('[link](README.md)', text)

    def test_as_of_never_moves_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, NOW.replace('2026-11-01', '2026-11-20'))
            closeout.fold(root, day='2026-11-20')
            self.assertIn('as_of: 2026-11-20', (root / 'NOW.md').read_text())

    def test_a_note_the_fold_cannot_place_is_refused_and_kept(self):
        bad = {'2026-11-12-bad.md': '# A heading\nStatus: too short\nNorth Star check (2026-11-12): holds. And more.\n',
               'Notes.md': NOTE, '2026-11-12-dash.md': NOTE.replace('this note', 'this note \u2014 now')}
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, notes=bad)
            result = closeout.fold(root, day='2026-11-12')
            self.assertEqual(result['folded'], [])
            self.assertEqual((root / 'NOW.md').read_text(), NOW)
            self.assertTrue((root / 'now-notes/2026-11-12-bad.md').exists())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = closeout.command(['check'], root=root)
        problems = out.getvalue()
        self.assertEqual(code, 1)
        for words in ('a line the fold cannot place', 'needs "Next:', 'needs one line "North Star check',
                      'is not named now-notes/', 'em dash'):
            self.assertIn(words, problems)

    def test_the_oldest_lines_move_to_the_log_when_now_md_is_too_long(self):
        recent = '\n'.join(f'- 2026-11-{d:02d} Change {d}: ' + 'x' * 1450 for d in range(11, 0, -1))
        long_now = NOW.replace('- 2026-11-01 Something with a [link](README.md).', recent)
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, long_now)
            result = closeout.fold(root, day='2026-11-12')
            text = (root / 'NOW.md').read_text()
            log = (root / 'docs/history/LOG.md').read_text()
        self.assertEqual(result['problems'], [])
        self.assertLessEqual(len(text), closeout.NOW_CHARS)
        self.assertIn('- 2026-11-12 A test proved the fold.', text)
        self.assertIn('Change 1: ', log)
        self.assertLess(log.index('Change 1: '), log.index('2026-09-20'))   # newest first
        self.assertNotIn('Change 2: ', log)

    def test_too_many_statuses_and_recent_items_are_trimmed_to_the_audit_limits(self):
        statuses = '\n'.join(f'- Status number {i}. (2026-11-{i:02d})' for i in range(10, 0, -1))
        recent = '\n'.join(f'- 2026-11-{d:02d} Change {d}.' for d in range(11, 0, -1))
        now = NOW.replace('- An older status. (2026-11-01)', statuses).replace(
            '- 2026-11-01 Something with a [link](README.md).', recent)
        with tempfile.TemporaryDirectory() as tmp:
            root = repo(tmp, now)
            result = closeout.fold(root, day='2026-11-12')
            text = (root / 'NOW.md').read_text()
        self.assertEqual(result['problems'], [])
        where = text.split('## Where it is right now')[1].split('## ')[0]
        changed = text.split('## What changed recently')[1].split('## ')[0]
        self.assertEqual(sum(1 for l in where.split('\n') if l.startswith('- ')), closeout.MAX_STATUS)
        self.assertEqual(sum(1 for l in changed.split('\n') if l.startswith('- ')), closeout.MAX_RECENT)
        self.assertIn('(2026-11-12)', where)

    def test_the_repository_holds_only_notes_the_fold_can_place(self):
        notes = closeout.read_notes()
        self.assertEqual([p for n in notes for p in n['problems']], [])
        log = Path(closeout.ROOT, 'docs/history/LOG.md').read_text()
        self.assertNotIn('\u2014', log)


if __name__ == '__main__':
    unittest.main()
