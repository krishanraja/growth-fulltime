"""The crew registry: who does each job, its lint before acting and its measured
check after acting (docs/ENGINE-V2.md, section 3).

CREW lists the ten specialists of the plan in order, then the Audience Builder that
ruling 9 added. Each names its runner, a lint and a check as dotted paths to real
callables in this repository, and its card (3 KB at most) and lens (1 KB at most)
under crew/<id>/. errors() proves every path imports and is callable and every card
and lens exists within its budget; load_crew() refuses a registry that fails it.

Four checks had no code before this registry, so they live here: the Match Clock's
fixtures_fresh() and publish_to_pack_minutes(), and the Card Maker's card_lint() and
glyph_readback() (R19). Nothing here posts, sends, schedules, spends or reads the network.
"""
import copy
import datetime as dt
import importlib
from pathlib import Path
import re
import sys
import unicodedata

from .clock import LONDON

ROOT = Path(__file__).resolve().parent.parent
CARD_LIMIT = 3 * 1024
LENS_LIMIT = 1024
FIELDS = ('id', 'name', 'runner', 'lint', 'check', 'card', 'lens')
RUNNERS = ('CLI', 'Claude', 'Codex')
CREW_ID = re.compile(r'^[a-z][a-z0-9_]{1,63}$')
DOTTED = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$')
FUTURE_GRACE = dt.timedelta(minutes=5)


def _member(cid, name, runner, lint, check):
    return {'id': cid, 'name': name, 'runner': runner, 'lint': lint, 'check': check,
            'card': f'crew/{cid}/card.md', 'lens': f'crew/{cid}/lens.md'}


CREW = [
    _member('product_truth', 'Product Truth', 'CLI', 'growth.freshness', 'engine.assets.fetch'),
    _member('match_clock', 'Match Clock', 'CLI', 'engine.crew.fixtures_fresh', 'engine.crew.publish_to_pack_minutes'),
    _member('take_writer', 'Take & Script Writer', 'Codex fills, Claude ranks', 'growth.problems',
            'engine.formats.g2_verdicts'),
    _member('voice_lock', 'Voice Lock', 'Codex', 'engine.creative_system.System.load_release',
            'engine.creative_system.System.artifact_gate'),
    _member('motion_maker', 'Motion Maker', 'Codex offline; Claude calls Higgsfield and Runway',
            'engine.assets.checked_segments', 'engine.assets.probe'),
    _member('card_maker', 'Card Maker', 'Claude, through the Canva connector', 'engine.crew.card_lint',
            'engine.crew.glyph_readback'),
    _member('channel_steward', 'Channel & Pack Steward', 'Codex builds; Claude reads Buffer', 'engine.pack.check',
            'engine.buffer_read.receipts'),
    _member('measurement_analyst', 'Measurement Analyst', 'Claude', 'engine.attribution.ga4_rows',
            'engine.attribution.objectives'),
    _member('what_works', 'What-Works Analyst', 'Claude, a fresh session that made nothing', 'engine.learning.judge',
            'engine.learning.kill_double_down'),
    _member('librarian', 'Librarian', 'CLI files; Claude reads back', 'engine.library.file_plan',
            'engine.library.reconcile'),
    _member('audience_builder', 'Audience Builder', 'Claude plans; Codex prepares copy offline; Krish acts',
            'engine.audience.gate', 'engine.audience.followers_check'),
]


# ---------------------------------------------------------------------------
# Dotted paths.
# ---------------------------------------------------------------------------
def resolve(dotted):
    """The object a dotted path names, such as 'engine.pack.check' or
    'engine.creative_system.System.artifact_gate'. ValueError when it does not import."""
    if not isinstance(dotted, str) or not DOTTED.match(dotted):
        raise ValueError(f'{dotted!r} is not a dotted path such as engine.pack.check')
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))      # growth.py and scripts/ live at the repository root
    parts = dotted.split('.')
    for cut in range(len(parts) - 1, 0, -1):
        module_name = '.'.join(parts[:cut])
        try:
            found = importlib.import_module(module_name)
        except ImportError as error:
            if error.name and not module_name.startswith(error.name) and error.name != module_name:
                raise ValueError(f'{dotted}: importing {module_name} failed ({error})') from None
            continue
        for attribute in parts[cut:]:
            if not hasattr(found, attribute):
                raise ValueError(f'{dotted}: {module_name} has no {".".join(parts[cut:])}')
            found = getattr(found, attribute)
        return found
    raise ValueError(f'{dotted}: no module in it can be imported')


