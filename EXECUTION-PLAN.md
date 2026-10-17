# Full Time growth execution plan

Build a repeatable path from an approved show to a finished listen, a return
visit and a voluntary recommendation. The first milestone is thirty invited
testers who finish a show. Broader distribution follows Full Time's release
bar and the recorded channel decisions.

Krish's limits, 17 October 2026: "this cannot use my personal social media
accounts and no cold outbound email" and "as low cost and close to free as
possible". These limits narrow the older channel banks and job instructions.
They apply to held drafts as well as ready items.

## Channel and cost limits

- Use Full Time's own website, feed and branded accounts. Never use Krish's
  personal profiles, followers, posts, comments, DMs or WhatsApp groups for
  acquisition. Creating or administering a brand account is a separate human
  action; an agent never signs up or changes accounts.
- No cold outbound email, including press pitches, creator pitches, bought
  lists or automated sequences. Product email is limited to replying to
  inbound requests and contacting people whose explicit opt-in covers that
  message. A launch-note subscription does not automatically cover a recap.
- Sharing is a listener's voluntary action from the product. The plan does
  not require Krish to send anything from his own WhatsApp account.
- Target **£0 incremental marketing cash**. No ads, paid creators, prizes,
  new SaaS subscriptions or paid media generation in this plan. Reuse
  published audio, transcripts, generated covers and the existing stack.
- Hosting, audio production, model calls and agent runs can still cost
  money or consume allowances. Record actual usage. No extra paid pipeline
  run or infrastructure upgrade is authorised by this plan.
- Agents prepare work; Krish performs external actions. The rail gate,
  consent work, product canon and existing rulings still apply. No ruling is
  marked approved by this document.

## Starting position

The latest 17 October sync read full-time at `210dc080fbdbf8d9a1bd888d2812dceda075bb44`.
The live rail had three matches with one AI Pundit each, so the push gate was
HOLD. All seven rulings were pending. Re-read with `python3 growth.py sync`
before using this position to make a decision.

The 1,000-user target for 8 November remains an ambition. A user is a unique
listener who finishes a show and leaves a permitted way to reach them. The
plan does not assume an existing audience, a conversion rate or viral growth.

## Delivery order and owners

Owners below are execution roles: the growth session works in this
repository; full-time and Control Center sessions implement their own product
and reporting changes; Krish owns product decisions and external actions.
Product briefs are collected in
[the build brief](briefs/GROWTH-FOUNDATIONS.md).

