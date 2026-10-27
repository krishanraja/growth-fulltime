#!/usr/bin/env python3
"""The Full Time growth engine's one tool: stay current with the full-time
repository and the live product, check every draft against Full Time's own
claim and voice rules, hold every push until the rail is full enough to be
worth a fan's first listen, and leave a pack of drafts where Krish can work it.

Standard library only. Runs anywhere Python 3.9+ and git run (a Codex
session, a Cowork session, a Mac, a GitHub Action). Nothing here posts,
sends, comments, follows, DMs, uploads, boosts or spends. The only writes are
this engine's own files under local/ (and state/ when a GitHub Action
publishes it), private exports, and the run's own attempts and reports to
Control Center through its growth engine protocol (growth.py cc).

    python3 growth.py sync [--publish]
        Read krishanraja/full-time as it is right now: the commit on main,
        what changed since the last sync, open pull requests, the canon its
        docs index routes marketing agents to, the decision log, and the live
        rail at fulltime.fm (which matches have shows, and which of the six AI
        Pundits made one). Writes local/state/fulltime.json and
        local/state/FULLTIME-NOW.md (--publish writes state/ instead, for the
        GitHub Action that keeps the repository's copy current). Every job
        starts here.

    python3 growth.py canon [--full]
        The canon documents at the synced commit, in order. --full prints
        them: the only source of product facts besides the live site.

    python3 growth.py rail
        The live rail: every match with a published show, how many of the six
        AI Pundits made one, and whether today is a push day.

    python3 growth.py link URL CREATIVE_ID
        The fulltime.fm url with the tracking every draft must carry, built
        from the creative id (PLAYBOOK.md, "Creative ids").

    python3 growth.py check PACK.json
        Full Time's rules on every draft, the creative ids and links, the
        rail gate, the rulings gate, and that the pack was written against
        today's full-time (no canon change since the sync it names). Exit 1
        names everything wrong.

    python3 growth.py post PACK.json
        Checks and stores locally with durable history and a handoff export.
        No remote request is made; this is never dashboard delivery.

    python3 growth.py read [--days 7] [--kind daily]
        The packs already stored, newest first (for the Monday report).

    python3 growth.py doctor
        Is this machine ready? Exit 1 names what is not, with the fix.

    python3 growth.py --self-test

A pack file:
    {"pack_date": "2026-10-19", "kind": "daily", "venture": "fulltime",
     "fulltime_sha": "<the sha sync printed>",
     "headline": "Monday: Palace 3-1 Forest, rail 5 of 6: clip, 3 editions, 6 invites",
     "items": [{"platform": "tiktok", "creative_id": "TT_CLASH_CLIP_C01_H02_V1_20261019",
                "target_url": "", "target_name": "", "why": "...", "text": "...",
                "needs": ""}],
     "numbers": null}

An item's "needs" is empty when it can go out today, a ruling id ("D1" to
"D7") when its channel waits on that ruling, or "RAIL" when it is ready but
waits for a full rail. A held item is still checked for every copy rule.

Kinds: daily, radar, numbers, conversion, report.
Operations: run, history, creative, experiment, metrics, assets, export, cc.
Environment: GITHUB_TOKEN optionally raises GitHub's read limit;
CONTROL_CENTER_ENGINE_TOKEN (or local/control-center/token) and
CONTROL_CENTER_URL are read only by growth.py cc. Packs stay local.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import math
from pathlib import Path
from engine import policy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = 'krishanraja/full-time'
BRANCH = 'main'
SITE = 'https://fulltime.fm'
TODAY_API = SITE + '/api/public/drops/today'
FEED = SITE + '/api/public/feed.rss'
RAW = 'https://raw.githubusercontent.com/' + REPO
API = 'https://api.github.com/repos/' + REPO
UA = {'User-Agent': 'growth-fulltime (+https://github.com/krishanraja/growth-fulltime)'}
LOCAL = os.path.join(HERE, 'local')

KINDS = ('daily', 'radar', 'numbers', 'conversion', 'report')
# 'whatsapp' is a listener sharing a link of their own accord; 'whatsapp_channel' is
# Full Time's own brand broadcast, which Krish posts by hand (ruling 2 of 27 October).
PLATFORMS = ('invite', 'whatsapp', 'email', 'tiktok', 'youtube', 'instagram', 'x', 'reddit',
             'threads', 'facebook', 'whatsapp_channel',
             'linkedin', 'hn', 'producthunt', 'press', 'creator', 'ads', 'fpl', 'site', 'other')

# The six AI Pundits: the product's ids and their public names (docs/01-brand.md).
PUNDITS = {'zen': 'The Reporter', 'gaffer': 'The Gaffer', 'stats': 'The Numbers Guy',
           'romantic': 'The Romantic', 'doomer': 'The Doomer', 'banter': 'The Wind-Up'}

# The rail gate. A push sends a fan to a match only when at least this many of
# the six AI Pundits made a show for it: the playbook's kill switch ("fewer
# than 4 of 6 pundits by 07:00: hold that day's push") and the December bar's
# "a median of four of the six" (full-time docs/22-vision-and-beta.md).
RAIL_MIN = 4

# ---------------------------------------------------------------------------
# What full-time says a marketing agent must read. Its docs index routes each
# task to its documents; these rows are followed, in this order, so a change
# to the index changes what the engine reads. The always-read files follow.
# ---------------------------------------------------------------------------
ROUTE_ROWS = ('Know where it is going', 'Market the live beta', 'Explain the product',
              'Know where it is right now')
ALWAYS_CANON = ('docs/product-state.json', 'docs/22-vision-and-beta.md', 'docs/21-go-to-market-agent.md',
                'docs/07-marketing.md', 'docs/01-brand.md', 'docs/00-product.md', 'docs/09-growth.md',
                'docs/11-legal.md', 'docs/12-roadmap.md', 'NOW.md', 'AGENTS.md')

# The sections of full-time's canon that the RULES below were written from,
# with their fingerprint at full-time commit 319d324 (16 Oct 2026). If any
# changes, or stops being canon, no pack passes until a person reads the new
# words and updates RULES and RULES_BASIS in an interactive session.
RULES_SOURCES = (
    ('docs/01-brand.md', '## Voice'),                           # words, filler, internal terms
    ('docs/01-brand.md', '## Review checklist'),                # marks, betting, living pundits
    ('docs/07-marketing.md', '## Copy bank'),                   # the avoid list
    ('docs/07-marketing.md', '## Current promise boundaries'),  # what may not be claimed
    ('docs/07-marketing.md', '## Release gate'),                # invited testers only, until the bar
    ('docs/21-go-to-market-agent.md', '## Autonomy boundary'),  # draft, never act
    ('docs/21-go-to-market-agent.md', '## Final gate'),         # the asset test
    ('docs/22-vision-and-beta.md', '## The pilot beta'),        # who, how, the inbox
    ('docs/22-vision-and-beta.md', '## The December release bar'),
    ('docs/product-state.json', 'commercialState'),             # available now, and not
    ('docs/product-state.json', 'claims'),
)
RULES_BASIS = {
    'docs/01-brand.md ## Voice': 'b918bf0fa1f8c81f',
    'docs/01-brand.md ## Review checklist': 'ba12511d5958b8b4',
    'docs/07-marketing.md ## Copy bank': '188f71fba7053425',
    'docs/07-marketing.md ## Current promise boundaries': '65189ede4031b54e',
    'docs/07-marketing.md ## Release gate': 'a031d5892eb1c5c1',
    'docs/21-go-to-market-agent.md ## Autonomy boundary': 'caceb8bda193b0e3',
    'docs/21-go-to-market-agent.md ## Final gate': '2a29c238153db173',
    'docs/22-vision-and-beta.md ## The pilot beta': 'dca94cccd872cc16',
    'docs/22-vision-and-beta.md ## The December release bar': '4c4f0672a14407bd',
    'docs/product-state.json commercialState': '93b4389fcdd995a9',
    'docs/product-state.json claims': '7cedc8282c3b45eb',
}

# ---------------------------------------------------------------------------
# Full Time's rules, from the sections above. Each line says where.
# ---------------------------------------------------------------------------
EM_DASH = re.compile('\u2014')                                          # Krish's kill list
FILLER = ['game-changing', 'game changing', 'game-changer', 'game changer', 'next-generation',
          'next generation', 'must-listen', 'must listen', 'unmissable', 'unbiased', 'seamless',
          'revolutionary', 'ai-powered', 'ai powered']                  # 01-brand Voice, 07 Copy bank
SLOP = ['delve', "in today's", 'in a world where', "it's worth noting", 'unlock', 'harness the',
        'leverage', 'robust', 'tapestry', 'realm', 'cutting-edge', 'revolutionize', 'revolutionise',
        'transformative', 'synergy', 'buckle up', 'look no further', 'a testament to', 'elevate',
        'unleash']                                                      # Krish's kill list
AVOID = [  # 07 Copy bank, "Avoid"
    (re.compile(r'\bAI[- ](?:character|host|presenter|commentator|voice actor)s?\b', re.I),
     'says an AI character, host or presenter: the public term is AI Pundit (01-brand)'),
    (re.compile(r'\bpersonal (?:ai )?(?:pundit|show|podcast|gary)|your own (?:ai )?(?:show|pundit|podcast)|'
                r'made (?:just )?for you\b|personali[sz]ed (?:ai )?(?:show|pundit|podcast|feed|playlist)|club playlist', re.I),
     'promises a personal show or playlist, which does not exist yet (07 promise boundaries)'),
    (re.compile(r'big five', re.I), 'promises Big Five coverage (07 Copy bank)'),
    (re.compile(r'every (?:single )?(?:premier league )?(?:day|morning|match|game|weekend)\b|'
                r'daily (?:show|without fail)|without fail|never miss', re.I),
     'promises daily or every-match shows, which are not a promise (07 promise boundaries, product-state notAvailable)'),
    (re.compile(r'guaranteed|accura(?:te|cy)|called it|track record|predicted (?:it|correctly)|beat the bookies|'
                r'\d+\s?% (?:right|correct)', re.I),
     'claims prediction performance or a guarantee (07 promise boundaries, product-state notAvailable)'),
    (re.compile(r'\bdecember\b|launch date|launching (?:on|in|this|next)|release date|coming soon', re.I),
     'names a launch or release time (07 promise boundaries: no guaranteed date)'),
    (re.compile(r'subscri(?:be|ption) (?:for|to pro)|\bpro plan\b|free forever|\bpaid plan\b', re.I),
     'promises a paid plan or a price (07 promise boundaries)'),
]
BETTING = re.compile(r'\b(?:betting|acca|accumulators?|bookies?|bookmakers?|wager|punters?|bet ?slips?|'
                     r'tipsters?|bet on|odds-on)\b|(?<!against )(?<!against the )(?<!against all )\bodds\b', re.I)
LIVING_PUNDITS = ['gary neville', 'jamie carragher', 'roy keane', 'micah richards', 'gary lineker', 'alan shearer',
                  'ian wright', 'rio ferdinand', 'jamie redknapp', 'peter crouch', 'chris sutton', 'paul merson',
                  'graeme souness', 'jermaine jenas', 'thierry henry', 'alex scott', 'karen carney', 'troy deeney',
                  'daniel sturridge', 'joe cole', 'wayne rooney', 'clinton morrison']   # 01-brand checklist
BROADCASTERS = re.compile(r'match of the day|\bmotd\b|sky sports|tnt sports|bbc sport|monday night football|'
                          r'talksport|the overlap|stick to football', re.I)            # 01-brand Assets
INTERNAL_TERMS = re.compile(r'calibrat|brier|\bvariance\b|\bharness(?:es)?\b|\bbaseline\b|\bledger\b|'
                            r'synthetic profile|probabilistic|evidence pack', re.I)    # 01-brand Voice
FAKE_PROOF = [
    (re.compile(r'#1\b|number one|best (?:football )?(?:podcast|show|app)|most popular|loved by|fans love|'
                r'listeners love|thousands of|millions of', re.I),
     'claims proof Full Time does not have (no audience, ranking or reaction figure is approved: 07 Proof order)'),
    (re.compile(r'\b\d[\d,.]*k?\+?\s+(?:listeners|users|fans|downloads|plays|subscribers|testers|followers)\b', re.I),
     'states an audience figure (none is approved for public copy: 07 Proof order)'),
    (re.compile(r'limited (?:time|spots|places)|only \d+ (?:spots|places|left)|spots left|hurry|last chance|'
                r'ends (?:tonight|soon|today)|don\'?t miss out|\bfomo\b', re.I),
     'manufactures urgency (07 Release gate: do not manufacture urgency)'),
]
NOT_BUT = re.compile(r"\b(?:it'?s|this is|that'?s)\s+not\s+(?:just\s+|only\s+|about\s+)?[^.;:!?]{1,60}[,;]\s*(?:it'?s|but)\b"
                     r"|\bisn'?t\s+(?:just|only)\b", re.I)                 # Krish's kill list
US = [(re.compile(r'(?<!r/)\bsoccer\b', re.I), 'football'), (re.compile(r'\bcolor', re.I), 'colour'),
      (re.compile(r'\bfavorite', re.I), 'favourite'), (re.compile(r'\bhumor\b', re.I), 'humour'),
      (re.compile(r'\bflavor', re.I), 'flavour')]                       # UK fans, UK English
WRONG_NAMES = [(re.compile(r'\bwind[ ]up\b|\bwindup\b', re.I), 'The Wind-Up (with the hyphen)'),
               (re.compile(r'\bstats guy\b|\bnumbers man\b', re.I), 'The Numbers Guy'),
               (re.compile(r'\bthe doom(?:ster|monger)\b', re.I), 'The Doomer')]   # 01-brand pundit names
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
CONTACT = 'krish@fulltime.fm'                                           # 22 pilot beta: the product inbox
EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27bf]')
HASHTAG = re.compile(r'(?<![\w&/])#\w+')
CURRENCY = re.compile(r'[£$€]\s?\d')
LIMITS = {'x': 280, 'whatsapp': 700, 'invite': 900, 'instagram': 2200, 'tiktok': 2200, 'youtube': 5000,
          'reddit': 3000, 'linkedin': 3000, 'threads': 500}

# Channels that tell the build story to AI and tech readers under Krish's name
# may use internal terms and the measured cost per run; fan channels may not.
BUILD = ('linkedin', 'hn', 'producthunt', 'press')
# Public posts must say it is AI (01-brand: the machine is visible).
DISCLOSE = ('tiktok', 'youtube', 'instagram', 'x', 'reddit', 'threads', 'facebook', 'whatsapp_channel',
            'linkedin', 'hn', 'producthunt')
# Briefs, reports, radar notes and product fixes mix notes for Krish with words
# the public will see. In those, only lines marked as public get the copy rules.
INTERNAL = ('other', 'site')
PUBLIC_LINE = re.compile(r'^\s*(?:on[- ]screen|voiceover|vo|caption|cover|copy|headline|title|hook|cta|'
                         r'end card|line)\s*:', re.I)

# Every link to the product carries tracking built from the creative id. A bare
# fulltime.fm counts: X, Threads and Facebook turn it into a link. krish@fulltime.fm does not.
OWN_LINK = re.compile(r'(?<![@\w.])(?:https?://)?(?:www\.)?fulltime\.fm(?![\w-])[^\s)>\]"\']*', re.I)
SCHEME = re.compile(r'https?://', re.I)
CREATIVE_ID = re.compile(r'^(INV|WA|EM|TT|YT|IG|X|RD|TH|FB|WC|LI|HN|PH|PR|CR|AD|FPL|WEB)_'
                         r'(CLASH|PROOF|TRIBE|BUILD|GAME|HABIT)_'
                         r'(CLIP|SHORT|VIDEO|STORY|POST|THREAD|COMMENT|DM|INVITE|EMAIL|PITCH|LAUNCH|NOTE)_'
                         r'C(\d{2,3})_H(\d{2,3})_V(\d{1,2})_(\d{8})$')
# utm_source per platform code. Personal invites are "beta": the December bar
# counts testers by that tag (full-time docs/22-vision-and-beta.md).
SOURCE = {'INV': 'beta', 'WA': 'wa', 'EM': 'email', 'TT': 'tiktok', 'YT': 'youtube', 'IG': 'instagram', 'X': 'x',
          'RD': 'reddit', 'TH': 'threads', 'FB': 'facebook', 'WC': 'whatsapp_channel', 'LI': 'linkedin', 'HN': 'hn',
          'PH': 'producthunt', 'PR': 'press', 'CR': 'creator', 'AD': 'paid', 'FPL': 'fpl', 'WEB': 'web'}
PREFIX = {'invite': 'INV', 'whatsapp': 'WA', 'email': 'EM', 'tiktok': 'TT', 'youtube': 'YT', 'instagram': 'IG',
          'x': 'X', 'reddit': 'RD', 'threads': 'TH', 'facebook': 'FB', 'whatsapp_channel': 'WC', 'linkedin': 'LI',
          'hn': 'HN', 'producthunt': 'PH', 'press': 'PR', 'creator': 'CR', 'ads': 'AD', 'fpl': 'FPL'}


def medium(plat, fmt):
    if plat == 'AD':
        return 'paid'
    if fmt in ('CLIP', 'SHORT', 'VIDEO', 'STORY'):
        return 'organic_video'
    return {'INVITE': 'referral', 'DM': 'referral', 'EMAIL': 'email', 'PITCH': 'press',
            'LAUNCH': 'launch'}.get(fmt, 'organic_social')


def tracked(url, creative_id):
    """The url with this engine's UTM tags (replacing any already there)."""
    m = CREATIVE_ID.match(creative_id or '')
    if not m:
        raise ValueError(f'"{creative_id}" is not a creative id (PLAYBOOK.md, "Creative ids")')
    plat, _pillar, fmt, _c, _h, _v, day = m.groups()
    base, _, frag = url.partition('#')
    base = re.sub(r'([?&])utm_[a-z]+=[^&]*', r'\1', base).rstrip('?&').replace('?&', '?')
    while '&&' in base:
        base = base.replace('&&', '&')
    if re.fullmatch(r'https?://(?:www\.)?fulltime\.fm', base, re.I):
        base += '/'
    tags = (f'utm_source={SOURCE[plat]}&utm_medium={medium(plat, fmt)}'
            f'&utm_campaign=ft_growth_{day[:6]}&utm_content={creative_id}')
    return base + ('&' if '?' in base else '?') + tags + (('#' + frag) if frag else '')


