"""The matchday pack: gate G2's payload (docs/ENGINE-V2.md, sections 3 to 5).

One pack per matchday lists every item Krish is asked about: its creative ID, the
fixture and format lock it is judged under, channel, caption, tracked link, media
hashes and the independent review that says why it clears the creative bar.
check() is the pack's own rules plus growth.py's copy rules and, given the week's
spec, its fixtures, locks, channels, AI Pundits and caps. build() refuses a pack
that breaks any of them, and proposal() turns a checked pack into one G2 ask for
Control Center: in proof mode a verdict ask that posts nothing, in live mode a
handcrafted post ask.

Rulings it applies (Krish, 27 October 2026):
- 1, the per-take gate: a take links to an exact AI Pundit show that is
  published on the rail, and every AI Pundit it names has a show for that match;
  the 4-of-6 rule applies to a whole-match claim, flagged or worded.
- 3, handcrafted: Krish posts each item himself in Buffer, and only in live mode.
  The pack is the exact artifact; nothing here posts, sends, spends or writes to a platform.
- 11, a match ad links to Today only while Today carries a published AI Pundit
  show, and its words never claim a show exists for its match.

The channel, release, identity and consent gates, readiness, ORGANIC and D7 belong
to the spec's mode check (engine/spec.py compile), so a pack can go to G2 in proof
mode before they open; a live ask needs the pack checked against the live spec.
"""
import copy
import datetime as dt
import json
import re
import unicodedata
from urllib.parse import parse_qsl, urlsplit

from . import policy

PACK_FIELDS = ('run_id', 'matchday', 'items')
ITEM_FIELDS = ('creative_id', 'master_id', 'format_id', 'fixture_ref', 'lock_version', 'channel', 'channel_ref',
               'caption', 'hashtags', 'link', 'drop_id', 'pundit', 'pundits', 'whole_match', 'media', 'ai_label',
               'scheduled_suggestion', 'review', 'note')
REQUIRED = ('creative_id', 'master_id', 'format_id', 'fixture_ref', 'lock_version', 'channel', 'channel_ref',
            'caption', 'hashtags', 'link', 'media', 'ai_label', 'scheduled_suggestion', 'review')
MEDIA_FIELDS = ('kind', 'sha256', 'bytes', 'review_url')
MEDIA_KINDS = ('video', 'image', 'audio')
AI_LABEL = ('platform_label_set', 'visible_ai_pundit')
REVIEW_FIELDS = ('rubric_total', 'ethics', 'action', 'alternatives', 'doctrine_ref', 'why_wins')
RUBRIC_MAX, RUBRIC_BAR = 48, 38
MODES = ('proof', 'live')
MAX_PAYLOAD = 8000          # the protocol's exact_payload limit
MAX_REVIEW_LINKS = 12       # the protocol's evidence limit
MAX_ID = 120                # the protocol's proposal_id limit
X_LINK = 23                 # X counts every link as 23 characters
BY_HAND = ('whatsapp_channel',)   # Buffer does not carry it, so Krish posts it by hand (ruling 2)
HOSTS = ('fulltime.fm', 'www.fulltime.fm')
SHA = re.compile(r'^[0-9a-f]{64}$')
RUN_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,119}$')
MASTER_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9:._-]{0,79}$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RAW_ID = re.compile(r'^(?:[0-9a-f]{24}|\d{6,})$')    # a Buffer or platform ID, never an allowlist ref
TAG = re.compile(r'^#\w+$')
# A link in the words: a scheme, www., or a bare domain that X, Threads and Facebook turn into a link.
LINK_IN_TEXT = re.compile(r'https?://|\bwww\.|\b[a-z0-9-]+\.(?:ly|com|co|io|me|gl|link|to|uk|net|org|app|page|fm|tv)'
                          r'(?:/|\b)', re.I)