Control Center is the unified dashboard for progress, recommendations and
human actions. The [reporting integration brief](https://github.com/krishanraja/control-center/pull/470)
records the verified source access, required native formats and UI gaps.
Existing Control Center aggregates should be reused. Local files are private
checkpoints and backups; saving one does not mean the report was delivered.

| ID | Priority and work | Owner | Depends on | Completion evidence |
|---|---|---|---|---|
| E00 | Verify runtime access and the Control Center reporting contract | Growth and Control Center sessions | Existing-secret execution path and scoped source access | An authenticated, product-isolated report is read back and usable on the existing dashboard; missing access and UI gaps are explicit |
| E01 | Diagnose the thin rail from stored verdicts and identify the smallest supported fix | Full-time build session | Stored verdict access | Cause and fix recorded; a fresh eligible match has at least four published AI Pundits and playable assets |
| E02 | Verify the source of consenting beta testers and the contact-capture and consent decisions | Krish, with a product brief | Existing consent records or inbound requests | Eligible source and aggregate count recorded; D3/D7 status and any recruitment boundary recorded in full-time |
| E03 | Define and verify the measurement queries and event context | Growth session prepares contract; full-time session implements | Appropriate analytics access and consent handling | A controlled journey is reconciled from visit through real playback, completion, comparison and opted-in return |
| E04 | Build the exact-edition share preview, share action and optional way back | Full-time build session | E03; D3 for the return feature | Recipient opens the intended match and AI Pundit; crawler preview names both; saved preference is preserved |
| E05 | Keep canonical execution history in Control Center with private recovery checkpoints | Growth session | E00 and E03 definitions | Reruns retain results, publication status and decisions without duplicate records; reports read the canonical history |
| E06 | Render one reusable two-pundit clip template | Growth session | Two published editions of the same match | Local MP4, captions, thumbnail and source timestamps; no new generated voice or footage |
| E07 | Consolidate agent jobs into a morning batch and a weekly review | Growth session | E05; current channel limits | Jobs, schedule manifest and docs agree; one proved run; usage recorded; inactive channels create no recurring work |
| E08 | Run the invited beta and read the seven-day cohorts | Krish acts; growth session analyses aggregates | E00-E05 and eligible invite source | Thirty distinct testers finish; return, comparison and feedback reported with denominators |
| E09 | Test Full Time's branded YouTube channel | Krish publishes; growth session prepares and measures | E06, E08, full release bar and channel rulings | One format tested through a complete observation window; results linked to publication URLs and completed listens |

E00, E01 and E03 can be prepared alongside each other. E04 must not ship tracking
without its consent handling. E06 can use existing approved material for a
private rendering test, but no promotion goes out while the rail is HOLD.

Vercel project access was rechecked across all eighteen projects on 17
October. Krish confirmed the reporting token also exists in GitHub secrets;
the existing sync workflow's manual reporting check verifies that execution
path without exporting its value. An external runtime does not inherit an
Actions secret automatically. Use the supported Actions path before asking
for another binding, and keep authentication separate from the safe report
delivery test.

The [authenticated Actions check](https://github.com/krishanraja/growth-fulltime/actions/runs/39020906185)
passed on 17 October at 09:23 UTC: the existing secret was available and the
pack API returned HTTP 200 with its expected shape. No Full Time namespace
was advertised and no write was attempted. Authentication is verified for
that execution path; E00 remains open for safe report delivery.

## First three working days

These are work windows, not promised product release dates. A failed exit
check keeps the dependent work held.

1. **Day one:** verify E00's source reads and report destination; prepare
   E01's diagnosis brief; establish whether an existing
   beta opt-in audience or inbound queue exists; specify E03's queries and
   controlled test. Name the owner, next action and evidence needed for each
   blocker. Do not pay to rerun the pipeline to investigate it.
2. **Day two:** take the smallest supported pipeline fix through the product
   checks; verify event semantics and attribution; prepare the E04 share and
   return change against the product's single-screen layout.
3. **Day three:** verify an eligible match and the recipient journey; prove
   the execution ledger; render one private clip example. Start invitations
   only when the rail and recruitment conditions pass.

## The first beta cohort

Invite in small batches from explicit requests or an existing audience whose
consent covers the invitation. Send from the product inbox only, one person
at a time, using a `beta`-tagged link. No personal social account is a seed
channel. Do not promise an invitation count until the eligible pool is known.

If that pool is empty, record the acquisition blocker. Prepare a narrowly
scoped Full Time branded beta-interest route and recruitment decision for a
full-time session. Publishing the invitation waits for that recorded
decision; an empty list does not permit cold email or bypass the invite-only
canon. Existing feed and website traffic can supply inbound interest, but
their audience size must be measured before relying on them.

First verify five complete journeys. Then work towards thirty distinct
testers who finish. Keep the football match and AI Pundit choice clear and
collect the existing three feedback questions. The thirty are an initial
learning cohort, not a statistically conclusive experiment sample.

Read the existing release bar without changing its thresholds:

- At least thirty testers finish a show.
- At least 40% of completers start another show within seven days.
- At least half of returning testers play a second AI Pundit. Report the
  existing switch event alongside actual starts of distinct AI Pundits; a
  paused load or a different match alone is not evidence of comparison.
- At least 40% of respondents answer "very disappointed". Show the response
  count and response rate beside the percentage.
- Report publication reliability, median rail fill, factual incidents and
  consent against every other row of the December bar.

Only include completers whose full seven-day follow-up window has elapsed
in the mature retention reading. Report newer cohorts separately. If no
approved follow-up show was available, show that supply problem beside the
cohort rather than attributing the result to audience disinterest.

## The first public distribution test

Public acquisition starts only after the current release bar is met and the
channel decision is in force, or a new product ruling explicitly changes
that boundary. D1 alone must not be read as silently waiving the release bar.

Start with one **Full Time branded YouTube channel**, which supports Shorts
and full editions from the same approved material. Krish creates or connects
the brand channel and performs uploads. Personal profiles and personal
cross-posts are excluded.

Prepare up to three Shorts across eligible match mornings in the first test
week, using one format: two real arguments about the same match, with the
source audio, captions, covers, AI disclosure and one permitted call to
action. Produce one version per match before expanding formats or platforms.
Use a destination viewers can actually reach from the surface; Shorts
description URLs must not be assumed clickable. Record the real path through
the channel profile or a related full edition and test it on mobile.

Measure completed approved listens per measured visit, new completers,
returning listeners, actual production cost and Krish's minutes. When the
platform cannot attribute a visit, mark it unknown. Native views and watch
time explain attention; they do not establish app conversion.

Use twenty-four and seventy-two-hour readings for creative triage. Run
product experiments for at least seven days with a suitable sample and a
predeclared stopping rule, as full-time's growth policy requires. Record an
inconclusive result when volume is too low. Add another channel only when the
first has produced repeatable completed listens within the time budget.

Keep podcast-directory readiness as the next free distribution option:
check the existing Reporter feed, contact address, artwork and website
destination before a human submits it from Full Time's identity. This is
held for the same public-release boundary. Paid creators, ads, FPL, personal
LinkedIn, founder launches and cold press pitches have no active work here.

## The engine implementation backlog

Deliver these as small reviewed changes in growth-fulltime after the
product briefs. They are planned work, not commands that already exist.

- **Measurement contract:** document unique listeners, completed shows,
  reachable completers and mature retention cohorts. Query whole-window
  distinct counts; never add daily unique counts. Scope PostHog to Full Time
  and verify initial and current source attribution. Keep only aggregates
  in growth files; listener identifiers stay in the analytics system.
- **Execution ledger:** record creative ID, experiment ID, source commit,
  match, AI Pundits, asset paths, channel identity, dependencies, estimated
  minutes, status and actual publication URL. Statuses are drafted, held,
  ready, published or skipped; a pack stored by `post` is not a publication.
  Record reasons and results without names or addresses of private people.
- **Durable history:** Control Center is the canonical progress record.
  Keep private checkpoints and backups in the existing persistent project,
  under ignored `local/`. Test restart recovery and a unified report reader.
  Do not provision another database. Resolve local saving on a successful
  Control Center write so delivery does not lose recovery history. Use stable
  IDs and versions so reruns are idempotent.
- **Asset renderer:** use local FFmpeg, existing audio and deterministic
  artwork. Check timestamps and transcripts, captions, aspect ratio, audio,
  AI disclosure and the tracked destination. Reuse renders; no image or
  video generation service is required.
- **Cheap orchestration:** replace the eight-job schedule with one morning
  batch and one Monday review in the same persistent project. The morning
  batch syncs, reads available aggregate numbers, checks blockers and only
  prepares eligible work. Run it on relevant mornings; research is bounded
  by the current test. Update jobs, `automations.json`, setup instructions
  and existing checks together before creating or changing schedules.
- **Experiment record:** record the decision, audience, one changed
  variable, primary metric, guardrails, duration, sample rule, result and
  next action. Keep negative results. Referral clicks, share attempts and
  attributed new completers are separate counts; private forwards and true
  viral coefficient remain unknown when they cannot be observed.

## Daily operation and weekly decisions

The proposed morning batch reports at most three prioritised actions and
one short scorecard through Control Center's native surfaces. Keep Krish's
execution within twenty minutes a day and
the Monday review within thirty minutes. On a HOLD morning, lead with the
changed blocker and avoid regenerating an identical bank of held copy.

Before presenting an item as ready, recheck its live match, AI Pundit,
playable assets, source claims, tracked destination, channel identity and
the applicable product and release gates. Krish records the actual action
and its URL. Agents never infer publication from a draft being accepted.

Monday's decision covers one current constraint, one experiment to keep,
change or stop, and one next product or distribution action. Show incremental
cash, recorded production/agent usage and founder minutes beside completed
and returning listeners. Reforecast the 1,000-user ambition using observed
conversion and referral delay; the steady-state `seed / (1 - K)` equation
does not establish growth before a deadline.

Success for the first execution cycle is a working product journey, thirty
real completers and a mature retention reading, with £0 new marketing cash.
Public reach follows demonstrated listener value and the release conditions.
