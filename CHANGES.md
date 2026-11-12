# Changes Krish made to the growth engine

Newest first. Record his words with the date, then change the job file and
`automations.json` together. A ruling (D1 to D7) is recorded here with his
words, and in `rulings.json` with the full-time decision-log heading that
records it.

- 2026-11-12: the docs match the engine, and closeout notes fold into NOW.md.
  Krish, 2026-11-12: "Is everything done? Are the project documentations up to date, 100%, every single
  word, with what this engine now is and how it works? Are there any other small bugs that you discovered
  that you just randomly left open?" NOW.md, README, AGENTS.md, the brief, GET-GOING, the credits session,
  the execution plan and the morning job now say what the code and Control Center do: the engine is held,
  Control Center has not woken it since 29 October, and no workspace run has reached it. The third
  obsession now quotes his own words of 17 October instead of summarising them. `growth.py closeout`
  checks and folds the closeout notes (engine/closeout.py, the fold job in check.yml); the six notes that
  had waited since 29 October are in docs/history/LOG.md. A repeated ack with a new line is now recorded,
  as Control Center accepts since protocol 1.21.0, the copy in docs/control-center/ is 1.21.0, and the
  hourly sync commits as `chore(heartbeat)` so the harness never marks NOW.md unreconciled for it. No
  job, schedule, ruling or wall changed, and the engine stays held.

