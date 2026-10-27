# Full Time growth engine v2: formats are code, runs are fill-ins

Status: approved. Ruling (Krish, 2026-10-27): "approved, do it all". Owner: Krish Raja. This is the build plan for v2; its phases are the new steps in [GET-GOING](GET-GOING.md). Where this file and the code disagree, the code and its tests are the truth and this file is corrected.

**North Star part this moves:** both halves of "most new listeners arrive because a fan shared an AI Pundit's take. This engine knows which takes travel and makes more of them". Phase 1 wires the count that is currently unmeasured (U4). Phases 1 to 4 build, and prove, the repeatable takes that travel.

---

## Context

**Why now.** On 27 October Krish asked for three things for this repo:
- the reference architecture's six rules, taken from the content-engine diagnosis;
- his growth corpus used as best practice;
- in his own words, an engine "obsessed with driving alpha testers to the app and putting out world class organic posts", that is "everywhere", and that delivers "11/10 organic creative that is WOW and viral", with voices, scripts and ad creatives that "replicate easily and reliably". Knowing what works is "CRITICAL", and he wants a full Canva brand kit.

**Where the repo really is** (read live from code, git, Actions, the synced product state and Control Center on 27 Oct; an independent review then checked the claims against the code):

| Fact | Evidence |
|---|---|
| 11 days of work: 49 commits, 12 PRs, 131 self-checks, 129 tests | git log; HANDOVER-2026-10-26.md |
| **Supply is the binding constraint.** The product has published 4 editions in 5 weeks (19 and 20 Sep, 11 and 19 Oct), each with 1 of 6 AI Pundits, and none since 19 Oct | `state/fulltime.json` rail |
| Attribution is not wired: outbound UTM tags exist (`growth.py` `tracked()`), but there is no share token, no share-to-first-listen join and no collector. `attributed_new_completers` is always reported missing | `engine/reporting.py` `objectives()` |
| The Control Center loop is green every day, in 14 to 20 seconds per run, and every run reports HOLD. Zero posts. North Star U4, unmeasured | Actions runs 1 to 10; `get_venture_state` |
| The engine sends protocol 1.0.0 and ignores amendments. Its go-live loop exists only as text. RELEASE can never open, because no code writes `marketing_release` | `reporting.py:359`; `control_center.classify`; `policy.release_open` |
| Each run re-sends five strategy asks (release, D1, D2, D3, D7). The protocol shows one ask per engine at a time and forbids a second ask of a kind that is already waiting | `reporting.py:346-351`; ENGINE-PROTOCOL.md:190 |
| The renderer accepts only `YT_` and `WEB_` IDs, at 720x1280. A creative ID cannot span channels. `change_plan` refuses any change to locks | `assets.py:95,213`; `records.py:140`; `creative_system.py:363` |
| A morning job requires 62 KB of reading, 1.7 times the 36 KB pack budget | standing-doc sweep |
| **The creative line is further along than the repo showed.** Two fictional match ads exist (AI Pundits on TV, the sofa cast; creative-system format `two_pundit_remote`). **Liverpool:** scripts v2 to v8; the v8 mid-broadcast TV mix is a listening candidate; Krish chose Epidemic cue A; the ending and the synthetic accents are unapproved; no v7 or v8 video. **Arsenal:** the stronger concept, with accepted audio; its video is held for artificial faces, lip sync, excess smiles and banter edge | origin/main `f06e900`: HANDOVER-2026-10-27-CREATIVES.md; Drive `Growth Build/00-START-HERE-FULLTIME-CREATIVES-2026-10-27.md` |
| **The private baseline is now portable.** Three hash-pinned packages are in `Growth Build` as 12 numbered parts (about 945 MB), with an index, member manifests and `assemble_fulltime_handoff.py`: creative system (265 files), ad finishing (133) and session review (58). Restore runs `standards restore` then `standards startup` on any machine | `fulltime-creative-handoff-2026-10-27.json` |
| The ad work so far ran on bespoke per-piece scripts (`build_liverpool_v6/v8_review_mix.py`, `render_review_candidates_v2.py`, `build_epidemic_ab.py`, `epidemic_mcp.ps1`), and cast voices came from ElevenLabs auditions. This is exactly the reference architecture's failure mode 5: per-job code that no gate covers | ad-finishing manifest |
| Buffer has room for 250 channels, but its 7 connected channels are Krish's personal accounts and makeyourmindup; there are none for Full Time. Canva has 9 brand kits and none for Full Time | Buffer `list_channels`; Canva `list-brand-kits` |

**The diagnosis.** The engine is all brakes and no motor. Every brake stays, rewritten as code invariants. The motor is a creative system that turns published shows into 11/10 posts with the same quality every time. Two product dependencies sit upstream of it: supply (published editions) and attribution (share tokens). Neither is in this repo, so both go out as product briefs in Phase 1.

## Krish's rulings, 27 October 2026 (record verbatim in CHANGES.md, rulings.json and AGENTS.md)