SHOW_WORDS = re.compile(r'\b(?:show|edition|episode|podcast|programme|program)s?\b', re.I)
MATCH_CLAIM = re.compile(r"\bout now\b"
                         r"|\b(?:on|about|for)\s+(?:this|today'?s|tonight'?s)\s+(?:match|game|fixture|derby)\b", re.I)
WHOLE_MATCH_WORDS = re.compile(r'\b(?:all|every|each)\s+(?:of\s+)?(?:the\s+)?(?:six\s+|6\s+)?AI\s+Pundits?\b'
                               # "six AI Pundits" on a match claims them all; "one of six AI Pundits" is the roster
                              r'|(?<!of )(?<!of the )(?<!among )(?<!among the )\b(?:six|6)\s+AI\s+Pundits\b'
                              r'|\bwhole[\s-]match\b'
                               r'|\b(?:six|6)\s+(?:of|out\s+of)\s+(?:six|6)\b|\b6/6\b|\bfull\s+panel\b', re.I)
TAG_OR_HANDLE = re.compile(r'(?<![\w&/])[#@](\w+)')
JOINS = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])|_')
# growth.py rules that read words, so they also apply to the words a hashtag or @handle joins.
WORD_RULES = ('betting language', 'a broadcaster', 'a living pundit', 'marketing filler', 'stock phrase',
              'promises', 'claims prediction', 'names a launch', 'claims proof', 'audience figure',
              'manufactures urgency', 'US English', 'internal term', 'AI character')

_CHECKED = {}   # payload digest -> (spec mode, spec run_id) for each pack check() passed in this process


def _growth():
    import growth
    return growth


def _datetime(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace('Z', '+00:00')).tzinfo is not None
    except ValueError:
        return False


def _london_day(value):
    from .clock import LONDON
    if not isinstance(value, str) or not _datetime(value):
        return None
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(LONDON).date().isoformat()


def _https(url):
    if not isinstance(url, str) or re.search(r'\s', url):
        return False
    parts = urlsplit(url)
    return parts.scheme == 'https' and bool(parts.hostname) and not parts.username and not parts.password


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _plain(text):
    """NFKC, without invisible format characters (zero-width space, soft hyphen), so a
    lookalike or a hidden break reads as the plain word."""
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if unicodedata.category(c) != 'Cf')


def _words(text):
    """The text with each #hashtag and @handle read as the words it joins: #SkySports is Sky Sports."""
    return TAG_OR_HANDLE.sub(lambda m: JOINS.sub(' ', m.group(1)), text)


def _said(item):
    """Everything the item says in public, caption and hashtags, as plain words."""
    caption = item['caption'] if isinstance(item.get('caption'), str) else ''
    tags = item.get('hashtags') if isinstance(item.get('hashtags'), list) else []
    return _words(_plain(' '.join([caption] + [t for t in tags if isinstance(t, str)])))


def _named(said):
    """The AI Pundit ids whose public names the words use, such as The Doomer or #TheWindUp."""
    growth = _growth()
    out = []
    for pid, name in growth.PUNDITS.items():
        rest = re.split(r'[\s-]+', name)[1:]          # 'The Wind-Up' is Wind, Up
        if re.search(r'\b[Tt]he\s+' + r'[\s-]?'.join(map(re.escape, rest)) + r'\b', said):
            out.append(pid)
    return out


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


def proposal_id(pack):
    """The G2 ask's id. The pack fulltime:<matchday>:g2 is fulltime-g2-<matchday>; a matchday
    split into parts, each with its own run_id (fulltime:<matchday>:g2a, :g2b), gets one id per part."""
    day, run = pack['matchday'], pack['run_id']
    tail = run[len(f'fulltime:{day}:'):]
    return f'fulltime-g2-{day}' if tail == 'g2' else f'fulltime-g2-{day}-{tail}'


