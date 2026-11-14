---
repo: krishanraja/growth-fulltime
product: Full Time growth engine
as_of: 2026-11-13
head: 9ecd7a8
lifecycle: building
production_url: none
state_doc: README.md
history_log: docs/history/LOG.md
truth_files: [docs/NORTH_STAR.md]
authority_order: [docs/NORTH_STAR.md, README.md]
steward: https://github.com/krishanraja/ai-harness/blob/main/docs/steward/RUNBOOK.md
---

# Full Time growth engine: where it is right now

## What it is

Full Time's growth engine: it drafts the moves that bring football fans to Full Time, and nothing it makes sends or posts on its own.

## Who it is for and why it matters for Mindmake

Football fans who become Full Time's returning listeners. It proves Mindmake can grow a product with drafted, approved moves and no paid acquisition.

## Where it is right now (as of 2026-11-13)

<!-- north-star-state {"week_of": "2026-11-09", "week_target": 30, "current": null, "current_as_of": "2026-11-12", "current_source": "Not measured: Full Time share links are not yet joined to new listens", "urgency": 4, "urgency_reason": "current number unmeasured"} --> **North Star number: U4, unmeasured.** New listeners this week who arrived through a fan's shared link or clip: unknown, against 30 this week, on the way to 1,250 by 25 January 2027. Nothing measures it yet: Full Time's share links are not joined to new listens (MEASUREMENT.md, and Step 3 of docs/GET-GOING.md). To measure it, full-time must export one weekly aggregate, metric `attributed_new_completers` (MEASUREMENT.md, "The North Star number", lists its exact fields): new identities whose first completed show came through a shared link, joined on the link's `utm_*` tags.

Lifecycle: building, and held. Krish held the engine on 29 October 2026 (Ruling, Krish, 2026-10-29: Not ready means a held activation state): Control Center's registry says held and so does the tracked `activation.json`. Control Center has not woken it since. Its last report there is the 29 October dispatch, sent before the hold landed, and no workspace run has ever reached Control Center: all 12 reports it holds are dispatches, from 19 to 29 October. So Control Center shows this file's "Where it is right now" and "What is next" as the engine's state of play.

- Full Time's AI answers are AEO-Engine's, the one AI-answers specialist (Ruling, Krish, 2026-11-12): AEO already researches Full Time every fortnight, and the runner reads its standing from the directive into one line (protocol 1.22.0, engine/ai_answers.py). The protocol copy in docs/control-center/ is Control Center's at 36df34bc (protocol 1.22.0). (2026-11-13)
- The protocol copy in docs/control-center/ is Control Center's at 212379e1 (1.21.0, the schemas unchanged): its voice_check row lists the 16 channels Control Center accepts, and it says a number objective's target comes from the repository's north-star block; Control Center reads no number objective for this engine (only Legibility, Mindmake, Heartside and Make Your Mind Up have one), so its registered objectives keep their registry targets. The code still speaks 1.20.0 and the engine is still held. (2026-11-12)
- The docs match the code and the live state, the engine's obsessions quote only Krish's own words, a repeated ack with a new line now updates Control Center (protocol 1.21.0), and closeout notes fold into NOW.md on every merge to main (engine/closeout.py). (2026-11-12)
- The code speaks Control Center protocol 1.20.0: a run reads Krish's instruction, acks it by id and reports its priorities, obsessions and next steps (`engine/engine_state.py`). None of it has reached Control Center, since no run has happened after it merged, and Krish has given this engine no instruction. The protocol copy in `docs/control-center/` is 1.21.0. (2026-11-12)
- The promotion rail is on HOLD: the four matches on fulltime.fm each have one AI Pundit of six, the newest from 19 October (`state/FULLTIME-NOW.md`, read hourly). A push needs a match with four. (2026-11-12)
- Rulings D1 to D7 are all pending, and full-time's `docs/12-roadmap.md` records no release decision (`rulings.json`, `state/FULLTIME-NOW.md`). (2026-11-12)
- The credits share is read and guarded (`engine/credits.py`) but nothing spends it: the engine is held. The daily credits task in docs/CREDITS-SESSION.md exists on claude.ai and is switched off while held (since 2026-11-14); it is switched back on at release, never recreated. (2026-11-14)
- Creative: Liverpool v8 is a listening candidate Krish has not judged, and the Arsenal video is still rejected; neither ad is ready to post. The private package is in the Growth Build Drive folder named in HANDOVER-2026-10-27-CREATIVES.md. (2026-10-27)

## What changed recently

