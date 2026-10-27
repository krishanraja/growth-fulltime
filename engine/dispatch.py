"""Codex task-card dispatch with the allowance guard (docs/ENGINE-V2.md, section 6).

A task card is the whole brief for one build or production job: a pinned model and
effort, its minutes and calls, a worktree for a build card, the files it may write
and at most five it reads, the never list, the interface verbatim, the acceptance
commands and the shape of its answer. validate_card() is the enforcement and
tasks/card.schema.json describes the same shape for people and tooling.

guard() is the allowance guard. The Codex allowance is shared by every venture, so
a Codex card is refused when the reading is unknown, stale or above 80%, unless a
spend decision from Krish names that exact card. command() only builds the argv for
codex-companion; this module never starts a process. After a run, Claude reruns the
acceptance commands outside the sandbox and outside_write_allow() checks the diff:
Codex's own report is never evidence."""
import datetime as dt
from fnmatch import fnmatchcase
import math
import os
import re

from . import reporting

PINNED_CODEX_MODEL = 'gpt-6.1-sol'
REFUSED_MODELS = ('gpt-6-astra',)
CARD_LIMIT = 6 * 1024
KINDS = ('build', 'production')
EXECUTORS = ('codex', 'claude')
EFFORTS = ('low', 'medium', 'high')
NEVER = ('git', 'network', 'mcp', 'publishing', 'new_dependencies', 'writes_outside_write_allow')
REQUIRED = ('card_id', 'kind', 'executor', 'model', 'effort', 'max_minutes', 'max_calls', 'write_allow',
            'read_files', 'never', 'interface', 'acceptance', 'return_shape')
OPTIONAL = ('worktree', 'goal')
MAX_MINUTES, MAX_CALLS, MAX_READ_FILES = 120, 400, 5
ALLOWANCE_CEILING = 80
READING_MAX_AGE = dt.timedelta(hours=1)
WORKTREE_ROOT = '../growth-fulltime-wt/'
CARD_ID = re.compile(r'^[a-z0-9-]+$')
DRIVE = re.compile(r'^[A-Za-z]:')
GLOB = re.compile(r'[*?\[]')
GIT_PROBES = ('.git/config', '.git/HEAD', '.git/hooks/pre-commit')


def _text(value):
    return isinstance(value, str) and value.strip() != ''


def _path_errors(value, path, globs):
    """A repo-relative path or glob: forward slashes, never absolute, no '..', never .git."""
    if not _text(value):
        return [f'{path}: must be a non-empty repo-relative path']
    out = []
    if '\\' in value:
        out.append(f'{path}: {value!r} must use forward slashes')
    if value.startswith(('/', '~')) or DRIVE.match(value):
        out.append(f'{path}: {value!r} is absolute; paths are relative to the repository root')
    if '..' in value:
        out.append(f'{path}: {value!r} contains ..; a card never reaches outside the repository')
    if not globs and GLOB.search(value):
        out.append(f'{path}: {value!r} is a glob; name each file to read')
    segments = value.split('/')
    if ('.git' in segments or fnmatchcase('.git', segments[0])
            or any(fnmatchcase(probe, value) for probe in GIT_PROBES)):
        out.append(f'{path}: {value!r} touches .git')
    return out


def _paths(card, key, globs, most=None):
    value = card.get(key)
    if not isinstance(value, list) or (globs and not value):
        return [f'card.{key}: must be a {"non-empty " if globs else ""}list of repo-relative paths']
    out = []
    if most is not None and len(value) > most:
        out.append(f'card.{key}: names {len(value)} files; a card reads at most {most}')
    if globs and value == ['**']:
        out.append('card.write_allow: ** is the whole repository; name the files or folders the card may write')
    for i, item in enumerate(value):
        out += _path_errors(item, f'card.{key}[{i}]', globs)
    if len(set(map(str, value))) != len(value):
        out.append(f'card.{key}: names one path twice')
    return out


