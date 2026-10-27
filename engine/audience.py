"""The Audience Builder: Full Time's brand profiles, easy to find and quick to follow.

Krish's rulings (27 October 2026): Full Time brand profiles only, never his
personal accounts; growth work is automated only within platform rules, through
official APIs, for actions each platform allows, and every action type needs his
ruling first. Publishing itself stays with Krish in Buffer (ruling 3).

engagement-actions.json lists every action type that might ever be automated,
each pending until he rules, and the banned ones, which this module refuses even
if they were ever ruled. load_actions() checks that file; gate() is the lint
before any automated action; profile_checklist() lists the fixes that make one
profile findable; daily_plan() orders the day's visibility work inside Krish's
minutes; followers_check() is the measured check after acting.

Follower counts are a diagnostic of distribution capacity, not a goal.
The North Star is unchanged: new listeners a week who arrived through a fan's
shared link or clip (docs/NORTH_STAR.md).

No function here calls a platform API or the network, and nothing here posts,
replies, follows, likes or messages. Execution adapters come later, one per
approved action type, and each one calls gate() first.
"""
import datetime as dt
import json
from pathlib import Path
import re

from . import buffer_read, pack, policy, spec

ROOT = Path(__file__).resolve().parent.parent
ACTIONS_FILE = ROOT / 'engagement-actions.json'
PLATFORMS = ('youtube', 'tiktok', 'instagram', 'threads', 'x', 'facebook', 'whatsapp_channel')
LABEL = {'youtube': 'YouTube', 'tiktok': 'TikTok', 'instagram': 'Instagram', 'threads': 'Threads', 'x': 'X',
         'facebook': 'Facebook', 'whatsapp_channel': 'WhatsApp Channel'}
# The spec channel whose creative ID prefix a profile's link carries.
PROFILE_CHANNEL = {'youtube': 'yt_shorts', 'tiktok': 'tiktok', 'instagram': 'ig_reels', 'threads': 'threads',
                   'x': 'x', 'facebook': 'facebook', 'whatsapp_channel': 'whatsapp_channel'}
STATUSES = ('pending', 'approved', 'retired')
TOP_FIELDS = {'_about', 'actions', 'banned'}
ACTION_FIELDS = {'title', 'platforms', 'official_api', 'rule_source', 'rule_checked_on', 'status', 'ruling',
                 'daily_cap', 'needs_review_each_time'}
RULING_FIELDS = {'date', 'words'}
RULE_CHECK_DAYS = 90
ACTION_ID = re.compile(r'^[a-z][a-z0-9_]{2,63}$')
NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]{0,63}$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
SHA = re.compile(r'^[0-9a-f]{64}$')
TAG = re.compile(r'^#\w{1,60}$')
# Refused in code even if a ruling ever names them, and kept in the file's banned list.
BANNED = {
    'automated_follow_or_unfollow': "X's automation rules ban automated following and unfollowing",
    'mass_liking': 'bulk or automated likes are platform manipulation',
    'unsolicited_dms': "Krish's rule: no cold outreach, and unsolicited messages are spam",
    'comments_on_other_accounts_at_scale': 'commenting on other accounts at scale is spam',
    'follow_for_follow': 'follow-for-follow inflates the count without fans',
    'engagement_bait': 'engagement bait can make posts ineligible for the For You feed',
    'buying_followers_or_engagement': 'bought followers or engagement are fake and break the zero-cash rule',
    'any_personal_account_action': "Krish's ruling: Full Time brand profiles only, never his personal accounts",
    'any_action_without_official_api': "Krish's ruling: automate only through official APIs",
}
# The only kinds of automated action this engine knows. A word list alone lets a banned
# tactic through under a synonym ("react", "heart", a reel "container"), so any other id
# is refused here: a new kind of action needs a code change, a review and a test.
KNOWN_ACTIONS = frozenset({
    'reply_to_comments_on_own_posts', 'hide_or_report_abusive_comments_on_own_posts',
    'pin_best_comment_on_own_post', 'update_profile_bio_and_links', 'rotate_pinned_post',
    'add_post_to_playlist_or_highlight', 'schedule_story_or_community_post', 'crosslink_profiles',
})
# Publishing stays with Krish in Buffer, whatever a ruling on the action says.
HANDCRAFTED = {'schedule_story_or_community_post': 'publishing stays with Krish in Buffer (ruling 3)'}
# What an action does, read from its id, title and official API with punctuation as
# spaces, so a banned tactic under a new id is still refused. A false match only
# leaves the task with Krish, by hand.
KINDS = (
    ('follows or unfollows accounts', 'automated_follow_or_unfollow',
     re.compile(r'\b(?:un)?follow(?:s|ed|ing)?\b', re.I)),
    ('likes posts or replies', 'mass_liking', re.compile(r'\b(?:un)?lik(?:e|es|ed|ing)\b|\bfavou?rit', re.I)),
    ('sends messages', 'unsolicited_dms', re.compile(r'\bdms?\b|\bmessag|\binbox', re.I)),
    ('publishes, posts or schedules', None,
     re.compile(r'\bpublish|\bschedul|\bupload|\brepost|\bretweet|\bstor(?:y|ies)\b(?! highlight)|'
                r'\bcontent posting\b|\bvideos insert\b|\bpost 2 tweets\b(?! id)|\bfeed\b|'
                r'\bpost(?:ing|ed)? (?:a|an|the|new|daily|every|it|them)\b', re.I)),
    ('buys or boosts reach', 'buying_followers_or_engagement',
     re.compile(r'\bbuy|\bpurchas|\bboost|\bpaid\b|\bads?\b|\bsponsor', re.I)),
    ('baits engagement', 'engagement_bait', re.compile(r'\bgiveaway|\bcontest|\btag a friend|\bto win\b', re.I)),
    ('acts on a personal account', 'any_personal_account_action', re.compile(r'\bpersonal\b', re.I)),
)
COMMENTS = re.compile(r'\bcomment|\brepl(?:y|ies|ied|ying)\b', re.I)
OWN = re.compile(r"\bown\b|\bfull time\b", re.I)
OTHERS = re.compile(r'\bother (?:accounts|creators|clubs|pages|profiles|people)\b|\bothers\b', re.I)

