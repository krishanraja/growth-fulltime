"""Krish's actions today, and the engine's own to-do, computed from what the engine holds.

Every report carries them (Control Center's activity lines), `growth.py actions` prints
them, and NOW.md shows the public part. Nothing here asks twice or guesses: an action
closes when the engine can see it done (a verified identity, the Buffer allowlist, the
handcrafted switch, ga4_landings in the directive, a ruling recorded), and a 'manual' one
closes only when a session records Krish's confirmation in engine/config/owner-actions.json.

Krish's answers come first (G2, then G1, then the one ruling asked), then the posts he
approved and has not yet made, then at most three one-off setup actions. His daily work
stays within twenty minutes (AGENTS.md); a one-off setup action is shown with its own
minutes and never counted against the day.
"""
import datetime as dt
import json
from pathlib import Path

from . import gates, policy
from .clock import LONDON
from .records import instant

OWNER_FILE = Path(__file__).resolve().parent / 'config' / 'owner-actions.json'
DAILY_MINUTES = 20
SETUP_SHOWN = 3
RULING_ORDER = ('D7', 'D2', 'D3')
PUSHED = ('tiktok', 'instagram', 'youtube')          # ruling 2: the three pushed daily
CHECKS = ('handcrafted', 'identity_verified', 'allowlist', 'ga4_landings', 'manual')


def load_owner(path=OWNER_FILE):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    out = []
    for n, entry in enumerate(data.get('actions') or [], start=1):
        if not isinstance(entry, dict) or entry.get('done_when') not in CHECKS:
            raise ValueError(f'owner action {n} must name done_when, one of ' + ', '.join(CHECKS))
        if not isinstance(entry.get('minutes'), int) or entry['minutes'] <= 0 or not entry.get('text'):
            raise ValueError(f'owner action {n} needs its text and whole minutes')
        out.append(entry)
    return out


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _seen(local, state, directive):
    """What the engine can see is done, each True, False or None when it cannot tell."""
    last = _read_json(Path(local) / 'control-center' / 'last.json') or {}
    autonomy = last.get('autonomy')
    identities = (state or {}).get('brand_identities') or {}
    identity = any(policy.identity_verified(x, p) for x in identities.values() for p in PUSHED)
    try:
        from . import buffer_read
        buffer_read.load_allowlist(local)
        allowlist = True
    except (ValueError, OSError):
        allowlist = False
    body = (directive or {}).get('directive') if isinstance(directive, dict) else None
    landings = None if body is None else 'ga4_landings' in body
    return {'handcrafted': None if autonomy is None else autonomy == 'handcrafted',
            'identity_verified': identity, 'allowlist': allowlist, 'ga4_landings': landings}


def _next_ruling(rulings):
    pending = [rid for rid, r in sorted((rulings or {}).items())
               if r.get('status') == 'pending' and rid != 'RELEASE']
    ordered = [rid for rid in RULING_ORDER if rid in pending] + [rid for rid in pending if rid not in RULING_ORDER]
    return ordered[0] if ordered else None


def _unposted(local):
    """Items of approved G2 asks Krish kept and has not yet posted (no permalink read back)."""
    ledger, out = gates.verdicts(local), []
    for _, gate in gates._gates(local):
        if gate.get('kind') != 'g2' or gate.get('decision') != 'approved':
            continue
        pid, sha = gate['proposal']['proposal_id'], gate['proposal']['payload_sha256']
        rejected = {r.get('creative_id') for r in ledger if r.get('proposal_id') == pid
                    and r.get('payload_sha256') == sha and r.get('verdict') == 'reject'}
        held = gate.get('receipts') or {}
        out += [(pid, cid, channel) for cid, channel in gates._pack_items(gate)
                if cid not in rejected and cid not in held]
    return out


def _week(day):
    year, week, _ = day.isocalendar()
    return f'{year}-W{week:02d}'


