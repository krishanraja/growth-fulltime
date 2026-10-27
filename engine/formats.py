"""The format registry and computed readiness (docs/ENGINE-V2.md, section 3).

Each format has a public skeleton in formats/<format_id>/recipe.json: its slots,
render steps, per-channel cuts and pre-live checks. The locks themselves stay in
the private creative system. Readiness is computed here from Krish's verdicts and
pre-live checks only (ruling 7); no session ever writes "ready", and post-live
metrics are never inputs. Nothing here posts, sends, schedules or spends."""
import datetime as dt
import json
from pathlib import Path
import re

from . import reporting, spec

ROOT = Path(__file__).resolve().parent.parent
FORMATS_DIR = ROOT / 'formats'
RECIPE = ('format_id', 'title', 'creative_system_format', 'published_pundits_min', 'links_to',
          'whole_match_claims_allowed', 'master', 'cuts', 'slots', 'render_steps', 'prelive_checks', 'cost_class')
LINKS = ('exact_show', 'today')
COST_CLASSES = ('zero_generation', 'zero_marginal', 'credits')
# The registered render steps. A recipe naming any other step is refused, which is
# how "no per-run bespoke code" is kept: a new step is registered here, with a test.
RENDER_STEPS = ('ffmpeg_take_render', 'ffmpeg_row_render', 'ffmpeg_ad_render', 'ffmpeg_cut',
                'canva_autofill', 'canva_export', 'tv_mix')
VERDICTS = ('post_it', 'edit', 'reject')
NAME = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
READY_FIXTURES = 3
# Rulings 1 and 11 as recipe rules: each link target carries its own pre-live checks.
REQUIRED_CHECKS = {'exact_show': ('show_published', 'link_live'), 'today': ('today_live', 'no_show_claim')}
WHOLE_MATCH_CHECK = 'whole_match_four_of_six'


def _size(value, path, out):
    if not isinstance(value, dict) or set(value) != {'width', 'height'}:
        out.append(f'{path}: must be exactly {{width, height}}')
        return
    for key in ('width', 'height'):
        if type(value[key]) is not int or value[key] < 1:
            out.append(f'{path}.{key}: must be a whole number of pixels')


def _names(value, path, out, allowed=None):
    if not isinstance(value, list) or not value:
        out.append(f'{path}: must be a non-empty list')
        return
    for item in value:
        if not isinstance(item, str) or not NAME.match(item):
            out.append(f'{path}: {item!r} is not a lower_snake name')
        elif allowed is not None and item not in allowed:
            out.append(f'{path}: {item} is not a registered step ({", ".join(allowed)})')
    if len(set(map(str, value))) != len(value):
        out.append(f'{path}: names one entry twice')


def recipe_errors(data, format_id):
    """Every reason a recipe file is refused. Empty means it is registered."""
    path = f'formats/{format_id}/recipe.json'
    if not isinstance(data, dict):
        return [f'{path}: must be an object']
    out = [f'{path}.{key}: is required' for key in RECIPE if key not in data]
    out += [f'{path}.{key}: unknown field' for key in data if key not in RECIPE]
    if data.get('format_id') != format_id:
        out.append(f'{path}.format_id: must be {format_id}')
    if not isinstance(data.get('title'), str) or not data.get('title', '').strip():
        out.append(f'{path}.title: must be a non-empty string')
    if data.get('creative_system_format') is not None and not isinstance(data.get('creative_system_format'), str):
        out.append(f'{path}.creative_system_format: must be a string or null')
    least = data.get('published_pundits_min')
    if type(least) is not int or not 0 <= least <= 6:
        out.append(f'{path}.published_pundits_min: must be a whole number from 0 to 6')
    links = data.get('links_to')
    if not isinstance(links, str) or links not in LINKS:
        out.append(f'{path}.links_to: must be exact_show or today')
    if not isinstance(data.get('whole_match_claims_allowed'), bool):
        out.append(f'{path}.whole_match_claims_allowed: must be true or false')
    _size(data.get('master'), f'{path}.master', out)
    cuts = data.get('cuts')
    if not isinstance(cuts, dict) or not cuts:
        out.append(f'{path}.cuts: must name at least one channel')
    else:
        for channel, cut in cuts.items():
            where = f'{path}.cuts.{channel}'
            if channel not in spec.CHANNELS:
                out.append(f'{where}: not one of {", ".join(spec.CHANNELS)}')
            if not isinstance(cut, dict) or set(cut) != {'width', 'height', 'max_seconds'}:
                out.append(f'{where}: must be exactly {{width, height, max_seconds}}')
                continue
            _size({'width': cut['width'], 'height': cut['height']}, where, out)
            seconds = cut['max_seconds']
            if seconds is not None and (type(seconds) is not int or seconds < 1):
                out.append(f'{where}.max_seconds: must be a whole number of seconds or null')
    _names(data.get('slots'), f'{path}.slots', out)
    _names(data.get('render_steps'), f'{path}.render_steps', out, RENDER_STEPS)
    checks = data.get('prelive_checks')
    _names(checks, f'{path}.prelive_checks', out)
    checks = checks if isinstance(checks, list) else []
    if links == 'today' and format_id != 'match_ad':
        out.append(f'{path}.links_to: only match_ad may link to Today (ruling 11)')
    for check in (REQUIRED_CHECKS.get(links, ()) if isinstance(links, str) else ()):
        if check not in checks:
            out.append(f'{path}.prelive_checks: a format linking to {links} must run {check}')
    if data.get('whole_match_claims_allowed') is True and WHOLE_MATCH_CHECK not in checks:
        out.append(f'{path}.prelive_checks: whole-match claims need {WHOLE_MATCH_CHECK} (the 4-of-6 rule)')
    if links == 'exact_show' and type(least) is int and least < 1:
        out.append(f'{path}.published_pundits_min: a format linking to an exact show needs at least 1')
    if data.get('cost_class') not in COST_CLASSES:
        out.append(f'{path}.cost_class: must be one of {", ".join(COST_CLASSES)}')
    return out


