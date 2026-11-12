"""Closeout notes folded into NOW.md: `growth.py closeout check` and `growth.py closeout fold`.

Every session that changes this repository leaves its status, next step and North Star check current
without Krish asking (Ruling, Krish, 2026-10-22), and pull requests never edit NOW.md at once, because two
that did conflicted (Ruling, Krish, 2026-10-28). So a session writes one note,
now-notes/YYYY-MM-DD-<slug>.md, in the format of ai-harness's closeout hook:

    Status: <what is true now that this work changed>
    Changed: <optional: the why, for "What changed recently">
    Next: <the single next action>
    North Star check (YYYY-MM-DD): holds.        (or "...: recalibration proposed. <why>")

When the note reaches main, the fold job in .github/workflows/check.yml runs `growth.py closeout fold`,
which writes each note into NOW.md and deletes it:

- its Status goes on top of the dated status bullets under "Where it is right now", below the
  north-star-state line and the section's prose;
- its Changed, when present, goes on top of "What changed recently";
- its Next replaces every top-level "- Next" item under "What is next and what is waiting on Krish",
  and its North Star check replaces the old check line there;
- `as_of`, the heading's date and `head` move forward, never back.

NOW.md then stays inside the nightly audit's limits (ai-harness config/now-audit.json): "What changed
recently" items older than 30 days or past the newest MAX_RECENT, and status bullets past the newest
MAX_STATUS, move to docs/history/LOG.md verbatim, newest first, and so do the oldest of both while the
file is over NOW_CHARS characters or NOW_LINES lines.

ai-harness's repository administration publisher excludes this repository
(contract/repository-administration.json), so no harness workflow folds here; this module is the fold.
`check` runs in the self-test and in CI on every pull request, so a note the fold cannot place fails
there, not on main.
"""
import argparse
import datetime as dt
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
NOW = 'NOW.md'
NOTES = 'now-notes'
LOG = Path('docs') / 'history' / 'LOG.md'
# The audit's limits: at most 16,000 characters, under 200 lines, 12 recent bullets, 8 status bullets,
# recent bullets no older than 30 days.
NOW_CHARS = 16000
NOW_LINES = 199
MAX_STATUS = 8
MAX_RECENT = 12
RECENT_DAYS = 30
WHERE = 'Where it is right now'
RECENT = 'What changed recently'
WAITING = 'What is next and what is waiting on Krish'
NOTE_NAME = re.compile(r'^(\d{4}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$')
LABELS = ('Status', 'Changed', 'Next')
NOTE_CHECK = re.compile(r'^North Star check \((\d{4}-\d{2}-\d{2})\): (holds\.|recalibration proposed\.\s+\S.*)$')
# Any earlier check line in NOW.md, whatever it went on to say.
NOW_CHECK = re.compile(r'^- (North Star|Earlier) check \(')
STATUS_BULLET = re.compile(r'^- .*\((\d{4}-\d{2}-\d{2})\)$')
RECENT_DATE = re.compile(r'^- \**(\d{4}-\d{2}-\d{2})')
EM_DASH = '\u2014'


def london_today():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo('Europe/London')).date().isoformat()
    except Exception:  # noqa: BLE001 - no tz database: UTC is within an hour of London
        return dt.datetime.now(dt.timezone.utc).date().isoformat()


# A note ---------------------------------------------------------------------