# ---------------------------------------------------------------------------
# Reading full-time and the live product.
# ---------------------------------------------------------------------------
def http(url, accept_json=True, timeout=60):
    headers = dict(UA)
    if url.startswith('https://api.github.com/'):
        headers['Accept'] = 'application/vnd.github+json'
        if os.environ.get('GITHUB_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        body = r.read()
    return json.loads(body) if accept_json else body.decode('utf-8', errors='replace')


def head_sha():
    """The commit on full-time's main right now: git first (no rate limit), then the API."""
    try:
        out = subprocess.run(['git', 'ls-remote', f'https://github.com/{REPO}', f'refs/heads/{BRANCH}'],
                             capture_output=True, text=True, encoding='utf-8', timeout=60)
        sha = (out.stdout.split() or [''])[0]
        if re.fullmatch(r'[0-9a-f]{40}', sha):
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    return http(f'{API}/commits/{BRANCH}')['sha']


def raw(path, sha):
    try:
        return http(f'{RAW}/{sha}/{path}', accept_json=False)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def canon_paths(index):
    """The canon full-time's docs index routes a marketing agent to, in its order, then the always-read files."""
    paths = []
    rows = {}
    for line in (index or '').splitlines():
        cells = [c.strip() for c in line.split('|')]
        if len(cells) > 3 and cells[1] in ROUTE_ROWS:
            rows[cells[1]] = line
    for name in ROUTE_ROWS:
        for target in re.findall(r'\]\(([^)#\s]+\.(?:md|json))\)', rows.get(name, '')):
            p = target[3:] if target.startswith('../') else 'docs/' + target.lstrip('./')
            if p not in paths:
                paths.append(p)
    found = bool(paths)
    for p in ALWAYS_CANON:
        if p not in paths:
            paths.append(p)
    return paths, found


def section(text, prefix):
    """A Markdown section from a heading beginning `prefix` to the next heading of its level,
    or, for a JSON document, the value under a top-level key."""
    if text is None:
        return None
    if not prefix.startswith('#'):
        try:
            value = json.loads(text).get(prefix)
        except (ValueError, AttributeError):
            return None
        return None if value is None else json.dumps(value, sort_keys=True)
    level = len(prefix) - len(prefix.lstrip('#'))
    out, on = [], False
    for line in text.split('\n'):
        if line.startswith(prefix):
            on = True
            out.append(line)
            continue
        if on:
            m = re.match(r'^(#+) ', line)
            if m and len(m.group(1)) <= level:
                break
            out.append(line)
    return '\n'.join(out).strip() if out else None


def digest(s):
    return hashlib.sha256((s if s is not None else '\0MISSING').encode()).hexdigest()


def fingerprints(texts):
    return {f'{path} {prefix}': digest(section(texts.get(path), prefix))[:16] for path, prefix in RULES_SOURCES}


def decisions(roadmap):
    """The newest headings of full-time's decision log (docs/12-roadmap.md)."""
    log = section(roadmap, '## Decision log') or ''
    return [l[4:].strip() for l in log.splitlines() if l.startswith('### ')]


def read_rail():
    """Every match Today can show, newest first, with the AI Pundits who made a show for it."""
    data = http(TODAY_API + '?pundit=zen')
    out = []
    for m in data.get('matches') or []:
        f = m.get('fixture') or {}
        pundits = [p for p in (m.get('pundits') or []) if p in PUNDITS]
        out.append({'drop': m.get('dropId'), 'date': m.get('coverageDate'), 'home': f.get('homeTeam'),
                    'away': f.get('awayTeam'), 'score': [f.get('homeScore'), f.get('awayScore')],
                    'pundits': pundits, 'fill': len(set(pundits))})
    return out


def whole_match_gate(rail):
    if rail is None:
        return {'open': False, 'why': 'the rail was not read, so nothing pushes blind'}
    if not rail:
        return {'open': False, 'why': 'no match has a published show'}
    top = rail[0]
    full = [m for m in rail if m['fill'] >= RAIL_MIN]
    if top['fill'] >= RAIL_MIN:
        return {'open': True, 'why': f'the newest match has {top["fill"]} of 6 AI Pundits'}
    if full:
        return {'open': True, 'why': f'the newest match has {top["fill"]} of 6; push the latest full one '
                                     f'({full[0]["home"]} v {full[0]["away"]}, {full[0]["fill"]} of 6) with its drop link'}
    return {'open': False, 'why': f'no match has {RAIL_MIN} of 6 AI Pundits (newest: {top["fill"]} of 6)'}


def push_gate(rail, state=None):
    """'open' is the whole-match gate: four of six. With a state whose ORGANIC is in force,
    'per_take' says whether a single take may go: true when a rail match has a published show,
    since the per-take gate (policy.take_gate) asks only for that exact show."""
    gate = whole_match_gate(rail)
    if state is not None and policy.organic_in_force(state):
        gate['per_take'] = any(m.get('pundits') for m in rail or [])
        if gate['per_take'] and not gate['open']:
            gate['why'] += ('; only a whole-match push waits for that: under ORGANIC a single take whose exact '
                            'AI Pundit show is published may go (the per-take gate)')
    return gate


def public_actions(s):
    """Krish's open actions this public reading can see: the one ruling asked next and the
    one-off setup steps not yet seen done (engine/actions.py holds the full list)."""
    from engine import actions, policy as _policy
    out = []
    pending = {rid: {'status': r['status'], 'title': t} for (rid, r), t in
               ((item, load_rulings().get(item[0], {}).get('title', '')) for item in s.get('rulings', {}).items())}
    ruling = actions._next_ruling(pending)
    if ruling:
        out.append(f'- Rule on {ruling} in Control Center: {pending[ruling]["title"].rstrip(".")}.')
    identities = s.get('brand_identities') or {}
    seen = {'identity_verified': any(_policy.identity_verified(x, p) for x in identities.values()
                                     for p in actions.PUSHED)}
    for entry in actions.load_owner():
        if entry.get('done_on') or seen.get(entry['done_when']) is True:
            continue
        out.append(f'- {entry["text"]} ({entry["minutes"]} min, one-off)')
    return out or ['- Nothing waits on Krish that this reading can see.']


def read_feed():
    xml = http(FEED, accept_json=False)
    items = []
    for block in re.findall(r'<item>(.*?)</item>', xml, re.S)[:5]:
        get = lambda tag: (re.search(f'<{tag}>(.*?)</{tag}>', block, re.S) or [None, ''])[1]
        items.append({'title': get('title').strip(), 'date': get('pubDate').strip(),
                      'link': get('link').replace('&amp;', '&').strip()})
    return items


def load_rulings():
    return json.loads(Path(HERE, 'rulings.json').read_text(encoding='utf-8'))['rulings']


def rulings_state(roadmap, rulings=None):
    """Each ruling's effect: in force only when approved here AND recorded in full-time's decision log."""
    rulings = rulings if rulings is not None else load_rulings()
    heads = set(decisions(roadmap))
    out = {}
    for rid, r in rulings.items():
        recorded = bool(r.get('evidence')) and r['evidence'] in heads
        out[rid] = {'status': r.get('status', 'pending'), 'recorded': recorded,
                    'in_force': r.get('status') == 'approved' and recorded}
    for rid, r in rulings.items():   # a ruling that needs another is in force only with it
        if any(not out.get(req, {}).get('in_force') for req in r.get('requires', [])):
            out[rid]['in_force'] = False
    return out


def release_evidence(rulings, decisions_read, sha):
    """The product release decision as policy.release_open reads it (R43): written only
    when rulings.json approves RELEASE and its heading is among the decisions this sync
    read from full-time's log; None otherwise, so nothing is written."""
    release = (rulings or {}).get('RELEASE') or {}
    heading = release.get('evidence') or ''
    if release.get('status') != 'approved' or not heading or heading not in (decisions_read or []):
        return None
    return {'verified': True, 'fulltime_sha': sha, 'decision_heading': heading, 'source_path': 'docs/12-roadmap.md'}


def state_dir(publish):
    return os.path.join(HERE, 'state') if publish else os.path.join(LOCAL, 'state')


def load_state(published_only=False):
    """The latest reading: this machine's own first, then the repository's copy.
    A publish compares only with the repository's copy."""
    dirs = [os.path.join(HERE, 'state')] if published_only else [os.path.join(LOCAL, 'state'), os.path.join(HERE, 'state')]
    for d in dirs:
        f = os.path.join(d, 'fulltime.json')
        if os.path.exists(f):
            state = json.loads(Path(f).read_text(encoding='utf-8'))
            if not published_only:
                state['brand_identities'] = policy.load_identities(LOCAL)
            return state
    return None


MEANINGFUL = ('sha', 'canon', 'rules', 'rules_ok', 'rail', 'feed', 'open_pulls', 'rulings')


def sync(publish=False, quiet=False):
    prev = load_state(published_only=publish) or {}
    sha = head_sha()
    index = raw('docs/README.md', sha)
    notes = []
    paths, found = canon_paths(index)
    texts = {'docs/README.md': index}
    for p in paths:
        if p not in texts:
            texts[p] = raw(p, sha)
    for p, _ in RULES_SOURCES:
        if p not in texts:
            texts[p] = raw(p, sha)
    canon = {p: digest(texts.get(p))[:16] for p in paths}
    prints = fingerprints(texts)
    rules_ok = prints == RULES_BASIS and all(p in paths for p, _ in RULES_SOURCES)
    commits, pulls = [], []
    try:
        since = prev.get('synced_at') or (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).isoformat()
        for c in http(f'{API}/commits?sha={BRANCH}&per_page=30&since={urllib.parse.quote(since)}'):
            commits.append({'sha': c['sha'][:10], 'date': c['commit']['committer']['date'],
                            'subject': c['commit']['message'].splitlines()[0][:140]})
        for p in http(f'{API}/pulls?state=open&per_page=20'):
            pulls.append({'number': p['number'], 'title': p['title'][:140], 'branch': p['head']['ref'],
                          'updated': p['updated_at']})
    except (urllib.error.URLError, KeyError, ValueError) as e:
        notes.append(f'commit list and pull requests not read ({getattr(e, "code", e)}); set GITHUB_TOKEN if GitHub is rate limiting')
    try:
        rail = read_rail()
    except (urllib.error.URLError, ValueError, KeyError, TypeError) as e:
        rail = None
        notes.append(f'fulltime.fm did not answer for the rail ({getattr(e, "code", e)})')
    try:
        feed = read_feed()
    except (urllib.error.URLError, ValueError) as e:
        feed = None
        notes.append(f'the Reporter feed did not answer ({getattr(e, "code", e)})')
    old = prev.get('canon') or {}
    changed = sorted(p for p in canon if p in old and old[p] != canon[p])
    added = sorted(set(paths) - set(old)) if old else []
    removed = sorted(set(old) - set(paths)) if old else []
    rulings = load_rulings()
    heads = decisions(texts.get('docs/12-roadmap.md'))
    ruled = rulings_state(texts.get('docs/12-roadmap.md'), rulings)
    state = {
        'repo': REPO, 'sha': sha, 'synced_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'previous_sha': prev.get('sha'), 'canon_from_index': found, 'canon': canon, 'rules': prints,
        'rules_ok': rules_ok, 'changed_since_last_sync': changed, 'canon_added': added, 'canon_removed': removed,
        'commits': commits, 'open_pulls': pulls, 'decisions': heads,
        'rulings': ruled, 'rail': rail, 'push': push_gate(rail, {'rulings': ruled}),
        'feed': feed, 'notes': notes,
    }
    release = release_evidence(rulings, heads, sha)   # every heading, so newer decisions never close RELEASE
    if release:
        state['marketing_release'] = release
    d = state_dir(publish)
    if publish and prev and all(prev.get(k) == state[k] for k in MEANINGFUL):
        # The repository's copy changes only when full-time, the rail or the
        # feed changed, so the hourly Action makes no commit for nothing.
        if not quiet:
            print(f'no change since {prev.get("synced_at")} (full-time {sha[:10]})')
        return prev
    os.makedirs(d, exist_ok=True)
    from engine.records import atomic_json
    atomic_json(os.path.join(d, 'fulltime.json'), state)
    Path(d, 'FULLTIME-NOW.md').write_text(now_md(state), encoding='utf-8')
    if not quiet:
        print(now_md(state))
    return state


def rail_rows(rail):
    rows = ['| Match | Shows on | AI Pundits | Made a show |', '|---|---|---|---|']
    for m in rail:
        names = ', '.join(PUNDITS[p] for p in m['pundits']) or 'none'
        rows.append(f'| {m["home"]} {m["score"][0]}-{m["score"][1]} {m["away"]} | {m["date"]} | '
                    f'{m["fill"]} of 6 | {names} |')
    return rows


def now_md(s):
    lines = [
        '# Full Time now', '',
        f'Read from `{s["repo"]}` at commit `{s["sha"][:10]}` and from fulltime.fm on {s["synced_at"]} UTC by `python3 growth.py sync`.',
        'Rewritten when a sync finds full-time, its open pull requests, the rail or the feed changed. The full-time repository and the live site are the source of truth; this is a reading of them.', '',
    ]
    if not s['rules_ok']:
        lines += ['## STOP: Full Time\'s rules changed', '',
                  'A rules section this engine checks against has changed or is no longer canon. No pack passes until',
                  'a person reads the new words and updates RULES and RULES_BASIS in growth.py (AGENTS.md, rule 2).', '',
                  '| Section | Now | Engine was written for |', '|---|---|---|']
        lines += [f'| `{k}` | {v} | {RULES_BASIS.get(k)} |' for k, v in s['rules'].items() if v != RULES_BASIS.get(k)]
        lines += ['']
    push = s['push']
    lines += [('## Whole-match push gate: ' if 'per_take' in push else '## Push gate: ') + ('OPEN' if push['open'] else 'HOLD'), '',
              f'{push["why"][0].upper() + push["why"][1:]}. A push sends fans to a match only when at least {RAIL_MIN} of the six AI Pundits made a show for it (PLAYBOOK.md, "The rail gate").', '']
    if 'per_take' in push:
        lines += ['## Per-take gate (ORGANIC): ' + ('OPEN' if push['per_take'] else 'HOLD'), '',
                  (f'A single take may go when the exact AI Pundit shows it names are published on this rail, read under 26 hours ago. Whole-match promotion still waits for {RAIL_MIN} of 6.'
                   if push['per_take'] else 'No match on the rail has a published show, so no take passes the per-take gate.'), '']
    lines += ['## The rail at fulltime.fm', '']
    lines += rail_rows(s['rail']) if s['rail'] else ['The rail was not read.' if s['rail'] is None else 'No match has a published show.']
    if s['changed_since_last_sync'] or s['canon_added'] or s['canon_removed']:
        lines += ['', '## Canon changed since the last sync', '', 'Read these again before drafting anything:', '']
        lines += [f'- changed: `{p}`' for p in s['changed_since_last_sync']]
        lines += [f'- newly canon: `{p}`' for p in s['canon_added']]
        lines += [f'- no longer canon: `{p}`' for p in s['canon_removed']]
    lines += ['', "## Krish's actions", '', 'His matchday and plan answers wait in Control Center; `growth.py actions` '
              'lists them with the rest. From what this public reading can see:', '']
    lines += public_actions(s)
    lines += ['', '## Rulings the playbook needs', '', '| Ruling | Here | In full-time\'s decision log | In force |', '|---|---|---|---|']
    titles = {k: v.get('title', '') for k, v in load_rulings().items()}
    for rid, r in s['rulings'].items():
        lines.append(f'| {rid}: {titles.get(rid, "")} | {r["status"]} | {"yes" if r["recorded"] else "no"} | {"yes" if r["in_force"] else "no"} |')
    lines += ['', '## Latest decisions (full-time `docs/12-roadmap.md`)', '']
    lines += [f'- {d}' for d in s['decisions'][:6]] or ['- none read']
    lines += ['', '## The Reporter feed', '']
    lines += [f'- {i["date"][:16]}: {i["title"]}' for i in (s['feed'] or [])] or ['- not read' if s['feed'] is None else '- empty']
    lines += ['', '## The canon, in order', '']
    lines += [f'{i}. `{p}`' for i, p in enumerate(s['canon'], 1)]
    if not s['canon_from_index']:
        lines += ['', 'The docs index routing rows were not found, so this is the always-read list. Check full-time\'s docs/README.md.']
    lines += ['', '## Recent commits on main', '']
    lines += [f'- `{c["sha"]}` {c["date"][:10]} {c["subject"]}' for c in s['commits']] or ['- none since the last sync']
    lines += ['', '## Work in flight (open pull requests)', '']
    lines += [f'- #{p["number"]} {p["title"]} (`{p["branch"]}`, updated {p["updated"][:10]})' for p in s['open_pulls']] or ['- none']
    if s['notes']:
        lines += ['', '## Not read this time', ''] + [f'- {n}' for n in s['notes']]
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# Checking a pack.
# ---------------------------------------------------------------------------
def gates_for(platform, rulings):
    """The rulings this platform waits on, and whether each is in force."""
    out = []
    for rid, r in load_rulings().items():
        if platform in r.get('unlocks', []):
            out.append((rid, (rulings or {}).get(rid, {}).get('in_force', False)))
    return out


def link_problems(url, rail, per_take=()):
    """A link to Today must name a match whose rail is full enough, and an AI Pundit who made a show for it.
    `per_take` holds the (drop, AI Pundit) pairs a draft passed the per-take gate for (ORGANIC in
    force): a link to one of those exact shows needs no four of six."""
    parts = urllib.parse.urlsplit(url)
    if parts.path not in ('', '/'):
        return []
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    if any(sum(1 for k, _ in pairs if k == key) > 1 for key in ('drop', 'pundit')):
        return [f'the link {url} names drop or pundit more than once (a browser opens the first, so name each once)']
    q = dict(pairs)
    if rail is None:
        return [f'the link {url} goes to Today, but the rail was not read in the sync (nothing pushes blind)']
    if not rail:
        return [f'the link {url} goes to Today, but no match has a published show']
    drop, pundit = q.get('drop'), q.get('pundit')
    match = next((m for m in rail if m['drop'] == drop), None) if drop else rail[0]
    if drop and match is None:
        return [f'the link names drop {drop[:8]}, which is not a match Today can show']
    out = []
    if pundit and pundit not in match['pundits']:
        out.append(f'the link opens {PUNDITS.get(pundit, pundit)}, who made no show for {match["home"]} v {match["away"]}')
    if match['fill'] < RAIL_MIN and (drop, pundit) not in set(per_take):
        out.append(f'the link sends fans to {match["home"]} v {match["away"]}, where {match["fill"]} of 6 AI Pundits '
                   f'made a show (push only at {RAIL_MIN} of 6: mark it "needs": "RAIL", or link a fuller match)')
    return out


def score_problems(text, rail):
    """A scoreline on a line that names a club in the live rail must be the result of a rail match that line names."""
    out = []
    for line in text.splitlines():
        low = line.lower()
        named = [m for m in rail or [] if any(n and n.lower() in low for n in (m['home'], m['away']))]
        if not named:
            continue
        # Dates (2026-10-16), times (16:30) and ranges are not scores.
        for a, b in re.findall(r'(?<![\d:/-])(\d{1,2})\s?-\s?(\d{1,2})(?![\d:/-])', line):
            pair = (int(a), int(b))
            if not any(pair in ((m['score'][0], m['score'][1]), (m['score'][1], m['score'][0])) for m in named):
                results = ', '.join(f'{m["home"]} {m["score"][0]}-{m["score"][1]} {m["away"]}' for m in named)
                out.append(f'the score {a}-{b} is not the result of the match that line names ({results})')
    return out


def problems(item, state=None):
    """Every rule this one draft breaks, in plain words."""
    state = state or {}
    string_fields = ('text', 'platform', 'needs', 'creative_id', 'target_name', 'target_url', 'account_scope',
                     'identity_ref', 'contact_basis', 'consent_ref', 'sender', 'distribution')
    if any(k in item and not isinstance(item[k], str) for k in string_fields):
        return ['draft text, channel, references and gate fields must be strings']
    out = policy.errors(item, state)
    full = item.get('text') or ''
    platform = (item.get('platform') or '').lower()
    needs = (item.get('needs') or '').strip()
    if not full.strip():
        return ['it has no text']
    if platform not in PLATFORMS:
        out.append(f'platform "{platform}" is not one of {", ".join(PLATFORMS)}')
    if needs and needs not in policy.HOLDS:
        out.append(f'needs "{needs}" must be a documented hold code')
    pending = policy.holds(item)
    # Under ORGANIC a take that passed the per-take gate may link its own published shows.
    per_take = set()
    if (platform in policy.BRAND_CHANNELS and policy.organic_in_force(state) and item.get('whole_match') is False
            and not policy.take_gate(item, state)):
        per_take = {(item['drop_id'], p) for p in item['pundits']}
    cid = item.get('creative_id')
    if cid:
        m = CREATIVE_ID.match(cid)
        if not m:
            out.append(f'creative_id "{cid}" does not follow PLAYBOOK.md, "Creative ids"')
        elif platform in PREFIX and m.group(1) != PREFIX[platform] and not (platform == 'whatsapp' and m.group(1) == 'INV'):
            out.append(f'creative_id starts {m.group(1)} but the platform is {platform} ({PREFIX[platform]})')
    for rid, in_force in gates_for(platform, state.get('rulings')):
        if not in_force and rid not in pending:
            out.append(f'{platform} waits on ruling {rid} (PLAYBOOK.md, "Rulings"): mark it "needs": "{rid}" until '
                       f'Krish rules and full-time records it')
    if EM_DASH.search(full):
        out.append('it has an em dash (use a comma, a full stop or "and")')
    text = full
    if platform in INTERNAL:
        text = '\n'.join(line for line in full.splitlines() if PUBLIC_LINE.match(line))
    low = text.lower()
    for w in FILLER:
        if re.search(r'(?<!\w)' + re.escape(w) + r'(?!\w)', low):
            out.append(f'it says "{w}", marketing filler Full Time avoids (01-brand, Voice)')
    for w in SLOP:
        if w in low:
            out.append(f'it says "{w}", a stock phrase that reads as machine-written')
    if NOT_BUT.search(text):
        out.append('it uses the "it\'s not X, it\'s Y" turn')
    for rx, why in AVOID + FAKE_PROOF:
        if rx.search(text):
            out.append(why)
    if BETTING.search(text):
        out.append('it uses betting language (Full Time is not a betting product: 01-brand checklist, 12-roadmap)')
    for name in LIVING_PUNDITS:
        if name in low:
            out.append(f'it names {name.title()}, a living pundit (no imitation or comparison: 01-brand checklist)')
    if BROADCASTERS.search(text):
        out.append('it names a broadcaster or its show (no broadcaster marks or comparisons: 01-brand, Assets)')
    if platform not in BUILD and INTERNAL_TERMS.search(text):
        out.append(f'it uses the internal term "{INTERNAL_TERMS.search(text).group(0)}" in public copy (01-brand, Voice)')
    if platform not in BUILD and platform not in INTERNAL and CURRENCY.search(text):
        out.append('it states a price or an amount of money (no price is approved: 07 promise boundaries)')
    for mm in re.finditer(r'\bai\s+pundits?\b', text, re.I):
        if not mm.group(0).startswith('AI Pundit'):
            out.append(f'it says "{mm.group(0)}": the term is "AI Pundit", exactly (01-brand)')
            break
    for rx, right in WRONG_NAMES:
        if rx.search(text):
            out.append(f'an AI Pundit\'s name is wrong: say {right}')
    for rx, uk in US:
        m = rx.search(text)
        if m:
            out.append(f'US English "{m.group(0)}" (Full Time talks to UK fans: {uk})')
    for addr in EMAIL.findall(full):
        if addr.lower() != CONTACT:
            out.append(f'the address {addr} (the only address in Full Time copy is {CONTACT})')
    if platform in DISCLOSE and not re.search(r'\bAI\b', text):
        out.append('a public post must say it is AI (the AI Pundit name does that)')
    if platform == 'creator' and not re.search(r'(?<![\w])(?:#ad|Ad)(?![\w])', full):
        out.append('a creator note must say the post is labelled "Ad" (ASA and CMA: any payment makes it an ad)')
    if sum(line.count('!') for line in text.splitlines()) > 1:
        out.append('more than one exclamation mark (no fake excitement: 01-brand, Voice)')
    if len(EMOJI.findall(text)) > 3:
        out.append(f'{len(EMOJI.findall(text))} emoji (three at most)')
    tags = HASHTAG.findall(text)
    if len(tags) > 5:
        out.append(f'{len(tags)} hashtags (2 to 5 specific ones at most)')
    if platform in LIMITS and len(text) > LIMITS[platform]:
        out.append(f'it is {len(text)} characters ({LIMITS[platform]} at most on {platform})')
    if len(full) > 8000:
        out.append('it is over 8,000 characters')
    for found in OWN_LINK.findall(full):
        if not SCHEME.match(found) and platform in INTERNAL:
            continue   # a note for Krish that names the site is not a link anyone clicks
        url = found if SCHEME.match(found) else 'https://' + found
        q = dict(re.findall(r'[?&](utm_[a-z]+)=([^&#]*)', url))
        if not SCHEME.match(found):
            out.append(f'the link {found} has no https:// (paste the exact link python3 growth.py link prints)')
        if not all(k in q for k in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content')):
            out.append(f'the link {found} is not tracked (python3 growth.py link <url> <creative_id>)')
        elif not CREATIVE_ID.match(q['utm_content']):
            out.append(f'the link {found} carries "{q["utm_content"]}", not a creative id')
        elif cid and q['utm_content'] != cid:
            out.append(f'the link {found} is tracked as {q["utm_content"]} but the draft is {cid}')
        elif not cid and platform in PREFIX:
            code = CREATIVE_ID.match(q['utm_content']).group(1)
            if code != PREFIX[platform] and not (platform == 'whatsapp' and code == 'INV'):
                out.append(f'the link {found} is tracked as {q["utm_content"]}, a {code} creative, but the draft is on '
                           f'{platform} ({PREFIX[platform]})')
        if platform not in INTERNAL:
            parts = urllib.parse.urlsplit(url)
            if parts.path in ('', '/') and not all(dict(urllib.parse.parse_qsl(parts.query)).get(k) for k in ('drop', 'pundit')):
                out.append('a show destination must name its exact drop and AI Pundit')
            link_errors = link_problems(url, state.get('rail'), per_take)
            out += [e for e in link_errors if 'RAIL' not in pending or 'made a show (push only' not in e]
    out += score_problems(text, state.get('rail'))
    return out


def check_pack(pack, state=None):
    if not isinstance(pack, dict):
        return ['a pack must be a JSON object']
    errs = policy.pack_errors(pack)
    if pack.get('kind') not in KINDS:
        errs.append(f'kind must be one of {", ".join(KINDS)}')
    if pack.get('venture') != 'fulltime':
        errs.append('venture must be "fulltime"')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(pack.get('pack_date') or '')):
        errs.append('pack_date must be YYYY-MM-DD')
    else:
        try:
            dt.date.fromisoformat(pack['pack_date'])
        except ValueError:
            errs.append('pack_date is not a calendar date')
    if not re.fullmatch(r'[0-9a-f]{7,40}', str(pack.get('fulltime_sha') or '')):
        errs.append('fulltime_sha is missing: run python3 growth.py sync and copy the commit it read')
    if not isinstance(pack.get('headline', ''), str):
        return errs + ['headline must be text']
    head = (pack.get('headline') or '').strip()
    if not head:
        errs.append('headline is empty')
    elif EM_DASH.search(head):
        errs.append('headline has an em dash')
    items = pack.get('items') or []
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        return errs + ['items must be a list of draft objects']
    if len(items) > 40:
        errs.append('more than 40 drafts in one pack')
    for i, item in enumerate(items, 1):
        for p in problems(item, state):
            errs.append(f'draft {i} ({item.get("platform", "?")}): {p}')
    if pack.get('kind') == 'numbers':
        rows = pack.get('numbers')
        if not isinstance(rows, list) or not rows:
            errs.append('a numbers pack needs "numbers": one row per place read')
        else:
            for r in rows:
                if not isinstance(r, dict):
                    errs.append('every numbers row must be an object')
                    continue
                if not r.get('platform') or not r.get('note'):
                    errs.append('every numbers row needs a platform and a note saying where it was read')
                for k, v in r.items():
                    if k not in ('platform', 'note') and v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0):
                        errs.append(f'numbers row {r.get("platform")}: {k} must be a number read today, or null')
    elif pack.get('numbers'):
        errs.append('numbers belong on a pack of kind numbers only')
    if pack.get('metrics'):
        from engine.measurements import validate
        try:
            for observation in pack['metrics']:
                validate(observation)
        except (ValueError, TypeError, KeyError) as error:
            errs.append(f'invalid aggregate observations: {error}')
    return errs


