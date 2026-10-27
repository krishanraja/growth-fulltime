"""The weekly campaign spec: the one artefact Krish signs (docs/ENGINE-V2.md, section 1).

A spec carries judgment only: the week, its objectives, fixtures, formats, channels,
experiments and the learnings it relies on. validate() is the enforcement and
specs/campaign.schema.json describes the same shape for people and tooling.
compile() refuses a spec its gates do not support, and proposal() builds the G1
plan behind the strategy wall. Nothing here posts, sends, schedules or spends."""
import copy
import datetime as dt
import json
import math
from pathlib import Path
import re

from . import reporting

SPEC_VERSION = '2.0.0'
FORMATS = ('take_clip', 'morning_card', 'row', 'match_ad')
CHANNELS = ('tiktok', 'ig_reels', 'yt_shorts', 'ig_feed', 'threads', 'x', 'facebook', 'whatsapp_channel')
# The growth.py platform name for each channel, and the creative ID platform code.
CHANNEL_PLATFORM = {'tiktok': 'tiktok', 'ig_reels': 'instagram', 'ig_feed': 'instagram', 'yt_shorts': 'youtube',
                    'threads': 'threads', 'x': 'x', 'facebook': 'facebook', 'whatsapp_channel': 'whatsapp_channel'}
CHANNEL_PREFIX = {'tiktok': 'TT', 'ig_reels': 'IG', 'ig_feed': 'IG', 'yt_shorts': 'YT',
                  'threads': 'TH', 'x': 'X', 'facebook': 'FB', 'whatsapp_channel': 'WC'}
MODES = ('proof', 'live')
OBJECTIVE_KEYS = ('share_arrived_new_listeners', 'brand_post_new_listeners', 'marketing_cash_gbp',
                  'attributed_new_completers')
REQUIRED_OBJECTIVES = ('share_arrived_new_listeners', 'marketing_cash_gbp')   # plan section 1
ROLES = ('push', 'derived')
ARM_UNITS = ('matchweek', 'match')
TIMEZONE = 'Europe/London'
# The key Control Center knows today; the new keys follow once it registers them.
PROPOSAL_OBJECTIVE = 'attributed_new_completers'
MAX_PAYLOAD = 8000
MAX_WINDOW_DAYS = 7

RUN_ID = re.compile(r'^fulltime:(\d{4})-W(\d{2})$')
LOCK = re.compile(r'^[0-9a-f]{64}$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RULE_WORDS = re.compile(r'do_not|avoid|never', re.I)

TOP = ('spec_version', 'run_id', 'window', 'mode', 'objectives', 'fixtures', 'formats', 'channels',
       'experiments', 'learnings_applied')
WINDOW = ('start', 'end', 'tz')
OBJECTIVE = ('key', 'target')
FIXTURE = ('fixture_ref', 'kickoff', 'home', 'away', 'rivalry', 'rank')
FORMAT = ('format_id', 'lock_version', 'max_per_matchday', 'channels', 'pundits_allowed')
CHANNEL = ('channel', 'role', 'identity_ref', 'cap_per_day')
EXPERIMENT = ('experiment_id', 'arm_unit', 'metric', 'min_matchweeks', 'stop_rule')


def pundit_ids():
    """The six AI Pundit ids, read from growth.py when asked (growth.py imports engine)."""
    import growth
    return tuple(growth.PUNDITS)


def load(path):
    """A spec file as JSON, refusing non-finite numbers."""
    def refuse(constant):
        raise ValueError(f'{path}: {constant} is not a number a spec can carry')
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=refuse)


def _is_int(value):
    return type(value) is int


def _is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _text(value):
    return isinstance(value, str) and value.strip() != ''


def _date(value):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _datetime_with_offset(value):
    from .records import instant
    try:
        return instant(value).tzinfo is not None
    except ValueError:
        return False


def _shape(value, keys, path, out):
    """True when value is an object; every key named, none missing, none unknown."""
    if not isinstance(value, dict):
        out.append(f'{path}: must be an object')
        return False
    for key in keys:
        if key not in value:
            out.append(f'{path}.{key}: is required')
    for key in value:
        if key not in keys:
            out.append(f'{path}.{key}: unknown field')
    return True


