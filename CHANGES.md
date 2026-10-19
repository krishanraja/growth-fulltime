# Changes Krish made to the growth engine

Newest first. Record his words with the date, then change the job file and
`automations.json` together. A ruling (D1 to D7) is recorded here with his
words, and in `rulings.json` with the full-time decision-log heading that
records it.

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
