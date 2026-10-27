# Card Maker

Crew card (docs/ENGINE-V2.md, section 3), loaded for `morning_card` and for every derived card on Threads, X, Facebook and the WhatsApp Channel.

**Job.** Make each card from a pinned Full Time brand template so it reads in one second at thumbnail size, with the AI visible and every character drawn.

**Runner.** Claude, through the Canva connector. Cards are filled with `autofill-design` when `get-brand-template-dataset` returns the fields (`quote`, `pundit`, `home`, `away`, `score`, `date`, `cta`); otherwise `copy-design` then `edit-design`. Then `read-design` and a hashed `export-design`.

**Owns.**
- The six Full Time templates in Canva `Growth/Templates`, pinned by ID from the brand-kit receipt.
- The exported file per channel, with its SHA-256 and dimensions.

**Lint before acting: `engine.crew.card_lint()`.** Given the card, its recipe (`engine.formats.recipe()`) and the pinned template IDs, it refuses an unpinned template, a card without "AI Pundit", a league or broadcaster mark in the text, and a size that is not the channel's cut. Club crests and player images are checked by eye.

**Measured check after acting: `engine.crew.glyph_readback()`.** The text read back with `read-design` equals the slot text after line wrapping, and every character has a glyph in the font (R19: a share image once shipped with missing glyphs). The export's hash and dimensions match its channel's cut. No CLI step runs the readback yet, so the session runs it on every export.

**Never.** Use another brand kit, a personal photo or account, or generate new logos or art. Share a design or change its permissions.

| Situation | Decision |
|---|---|
| The template's fields are missing | Fall back to copy and edit; record it |
| Readback differs from the slot text | Refused; fix the text box, export again |
| The font lacks a glyph (such as £) | Change the font or the words |
| Dimensions differ from the cut | Export again at the right size |
| A league or broadcaster mark appears | Remove it before review |

**Lens.** `crew/card_maker/lens.md`.
