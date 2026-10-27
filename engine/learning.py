"""The What-Works Analyst's learning register (docs/ENGINE-V2.md, crew row 9, and the
learning register paragraph).

Each learning is a claim that arm a beats arm b, the signal that measures it, the
evidence that would flip it, and what it is applied to. observe() adds a revision
whose status is computed from the evidence, never written by hand; earlier
revisions are kept. 'confirmed' needs pre-registration, no overlapping test, at
least two matchweeks, at least 20 events per arm and z = (a - b) / sqrt(a + b) of 2
or more for a; 'refuted' is the same bar with z of 2 or more for b; 'no_difference'
is |z| under 2 once the planned matchweeks have passed with 20 events per arm;
anything else is 'directional'. Before the first live post the register holds
verdict analysis only.

The store is <local>/engine/learning.json, written with records.atomic_json under a
lock, with an immutable backup of the previous state per change, like
records.History. Nothing here posts, sends, schedules or spends.
"""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import re
import time

from .attribution import poisson_interval, z_score
from .policy import sensitive_errors
from .records import atomic_json, fingerprint, now

STATUSES = ('directional', 'confirmed', 'refuted', 'no_difference')
MIN_EVENTS = 20
MIN_MATCHWEEKS = 2
Z_BAR = 2
VERDICTS = ('post_it', 'edit', 'reject')
ENTRY = ('id', 'claim', 'signal', 'flip_rule', 'applied_to', 'created_at', 'revisions')
EVIDENCE = ('a', 'b', 'matchweeks', 'preregistered', 'overlapping', 'planned_matchweeks')
REVISION = ('revision', 'observed_at', 'n', 'z', 'interval_a', 'interval_b', 'status', 'why') + EVIDENCE
IDENTIFIER = re.compile(r'^learning-([0-9]{3,6})$')
CSV_FIELDS = ('id', 'status', 'claim', 'signal', 'revision', 'a', 'b', 'n', 'z', 'interval_a', 'interval_b',
              'matchweeks', 'planned_matchweeks', 'preregistered', 'overlapping', 'flip_rule', 'applied_to',
              'created_at', 'observed_at')
# Words too common to be a reason on their own.
STOP = {'the', 'and', 'but', 'for', 'with', 'too', 'not', 'are', 'was', 'its', "it's", 'this', 'that', 'than',
        'then', 'there', 'their', 'they', 'them', 'you', 'your', 'our', 'his', 'her', 'has', 'have', 'had',
        'does', 'did', 'can', 'could', 'should', 'would', 'will', 'more', 'less', 'much', 'some', 'any', 'all',
        'one', 'out', 'into', 'about', 'what', 'which', 'who', 'how', 'why', 'when', 'also', 'just', 'very',
        'from', 'been', 'being', 'were', 'only', 'here', 'like', 'make', 'needs', 'need'}


def _root(local):
    return Path(local) / 'engine'


def empty():
    return {'schema_version': 1, 'product': 'fulltime', 'learnings': {}}


def _text(value, what):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError(f'{what} must be non-empty text of up to 1,000 characters')
    return value.strip()


def _whole(value, what, least=0):
    if type(value) is not int or value < least:
        raise ValueError(f'{what} must be a whole number of at least {least}')
    return value


