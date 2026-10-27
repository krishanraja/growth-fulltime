"""The invariant registry: every past failure, correction and rule, mapped to the code
that enforces it and the test that proves it (docs/ENGINE-V2.md, section 4).
docs/FAILURE-REGISTER.md is the readable copy.

invariants/registry.json holds one entry per rule: R01 to R50, the 22 rules that
existed only as documents, GET-GOING steps 0 to 5, the library rules and the new hard
invariants. Each entry says honestly where it stands:

- enforced: code enforces it and the named test proves it;
- open: it can be checked in code, but not all of it is yet; remains says what is missing;
- product_item: it belongs to full-time or Control Center, so here it is a brief;
- owner_item: Krish decides it or does it;
- human_judgment: a person's call, such as the 11/10 verdict, humour or natural faces.

load() checks the file. check() loads every named test with
unittest.defaultTestLoader.loadTestsFromName and, when asked, runs them: it is ok only
when every enforced entry names a test that exists and passes, and every enforced_by
path resolves. now_state_errors() checks the North Star state line in NOW.md (R31),
which had no other home. Nothing here posts, sends, spends or reads the network.
"""
import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import re
import unittest

from .clock import LONDON
from .crew import resolve

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'invariants' / 'registry.json'
TOP = ('_about', 'schema_version', 'entries')
ENTRY = ('id', 'rule', 'origin', 'status', 'enforced_by', 'test', 'remains')
STATUSES = ('enforced', 'open', 'product_item', 'owner_item', 'human_judgment')
ENTRY_ID = re.compile(r'^(?:R[0-9]{2}|DOC[0-9]{2}|GG[0-9](?:\.5)?|LIB[0-9]|INV-[A-Z0-9]+(?:-[A-Z0-9]+)*)$')
TEST_ID = re.compile(r'^tests\.test_[a-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]*\.test_[A-Za-z0-9_]+$')
DOTTED = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$')
MAX_TEXT = 600
_running = False


# ---------------------------------------------------------------------------
# The registry file.
# ---------------------------------------------------------------------------
def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _entry_errors(entry, number):
    if not isinstance(entry, dict) or set(entry) != set(ENTRY):
        return [f'entry {number} must carry exactly ' + ', '.join(ENTRY)]
    label = entry['id'] if isinstance(entry['id'], str) else f'entry {number}'
    out = []
    if not isinstance(entry['id'], str) or not ENTRY_ID.match(entry['id']):
        out.append(f'{label}: the id must look like R01, DOC01, GG0.5, LIB1 or INV-NAME')
    for key in ('rule', 'origin'):
        if not _text(entry[key]) or len(entry[key]) > MAX_TEXT:
            out.append(f'{label}: {key} must be non-empty text of at most {MAX_TEXT} characters')
    if entry['status'] not in STATUSES:
        out.append(f'{label}: status must be one of ' + ', '.join(STATUSES))
    if entry['enforced_by'] is not None and not (isinstance(entry['enforced_by'], str)
                                                 and DOTTED.match(entry['enforced_by'])):
        out.append(f'{label}: enforced_by must be a dotted path such as engine.pack.check, or null')
    if entry['test'] is not None and not (isinstance(entry['test'], str) and TEST_ID.match(entry['test'])):
        out.append(f'{label}: test must be tests.test_x.ClassName.test_name, or null')
    if entry['remains'] is not None and (not _text(entry['remains']) or len(entry['remains']) > MAX_TEXT):
        out.append(f'{label}: remains must be non-empty text of at most {MAX_TEXT} characters, or null')
    if entry['status'] == 'enforced' and entry['test'] is None:
        out.append(f'{label}: an enforced entry must name the test that proves it')
    if entry['status'] != 'enforced' and entry['remains'] is None:
        out.append(f'{label}: a {entry["status"]} entry must say what remains, and where')
    for key in ('rule', 'origin', 'remains'):
        if isinstance(entry[key], str) and '\u2014' in entry[key]:
            out.append(f'{label}: {key} has an em dash')
    return out


def load(path=None):
    """The registry's entries, in file order. ValueError names every problem in it."""
    path = Path(path) if path else REGISTRY
    try:
        data = json.loads(path.read_text(encoding='utf-8'),
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path}: the invariant registry is unreadable ({error})') from None
    if not isinstance(data, dict) or set(data) != set(TOP):
        raise ValueError(f'{path}: the registry must carry exactly ' + ', '.join(TOP))
    if data['schema_version'] != 1:
        raise ValueError(f'{path}: schema_version must be 1')
    entries = data['entries']
    if not isinstance(entries, list) or not entries:
        raise ValueError(f'{path}: entries must be a non-empty list')
    out, seen = [], set()
    for number, entry in enumerate(entries, 1):
        out += _entry_errors(entry, number)
        if isinstance(entry, dict) and isinstance(entry.get('id'), str):
            if entry['id'] in seen:
                out.append(f'{entry["id"]}: the id is listed twice')
            seen.add(entry['id'])
    if out:
        raise ValueError(f'{path}: ' + '; '.join(out))
    return entries


