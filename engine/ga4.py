"""A direct, read-only Google Analytics 4 reader for the Measurement Analyst.

Ruling (Krish, 2026-10-27): "Direct read-only API". Google Analytics 4 runs on
fulltime.fm (measurement ID G-W2QL8RKFJ1, page views only). This module reads
one aggregate report through the Google Analytics Data API: new users, sessions
and engaged sessions by session source, medium, campaign and manual ad content
(the engine's utm_content, which carries the creative ID). It never asks for a
user, client or device dimension, and it has no write verb. These are web
landings on fulltime.fm, never listeners, so the export stays apart from every
listener number. Consent item D7 is still open; reading aggregates does not
close it.

Credentials come from GA4_CLIENT_ID, GA4_CLIENT_SECRET, GA4_REFRESH_TOKEN and
GA4_PROPERTY_ID, else from the ignored local/ga4/oauth.json, which
`growth.py ga4 authorize` writes once on Krish's own machine
(docs/GA4-ACCESS.md). No credential or access token is ever printed, logged,
written to an export or put in an exception: every failure is a lower_snake code.
"""
import argparse
import base64
import datetime as dt
import getpass
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from . import policy, reporting
from .control_center import opener
from .records import atomic_json

MEASUREMENT_ID = 'G-W2QL8RKFJ1'
QUERY_REF = 'ga4-data-v1beta:runReport:landings-by-creative:v1'
SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
DATA_URL = 'https://analyticsdata.googleapis.com'
TIMEOUT = 20
LIMIT = 2 * 1024 * 1024
PAGE = 10000
MAX_ROWS = 100000
FILE = Path('ga4') / 'oauth.json'
ENV = {'client_id': 'GA4_CLIENT_ID', 'client_secret': 'GA4_CLIENT_SECRET',
       'refresh_token': 'GA4_REFRESH_TOKEN', 'property_id': 'GA4_PROPERTY_ID'}
SECRET_FIELDS = ('client_id', 'client_secret', 'refresh_token')
DIMENSIONS = {'sessionSource': 'utm_source', 'sessionMedium': 'utm_medium',
              'sessionCampaignName': 'utm_campaign', 'sessionManualAdContent': 'utm_content'}
