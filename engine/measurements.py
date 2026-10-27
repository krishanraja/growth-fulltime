"""Validate aggregate observations. Never ingest people or sum unique counts."""
import datetime as dt
import math
import re

from .clock import LONDON
from .records import instant as rfc3339

METRICS = {'unique_visitors', 'unique_players', 'unique_completers', 'reachable_completers',
           'mature_completers', 'returners_7d', 'returners_playing_second_pundit',
           'survey_respondents', 'very_disappointed', 'shares_attempted', 'attributed_new_completers',
           'ga4_users', 'ga4_sessions', 'posthog_active_users', 'pageviews', 'events',
           'wrong_fact_reports', 'marketing_cash_gbp', 'model_spend_usd', 'founder_minutes',
           'share_arrived_new_listeners', 'brand_post_new_listeners', 'untokenised_new_listeners',
           'shares_created', 'ga4_landing_new_users', 'ga4_landing_sessions'}
COUNTS = METRICS - {'marketing_cash_gbp', 'model_spend_usd', 'founder_minutes'}
RATIOS = {'play_rate': ('unique_players', 'unique_visitors'),
          'finish_rate': ('unique_completers', 'unique_players'),
          'reachable_completion_rate': ('reachable_completers', 'unique_completers'),
          'return_rate_7d': ('returners_7d', 'mature_completers'),
          'second_pundit_rate': ('returners_playing_second_pundit', 'returners_7d'),
          'very_disappointed_rate': ('very_disappointed', 'survey_respondents')}
FIELDS = {'metric', 'value', 'source', 'query_ref', 'window_start', 'window_end',
          'observed_at', 'status', 'note', 'cohort_start', 'cohort_end', 'follow_up_through', 'creative_id'}
# The one metric the product may break down by creative ID, beside its total row.
BY_CREATIVE = 'brand_post_new_listeners'
DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
# Google Analytics in any spelling, compared after lower-casing and removing all
# but letters and digits; GA and gtag as whole words. The last mark is Full Time's
# measurement ID, G-W2QL8RKFJ1.
GA4_MARKS = ('ga4', 'googleanalytics', 'universalanalytics', 'firebaseanalytics', 'analyticsdata', 'runreport',
             'gw2ql8rkfj1')
GA4_WORDS = {'ga', 'gtag'}


def date(value):
    """A calendar date written YYYY-MM-DD, read the same way on every Python."""
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError(f'{value!r} is not a date written YYYY-MM-DD')
    return dt.date.fromisoformat(value)


def instant(value):
    """An RFC 3339 moment with its offset (records.instant)."""
    return rfc3339(value)


def from_ga4(observation):
    """True when the row's source or query_ref names Google Analytics, however spelt."""
    text = f'{observation.get("source", "")} {observation.get("query_ref", "")}'.lower()
    return (any(mark in re.sub(r'[^a-z0-9]', '', text) for mark in GA4_MARKS)
            or bool(GA4_WORDS & set(re.split(r'[^a-z0-9]+', text))))


