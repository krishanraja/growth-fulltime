# History log

Newest first. Entries are written by the closeout fold (`python3 growth.py closeout fold`, engine/closeout.py),
by the docs steward (`krishanraja/ai-harness`, `docs/steward/RUNBOOK.md`) and by people doing the same job by
hand. Nothing in this file describes current behaviour; `NOW.md` and `README.md` do. Text moved here from
`NOW.md` keeps its wording verbatim; only its relative links are re-pointed to work from here.

## 2026-11-12

Moved verbatim from `NOW.md` (the 12 November docs audit, when NOW.md was rewritten to match the code and
live state), and the six closeout notes that had waited in `now-notes/` since 29 October with no fold to
write them in, each verbatim. From now on the fold job in `.github/workflows/check.yml` writes each note
into NOW.md (`engine/closeout.py`).

From "Where it is right now (as of 2026-10-27)":

<!-- north-star-state {"week_of": "2026-10-26", "week_target": 5, "current": null, "current_as_of": "2026-10-27", "current_source": "No fresh cohort measurement available; prior 2026-10-23 value is historical", "urgency": 4, "urgency_reason": "current number unmeasured"} --> **North Star number: U4, unmeasured.** New listeners this week who arrived through a fan's shared link or clip: unknown, against 5 this week, on the way to 1,250 by 25 January 2027. The previous 0 was a 23 October observation, not a measurement of this week's attribution.

Lifecycle: building. The detail is in `README.md`.

The offline [creative system](../../creative-system/README.md) now pins independent
character and shared-style modules, exact input hashes and owner review evidence.
It preserves private creative history under ignored `local/creative-system/` and
starts with `python3 growth.py standards startup`. Creative acceptance and
technical success are separate; no new generation, publication or product
change is authorised by loading a baseline. A fresh product sync still reports
the minimum-four-pundit rail HOLD.

