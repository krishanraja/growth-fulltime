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
    if links not in LINKS:
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
    for check in REQUIRED_CHECKS.get(links, ()):
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
    value = verdict.get('decided_at')
    try:
        moment = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f'the verdict on {verdict.get("creative_id")!r} has no ISO decided_at')
    if moment.tzinfo is None:
        raise ValueError(f'the verdict on {verdict.get("creative_id")!r} has no time zone on decided_at')
    return moment


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
    Only this format and lock count, so a lock change restarts the streak. Only the
    verdict fields are read; views, shares and every other post-live number are ignored."""
    if format_id not in spec.FORMATS:
        raise ValueError(f'{format_id!r} is not one of {", ".join(spec.FORMATS)}')
    if lock_version != 'unlocked' and not (isinstance(lock_version, str) and spec.LOCK.match(lock_version)):
        raise ValueError('lock_version must be a 64-character lowercase SHA-256 or "unlocked"')
    mine = [(i, v) for i, v in enumerate(verdicts or [])
            if isinstance(v, dict) and v.get('format_id') == format_id and v.get('lock_version') == lock_version]
    newest_first = sorted(mine, key=lambda pair: (_decided(pair[1]), pair[0]), reverse=True)
    streak, fixtures, stopped = 0, set(), None
    for _, verdict in newest_first:
        if not _counts(verdict):
            stopped = verdict
            break
        streak += 1
        fixtures.add(verdict['fixture_ref'])
    distinct = len(fixtures)
    if not mine:
        reason = f'no verdicts yet for {format_id} under this lock'
    else:
        reason = (f'{streak} post it in a row on {distinct} match{"es" if distinct != 1 else ""}'
                  + (f', stopped by {_why_stopped(stopped)} on {stopped.get("creative_id") or "an unnamed item"}'
                     if stopped else ''))
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


def g2_verdicts(sent_payload, decision):
    """[{creative_id, verdict, note}] in the order sent. Clear is post it for every
    item, Purge is reject for every item, and Change it first is judged per item by
    diff: removed is reject, changed (ignoring note) is edit, unchanged is post it."""
    sent = _items(sent_payload, 'sent')
    if not isinstance(decision, dict) or decision.get('decision') not in ('approved', 'declined', 'done'):
        raise ValueError('the decision must be approved, declined or done')
    if decision['decision'] == 'declined':
        return [{'creative_id': cid, 'verdict': 'reject', 'note': None} for cid in sent]
    if decision.get('amended') is not True:
        return [{'creative_id': cid, 'verdict': 'post_it', 'note': None} for cid in sent]
    if 'amended_sha256' in decision:
        expected = reporting.canonical_sha256({'amount_usd': decision.get('amount_usd'),
                                               'exact_payload': decision.get('exact_payload')})
        if decision['amended_sha256'] != expected:
            raise ValueError('amended_sha256 does not match his version; it is not read')
    amended = _items(decision.get('exact_payload'), 'amended')
    added = sorted(set(amended) - set(sent))
    if added:
        raise ValueError('the amended payload adds items that were never sent: ' + ', '.join(added))
    out = []
    for cid, item in sent.items():
        theirs = amended.get(cid)
        if theirs is None:
            verdict = 'reject'
        elif _without_note(theirs) != _without_note(item):
            verdict = 'edit'
        else:
            verdict = 'post_it'
        out.append({'creative_id': cid, 'verdict': verdict, 'note': _note(theirs)})
    return out
