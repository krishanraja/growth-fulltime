"""The Librarian: one private home for everything the engine makes (docs/ENGINE-V2.md, section 2a).

Growth Build in Drive (Ventures, Full Time) holds every strategy, format lock,
run, learning report, brand-kit receipt and backup the engine produces. Its tree
is fixed, every name follows one pattern, and INDEX.csv carries exactly one row
per file. This module is the rulebook and the planner:

- name_errors() and folder_errors() say which rule a path breaks;
- read_index() and write_index() keep INDEX.csv in one exact shape;
- reconcile() compares a Drive listing with the index and finds the sprawl, and
  hold() turns an unclean result into the LIBRARY hold for Control Center;
- canva_reconcile() checks the Canva Growth/ mirror the same way (rule 8), and
  stamp_errors() checks the source stamp on a Drive copy of a public doc (rule 9);
- file_plan() and archive_plan() say what to file or move, never what to delete;
- bundle() and assemble() make and check the numbered-part backups that the
  Drive connector's 100 MB upload cap needs, ported from the 27 October
  handoff's assemble_fulltime_handoff.py.

Nothing here talks to Drive or any platform, changes sharing or deletes a library
file. A caller moves or uploads exactly what a plan names, then reads it back."""
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import zipfile

from . import spec

TREE = ('00_START-HERE', '01_Strategy', '02_Formats', '03_Runs', '04_Learning', '05_Brand-Kit',
        '06_Reference', '99_Archive')
INDEX_FIELDS = ('path', 'kind', 'week', 'match', 'format', 'pundit', 'channel', 'status', 'sha256', 'bytes',
                'drive_file_id', 'source')
# The 27 October handoff moved here unrenamed, so its files keep their original names.
# Only that adopted date is exempt from rule 3: a later handoff folder follows the pattern.
ADOPTED = '06_Reference/creative-handoff/'
ADOPTED_DATES = ('2026-10-27',)
ARCHIVE = '99_Archive/'
# An archived file keeps its top folder and name, and its original subfolders become one
# folder joined by JOIN, so 99_Archive stays within rule 2's depth. No tree folder name
# holds two hyphens in a row, so the original path is always recoverable.
JOIN = '--'
FORMATS = spec.FORMATS
CHANNELS = spec.CHANNELS
START_FILES = ('START-HERE.md', 'INDEX.csv')
INDEX_PATH = '00_START-HERE/INDEX.csv'   # the index never holds a row for itself
RUN_FILES = ('pack.json', 'review.json')
REFERENCE = ('baseline', 'rulings', 'backups', ADOPTED.split('/')[1])
STATUSES = ('draft', 'reviewed', 'verdict', 'posted', 'current', 'reference', 'superseded', 'rejected')
ARCHIVE_STATUSES = ('superseded', 'rejected')
DIMS = ('week', 'match', 'format', 'pundit', 'channel', 'status', 'drive_file_id')
PENDING = 'pending-local'      # a row whose bytes were not hashed yet
MAX_DEPTH = 4                  # folders below Growth Build, 99_Archive included
PART_BYTES = 90 * 1024 * 1024
UPLOAD_CAP = 100 * 1000 * 1000  # the Drive connector's upload cap
BLOCK = 4 * 1024 * 1024
ZIP64 = (1 << 31) - 1

TREE_RULE = 'rule 2, fixed tree'
DEPTH_RULE = 'rule 2, depth'
NAME_RULE = 'rule 3, one name pattern'
INDEX_RULE = 'rule 4, one row per file'
KEEP_RULE = 'rule 5, never overwrite'

SLUG = r'[a-z0-9]+(?:-[a-z0-9]+)*'
PAIR = r'[a-z0-9]+(?:-[a-z0-9]+)+'
WEEK = re.compile(r'^([0-9]{4})-W([0-9]{2})$')
DATE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
VERSIONED = re.compile(r'^([0-9]{4}-W[0-9]{2})_(' + SLUG + r')_v[1-9][0-9]*\.[a-z0-9]+$')
REPORT = re.compile(r'^([0-9]{4}-W[0-9]{2})_learning-report_v[1-9][0-9]*\.md$')
DATED = re.compile(r'^([0-9]{4}-[0-9]{2}-[0-9]{2})_(baseline|rulings)_v[1-9][0-9]*\.json$')
MATCH_FOLDER = re.compile(r'^([0-9]{4}-[0-9]{2}-[0-9]{2})_(' + PAIR + r')$')
INSTANCE = re.compile(r'^([0-9]{4}-[0-9]{2}-[0-9]{2})_(' + '|'.join(FORMATS) + r')_(' + SLUG + r')_(' + PAIR
                      + r')_(' + '|'.join(sorted(CHANNELS, key=len, reverse=True)) + r')_([A-Z0-9_]+)\.[a-z0-9]+$')
