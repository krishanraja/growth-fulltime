# Get going

When Krish opens this repository and says "Get going", this is the work. AGENTS.md says how to use it; this file says what to do. Written 2026-10-19 by Control Center, from this engine's first live reports.

**Held (2026-10-29).** The engine is held by Control Center and by `activation.json` (Ruling, Krish, 2026-10-29: Not ready means a held activation state: no wake, no asks on his list, no growth council move, and the bearer stays valid). Control Center has not woken it since 29 October. While it is held, a "Get going" session prepares nothing for his list: every report carries one NOT_READY hold and no proposals, so a spend plan or a ruling ask would be dropped unseen. Step 2 (acting on his rulings), the spending in Step 6 and Step 7 wait for his release, and so does putting anything "on his list in Control Center" in item 2 below. Work that asks nothing of him (Steps 1, 3, 4 and 5) can still go ahead, proved against the stand-in. Only Krish releases the engine: on Growth > Engines in Control Center, and in `activation.json` through an interactive session that records his words and the date there and in `CHANGES.md`.

## Before release

When Krish releases the engine, and before its first run after release:

1. Re-copy `docs/control-center/` from Control Center main (`docs/app/growth/ENGINE-PROTOCOL.md` and the two schemas beside it), at a named commit, as the copies at 212379e1 and 36df34bc were. The copy here is 1.22.0; Control Center served 1.26.0 on 2026-11-14.
2. Read in that copy every version after 1.22.0 that a venture engine receives, and first `ai_answers_detail`: AEO-Engine's kits for Full Time reach Krish through this engine. Adopt only the fields this engine uses (protocol, "Versions").
3. Switch the daily credits task back on (docs/CREDITS-SESSION.md); never create a second one.

## What "Get going" does

For creative-continuity work, first follow the
[creative system](../creative-system/README.md) and its private current handoff.
A captured standards baseline does not approve a video or reopen generation.

