---
repo: krishanraja/growth-fulltime
product: Full Time growth engine
as_of: 2026-10-27
head: 4f74866
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

Full Time's growth engine: it reads the product, prepares the posts that bring football fans to Full Time, asks Krish one thing at a time in Control Center, and counts what worked. Nothing it makes sends, posts, schedules or spends on its own: Krish posts by hand in Buffer.

## Who it is for and why it matters for Mindmake

Football fans who become Full Time's returning listeners. It proves Mindmake can grow a product with approved moves, no paid acquisition and a measured number.

## Where it is right now (as of 2026-10-27)

<!-- north-star-state {"week_of": "2026-10-26", "week_target": 5, "current": null, "current_as_of": "2026-10-27", "current_source": "No fresh cohort measurement available; prior 2026-10-23 value is historical", "urgency": 4, "urgency_reason": "current number unmeasured"} --> **North Star number: U4, unmeasured.** New listeners this week who arrived through a fan's shared link or clip: unknown, against 5 this week, on the way to 1,250 by 25 January 2027. It stays unmeasured until full-time ships share tokens (`briefs/2026-10-27-share-attribution.md`).

Lifecycle: building. Engine v2 ([docs/ENGINE-V2.md](docs/ENGINE-V2.md), approved by Krish on 27 October: "approved, do it all") is built through its engine phases and waits on Krish and the product for the rest.

- **Built and verified:** the weekly plan (G1) and matchday pack (G2) gates, readiness computed from Krish's own verdicts, eleven crew cards, the invariant registry (116 entries, 80 enforced by passing tests), session packs, the Codex dispatch guard, the Growth Build library rules, the read-only Buffer reader and receipts, attribution and learning, protocol 1.1.0, the Match Clock's fixtures reader, and Krish's daily actions list in every report. Two independent review waves found real defects; every confirmed one is fixed with a regression test. CI is green on Linux, Python 3.9 and Windows.
- **The social kit is approved:** "The Switch, revision 1" (Krish: "I like it. Looks good."), landing in `brand/social-kit/`, pinned by `LOCK.json`. It is the look every take clip, card and thumbnail is rendered in.
- **Nothing is posted yet,** by design: the handles, D7 consent and a published show to link to come first, and every format must earn readiness from three no-edit "post it" verdicts.
- **Supply is the binding constraint:** four published editions in five weeks, each with 1 of 6 AI Pundits, none since 19 October (`briefs/2026-10-27-rail-supply.md`).

## What changed recently

- 2026-10-27: engine v2 built, reviewed twice and fixed; daily autonomy (Krish's actions, the engine's to-do, fixtures, receipts); the social kit chosen by two blind judges from three concepts and approved by Krish. See [the v2 handover](HANDOVER-2026-10-27-ENGINE-V2.md).
- 2026-10-27: the full private two-ad session and creative baseline archived to Drive `Growth Build/06_Reference/creative-handoff/2026-10-27/`. See [the creative handover](HANDOVER-2026-10-27-CREATIVES.md).
- 2026-10-23: the North Star got a number, a weekly ladder and an urgency rating (`docs/NORTH_STAR.md`).

## What is next and what is waiting on Krish

`python3 growth.py actions` gives the live list. Today, in order:

1. Rule on D7 (PostHog and Google Analytics consent) in Control Center. It must close before the first post.
2. Switch Full Time to handcrafted in Control Center (one click).
3. Create the Full Time handles on YouTube (a Brand Account), TikTok and Instagram (Business), with the brand inbox, then connect them to Buffer.
4. Listen to the whole Liverpool v8 mix once and give one verdict.
5. Approve the two product briefs (share attribution, rail supply) and start a Control Center session with `briefs/2026-10-27-control-center-measurement.md`.

The engine's next work, without asking: render proof zero (take clips in the approved kit on the published editions) as the first G2, read fixtures each morning, and propose each week's plan on Monday.

North Star check (2026-10-27): holds; U4 until attribution exists.

## Read next

- `docs/NORTH_STAR.md`: the North Star, its number and its weekly ladder.
- `docs/ENGINE.md`: the 6 KB map a fresh session starts from.
- `HANDOVER-2026-10-27-ENGINE-V2.md`: what was built, how it was proved, what is open.
- `README.md`: what this repository is and how it runs.

## Do not trust

Do not treat a render, a technical media pass or a review-ready receipt as approval to post. Do not read the prior listener count as a fresh attribution measurement. Do not read a sample line in the social kit as anything an AI Pundit said: real quotes come from published show transcripts only.
