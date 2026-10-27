"""The matchday pack: gate G2's payload (docs/ENGINE-V2.md, sections 3 to 5).

One pack per matchday lists every item Krish is asked to post by hand: its
creative ID, channel, caption, tracked link, media hashes and the independent
review that says why it clears the creative bar. check() is the pack's own rules
plus growth.py's copy rules, build() refuses a pack that breaks any of them, and
proposal() turns a checked pack into one post ask for Control Center.

Rulings it applies (Krish, 27 October 2026):
- 1, the per-take gate: a take links to an exact AI Pundit show that is
  published on the rail; the 4-of-6 rule applies only to a whole-match claim.
- 3, handcrafted: Krish posts each item himself in Buffer. The pack is the
  exact artifact; nothing here posts, sends, spends or writes to a platform.
- 11, a match ad links to Today only while Today carries a published AI Pundit
  show, and its words never claim a show exists for its match.

The channel, release, identity and consent gates belong to the spec's mode check
(engine/spec.py), so a pack can go to G2 in proof mode before they open.
"""
import copy
import datetime as dt
import re
from urllib.parse import parse_qsl, urlsplit

from . import policy

PACK_FIELDS = ('run_id', 'matchday', 'items')
ITEM_FIELDS = ('creative_id', 'master_id', 'format_id', 'channel', 'channel_ref', 'caption', 'hashtags',
               'link', 'drop_id', 'pundit', 'whole_match', 'media', 'ai_label', 'scheduled_suggestion',
               'review', 'note')
REQUIRED = ('creative_id', 'master_id', 'format_id', 'channel', 'channel_ref', 'caption', 'hashtags',
            'link', 'media', 'ai_label', 'scheduled_suggestion', 'review')
MEDIA_FIELDS = ('kind', 'sha256', 'bytes', 'review_url')
MEDIA_KINDS = ('video', 'image', 'audio')
AI_LABEL = ('platform_label_set', 'visible_ai_pundit')
REVIEW_FIELDS = ('rubric_total', 'ethics', 'action', 'alternatives', 'doctrine_ref', 'why_wins')
RUBRIC_MAX, RUBRIC_BAR = 48, 38
MAX_PAYLOAD = 8000          # the protocol's exact_payload limit
MAX_REVIEW_LINKS = 12       # the protocol's evidence limit
HOSTS = ('fulltime.fm', 'www.fulltime.fm')
SHA = re.compile(r'^[0-9a-f]{64}$')
RUN_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,119}$')
MASTER_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,79}$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RAW_ID = re.compile(r'^(?:[0-9a-f]{24}|\d{6,})$')    # a Buffer or platform ID, never an allowlist ref
TAG = re.compile(r'^#\w+$')
LINK_IN_TEXT = re.compile(r'https?://|\bwww\.|\bfulltime\.fm\b', re.I)
SHOW_WORDS = re.compile(r'\b(?:show|edition|episode)s?\b', re.I)


def _growth():
    import growth
    return growth


def _datetime(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace('Z', '+00:00')).tzinfo is not None
    except ValueError:
        return False


def _https(url):
    if not isinstance(url, str) or re.search(r'\s', url):
        return False
    parts = urlsplit(url)
    return parts.scheme == 'https' and bool(parts.hostname) and not parts.username and not parts.password


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def review_urls(pack):
    """The distinct review links in the pack, in order: they become the proposal's evidence."""
    out = []
    items = pack.get('items') if isinstance(pack, dict) else None
    for item in items if isinstance(items, list) else []:
        media = item.get('media') if isinstance(item, dict) else None
        for entry in media if isinstance(media, list) else []:
            url = entry.get('review_url') if isinstance(entry, dict) else None
            if isinstance(url, str) and url not in out:
                out.append(url)
    return out


def payload_length(text):
    """Length as JavaScript counts it (UTF-16 code units), never less than Python's."""
    return len(text.encode('utf-16-le')) // 2


def size_errors(pack):
    from .reporting import canonical
    try:
        exact = canonical(pack)
    except ValueError as error:
        return [f'the pack is not plain JSON ({error})']
    out = []
    if payload_length(exact) > MAX_PAYLOAD:
        out.append(f'the pack is {payload_length(exact)} characters as exact_payload; '
                   f'Control Center takes at most {MAX_PAYLOAD}: split the matchday or trim it')
    links = len(review_urls(pack))
    if links > MAX_REVIEW_LINKS:
        out.append(f'the pack has {links} distinct review links; a proposal carries at most {MAX_REVIEW_LINKS}')
    return out