def parse_note(name, text):
    """{path, date, status, changed, next, check, problems}. Each label starts a line and runs on until the
    next label or a blank line; anything else is a problem, so a note can only say what the fold can place."""
    path = NOTES + '/' + name
    found = NOTE_NAME.match(name)
    note = {'path': path, 'date': found.group(1) if found else None, 'status': None, 'changed': None,
            'next': None, 'check': None, 'problems': []}
    if not found:
        note['problems'].append(path + ' is not named ' + NOTES + '/YYYY-MM-DD-<slug>.md (lowercase letters, '
                                'digits and hyphens)')
        return note
    field = None
    for raw in str(text).replace('\r\n', '\n').split('\n'):
        line = raw.strip()
        if not line:
            field = None
            continue
        label = next((l for l in LABELS if line.startswith(l + ':')), None)
        check = NOTE_CHECK.match(line)
        if label:
            field = label.lower()
            note[field] = line[len(label) + 1:].strip()
        elif check:
            field = None
            note['check'] = line
        elif field:
            note[field] = (note[field] + ' ' + line).strip()
        else:
            note['problems'].append(path + ' has a line the fold cannot place: "' + line[:60] + '". Use only '
                                    'Status:, Changed:, Next: and the North Star check line')
    if not note['status'] or len(note['status']) < 20:
        note['problems'].append(path + ' needs "Status: <what is true now that this work changed>" (a sentence)')
    if not note['next'] or len(note['next']) < 5:
        note['problems'].append(path + ' needs "Next: <the single next action>"')
    if not note['check']:
        note['problems'].append(path + ' needs one line "North Star check (' + str(note['date']) + '): holds." or '
                                '"...: recalibration proposed. <why>"')
    if EM_DASH in str(text):
        note['problems'].append(path + ' contains an em dash; NOW.md never does')
    return note


def _read(path):
    """The file's text with its own line endings (read_text would turn CRLF into LF)."""
    with open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


def _write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)


def read_notes(root=ROOT):
    folder = Path(root) / NOTES
    if not folder.is_dir():
        return []
    return [parse_note(p.name, p.read_text(encoding='utf-8'))
            for p in sorted(folder.glob('*.md')) if p.name.lower() != 'readme.md']


# NOW.md ---------------------------------------------------------------------

def _section(lines, heading):
    """(start, end): the heading's index and the next '## ' heading's (or the end), or None."""
    at = next((i for i, l in enumerate(lines) if l.startswith('## ' + heading)), None)
    if at is None:
        return None
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    return at, end


def _body_start(lines, span):
    i = span[0] + 1
    while i < span[1] and not lines[i].strip():
        i += 1
    return i


def _body_end(lines, span):
    i = span[1]
    while i > span[0] + 1 and not lines[i - 1].strip():
        i -= 1
    return i


def _items(lines, span):
    """Top-level '- ' items in a section, each (start, end) with its indented continuation lines."""
    out, i = [], span[0] + 1
    while i < span[1]:
        if lines[i].startswith('- '):
            j = i + 1
            while j < span[1] and lines[j].startswith((' ', '\t')) and lines[j].strip():
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def fold_note(lines, note):
    """Write one parsed note into NOW.md's lines in place. Returns a problem string or None."""
    where, waiting = _section(lines, WHERE), _section(lines, WAITING)
    recent = _section(lines, RECENT)
    if not where or not waiting or (note['changed'] and not recent):
        return (NOW + ' is missing a section ' + note['path'] + ' needs ("' + WHERE + '", "' + WAITING + '"'
                + (', "' + RECENT + '"' if note['changed'] else '') + ')')
    # What is next: the note's check replaces every old one; its Next replaces every top-level "- Next" item.
    for start, end in reversed(_items(lines, waiting)):
        if NOW_CHECK.match(lines[start]) or re.match(r'^- Next\b', lines[start]):
            del lines[start:end]
    waiting = _section(lines, WAITING)
    lines.insert(_body_start(lines, waiting), '- Next (' + note['date'] + '): ' + note['next'])
    waiting = _section(lines, WAITING)
    lines.insert(_body_end(lines, waiting), '- ' + note['check'])
    # What changed recently: newest first.
    if note['changed']:
        recent = _section(lines, RECENT)
        lines.insert(_body_start(lines, recent), '- ' + note['date'] + ' ' + note['changed'])
    # Where it is right now: on top of its bullets, or after its prose (never above the state line).
    where = _section(lines, WHERE)
    bullet = next((i for i in range(where[0] + 1, where[1]) if lines[i].startswith('- ')), None)
    status = '- ' + note['status'] + ' (' + note['date'] + ')'
    if bullet is not None:
        lines.insert(bullet, status)
    else:
        lines[_body_end(lines, where):_body_end(lines, where)] = ['', status]
    # as_of and the heading move forward, never back.
    stamp = next((m.group(1) for m in (re.match(r'^as_of:\s*(\d{4}-\d{2}-\d{2})\s*$', l) for l in lines) if m), None)
    if stamp is None or stamp < note['date']:
        for i, l in enumerate(lines):
            if re.match(r'^as_of:\s*\d{4}-\d{2}-\d{2}\s*$', l):
                lines[i] = 'as_of: ' + note['date']
            lines[i] = re.sub(r'^(## Where it is right now \(as of )\d{4}-\d{2}-\d{2}(\))', r'\g<1>' + note['date'] + r'\2',
                              lines[i])
    return None


