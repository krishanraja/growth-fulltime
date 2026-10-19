# Full Time growth engine

<!-- north-star:start -->
## North Star: read it first, every session

This repository's North Star is [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md): an ambition Krish set that is not reached yet.

- Read it before any work, every session.
- Before you start, say which part of it the task moves. If it moves nothing, say so first and let Krish decide.
- Prefer the work that moves it furthest, and close by noting what moved.
- Only Krish changes it.
<!-- north-star:end -->

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
3. Read `PLAYBOOK.md`, `EXECUTION-PLAN.md`, `BROWSER.md`, then the job file.
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
- Target zero incremental marketing cash. Record known model/audio usage,
  hosting and agent costs separately; unknown costs stay null. Never run a paid
  production pipeline to diagnose a failure. Read stored verdicts first.
- Do not ask again for a reporting token: the existing GitHub Actions secret
  was verified. It does not grant permission to implement Control Centre.

Krish, 19 October 2026: "make each engine adopt its brief now". Every run
journals its attempt, pulls Control Center's directive, reports and reads his
decisions. His approval binds only the exact payload it was made on, and even
then nothing here sends, posts, spends or publishes. The bearer is
`CONTROL_CENTER_ENGINE_TOKEN` (an Actions secret) or the ignored file
`local/control-center/token`; never print, copy or commit it.

## The rules

1. Draft and analyse. Never send, post, upload, comment, like, follow, DM,
   subscribe, sign up, boost, buy, or change external accounts or settings.
   Human publication evidence can be recorded without performing the action.
2. Product truth comes from the synced full-time canon and the live site.
   Do not change full-time, PostHog, Vercel, Supabase or another product.
3. No promotion to a match below four published AI Pundits. Validate the
   exact drop and published AI Pundit in every show link. A held draft still
   needs a real destination and accurate facts.
4. Public acquisition also needs the product's separate release decision,
   verified brand identity and channel rulings. D1 alone does not waive the
   December release bar. Never mark a ruling approved from a plan or test.
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
