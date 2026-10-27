"""Short fresh sessions: the 36 KB pack, the session budgets and the ledger
(docs/ENGINE-V2.md, section 5).

A session starts from a pack, never from the long documents. pack() puts
docs/ENGINE.md first, then the spec as canonical JSON (called signed only when its
digest is the one Krish cleared), then the crew cards in play (for an independent
review, their lenses only), what this kind of session works from (a review: the
COPY.md rubric and the contact sheet; a build: its task card and read files; a
production run: its instance and locks), the open findings, the gate status and the
last report summary, and refuses anything over 36 KB. A part the caller did not
supply is printed as not supplied, never as none.

Every session leaves one line in local/engine/sessions.jsonl: its kind, when it
started and ended, Claude tokens in and out, calls, engine minutes, minutes spent
waiting on Krish, Krish's own minutes and its outcome. Unknown is null, never zero.
The 20x target is measured from this ledger and scripts/baseline.py, never claimed.
Budgets are config in engine/config/budgets.json. Nothing here calls a model,
posts, sends or spends."""
import datetime as dt
import json
import math
from pathlib import Path
import re

from . import reporting

KINDS = ('scheduled', 'orchestrator', 'production', 'review', 'build')
PACK_LIMIT = 36 * 1024
CARD_BYTES, LENS_BYTES = 3 * 1024, 1024
LEDGER_FIELDS = ('kind', 'started_at', 'ended_at', 'tokens_in', 'tokens_out', 'calls', 'engine_minutes',
                 'waiting_minutes', 'krish_minutes', 'outcome')
COUNTS = ('tokens_in', 'tokens_out', 'calls')
MINUTES = ('engine_minutes', 'waiting_minutes', 'krish_minutes')
BUDGET_FIELDS = ('max_tokens', 'max_engine_minutes', 'note')
BUDGET_TOP = ('_about', 'schema_version', 'kinds', 'krish_minutes_per_day')
MAX_OUTCOME = 200
ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / 'docs' / 'ENGINE.md'
COPY = ROOT / 'COPY.md'
RUBRIC = '## Rubric for packs'
BUDGETS = Path(__file__).resolve().parent / 'config' / 'budgets.json'
CREW_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}')     # always fullmatch: '$' alone lets 'x\n' through


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_budgets(path=None):
    """engine/config/budgets.json, checked: every kind once, each budget a whole number
    of 0 or more, null only for build (its budget is the card's), and Krish's daily minutes."""
    path = Path(path) if path else BUDGETS
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path}: the session budgets are unreadable ({error})')
    if not isinstance(data, dict) or not isinstance(data.get('kinds'), dict):
        raise ValueError(f'{path}: the session budgets need a kinds object')
    errors = [f'{key}: unknown field' for key in data if key not in BUDGET_TOP]
    kinds = data['kinds']
    errors += [f'kinds.{kind}: is required' for kind in KINDS if kind not in kinds]
    for kind, budget in kinds.items():
        if kind not in KINDS:
            errors.append(f'kinds.{kind}: is not one of {", ".join(KINDS)}')
            continue
        if not isinstance(budget, dict):
            errors.append(f'kinds.{kind}: must be an object')
            continue
        errors += [f'kinds.{kind}.{key}: unknown field' for key in budget if key not in BUDGET_FIELDS]
        for key in ('max_tokens', 'max_engine_minutes'):
            value = budget.get(key, 'missing')
            if value == 'missing':
                errors.append(f'kinds.{kind}.{key}: is required')
            elif value is None:
                if kind != 'build':
                    errors.append(f'kinds.{kind}.{key}: only build may be null (its budget is the card\'s)')
            elif type(value) is not int or value < 0:
                errors.append(f'kinds.{kind}.{key}: must be a whole number of 0 or more')
    daily = data.get('krish_minutes_per_day')
    if not _number(daily) or daily <= 0:
        errors.append('krish_minutes_per_day: must be a number above 0')
    if errors:
        raise ValueError(f'{path}: ' + '; '.join(errors))
    return data