def size_errors(pack):
    from .reporting import canonical
    try:
        exact = canonical(pack)
    except ValueError as error:
        return [f'the pack is not plain JSON ({error})']
    out = []
    if payload_length(exact) > MAX_PAYLOAD:
        stem = f'fulltime:{pack.get("matchday")}:g2' if isinstance(pack, dict) else 'fulltime:<matchday>:g2'
        out.append(f'the pack is {payload_length(exact)} characters as exact_payload; Control Center takes at most '
                   f'{MAX_PAYLOAD}: split the matchday into packs with their own run_id ({stem}a, {stem}b and so '
                   'on), so each part is its own G2 ask, or trim it')
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
    """growth.py's copy rules on the words that go out: the caption and its hashtags,
    then once more on those words as plain text with each hashtag and @handle split
    into the words it joins, for the rules that read words (#BettingTips, @SkySportsPL).
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
    out = [e for e in growth.problems(draft, copy_state) if e != unlisted]
    split = _words(_plain(draft['text']))
    if split != draft['text']:
        out += [f'{e} (read with each hashtag and @handle as words)'
                for e in growth.problems({**draft, 'text': split}, copy_state)
                if e not in out and any(rule in e for rule in WORD_RULES)]
    return out


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
    """The item's allowlist entry, held to buffer_read's own rules, with a Buffer ID on
    every channel Buffer carries, so its post can be read back."""
    from .buffer_read import allowlist_errors
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
    out = [f'the allowlist entry is refused: {e}'
           for e in allowlist_errors({'product': 'fulltime', 'channels': {ref: entry}})]
    if not out and entry.get('buffer_channel_id') is None and entry.get('channel') not in BY_HAND:
        out.append(f'channel_ref {ref!r} has no Buffer channel ID, so its post could never be read back; '
                   'only the WhatsApp Channel is posted by hand outside Buffer')
    return out


def _link_errors(drop, pundit, cid, link):
    """The exact show link and nothing else: drop and pundit once each, read as a browser
    reads them (the first value), plus the creative's tracking."""
    growth = _growth()
    parts = urlsplit(link) if isinstance(link, str) else None
    if parts is None or parts.hostname not in HOSTS:
        return []                     # _item_errors reports a link that is not fulltime.fm
    first = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True) if parts.path in ('', '/') else []:
        first.setdefault(key, value)
    show = f'{growth.SITE}/?drop={drop}&pundit={pundit}'
    if first.get('drop') != drop or first.get('pundit') != pundit:
        return [f'the link must open drop {drop} with {growth.PUNDITS.get(pundit, pundit)}: {show}, tracked']
    if not (isinstance(cid, str) and growth.CREATIVE_ID.fullmatch(cid)):
        return []
    exact = growth.tracked(show, cid)
    if link != exact and growth.tracked(link, cid) != exact:     # tracking alone is reported as "not tracked"
        return [f'the link must be exactly {exact}: drop and pundit once each, and nothing else']
    return []


