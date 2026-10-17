# growth-fulltime

Full Time's growth engine: enforce the owner's channel limits, read live
product truth, keep creative and experiment history, reuse approved media and
prepare honest reports for a separate Control Centre integration.

No personal social accounts, cold outbound email, paid acquisition or paid
media generation. All implementation belongs here. Full-time and Control
Centre changes are handoff briefs. Nothing here sends or publishes marketing.

## Run

Python 3.9+, git and network access are required. Rendering additionally uses
local FFmpeg and FFprobe. Python modules use the standard library only.

```bash
python3 growth.py sync
python3 growth.py doctor
python3 growth.py run morning
python3 growth.py run weekly
python3 growth.py export
```

`run` syncs product truth first, prepares at most three actions and saves a
scorecard and a versioned handoff export. It makes no model, audio or outbound
marketing calls. The full scorecard distinguishes missing, stale and measured
zero. A HOLD run is successful operation, not permission to promote.

Offline verification uses a current saved sync:

```bash
python3 growth.py run morning --offline
python3 growth.py metrics examples/observations.json
python3 growth.py run morning --observations local/approved-aggregates.json
```

The last command imports only a product-scoped aggregate export conforming to
MEASUREMENT.md. No person-level data is accepted. Without a collector export,
completed listeners and retention remain unknown. GA4 and coarse PostHog
counters are not replacements for those outcomes.

## Drafts, history and experiments

```bash
python3 growth.py check local/draft.json
python3 growth.py post local/draft.json
python3 growth.py read --days 8
python3 growth.py history --backups
python3 growth.py history --restore local/engine/backups/REPLACE_WITH_BACKUP.json
python3 growth.py experiment add examples/experiment.json
python3 growth.py experiment list
python3 growth.py experiment result local/result.json --id exact-edition-share-v1
python3 growth.py creative CREATIVE_ID --status published --url https://youtube.com/watch?v=ACTUAL_ID --human-confirmed
```

`post` saves locally only. Stable pack IDs include product, date and kind;
revisions preserve history. Creative identities, actual publication proof and
experiment results survive reruns. No draft or export implies publication.
History writes are locked and atomic. Corruption fails closed; recovery validates
a backup and preserves the damaged file. Private data lives in ignored local/.

Brand verification is read from local/brand-identities.json, scoped to product
fulltime, with an identities object keyed by identity_ref. Each record needs
platform, account_scope brand, verified true, an actual HTTPS channel source_url
and a timezone-aware verified_at within thirty days. Missing or stale proof
keeps CHANNEL held. This registry does not approve release or consent.

## Reuse approved media

```bash
python3 growth.py assets fetch --drop PUBLISHED_DROP_ID --pundit zen
python3 growth.py assets render local/clip-manifest.json
```

Use examples/clip-manifest.json as the input shape after downloading a real
published edition. One segment makes a private one-edition preview; two need
distinct published AI Pundits from the same match. The renderer checks source
hashes, transcript quotation, audio bounds, duration, audio/video streams and
portrait dimensions. It produces MP4, burned captions, SRT, thumbnail and a
receipt with source timestamps and a tracked destination. Caption timing still
needs review. Existing renders are reused. Nothing is uploaded.

## Two agent jobs

| Job | Europe/London | Instruction |
|---|---|---|
| Morning batch | Daily 06:15 | Run jobs/morning.md |
| Weekly review | Monday 08:00 | Run jobs/weekly.md |

`automations.json` owns these two tasks. Reuse this persistent project and its
private history. Scheduled commands use --require-existing-history. Never silently reset the ledger if a scheduled execution
cannot access it. The separate hourly GitHub sync only keeps public source
state current. Schedule status and task IDs are recorded in the final handover.

## Reporting and handoff

Control Centre is the future unified dashboard. The completed brief is
[briefs/CONTROL-CENTRE-HANDOFF.md](briefs/CONTROL-CENTRE-HANDOFF.md), with the
[versioned report schema](contracts/reporting-v2.schema.json). Full-time work
is in [briefs/GROWTH-FOUNDATIONS.md](briefs/GROWTH-FOUNDATIONS.md).

`export` writes local/handoff/reporting-bundle.json with report IDs, revisions,
held reasons, item identities, source commits, aggregate observations, scorecards,
usage and native weekly-review data. It never contacts Control Centre. No
capability response automatically enables writing. A future integrator must
verify a full product-isolated, field-preserving round trip on the existing UI.

Existing access proof: all eighteen Vercel projects were visible; the existing
GitHub Actions GROWTH_ENGINE_TOKEN authenticated a pack GET with HTTP 200 in
run 39020906185. Full-time preflight run 39021034413 verified its configured
backend. These do not establish complete verdict/spend or listener-cohort access.
The manual reporting_access mode in .github/workflows/sync.yml remains available
as a read-only diagnostic; it is not invoked by the operational engine.

## Verify

```bash
python3 growth.py --self-test
python3 -m unittest discover -s tests -v
```

Tests include actual local FFmpeg rendering, policy and release gates,
whole-window measurement, immutable experiment definitions, rerun preservation,
concurrent writers, damaged-history recovery and lossless reporting receipts.
See the newest HANDOVER file for completion evidence and remaining external
product/reporting dependencies.
