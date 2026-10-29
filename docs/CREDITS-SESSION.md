# The daily credits session

This file is the playbook for one scheduled Claude session a day. That session spends Full Time's share of the prepaid credit pools (protocol 1.16.0). The rule comes from [CONTROL-CENTER-BRIEF.md](CONTROL-CENTER-BRIEF.md), "Prepaid credits".

Ruling (Krish, 2026-10-29): a growth engine may spend up to its placement share of a tool's prepaid credits each cycle with no per-batch approval, and reports what it made. Krish chose scheduled sessions to do the spending: the GitHub runner holds no generator keys, so this session spends the share through the tools' own connectors.

This is not one of the two consolidated jobs in `jobs/` and adds no row to `automations.json`. It is the only route by which this engine spends prepaid credits. The runner (`growth.py cc`) only reads the share and reports it (`engine/credits.py`).

## Connectors

- Control Center
- Higgsfield
- Runway
- 21st Dev

## Every run

1. **Read the share.** Call `get_engine_credits` with `engine: "fulltime"`.
   - If it says `held: true`, stop and end with "Held: nothing spent."
   - If `credits` is null (unknown), stop and end with "Credits unknown: nothing spent."
   - Full Time is held today, so the run stops here until Krish releases it.
2. **Set today's pace for each pool.** The pace is `remaining_for_you` divided by `days_left`. In the last three days before `use_by`, take everything that is left.
3. **Make work that moves Full Time's objectives.** Only concepts that already exist in this repository (`creative-system/`, the drafts the morning batch saved), written to [COPY.md](../COPY.md) and held to every rule in AGENTS.md:
   - Full Time's own artwork only;
   - no football footage;
   - no player likenesses;
   - no imitation of a living pundit;
   - AI disclosed.

   Which tool does what:
   - **Higgsfield:** stills first (a GPT Image still is about 2.75 credits). Motion (a Seedance clip, about 210) only for a concept whose still earned it.
   - **Runway:** clips for a concept whose still earned motion.
   - **21st Dev:** interface components for fulltime.fm drafts, only after the design is decided.
4. **Reserve, make, settle.** Before every generation, call `reserve_credit_spend` with:
   - `engine: "fulltime"`;
   - the pool;
   - the expected cost (from the tool's own quote, or `unit_costs`);
   - `asset` in words;
   - the objective key.

   If it refuses (`over_share`, `held`, `unknown`, `no_pool`, `open_reservation`), make nothing. After the generation, call `settle_credit_spend` with the provider's actual cost and its job ids as the receipt. Pass `0` if it failed or charged nothing.
5. **Leave the work for review.** Keep everything made in the tool's own library or in the ignored `local/` of the persistent workspace. Nothing goes on any account.
6. **End with one line:** what was made, credits spent per pool, and what is left.

## The walls

The share only guards how much is spent. These never move:
- Never past `remaining_for_you`.
- Never a top-up, a plan change or new money.
- Nothing made is published, posted or sent without its own approval: the go-live step in AGENTS.md.

The session records its spend through `settle_credit_spend` only. The runner's report never repeats it in `credits_spent`, because Control Center already subtracts the session's spends from the share.
