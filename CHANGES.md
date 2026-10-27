# Changes Krish made to the growth engine

Newest first. Record his words with the date, then change the job file and
`automations.json` together. A ruling (D1 to D7) is recorded here with his
words, and in `rulings.json` with the full-time decision-log heading that
records it.

- 2026-10-27: approved engine v2 and recorded nine rulings.
  Ruling (Krish, 2026-10-27): "approved, do it all" for [docs/ENGINE-V2.md](docs/ENGINE-V2.md).
  His decisions that day, in his words where given: going live "Go now, per-take
  gate (Recommended)" (D1 approved, new ORGANIC entry; in force once full-time's
  decision log carries the heading); accounts "Reserve all, push three
  (Recommended)"; publishing "i will do it in Buffer, but not until the voices,
  scripts and the video/image ad creatives are ready to be replicated easily and
  reliably"; roles "Claude handles planning, strategy, orchestration, whilst codex
  handles creative production and social media management"; the 11/10 bar built
  against the remote-switch ad, take clips, rows and match-morning cards;
  production on his machine; ready after "3 in a row, no edits"; brand match ads
  may link to Today; each format goes live on its own readiness; "knowing what
  works and what doesnt is CRITICAL"; a full Canva brand kit; every asset and
  strategy in the Drive Growth folder with no sprawl; Google Analytics as part of
  measurement. The Drive library `Ventures/Full Time/Growth Build` now has its
  fixed tree, START-HERE and INDEX, and the 27 October creative handoff moved,
  unrenamed and with its file IDs intact, into `06_Reference/creative-handoff/`.
  Nothing was posted, sent, scheduled or spent.

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