ENGINE_NAME = re.compile(r'^[a-z0-9]+(?:[._-][a-z0-9]+)*\.[a-z0-9]+$')
STEM = re.compile(r'^[a-z0-9]+(?:[_-][a-z0-9]+)*$')
PART = re.compile(r'^[a-z0-9]+(?:[._-][a-z0-9]+)*\.zip\.part[0-9]{2,}$')
MANIFEST = re.compile(r'^[a-z0-9]+(?:[._-][a-z0-9]+)*\.json$')
LOCK = re.compile(r'^(?:unlocked|[0-9a-f]{64}|v[1-9][0-9]*)$')
SHA = re.compile(r'^[0-9a-f]{64}$')
DIGITS = re.compile(r'^[0-9]+$')
DRIVE_ID = re.compile(r'^[A-Za-z0-9_-]*$')
# Names Windows cannot hold, or holds as another file, on the H: mount of Growth Build.
WINDOWS_BAD = re.compile(r'[<>:"|?*]')
WINDOWS_DEVICES = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{d}{n}' for d in ('COM', 'LPT') for n in range(1, 10)}
STAMP_RULE = 'rule 9, single source'
STAMP = re.compile(r'^source: (\S+)@([0-9a-f]{7,40})$')
CANVA_RULE = 'rule 8, Canva mirrors the tree'
TEMPLATE = re.compile(r'^template_[0-9]+x[0-9]+_[a-z0-9]+(?:[_-][a-z0-9]+)*$')

LAYOUT = {
    '00_START-HERE': '00_START-HERE/START-HERE.md or 00_START-HERE/INDEX.csv',
    '01_Strategy': '01_Strategy/<YYYY-Www>/<YYYY-Www>_<kind>_v<n>.<ext>',
    '02_Formats': '02_Formats/<format_id>/<lock>/<name>',
    '03_Runs': ('03_Runs/<YYYY-Www>/<YYYY-MM-DD>_<home>-<away>/ holding pack.json, review.json or '
                '<YYYY-MM-DD>_<format>_<pundit>_<home>-<away>_<channel>_<CREATIVE_ID>.<ext>'),
    '04_Learning': '04_Learning/register.csv or 04_Learning/<YYYY-Www>/<YYYY-Www>_learning-report_v<n>.md',
    '05_Brand-Kit': '05_Brand-Kit/<YYYY-Www>_<kind>_v<n>.<ext>',
    '06_Reference': ('06_Reference/baseline/<YYYY-MM-DD>_baseline_v<n>.json, '
                     '06_Reference/rulings/<YYYY-MM-DD>_rulings_v<n>.json, '
                     '06_Reference/backups/<YYYY-MM-DD>/<part or manifest> or '
                     '06_Reference/creative-handoff/<YYYY-MM-DD>/<adopted name>'),
    '99_Archive': ("99_Archive/<YYYY-Www>/<top folder>/<its original subfolders joined by -->/<original name>, "
                   'for example 99_Archive/2026-W45/03_Runs/2026-W44--2026-10-31_reds-blues/pack.json'),
}


def _growth():
    import growth
    return growth


def _week(value):
    """The week text when it names a real ISO week (YYYY-Www), else None."""
    m = WEEK.match(value or '')
    if not m:
        return None
    try:
        dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return None
    return value