def _model(card, out):
    model = card.get('model')
    if not _text(model):
        out.append('card.model: is required and never empty; a card never inherits the default model')
    elif model.strip().lower() == 'default':
        out.append('card.model: is never "default"; pin the model')
    elif model.strip().lower() in REFUSED_MODELS:
        out.append(f'card.model: {model} is refused; it burns the shared allowance 2 to 2.6 times faster')
    elif card.get('executor') == 'codex' and model != PINNED_CODEX_MODEL:
        out.append(f'card.model: a Codex card runs on {PINNED_CODEX_MODEL}, not {model}')


def validate_card(card):
    """Every reason the task card is refused, in plain words. Empty means valid."""
    if not isinstance(card, dict):
        return ['card: must be an object']
    out = [f'card.{key}: is required' for key in REQUIRED if key not in card]
    out += [f'card.{key}: unknown field' for key in card if key not in REQUIRED + OPTIONAL]
    card_id, kind = card.get('card_id'), card.get('kind')
    if not isinstance(card_id, str) or not CARD_ID.match(card_id):
        out.append('card.card_id: must be lowercase letters, digits and hyphens only')
    if kind not in KINDS:
        out.append('card.kind: must be build or production')
    if card.get('executor') not in EXECUTORS:
        out.append('card.executor: must be codex or claude')
    _model(card, out)
    if card.get('effort') not in EFFORTS:
        out.append('card.effort: must be low, medium or high')
    for key, most in (('max_minutes', MAX_MINUTES), ('max_calls', MAX_CALLS)):
        value = card.get(key)
        if type(value) is not int or not 1 <= value <= most:
            out.append(f'card.{key}: must be a whole number from 1 to {most}')
    if kind == 'build':
        expected = WORKTREE_ROOT + (card_id if isinstance(card_id, str) else '<card_id>')
        if card.get('worktree') != expected:
            out.append(f'card.worktree: a build card runs in its own worktree, exactly {expected}')
    elif kind == 'production' and 'worktree' in card:
        out.append('card.worktree: a production card runs in the main checkout with '
                   '--require-existing-history, never in a worktree')
    out += _paths(card, 'write_allow', True)
    out += _paths(card, 'read_files', False, MAX_READ_FILES)
    never = card.get('never')
    if not isinstance(never, list) or not all(_text(item) for item in never):
        out.append('card.never: must be a list of what the card never does')
    else:
        missing = [item for item in NEVER if item not in never]
        if missing:
            out.append('card.never: must include ' + ', '.join(missing))
        if len(set(never)) != len(never):
            out.append('card.never: names one item twice')
    if not _text(card.get('interface')):
        out.append('card.interface: must be the interface, verbatim')
    acceptance = card.get('acceptance')
    if not isinstance(acceptance, list) or not acceptance or not all(_text(item) for item in acceptance):
        out.append('card.acceptance: must be a non-empty list of shell commands that exit 0 when the card is done')
    shape = card.get('return_shape')
    if not isinstance(shape, dict) or not shape:
        out.append('card.return_shape: must be an object naming each field of the answer')
    if 'goal' in card and not _text(card.get('goal')):
        out.append('card.goal: when present, must be non-empty text')
    try:
        size = len(reporting.canonical(card).encode('utf-8'))
    except ValueError:
        out.append('card: must be plain JSON')
    else:
        if size > CARD_LIMIT:
            out.append(f'card: is {size} bytes as canonical JSON, over the {CARD_LIMIT}-byte limit (6 KB)')
    return out


def _moment(value):
    if isinstance(value, dt.datetime):
        moment = value
    elif isinstance(value, str) and 'T' in value:
        try:
            moment = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo is not None else None


