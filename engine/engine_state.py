"""Krish's instruction and the engine's state, protocol 1.20.0
(docs/control-center/ENGINE-PROTOCOL.md, "Krish's instruction and the engine's state (1.20.0)").

Ruling (Krish, 2026-11-11): every growth engine's priorities, obsessions, next
steps and outstanding items feed live across Control Centre, and Krish
instructs each engine with his next best action, which starts it.

Control Center's directive may carry `krish_instruction`: his own next best
action for this engine, given through its one door. It comes first in a run's
work, inside the walls. It is never an approval, so anything at a wall still
goes to him as a proposal. This repository and its Actions logs are public:
his words are never printed, logged, committed or reported. Only the id and a
SHA-256 digest appear; the words are kept only in the ignored file
local/control-center/instruction.json, which the morning job reads.

At 1.20.0, and only when the directive says `features.engine_state` is true,
a report carries `priorities`, `obsessions`, `next_steps` and
`instruction_acks`. Each is filled from this repository's own files (the North
Star, AGENTS.md, docs/GET-GOING.md, NOW.md) and the run's own gates, never
invented: a field with no source is left out.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

from .records import atomic_json

ROOT = Path(__file__).resolve().parent.parent
VERSION = '1.20.0'
ID = re.compile(r'^ki_[0-9a-f]{24}$')
ACK_STATES = ('received', 'started', 'done', 'blocked')
HAND_STATES = ('started', 'done', 'blocked')
STATE_LINE_MAX = 200
ACK_LINE_MAX = 280
WORDS_MAX = 2000
PRIORITIES_MAX, OBSESSIONS_MAX, NEXT_STEPS_MAX, ACKS_MAX = 5, 3, 5, 5
NS_KEY = 'attributed_new_completers'
KEEP_IDS = 20
# Control Center's own line guard (src/lib/growthEngines.ts, lineCarriesContact): an address, or a run of
# ten digits or more, refuses the whole report.
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[a-z]{2,}', re.I)
PHONE_RUN = re.compile(r'\+?\d[\d\s().-]{8,}\d')
CONTROL = re.compile(r'[\x00-\x1f\x7f]')

RECEIVED_RUNNER = ('Received. This clean runner has no model and no private workspace, so the morning job in '
                   'the persistent workspace acts on it first, inside the walls.')
RECEIVED_WORKSPACE = ('Received in the persistent workspace. The morning job acts on it first, inside the walls; '
                      'anything at a wall goes to Krish as a proposal.')
RECEIVED_HELD = 'Received while the engine is held.'
HELD_LINES = {'activation.json': 'Engine held: nothing runs on this until Krish releases the hold in activation.json.',
              'control_center': 'Engine held: nothing runs on this until Krish releases the hold in Control Center.'}


# ---------------------------------------------------------------------------
# Reading the directive.
# ---------------------------------------------------------------------------
def _body(directive):
    body = directive.get('directive') if isinstance(directive, dict) else None
    return body if isinstance(body, dict) else {}


def features_on(directive):
    """True only when the served directive says features.engine_state is true (1.20.0)."""
    features = _body(directive).get('features')
    return isinstance(features, dict) and features.get('engine_state') is True


def digest(words):
    return hashlib.sha256(words.encode('utf-8')).hexdigest()


def instruction(directive):
    """The directive's krish_instruction, checked, or None when it is null, absent or malformed."""
    value = _body(directive).get('krish_instruction')
    if not isinstance(value, dict):
        return None
    iid, words = value.get('id'), value.get('words')
    if not (isinstance(iid, str) and ID.match(iid) and isinstance(words, str) and 0 < len(words) <= WORDS_MAX):
        return None
    supersedes = value.get('supersedes')
    given = value.get('given_at')
    return {'id': iid, 'words': words, 'given_at': given if isinstance(given, str) else None,
            'supersedes': supersedes if isinstance(supersedes, str) and ID.match(supersedes) else None,
            'words_sha256': digest(words)}


def shown(instr):
    """What may be printed or logged about an instruction: its id and digest, never its words."""
    return None if not instr else {'id': instr['id'], 'words_sha256': instr['words_sha256']}


def activity_line(instr, held):
    """The report's first activity line on a run that carries an instruction. The id only, never the words."""
    if held:
        return (f"Received Krish's instruction {instr['id']}. The engine is held, so nothing runs on it until "
                'Krish releases the hold.')
    return (f"Received Krish's instruction {instr['id']}. It comes first in this run's work, inside the walls: it "
            'approves no send, post or spend, so anything at a wall still goes to him as a proposal.')