def _scorelines(rail):
    """Only what growth's scoreline check reads, from well-formed rail rows."""
    if not isinstance(rail, list):
        return None
    return [{'drop': m.get('drop'), 'home': m['home'], 'away': m['away'], 'score': list(m['score']),
             'pundits': [], 'fill': 0}
            for m in rail if isinstance(m, dict) and isinstance(m.get('home'), str)
            and isinstance(m.get('away'), str) and isinstance(m.get('score'), list) and len(m['score']) == 2]


def _copy_errors(item, state):
    """growth.py's copy rules on the words that go out: the caption and its hashtags.
    The gates are held here because they are the spec's mode check, and every
    ruling counts as in force so only copy is judged; the rail still checks
    every scoreline against the match it names."""
    growth = _growth()
    from .spec import CHANNEL_PLATFORM
    platform = CHANNEL_PLATFORM[item['channel']]
    draft = {'platform': platform, 'account_scope': 'brand', 'holds': ['CHANNEL', 'RELEASE', 'RAIL', 'CONSENT'],
             'text': item['caption'] + '\n\n' + ' '.join(item['hashtags'])}
    copy_state = {'rail': _scorelines(state.get('rail') if isinstance(state, dict) else None),
                  'rulings': {rid: {'in_force': True} for rid in growth.load_rulings()}}
    # A channel growth.py does not list yet still gets every copy rule.
    unlisted = f'platform "{platform}" is not one of {", ".join(growth.PLATFORMS)}'
    return [e for e in growth.problems(draft, copy_state) if e != unlisted]


def _media_errors(media):
    if not isinstance(media, list) or not media:
        return ['media must list at least one rendered file with its SHA-256']
    out = []
    for j, entry in enumerate(media, 1):
        where = f'media {j}'
        if not isinstance(entry, dict) or set(entry) != set(MEDIA_FIELDS):
            out.append(f'{where} must have exactly ' + ', '.join(MEDIA_FIELDS))
            continue
        if entry['kind'] not in MEDIA_KINDS:
            out.append(f'{where} kind must be one of ' + ', '.join(MEDIA_KINDS))
        if not isinstance(entry['sha256'], str) or not SHA.fullmatch(entry['sha256']):
            out.append(f'{where} sha256 must be 64 lowercase hex characters')
        if type(entry['bytes']) is not int or entry['bytes'] <= 0:
            out.append(f'{where} bytes must be a whole number above 0')
        if not _https(entry['review_url']):
            out.append(f'{where} review_url must be an https link')
    return out


def _review_errors(review):
    if not isinstance(review, dict):
        return ['review must be the independent review: ' + ', '.join(REVIEW_FIELDS)]
    out = []
    if set(review) != set(REVIEW_FIELDS):
        out.append('review must have exactly ' + ', '.join(REVIEW_FIELDS))
    total = review.get('rubric_total')
    if type(total) is not int or not 0 <= total <= RUBRIC_MAX:
        out.append(f'review rubric_total must be a whole number from 0 to {RUBRIC_MAX}')
    elif total < RUBRIC_BAR:
        out.append(f'the review scored {total} of {RUBRIC_MAX}; the bar is {RUBRIC_BAR}, so it is held, not proposed')
    for key in ('ethics', 'action'):
        if type(review.get(key)) is not int or review.get(key) != 4:
            out.append(f'review {key} must score 4')
    alternatives = review.get('alternatives')
    if (not isinstance(alternatives, list) or len(alternatives) < 2
            or not all(_text(a) for a in alternatives) or len(set(alternatives)) != len(alternatives)):
        out.append('review alternatives must name at least two different alternatives that were made')
    for key in ('doctrine_ref', 'why_wins'):
        if not _text(review.get(key)):
            out.append(f'review {key} must be non-empty text')
    return out


def _channel_ref_errors(ref, channel, allowlist):
    entries = allowlist.get('channels') if isinstance(allowlist, dict) else None
    if not _text(ref):
        return ['channel_ref must name an entry in the Full Time Buffer allowlist']
    if RAW_ID.fullmatch(ref):
        return ['channel_ref is a raw platform ID: name its allowlist entry instead']
    if not isinstance(entries, dict) or ref not in entries:
        return [f'channel_ref {ref!r} is not in the Full Time Buffer allowlist']
    entry = entries[ref]
    if not isinstance(entry, dict) or entry.get('account_scope') != 'brand':
        return [f'channel_ref {ref!r} is not a Full Time brand channel']
    if channel and entry.get('channel') != channel:
        return [f'channel_ref {ref!r} is the {entry.get("channel")} channel, not {channel}']
    return []


