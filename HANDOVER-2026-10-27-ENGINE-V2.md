# Engine v2 handover, 27 October 2026

Start with [NOW.md](NOW.md), then [docs/ENGINE.md](docs/ENGINE.md), the 6 KB map a fresh
session starts from. The plan Krish approved ("approved, do it all") is
[docs/ENGINE-V2.md](docs/ENGINE-V2.md); its steps and their state are in
[docs/GET-GOING.md](docs/GET-GOING.md). This handover says what was built, how it was
proved, and what is open. The [creative handover](HANDOVER-2026-10-27-CREATIVES.md) of
the same day still owns the match-ad session and its private baseline.

## North Star part this moved

Both halves of "most new listeners arrive because a fan shared an AI Pundit's take; this
engine knows which takes travel and makes more of them". The engine can now prepare
shareable takes in an approved look, ask Krish one thing at a time, read back what he
posted and count what worked. The number itself stays unmeasured (U4) until full-time
ships share tokens: that brief waits on Krish's approval.

## What was built

| Part | Where | What it does |
|---|---|---|
| Weekly plan, G1 | `engine/spec.py`, `growth.py spec` | The week's spec (fixtures, formats, channels, experiments, learnings) checked, digested and asked as one `plan` |
| Matchday pack, G2 | `engine/pack.py`, `growth.py pack` | Every item checked against product truth, the week spec and earlier asks, then asked as one `post` |
| Gates and verdicts | `engine/gates.py` | Krish's answers settle each gate; per-item verdicts by diff; receipts close G2 |
| Readiness | `engine/formats.py` | Three no-edit "post it" verdicts on three matches, on a pinned lock, computed and never written |
| Crew of eleven | `crew/`, `engine/crew.py` | A card and a lens per specialist, each with a lint before and a measured check after |
| Invariants | `invariants/registry.json`, `engine/invariants.py` | 116 entries over the failure history; 80 enforced by tests that must exist and pass |
| Sessions and dispatch | `engine/session.py`, `engine/dispatch.py` | The 36 KB pack; the Codex allowance guard with a spend ask |
| Library | `engine/library.py` | The Growth Build rules 1 to 9, with sprawl tests |
| Buffer, read only | `engine/buffer_read.py` | Allowlisted Full Time channels only; receipts matched to the approved caption |
| Measurement | `engine/attribution.py`, `engine/learning.py`, `engine/ga4.py` | The North Star join, Poisson intervals, the learning register; Google Analytics from Control Center's `ga4_landings` |
| Audience Builder | `engine/audience.py`, `engagement-actions.json` | Brand-profile actions only, each kind known in code and ruled by Krish |
| Protocol 1.1.0 | `engine/control_center.py`, `engine/reporting.py` | Stages, amendments, one ask of each kind at a time, the capabilities check |
| Daily autonomy | `engine/actions.py`, `engine/fixtures.py`, `jobs/` | Krish's actions and the engine's to-do in every report; fixtures read, never remembered |
| Social kit | `brand/social-kit/` | The approved look, pinned by `LOCK.json` (CI fails on any unapproved change), rendering byte-identical to the frames Krish approved |
| take_clip renderer | `brand/social-kit/take_clip.js`, `engine/assets.py` | Kit layers from Playwright, composed by FFmpeg over the show audio: frame 0 for one second, caption plates, the lime progress fill; every existing check kept, `RENDERER_VERSION` 4 |
| Windows | `engine/clock.py`, CI | London time without tzdata, UTF-8 everywhere, a Windows CI job |

## How a day runs

06:15 London, `jobs/morning.md`: sync, run, `growth.py actions`, then the engine's own
to-do (fixtures, receipts, the North Star line), then on a matchday with a published
show the pack, and `growth.py cc morning` reports with Krish's actions as plain lines.
Monday 08:00, `jobs/weekly.md`: what works, the week's plan as G1, the library
reconcile and backup, and `growth.py cc weekly`. Krish answers in Control Center and
posts by hand in Buffer. Nothing in this repository posts, sends, schedules or spends.

## How it was proved

- Two independent review waves. In each, finders read the code cold, verifiers reproduced
  each finding with a probe, fixers fixed it with a regression test, and a fresh agent
  re-ran every probe. Wave 2's residuals (declined posts holding slots, receipts from the
  wrong host or week, synonyms for banned actions, a calendar-coupled test, the gate
  without ORGANIC) were fixed the same day.
- The social kit: three concepts generated blind to each other, two blind judges with a
  shared rubric (both picked The Switch), one synthesis with their must-fixes, shown to
  Krish cold. His verdict: "I like it. Looks good."
- Checks on the last commit: the full unit suite, `python3 growth.py --self-test`,
  `python3 scripts/verify_repository.py` and `invariants.check()` pass locally; CI's three
  jobs (Linux with FFmpeg, Python 3.9, Windows) are green on the branch.

## Drive library (`Ventures/Full Time/Growth Build`)

- `01_Strategy/2026-W44/`: the four briefs (v1) and the two revised briefs (v2) with
  `source: <path>@<commit>` stamps. The plan itself is not mirrored: git is its single
  source (library rule 9).
- `05_Brand-Kit/2026-W44_social-kit-approval_v1.json`: Krish's approval, the reviewed page
  and the SHA-256 of every approved frame. Rendered frames are filed from Krish's machine
  (`brand/social-kit/README.md`), because the Drive connector cannot carry large images.
- `06_Reference/baseline/2026-10-27_baseline_v1.json`: the build and run baseline.
- `06_Reference/creative-handoff/2026-10-27/`: the creative session's 18 files, moved
  intact.

## Open, and who holds it

| Item | Holder | Next step |
|---|---|---|
| D7 consent | Krish | Rule in Control Center; it must close before the first post |
| Handcrafted mode, handles, Buffer channels | Krish | `growth.py actions` lists them with minutes |
| Liverpool v8 listening | Krish | One verdict on the whole mix |
| Share attribution and rail supply | full-time, after Krish approves the briefs | Without them the number stays U4 and there is little fresh to post |
| `ga4_landings` and the two objective keys | Control Center, after Krish starts the session | `briefs/2026-10-27-control-center-measurement.md` |
| Proof zero | engine, on Krish's machine | The renderer is proved on a synthetic tone; render take clips with each published edition's real audio and ask them as the first G2 |
| Caption timing and motion | engine | Word timings would light the current word; the tab blink, seal stamp and the cut variant are specified but not yet animated |
| Canva templates | engine and Krish | Rebuild the Cowork brief's six templates from the approved kit; uploads need his yes |
| Baseline from Krish's machine | Krish's machine | `scripts/baseline.py` with his Codex and Claude logs; until then the baseline is cloud-only |
| v1 briefs with the old stamp form | Librarian | Archive to `99_Archive/2026-W44/` at week close (Sunday) |
| Hosted task prompts | Krish or a hosted session | Copy `automations.json`'s two prompts into the hosted tasks |

## Do not trust

A render, a review-ready receipt or a passing test is not approval to post. A sample
line in the kit is not anything an AI Pundit said. The baseline counts only this cloud
session's logs, so it is a lower bound until it reads Krish's machine.
