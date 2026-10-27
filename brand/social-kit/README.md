# Full Time social kit: The Switch, revision 1

The design system for Full Time's organic social posts: take_clip frame 0 and mid frame, the variant cut, Pundit v Pundit rows, morning cards, the match ad end card, share card, thumbnail and the profile grid. Every artboard is a pure function of its slots, rendered at true pixel size.

**Approved.** Krish, 27 October 2026: "I like it. Looks good."

The rules are [spec.md](spec.md), copied verbatim from the approved board. [LOCK.json](LOCK.json) holds the SHA-256 of `spec.md`, `templates.js` and `slots.json` with the approval. `tests/test_social_kit.py` fails CI if any of them changes, and `render.js`, `take_clip.js` and the engine refuse to render. A change to the look is a new revision: show Krish the board, and only after his approval update the files, `revision` and the hashes in `LOCK.json` together.

## Files

| File | What it is |
|---|---|
| `spec.md` | The approved rules (locked, 4 KB at most) |
| `templates.js` | The browser-side templates (locked) |
| `slots.json` | The board's slots: the four real published matches, sample lines marked as such (locked) |
| `board.js` | The board page layout and its spec panel |
| `render.js` | Renders every artboard and the board, with its automatic checks |
| `take_clip.js` | Renders the still layers of one take_clip for the engine to compose |
| `prepare-assets.mjs` | Makes the covers, seals and marks from a Full Time checkout |

## Prepare the assets

The covers, seals and atmospheres come from the product's own code; the mark and wordmark are the product's PNGs. Nothing of the product is committed here: this repository is public.

```
node brand/social-kit/prepare-assets.mjs C:\Users\krish\dev\mindmake\full-time
```

The checkout is the first argument, else `FULL_TIME_REPO`, else `../full-time` beside this repository. The script copies `src/lib/pundit-cover.ts`, `match-seal.ts`, `match-atmosphere.ts`, `colour.ts`, `club-colours.ts`, `premier-league.ts` and `pundit/types.ts` into a temporary folder, patches their relative imports to `.ts`, runs them with Node's type stripping (Node 22.6 or later), and deletes the folder. It writes `local/brand-kit/assets/`, with `SOURCE.json` naming the product commit and each file's SHA-256. Add `--instance <take.json>` for a match outside the four.

## Render the kit

```
node brand/social-kit/render.js
```

Needs Node with Playwright (`require('playwright')`) and Google Fonts (Instrument Serif, Schibsted Grotesk) over the network. It writes `local/brand-kit/board.html`, the frames to `local/brand-kit/frames/` under Growth Build library names for `05_Brand-Kit` (`2026-W44_social-kit-<frame>_v1.png`: the approval week and the revision), and `local/brand-kit/manifest.json` with each output's bytes and SHA-256. It exits 1 on a changed locked file, missing assets, text outside the 9:16 safe area, text overflow, banned copy or a broken grid rule. Check a name with `python3 growth.py library name 05_Brand-Kit/<name>`; the Librarian files the frames in Drive. The render is deterministic: on 27 October 2026 all 21 frames matched the approved board byte for byte.

`BRAND_KIT_DIR` moves `local/brand-kit` elsewhere (it must hold `assets/`).

## A take_clip, from instance to video

1. **The instance** (JSON, inside `local/`): one published AI Pundit show.

   ```
   {"schema_version": 1, "pundit": "zen", "drop": "<drop id>", "home": "Tottenham", "away": "Coventry",
    "score": [3, 1], "date": "2026-10-19", "shows": ["zen"], "quote": "<frame 0 hook, 90 characters at most>",
    "sample": false, "captions": [{"start": 0.0, "end": 2.4, "text": "<words>"}],
    "audio": {"source_record": "local/assets/<drop>/zen/source.json", "start_seconds": 12.0, "end_seconds": 24.0}}
   ```

   `shows` is every AI Pundit published for the match (the strip's data truth). Caption times are clip seconds. The quote and every caption must be exact quotations from the published transcript, and the captions together must be exactly the segment's quote. `sample: true` prints "Sample line" tags.

2. **The layers.** `node brand/social-kit/take_clip.js <instance.json>` writes `local/brand-kit/layers/<instance name>/`: `frame0.png` and one `plate-NNN.png` per caption (the mid frame with that caption and an empty progress track), all 1080x1920, and `layers.json` with each layer's SHA-256, the text it carries, the instance's SHA-256, the kit lock, and the progress track's exact rectangle and lime colour, measured in the page. A caption over two lines, or any check `render.js` makes, refuses the layers.

3. **The video.** Add `"size": "1080x1920"`, `"layers": "<that folder>"` and `"instance": "<instance.json>"` to the render manifest (one segment, matching the instance's `audio`), then `python3 growth.py assets render <manifest.json>`. FFmpeg holds frame 0 for the first second, then shows the plates in caption order over the published audio at 30 frames a second, and draws the lime fill growing with the audio in the track's rectangle. Every renderer check still applies (hashes, quote exactness, bounds, the AI label on every layer, creative ID rules, holds), and the receipt carries the layer and instance hashes and the kit's lock.

The motion beyond the cut (the tab blink, the seal stamp, the art band rising) and the end card are not in the video yet.
