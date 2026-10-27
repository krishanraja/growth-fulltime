"""Private atomic checkpoints with stable IDs, history, locking and recovery."""
import contextlib
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


RFC3339 = re.compile(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})')


def instant(value):
    """A moment with its offset, read the same way on every Python from 3.9: RFC 3339
    only (date, T, time, optional fraction, then Z or +HH:MM). Python 3.11 and later
    accept far more in fromisoformat, so it is never trusted alone."""
    found = RFC3339.fullmatch(value) if isinstance(value, str) else None
    if not found:
        raise ValueError(f'{value!r} is not an RFC 3339 date and time with its offset')
    day, clock, fraction, offset = found.groups()
    fraction = '.' + (fraction + '000000')[:6] if fraction else ''
    return dt.datetime.fromisoformat(f'{day}T{clock}{fraction}{"+00:00" if offset == "Z" else offset}')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def empty():
    return {'schema_version': 1, 'product': 'fulltime', 'packs': {}, 'creatives': {},
            'experiments': {}, 'runs': {}, 'observations': []}


def validate(value):
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('product') != 'fulltime':
        raise ValueError('invalid history schema or product; history was not replaced')
    for key in ('packs', 'creatives', 'experiments', 'runs'):
        if not isinstance(value.get(key), dict) or any(not isinstance(row, dict) for row in value[key].values()):
            raise ValueError('invalid history collection: ' + key)
    if not isinstance(value.get('observations'), list):
        raise ValueError('invalid observation history')
    for key, record in value['packs'].items():
        if record.get('id') != key or not isinstance(record.get('revisions'), list):
            raise ValueError('invalid pack identity or revision history')
        for revision in record['revisions']:
            if not isinstance(revision, dict) or fingerprint(revision.get('pack')) != revision.get('digest'):
                raise ValueError('pack revision checksum does not match its content')
        if not any(row['digest'] == record.get('latest_digest') for row in record['revisions']):
            raise ValueError('latest pack revision is missing')
    from .policy import sensitive_errors
    if sensitive_errors(value):
        raise ValueError('history contains private contacts or credential-like data')
    return value