- 2026-11-12 Krish, 2026-11-12: "make sure everything's a cohesive system and that the project documentation is 100% up to date with absolutely nothing old or misleading left in there".
- 2026-11-12 Krish asked whether the documentation was up to date, every word. It was not: NOW.md had stopped at 27 October with six notes waiting and no fold to write them in, the brief still said the engine was switched on with dispatch on, the third obsession was a summary of his words rather than his words, and the hourly sync's commits would have marked NOW.md unreconciled two days after every update. Each is fixed, and the sync now commits as chore(heartbeat).
- 2026-11-11 Protocol 1.20.0 (PR 19). Ruling (Krish, 2026-11-11): every growth engine's priorities, obsessions, next steps and outstanding items feed live across Control Centre, and he instructs each engine with his next best action. The morning job now pulls his instruction first (`growth.py cc instruction`) and records what it did (`growth.py cc ack`); his words stay in ignored `local/`, and a dispatch's run id is unique per wake.
- 2026-11-10 Claude sessions here show Krish a ChatGPT sign-in link and code whenever Codex is signed out (`.claude/hooks/codex-login.sh`, commit 05d8b8b), so Codex runs on his subscription, never an API key.
- 2026-10-30 The seven channel tasks joined the plan as Step 7 of docs/GET-GOING.md (PR 18), dormant while the engine is held and until D1 clears. Krish asked for each saved Instagram growth prompt to be its own task, defined once in ai-harness `contract/channel-tasks.md`.
- 2026-10-29 The credits step was built (PR 16). Krish chose "Scheduled sessions" to spend the share: the runner only reads it and refuses any spend past `remaining_for_you` or while held, and a report carries `credits_spent` at 1.16.0 only when a run spent.
- 2026-10-29 Protocol 1.16.0, prepaid credits (PR 15). Ruling (Krish, 2026-10-29): a growth engine may spend up to its share of credits already paid for, with no per-batch approval. Full Time's shares are about 600 Higgsfield, 450 Runway and 50 21st Dev credits a month (docs/CONTROL-CENTER-BRIEF.md).
- 2026-10-29 Held until Krish releases it (PR 14). Full Time is a few weeks from being in motion, so each report carries no proposals and one NOT_READY hold naming the readiness gates. It stopped five daily asks reaching his list for an engine that is not ready.
- 2026-10-27: archived the full private two-ad session and creative baseline to
  Drive, verified local rebuild and Drive file identity/size readback, and set a
  portable start-here path. The Liverpool ending, accents and TV music remain
  subject to owner listening. See [current handover](HANDOVER-2026-10-27-CREATIVES.md).
- 2026-10-26: implemented versioned creative standards, isolated composition,
  scope checks, improvement/regression gates, exact owner promotion and verified
  private bundle recovery. See [handover](HANDOVER-2026-10-26.md).
- 2026-10-23 **The North Star now has a number, a weekly ladder and an urgency rating.** Ruling (Krish, 2026-10-23): every repository chases one aggressive number on a weekly ladder, and urgency U1 to U5 sets how hard it pushes. The number is in `docs/NORTH_STAR.md`; contract: ai-harness `contract/north-star-metric.md`.

## What is next and what is waiting on Krish

- Next (2026-11-13): When Krish releases this engine, read Full Time's AI answers on its tile and decide with him whether to ask AEO to track more questions.
- Waiting on Krish (2026-11-12): the release decision and D1, each recorded in full-time's decision log, and a full listen to Liverpool v8 (HANDOVER-2026-10-27-CREATIVES.md).
- North Star check (2026-11-13): holds.

## Read next

- `docs/NORTH_STAR.md`: the North Star, its number and its weekly ladder.
- `README.md`: what this repository is and how it runs.
- `docs/GET-GOING.md`: the build, step by step, and which steps wait while held.
- `docs/CONTROL-CENTER-BRIEF.md`: how this engine reports to Control Center.
- `docs/history/LOG.md`: what this file used to say, verbatim.

## Do not trust

Do not treat a successful render, technical media pass or historical review-ready
receipt as current creative approval. Do not read the prior listener count as a
fresh attribution measurement, or an empty local reporting export as delivery.
Do not read the 7 proposals in Control Center's last report (29 October) as live
asks: they predate the hold, and a held engine's asks never reach his list.
`briefs/CONTROL-CENTRE-HANDOFF.md` was superseded on 18 October by
`docs/CONTROL-CENTER-BRIEF.md`, and `briefs/2026-10-22-media-credits.md` on 29
October by the prepaid credits ruling and `docs/CREDITS-SESSION.md`. The
creative next action in `HANDOVER-2026-10-26.md` was superseded on 27 October by
`HANDOVER-2026-10-27-CREATIVES.md`.