def _show_errors(item, recipe, state, link, said):
    """Ruling 1: an exact published show, every AI Pundit the item names or lists published
    for its match, and 4 of 6 for a whole-match claim, flagged or worded."""
    growth = _growth()
    drop, pundit, fmt = item.get('drop_id'), item.get('pundit'), item.get('format_id')
    if not _text(drop) or not _text(pundit):
        return ['a link to an exact show needs drop_id and pundit (ruling 1)']
    out = []
    if pundit not in growth.PUNDITS:
        out.append(f'pundit {pundit!r} is not one of ' + ', '.join(growth.PUNDITS))
    out += _link_errors(drop, pundit, item.get('creative_id'), link)
    least = recipe.get('published_pundits_min') if type(recipe.get('published_pundits_min')) is int else 0
    listed = item.get('pundits')
    if 'pundits' in item:
        if (not isinstance(listed, list) or not all(isinstance(p, str) and p in growth.PUNDITS for p in listed)
                or len(set(listed)) != len(listed) or pundit not in listed):
            out.append('pundits must list distinct AI Pundit ids, the item\'s own pundit among them')
        elif len(listed) < least:
            out.append(f'{fmt} names {least} AI Pundits: pundits lists {len(listed)}')
    elif least >= 2:
        out.append(f'{fmt} names {least} AI Pundits: list every one in pundits, the item\'s own pundit among them')
    worded = WHOLE_MATCH_WORDS.search(said)
    claimed = item.get('whole_match') is True or worded is not None
    if worded and item.get('whole_match') is not True:
        out.append(f'the words claim the whole match ("{worded.group(0)}"), so whole_match must be true')
    if claimed and recipe.get('whole_match_claims_allowed') is not True:
        out.append(f'{fmt} may not claim a whole match')
    rail = state.get('rail') if isinstance(state, dict) else None
    if not isinstance(rail, list):
        return out + ['the rail was not read, so no show is confirmed published (run python3 growth.py sync)']
    match = next((m for m in rail if isinstance(m, dict) and m.get('drop') == drop), None)
    if match is None:
        return out + [f'drop {drop} has no published show on the rail (ruling 1)']
    shows = match.get('pundits') if isinstance(match.get('pundits'), list) else []
    pundits = [p for p in shows if isinstance(p, str) and p in growth.PUNDITS]
    name = f'{match.get("home")} v {match.get("away")}'
    others = [p for p in (listed if isinstance(listed, list) else []) + _named(said) if isinstance(p, str)]
    for pid in dict.fromkeys([pundit] + [p for p in others if p in growth.PUNDITS]):
        if pid not in pundits:
            out.append(f'{growth.PUNDITS.get(pid, pid)} has no published show for {name} (ruling 1)')
    fill = match['fill'] if type(match.get('fill')) is int else len(set(pundits))
    if fill < least:
        out.append(f'{fmt} needs {least} published AI Pundits on the match; {name} has {fill}')
    if claimed and fill < growth.RAIL_MIN:
        out.append(f'a whole-match claim needs {growth.RAIL_MIN} of 6 AI Pundits; {name} has {fill}')
    return out


def _today_errors(item, today_live, link, said):
    """Ruling 11: a match ad links to Today while it carries a published show, and never claims one."""
    growth = _growth()
    out = []
    if item.get('drop_id') is not None or item.get('pundit') is not None or item.get('pundits') is not None:
        out.append('a link to Today names no drop_id, pundit or pundits (ruling 11)')
    if item.get('whole_match') is True:
        out.append('a link to Today makes no whole-match claim')
    cid = item.get('creative_id')
    if (isinstance(link, str) and isinstance(cid, str) and growth.CREATIVE_ID.fullmatch(cid)
            and link != growth.tracked(growth.SITE + '/', cid)):
        out.append(f'a match ad links to the Today home page: {growth.tracked(growth.SITE + "/", cid)}')
    if today_live is not True:
        out.append('Today has no published AI Pundit show right now, so the match ad is held (ruling 11)')
    found = SHOW_WORDS.search(said) or MATCH_CLAIM.search(said)
    if found:
        out.append(f'a match ad never claims a show exists for its match: it says "{found.group(0)}" (ruling 11)')
    return out