# ---------------------------------------------------------------------------
# Lines: plain, one line, no address or phone number, never his words.
# ---------------------------------------------------------------------------
def contact_free(text):
    return not EMAIL.search(text) and not any(len(re.sub(r'\D', '', run)) >= 10 for run in PHONE_RUN.findall(text))


def line_ok(text, limit):
    return (isinstance(text, str) and 0 < len(text) <= limit and text == text.strip()
            and not CONTROL.search(text) and contact_free(text))


def plain(text):
    """Markdown as plain words on one line: links to their text, no code ticks or emphasis."""
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'(\*\*|__)(.+?)\1', r'\2', text)
    return re.sub(r'\s+', ' ', text).strip()


def sentences(text):
    return [s for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"])', plain(text)) if s]


def clause(text, limit=STATE_LINE_MAX):
    """A whole thought that fits: the text, else its first sentence, else that sentence up to its first
    colon or semicolon. Never cut mid-phrase; None when nothing whole fits or the line is not plain."""
    whole = plain(text)
    first = (sentences(whole) or [''])[0]
    head = re.split(r'[:;]\s', first, maxsplit=1)[0].rstrip(' ,')
    for candidate in (whole, first, head + ('' if head.endswith(('.', '!', '?')) else '.')):
        if line_ok(candidate, limit):
            return candidate
    return None


def _tokens(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def quotes(line, words):
    """True when a line repeats Krish's words: any five of them in a row, or all of a short instruction."""
    said, own = _tokens(words), _tokens(line)
    size = min(5, len(said))
    if size < 3:
        joined = ' '.join(said)
        return len(joined) >= 8 and joined in ' '.join(own)
    grams = {tuple(said[i:i + size]) for i in range(len(said) - size + 1)}
    return any(tuple(own[i:i + size]) in grams for i in range(len(own) - size + 1))


def ack_step(previous, state):
    """Control Center's own rule (ackStep): forward only, nothing after done; received only opens;
    started and blocked can follow each other; either can go to done."""
    if previous == 'done':
        return False
    if previous is None:
        return True
    if state == 'received':
        return False
    if state == 'done':
        return True
    if previous == 'received':
        return True
    return previous != state


def _iso(moment):
    return moment.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _parse(stamp):
    try:
        return dt.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except ValueError:
        return None


def _after(entries, now):
    """A time after every recorded ack, so Control Center, which applies acks in time order, keeps their order."""
    last = max((t for t in (_parse(e.get('at')) for e in entries) if t), default=None)
    moment = now.replace(microsecond=0)
    return moment if last is None or moment > last else last + dt.timedelta(seconds=1)


def _ack(iid, state, line, at, evidence_url=None):
    return {'instruction_id': iid, 'state': state, 'line': line, 'at': _iso(at), 'evidence_url': evidence_url}


def held_line(sources):
    return HELD_LINES['activation.json' if 'activation.json' in sources else 'control_center']


# ---------------------------------------------------------------------------
# Acks on a clean runner: it has no memory, so it acks what it can see. A repeat is
# ignored by Control Center (an identical ack changes nothing; a backwards one is stale).
# ---------------------------------------------------------------------------
def runner_acks(instr, held_sources, now, evidence_url=None):
    if not instr:
        return []
    if held_sources:
        return [_ack(instr['id'], 'received', RECEIVED_HELD, now, evidence_url),
                _ack(instr['id'], 'blocked', held_line(held_sources), now + dt.timedelta(seconds=1), evidence_url)]
    return [_ack(instr['id'], 'received', RECEIVED_RUNNER, now, evidence_url)]


# ---------------------------------------------------------------------------
# The persistent workspace keeps the instruction and its acks under ignored local/.
# ---------------------------------------------------------------------------
def current_path(local):
    return Path(local) / 'control-center' / 'instruction.json'


def ledger_path(local):
    return Path(local) / 'control-center' / 'acks.json'


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def read_current(local):
    value = _read(current_path(local))
    return value if value and isinstance(value.get('id'), str) and ID.match(value['id']) \
        and isinstance(value.get('words'), str) else None


def read_ledger(local):
    value = _read(ledger_path(local)) or {}
    return {k: v for k, v in value.items() if ID.match(k) and isinstance(v, list)}


def _write_ledger(local, ledger):
    kept = sorted(ledger.items(), key=lambda kv: max((str(e.get('at', '')) for e in kv[1]), default=''))[-KEEP_IDS:]
    atomic_json(ledger_path(local), dict(kept))


def keep(local, instr, held_sources, now):
    """Mirror the directive locally: the open instruction (with its words, ignored) and a received ack the
    first time it is seen. No instruction in the directive removes the local copy, so a closed, withdrawn
    or replaced one is never acted on."""
    path = current_path(local)
    if not instr:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return None
    atomic_json(path, {**instr, 'held': bool(held_sources), 'pulled_at': _iso(now),
                       'note': 'Krish\'s words. Never print, log, commit or report them (the repository is public).'})
    ledger = read_ledger(local)
    if instr['id'] not in ledger:
        ledger[instr['id']] = [_ack(instr['id'], 'received', RECEIVED_HELD if held_sources else RECEIVED_WORKSPACE,
                                    now)]
        _write_ledger(local, ledger)
    return instr


class AckRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def record(local, state, line, evidence_url, now, held):
    """`growth.py cc ack`: what the morning job did with the instruction, kept for the next report.
    It writes only the ignored ledger; nothing reaches Control Center until `growth.py cc` reports."""
    if held:
        raise AckRefused('engine_held')
    instr = read_current(local)
    if not instr:
        raise AckRefused('no_instruction')
    if state not in HAND_STATES:
        raise AckRefused('bad_ack_state')
    line = re.sub(r'\s+', ' ', line or '').strip()
    if not line_ok(line, ACK_LINE_MAX):
        raise AckRefused('bad_ack_line')
    if quotes(line, instr['words']):
        raise AckRefused('ack_quotes_words')
    if evidence_url is not None and not re.fullmatch(r'https://\S+', evidence_url):
        raise AckRefused('bad_evidence_url')
    ledger = read_ledger(local)
    entries = ledger.setdefault(instr['id'], [_ack(instr['id'], 'received', RECEIVED_WORKSPACE, now)])
    if not ack_step(entries[-1]['state'], state):
        raise AckRefused('ack_backwards')
    entry = _ack(instr['id'], state, line, _after(entries, now), evidence_url)
    entries.append(entry)
    _write_ledger(local, ledger)
    return entry


def workspace_acks(local, instr, held_sources, now):
    """The acks a workspace report carries for the directive's instruction: the received ack and the latest
    four after it. While held, the last one says blocked, engine held."""
    if not keep(local, instr, held_sources, now):
        return []
    ledger = read_ledger(local)
    entries = ledger[instr['id']]
    if held_sources:
        line = held_line(held_sources)
        last = entries[-1]
        if not (last['state'] == 'blocked' and last['line'] == line) and ack_step(last['state'], 'blocked'):
            entries.append(_ack(instr['id'], 'blocked', line, _after(entries, now)))
            _write_ledger(local, ledger)
    return [dict(e) for e in entries[:1] + entries[1:][-(ACKS_MAX - 1):]]


# ---------------------------------------------------------------------------
# The engine's state, from this repository's own files. Never invented.
# ---------------------------------------------------------------------------
def _text(root, name):
    try:
        return (Path(root) / name).read_text(encoding='utf-8')
    except OSError:
        return ''


def north_star(root=ROOT):
    """The metric, target, deadline and weekly ladder from docs/NORTH_STAR.md, or None."""
    text = _text(root, 'docs/NORTH_STAR.md')
    block = re.search(r'```yaml north-star-metric\n(.*?)```', text, re.S)
    if not block:
        return None
    body = block.group(1)
    metric = re.search(r'^metric:\s*"([^"]+)"', body, re.M)
    target = re.search(r'^target:\s*(\d+)\s*$', body, re.M)
    deadline = re.search(r'^deadline:\s*(\d{4}-\d{2}-\d{2})', body, re.M)
    ladder = [(dt.date.fromisoformat(d), int(n)) for d, n in
              re.findall(r'^\s*-\s*\[(\d{4}-\d{2}-\d{2}),\s*(\d+)\]', body, re.M)]
    if not (metric and target and deadline and ladder):
        return None
    return {'metric': metric.group(1), 'target': int(target.group(1)),
            'deadline': dt.date.fromisoformat(deadline.group(1)), 'ladder': sorted(ladder)}


def week_target(ladder, today):
    """This week's rung: the latest one on or before today (the first before the ladder starts)."""
    on_or_before = [n for day, n in ladder if day <= today]
    return on_or_before[-1] if on_or_before else ladder[0][1]


def _day(date):
    return f'{date.day} {date:%B %Y}'


def priorities(today, objectives_list, gate_lines, root=ROOT):
    """First the North Star number this week against its target; then the engine's own gates or
    constraints in its own words, in its own order."""
    out = []
    star = north_star(root)
    if star:
        reading = next((o for o in objectives_list or [] if o.get('key') == NS_KEY), None) or {}
        value = reading.get('value')
        if reading.get('availability') == 'measured' and type(value) in (int, float):
            status = f'{value:g} last week'
        elif reading.get('availability') == 'stale' and type(value) in (int, float):
            status = f'{value:g} at the last reading, now stale'
        else:
            status = 'not measured yet'
        line = clause(f'{star["metric"]}: {week_target(star["ladder"], today):,} this week, '
                      f'{star["target"]:,} by {_day(star["deadline"])}; {status}.')
        if line:
            out.append({'rank': 1, 'line': line, 'objective_key': NS_KEY})
    for text in gate_lines or []:
        line = clause(text)
        if line and len(out) < PRIORITIES_MAX and line not in {p['line'] for p in out}:
            out.append({'rank': len(out) + 1, 'line': line, 'objective_key': None})
    return out


def obsessions(root=ROOT):
    """Krish's own aims, quoted from this repository's docs, each with the day he set it."""
    out = []
    star = _text(root, 'docs/NORTH_STAR.md')
    quote = re.search(r'^> (.+)$', star, re.M)
    set_on = re.search(r'Set by Krish on (\d{1,2} [A-Z][a-z]+ \d{4})', star)
    if quote:
        words = plain(quote.group(1))
        line = words if line_ok(words, STATE_LINE_MAX) else next(
            (s for s in sentences(words)[:1] if line_ok(s, STATE_LINE_MAX)), None)
        since = dt.datetime.strptime(set_on.group(1), '%d %B %Y').date().isoformat() if set_on else None
        if line:
            out.append({'line': line, 'since': since})
    agents = _text(root, 'AGENTS.md')
    autonomy = re.search(r'^## Autonomy \(Ruling, Krish, (\d{4}-\d{2}-\d{2})\)\s*\n+Krish: "([^"]+)"', agents, re.M)
    if autonomy:
        line = f'Krish: "{plain(autonomy.group(2))}"'
        if line_ok(line, STATE_LINE_MAX):
            out.append({'line': line, 'since': autonomy.group(1)})
    owner = re.search(r'^## Owner instructions\s*\n+Krish, (\d{1,2} [A-Z][a-z]+ \d{4}): (.+?\.)(?:\s|$)', agents,
                      re.M | re.S)
    if owner:
        line = f'Krish: {plain(owner.group(2))}'
        if line_ok(line, STATE_LINE_MAX):
            out.append({'line': line, 'since': dt.datetime.strptime(owner.group(1), '%d %B %Y').date().isoformat()})
    return out[:OBSESSIONS_MAX]


def _waits_on(line):
    return 'krish' if re.search(r'\bKrish\b', line) else 'engine'


def next_steps(held, root=ROOT):
    """The first open step of docs/GET-GOING.md (skipping one that waits while held, when held), then
    NOW.md's "What is next", one sentence a step, never its North Star check line."""
    out = []
    plan = _text(root, 'docs/GET-GOING.md')
    for number, note, body in re.findall(r'^- \[ \] \*\*Step (\d+)(?: \(([^)]*)\))?\.?\*\*\.?\s*(.+)$', plan, re.M):
        if held and 'waits while held' in (note or ''):
            continue
        prefix = f'Step {number} in docs/GET-GOING.md: '
        own = clause(body, STATE_LINE_MAX - len(prefix))
        line = prefix + own if own else None
        if line:
            out.append({'line': line, 'waits_on': _waits_on(line), 'when': None})
        break
    now = _text(root, 'NOW.md')
    section = re.search(r'^## What is next[^\n]*\n(.*?)(?=^## |\Z)', now, re.M | re.S)
    items, current = [], None
    for raw in (section.group(1).splitlines() if section else []):
        if raw.startswith('- '):
            current = [raw[2:]]
            items.append(current)
        elif raw.strip() and current is not None and raw.startswith((' ', '\t')):
            current.append(raw.strip())
        elif not raw.strip():
            current = None
    for item in items:
        text = ' '.join(item)
        if text.startswith('North Star check'):
            continue
        for sentence in sentences(text):
            line = clause(sentence)
            if line and len(out) < NEXT_STEPS_MAX and line not in {s['line'] for s in out}:
                out.append({'line': line, 'waits_on': _waits_on(line), 'when': None})
    return out[:NEXT_STEPS_MAX]


def report_fields(directive, today, objectives_list, gate_lines, held, acks, root=ROOT):
    """The 1.20.0 fields a report carries, or None when the directive does not say features.engine_state."""
    if not features_on(directive):
        return None
    out = {}
    for key, value in (('priorities', priorities(today, objectives_list, gate_lines, root)),
                       ('obsessions', obsessions(root)), ('next_steps', next_steps(held, root)),
                       ('instruction_acks', list(acks or [])[:ACKS_MAX])):
        if value:
            out[key] = value
    return out or None
