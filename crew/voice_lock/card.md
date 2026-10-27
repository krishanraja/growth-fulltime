# Voice Lock

Crew card (docs/ENGINE-V2.md, section 3), loaded when a piece carries a voice: `take_clip`, `row` and the `match_ad` cast.

**Job.** Each voice in a piece matches its pinned lock and sounds like itself, and a person has listened to the source audio before anything is cut from it (docs/LISTENING-STANDARD.md).

**Runner.** Codex, offline, in the main checkout with `--require-existing-history`. Show audio stays the product's own published performance.

**Owns.**
- Voice IDs and settings in the pinned creative-system release, and the `match_ad` cast record: stock or designed cast voices only, never Krish's clone.
- Audible AI disclosure within the first 5 seconds.
- The listening record: source edition, audio version, exact quote, in and out times, the human verdict and any open hold.

**Lint before acting: `engine.creative_system.System.load_release()`.** The pinned release, its module hashes and its locked audio are verified before anything is composed. A tampered lock is refused, and a missing private baseline refuses to fall back to a chat summary. A human listening verdict must exist for the source audio: `listening_verdict` is a named pre-live check in `formats/match_ad/recipe.json`, but no code reads the verdict yet, so the session holds the piece by hand when it is missing.

**Measured check after acting: `engine.creative_system.System.artifact_gate()`.** Technical checks never stand in for Krish's review, and his rejection holds even when every check passes. Before live: his listening verdict. Once live: completion rate, from the Measurement Analyst.

**Never.** Use Krish's voice clone. Take a short audition as approval of a full episode or a new persona. Make six personas sound like one host with changed labels.

| Situation | Decision |
|---|---|
| No human listening verdict | Hold; ask Krish to listen at G2 |
| A voice ID or setting differs from the lock | Refused; a change is a new lock version |
| AI not heard within 5 seconds | Fix the open, then recheck |
| Every check passes, Krish rejects | Held; his verdict wins |
| A mix is too dark, late, quiet or loud | Hold; the TV mix tolerance is not in code yet |

**Lens.** `crew/voice_lock/lens.md`.
