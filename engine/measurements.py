"""Validate aggregate observations. Never ingest people or sum unique counts."""
import datetime as dt
import math

METRICS = {'unique_visitors', 'unique_players', 'unique_completers', 'reachable_completers',
           'mature_completers', 'returners_7d', 'returners_playing_second_pundit',
           'survey_respondents', 'very_disappointed', 'shares_attempted', 'attributed_new_completers',
           'ga4_users', 'ga4_sessions', 'posthog_active_users', 'pageviews', 'events',
           'wrong_fact_reports', 'marketing_cash_gbp', 'model_spend_usd', 'founder_minutes'}
COUNTS = METRICS - {'marketing_cash_gbp', 'model_spend_usd', 'founder_minutes'}
RATIOS = {'play_rate': ('unique_players', 'unique_visitors'),
          'finish_rate': ('unique_completers', 'unique_players'),
          'reachable_completion_rate': ('reachable_completers', 'unique_completers'),
          'return_rate_7d': ('returners_7d', 'mature_completers'),
          'second_pundit_rate': ('returners_playing_second_pundit', 'returners_7d'),
          'very_disappointed_rate': ('very_disappointed', 'survey_respondents')}
FIELDS = {'metric', 'value', 'source', 'query_ref', 'window_start', 'window_end',
          'observed_at', 'status', 'note', 'cohort_end', 'follow_up_through'}


def date(value):
    return dt.date.fromisoformat(value)


def instant(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('observation timestamp must include a timezone')
    return result


def validate(observation):
    if set(observation) - FIELDS:
        raise ValueError('unsupported observation fields; only aggregate measures are accepted')
    required = {'metric', 'value', 'source', 'query_ref', 'window_start', 'window_end', 'observed_at', 'status'}
    if not required <= set(observation) or observation['metric'] not in METRICS:
        raise ValueError('observation is missing provenance or has an unknown metric')
    if not observation['source'] or not observation['query_ref']:
        raise ValueError('source and query_ref must be non-empty')
    start, end = date(observation['window_start']), date(observation['window_end'])
    captured = instant(observation['observed_at'])
    if start > end or captured.date() < end or captured > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError('invalid source window or capture time')
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
        if not observation.get('cohort_end') or not observation.get('follow_up_through'):
            raise ValueError('retention requires cohort and follow-up dates')
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
        key = (row['metric'], row['window_start'], row['window_end'])
        if key in seen:
            raise ValueError('duplicate metric/window; reconcile upstream instead of adding unique counts')
        seen.add(key)
    return rows


def scorecard(rows, window_start, window_end, as_of=None):
    as_of = as_of or dt.datetime.now(dt.timezone.utc)
    values = {}
    for row in rows:
        validate(row)
        if (row['window_start'], row['window_end']) != (window_start, window_end):
            continue
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
        if usable and (n.get('source'), n.get('cohort_end'), n.get('follow_up_through')) != (
                d.get('source'), d.get('cohort_end'), d.get('follow_up_through')):
            usable = False
        if usable and n['value'] > d['value']:
            raise ValueError(f'{name}: numerator exceeds denominator; reconcile the aggregate query')
        result[name] = {'value': n['value'] / d['value'] if usable else None,
                        'numerator': n['value'], 'denominator': d['value'],
                        'status': 'measured' if usable else 'insufficient_data',
                        'window_start': window_start, 'window_end': window_end}
    return result
