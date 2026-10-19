# Morning batch

Kind `daily`. Run `python3 growth.py sync` first when working interactively;
`python3 growth.py run morning --require-existing-history` includes that sync for a scheduled execution.
Read AGENTS.md, the current handover, live source state and EXECUTION-PLAN.md.

1. Verify the existing persistent project and private ledger are available.
2. Run `python3 growth.py run morning --require-existing-history`. Import an approved aggregate export
   with --observations only when its product, consent, provenance and window
   are verified. Missing collectors stay missing. Never inspect personal accounts.
3. Read the saved scorecard. On HOLD, keep the changed constraint and at most
   three next actions; do not regenerate the same bank of held marketing.
4. Prepare eligible brand work only if all product, rail, identity, channel
   and consent gates pass. Read at most three relevant public sources when
   research would change the current test; do no broad recurring research.
5. Check and save drafts locally. Record actual publication URLs only after
   a human action. Keep daily human work within twenty minutes.
6. End with `python3 growth.py cc morning --require-existing-history`. It
   journals a started attempt, pulls Control Center's directive, repeats the
   morning batch (a repeat keeps the same identities), reports with a digest
   readback, reads Krish's decisions and journals the end. A creative saved
   in step 5 that passed every gate is proposed behind the post wall with
   its exact words; a held one goes in as a hold with its code. Nothing is
   sent or posted. Without a bearer it exits with `missing_token`: say that
   reporting was unavailable; step 2 already saved the run locally.
7. Return a concise checkpoint, the attempt status and any changed dependency.
