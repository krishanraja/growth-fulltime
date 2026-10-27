"""The Control Center growth engine protocol client (docs/control-center/ENGINE-PROTOCOL.md).

One loop, two entry points: `growth.py cc morning|weekly` in the persistent
workspace, and `growth.py cc dispatch` on a clean GitHub Actions runner.
Each run journals a started attempt before reading any source, pulls the
directive, does the engine's own work, reports with an Idempotency-Key and
reads the digest back, reads Krish's decisions, and journals one terminal
attempt. Nothing here sends, posts, publishes or spends: an approval only
records that Krish said yes to exactly that payload, or to his amended version
once its amended_sha256 checks. Full Time is handcrafted (ruling 3 of 27
October): an approved go-live becomes a recorded instruction for Krish, in
local/control-center/instructions.jsonl, never an action. Any protocol 1.x is
taken from Control Center; a directive or decision declaring another major
version is refused.

The bearer comes from CONTROL_CENTER_ENGINE_TOKEN or the ignored file
local/control-center/token. It is never printed, logged or written.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import gates, policy, reporting
from .records import History, atomic_json, instant

DEFAULT_URL = 'https://controlcenter.krishraja.com'
TOKEN_ENV = 'CONTROL_CENTER_ENGINE_TOKEN'
URL_ENV = 'CONTROL_CENTER_URL'
TIMEOUT = 20
LIMIT = 1_048_576
MESSAGES = {
    'missing_token': 'Control Center bearer unavailable: set CONTROL_CENTER_ENGINE_TOKEN or write it to '
                     'local/control-center/token. Nothing was run.',
    'token_malformed': 'The Control Center bearer is not a single printable token. Nothing was run.',
    'bad_base_url': 'CONTROL_CENTER_URL must be an https origin with no path, query or credentials. Nothing was run.',
    'wrong_engine': 'This dispatch names another engine. Nothing was run.',
}


class ControlCenterError(Exception):
    """A lower_snake code, never a message, body, URL or credential."""

    def __init__(self, code, status=None):
        super().__init__(code)
        self.code = code
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def opener(direct=False):
    handlers = [NoRedirect()]
    if direct:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def load_token(local):
    token = os.environ.get(TOKEN_ENV, '').strip()
    if not token:
        path = Path(local) / 'control-center' / 'token'
        if path.is_file():
            token = path.read_text(encoding='utf-8').strip()
    if not token:
        raise ControlCenterError('missing_token')
    if not re.fullmatch(r'[\x21-\x7e]{20,512}', token):
        raise ControlCenterError('token_malformed')
    return token


def base_url(value=None):
    value = (value if value is not None else os.environ.get(URL_ENV, '')).strip() or DEFAULT_URL
    parts = urllib.parse.urlsplit(value)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ('', '/')):
        raise ControlCenterError('bad_base_url')
    return f'https://{parts.netloc}'


STATUS_CODES = {400: 'bad_request', 401: 'unauthorized', 403: 'forbidden', 404: 'not_found',
                409: 'conflict', 413: 'report_too_large', 429: 'rate_limited'}
VERSION_REFUSED = 'protocol_version_unsupported'
BY_HAND = {'post': 'post it yourself', 'send': 'send it yourself', 'spend': 'spend it yourself'}


def version_supported(value):
    """Any 1.x is taken: within 1.x Control Center only adds. Another major version,
    or a version that is not one, is refused. An undeclared version is not checked."""
    return value is None or (reporting.version_numbers(value) or (None,))[0] == 1


class Client:
    def __init__(self, base, token, slug=reporting.SLUG, timeout=TIMEOUT, loopback_for_tests=False):
        parts = urllib.parse.urlsplit(base)
        loopback = loopback_for_tests and parts.scheme == 'http' and parts.hostname == '127.0.0.1'
        if not loopback:
            base = base_url(base)
        self._base = base.rstrip('/') + f'/api/growth/engines/{slug}/'
        self._token = token
        self._timeout = timeout
        self._opener = opener(direct=loopback)

    def __repr__(self):
        return 'Client(<redacted>)'

    def _call(self, method, path, body=None, headers=None):
        data = None
        head = {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json',
                'User-Agent': 'growth-fulltime (+https://github.com/krishanraja/growth-fulltime)'}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
            head['Content-Type'] = 'application/json'
        head.update(headers or {})
        request = urllib.request.Request(self._base + path, data=data, headers=head, method=method)
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
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
            raise ControlCenterError('network_error') from None
        if len(raw) > LIMIT:
            raise ControlCenterError('response_too_large', status)
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = None
            if 200 <= status < 300:
                raise ControlCenterError('bad_response', status) from None
        return status, payload

    @staticmethod
    def _refuse(status, payload):
        if 300 <= status < 400:
            return ControlCenterError('redirect_refused', status)
        if status == 409 and 'engine_inactive' in json.dumps(payload or {}):
            return ControlCenterError('engine_inactive', status)
        if status >= 500:
            return ControlCenterError('server_error', status)
        return ControlCenterError(STATUS_CODES.get(status, 'unexpected_status'), status)

    def attempt(self, record):
        status, payload = self._call('POST', 'attempts', record)
        if status in (200, 201) and isinstance(payload, dict) and payload.get('ok') is True:
            return payload
        if status == 409:
            raise ControlCenterError('attempt_conflict', status)
        raise self._refuse(status, payload) if status >= 300 else ControlCenterError('bad_response', status)

    def directive(self):
        status, payload = self._call('GET', 'directive')
        if status == 200 and isinstance(payload, dict) and isinstance(payload.get('directive'), dict):
            if not (version_supported(payload.get('schema_version'))
                    and version_supported(payload['directive'].get('schema_version'))):
                raise ControlCenterError(VERSION_REFUSED, status)
            return payload
        raise self._refuse(status, payload) if status >= 300 else ControlCenterError('bad_response', status)

    def capabilities(self):
        """What Control Center takes (ENGINE-PROTOCOL.md: check that the version you send is
        in schema_versions). None when an older server has no such route."""
        status, payload = self._call('GET', 'capabilities')
        if status == 404:
            return None
        if status == 200 and isinstance(payload, dict):
            if not version_supported(payload.get('schema_version')):
                raise ControlCenterError(VERSION_REFUSED, status)
            return payload
        raise self._refuse(status, payload) if status >= 300 else ControlCenterError('bad_response', status)

    def get_report(self, run_id):
        status, payload = self._call('GET', 'reports/' + urllib.parse.quote(run_id, safe=''))
        if status == 404:
            return None
        if status == 200 and isinstance(payload, dict) and payload.get('accepted') is True:
            return payload
        raise self._refuse(status, payload) if status >= 300 else ControlCenterError('bad_response', status)

    def post_report(self, report):
        return self._call('POST', 'reports', report, {'Idempotency-Key': report['run_id']})

    def decisions(self, since):
        query = '?since=' + urllib.parse.quote(since, safe='') if since else ''
        status, payload = self._call('GET', 'decisions' + query)
        if status == 200 and isinstance(payload, dict) and isinstance(payload.get('decisions'), list):
            if not version_supported(payload.get('schema_version')):
                raise ControlCenterError(VERSION_REFUSED, status)
            return [d for d in payload['decisions'] if isinstance(d, dict)]
        raise self._refuse(status, payload) if status >= 300 else ControlCenterError('bad_response', status)

    def deliver(self, report):
        """Report once, read it back. Read before every write; never retry a write blindly.
        A run_id already holding a different payload (a rerun the same day) takes the
        next revision suffix, :r2 to :r9, found by reading, not by posting."""
        digest = lambda stored: stored.get('payload_sha256')
        base = report['run_id']
        body = None
        for number in range(1, 10):
            candidate = report if number == 1 else reporting.seal({**report, 'run_id': f'{base}:r{number}'})
            stored = self.get_report(candidate['run_id'])
            if stored is None:
                body = candidate
                break
            if digest(stored) == candidate['payload_sha256']:
                return {'run_id': candidate['run_id'], 'payload_sha256': candidate['payload_sha256'],
                        'replayed': True, 'readback': True, 'report': candidate}
        if body is None:
            raise ControlCenterError('too_many_revisions')
        try:
            status, payload = self.post_report(body)
        except ControlCenterError as error:
            if error.code != 'network_error':
                raise
            status, payload = None, None
        if status is None or status == 409:
            if status == 409 and 'engine_inactive' in json.dumps(payload or {}):
                raise ControlCenterError('engine_inactive', 409)
            try:
                stored = self.get_report(body['run_id'])
            except ControlCenterError:
                stored = None
            if stored is not None and digest(stored) == body['payload_sha256']:
                return {'run_id': body['run_id'], 'payload_sha256': body['payload_sha256'],
                        'replayed': True, 'readback': True, 'report': body}
            raise ControlCenterError('report_unconfirmed' if status is None else 'report_conflict', status)
        if status not in (200, 201):
            raise self._refuse(status, payload)
        if not isinstance(payload, dict) or payload.get('accepted') is not True \
                or payload.get('payload_sha256') != body['payload_sha256']:
            raise ControlCenterError('report_digest_mismatch', status)
        stored = self.get_report(body['run_id'])
        if stored is None or digest(stored) != body['payload_sha256']:
            raise ControlCenterError('readback_mismatch')
        return {'run_id': body['run_id'], 'payload_sha256': body['payload_sha256'],
                'replayed': bool(payload.get('replayed')), 'readback': True, 'report': body}


def amended_digest(decision):
    """His version's digest, as Control Center computes amended_sha256: the canonical
    JSON of exactly {amount_usd, exact_payload}, each null when absent."""
    return reporting.canonical_sha256({'amount_usd': decision.get('amount_usd'),
                                       'exact_payload': decision.get('exact_payload')})


def handcrafted_instruction(proposal, approved):
    """Handcrafted (ruling 3): what Krish does by hand with an approved go-live. It is
    a record for him, never an action: the engine does not post, send or spend."""
    wall, channel = proposal.get('wall'), proposal.get('channel')
    amount = approved.get('amount_usd')
    line = (f'Approved {proposal["proposal_id"]}: {BY_HAND.get(wall, "carry it out yourself")}'
            + (f' on {channel}' if channel else '')
            + (f', {amount} USD' if amount is not None else '')
            + (', using your amended version' if approved['amended'] else ', exactly as approved')
            + f' (sha256 {approved["sha256"][:12]}). The engine does not post, send or spend.')
    return {'proposal_id': proposal['proposal_id'], 'stage': approved['stage'], 'wall': wall,
            'channel': channel, 'amount_usd': amount, 'sha256': approved['sha256'],
            'amended': approved['amended'], 'by': 'krish', 'line': line}


def classify(decisions, proposals):
    """His yes counts only on the payload it was made on (payload_sha256). When he amended
    it, amended_sha256 is recomputed from his version; on a match his words and amount
    are what he approved, never the engine's, and on a mismatch the decision is unverified
    and counts for nothing. A decision declaring a protocol major other than 1 is refused.
    The engine still never acts on a yes by sending, posting or spending: an approved
    go-live becomes an instruction for Krish, and a ruling is recorded by an
    interactive session. `answered` maps each proposal he answered to the digest he
    answered it on, with his decision and any version of his, for the history."""
    current = {p['proposal_id']: p for p in proposals}
    out = {'approved_current': [], 'approved_amended': [], 'approved_changed': [], 'amended_unverified': [],
           'declined': [], 'done': [], 'not_in_report': [], 'refused': [], 'approved': {}, 'instructions': [],
           'answered': {}}

    def answer(pid, decision, sha, verified=True):
        row = {'payload_sha256': sha, 'decision': decision.get('decision'), 'amended': decision.get('amended') is True,
               'verified': verified, 'decided_at': decision.get('decided_at')}
        if row['amended']:
            row.update({key: decision.get(key) for key in ('exact_payload', 'amount_usd', 'amended_sha256')})
        out['answered'][pid] = row

    for decision in decisions:
        pid = decision.get('proposal_id')
        if not version_supported(decision.get('schema_version')):
            out['refused'].append({'proposal_id': pid, 'code': VERSION_REFUSED})
            continue
        if not isinstance(pid, str) or pid not in current:
            out['not_in_report'].append(pid)
            continue
        proposal, verdict = current[pid], decision.get('decision')
        if verdict in ('declined', 'done'):
            out[verdict].append(pid)
            answer(pid, decision, decision.get('payload_sha256'))
            continue
        if verdict != 'approved':
            continue
        amended = decision.get('amended') is True
        if amended:
            try:
                verified = decision.get('amended_sha256') == amended_digest(decision)
            except ValueError:
                verified = False
            if not verified:
                out['amended_unverified'].append(pid)
                answer(pid, decision, decision.get('payload_sha256'), verified=False)
                continue
        if decision.get('payload_sha256') != proposal['payload_sha256']:
            out['approved_changed'].append(pid)
            continue
        answer(pid, decision, proposal['payload_sha256'])
        source = decision if amended else proposal
        approved = {'amended': amended, 'stage': proposal.get('stage') or decision.get('stage'),
                    'exact_payload': source.get('exact_payload'), 'amount_usd': source.get('amount_usd'),
                    'sha256': decision['amended_sha256'] if amended else proposal['payload_sha256']}
        out['approved_amended' if amended else 'approved_current'].append(pid)
        out['approved'][pid] = approved
        if approved['stage'] == 'go_live' or proposal.get('wall') in reporting.GO_LIVE_WALLS:
            out['instructions'].append(handcrafted_instruction(proposal, approved))
    return out


def still_waiting(report, decided, answered=()):
    """What a live report leaves on Krish's list: its walled asks he has not answered on
    their current digest, in this run (`decided`) or any earlier one (`answered`, pairs
    of proposal_id and payload_sha256). Control Center keeps an answered digest off his
    list for good, so it never waits again. An ask answered on an older digest comes
    back to him, so it still waits. A synthetic report puts nothing on his list, so it
    returns None."""
    if report.get('mode') != 'live':
        return None
    done = reporting.answered_pairs(answered) | reporting.answered_pairs(
        (pid, row.get('payload_sha256')) for pid, row in ((decided or {}).get('answered') or {}).items())
    return {p['proposal_id']: reporting.ask_kind(p) for p in report['proposals']
            if p.get('wall') != 'none' and (p['proposal_id'], p['payload_sha256']) not in done}


def answered_in(directive):
    """(proposal_id, payload_sha256) of each answer in the directive's decisions_since (his
    last seven days), so a run with no history of its own, such as a clean runner, still
    knows what he has answered and asks the next thing instead."""
    found = ((directive or {}).get('directive') or {}).get('decisions_since')
    return reporting.answered_pairs(
        (d.get('proposal_id'), d.get('payload_sha256')) for d in (found if isinstance(found, list) else [])
        if isinstance(d, dict) and d.get('decision') in ('approved', 'declined', 'done')
        and version_supported(d.get('schema_version')))


def _jsonl(path):
    """The object rows of a local JSON-lines file; a line that cannot be read is skipped."""
    rows = []
    if Path(path).is_file():
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                rows.append(entry)
    return rows


def _append(path, rows):
    if rows:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open('a', encoding='utf-8', newline='\n') as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


ANSWERS = Path('control-center') / 'decisions.jsonl'


def record_answers(local, decided, at):
    """Append each answer Krish gave (approved, declined, done, with his version when he
    amended) once, by proposal, digest, decision and time, to the ignored
    local/control-center/decisions.jsonl: his history of declines and amendments, and
    what later runs know he answered. Returns how many were new."""
    path = Path(local) / ANSWERS
    key = lambda row: (row.get('proposal_id'), row.get('payload_sha256'), row.get('decision'), row.get('decided_at'))
    seen = {key(row) for row in _jsonl(path)}
    new = []
    for pid, row in sorted(((decided or {}).get('answered') or {}).items()):
        entry = {**row, 'proposal_id': pid, 'read_at': at}
        if key(entry) not in seen:
            seen.add(key(entry))
            new.append(entry)
    _append(path, new)
    return len(new)


def answered_before(local):
    """Every (proposal_id, payload_sha256) Krish has answered, from decisions.jsonl."""
    return reporting.answered_pairs((row.get('proposal_id'), row.get('payload_sha256'))
                                    for row in _jsonl(Path(local) / ANSWERS))


OVERLAP = dt.timedelta(minutes=15)


def read_from(previous, moment=None):
    """Where a run starts reading his decisions: the last read less fifteen minutes,
    because decided_at is Control Center's clock and the read time is this machine's.
    What is read twice is taken once (settle, record_answers and record_instructions
    keep each answer once). With no valid last read, seven days back."""
    try:
        return reporting.iso(instant(previous) - OVERLAP)
    except ValueError:
        return reporting.iso((moment or reporting.utc_now()) - dt.timedelta(days=7))


def waiting_from(value):
    """A saved waiting map, or None when it is missing or not of the right shape."""
    if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v in reporting.ASK_KINDS for k, v in value.items()):
        return None
    return dict(value)


def record_instructions(local, instructions, at):
    """Append each new instruction once (by proposal and digest) to the ignored
    local/control-center/instructions.jsonl. Returns how many were new."""
    path = Path(local) / 'control-center' / 'instructions.jsonl'
    seen = {(entry.get('proposal_id'), entry.get('sha256')) for entry in _jsonl(path)}
    new = []
    for item in instructions or []:
        key = (item.get('proposal_id'), item.get('sha256'))
        if key not in seen:
            seen.add(key)
            new.append({**item, 'recorded_at': at})
    _append(path, new)
    return len(new)


def execute(client, command, run_id, work, since, answered=()):
    """The protocol loop. Returns a summary that names codes only. `answered` is what
    earlier runs know he answered (answered_before), for what still waits."""
    started = reporting.utc_now()
    attempt_id = f'{run_id}:{started.strftime("%Y%m%dT%H%M%SZ")}:{uuid.uuid4().hex[:6]}'
    summary = {'command': command, 'attempt_id': attempt_id, 'run_id': None, 'status': None,
               'phase': None, 'error_code': None, 'report_sha256': None, 'readback': False,
               'replayed': None, 'next_action': None, 'decisions': None, 'decisions_read_at': None,
               'waiting': None}

    def finish(status, phase, code=None, delivered=None):
        record = {'attempt_id': attempt_id, 'command': command, 'run_id': delivered, 'status': status,
                  'phase': phase, 'error_code': code, 'started_at': reporting.iso(started),
                  'finished_at': reporting.iso(reporting.utc_now())}
        try:
            client.attempt(record)
        except ControlCenterError as error:
            summary['journal_error'] = error.code
        summary.update(status=status, phase=phase, error_code=code, run_id=delivered)
        return summary

    try:
        client.attempt({'attempt_id': attempt_id, 'command': command, 'run_id': None, 'status': 'started',
                        'phase': 'capture', 'error_code': None, 'started_at': reporting.iso(started)})
    except ControlCenterError as error:
        summary.update(status='failed', phase='capture', error_code=error.code, journal_error=error.code)
        return summary
    try:
        directive = client.directive()
    except ControlCenterError as error:
        return finish('failed', 'directive', error.code)
    action = (directive.get('directive') or {}).get('next_action') or {}
    summary['next_action'] = action.get('proposal_id')
    try:
        report, notes = work(directive)
    except ControlCenterError as error:
        return finish('failed', 'plan', error.code)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        return finish('failed', 'plan', 'run_failed')
    if reporting.schema_errors(report):
        return finish('failed', 'report', 'report_invalid')
    try:
        offered = client.capabilities()
    except ControlCenterError as error:
        return finish('failed', 'report', error.code)
    if offered is not None:
        summary['autonomy'] = offered.get('autonomy')        # ruling 3: Full Time should read handcrafted
        versions = offered.get('schema_versions')
        if isinstance(versions, list) and report['schema_version'] not in versions:
            return finish('failed', 'report', 'version_not_offered')
    try:
        delivery = client.deliver(report)
    except ControlCenterError as error:
        return finish('unknown' if error.code == 'report_unconfirmed' else 'failed', 'report', error.code)
    summary.update(report_sha256=delivery['payload_sha256'], readback=delivery['readback'],
                   replayed=delivery['replayed'])
    read_at = reporting.iso(reporting.utc_now())
    try:
        decisions = client.decisions(since)
    except ControlCenterError as error:
        return finish('failed', 'decisions', error.code, delivery['run_id'])
    summary['decisions'] = classify(decisions, delivery['report']['proposals'])
    summary['decisions_read_at'] = read_at
    summary['waiting'] = still_waiting(delivery['report'], summary['decisions'], answered)
    code = notes.get('error_code')
    return finish('failed' if code else 'succeeded', notes.get('phase', 'decisions') if code else 'decisions',
                  code, delivery['run_id'])


# ---------------------------------------------------------------------------
# The engine's own work for each entry point.
# ---------------------------------------------------------------------------
def measurement_lines(local, today, rows=None, directive=None):
    """The North Star readings and Google Analytics landings, as activity lines for
    Control Center. They stay out of the objectives until Control Center registers
    the new keys (briefs/2026-10-27-control-center-measurement.md), and out of the
    printed summary, because the runner's log is public. Landings come from Control
    Center itself when its directive carries ga4_landings (Krish, 2026-10-27: "just
    get google analytics data from control center"), else from local/ga4/."""
    from . import attribution
    lines = []
    try:
        for row in attribution.objectives(rows or [], today):
            value = 'missing' if row['value'] is None else f'{row["value"]} people'
            lines.append(f'North Star reading, {row["key"]}: {value}. {row["reason"] or ""}'.strip())
    except ValueError as error:
        lines.append(f'North Star reading refused: {error}')
    sent = ((directive or {}).get('directive') or {}).get('ga4_landings')
    path = Path(local) / 'ga4' / 'landings-latest.json'
    if sent is None and not path.is_file():
        return lines + ['Google Analytics: Control Center sent no landings this run, and none were saved '
                        'locally (docs/GA4-ACCESS.md).']
    source = 'from Control Center' if sent is not None else 'saved locally'
    try:
        export = sent if sent is not None else json.loads(path.read_text(encoding='utf-8'))
        landings = attribution.by_creative(export)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return lines + [f'Google Analytics: the export {source} was refused ({str(error)[:160]}).']
    tagged = sum(v['new_users'] for v in landings.values())
    top = sorted(landings.items(), key=lambda kv: (-kv[1]['new_users'], kv[0]))[:3]
    best = '; most: ' + ', '.join(f'{cid} {v["new_users"]}' for cid, v in top) if top else ''
    return lines + [f'Google Analytics ({source}), {export["window_start"]} to {export["window_end"]}: {tagged} new web '
                    f'users from {len(landings)} tagged creatives and {landings.untagged["new_users"]} from '
                    f'untagged links{best}. Web landings on fulltime.fm, never listeners.']


LISTING_FRESH = dt.timedelta(days=7)


def library_check(local, moment=None):
    """The weekly Growth Build reconcile (docs/ENGINE-V2.md, section 2a, rule 7): a
    listing a Claude session read back from Drive, against INDEX.csv, both under
    local/library/. The listing document says when it was read ({"read_at": RFC 3339,
    "listing": [...]}), and only a read from the last seven days reconciles this week:
    a missing, undated or older listing is a LIBRARY hold, since unknown is never clean.
    Returns (activity line, holds)."""
    from . import library
    moment = moment or reporting.utc_now()
    folder = Path(local) / 'library'
    listing, index = folder / 'listing.json', folder / 'INDEX.csv'

    def unreconciled(why):
        return (f'Growth Build library: not reconciled this week ({why}).',
                [('LIBRARY', f'The library was not reconciled this week: {why}.')])

    if not listing.is_file():
        return unreconciled('no listing was read back from Drive into local/library/listing.json')
    if not index.is_file():
        return unreconciled('local/library/INDEX.csv is missing')
    try:
        document = json.loads(listing.read_text(encoding='utf-8'))
        found = document.get('listing') if isinstance(document, dict) else document
        rows = library.read_index(index.read_text(encoding='utf-8'))
    except (ValueError, OSError) as error:
        return f'Growth Build library: the listing or index was refused ({str(error)[:160]}).', [
            ('LIBRARY', 'The weekly reconcile could not read its listing or index.')]
    read_at = document.get('read_at') if isinstance(document, dict) else None
    try:
        read = instant(read_at)
    except ValueError:
        return unreconciled('the listing does not say when it was read (read_at, an RFC 3339 time)')
    if read > moment + OVERLAP:
        return unreconciled(f'the listing says it was read at {read_at}, which is in the future')
    if moment - read > LISTING_FRESH:
        return unreconciled(f'the newest listing was read at {read_at}, more than 7 days ago')
    try:
        result = library.reconcile(found, rows)
    except ValueError as error:
        return f'Growth Build library: the listing or index was refused ({str(error)[:160]}).', [
            ('LIBRARY', 'The weekly reconcile could not read its listing or index.')]
    held = library.hold(result)
    if held is None:
        return 'Growth Build library: reconciled clean, nothing outside the tree, misnamed or duplicated.', []
    return 'Growth Build library: ' + held['detail'], [(held['code'], held['detail'])]


def directive_line(directive, dispatched=None):
    body = directive.get('directive') or {}
    action = body.get('next_action') or {}
    line = (f'Control Center push for {body.get("for_date", "today")}: '
            f'{action.get("proposal_id") or "no proposal"} (chosen by {directive.get("chosen_by", "rule")}); '
            'used as data, never as permission to send or post.')
    lines = [line]
    if dispatched and body.get('directive_id') and dispatched != body['directive_id']:
        lines.append('The dispatch named a different directive from the one pulled; the pulled one was used.')
    return lines


def max_actions(directive):
    value = ((directive.get('directive') or {}).get('constraints') or {}).get('max_actions')
    return min(3, value) if type(value) is int and value >= 0 else 3


def workspace_work(growth, mode, report_mode, offline, observations, require_existing, waiting=None, answered=()):
    """The morning batch or weekly review in the persistent workspace, mapped to a report.
    `waiting` is what the last live delivery left on Krish's list (one ask at a time);
    `answered` is what he has already answered (answered_before), with the directive's
    own decisions_since added."""
    def work(directive):
        from .runner import run
        journal = History(Path(growth.LOCAL) / 'engine')
        if require_existing and not journal.path.exists():
            raise ControlCenterError('history_unavailable')
        try:
            result = run(growth, mode, offline, observations)
        except ValueError as error:
            text = str(error)
            raise ControlCenterError('source_stale' if 'stale' in text else
                                     'source_unverified' if 'sync' in text else 'run_failed') from None
        except (urllib.error.URLError, OSError):
            raise ControlCenterError('source_unavailable') from None
        saved = journal.read()
        record = saved['runs'][result['run_id']]
        today = dt.date.fromisoformat(record['date'])
        kind = 'report' if mode == 'weekly' else 'daily'
        pack_record = saved['packs'][f'{reporting.SLUG}:{today}:{kind}']
        pack = next(x['pack'] for x in pack_record['revisions'] if x['digest'] == pack_record['latest_digest'])
        state = dict(growth.load_state() or {})
        state['push'] = record['gate']
        identities = state.get('brand_identities') or {}
        identity_known = any(policy.identity_verified(x, platform) for x in identities.values()
                             for platform in ('tiktok', 'instagram', 'youtube'))   # ruling 2: the three pushed
        usage = record['usage']
        gate = record['gate']
        activity = [f'Synced full-time {record["source_sha"][:10]}, read {record["source_observed_at"]}; '
                    f'rail gate {"OPEN" if gate["open"] else "HOLD"}: {gate["why"]}.',
                    f'Prepared {len(record["actions"])} of at most three actions; nothing was sent, posted or spent.',
                    f'Recorded usage: {usage["marketing_cash_gbp"]} GBP marketing cash, {usage["model_calls"]} model calls, '
                    f'{usage["audio_generation_calls"]} audio generation calls.']
        held = reporting.held_creatives(saved['creatives'])
        activity.append(f'{len(held)} creatives are held in private history with their codes.')
        library_holds = []
        if mode == 'weekly':
            activity.append('Weekly review over the seven complete London days ending yesterday: '
                            + record['native_weekly_review']['findings']['measurement'])
            line, library_holds = library_check(growth.LOCAL)
            activity.append(line)
        activity += directive_line(directive)
        activity += measurement_lines(growth.LOCAL, today, saved['observations'], directive)
        degraded = [] if record.get('rail') is not None else ['The live rail was not read; fulltime.fm did not answer.']
        start = reporting.week_window(today)[0].isoformat()
        report = reporting.build(
            reporting.run_id_for(today, kind), report_mode, reporting.iso(reporting.utc_now()), state,
            reporting.ready_creatives(saved['creatives']) + pack['items'], growth.load_rulings(),
            reporting.objectives(today, saved['observations'], saved['runs']),
            activity, held_items=held,
            events=reporting.publication_events(saved['creatives'], start) + gates.events(growth.LOCAL, start),
            identity_known=identity_known,
            kill_list=record['native_weekly_review']['kill_list'] if mode == 'weekly' else (),
            degraded=degraded, max_actions=max_actions(directive), waiting=waiting,
            gate_proposals=gates.pending(growth.LOCAL), extra_holds=library_holds,
            answered=reporting.answered_pairs(answered) | answered_in(directive))
        return report, {}
    return work


def runner_work(growth, report_mode, dispatched=None, waiting=None, answered=()):
    """What a clean runner can see: the checks, the committed rulings and contracts,
    and the public sources the hourly sync reads. No private history. `waiting` and
    `answered` are as for workspace_work; a clean runner has no ledger, so they are
    usually empty and the directive's decisions_since says what he answered."""
    def work(directive):
        from .measurements import scorecard
        from .runner import constraints
        here = Path(growth.HERE)
        run_url = None
        if os.environ.get('GITHUB_RUN_ID', '').isdigit() and re.fullmatch(
                r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', os.environ.get('GITHUB_REPOSITORY', '')):
            run_url = f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'
        activity, degraded, notes = [], [], {}
        for name, script in (('Self-test', ['growth.py', '--self-test']),
                             ('Repository verification', ['scripts/verify_repository.py'])):
            quiet_env = {k: v for k, v in os.environ.items() if k != TOKEN_ENV}
            quiet_env['PYTHONIOENCODING'] = 'utf-8'     # a Windows child would otherwise write its code page (R35)
            proc = subprocess.run([sys.executable] + script, cwd=here, capture_output=True, text=True, encoding='utf-8',
                                  errors='replace', timeout=300, env=quiet_env)
            last = (proc.stdout.strip().splitlines() or [''])[-1][:300]
            if proc.returncode == 0:
                activity.append((f'{name} passed: {last}', run_url))
            else:
                degraded.append(f'{name} failed on this runner.')
                notes = {'error_code': 'checks_failed', 'phase': 'checks'}
        try:
            state = growth.sync(quiet=True)
            activity.append(f'Read full-time {state["sha"][:10]} and the live rail at {state["synced_at"]}.')
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            state = growth.load_state(published_only=True)
            degraded.append('The live sync failed; the committed state/ snapshot was used.')
        state = dict(state or {})
        if not state:
            degraded.append('No source snapshot could be read.')
        else:
            if not state.get('rules_ok'):
                degraded.append("Full Time's rules changed; drafting stops until they are reconciled.")
            try:
                age = reporting.utc_now() - dt.datetime.fromisoformat(state['synced_at'])
                if age > dt.timedelta(hours=26):
                    degraded.append('The source snapshot is older than 26 hours.')
            except (KeyError, ValueError, TypeError):
                degraded.append('The source snapshot has no valid capture time.')
            if state.get('rail') is None:
                degraded.append('The live rail was not read; fulltime.fm did not answer.')
        state['push'] = state.get('push') or growth.push_gate(state.get('rail'), state)
        today = reporting.london_today()
        start, end = reporting.week_window(today)[:2]
        measures = scorecard([], start.isoformat(), end.isoformat())
        items = [{'item_id': 'fulltime-' + key, 'platform': 'other', 'why': key, 'text': text}
                 for key, text in constraints(state['push'], measures, state)]
        gate = state['push']
        activity.append(f'Rail gate {"OPEN" if gate.get("open") else "HOLD"}: {gate.get("why")}.')
        activity.append('Private history, held creatives, brand identity proof and approved aggregates stay in '
                        'the persistent workspace; this runner reports only what it can see.')
        activity += directive_line(directive, dispatched)
        activity += measurement_lines(growth.LOCAL, today, directive=directive)
        report = reporting.build(
            reporting.run_id_for(today, 'dispatch'), report_mode, reporting.iso(reporting.utc_now()), state,
            items, growth.load_rulings(), reporting.objectives(today, workspace=False), activity,
            identity_known=None, degraded=degraded, max_actions=max_actions(directive), waiting=waiting,
            answered=reporting.answered_pairs(answered) | answered_in(directive))
        return report, notes
    return work


def main(args, growth):
    """`growth.py cc TARGET`. Returns (summary, exit code)."""
    dispatched_engine = os.environ.get('CC_DISPATCH_ENGINE_ID', '').strip()
    if dispatched_engine and dispatched_engine != reporting.ENGINE_ID:
        return {'status': 'not_started', 'error_code': 'wrong_engine', 'message': MESSAGES['wrong_engine']}, 2
    try:
        token = load_token(growth.LOCAL)
        base = base_url()
    except ControlCenterError as error:
        return {'status': 'not_started', 'error_code': error.code, 'message': MESSAGES[error.code]}, 2
    client = Client(base, token)
    del token
    report_mode = 'synthetic' if args.synthetic else 'live'
    # Only a live workspace report carries every ask he can answer, the queued gates
    # included, so only its run takes his decisions: it records his answers and
    # instructions, settles gates and moves the read window. A synthetic run or a
    # dispatch reads them and leaves every one for the next live workspace run.
    takes = report_mode == 'live' and args.target != 'dispatch'
    ledger = Path(growth.LOCAL) / 'control-center' / 'last.json'
    previous, waiting = None, None
    try:
        saved = json.loads(ledger.read_text(encoding='utf-8'))
        previous = saved.get('decisions_read_at')
        waiting = waiting_from(saved.get('waiting'))
    except (OSError, ValueError, AttributeError):
        pass
    answered = answered_before(growth.LOCAL)
    since = read_from(previous)
    today = reporting.london_today()
    if args.target == 'dispatch':
        dispatched = os.environ.get('CC_DIRECTIVE_ID', '').strip()[:120] or None
        summary = execute(client, 'dispatch', reporting.run_id_for(today, 'dispatch'),
                          runner_work(growth, report_mode, dispatched, waiting, answered=answered), since, answered)
    else:
        kind = 'report' if args.target == 'weekly' else 'daily'
        summary = execute(client, args.target, reporting.run_id_for(today, kind),
                          workspace_work(growth, args.target, report_mode, args.offline, args.observations,
                                         args.require_existing_history, waiting, answered=answered), since, answered)
    summary['mode'] = report_mode
    if summary.get('waiting') is None:   # a synthetic or failed run leaves his list as it was
        summary['waiting'] = waiting
    decided = summary.get('decisions')
    instructions = (decided or {}).get('instructions') or []
    if takes and decided is not None and summary.get('decisions_read_at'):
        record_answers(growth.LOCAL, decided, summary['decisions_read_at'])
        record_instructions(growth.LOCAL, instructions, summary['decisions_read_at'])
        settled = gates.settle(growth.LOCAL, decided)
        if settled:
            summary['verdicts_recorded'] = len(settled)
    else:
        summary['decisions_read_at'] = previous     # nothing taken, so the next live run reads it all again
    atomic_json(ledger, summary)
    shown = dict(summary)
    if shown.get('decisions'):
        shown['decisions'] = {k: len(v) for k, v in shown['decisions'].items()}
    if isinstance(shown.get('waiting'), dict):
        shown['waiting'] = len(shown['waiting'])
    if instructions:
        shown['instructions'] = [x['line'] for x in instructions]
    return shown, 0 if summary['status'] == 'succeeded' else 1