def load_registry(directory=None):
    """{format_id: recipe} for every format in spec.FORMATS that has a recipe file.
    A recipe file that is present but malformed is refused, never skipped."""
    directory = Path(directory) if directory is not None else FORMATS_DIR
    registry = {}
    for format_id in spec.FORMATS:
        path = directory / format_id / 'recipe.json'
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except ValueError as error:
            raise ValueError(f'formats/{format_id}/recipe.json is not valid JSON ({error})')
        errors = recipe_errors(data, format_id)
        if errors:
            raise ValueError('; '.join(errors))
        registry[format_id] = data
    return registry


def lock_of(format_id, directory=None):
    """The public lock for a format: the SHA-256 of its committed recipe and the renderer
    version that makes it, so proof verdicts count under a pinned lock and any change to
    either starts a new streak. A format built from the private creative release (the
    match ad) is pinned to that release's own lock instead, which lives in local/."""
    from .assets import RENDERER_VERSION
    return reporting.canonical_sha256({'recipe': recipe(format_id, directory), 'renderer_version': RENDERER_VERSION})


def registered(format_id, directory=None):
    return format_id in load_registry(directory)


def recipe(format_id, directory=None):
    registry = load_registry(directory)
    if format_id not in registry:
        raise ValueError(f'{format_id!r} has no registered recipe in formats/')
    return registry[format_id]


# ---------------------------------------------------------------------------
# Readiness (ruling 7): three post it verdicts in a row, on three different
# matches, each with its pre-live checks passed and its unit cost and minutes
# recorded, under one lock version.
# ---------------------------------------------------------------------------
def _decided(verdict):
    from .records import instant
    try:
        return instant(verdict.get('decided_at'))
    except ValueError:
        raise ValueError(f'the verdict on {verdict.get("creative_id")!r} has no RFC 3339 decided_at with its offset')


def _counts(verdict):
    """A clean post it: Krish's yes with no edits, checks passed, cost and minutes measured."""
    return (verdict.get('verdict') == 'post_it' and verdict.get('prelive_checks_passed') is True
            and verdict.get('unit_cost_recorded') is True and verdict.get('unit_minutes_recorded') is True
            and isinstance(verdict.get('fixture_ref'), str) and verdict['fixture_ref'] != '')


def _why_stopped(verdict):
    if verdict.get('verdict') == 'edit':
        return 'an edit'
    if verdict.get('verdict') == 'reject':
        return 'a reject'
    if verdict.get('verdict') != 'post_it':
        return 'a verdict that is not post it, edit or reject'
    if verdict.get('prelive_checks_passed') is not True:
        return 'a failed pre-live check'
    if verdict.get('unit_cost_recorded') is not True or verdict.get('unit_minutes_recorded') is not True:
        return 'a post it without its unit cost and minutes recorded'
    return 'a post it with no fixture_ref'


