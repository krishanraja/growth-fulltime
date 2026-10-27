"""The Match Clock's fixtures reader (crew/match_clock/card.md).

It reads one London week of Premier League fixtures and ranks them for the weekly spec.
Two routes, and neither guesses a fixture:

- import: a JSON reply a session saved from Control Center's football-data operation, or
  from football-data.org (v4 `matches`) or API-Football (v3 `response`), checked and
  normalised;
- fetch: football-data.org v4 directly, with the token from FOOTBALL_DATA_TOKEN or the
  ignored file local/football-data/token. The token is never printed, logged or stored.

Names are the product's (API-Football's, which the rail uses), so a fixture lines up with
the rail and the club colours. Rank puts the derbies first (RIVALRIES, a starting table
Krish may strike from at G1), then kickoff. The result is local/fixtures/latest.json with
its read_at, which engine.crew.fixtures_fresh checks before anything is ranked or timed.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from .clock import LONDON
from .records import atomic_json, instant, now

FOLDER = Path('fixtures')
FOOTBALL_DATA = 'https://api.football-data.org/v4/competitions/PL/matches'
TOKEN_FILE = Path('football-data') / 'token'
# football-data.org's full names, mapped to the names the product's rail uses.
NAMES = {
    'Tottenham Hotspur': 'Tottenham', 'Brighton & Hove Albion': 'Brighton', 'Wolverhampton Wanderers': 'Wolves',
    'West Ham United': 'West Ham', 'Newcastle United': 'Newcastle', 'Leeds United': 'Leeds',
    'Coventry City': 'Coventry', 'Leicester City': 'Leicester', 'Ipswich Town': 'Ipswich',
    'Sheffield United': 'Sheffield Utd', 'Bournemouth': 'Bournemouth', 'Hull City': 'Hull City',
}
SUFFIX = re.compile(r'^(?:AFC|FC)\s+|\s+(?:AFC|FC)$')
# Derbies and long rivalries among clubs that have been in the Premier League. A starting
# table, not a ruling: Krish strikes a fixture at G1 and it stays off that week.
RIVALRIES = {frozenset(pair) for pair in (
    ('Arsenal', 'Tottenham'), ('Liverpool', 'Everton'), ('Manchester City', 'Manchester United'),
    ('Liverpool', 'Manchester United'), ('Newcastle', 'Sunderland'), ('Crystal Palace', 'Brighton'),
    ('Nottingham Forest', 'Leicester'), ('Chelsea', 'Arsenal'), ('Chelsea', 'Tottenham'),
    ('West Ham', 'Tottenham'), ('Chelsea', 'Fulham'), ('Wolves', 'Aston Villa'), ('Leeds', 'Manchester United'),
    ('Arsenal', 'Manchester United'), ('Liverpool', 'Manchester City'), ('Chelsea', 'West Ham'),
)}


def club(name):
    """A provider's club name as the product's rail spells it."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError('a fixture needs both club names')
    bare = SUFFIX.sub('', name.strip()).strip()
    return NAMES.get(bare, bare)


def _row(source, ref, kickoff, home, away):
    if not isinstance(ref, (str, int)) or isinstance(ref, bool) or not str(ref).strip():
        raise ValueError('a fixture needs its provider id')
    try:
        instant(kickoff)
    except (ValueError, TypeError):
        raise ValueError(f'fixture {ref}: kickoff must be a date and time with its UTC offset') from None
    home, away = club(home), club(away)
    if home == away:
        raise ValueError(f'fixture {ref}: a club cannot play itself')
    return {'fixture_ref': f'{source}:{ref}', 'kickoff': kickoff.replace('+00:00', 'Z'),
            'home': home, 'away': away, 'rivalry': frozenset((home, away)) in RIVALRIES}