class History:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'history.json'

    def read(self):
        if not self.path.exists():
            return empty()
        try:
            return validate(json.loads(self.path.read_text(encoding='utf-8')))
        except (ValueError, OSError) as error:
            raise ValueError('history is unreadable; restore a validated backup before continuing') from error

    @contextlib.contextmanager
    def transaction(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / '.write-lock'
        deadline = time.monotonic() + 10
        while True:
            try:
                lock.mkdir()
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ValueError('history is locked; verify no writer is running before removing .write-lock')
                time.sleep(0.02)
        try:
            state = self.read()
            before = copy.deepcopy(state)
            yield state
            validate(state)
            if state != before or not self.path.exists():
                if self.path.exists():
                    backup = self.root / 'backups' / (fingerprint(before) + '.json')
                    if not backup.exists():
                        atomic_json(backup, before)
                atomic_json(self.path, state)
        finally:
            lock.rmdir()

    def restore(self, source):
        candidate = validate(json.loads(Path(source).read_text(encoding='utf-8')))
        # Recovery also locks, but intentionally does not parse the damaged primary.
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / '.write-lock'
        try:
            lock.mkdir()
        except FileExistsError as error:
            raise ValueError('history is locked; recovery refused') from error
        try:
            if self.path.exists():
                damaged = self.root / ('before-restore-' + uuid.uuid4().hex + '.json')
                damaged.write_bytes(self.path.read_bytes())
            atomic_json(self.path, candidate)
        finally:
            lock.rmdir()
        return self.read()

    def checkpoint(self, pack):
        from .policy import sensitive_errors
        if pack.get('venture') != 'fulltime':
            raise ValueError('history accepts only explicitly scoped Full Time packs')
        if sensitive_errors(pack):
            raise ValueError('private contact or credential-like data refused before checkpoint')
        key = f'fulltime:{pack["pack_date"]}:{pack["kind"]}'
        revision = fingerprint(pack)
        with self.transaction() as state:
            old = state['packs'].get(key, {'revisions': []})
            if not any(x['digest'] == revision for x in old['revisions']):
                old['revisions'].append({'digest': revision, 'captured_at': now(), 'pack': copy.deepcopy(pack)})
            old.update({'id': key, 'latest_digest': revision, 'delivery': 'pending_handoff'})
            state['packs'][key] = old
            for item in pack.get('items') or []:
                cid = item.get('creative_id')
                if not cid:
                    continue
                creative = state['creatives'].get(cid)
                identity = {k: item.get(k) for k in ('platform', 'drop_id', 'pundits')}
                if creative and creative['identity'] != identity:
                    raise ValueError('creative ID reused for a different channel, match or AI Pundit')
                if not creative:
                    creative = {'id': cid, 'identity': identity, 'status': 'drafted', 'versions': [],
                                'publication': None, 'outcomes': []}
                if not any(v['digest'] == fingerprint(item) for v in creative['versions']):
                    creative['versions'].append({'digest': fingerprint(item), 'item': copy.deepcopy(item), 'at': now()})
                if creative['status'] not in ('published', 'skipped'):
                    creative['status'] = 'held' if item.get('holds') or item.get('needs') else 'ready'
                published = creative.get('publication') or {}
                creative['current_version_published'] = (creative['status'] == 'published'
                                                        and published.get('version_digest') == fingerprint(item))
                creative['latest_version_status'] = ('published' if creative['current_version_published'] else
                                                     'held' if item.get('holds') or item.get('needs') else 'ready')
                state['creatives'][cid] = creative
        return {'id': key, 'digest': revision, 'delivery': 'pending_handoff'}

    def mark(self, creative_id, status, url=None, human_confirmed=False):
        if status not in ('published', 'skipped'):
            raise ValueError('manual status must be published or skipped')
        if not human_confirmed:
            raise ValueError('publication and skip evidence need explicit human confirmation')
        if status == 'published':
            from urllib.parse import urlsplit
            parsed = urlsplit(url or '')
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('published work needs an actual HTTPS publication URL')
            from .policy import sensitive_errors
            if sensitive_errors(url):
                raise ValueError('publication evidence must not contain credentials or contact data')
        with self.transaction() as state:
            creative = state['creatives'].get(creative_id)
            if not creative:
                raise ValueError('unknown creative ID')
            creative['status'] = status
            creative['publication'] = {'url': url if status == 'published' else None,
                                       'recorded_at': now(), 'human_confirmed': True,
                                       'version_digest': creative['versions'][-1]['digest']}
            creative['current_version_published'] = status == 'published'
            creative['latest_version_status'] = status

    def experiment(self, spec):
        from .measurements import METRICS, RATIOS
        from .policy import sensitive_errors
        if sensitive_errors(spec):
            raise ValueError('experiment records contain aggregates and references only')
        required = {'id', 'hypothesis', 'audience', 'changed_variable', 'primary_metric',
                    'guardrails', 'duration_days', 'min_sample', 'stopping_rule'}
        if set(spec) != required or not all(spec.get(k) for k in required):
            raise ValueError('experiment must contain exactly the documented non-empty fields')
        if not re_identifier(spec['id']) or spec['primary_metric'] not in METRICS | set(RATIOS):
            raise ValueError('invalid experiment ID or primary metric')
        if any(not isinstance(spec[k], str) or not spec[k].strip()
               for k in ('hypothesis', 'audience', 'changed_variable', 'stopping_rule')):
            raise ValueError('experiment hypothesis, audience, variable and stopping rule must be text')
        if type(spec['duration_days']) is not int or spec['duration_days'] < 7:
            raise ValueError('product experiments must run at least seven days')
        if type(spec['min_sample']) is not int or spec['min_sample'] < 1:
            raise ValueError('min_sample must be positive')
        if not isinstance(spec['guardrails'], list) or not spec['guardrails'] or any(not isinstance(x, str) or not x.strip() for x in spec['guardrails']):
            raise ValueError('guardrails must be a non-empty list')
        with self.transaction() as state:
            old = state['experiments'].get(spec['id'])
            if old and old['spec'] != spec:
                raise ValueError('experiment definition is immutable; use a new ID for a new test')
            state['experiments'].setdefault(spec['id'], {'spec': spec, 'status': 'planned', 'results': []})

    def result(self, identifier, result):
        fields = {'started_on', 'ended_on', 'sample', 'value', 'decision', 'evidence_ref'}
        if set(result) != fields or not result.get('evidence_ref'):
            raise ValueError('result needs the documented fields and an evidence reference')
        start, end = (dt.date.fromisoformat(result[k]) for k in ('started_on', 'ended_on'))
        if end < start or end > dt.datetime.now(dt.timezone.utc).date():
            raise ValueError('invalid observation window')
        if type(result['sample']) is not int or result['sample'] < 0:
            raise ValueError('sample must be a non-negative integer')
        if result['decision'] not in ('scale', 'iterate', 'hold', 'kill'):
            raise ValueError('decision must be scale, iterate, hold or kill')
        if result['value'] is not None:
            import math
            if type(result['value']) not in (float, int) or not math.isfinite(result['value']):
                raise ValueError('result must be a finite number or null')
        with self.transaction() as state:
            experiment = state['experiments'].get(identifier)
            if not experiment:
                raise ValueError('unknown experiment')
            spec = experiment['spec']
            from .measurements import RATIOS, COUNTS
            if result['value'] is not None:
                if result['value'] < 0 or (spec['primary_metric'] in RATIOS and result['value'] > 1):
                    raise ValueError('metric result is outside its non-negative or rate bounds')
                if spec['primary_metric'] in COUNTS and int(result['value']) != result['value']:
                    raise ValueError('count results must be whole numbers')
            enough = ((end-start).days >= spec['duration_days'] and result['sample'] >= spec['min_sample']
                      and result['value'] is not None)
            if not enough and result['decision'] == 'scale':
                raise ValueError('cannot scale an immature or underpowered experiment')
            experiment['status'] = 'complete' if enough else 'inconclusive'
            entry = {**result, 'status': experiment['status']}
            if entry not in experiment['results']:
                experiment['results'].append(entry)


def re_identifier(value):
    import re
    return isinstance(value, str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,79}', value) is not None
