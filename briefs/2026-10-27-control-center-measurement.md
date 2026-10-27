# Brief for Control Center: Google Analytics, new objectives and handcrafted mode (27 October 2026)

For a Control Center session, once Krish approves. Growth does not implement anything in Control Center (AGENTS.md); this is the handoff. Plan: [ENGINE-V2](../docs/ENGINE-V2.md).

## 1. Google Analytics 4 for the Measurement Analyst

Krish, 27 October 2026: "You have Google Analytics installed already and Control Centre can see that. Make sure this is a part of your Measurement Specialist."

Google Analytics 4 runs on fulltime.fm (property `G-W2QL8RKFJ1`, page views only). Control Center's API gateway lists no Google Analytics operation today, so the engine cannot read it. Please expose a read-only, aggregate operation, or attach the data to the engine's directive:

- property `G-W2QL8RKFJ1`, whole London days or weeks;
- dimensions: session source, medium, campaign and manual ad content (the engine's `utm_content`, which is the creative ID);
- metrics: new users, sessions, engaged sessions;
- counts only, with no client, user or device IDs.

The engine's adapter is `engine/attribution.py` (`ga4_rows`, `ga4_observations`, `by_creative`), and the export shape is in `MEASUREMENT.md` and `examples/ga4-export.example.json`. These are web landings, never listeners; the engine keeps them apart from every listener number.

## 2. Register two objectives for growth-fulltime

`share_arrived_new_listeners` (the North Star) and `brand_post_new_listeners` (alpha testers from brand posts). The engine keeps reporting `attributed_new_completers` until these are registered, so nothing breaks.

## 3. Handcrafted mode for Full Time

Ruling (Krish, 2026-10-27): he publishes in Buffer himself. In protocol terms this is `handcrafted`: the engine prepares the exact artifact and stops. Krish switches Full Time to handcrafted on his list; the engine already treats an approved go-live as an instruction for him, never an action.

## 4. What the engine now sends

Reports at protocol 1.1.0, with the weekly campaign spec as a `stage: "plan"` proposal behind `strategy` (gate G1) and each matchday pack as one `post` proposal (gate G2). Ruling asks that Krish has decided (D1, and the new ORGANIC entry) are no longer re-sent.