def _crew_names(kind, crew):
    if isinstance(crew, (str, bytes)) or crew is None:
        raise ValueError('crew must be a list of crew member names, such as ["librarian"]')
    names = list(crew)
    for name in names:
        if not isinstance(name, str) or not CREW_NAME.fullmatch(name):
            raise ValueError(f'crew member {name!r} is not a crew folder name (lowercase letters, digits, - and _)')
    if len(set(names)) != len(names):
        raise ValueError('crew names one member twice')
    if kind == 'review' and not names:
        raise ValueError('a review pack needs at least one crew member, for its lens')
    return names


def _crew_section(kind, crew_dir, names):
    filename, limit = ('lens.md', LENS_BYTES) if kind == 'review' else ('card.md', CARD_BYTES)
    title = 'Lenses for this review' if kind == 'review' else 'Crew cards in play'
    if not names:
        return f'## {title}\n\nNo crew member is in play.'
    parts = [f'## {title}']
    for name in names:
        path = Path(crew_dir) / name / filename
        try:
            raw = path.read_bytes().replace(b'\r\n', b'\n')   # the same budget on a Windows checkout
        except OSError:
            raise ValueError(f'{path}: is missing; every crew member in play needs its {filename}')
        if len(raw) > limit:
            raise ValueError(f'{path}: is {len(raw)} bytes; a {filename} is at most {limit} bytes')
        parts.append(f'### {name} ({filename})\n\n' + raw.decode('utf-8').strip())
    return '\n\n'.join(parts)


def _not_supplied(where):
    return f'Not supplied to this pack, so unknown here, not none: {where}.'


def _findings_section(findings):
    if findings is None:
        return '## Open findings\n\n' + _not_supplied('read docs/FAILURE-REGISTER.md')
    if isinstance(findings, (str, bytes, dict)):
        raise ValueError('findings must be a list of open findings (text or objects)')
    lines = []
    for item in findings:
        if isinstance(item, str) and item.strip():
            lines.append('- ' + item.strip())
        elif isinstance(item, dict):
            lines.append('- ' + reporting.canonical(item))
        else:
            raise ValueError(f'finding {item!r} must be non-empty text or an object')
    return '## Open findings\n\n' + ('\n'.join(lines) if lines else 'None open.')


def _gates_section(gates):
    if gates is None:
        return '## Gate status\n\n' + _not_supplied("read Krish's list in Control Center and local/engine/gates/")
    if not isinstance(gates, dict):
        raise ValueError('gates must be an object, such as {"G1": "waiting on Krish"}')
    lines = [f'- {key}: {value if isinstance(value, str) else reporting.canonical(value)}'
             for key, value in sorted(gates.items(), key=lambda pair: str(pair[0]))]
    return '## Gate status\n\n' + ('\n'.join(lines) if lines else 'No gate status recorded.')


def _report_section(last_report):
    if last_report is None:
        body = _not_supplied('read local/control-center/last.json')
    elif isinstance(last_report, str):
        body = last_report.strip() or 'No report yet.'
    else:
        body = reporting.canonical(last_report)
    return '## Last report summary\n\n' + body


def _spec_section(spec, signed_sha256):
    if spec is None:
        if signed_sha256 is not None:
            raise ValueError('signed_sha256 was given without the spec it signs')
        return '## Spec\n\nNo spec for this session.'
    if not isinstance(spec, dict):
        raise ValueError('spec must be the spec object')
    digest = reporting.canonical_sha256(spec)
    if signed_sha256 is None:
        return f'## Spec (not signed)\n\nsha256 {digest}\n\n' + reporting.canonical(spec)
    if signed_sha256 != digest:
        raise ValueError(f'the spec is sha256 {digest}, not the {signed_sha256} Krish signed; '
                         'a changed spec needs his Clear again')
    return f'## Signed spec\n\nsha256 {digest}\n\n' + reporting.canonical(spec)


def _rubric(copy_path):
    try:
        text = Path(copy_path).read_text(encoding='utf-8')
    except OSError:
        raise ValueError(f'{copy_path}: is missing; a review pack carries its rubric')
    start = text.find('\n' + RUBRIC)
    if start < 0:
        raise ValueError(f'{copy_path}: has no "{RUBRIC[3:]}" section')
    end = text.find('\n## ', start + 1)
    return text[start + 1:end if end >= 0 else len(text)].strip().replace(RUBRIC, '## COPY.md: ' + RUBRIC[3:], 1)