def freshness(pack, state, head_fn, fetch_fn):
    """Was this pack written against today's full-time? A list of reasons it was not."""
    if not state:
        return ['no sync on this machine: run python3 growth.py sync first']
    stale = policy.sync_age(state)
    if stale:
        return [stale]
    sha = str(pack.get('fulltime_sha') or '')
    if not sha or not state['sha'].startswith(sha):
        return [f'the pack names full-time {sha or "(none)"} but the last sync read {state["sha"][:10]}: sync, re-read, redraft']
    if not state.get('rules_ok', False):
        return ['Full Time\'s rules changed (local/state/FULLTIME-NOW.md, "STOP"): a person must update growth.py first']
    now = head_fn()
    if now == state['sha']:
        return []
    index = fetch_fn('docs/README.md', now)
    paths, _ = canon_paths(index)
    texts = {'docs/README.md': index}
    moved = []
    for p in paths:
        if p not in texts:
            texts[p] = fetch_fn(p, now)
        if p == 'NOW.md':
            continue   # the docs steward rewrites NOW.md nightly; its facts reach the pack through the next sync
        if state['canon'].get(p) != digest(texts[p])[:16]:
            moved.append(p)
    moved += sorted(set(state['canon']) - set(paths))
    for p, _ in RULES_SOURCES:
        if p not in texts:
            texts[p] = fetch_fn(p, now)
    if fingerprints(texts) != RULES_BASIS:
        moved.append('a rules section')
    if moved:
        return [f'full-time moved to {now[:10]} and changed {", ".join(sorted(set(moved)))} since your sync: sync, re-read, redraft']
    return []


