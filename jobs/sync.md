# Job: sync with full-time and the rail (every day, and first in every other job)

No pack. This job keeps the engine across what the full-time repository and
the live product are doing. Every other job starts with the same command.

1. `git pull --ff-only` (this repository).
2. `python3 growth.py sync`. It reads `krishanraja/full-time` on `main` and
   fulltime.fm, and writes `local/state/fulltime.json` and
   `local/state/FULLTIME-NOW.md`:
   - the commit it read (`fulltime_sha`);
   - **the rail**: every match Today can show, its score, and which of the
     six AI Pundits made a show for it;
   - **the push gate**: OPEN when a match has at least 4 of 6, HOLD when
     none does;
   - the rulings the playbook needs, and whether full-time's decision log
     records each one;
   - commits since the last sync, and open pull requests (work in flight);
   - the canon, in the order full-time's docs index routes a marketing
     agent, and which canon files changed since the last sync;
   - the newest headings of the decision log;
   - the latest Reporter feed items;
   - whether the rules sections the checker was written from are unchanged.
3. Read `local/state/FULLTIME-NOW.md`. If canon changed, read the changed
   files (`python3 growth.py canon --full`). In your final message, say in
   one or two plain lines what changed and what it means for growth, for
   example:
   - "the rail on Forest v Arsenal is 5 of 6: the gate is open, today's pack
     pushes that match";
   - "full-time merged a share button on Today: tracked shares become
     countable, the product job should read it";
   - "the decision log records D1: fan channels open once this repository
     marks it approved".
4. If the sync printed **STOP**, Full Time's rules changed. Name the changed
   sections and say a person must update `RULES` and `RULES_BASIS` in
   `growth.py` before any pack can pass. Don't change `growth.py` yourself in
   a scheduled run.

Final message: the full-time commit, the push gate and why, what changed,
and anything a later job today must do differently.