def _rule_keys(value, path, out):
    """Rules belong in invariants/registry.json, never in the signed spec."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if RULE_WORDS.search(str(key)):
                out.append(f'{path}.{key}: a rule is not judgment; put it in invariants/registry.json, not the spec')
            _rule_keys(nested, f'{path}.{key}', out)
    elif isinstance(value, list):
        for i, nested in enumerate(value):
            _rule_keys(nested, f'{path}[{i}]', out)


def _subset(value, allowed, path, out, what):
    if not isinstance(value, list) or not value:
        out.append(f'{path}: must be a non-empty list of {what}')
        return []
    for item in value:
        if item not in allowed:
            out.append(f'{path}: {item!r} is not one of {what} ({", ".join(allowed)})')
    if len(set(map(str, value))) != len(value):
        out.append(f'{path}: names one entry twice')
    return [v for v in value if v in allowed]


def _list(spec, key, out):
    value = spec.get(key)
    if not isinstance(value, list):
        out.append(f'spec.{key}: must be a list')
        return []
    return value


def _window(spec, out):
    window = spec.get('window')
    if not _shape(window, WINDOW, 'spec.window', out):
        return
    start, end = _date(window.get('start')), _date(window.get('end'))
    if start is None:
        out.append('spec.window.start: must be an ISO date (YYYY-MM-DD)')
    if end is None:
        out.append('spec.window.end: must be an ISO date (YYYY-MM-DD)')
    if window.get('tz') != TIMEZONE:
        out.append(f'spec.window.tz: must be {TIMEZONE}')
    if start and end:
        if start >= end:
            out.append('spec.window: start must be before end')
        elif (end - start).days > MAX_WINDOW_DAYS:
            out.append(f'spec.window: covers more than {MAX_WINDOW_DAYS} days')
    match = RUN_ID.fullmatch(spec.get('run_id') or '') if isinstance(spec.get('run_id'), str) else None
    if start and end and match:
        try:
            monday = dt.date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            return
        if (start, end) != (monday, monday + dt.timedelta(days=6)):
            out.append(f'spec.window: one matchweek, Monday to Sunday: {monday} to {monday + dt.timedelta(days=6)}')


def _objectives(spec, out):
    seen = set()
    for i, item in enumerate(_list(spec, 'objectives', out)):
        path = f'spec.objectives[{i}]'
        if not _shape(item, OBJECTIVE, path, out):
            continue
        key, target = item.get('key'), item.get('target')
        if key not in OBJECTIVE_KEYS:
            out.append(f'{path}.key: {key!r} is not one of {", ".join(OBJECTIVE_KEYS)}')
        elif key in seen:
            out.append(f'{path}.key: {key} is named twice')
        else:
            seen.add(key)
        if not _is_number(target) or target < 0:
            out.append(f'{path}.target: must be a number of 0 or more')
        elif key == 'marketing_cash_gbp' and target != 0:
            out.append(f'{path}.target: marketing cash must be exactly 0')
    for key in REQUIRED_OBJECTIVES:
        if key not in seen:
            out.append(f'spec.objectives: must include {key}')


def _fixtures(spec, out):
    ranks, refs = set(), set()
    window = spec.get('window') if isinstance(spec.get('window'), dict) else {}
    first, last = _date(window.get('start')), _date(window.get('end'))
    for i, item in enumerate(_list(spec, 'fixtures', out)):
        path = f'spec.fixtures[{i}]'
        if not _shape(item, FIXTURE, path, out):
            continue
        ref = item.get('fixture_ref')
        if not _text(ref):
            out.append(f'{path}.fixture_ref: must be a non-empty string')
        elif ref in refs:
            out.append(f'{path}.fixture_ref: {ref} is named twice')
        refs.add(ref if isinstance(ref, str) else None)
        if not _datetime_with_offset(item.get('kickoff')):
            out.append(f'{path}.kickoff: must be an ISO date and time with its UTC offset')
        elif first and last:
            from .clock import LONDON
            from .records import instant
            day = instant(item['kickoff']).astimezone(LONDON).date()
            if not first <= day <= last:
                out.append(f'{path}.kickoff: {day} is outside the spec window')
        for side in ('home', 'away'):
            if not _text(item.get(side)):
                out.append(f'{path}.{side}: must be a non-empty string')
        if not isinstance(item.get('rivalry'), bool):
            out.append(f'{path}.rivalry: must be true or false')
        rank = item.get('rank')
        if not _is_int(rank) or rank < 1:
            out.append(f'{path}.rank: must be a whole number of 1 or more')
        elif rank in ranks:
            out.append(f'{path}.rank: {rank} is used twice; ranks are unique')
        ranks.add(rank if _is_int(rank) else None)


def _formats(spec, registry, out):
    named, seen, pundits = set(), set(), pundit_ids()
    for i, item in enumerate(_list(spec, 'formats', out)):
        path = f'spec.formats[{i}]'
        if not _shape(item, FORMAT, path, out):
            continue
        fid = item.get('format_id')
        recipe = None
        if fid not in FORMATS:
            out.append(f'{path}.format_id: {fid!r} is not one of {", ".join(FORMATS)}')
        elif fid in seen:
            out.append(f'{path}.format_id: {fid} is named twice')
        elif fid not in registry:
            out.append(f'{path}.format_id: {fid} has no registered recipe in formats/{fid}/recipe.json')
        else:
            recipe = registry[fid]
        seen.add(fid if isinstance(fid, str) else None)
        lock = item.get('lock_version')
        if lock != 'unlocked' and not (isinstance(lock, str) and LOCK.fullmatch(lock)):
            out.append(f'{path}.lock_version: must be a 64-character lowercase SHA-256 or "unlocked"')
        most = item.get('max_per_matchday')
        if not _is_int(most) or not 1 <= most <= 6:
            out.append(f'{path}.max_per_matchday: must be a whole number from 1 to 6')
        channels = _subset(item.get('channels'), CHANNELS, f'{path}.channels', out, 'channels')
        named.update(channels)
        if recipe:
            for channel in channels:
                if channel not in recipe['cuts']:
                    out.append(f'{path}.channels: the {fid} recipe has no cut for {channel}')
        allowed = _subset(item.get('pundits_allowed'), pundits, f'{path}.pundits_allowed', out, 'AI Pundit ids')
        if recipe and allowed and len(set(allowed)) < recipe['published_pundits_min']:
            out.append(f'{path}.pundits_allowed: {fid} needs at least {recipe["published_pundits_min"]} AI Pundits')
    return named


def _channels(spec, named, out):
    listed = set()
    for i, item in enumerate(_list(spec, 'channels', out)):
        path = f'spec.channels[{i}]'
        if not _shape(item, CHANNEL, path, out):
            continue
        channel = item.get('channel')
        if channel not in CHANNELS:
            out.append(f'{path}.channel: {channel!r} is not one of {", ".join(CHANNELS)}')
        elif channel in listed:
            out.append(f'{path}.channel: {channel} is listed twice')
        listed.add(channel if isinstance(channel, str) else None)
        if item.get('role') not in ROLES:
            out.append(f'{path}.role: must be push or derived')
        if not _text(item.get('identity_ref')):
            out.append(f'{path}.identity_ref: must be a non-empty string')
        cap = item.get('cap_per_day')
        if not _is_int(cap) or not 1 <= cap <= 5:
            out.append(f'{path}.cap_per_day: must be a whole number from 1 to 5')
    for channel in sorted(named - listed):
        out.append(f'spec.channels: {channel} is named by a format but not listed here')


def _experiments(spec, out):
    seen = set()
    for i, item in enumerate(_list(spec, 'experiments', out)):
        path = f'spec.experiments[{i}]'
        if not _shape(item, EXPERIMENT, path, out):
            continue
        eid = item.get('experiment_id')
        if not _text(eid):
            out.append(f'{path}.experiment_id: must be a non-empty string')
        elif eid in seen:
            out.append(f'{path}.experiment_id: {eid} is named twice')
        seen.add(eid if isinstance(eid, str) else None)
        if item.get('arm_unit') not in ARM_UNITS:
            out.append(f'{path}.arm_unit: must be matchweek or match, never a sharer')
        if item.get('metric') not in OBJECTIVE_KEYS:
            out.append(f'{path}.metric: must be one of {", ".join(OBJECTIVE_KEYS)}')
        weeks = item.get('min_matchweeks')
        if not _is_int(weeks) or weeks < 2:
            out.append(f'{path}.min_matchweeks: must be a whole number of 2 or more')
        if not _text(item.get('stop_rule')):
            out.append(f'{path}.stop_rule: must be a non-empty string')


def validate(spec, registry=None):
    """Every reason the spec is refused, in plain words. Empty means valid."""
    out = []
    if not _shape(spec, TOP, 'spec', out):
        return out
    _rule_keys(spec, 'spec', out)
    if spec.get('spec_version') != SPEC_VERSION:
        out.append(f'spec.spec_version: must be {SPEC_VERSION}')
    run_id = spec.get('run_id')
    match = RUN_ID.fullmatch(run_id) if isinstance(run_id, str) else None
    if not match:
        out.append('spec.run_id: must look like fulltime:YYYY-Www')
    else:
        try:
            dt.date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            out.append(f'spec.run_id: {run_id} is not a real ISO week')
    _window(spec, out)
    if spec.get('mode') not in MODES:
        out.append('spec.mode: must be proof or live')
    _objectives(spec, out)
    _fixtures(spec, out)
    if registry is None:
        from . import formats
        try:
            registry = formats.load_registry()
        except ValueError as error:
            out.append(f'formats: {error}')
            registry = {}
    named = _formats(spec, registry, out)
    _channels(spec, named, out)
    _experiments(spec, out)
    learnings = _list(spec, 'learnings_applied', out)
    for i, item in enumerate(learnings):
        if not _text(item):
            out.append(f'spec.learnings_applied[{i}]: must be a non-empty string')
    if len(set(map(str, learnings))) != len(learnings):
        out.append('spec.learnings_applied: names one learning twice')
    return out


def digest(spec):
    """The SHA-256 Krish's Clear binds: canonical JSON, as Control Center computes it."""
    return reporting.canonical_sha256(spec)


