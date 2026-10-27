# Engine index

Status: current, 27 October 2026. The map a fresh session starts from (6 KB at most). Read only the long document your task needs; where it and the code disagree, the code and its tests are right.

## What the engine is

Full Time's growth engine: a public repository, Python 3.9+ standard library only. It reads live product truth, keeps creative and experiment history, prepares exact posts and reports to Control Center with `python3 growth.py cc`. Nothing it makes sends, posts, schedules or spends on its own: Krish posts by hand in Buffer. Private data is in ignored `local/` and in Drive `Ventures/Full Time/Growth Build`.

## North Star

By 31 January 2027, most new Full Time listeners arrive because a fan shared an AI Pundit's take. The number is new listeners a week who arrived through a fan's shared link or clip: 1,250 by 25 January 2027, 49 by 16 November. Its value and urgency (U1 to U5) are on the first line under "Where it is right now" in [NOW.md](../NOW.md): U4 on 27 October, unmeasured until share attribution is wired.

## Rulings of 27 October (Krish), numbered as in AGENTS.md and ENGINE-V2

1. Per take: a post may go once the exact show it links to is published and checked; 4 of 6 only for whole-match posts; D7 first.
2. Reserve every handle; push TikTok, Reels and Shorts daily from one vertical master.
3. Handcrafted: Krish posts in Buffer. The engine never posts, schedules or writes to Buffer.
4. Claude plans and orchestrates; Codex makes, never touches network or accounts, never certifies itself.
5. Four formats: match ad, take clip, Pundit vs Pundit row, morning card.
6. Production runs on Krish's machine.
7. Ready = three no-edit "post it" verdicts on three matches, on a pinned lock, cost measured.
8. What-Works Analyst owns what works; the Measurement Analyst owns the number.
9. A full Canva brand kit, built through Cowork from the approved social kit.
10. Everything lives in Drive `Growth Build`, filed by the Librarian.
11. A match ad may link to Today only while Today has a live show.
12. Each format goes live on its own readiness.
13. The Audience Builder grows the brand profiles only.
14. Automate within platform rules: official APIs, each action kind ruled and known in code.
15. Google Analytics comes from Control Center's `ga4_landings`; landings are never listeners.

## The crew

Each has `crew/<name>/card.md` (3 KB at most) and a reviewer's `lens.md` (1 KB). Ruling 13 added the eleventh.

1. Product Truth: every claim and link points at something live now.
2. Match Clock: the match fans are arguing about, timed from the product's publish.
3. Take & Script Writer: the exact line a fan would send to one named mate.
4. Voice Lock: each voice matches its pinned lock and has a human listening verdict.
5. Motion Maker: renders offline, stills before video, credits only inside an approved `spend`.
6. Card Maker: Canva cards from pinned brand templates.
7. Channel & Pack Steward: allowlisted Full Time channels only; receipts from read-only Buffer.
8. Measurement Analyst (the number): counts it from the product export with a 95% interval; reads Google Analytics 4 landings by creative ID, read-only, kept apart from listener numbers.
9. What-Works Analyst: a fresh session, never a maker. A claim is confirmed only after two matchweeks, 20 events per arm and |z| of 2 or more.
10. Librarian: the only writer into Growth Build; no orphans, duplicates or misnamed files.
11. Audience Builder: brand-profile visibility and followers, within platform rules.

## Gates, one ask at a time on Krish's list

- G1, each Monday: the weekly spec as a `plan` behind `strategy`, with last week's check-in folded in, then that week's `spend`.
- G2, each matchday: one handcrafted `post` ask listing every item. Clear is "post it" for all, Purge rejects all, Change it first gives a verdict per item by diff, Bump waits a day.
- No questions mid-turn: they go in `open_questions[]` and the session ends at the gate.

## Sessions

Kinds: scheduled (the CLI, no model), orchestrator, production (Codex, main checkout), review (lenses and rubric) and build (a task card). Budgets: `engine/config/budgets.json`; Krish's minutes stay at 20 a day or fewer. `engine/session.py` builds the pack (36 KB at most) and logs sessions. `engine/dispatch.py` checks task cards and guards the Codex allowance: refused above 80% or on an unknown reading, unless Krish approved that card's spend ask. Codex runs on `gpt-6.1-sol`.

## Commands

```
python3 growth.py sync | doctor | --self-test | standards startup
growth.py run|cc morning|weekly [--require-existing-history]; cc dispatch
growth.py actions                  # Krish's actions today, the engine's to-do
growth.py fixtures fetch|import F  # the Match Clock's week
growth.py spec check|compile|propose F   # G1
growth.py formats readiness|lock   # readiness is computed, never written
growth.py pack check|propose F     # G2
growth.py buffer receipts ... --record
growth.py library | session | dispatch | audience | ga4
python3 -m unittest discover -s tests; python3 scripts/verify_repository.py
python3 scripts/baseline.py   # build and run cost, from real logs
```

None of these posts, sends, schedules or spends; `--help` gives options.

## Where the long documents are

- [AGENTS.md](../AGENTS.md): the whole brief and every ruling.
- [COPY.md](../COPY.md): the copy doctrine; read it before any drafting or review.
- [creative-system/README.md](../creative-system/README.md): characters, voices and visuals.
- [ENGINE-V2.md](ENGINE-V2.md): the approved v2 plan; [GET-GOING.md](GET-GOING.md): the build steps.
- [NORTH_STAR.md](NORTH_STAR.md): the ambition.
- [RUNBOOK-MATCHDAY.md](RUNBOOK-MATCHDAY.md): one matchday; [OPEN.md](OPEN.md): what is open, and who holds it.