def readiness(verdicts, format_id, lock_version):
    """{'ready', 'streak', 'distinct_fixtures', 'reason'} for one format under one lock.
    The streak is the newest run of this lock's verdicts: a verdict under another lock
    newer than it ends it, so a lock change restarts the streak and rolling back to an
    old lock does not revive it. Verdicts given at the same instant (one G2 decision)
    count together or not at all, so the order of items in a pack never matters. Only
    the verdict fields are read; views, shares and every other post-live number are ignored."""
    if format_id not in spec.FORMATS:
        raise ValueError(f'{format_id!r} is not one of {", ".join(spec.FORMATS)}')
    if lock_version != 'unlocked' and not (isinstance(lock_version, str) and spec.LOCK.fullmatch(lock_version)):
        raise ValueError('lock_version must be a 64-character lowercase SHA-256 or "unlocked"')
    ours = [v for v in verdicts or [] if isinstance(v, dict) and v.get('format_id') == format_id]
    mine = [v for v in ours if v.get('lock_version') == lock_version]
    groups = {}
    for verdict in ours:
        groups.setdefault(_decided(verdict), []).append(verdict)
    streak, fixtures, stopped, started = 0, set(), None, False
    for moment in sorted(groups, reverse=True):
        group = groups[moment]
        same = [v for v in group if v.get('lock_version') == lock_version]
        if not started and not same:
            continue                      # newer verdicts of another lock, before this lock's newest run
        started = True
        other = next((v for v in group if v.get('lock_version') != lock_version), None)
        failed = next((v for v in same if not _counts(v)), None)
        if other is not None or failed is not None:
            stopped = failed if failed is not None else other
            break
        streak += len(same)
        fixtures.update(v['fixture_ref'] for v in same)
    distinct = len(fixtures)
    if not mine:
        reason = f'no verdicts yet for {format_id} under this lock'
    else:
        why = ('a verdict under another lock' if stopped is not None and stopped.get('lock_version') != lock_version
               else _why_stopped(stopped) if stopped is not None else '')
        reason = (f'{streak} post it in a row on {distinct} match{"es" if distinct != 1 else ""}'
                  + (f', stopped by {why} on {stopped.get("creative_id") or "an unnamed item"}' if stopped else ''))
    if lock_version == 'unlocked':
        return {'ready': False, 'streak': streak, 'distinct_fixtures': distinct,
                'reason': 'not ready: an unlocked format is never ready, because only a pinned lock can be '
                          'repeated; ' + reason}
    ready = distinct >= READY_FIXTURES
    return {'ready': ready, 'streak': streak, 'distinct_fixtures': distinct,
            'reason': ('ready: ' if ready else f'not ready, needs {READY_FIXTURES} matches: ') + reason}


def readiness_gate(verdicts, campaign):
    """{format_id: bool} for spec.compile's gates, under each format's own lock_version."""
    return {item['format_id']: readiness(verdicts, item['format_id'], item['lock_version'])['ready']
            for item in campaign.get('formats') or []}


# ---------------------------------------------------------------------------
# G2: Krish's decision on one matchday's post ask, as a verdict per item.
# ---------------------------------------------------------------------------
def _items(text, what):
    try:
        data = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError(f'the {what} payload must be JSON of the form {{"items": [...]}}')
    out = {}
    for item in data['items']:
        cid = item.get('creative_id') if isinstance(item, dict) else None
        if not isinstance(cid, str) or not cid:
            raise ValueError(f'every item in the {what} payload needs a creative_id')
        if cid in out:
            raise ValueError(f'the {what} payload names {cid} twice')
        out[cid] = item
    return out


def _without_note(item):
    return reporting.canonical({k: v for k, v in item.items() if k != 'note'})


def _note(item):
    note = item.get('note') if item else None
    return note if isinstance(note, str) and note.strip() else None


BOUND = ('format_id', 'lock_version', 'fixture_ref')   # carried in each sent item, so in what Krish decided


def _row(cid, item, verdict, note):
    row = {'creative_id': cid, 'verdict': verdict, 'note': note}
    row.update({key: item[key] for key in BOUND if key in item})
    return row


def g2_verdicts(sent_payload, decision):
    """[{creative_id, verdict, note, format_id, lock_version, fixture_ref}] in the order
    sent, the last three copied from each sent item. Clear is post it for every item,
    Purge is reject for every item, and Change it first is judged per item by diff:
    removed is reject, changed (ignoring note) is edit, unchanged is post it. An item
    Krish adds was never sent, so it gets no verdict and never fails the others. A note
    counts as his only when it differs from the note the engine sent."""
    sent = _items(sent_payload, 'sent')
    if not isinstance(decision, dict) or decision.get('decision') not in ('approved', 'declined', 'done'):
        raise ValueError('the decision must be approved, declined or done')
    if decision['decision'] == 'declined':
        return [_row(cid, item, 'reject', None) for cid, item in sent.items()]
    if decision.get('amended') is not True:
        return [_row(cid, item, 'post_it', None) for cid, item in sent.items()]
    if 'amended_sha256' in decision:
        expected = reporting.canonical_sha256({'amount_usd': decision.get('amount_usd'),
                                               'exact_payload': decision.get('exact_payload')})
        if decision['amended_sha256'] != expected:
            raise ValueError('amended_sha256 does not match his version; it is not read')
    amended = _items(decision.get('exact_payload'), 'amended')
    out = []
    for cid, item in sent.items():
        theirs = amended.get(cid)
        if theirs is None:
            verdict = 'reject'
        elif _without_note(theirs) != _without_note(item):
            verdict = 'edit'
        else:
            verdict = 'post_it'
        mine = _note(theirs)
        out.append(_row(cid, item, verdict, mine if mine != _note(item) else None))
    return out


def added_items(sent_payload, decision):
    """The creative IDs Krish added while amending, which were never sent."""
    if not isinstance(decision, dict) or decision.get('amended') is not True:
        return []
    return sorted(set(_items(decision.get('exact_payload'), 'amended')) - set(_items(sent_payload, 'sent')))