# ---------------------------------------------------------------------------
# Storing a pack.
# ---------------------------------------------------------------------------
def control_center_takes_fulltime():
    """Packs are never written to Control Center. Run reports go only through
    the growth engine protocol (growth.py cc, engine/control_center.py)."""
    return False, 'packs stay local; run reports reach Control Center only through growth.py cc'


def render_md(pack):
    items = pack.get('items') or []
    ready = sum(1 for it in items if not policy.holds(it))
    out = [f'# {pack["headline"]}', '',
           f'{pack["kind"]}, {pack["pack_date"]}, full-time `{pack["fulltime_sha"][:10]}`. '
           f'{ready} ready, {len(items) - ready} held.', '']
    for i, it in enumerate(items, 1):
        held = policy.holds(it)
        tag = (' (HELD: ' + ', '.join(held) + ')') if held else ''
        out += [f'## {i}. {it.get("platform")}' + (f' `{it["creative_id"]}`' if it.get('creative_id') else '') + tag, '']
        for k in ('target_name', 'target_url', 'why'):
            if it.get(k):
                out.append(f'**{k.replace("_", " ")}:** {it[k]}  ')
        out += ['', '```text', it.get('text', ''), '```', '']
    if pack.get('numbers'):
        out += ['## Numbers', '', '```json', json.dumps(pack['numbers'], indent=1), '```', '']
    return '\n'.join(out)


