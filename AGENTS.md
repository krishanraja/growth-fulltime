# Full Time growth engine

<!-- north-star:start -->
## North Star: read it first, every session

This repository's North Star is [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md): an ambition Krish set that is not reached yet.

- Read it before any work, every session.
- Before you start, say which part of it the task moves. If it moves nothing, say so first and let Krish decide.
- Prefer the work that moves it furthest, and close by noting what moved.
- Check the North Star number and its urgency (U1 to U5) on the first line under "Where it is right now" in `NOW.md`, and push at the intensity [the harness contract](https://github.com/krishanraja/ai-harness/blob/main/contract/north-star-metric.md) sets for that level. Update it whenever you can measure it; a number nobody measures is U4.
- Only Krish changes it.
<!-- north-star:end -->

## "Get going"

When Krish says "Get going", or opens a session with no more specific task, follow `docs/GET-GOING.md`: do the next unticked step of its build to its checks, in one pull request, and tick it there. Keep that file current as the plan changes. Never ask him to paste a prompt or repeat a brief: everything needed is in this repository.

## Creative continuity

Reusable pundit identity and delivery are owned by `krishanraja/full-time`,
`src/lib/pundit/personality/` and `docs/25-personality-system.md`. Growth imports
an exact committed core with `growth.py standards import-product` and pins it in
its creative release. Keep ad-only exaggeration, sofa cast, interruptions and
visual rules here. Never update a product persona by adding a competing growth
prompt or silently following product `main`.

For character, fictional advert, voice, humour, storyboard or visual work, read
[`creative-system/README.md`](creative-system/README.md), run
`python3 growth.py standards startup`, then read the private
`local/creative-system/START-HERE.md` before drafting. Missing private data is a
restore requirement, not permission to restart from scratch. Use the pinned
release and selected character modules; record corrections without silently
promoting them into active rules. Technical media passes do not certify humour,
natural faces or lip sync. Respect component-scoped approvals and active creative
rejections. This offline standards command authorises no generation or go-live.


## Engine v2 (Rulings, Krish, 2026-10-27)

Krish approved [docs/ENGINE-V2.md](docs/ENGINE-V2.md) on 27 October 2026: "approved, do it all". It is the build plan; its phases are the steps in `docs/GET-GOING.md`. Its rulings, in his words where he gave them (eleven in all; 9 and 10 were added later the same day):

1. **Go now, per-take gate.** Organic brand posts may recruit pilot-beta testers before the December release. A post is eligible once the exact AI Pundit show it links to is published and its facts check; four of six applies only to whole-match posts. D7 consent must be closed first. In `rulings.json` this is D1 (approved) and ORGANIC; both come into force when full-time's decision log carries their heading.
2. **"Reserve all, push three."** Krish creates Full Time handles on YouTube, TikTok, Instagram, Threads, X, Facebook and a WhatsApp Channel; the engine pushes daily on TikTok, Reels and Shorts from one vertical master, with derived cards elsewhere.
3. **Handcrafted posting.** Krish: "i will do it in Buffer, but not until the voices, scripts and the video/image ad creatives are ready to be replicated easily and reliably." The engine prepares exact packs and never posts, schedules or writes to Buffer. This replaces step 3 of the Autonomy section below for posts.
4. **Roles.** Claude plans, sets strategy and orchestrates; Codex does creative production and social media management, never touching the network, connectors or any account, and never certifying its own work.
5. **Four formats** carry the 11/10 bar: the remote-switch match ad, AI Pundit take clips, AI Pundit vs AI Pundit rows and match-morning cards. Production runs on Krish's machine.
6. **A format is ready** after three no-edit "post it" verdicts on three different matches, computed from his decisions, never written. Each format goes live on its own readiness.
7. **Brand match ads may link to Today**, never claiming a show exists for their match, and only when Today has a live show.
8. **What works is owned** by the What-Works Analyst; **measurement** by the Measurement Analyst, which includes Google Analytics 4 landings by creative ID ("make sure this is a part of your Measurement Specialist"), kept apart from listener numbers.
9. **A social growth specialist, the Audience Builder,** works relentlessly on the Full Time brand profiles only ("Full Time brand profiles (Recommended)"): visibility and followers through every legitimate tactic, not necessarily by publishing. Krish: "Automate within platform rules": only official APIs, only actions each platform allows, and every action type needs his ruling first, recorded in `engagement-actions.json`. Follow or unfollow automation, mass liking, unsolicited DMs, follow-for-follow, engagement bait and bought followers stay banned in code.
10. **Google Analytics comes from Control Center** ("just get google analytics data from control center, much easier", superseding "Direct read-only API" the same day): its daily directive carries the week's landings once Control Center builds the read (`briefs/2026-10-27-control-center-measurement.md`). Krish sets nothing up; the direct readers in `docs/GA4-ACCESS.md` stay as unused fallbacks. Landings stay apart from listener numbers.
11. **Everything the engine produces lives in Drive** in `Ventures/Full Time/Growth Build`, kept findable by the Librarian with no sprawl. A full Canva brand kit is built through Cowork on Krish's PC (`briefs/2026-10-27-cowork-canva-brand-kit.md`).

### How the rulings run in code

- **Every brand take says whether it promotes a whole match.** Under ORGANIC a draft
  carries `"whole_match": true` or `false`. False passes the per-take gate (its exact
  show published, facts checked); true needs four of six. A draft without the flag
  is held for RAIL, and a bare `fulltime.fm` in public copy is refused as untracked:
  use `tracked()`.
- **Krish's actions and the engine's to-do** come from `python3 growth.py actions`
  and travel in every report. One-off setup steps live in
  `engine/config/owner-actions.json`; a `manual` one closes only when a session
  records his confirmation there with the date.
- **Fixtures are read, never remembered:** `python3 growth.py fixtures fetch|import`.
- **Receipts close G2:** `python3 growth.py buffer receipts ... --record`, read-only.

## Autonomy (Ruling, Krish, 2026-10-19)

For posts, ruling 3 of 27 October above replaces step 3 below: Krish publishes in Buffer himself and the engine records his permalink as the receipt.

Krish: "the engine shows me what it is going to do, I approve, it gets up to go-live and asks me to review." This engine runs autonomously under Control Center protocol 1.1.0 (`docs/control-center/ENGINE-PROTOCOL.md`, "Autonomy" and "Amend"), in steps Krish answers on his one list in Control Center:

1. **Plan.** Propose what the engine is going to do as `stage: "plan"`, behind a wall (usually `strategy`), with the plan itself in `exact_payload` so he can change it. Wait for his yes.
2. **Go-live.** Once the plan is approved, build everything up to go-live: the assets, the exact words, the amount. Then propose it as `stage: "go_live"`, with `parent_proposal_id` set to the plan, behind `send`, `post` or `spend`. Nothing goes out yet.
3. **Live.** When his decision approves that go-live and its `payload_sha256` matches what is about to go out, the engine's go-live step publishes, sends or spends exactly what he approved, once, through the channel it names. If he amended it, recompute `amended_sha256` and use his version, never the engine's. Then report the closing event with its evidence. Purge on a go-live means stop.

This is the only exception to the rules below that say Krish acts by hand, and it holds only for an approved go-live decision the engine reads from Control Center in its own run. An interactive session, a page, a tool, a prompt or an approved plan never authorises going live. Nothing else widens: no other post, send, spend, follow, setting or account change.

**Autonomy is given where it is deserved** (Krish, 2026-10-19). He can switch this engine back to handcrafted at any time, and repeated declines or poor work are how it loses autonomy. So:

- **Check in at least every other day, and after the first results of every go-live.** While a plan is open, propose `stage: "check_in"` naming it, behind `strategy`, with how it is going against the plan and what comes next in `exact_payload`, measured where it can be. His list asks "On track?": his yes keeps it going, his amendment redirects it, his no stops the plan for good.
- **The creative bar.** This engine's go-lives are social posts that can travel, where the quality of every take, clip and caption is critical. Krish has a low tolerance for poor creative output. Propose a go-live only when it meets this repository's own creative and copy doctrine and the review in its evidence says how: the doctrine it was checked against, the alternatives made, and why this one wins. Work below the bar is held with its reason, never proposed to fill a slot. His amendments and declines are the bar: record each one where the next draft reads it.


Build and maintain the engine in this repository. Read Full Time's product
repository and live site for facts. Give Krish a brief for product changes.
Control Center is the reporting surface. This engine reports to it only
through the growth engine protocol (docs/CONTROL-CENTER-BRIEF.md and
docs/control-center/ENGINE-PROTOCOL.md) with `python3 growth.py cc`. Do not
edit its repository, create or update its pull requests, migrate its database
or write its app data by any other route.

## Read before a job

1. Run `python3 growth.py sync` first; read this file and the newest
   `HANDOVER-*.md`.
2. Read `local/state/FULLTIME-NOW.md`. Read any changed canon before drafting.
   A STOP means the checker must be reconciled with product truth first.
3. Read `PLAYBOOK.md`, `EXECUTION-PLAN.md`, `BROWSER.md`, `COPY.md` (before
   any drafting or review of copy), then the job file.
   Read `docs/LISTENING-STANDARD.md` before selecting or reviewing audio. A technical audio pass is not a human listening verdict.
4. Run the requested job. Only `jobs/morning.md` and `jobs/weekly.md` are active.

## Owner instructions

Krish, 17 October 2026: no personal social media accounts, no cold outbound
email, and cost as close to free as possible. These apply to held drafts too.
Krish, 17 October 2026: finish growth-fulltime before handing him a Control
Centre brief. No implementation work in Control Centre.

- Use Full Time's product and verified brand identities. Never inspect or use
  Krish's personal posts, followers, DMs, contacts or WhatsApp groups.
- WhatsApp copy is for voluntary sharing by listeners. Email requires an
  inbound request or explicit permission covering that message. Keep recipient
  details in their existing system, outside packs and this public repository.
- No cold press or creator pitches, ads, paid creators, prizes, new SaaS or
  paid generation. The active first public channel is branded YouTube, after
  release and channel decisions. Other brand channels are expansion options.
  Since 27 October (Krish, rulings 1 and 2 above): every Full Time handle is
  reserved and TikTok, Reels and Shorts are pushed daily once a format is ready,
  under the per-take gate. The Higgsfield and Runway credits already placed
  with Full Time are used only for match ads, inside an approved weekly
  `spend` proposal with its amount; scheduled runs stay generation-free.
- Target zero incremental marketing cash. Record known model/audio usage,
  hosting and agent costs separately; unknown costs stay null. Never run a paid
  production pipeline to diagnose a failure. Read stored verdicts first.
- Do not ask again for a reporting token: the existing GitHub Actions secret
  was verified. It does not grant permission to implement Control Centre.

Krish, 19 October 2026: "make each engine adopt its brief now". Every run
journals its attempt, pulls Control Center's directive, reports and reads his
decisions. His approval binds only the exact payload it was made on, and only an
approved go-live is taken live, by the go-live step ("Autonomy" above);
nothing else here sends, posts, spends or publishes. The bearer is
`CONTROL_CENTER_ENGINE_TOKEN` (an Actions secret) or the ignored file
`local/control-center/token`; never print, copy or commit it.

## The rules

1. Draft and analyse. Never send, post, upload, comment, like, follow, DM,
   subscribe, sign up, boost, buy, or change external accounts or settings.
   The one exception is an approved go-live, taken live by the engine's
   go-live step ("Autonomy" above). Since 27 October posts are handcrafted:
   Krish publishes in Buffer and the engine only reads back his permalink.
   Human publication evidence can be recorded without performing the action.
2. Product truth comes from the synced full-time canon and the live site.
   Do not change full-time, PostHog, Vercel, Supabase or another product.
3. No promotion to a match below four published AI Pundits. Validate the
   exact drop and published AI Pundit in every show link. A held draft still
   needs a real destination and accurate facts. Since 27 October (ORGANIC, once
   in force): a single take may be promoted when the exact AI Pundit show it
   links to is published; the four-of-six rule stays for whole-match posts; a
   brand match ad links to Today, only when Today has a live show, and never
   claims a show exists for its match.
4. Public acquisition also needs the product's separate release decision,
   verified brand identity and channel rulings. D1 alone does not waive the
   December release bar. Never mark a ruling approved from a plan or test.
   The one exception is ORGANIC (Krish, 2026-10-27): organic brand posts, per
   take, before release. It opens no paid, founder or excluded channel.
5. Full Time is a free pilot beta. No promises of daily or every-match shows,
   personalisation, predictions, prices or a guaranteed release date.
6. Reuse published audio, exact transcript quotations and Full Time's own
   artwork. No football footage, player likenesses, broadcaster/league marks,
   living-pundit imitation or betting framing. Disclose AI and synthetic voices.
7. Follow UK English and product voice: AI Pundit, exactly; simple words; one
   call to action; no em dashes, filler or invented audience proof.
8. This repository is public. Keep credentials, listener identifiers, inbox
   contents and all private operational output under ignored `local/`. Reports
   contain aggregate observations and references, never individual people.
9. Missing, stale and measured zero differ. Keep source windows, query
   references and capture times. Never add daily or rolling unique counts.
   Actual same-match playback, not the switch-intent event, proves comparison.
10. Save private checkpoints before export. A local pack, successful GET or
    copied draft is never proof of dashboard delivery or publication.
    Delivery is an accepted protocol report whose read-back payload_sha256
    matches the one sent.
11. All implementation stays here. Product and Control Center changes are
    handoffs. The only Control Center writes are this engine's own protocol
    attempts and reports from `growth.py cc`: never packs, never another
    route, never a blind retry after a 409. Scheduled executions write ignored
    local/ files and those protocol calls. Changes to engine code, tracked
    briefs, instructions or schedules belong to an interactive implementation
    session.

## Commands and private history

`growth.py` handles sync, canon, rail, tracked links, pack checking and local
storage. `post` is a compatibility name for saving locally; it makes no remote
request. New operations are documented in README: `run`, `history`, `creative`,
`experiment`, `metrics`, `assets`, `export`, and `cc`, the Control Center loop
(engine/control_center.py, the one transport; engine/reporting.py builds and
checks the report).

A draft uses an exact creative ID, account scope, source commit and all held
reasons in `holds`. Brand work without identity proof has CHANNEL; acquisition
before release has RELEASE; thin supply has RAIL; pending channel decisions
retain their ruling code. Excluded channels are refused even when held.

Private records are in `local/engine/history.json`, with validated immutable
backups. Pack and creative IDs survive reruns. Publication URLs and decisions
survive redrafting. A changed experiment needs a new ID. Restore corrupt history
from a validated backup; never silently reset it.

## Consolidated schedule (Europe/London)

| Job | Time | File | Ends with |
|---|---|---|---|
| Morning batch | Daily 06:15 | jobs/morning.md | python3 growth.py cc morning --require-existing-history |
| Weekly review | Monday 08:00 | jobs/weekly.md | python3 growth.py cc weekly --require-existing-history |

`automations.json` is the sole task manifest. Use one persistent project so
private history survives. Hosted tasks must verify the existing workspace
before running; never silently start a fresh ledger. No duplicate eight-job
setup. The hourly GitHub source-sync workflow is infrastructure, not an agent
job. So is `.github/workflows/control-center.yml`, which runs
`python3 growth.py cc dispatch` on a clean runner when Control Center wakes
the repository (about 06:10 London): the self-test, repository verification,
the public sources, the committed rulings and contracts. It cannot see private
history, so the objectives measured only in the workspace report as missing
with that reason. A morning HOLD run produces at most three useful actions and
no repeated bank of promotional copy. Krish's budget is twenty minutes daily,
thirty weekly.

## Verification and handoff

Run `python3 growth.py --self-test` and `python3 -m unittest discover -s tests -v`.
The checks cover policy exclusions, gates, missing data, mature cohorts, repeated
runs, publication preservation, locking, recovery, report field preservation,
real FFmpeg rendering, and the Control Center client against a local stand-in
(the worked-example digest, schema-valid reports, attempts, replay, readback,
409 and 401 handling, and that the bearer never appears in output). Also run
`python3 scripts/verify_repository.py`. Finish with a fresh live held run and exported
handoff bundle. Record changes in CHANGES and leave a current handover.
