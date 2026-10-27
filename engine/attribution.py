"""The Measurement Analyst (docs/ENGINE-V2.md, crew row 8; MEASUREMENT.md, "Share
attribution and Google Analytics").

The North Star is share_arrived_new_listeners: new listeners whose first finished
listen came within seven days of a Full Time share token, counted inside the product
and exported as a weekly aggregate once the product builds the join.
brand_post_new_listeners counts first finished listens from a brand post's link,
read from the creative ID in utm_content, from the same export. Both reach Control
Center as objectives with a rough Poisson interval, or as null with the reason.

Google Analytics 4 runs on fulltime.fm (property G-W2QL8RKFJ1, page views only;
consent item D7 is still open). Its landings by creative ID are a leading web
signal: web sessions, never listeners. No function here turns a GA4 row into a
listener metric, and a GA4 row offered as one is refused. Aggregates only: nothing
here reads the network, posts, sends, schedules or spends.
"""
import datetime as dt
import math
import re

from . import policy, reporting
from .measurements import instant, validate

GA4_PROPERTY = 'G-W2QL8RKFJ1'
GA4_EXPORT = ('product', 'source', 'property', 'query_ref', 'window_start', 'window_end', 'observed_at', 'rows')
GA4_LABELS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content')
GA4_COUNTS = ('new_users', 'sessions', 'engaged_sessions')
GA4_METRICS = ('ga4_landing_new_users', 'ga4_landing_sessions')
UNTAGGED = '(not set)'
LISTENER_OBJECTIVES = ('share_arrived_new_listeners', 'brand_post_new_listeners')
STALE_AFTER = dt.timedelta(hours=48)
DATE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
# Field names that identify a person, a browser or a device. Compared after
# lower-casing and removing everything but letters and digits.
PERSON_NAMES = {'ip', 'ipaddress', 'ipaddr', 'user', 'client', 'device', 'uid', 'cid', 'name', 'fullname',
                'firstname', 'lastname', 'address', 'postcode', 'zipcode', 'idfa', 'idfv', 'gaid',
                'gclid', 'fbclid', 'msclkid', 'ttclid'}
PERSON_PART = re.compile(r'email|phone|mobile|cookie|fingerprint|useragent|'
                         r'(client|user|device|visitor|member|sharer|listener|account|customer|person|profile|'
                         r'session|advertising|pseudo|install|instance|contact)(id|identifier|key|hash)')
NO_EXPORT = {
    'share_arrived_new_listeners':
        'No product export yet: the share token and its join to the first finished listen within 7 days '
        'are not built in the product (MEASUREMENT.md, share attribution).',
    'brand_post_new_listeners':
        'No product export yet: first finished listens by brand-post creative ID (utm_content) are not '
        'exported by the product yet (MEASUREMENT.md, share attribution).'}


def _growth():
    import growth
    return growth


def _count(value, what):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{what} must be a finite, non-negative count')
    return value


# ---------------------------------------------------------------------------
# Small numbers, honestly (MEASUREMENT.md, the interval rule).
# ---------------------------------------------------------------------------
def poisson_interval(count):
    """The rough 95% interval for a weekly count: count plus or minus twice its square
    root, the low end floored at zero, both to one decimal. None for None."""
    if count is None:
        return None
    count = _count(count, 'the count')
    spread = 2 * math.sqrt(count)
    return round(max(0.0, count - spread), 1), round(count + spread, 1)


def z_score(a, b):
    """(a - b) / sqrt(a + b) for two arms with equal exposure; 0.0 when both are zero."""
    a, b = _count(a, 'arm a'), _count(b, 'arm b')
    return 0.0 if a + b == 0 else (a - b) / math.sqrt(a + b)


# ---------------------------------------------------------------------------
# The listener objectives, from the product export only.
# ---------------------------------------------------------------------------
def _from_ga4(row):
    return 'ga4' in str(row.get('source', '')).lower() or str(row.get('query_ref', '')).lower().startswith('ga4')


def _interval_reason(row, extra=''):
    low, high = poisson_interval(row['value'])
    text = (f'Rough 95% interval {low} to {high}: the count plus or minus twice its square root. '
            f'From {row["source"]}, {row["query_ref"]}.' + extra)
    return text[:500]


