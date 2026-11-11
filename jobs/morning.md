# Morning batch

Kind `daily`. Run `python3 growth.py sync` first when working interactively;
`python3 growth.py run morning --require-existing-history` includes that sync for a scheduled execution.
Read AGENTS.md, the current handover, live source state and EXECUTION-PLAN.md.

1. Verify the existing persistent project and private ledger are available.
2. Pull Krish's instruction before anything else: `python3 growth.py cc instruction`.
   It prints the instruction's id and a digest only, and keeps his words in the
   ignored `local/control-center/instruction.json`. When it says `act: true`,
   read that file and do what it asks first in this run, inside the walls: it
   never approves a send, post, spend, deletion or account change (AGENTS.md,
   "Krish's instruction" and rules 1 to 11), so anything at a wall becomes a
   proposal or a hold in the report. Record what you did with
   `python3 growth.py cc ack --state started --line "..."`, then `--state done`
   or `--state blocked`, each line in your own words: what you did, or why it is
   blocked and what would unblock it. Never copy his words into a tracked file,
   a commit, a pull request, a log, a report or an ack line. When it says held,
   do nothing on it: the report acks it received and blocked. Without a bearer
   it exits with `missing_token`; go on with the job.
3. Run `python3 growth.py run morning --require-existing-history`. Import an approved aggregate export
   with --observations only when its product, consent, provenance and window
   are verified. Missing collectors stay missing. Never inspect personal accounts.
4. Read the saved scorecard. On HOLD, keep the changed constraint and at most
   three next actions; do not regenerate the same bank of held marketing.
5. Prepare eligible brand work only if all product, rail, identity, channel
   and consent gates pass. Read at most three relevant public sources when
   research would change the current test; do no broad recurring research.
   Draft per COPY.md: set awareness and lead for the surface and pass the
   take test before writing; run edit passes A to E and score the rubric
   before saving, with the diagnosis in `why`.
   Apply [the listening standard](../docs/LISTENING-STANDARD.md) to source audio and the exact destination edition. Missing full-length listening evidence stays a creative-review hold; an audition is not a public-release approval.
6. Check and save drafts locally. Record actual publication URLs only after
   a human action. Keep daily human work within twenty minutes.
7. End with `python3 growth.py cc morning --require-existing-history`. It
   journals a started attempt, pulls Control Center's directive, repeats the
   morning batch (a repeat keeps the same identities), reports (with the
   instruction's acks and the engine's state, protocol 1.20.0) with a digest
   readback, reads Krish's decisions and journals the end. A creative saved
   in step 6 that passed every gate is proposed behind the post wall with
   its exact words; a held one goes in as a hold with its code. Nothing is
   sent or posted. Without a bearer it exits with `missing_token`: say that
   reporting was unavailable; step 3 already saved the run locally.
8. Return a concise checkpoint, the attempt status and any changed dependency.