def _date(value):
    if not isinstance(value, str) or not DATE.match(value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def week_of(day):
    """The YYYY-Www week a date falls in (Monday to Sunday, as matchweeks run)."""
    year, week = day.isocalendar()[:2]
    return f'{year:04d}-W{week:02d}'


def _parts(path, folder=False):
    """A library path split into its parts, or (None, why it is not a usable path)."""
    if not isinstance(path, str) or not path.strip():
        return None, 'a path must be text relative to Growth Build'
    if folder:
        path = path.rstrip('/')
    if '\\' in path or path.startswith('/') or path[1:2] == ':':
        return None, 'use forward slashes and a path relative to Growth Build'
    if any(ord(c) < 32 or c == '\x7f' for c in path):
        return None, 'a path has no control characters or line breaks'
    parts = path.split('/')
    if any(p in ('', '.', '..') for p in parts):
        return None, 'a path has no empty, "." or ".." parts'
    return parts, None


def _walk(folders, steps, layout):
    """The first folder below the top one that breaks its step, as a message."""
    if len(folders) - 1 > len(steps):
        return f'{TREE_RULE}: {"/".join(folders)} goes deeper than {layout}'
    for segment, (test, what) in zip(folders[1:], steps):
        if not test(segment, folders):
            return f'{TREE_RULE}: {segment!r} is not {what}; the layout is {layout}'
    return None


def _versioned(name, week):
    """Errors and the week for a <YYYY-Www>_<kind>_v<n>.<ext> name."""
    m = VERSIONED.match(name)
    if not m:
        return [f'{NAME_RULE}: {name!r} is not <YYYY-Www>_<kind>_v<n>.<ext>: lowercase ASCII, hyphens within parts, underscores between them'], None
    if not _week(m.group(1)):
        return [f'{NAME_RULE}: {m.group(1)} in {name!r} is not a real week'], None
    if week and m.group(1) != week:
        return [f'{NAME_RULE}: {name!r} carries week {m.group(1)} but sits in the {week} folder'], None
    return [], m.group(1)


def _instance(name):
    """Errors and the format, pundit, match and channel of a run instance name."""
    m = INSTANCE.match(name)
    if not m:
        return [f'{NAME_RULE}: {name!r} is not <YYYY-MM-DD>_<format>_<pundit>_<home>-<away>_<channel>_'
                f'<CREATIVE_ID>.<ext>: lowercase ASCII, hyphens within parts, underscores between them, the creative ID in its own uppercase form, with format one of {", ".join(FORMATS)} '
                f'and channel one of {", ".join(CHANNELS)}'], {}
    day, fmt, pundit, match, channel, creative_id = m.groups()
    dims = {'format': fmt, 'pundit': pundit, 'match': match, 'channel': channel}
    if not _date(day):
        return [f'{NAME_RULE}: {day} in {name!r} is not a real date'], dims
    if not _growth().CREATIVE_ID.match(creative_id):
        return [f'{NAME_RULE}: {creative_id} in {name!r} is not a creative ID (PLAYBOOK.md, "Creative ids")'], dims
    prefix = spec.CHANNEL_PREFIX.get(channel)
    if prefix and creative_id.split('_')[0] != prefix:
        return [f'{NAME_RULE}: {creative_id} in {name!r} is not a {channel} creative ID, which starts {prefix}_'], dims
    return [], dims


def _start_here(folders, name):
    if len(folders) > 1:
        return [f'{TREE_RULE}: 00_START-HERE has no subfolders; the layout is {LAYOUT["00_START-HERE"]}'], {}
    if name is not None and name not in START_FILES:
        return [f'{NAME_RULE}: 00_START-HERE holds only START-HERE.md and INDEX.csv, not {name!r}'], {}
    return [], {}


def _strategy(folders, name):
    layout = LAYOUT['01_Strategy']
    error = _walk(folders, [(lambda s, f: _week(s), 'a week folder (YYYY-Www)')], layout)
    if error:
        return [error], {}
    dims = {'week': folders[1]} if len(folders) > 1 else {}
    if name is None:
        return [], dims
    if len(folders) != 2:
        return [f'{TREE_RULE}: strategy files sit in a week folder; the layout is {layout}'], dims
    return _versioned(name, folders[1])[0], dims


def _formats(folders, name):
    layout = LAYOUT['02_Formats']
    error = _walk(folders, [(lambda s, f: s in FORMATS, f'a format ({", ".join(FORMATS)})'),
                            (lambda s, f: LOCK.match(s), "a lock ('unlocked', a 64-character SHA-256 or v<n>)")],
                  layout)
    if error:
        return [error], {}
    dims = {'format': folders[1]} if len(folders) > 1 else {}
    if name is None:
        return [], dims
    if len(folders) != 3:
        return [f'{TREE_RULE}: format files sit in a lock folder; the layout is {layout}'], dims
    if ENGINE_NAME.match(name):
        return [], dims
    errors, found = _instance(name)
    if errors:
        return [f'{NAME_RULE}: {name!r} is neither a lowercase <name>.<ext> nor a run instance name'] + errors, dims
    if found['format'] != folders[1]:
        return [f'{NAME_RULE}: {name!r} is a {found["format"]} piece but sits under {folders[1]}'], dims
    return [], dict(dims, **found)


def _match_folder(segment, week):
    m = MATCH_FOLDER.match(segment)
    day = _date(m.group(1)) if m else None
    return bool(day) and week_of(day) == week


def _runs(folders, name):
    layout = LAYOUT['03_Runs']
    error = _walk(folders, [(lambda s, f: _week(s), 'a week folder (YYYY-Www)'),
                            (lambda s, f: _match_folder(s, f[1]),
                             'a match folder <YYYY-MM-DD>_<home>-<away> dated inside its week')], layout)
    if error:
        return [error], {}
    dims = {'week': folders[1]} if len(folders) > 1 else {}
    if len(folders) > 2:
        dims['match'] = MATCH_FOLDER.match(folders[2]).group(2)
    if name is None:
        return [], dims
    if len(folders) != 3:
        return [f'{TREE_RULE}: run files sit in a match folder; the layout is {layout}'], dims
    if name in RUN_FILES:
        return [], dims
    errors, found = _instance(name)
    if errors:
        return errors, dims
    if found['match'] != dims['match']:
        return [f'{NAME_RULE}: {name!r} names {found["match"]} but sits in the {folders[2]} folder'], dims
    return [], dict(dims, **found)


def _learning(folders, name):
    layout = LAYOUT['04_Learning']
    error = _walk(folders, [(lambda s, f: _week(s), 'a week folder (YYYY-Www)')], layout)
    if error:
        return [error], {}
    dims = {'week': folders[1]} if len(folders) > 1 else {}
    if name is None:
        return [], dims
    if len(folders) == 1:
        ok = name == 'register.csv'
    else:
        m = REPORT.match(name)
        ok = bool(m) and m.group(1) == folders[1]
    return ([] if ok else [f'{NAME_RULE}: {name!r} does not fit {layout}']), dims


def _brand_kit(folders, name):
    if len(folders) > 1:
        return [f'{TREE_RULE}: 05_Brand-Kit has no subfolders; the layout is {LAYOUT["05_Brand-Kit"]}'], {}
    if name is None:
        return [], {}
    errors, week = _versioned(name, None)
    return errors, ({'week': week} if week else {})


def _reference(folders, name):
    layout = LAYOUT['06_Reference']
    sub = folders[1] if len(folders) > 1 else None
    steps = [(lambda s, f: s in REFERENCE, f'one of {", ".join(REFERENCE)}')]
    if sub in ('backups', REFERENCE[3]):
        steps.append((lambda s, f: _date(s), 'a date folder (YYYY-MM-DD)'))
    error = _walk(folders, steps, layout)
    if error:
        return [error], {}
    dims = {'week': week_of(_date(folders[2]))} if len(folders) > 2 else {}
    if name is None:
        return [], dims
    if len(folders) != len(steps) + 1:
        return [f'{TREE_RULE}: reference files sit inside {", ".join(REFERENCE)}; the layout is {layout}'], dims
    if sub in ('baseline', 'rulings'):
        m = DATED.match(name)
        if not m or m.group(2) != sub or not _date(m.group(1)):
            return [f'{NAME_RULE}: {name!r} is not <YYYY-MM-DD>_{sub}_v<n>.json'], dims
        return [], {'week': week_of(_date(m.group(1)))}
    if sub == 'backups' and not (PART.match(name) or MANIFEST.match(name)):
        return [f'{NAME_RULE}: a backup folder holds only numbered parts (<name>.zip.partNN) and manifests '
                f'(<name>.json) in lowercase ASCII, not {name!r}'], dims
    if sub == REFERENCE[3] and folders[2] not in ADOPTED_DATES and not ENGINE_NAME.match(name):
        return [f'{NAME_RULE}: only the adopted {", ".join(ADOPTED_DATES)} handoff keeps its original names; '
                f'{name!r} must be a lowercase <name>.<ext>'], dims
    return [], dims       # adopted handoff files keep their original names


def _windows_errors(name):
    """Why Windows could not hold this original name as its own file, if it could not."""
    stem = name.split('.')[0].rstrip(' ').upper()
    if WINDOWS_BAD.search(name) or stem in WINDOWS_DEVICES or name[-1] in '. ':
        return [f'{NAME_RULE}: {name!r} is not a name Windows can hold as its own file (no <>:"|?*, no device '
                'name such as CON or AUX, and no trailing dot or space)']
    return []


def _windows_key(path):
    """The path as Windows compares it: case folded, trailing dots and spaces dropped from each part."""
    return '/'.join(part.rstrip('. ').casefold() for part in path.split('/'))


CHECKS = {'00_START-HERE': _start_here, '01_Strategy': _strategy, '02_Formats': _formats, '03_Runs': _runs,
          '04_Learning': _learning, '05_Brand-Kit': _brand_kit, '06_Reference': _reference}


def _check(parts, folder):
    """Every rule a split path breaks, and the index columns its name gives."""
    if not folder and len(parts) == 1:
        return [f'{TREE_RULE}: nothing sits at the top of Growth Build; file it inside a numbered folder'], {}
    top = parts[0]
    if top not in TREE:
        return [f'{TREE_RULE}: {top!r} is not one of the numbered folders ({", ".join(TREE)})'], {}
    if top == TREE[-1] and len(parts) > 2 and parts[2] == top:
        return [f'{TREE_RULE}: an archived copy is never archived again'], {}
    depth = len(parts) - (0 if folder else 1)
    if depth > MAX_DEPTH:
        return [f'{DEPTH_RULE}: {depth} folders deep; Growth Build allows at most {MAX_DEPTH}'], {}
    if top != TREE[-1]:
        folders, name = (parts, None) if folder else (parts[:-1], parts[-1])
        errors, dims = CHECKS[top](folders, name)
        return (errors or ([] if folder else _windows_errors(name))), dims
    if len(parts) > 1 and not _week(parts[1]):
        return [f'{TREE_RULE}: {parts[1]!r} is not a week folder; the layout is {LAYOUT[top]}'], {}
    if len(parts) <= (2 if folder else 3):
        if folder:
            return [], {}
        return [f'{TREE_RULE}: an archived file keeps its top folder and name; the layout is {LAYOUT[top]}'], {}
    original = _unarchived(parts[2:], folder)
    if original is None:
        return [f'{TREE_RULE}: {"/".join(parts[3:])!r} does not join its original subfolders with {JOIN}; '
                f'the layout is {LAYOUT[top]}'], {}
    return _check(original, folder)


def _unarchived(rest, folder):
    """The original path parts of an archived path below 99_Archive/<week>/, or None."""
    joined = rest[1:] if folder else rest[1:-1]
    middle = joined[0].split(JOIN) if joined else []
    if '' in middle:
        return None
    return [rest[0]] + middle + ([] if folder else [rest[-1]])


def archived_path(path, week):
    """Where a filed path goes in 99_Archive at the close of week, within the depth limit."""
    parts = path.split('/')
    folders = [JOIN.join(parts[1:-1])] if len(parts) > 2 else []
    return '/'.join([TREE[-1], week, parts[0]] + folders + [parts[-1]])


def name_errors(path):
    """Every rule the path of one file breaks, as plain sentences; [] when it may be filed."""
    parts, error = _parts(path)
    if error:
        return [f'{path!r}: {error}']
    return [f'{path}: {e}' for e in _check(parts, False)[0]]


def folder_errors(path):
    """Every rule a folder path breaks; [] when the folder is part of the fixed tree."""
    parts, error = _parts(path, folder=True)
    if error:
        return [f'{path!r}: {error}']
    return [f'{path}: {e}' for e in _check(parts, True)[0]]


def _row(row):
    if not isinstance(row, dict):
        return row
    return {k: ('' if v is None else str(v) if type(v) is int else v) for k, v in row.items()}


def _rows(rows):
    """Rows with whole numbers as text, checked; a caller may pass bytes as an int."""
    return _check_rows([_row(row) for row in rows] if isinstance(rows, list) else rows)


def _check_rows(rows):
    """Refuse index rows that are not exactly one well-formed row per path."""
    if not isinstance(rows, list):
        raise ValueError('index rows must be a list')
    seen = set()
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) != set(INDEX_FIELDS):
            raise ValueError(f'index row {number} must have exactly the fields {", ".join(INDEX_FIELDS)}')
        if any(not isinstance(v, str) or '\n' in v or '\r' in v for v in row.values()):
            raise ValueError(f'index row {number} must hold text on one line in every field')
        path = row['path']
        if _parts(path)[1]:
            raise ValueError(f'index row {number}: {path!r} is not a path relative to Growth Build')
        if path in seen:
            raise ValueError(f'{INDEX_RULE}: {path} has more than one row in INDEX.csv')
        seen.add(path)
        checks = (
            (row['kind'] and row['source'], 'needs a kind and a source'),
            (SHA.match(row['sha256']) or row['sha256'] == PENDING, f'sha256 must be 64 lowercase hex or {PENDING}'),
            (DIGITS.match(row['bytes']), 'bytes must be a whole number'),
            (row['status'] in STATUSES, f'status must be one of {", ".join(STATUSES)}'),
            (not row['week'] or _week(row['week']), 'week must be YYYY-Www'),
            (not row['format'] or row['format'] in FORMATS, f'format must be one of {", ".join(FORMATS)}'),
            (not row['channel'] or row['channel'] in CHANNELS, f'channel must be one of {", ".join(CHANNELS)}'),
            (DRIVE_ID.match(row['drive_file_id']), 'drive_file_id must be a Drive file ID or empty'),
        )
        for ok, why in checks:
            if not ok:
                raise ValueError(f'INDEX.csv row for {path}: {why}')
    return rows