def _claims_allowed(format_id):
    from . import formats
    try:
        return formats.recipe(format_id).get('whole_match_claims_allowed') is True
    except (ValueError, KeyError, TypeError):
        return False


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
    if 'fixture_ref' in item and not _text(item['fixture_ref']):
        out.append('fixture_ref must name the match: the spec\'s fixture_ref')
    lock = item.get('lock_version')
    if 'lock_version' in item and lock != 'unlocked' and not (isinstance(lock, str) and SHA.fullmatch(lock)):
        out.append('lock_version must be "unlocked" or the format lock, 64 lowercase hex characters')
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
        if LINK_IN_TEXT.search(_plain(caption)):
            out.append('the caption carries no link: the link field holds the one tracked link')
        if growth.HASHTAG.search(caption):
            out.append('hashtags go in the hashtags list, not the caption')
        if channel and tags_ok:
            out += _copy_errors(item, state)
            text = caption + '\n\n' + ' '.join(tags)
            limit = growth.LIMITS['x']
            if channel == 'x' and len(text) <= limit < len(text) + 1 + X_LINK:
                out.append(f'on x the post is {len(text) + 1 + X_LINK} characters with its link (X counts every '
                           f'link as {X_LINK}); {limit} at most')
    link = item.get('link')
    parts = urlsplit(link) if isinstance(link, str) else None
    if (parts is None or parts.scheme != 'https' or parts.hostname not in HOSTS
            or parts.username or parts.password or parts.port):
        out.append('link must be an https fulltime.fm link')
    elif matched and link != growth.tracked(link, cid):
        out.append(f'the link is not tracked as {cid}: use {growth.tracked(link, cid)}')
    if 'whole_match' in item and not isinstance(item['whole_match'], bool):
        out.append('whole_match must be true or false')
    if recipe and recipe.get('whole_match_claims_allowed') is True and 'whole_match' not in item:
        out.append(f'whole_match must be set, true or false: a {item.get("format_id")} may claim a whole match')
    if recipe:
        target, said = recipe.get('links_to'), _said(item)
        if target == 'exact_show':
            out += _show_errors(item, recipe, state, link, said)
        elif target == 'today':
            out += _today_errors(item, today_live, link, said)
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


def _spec_item_errors(item, campaign):
    """The week spec allows this item: its fixture, its format's lock, channel and AI Pundits."""
    growth = _growth()
    run, fid = campaign['run_id'], item.get('format_id')
    out = []
    if item.get('fixture_ref') not in [f['fixture_ref'] for f in campaign['fixtures']]:
        out.append(f'fixture_ref {item.get("fixture_ref")!r} is not a fixture in the week spec {run}')
    allowed = next((f for f in campaign['formats'] if f['format_id'] == fid), None)
    if allowed is None:
        return out + [f'{fid} is not a format in the week spec {run}']
    if item.get('lock_version') != allowed['lock_version']:
        out.append(f'lock_version {item.get("lock_version")!r} is not the {fid} lock in the week spec {run} '
                   f'({allowed["lock_version"]})')
    if item.get('channel') not in allowed['channels']:
        out.append(f'the week spec {run} allows {fid} on {", ".join(allowed["channels"])}, not {item.get("channel")}')
    listed = item.get('pundits') if isinstance(item.get('pundits'), list) else []
    for pid in dict.fromkeys(p for p in [item.get('pundit')] + listed if isinstance(p, str)):
        if pid not in allowed['pundits_allowed']:
            out.append(f'the week spec {run} does not allow {growth.PUNDITS.get(pid, pid)} in {fid}')
    return out


def _cap_errors(items, others, matchday, campaign):
    """max_per_matchday counts the format's masters on this matchday (one master on several
    channels is one take, ruling 2), and cap_per_day the items on each channel each London
    day, counting the other packs' items given in earlier."""
    most = {f['format_id']: f['max_per_matchday'] for f in campaign['formats']}
    caps = {c['channel']: c['cap_per_day'] for c in campaign['channels']}
    masters, per_day = {}, {}
    for day, item in [(matchday, x) for x in items] + others:
        fid, channel, master = item.get('format_id'), item.get('channel'), item.get('master_id')
        if day == matchday and isinstance(fid, str) and fid in most and isinstance(master, str):
            masters.setdefault(fid, set()).add(master)
        when = _london_day(item.get('scheduled_suggestion'))
        if isinstance(channel, str) and channel in caps and when:
            per_day[(channel, when)] = per_day.get((channel, when), 0) + 1
    out = []
    for fid, found in sorted(masters.items()):
        if len(found) > most[fid]:
            out.append(f'{fid}: {len(found)} masters on matchday {matchday}, and the week spec allows '
                       f'{most[fid]} (max_per_matchday; one master on several channels counts once)')
    for (channel, when), count in sorted(per_day.items()):
        if count > caps[channel]:
            out.append(f'{channel}: {count} items on {when}, and the week spec allows {caps[channel]} a day '
                       '(cap_per_day)')
    return out