The product now owns the reusable six-pundit core in `krishanraja/full-time`;
growth imports and pins a committed export rather than owning duplicate identities.
Ad performance, sofa cast, visual direction and exact audio locks stay here.
The baseline and bridge are merged in PRs #10 and #11. Product PR #99 is merged;
the active private release pins its exact core from product commit `43c4ae2`.
The original audio locks and four owner video rejections survive this ownership
migration; it claims no new creative approval. The complete private continuation
package now lives in the [canonical Growth Build Drive folder](https://drive.google.com/drive/folders/1Pn_ibUcfpcyWzi4w1ryDMZMF-8m1gT_M).
Read [the 27 October creative handover](../../HANDOVER-2026-10-27-CREATIVES.md) first.
It contains the exact package hashes, restore route, owner corrections and next
review target. Liverpool v8 is a listening candidate; neither ad is ready to post.

Local proof: 131 self-checks, 129 unit/integration tests including 46 creative
tests, and repository verification passed. Actual session assets remain private.
The local operational run refused to proceed because existing growth history
was absent; no live report was sent or fresh operational ledger created.

From "What changed recently":

- 2026-10-27: archived the full private two-ad session and creative baseline to
  Drive, verified local rebuild and Drive file identity/size readback, and set a
  portable start-here path. The Liverpool ending, accents and TV music remain
  subject to owner listening. See [current handover](../../HANDOVER-2026-10-27-CREATIVES.md).

- 2026-10-26: implemented versioned creative standards, isolated composition,
  scope checks, improvement/regression gates, exact owner promotion and verified
  private bundle recovery. See [handover](../../HANDOVER-2026-10-26.md).

- 2026-10-23 **The North Star now has a number, a weekly ladder and an urgency rating.** Ruling (Krish, 2026-10-23): every repository chases one aggressive number on a weekly ladder, and urgency U1 to U5 sets how hard it pushes. The number is in `docs/NORTH_STAR.md`; contract: ai-harness `contract/north-star-metric.md`.

From "What is next and what is waiting on Krish":

- Review the full Liverpool v8 mix with Krish, correct only what the listening
  warrants, then get both existing concepts through audio and phone-size visual
  acceptance. Extract and test a fast, low-cost match-ad recipe after that.
- North Star check (2026-10-27): holds; U4 attribution is unmeasured.

From `now-notes/2026-10-29-credits-1-16-0.md`:

# 2026-10-29: Control Center protocol 1.16.0, prepaid credits

Status: the protocol copy in `docs/control-center/` is Control Center's current one (1.16.0): the directive may carry a `credits` block and a report may carry `credits_spent[]` at `schema_version` 1.16.0. `docs/CONTROL-CENTER-BRIEF.md` names Full Time's shares (Higgsfield about 600 of 3,000 a month, Runway about 450 of 2,250, 21st Dev about 50 of 500), what to do and the walls. The engine is held, so the share applies only once Krish releases it. No engine code changed: reports still go out at 1.0.0 with no `credits_spent`.

Next: once Krish releases the engine, do Step 6 of `docs/GET-GOING.md`: read `credits`, spend the share on stills first, and report `credits_spent` at 1.16.0, proved against the stand-in.

North Star check (2026-10-29): holds.

From `now-notes/2026-10-29-credits-spending.md`:

# 2026-10-29: the credits step is built

Status: the runner reads the directive's `credits` into its activity (absent means unknown and nothing is spent), its guard refuses any spend past `remaining_for_you` or while held, and a report carries `credits_spent` at 1.16.0 only when a run spent, proved against the stand-in. The share itself is spent by one daily scheduled session (`docs/CREDITS-SESSION.md`) through Control Center's `reserve_credit_spend` and `settle_credit_spend`. The engine is held, so that session spends nothing until Krish releases it.

Next: when Krish releases the engine, enable its credits session and check the first settled spend lowers `remaining_for_you`.

North Star check (2026-10-29): holds.

From `now-notes/2026-10-29-held.md`:

# 2026-10-29: held until Krish releases it

Status: the engine honours a held activation state. When Control Center's directive or the tracked `activation.json` (held by default) says held, every `growth.py cc` report carries no proposals and exactly one `NOT_READY` hold naming the readiness gates: the rail at 4 of 6 AI Pundits, the release decision, D7, attribution, the workspace, and D1, which stays pending until its full-time decision-log entry exists. No ruling status changed.

Next: Krish records D1 in full-time's decision log, then an interactive session here sets its status in `rulings.json`; the hold lifts only when he releases it.

North Star check (2026-10-29): holds. The number is unmeasured (U4) and this change moves none of it; it stops five daily asks reaching his list while the engine is not ready.

From `now-notes/2026-10-30-channel-tasks.md`:

Status: The seven channel tasks are planned as GET-GOING Step 7, dormant behind the hold and ruling D1. No code, job or automation changed.
Next: when Krish releases the hold and clears D1, map the morning and weekly jobs onto the tasks.
North Star check (2026-10-30): holds.

From `now-notes/2026-11-10-codex-signin.md`:

Status: Claude sessions here show Krish a ChatGPT sign-in link and code whenever Codex is signed out (.claude/hooks/codex-login.sh at session start, cloud included); his subscription, never an API key (Krish, 2026-11-10).
Next: none for this; the first cloud session that uses Codex shows him the link and code.
North Star check (2026-11-10): holds.

From `now-notes/2026-11-11-instruction-and-state.md`:

Status: Control Center protocol 1.20.0 is built here. When the directive says features.engine_state, each report goes out at 1.20.0 with the engine's priorities (the North Star number this week against its target, then its open gates), Krish's quoted aims as obsessions, its next steps (the first open GET-GOING step, then NOW.md's "What is next") and acks of his instruction by id. The morning job pulls his instruction first (growth.py cc instruction) and records what it did (growth.py cc ack); his words stay in ignored local/. A dispatch's run id is unique per GitHub wake. The engine stays held, so an instruction is acked received, then blocked "Engine held".
Changed: engine/engine_state.py (new), engine/control_center.py, engine/reporting.py, engine/cli.py, jobs/morning.md, the morning automation's prompt, AGENTS.md, README, the brief, GET-GOING (Step 0 found done, Step 8 added), and the protocol copies in docs/control-center/ (1.20.0).
Next: on the first run after this merges (a dispatch or the morning job), read the stored report back and confirm it is schema_version 1.20.0 with priorities, obsessions and next_steps, and that Growth > Engines shows them.
North Star check (2026-11-11): holds.
