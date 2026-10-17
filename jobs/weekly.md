# Weekly review

Kind `report`. Run `python3 growth.py sync` first when working interactively;
`python3 growth.py run weekly --require-existing-history` includes it for a scheduled execution.
Read AGENTS.md, the current handover, EXECUTION-PLAN.md and MEASUREMENT.md.

1. Verify persistent private history; run `python3 growth.py run weekly --require-existing-history`.
2. Read a whole seven-day window, its actual source dates and mature cohorts.
   Never add daily unique counts or call switch-intent an actual comparison.
3. Review experiment stopping rules, negative results, observed usage and human
   minutes. Underpowered tests remain inconclusive. Do not infer publication.
4. Make one constraint call and one keep/change/stop recommendation. Native
   review findings, kill_list and double_down are prepared locally; human
   decision fields are never written. Keep human work within thirty minutes.
5. Run `python3 growth.py export` for the private handoff bundle. Identify
   changed external dependencies in the existing briefs. Do no work in Control
   Centre or full-time and do not turn a ready flag into permission to promote.