def _earlier_items(earlier, own):
    """(proposal_id, matchday, item) for every item in the earlier G2 asks other than this
    pack's own id (a revision of this pack replaces it), and every ask that cannot be read."""
    rows, errors = [], []
    for n, ask in enumerate(earlier or [], 1):
        pid = ask.get('proposal_id') if isinstance(ask, dict) else None
        if own is not None and pid == own:
            continue
        try:
            data = json.loads(ask['exact_payload'])
            rows += [(pid, data.get('matchday'), x) for x in data['items'] if isinstance(x, dict)]
        except (KeyError, TypeError, ValueError, AttributeError):
            errors.append(f'earlier G2 ask {n} ({pid}) cannot be read, so reuse cannot be ruled out')
    return rows, errors


def check(pack, state, allowlist, today_live, campaign=None, earlier=None):
    """Every reason this matchday pack cannot go to G2, in plain words. Empty means it can.
    campaign is the week spec (signed for a live ask): each item must sit inside it, and
    its caps hold. earlier lists the G2 asks already made (gates' proposals): no creative
    ID repeats, and no asset goes on a channel it already went on."""
    if not isinstance(pack, dict):
        return ['a matchday pack must be a JSON object']
    out = []
    unknown = sorted(set(pack) - set(PACK_FIELDS))
    if unknown:
        out.append('unknown pack fields: ' + ', '.join(unknown))
    matchday, run = pack.get('matchday'), pack.get('run_id')
    try:
        if not isinstance(matchday, str) or not DATE.fullmatch(matchday):
            raise ValueError
        dt.date.fromisoformat(matchday)
    except ValueError:
        out.append('matchday must be a calendar date, YYYY-MM-DD')
        matchday = None
    own = None
    if not isinstance(run, str) or not RUN_ID.fullmatch(run):
        out.append('run_id must be a stable run id (letters, digits and : . _ -)')
    elif matchday and not run.startswith(f'fulltime:{matchday}:'):
        out.append(f'run_id must name its matchday: fulltime:{matchday}:g2, or fulltime:{matchday}:g2a and so on '
                   'for each part of a split matchday')
    elif matchday:
        own = proposal_id(pack)
        if len(own) > MAX_ID:
            out.append(f'run_id is too long: the G2 ask {own[:40]}... needs at most {MAX_ID} characters')
    if not isinstance(allowlist, dict) or allowlist.get('product') != 'fulltime':
        out.append('the Buffer allowlist must be scoped to product "fulltime"')
    if campaign is not None:
        from . import spec
        refused = spec.validate(campaign) if isinstance(campaign, dict) else ['the week spec must be a JSON object']
        if refused:
            out.append('the week spec is refused, so no item is checked against it: ' + '; '.join(refused))
            campaign = None
    items = pack.get('items')
    if not isinstance(items, list) or not items or not all(isinstance(x, dict) for x in items):
        return out + ['items must be a non-empty list of pack items']
    prior, unread = _earlier_items(earlier, own)
    out += unread
    used_ids = {x.get('creative_id'): pid for pid, _, x in prior if isinstance(x.get('creative_id'), str)}
    used_assets = {}
    for pid, _, x in prior:
        for entry in x.get('media') if isinstance(x.get('media'), list) else []:
            if isinstance(entry, dict) and isinstance(entry.get('sha256'), str) and isinstance(x.get('channel'), str):
                used_assets.setdefault((entry['sha256'], x['channel']), pid)
    ids, masters, assets = set(), set(), set()
    for i, item in enumerate(items, 1):
        cid, channel = item.get('creative_id'), item.get('channel')
        label = f'item {i} ({cid if isinstance(cid, str) else "?"})'
        found = _item_errors(item, state, allowlist, today_live)
        if campaign is not None:
            found += _spec_item_errors(item, campaign)
        out += [f'{label}: {e}' for e in found]
        if isinstance(cid, str):
            if cid in ids:
                out.append(f'{label}: creative_id {cid} appears twice in the pack')
            elif cid in used_ids:
                out.append(f'{label}: creative_id {cid} was already asked in {used_ids[cid]}; a new cut needs a new ID')
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
                elif (digest, channel) in used_assets:
                    out.append(f'{label}: the same asset ({digest[:12]}) already went on {channel} in '
                               f'{used_assets[(digest, channel)]}')
                assets.add((digest, channel))
    if campaign is not None and matchday:
        out += _cap_errors(items, [(day, x) for _, day, x in prior], matchday, campaign)
    out += size_errors(pack) + policy.sensitive_errors(pack)
    _remember(pack, out, campaign)
    return out