def _size(path):
    """Bytes with LF line endings, as the CI budget counts them on a Windows checkout too."""
    return len(path.read_bytes().replace(b'\r\n', b'\n'))


# ---------------------------------------------------------------------------
# The registry.
# ---------------------------------------------------------------------------
def errors(crew=None, root=None):
    """Every reason the crew registry cannot be used, in plain words. Empty means it can."""
    crew = CREW if crew is None else crew
    root = Path(root) if root else ROOT
    if not isinstance(crew, list) or not crew:
        return ['the crew must be a non-empty list of members']
    out, ids, names = [], set(), set()
    for number, member in enumerate(crew, 1):
        if not isinstance(member, dict) or set(member) != set(FIELDS):
            out.append(f'crew member {number} must carry exactly ' + ', '.join(FIELDS))
            continue
        cid = member['id']
        label = cid if isinstance(cid, str) else f'crew member {number}'
        if not isinstance(cid, str) or not CREW_ID.match(cid):
            out.append(f'{label}: the id must be lower_snake letters and digits')
        elif cid in ids:
            out.append(f'{label}: the id is listed twice')
        ids.add(cid)
        name = member['name']
        if not isinstance(name, str) or not name.strip():
            out.append(f'{label}: the name must be non-empty text')
        elif name in names:
            out.append(f'{label}: the name {name!r} is listed twice')
        names.add(name)
        runner = member['runner']
        if not isinstance(runner, str) or not any(r in runner for r in RUNNERS):
            out.append(f'{label}: the runner must name the CLI, Claude or Codex')
        for key in ('lint', 'check'):
            try:
                found = resolve(member[key])
            except ValueError as error:
                out.append(f'{label}: the {key} does not resolve ({error})')
                continue
            if not callable(found):
                out.append(f'{label}: the {key} {member[key]} is not callable')
        for key, limit in (('card', CARD_LIMIT), ('lens', LENS_LIMIT)):
            want = f'crew/{cid}/{key}.md'
            if member[key] != want:
                out.append(f'{label}: the {key} must be {want}')
                continue
            path = root / want
            if not path.is_file():
                out.append(f'{label}: {want} is missing')
                continue
            size = _size(path)
            if size > limit:
                out.append(f'{label}: {want} is {size} bytes, over the {limit}-byte budget')
            try:
                path.read_bytes().decode('utf-8')
            except UnicodeDecodeError:
                out.append(f'{label}: {want} is not UTF-8')
    folder = root / 'crew'
    if folder.is_dir():
        for path in sorted(p for p in folder.iterdir() if p.is_dir()):
            if path.name not in ids and not path.name.startswith(('.', '_')):
                out.append(f'crew/{path.name}/ is not in the crew registry')
    return out


def load_crew(ids=None):
    """The crew in order, as copies, or only the members named in ids, in the order given.
    Refuses a registry that errors() finds broken, and an id that is not a member."""
    problems = errors()
    if problems:
        raise ValueError('the crew registry is broken: ' + '; '.join(problems))
    if ids is None:
        return copy.deepcopy(CREW)
    if isinstance(ids, (str, bytes)):
        raise ValueError('ids must be a list of crew ids, such as ["librarian"]')
    known = {member['id']: member for member in CREW}
    unknown = [cid for cid in ids if cid not in known]
    if unknown:
        raise ValueError('not crew members: ' + ', '.join(map(str, unknown)))
    return [copy.deepcopy(known[cid]) for cid in ids]


# ---------------------------------------------------------------------------
# The Match Clock: fixtures read today, and minutes from publish to pack.
# ---------------------------------------------------------------------------
def _moment(value, what):
    try:
        moment = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f'{what} must be an ISO date and time with its UTC offset') from None
    if moment.tzinfo is None:
        raise ValueError(f'{what} must carry its UTC offset')
    return moment


