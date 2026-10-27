# Cowork prompt: the Full Time design system in Canva (27 October 2026)

Krish runs this in Cowork on his PC with the Full Time folder in Ventures open on his H drive and Canva logged in. It builds the brand kit and six templates; the kit itself cannot be made through the Canva connector. Afterwards Claude tags the autofill fields through the connector and checks them with `get-brand-template-dataset`. The receipt lands in `Growth Build/05_Brand-Kit`. Ruling (Krish, 2026-10-27): "ensure there is a full brand kit built in Canva".

Paste everything below the line.

---

Task: build the complete Full Time design system in my Canva account: one brand kit plus six templates. Use only the brand assets in the Full Time folder I have open on my H drive (Ventures, Full Time, the folder that contains 00_Brand-Assets and Growth Build). I am logged in to Canva.

First: if my Canva account has more than one team or brand, ask me once which one to use before you create anything. That is the only question you ask before the end.

Sources of truth, in this order:
1. C:\Users\krish\dev\mindmake\full-time\docs\01-brand.md. The product owns identity, and 00_Brand-Assets\START-HERE.txt says this file governs.
2. 00_Brand-Assets\06_Claude-Design-System\full-time.tokens.json, for exact colour and type tokens.
3. 00_Brand-Assets\06_Claude-Design-System\Full-Time-Brand-system.md, then 00_Brand-Assets\01_Identity\Brand-system.md.
Take every hex value, font name and AI Pundit name exactly from these files. Never guess one. If the sources disagree, record both values under "gaps" and use neither.

Assets:
- 01_Identity: the wordmark, the trimmed wordmark, the icon and favicon, and App-icons. A .asset.json file is a pointer record; follow it only to the product's own URL.
- 03_Social-and-Ads: PowerPoint starters, for reference only.
- The AI Pundit covers and match imagery are made by the app, so 02_Imagery is empty on purpose. If no cover files exist anywhere in the folder, list them under "gaps".

Existing Canva work to reuse, never duplicate:
- Project folder: https://www.canva.com/folder/FAHXUrp5y8s
- Logo design (5 pages): https://www.canva.com/design/DAHM0g8bvcw
- Growth/Templates folder, already created for you: https://www.canva.com/folder/FAHZNeZeizc

Steps:
1. Inventory. List every file in 00_Brand-Assets with its size and date. This is read only: never move, rename, edit or delete anything on the H drive.
2. Map files to kit slots:
   - logos: primary, mark, mono, reversed;
   - colour palettes, with exact hex values: the ground and ink, the accent kept for the mark, play and progress, and the text colours;
   - fonts for heading, subheading and body. Upload font files only if the folder holds them with their licence; the brand uses OFL faces;
   - graphics: all six AI Pundit covers, the match seal and its textures;
   - brand voice: the exact term "AI Pundit", UK English, simple words, no em dashes, and AI always disclosed.
3. In Canva go to Brand, then Brand Kit, and create a kit named "Full Time". Add everything above to it.
4. Templates. Put them in the existing Growth/Templates folder above. Do not create another Growth or Templates folder. In Templates, make six designs named template_<size>_<use>:
   - 1080x1920 vertical cover
   - 1080x1350 card
   - 1080x1080 card
   - 1200x630 share card
   - a ten-page 1080x1350 carousel
   - a 1280x720 thumbnail
   Every template uses the kit's fonts and colours and carries a fixed, visible "AI Pundit" label. Publish each one as a brand template inside my own Canva only. Put one text box on each template for each of these fields, labelled with exactly this text as placeholder copy: quote, pundit, home, away, score, date, cta. Claude will connect the autofill fields through the Canva connector afterwards. If brand templates are not available on my plan, keep them as normal designs in that folder and record brand_template: false.
   Never use league or broadcaster marks, club crests, player images, or anything that looks like a real pundit.
5. Verify:
   - Screenshot the Full Time brand kit page and each template. No screenshot may show other brand kits.
   - Check every hex value in Canva against the source file.
   - In each font, render the text "Full Time, AI Pundit: 2-1, £ ' ?" and check every character appears.

Never:
- post, publish publicly, share a link, or invite anyone;
- change my Canva plan, billing or settings;
- use any other brand kit (for example Mindmaker), or my personal photos or accounts;
- generate new logos or art with AI;
- upload anything from outside this Full Time folder.
If an asset is missing or two versions conflict, do not invent one or choose between them. Put it under "gaps" and keep going.

Receipt: write 2026-W44_brand-kit-receipt_v1.json into Growth Build\05_Brand-Kit\ in the same Full Time folder. That is the only place outside 00_Brand-Assets you may write, and you only add that one file. If you can reach C:\Users\krish\dev\mindmake\growth-fulltime\local\canva\, put a copy there too. The receipt holds:
- brand_kit_id, taken from the kit's URL;
- assets: for each one, its source path, SHA-256 (use Get-FileHash, or certutil -hashfile <file> SHA256) and its name in Canva;
- palettes, with hex values;
- fonts;
- templates: each one's ID, URL and brand_template flag;
- screenshots: the file paths;
- gaps.

Finish by showing me every gap in one list, so I can answer them all at once.
