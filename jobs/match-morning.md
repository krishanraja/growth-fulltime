# Job: the match-morning pack (every day)

Kind `daily`. "The content system" and "The loops" in `PLAYBOOK.md`. Time
for Krish: about 10 minutes to read, then the time to send and post.

1. `python3 growth.py sync`. Use the `fulltime_sha` it prints. Run
   `python3 growth.py rail`. Note the push gate.
   - **OPEN**: today's pack pushes the match the gate names (the newest, or
     the latest full one), with links that name its drop.
   - **HOLD**: today's pack still drafts everything below, every push item
     marked `"needs": "RAIL"`, and leads with one item for a full-time
     session: which AI Pundits failed on the newest match and what the
     sync's notes say about why (`platform: site`). The headline says HOLD.
   - **No match yesterday** (a weekday, or the international break): draft
     an evergreen pack: "meet the six", a **Show me why** reveal from the
     latest full match, or a re-engagement note to testers.
2. Choose **one concept**. In order of preference:
   - a winner to multiply (the latest `report` or `numbers` pack names it);
   - the strongest argument in today's or yesterday's radar
     (`python3 growth.py read --days 2 --kind radar`);
   - the next format in the PLAYBOOK bank not used in the last 7 days.

   Before drafting, write down:
   - the concept number;
   - the pillar;
   - the one-sentence mechanism ("two AI Pundits disagreeing about the same
     scoreline makes a fan send it to the friend who takes the other side");
   - the fanbase (which club, and its rival);
   - the one signal it should move (shares, finished shows, second-pundit
     plays).
3. Draft, one item each, each with its own creative id (PLAYBOOK, "Creative
   ids"). Every fulltime.fm link is tracked (`python3 growth.py link`), names
   the match's drop, and opens an AI Pundit who made a show for it. Keep the
   idea the same in every edition. Change the opening, hook, caption and
   call to action to suit the place. Never paste the same text twice.
   - **The clip brief** (`platform: other`): "Same match, two minds" or
     another format from the bank. It includes:
     - the hook (first frame, works muted);
     - a beat sheet with times: which two AI Pundits, the exact lines from
       their published transcripts (quote only what the show says), the
       score in the match seal, the end card;
     - the assets: the two AI Pundit covers, the match seal, the share card,
       the audio segment by timestamp;
     - what must not appear: broadcast footage, player photos, league or
       broadcaster marks, a living pundit, betting, an invented quote.

     9:16, captions burned in, text inside the safe zone. Start every line
     the public will see or hear with `Hook:`, `On screen:`, `Voiceover:`,
     `Caption:`, `Cover:` or `End card:`.
   - **TikTok** (`tiktok`, CLIP), **YouTube Short** (`youtube`, SHORT) and
     **Instagram Reel** (`instagram`, CLIP): the caption with the match in
     the first line, 2 to 5 specific hashtags, one call to action ("Pick
     your AI Pundit"). These wait on D1 until it is in force.
   - **WhatsApp share lines** (`whatsapp`, INVITE), one per AI Pundit who
     made a show, written for the group chat: what that AI Pundit thinks,
     in one line a fan would forward, and the tracked link that opens that
     AI Pundit's show. A rival line ("The Wind-Up has a message for Forest
     fans") when The Wind-Up or The Doomer made one.
   - **Personal invites** (`invite`, INVITE): up to 10 a day from
     `local/lists/invites.md`, each written for one named person (their
     club, the match they care about), asking them to listen and to send it
     to their club's group chat. Create the list with a table if it is
     missing: name, their club, how Krish knows them, the step (to invite,
     invited, listened, replied), the date. Names stay in `local/`.
   - **Full edition on YouTube** (`youtube`, VIDEO), when the match's rail
     is full: the title, the description with the tracked link, and the
     cover to use. Waits on D1.
4. For each item, `why` names the signal it should move.
5. Headline: the day, the match, the gate and what is in the pack, for
   example "Sunday, Forest 1-2 Arsenal, rail 5 of 6, OPEN: clip, 3 editions,
   5 share lines, 10 invites". Check, then post. Add the new creative ids to
   `local/creatives.csv`, one row each, with approval left blank for Krish.
