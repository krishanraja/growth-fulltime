# Matchday runbook: from a published show to Krish's G2 ask

Status: current, 27 October 2026. One matchday, step by step, on Krish's machine
(ruling 6). Nothing here posts, sends, schedules or spends: the last step is an
ask on Krish's list, and he posts by hand in Buffer (ruling 3).

## Before the first matchday (once)

- Python 3.9+, FFmpeg and FFprobe on the path; Node 22.6 or later with Playwright
  (`npm i playwright` in this repository, then `npx playwright install chromium`;
  `.gitignore` keeps `node_modules/` and the npm files out of git); network to
  Google Fonts and fulltime.fm.
- A checkout of `krishanraja/full-time` beside this one (`../full-time`), for the
  kit's art: `node brand/social-kit/prepare-assets.mjs ../full-time`.
- Persistent history in `local/engine/history.json` (never start a fresh one).
- `local/buffer-channels.json` for the receipts step, once the channels exist.

## The week (Monday, `jobs/weekly.md`)

1. `python3 growth.py fixtures fetch` (or `fixtures import FILE` with Control
   Center's football-data reply). Derbies rank first.
2. Pin each format's lock: `python3 growth.py formats lock --format take_clip`
   prints the `lock_version` (the recipe plus the renderer version). Put it in the
   spec's `formats[]`. A spec that says `"unlocked"` can never earn readiness.
3. Write the spec from `specs/examples/synthetic-week.json`, then
   `python3 growth.py spec check FILE` and
   `python3 growth.py spec propose FILE --expires-at <Sunday 23:59 London> --queue`.
   Krish signs it as G1; the signed copy lands in `local/specs/<week>.signed.json`.

## The matchday

1. **A show is published.** `python3 growth.py sync`, then
   `python3 growth.py assets fetch --drop <drop> --pundit <id>`. This writes
   `local/assets/<drop>/<pundit>/source.json` with the audio, cover and the
   **published transcript**: every quote and caption comes from it, word for word.
2. **Choose the take** (crew/take_writer): one line a fan would send to one named
   mate, 90 characters at most, exact from the transcript, passing COPY.md's take
   test. Note its start and end seconds in the audio.
3. **The instance** (`local/takes/<name>.json`): the shape is in
   `brand/social-kit/README.md`, "A take_clip". `shows` lists every AI Pundit
   published for the match (from the rail), captions are clip seconds and together
   equal the quote, `sample: false`.
4. **The layers:** `node brand/social-kit/take_clip.js local/takes/<name>.json`
   writes `local/brand-kit/layers/<name>/`.
5. **The creative ID**, one per channel (ruling 2: one master, one ID each):
   `<PREFIX>_<GOAL>_<FORMAT>_C<nn>_H<nn>_V<n>_<YYYYMMDD>`.
   - Prefix by channel: TikTok `TT`, Instagram Reels and feed `IG`, YouTube Shorts
     `YT`, Threads `TH`, X `X`, Facebook `FB`, WhatsApp Channel `WC`.
   - Goal: `CLASH`, `PROOF`, `TRIBE`, `BUILD`, `GAME` or `HABIT`. Format word for a
     take clip: `CLIP` (TikTok, Reels) or `SHORT` (YouTube).
   - Example: `TT_CLASH_CLIP_C01_H01_V1_20261101`. `master_id` ties the cuts together.
6. **Render:** copy `examples/clip-manifest.json` to `local/takes/<name>.manifest.json`;
   set `creative_id`, `drop_id`, one segment matching the instance's audio,
   `"size": "1080x1920"`, `"layers"` and `"instance"`. Leave
   `caption_alignment_verified` false: the render carries an ASSETS hold until Krish
   judges it, and his no-edit "post it" in G2 is the caption verdict (crew/motion_maker;
   only that verdict counts toward readiness). Then
   `python3 growth.py assets render local/takes/<name>.manifest.json`.
   Output: `local/renders/<creative_id>/<hash>/` (the MP4, SRT, thumbnail and a
   receipt with every hash).
7. **Review:** a fresh session that made nothing scores it with the crew lenses and
   COPY.md's rubric (38 of 48 or more, Ethics and Action at 4). Below the bar it is
   held with its reason, never asked.
8. **File it:** the Librarian files the render into Drive
   `Growth Build/03_Runs/<YYYY-Www>/<YYYY-MM-DD>_<home>-<away>/` with an INDEX row
   (`python3 growth.py library name <path>` checks the name first).
9. **The pack:** one item per channel (fields in `engine/pack.py`, `ITEM_FIELDS`):
   the tracked link from `growth.tracked()`, never a bare `fulltime.fm` in the
   caption; `"whole_match": false` for a single show; the media hashes from the
   receipt; the review link into `03_Runs`. Then
   `python3 growth.py pack check FILE --spec local/specs/<week>.signed.json` and
   `python3 growth.py pack propose FILE --spec local/specs/<week>.signed.json --context CONTEXT --expires-at <end of matchday, London> --queue`
   `--context` is `{"<creative_id>": {"unit_cost_gbp": 0.0, "unit_minutes": 12, "checks": {}}}`:
   the measured cost and minutes for each item, and any pre-live check the engine
   cannot see itself. The engine fills the rest: copy and AI label from the pack check,
   the live-rail checks, and exact quote, dimensions, media hashes and captions from
   the item's own render receipt. A verdict counts toward readiness only when every
   check in `formats/<format_id>/recipe.json` is true and cost and minutes are measured,
   never null.
10. **The ask:** the next `python3 growth.py cc morning` carries it as G2. Krish
    answers: Clear posts every item, Change it first gives each item a verdict,
    Purge rejects them all, Bump keeps it off his list until his next day.
11. **After he posts:** `python3 growth.py buffer query --channels FILE` gives the
    read-only `list_posts` query for the Full Time allowlist; run it with the Buffer
    connector, save the reply, then
    `python3 growth.py buffer receipts --posts FILE --pack FILE --channels FILE --record`
    (`--channels` is Buffer's own `list_channels` reply). That reads his permalinks back
    and closes the G2. His no-edit "post it" verdicts on pinned
    locks build each format's readiness (`python3 growth.py formats readiness`).

## Proof zero: the shows already published

The four published editions (19 and 20 September, 11 and 19 October) sit in past
weeks, and a pack must sit inside its own week's spec. So proof zero uses one
**proof-mode** spec per past week: copy the example, set `run_id` (for example
`fulltime:2026-W43`), the Monday-to-Sunday `window` holding the match, `"mode": "proof"`,
the match as the one fixture and the pinned locks. `spec check` accepts it, and a
proof spec needs no signature: its G2 asks for verdicts only and says nothing is to
be posted. Then follow the matchday steps above with that spec. Krish's no-edit
"post it" verdicts count toward readiness; posts about old matches are never made.

## Why the kit's "fulltime.fm" is allowed

The approved kit prints "Free pilot beta at fulltime.fm" inside the image. That is
artwork, not a link. The untracked-link rule applies to captions and links, where
every link must carry its creative ID through `growth.tracked()`.