def _remember(pack, errors, campaign):
    """Record what the latest check of exactly this pack found, so proposal() states it truthfully."""
    from .reporting import canonical_sha256
    try:
        digest = canonical_sha256(pack)
    except (ValueError, TypeError):
        return
    _CHECKED.pop(digest, None)
    if not errors:
        if len(_CHECKED) >= 256:
            _CHECKED.pop(next(iter(_CHECKED)))
        _CHECKED[digest] = (campaign['mode'], campaign['run_id']) if campaign else (None, None)


def checked(pack):
    """(spec mode, spec run_id) when check() passed on exactly this pack in this process,
    ((None, None) when it ran without a week spec), else None."""
    from .reporting import canonical_sha256
    try:
        return _CHECKED.get(canonical_sha256(pack))
    except (ValueError, TypeError):
        return None


def _explicit(item):
    """The item, with whole_match false where its format may not claim a whole match.
    A format that may claim one must say so on every item, true or false."""
    out = copy.deepcopy(item)
    if isinstance(out, dict) and 'whole_match' not in out and not _claims_allowed(out.get('format_id')):
        out['whole_match'] = False
    return out


def build(items, run_id, matchday, state, allowlist, today_live, campaign=None, earlier=None):
    """The checked pack, with whole_match explicit on every item. Refused with every reason."""
    if not isinstance(items, list):
        raise ValueError('items must be a list of pack items')
    pack = {'run_id': run_id, 'matchday': matchday, 'items': [_explicit(x) for x in items]}
    errors = check(pack, state, allowlist, today_live, campaign, earlier)
    if errors:
        raise ValueError('the matchday pack was refused: ' + '; '.join(errors))
    return pack


def _end_of(day):
    """The end of a matchday in Europe/London, as an aware time."""
    from .clock import LONDON
    after = dt.date.fromisoformat(day) + dt.timedelta(days=1)
    return dt.datetime(after.year, after.month, after.day, tzinfo=LONDON)


