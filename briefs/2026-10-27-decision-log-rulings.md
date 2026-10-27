# Brief for full-time: record the organic per-take ruling in the decision log (27 October 2026)

For a full-time session, once Krish approves. Growth does not change the product; this is the handoff that puts two of his rulings into force.

## Why

Growth reads its rulings from `rulings.json`, but a ruling is in force only when full-time's decision log (`docs/12-roadmap.md`, `## Decision log`) carries its heading, because the product owns what may be said about it (AGENTS.md, ruling 1). Krish approved D1 and ORGANIC on 27 October 2026. Until the heading exists, `growth.py sync` reports both as approved but not in force, the per-take gate stays shut, and only whole-match posts at four of six AI Pundits could ever pass.

## What to add

One heading in the decision log, newest first, exactly:

```
### 2026-10-27 - Organic brand posts may recruit pilot testers before release, per-take gate
```

Under it, in the log's usual style:

- **Ruling (Krish, 2026-10-27):** "Go now, per-take gate (Recommended). Reserve all, push three (Recommended)."
- **What it allows:** an organic Full Time brand post may recruit pilot-beta testers before the December release once the exact AI Pundit show it links to is published and its facts check. Promoting a whole match still needs four of six AI Pundits.
- **What it does not change:** the release decision, paid acquisition, the product's own copy, or consent. D7 (PostHog and Google Analytics consent, with counsel's check per `docs/11-legal.md`) must close before the first public post.

## Accept when

Growth's next `python3 growth.py sync` shows D1 and ORGANIC as in force in `state/FULLTIME-NOW.md` ("Rulings the playbook needs"), and the per-take gate line reads OPEN when a published show is on the rail.