METRICS = {'newUsers': 'new_users', 'sessions': 'sessions', 'engagedSessions': 'engaged_sessions'}
PRINTABLE = re.compile(r'[\x21-\x7e]{8,4096}')
PROPERTY = re.compile(r'[0-9]{1,20}')
COUNT = re.compile(r'[0-9]{1,15}')
USER_AGENT = 'growth-fulltime (+https://github.com/krishanraja/growth-fulltime)'
MESSAGES = {
    'missing_ga4_credentials': 'Google Analytics credentials unavailable: set GA4_CLIENT_ID, GA4_CLIENT_SECRET, '
                               'GA4_REFRESH_TOKEN and GA4_PROPERTY_ID, or run growth.py ga4 authorize '
                               '(docs/GA4-ACCESS.md). Nothing was read.',
    'missing_ga4_property_id': 'No Google Analytics property ID: set GA4_PROPERTY_ID, or fill property_id in '
                               'local/ga4/oauth.json, with the number in Admin, Property details. Nothing was read.',
    'ga4_property_id_invalid': 'The property ID must be the number in Admin, Property details, not the G- '
                               'measurement ID. Nothing was read.',
    'ga4_credentials_malformed': 'The Google Analytics credentials are not well formed: run growth.py ga4 '
                                 'authorize again. Nothing was read.',
    'ga4_credentials_exposed': 'local/ga4/oauth.json can be read by other users on this machine: run '
                               'chmod 600 on it. Nothing was read.',
    'unauthorized': 'Google refused the credentials. The refresh token may be revoked or expired: run '
                    'growth.py ga4 authorize again.',
    'forbidden': 'Google refused access to that property: check that the signed-in account can view it and '
                 'that the Google Analytics Data API is enabled in the Cloud project.',
    'not_found': 'Google found no property with that ID: check the number in Admin, Property details.',
    'bad_request': 'Google refused the report request as malformed.',
    'ga4_unavailable': 'Google Analytics did not answer, or asked for fewer requests. Try again later.',
    'redirect_refused': 'Google answered with a redirect, which this reader never follows.',
    'response_too_large': 'The answer was over 2 MB, so it was not read. Try a shorter window.',
    'too_many_rows': 'The report has more than 100,000 rows, so it was not read. Try a shorter window.',
    'bad_response': "Google's answer was not the expected shape, so nothing was kept.",
    'unexpected_status': 'Google answered with an unexpected status, so nothing was kept.',
    'bad_base_url': 'Google endpoints must be https origins with no credentials, query or fragment.',
    'state_mismatch': 'The sign-in answer did not match this request, so it was refused. Nothing was saved.',
    'access_denied': 'Sign-in was cancelled or refused in the browser. Nothing was saved.',
    'no_refresh_token': 'Google returned no refresh token: remove the app at myaccount.google.com/permissions '
                        'and run authorize again. Nothing was saved.',
    'scope_refused': 'Google did not grant exactly read-only Analytics access: run authorize again and allow '
                     'only that. Nothing was saved.',
    'authorize_timeout': 'No sign-in arrived within the time allowed. Nothing was saved.',
    'browser_unavailable': 'No browser could be opened here: run authorize on your own computer. Nothing was saved.',
}
NOT_STARTED = {'missing_ga4_credentials', 'missing_ga4_property_id', 'ga4_property_id_invalid',
               'ga4_credentials_malformed', 'ga4_credentials_exposed', 'bad_base_url'}


class GA4Error(ValueError):
    """A lower_snake code, never a message, body, URL or credential."""

    def __init__(self, code, status=None):
        super().__init__(code)
        self.code = code
        self.status = status


class Credentials(dict):
    """A plain dict whose printed form never shows a value."""

    def __repr__(self):
        return 'Credentials(<redacted>)'

    __str__ = __repr__


class Rows(list):
    """Report rows, with what Google said about them: the property's time zone, and
    whether thresholding or an "(other)" row hid detail."""
    time_zone = None
    thresholded = False
    other_row = False
    pages = 0


# ---------------------------------------------------------------------------
# Credentials: the environment first, then the ignored file.
# ---------------------------------------------------------------------------
def _property_id(value):
    text = str(value if value is not None else '').strip()
    text = text[len('properties/'):] if text.startswith('properties/') else text
    if text and not PROPERTY.fullmatch(text):
        raise GA4Error('ga4_property_id_invalid')
    return text or None


def _read_file(path):
    if not path.is_file():
        return None
    if os.name == 'posix' and path.stat().st_mode & 0o077:
        raise GA4Error('ga4_credentials_exposed')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise GA4Error('ga4_credentials_malformed') from None
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in SECRET_FIELDS):
        raise GA4Error('ga4_credentials_malformed')
    return {**{k: data[k].strip() for k in SECRET_FIELDS}, 'property_id': data.get('property_id')}


def credentials(local_dir, environ=None):
    """The OAuth client, refresh token and numeric property ID, from the environment when
    all three secrets are set there, else from local_dir/ga4/oauth.json (refused when
    other users can read it). None when neither holds them: report missing_ga4_credentials.
    GA4_PROPERTY_ID in the environment, when set, names the property for either source."""
    environ = os.environ if environ is None else environ
    value = lambda key: str(environ.get(ENV[key]) or '').strip()
    if all(value(k) for k in SECRET_FIELDS):
        found, source = {k: value(k) for k in SECRET_FIELDS}, 'environment'
        found['property_id'] = value('property_id')
    else:
        found, source = _read_file(Path(local_dir) / FILE), 'file'
        if found is None:
            return None
        found['property_id'] = value('property_id') or found['property_id']
    if not all(PRINTABLE.fullmatch(found[k]) for k in SECRET_FIELDS):
        raise GA4Error('ga4_credentials_malformed')
    return Credentials(found, property_id=_property_id(found['property_id']), source=source)