PROFILE_FIELDS = {'account_scope', 'name', 'handle', 'bio', 'link', 'pinned_post', 'avatar_sha256',
                  'cross_links', 'ai_disclosure', 'image_marks'}
PROFILE_REQUIRED = {'account_scope', 'name', 'handle', 'bio', 'link'}
BIO_LINE = 80              # TikTok's bio limit, the tightest of the brand platforms
PIN_POST = ('tiktok', 'instagram', 'x', 'threads', 'facebook')
PIN_COMMENT = ('youtube', 'tiktok', 'instagram')
PLAYLIST = {'youtube': 'the AI Pundit playlist', 'tiktok': 'the AI Pundit playlist',
            'instagram': 'an AI Pundit story highlight'}
REMIX = {'tiktok': 'duets and stitches', 'instagram': 'remixes', 'youtube': 'remixes'}
SOUND = ('tiktok', 'instagram')
PUSH = ('tiktok', 'instagram', 'youtube')      # ruling 2: pushed daily; the rest get derived cards
HASHTAGS = ('tiktok', 'instagram', 'youtube')     # Threads takes one topic tag, so it is left out
BEST_DAYS, TREND_HOURS, PLAYLIST_DAYS = 14, 72, 7
# League names in a profile's name or handle read as affiliation; logos anywhere are refused.
LEAGUE = re.compile(r'premier league|\bepl\b|champions league|europa league|conference league|\buefa\b|'
                    r'\bfifa\b|\befl\b|fa cup|carabao cup|la ?liga|serie a|bundesliga|ligue 1', re.I)
PERFORMANCE_FIELDS = {'channel', 'post_ref', 'published_at', 'follows', 'shares', 'views', 'comments',
                      'comments_waiting', 'in_playlist', 'source'}
RANK_KEYS = ('follows', 'shares', 'views')      # the best post gained the most follows, then shares, then views
TREND_FIELDS = {'platform', 'kind', 'name', 'observed_at', 'source', 'commercial_ok'}
READING_FIELDS = {'channel', 'metric', 'value', 'observed_at', 'source', 'ref', 'account_scope'}
METRICS = ('followers', 'profile_visits')
SOURCES = ('platform_analytics', 'manual_entry')
STALE_DAYS = 3
# Expected follower gain in relative points: priors from the growth corpus
# (sections 3, 4 and 6), not measurements. The What-Works Analyst replaces them
# with measured lifts once posts are live.
GAIN = {'create_profile': 10, 'create_derived_profile': 8, 'first_hour_replies': 7, 'product_brief': 5,
        'replies': 4, 'trend_sound': 4, 'collab_prompt': 3, 'cross_promotion': 3, 'trend_hashtags': 2,
        'pin_comment': 2, 'community': 2, 'playlist': 1}


def _growth():
    import growth
    return growth


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _name(value):
    """A name safe to repeat in a message: never a credential or private data."""
    if isinstance(value, str) and NAME.match(value) and not policy.sensitive_errors(value):
        return value
    return 'an unreadable name'


def _count(value):
    return type(value) is int and value >= 0