def _reading_problem(reading, now):
    if reading is None:
        return 'the Codex allowance reading is unknown'
    if not isinstance(reading, dict):
        return 'the Codex allowance reading is unreadable'
    pct, read_at = reading.get('pct'), _moment(reading.get('read_at'))
    if type(pct) not in (int, float) or not math.isfinite(pct) or pct < 0:
        return 'the Codex allowance reading has no usable pct'
    if read_at is None:
        return 'the Codex allowance reading has no read_at with its UTC offset'
    if read_at > now:
        return f'the Codex allowance reading is dated {reporting.iso(read_at)}, in the future'
    if now - read_at > READING_MAX_AGE:
        minutes = int((now - read_at).total_seconds() // 60)
        return f'the Codex allowance reading is {minutes} minutes old; a reading counts for one hour'
    if pct > ALLOWANCE_CEILING:
        return f'the Codex allowance is at {pct:g}%, over the {ALLOWANCE_CEILING}% ceiling'
    return None


def _decision_problem(card, decision):
    if decision is None:
        return 'no spend decision names this card'
    if not isinstance(decision, dict) or not _text(decision.get('decision_id')):
        return 'the spend decision has no decision_id'
    if decision.get('approved') is not True:
        return f'spend decision {decision["decision_id"]} is not an approval'
    if decision.get('card_id') != card.get('card_id'):
        return f'spend decision {decision["decision_id"]} names {decision.get("card_id")!r}, not this card'
    return None


def guard(card, reading, now, spend_decision=None):
    """None when the card may use the Codex allowance, else ValueError saying why.
    reading = {'pct': number, 'read_at': ISO time}; spend_decision = {'decision_id',
    'approved': True, 'card_id'} from Krish's spend decision in Control Center."""
    if not isinstance(card, dict) or card.get('executor') not in EXECUTORS:
        raise ValueError('card.executor must be codex or claude before the guard can read it')
    if card['executor'] != 'codex':
        return None
    current = _moment(now)
    if current is None:
        raise ValueError('now must be a date and time with its UTC offset')
    problem = _reading_problem(reading, current)
    if problem is None:
        return None
    refusal = _decision_problem(card, spend_decision)
    if refusal is None:
        return None
    raise ValueError(f'card {card.get("card_id")}: {problem}, and {refusal}. Codex work needs a spend '
                     'decision from Krish in Control Center that names this card.')


def command(card, plugin_root, prompt_file):
    """The argv that dispatches a valid Codex card through codex-companion. It is never run here."""
    errors = validate_card(card)
    if errors:
        raise ValueError('the card is refused: ' + '; '.join(errors))
    if card['executor'] != 'codex':
        raise ValueError(f'card {card["card_id"]}: only a Codex card dispatches through codex-companion; '
                         'a Claude card runs in a fresh Claude Code session')
    if not plugin_root or not str(plugin_root).strip():
        raise ValueError('plugin_root must name the Codex plugin folder')
    if not prompt_file or not str(prompt_file).strip():
        raise ValueError('prompt_file must name the card\'s prompt file')
    return ['node', os.path.join(str(plugin_root), 'scripts', 'codex-companion.mjs'), 'task', '--background',
            '--fresh', '--write', '--model', card['model'], '--effort', card['effort'],
            '--cwd', card.get('worktree') or '.', '--prompt-file', str(prompt_file)]


def _clean(path):
    text = str(path).replace('\\', '/')
    while text.startswith('./'):
        text = text[2:]
    return text


def outside_write_allow(changed_paths, write_allow):
    """The changed paths no write_allow glob matches (fnmatch, case-sensitive), in order.
    A path that is absolute, climbs with .. or sits in .git is always outside."""
    if isinstance(changed_paths, (str, bytes)) or isinstance(write_allow, (str, bytes)):
        raise ValueError('changed_paths and write_allow must be lists of paths')
    patterns = [_clean(p) for p in (write_allow or [])]
    out = []
    for path in changed_paths:
        clean = _clean(path)
        segments = clean.split('/')
        escaped = (not clean or clean.startswith('/') or bool(DRIVE.match(clean))
                   or '..' in segments or '.git' in segments)
        if (escaped or not any(fnmatchcase(clean, p) for p in patterns)) and path not in out:
            out.append(path)
    return out