def read_index(text):
    """INDEX.csv text as a list of rows (dicts of text), refusing any other header or shape."""
    if not isinstance(text, str):
        raise ValueError('INDEX.csv must be read as text')
    lines = list(csv.reader(io.StringIO(text[1:] if text.startswith('\ufeff') else text, newline='')))
    if not lines or tuple(lines[0]) != INDEX_FIELDS:
        raise ValueError('INDEX.csv must start with exactly this header: ' + ','.join(INDEX_FIELDS))
    rows = []
    for number, values in enumerate(lines[1:], start=2):
        if not values:
            continue
        if len(values) != len(INDEX_FIELDS):
            raise ValueError(f'INDEX.csv line {number} has {len(values)} fields, not {len(INDEX_FIELDS)}')
        rows.append(dict(zip(INDEX_FIELDS, values)))
    return _check_rows(rows)


def write_index(rows):
    """INDEX.csv text: exactly INDEX_FIELDS as the header, LF line endings, rows sorted by path."""
    rows = _rows(rows)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(INDEX_FIELDS)
    for row in sorted(rows, key=lambda r: r['path']):
        writer.writerow([row[key] for key in INDEX_FIELDS])
    return out.getvalue()


def _listing(listing):
    """The Drive listing as (path, bytes, is_folder) entries; the root itself is skipped."""
    if not isinstance(listing, list):
        raise ValueError('a library listing must be a list of {path, bytes, is_folder}')
    out = []
    for number, entry in enumerate(listing, start=1):
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) \
                or type(entry.get('is_folder')) is not bool:
            raise ValueError(f'listing entry {number} needs a text path and a true or false is_folder')
        size = entry.get('bytes')
        if size is not None and (type(size) is not int or size < 0):
            raise ValueError(f'listing entry {number}: bytes must be a whole number or null')
        path = entry['path'].rstrip('/') if entry['is_folder'] else entry['path']
        if path not in ('', '.'):
            out.append((path, size, entry['is_folder']))
    return out


