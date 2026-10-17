# Control Centre implementation handoff

The growth-fulltime implementation is complete in its own repository. This is
the brief for a separate Control Centre session. No Control Centre repository,
database, UI, permissions or app data were changed during that implementation.

## Goal and boundaries

Make Full Time's progress, evidence and recommendations usable through the
existing Growth, Board and Home surfaces. Extend the current primitives; add
no parallel dashboard, product registry, work queue or weekly model job.

Owner constraints must travel with the product: no personal social accounts,
personal-network acquisition, cold outbound email, paid promotion or paid media
generation. Target zero incremental marketing cash. Defining its B2C audience
must not enable legacy prospecting or another product's account fallback.

Read Control Centre's current AGENTS.md, operating context and docs/app/ first.
The source review below predates implementation; recheck current code/schema.

## What is already delivered by growth-fulltime

- Enforced channel, identity, consent, rail and separate release gates.
- Atomic, locked private history with backups, recovery, stable creative IDs,
  immutable experiment definitions, result history and human publication proof.
- Whole-window aggregate validation and scorecards with source dates, stale
  handling, mature cohorts, denominators and explicit missing values.
- One deterministic morning batch and one weekly review. No outbound actions
  or paid model/audio generation. A HOLD run returns at most three actions.
- A local FFmpeg template for one published edition or two distinct AI Pundits
  on the same match, with provenance, quotations, captions, thumbnail and receipt.
- A version 2 handoff envelope and native weekly-review output. No remote writer
  and no automatic switch based on an advertised ventures list.

Run `python3 growth.py export` in the persistent project. Its private output is
`local/handoff/reporting-bundle.json`: reports, run_reports, creative_history
and experiments. Run reports
include complete scorecards, source windows, usage, actions and native review
data. Files are recovery checkpoints; they are not dashboard delivery.

## Existing access proof

All eighteen Vercel team projects were visible. GitHub Actions used the existing
GROWTH_ENGINE_TOKEN and received HTTP 200 with the expected pack response in
[run 39020906185](https://github.com/krishanraja/growth-fulltime/actions/runs/39020906185).
Do not rotate or request that token again. It is available inside its configured
Actions execution context, not automatically inside every external runtime.

[Full Time preflight run 39021034413](https://github.com/krishanraja/full-time/actions/runs/39021034413)
passed through its configured backend. It reads release, voice and daily-drop
state. It does not supply editorial verdicts, spend history or listening cohorts.
No broader source access is claimed. Product inbox coverage remains unverified.

## Current interface defects

Reviewed paths: src/lib/growthPacks.ts, api/growth/packs.ts,
src/components/growth/PacksView.tsx and src/lib/portfolio.ts.

The reviewed growth_packs schema upserts on (pack_date, kind), with no product
namespace. The parser drops Full Time's source commit, creative/item IDs, held
reasons and listening measures. GET authentication works, but a Full Time write
could overwrite another product's same-day pack and turn held work into ready
copy. An empty table is not proof that this is safe.

The portfolio reader also had stale Full Time paid-plan/checkout wording. Use
full-time's current canon: free pilot beta, checkout disabled, first listen
without an account. Do not publish a launch date or silently alter release bars.

## Required implementation

1. **One product adapter.** Keep portfolio.ts authoritative. The engine uses
   fulltime, Growth reviews full-time, and registry/metrics full_time. Resolve
   those aliases at one boundary; reject unknown products. Do not rename live
   registry keys or add a second map elsewhere.
2. **Product-isolated packs.** Add a validated product key and unique product,
   date, kind key. Scope GET, PATCH, status carry-over and reruns. Migrate existing
   publication packs into their correct product without changing their content.
3. **Versioned lossless ingestion.** Extend the existing packs route to accept
   contracts/reporting-v2.schema.json. Preserve report_id, revision, source SHA,
   policy, stable item/creative IDs, all holds, readiness, assets and typed
   aggregate provenance. Keep current publication callers compatible through the
   same parser boundary. Reject unsupported fields explicitly rather than losing
   them silently. Keep internal rates separate from public-copy validation.
4. **Readback proof.** The future adapter can POST the v2 envelope through the
   existing authenticated route. GET by report_id and product must return
   `{ok: true, report: {report_id, revision, product_slug, venture, pack}}`.
   engine/reporting.py verifies all those fields and the entire round-tripped
   pack. Product namespace or HTTP 200 alone never acknowledges delivery.
   Use stable item IDs for Full Time status updates, not an array index that
   can point to another item after redrafting.
5. **Native review ownership.** Run outputs already provide product_slug,
   week_start, findings, kill_list and double_down. Feed that evidence into the
   existing growth_council_reviews writer and Growth Next/This week readers.
   Do not create a competing writer or council cron. Preserve krish_decision
   and decided_at; reconcile the source week with the week the existing UI reads.
6. **Work and human actions.** Use the existing /api/workbench engine interface
   for work_board_items, never SQL inserts bypassing admission/closure rules.
   Only actions requiring Krish go onto Home's one list, with only_you, link,
   closes_on and close_ref where required. Unknown evidence never closes an item.
7. **Measures and source health.** Reuse current GA4/PostHog collection and
   extend its existing source path with MEASUREMENT.md's aggregate definitions.
   No new analytics subscription or model-based collector. Keep absent access,
   a stale sample and a measured zero distinct. Add verdict/spend aggregates
   through an approved product read path; never copy broad service keys.

## Required UI behaviour

| Existing surface | Required addition |
|---|---|
| Growth Packs | Visible product, stable item identity, all held reasons, source/asset links and actual publication receipt |
| Growth Numbers | Unique completers, reachable completers, mature return, actual same-match comparison, survey denominator, source window and capture time |
| Growth Next / This week | One leading constraint, concise evidence and at most three useful next actions |
| Home | Only actions requiring Krish, once, with an explicit close condition |
| Buyers / Places | Full Time's own B2C audience and actual brand identity; planned accounts remain unavailable |
| Existing work view | Execution status, evidence and clear ownership without creating another queue |

On phone and desk, long instructions and URLs must wrap and all held reasons
must be readable. A copied draft is never labelled published. A private local
asset path needs the existing protected asset-serving solution before it becomes
a usable dashboard link; do not expose private checkpoints in a public bucket.

## Acceptance evidence

- Two products can store the same day and kind; reads, edits, reruns and status
  carry-over cannot cross products. Reject unknown aliases.
- A v2 report survives POST/GET without losing any field or changing its product,
  report ID or revision. Deleting one held reason must fail receipt verification.
- Reordering or rewriting copy retains the correct human publication proof by
  stable item identity. A saved draft does not create publication evidence.
- Missing/stale/zero metrics render differently. Return denominators contain only
  mature cohorts; switch-intent never masquerades as actual comparison.
- Weekly evidence uses the existing writer; human decisions survive a rerun.
- Defining the audience cannot activate personal accounts, cold email or paid
  channels. Unverified brand identities stay unavailable.
- Extend tests/api/growthPacks.test.ts and e2e/growth.spec.ts; retain the existing
  bridge-never-sends, one-list, one-close, design-token and no-scroll checks.
- Verify the deployed source reads, a controlled report round trip and the
  signed-in phone/desk UI. Fixtures and binding metadata alone are insufficient.

The growth engine remains brief-only until a separate implementation is
verified and the owner changes that boundary. This handoff does not activate
public marketing, approve a product ruling or authorise a production run.