def _show_errors(item, recipe, state, link_query):
    """Ruling 1: an exact published show, and 4 of 6 only for a whole-match claim."""
    growth = _growth()
    drop, pundit = item.get('drop_id'), item.get('pundit')
    if not _text(drop) or not _text(pundit):
        return ['a link to an exact show needs drop_id and pundit (ruling 1)']
    out = []
    if pundit not in growth.PUNDITS:
        out.append(f'pundit {pundit!r} is not one of ' + ', '.join(growth.PUNDITS))
    if link_query is not None and (link_query.get('drop') != drop or link_query.get('pundit') != pundit):
        out.append(f'the link must open drop {drop} with {growth.PUNDITS.get(pundit, pundit)}: '
                   f'{growth.SITE}/?drop={drop}&pundit={pundit}, tracked')
    rail = state.get('rail') if isinstance(state, dict) else None
    if not isinstance(rail, list):
        return out + ['the rail was not read, so no show is confirmed published (run python3 growth.py sync)']
    match = next((m for m in rail if isinstance(m, dict) and m.get('drop') == drop), None)
    if match is None:
        return out + [f'drop {drop} has no published show on the rail (ruling 1)']
    listed = match.get('pundits') if isinstance(match.get('pundits'), list) else []
    pundits = [p for p in listed if isinstance(p, str) and p in growth.PUNDITS]
    name = f'{match.get("home")} v {match.get("away")}'
    if pundit not in pundits:
        out.append(f'{growth.PUNDITS.get(pundit, pundit)} has no published show for {name} (ruling 1)')
    fill = match['fill'] if type(match.get('fill')) is int else len(set(pundits))
    least = recipe.get('published_pundits_min')
    if type(least) is int and fill < least:
        out.append(f'{item.get("format_id")} needs {least} published AI Pundits on the match; {name} has {fill}')
    if item.get('whole_match') is True:
        if recipe.get('whole_match_claims_allowed') is not True:
            out.append(f'{item.get("format_id")} may not claim a whole match')
        if fill < growth.RAIL_MIN:
            out.append(f'a whole-match claim needs {growth.RAIL_MIN} of 6 AI Pundits; {name} has {fill}')
    return out


def _today_errors(item, today_live, link):
    """Ruling 11: a match ad links to Today while it carries a published show, and never claims one."""
    growth = _growth()
    out = []
    if item.get('drop_id') is not None or item.get('pundit') is not None:
        out.append('a link to Today names no drop_id or pundit (ruling 11)')
    if item.get('whole_match') is True:
        out.append('a link to Today makes no whole-match claim')
    cid = item.get('creative_id')
    if (isinstance(link, str) and isinstance(cid, str) and growth.CREATIVE_ID.fullmatch(cid)
            and link != growth.tracked(growth.SITE + '/', cid)):
        out.append(f'a match ad links to the Today home page: {growth.tracked(growth.SITE + "/", cid)}')
    if today_live is not True:
        out.append('Today has no published AI Pundit show right now, so the match ad is held (ruling 11)')
    words = ' '.join([item['caption'] if isinstance(item.get('caption'), str) else ''] +
                     [t for t in item.get('hashtags') or [] if isinstance(t, str)])
    found = SHOW_WORDS.search(words)
    if found:
        out.append(f'a match ad never claims a show exists for its match: it says "{found.group(0)}" (ruling 11)')
    return out