def gates(campaign, verdicts=(), state=None, identities=None):
    """The gates a live week needs, computed from evidence and never written by hand:
    readiness from Krish's verdict ledger under each format's own lock, ORGANIC and D7
    from the synced state, and each channel's brand identity from the verified registry."""
    from . import formats, policy
    state = state if isinstance(state, dict) else {}
    rulings = state.get('rulings') if isinstance(state.get('rulings'), dict) else {}
    found = [x for x in (identities or {}).values()] if isinstance(identities, dict) else []
    return {'readiness': formats.readiness_gate(list(verdicts or []), campaign),
            'organic_in_force': policy.organic_in_force(state),
            'd7_in_force': (rulings.get('D7') or {}).get('in_force') is True,
            'identity_verified': {item['channel']: any(policy.identity_verified(x, CHANNEL_PLATFORM[item['channel']])
                                                       for x in found) for item in campaign['channels']}}


def compile(spec, verdicts=(), state=None, identities=None, registry=None):
    """The run the spec allows, or ValueError with every reason it is refused.
    Proof mode posts nothing, so only live mode reads the gates, and it computes them
    itself (gates()): a ready format needs three clean verdicts on three matches in
    the ledger, so no session can declare it."""
    errors = validate(spec, registry)
    if not errors and spec['mode'] == 'live':
        found = gates(spec, verdicts, state, identities)
        for item in spec['formats']:
            if found['readiness'].get(item['format_id']) is not True:
                errors.append(f'live mode: {item["format_id"]} is not ready (three post it verdicts on three matches)')
        if found['organic_in_force'] is not True:
            errors.append('live mode: the ORGANIC exception is not in force')
        if found['d7_in_force'] is not True:
            errors.append('live mode: D7, the analytics consent item, is not in force')
        for item in spec['channels']:
            if found['identity_verified'].get(item['channel']) is not True:
                errors.append(f'live mode: the Full Time identity on {item["channel"]} is not verified')
    if errors:
        raise ValueError('; '.join(errors))
    return {'run_id': spec['run_id'], 'mode': spec['mode'], 'formats': copy.deepcopy(spec['formats']),
            'channels': copy.deepcopy(spec['channels']), 'payload_sha256': digest(spec)}