def reconcile(listing, rows):
    """Compare a Growth Build listing with the INDEX rows and report every kind of sprawl.

    outside_tree, orphans (files with no row), missing (rows with no file) and
    pending_hashes are sorted paths; misnamed is [{path, errors}]; duplicates is
    [{sha256, paths}], where sha256 None marks one path (file or folder) listed more
    than once, as Drive allows two same-named items under one parent;
    size_mismatch is [{path, listed_bytes, indexed_bytes}]. clean is true only when
    every list except pending_hashes is empty. INDEX.csv itself needs no row, and a
    listed file whose bytes are null (a Drive-native document) skips the size check."""
    entries = _listing(listing)
    rows = _rows(rows)
    by_path = {row['path']: row for row in rows}
    outside, misnamed, orphans, sizes, files, folders = [], [], [], [], {}, {}
    for path, size, is_folder in entries:
        parts, error = _parts(path, folder=is_folder)
        if is_folder:
            folders[path] = folders.get(path, 0) + 1
            if error or _check(parts, True)[0]:
                outside.append(path)
            continue
        files.setdefault(path, []).append(size)
        if error or len(parts) == 1 or _check(parts[:-1], True)[0]:
            outside.append(path)
        else:
            errors = name_errors(path)
            if errors:
                misnamed.append({'path': path, 'errors': errors})
        row = by_path.get(path)
        if row is None:
            if path != INDEX_PATH:
                orphans.append(path)
        elif size is not None and str(size) != row['bytes']:
            sizes.append({'path': path, 'listed_bytes': size, 'indexed_bytes': int(row['bytes'])})
    by_sha = {}
    for row in rows:
        if row['sha256'] != PENDING:
            by_sha.setdefault(row['sha256'], []).append(row['path'])
    duplicates = [{'sha256': sha, 'paths': sorted(paths)} for sha, paths in sorted(by_sha.items()) if len(paths) > 1]
    duplicates += [{'sha256': None, 'paths': [path] * count} for path, count in
                   sorted([(p, len(found)) for p, found in files.items()] + list(folders.items())) if count > 1]
    result = {'outside_tree': sorted(set(outside)), 'misnamed': sorted(misnamed, key=lambda m: m['path']),
              'orphans': sorted(set(orphans)), 'missing': sorted(p for p in by_path if p not in files),
              'duplicates': duplicates, 'size_mismatch': sorted(sizes, key=lambda s: s['path']),
              'pending_hashes': sorted(row['path'] for row in rows if row['sha256'] == PENDING)}
    result['clean'] = not any(result[key] for key in result if key != 'pending_hashes')
    return result