# ---------------------------------------------------------------------------
# Transport: https only, no redirects, 20 seconds, 2 MB.
# ---------------------------------------------------------------------------
def _endpoint(url, origin=False):
    """True when this is the 127.0.0.1 stand-in a test runs; refuses anything but https otherwise."""
    parts = urllib.parse.urlsplit(str(url))
    loopback = parts.scheme == 'http' and parts.hostname == '127.0.0.1'
    if ((parts.scheme != 'https' and not loopback) or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or (origin and parts.path not in ('', '/'))):
        raise GA4Error('bad_base_url')
    return loopback


def _post(url, data, headers, loopback):
    head = {'Accept': 'application/json', 'User-Agent': USER_AGENT, **headers}
    request = urllib.request.Request(url, data=data, headers=head, method='POST')
    try:
        with opener(direct=loopback).open(request, timeout=TIMEOUT) as response:
            status, raw = response.status, response.read(LIMIT + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            raw = error.read(LIMIT + 1)
        except OSError:
            raw = b''
        finally:
            error.close()
    except (urllib.error.URLError, OSError, ValueError):
        raise GA4Error('ga4_unavailable') from None
    if 300 <= status < 400:
        raise GA4Error('redirect_refused', status)
    if len(raw) > LIMIT:
        raise GA4Error('response_too_large', status)
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        payload = None
    return status, payload


def _form(fields):
    return urllib.parse.urlencode(fields).encode('ascii')


FORM = {'Content-Type': 'application/x-www-form-urlencoded'}
STATUS_CODES = {400: 'bad_request', 401: 'unauthorized', 403: 'forbidden', 404: 'not_found', 429: 'ga4_unavailable'}


def _refused(status):
    return GA4Error('ga4_unavailable' if status >= 500 else STATUS_CODES.get(status, 'unexpected_status'), status)


def _token_refused(status):
    return GA4Error('unauthorized', status) if status in (400, 401, 403) else _refused(status)


def access_token(creds, token_url=TOKEN_URL):
    """A short-lived access token from the OAuth refresh-token grant. The refresh token goes
    only to the token endpoint, and is never logged or returned."""
    if not creds:
        raise GA4Error('missing_ga4_credentials')
    loopback = _endpoint(token_url)
    status, payload = _post(token_url, _form({
        'grant_type': 'refresh_token', 'client_id': creds['client_id'],
        'client_secret': creds['client_secret'], 'refresh_token': creds['refresh_token']}), FORM, loopback)
    if status != 200:
        raise _token_refused(status)
    token = payload.get('access_token') if isinstance(payload, dict) else None
    if (not isinstance(token, str) or not PRINTABLE.fullmatch(token)
            or str(payload.get('token_type', 'Bearer')).lower() != 'bearer'):
        raise GA4Error('bad_response', status)
    return token


# ---------------------------------------------------------------------------
# The report: aggregate landings by creative, paged until rowCount is reached.
# ---------------------------------------------------------------------------
def _day(value):
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise ValueError('window dates must be YYYY-MM-DD') from None


def report_request(start, end, offset=0):
    """The exact runReport body: four session dimensions, three counts, one date range.
    No user, client or device dimension is ever asked for."""
    return {'dateRanges': [{'startDate': _day(start).isoformat(), 'endDate': _day(end).isoformat()}],
            'dimensions': [{'name': name} for name in DIMENSIONS],
            'metrics': [{'name': name} for name in METRICS],
            'limit': PAGE, 'offset': offset, 'keepEmptyRows': False}


def _page(payload):
    if not isinstance(payload, dict):
        raise GA4Error('bad_response')
    found = payload.get('rows') or []
    if not isinstance(found, list):
        raise GA4Error('bad_response')
    if found:
        names = lambda key: [h.get('name') if isinstance(h, dict) else None for h in payload.get(key) or []]
        if names('dimensionHeaders') != list(DIMENSIONS) or names('metricHeaders') != list(METRICS):
            raise GA4Error('bad_response')
    rows = []
    for row in found:
        try:
            dims = [v['value'] for v in row['dimensionValues']]
            counts = [v['value'] for v in row['metricValues']]
        except (KeyError, TypeError):
            raise GA4Error('bad_response') from None
        if len(dims) != len(DIMENSIONS) or len(counts) != len(METRICS):
            raise GA4Error('bad_response')
        rows.append(dict(zip(list(DIMENSIONS) + list(METRICS), dims + counts)))
    count = payload.get('rowCount')
    if count is not None and (type(count) is not int or count < 0):
        raise GA4Error('bad_response')
    meta = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
    return rows, count, meta


def run_report(creds, start, end, base_url=DATA_URL, *, token_url=TOKEN_URL, access=None):
    """Every row of the landings-by-creative report for one inclusive date range, keyed by
    GA4's own names with GA4's string values. POST /v1beta/properties/<id>:runReport,
    limit 10000, offset paging until rowCount is reached."""
    start, end = _day(start), _day(end)
    if start > end:
        raise ValueError('the report window starts after it ends')
    if not creds:
        raise GA4Error('missing_ga4_credentials')
    property_id = _property_id(creds.get('property_id'))
    if property_id is None:
        raise GA4Error('missing_ga4_property_id')
    loopback = _endpoint(base_url, origin=True)
    url = base_url.rstrip('/') + f'/v1beta/properties/{property_id}:runReport?prettyPrint=false'
    head = {'Authorization': 'Bearer ' + (access or access_token(creds, token_url)),
            'Content-Type': 'application/json'}
    rows, total = Rows(), None
    while True:
        body = json.dumps(report_request(start, end, len(rows)), separators=(',', ':')).encode('utf-8')
        status, payload = _post(url, body, head, loopback)
        if status != 200:
            raise _refused(status)
        page, count, meta = _page(payload)
        rows.pages += 1
        if total is None:
            total = len(page) if count is None else count
            if total > MAX_ROWS:
                raise GA4Error('too_many_rows')
        rows.extend(page)
        rows.time_zone = meta.get('timeZone') if isinstance(meta.get('timeZone'), str) else rows.time_zone
        rows.thresholded = rows.thresholded or meta.get('subjectToThresholding') is True
        rows.other_row = rows.other_row or meta.get('dataLossFromOtherRow') is True
        if len(rows) >= total:
            return rows
        if not page:
            raise GA4Error('bad_response')


def _label(value, name):
    if not isinstance(value, str) or len(value) > 500:
        raise ValueError(f'GA4 returned an unreadable {name}')
    value = value.strip() or '(not set)'
    return '(redacted)' if policy.sensitive_errors(value) else value


def _count(value, name):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and COUNT.fullmatch(value):
        return int(value)
    raise ValueError(f'GA4 returned {name} that is not a whole, non-negative count')


def _observed(value):
    if isinstance(value, str):
        try:
            value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('observed_at must be an ISO 8601 time with an offset') from None
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise ValueError('observed_at must be an ISO 8601 time with an offset')
    return value.replace(microsecond=0).isoformat()


def to_export(rows, start, end, observed_at):
    """The aggregate export engine/attribution.py reads: GA4 names mapped to utm_ names and
    counts to ints. Rows identical after cleaning are summed; a value that looks like a
    contact or credential becomes "(redacted)"."""
    start, end = _day(start), _day(end)
    if start > end:
        raise ValueError('the export window starts after it ends')
    merged = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(DIMENSIONS) | set(METRICS):
            raise ValueError('a GA4 row must carry exactly the four session dimensions and three counts')
        key = tuple(_label(row[k], DIMENSIONS[k]) for k in DIMENSIONS)
        counts = [_count(row[k], METRICS[k]) for k in METRICS]
        merged[key] = [a + b for a, b in zip(merged.get(key, [0] * len(METRICS)), counts)]
    out = [{**dict(zip(DIMENSIONS.values(), key)), **dict(zip(METRICS.values(), merged[key]))}
           for key in sorted(merged)]
    return {'product': 'fulltime', 'source': 'ga4', 'property': MEASUREMENT_ID, 'query_ref': QUERY_REF,
            'window_start': start.isoformat(), 'window_end': end.isoformat(),
            'observed_at': _observed(observed_at), 'rows': out}


def week_window(today=None):
    """The seven complete London days ending yesterday, by reporting.week_window's rule."""
    start, end = reporting.week_window(today or reporting.london_today())[:2]
    return start, end


def days_window(days, today=None):
    """The given number of complete London days ending yesterday."""
    if type(days) is not int or not 1 <= days <= 92:
        raise ValueError('--days must be a whole number from 1 to 92')
    start, end = week_window(today)
    return end - dt.timedelta(days=days - 1), end


# ---------------------------------------------------------------------------
# One-time sign-in on Krish's own machine: loopback, PKCE S256, read-only scope.
# ---------------------------------------------------------------------------
def _urlsafe(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _same(given, expected):
    return secrets.compare_digest(str(given or '').encode('utf-8'), expected.encode('utf-8'))


class _Callback(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        if parts.path != '/':
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        answer = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items() if v}
        self.server.answer = answer
        good = _same(answer.get('state'), self.server.state) and 'code' in answer and 'error' not in answer
        page = ('<!doctype html><meta charset="utf-8"><title>Full Time growth engine</title><p>'
                + ('Signed in. You can close this tab and go back to the terminal.' if good else
                   'This sign-in was refused. Nothing was saved.') + '</p>').encode('utf-8')
        self.send_response(200 if good else 400)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(page)))
        self.end_headers()
        self.wfile.write(page)