# ---------------------------------------------------------------------------
# Loading and running the named tests.
# ---------------------------------------------------------------------------
def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def _load_test(test_id):
    """The one TestCase a test id names, or None when it does not exist."""
    loader = unittest.defaultTestLoader
    before = len(loader.errors)
    try:
        suite = loader.loadTestsFromName(test_id)
    except Exception:            # a test module that fails to import is a missing test
        return None
    finally:
        failed = len(loader.errors) > before
        del loader.errors[before:]   # never leave this lookup's errors for an outer test run
    cases = list(_flatten(suite)) if isinstance(suite, unittest.TestSuite) else []
    if failed or [case.id() for case in cases] != [test_id]:
        return None
    return cases[0]


class _Recorder(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.passed, self.skips = set(), set()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.add(test.id())

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skips.add(test.id())


def _run(cases):
    """(passed, skipped) test ids. A test that errors, fails, or never runs because its
    class could not be set up is in neither."""
    suite = unittest.TestSuite(cases[key] for key in sorted(cases))
    result = _Recorder()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        suite.run(result)
    return result.passed, result.skips


def check(run_tests=True, path=None):
    """The registry's standing: {'entries', 'enforced', 'by_status', 'missing_tests',
    'unresolved', 'failing', 'skipped', 'ran', 'ok'}. ok is true only when every named test
    exists, every enforced_by path resolves and, when run_tests is true, every named test
    passed. A skipped test did not pass."""
    global _running
    if _running:
        raise ValueError('invariants.check is already running its tests; it never runs itself')
    entries = load(path)
    by_status = {status: sum(1 for e in entries if e['status'] == status) for status in STATUSES}
    missing, unresolved, cases = [], [], {}
    for entry in entries:
        if entry['enforced_by'] is not None:
            try:
                if not callable(resolve(entry['enforced_by'])):
                    unresolved.append(f'{entry["id"]}: {entry["enforced_by"]} is not callable')
            except ValueError as error:
                unresolved.append(f'{entry["id"]}: {error}')
        test_id = entry['test']
        if test_id is None:
            continue
        if test_id not in cases:
            case = _load_test(test_id)
            if case is None:
                missing.append(f'{entry["id"]}: {test_id} does not exist')
                continue
            cases[test_id] = case
    failing, skipped, ran = [], [], 0
    if run_tests and cases:
        _running = True
        try:
            passed, skips = _run(cases)
        finally:
            _running = False
        ran = len(cases)
        for entry in entries:
            test_id = entry['test']
            if test_id in cases and test_id in skips:
                skipped.append(f'{entry["id"]}: {test_id}')
            elif test_id in cases and test_id not in passed:
                failing.append(f'{entry["id"]}: {test_id}')
    ok = not missing and not unresolved and not failing and not skipped
    return {'entries': len(entries), 'enforced': by_status['enforced'], 'by_status': by_status,
            'missing_tests': missing, 'unresolved': unresolved, 'failing': failing, 'skipped': skipped,
            'ran': ran, 'ok': ok}


# ---------------------------------------------------------------------------
# R31: the North Star state line in NOW.md.
# ---------------------------------------------------------------------------
STATE = re.compile(r'<!-- north-star-state (\{.*?\}) -->(.*)$', re.M)
STATE_FIELDS = ('week_of', 'week_target', 'current', 'current_as_of', 'current_source', 'urgency',
                'urgency_reason')
LADDER = re.compile(r'^\s*-\s*\[([0-9]{4}-[0-9]{2}-[0-9]{2}),\s*([0-9]+)\]\s*$', re.M)
UNMEASURED_URGENCY = 4          # CLAUDE.md: "a number nobody measures is U4"
# The harness contract (ai-harness contract/north-star-metric.md): U1 at or above this
# week's target, U2 at 75% or more, U3 at 40% to 75%, U4 under 40%, unmeasured, or a
# reading more than 7 days old. U5 needs history this line does not carry.
BANDS = ((1.0, 1), (0.75, 2), (0.4, 3))
STALE_READING_DAYS = 7
MAX_READING_DAYS = 8


def _band(current, target):
    """The least urgency the contract allows for current against this week's target."""
    share = current / target
    return next((level for floor, level in BANDS if share >= floor), 4)


def _today(today):
    if today is None:
        return dt.datetime.now(LONDON).date()
    if isinstance(today, dt.datetime):
        if today.tzinfo is None:
            raise ValueError('today must be a date, or a date and time with its offset')
        return today.astimezone(LONDON).date()
    if isinstance(today, dt.date):
        return today
    raise ValueError('today must be a date, or a date and time with its offset')


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError
    return dt.date.fromisoformat(value)


def now_state_errors(now_text=None, north_star_text=None, today=None):
    """Every reason the north-star-state line in NOW.md is wrong, in plain words: its
    shape, that it is for this London week (today, London, by default) with a reading at
    most 8 days old, this week's target against the ladder in docs/NORTH_STAR.md, and the
    urgency (U1 to U5, never below the contract's band for current against the target,
    and at least U4 while unmeasured or read more than 7 days ago) and the visible line."""
    today = _today(today)
    now_text = (ROOT / 'NOW.md').read_text(encoding='utf-8') if now_text is None else now_text
    if north_star_text is None:
        north_star_text = (ROOT / 'docs' / 'NORTH_STAR.md').read_text(encoding='utf-8')
    found = STATE.findall(now_text)
    if len(found) != 1:
        return [f'NOW.md must carry exactly one north-star-state line; it carries {len(found)}']
    raw, visible = found[0]
    try:
        state = json.loads(raw)
    except ValueError:
        return ['the north-star-state block is not valid JSON']
    if not isinstance(state, dict) or set(state) != set(STATE_FIELDS):
        return ['the north-star-state block must carry exactly ' + ', '.join(STATE_FIELDS)]
    ladder = {day: int(target) for day, target in LADDER.findall(north_star_text)}
    out = []
    try:
        week = _day(state['week_of'])
    except ValueError:
        return ['week_of must be a date, YYYY-MM-DD']
    if week.weekday() != 0:
        out.append(f'week_of {week.isoformat()} is not a Monday')
    monday = today - dt.timedelta(days=today.weekday())
    if week != monday:
        out.append(f'the state line is for the week of {week.isoformat()}, not this week (the week of '
                   f'{monday.isoformat()}, London): update NOW.md')
    if week.isoformat() not in ladder:
        out.append(f'week_of {week.isoformat()} is not a week on the ladder in docs/NORTH_STAR.md')
    elif state['week_target'] != ladder[week.isoformat()]:
        out.append(f'week_target is {state["week_target"]!r}, but the ladder says {ladder[week.isoformat()]} '
                   f'for the week of {week.isoformat()}')
    current = state['current']
    if current is not None and (type(current) is not int or current < 0):
        out.append('current must be a whole number of 0 or more, or null when unmeasured')
    age = None
    try:
        as_of = _day(state['current_as_of'])
        if not week <= as_of < week + dt.timedelta(days=7):
            out.append(f'current_as_of {as_of.isoformat()} is outside the week of {week.isoformat()}')
        age = (today - as_of).days
        if age < 0:
            out.append(f'current_as_of {as_of.isoformat()} is after today ({today.isoformat()}, London)')
        elif age > MAX_READING_DAYS:
            out.append(f'current_as_of {as_of.isoformat()} is {age} days old: the line must be read within '
                       f'{MAX_READING_DAYS} days')
    except ValueError:
        out.append('current_as_of must be a date, YYYY-MM-DD')
    for key in ('current_source', 'urgency_reason'):
        if not _text(state[key]):
            out.append(f'{key} must say where the number came from, or why it is missing')
    urgency = state['urgency']
    if type(urgency) is not int or not 1 <= urgency <= 5:
        out.append('urgency must be a whole number from 1 to 5')
    else:
        if current is None and urgency < UNMEASURED_URGENCY:
            out.append(f'an unmeasured number is at least U{UNMEASURED_URGENCY}, not U{urgency}')
        if age is not None and age > STALE_READING_DAYS and urgency < UNMEASURED_URGENCY:
            out.append(f'a reading more than {STALE_READING_DAYS} days old is at least U{UNMEASURED_URGENCY}, '
                       f'not U{urgency}')
        target = state['week_target']
        if type(current) is int and current >= 0 and type(target) is int and target > 0:
            band = _band(current, target)
            if urgency < band:
                out.append(f'the contract puts {current} of {target} at U{band} or higher, not U{urgency}')
        if f'U{urgency}' not in visible:
            out.append(f'the visible North Star line does not say U{urgency}')
    return out
