# Full Time measurement contract

Only aggregate data enters this engine. The source system resolves anonymous
identity, consent, cross-device joins and deduplication. Do not export person
IDs, addresses, contact records, event payloads or transcripts into a metric.

## Input and observation windows

`growth.py metrics FILE` validates a version 1 export with product `fulltime`
and an observations array. `run --observations FILE` imports it into private
history. Each observation contains metric, value, source, query_ref,
window_start, window_end, observed_at and status. Dates are inclusive source
dates; the operational window is Europe/London. Captures include a timezone.
An optional note explains limitations without identifying anyone.

Statuses are measured, missing and stale. Missing values are null. Measured
zero means the exact query ran successfully and returned zero. Old samples
retain their dates and become stale after 48 hours. No matching whole-window
query means missing. Daily or rolling uniques are never added into a week.
Duplicate metric/window rows within one export are refused. A subsequent
capture updates the reading while preserving source history.

For retention measures, include cohort_start, cohort_end and follow_up_through.
The cohort interval identifies first completions; the observation window and
follow-up interval identify when the mature reading was taken. Numerators and
denominators must refer to the same complete cohort interval. Every member
of the reported cohort must have a full seven-day opportunity to return.
Immature cohorts are refused as measured retention. Supply gaps belong beside
the cohort, not in a guessed explanation of its behaviour.

## Required source queries

These are semantic query requirements, not claims that collectors already
implement them. The full-time/Control Centre implementation owns the joins.
Version the actual executed query in query_ref and reconcile a controlled
journey before calling its output measured.

| Metric | Whole-window definition |
|---|---|
| unique_visitors | Distinct permitted anonymous/product identities with a valid visit in the exact window |
| unique_players | Distinct identities with actual media playback, not loading, intent or resume duplication |
| unique_completers | Distinct identities completing an approved edition; deduplicate repeat completions |
| reachable_completers | Completers with a verified, permission-covered contact or push opt-in; count the intersection upstream |
| mature_completers | Distinct first completers whose entire seven-day follow-up has elapsed |
| returners_7d | Members of that same mature cohort who actually start another approved show within seven days |
| returners_playing_second_pundit | Returning cohort members with actual playback of two distinct AI Pundits on the same match |
| survey_respondents | Distinct eligible respondents to the disappointment question |
| very_disappointed | Respondents selecting that exact answer; retain denominator and response rate |
| shares_attempted | Observed share intents; never label this delivered private messages |
| attributed_new_completers | New completers with supported creative/source attribution; not all private forwards |
| wrong_fact_reports | Verified inbound reports in the exact window; absent inbox access is missing |
| ga4_users, ga4_sessions | GA4's stated users/sessions in its source window, separate from listening outcomes |
| posthog_active_users, pageviews, events | Coarse source counters, never substitutes for completers |
| marketing_cash_gbp, model_spend_usd, founder_minutes | Recorded actual usage in the window; missing usage stays unknown |

The source needs edition, drop, AI Pundit, playback-session and coverage-date
context on actual starts and completions. The existing switch event also fires
on paused loading and match navigation. It cannot establish comparison.
Beta membership and initial/current attribution need explicit definitions:
preserve source and creative tags; do not silently count unrelated traffic.

Use `COUNT(DISTINCT identity)` over the requested complete interval, a
source-local existence join for reachable consent, and cohort-based existence
queries for return/comparison. Keep identity joins inside the source. Report
anonymous-device and cross-device limitations; never assume an unimplemented
join. Refused consent must not produce prohibited analytics events.

## Derived rates and decisions

The scorecard computes play/visit, complete/play, reachable/complete,
returner/mature-completer, second-pundit/returner and very-disappointed/respondent
rates only from matching measured windows and compatible sources/cohorts.
It reports numerator and denominator. A zero denominator, missing or stale
input produces insufficient_data, never an invented zero. A numerator above
its denominator is refused. Rates are numeric internal evidence, not public
marketing claims.

Experiments need an immutable ID, hypothesis, audience, one changed variable,
primary metric, guardrails, duration of at least seven days, minimum sample
and stopping rule. Result files contain started_on, ended_on, sample, value,
decision and evidence_ref. Value may be null. Decisions are scale, iterate,
hold or kill. Immature/underpowered tests are inconclusive and cannot scale.
Newer results and failed tests remain in history.

The existing release thresholds remain product decisions: this contract does
not approve them, close consent or declare launch readiness.