def _save(path, data):
    """Write the credential file readable only by its owner (mode 600 where supported)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix':
        os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        handle = os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8')
        with handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        if os.name == 'posix':
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def authorize(local_dir, client_id, client_secret, open_browser=True, *, property_id=None, auth_url=AUTH_URL,
              token_url=TOKEN_URL, timeout=300, on_url=None, out=None):
    """The installed-app OAuth flow, once, on Krish's own machine. Listens on 127.0.0.1 at a
    random port, asks only for read-only Analytics access with PKCE S256, refuses an answer
    whose state does not match, exchanges the code and writes local_dir/ga4/oauth.json.
    Prints only success and the names of the secrets to add, never their values."""
    out = out or sys.stdout
    client_id, client_secret = str(client_id or '').strip(), str(client_secret or '').strip()
    if not PRINTABLE.fullmatch(client_id) or not PRINTABLE.fullmatch(client_secret):
        raise GA4Error('ga4_credentials_malformed')
    path = Path(local_dir) / FILE
    try:
        kept = json.loads(path.read_text(encoding='utf-8')).get('property_id') if path.is_file() else None
    except (OSError, ValueError, AttributeError):
        kept = None
    property_id = _property_id(property_id) or _property_id(kept)
    token_loopback = _endpoint(token_url)
    _endpoint(auth_url)
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    server = HTTPServer(('127.0.0.1', 0), _Callback)
    server.state, server.answer = state, None
    try:
        redirect_uri = f'http://127.0.0.1:{server.server_address[1]}/'
        url = auth_url + '?' + urllib.parse.urlencode({
            'client_id': client_id, 'redirect_uri': redirect_uri, 'response_type': 'code', 'scope': SCOPE,
            'code_challenge': _urlsafe(hashlib.sha256(verifier.encode('ascii')).digest()),
            'code_challenge_method': 'S256', 'state': state, 'access_type': 'offline', 'prompt': 'consent'})
        if open_browser:
            print('Opening your browser to sign in to Google Analytics (read-only).', file=out)
            if not webbrowser.open(url):
                raise GA4Error('browser_unavailable')
        elif on_url is not None:
            on_url(url)
        else:
            raise ValueError('authorize needs a browser, or on_url when open_browser is False')
        deadline = time.monotonic() + timeout
        while server.answer is None:
            left = deadline - time.monotonic()
            if left <= 0:
                raise GA4Error('authorize_timeout')
            server.timeout = min(left, 1.0)
            server.handle_request()
        answer = server.answer
    finally:
        server.server_close()
    if not _same(answer.get('state'), state):
        raise GA4Error('state_mismatch')
    if 'error' in answer:
        raise GA4Error('access_denied')
    if not answer.get('code'):
        raise GA4Error('bad_response')
    status, payload = _post(token_url, _form({
        'grant_type': 'authorization_code', 'code': answer['code'], 'redirect_uri': redirect_uri,
        'client_id': client_id, 'client_secret': client_secret, 'code_verifier': verifier}), FORM, token_loopback)
    if status != 200:
        raise _token_refused(status)
    if not isinstance(payload, dict):
        raise GA4Error('bad_response', status)
    refresh = payload.get('refresh_token')
    if not isinstance(refresh, str) or not PRINTABLE.fullmatch(refresh):
        raise GA4Error('no_refresh_token', status)
    granted = payload.get('scope')
    if granted is not None and (not isinstance(granted, str) or set(granted.split()) != {SCOPE}):
        raise GA4Error('scope_refused', status)
    _save(path, {'client_id': client_id, 'client_secret': client_secret, 'refresh_token': refresh,
                 'property_id': property_id})
    print(f'Signed in with read-only access. Saved {path}, readable only by you.', file=out)
    print('Add these names to the cloud environment\'s secrets, copying each value from that file yourself '
          '(never into chat): ' + ', '.join(ENV.values()) + '.', file=out)
    if property_id is None:
        print('property_id is empty: fill it in that file, and in GA4_PROPERTY_ID, with the number in Admin, '
              'Property details (not the G- measurement ID).', file=out)
    return {'saved': str(path), 'property_id_set': property_id is not None, 'secret_names': list(ENV.values())}


# ---------------------------------------------------------------------------
# growth.py ga4 doctor|report|authorize
# ---------------------------------------------------------------------------
def _failed(operation, error):
    code = error.code if isinstance(error, GA4Error) else 'not_ready'
    message = MESSAGES.get(code, 'Not ready.') if isinstance(error, GA4Error) else str(error)
    return {'operation': operation, 'status': 'failed', 'error_code': code, 'message': message}


def _doctor(local):
    names = [name for name in ENV.values() if str(os.environ.get(name) or '').strip()]
    summary = {'operation': 'doctor', 'environment_names_present': names,
               'file': 'present' if (local / FILE).is_file() else 'absent'}
    creds = credentials(local)
    if creds is None:
        return {**summary, **_failed('doctor', GA4Error('missing_ga4_credentials')), 'credentials': 'missing'}, 2
    summary.update(credentials=creds['source'], property_id='set' if creds['property_id'] else 'missing')
    try:
        access_token(creds, TOKEN_URL)
        summary['token_refresh'] = 'ok'
    except GA4Error as error:
        summary['token_refresh'] = error.code
        summary['message'] = MESSAGES.get(error.code, 'Not ready.')
    if summary['property_id'] == 'missing' and 'message' not in summary:
        summary['message'] = MESSAGES['missing_ga4_property_id']
    healthy = summary['token_refresh'] == 'ok' and summary['property_id'] == 'set'
    summary['status'] = 'succeeded' if healthy else 'failed'
    return summary, 0 if healthy else 1


def _report(local, days, out):
    start, end = days_window(days)
    target = Path(out) if out else local / 'ga4' / f'landings-{start}-{end}.json'
    if local.resolve() not in target.resolve().parents:
        raise ValueError('GA4 exports must stay under ignored local/')
    creds = credentials(local)
    if creds is None:
        raise GA4Error('missing_ga4_credentials')
    rows = run_report(creds, start, end, DATA_URL, token_url=TOKEN_URL)
    export = to_export(rows, start, end, reporting.utc_now())
    if policy.sensitive_errors(export):
        raise ValueError('the export carried contact or credential-like text and was not written')
    atomic_json(target, export)
    total = lambda key: sum(row[key] for row in export['rows'])
    notes = ['Web landings on fulltime.fm, never listeners: kept apart from every listener number.']
    if rows.time_zone and rows.time_zone != 'Europe/London':
        notes.append(f'The property reports in {rows.time_zone}, so its days are not London days.')
    if rows.thresholded:
        notes.append('Google applied thresholding, so small counts may be hidden.')
    if rows.other_row:
        notes.append('Google folded some rows into "(other)", so some creatives may be hidden.')
    return {'operation': 'report', 'status': 'succeeded', 'window_start': start.isoformat(),
            'window_end': end.isoformat(), 'rows': len(export['rows']), 'pages': rows.pages,
            'creatives': len({r['utm_content'] for r in export['rows']} - {'(not set)', '(redacted)'}),
            'new_users': total('new_users'), 'sessions': total('sessions'),
            'engaged_sessions': total('engaged_sessions'), 'out': str(target), 'notes': notes}, 0


class _Parser(argparse.ArgumentParser):
    """Never echoes what was typed, so a mistyped flag cannot print a secret."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, 'growth.py ga4: those arguments were not understood.\n')