def proposal(spec, expires_at, registry=None):
    """Gate G1: the spec as a plan behind the strategy wall, with the spec itself as
    exact_payload so Krish can amend it. His Clear binds payload_sha256 = digest(spec)."""
    errors = validate(spec, registry)
    if errors:
        raise ValueError('the spec is not valid: ' + '; '.join(errors))
    if not isinstance(expires_at, str) or not _datetime_with_offset(expires_at):
        raise ValueError('expires_at must be an ISO date and time with its UTC offset')
    exact = reporting.canonical(spec)
    if len(exact) > MAX_PAYLOAD:
        raise ValueError(f'the spec is {len(exact)} characters; Control Center takes at most {MAX_PAYLOAD}')
    week = spec['run_id'].split(':', 1)[1]
    fixtures = len(spec['fixtures'])
    why = (f'The {spec["mode"]} spec for matchweek {week}: {len(spec["formats"])} formats, '
           f'{len(spec["channels"])} channels, {fixtures} fixture{"s" if fixtures != 1 else ""}. '
           'Clear signs exactly this spec. Nothing posts from it: each matchday comes back as its own post ask.')
    plan = reporting._proposal(
        f'fulltime-spec-{week}', f'Weekly campaign spec, {week} ({spec["mode"]})', why, 'prepared', 'strategy',
        spec, 'campaign_week_closed', spec['run_id'], objective_key=PROPOSAL_OBJECTIVE, exact_payload=exact,
        evidence=[{'label': 'Campaign spec schema', 'url': reporting.REPO_URL + '/blob/main/specs/campaign.schema.json'}],
        expires_at=expires_at)
    return {**plan, 'stage': 'plan', 'parent_proposal_id': None}