def store_pack(pack):
    from engine.records import History, atomic_json
    from engine.reporting import envelope
    errors = check_pack(pack, load_state())
    if errors:
        raise ValueError('pack refused before storage: ' + '; '.join(errors))
    receipt = History(os.path.join(LOCAL, 'engine')).checkpoint(pack)
    why = control_center_takes_fulltime()[1]
    d = os.path.join(LOCAL, 'packs')
    os.makedirs(d, exist_ok=True)
    name = f'{pack["pack_date"]}-{pack["kind"]}'
    atomic_json(os.path.join(d, name + '.json'), pack)
    atomic_json(os.path.join(LOCAL, 'outbox', name + '.json'), envelope(pack, receipt))
    Path(d, name + '.md').write_text(render_md(pack), encoding='utf-8')
    print(f'stored on this machine: local/packs/{name}.md ({why}). The pack in full:\n')
    print(render_md(pack))
    return receipt


def read_packs(days, kind):
    d = os.path.join(LOCAL, 'packs')
    from engine.clock import LONDON
    since = (dt.datetime.now(LONDON).date() - dt.timedelta(days=days)).isoformat()
    out = []
    for f in sorted(os.listdir(d) if os.path.isdir(d) else [], reverse=True):
        if f.endswith('.json') and f[:10] >= since:
            p = json.loads(Path(d, f).read_text(encoding='utf-8'))
            if not kind or p.get('kind') == kind:
                out.append(p)
    from engine.records import History
    saved = History(os.path.join(LOCAL, 'engine')).read()
    by_key = {(p['pack_date'], p['kind']): p for p in out}
    for record in saved['packs'].values():
        latest = next(r['pack'] for r in record['revisions'] if r['digest'] == record['latest_digest'])
        if latest['pack_date'] >= since and (not kind or latest['kind'] == kind):
            by_key[(latest['pack_date'], latest['kind'])] = latest
    return sorted(by_key.values(), key=lambda p: (p['pack_date'], p['kind']), reverse=True)