def judge(a, b, matchweeks, preregistered, overlapping, planned_matchweeks):
    """(status, why) for this evidence, by the rule in the module docstring."""
    z = z_score(a, b)
    powered = a >= MIN_EVENTS and b >= MIN_EVENTS
    clean = preregistered and not overlapping and matchweeks >= MIN_MATCHWEEKS and powered
    if clean and z >= Z_BAR:
        return 'confirmed', f'z {z:.2f} for a, pre-registered, no overlap, {matchweeks} matchweeks, {a} against {b}'
    if clean and z <= -Z_BAR:
        return 'refuted', f'z {z:.2f} for b, pre-registered, no overlap, {matchweeks} matchweeks, {a} against {b}'
    if matchweeks >= planned_matchweeks and abs(z) < Z_BAR and powered:
        return 'no_difference', (f'|z| {abs(z):.2f} under {Z_BAR} after the planned {planned_matchweeks} '
                                 'matchweeks: keep the cheaper arm')
    short = []
    if not preregistered:
        short.append('not pre-registered')
    if overlapping:
        short.append('overlaps another test')
    if matchweeks < MIN_MATCHWEEKS:
        short.append(f'{matchweeks} of {MIN_MATCHWEEKS} matchweeks')
    for arm, count in (('a', a), ('b', b)):
        if count < MIN_EVENTS:
            short.append(f'arm {arm} has {count} of {MIN_EVENTS} events')
    if abs(z) < Z_BAR:
        short.append(f'|z| {abs(z):.2f} under {Z_BAR}' + (', planned matchweeks still running'
                                                         if matchweeks < planned_matchweeks else ''))
    return 'directional', 'directional only: ' + '; '.join(short or ['the evidence bar is not met'])


def _check_revision(revision, number, where):
    if not isinstance(revision, dict) or set(revision) != set(REVISION) or revision['revision'] != number:
        raise ValueError(f'{where}: revision {number} is not in the register shape')
    evidence = [revision[k] for k in EVIDENCE]
    if judge(*evidence)[0] != revision['status']:
        raise ValueError(f'{where}: revision {number} has a status its evidence does not give; '
                         'statuses are computed, never written')


def validate(store):
    if not isinstance(store, dict) or set(store) != {'schema_version', 'product', 'learnings'} \
            or store['schema_version'] != 1 or store['product'] != 'fulltime' \
            or not isinstance(store['learnings'], dict):
        raise ValueError('invalid learning register schema or product; the register was not replaced')
    for key, entry in store['learnings'].items():
        if not isinstance(entry, dict) or set(entry) != set(ENTRY) or entry['id'] != key \
                or not IDENTIFIER.match(key) or not isinstance(entry['revisions'], list) \
                or not isinstance(entry['applied_to'], list):
            raise ValueError(f'learning {key!r} is not in the register shape')
        for number, revision in enumerate(entry['revisions'], start=1):
            _check_revision(revision, number, key)
    if sensitive_errors(store):
        raise ValueError('the learning register contains private contacts or credential-like data')
    return store


def read(local):
    """The register as stored, or an empty one."""
    path = _root(local) / 'learning.json'
    if not path.exists():
        return empty()
    try:
        return validate(json.loads(path.read_text(encoding='utf-8')))
    except (ValueError, OSError) as error:
        raise ValueError('the learning register is unreadable; restore a validated backup before continuing') from error


@contextlib.contextmanager
def _transaction(local):
    root = _root(local)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.learning-lock'
    deadline = time.monotonic() + 10
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('the learning register is locked; verify no writer is running before '
                                 'removing .learning-lock')
            time.sleep(0.02)
    try:
        path = root / 'learning.json'
        store = read(local)
        before = copy.deepcopy(store)
        yield store
        validate(store)
        if store != before or not path.exists():
            if path.exists():
                backup = root / 'learning-backups' / (fingerprint(before) + '.json')
                if not backup.exists():
                    atomic_json(backup, before)
            atomic_json(path, store)
    finally:
        lock.rmdir()


def add(local, claim, signal, flip_rule, applied_to):
    """A new learning, status directional until evidence arrives; returns its ID.
    The same definition added again returns the existing ID."""
    definition = {'claim': _text(claim, 'the claim'), 'signal': _text(signal, 'the signal'),
                  'flip_rule': _text(flip_rule, 'the flip rule')}
    if not isinstance(applied_to, list) or any(not isinstance(x, str) or not x.strip() for x in applied_to):
        raise ValueError('applied_to must be a list of non-empty references, such as a format or lock version')
    definition['applied_to'] = [x.strip() for x in applied_to]
    if len(set(definition['applied_to'])) != len(definition['applied_to']):
        raise ValueError('applied_to names one reference twice')
    if sensitive_errors(definition):
        raise ValueError('a learning holds aggregates and references only, never contacts or credentials')
    with _transaction(local) as store:
        for key, entry in store['learnings'].items():
            if {k: entry[k] for k in definition} == definition:
                return key
        numbers = [int(IDENTIFIER.match(k).group(1)) for k in store['learnings']]
        identifier = f'learning-{max(numbers, default=0) + 1:03d}'
        store['learnings'][identifier] = {'id': identifier, **definition, 'created_at': now(), 'revisions': []}
        return identifier


