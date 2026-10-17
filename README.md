# growth-fulltime

The growth engine for [Full Time](https://fulltime.fm): one real Premier
League match, six complete shows, each made by a different AI Pundit. It
drafts what gets Full Time into fans' hands at a cost close to zero: the
match-morning clips and their native editions, the WhatsApp lines fans
forward, opt-in beta invitations, product fixes for the share loop, branded
creative, the numbers and a weekly decision. Krish performs external actions
by hand and keeps or kills work from the Monday report.

**Current execution plan:** [`EXECUTION-PLAN.md`](./EXECUTION-PLAN.md), with
ordered work, owners, dependencies and completion checks. No personal social
accounts, no cold outbound email, and a £0 incremental marketing cash target.
Start with product readiness and invited listeners; branded YouTube follows
the release conditions. [Product build briefs](./briefs/GROWTH-FOUNDATIONS.md)
are ready for a session on full-time.

**Goal:** 1,000 users by Sunday 8 November 2026 (a user finished a show and
left a way to reach them), and the evidence for Full Time's December release
bar. See `PLAYBOOK.md`.

**The first constraint is the rail.** The engine pushes no fan to a match
until at least 4 of the 6 AI Pundits made a show for it. On 16 October 2026
every match on the rail had one. Read it now in `state/FULLTIME-NOW.md`, or
run `python3 growth.py rail`.

Nothing here posts, sends, comments, uploads, boosts or spends. Nothing here
changes the full-time repository or the site.

- How it works and the rules: `AGENTS.md` (every run reads it first).
- The operating system, applied to Full Time: `PLAYBOOK.md`.
- The seven decisions the playbook needs from Krish: `rulings.json`.
- Krish's source document, and where Full Time changes it: `knowledge/`.
- The jobs: `jobs/`. The one tool: `growth.py` (Python standard library,
  plus git).
- What Full Time is doing right now: `state/FULLTIME-NOW.md`.
- Krish's changes: `CHANGES.md`.
- Where the last interactive session stopped, and the setup steps for the
  next one: the newest `HANDOVER-*.md`.

## How it stays across full-time

The full-time repository (`krishanraja/full-time`) is the source of truth for
the product, its words and its claims, and fulltime.fm is the source of truth
for what fans can hear. This engine never keeps its own copy of either.

| When | What happens |
|---|---|
| Every run, first | `python3 growth.py sync` reads full-time's main branch (the commit, the commits since the last sync, open pull requests, the canon its docs index routes a marketing agent to, the decision log) and the live rail at fulltime.fm. It writes `local/state/FULLTIME-NOW.md`, and the job reads any canon that changed before drafting. |
| Every pack | `check` refuses a pack whose `fulltime_sha` is older than a canon change on full-time, or written while Full Time's rules differ from what the checker was written for. It refuses a link to a thin rail, a link to an AI Pundit who made no show, a wrong score, and any channel whose ruling is not in force. |
| Every hour | A GitHub Action (`.github/workflows/sync.yml`) rewrites `state/FULLTIME-NOW.md` here when full-time, its open pull requests, the rail or the feed changed. If Full Time's rules changed, it commits a STOP notice and fails the run, so GitHub emails the owner. |

**The contract with full-time:** the canon is whatever the "Read by task"
rows of full-time's `docs/README.md` route for knowing where it is going,
marketing the live beta, explaining the product and knowing where it is
right now, in that order. Then `docs/product-state.json`, the vision and
beta page, the go-to-market manual, marketing, brand, product, growth, legal,
the roadmap, `NOW.md` and `AGENTS.md`. Change those rows, and this engine
follows on its next sync.

**Rulings.** A ruling is in force only when Krish has made it, a full-time
session has recorded it in full-time's decision log (`docs/12-roadmap.md`),
and `rulings.json` here marks it approved with that heading as evidence. The
sync checks the heading is there.

## Setting it up (Krish, once)

The eight-job setup below is the existing inventory. E07 in the execution
plan replaces it with a morning batch and a weekly review, updating the
manifest and setup instructions together before activation. The execution
plan does not create or enable scheduled tasks.

1. **Connect this repository** in Codex (cloud or the desktop app) or Cowork,
   with network access on. Runs need to reach github.com,
   raw.githubusercontent.com, fulltime.fm and the channels. Use the desktop
   app and "run in this project" so every run shares `local/`.
2. **Optional, for the dashboards:** a browser signed in to PostHog, Google
   Analytics, the krish@fulltime.fm inbox, and Full Time's TikTok, YouTube
   and Instagram accounts once they exist. The engine only reads
   (`BROWSER.md`).
3. **Create the schedule.** Open a chat on this repository and type "create
   the automations". It checks the machine, creates the eight tasks below and
   runs one to prove it. To add them by hand instead, use these (London
   time):

   | Name | When | Prompt |
   |---|---|---|
   | Full Time growth: sync | daily 06:00 | `Run jobs/sync.md as AGENTS.md says.` |
   | Full Time growth: numbers | daily 06:15 | `Run jobs/numbers.md as AGENTS.md says.` |
   | Full Time growth: radar | daily 06:30 | `Run jobs/radar.md as AGENTS.md says.` |
   | Full Time growth: match morning | daily 06:45 | `Run jobs/match-morning.md as AGENTS.md says.` |
   | Full Time growth: report | Mon 08:00 | `Run jobs/report.md as AGENTS.md says.` |
   | Full Time growth: creators | Tue 08:00 | `Run jobs/creators.md as AGENTS.md says.` |
   | Full Time growth: product | Wed 08:00 | `Run jobs/product.md as AGENTS.md says.` |
   | Full Time growth: launch | Thu 08:00 | `Run jobs/launch.md as AGENTS.md says.` |

To run one job by hand from anywhere, open a chat on this repository and
type, for example, "Run jobs/match-morning.md as AGENTS.md says."

Check the machine at any time with `python3 growth.py doctor`.

## Control Center

Packs don't go to Control Center yet. Control Center's `growth_packs` table
keeps one pack per `(pack_date, kind)`, with no venture, so a Full Time
`daily` pack would replace another venture's `daily` pack for the same day.
Until that changes, `post` saves each pack in `local/packs/` and prints it in
full in the run's final message.

`post` checks for a `ventures` list in Control Center's answer before every
send, and switches to Control Center by itself once it includes `fulltime`.
The change Control Center needs is the one `growth-heartside`'s README
describes, with `fulltime` added to the ventures.

## Layout

```
AGENTS.md         the brief every run reads first
HANDOVER-*.md     where the last interactive session stopped (newest first)
PLAYBOOK.md       the operating system, applied to Full Time
EXECUTION-PLAN.md current limits, ordered work and completion checks
briefs/           product work for a separate full-time build session
rulings.json      the seven decisions the playbook needs, and what each opens
BROWSER.md        read-only rules for the signed-in browser
jobs/             one file per job; automations.json schedules them
growth.py         sync, canon, rail, link, check, post, read, doctor, self-test
knowledge/        Krish's source document, and where Full Time changes it
state/            the hourly reading of full-time and the rail (written by the Action)
local/            on the running machine only, never committed: sync, packs, lists
```