def _work_section(kind, card, contact_sheet, instance, locks, copy_path):
    """What this kind of session works from (docs/ENGINE-V2.md, section 5)."""
    given = {'card': card, 'contact_sheet': contact_sheet, 'instance': instance, 'locks': locks}
    allowed = {'review': ('contact_sheet',), 'build': ('card',), 'production': ('instance', 'locks')}.get(kind, ())
    stray = [key for key, value in given.items() if value is not None and key not in allowed]
    if stray:
        raise ValueError(f'a {kind} pack does not carry {", ".join(stray)}')
    if kind == 'review':
        if contact_sheet is not None and not (isinstance(contact_sheet, str) and contact_sheet.strip()):
            raise ValueError('contact_sheet must be the contact sheet\'s path or link')
        sheet = contact_sheet.strip() if contact_sheet else _not_supplied('ask for the contact sheet')
        return _rubric(copy_path) + '\n\n## Contact sheet\n\n' + sheet
    if kind == 'build':
        if card is None:
            return '## Task card\n\n' + _not_supplied('the card names what this build reads and writes')
        from . import dispatch
        errors = dispatch.validate_card(card)
        if errors:
            raise ValueError('the task card is refused: ' + '; '.join(errors))
        reads = '\n'.join('- ' + path for path in card['read_files']) or 'None: the card reads nothing.'
        return (f'## Task card {card["card_id"]}\n\n' + reporting.canonical(card)
                + '\n\n### Read these files, and only these\n\n' + reads)
    if kind == 'production':
        parts = []
        for title, value in (('Instance', instance), ('Locks', locks)):
            if value is not None and not isinstance(value, dict):
                raise ValueError(f'{title.lower()} must be an object')
            parts.append(f'## {title}\n\n' + (reporting.canonical(value) if value is not None
                                                 else _not_supplied('read the run folder in Growth Build')))
        return '\n\n'.join(parts)
    return None


def pack(kind, crew_dir, crew, spec=None, findings=None, gates=None, last_report=None, index=None,
         signed_sha256=None, card=None, contact_sheet=None, instance=None, locks=None, copy=None):
    """The text a fresh session starts from. docs/ENGINE.md comes first (index= and copy=
    swap in other files, for tests). None means not supplied, printed as unknown, never
    as none: findings=[] is what says none are open. The spec is labelled signed only
    when signed_sha256 (the digest of the spec Krish cleared) equals its digest; a
    mismatch is refused. ValueError names the size when it is over PACK_LIMIT bytes."""
    if kind not in KINDS:
        raise ValueError(f'session kind {kind!r} is not one of {", ".join(KINDS)}')
    if kind == 'scheduled':
        raise ValueError('a scheduled run has no pack: it is the CLI at zero model tokens')
    names = _crew_names(kind, crew)
    index_path = Path(index) if index else INDEX
    try:
        head = index_path.read_text(encoding='utf-8').strip()
    except OSError:
        raise ValueError(f'{index_path}: is missing; a pack starts from docs/ENGINE.md')
    work = _work_section(kind, card, contact_sheet, instance, locks, copy or COPY)
    sections = [head, f'# Session pack: {kind}', _spec_section(spec, signed_sha256),
                _crew_section(kind, crew_dir, names), work, _findings_section(findings), _gates_section(gates),
                _report_section(last_report)]
    text = '\n\n'.join(part for part in sections if part is not None) + '\n'
    size = len(text.encode('utf-8'))
    if size > PACK_LIMIT:
        raise ValueError(f'the {kind} pack is {size} bytes, over the {PACK_LIMIT}-byte limit (36 KB); '
                         'trim the findings or the report summary, never the index')
    return text


def _moment(value):
    if not isinstance(value, str) or 'T' not in value:
        return None
    try:
        moment = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def record_errors(record):
    """Every reason a ledger record is refused, in plain words. Empty means valid."""
    if not isinstance(record, dict):
        return ['record: must be an object']
    out = [f'record.{key}: unknown field' for key in record if key not in LEDGER_FIELDS]
    out += [f'record.{key}: is required (null when unknown)' for key in LEDGER_FIELDS if key not in record]
    if record.get('kind', KINDS[0]) not in KINDS:
        out.append(f'record.kind: must be one of {", ".join(KINDS)}')
    started, ended = _moment(record.get('started_at')), _moment(record.get('ended_at'))
    for key, moment in (('started_at', started), ('ended_at', ended)):
        if key in record and moment is None:
            out.append(f'record.{key}: must be an ISO date and time with its UTC offset')
    if started and ended and ended <= started:
        out.append('record.ended_at: must be after started_at')
    for key in COUNTS:
        value = record.get(key)
        if value is not None and (type(value) is not int or value < 0):
            out.append(f'record.{key}: must be a whole number of 0 or more, or null when unknown')
    for key in MINUTES:
        value = record.get(key)
        if value is not None and (not _number(value) or value < 0):
            out.append(f'record.{key}: must be a number of 0 or more, or null when unknown')
    outcome = record.get('outcome')
    if 'outcome' in record and (not isinstance(outcome, str) or not outcome.strip() or len(outcome) > MAX_OUTCOME):
        out.append(f'record.outcome: must be non-empty text of at most {MAX_OUTCOME} characters')
    return out


