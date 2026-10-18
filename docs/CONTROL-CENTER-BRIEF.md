# Control Center brief: growth-fulltime

Written 2026-10-18 by Control Center. This brief **supersedes `briefs/CONTROL-CENTRE-HANDOFF.md`** as the reporting contract. Krish ruled that every growth engine reports through one protocol (ADR-038 in Control Center). Your reporting v2 bundle becomes a protocol report. Product isolation of packs remains a Control Center follow-up for media review only.

## What Control Center now does for you

- **Pushes you one next action every day, chosen by rule.** That is at most one; you keep your own cap of three actions per run.
- **Puts every post, release ruling and channel ruling (D1 to D7) on Krish's one list on Home**, and returns his decision bound to the exact payload.
- **Shows your health, objectives, today's push and what you did** on Growth > Engines.

## Your registry row

| | |
|---|---|
| Slug in the path | `fulltime` |
| `engine_id` | `growth-fulltime` |
| `product_slug` | `full-time` (your `engine_product: fulltime` and `venture: full_time` are not used here) |
| Aim | Most new Full Time listeners arrive because a fan shared an AI Pundit's take, not because anyone was invited. By 2027-01-31 |
| Objectives | `attributed_new_completers`: no target set yet, per week (Europe/London); `marketing_cash_gbp`: target 0 |
| Cadence | daily |
| State | Switched on 2026-10-18, with dispatch on. Your bearer arrives in this repository's secrets as `CONTROL_CENTER_ENGINE_TOKEN`, with `CONTROL_CENTER_URL` as a variable. Until then, build against `mode: synthetic` |

## The protocol, in short

The full spec is `docs/control-center/ENGINE-PROTOCOL.md`, with the report and directive schemas and a worked example beside it. In short:

**Base URL and auth.**
- Base: `CONTROL_CENTER_URL`, which is `https://controlcenter.krishraja.com`.
- Bearer: `Authorization: Bearer $CONTROL_CENTER_ENGINE_TOKEN`. This is a `gen1_` token issued for this engine alone. Control Center keeps only its SHA-256, and it opens this engine's routes and no others.
- Transport: HTTPS only. Follow no redirects, use bounded timeouts, and read back before retrying any write.

**Every run, in this order:**
1. `POST {base}/api/growth/engines/fulltime/attempts` with `status: started`, before reading any source.
2. `GET {base}/api/growth/engines/fulltime/directive` returns today's `next_action`, your objectives with their targets and latest values, his decisions of the last seven days, and the walls.
3. Do the work, inside the walls. The rule, word for word: "Nothing sends, posts, spends, deletes or changes a permission without a decision from Krish whose payload_sha256 matches what you are about to do."
4. `POST {base}/api/growth/engines/fulltime/reports` with header `Idempotency-Key: {run_id}`. The body is the report envelope:
   - `schema_version: "1.0.0"`, `engine_id`, `product_slug`, `run_id`, `mode`, `observed_at`, `source`, `status`
   - `objectives[]`, `activity[]`, `proposals[]`, `events[]`, `holds[]`
   - `payload_sha256`: the SHA-256 of the canonical JSON without that field, with keys sorted at every depth and no whitespace

   An unknown field is refused, never dropped. Then `GET .../reports/{run_id}` and compare the digest.
5. `POST .../attempts` again with the terminal state (`succeeded`, `failed` with a lower_snake `error_code`, or `unknown`) and `finished_at`. A terminal record never changes.
6. `GET {base}/api/growth/engines/fulltime/decisions?since={last run}` returns his yes and no, each with the `payload_sha256` it was made on. Act on a yes only when that digest equals the payload you are about to use. A changed payload is a new ask, and it goes back to him by itself when you report it.

**How proposals and readings are judged.**
- A proposal behind a wall (`spend` with its `amount_usd`, `send` or `post` with its `exact_payload`, or `strategy`) goes on Krish's one list on Home, where Clear approves it, Purge declines it and Bump defers it a day.
- A proposal inside the walls is yours to do. Control Center may pick it as your next push.
- Unknown is `value: null` with a `reason`, never zero. A measured zero is `0`.
- `mode: synthetic` is stored and read back but never touches his numbers or his list. Use it to prove your client before Krish switches you on. A live report is refused (409 `engine_inactive`) until he does.

**The wake-up.** Control Center wakes you once a day around 06:10 London with `repository_dispatch` of type `cc-growth-directive`, whose `client_payload` is `{ directive_id, engine_id }` and nothing else. Add that trigger to your workflow. If you do not run on GitHub Actions, pull the directive at the start of your own run instead; it is the same directive.

## How your old handoff maps

| Your contract | In the protocol |
|---|---|
| `report_id` (`fulltime:YYYY-MM-DD:kind`) and `revision` | `run_id` is your `report_id`, and `payload_sha256` replaces `revision` as the digest Control Center checks |
| Items with `holds[]` codes (RAIL, RELEASE, CHANNEL, CONSENT, DATA, ASSETS, APPROVAL, D1 to D7) | Ready items become proposals. Held ones become `holds[]` with the code as `reason` |
| Measures (`unique_completers`, `returners_7d`, `marketing_cash_gbp`, `model_spend_usd`, …) | `objectives[]` for the two registered ones. The rest go in `activity[]` until Krish adds them as objectives. `status: missing` or `stale` maps to `availability` with a reason |
| Weekly review (`findings`, `kill_list`, `double_down`) | A report from your Monday run. `double_down` items become proposals, and the kill list becomes `strategy` proposals for his call |
| Publication receipts (`--human-confirmed`) | `events[]` `creative_published` with the permalink |

## What you build now

1. A client for the six calls, used from your 06:15 and Monday 08:00 London automations. Pull the directive at the start of each, since you do not run on GitHub Actions.
2. A synthetic report, read back by digest.

## What you stop

- Writing `local/handoff/reporting-bundle.json` as the hand-off. Report through the protocol instead.
- Asking Control Center for a packs v2 parser or a product adapter for reporting.

## Acceptance

- A held item shows its code on Growth > Engines.
- A D-ruling proposal reaches Krish's list as his call, and his answer comes back in `GET decisions`.