def _item_errors(item, state, allowlist, today_live):
    growth = _growth()
    from . import formats, spec
    out = []
    unknown = sorted(set(item) - set(ITEM_FIELDS))
    if unknown:
        out.append('unknown fields: ' + ', '.join(unknown))
    missing = [k for k in REQUIRED if k not in item]
    if missing:
        out.append('missing fields: ' + ', '.join(missing))
    channel = item.get('channel')
    if channel not in spec.CHANNELS:
        out.append(f'channel {channel!r} is not one of ' + ', '.join(spec.CHANNELS))
        channel = None
    cid = item.get('creative_id')
    matched = growth.CREATIVE_ID.fullmatch(cid) if isinstance(cid, str) else None
    if not matched:
        out.append(f'creative_id {cid!r} does not follow PLAYBOOK.md, "Creative ids"')
    elif channel and matched.group(1) != spec.CHANNEL_PREFIX[channel]:
        out.append(f'creative_id starts {matched.group(1)}, but {channel} takes {spec.CHANNEL_PREFIX[channel]}')
    if not isinstance(item.get('master_id'), str) or not MASTER_ID.fullmatch(item['master_id']):
        out.append('master_id must name the master this cut comes from')
    recipe = None
    try:
        recipe = formats.recipe(item.get('format_id'))
    except (ValueError, KeyError, TypeError) as error:
        out.append(f'format_id {item.get("format_id")!r} is not a registered format ({error})')
    if recipe and channel and isinstance(recipe.get('cuts'), dict) and channel not in recipe['cuts']:
        out.append(f'{item.get("format_id")} has no cut for {channel}')
    out += _channel_ref_errors(item.get('channel_ref'), channel, allowlist)
    caption, tags = item.get('caption'), item.get('hashtags')
    tags_ok = isinstance(tags, list) and all(isinstance(t, str) for t in tags)
    if not tags_ok or not 2 <= len(tags) <= 5:
        out.append('hashtags must list 2 to 5 entries')
    if tags_ok and not all(TAG.fullmatch(t) for t in tags):
        out.append('each hashtag is one word starting "#"')
    if tags_ok and len({t.lower() for t in tags}) != len(tags):
        out.append('a hashtag is listed twice')
    if not _text(caption):
        out.append('caption must be non-empty text')
    else:
        if 'AI Pundit' not in caption:
            out.append('the caption must say "AI Pundit", exactly, so the AI is visible')
        if LINK_IN_TEXT.search(caption):
            out.append('the caption carries no link: the link field holds the one tracked link')
        if growth.HASHTAG.search(caption):
            out.append('hashtags go in the hashtags list, not the caption')
        if channel and tags_ok:
            out += _copy_errors(item, state)
    link, query = item.get('link'), None
    parts = urlsplit(link) if isinstance(link, str) else None
    if (parts is None or parts.scheme != 'https' or parts.hostname not in HOSTS
            or parts.username or parts.password or parts.port):
        out.append('link must be an https fulltime.fm link')
    else:
        query = dict(parse_qsl(parts.query)) if parts.path in ('', '/') else {}
        if matched and link != growth.tracked(link, cid):
            out.append(f'the link is not tracked as {cid}: use {growth.tracked(link, cid)}')
    if 'whole_match' in item and not isinstance(item['whole_match'], bool):
        out.append('whole_match must be true or false')
    if recipe:
        target = recipe.get('links_to')
        if target == 'exact_show':
            out += _show_errors(item, recipe, state, query)
        elif target == 'today':
            out += _today_errors(item, today_live, link)
        else:
            out.append(f'{item.get("format_id")} links to {target!r}, which the pack does not know')
    out += _media_errors(item.get('media'))
    label = item.get('ai_label')
    if not isinstance(label, dict) or set(label) != set(AI_LABEL) or any(label[k] is not True for k in AI_LABEL):
        out.append('ai_label must set platform_label_set and visible_ai_pundit, both true')
    if not _datetime(item.get('scheduled_suggestion')):
        out.append('scheduled_suggestion must be an ISO date and time with its UTC offset')
    out += _review_errors(item.get('review'))
    if 'note' in item and not isinstance(item['note'], str):
        out.append('note must be text')
    return out


