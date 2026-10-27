# Morning batch

Kind `daily`, 06:15 London. The v2 loop (docs/ENGINE-V2.md): the engine reads, checks
and prepares; Krish answers in Control Center and posts by hand in Buffer (ruling 3).
Run `python3 growth.py sync` first when working interactively; `python3 growth.py run morning
--require-existing-history` includes it for a scheduled run. Read
AGENTS.md, the newest HANDOVER-*.md and docs/ENGINE.md first; `python3 growth.py
session pack --kind orchestrator --check` is the whole reading list, 36 KB or less.

1. Verify the existing persistent project and private ledger are available. Never
   start a fresh ledger (`--require-existing-history`).
2. `python3 growth.py run morning --require-existing-history`. Import an approved
   aggregate export with `--observations` only when its product, consent,
   provenance and window are verified. Missing collectors stay missing. Never
   inspect personal accounts.
3. `python3 growth.py actions`. It lists Krish's actions today (his answers first,
   then the posts he approved and has not made, then at most three one-off setup
   steps) and the engine's own to-do. Do the engine's to-do in this run, in order:
   - **fixtures:** `python3 growth.py fixtures fetch`, or save Control Center's
     football-data reply and `python3 growth.py fixtures import FILE`. Never rank
     or time a take from memory (crew/match_clock).
   - **receipts:** read Buffer's posts on the Full Time allowlist only (read-only,
     `growth.py buffer query` then the Buffer connector's list_posts), then
     `python3 growth.py buffer receipts --posts FILE --pack FILE --channels FILE --record`.
     That closes each approved G2 whose kept items are all posted.
   - **north-star-line:** a scheduled run keeps the git tree clean, so it reports
     this one; the next interactive session updates the state line in NOW.md for
     this week from the measured number, or U4 if unmeasured. Only Krish changes
     the North Star itself.
4. On a matchday with a newly published edition and a format in play in the signed
   spec, prepare that day's pack: the crew cards in play, `growth.py pack check`,
   then `growth.py pack propose --spec local/specs/<week>.signed.json --queue`.
   Draft per COPY.md (take test, passes A to E, rubric with the diagnosis in
   `why`) and apply [the listening standard](../docs/LISTENING-STANDARD.md). Build
   nothing mid-run: a missing part is a hold with its code, not new code.
5. Keep Krish's day within twenty minutes. The actions list says when it is over;
   then ask fewer things, never more.
6. End with `python3 growth.py cc morning --require-existing-history`. It journals
   the attempt, pulls Control Center's directive, repeats the morning batch, reports
   with a digest readback (his actions travel as activity lines), reads his
   decisions, settles any G1 or G2 he answered and journals the end. One ask of each
   kind at a time; nothing is sent, posted or spent. Without a bearer it exits with
   `missing_token`: say reporting was unavailable; step 2 saved the run locally.
7. Return a short checkpoint: the gate, Krish's actions today in his words, what the
   engine did from its to-do, and the report's attempt status.