1. **Go now, with a per-take gate.** Organic brand posts may recruit pilot-beta testers before the December release. A post is eligible once the exact AI Pundit show it links to is published and its facts check out. The 4-of-6 rule applies only to posts that promote a whole match. D7 consent must be closed in the product before the first post.

   In code this is a new `ORGANIC` exception, kept separate from RELEASE so that AGENTS.md rule 4 still holds. It is in force once rulings.json records it and full-time's decision log carries the heading, which a full-time session adds through a handoff. RELEASE itself gets the R43 fix: `sync` writes `marketing_release` from the decision heading.
2. **Reserve every handle, push hardest on three.** Krish creates Full Time handles on YouTube, TikTok, Instagram, Threads, X, Facebook and a WhatsApp Channel. The engine pushes daily on TikTok, Reels and Shorts from one vertical master. The other channels get cards and text derived from it. The WhatsApp Channel is a brand broadcast that Krish posts by hand; it is not listener sharing.
3. **Krish publishes in Buffer, by hand.** This is the protocol's **`handcrafted`** mode: "prepare the exact artifact and stop. Krish sends, posts or spends himself." He switches Full Time to handcrafted in Control Center, with one click. The engine never publishes or schedules, and the go-live loop text in AGENTS.md is amended to match.
4. **Roles.** Claude does planning, strategy and orchestration. Codex does creative production and social media management (see the limits below).
5. **The 11/10 bar is built against four formats:** the remote-switch ad (the `match_ad` format; Liverpool and Arsenal are its current pieces), Pundit take clips, Pundit vs Pundit rows, and match-morning cards.
6. **Production runs on Krish's machine**, where the private baseline and Codex already live.
7. **A format is ready** when three instances, on three different matches, each get his "post it" with no edits, pass every pre-live check, and have their unit cost and time measured. The engine computes this. No session ever writes "ready".
8. **Knowing what works and what does not is critical,** so it gets its own owner, the What-Works Analyst (crew #9). That owner is not one of the makers and not the counter.
9. **A full brand kit is built in Canva** through Cowork with computer use on Krish's PC, from the brand assets in his H drive Ventures folder (Appendix A).
10. **Every asset and strategy the engine produces lives in one Growth folder** in Drive (Ventures, Full Time), and the engine is responsible for keeping it easy to find with no sprawl. The home is the existing **`Full Time/Growth Build`** folder, which Krish created on 27 Oct and which is still empty. A second "Growth" folder beside it would be the first sprawl. If he wants a separate one, he says so at approval. A tenth specialist, the Librarian, owns this (section 2a).

AGENTS.md lines amended to match these rulings:
- rule 3 (per-take);
- "first public channel is branded YouTube" (push three);
- "no paid generation", which becomes credits within placements, behind `spend`;
- the Autonomy section (handcrafted for posting);
- the `automations.json` prompts, which keep scheduled runs generation-free.

11. **Brand match ads may link to Today**, even when that match has no published show. This widens ruling 1 for `match_ad` only. Two invariants keep it honest:
    - the ad's words never claim a show exists for its match;
    - Today must carry at least one published AI Pundit show at post time, checked live; otherwise the ad is held, so a tap never lands on "No match to cover today".
12. **Each format goes live on its own readiness.** `take_clip` or `morning_card` can start posting while `match_ad` is still working toward its bar.
13. **A social growth specialist, the Audience Builder (crew #11),** works relentlessly on brand-profile visibility and followers, Full Time brand profiles only.
14. **"Automate within platform rules."** Official APIs only, actions each platform allows, every action type ruled by Krish first in `engagement-actions.json`; follow or unfollow automation, mass liking, unsolicited DMs, follow-for-follow, engagement bait and bought followers are banned in code.
15. **Google Analytics comes from Control Center** ("just get google analytics data from control center, much easier", superseding the direct read the same day): the daily directive carries the week's landings once Control Center builds the read (`briefs/2026-10-27-control-center-measurement.md`); `engine/ga4.py` stays as an unused fallback.

Public copy keeps the product's term, "free pilot beta".

## Where I differ from Krish's split (he asked)

I agree that Codex owns creative production and social media management, with three limits:

1. **Codex never touches the network or connectors.** Its sandbox has no network and no MCP. Codex fills script slots, runs FFmpeg offline and builds the Buffer-ready pack (per-channel captions, AI labels, times, tracked links). Every connector or network call goes through local Claude Code on Krish's machine or the stdlib CLI, and is logged per step: Canva, Higgsfield, Runway, Epidemic, product fetches and the read-only Buffer analytics. No writes to Buffer or any platform, and no replies, comments or DMs.
2. **Codex's allowance goes on creative work, not plumbing.** The allowance is shared and at 100%. Production runs execute compiled recipes, minutes per matchday rather than hours. Engine plumbing is built by fresh Claude Code sessions in worktrees while Codex is above 80%.
3. **Nobody certifies their own creative.** A fresh-session lens reviewer scores the work, and only Krish's verdict promotes. This is already code: `test_model_review_cannot_promote_creative`.

Production uses the **main checkout** with `--require-existing-history`, because `History.read()` returns an empty ledger when the file is missing (`records.py:67`). Worktrees are for build cards only.

---

## 1. The run spec: the one artefact Krish signs

There is one **weekly campaign spec** per matchweek (Monday to Sunday, London time). It arrives as a `stage: "plan"` proposal behind `strategy`, with the spec as `exact_payload`. Krish's Clear decision binds `payload_sha256`, which the existing `reporting.canonical()` and `seal()` already compute. The schema and a synthetic example are tracked in git. Signed copies live in `local/specs/`. It carries judgment only:

| Field | Type and meaning |
|---|---|
| `run_id`, `window` | `fulltime:YYYY-Www`; start and end in Europe/London |
| `mode` | `proof` or `live`. `live` is refused unless the format is ready, ORGANIC and D7 are in force, and the brand identity is verified |
| `objectives[]` | `share_arrived_new_listeners` (the North Star, with this week's ladder target), `brand_post_new_listeners` (alpha testers from brand posts) and `marketing_cash_gbp` (0). The existing `attributed_new_completers` key keeps reporting until Control Center registers the new keys (handoff) |
| `fixtures[]` | `fixture_ref`, clubs, `rivalry`, `rank` (computed by the Match Clock; Krish may strike one) |
| `formats[]` | `format_id`, `lock_version` (a hash pin), `max_per_matchday`, `channels[]`, `pundits_allowed[]` |
| `channels[]` | channel, role (push or derived), `identity_ref`, `cap_per_day` |
| `experiments[]` | ID, arm unit (matchweek or match, never sharer), metric, stop rule |
| `learnings_applied[]` | IDs from the learning register that the week's choices rely on |

Budgets and invariants are config (`engine/config/budgets.json` and `invariants/registry.json`). They are not judgment, so they are not signed. Credits go in a separate weekly **`spend`** proposal with `amount_usd`, which the protocol requires; Phase 0 measures the price per credit from receipts. The compiler refuses a spec that names an unregistered format, a channel outside the allowlist, or a mode its gates do not support.

## 2. Repo structure (additive only)

```
specs/      campaign.schema.json, examples/synthetic-week.json
formats/    <format_id>/recipe.schema.json, slots.schema.json   (public skeleton; locks stay in local/creative-system/)
crew/       <specialist>/card.md (3 KB max), lens.md (1 KB max)
invariants/ registry.json   (every R## item, doc-only rule and GET-GOING step mapped to code and test)
tasks/      <card_id>.json  (task cards, 6 KB max)
engine/     spec.py, formats.py, pack.py, session.py, dispatch.py, attribution.py,
            learning.py, buffer_read.py, crew/<specialist>.py, config/budgets.json
scripts/    baseline.py
docs/       ENGINE-V2.md, FAILURE-REGISTER.md (R01 to R45 filed), GET-GOING.md (new steps)
```

**New CLI verbs** (stdlib, offline-first, in `engine/`):
As built (27 October; `python3 growth.py --help` lists them all):
- `spec check|digest|compile|propose`
- `formats list|readiness|lock`
- `pack check|propose`
- `session pack|minutes --kind K`
- `dispatch CARD`
- `invariants check`
- `actions`, `fixtures fetch|import|show`, `buffer query|receipts`, `library name|reconcile|canva|stamp|bundle|assemble`, `audience actions|plan|followers`, `ga4 doctor|report|authorize`

Proof runs use `pack propose` in proof mode; their verdicts come back through `gates.settle`, so no separate `proof` verb was needed.

Every existing command keeps working unchanged as the fallback until v2 has run one full real matchweek.

**CI refuses:**
- a card over 3 KB, a lens over 1 KB, a task card over 6 KB, or a session pack over 36 KB;
- code under `specs/` or `formats/`;
- a run that names an unregistered recipe, which is how "no per-run bespoke code" is enforced;
- an invariant whose test does not exist and pass.

CI also gains a **Windows job**.

## 2a. The Growth library in Drive: one home, no sprawl

Git keeps public code, schemas and the public plan. `local/` stays the working cache and ledger. **`Full Time/Growth Build` in Drive is the private, canonical store for everything the engine produces.** Its tree is fixed, and numbered the same way as Krish's `00_Brand-Assets`:

```
Growth Build/
  00_START-HERE/   START-HERE.md (the map, the rules, links to this week)   INDEX.csv (one row per file)
  01_Strategy/     <YYYY-Www>/   signed spec, check-in, weekly report, briefs, plan mirrors
  02_Formats/      <format_id>/<lock_version>/   the lock card and approved reference instances
  03_Runs/         <YYYY-Www>/<YYYY-MM-DD>_<home>-<away>/   instances, pack.json, review.json
  04_Learning/     register.csv (current)   <YYYY-Www>/ learning report, what works and what doesn't
  05_Brand-Kit/    the Canva kit receipt and template IDs (brand assets stay in 00_Brand-Assets, never copied)
  06_Reference/    baseline, rulings snapshot, backups/<date>/ (verified private bundles),
                   creative-handoff/2026-10-27/ (the previous session's 12 parts, index, manifests, assembler, START-HERE)
  99_Archive/      <YYYY-Www>/   rejected or superseded items, moved at week close, never deleted
```

**Adopting what is already there.** The previous session's 17 files sat at the root of Growth Build. On 27 October they moved together, unrenamed, into `06_Reference/creative-handoff/2026-10-27/`. Drive file IDs survive a move, and the handoff JSON identifies every part by ID and SHA-256, so restore keeps working. The new `00_START-HERE/START-HERE.md` links to that folder first, and the repo's HANDOVER-2026-10-27-CREATIVES.md and NOW.md get a one-line pointer update in the same PR. Their numbered-part method and `assemble_fulltime_handoff.py`, which exist because the Drive connector caps uploads at 100 MB, become the Librarian's backup component (`library bundle|assemble`), with tests.

**Rules, enforced in code** (`engine/library.py`; `growth.py library name|reconcile|canva|stamp|bundle|assemble`):
1. **One writer.** Only the Librarian files into Growth Build. Every other specialist hands its output to the Librarian.
2. **Fixed tree.** The numbered folders above are the only ones allowed, nothing sits at the root, and the depth is 4 or less. An ad-hoc folder is refused.
3. **Names in one pattern.**
   - Instances: `<YYYY-MM-DD>_<format>_<pundit>_<home>-<away>_<channel>_<creative_id>.<ext>`.
   - Strategy: `<YYYY-Www>_<kind>_v<n>.<ext>`.
   - Lowercase ASCII and hyphens only. Anything else is refused.
4. **Every file has exactly one `INDEX.csv` row, and every row has its file.** The row holds:
   - path, kind, week, match, format, AI Pundit, channel;
   - status: draft, reviewed, verdict or posted;
   - SHA-256;
   - source: a repo commit or a creative ID.

   A file whose SHA-256 is already filed is refused, and the existing copy is linked instead.
5. **Never overwrite, never delete.** A new version is a new `_v<n>` file. At week close the old version and any rejects move to `99_Archive`.
6. **Never change sharing or permissions, never write outside Growth Build, and read `00_Brand-Assets` read-only.**
7. **Weekly reconcile** (inside the Monday run):
   - files outside the tree, orphans, duplicates and misnamed files must all be **zero**, or a `LIBRARY` hold leads the report;
   - START-HERE's "This week" links are refreshed.
8. **Canva mirrors the tree.** The existing Full Time Canva project folder gets `Growth/Templates` and `Growth/<YYYY-Www>`, with the same names, and is reconciled the same way.
9. **Single source per artefact.**
   - Public docs, including this plan: git is the source, and the Drive copy carries a `source: <path>@<commit>` stamp.
   - Private assets: Drive is the source, and `local/` is a cache.
   - Each week a verified private backup goes to `06_Reference/backups/`: the history ledger plus `standards export`. This removes the single-machine risk to the private baseline.

**Mechanics.** On Krish's PC the H drive is assumed to be Google Drive for Desktop. Phase 0 verifies this. If it holds, the stdlib CLI copies files into the mounted path, at zero tokens, and Claude reads back through the Drive connector (`search_files` by `parentId`) to check names, sizes and the index. In the cloud, the Drive connector writes directly.

## 3. The crew: eleven specialists

Each specialist has:
- a lint (zero tokens) before acting;
- a measured check after acting, from real data;
- a card (3 KB maximum), loaded only when its format or channel is in play;
- a lens (1 KB maximum) for the independent reviewer.

Lints reuse existing code.

| # | Specialist (who runs it) | Lint before acting | Measured check after acting | Lens question |
|---|---|---|---|---|
| 1 | **Product Truth** (CLI) | Sync under 26 h old with no STOP; the linked edition is published per `/api/public/drops/{drop}/variants/{pundit}` (`assets.fetch`, `freshness`) | Each pack link returns 200 and the right AI Pundit at pack time, and again at review time | Does every claim and link point at something live now? |
| 2 | **Match Clock** (CLI) | Fixtures refreshed today (API-Football); windows anchored to the product's publish, not the final whistle | Minutes from publish to pack ready | Is this the match fans are arguing about? |
| 3 | **Take & Script Writer** (Codex fills, Claude ranks) | Exact transcript quote and the 62 copy checks (`problems()`); traced to a match fact | Pre-live: Krish's verdict per item. Live: sends and shares per asset | Would a fan send this exact line to one named mate? |
| 4 | **Voice Lock** (Codex) | Voice ID and settings match the pinned lock hash; AI disclosed audibly within 5 s; a human listening verdict exists for the source audio | Krish's listening verdict; live completion rate | Without the script, does each voice sound like itself and alive? |
| 5 | **Motion Maker** (Codex offline; Claude calls Higgsfield and Runway) | Renderer checks (hashes, quotes, bounds, captions, label); credits within the approved `spend`; stills before video; a full video refused without a passed realism proof (R47); for posting, Today live at post time (ruling 11); a generation record | ffprobe and output hashes; caption alignment from Krish's verdict (no longer self-declared); live 3-second hold | Muted, then with sound: does the first second stop the thumb? |
| 6 | **Card Maker** (Claude through the Canva connector) | Pinned brand template; "AI Pundit" visible; no league or broadcaster marks; dimensions per channel | Export hash and dimensions; the text read back from the design equals the slot text, with every glyph present (R19) | At thumbnail size, does a ten-year-old get it in one second? |
| 7 | **Channel & Pack Steward** (Codex builds; Claude reads Buffer) | Targets in the Full Time allowlist only (personal and makeyourmindup channel IDs refused; IDs held in ignored `local/`); identity verified within 30 days; rules re-checked within 90 days; AI labels set; caps; never the same asset twice on one channel | Read-only Buffer readback of Full Time channels: the post matches the pack's caption hash and creative ID, giving a permalink receipt (`History.mark`) | Is it native to its platform, or a cross-post? |
| 8 | **Measurement Analyst** (Claude): counts the number | Every link carries its creative ID (`tracked()`); every export is an aggregate with no person-level fields | Weekly counts with a Poisson 95% interval from the product export (share-token arrivals, brand-post arrivals by creative ID); Google Analytics 4 landings by creative ID (property G-W2QL8RKFJ1, page views only, read-only, from Control Center's directive, ruling 15) as a leading web signal that never counts as listeners; untokenised arrivals reported separately | Would this number survive "how was it counted"? |
| 9 | **What-Works Analyst** (Claude, a fresh session, never a maker): owns what works | A claim is "confirmed" only after pre-registration, no overlapping test, **at least two matchweeks and at least 20 events per arm**, and \|z\| of 2 or more with z = (a−b)/√(a+b). Anything less is "directional" | Weekly learning report. Pre-live: which of Krish's edits and rejects repeat, and why. Live: format, AI Pundit, hook, channel and time against the control. Then the kill and double-down list | What would we stop doing tomorrow, and what evidence flips it? |
| 10 | **Librarian** (CLI files; Claude reads back): owns findability | Name matches the pattern, path is inside the fixed tree, not a duplicate SHA-256, index row prepared | Drive and Canva readback equals the manifest; reconcile finds zero files outside the tree, zero orphans, zero duplicates and zero misnamed files | From START-HERE, can Krish find this in ten seconds? |
| 11 | **Audience Builder** (Claude plans; Codex prepares profile copy; automated only through an approved official-API adapter): owns brand-profile visibility and followers | `engine.audience.gate`: the action type is approved by Krish's ruling, has an official API, a rule check within 90 days, a brand allowlisted account and room under its daily cap; banned types refused | `engine.audience.followers_check`: weekly followers and profile visits per brand channel, missing distinct from zero; a diagnostic of reach, never the North Star | Would a fan who lands on this profile follow it within three seconds, and why? |

**The learning register** (`learnings` in `local/engine/history.json`; exported each week to `Growth Build/04_Learning/register.csv`, immutable and versioned like experiments) is the Assumption Ledger in code. Each entry holds:
- the claim;
- the signal;
- `n` and the interval;
- a status: directional, confirmed or refuted;
- the flip rule;
- `applied_to`.

It reads only measured checks, Control Center decisions and read-only Buffer analytics on Full Time channels. It feeds three things:
- the Writer's ranking;
- new **lock versions**;
- the next spec's `learnings_applied[]`.

Its kill and double-down items become weekly `strategy` proposals through the existing `reporting.kill_proposal`. Statistics on audience data start with the first live post. Before that, the register holds verdict analysis only.

**The four format locks.** Each lock is a versioned recipe compiled from the pinned creative release, containing:
- templates;
- voice locks;
- style modules;
- a slot schema;
- render steps;
- per-channel cuts;
- caption rules;
- measured unit cost.

A run only fills slots. One 1080x1920 master gets a creative ID per channel, all linked by a `master_id`, because `records.py:140` forbids one ID across channels.

**A lock change is a new lock version.** It goes through `artifact_gate`, then owner `promote`, and restarts that format's streak. `change_plan` stays as it is: it refuses lock edits by design.

| Format | Built from | Can run now? |
|---|---|---|
| `take_clip` | Published audio plus the AI Pundit's cover (the existing renderer, widened) | **Yes:** 4 editions on 4 matches exist |
| `morning_card` | Full Time Canva templates | **Yes**, on the same editions |
| `row` | Two published AI Pundits on one match | **No** until a match has 2 published |
| `match_ad` (the remote-switch line; creative-system format `two_pundit_remote`) | Today, the private ad-finishing package: scripts, cast voices, Epidemic cue A, and the v8 TV-mix builder. Next, a lock compiled from the accepted Liverpool and Arsenal pieces: fact check, rivalry beat map, cast and voice record, TV audio template, short realism proof, captions, call to action, cost, gates | **Yes, the creative track:** Liverpool v8 listening, then both concepts through review. Links to Today (ruling 11). A full video needs an approved `spend` and a passed realism proof |

**Readiness is computed from pre-live checks and Krish's verdicts only.** In proof mode nothing is posted, so proof verdicts on the 4 existing editions count. Posts about old matches are never made: "a take that misses its window is archived".

## 4. Checks mapped to the repo's own failure history

`docs/FAILURE-REGISTER.md` and `invariants/registry.json` file **all of** the following, each with the code that enforces it and the test that proves it:
- R01 to R45;
- the 22 rules that exist only as documents;
- GET-GOING steps 0 to 5.

**Steps:**
- Step 0 (status line): Phase 0.
- Step 0.5 (media credits): the weekly `spend` proposal.
- Step 1 (autonomy loop): superseded by ruling 3, and recorded as such.
- Step 2 (rulings): Phase 0.
- Step 3 (attribution): Phase 1.
- Step 4 (rail diagnosis): Phase 1 product brief.
- Step 5 (hosted-task prompts): Phase 1, R44.

**Kept as regressions, untouched:** R02, R05, R06, R07, R09, R13, R14, R15, R18, R20, R22, R23, R25, R26, R27 and R36 to R40.

**New code:**
- R01: per-take gate test, with the whole-match 4-of-6 kept.
- R03: D2 and D5 timing conditions become lints.
- R04: costs only from the measured ledger.
- R10: sender-domain check on every pack address.
- R19: glyph readback.
- R21: a missing scheduled slot is reported.
- R24: the client sends 1.1.0 (stages; 1.2.0 only if `subject_ref` is used), and the stand-in serves 1.0 to 1.2 and refuses 2.x.
- R29: listening-verdict lint.
- R30 and R41: the video gate, now a passed realism proof plus approved `spend`, never a new full-video iteration just because a session started.
- R31: NOW.md state-block validator.
- R32 to R34: static check.yml assertions.
- R35: UTF-8 on every `read_text`, plus the Windows CI job.
- R42: switch events kept out of comparison metrics.
- R43: `sync` writes `marketing_release` from the decision heading.
- R44: automation prompts name "the newest HANDOVER".
- R45: front-matter paths verified.

**Recorded as product-side or owner items** (they cannot be tests here): R08, R11, R12 (public playbook exposure: an open owner decision), R16, R17, R28.

**New from the 27 Oct creative handover:**
- R46: mixes that came out too dark, too late, too quiet or too loud. The TV audio template's entry time, level curve and cue ID are locked parameters, with tolerance tests.
- R47: video rejected for artificial faces, lip sync, excess smiles and banter edge. A full video is refused without a passed realism proof and an owner visual verdict.
- R48: the Drive upload cap of 100 MB. Handled by the numbered-part bundle and assembler, with tests.
- R49: Drive bytes not hashed remotely. Readback downloads and hashes each part.
- R50: bespoke per-piece builders. Ported into the library, then refused by CI.

**Document-only rules made code:**
- creative-bar evidence (doctrine, at least two alternatives, why this one wins), schema-checked;
- one ask at a time, with ruling asks retired once ruled;
- declines and amendments written to history;
- Krish's minutes summed per day, at 20 or fewer;
- a clean git tree in scheduled runs;
- hashtags from 2 to 5;
- a generation record for every generation;
- media bound by hash.

**Judgment that stays human:** the 11/10 verdict, humour, natural faces, lip sync.

**New hard invariants:**
- no Buffer or platform write verb exists; a test blocks write endpoints;
- the Buffer reader is allowlist-only;
- Krish's personal posts are never inspected;
- every `exact_payload` carries the SHA-256 of each rendered file and Canva export, and stays within the protocol's 8,000 characters and 12 evidence links;
- library rules 1 to 9 (section 2a), each with a test. That includes a "sprawl" test that plants a stray folder, a misnamed file and a duplicate, and expects all three refused or reported.

## 5. Session protocol and gates

| Session kind | Who | Pack | Budget (provisional; Phase 0 calibrates) | Ends at |
|---|---|---|---|---|
| Scheduled run (06:15, Monday 08:00, 05:10 UTC dispatch) | CLI | none | 0 model tokens; 2 min or less | report |
| Orchestrator | Claude, fresh | 36 KB or less | 150k tokens or less, 20 min or less | a gate |
| Production, per matchday (started on demand from Krish's machine; not a third automation) | Codex in the main checkout (any machine after a verified restore from `06_Reference/creative-handoff`), with Claude for connector calls | instance file and locks | 30 Codex minutes or less; pinned model | pack ready |
| Independent review | Claude, a fresh session that made nothing | lenses, the COPY.md rubric, a contact sheet | 60k tokens or less | 38 of 48 or more, Ethics and Action both at 4, two alternatives |
| Build | Claude or Codex, from a card | the card's 5 or fewer read files | per card | acceptance exits 0 |

- **The pack** (`session pack`, which refuses anything over 36 KB) holds:
  - `ENGINE.md` (6 KB or less, an index; AGENTS.md, COPY.md and the creative system stay untouched);
  - the signed spec;
  - the cards in play;
  - open findings;
  - gate status;
  - the last report.
- **Gates, all on Krish's list, one ask at a time:**
  - **G1 (Monday):** the weekly spec as a `plan`, with last week's check-in folded in, then that week's `spend`.
  - **G2 (each matchday):** one `post` proposal (handcrafted) whose `exact_payload` lists every item: creative ID, channel, caption, link and media hashes, with review links to Canva and a private Drive folder.
    - Clear means "post it" for every item.
    - Purge means reject every item.
    - Change it first gives a verdict per item, by diff: an unchanged item is "post it", an edited one is an edit, and a removed one is a reject. An optional `note` per item carries his reason, and the next draft reads it.
    - It closes with `creative_published` events (existing).
  - **Standing asks:** D2, D3 and D7 stay asks until he rules; D1 and release retire when ruling 1 is recorded.
- **No questions mid-turn:** they go into `open_questions[]`, and the session ends at the gate.
- **A ledger** (`local/engine/sessions.jsonl`) records kind, tokens, calls, engine minutes and minutes waiting on Krish, from proposal and decision timestamps.

## 6. Codex task-card dispatch

- **Card fields** (JSON, 6 KB maximum):
  - `executor`;
  - `model`, pinned to `gpt-6.1-sol` and never inherited (the default `gpt-6-astra` burns 2 to 2.6 times faster);
  - `effort`, pinned (medium);
  - `max_minutes` and `max_calls`;
  - `worktree`, for build cards only;
  - `write_allow`;
  - 5 or fewer `read_files`;
  - a `never` list: git, network, MCP, publishing, new dependencies, writes outside `write_allow`;
  - the `interface`, verbatim;
  - `acceptance`;
  - the `return` shape.
- **Dispatch:**
  - `node <plugin>/scripts/codex-companion.mjs task --background --fresh --write --model <pinned> --effort <pinned> --cwd <dir> --prompt-file tasks/<id>.md`
  - Then `status --wait` and `result`. Long jobs use `codex exec`.
  - Never codex-rescue.
- **Allowance guard:** `dispatch` refuses above 80% or when the reading is unknown, unless `--spend-approved <decision_id>` names a Control Center spend decision. The reading comes from a helper that captures Codex's reported usage. If Codex reports none, the reading stays unknown, so every Codex card needs a spend decision until the reset.
- **Verification:** Claude reruns the acceptance commands outside the sandbox and checks that the diff stays inside `write_allow`. Codex's report is never evidence.

## 7. Tool routing (Control Center placements, 26 October)

| Tool | Placement | Use |
|---|---|---|
| Canva | main: full_time; "zero limits" | Brand kit via Cowork (Appendix A), then all cards through `autofill-design` when `get-brand-template-dataset` returns the fields; fallback `copy-design` plus `edit-design`; readback with `read-design`; `export-design` hashed |
| ChatGPT Images | ruling of 27 Oct: publication stills | New still imagery only where product art is not enough |
| Higgsfield / Runway | some: full_time | `match_ad` only: stills first, then a short realism proof, then full video only after the proof passes, behind the weekly `spend` (still 2.75 credits, Seedance clip 210) |
| Epidemic Sound | main: full_time | Music for own channels (Creator plan); recording ID per asset |
| Buffer | Krish publishes | Read-only, on the Full Time allowlist |
| API-Football, football-data.org | main: full_time | Fixtures and facts |
| Supabase, Vercel | product | Read-only, through the product export and deploy readback |
| Google Drive | the canonical private store | `Full Time/Growth Build` (section 2a), filed by the Librarian; G2 review links point into `03_Runs` |
| ElevenLabs | main: Mindmake (Krish's clone); unplaced for Full Time | Already used for the ads' cast auditions and takes. Kept to stock or designed cast voices, with voice IDs locked in the `match_ad` cast record, and never Krish's clone. Show audio stays the product's own |
| HeyGen | main: Mindmake | Not used |
| Instantly, Apollo, Fireflies, Descript | retired | Never |

## 8. Phased build, acceptance and the 20x target

**Phase 0: baseline, inventory, rulings, brand kit (27 to 28 Oct).**
- `scripts/baseline.py` measures **build** and **run** separately, from:
  - git and PR timestamps;
  - Actions durations;
  - Codex logs and Claude Code transcripts on Krish's machine.

  It reports tokens, calls, mean context, engine minutes against waiting minutes, and outcomes.
- On Krish's machine:
  - `standards startup`;
  - `history --backups` (lose nothing);
  - the Codex plugin path;
  - Windows FFmpeg font handling;
  - the price per credit.
- Record rulings 1 to 12 and the AGENTS.md amendments, and send the full-time decision-log handoff.
- Move the previous session's handoff set into `06_Reference/creative-handoff/2026-10-27/`. Download one part, hash it, and match it against the index; this closes the "remote bytes not independently checked" gap.
- Krish runs Appendix A in Cowork and switches Full Time to handcrafted.
- Create the Growth Build tree and START-HERE, using the Drive connector in his own folder. This is a folder and file write, so it happens only after plan approval. Then file this plan's mirror in `01_Strategy/2026-W44/`. Verify that the H drive is the Drive for Desktop mount.
- **Accept when:**
  - the baseline JSON exists from real logs, or is marked a lower bound;
  - private state is located;
  - rulings are recorded with their tests;
  - `list-brand-kits` shows "Full Time" with the source colours and fonts;
  - `get-brand-template-dataset` returns the 7 fields, or the fallback is recorded;
  - the Drive readback shows the fixed tree, START-HERE and an `INDEX.csv` that reconciles to zero findings.

**Phase 1: product briefs, engine truth, proof zero (by 2 Nov).**
- **Briefs to full-time**, each to a full-time session once Krish approves:
  - `briefs/2026-10-27-share-attribution.md`:
    - a share action minting `?s=<token>`;
    - first touch joined to the first `listen_completed` within 7 days;
    - a recipient preview that keeps the saved choice;
    - per-edition og meta;
    - a weekly aggregate export with `query_ref`;
    - D7 closed, with counsel.
  - `briefs/2026-10-27-rail-supply.md`: GET-GOING Step 4, the rail diagnosis from stored verdicts, and why nothing has published since 19 Oct.
- **Engine:**
  - `attribution.py`, with a contract test against the export spec;
  - protocol 1.1.0;
  - the R43 and R44 fixes;
  - ORGANIC;
  - regression tests for every gap.
- **Proof zero:** with the *existing* renderer and the 4 published editions, make `take_clip` instances, review them independently, and send them as G2. Nothing is built mid-run and nothing posts. Krish's first verdicts start the learning register.
- **The creative track** (from day 1, in parallel, picking up the 27 Oct handover's single next action):
  1. Krish listens to the whole Liverpool v8 mix as the first G2. Make only the smallest corrections the listening supports.
  2. Bring both concepts through full ear, phone-size visual and owner review.
  3. Run a short realism proof (behind `spend`) before any full video.
  4. **Turn the bespoke builders into library parts:** Codex cards port the v8 mix builder, the review-candidate renderer and the Epidemic fetch into `engine/formats/match_ad/`. Each card's acceptance is that the ported code **reproduces the existing v8 mix and v4 review cuts byte for byte from the same inputs.** CI then refuses new per-piece scripts.
  5. With both concepts accepted, compile them into lock v1, and make the first test on a second game.
- **Accept when:**
  - the suites pass on Linux and Windows;
  - the join is proven against the spec on synthetic data;
  - the report shows each objective measured, or "blocked on product" with its brief;
  - the first G2 verdicts are recorded.

**Phase 2: spec, crew, locks, templates (by 9 Nov).**
- Schema and compiler; `invariants/registry.json`, mapping every item; the ten crews and the learning register; `engine/library.py` with its sprawl tests; the session-pack builder; dispatch with the guard; the Buffer reader.
- Code edits, each with tests:
  - renderer prefixes for every channel, a 1080x1920 master and `master_id`;
  - `PLATFORMS` and `BRAND_CHANNELS` gain threads, facebook and whatsapp_channel;
  - explicit font files and `fontsdir` for Windows.
- Lock skeletons for `take_clip`, `morning_card` and `row`, plus `match_ad` lock v1 once the creative track accepts both concepts. The six Canva templates.
- **Accept when** `invariants check` passes in full, the size CI holds, and a synthetic week compiles and digests the same way twice.

**Phase 3: proof on all available formats (from 9 Nov).**
- `take_clip` and `morning_card` run on every new edition.
- `match_ad` lock v1 runs on each week's biggest rivalry, linking to Today.
- `row` starts as soon as a match has two published AI Pundits.
- **Accept when** readiness is computed from real verdicts and the first format reaches three in a row.

**Phase 4: live, per format.**
- The handles exist and are connected to Buffer; identity is registered; ORGANIC and D7 are in force; the format is ready.
- Packs say "post in Buffer", and receipts come from the Buffer readback. TikTok, Reels and Shorts are pushed daily, with derived cuts elsewhere. The old route keeps running in parallel for one full matchweek.
- **Accept when** the first permalink receipt is recorded and the first weekly number is measured with its interval.

**The 20x target.**
- Run cost per owner-reviewed instance (tokens and engine minutes) falls to a twentieth of the Phase 0 *run* baseline.
- Build cost is reported separately. Krish's minutes stay at 20 a day or fewer, and waiting time is kept separate.
- With no reproduced baseline, there is no 20x claim.

## Where the North Star lands (honest read)

- This week's 5 and 16 November's 49 will probably be missed. Attribution and supply both wait on product work, and posting waits on readiness. The report will say U4 heading for U5, plainly.
- What moves fastest:
  - the Liverpool v8 listening verdict;
  - proof zero this week on the existing editions.

  Then the first format can be ready the moment D7 lands and Today has a live show.
- **Krish's actions:**
  1. Approve this plan.
  2. Switch Full Time to handcrafted.
  3. Run Appendix A.
  4. Create handles on **YouTube (a Brand Account), TikTok and Instagram (Business)** first, then reserve Threads, X, Facebook and a WhatsApp Channel. Use one handle everywhere and a brand inbox, never his personal email, and connect them to Buffer.
  5. Listen to Liverpool v8.
  6. Approve the two product briefs and the D7 counsel check.
  7. Answer G2 within 20 minutes a day.

## Verification

- **Every phase:** `python3 growth.py --self-test`, `python3 -m unittest discover -s tests -v` and `python3 scripts/verify_repository.py`, on Linux and Windows.
- **New:**
  - `growth.py invariants check`;
  - `growth.py spec check specs/examples/synthetic-week.json`;
  - `growth.py session pack --kind orchestrator --check`;
  - `growth.py formats readiness` against stand-in decisions.
- **End to end:**
  - proof zero on a real edition;
  - G2 through the stand-in, then live;
  - an amended payload diff that updates the per-item streaks;
  - the Buffer reader refusing synthetic personal IDs;
  - a fresh live held run with an exported bundle.
- `verification-loop` checks observable evidence after each phase. Prose is not evidence.

---

## Appendix A: the Cowork prompt for the Canva design system

The prompt Krish runs in Cowork on his PC is filed as [briefs/2026-10-27-cowork-canva-brand-kit.md](../briefs/2026-10-27-cowork-canva-brand-kit.md). The Canva folder `Full Time / Growth / Templates` already exists for it, and the receipt lands in `Growth Build/05_Brand-Kit`. Once the kit and templates exist, Claude tags the autofill fields through the Canva connector and verifies them with `get-brand-template-dataset`.
