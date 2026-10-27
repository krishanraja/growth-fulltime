# Match Clock

Crew card (docs/ENGINE-V2.md, section 3), loaded when the week's fixtures are ranked and when a matchday pack is timed.

**Job.** Pick the matches fans are arguing about, rank them for the weekly spec, and time each take from the product's publish of its show, not from the final whistle.

**Runner.** The CLI. No model, no tokens.

**Owns.**
- The spec's `fixtures[]`: `fixture_ref`, kickoff, home, away, rivalry and `rank`. Krish may strike one at G1; a struck fixture stays off that week.
- The window for each take, anchored to the edition's `published_at`.
- The minutes from publish to pack ready, for every pack.

**Lint before acting: `engine.crew.fixtures_fresh()`.** The fixtures were read today in London, and never in the future. The ranked fixtures then pass `engine.spec.validate()`: a kickoff with its UTC offset, a rank, a rivalry flag.

**Measured check after acting: `engine.crew.publish_to_pack_minutes()`.** Whole minutes from the edition's `published_at` (from `engine.assets.fetch()`) to the pack being ready. A pack dated before its publish is refused.

**Not built yet.** The fixtures reader (API-Football, football-data.org) does not exist, so the lint has nothing to read until it lands. Until then the session says the fixtures are unread; it never guesses them.

**Never.** Rank from memory. Make a post about an old match: a take that misses its window is archived. Read fixtures less often than weekly.

| Situation | Decision |
|---|---|
| Fixtures not read today | Stop; refresh them before ranking |
| A match has no published show | Leave it out for exact-show formats |
| Krish strikes a fixture | Drop it for the week |
| A take misses its window | Archive it; never post it later |
| Publish to pack is slow | Report the minutes; What-Works judges them |

**Lens.** `crew/match_clock/lens.md`.