# ---------------------------------------------------------------------------
# Doctor and self-test.
# ---------------------------------------------------------------------------
def doctor():
    ok = True

    def line(good, what, fix=''):
        nonlocal ok
        ok = ok and good
        print(('ready     ' if good else 'NOT READY ') + what + ('' if good else f'\n          fix: {fix}'))

    line(sys.version_info >= (3, 9), f'Python {sys.version.split()[0]}', 'install Python 3.9 or newer')
    try:
        sha = head_sha()
        line(True, f'full-time main is readable (commit {sha[:10]})')
    except Exception as e:  # noqa: BLE001 - doctor reports, never raises
        line(False, 'full-time main is readable', f'network access is off or GitHub is blocked: {e}')
    try:
        rail = read_rail()
        line(True, f'fulltime.fm answers ({len(rail)} matches with a show; newest {rail[0]["fill"] if rail else 0} of 6)')
    except Exception as e:  # noqa: BLE001
        line(False, 'fulltime.fm answers', f'network access is off or the site is down: {e}')
    s = load_state()
    if s:
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(s['synced_at'])
        line(age < dt.timedelta(hours=26), f'last sync {int(age.total_seconds() // 3600)} hours ago (full-time {s["sha"][:10]})', 'run python3 growth.py sync')
        line(s.get('rules_ok', False), 'Full Time\'s rules match what the checker was written for',
             'read the changed sections in local/state/FULLTIME-NOW.md, then update RULES and RULES_BASIS in growth.py')
    else:
        line(False, 'a sync on this machine', 'run python3 growth.py sync')
    autos = json.loads(Path(HERE, 'automations.json').read_text(encoding='utf-8'))['automations']
    line(all(os.path.exists(os.path.join(HERE, a['job'])) for a in autos),
         f'automations.json ({len(autos)} automations, every job file present)', 'a job file named in automations.json is missing')
    try:
        os.makedirs(os.path.join(LOCAL, 'packs'), exist_ok=True)
        line(True, 'local/ is writable (packs and lists stay on this machine)')
    except OSError as e:
        line(False, 'local/ is writable', str(e))
    from engine.records import History
    import shutil
    try:
        History(os.path.join(LOCAL, 'engine')).read()
        line(True, 'private history validates (existing pack revision checksums included)')
    except ValueError:
        line(False, 'private history validates', 'restore a validated backup with growth.py history --restore before continuing')
    line(bool(shutil.which('ffmpeg') and shutil.which('ffprobe')), 'FFmpeg and FFprobe are available',
         'install the free local FFmpeg package for rendering')
    _, why = control_center_takes_fulltime()
    print(f'note      packs: {why}; they are saved in local/packs/ and printed in full')
    bearer = bool(os.environ.get('CONTROL_CENTER_ENGINE_TOKEN', '').strip()) or Path(LOCAL, 'control-center', 'token').is_file()
    print('note      Control Center bearer: ' + ('available to growth.py cc' if bearer else
          'not found; set CONTROL_CENTER_ENGINE_TOKEN or write local/control-center/token (never commit it)'))
    print('\nready to run' if ok else '\nnot ready: fix the lines above, then run doctor again')
    return 0 if ok else 1