def _move(lines, name, moved, eol, keep, over=None, older_than=None):
    """Move items of one section to moved[name], oldest (bottom) first. Without `over`, while more than `keep`
    remain; with it, while over() says NOW.md is still too big and more than `keep` remain. With `older_than`
    (YYYY-MM-DD), only the items dated before it, whatever their number."""
    while True:
        span = _section(lines, name)
        if not span:
            return
        items = _items(lines, span)
        if name == WHERE:
            items = [it for it in items if STATUS_BULLET.match(' '.join(l.strip() for l in lines[it[0]:it[1]]))]
        if older_than is not None:
            old = [it for it in items if (RECENT_DATE.match(lines[it[0]]) or [None, '9999'])[1] < older_than]
            if not old:
                return
            start, end = old[-1]
        else:
            if len(items) <= keep or (over is not None and not over()):
                return
            start, end = items[-1]
        moved.setdefault(name, []).insert(0, eol.join(lines[start:end]))
        del lines[start:end]


def trim(lines, day, eol='\n'):
    """Keep NOW.md inside the audit's limits: recent items no older than RECENT_DAYS and at most MAX_RECENT,
    at most MAX_STATUS dated status bullets, then under NOW_CHARS characters and NOW_LINES lines, taking
    recent items first and never the newest status. Returns {section: [moved items, newest first]}."""
    moved = {}
    over = lambda: len(eol.join(lines)) > NOW_CHARS or len(lines) > NOW_LINES  # noqa: E731
    cutoff = (dt.date.fromisoformat(day) - dt.timedelta(days=RECENT_DAYS)).isoformat()
    _move(lines, RECENT, moved, eol, 0, older_than=cutoff)
    _move(lines, RECENT, moved, eol, MAX_RECENT)
    _move(lines, WHERE, moved, eol, MAX_STATUS)
    _move(lines, RECENT, moved, eol, 0, over)
    _move(lines, WHERE, moved, eol, 1, over)
    return moved


RELATIVE_LINK = re.compile(r'\]\((?![a-z][a-z0-9+.-]*:|#|/)([^)\s]+)\)', re.I)


def from_history(text):
    """A NOW.md line as it reads from docs/history/: the same words, its relative links pointing back up to the
    repository root, so a link that worked in NOW.md still works in LOG.md."""
    return RELATIVE_LINK.sub(r'](../../\1)', text)


def log_entry(moved, day, eol='\n'):
    """The block docs/history/LOG.md gains: the moved lines, verbatim (relative links re-pointed from there)."""
    out = ['## ' + day, '', 'Moved verbatim from `NOW.md` (closeout fold, to keep NOW.md inside the audit\'s limits).',
           '']
    for name in (RECENT, WHERE):
        if moved.get(name):
            out += ['From "' + name + '":', ''] + [from_history(item) for item in moved[name]] + ['']
    return eol.join(out)