- 2026-11-11: Control Center protocol 1.20.0, Krish's instruction and the engine's state.
  Krish, 2026-11-11: "Ensure the priorities, obsessions, and next steps for all the growth engines are
  feeding live to this dashboard, and not just in the growth tab. They are responsible for driving the
  overall success of each venture, so make sure I can instruct each one with my next best action and have
  it get going (as well as always understand the current state of play and what's outstanding). ... Get
  building". The morning job now pulls his instruction first (`growth.py cc instruction`) and records what
  it did (`growth.py cc ack`); the morning automation's prompt says so. Reports carry the acks and the
  engine's priorities, obsessions and next steps when the directive asks. His words stay in ignored
  `local/`. No wall moved and the engine stays held.

- 2026-10-30: the seven channel tasks join the plan as GET-GOING Step 7, dormant while the engine is
  held and until D1 is cleared. Krish asked for each of seven saved Instagram growth prompts to be its
  own task for every growth engine's specialists, defined once in ai-harness `contract/channel-tasks.md`.
  No job, automation or code changes.

- 2026-10-29: the credits step is built.
  Krish, 2026-10-29: "Scheduled sessions". `engine/credits.py` reads the
  share and guards any spend; the daily session in docs/CREDITS-SESSION.md
  spends it through Control Center's reserve and settle, never while held.
  No job, schedule or wall changed.
- 2026-10-29: Control Center protocol 1.16.0, prepaid credits.
  Ruling (Krish, 2026-10-29): a growth engine may spend up to its placement
  share of a tool's prepaid credits each cycle with no per-batch approval, and
  reports what it made. The protocol copy in `docs/control-center/` is now
  Control Center's current one, and docs/CONTROL-CENTER-BRIEF.md names Full
  Time's shares. While the engine is held it spends nothing. No code, schedule
  or wall changed.
- 2026-10-29: the engine is held until Krish releases it.
  Ruling (Krish, 2026-10-29): Not ready means a held activation state: no
  wake, no asks on his list, no growth council move, and the bearer stays
  valid. Full Time is a few weeks from being in motion. While Control Center's
  directive or the tracked `activation.json` (held by default) says held,
  each report has no proposals and one `NOT_READY` hold naming the readiness
  gates: the rail at 4 of 6, the release decision, D7, attribution, the
  workspace, and D1, still pending until its full-time decision-log entry
  exists. No ruling status, schedule or wall changed.
- 2026-10-26: connected creative releases to the product-owned personality core.
  Exact committed exports are verified and imported without activation; linked
  character variants receive only their selected core identity plus shared
  reusable speech. A changed product pin expands regression review. Core identity
  changes belong in the actual product; ad-only execution remains scoped here.
- 2026-10-26: added the offline creative continuity system.
  Ruling (Krish, 2026-10-26): "Build the engine, not the session."
  Separate versioned character and shared-style owners, pinned releases,
  scoped artifact judgments and regression gates now live behind
  `growth.py standards`. Actual dialogue, source media and review history stay
  under ignored `local/creative-system/`; the public schema and tests use no
  production creative. Technical success cannot override a human rejection.
  No schedule, channel, generation, product or Control Center authority changed.

- 2026-10-19: the copywriting, offers and demand corpus is now working knowledge.
  Krish: "all of these growth engines need to be imbued with this knowledge".
  Both files are preserved byte for byte in `knowledge/` and registered in
  `knowledge/sources.json`; repository verification and a unit test check
  their size and SHA-256. `COPY.md` applies the corpus to this engine and
  lists where its rules override it. PLAYBOOK.md, both job files and AGENTS.md
  now point drafting and review at it. No schedule, automation, contract,
  policy gate or Control Center behaviour changed.
- 2026-10-19: adopted the Control Center growth engine protocol.
  Ruling (Krish, 2026-10-19): "make each engine adopt its brief now".
  This supersedes the 17 October brief-only rule for run reports only: the
  engine now journals attempts, pulls its directive, reports with a digest
  readback and reads decisions through `growth.py cc`, at the end of both
  workspace tasks and on Control Center's daily `cc-growth-directive`
  dispatch (`.github/workflows/control-center.yml`). Packs stay local. The
  third morning action is now the release decision, since the reporting
  integration it named is done. Nothing sends, posts, spends or publishes,
  and an approval is recorded, never executed.
- 2026-10-17: completed the growth-side engine and made Control Centre a brief-only handoff.
  Ruling (Krish, 2026-10-17): "you are not to do any actual work in control-center, only pass me a brief once you have completed your work".
  Ruling (Krish, 2026-10-17): "Complete this all to 100% without coming back to me again."
  Enforced exclusions in code, removed remote report writes and the old eight-job
  setup, added durable history/recovery, aggregate measurement, experiment rules,
  local rendering, two consolidated jobs and a complete handoff contract. Product
  and release dependencies remain explicit; no product ruling was approved.
- 2026-10-17: verify existing access before requesting new credentials.
  Krish: "You should have full access to Vercel and all my projects.
  GROWTH_ENGINE_TOKEN is also in the github secrets". All eighteen Vercel
  projects are visible. The existing sync workflow now has a manual,
  read-only reporting check using that Actions secret. It skips sync writes
  and keeps credentials and report content out of logs. Authenticated reading
  does not waive the product-isolation requirement for report delivery.
- 2026-10-17: Control Centre is the unified reporting and action destination.
  Krish: "Control Centre is ultimately where the unified dashboard is going
  to be: where you report back on progress and recommendations to improve in
  the format that it requires." He also asks to be told when its UI cannot
  make recommendations actionable. E00 now proves access and native delivery;
  the private Control Center integration brief is pull request #470. Existing
  aggregate reads come before browser fallbacks, and local checkpoints do
  not count as dashboard delivery.
- 2026-10-17: execution plan and product build briefs, with the channel and
  cost limits carried into AGENTS, the playbook, browser rules and README.
  Krish: "Okay can you line up the execution plan? Just bear in mind that
  this cannot use my personal social media accounts and no cold outbound
  email. This needs to be as low cost and close to free as possible."
  The active plan targets £0 incremental marketing cash, uses Full Time's
  product and brand identity, and defers paid and founder-account channels.
  No product ruling or schedule is activated by the plan.
- 2026-10-16: a handover for the setup session (`HANDOVER-2026-10-16.md`),
  which `AGENTS.md` now tells every run to read after itself. Krish: "just
  save all of this in to the repo so the next codex session can go from here
  and set up the autonomous engine".
- 2026-10-16: the engine is built from the document in `knowledge/`. Krish
  attached "Full Time: The 1,000 Free Users in 30 Days Playbook" with the
  instruction below. Its seven decisions (section 9) are in `rulings.json`,
  all pending.
- 2026-10-16: a dedicated repository, the growth engine for Full Time. Krish:
  "now build out growth-fulltime repository as the dedicated growth engine
  for this app, obsessed with getting this into market". Built on the
  pattern of `growth-heartside`: drafts only, every run synced to the
  full-time repository first, a checker for Full Time's own rules, and
  scheduled Codex or Cowork runs.