def self_test():
    n = 0

    def t(name, cond):
        nonlocal n
        if not cond:
            sys.exit(f'self-test FAILED: {name}')
        n += 1

    drop_full, drop_thin = 'aaaaaaaa-0000-4000-8000-000000000001', 'bbbbbbbb-0000-4000-8000-000000000002'
    rail = [{'drop': drop_thin, 'date': '2026-10-19', 'home': 'Leeds United', 'away': 'Manchester United',
             'score': [1, 1], 'pundits': ['zen'], 'fill': 1},
            {'drop': drop_full, 'date': '2026-10-18', 'home': 'Crystal Palace', 'away': 'Nottingham Forest',
             'score': [3, 1], 'pundits': ['zen', 'gaffer', 'stats', 'doomer', 'banter'], 'fill': 5}]
    on = {'D1': {'in_force': True}, 'D4': {'in_force': True}, 'D5': {'in_force': True}, 'D6': {'in_force': True}, 'D7': {'in_force': True}}
    brand_identities = {p: {'verified': True, 'platform': p, 'account_scope': 'brand',
                            'source_url': 'https://' + {'youtube':'youtube.com','x':'x.com','whatsapp_channel':'whatsapp.com'}.get(p,p+'.com') + '/example-fixture',
                            'verified_at': dt.datetime.now(dt.timezone.utc).isoformat()}
                        for p in policy.BRAND_CHANNELS}
    synced = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    st = {'rail': rail, 'rulings': on, 'brand_identities': brand_identities, 'synced_at': synced}
    cid = 'TT_CLASH_CLIP_C01_H02_V1_20261019'
    link = tracked(f'https://fulltime.fm/?drop={drop_full}&pundit=doomer', cid)
    t('a tracked link is built from the creative id', link ==
      f'https://fulltime.fm/?drop={drop_full}&pundit=doomer&utm_source=tiktok&utm_medium=organic_video'
      f'&utm_campaign=ft_growth_202610&utm_content={cid}')
    t('tracking replaces old tags', tracked('https://fulltime.fm/?utm_source=old&a=1', 'WA_TRIBE_INVITE_C02_H01_V1_20261101') ==
      'https://fulltime.fm/?a=1&utm_source=wa&utm_medium=referral&utm_campaign=ft_growth_202611&utm_content=WA_TRIBE_INVITE_C02_H01_V1_20261101')
    t('a personal invite is tagged beta, the December bar\'s cohort', 'utm_source=beta&' in tracked('https://fulltime.fm', 'INV_CLASH_INVITE_C01_H01_V1_20261019'))
    t('a bare domain gets a path', tracked('https://fulltime.fm', 'INV_CLASH_INVITE_C01_H01_V1_20261019').startswith('https://fulltime.fm/?utm_source='))
    good = {'pack_date': '2026-10-19', 'kind': 'daily', 'venture': 'fulltime', 'fulltime_sha': '319d324920',
            'headline': 'Monday pack', 'items': [{'platform': 'tiktok', 'creative_id': cid,
                                                  'account_scope': 'brand', 'identity_ref': 'tiktok', 'holds': ['RELEASE'],
                                                  'text': f'The Doomer and The Romantic heard the same match. One AI Pundit is not happy. {link}'}]}
    t('a clean pack passes', check_pack(good, st) == [])

    def errs(text, platform='tiktok', needs='', cid_=None, state=None):
        item = {'platform': platform, 'text': text, 'needs': needs}
        if platform in policy.BRAND_CHANNELS:
            item.update(account_scope='brand', identity_ref=platform, holds=['RELEASE', 'CHANNEL', 'CONSENT'])
        if platform == 'whatsapp':
            item['distribution'] = 'listener_initiated'
        if cid_:
            item['creative_id'] = cid_
        return check_pack({**good, 'items': [item]}, st if state is None else state)

    def bad(text, word, **kw):
        return any(word in e for e in errs(text, **kw))
    t('an em dash is refused', bad('Six AI Pundits \u2014 one match', 'em dash'))
    t('filler is refused', bad('An unmissable AI Pundit show', 'filler'))
    t('slop is refused', bad('AI Pundits that unlock the match', 'machine-written'))
    t('the retired label is refused', bad('Meet the AI characters', 'AI Pundit (01-brand)'))
    t('"ai pundits" in the wrong case is refused', bad('Six ai pundits argue', 'exactly'))
    t('a personal show is refused', bad('Your personal AI Pundit show', 'personal'))
    t('daily promises are refused', bad('A new AI Pundit show every morning', 'daily'))
    t('every-match promises are refused', bad('AI Pundit shows for every match', 'every-match'))
    t('prediction claims are refused', bad('Our AI Pundit called it', 'prediction'))
    t('launch timing is refused', bad('AI Pundits launching in December', 'launch'))
    t('a price is refused on a fan channel', bad('AI Pundit shows for £2', 'price'))
    t('the build story may state the cost', not bad('About $2 of model spend per run of six AI Pundit shows', 'price', platform='hn', needs='D4'))
    t('betting language is refused', bad('AI Pundit acca tips', 'betting'))
    t('"against the odds" is football, not betting', not bad('An AI Pundit on a win against the odds', 'betting'))
    t('odds alone are betting', bad('The AI Pundit gives the odds', 'betting'))
    t('a living pundit is refused', bad('Better than Gary Neville, says the AI Pundit', 'living pundit'))
    t('a broadcaster is refused', bad('Skip Match of the Day, hear an AI Pundit', 'broadcaster'))
    t('internal terms stay out of fan copy', bad('An AI Pundit harness checks it', 'internal term'))
    t('internal terms may tell the build story', not bad('Twenty-five harnesses check each AI show', 'internal term', platform='hn', needs='D4'))
    t('invented proof is refused', bad('The best football podcast, says every AI Pundit fan', 'proof'))
    t('an audience figure is refused', bad('Join 3,000 listeners of the AI Pundits', 'audience figure'))
    t('urgency is refused', bad('Only 5 spots left for AI Pundit shows', 'urgency'))
    t('the not-X-but-Y turn is refused', bad("It's not a podcast, it's six AI Pundits", "it's not X"))
    t('US English is refused', bad('The AI Pundit on soccer', 'US English'))
    t('r/soccer is a name, not US English', not bad('Seen on r/soccer: the AI Pundit view', 'US English'))
    t('a wrong pundit name is refused', bad('The Wind Up, an AI Pundit, has thoughts', 'name is wrong'))
    t('the right pundit name passes', not bad('The Wind-Up, an AI Pundit, has thoughts', 'name is wrong'))
    t('another address is refused', bad('AI Pundit feedback to hello@krishraja.com', 'only address'))
    t('the product inbox passes', not bad('AI Pundit feedback to krish@fulltime.fm', 'only address'))
    t('a public post must say AI', bad('The Doomer has thoughts about your back four', 'must say it is AI'))
    t('a WhatsApp invite need not', not bad('The Doomer has thoughts about your back four', 'must say it is AI', platform='whatsapp'))
    t('two exclamation marks are refused', bad('AI Pundits! Six of them!', 'exclamation'))
    t('a hashtag wall is refused', bad('AI #a #b #c #d #e #f', 'hashtags'))
    t('too many emoji are refused', bad('AI Pundit \U0001F440\U0001F440\U0001F440\U0001F440', 'emoji'))
    t('an X post over 280 is refused', bad('AI ' + 'x' * 290, '280', platform='x', needs='D1'))
    t('an untracked link is refused', bad('AI Pundit show: https://fulltime.fm/', 'not tracked'))
    t('a mismatched creative id is refused', bad(link, 'tracked as', cid_='TT_CLASH_CLIP_C01_H02_V2_20261019'))
    t('a bad creative id is refused', bad('AI Pundit', 'creative_id', cid_='clip-1'))
    t('a creative id for another platform is refused', bad('AI Pundit', 'platform is tiktok', cid_='YT_CLASH_SHORT_C01_H01_V1_20261019'))
    thin = tracked(f'https://fulltime.fm/?drop={drop_thin}&pundit=zen', 'WA_TRIBE_INVITE_C02_H01_V1_20261019')
    t('a push to a thin rail is refused', bad(f'Leeds v Man Utd, AI Pundit takes: {thin}', '1 of 6', platform='whatsapp', cid_='WA_TRIBE_INVITE_C02_H01_V1_20261019'))
    t('a held push to a thin rail passes', not errs(f'Hear it: {thin}', platform='whatsapp', needs='RAIL', cid_='WA_TRIBE_INVITE_C02_H01_V1_20261019'))
    bare = tracked('https://fulltime.fm/', 'WA_TRIBE_INVITE_C02_H01_V1_20261019')
    t('a bare Today link follows the newest match', bad(f'Hear it: {bare}', '1 of 6', platform='whatsapp', cid_='WA_TRIBE_INVITE_C02_H01_V1_20261019'))
    nobody = tracked(f'https://fulltime.fm/?drop={drop_full}&pundit=romantic', cid)
    t('a link to an AI Pundit who made no show is refused', bad(f'AI Pundit: {nobody}', 'made no show'))
    gone = tracked('https://fulltime.fm/?drop=cccccccc-0000-4000-8000-000000000003', cid)
    t('a link to a match Today cannot show is refused', bad(f'AI Pundit: {gone}', 'not a match Today can show'))
    t('nothing pushes blind', bad(f'AI Pundit: {link}', 'not read', state={'rail': None, 'rulings': on}))
    t('a privacy link is not a push', not bad('AI Pundit privacy: ' + tracked('https://fulltime.fm/legal/privacy', cid), '1 of 6'))
    t('a wrong score beside a club is refused', bad('AI Pundits on Crystal Palace 2-1 Nottingham Forest', 'not the result'))
    t('the right score passes', not bad('AI Pundits on Crystal Palace 3-1 Nottingham Forest', 'not the result'))
    t('the score either way round passes', not bad('AI Pundits on Nottingham Forest 1-3 at home to Crystal Palace', 'not the result'))
    two = {'rail': rail + [{'drop': 'dddddddd-0000-4000-8000-000000000004', 'date': '2026-10-04', 'home': 'Crystal Palace',
                            'away': 'Everton', 'score': [0, 0], 'pundits': ['zen'], 'fill': 1}], 'rulings': on}
    t('a club on the rail twice: either result passes', not bad('AI Pundits on Crystal Palace 3-1 Nottingham Forest', 'not the result', state=two))
    t('a club on the rail twice: a wrong score still fails', bad('AI Pundits on Crystal Palace 4-1', 'not the result', state=two))
    t('a date beside a club is not a score', not bad('AI Pundits on Crystal Palace, 2026-10-11', 'not the result'))
    off = {'rail': rail, 'rulings': {}}
    t('a gated channel waits on its ruling', bad('AI Pundit', 'waits on ruling D1', state=off))
    t('a gated draft marked with its ruling passes', not errs('AI Pundit', needs='D1', state=off))
    t('a creator note waits on D5', bad('AI Pundit reaction, labelled Ad', 'D5', platform='creator', state=off))
    t('a creator note must say Ad', bad('React to the AI Pundit', 'labelled "Ad"', platform='creator'))
    t('needs must be a ruling or RAIL', bad('AI Pundit', 'needs "soon"', needs='soon'))
    t('a brief\'s notes are not copy', not errs('Must not appear: broadcast footage, league marks, betting odds, Gary Neville\nOn screen: The Doomer, an AI Pundit, on the wobble', platform='other'))
    t('a brief\'s on-screen line gets the copy rules', bad('Shot 1: covers\nOn screen: every match, six AI Pundits', 'every-match', platform='other'))
    t('a brief\'s em dash is still refused', bad('Shot 1 \u2014 covers', 'em dash', platform='other'))
    t('a brief\'s link is still tracked', bad('Landing: https://fulltime.fm/', 'not tracked', platform='other'))
    t('a report can state money', not bad('Model spend $14 this week', 'price', platform='other'))
    t('an unknown kind is refused', any('kind' in e for e in check_pack({**good, 'kind': 'pitches'}, st)))
    t('a pack without fulltime_sha is refused', any('fulltime_sha' in e for e in check_pack({**good, 'fulltime_sha': ''}, st)))
    t('a numbers row needs a note', any('note' in e for e in check_pack({**good, 'kind': 'numbers', 'items': [], 'numbers': [{'platform': 'posthog', 'users': 3}]}, st)))
    t('a guessed number is refused', any('number read today' in e for e in check_pack({**good, 'kind': 'numbers', 'items': [], 'numbers': [{'platform': 'posthog', 'users': 'about 3', 'note': 'x'}]}, st)))
    t('the gate opens on a full newest match', push_gate(list(reversed(rail)))['open'])
    t('the gate opens on an older full match, naming it', push_gate(rail)['open'] and 'Crystal Palace' in push_gate(rail)['why'])
    t('the gate holds with no full match', not push_gate([rail[0]])['open'])
    t('the gate holds when the rail was not read', not push_gate(None)['open'])
    index = ('| Need | Read first | Then |\n|---|---|---|\n'
             '| Know where it is going | [`22-vision-and-beta.md`](./22-vision-and-beta.md) | [`12-roadmap.md`](./12-roadmap.md) |\n'
             '| Market the live beta | [`21-go-to-market-agent.md`](./21-go-to-market-agent.md) | [`07-marketing.md`](./07-marketing.md) |\n'
             '| Know where it is right now | [`../NOW.md`](../NOW.md) | [`product-state.json`](./product-state.json) |\n'
             '| Change the product | [`00-product.md`](./00-product.md) | x |')
    paths, found = canon_paths(index)
    t('canon follows the docs index, in its order', found and paths[:5] == ['docs/22-vision-and-beta.md', 'docs/12-roadmap.md',
                                                                           'docs/21-go-to-market-agent.md', 'docs/07-marketing.md', 'NOW.md'])
    t('canon always adds the brand and legal docs', 'docs/01-brand.md' in paths and 'docs/11-legal.md' in paths)
    t('no routing rows falls back to the always-read list', canon_paths('# nothing') == (list(ALWAYS_CANON), False))
    doc = '# T\n\n## Voice\nno filler\n### sub\nmore\n\n## Assets\nmarks'
    t('a section runs to the next heading of its level', section(doc, '## Voice') == '## Voice\nno filler\n### sub\nmore')
    t('a missing section is None', section(doc, '## Nine') is None)
    t('a JSON key is a section', section('{"commercialState": {"b": 1, "a": 2}}', 'commercialState') == '{"a": 2, "b": 1}')
    roadmap = '## Decision log\n\n### 2026-10-20 - Invite-led at scale\n\nx\n\n### 2026-10-16 - A pilot beta\n'
    t('decisions come from the log', decisions(roadmap) == ['2026-10-20 - Invite-led at scale', '2026-10-16 - A pilot beta'])
    rs = {'D1': {'status': 'approved', 'evidence': '2026-10-20 - Invite-led at scale', 'unlocks': ['tiktok']},
          'D4': {'status': 'approved', 'evidence': '2026-10-21 - Krish names Full Time', 'unlocks': ['hn']},
          'D5': {'status': 'approved', 'evidence': '2026-10-20 - Invite-led at scale', 'requires': ['D7'], 'unlocks': ['creator']},
          'D7': {'status': 'pending', 'evidence': '', 'unlocks': []}}
    rst = rulings_state(roadmap, rs)
    t('an approved ruling in the decision log is in force', rst['D1']['in_force'])
    t('an approved ruling missing from the log is not', not rst['D4']['in_force'] and not rst['D4']['recorded'])
    t('a ruling that needs another waits for it', not rst['D5']['in_force'])
    files = {'docs/README.md': index, 'docs/22-vision-and-beta.md': 'v', 'docs/12-roadmap.md': roadmap,
             'docs/21-go-to-market-agent.md': 'g', 'docs/07-marketing.md': 'm', 'NOW.md': 'n',
             'docs/product-state.json': '{}', 'docs/01-brand.md': 'b', 'docs/00-product.md': 'p',
             'docs/09-growth.md': 'gr', 'docs/11-legal.md': 'l'}
    sst = {'sha': 'a' * 40, 'rules_ok': True, 'canon': {p: digest(files.get(p))[:16] for p in paths}, 'synced_at': synced}
    global RULES_BASIS
    saved = RULES_BASIS
    RULES_BASIS = fingerprints(files)
    try:
        t('fresh when full-time has not moved', freshness({'fulltime_sha': 'aaaaaaa'}, sst, lambda: 'a' * 40, lambda p, s: files.get(p)) == [])
        t('fresh when full-time moved but no canon changed', freshness({'fulltime_sha': 'aaaaaaa'}, sst, lambda: 'b' * 40, lambda p, s: files.get(p)) == [])
        t('fresh when only the steward rewrote NOW.md', freshness({'fulltime_sha': 'aaaaaaa'}, sst, lambda: 'b' * 40, lambda p, s: {**files, 'NOW.md': 'n2'}.get(p)) == [])
        moved = {**files, 'docs/07-marketing.md': 'm changed'}
        t('stale when a canon file changed', any('07-marketing' in e for e in freshness({'fulltime_sha': 'aaaaaaa'}, sst, lambda: 'b' * 40, lambda p, s: moved.get(p))))
        t('stale when the pack names another sync', any('last sync' in e for e in freshness({'fulltime_sha': 'bbbbbbb'}, sst, lambda: 'a' * 40, lambda p, s: files.get(p))))
        t('stopped when rules changed', any('rules changed' in e for e in freshness({'fulltime_sha': 'aaaaaaa'}, {**sst, 'rules_ok': False}, lambda: 'a' * 40, lambda p, s: files.get(p))))
        t('stopped with no sync', any('no sync' in e for e in freshness({'fulltime_sha': 'aaaaaaa'}, None, lambda: 'a' * 40, lambda p, s: None)))
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=27)).isoformat()
        t('stale when the sync is over 26 hours old', any('26' in e for e in freshness({'fulltime_sha': 'aaaaaaa'}, {**sst, 'synced_at': old}, lambda: 'a' * 40, lambda p, s: files.get(p))))
    finally:
        RULES_BASIS = saved
    t('RULES_BASIS is filled in', all(v != 'FILL' and len(v) == 16 for v in RULES_BASIS.values()))
    t('RULES_BASIS covers every rules source', set(RULES_BASIS) == {f'{p} {s}' for p, s in RULES_SOURCES})
    import inspect
    t('a publish compares only with the published copy', 'load_state(published_only=publish)' in inspect.getsource(sync))
    rulings = load_rulings()
    t('rulings.json names D1 to D7, ORGANIC and RELEASE',
      sorted(rulings) == sorted([f'D{i}' for i in range(1, 8)] + ['ORGANIC', 'RELEASE']))
    t('every ruling has the documented fields', all(set(r) == {'title', 'recommendation', 'unlocks', 'requires', 'status',
                                                               'date', 'words', 'evidence'} for r in rulings.values()))
    t('every ruling a ruling requires exists', all(q in rulings for r in rulings.values() for q in r.get('requires', [])))
    t('ORGANIC comes into force only with D1', rulings['ORGANIC'].get('requires') == ['D1'])
    t('every gated platform is a platform', all(p in PLATFORMS for r in rulings.values() for p in r.get('unlocks', [])))
    t('every brand channel has a creative id code and a utm_source', all(
        p in PLATFORMS and PREFIX[p] in SOURCE and CREATIVE_ID.match(PREFIX[p] + '_CLASH_POST_C01_H01_V1_20261027')
        for p in policy.BRAND_CHANNELS))
    t('the brand WhatsApp Channel is apart from listener sharing',
      'whatsapp_channel' in policy.BRAND_CHANNELS and 'whatsapp' not in policy.BRAND_CHANNELS)
    t('policy and growth hold the same rail gate', policy.RAIL_MIN == RAIL_MIN)
    take = {'platform': 'tiktok', 'creative_id': cid, 'account_scope': 'brand', 'identity_ref': 'tiktok',
            'drop_id': drop_thin, 'pundits': ['zen'], 'whole_match': False, 'holds': [],
            'text': 'The Reporter, an AI Pundit, on Leeds United 1-1 Manchester United: '
                    + tracked(f'https://fulltime.fm/?drop={drop_thin}&pundit=zen', cid)}
    organic = {**st, 'rulings': {**on, 'ORGANIC': {'in_force': True}}}
    t('ORGANIC in force: a published take passes with no RELEASE or RAIL hold', check_pack({**good, 'items': [take]}, organic) == [])
    t('ORGANIC not in force: the same take still waits for RELEASE and RAIL',
      any('RELEASE' in e for e in check_pack({**good, 'items': [take]}, {**st, 'rail': [rail[0]]})))
    t('ORGANIC in force: a take on an AI Pundit with no show is held for RAIL',
      any('per-take gate' in e for e in check_pack({**good, 'items': [{**take, 'pundits': ['gaffer']}]}, organic)))
    t('ORGANIC in force: a whole-match post still needs four of six',
      any('whole-match' in e for e in check_pack({**good, 'items': [{**take, 'whole_match': True}]}, organic)))
    t('ORGANIC in force: a take that does not say whole_match is held, never read as per-take',
      any('whole_match' in e for e in check_pack({**good, 'items': [{k: v for k, v in take.items() if k != 'whole_match'}]}, organic)))
    changes = Path(HERE, 'CHANGES.md').read_text(encoding='utf-8')
    for rid, r in rulings.items():
        t(f'{rid} is pending, approved or declined', r.get('status') in ('pending', 'approved', 'declined'))
        if r.get('status') == 'approved':
            t(f'{rid} approved names its decision-log heading', bool(r.get('evidence')))
            t(f'{rid} approved has Krish\'s words in CHANGES.md', rid in changes)
    agents = Path(HERE, 'AGENTS.md').read_text(encoding='utf-8')
    autos = json.loads(Path(HERE, 'automations.json').read_text(encoding='utf-8'))['automations']
    for f in sorted(os.listdir(os.path.join(HERE, 'jobs'))):
        body = Path(HERE, 'jobs', f).read_text(encoding='utf-8')
        m = re.search(r'Kind `(\w+)`', body)
        t(f'jobs/{f} names a kind', bool(m) and m.group(1) in KINDS or f == 'sync.md')
        t(f'jobs/{f} is on the schedule in AGENTS.md', f'jobs/{f}' in agents)
        t(f'jobs/{f} starts with a sync', 'growth.py sync' in body)
    for au in autos:
        t(f'automation "{au["name"]}" runs a job that exists', os.path.exists(os.path.join(HERE, au['job'])))
        t(f'automation "{au["name"]}" has a schedule rule', au['schedule'].startswith('RRULE:FREQ='))
        t(f'automation "{au["name"]}" never asks to post', not re.search(r'\b(post|publish|send|upload|boost)\b', au['prompt'], re.I))
    t('every job file has an automation', {a['job'] for a in autos} == {f'jobs/{f}' for f in os.listdir(os.path.join(HERE, 'jobs'))})
    t('every automation ends with the Control Center loop', all('python3 growth.py cc ' in au['prompt'] for au in autos))
    from engine import reporting as protocol
    example = json.loads(Path(HERE, 'docs', 'control-center', 'engine-report.example.json').read_text(encoding='utf-8'))
    t('the protocol digest reproduces the worked example', protocol.seal(example)['payload_sha256'] == example['payload_sha256'])
    flow = Path(HERE, '.github', 'workflows', 'control-center.yml').read_text(encoding='utf-8')
    t('the dispatch workflow wakes on cc-growth-directive with read-only contents',
      'types: [cc-growth-directive]' in flow and 'contents: read' in flow and 'upload-artifact' not in flow)
    for f in ('PLAYBOOK.md', 'BROWSER.md', 'CHANGES.md', 'COPY.md', 'rulings.json', 'knowledge/README.md',
              'knowledge/full-time-1000-users-playbook.md', 'knowledge/sources.json',
              'knowledge/copywriting-offers-demand-corpus.md', 'knowledge/copywriting-offers-demand-corpus-summary.md'):
        t(f'{f} exists', os.path.exists(os.path.join(HERE, f)))
    ignored = Path(HERE, '.gitignore').read_text(encoding='utf-8')
    t('local/ is never committed (the repository is public)', re.search(r'^/?local/?$', ignored, re.M) is not None)
    print(f'growth-fulltime self-test passed: {n} checks')


