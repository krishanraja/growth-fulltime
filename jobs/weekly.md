# Weekly review

Kind `report`. Run `python3 growth.py sync` first when working interactively;
`python3 growth.py run weekly --require-existing-history` includes it for a scheduled execution.
Read AGENTS.md, the current handover, EXECUTION-PLAN.md and MEASUREMENT.md.

1. Verify persistent private history; run `python3 growth.py run weekly --require-existing-history`.
2. Read a whole seven-day window, its actual source dates and mature cohorts.
   Never add daily unique counts or call switch-intent an actual comparison.
3. Review experiment stopping rules, negative results, observed usage and human
   minutes. Underpowered tests remain inconclusive. Do not infer publication.
   Read results through COPY.md's test record: which take, lead and proof
   travelled, and the weakest persuasion link in what did not.
   Apply [the listening standard](../docs/LISTENING-STANDARD.md): separate source-performance problems from hook or distribution problems, and retain the human listening verdict with the exact audio version.
4. Make one constraint call and one keep/change/stop recommendation. Native
   review findings, kill_list and double_down are prepared locally; human
   decision fields are never written. Keep human work within thirty minutes.
5. End with `python3 growth.py cc weekly --require-existing-history`. It
   repeats step 1's command inside the Control Center loop (a repeat keeps
   the same identities), reports with a digest readback and reads Krish's
   decisions. The kill list goes to Krish as strategy proposals and the
   double-down items as actions. `python3 growth.py export` remains a private local backup, not the
   hand-off. Identify changed external dependencies in the existing briefs. Do
   no implementation in Control Center or full-time and do not turn a ready
   flag or an approval into permission to promote.