def validate(observation):
    if set(observation) - FIELDS:
        raise ValueError('unsupported observation fields; only aggregate measures are accepted')
    required = {'metric', 'value', 'source', 'query_ref', 'window_start', 'window_end', 'observed_at', 'status'}
    if not required <= set(observation) or observation['metric'] not in METRICS:
        raise ValueError('observation is missing provenance or has an unknown metric')
    if any(not isinstance(observation[k], str) or not observation[k].strip() for k in ('source', 'query_ref')):
        raise ValueError('source and query_ref must be non-empty text')
    if observation['metric'].endswith('_listeners') and from_ga4(observation):
        raise ValueError('GA4 landings are web sessions, never listeners; a listener count must come '
                         'from the product export')
    if 'creative_id' in observation:
        import growth
        if observation['metric'] != BY_CREATIVE or not isinstance(observation['creative_id'], str) \
                or not growth.CREATIVE_ID.fullmatch(observation['creative_id']):
            raise ValueError(f'creative_id is only for a {BY_CREATIVE} breakdown row, and must be a creative ID')
    start, end = date(observation['window_start']), date(observation['window_end'])
    captured = instant(observation['observed_at'])
    if start > end or captured.astimezone(LONDON).date() <= end \
            or captured > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError('invalid source window or capture time: a window is whole London days, read after '
                         'its last day ended in London and not in the future')
    status, value = observation['status'], observation['value']
    if status not in ('measured', 'missing', 'stale'):
        raise ValueError('status must be measured, missing or stale')
    if status == 'missing' and value is not None:
        raise ValueError('missing observations must have a null value')
    if status != 'missing' and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
        raise ValueError('measured and stale observations need a finite non-negative value')
    if value is not None and observation['metric'] in COUNTS and int(value) != value:
        raise ValueError('counts must be whole numbers')
    if observation['metric'] in ('mature_completers', 'returners_7d', 'returners_playing_second_pundit') and status == 'measured':
        if not all(observation.get(k) for k in ('cohort_start', 'cohort_end', 'follow_up_through')):
            raise ValueError('retention requires cohort and follow-up dates')
        if date(observation['cohort_start']) > date(observation['cohort_end']):
            raise ValueError('invalid cohort start/end interval')
        if date(observation['cohort_end']) + dt.timedelta(days=7) > date(observation['follow_up_through']):
            raise ValueError('retention cohort has not completed its seven-day window')
        if date(observation['follow_up_through']) > captured.date():
            raise ValueError('follow-up cannot be after the observation')
    return observation


def validate_export(export):
    if set(export) != {'schema_version', 'product', 'observations'} or export['schema_version'] != 1 or export['product'] != 'fulltime':
        raise ValueError('aggregate export must identify schema version 1 and product fulltime')
    if not isinstance(export['observations'], list):
        raise ValueError('observations must be a list')
    rows = [validate(x) for x in export['observations']]
    seen = set()
    for row in rows:
        key = (row['metric'], row['window_start'], row['window_end'], row.get('creative_id'))
        if key in seen:
            raise ValueError('duplicate metric/window; reconcile upstream instead of adding unique counts')
        seen.add(key)
    return rows


def scorecard(rows, window_start, window_end, as_of=None):
    as_of = as_of or dt.datetime.now(dt.timezone.utc)
    values = {}
    for row in rows:
        # Only this window's totals are read, so only they are checked: a row for
        # another window, or a per-creative breakdown row, never enters a value.
        if (row.get('window_start'), row.get('window_end')) != (window_start, window_end) or 'creative_id' in row:
            continue
        validate(row)
        old = values.get(row['metric'])
        if old is None or instant(row['observed_at']) > instant(old['observed_at']):
            values[row['metric']] = row
    result = {}
    for metric in sorted(METRICS):
        row = values.get(metric)
        if not row:
            result[metric] = {'value': None, 'status': 'missing', 'note': 'no matching whole-window aggregate'}
        else:
            status = row['status']
            if status == 'measured' and as_of - instant(row['observed_at']) > dt.timedelta(hours=48):
                status = 'stale'
            result[metric] = {**row, 'status': status}
    for name, (num, den) in RATIOS.items():
        n, d = result[num], result[den]
        usable = n['status'] == d['status'] == 'measured' and d['value'] > 0
        if usable and (n.get('source'), n.get('cohort_start'), n.get('cohort_end'), n.get('follow_up_through')) != (
                d.get('source'), d.get('cohort_start'), d.get('cohort_end'), d.get('follow_up_through')):
            usable = False
        if usable and n['value'] > d['value']:
            raise ValueError(f'{name}: numerator exceeds denominator; reconcile the aggregate query')
        result[name] = {'value': n['value'] / d['value'] if usable else None,
                        'numerator': n['value'], 'denominator': d['value'],
                        'status': 'measured' if usable else 'insufficient_data',
                        'window_start': window_start, 'window_end': window_end}
    return result
