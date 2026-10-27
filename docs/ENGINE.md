# Engine index

Status: current, 27 October 2026. The map a fresh session starts from (6 KB at most). Read only the long document your task needs. Where this file and the code disagree, the code and its tests are right.

## What the engine is

Full Time's growth engine: a public repository, Python 3.9+ standard library only. It reads live product truth, keeps creative and experiment history, prepares exact posts and reports to Control Center with `python3 growth.py cc`. Nothing it makes sends, posts, schedules or spends on its own: Krish posts by hand in Buffer. Private data stays in ignored `local/` and in Drive `Ventures/Full Time/Growth Build`.

## North Star

By 31 January 2027, most new Full Time listeners arrive because a fan shared an AI Pundit's take. The number is new listeners a week who arrived through a fan's shared link or clip: 1,250 by 25 January 2027, 49 by 16 November. Its value and urgency (U1 to U5) are on the first line under "Where it is right now" in [NOW.md](../NOW.md): U4 on 27 October, unmeasured until share attribution is wired.

## Rulings of 27 October (Krish), numbered as in AGENTS.md

1. Go now, per take: a brand post may recruit pilot-beta testers once the exact show it links to is published and its facts check. Four of six applies only to whole-match posts. D7 consent closes first.
2. Reserve every handle, push three: TikTok, Reels and Shorts daily from one vertical master; derived cards elsewhere.
3. Handcrafted posting: Krish posts in Buffer himself. The engine prepares exact packs and never posts, schedules or writes to Buffer.
4. Roles: Claude plans and orchestrates; Codex makes creative and packs, never touches the network, connectors or accounts, nor certifies its own work.
5. Four formats carry the 11/10 bar: the remote-switch match ad, take clips, Pundit vs Pundit rows and match-morning cards. Production runs on Krish's machine.
6. A format is ready after three no-edit "post it" verdicts on three matches, computed, never written. Each goes live on its own.
7. A match ad may link to Today only while Today has a live show, and never claims a show exists for its match.
8. What works is owned by the What-Works Analyst; measurement by the Measurement Analyst, including Google Analytics 4 landings by creative ID.
9. The Audience Builder grows the Full Time brand profiles only, within platform rules: official APIs, every action type ruled by Krish first. Follow automation, mass liking and bought followers stay banned in code.
10. Google Analytics comes from Control Center's daily directive (`ga4_landings`); Krish sets nothing up. Landings never count as listeners.
11. Everything the engine produces lives in Drive `Growth Build`, filed by the Librarian with no sprawl. A full Canva brand kit is built through Cowork.

## The crew

Each has `crew/<name>/card.md` (3 KB at most) and a reviewer's `lens.md` (1 KB). Ruling 9 added the eleventh.

1. Product Truth: every claim and link points at something live now.
2. Match Clock: the match fans are arguing about, timed from the product's publish.
3. Take & Script Writer: the exact line a fan would send to one named mate.
4. Voice Lock: each voice matches its pinned lock and has a human listening verdict.
5. Motion Maker: renders offline, stills before video, credits only inside an approved `spend`.
6. Card Maker: Canva cards from pinned brand templates.
7. Channel & Pack Steward: Full Time allowlisted channels only; receipts from the read-only Buffer readback.
8. Measurement Analyst (the Measurement Specialist): counts the number from the product export with a 95% interval, and reads Google Analytics 4 landings by creative ID, read-only, from Control Center (`docs/GA4-ACCESS.md`) as a leading web signal, kept apart from listener numbers.
9. What-Works Analyst: a fresh session, never a maker. A claim is confirmed only after two matchweeks, 20 events per arm and |z| of 2 or more.
10. Librarian: the only writer into Growth Build; no orphans, duplicates or misnamed files.
11. Audience Builder: brand-profile visibility and followers, within platform rules.

## Gates, one ask at a time on Krish's list

- G1, each Monday: the weekly spec as a `plan` behind `strategy`, with last week's check-in folded in, then that week's `spend`.
- G2, each matchday: one handcrafted `post` ask listing every item. Clear is "post it" for all, Purge rejects all, Change it first gives a verdict per item by diff.
- No questions mid-turn: they go in `open_questions[]` and the session ends at the gate.

## Sessions

Kinds: scheduled (the CLI, no model), orchestrator, production (Codex, main checkout), review (lenses and rubric) and build (a task card). Budgets: `engine/config/budgets.json`; Krish's minutes stay at 20 a day or fewer. `engine/session.py` builds the pack (36 KB at most) and logs each session to `local/engine/sessions.jsonl`. `engine/dispatch.py` checks task cards (`tasks/card.schema.json`) and guards the shared Codex allowance: refused above 80% or on an unknown or stale reading, unless Krish approved its spend ask (`fulltime-codex-<card_id>`) on that exact card. Codex runs on `gpt-6.1-sol`.

## Commands

```
python3 growth.py sync | doctor | --self-test | standards startup
python3 growth.py run morning|weekly [--offline] [--require-existing-history]
python3 growth.py cc morning|weekly|dispatch
python3 -m unittest discover -s tests -v
python3 scripts/verify_repository.py
python3 scripts/baseline.py [--actions-json FILE] [--run-sessions-dir DIR] [--build-sessions-dir DIR]
```

The v2 verbs are wired as each phase lands; [ENGINE-V2.md](ENGINE-V2.md) section 2 lists them.

## Where the long documents are

- [AGENTS.md](../AGENTS.md): the whole brief and every ruling.
- [COPY.md](../COPY.md): the copy doctrine; read it before any drafting or review.
- [creative-system/README.md](../creative-system/README.md): characters, voices and visuals.
- [ENGINE-V2.md](ENGINE-V2.md): the approved v2 plan; [GET-GOING.md](GET-GOING.md): the build steps.
- [NORTH_STAR.md](NORTH_STAR.md): the ambition.
