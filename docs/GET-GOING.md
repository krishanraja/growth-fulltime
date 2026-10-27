# Get going

When Krish opens this repository and says "Get going", this is the work. AGENTS.md says how to use it; this file says what to do. Written 2026-10-19 by Control Center, from this engine's first live reports.

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

Read AGENTS.md first and follow it (it records Krish's rulings of 2026-10-19), then docs/NORTH_STAR.md, docs/CONTROL-CENTER-BRIEF.md and docs/control-center/ENGINE-PROTOCOL.md (protocol 1.1.0). Before you start, say which part of the North Star this work moves.

Where things stand (2026-10-19): this engine runs the Control Center loop live. Every day at 05:10 UTC Control Center writes this engine a directive and wakes `.github/workflows/control-center.yml` (`python3 growth.py cc dispatch`) with a `cc-growth-directive` repository_dispatch. The first live run on 2026-10-19 succeeded: it journaled its attempt, read the directive, sent a report, read it back by digest and read Krish's decisions. Control Center now speaks protocol 1.1.0: send `schema_version: "1.1.0"`, and read `stage`, `amended`, `exact_payload`, `amount_usd` and `amended_sha256` from decisions.

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

Today's live report (2026-10-19) was `held`:
- Five `wall: strategy` asks wait on Krish's list: the release decision, and rulings D1, D2, D3 and D7.
- Two unwalled proposals: "Diagnose the thin rail from stored verdicts" and "Build the completion and return queries".
- Holds: RAIL (no match has 4 of 6 AI Pundits; the newest has 1 of 6), RELEASE (no release decision recorded in full-time docs/12-roadmap.md), CHANNEL (brand proof is private), CONSENT (D7 not in force), and D4 to D6 (they open only channels he excluded on 2026-10-17).
- Both objectives are missing: `attributed_new_completers` and `marketing_cash_gbp` (target 0).

## The build

- [x] **Step 0.** (Done 2026-10-27: the status line now records the live runs.) Correct the status line at the top of docs/CONTROL-CENTER-BRIEF.md: the first live run on 2026-10-19 succeeded, so it is no longer only tested against a local stand-in.
- [ ] **Step 0.5 (added 2026-10-22; folded into v2 phase 1 as the weekly `spend` proposal, stills before video).** Pick up briefs/2026-10-22-media-credits.md: propose about 10 Higgsfield pundit stills (about 30 credits) as a `stage: "plan"` behind `spend`, and confirm editions are publishing before any video. Generate nothing before his yes.
- [ ] **Step 1 (superseded for posts by the 27 October handcrafted ruling; the plan, check-in and amendment parts are v2 phase 1).** The autonomy loop above (plan, go-live, the go-live step, check-ins) on protocol 1.1.0, proved against the stand-in: an approved plan never goes live, an approved go-live goes live once with exactly its payload, an amended one goes live in his words, a declined check-in stops its plan. Then the creative review every go-live passes: the doctrine it was checked against, at least two alternatives made, and why this one wins, in its evidence. Krish has a low tolerance for poor creative output, so a weak go-live is held, not proposed.
- [ ] **Step 2 (v2 phase 0 records D1 and ORGANIC; the full-time decision-log heading is a handoff).** Act on his rulings. When he clears the release decision or D1, D2, D3 or D7 on his list, record it where the engine reads its rulings (`rulings.json`) and release the matching hold on the next run, with the decision as evidence. When he declines one, keep the hold and say so.
- [ ] **Step 3 (v2 phase 1: `engine/attribution.py` and `briefs/2026-10-27-share-attribution.md`).** Build `attributed_new_completers`: define the query (a shared take to a first finished show), its window and timezone, and implement it against what full-time exposes. Where the data is not there, name the exact gap.
- [ ] **Step 4 (v2 phase 1: handed to full-time as `briefs/2026-10-27-rail-supply.md`).** Diagnose the thin rail from stored verdicts and propose the fix.
- [ ] **Step 5 (v2 phase 1: `automations.json` now names the newest handover; the hosted copies still need updating to match).** Update the two hosted tasks so their prompts match `automations.json`, and make the workspace runs stop loudly when the token is missing (`local/control-center/token` or `CONTROL_CENTER_ENGINE_TOKEN`).

## The v2 build (approved 2026-10-27)

Ruling (Krish, 2026-10-27): "approved, do it all". The plan is [ENGINE-V2](ENGINE-V2.md). Each phase is done when its acceptance in that file is met with evidence, never when a session says so.

- [ ] **Phase 0.** Baseline, inventory, rulings and brand kit. Done so far (27 October): the Drive library tree, START-HERE and INDEX; the creative handoff moved into `06_Reference`; the Canva `Growth/Templates` folder; rulings recorded here and in `rulings.json`. Waiting on Krish: run the Cowork prompt (`briefs/2026-10-27-cowork-canva-brand-kit.md`), switch Full Time to handcrafted, create the handles, and let `scripts/baseline.py` read the Codex and Claude logs on his machine.
- [ ] **Phase 1.** Product briefs (share attribution, rail supply), the Control Center brief (Google Analytics, objectives, handcrafted), engine truth (protocol 1.1.0, RELEASE fix, ORGANIC gate), proof zero on the published editions, and the creative track from the Liverpool v8 listening. Done so far (27 October): the three briefs are written; protocol 1.1.0 with stages, amendments, one ask at a time and the capabilities check; the RELEASE and ORGANIC fixes; `engine/attribution.py` with its contract test; Krish's actions in every report. Waiting: Krish approves the briefs and listens to Liverpool v8; the social kit is approved and the take_clip renderer is built (`brand/social-kit/`); proof zero runs on Krish's machine with each edition's real audio.
- [ ] **Phase 2.** Spec, the crew, invariants, session packs, dispatch guard, the Librarian, the Buffer reader, the format locks and the six Canva templates. Done so far (27 October): the spec and compiler, eleven crew cards and lenses, the invariant registry (116 entries, 80 enforced by passing tests), session packs, the dispatch guard, the library rules with their sprawl tests, the read-only Buffer reader and receipts, the Match Clock's fixtures reader, and two independent review waves with every confirmed finding fixed. Waiting: the format locks and the Canva templates, both built from the approved social kit.
- [ ] **Phase 3.** Proof on real matches until the first format reaches three in a row.
- [ ] **Phase 4.** Live, per format, published by Krish in Buffer.

## Checks

`python3 growth.py --self-test`, the unit tests, `verify_repository`, the JSON checks.
