# Switch r1 rules

**Channels (fixed).** zen 1 Reporter #3F607C · gaffer 2 #4E6B3C · stats 3 Numbers Guy #2E6463 · romantic 4 #9B6269 · doomer 5 #4F4868 · banter 6 Wind-Up #A3542E. Rival = 7 − n. Mate lines (after "Send to your mate who"): 1 wants the facts before the arguments. 2 picks the team from the sofa. 3 wins every argument with a spreadsheet. 4 still gets goosebumps at kick-off. 5 is worried even when you win. 6 bites every single time.

**Slots.** pundit, match {home, away, score, date, shows[]}, quote (≤90), rival_quote (≤6 words), said/now/next, cta (fixed "Pick your channel. Free pilot beta at fulltime.fm"). Cover and seal SVGs: product code.

**Data truth.**
- Strip tab: lit = this post's pundit; on = in shows[]; off = not in shows[] (38% opacity). No match bound: all on.
- take_clip frame 0 is single channel. The cut renders only if shows[] has rival(n) AND rival_quote is set; else default.
- row only if shows[] has both and both lines are real and opposed.
- morning_card headliner must be in shows[].
- No copy claims disagreement without the other pundit's real line on the frame.
- Until transcripts: quote = public line or opinion line, no facts or numbers, plus "SAMPLE LINE".

**Type.** Serif = Instrument Serif; sans = Schibsted Grotesk (labels 600 caps +.14em). Name px = min(cap, column ÷ width@1px); "The" italic 0.42 px above; "CH n · AI Pundit" beside it. Quote 104px lh1.02 (≤60, 3 lines) or 88px lh.99 (61 to 90, 4 lines), opening mark hung −0.36em, one-letter words glued to the next. Wind-Up hyphen margins −.05/−.075em.

**take_clip frame 0 (1080×1920).** Paper ground. Strip x64 y250 876×64 on a ground plate (pad 7). Group = name (column 876, cap 240) + 52 + quote + 14 + tag, centred in y338 to 1066. Seal 316 at x64 y1090 (FULL TIME, score 0.30d, dd·mm·yy). x410: date label y1096, "Home v Away" 600 36 (break before "v"), mate block y1250. CTA y1426: mark 68 + 700 36 / 500 28. Cover art band y1520 to 1920, no text.

**Variant cut.** Rival paper y0 to 620, rival art y0 to 220, "CH r → CH n" y346, rival name 56, rival_quote italic 58 (break after first sentence). Seam y620: one 330×22 rival bar + 3px cream line. Seal 316 at x624 y470. Our group in y656 to 1300, name column 540 cap 200, quote ≥ y806. "Who is right? Comment r or n. Send it to the mate who is wrong." y1322. CTA y1426.

**Mid frame.** Header y346: label, name 68, match, date. Seal 180 at x760 y330. Cover art full bleed y540 to 1920, 3px cream line at 538. Ground plate x64 to 940 y1068 to 1480: caption 700 64/1.12, lime pause + fill y1262, "Made by AI from checked match facts" y1326, CTA y1394.

**morning_card 1080×1350.** Ground. Strip y56 h56. "Dimmed: no show for this match" y132. Cover 388×458 at x64 y184; x492 "Top of the bill", name (524, cap 170), public line. Seal 388 at x64 y672; club names serif fit 524 cap 96. Mate block y1100. CTA line y1252.

**row 1080×1350.** Paper a y0 to 620, paper b 620 to 1130, ground below. Names column 640 cap 140, quotes 68. Art tiles 246×290 x770. Seam y620, seal 290 at x744 y470. "Who is right? Comment a or b. Send it to the mate who is wrong.", CTA.

**End card 9:16.** Strip y250 (all on, lit). Six bands y340, 118 each: CH n, name 74, art right 380. Mark + wordmark y1082, "One real match. Six AI Pundits. / Pick the brain you fancy." y1206, CTA y1384, lit pundit's art band y1520.

**Share 1200×630.** Six bands 680×105, lockup, CTA. **Thumb 1280×720.** Strip, name (720, cap 180), "Home s–s Away" 800 fit 720 cap 62, date, CTA; cover 406×479 at x826, seal 300 at x850 y372; bottom-right 130×60 clear.

**Safe (9:16).** Text inside x≤940, y220 to 1500. Bottom 420 = art only.

**Grid.** 3:4 crops: 9:16 window y190 to 1630, 4:5 centred. Never the same lead paper twice in a row.

**Motion.** 0.00 frame 0 complete. 0.08 to 0.24s lit tab blinks once. 0.24 to 0.42s seal stamps 1.06→1, 4px drop. Audio by 2s: "This is The {name}, an AI Pundit on Full Time." 1.00 to 1.30s cut to mid layout, art band rises. Cut: 0 to 0.12s seam bar slips 24px, then rival slab wipes up.