1. Read AGENTS.md to the end (it records Krish's rulings), then docs/NORTH_STAR.md. Say in one line which part of the North Star this run moves.
2. Do the first unticked step of **The build** below, completely: to its checks and one pull request. Tick it in that same pull request, with a one-line note of what it changed in the live report. If a step is blocked on something only Krish can do (a secret, a ruling), say exactly what in the pull request and on his list in Control Center, tick nothing, and go on to the next step.
3. Stop after one step, unless it took under an hour and the next step needs nothing from him.
4. When every step is ticked, "Get going" means: read the engine's latest live report and today's directive, find what most limits tomorrow's report (an unknown objective, a held proposal, a weak go-live, a check-in he declined), fix that, and add it here as a ticked step.

Never ask Krish to paste a prompt or repeat a brief: everything needed is in this repository.

## The brief

Read AGENTS.md first and follow it (it records Krish's rulings), then docs/NORTH_STAR.md, docs/CONTROL-CENTER-BRIEF.md and docs/control-center/ENGINE-PROTOCOL.md (Control Center's protocol, copied here at 1.22.0, from Control Center at 36df34bc; Control Center served 1.26.0 on 2026-11-14). Before you start, say which part of the North Star this work moves.

Where things stand (2026-11-12): the Control Center loop is built and ran live from 19 to 29 October. On each of those days Control Center wrote this engine a directive at 05:10 UTC and woke `.github/workflows/control-center.yml` (`python3 growth.py cc dispatch`) with a `cc-growth-directive` repository_dispatch; each run journaled its attempt, read the directive, sent a report, read it back by digest and read Krish's decisions. Since Krish held the engine on 29 October, Control Center does not wake it. The engine sends `schema_version: "1.0.0"`, raised to `1.16.0` when a run spent credits and to `1.20.0` when the directive asks for the engine's state. For the loop below, send `schema_version: "1.1.0"` or later with a proposal's `stage`, and read `stage`, `amended`, `exact_payload`, `amount_usd` and `amended_sha256` from decisions.

The job now is to make the daily report worth Krish's morning. Every run should leave Control Center with:

1. Every objective measured honestly: a real value with its window and timezone, or `value: null` with a specific reason. Never a zero you did not measure.
2. One best recommendation plus a few alternatives as `proposals[]` (at most 10). Each one names its `objective_key`, says why in plain words, links its evidence (https only), says its `kind` (advice, prepared or autonomous), names the event that proves it done in `close_condition`, and has an `expires_at`. Control Center picks tomorrow's next action by rule: first what Krish approved and you have not done, then a repair if the engine is failing, then the unwalled proposal on the objective with the widest gap. So make the move you most want done unwalled where you can, and aim it at the widest gap.
3. Anything behind a wall (`wall`: send, post, spend or strategy) complete enough that his yes is the whole decision: the exact words in `exact_payload`, the channel, `amount_usd` for spend, and the evidence. It lands on his one list in Control Center, where Clear approves exactly that payload, "Change it first" lets him approve his own version, and Purge declines it. Keep a proposal's `proposal_id` stable across runs: if the words change, the new `payload_sha256` sends it back to him, and his earlier yes and any version of his no longer apply.
4. `events[]` for what closed, with evidence, naming the proposal_id and the event in its close_condition.
5. `holds[]` for anything set aside, each with a reason code and one plain sentence.

Acting on his decisions: this engine is autonomous (AGENTS.md, "Autonomy"), and autonomy is given where it is deserved. Build the whole loop:
- **Plan** (`stage: "plan"`, behind `strategy`, the plan in `exact_payload`): what the engine is going to do, aimed at the objective with the widest gap. Wait for his yes.
- **Go-live** (`stage: "go_live"`, `parent_proposal_id` = the plan, behind `send`, `post` or `spend`): once the plan is approved, build everything up to go-live and propose it for his review, with the exact words, the assets and the amount, and the quality review in its evidence. Nothing goes out yet.
- **The go-live step**: when a decision approves a go-live whose `payload_sha256` matches, publish, send or spend exactly that, once, through the channel it names, then report the closing event with evidence. When `amended` is true, recompute `amended_sha256` (SHA-256 of canonical JSON of exactly `{"amount_usd": ..., "exact_payload": ...}`) and use his version, never yours. Purge means stop. Never go live from an approved plan, an interactive session or a prompt. If a channel needs a credential the runner lacks, report a hold naming the exact secret Krish must add; never ask for a value.
- **Check-ins** (`stage: "check_in"`, behind `strategy`, naming the plan, with how it is going and what comes next in `exact_payload`) at the cadence AGENTS.md sets. His yes keeps the plan going, his amendment redirects it, his no stops it for good.
- **The quality bar** in AGENTS.md holds before any go-live is proposed. Hold work below it, with its reason. Record each of his amendments and declines where the next draft reads it.

Rules that do not move:
- This repository is public. Synthetic fixtures only. No live people, drafts, business figures, tokens or production receipts in code, tests, logs, artifacts or pull requests. Public Actions logs carry counts and codes only.
- Never print or commit `CONTROL_CENTER_ENGINE_TOKEN`. This task has no token and needs none: prove every change against the repository's local protocol stand-in (the fake server in `tests/test_control_center.py`). The only live writes are the scheduled Actions run and the workspace runs Krish starts.
- Never retry a write blindly. After a timeout or a 409, read back first.
- Plain English, no em dashes.

Finish with the checks below passing and one pull request whose description says, in plain words, what tomorrow's live report will say that today's did not.

### This engine

The last live report, the dispatch of 2026-10-29 (sent before the hold landed), had status `held` (the rail gate) at `schema_version: "1.0.0"`:
- Five `wall: strategy` proposals: the release decision, and rulings D1, D2, D3 and D7. They never reach his list now: a held engine's asks are left off it.
- Two unwalled proposals: "Diagnose the thin rail from stored verdicts" and "Build the completion and return queries".
- Holds: RAIL (no match has 4 of 6 AI Pundits; the newest has 1 of 6), RELEASE (no release decision recorded in full-time docs/12-roadmap.md), CHANNEL (brand proof is private), CONSENT (D7 not in force), and D4 to D6 (they open only channels he excluded on 2026-10-17).
- Both objectives are missing: `attributed_new_completers` and `marketing_cash_gbp` (target 0).

The next report, on the first run after he releases it, is the first at 1.20.0, with this engine's priorities, obsessions and next steps.

## The build

- [x] **Step 0.** Correct the status line at the top of docs/CONTROL-CENTER-BRIEF.md: the first live run on 2026-10-19 succeeded, so it is no longer only tested against a local stand-in. *Found done 2026-11-11:* the status line already reads "adopted"; ticked so the next step the report names is a real one.
- [ ] **Step 1.** The autonomy loop above (plan, go-live, the go-live step, check-ins), proved against the stand-in: an approved plan never goes live, an approved go-live goes live once with exactly its payload, an amended one goes live in his words, a declined check-in stops its plan. Its proposals carry `stage` and `parent_proposal_id`, so those reports go out at protocol 1.1.0 or later. Then the creative review every go-live passes: the doctrine it was checked against, at least two alternatives made, and why this one wins, in its evidence. Krish has a low tolerance for poor creative output, so a weak go-live is held, not proposed.
- [ ] **Step 2 (waits while held).** Act on his rulings. When he clears the release decision or D1, D2, D3 or D7 on his list, record it where the engine reads its rulings (`rulings.json`) and release the matching hold on the next run, with the decision as evidence. When he declines one, keep the hold and say so.
- [ ] **Step 3.** Build `attributed_new_completers`: define the query (a shared take to a first finished show), its window and timezone, and implement it against what full-time exposes. Where the data is not there, name the exact gap.
- [ ] **Step 4.** Diagnose the thin rail from stored verdicts and propose the fix.
- [ ] **Step 5.** Update the two hosted tasks so their prompts match `automations.json`, and make the workspace runs stop loudly when the token is missing (`local/control-center/token` or `CONTROL_CENTER_ENGINE_TOKEN`).
- [x] **Step 6 (added 2026-10-29; waits while held).** Prepaid credits, protocol 1.16.0 (docs/CONTROL-CENTER-BRIEF.md, "Prepaid credits"). Read the directive's optional `credits` block; once Krish releases the engine, spend up to each pool's `remaining_for_you` on work that moves the objectives with no proposal (stills before video; nothing published, posted or sent without its own approval; never past `remaining_for_you`, never a top-up or new money), and report each spend in `credits_spent[]` at `schema_version: "1.16.0"`, proved against the stand-in. A missing `credits` block means unknown: spend nothing. *Built 2026-10-29:* `engine/credits.py` reads `credits` into the report's activity (absent: unknown, nothing spent), its `Guard` refuses past `remaining_for_you` and while held, and `reporting.build` carries `credits_spent` at 1.16.0 only when a run spent, proved against the stand-in (`tests/test_control_center.py`, `CreditsTests`). The spending itself is the daily scheduled session in [CREDITS-SESSION.md](CREDITS-SESSION.md), which reserves and settles each spend through Control Center; it spends nothing while the engine is held.
- [ ] **Step 7 (added 2026-10-30; waits while held and for D1).** The channel tasks (ai-harness `contract/channel-tasks.md`), said for Full Time's own outcome: a fan shares an AI Pundit's take and a new listener arrives through it. Dormant until Krish releases the hold in `activation.json` and clears D1 in `rulings.json`. When live, each task accomplishes this here:
  - idea-bank: match moments where two Pundits genuinely disagree, the "Same match, two minds" shape, from real Pundit lines only, never invented ones;
  - reel-script: 5 hooks per match-morning clip whose payoff is the second Pundit's answer, judged on shares per view;
  - caption-set: 5 captions that make a fan of either club want to send it to a rival fan, carrying the share link;
  - trend-scan: the week's fixtures and talking points fans are already arguing about, dated, so a take lands while the argument is live;
  - platform-truth and profile-audit: for the branded YouTube format first, the first channel step after release, then the others D1 unlocks;
  - channel-plan: the fixture calendar worked back from the ladder (5 for the week of 26 October, 16 for 2 November, 30 for 9 November, 49 for 16 November).

  The weekly loop opens with `X of Y, U-n, short by Z`, splits the gap across the unlocked channels, and reviews each take at 24 hours, 72 hours and 7 days. Nothing runs, drafts or proposes while held.
- [x] **Step 8 (added 2026-11-11).** Krish's instruction and the engine's state, protocol 1.20.0 (docs/CONTROL-CENTER-BRIEF.md, "Krish's instruction and the engine's state"). Krish, 2026-11-11: "Ensure the priorities, obsessions, and next steps for all the growth engines are feeding live to this dashboard ... Get building". *Built 2026-11-11:* `engine/engine_state.py` reads `krish_instruction`, puts its id first in the report's activity, acks it (received on the clean runner; received then blocked while held; received, started, done or blocked in the workspace from `growth.py cc ack`), and fills `priorities`, `obsessions` and `next_steps` from this repository's files, only when the directive says `features.engine_state`. The morning job pulls it first (`growth.py cc instruction`). A dispatch's `run_id` is unique per GitHub wake. Proved against the stand-in (`tests/test_control_center.py`, `InstructionTests`).

## Checks

`python3 growth.py --self-test`, the unit tests, `verify_repository`, the JSON checks.