def main(argv, growth):
    """`growth.py ga4 doctor|report|authorize`. Prints a JSON summary of codes, counts and
    paths only (authorize prints plain lines) and returns the exit code."""
    argv = list(argv)
    argv = argv[1:] if argv[:1] == ['ga4'] else argv
    parser = _Parser(prog='growth.py ga4', description='Read-only Google Analytics 4 landings.')
    operations = parser.add_subparsers(dest='operation', required=True)
    operations.add_parser('doctor', help='check the credentials and a token refresh, printing no secret')
    report = operations.add_parser('report', help='write the landings-by-creative export under local/')
    report.add_argument('--days', type=int, default=7)
    report.add_argument('--out')
    signin = operations.add_parser('authorize', help='sign in once on your own machine')
    signin.add_argument('--client-id'); signin.add_argument('--client-secret'); signin.add_argument('--property-id')
    args = parser.parse_args(argv)
    local = Path(growth.LOCAL)
    try:
        if args.operation == 'authorize':
            client_id = args.client_id or str(os.environ.get(ENV['client_id']) or '').strip() or input('Client ID: ')
            client_secret = (args.client_secret or str(os.environ.get(ENV['client_secret']) or '').strip()
                             or getpass.getpass('Client secret (not shown): '))
            authorize(local, client_id, client_secret, True, property_id=args.property_id,
                      auth_url=AUTH_URL, token_url=TOKEN_URL)
            return 0
        if args.operation == 'doctor':
            summary, code = _doctor(local)
        else:
            summary, code = _report(local, args.days, args.out)
    except GA4Error as error:
        summary = _failed(args.operation, error)
        code = 2 if error.code in NOT_STARTED else 1
    except EOFError:
        summary, code = _failed(args.operation, ValueError('the client ID and secret are needed')), 2
    except (ValueError, OSError) as error:
        summary, code = _failed(args.operation, error), 1
    if args.operation == 'authorize':
        print('Not ready: ' + summary['message'], file=sys.stderr)
        return code
    print(json.dumps(summary, indent=2, allow_nan=False))
    return code