def check(pack, state, allowlist, today_live):
    """Every reason this matchday pack cannot go to G2, in plain words. Empty means it can."""
    if not isinstance(pack, dict):
        return ['a matchday pack must be a JSON object']
    out = []
    unknown = sorted(set(pack) - set(PACK_FIELDS))
    if unknown:
        out.append('unknown pack fields: ' + ', '.join(unknown))
    if not isinstance(pack.get('run_id'), str) or not RUN_ID.fullmatch(pack['run_id']):
        out.append('run_id must be a stable run id (letters, digits and : . _ -)')
    matchday = pack.get('matchday')
    try:
        if not isinstance(matchday, str) or not DATE.fullmatch(matchday):
            raise ValueError
        dt.date.fromisoformat(matchday)
    except ValueError:
        out.append('matchday must be a calendar date, YYYY-MM-DD')
    if not isinstance(allowlist, dict) or allowlist.get('product') != 'fulltime':
        out.append('the Buffer allowlist must be scoped to product "fulltime"')
    items = pack.get('items')
    if not isinstance(items, list) or not items or not all(isinstance(x, dict) for x in items):
        return out + ['items must be a non-empty list of pack items']
    ids, masters, assets = set(), set(), set()
    for i, item in enumerate(items, 1):
        cid, channel = item.get('creative_id'), item.get('channel')
        label = f'item {i} ({cid if isinstance(cid, str) else "?"})'
        out += [f'{label}: {e}' for e in _item_errors(item, state, allowlist, today_live)]
        if isinstance(cid, str):
            if cid in ids:
                out.append(f'{label}: creative_id {cid} appears twice in the pack')
            ids.add(cid)
        master = item.get('master_id')
        if isinstance(master, str) and isinstance(channel, str):
            if (master, channel) in masters:
                out.append(f'{label}: master {master} appears twice on {channel}')
            masters.add((master, channel))
        for entry in item.get('media') if isinstance(item.get('media'), list) else []:
            digest = entry.get('sha256') if isinstance(entry, dict) else None
            if isinstance(digest, str) and isinstance(channel, str):
                if (digest, channel) in assets:
                    out.append(f'{label}: the same asset ({digest[:12]}) goes on {channel} twice')
                assets.add((digest, channel))
    return out + size_errors(pack) + policy.sensitive_errors(pack)


def build(items, run_id, matchday, state, allowlist, today_live):
    """The checked pack, with whole_match explicit on every item. Refused with every reason."""
    if not isinstance(items, list):
        raise ValueError('items must be a list of pack items')
    pack = {'run_id': run_id, 'matchday': matchday,
            'items': [{**copy.deepcopy(x), 'whole_match': x.get('whole_match', False)} if isinstance(x, dict)
                      else copy.deepcopy(x) for x in items]}
    errors = check(pack, state, allowlist, today_live)
    if errors:
        raise ValueError('the matchday pack was refused: ' + '; '.join(errors))
    return pack


def proposal(pack, expires_at):
    """Gate G2: one handcrafted post ask whose exact_payload is the whole pack. Clear is
    post it for every item, Purge rejects every item, and Change it first is read per
    item by diff (engine/formats.py, g2_verdicts). It closes on creative_published."""
    from . import reporting, spec
    items = pack.get('items') if isinstance(pack, dict) else None
    if (not isinstance(items, list) or not items
            or not all(isinstance(x, dict) and _text(x.get('creative_id')) for x in items)
            or not isinstance(pack.get('matchday'), str) or not DATE.fullmatch(pack['matchday'])
            or not isinstance(pack.get('run_id'), str) or not RUN_ID.fullmatch(pack['run_id'])):
        raise ValueError('a checked matchday pack is needed: make it with pack.build first')
    if expires_at is not None and not _datetime(expires_at):
        raise ValueError('expires_at must be an ISO date and time with its UTC offset, or null')
    errors = size_errors(pack)
    if errors:
        raise ValueError('; '.join(errors))
    exact = reporting.canonical(pack)
    channels = list(dict.fromkeys(str(x.get('channel')) for x in items))
    count = len(items)
    title = (f'Matchday {pack["matchday"]}: {count} post{"s" if count != 1 else ""} to make by hand '
             f'({", ".join(channels)})')
    why = ('Handcrafted (ruling 3): you post each item yourself in Buffer, and the WhatsApp Channel by hand. '
           'Clear means post it for every item. Purge rejects every item. Change it first is read per item: '
           'unchanged is post it, edited is an edit, removed is a reject, and a note on an item is kept for '
           'the next draft. Every item links to a published AI Pundit show, or for a match ad to Today while '
           f'it carries one, passed the copy rules, and scored at least {RUBRIC_BAR} of {RUBRIC_MAX} in an '
           'independent review with Ethics and Action at 4.')
    uses = {}
    for item in items:
        for entry in item.get('media') or []:
            if isinstance(entry, dict) and isinstance(entry.get('review_url'), str):
                uses.setdefault(entry['review_url'], []).append(f'{item["creative_id"]} {entry.get("kind")}')
    evidence = [{'label': ('Review: ' + ', '.join(dict.fromkeys(uses[url])))[:500], 'url': url}
                for url in review_urls(pack)]
    return reporting._proposal(
        f'fulltime-g2-{pack["matchday"]}', title, why, 'prepared', 'post', pack, 'creative_published',
        pack['run_id'], objective_key=spec.PROPOSAL_OBJECTIVE,
        channel=channels[0] if len(channels) == 1 else 'multi', exact_payload=exact,
        evidence=evidence, expires_at=expires_at)