ENGINE_COMMANDS = ('run', 'history', 'creative', 'experiment', 'metrics', 'assets', 'export', 'cc',
                   'spec', 'formats', 'pack', 'buffer', 'library', 'session', 'dispatch', 'audience', 'ga4',
                   'fixtures', 'actions')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'standards':
        from engine.creative_system import main as standards_main
        raise SystemExit(standards_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] in ENGINE_COMMANDS:
        from engine.cli import main as operations_main
        return operations_main(sys.argv[1:], sys.modules[__name__])
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--self-test', action='store_true')
    sub = ap.add_subparsers(dest='cmd')
    sy = sub.add_parser('sync'); sy.add_argument('--publish', action='store_true'); sy.add_argument('--quiet', action='store_true')
    cn = sub.add_parser('canon'); cn.add_argument('--full', action='store_true')
    sub.add_parser('rail')
    lk = sub.add_parser('link'); lk.add_argument('url'); lk.add_argument('creative_id')
    c = sub.add_parser('check'); c.add_argument('file')
    s = sub.add_parser('post'); s.add_argument('file')
    r = sub.add_parser('read'); r.add_argument('--days', type=int, default=7); r.add_argument('--kind')
    sub.add_parser('doctor')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.cmd == 'sync':
        st = sync(publish=a.publish, quiet=a.quiet)
        print(f'fulltime_sha: {st["sha"]}')
        print(f'push gate: {"OPEN" if st["push"]["open"] else "HOLD"} ({st["push"]["why"]})')
        if not st['rules_ok']:
            print('STOP: Full Time\'s rules changed. No pack can pass until growth.py is updated (AGENTS.md, rule 2).')
            sys.exit(2)
        return
    if a.cmd == 'canon':
        st = load_state()
        if not st:
            sys.exit('No sync yet: run python3 growth.py sync first.')
        for i, p in enumerate(st['canon'], 1):
            print(f'{i}. {p}  (full-time {st["sha"][:10]})')
            if a.full:
                print('\n' + (raw(p, st['sha']) or '(missing at this commit)') + '\n' + '-' * 72)
        return
    if a.cmd == 'rail':
        rail = read_rail()
        print('\n'.join(rail_rows(rail)) if rail else 'No match has a published show.')
        gate = push_gate(rail, load_state() or {})
        print(f'\npush gate: {"OPEN" if gate["open"] else "HOLD"} ({gate["why"]})')
        return
    if a.cmd == 'link':
        try:
            print(tracked(a.url, a.creative_id))
        except ValueError as e:
            sys.exit(str(e))
        return
    if a.cmd in ('check', 'post'):
        pack = json.loads(Path(a.file).read_text(encoding='utf-8'))
        st = load_state()
        errs = check_pack(pack, st)
        try:
            errs += freshness(pack, st, head_sha, raw)
        except (urllib.error.URLError, OSError) as e:
            errs.append(f'could not confirm full-time is unchanged since the sync ({e}); with no answer, nothing passes')
        if errs:
            print('Not ready:\n  ' + '\n  '.join(errs))
            sys.exit(1)
        items = pack.get('items') or []
        held = sum(1 for it in items if policy.holds(it))
        if a.cmd == 'check':
            print(f'ready: {len(items)} drafts ({len(items) - held} to go today, {held} held), written against full-time {pack["fulltime_sha"][:10]}')
            return
        return store_pack(pack)
    if a.cmd == 'read':
        print(json.dumps(read_packs(a.days, a.kind), indent=1))
        return
    if a.cmd == 'doctor':
        sys.exit(doctor())
    ap.print_help()


if __name__ == '__main__':
    main()