def objectives(rows, today, as_of=None):
    """Control Center objectives for share_arrived_new_listeners (the North Star) and
    brand_post_new_listeners, over the seven complete London days ending yesterday, in
    reporting.objectives' shape. A value only from a measured product row for exactly
    that week, with its interval in the reason; otherwise null with the reason: no
    product export yet, stale, or window mismatch. A GA4 row is never a listener count."""
    window = reporting.week_window(today)
    start, end = window[0].isoformat(), window[1].isoformat()
    as_of = as_of or reporting.utc_now()
    rows = [validate(dict(row)) for row in rows or []]
    for row in rows:
        if row['metric'].endswith('_listeners') and _from_ga4(row):
            raise ValueError('GA4 landings are web sessions, never listeners; a listener count must come '
                             'from the product export')
    newest = lambda found: max(found, key=lambda r: (instant(r['observed_at']), r['window_end'], r['window_start']))
    exact = {}
    for row in rows:
        if (row['window_start'], row['window_end']) == (start, end):
            exact.setdefault(row['metric'], []).append(row)
    out = []
    for key in LISTENER_OBJECTIVES:
        mine = [r for r in rows if r['metric'] == key]
        if not mine:
            out.append(reporting._objective(key, 'people', None, 'missing', NO_EXPORT[key], window))
            continue
        if key not in exact:
            other = newest(mine)
            out.append(reporting._objective(
                key, 'people', None, 'missing',
                f'Window mismatch: the newest product export covers {other["window_start"]} to '
                f'{other["window_end"]}, not the seven complete London days {start} to {end}. Other windows '
                'are never added into a week.', window))
            continue
        row = newest(exact[key])
        if row['status'] == 'missing':
            out.append(reporting._objective(
                key, 'people', None, 'missing',
                'The product export for this week reports this count as missing; nothing was measured.', window))
        elif row['status'] == 'stale' or as_of - instant(row['observed_at']) > STALE_AFTER:
            out.append(reporting._objective(
                key, 'people', None, 'stale',
                f'Stale: the newest product export for this week was taken at {row["observed_at"]}, more than '
                '48 hours ago or marked stale. Refresh it before counting.', window))
        else:
            extra = ''
            dark = [r for r in exact.get('untokenised_new_listeners', []) if r['status'] == 'measured']
            if key == 'share_arrived_new_listeners' and dark:
                extra = (f' Untokenised new listeners, reported apart and never counted here: '
                         f'{newest(dark)["value"]}.')
            out.append(reporting._objective(key, 'people', row['value'], 'measured',
                                            _interval_reason(row, extra), window))
    return out


# ---------------------------------------------------------------------------
# Google Analytics 4 landings: a leading web signal, never listeners.
# ---------------------------------------------------------------------------
def _person(key):
    name = re.sub(r'[^a-z0-9]', '', str(key).lower())
    return name in PERSON_NAMES or PERSON_PART.search(name) is not None


def _refuse_people(fields, where):
    found = sorted(str(k) for k in fields if _person(k))
    if found:
        raise ValueError(f'{where} carries person-level fields ({", ".join(found)}); only aggregate counts '
                         'by campaign tag enter this engine')


def _whole_days(export):
    start, end = export['window_start'], export['window_end']
    if not all(isinstance(v, str) and DATE.match(v) for v in (start, end)):
        raise ValueError('a GA4 window must be whole London days, given as dates (YYYY-MM-DD), not times')
    try:
        first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        captured = instant(str(export['observed_at']))
    except ValueError:
        raise ValueError('a GA4 export needs real window dates and an observed_at with a time zone') from None
    if first > last:
        raise ValueError('the GA4 window starts after it ends')
    if captured.astimezone(reporting.LONDON).date() <= last:
        raise ValueError('the GA4 window must be whole London days: its last day had not ended in London '
                         'when it was read')
    if captured > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError('the GA4 export was observed in the future')