def add_to_log(log_text, entry, eol='\n'):
    """Newest first: the entry goes above the first dated '## ' heading."""
    lines = log_text.split(eol)
    at = next((i for i, l in enumerate(lines) if l.startswith('## ')), len(lines))
    return eol.join(lines[:at] + entry.split(eol) + lines[at:])


def fold(root=ROOT, head=None, day=None, write=True):
    """Fold every note in now-notes/ into NOW.md and delete it; trim NOW.md into docs/history/LOG.md.
    Returns {folded, problems, moved, size}."""
    root = Path(root)
    day = day or london_today()
    notes = read_notes(root)
    result = {'folded': [], 'problems': [], 'moved': {}, 'size': None}
    if not notes:
        return result
    now_path, log_path = root / NOW, root / LOG
    if not now_path.is_file():
        result['problems'].append(NOW + ' does not exist; ' + str(len(notes)) + ' note(s) wait in ' + NOTES + '/')
        return result
    text = _read(now_path)
    eol = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(eol)
    for note in sorted(notes, key=lambda n: n['path']):
        if note['problems']:
            result['problems'] += note['problems']
            continue
        problem = fold_note(lines, note)
        if problem:
            result['problems'].append(problem)
            continue
        result['folded'].append(note['path'])
    if not result['folded']:
        return result
    if head and re.match(r'^[0-9a-f]{7,40}$', head):
        lines = [('head: ' + head[:7]) if re.match(r'^head:\s*\S+\s*$', l) else l for l in lines]
    moved = trim(lines, day, eol)
    text = eol.join(lines)
    result['moved'], result['size'] = moved, len(text)
    if len(text) > NOW_CHARS or len(lines) > NOW_LINES:
        result['problems'].append(NOW + ' is ' + str(len(text)) + ' characters and ' + str(len(lines)) + ' lines '
                                  'after the fold, over the audit\'s limits; shorten its prose by hand')
    if write:
        _write(now_path, text)
        if moved:
            log = _read(log_path) if log_path.is_file() else '# History\n'
            log_eol = '\r\n' if '\r\n' in log else '\n'
            _write(log_path, add_to_log(log, log_entry(moved, day, log_eol), log_eol))
        for path in result['folded']:
            (root / path).unlink()
    return result


def command(argv, root=ROOT, out=print):
    parser = argparse.ArgumentParser(prog='growth.py closeout', description='Closeout notes: check them, or fold '
                                     'them into NOW.md on main (engine/closeout.py).')
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser('check', help='every note in now-notes/ is one the fold can place')
    f = sub.add_parser('fold', help='fold every note into NOW.md and delete it (the fold job on main)')
    f.add_argument('--head', help='the commit NOW.md now describes (7 or more hex characters)')
    f.add_argument('--today', help='YYYY-MM-DD for the history entry and the age cut (default: today in London)')
    f.add_argument('--dry-run', action='store_true', help='say what would change; write nothing')
    args = parser.parse_args(argv)
    if args.cmd == 'check':
        notes = read_notes(root)
        problems = [p for n in notes for p in n['problems']]
        for p in problems:
            out(p)
        out(str(len(notes)) + ' closeout note(s), ' + str(len(problems)) + ' problem(s)')
        return int(bool(problems))
    if args.cmd == 'fold':
        result = fold(root, args.head, args.today, write=not args.dry_run)
        for path in result['folded']:
            out(('would fold ' if args.dry_run else 'folded ') + path)
        for name, items in result['moved'].items():
            out(('would move ' if args.dry_run else 'moved ') + str(len(items)) + ' item(s) of "' + name
                + '" to ' + LOG.as_posix())
        for p in result['problems']:
            out(('::error::' if not args.dry_run else '') + p)
        if not result['folded'] and not result['problems']:
            out('No closeout notes to fold.')
        return int(bool(result['problems']))
    parser.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(command(sys.argv[1:]))