def observe(local, identifier, a, b, matchweeks, preregistered, overlapping, planned_matchweeks):
    """A new revision for this learning, with its status computed. a is the arm the
    claim says wins and b its control. The same evidence twice returns the latest
    revision unchanged."""
    evidence = {'a': _whole(a, 'arm a'), 'b': _whole(b, 'arm b'),
                'matchweeks': _whole(matchweeks, 'matchweeks'),
                'planned_matchweeks': _whole(planned_matchweeks, 'planned_matchweeks', MIN_MATCHWEEKS)}
    for key, value in (('preregistered', preregistered), ('overlapping', overlapping)):
        if type(value) is not bool:
            raise ValueError(f'{key} must be true or false')
        evidence[key] = value
    computed, why = judge(*[evidence[k] for k in EVIDENCE])
    with _transaction(local) as store:
        entry = store['learnings'].get(identifier)
        if entry is None:
            raise ValueError(f'unknown learning {identifier!r}; add it first')
        if entry['revisions'] and {k: entry['revisions'][-1][k] for k in EVIDENCE} == evidence:
            return copy.deepcopy(entry['revisions'][-1])
        revision = {'revision': len(entry['revisions']) + 1, 'observed_at': now(), **evidence,
                    'n': evidence['a'] + evidence['b'], 'z': round(z_score(evidence['a'], evidence['b']), 2),
                    'interval_a': list(poisson_interval(evidence['a'])),
                    'interval_b': list(poisson_interval(evidence['b'])), 'status': computed, 'why': why}
        entry['revisions'].append(revision)
        return copy.deepcopy(revision)


# ---------------------------------------------------------------------------
# Reading the register.
# ---------------------------------------------------------------------------
def _entries(register):
    if isinstance(register, dict) and isinstance(register.get('learnings'), dict):
        return [register['learnings'][k] for k in sorted(register['learnings'])]
    if isinstance(register, list):
        return list(register)
    raise ValueError('a register is the store learning.read returns, or a list of its entries')


def _latest(entry):
    return entry['revisions'][-1] if entry.get('revisions') else None


def status(entry):
    """The entry's current status: its newest revision's, or directional before any evidence."""
    latest = _latest(entry)
    return latest['status'] if latest else 'directional'


def kill_double_down(register):
    """{'kill': [...], 'double_down': [...]}: refuted learnings to stop relying on and
    confirmed ones to do more of. Each item carries a line for reporting.kill_proposal."""
    out = {'kill': [], 'double_down': []}
    for entry in _entries(register):
        latest = _latest(entry)
        if not latest or latest['status'] not in ('confirmed', 'refuted'):
            continue
        confirmed = latest['status'] == 'confirmed'
        evidence = (f'z {latest["z"]}, {latest["a"]} against {latest["b"]} over {latest["matchweeks"]} matchweeks')
        line = ((f'Double down on {entry["id"]}: "{entry["claim"]}" is confirmed ({evidence}).' if confirmed else
                 f'Stop relying on {entry["id"]}: "{entry["claim"]}" was refuted ({evidence}).')
                + f' What flips it: {entry["flip_rule"]}')
        out['double_down' if confirmed else 'kill'].append(
            {'id': entry['id'], 'claim': entry['claim'], 'status': latest['status'], 'z': latest['z'],
             'a': latest['a'], 'b': latest['b'], 'applied_to': list(entry['applied_to']),
             'flip_rule': entry['flip_rule'], 'line': line[:1000]})
    return out