def ga4_rows(export):
    """The validated landing rows of a GA4 aggregate export (MEASUREMENT.md, export
    shapes). Refuses unknown fields, any person-level field, contact-like values,
    counts that are not whole and non-negative, any property but Full Time's, windows
    that are not whole London days, and utm_content that is neither a creative ID nor
    "(not set)"."""
    if not isinstance(export, dict):
        raise ValueError('a GA4 export must be a JSON object')
    _refuse_people(export, 'the GA4 export')
    if set(export) != set(GA4_EXPORT):
        unknown = sorted(set(map(str, export)) - set(GA4_EXPORT))
        raise ValueError('a GA4 export must carry exactly ' + ', '.join(GA4_EXPORT)
                         + (f'; unknown: {", ".join(unknown)}' if unknown else ''))
    if export['product'] != 'fulltime' or export['source'] != 'ga4':
        raise ValueError('a GA4 export must say product fulltime and source ga4')
    if export['property'] != GA4_PROPERTY:
        raise ValueError(f'this GA4 export is not for Full Time\'s property {GA4_PROPERTY}')
    if not isinstance(export['query_ref'], str) or not export['query_ref'].strip():
        raise ValueError('a GA4 export needs a non-empty query_ref')
    _whole_days(export)
    if not isinstance(export['rows'], list):
        raise ValueError('GA4 rows must be a list')
    if policy.sensitive_errors(export):
        raise ValueError('the GA4 export carries contact or credential-like text; only aggregates are accepted')
    creative = _growth().CREATIVE_ID
    out, seen = [], set()
    for number, row in enumerate(export['rows'], start=1):
        if not isinstance(row, dict):
            raise ValueError(f'GA4 row {number} must be an object')
        _refuse_people(row, f'GA4 row {number}')
        if set(row) != set(GA4_LABELS) | set(GA4_COUNTS):
            raise ValueError(f'GA4 row {number} must carry exactly ' + ', '.join(GA4_LABELS + GA4_COUNTS))
        for key in GA4_LABELS:
            if not isinstance(row[key], str) or not row[key].strip() or len(row[key]) > 500:
                raise ValueError(f'GA4 row {number}: {key} must be non-empty text')
        if row['utm_content'] != UNTAGGED and not creative.match(row['utm_content']):
            raise ValueError(f'GA4 row {number}: utm_content must be a creative ID or {UNTAGGED}; '
                             'fold other labels into (not set) before export')
        for key in GA4_COUNTS:
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError(f'GA4 row {number}: {key} must be a whole, non-negative count')
        if row['engaged_sessions'] > row['sessions']:
            raise ValueError(f'GA4 row {number}: engaged sessions cannot exceed sessions')
        key = tuple(row[k] for k in GA4_LABELS)
        if key in seen:
            raise ValueError(f'GA4 row {number} repeats a campaign tag; reconcile upstream instead of adding')
        seen.add(key)
        out.append(dict(row))
    return out


def ga4_observations(export):
    """MEASUREMENT.md version 1 rows for ga4_landing_new_users and ga4_landing_sessions,
    the export's totals, measured. Web landings on fulltime.fm, never listeners: these
    two GA4 metrics are the only ones this function can produce."""
    rows = ga4_rows(export)
    untagged = sum(r['sessions'] for r in rows if r['utm_content'] == UNTAGGED)
    note = (f'GA4 web landings on fulltime.fm ({GA4_PROPERTY}), summed over {len(rows)} campaign rows, '
            f'{untagged} sessions untagged. Web sessions, never listeners. Consent item D7 is open.')
    totals = {'ga4_landing_new_users': sum(r['new_users'] for r in rows),
              'ga4_landing_sessions': sum(r['sessions'] for r in rows)}
    out = []
    for metric in GA4_METRICS:
        if metric.endswith('_listeners'):
            raise ValueError('GA4 landings are never listeners')
        out.append(validate({'metric': metric, 'value': totals[metric], 'source': 'ga4',
                             'query_ref': export['query_ref'], 'window_start': export['window_start'],
                             'window_end': export['window_end'], 'observed_at': export['observed_at'],
                             'status': 'measured', 'note': note}))
    return out


class Landings(dict):
    """{creative_id: {new_users, sessions}}, with "(not set)" traffic kept beside it
    as .untagged and never assigned to a creative."""
    untagged = None


def by_creative(ga4_export):
    """GA4 landings per creative ID for the What-Works Analyst and the weekly report.
    A leading web signal only: it never stands in for a listener count."""
    out = Landings()
    out.untagged = {'new_users': 0, 'sessions': 0}
    for row in sorted(ga4_rows(ga4_export), key=lambda r: r['utm_content']):
        target = out.untagged if row['utm_content'] == UNTAGGED else out.setdefault(
            row['utm_content'], {'new_users': 0, 'sessions': 0})
        target['new_users'] += row['new_users']
        target['sessions'] += row['sessions']
    return out