def fixtures_fresh(read_at, now):
    """The Match Clock's lint: [] when the fixtures were read today in London, else the
    reasons. A fixtures read in the future, or on an earlier London day, is refused."""
    try:
        read, current = _moment(read_at, 'read_at'), _moment(now, 'now')
    except ValueError as error:
        return [str(error)]
    if read > current + FUTURE_GRACE:
        return ['the fixtures were read in the future; check the clock before ranking']
    day, today = read.astimezone(LONDON).date(), current.astimezone(LONDON).date()
    if day != today:
        return [f'the fixtures were read on {day.isoformat()}, not today ({today.isoformat()}, London): '
                'refresh them before ranking']
    return []


def publish_to_pack_minutes(published_at, pack_ready_at):
    """The Match Clock's measured check: whole minutes from the product's publish of the
    edition (its published_at) to the pack being ready. A pack before its publish is refused."""
    published, ready = _moment(published_at, 'published_at'), _moment(pack_ready_at, 'pack_ready_at')
    if ready < published:
        raise ValueError('the pack cannot be ready before the edition it links to was published')
    return int((ready - published).total_seconds() // 60)


# ---------------------------------------------------------------------------
# The Card Maker: the lint before making a card, and glyph readback (R19).
# ---------------------------------------------------------------------------
CARD_FIELDS = ('template_id', 'text', 'channel', 'width', 'height')


def card_lint(card, recipe, pinned_templates):
    """The Card Maker's lint before acting: [] when the card is made from a pinned Full
    Time template, shows "AI Pundit", carries no league or broadcaster mark and has its
    channel's cut size in the recipe (engine.formats.recipe); else the reasons.

    card is {template_id, text, channel, width, height}; pinned_templates the template IDs
    pinned in the brand-kit receipt."""
    import growth
    from .audience import LEAGUE
    if not isinstance(card, dict) or set(card) != set(CARD_FIELDS):
        raise ValueError('card must carry exactly ' + ', '.join(CARD_FIELDS))
    if not isinstance(recipe, dict) or not isinstance(recipe.get('cuts'), dict):
        raise ValueError('recipe must be a format recipe with its cuts, from engine.formats.recipe')
    if isinstance(pinned_templates, (str, bytes)) or not hasattr(pinned_templates, '__iter__'):
        raise ValueError('pinned_templates must list the template IDs pinned in the brand-kit receipt')
    text = card['text'] if isinstance(card['text'], str) else ''
    out = []
    if card['template_id'] not in set(pinned_templates):
        out.append('the card is not made from a pinned Full Time template: use one pinned in the brand-kit receipt')
    if 'AI Pundit' not in text:
        out.append('the card must show "AI Pundit", exactly')
    found = growth.BROADCASTERS.search(text) or LEAGUE.search(text)
    if found:
        out.append(f'the card shows a league or broadcaster mark: "{found.group(0)}"')
    cut = recipe['cuts'].get(card['channel'])
    if not isinstance(cut, dict):
        out.append(f'the {recipe.get("format_id", "format")} recipe has no cut for this channel')
    elif (card['width'], card['height']) != (cut.get('width'), cut.get('height')):
        out.append(f'the card is {card["width"]}x{card["height"]}, but the cut for this channel is '
                   f'{cut.get("width")}x{cut.get("height")}')
    return out


def _plain(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def glyph_readback(slot_text, read_back, font_glyphs=None):
    """The Card Maker's measured check (R19): [] when the text read back from the design
    equals the slot text, after line wrapping, and every character has a glyph in the
    font when font_glyphs (the characters the font covers) is given; else the reasons."""
    if not isinstance(slot_text, str) or not slot_text.strip():
        raise ValueError('slot_text must be the non-empty text the slot was filled with')
    if not isinstance(read_back, str):
        raise ValueError('read_back must be the text read back from the design')
    want, got = _plain(slot_text), _plain(read_back)
    out = []
    if want != got:
        lost = sorted(set(want) - set(got) - {' '})
        out.append(f'the design reads back "{got[:120]}", not the slot text "{want[:120]}"'
                   + (f'; missing: {" ".join(lost)}' if lost else ''))
    if font_glyphs is not None:
        covered = set(font_glyphs)
        bare = sorted({ch for ch in want if not ch.isspace() and ch not in covered})
        if bare:
            out.append('the font has no glyph for: ' + ' '.join(bare))
    return out