HOLD_COUNTS = (('outside_tree', 'item outside the fixed tree', 'items outside the fixed tree'),
               ('misnamed', 'misnamed file', 'misnamed files'),
               ('orphans', 'file with no index row', 'files with no index row'),
               ('missing', 'index row with no file', 'index rows with no file'),
               ('duplicates', 'set of duplicates', 'sets of duplicates'),
               ('size_mismatch', 'size that does not match its row', 'sizes that do not match their rows'))


def hold(result, place='The Growth Build library'):
    """None when the library is clean, else the LIBRARY entry for the report's holds.
    place names what was reconciled, such as 'The Canva Growth folder'."""
    if result.get('clean'):
        return None
    sizes = [(len(result.get(key) or []), one, many) for key, one, many in HOLD_COUNTS]
    counts = [f'{n} {one if n == 1 else many}' for n, one, many in sizes if n]
    if not counts:
        return {'code': 'LIBRARY', 'detail': f'{place} did not reconcile cleanly.'}
    listed = counts[0] if len(counts) == 1 else ', '.join(counts[:-1]) + ' and ' + counts[-1]
    return {'code': 'LIBRARY', 'detail': f'{place} needs tidying: {listed}.'}


def canva_reconcile(listing):
    """Check the Canva Growth/ mirror (rule 8) the way reconcile() checks Drive.

    listing is [{path, is_folder}] relative to the Full Time project's Growth folder,
    with bytes null or left out. Growth holds only Templates and real week folders
    (YYYY-Www, the Drive tree's names), one level deep; each template is named
    template_<size>_<use>. Week designs are not name-checked: the plan sets no pattern
    for them yet. Returns outside_tree, misnamed, duplicates and clean, which hold()
    reads with place='The Canva Growth folder'."""
    if not isinstance(listing, list):
        raise ValueError('a Canva listing must be a list of {path, is_folder}')
    entries = _listing([dict(e, bytes=None) if isinstance(e, dict) else e for e in listing])
    outside, misnamed, seen = [], [], {}
    for path, _, is_folder in entries:
        seen[path] = seen.get(path, 0) + 1
        parts, error = _parts(path, folder=is_folder)
        home = None if error else parts[0]
        if error or (home != 'Templates' and not _week(home)) or len(parts) > (1 if is_folder else 2) \
                or (not is_folder and len(parts) == 1):
            outside.append(path)
        elif home == 'Templates' and not is_folder and not TEMPLATE.match(parts[1]):
            misnamed.append({'path': path, 'errors': [f'{path}: {CANVA_RULE}: {parts[1]!r} is not '
                                                       'template_<size>_<use>, such as template_1080x1920_cover']})
    duplicates = [{'sha256': None, 'paths': [path] * n} for path, n in sorted(seen.items()) if n > 1]
    result = {'outside_tree': sorted(set(outside)), 'misnamed': sorted(misnamed, key=lambda m: m['path']),
              'duplicates': duplicates}
    result['clean'] = not any(result.values())
    return result


def stamp_errors(text, repo_path=None):
    """Why a Drive copy of a public doc does not carry its one source stamp (rule 9): a line
    reading exactly 'source: <repo path>@<commit>', naming repo_path when it is given."""
    if not isinstance(text, str):
        return [f'{STAMP_RULE}: the Drive copy must be read as text']
    stamps = [STAMP.match(line.strip()) for line in text.splitlines() if line.strip().startswith('source:')]
    if not stamps:
        return [f'{STAMP_RULE}: the Drive copy carries no "source: <path>@<commit>" stamp']
    if len(stamps) > 1:
        return [f'{STAMP_RULE}: the Drive copy carries {len(stamps)} source lines; it needs exactly one']
    if not stamps[0]:
        return [f'{STAMP_RULE}: the source line must read "source: <repo path>@<commit>", with the commit '
                'in 7 to 40 lowercase hex']
    path = stamps[0].group(1)
    if _parts(path)[1] or path.startswith('local/'):
        return [f'{STAMP_RULE}: {path!r} is not a public repo path']
    if repo_path is not None and path != repo_path:
        return [f'{STAMP_RULE}: the stamp names {path}, not {repo_path}']
    return []


