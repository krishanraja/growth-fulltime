# Weekly review

Kind `report`, Monday 08:00 London. Run `python3 growth.py sync` first when working interactively; `python3 growth.py run weekly
--require-existing-history` includes it for a scheduled run. Read AGENTS.md, the newest
HANDOVER-*.md, docs/ENGINE.md and MEASUREMENT.md.

1. Verify persistent private history; run `python3 growth.py run weekly --require-existing-history`.
2. Read a whole seven-day window, its actual source dates and mature cohorts.
   Never add daily unique counts or call switch-intent an actual comparison.
3. **What works** (crew/what_works, a fresh session that made nothing): the learning
   register from Krish's verdicts, read-only Buffer analytics on the Full Time
   allowlist and Control Center's ga4_landings. "Confirmed" needs pre-registration,
   no overlapping test, two matchweeks, 20 events per arm and |z| of 2 or more;
   anything less is directional. Underpowered tests stay inconclusive. Read results
   through COPY.md's test record and [the listening standard](../docs/LISTENING-STANDARD.md).
4. **This week's plan (G1):** `python3 growth.py fixtures fetch` (or import), rank
   the fixtures, write the spec from the signed template and `learnings_applied`,
   then `python3 growth.py spec check FILE` and
   `python3 growth.py spec propose FILE --expires-at <Sunday 23:59 London> --queue`.
   The Monday loop carries it as the one plan ask. A credits ask (`spend`) follows
   only after G1 is signed, never beside it.
5. **Library:** reconcile Growth Build (`python3 growth.py library reconcile` on a
   fresh listing with its read_at). Files outside the tree, orphans, duplicates and
   misnamed files must be zero, or a LIBRARY hold leads the report. Refresh
   START-HERE's "This week" links. Back up the history ledger and `standards
   export` to 06_Reference/backups/ as a verified bundle.
6. Make one constraint call and one keep/change/stop recommendation. The kill list
   and double-down items are prepared locally; human decision fields are never
   written. Keep Krish's weekly work within thirty minutes.
7. End with `python3 growth.py cc weekly --require-existing-history`. It repeats step
   1's command inside the Control Center loop, reports with a digest readback (the
   weekly LIBRARY check and his actions included) and reads his decisions. The kill
   list goes to Krish as strategy proposals, one at a time. `python3 growth.py
   export` remains a private local backup, not the hand-off. Do no implementation in
   Control Center or full-time; identify changed external dependencies in the
   existing briefs; never turn a ready flag or an approval into permission to promote.