def _date(value):
    if not isinstance(value, str) or not DATE.match(value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _day(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    raise ValueError('now must be a date or a datetime')


def _moment(value, what):
    """An aware datetime from a datetime or ISO text with its offset."""
    if isinstance(value, dt.datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            moment = None
    else:
        moment = None
    if moment is None or moment.tzinfo is None:
        raise ValueError(f'{what} must be a date and time with its offset')
    return moment


def _now(now):
    return dt.datetime.now(dt.timezone.utc) if now is None else _moment(now, 'now')


# ---------------------------------------------------------------------------
# The action registry.
# ---------------------------------------------------------------------------
def _action_errors(aid, entry, banned, today):
    if not isinstance(aid, str) or not ACTION_ID.match(aid) or policy.sensitive_errors(aid):
        return ['an action id must be a short lowercase name, never credential-like']
    where = f'action {aid}'
    if aid in BANNED or aid in banned:
        return [f'{where} is banned and can never be listed as an action']
    if not isinstance(entry, dict):
        return [f'{where} must be an object']
    out = []
    missing, unknown = ACTION_FIELDS - set(entry), set(entry) - ACTION_FIELDS
    if missing:
        out.append(f'{where} needs ' + ', '.join(sorted(missing)))
    if unknown:
        out.append(f'{where} has unknown fields: ' + ', '.join(sorted(_name(k) for k in unknown)))
    if not _text(entry.get('title')):
        out.append(f'{where} needs a title')
    platforms = entry.get('platforms')
    if (not isinstance(platforms, list) or not platforms or len(set(map(str, platforms))) != len(platforms)
            or any(p not in PLATFORMS for p in platforms)):
        out.append(f'{where} platforms must list Full Time brand platforms once each: ' + ', '.join(PLATFORMS))
    api = entry.get('official_api')
    if api is not None and not _text(api):
        out.append(f'{where} official_api must name the official API and endpoint family, or be null')
    if not _text(entry.get('rule_source')):
        out.append(f'{where} rule_source must say where the platform states its rule')
    checked_text = entry.get('rule_checked_on')
    checked = _date(checked_text)
    if checked_text != '' and checked is None:
        out.append(f'{where} rule_checked_on must be YYYY-MM-DD, or empty until a rule check is dated')
    status = entry.get('status')
    if status not in STATUSES:
        out.append(f'{where} status must be one of ' + ', '.join(STATUSES))
    ruling = entry.get('ruling')
    ruled = False
    if not isinstance(ruling, dict) or set(ruling) != RULING_FIELDS:
        out.append(f'{where} ruling must have exactly date and words, empty until Krish rules')
    elif ruling['date'] == '' and ruling['words'] == '':
        pass
    elif _date(ruling['date']) is None or not _text(ruling['words']):
        out.append(f"{where} ruling needs Krish's date (YYYY-MM-DD) and his words")
    else:
        ruled = True
        if today is not None and _date(ruling['date']) > today:
            out.append(f'{where} ruling is dated in the future')
    if not _count(entry.get('daily_cap')):
        out.append(f'{where} daily_cap must be a whole number, 0 or more')
    if type(entry.get('needs_review_each_time')) is not bool:
        out.append(f'{where} needs_review_each_time must be true or false')
    if status == 'pending' and ruled:
        out.append(f'{where} is pending, so its ruling stays empty until Krish rules')
    if status == 'approved':
        if not ruled:
            out.append(f"{where} is approved without a ruling: it needs Krish's date and words")
        if api is None:
            out.append(f'{where} is approved, but no official API supports it (any_action_without_official_api '
                       'is banned)')
        if checked is None:
            out.append(f'{where} is approved without a dated platform rule check')
        elif today is not None and not 0 <= (today - checked).days <= RULE_CHECK_DAYS:
            out.append(f'{where} rule check of {checked_text} is not within the last {RULE_CHECK_DAYS} days')
    return out


def actions_errors(data, today=None):
    """Every reason the action registry cannot be used, in plain words. With today,
    an approved action's rule check must also be at most 90 days old."""
    if not isinstance(data, dict):
        return ['the action registry must be a JSON object']
    out = []
    missing, unknown = TOP_FIELDS - set(data), set(data) - TOP_FIELDS
    if missing:
        out.append('the action registry needs ' + ', '.join(sorted(missing)))
    if unknown:
        out.append('unknown registry fields: ' + ', '.join(sorted(_name(k) for k in unknown)))
    if not _text(data.get('_about')):
        out.append('_about must say in one sentence what the file is')
    banned = data.get('banned')
    if not isinstance(banned, dict):
        out.append('banned must map each banned id to its reason')
        banned = {}
    else:
        dropped = sorted(set(BANNED) - set(banned))
        if dropped:
            out.append('banned must keep every id the code bans: ' + ', '.join(dropped))
        for bid, reason in banned.items():
            if not isinstance(bid, str) or not ACTION_ID.match(bid) or policy.sensitive_errors(bid):
                out.append('a banned id must be a short lowercase name, never credential-like')
            elif not _text(reason):
                out.append(f'banned {bid} needs its reason')
    actions = data.get('actions')
    if not isinstance(actions, dict) or not actions:
        out.append('actions must name at least one action type')
    else:
        for aid, entry in actions.items():
            out += _action_errors(aid, entry, banned, today)
    return out + policy.sensitive_errors(data)


def load_actions(path=ACTIONS_FILE, today=None):
    """The validated registry. An approved action needs Krish's ruling (date and
    words), an official API and a rule check at most 90 days before today."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except OSError as error:
        raise ValueError(f'no action registry could be read at {path}') from error
    except ValueError as error:
        raise ValueError(f'the action registry at {path} is not valid JSON') from error
    errors = actions_errors(data, dt.date.today() if today is None else _day(today))
    if errors:
        raise ValueError('the action registry was refused: ' + '; '.join(errors))
    return data


# ---------------------------------------------------------------------------
# The gate: the lint before any automated action.
# ---------------------------------------------------------------------------
def _personal(scope):
    return [f'a {scope} account is always refused: Full Time brand profiles only '
            f'(any_personal_account_action is banned)']


def _account_refusals(platform, account, allowlist):
    if isinstance(account, dict):
        if account.get('account_scope') != 'brand':
            return _personal('personal or other non-brand')
        ref = account.get('ref')
    else:
        ref = account
    if allowlist is None:
        try:
            allowlist = buffer_read.load_allowlist(ROOT / 'local')
        except ValueError as error:
            return [str(error)]
    errors = buffer_read.allowlist_errors(allowlist)
    if errors:
        safe = [e if not policy.sensitive_errors(e) else 'an entry carries credential-like content' for e in errors]
        personal = any('not a Full Time brand channel' in e for e in errors)
        out = _personal('personal or other non-brand') if personal else []
        return out + ['the brand allowlist was refused: ' + '; '.join(safe)]
    entries = allowlist['channels']
    if not isinstance(ref, str) or ref not in entries:
        return ['the account is not in the Full Time brand allowlist']
    on = spec.CHANNEL_PLATFORM.get(entries[ref]['channel'])
    if platform in PLATFORMS and on != platform:
        return [f'the account {_name(ref)} is the {on} profile, not {platform}']
    return []


def _kind_refusals(action_id, entry):
    """Every banned kind of action this one does, whatever its id: read from the id, the
    title and the official API (ruling 9: these tactics stay banned in code)."""
    title = re.sub(r'[^A-Za-z0-9]+', ' ', str(entry.get('title') or ''))
    words = ' '.join((re.sub(r'[^A-Za-z0-9]+', ' ', str(action_id)), title,
                      re.sub(r'[^A-Za-z0-9]+', ' ', str(entry.get('official_api') or ''))))
    out = []
    for kind, ban, pattern in KINDS:
        if pattern.search(words):
            why = BANNED[ban] if ban else HANDCRAFTED['schedule_story_or_community_post']
            out.append(f'{_name(action_id)} {kind}, a banned kind of action whatever its id: {why}')
    if COMMENTS.search(title) and (not OWN.search(title) or OTHERS.search(title)):
        out.append(f'{_name(action_id)} comments beyond Full Time\'s own posts, a banned kind of action whatever its '
                   f'id: {BANNED["comments_on_other_accounts_at_scale"]}')
    return out


def refusals(action_id, platform, account, now, today_count, actions=None, allowlist=None):
    """Every reason this automated action may not go ahead, leaving out the per-action
    review that gate() also needs. An empty list means only that review remains."""
    name = (action_id if isinstance(action_id, str) and ACTION_ID.match(action_id)
            and not policy.sensitive_errors(action_id) else None)
    file_banned = actions.get('banned') if isinstance(actions, dict) else None
    if name in BANNED:
        return [f'{name} is banned: {BANNED[name]}']
    if isinstance(file_banned, dict) and name in file_banned:
        return [f'{name} is banned in engagement-actions.json']
    if name is None:
        return ['the action id is not a known action type']
    day = _day(now)
    if actions is None:
        try:
            actions = load_actions(ACTIONS_FILE, day)
        except ValueError as error:
            return [str(error)]
    errors = actions_errors(actions, day)
    if errors:
        return ['the action registry was refused: ' + '; '.join(errors)]
    entry = actions['actions'].get(name)
    if entry is None:
        return [f'{name} is not in engagement-actions.json']
    out = _kind_refusals(name, entry)
    if name not in KNOWN_ACTIONS:
        out.append(f'{name} is not a kind of action this engine knows; a new kind needs a code change '
                   'and review (engine/audience.py KNOWN_ACTIONS), never only an entry in the file')
    if name in HANDCRAFTED:
        out.append(f'{name} is never automated: {HANDCRAFTED[name]}')
    if entry['status'] != 'approved':
        out.append(f'{name} is {entry["status"]}, not approved by Krish')
    if entry['ruling']['date'] == '' or not _text(entry['ruling']['words']):
        out.append(f"{name} has no ruling from Krish (his date and words)")
    checked = _date(entry['rule_checked_on'])
    if checked is None:
        out.append(f'{name} has no dated platform rule check')
    elif not 0 <= (day - checked).days <= RULE_CHECK_DAYS:
        out.append(f'{name} rule check of {entry["rule_checked_on"]} is stale: it must be within the last '
                   f'{RULE_CHECK_DAYS} days')
    if entry['official_api'] is None:
        out.append(f'{name} has no official API, so it can only be a manual task for Krish '
                   '(any_action_without_official_api is banned)')
    if platform not in PLATFORMS:
        out.append('the platform is not a Full Time brand platform: ' + ', '.join(PLATFORMS))
    elif platform not in entry['platforms']:
        out.append(f'{platform} is not listed for {name}')
    out += _account_refusals(platform, account, allowlist)
    cap = entry['daily_cap']
    if not _count(today_count):
        out.append("today_count must be the whole number of these actions taken today")
    elif today_count >= cap:
        out.append(f'the daily cap is reached: {today_count} of {cap} today')
    return out


def gate(action_id, platform, account, now, today_count, actions=None, allowlist=None, review_ref=None):
    """None when this automated action may go ahead; otherwise ValueError with every reason.

    account is an allowlist ref (local/buffer-channels.json, engine/buffer_read.py) or
    {"ref", "account_scope"}; a personal account is always refused. An action that
    needs review each time also needs review_ref, the reference of Krish's review."""
    if actions is None:
        try:
            actions = load_actions(ACTIONS_FILE, _day(now))
        except ValueError as error:
            raise ValueError('the action was refused: ' + str(error)) from None
    reasons = refusals(action_id, platform, account, now, today_count, actions, allowlist)
    entry = None
    if isinstance(actions, dict) and isinstance(actions.get('actions'), dict):
        entry = actions['actions'].get(action_id) if isinstance(action_id, str) else None
    if isinstance(entry, dict) and entry.get('needs_review_each_time') is not False and not _text(review_ref):
        reasons.append('Krish reviews each one first: pass the reference of his review of this exact action')
    if review_ref is not None and policy.sensitive_errors(review_ref):
        reasons.append('the review reference carries credential-like content')
    if reasons:
        raise ValueError('the action was refused: ' + '; '.join(reasons))
    return None


# ---------------------------------------------------------------------------
# One profile's findability.
# ---------------------------------------------------------------------------
def _profile_checked(platform, profile):
    if platform not in PLATFORMS:
        raise ValueError('channel must be one of ' + ', '.join(PLATFORMS))
    if not isinstance(profile, dict):
        raise ValueError(f'the {LABEL[platform]} profile must be an object, or None before the handle exists')
    if profile.get('account_scope') != 'brand':
        raise ValueError('personal accounts are never audited or changed: Full Time brand profiles only')
    out = []
    missing, unknown = PROFILE_REQUIRED - set(profile), set(profile) - PROFILE_FIELDS
    if missing:
        out.append('it needs ' + ', '.join(sorted(missing)))
    if unknown:
        out.append('unknown fields: ' + ', '.join(sorted(_name(k) for k in unknown)))
    for key in ('name', 'handle', 'bio'):
        if key in profile and not isinstance(profile[key], str):
            out.append(f'{key} must be text')
    for key in ('link', 'pinned_post'):
        if profile.get(key) is not None and not isinstance(profile[key], str):
            out.append(f'{key} must be text or null')
    if profile.get('avatar_sha256') is not None and not SHA.match(str(profile['avatar_sha256'])):
        out.append('avatar_sha256 must be the 64-character SHA-256 of the avatar, or null')
    links = profile.get('cross_links', [])
    if not isinstance(links, list) or any(p not in PLATFORMS for p in links):
        out.append('cross_links must list brand platforms: ' + ', '.join(PLATFORMS))
    if 'ai_disclosure' in profile and type(profile['ai_disclosure']) is not bool:
        out.append('ai_disclosure must be true or false')
    marks = profile.get('image_marks', [])
    if not isinstance(marks, list) or not all(_text(m) for m in marks):
        out.append('image_marks must list the marks a review found in the avatar or banner')
    out += policy.sensitive_errors(profile)
    if out:
        raise ValueError(f'the {LABEL[platform]} profile was refused: ' + '; '.join(out))
    return profile


def _fix(check, fix, points, minutes, must=False, action_id=None):
    return {'check': check, 'fix': fix, 'points': points, 'minutes': minutes, 'must': must, 'action_id': action_id}


def _common(values):
    """The most common value, ties going to the first in platform order."""
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return max(counts, key=lambda v: (counts[v], -values.index(v))) if counts else None


def _link_fix(platform, link):
    growth = _growth()
    prefix = spec.CHANNEL_PREFIX[PROFILE_CHANNEL[platform]]
    try:
        growth.tracked(growth.SITE + '/', f'{prefix}_TRIBE_POST_C01_H01_V1_20261101')
    except (ValueError, KeyError):
        return _fix('link', f'growth.py has no {prefix} creative ID code yet, so the {LABEL[platform]} profile link '
                    'cannot be tracked: brief the engine to add it', 4, 1)
    want = (f'Set the {LABEL[platform]} profile link to a tracked Full Time link with a {prefix}_ creative ID '
            f'(python3 growth.py link {growth.SITE}/ <creative ID>)')
    site = re.escape(growth.SITE).replace('://', r'://(?:www\.)?')
    found = re.search(r'[?&]utm_content=([^&#]*)', link) if isinstance(link, str) else None
    cid = found.group(1) if found else ''
    matched = growth.CREATIVE_ID.match(cid)
    if (not isinstance(link, str) or not re.match(site + r'(?:[/?#]|$)', link) or not matched
            or matched.group(1) != prefix or link != growth.tracked(link, cid)):
        return _fix('link', want, 4, 1, action_id='update_profile_bio_and_links')
    return None


def _performance_checked(performance):
    out = []
    for reading in performance or []:
        if not isinstance(reading, dict):
            raise ValueError('each performance reading must be an object')
        unknown = set(reading) - PERFORMANCE_FIELDS
        if unknown:
            raise ValueError('unknown performance fields: ' + ', '.join(sorted(_name(k) for k in unknown)))
        if reading.get('channel') not in PLATFORMS or not _text(reading.get('post_ref')):
            raise ValueError('a performance reading needs a brand channel and a post_ref')
        for key in ('follows', 'shares', 'views', 'comments', 'comments_waiting'):
            if reading.get(key) is not None and not _count(reading[key]):
                raise ValueError(f'{key} must be a whole number or null (null is missing, not zero)')
        if reading.get('in_playlist') is not None and type(reading['in_playlist']) is not bool:
            raise ValueError('in_playlist must be true, false or null')
        if policy.sensitive_errors(reading):
            raise ValueError('a performance reading carries credential-like or private content')
        out.append(dict(reading, published_at=_moment(reading.get('published_at'), 'published_at')))
    return out


def _within(moment, now, days=None, hours=None):
    span = dt.timedelta(days=days or 0, hours=hours or 0)
    return now - span <= moment <= now


def _best_post(platform, performance, now):
    scored = [r for r in performance if r['channel'] == platform and _within(r['published_at'], now, BEST_DAYS)
              and any(r.get(k) is not None for k in RANK_KEYS)]
    if not scored:
        return None
    return max(scored, key=lambda r: (tuple(-1 if r.get(k) is None else r[k] for k in RANK_KEYS), r['post_ref']))


def _checklist(platform, profile, others, performance, now):
    growth = _growth()
    name, handle, bio = profile['name'], profile['handle'], profile['bio']
    out = []
    if 'Full Time' not in name:
        out.append(_fix('name', f'Put "Full Time" in the {LABEL[platform]} profile name, so a search for Full Time '
                        'finds it', 6, 1))
    found = growth.BROADCASTERS.search(' '.join((name, handle, bio))) or LEAGUE.search(' '.join((name, handle)))
    if found or profile.get('image_marks'):
        seen = f'it shows "{found.group(0)}"' if found else 'the avatar or banner carries one'
        out.append(_fix('marks', f'Remove the league or broadcaster mark from the {LABEL[platform]} profile: {seen}',
                        6, 3, must=True))
    if profile.get('ai_disclosure') is not True and not re.search(r'\bAI\b', bio):
        out.append(_fix('ai_disclosure', f'Say it is AI on the {LABEL[platform]} profile: "AI Pundit" in the bio '
                        'does it', 5, 1, must=True))
    line = bio.strip().splitlines()[0].strip() if bio.strip() else ''
    why = []
    if 'AI Pundit' not in line:
        why.append('say "AI Pundit", exactly, in its first line')
    if len(line) > BIO_LINE:
        why.append(f'keep that line to {BIO_LINE} characters')
    if growth.EM_DASH.search(bio):
        why.append('take out the em dash')
    if why:
        out.append(_fix('bio', f'Make the {LABEL[platform]} bio say what Full Time is in one line: ' + ', '.join(why)
                        + ' (Codex drafts the copy; Krish pastes it)', 5, 2, action_id='update_profile_bio_and_links'))
    link = _link_fix(platform, profile['link'])
    if link:
        out.append(link)
    everyone = [p for p in (dict(others, **{platform: profile}).get(q) for q in PLATFORMS) if p is not None]
    handles = [p['handle'].lower().lstrip('@') for p in everyone if p['handle'].strip()]
    canon = _common(handles)
    if not handle.strip() or (len(handles) > 1 and handle.lower().lstrip('@') != canon):
        out.append(_fix('handle', f'Use the same handle as the other brand profiles on {LABEL[platform]}'
                        + (f': @{canon}' if canon else ''), 4, 2))
    avatars = [p.get('avatar_sha256') for p in everyone if p.get('avatar_sha256')]
    if not profile.get('avatar_sha256'):
        out.append(_fix('avatar', f'Set the Full Time avatar on {LABEL[platform]}', 3, 1))
    elif len(avatars) > 1 and profile['avatar_sha256'] != _common(avatars):
        out.append(_fix('avatar', f'Use the same avatar on {LABEL[platform]} as on the other brand profiles', 3, 1))
    best = _best_post(platform, performance, now) if platform in PIN_POST else None
    if best and profile.get('pinned_post') != best['post_ref']:
        out.append(_fix('pinned_post', f'Pin {best["post_ref"]} on {LABEL[platform]}: the best post of the last '
                        f'{BEST_DAYS} days', 3, 1, action_id='rotate_pinned_post'))
    missing = [LABEL[p] for p in PLATFORMS if p in others and p not in profile.get('cross_links', [])]
    if missing:
        out.append(_fix('cross_links', f'Link the other brand profiles from {LABEL[platform]}: ' + ', '.join(missing),
                        2, 2, action_id='crosslink_profiles'))
    return sorted(out, key=lambda f: (not f['must'], -f['points'], f['check']))


def _profiles_checked(profiles):
    if profiles is None:
        return {}
    if not isinstance(profiles, dict) or any(p not in PLATFORMS for p in profiles):
        raise ValueError('profiles must map brand platforms to profiles: ' + ', '.join(PLATFORMS))
    return {p: _profile_checked(p, v) for p, v in profiles.items() if v is not None}


def profile_checklist(channel, profile, profiles=None, performance=None, now=None):
    """The fixes that make one Full Time brand profile findable, rule fixes first and then
    most findability points: [{check, fix, points, minutes, must, action_id}].

    profiles (every brand profile, by platform) is used for handle, avatar and cross-link
    consistency, and performance (post readings) for the pinned post. None as the profile
    means the handle does not exist yet."""
    if channel not in PLATFORMS:
        raise ValueError('channel must be one of ' + ', '.join(PLATFORMS))
    if profile is None:
        return [_fix('create', f'Create the Full Time {LABEL[channel]} handle (ruling 2: every handle is reserved)',
                     10, 5)]
    _profile_checked(channel, profile)
    others = {p: v for p, v in _profiles_checked(profiles).items() if p != channel}
    return _checklist(channel, profile, others, _performance_checked(performance), _now(now))


# ---------------------------------------------------------------------------
# The day's visibility work.
# ---------------------------------------------------------------------------
def _trends_checked(trends, now):
    growth = _growth()
    out = []
    for trend in trends or []:
        if not isinstance(trend, dict) or set(trend) - TREND_FIELDS:
            raise ValueError('a trend has platform, kind, name, observed_at, source and, for a sound, commercial_ok')
        if trend.get('platform') not in PLATFORMS or trend.get('kind') not in ('sound', 'hashtag'):
            raise ValueError('a trend needs a brand platform and a kind of sound or hashtag')
        if not _text(trend.get('name')) or not _text(trend.get('source')):
            raise ValueError('a trend needs its name and the source it was read from')
        if trend['kind'] == 'hashtag' and not TAG.match(trend['name']):
            raise ValueError('a trending hashtag is one word starting "#"')
        if trend['kind'] == 'sound' and type(trend.get('commercial_ok')) is not bool:
            raise ValueError('a trending sound needs commercial_ok: brand accounts use the commercial library only')
        if policy.sensitive_errors(trend):
            raise ValueError('a trend carries credential-like or private content')
        moment = _moment(trend.get('observed_at'), 'observed_at')
        if (_within(moment, now, hours=TREND_HOURS) and not growth.BROADCASTERS.search(trend['name'])
                and not growth.BETTING.search(trend['name'])):
            out.append(dict(trend, observed_at=moment))
    return sorted(out, key=lambda t: (-t['observed_at'].timestamp(), t['name']))


def _item(tactic, platform, what, minutes, gain, action_id=None, must=False):
    return {'tactic': tactic, 'platform': platform, 'what': what, 'who': 'krish', 'action_id': action_id,
            'minutes': minutes, 'expected_gain': gain, 'gain_basis': 'prior', 'must': must}


def _automated(item, actions, allowlist, counts, now):
    """The item as an approved automated action when the gate clears it, else unchanged."""
    aid, platform = item['action_id'], item['platform']
    if aid is None or allowlist is None or platform not in PLATFORMS or buffer_read.allowlist_errors(allowlist):
        return item
    refs = sorted(ref for ref, entry in allowlist['channels'].items()
                  if spec.CHANNEL_PLATFORM.get(entry['channel']) == platform)
    for ref in refs:
        if not refusals(aid, platform, ref, now, (counts or {}).get(aid, 0), actions, allowlist):
            review = actions['actions'][aid]['needs_review_each_time']
            return dict(item, who='automated', minutes=1 if review else 0,
                        what=item['what'] + ' (through its approved official-API adapter'
                        + (', after Krish reviews it)' if review else ')'))
    return item


def _cross_promotion(best, created):
    """A derived card for the next G2 matchday pack, never a post of its own (ruling 3):
    Krish publishes pack items only once G2 clears them, and the WhatsApp Channel by hand."""
    names = [LABEL[p] for p in PLATFORMS if p in created and p != best['channel'] and p not in pack.BY_HAND]
    hand = [LABEL[p] for p in PLATFORMS if p in created and p != best['channel'] and p in pack.BY_HAND]
    targets = ', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else ''.join(names)
    where = (f'for {targets}' if names else '') + (' and, by hand, ' if names and hand else 'for, by hand, ' if hand
                                                   else '') + ' and '.join(f'the {h}' for h in hand)
    return (f'Add a derived card pointing at {best["post_ref"]}, the best {LABEL[best["channel"]]} post of the last '
            f'{BEST_DAYS} days, to the next G2 matchday pack {where}: it goes out only as a pack item that clears '
            'G2, never as a post of its own')


def _candidates(created, performance, trends, product_brief_sent, now):
    out = [_item('create_profile', p, f'Create the Full Time {LABEL[p]} handle (ruling 2: every handle is reserved)',
                 5, GAIN['create_profile' if p in PUSH else 'create_derived_profile'])
           for p in PLATFORMS if p not in created]
    for platform, profile in created.items():
        others = {p: v for p, v in created.items() if p != platform}
        for fix in _checklist(platform, profile, others, performance, now):
            out.append(_item('profile_fix', platform, fix['fix'], fix['minutes'], fix['points'], fix['action_id'],
                             fix['must']))
    for r in performance:
        waiting = r.get('comments_waiting') or 0
        if r['channel'] in created and waiting > 0 and _within(r['published_at'], now, 1):
            first = _within(r['published_at'], now, hours=1)
            tactic = 'first_hour_replies' if first else 'replies'
            out.append(_item(tactic, r['channel'], f'Reply to {waiting} fan comments on {r["post_ref"]} on '
                             f'{LABEL[r["channel"]]}' + (', now, inside its first hour' if first
                                                         else ', and inside the first hour next time'),
                             min(10, 2 + waiting // 5), GAIN[tactic], 'reply_to_comments_on_own_posts'))
    for platform in PIN_COMMENT:
        best = _best_post(platform, performance, now) if platform in created else None
        if best and (best.get('comments') or 0) > 0:
            out.append(_item('pin_comment', platform, f'Pin the best fan comment on {best["post_ref"]}, the best '
                             f'{LABEL[platform]} post of the last {BEST_DAYS} days', 1, GAIN['pin_comment'],
                             'pin_best_comment_on_own_post'))
    for platform, where in PLAYLIST.items():
        refs = sorted(r['post_ref'] for r in performance if r['channel'] == platform and platform in created
                      and r.get('in_playlist') is False and _within(r['published_at'], now, PLAYLIST_DAYS))
        if refs:
            out.append(_item('playlist', platform, f'Add {", ".join(refs)} to {where} on {LABEL[platform]}',
                             1 + len(refs) // 3, GAIN['playlist'], 'add_post_to_playlist_or_highlight'))
    bests = [b for b in (_best_post(p, performance, now) for p in created) if b]
    if len(created) > 1 and bests:
        best = max(bests, key=lambda r: (tuple(-1 if r.get(k) is None else r[k] for k in RANK_KEYS), r['post_ref']))
        out.append(_item('cross_promotion', best['channel'], _cross_promotion(best, created), 3,
                         GAIN['cross_promotion']))
    for platform in SOUND:
        sounds = [t for t in trends if t['platform'] == platform and t['kind'] == 'sound' and t['commercial_ok']]
        if platform in created and sounds:
            out.append(_item('trend_sound', platform, f'Use the trending sound "{sounds[0]["name"]}" on the next '
                             f'{LABEL[platform]} take where it fits (commercial library only on a brand account)',
                             2, GAIN['trend_sound']))
    for platform in HASHTAGS:
        tags = []
        for t in trends:
            if t['platform'] == platform and t['kind'] == 'hashtag' and t['name'].lower() not in map(str.lower, tags):
                tags.append(t['name'])
        if platform in created and len(tags) >= 2:
            out.append(_item('trend_hashtags', platform, f'Give the next {LABEL[platform]} pack these trending '
                             f'hashtags where they fit the take: {" ".join(tags[:5])}', 1, GAIN['trend_hashtags']))
    remix = next((p for p in REMIX if p in created), None)
    if remix:
        out.append(_item('collab_prompt', remix, f'Allow {REMIX[remix]} on the next {LABEL[remix]} take clip and make '
                         'its one call to action an open ask for fan creators to answer with their own call: an ask '
                         'only, never a DM, a cold pitch or a payment', 2, GAIN['collab_prompt']))
    if created:
        out.append(_item('community', None, 'Take part by hand in one fan community as a Full Time brand profile: read '
                         'and log its written rules first, add to the conversation, post no link its rules do not '
                         'allow, and keep promotion under one post in ten', 10, GAIN['community']))
    if not product_brief_sent:
        out.append(_item('product_brief', None, 'Approve a brief to full-time for a follow prompt in the app after a '
                         'show ends, linking the brand profiles (Claude drafts it; it is never built here)', 3,
                         GAIN['product_brief']))
    return out


def daily_plan(profiles, performance, trends, budget_minutes=10, actions=None, allowlist=None, counts=None,
               product_brief_sent=False, now=None):
    """The day's visibility actions inside Krish's minutes: rule fixes first, then the
    highest expected follower gain. Each item is {rank, tactic, platform, what, who
    ('krish' or 'automated'), action_id, minutes, expected_gain, gain_basis, must}.

    An item becomes 'automated' only when gate() would clear its approved action type
    for an allowlisted brand account (review aside); every other item is Krish's, by
    hand. Expected gains are priors in relative points, not measured followers."""
    if type(budget_minutes) not in (int, float) or budget_minutes < 0:
        raise ValueError('budget_minutes must be a number of minutes, 0 or more')
    if counts is not None and (not isinstance(counts, dict) or not all(_count(v) for v in counts.values())):
        raise ValueError('counts must map action ids to the whole number taken today')
    moment = _now(now)
    created = _profiles_checked(profiles)
    if actions is None:
        actions = load_actions(ACTIONS_FILE, moment)
    elif actions_errors(actions, moment.date()):
        raise ValueError('the action registry was refused: ' + '; '.join(actions_errors(actions, moment.date())))
    items = [_automated(item, actions, allowlist, counts, moment)
             for item in _candidates(created, _performance_checked(performance), _trends_checked(trends, moment),
                                     product_brief_sent, moment)]
    items.sort(key=lambda i: (not i['must'], -i['expected_gain'], i['minutes'], i['tactic'],
                              PLATFORMS.index(i['platform']) if i['platform'] else len(PLATFORMS), i['what']))
    plan, used = [], 0
    for item in items:
        if used + item['minutes'] <= budget_minutes:
            used += item['minutes']
            plan.append(dict(item, rank=len(plan) + 1))
    return plan


# ---------------------------------------------------------------------------
# The measured check after acting.
# ---------------------------------------------------------------------------
def _readings_checked(readings, now):
    seen = {}
    for reading in readings or []:
        if not isinstance(reading, dict):
            raise ValueError('each reading must be an object')
        missing = {'channel', 'metric', 'value', 'observed_at', 'source'} - set(reading)
        if missing:
            raise ValueError('a reading needs ' + ', '.join(sorted(missing)))
        unknown = set(reading) - READING_FIELDS
        if unknown:
            raise ValueError('unknown reading fields: ' + ', '.join(sorted(_name(k) for k in unknown)))
        if reading.get('account_scope', 'brand') != 'brand':
            raise ValueError('personal accounts are never read: Full Time brand profiles only')
        if reading['channel'] not in PLATFORMS:
            raise ValueError('a reading channel must be one of ' + ', '.join(PLATFORMS))
        if reading['metric'] not in METRICS:
            raise ValueError('a reading metric must be one of ' + ', '.join(METRICS))
        if not _count(reading['value']):
            raise ValueError('a reading value is a whole number, 0 or more: leave a missing reading out')
        if reading['source'] not in SOURCES:
            raise ValueError('a reading source must be one of ' + ', '.join(SOURCES))
        if reading.get('ref') is not None and not _text(reading['ref']):
            raise ValueError('ref must be text naming the query or capture, or be left out')
        if policy.sensitive_errors(reading):
            raise ValueError('a reading carries credential-like or private content')
        moment = _moment(reading['observed_at'], 'observed_at')
        if moment > now:
            raise ValueError('a reading is dated in the future')
        key = (reading['channel'], reading['metric'], moment)
        if key in seen and seen[key]['value'] != reading['value']:
            raise ValueError(f'two {reading["channel"]} {reading["metric"]} readings at {moment.isoformat()} disagree')
        seen[key] = dict(reading, observed_at=moment)
    return list(seen.values())


def _change(rows, now):
    out = {'status': 'missing', 'change': None, 'latest': None, 'latest_at': None, 'week_before': None,
           'week_before_at': None, 'sources': [], 'reason': 'no reading'}
    if not rows:
        return out
    latest = max(rows, key=lambda r: r['observed_at'])
    out.update(latest=latest['value'], latest_at=latest['observed_at'].isoformat(), sources=[latest['source']])
    week = dt.timedelta(days=7)
    near = [r for r in rows if dt.timedelta(days=6) <= latest['observed_at'] - r['observed_at'] <= dt.timedelta(days=8)]
    if not near:
        out['reason'] = 'no reading about a week before the latest'
        return out
    before = min(near, key=lambda r: (abs(latest['observed_at'] - r['observed_at'] - week), r['observed_at']))
    age = (now - latest['observed_at']).days
    out.update(change=latest['value'] - before['value'], week_before=before['value'],
               week_before_at=before['observed_at'].isoformat(),
               sources=sorted({latest['source'], before['source']}),
               status='stale' if age > STALE_DAYS else 'measured',
               reason=f'the latest reading is {age} days old' if age > STALE_DAYS else None)
    return out


def followers_check(readings, now=None):
    """The weekly follower and profile-visit change per brand channel, from platform
    analytics or a manual entry. A missing change is None with its reason, never 0;
    a measured 0 is status 'measured'. Follower readings are totals at observed_at,
    profile-visit readings the 7-day count the platform reports at observed_at.

    This is a diagnostic of distribution capacity. The North Star (share-arrived new
    listeners) is unchanged and is never read from these numbers."""
    moment = _now(now)
    rows = _readings_checked(readings, moment)
    return [{'channel': p, **{m: _change([r for r in rows if r['channel'] == p and r['metric'] == m], moment)
                              for m in METRICS}} for p in PLATFORMS]
