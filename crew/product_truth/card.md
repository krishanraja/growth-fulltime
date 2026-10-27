# Product Truth

Crew card (docs/ENGINE-V2.md, section 3), loaded for every pack and every review.

**Job.** Every claim and every link in a pack points at something live in the product now: a published AI Pundit show, a real match and score, the live site.

**Runner.** The CLI (`growth.py sync`, `growth.py pack check`). No model, no tokens.

**Owns.**
- The synced product state (`state/fulltime.json`) and its STOP flag.
- The live rail at pack time: `pack check` reads it with `growth.read_rail()`. Offline, the synced rail is used and Today counts as not live, so a match ad fails closed.
- The published-edition check before any media is used.

**Lint before acting: `growth.freshness()`.** The pack names the full-time sha of the last sync, the rules have not changed (no STOP), and no canon file moved since. `engine.runner.run()` also refuses a sync older than 26 hours. A rail that was not read means nothing is promoted blind.

**Measured check after acting: `engine.assets.fetch()`.** The public endpoint `/api/public/drops/{drop}/variants/{pundit}` must say published, for the same drop and AI Pundit, before audio or a cover is used. At pack time `engine.pack.check()` holds each link to a show on the live rail; repeat the check at review time, before G2.

**Never.** Promote a match from memory or a chat summary. Treat a local branch, a 200 or a cached copy as product truth. Claim a show exists that the rail does not list.

| Situation | Decision |
|---|---|
| Sync older than 26 hours | Stop; run `growth.py sync` |
| STOP: Full Time's rules changed | Stop; a person updates growth.py |
| The linked show is not on the rail | Refuse the item (ruling 1, per take) |
| A whole-match claim on a match under 4 of 6 | Refuse it |
| Today carries no published show | Hold every match ad (ruling 11) |
| The endpoint does not verify the edition | Refuse the media; render nothing |
| Working offline | Synced rail only; match ads fail closed |

**Lens.** `crew/product_truth/lens.md`.