def compute(local, today, state=None, rulings=None, directive=None, now=None, owner=None):
    """{'krish': [...], 'engine': [...], 'minutes': his minutes today, 'over_budget': bool}.
    Each action is {'id', 'kind', 'minutes', 'text'}; kind is decision, post or setup."""
    local = Path(local)
    now = now or dt.datetime.now(dt.timezone.utc)
    krish, engine = [], []
    open_gates = [g for _, g in gates._gates(local) if not g.get('settled_at')]
    for kind, minutes, text in (
            ('g2', 10, "Answer today's matchday pack in Control Center: Clear posts every item, Change it first "
                       'gives each item a verdict, Purge rejects them all.'),
            ('g1', 5, "Sign this week's plan (G1) in Control Center, then its credits ask if one follows.")):
        asks = sorted(g['proposal']['proposal_id'] for g in open_gates if g.get('kind') == kind)
        if asks:
            krish.append({'id': asks[0], 'kind': 'decision', 'minutes': minutes, 'text': text})
    ruling = _next_ruling(rulings)
    if ruling:
        title = (rulings[ruling].get('title') or '').rstrip('.')
        krish.append({'id': f'ruling-{ruling}', 'kind': 'decision', 'minutes': 2,
                      'text': f'Rule on {ruling} in Control Center: {title}.'})
    unposted = _unposted(local)
    if unposted:
        channels = sorted({c for _, _, c in unposted if c})
        krish.append({'id': 'post-approved', 'kind': 'post', 'minutes': 2 * len(unposted),
                      'text': f'Post the {len(unposted)} item{"s" if len(unposted) != 1 else ""} you approved by hand '
                              f'in Buffer ({", ".join(channels) or "their channels"}); the engine reads the permalinks back.'})
    seen = _seen(local, state, directive)
    setup = []
    for entry in owner if owner is not None else load_owner():
        check = entry['done_when']
        if entry.get('done_on') or (check != 'manual' and seen.get(check) is True):
            continue
        note = ' (the engine cannot see this yet; it shows until it can)' if seen.get(check) is None and check != 'manual' else ''
        setup.append({'id': entry['id'], 'kind': 'setup', 'minutes': entry['minutes'], 'text': entry['text'] + note})
    krish += setup[:SETUP_SHOWN]
    minutes = sum(a['minutes'] for a in krish if a['kind'] != 'setup')

    # The engine's own to-do: what the next session does without asking him.
    fixtures = _read_json(local / 'fixtures' / 'latest.json') or {}
    try:
        fresh = instant(fixtures.get('read_at', '')).astimezone(LONDON).date() == today
    except ValueError:
        fresh = False
    if not fresh:
        engine.append({'id': 'fixtures', 'text': 'Read this week\'s Premier League fixtures (growth.py fixtures) '
                                                'before ranking or timing any take.'})
    try:
        from . import invariants
        stale = invariants.now_state_errors(today=today)
    except (OSError, ValueError):
        stale = ['NOW.md could not be read']
    if stale:
        engine.append({'id': 'north-star-line', 'text': 'Update the North Star line in NOW.md for this week: '
                                                        + stale[0]})
    if today.weekday() >= 4:
        nxt = _week(today + dt.timedelta(days=7 - today.weekday()))
        has = any(gate.get('kind') == 'g1' and nxt in json.dumps(gate['proposal'].get('exact_payload', ''))
                  for _, gate in gates._gates(local))
        if not has:
            engine.append({'id': 'next-spec', 'text': f'Propose the {nxt} spec (G1) so Krish can sign it before Monday.'})
    if unposted:
        engine.append({'id': 'receipts', 'text': 'Read back Buffer receipts for the approved items '
                                                 '(growth.py buffer receipts --record).'})
    return {'krish': krish, 'engine': engine, 'minutes': minutes, 'over_budget': minutes > DAILY_MINUTES}


def lines(result):
    """Activity lines for the report: his actions numbered, then the engine's to-do."""
    out = []
    krish = result['krish']
    if not krish:
        out.append('Your actions today: none. Nothing waits on you.')
    for n, a in enumerate(krish, start=1):
        label = 'one-off' if a['kind'] == 'setup' else a['kind']
        out.append(f'Your action {n} of {len(krish)} ({a["minutes"]} min, {label}): {a["text"]}')
    if result['over_budget']:
        out.append(f'Your answers and posts today come to {result["minutes"]} minutes, over the '
                   f'{DAILY_MINUTES}-minute day: the engine asks fewer things tomorrow.')
    for a in result['engine']:
        out.append(f'Engine to-do: {a["text"]}')
    return [x[:500] for x in out]
