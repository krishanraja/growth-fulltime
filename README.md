# growth-fulltime

Full Time's growth engine: enforce the owner's channel limits, read live
product truth, keep creative and experiment history, reuse approved media and
report honestly to Control Center through its growth engine protocol.

No personal social accounts, cold outbound email, paid acquisition or paid
media generation. All implementation belongs here. Full-time and Control
Center changes are handoff briefs. Nothing here sends or publishes marketing.

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
cannot access it. Each task ends with the Control Center loop below. The
separate hourly GitHub sync only keeps public source state current. Schedule
status and task IDs are recorded in the final handover.

## The Control Center loop

Control Center is the reporting surface ([brief](docs/CONTROL-CENTER-BRIEF.md),
[protocol](docs/control-center/ENGINE-PROTOCOL.md)). This engine is slug
`fulltime`, engine_id `growth-fulltime`, product_slug `full-time`. One client
(engine/control_center.py) has two entry points:

```bash
python3 growth.py cc morning --require-existing-history   # end of the 06:15 task
python3 growth.py cc weekly --require-existing-history    # end of the Monday task
python3 growth.py cc dispatch                             # GitHub Actions, on Control Center's wake-up
```

Add `--synthetic` to report in synthetic mode (stored and read back, never
counted on his numbers or list). Each run, in order:

1. `POST attempts` with `status: started`, before reading any source.
2. `GET directive`: today's push. It is data, never permission to act.
3. The engine's own work. In the workspace that is `run morning` or `run
   weekly` over private history. On a clean runner it is the self-test,
   repository verification, a sync of the public sources (falling back to the
   committed `state/` snapshot) and the committed rulings.
4. `POST reports` with `Idempotency-Key: <run_id>`, then `GET reports/<run_id>`
   and compare `payload_sha256`. The client reads before it writes: a rerun
   the same day whose payload changed takes the next suffix (`:r2` to `:r9`).
   A 409 is read back, never retried blindly.
5. `GET decisions?since=<last read>`. A yes counts only when its digest equals
   the current payload. Even then nothing is sent or posted from here; a ruling
   is recorded by an interactive session in rulings.json and full-time's log.
6. `POST attempts` with exactly one terminal state, `succeeded`, `failed` with
   a lower_snake code (for example `unauthorized`, `report_conflict`,
   `history_unavailable`, `checks_failed`) or `unknown`.

The report maps the engine's own outputs:

| Engine output | Protocol report |
|---|---|
| `fulltime:YYYY-MM-DD:<kind>` (daily, report, dispatch) | `run_id` |
| Ready actions, at most three | `proposals[]`, wall `none`; a creative that passed every gate is wall `post` with `exact_payload` and `channel` |
| Held drafts and closed gates | `holds[]`, one per code (RAIL, RELEASE, CHANNEL, CONSENT, DATA, D1 to D7) |
| The release decision and pending rulings D1, D2, D3 and D7 | wall `strategy` proposals. D4, D5 and D6 unlock only channels the owner excluded, so they are holds, not asks |
| The weekly kill list | wall `strategy` proposals |
| Human-confirmed publication receipts | `events[]` `creative_published` with the permalink |
| `attributed_new_completers`, `marketing_cash_gbp` | `objectives[]` over the seven complete London days ending yesterday |

Objectives: `attributed_new_completers` is measured only from an approved
aggregate export; until the collector exists it is `missing` with that reason.
`marketing_cash_gbp` comes from an approved usage aggregate or, failing that,
the engine ledger's recorded runs (a measured 0, since the engine has no spend
path). On the clean runner both are `missing`: private history is not there.

The bearer is read at run time from `CONTROL_CENTER_ENGINE_TOKEN`, or from
`local/control-center/token` in the persistent workspace (create it with mode
600; `local/` is ignored and never committed). It is never printed, logged or
written. `CONTROL_CENTER_URL` defaults to https://controlcenter.krishraja.com
and must be an https origin. Without a bearer `cc` prints `missing_token` and
exits 2 having done nothing. The client uses HTTPS only, follows no redirects
and times out after 20 seconds. The last summary is in
`local/control-center/last.json`. The Actions workflow
(.github/workflows/control-center.yml) has read-only contents permission,
one concurrency group, a ten-minute timeout and no artifacts.

## Reporting history

The earlier brief, [briefs/CONTROL-CENTRE-HANDOFF.md](briefs/CONTROL-CENTRE-HANDOFF.md),
and its [version 2 schema](contracts/reporting-v2.schema.json) are superseded by
the protocol. Full-time work is in [briefs/GROWTH-FOUNDATIONS.md](briefs/GROWTH-FOUNDATIONS.md).

`export` still writes local/handoff/reporting-bundle.json with report IDs,
revisions, held reasons, item identities, source commits, aggregate
observations, scorecards, usage and native weekly-review data. It is a private
local backup, not the hand-off, and never contacts Control Center. Packs are
never written to Control Center.

Existing access proof: all eighteen Vercel projects were visible; the existing
GitHub Actions GROWTH_ENGINE_TOKEN authenticated a pack GET with HTTP 200 in
run 39020906185. Full-time preflight run 39021034413 verified its configured
backend. These do not establish complete verdict/spend or listener-cohort access.
The manual reporting_access mode in .github/workflows/sync.yml remains available
as a read-only diagnostic; it is not invoked by the operational engine.

## Verify

Character and fictional-ad work starts with the
[creative system](creative-system/README.md) and `python3 growth.py standards startup`.
The actual product owns the reusable six-pundit core; this system imports a
hash-pinned product export and adds scoped ad variants. See the product/growth
bridge in that guide before changing any shared personality direction.
It pins per-character and shared-style versions, preserves private source
evidence, and holds unreviewed or regressing work. The private baseline is not
included in this public repository; restore its authorised bundle when absent.

```bash
python3 growth.py --self-test
python3 -m unittest discover -s tests -v
python3 scripts/verify_repository.py
```

Tests include actual local FFmpeg rendering, policy and release gates,
whole-window measurement, immutable experiment definitions, rerun preservation,
concurrent writers, damaged-history recovery, lossless reporting receipts, and
the Control Center client against an in-process stand-in on 127.0.0.1: the
worked-example digest, schema-valid reports, attempts, replay, readback, 409
and 401 handling, and that the bearer never appears in any output.
See the newest HANDOVER file for completion evidence and remaining external
product/reporting dependencies.