def ledger_append(local_dir, record):
    """Append one session to <local_dir>/engine/sessions.jsonl and return that path."""
    errors = record_errors(record)
    if errors:
        raise ValueError('the session record is refused: ' + '; '.join(errors))
    path = Path(local_dir) / 'engine' / 'sessions.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    # ASCII escapes, so a U+2028 or U+0085 in an outcome never splits the line for any reader.
    line = json.dumps({key: record[key] for key in LEDGER_FIELDS}, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':'))
    with open(path, 'a', encoding='utf-8', newline='\n') as handle:
        handle.write(line + '\n')
    return path


def read_ledger(ledger_path):
    """Every record in the ledger, each checked again; ValueError names a bad line."""
    path = Path(ledger_path)
    records = []
    # One record per '\n', never splitlines(): it also breaks at U+2028, U+2029 and U+0085.
    for number, line in enumerate(path.read_text(encoding='utf-8').split('\n'), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            raise ValueError(f'{path}:{number}: is not JSON')
        errors = record_errors(record)
        if errors:
            raise ValueError(f'{path}:{number}: ' + '; '.join(errors))
        records.append(record)
    return records


def _day(date):
    if isinstance(date, dt.datetime):
        raise ValueError('date must be a London date (YYYY-MM-DD), not a date and time')
    if isinstance(date, dt.date):
        return date
    try:
        return dt.date.fromisoformat(str(date))
    except ValueError:
        raise ValueError(f'date {date!r} must be a London date (YYYY-MM-DD)')


def _london_day(record):
    return _moment(record['started_at']).astimezone(reporting.LONDON).date()


def krish_minutes_on(ledger_path, date):
    """Krish's minutes on sessions that started on this London date. None when the
    ledger is missing or no session that day recorded them: unknown is not zero."""
    day, path = _day(date), Path(ledger_path)
    if not path.exists():
        return None
    known = [r['krish_minutes'] for r in read_ledger(path)
             if _london_day(r) == day and r['krish_minutes'] is not None]
    return sum(known) if known else None


def budget_errors(ledger_path, date, budgets=None):
    """Plain-English flags for one London date: Krish over his daily minutes, and any
    session over its kind's token or engine-minute budget. Unknown values flag nothing."""
    if budgets is None or isinstance(budgets, (str, Path)):
        budgets = load_budgets(budgets)
    day, path = _day(date), Path(ledger_path)
    errors = []
    limit = budgets['krish_minutes_per_day']
    spent = krish_minutes_on(path, day)
    if spent is not None and spent > limit:
        errors.append(f'{day}: Krish spent {spent:g} minutes on engine sessions, over his {limit:g}-minute daily budget')
    if not path.exists():
        return errors
    for record in read_ledger(path):
        if _london_day(record) != day:
            continue
        budget = budgets['kinds'][record['kind']]
        known = [record[key] for key in ('tokens_in', 'tokens_out') if record[key] is not None]
        tokens = sum(known) if known else None
        cap = budget['max_tokens']
        if cap is not None and tokens is not None and tokens > cap:
            errors.append(f'{day}: the {record["kind"]} session started {record["started_at"]} used {tokens} '
                          f'Claude tokens, over its budget of {cap}')
        minutes, cap = record['engine_minutes'], budget['max_engine_minutes']
        if cap is not None and minutes is not None and minutes > cap:
            errors.append(f'{day}: the {record["kind"]} session started {record["started_at"]} ran {minutes:g} '
                          f'engine minutes, over its budget of {cap}')
    return errors