def _cell(value):
    """Text that a spreadsheet could read as a formula is kept as text."""
    return "'" + value if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r') else value


def export_csv(register):
    """register.csv text for Growth Build/04_Learning: one row per learning at its
    newest revision, LF line endings, rows by ID."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(CSV_FIELDS)
    for entry in sorted(_entries(register), key=lambda e: e['id']):
        latest = _latest(entry) or {}
        span = lambda key: '' if not latest else f'{latest[key][0]} to {latest[key][1]}'
        flag = lambda key: '' if not latest else ('yes' if latest[key] else 'no')
        writer.writerow([
            entry['id'], status(entry), _cell(entry['claim']), _cell(entry['signal']),
            latest.get('revision', 0), latest.get('a', ''), latest.get('b', ''), latest.get('n', ''),
            latest.get('z', ''), span('interval_a'), span('interval_b'), latest.get('matchweeks', ''),
            latest.get('planned_matchweeks', ''), flag('preregistered'), flag('overlapping'),
            _cell(entry['flip_rule']), _cell('; '.join(entry['applied_to'])), entry['created_at'],
            latest.get('observed_at', '')])
    return out.getvalue()


def blocked_locks(register, locks):
    """The lock versions that cite a refuted learning, in the order given. locks is a
    list of {'lock_version', 'learnings': [ids]} or a mapping of lock_version to ids.
    A blocked lock needs a new lock version that drops the refuted learning."""
    refuted = {e['id'] for e in _entries(register) if status(e) == 'refuted'}
    if isinstance(locks, dict):
        pairs = list(locks.items())
    elif isinstance(locks, list) and all(isinstance(x, dict) for x in locks):
        pairs = [(x.get('lock_version'), x.get('learnings')) for x in locks]
    else:
        raise ValueError('locks must be a list of {lock_version, learnings} or a mapping of version to IDs')
    out = []
    for version, cited in pairs:
        if not isinstance(version, str) or not version or not isinstance(cited, list):
            raise ValueError('each lock needs a lock_version and a list of the learnings it cites')
        if refuted & set(map(str, cited)) and version not in out:
            out.append(version)
    return out


# ---------------------------------------------------------------------------
# Verdict analysis: which of Krish's edits and rejects repeat, and why.
# ---------------------------------------------------------------------------
def _words(note):
    if not isinstance(note, str):
        return set()
    words = {w.strip("'-") for w in re.findall(r"[a-z][a-z'-]*", note.lower())}
    return {w for w in words if len(w) >= 3 and w not in STOP}


def verdict_analysis(verdicts):
    """Counts of edit and reject verdicts by format, by AI Pundit and by the words in
    their notes, flagging every reason seen at least twice. Each verdict is a dict with
    verdict (post_it, edit or reject), format_id, pundit and note; post it is not counted."""
    out = {'edit': 0, 'reject': 0, 'by_format': {}, 'by_pundit': {}, 'by_word': {}, 'repeated': []}
    for number, verdict in enumerate(verdicts or [], start=1):
        if not isinstance(verdict, dict) or verdict.get('verdict') not in VERDICTS:
            raise ValueError(f'verdict {number} must be post_it, edit or reject')
        kind = verdict['verdict']
        if kind == 'post_it':
            continue
        out[kind] += 1
        for field, bucket in (('format_id', 'by_format'), ('pundit', 'by_pundit')):
            name = verdict.get(field) if isinstance(verdict.get(field), str) and verdict.get(field) else 'unknown'
            out[bucket].setdefault(name, {'edit': 0, 'reject': 0})[kind] += 1
        for word in sorted(_words(verdict.get('note'))):
            out['by_word'].setdefault(word, {'edit': 0, 'reject': 0})[kind] += 1
    totals = {word: c['edit'] + c['reject'] for word, c in out['by_word'].items()}
    out['repeated'] = [{'reason': word, 'count': count, **out['by_word'][word]}
                       for word, count in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))
                       if count >= 2]
    return out