def file_plan(rows, path, sha256, bytes, kind, source, **dims):
    """The INDEX row for filing a new file, or the existing copy to link when the bytes are already filed.

    dims are week, match, format, pundit, channel, status (draft by default) and
    drive_file_id. Columns the path's name gives are filled from it, and a dim
    that disagrees with the name is refused."""
    errors = name_errors(path)
    if errors:
        raise ValueError('; '.join(errors))
    if not (isinstance(sha256, str) and (SHA.match(sha256) or sha256 == PENDING)):
        raise ValueError(f'{path}: sha256 must be 64 lowercase hex characters or {PENDING}')
    if type(bytes) is not int or bytes < 0:
        raise ValueError(f'{path}: bytes must be a whole number')
    unknown = sorted(set(dims) - set(DIMS))
    if unknown:
        raise ValueError(f'{path}: unknown index columns {", ".join(unknown)}; use {", ".join(DIMS)}')
    rows = _rows(rows)
    if sha256 != PENDING:
        for row in rows:
            if row['sha256'] == sha256:
                return {'action': 'link_existing', 'path': row['path']}
    key = _windows_key(path)
    for row in rows:
        if _windows_key(row['path']) == key:
            twin = '' if row['path'] == path else f' (as {row["path"]}, the same file on Windows)'
            raise ValueError(f'{KEEP_RULE}: {path} is already filed with other bytes{twin}; '
                             'a new version is a new _v<n> file')
    derived = _check(path.split('/'), False)[1]
    row = dict.fromkeys(INDEX_FIELDS, '')
    row.update(derived, status='draft')
    for key, value in dims.items():
        value = '' if value is None else str(value)
        if key in derived and value and value != derived[key]:
            raise ValueError(f'{path}: its name gives {key} {derived[key]}, not {value}')
        if value:
            row[key] = value
    row.update(path=path, kind=kind if isinstance(kind, str) else '', sha256=sha256, bytes=str(bytes),
               source=source if isinstance(source, str) else '')
    _check_rows([row])
    return {'action': 'file', 'row': row}


def archive_plan(rows, week):
    """The moves that close a week: superseded and rejected files go to 99_Archive/<week>/
    (archived_path: the top folder, the original subfolders joined by --, the name).

    Only moves are ever planned. A move that would land on a path already in the
    index (as Windows compares paths) is refused, so nothing is overwritten."""
    if not isinstance(week, str) or not _week(week):
        raise ValueError(f'{week!r} is not a week (YYYY-Www)')
    rows = _rows(rows)
    taken = {_windows_key(row['path']) for row in rows}
    plan = []
    for row in sorted(rows, key=lambda r: r['path']):
        if row['status'] not in ARCHIVE_STATUSES or row['path'].startswith(ARCHIVE):
            continue
        target = archived_path(row['path'], week)
        if _windows_key(target) in taken:
            raise ValueError(f'{KEEP_RULE}: {target} is already indexed, so {row["path"]} cannot move there')
        errors = name_errors(target)
        if errors:
            raise ValueError('; '.join(errors))
        taken.add(_windows_key(target))
        plan.append({'move': row['path'], 'to': target})
    return plan


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(BLOCK), b''):
            digest.update(block)
    return digest.hexdigest()


def _plain(name, what):
    """A manifest's file name, refused unless it is one plain file name."""
    if not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\\' in name \
            or any(ord(c) < 32 for c in name) or Path(name).name != name:
        raise ValueError(f'{what} {name!r} is not a plain file name')
    return name


def _members(files):
    """Sorted (archive name, source path) pairs; a list of paths keeps each file's own name."""
    pairs = files.items() if isinstance(files, dict) else [(Path(f).name, f) for f in files]
    members = {}
    for arcname, source in pairs:
        parts, error = _parts(arcname)
        if error:
            raise ValueError(f'archive member {arcname!r}: {error}')
        if not Path(source).is_file():
            raise ValueError(f'{source} is not a file, so it cannot be bundled')
        if arcname in members:
            raise ValueError(f'two files would share the name {arcname} in the archive')
        members[arcname] = Path(source)
    if not members:
        raise ValueError('a bundle needs at least one file')
    return sorted(members.items())


