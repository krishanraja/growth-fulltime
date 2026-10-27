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

## Share attribution and Google Analytics (v2, 2026-10-27)

The Measurement Analyst (`engine/attribution.py`) owns the North Star count. It
reads aggregates only, under every rule above. Missing, stale and measured zero
stay different: a count nobody has measured is null with its reason, never zero.

**The North Star: `share_arrived_new_listeners`.** New listeners in the window
whose first ever finished listen came within 7 days of opening a Full Time share
link with a valid share token. First touch wins: when one new listener opened two
tokens, the earliest in the window gets the credit. The product mints the token
and runs the join to the first finished listen inside its own source; the export
carries only the weekly count. Until the product builds the token and the join,
this objective is reported as missing with the reason "no product export yet".
Arrivals without a token never count, even when they are probably word of mouth:
the export reports them apart as `untokenised_new_listeners`. Shares made outside
Full Time, such as a platform's own clip tool, are invisible and are never
estimated into the number. `shares_created` counts the tokens minted in the
window, so share yield (arrivals per share) can be read beside the count.

**Brand-post arrivals: `brand_post_new_listeners`.** New listeners whose first
finished listen came from a session that landed through a brand post's link. The
post is identified by `utm_content`, which carries the creative ID that
`growth.py link` adds. It comes from the same product export, and the product
credits each new listener once, to the first touch in the window.

**Google Analytics 4 landings: `ga4_landing_new_users` and `ga4_landing_sessions`.**
Google Analytics 4 runs on fulltime.fm (measurement ID `G-W2QL8RKFJ1`, page views
only). Consent item D7 is still open, and reading aggregates does not close it.
New users and sessions by session source, medium, campaign and manual ad content
(`utm_content`) are a leading web signal by creative ID: they show which posts sent
people to the site, not who listened. They are web sessions, never listeners. No
code path turns a GA4 row into any `*_listeners` metric, a GA4-sourced row offered
as a listener count is refused, and a test proves both. GA4 numbers never replace
a listening outcome; the What-Works Analyst may use them only as a leading signal
beside the listener counts. `(not set)` traffic is reported as untagged and is
never assigned to a creative. Summing rows is sound here because each new user's
first session, and each session, has exactly one source, medium, campaign and
content within the one window.

**Export shapes.** The product export is a version 1 observation export, as above,
with these four metrics for the seven complete London days ending yesterday
(`examples/attribution-export.example.json`, synthetic):

```json
{"schema_version": 1, "product": "fulltime", "observations": [
  {"metric": "share_arrived_new_listeners", "value": 7, "source": "...", "query_ref": "...",
   "window_start": "2026-10-19", "window_end": "2026-10-25",
   "observed_at": "2026-10-26T07:30:00+00:00", "status": "measured"}]}
```

The GA4 export is written by the read-only reader (`growth.py ga4 report`,
`engine/ga4.py`) or produced through Control Center
(`examples/ga4-export.example.json`, synthetic):

```json
{"product": "fulltime", "source": "ga4", "property": "G-W2QL8RKFJ1", "query_ref": "...",
 "window_start": "2026-10-19", "window_end": "2026-10-25",
 "observed_at": "2026-10-26T07:30:00+00:00",
 "rows": [{"utm_source": "tiktok", "utm_medium": "organic_video",
           "utm_campaign": "ft_growth_202610", "utm_content": "<creative ID or (not set)>",
           "new_users": 12, "sessions": 14, "engaged_sessions": 9}]}
```

A GA4 export carries exactly these fields. Its window is whole London days, given
as dates, and its last day had ended in London when it was read; the property must
report in Europe/London for its days to be London days. Counts are whole and
non-negative, and engaged sessions never exceed sessions. `utm_content` is a
creative ID or `(not set)`; a file with any other label is refused, so an exporter
must fold other labels into `(not set)` first. One campaign tag appears once. The property
must be Full Time's. Any person-level field (a client ID, user ID, IP address,
email, device ID or similar) or any contact-like value refuses the whole file.
Google's thresholding can hide small counts: that is a limitation to report, never
a zero.

**Objectives.** Control Center receives `share_arrived_new_listeners` and
`brand_post_new_listeners` for the seven complete London days ending yesterday. A
measured row for exactly that week gives the value, with its interval in the
reason. Otherwise the value is null and the reason says which: no product export
yet; stale (taken more than 48 hours ago, or marked stale); or window mismatch (an
export exists, but not for that exact week; other windows are never added into a
week). The existing `attributed_new_completers` objective keeps reporting until
Control Center registers the new keys.

**The interval rule.** Weekly counts are treated as Poisson. A measured count is
reported with a rough 95% interval: the count plus or minus twice its square root,
the low end floored at zero, both to one decimal (0.5 to 9.5 at 5; 35.0 to 63.0 at
49). Two arms with equal exposure are compared with z = (a - b) / sqrt(a + b), and
a difference is called only when z is 2 or more in size. A result from fewer than
20 events per arm is directional only. The learning register (`engine/learning.py`)
applies this bar: a claim is confirmed only when it was pre-registered, overlaps no
other test, ran at least two matchweeks, has at least 20 events per arm and z of 2
or more in its favour; it is refuted on the same bar with z of 2 or more against
it; and it shows no difference when the planned matchweeks have passed with z under
2 in size and 20 events per arm. Anything else is directional.