def normalise(reply):
    """[(fixture rows), source] from a football-data.org v4 or API-Football v3 reply."""
    if isinstance(reply, dict) and isinstance(reply.get('matches'), list):
        rows = [_row('fd', m.get('id'), m.get('utcDate'), (m.get('homeTeam') or {}).get('name'),
                     (m.get('awayTeam') or {}).get('name')) for m in reply['matches'] if isinstance(m, dict)]
        return rows, 'football-data.org v4'
    if isinstance(reply, dict) and isinstance(reply.get('response'), list):
        rows = []
        for m in reply['response']:
            if not isinstance(m, dict):
                continue
            if (m.get('league') or {}).get('id') not in (39, None):
                continue                                     # Premier League only (af_39)
            teams = m.get('teams') or {}
            rows.append(_row('af', (m.get('fixture') or {}).get('id'), (m.get('fixture') or {}).get('date'),
                             (teams.get('home') or {}).get('name'), (teams.get('away') or {}).get('name')))
        return rows, 'API-Football v3'
    raise ValueError('not a fixtures reply: expected football-data.org "matches" or API-Football "response"')


def week_window(day):
    """Monday to Sunday, London, holding day."""
    start = day - dt.timedelta(days=day.weekday())
    return start, start + dt.timedelta(days=6)


def rank(rows, start, end):
    """The week's fixtures, in the window (London), derbies first then kickoff, ranked 1 up."""
    def day(row):
        return instant(row['kickoff']).astimezone(LONDON).date()
    keep = [r for r in rows if start <= day(r) <= end]
    seen, out = set(), []
    for r in sorted(keep, key=lambda r: (not r['rivalry'], instant(r['kickoff']), r['home'])):
        if r['fixture_ref'] in seen:
            continue
        seen.add(r['fixture_ref'])
        out.append({**r, 'rank': len(out) + 1})
    return out


def save(local, reply, day, source_note=None, read_at=None):
    """Check, rank and keep a reply as local/fixtures/latest.json (and a dated copy)."""
    rows, source = normalise(reply)
    start, end = week_window(day)
    ranked = rank(rows, start, end)
    data = {'read_at': read_at or now(), 'source': source_note or source,
            'window': {'start': start.isoformat(), 'end': end.isoformat(), 'timezone': 'Europe/London'},
            'fixtures': ranked}
    folder = Path(local) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    atomic_json(folder / f'{start.isoformat()}.json', data)
    atomic_json(folder / 'latest.json', data)
    return {'saved': str(folder / 'latest.json'), 'source': data['source'], 'fixtures': len(ranked),
            'window': data['window'], 'top': [f'{r["rank"]}. {r["home"]} v {r["away"]}' + (' (derby)' if r['rivalry'] else '')
                                              for r in ranked[:5]]}


def token(local):
    value = os.environ.get('FOOTBALL_DATA_TOKEN', '').strip()
    if not value:
        path = Path(local) / TOKEN_FILE
        value = path.read_text(encoding='utf-8').strip() if path.is_file() else ''
    return value or None


def fetch(local, day, opener=urllib.request.urlopen):
    """football-data.org v4 for the London week holding day. Never prints the token."""
    secret = token(local)
    if not secret:
        raise ValueError('no football-data.org token: set FOOTBALL_DATA_TOKEN or put it in '
                         'local/football-data/token, or import a reply saved from Control Center')
    start, end = week_window(day)
    # A day either side: kickoffs are in UTC and the week is London's.
    query = urllib.parse.urlencode({'dateFrom': (start - dt.timedelta(days=1)).isoformat(),
                                    'dateTo': (end + dt.timedelta(days=1)).isoformat()})
    request = urllib.request.Request(f'{FOOTBALL_DATA}?{query}', headers={'X-Auth-Token': secret,
                                                                          'Accept': 'application/json'})
    del secret
    try:
        with opener(request, timeout=20) as reply:
            body = json.loads(reply.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        raise ValueError(f'football-data.org answered {error.code}') from None
    except (urllib.error.URLError, OSError, ValueError):
        raise ValueError('football-data.org could not be read') from None
    return save(local, body, day, 'football-data.org v4')


def latest(local):
    path = Path(local) / FOLDER / 'latest.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