def bundle(files, out_dir, part_bytes=PART_BYTES, *, created_on, name='fulltime-growth-backup', role='backup'):
    """Write a ZIP of files to out_dir as numbered parts under the Drive upload cap, plus its manifest.

    files is a list of paths or a dict of {name in the archive: path}. The parts
    are <name>-<created_on>.zip.partNN and the manifest <name>-<created_on>.json,
    in the shape of the 27 October handoff index (schema_version 1). The whole
    ZIP is built in a temporary folder and only its parts are kept. Refuses to
    overwrite any file already in out_dir."""
    day = _date(created_on)
    if not day:
        raise ValueError(f'created_on {created_on!r} must be a date (YYYY-MM-DD)')
    if not isinstance(name, str) or not STEM.match(name) or not isinstance(role, str) or not role:
        raise ValueError('a bundle name is lowercase ASCII with hyphens or underscores, and its role is text')
    if type(part_bytes) is not int or not 0 < part_bytes <= UPLOAD_CAP:
        raise ValueError(f'part_bytes must be a whole number from 1 to {UPLOAD_CAP}, the Drive upload cap')
    members = _members(files)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f'{name}-{created_on}'
    zip_name, manifest_path = stem + '.zip', out_dir / (stem + '.json')
    clashes = [p.name for p in (out_dir / zip_name, manifest_path) if p.exists()]
    clashes += sorted(p.name for p in out_dir.glob(zip_name + '.part*'))
    if clashes:
        raise ValueError(f'Refusing to overwrite {", ".join(clashes)} in {out_dir}')
    stamp = (day.year, day.month, day.day, 0, 0, 0)
    parts, whole, total = [], hashlib.sha256(), 0
    with tempfile.TemporaryDirectory(prefix='fulltime-bundle-') as work:
        archive = Path(work) / zip_name
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as packed:
            for arcname, source in members:
                info = zipfile.ZipInfo(arcname, date_time=stamp)
                info.compress_type, info.create_system, info.external_attr = zipfile.ZIP_DEFLATED, 3, 0o644 << 16
                with source.open('rb') as reader, \
                        packed.open(info, 'w', force_zip64=source.stat().st_size >= ZIP64) as writer:
                    for block in iter(lambda: reader.read(BLOCK), b''):
                        writer.write(block)
        size = archive.stat().st_size
        with archive.open('rb') as reader:
            while total < size:
                part_name = f'{zip_name}.part{len(parts) + 1:02d}'
                digest, md5, written = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
                try:
                    with (out_dir / part_name).open('xb') as writer:
                        while written < part_bytes:
                            block = reader.read(min(BLOCK, part_bytes - written))
                            if not block:
                                break
                            writer.write(block)
                            for h in (digest, md5, whole):
                                h.update(block)
                            written += len(block)
                except FileExistsError:
                    raise ValueError(f'Refusing to overwrite {part_name} in {out_dir}') from None
                total += written
                parts.append({'file_name': part_name, 'part_number': len(parts) + 1, 'bytes': written,
                              'sha256': digest.hexdigest(), 'md5': md5.hexdigest(), 'drive_file_id': None})
    manifest = {'schema_version': 1, 'created_on': created_on, 'upload_form': 'numbered_parts_under_100mb',
                'archives': [{'role': role, 'file_name': zip_name, 'bytes': total, 'sha256': whole.hexdigest(),
                              'file_count': len(members), 'drive_file_id': None, 'parts': parts}]}
    try:
        with manifest_path.open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(manifest, handle, indent=2)
            handle.write('\n')
    except FileExistsError:
        raise ValueError(f'Refusing to overwrite {manifest_path}') from None
    return manifest


def _archive_parts(archive):
    """An archive's parts in order, refusing missing, repeated or malformed part entries."""
    name = _plain(archive.get('file_name') if isinstance(archive, dict) else None, 'archive')
    items = archive.get('parts')
    if not isinstance(items, list) or not items:
        raise ValueError(f'{name} lists no parts')
    for item in items:
        if not isinstance(item, dict) or type(item.get('part_number')) is not int \
                or type(item.get('bytes')) is not int or not isinstance(item.get('sha256'), str):
            raise ValueError(f'{name} has a part without a part_number, bytes and sha256')
        _plain(item.get('file_name'), 'part')
    if type(archive.get('bytes')) is not int or not isinstance(archive.get('sha256'), str):
        raise ValueError(f'{name} needs its whole bytes and sha256')
    parts = sorted(items, key=lambda item: item['part_number'])
    if [item['part_number'] for item in parts] != list(range(1, len(parts) + 1)):
        raise ValueError(f'Missing or repeated part number for {name}')
    return name, parts


def assemble(manifest, parts_dir, out_dir):
    """Rebuild each archive a bundle or handoff manifest lists, and verify it. Nothing is extracted.

    The checks are the 27 October assembler's: schema_version 1, contiguous part
    numbers, every part's size and SHA-256, no overwrite, the whole archive's size
    and SHA-256, and a full ZIP test. An archive this call wrote that then fails a
    check is removed, so nothing unverified is left looking finished."""
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('Unknown handoff schema: schema_version must be 1')
    archives = manifest.get('archives')
    if not isinstance(archives, list) or not archives:
        raise ValueError('The manifest lists no archives')
    parts_dir, out_dir = Path(parts_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for archive in archives:
        name, parts = _archive_parts(archive)
        target = out_dir / name
        if target.exists():
            raise ValueError(f'Refusing to overwrite {target}')
        for item in parts:
            source = parts_dir / item['file_name']
            if not source.is_file() or source.stat().st_size != item['bytes']:
                raise ValueError(f'Missing or wrong-size part {item["file_name"]}')
            if _sha256(source) != item['sha256']:
                raise ValueError(f'Part hash mismatch {item["file_name"]}')
        try:
            destination = target.open('xb')
        except FileExistsError:
            raise ValueError(f'Refusing to overwrite {target}') from None
        try:
            with destination:
                for item in parts:
                    with (parts_dir / item['file_name']).open('rb') as source:
                        for block in iter(lambda: source.read(BLOCK), b''):
                            destination.write(block)
            if target.stat().st_size != archive['bytes'] or _sha256(target) != archive['sha256']:
                raise ValueError(f'Reassembled archive hash mismatch {target}')
            try:
                with zipfile.ZipFile(target) as packed:
                    damaged = packed.testzip()
            except zipfile.BadZipFile as error:
                raise ValueError(f'{target} is not a readable ZIP: {error}') from None
            except Exception as error:     # an unsupported method, encryption or a broken stream
                raise ValueError(f'{target} failed the ZIP test: {type(error).__name__}: {error}') from None
            if damaged:
                raise ValueError(f'Corrupt ZIP member {damaged}')
        except BaseException:
            target.unlink()                # this call wrote it, so nothing unverified is left behind
            raise
        results.append({'file_name': target.name, 'sha256': archive['sha256'], 'bytes': target.stat().st_size,
                        'zip_verified': True})
    return results
