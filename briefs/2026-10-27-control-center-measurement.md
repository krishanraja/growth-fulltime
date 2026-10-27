# Brief for Control Center: Google Analytics, new objectives and handcrafted mode (27 October 2026)

For a Control Center session, once Krish approves. Growth does not implement anything in Control Center (AGENTS.md); this is the handoff. Plan: [ENGINE-V2](../docs/ENGINE-V2.md).

## 1. Google Analytics 4 for the Measurement Analyst

Krish, 27 October 2026: "You have Google Analytics installed already and Control Centre can see that. Make sure this is a part of your Measurement Specialist." Later the same day: "just get google analytics data from control center, much easier".

Google Analytics 4 runs on fulltime.fm (measurement ID `G-W2QL8RKFJ1`, page views only). Read live on 27 October, Control Center's API gateway has no Google Analytics operation, and the only Analytics fact it holds for Full Time is full-time's own NOW.md line saying the tag loads on every page. So it cannot hand the engine any numbers yet. Control Center is the route Krish chose: please add the read there, with the Google sign-in held server-side like the gateway's other keys, read-only (`analytics.readonly`).

**What to build, in the order that needs nothing from Krish once it ships:**

1. **Attach the week's landings to the engine's directive.** In the directive for `growth-fulltime`, add a field `ga4_landings` holding one export in exactly the shape below, for the seven complete London days ending yesterday. The engine's daily loop already reads the directive, and the protocol lets an engine ignore a field it does not know, so this breaks no other engine. The engine reads it today: `engine/control_center.py`, `measurement_lines`.
2. **A gateway operation for sessions**, for example `ga4.landings` with input `{venture: "full_time", start_date, end_date}` (whole London days, at most 92), returning the same export. A Claude session saves it to `local/ga4/landings-latest.json`, which the engine reads too.

**The export** (MEASUREMENT.md, "Google Analytics landings"; `examples/ga4-export.example.json`; checked by `engine/attribution.py` `ga4_rows`):

```json
{"product": "fulltime", "source": "ga4", "property": "G-W2QL8RKFJ1",
 "query_ref": "<a stable id for the query>", "window_start": "YYYY-MM-DD", "window_end": "YYYY-MM-DD",
 "observed_at": "<ISO time with offset, after the window's last London day ended>",
 "rows": [{"utm_source": "...", "utm_medium": "...", "utm_campaign": "...", "utm_content": "...",
           "new_users": 0, "sessions": 0, "engaged_sessions": 0}]}
```

- The query: one runReport on the Full Time property with dimensions `sessionSource`, `sessionMedium`, `sessionCampaignName` and `sessionManualAdContent` (the engine's `utm_content`, which carries the creative ID), and metrics `newUsers`, `sessions` and `engagedSessions`. Counts only: never a client, user or device ID.
- `utm_content` must be one of the engine's creative IDs (the `CREATIVE_ID` pattern in `growth.py`) or `(not set)`: fold any other value, including another site's tag, `(other)` and anything that looks like an email, into `(not set)` and sum the rows that then coincide. Empty labels become `(not set)`.
- A reference implementation of the read and the folding, standard library only, is `engine/ga4.py` (`report_request`, `run_report`, `to_export`), which can be copied as it is.

These are web landings, never listeners; the engine keeps them apart from every listener number.

## 2. Register two objectives for growth-fulltime

`share_arrived_new_listeners` (the North Star) and `brand_post_new_listeners` (alpha testers from brand posts). The engine keeps reporting `attributed_new_completers` until these are registered, so nothing breaks.

## 3. Handcrafted mode for Full Time

Ruling (Krish, 2026-10-27): he publishes in Buffer himself. In protocol terms this is `handcrafted`: the engine prepares the exact artifact and stops. Krish switches Full Time to handcrafted on his list; the engine already treats an approved go-live as an instruction for him, never an action.

## 4. What the engine now sends

Reports at protocol 1.1.0, with the weekly campaign spec as a `stage: "plan"` proposal behind `strategy` (gate G1) and each matchday pack as one `post` proposal (gate G2). Ruling asks that Krish has decided (D1, and the new ORGANIC entry) are no longer re-sent.