def proposal(pack, expires_at, mode='proof'):
    """Gate G2: one ask whose exact_payload is the whole pack. It re-runs no check: it
    says the pack was checked when it was built only when check() passed on exactly this
    pack. In proof mode it is a verdict ask and nothing is posted: Krish answers post it,
    edit or reject per item to build readiness. Only live mode, for a pack checked against
    the live spec, asks him to post by hand in Buffer. Clear is post it for every item,
    Purge rejects every item, and Change it first is read per item by diff (engine/formats.py,
    g2_verdicts). It closes on creative_published."""
    from . import reporting, spec
    if mode not in MODES:
        raise ValueError('mode must be proof or live: the week spec\'s mode')
    items = pack.get('items') if isinstance(pack, dict) else None
    if (not isinstance(items, list) or not items
            or not all(isinstance(x, dict) and _text(x.get('creative_id')) for x in items)
            or not isinstance(pack.get('matchday'), str) or not DATE.fullmatch(pack['matchday'])
            or not isinstance(pack.get('run_id'), str) or not RUN_ID.fullmatch(pack['run_id'])
            or not pack['run_id'].startswith(f'fulltime:{pack["matchday"]}:')):
        raise ValueError('a checked matchday pack is needed: make it with pack.build first')
    if not isinstance(expires_at, str) or not _datetime(expires_at):
        raise ValueError('expires_at must be an ISO date and time with its UTC offset: every G2 ask expires')
    errors = size_errors(pack)
    if errors:
        raise ValueError('; '.join(errors))
    if len(proposal_id(pack)) > MAX_ID:
        raise ValueError(f'the run_id is too long to name a G2 ask of at most {MAX_ID} characters')
    record = checked(pack)
    spec_mode, spec_run = record or (None, None)
    if spec_mode is not None and spec_mode != mode:
        raise ValueError(f'the pack was checked against the {spec_mode} spec {spec_run}, so its ask is {spec_mode}')
    if mode == 'live' and spec_mode != 'live':
        raise ValueError('a live ask needs pack.check to pass on exactly this pack against the signed live spec')
    ads = any(x.get('format_id') == 'match_ad' for x in items)
    expires = dt.datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    if mode == 'live' and ads and expires > _end_of(pack['matchday']):
        raise ValueError(f'a live pack with a match ad expires by the end of matchday {pack["matchday"]} '
                         '(Europe/London): Today is checked live at post time (ruling 11)')
    exact = reporting.canonical(pack)
    channels = list(dict.fromkeys(str(x.get('channel')) for x in items))
    count, plural = len(items), 's' if len(items) != 1 else ''
    answers = ('Change it first is read per item: unchanged is post it, edited is an edit, removed is a reject, '
               'and a note on an item is kept for the next draft. ')
    if record is not None:
        against = f' against the week spec {spec_run}' if spec_run else ''
        found = (f'Checked when the pack was built{against}: every item links to a published AI Pundit show, or for '
                 'a match ad to Today while it carried one, passed the copy rules, and scored at least '
                 f'{RUBRIC_BAR} of {RUBRIC_MAX} in an independent review with Ethics and Action at 4.')
    else:
        found = ('Not checked: pack.check has not passed on exactly this pack, so nothing here says it meets '
                 'the rules.')
    if mode == 'proof':
        title = (f'Matchday {pack["matchday"]}, proof: verdicts only on {count} item{plural}, nothing to post '
                 f'({", ".join(channels)})')
        why = ('Proof: a verdict ask only. Nothing is to be posted, and you do not post any item. Your answer on '
               'each item (post it, edit or reject) builds its format\'s readiness. Clear records post it for every '
               'item and posts nothing. Purge records reject for every item. ' + answers + found)
    else:
        title = f'Matchday {pack["matchday"]}: {count} post{plural} to make by hand ({", ".join(channels)})'
        why = (f'Live, under the signed spec {spec_run}. Handcrafted (ruling 3): you post each item yourself in '
               'Buffer, and the WhatsApp Channel by hand. Clear means post it for every item. Purge rejects every '
               'item. ' + answers
               + ('Before posting a match ad, check Today carries a published AI Pundit show (ruling 11). '
                  if ads else '') + found)
    uses = {}
    for item in items:
        for entry in item.get('media') or []:
            if isinstance(entry, dict) and isinstance(entry.get('review_url'), str):
                uses.setdefault(entry['review_url'], []).append(f'{item["creative_id"]} {entry.get("kind")}')
    evidence = [{'label': ('Review: ' + ', '.join(dict.fromkeys(uses[url])))[:500], 'url': url}
                for url in review_urls(pack)]
    return reporting._proposal(
        proposal_id(pack), title, why, 'prepared', 'post', pack, 'creative_published',
        pack['run_id'], objective_key=spec.PROPOSAL_OBJECTIVE,
        channel=channels[0] if len(channels) == 1 else 'multi', exact_payload=exact,
        evidence=evidence, expires_at=expires_at)
