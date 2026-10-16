# The playbook: 1,000 users, applied to Full Time

Source: "Full Time: The 1,000 Free Users in 30 Days Playbook", the document
Krish gave this engine on 16 October 2026, kept in `knowledge/`. It was
written from the full-time repository on that day. This file is how the
engine runs it: where Full Time's canon limits it, which rulings it waits on,
and what each job does with it. `knowledge/README.md` lists every place the
engine departs from the document and why.

**Order of authority, highest first:**
1. The full-time repository's canon and the live site, as
   `python3 growth.py sync` reads them today.
2. Rulings in force (`rulings.json`, recorded in full-time's decision log).
3. Krish's words in `CHANGES.md`.
4. This playbook.
5. The document in `knowledge/`.

If this file disagrees with full-time's canon, the canon wins. Say so in the
pack's headline so the playbook gets fixed.

## The goal

Krish, 16 October 2026: "obsessed with getting this into market".

- **The number.** 1,000 users by **Sunday 8 November 2026**. The Premier
  League's November international break runs 9 to 17 November, so the last
  match weekend before it is the real deadline, and the break is for
  bringing people back, not for finding new ones.
- **A user** is a person who finished at least one AI Pundit show
  (`listen_completed`) and left a way to reach them: a verified account
  email, or a push opt-in. Page views and plays don't count. Today the
  product has no sign-up moment, so this number reads zero until ruling D3
  and the Sprint 0 work below give it one.
- **Beside it, two numbers:** finished shows by `utm_source` (activated
  listeners), and the second-pundit rate (`pundit_switch_committed`), the
  evidence that six minds beat one.
- **Under it, the December bar** (full-time `docs/22-vision-and-beta.md`):
  a show every match morning, a mostly full rail, no wrong fact reaching a
  listener, 30 testers who finish a show, 40% back within seven days, half
  of them trying a second AI Pundit, 40% "very disappointed" if it went
  away, and the consent item closed. Reaching 1,000 the right way is the
  evidence for that bar.
- **Minimal spend.** Agents never spend. Paid creators (up to £600) and one
  paid test (up to £300) are the only cash in the plan, both waiting on
  rulings D5 and D7. Model spend for more shows is a full-time decision,
  quoted with its arithmetic by the session that runs it.

## The rail gate: the first constraint

Full Time's promise is six minds on one match. A fan who opens it to find one
AI Pundit and five dimmed sees a broken app, and a first listen is spent
once. So the engine pushes nobody anywhere until a match has **at least 4 of
the 6 AI Pundits** (`RAIL_MIN` in `growth.py`). That is the document's own
first move and its kill switch, and the December bar's "a median of four".

**The reading on 16 October 2026:** three matches on the rail (Crystal
Palace 3-1 Nottingham Forest, 11 October; Manchester City 5-3 Sunderland,
20 September; Tottenham 2-3 Aston Villa, 19 September), and **each has one
AI Pundit**. The newest show published on 12 October. The gate is HOLD. Read
it live with `python3 growth.py rail`; this paragraph is history the moment
the next show publishes.

What the engine does about it:
- every push item is still drafted, marked `"needs": "RAIL"`, so the kit is
  ready the morning a match fills;
- the product job leads with the rail: which AI Pundits failed on the
  newest match, and a brief for a full-time session to read the stored
  verdicts first (free, per full-time's `AGENTS.md`, "The order of
  instruments") before touching a prompt or paying for a run;
- the numbers job tracks the fill every morning.

Filling the rail is full-time's work, not this engine's. Until it fills,
the one most valuable thing this engine can do for growth is keep saying so.

## The equation

    users = unique visitors x play rate x finish rate x sign-up rate
    total users = seed / (1 - K),   K = shares per user x share-to-user rate

The document's planning numbers. **These are assumptions to replace with
PostHog's readings after the first open weekend, not forecasts.**

| Step | Assumed rate |
|---|---|
| Visit to play | 50% |
| Play to finished show | 45% |
| Finished show to sign-up | 40% |
| Visit to user | about 9%, so about 11,000 visitors for 1,000 users |

| Seed users | K | Total |
|---|---|---|
| 700 | 0.3 | 1,000 |
| 500 | 0.5 | 1,000 |
| 300 | 0.7 | 1,000 |

What follows from it:
- **The finish rate and the sign-up step beat traffic.** Lifting sign-up from
  40% to 60% cuts the visitors needed from about 11,000 to about 7,400.
- **K comes from the group chat.** Three WhatsApp sends per user at a 10%
  conversion is K = 0.3. That needs a share button and a preview worth
  clicking (Sprint 0, P2 and P3), which Today does not have yet.
- **Every share is an invite.** The share loop is the moat to test: new
  users per sharing user.

## Where the document meets Full Time's canon

| The document says | Full Time's canon says today | So the engine |
|---|---|---|
| Market to fans on TikTok, Shorts, Reels, Reddit, X | "Until then, growth is invited testers only" (full-time `docs/07-marketing.md`, "Release gate") | Drafts fan-channel posts held for D1. Personal invites, one person at a time, go out as soon as the rail gate opens |
| Cover every Premier League match | One match a day; a day without a finished Premier League match publishes nothing (`docs/00-product.md`) | Waits on D2. Never says "every match" in copy |
| Count users who sign up after a show | No sign-up moment; the morning recap is off in the beta (`docs/product-state.json`) | Waits on D3; the product job briefs the build |
| LinkedIn, Show HN, Product Hunt and press under Krish's name | full-time's `NOW.md` keeps a `never_publish` list for Krish's anonymised Mindmake proof writing | Drafts the launch kit held for D4, with a written boundary between the two stories |
| Paid creators and a paid test | Paid promotion is off (`docs/00-product.md`); the consent item is open (`docs/11-legal.md`) | Shortlists and drafts held for D5, which needs D7 |
| An FPL "Beat the AI Pundits" league | No forecast-performance claim (`docs/product-state.json`) | Drafts held for D6, framed as a game |
| A six-pundit run costs 2.14 US dollars | full-time's `AGENTS.md`: "roughly $6" per six-pundit run; 2.14 was measured on the Haiku bench, and the OpenAI bench cached far worse | Quotes the canon's figure with its source, never the document's |
| `utm_source` per channel | Testers' invite links carry `?utm_source=beta`, and the December bar counts them by it (`docs/22-vision-and-beta.md`) | Tags personal invites `beta` and every other channel by its own name |
| Market statistics (Edison, Acast, Castfox, Robinhood, NotebookLM) | Not canon | Planning context only. Never in public copy unless re-read and cited that day |

## The parts and the job that runs each

| Part | What it means here | Job |
|---|---|---|
| The rail | Is a match full enough to push? What failed? | `sync` (daily), `product` (weekly) |
| Demand and the fans' words | Post-match arguments in club subreddits and football video, comments on Full Time's posts, FPL chatter | `radar` (daily) |
| Creative | One concept a match morning, native editions per channel, share lines per AI Pundit, personal invites | `daily` (match morning) |
| The product is part of the engine | Share button, per-edition preview, sign-up after a show, the recap, tracking, consent | `conversion` (weekly) |
| Borrowed reach | UK football fan creators, disclosed | `partners` (weekly) |
| The launch | The build story for AI and tech readers | `launch` (weekly) |
| Measurement and decisions | Daily numbers; a weekly scale, iterate, hold or kill call | `numbers` (daily), `report` (Monday) |

## Each channel's job

| Channel | Job | What the engine drafts | Waits on |
|---|---|---|---|
| Personal invites | The first testers: people Krish knows, by club | One message per person, naming their club's match, asking them to forward it to their club's group chat | The rail gate |
| WhatsApp | Where football banter lives | One forwardable line per AI Pundit who made a show, and the rival line | The rail gate |
| TikTok, YouTube Shorts, Instagram Reels | Discovery for fans under 30 | "Same match, two minds" and "Show me why" clips, footage-free | D1 and the rail gate |
| YouTube (full editions) | Where podcasts are found now | The full show as a video with its cover, title and tracked link | D1 and the rail gate |
| Reddit | Earned trust in club communities | Comments with the actual argument, no link; a link only where moderators said yes | D1, the rail gate, and each subreddit's moderators |
| Show HN, Product Hunt, Podnews, AI newsletters, LinkedIn | The build story: one founder, named checks, a measured cost, failures left visible | The launch kit and its fact sheet | D4 |
| Creators | Reaction videos from club fan creators, labelled "Ad" | The shortlist and one note each | D5 (after D7) |
| FPL | Six AI Pundit teams in a public league | The league description and weekly table lines | D6 |
| Email to testers | Feedback and return | The three questions, and the weekly "best arguments" note in the break | The rail gate |

## The content system

**The one idea:** "One match. Six AI Pundits. Pick the brain you fancy."
(full-time `docs/01-brand.md`.) Every piece shows two or more minds
disagreeing about the same real match, and every link opens a show.

**Formats bank** (footage-free; covers, the match seal and share cards only):
1. **Same match, two minds** (15 to 25 seconds): two AI Pundit covers, one
   line each from their published shows about the same scoreline, captions
   burned in, end card "Pick your AI Pundit."
2. **Show me why** (20 seconds): a spicy claim, the checked fact, then the
   boundary line, "The data shows what happened, but not always why."
3. **The Wind-Up versus your club** (10 to 15 seconds), the morning after,
   one per fanbase.
4. **The rival line**: The Wind-Up or The Doomer has a message for the other
   side's fans.
5. **Which AI Pundit got it right?**: a comment prompt under a two-minds clip.
6. **Meet the six**: each AI Pundit's public line (01-brand), one card each.
7. **The full edition on YouTube**, with its cover.
8. **The withheld show**: for AI readers only, why a show that failed its
   checks never published (from full-time's decision log).
9. **The FPL table line**, once D6 is in force.

**Hooks** (approved lines from full-time `docs/07-marketing.md` and
`docs/01-brand.md`; the first frame works muted):
- "One match. Six AI Pundits."
- "Pick the brain you fancy."
- "Same facts. Six different shows."
- "The score is only the start."
- "Football has enough hot takes. Pick a better one."
- The six AI Pundit lines: "Calm, clear, and first with the facts." "Spots
  the choices that changed the game." "Counts everything. Trusts almost
  nothing." "Finds the bit that made football feel magic." "Sees the wobble
  before anyone else." "Starts arguments for fun. Football needs one."

**Calls to action** (one per post): "Pick your AI Pundit", "Play today's
show", "Compare the shows", "Show me why", "Send it to the group chat",
"Tell us what you think" (testers only).

**Always:** "AI Pundit", exactly; that it is AI-written with synthetic voices;
free beta; one call to action. **Never:** "daily without fail", "every
match", "your personal pundit", "unbiased", predictions or accuracy, prices,
"December", a launch date, league or broadcaster logos, match footage,
player photos, a living pundit, betting words. `growth.py check` refuses
what code can see.

**Production truth.** A clip quotes only what a published show says, from
its transcript, by timestamp. Never write a line for an AI Pundit and
present it as theirs. The visuals are Full Time's own generated covers, the
match seal and the 1200 by 630 share card (full-time `docs/01-brand.md`).

## Measurement

**PostHog is the ledger for users.** Platform analytics explain attention.
They never stand in for finished shows or sign-ups.

**Creative ids.** Every draft that leads somewhere gets one:

    {PLATFORM}_{PILLAR}_{FORMAT}_C{concept}_H{hook}_V{version}_{YYYYMMDD}
    e.g. TT_CLASH_CLIP_C03_H07_V2_20261025

- **Platform:** INV (a personal invite), WA (WhatsApp), EM (email), TT, YT,
  IG, X, RD (Reddit), LI (LinkedIn), HN, PH (Product Hunt), PR (press), CR
  (creator), AD (paid), FPL, WEB.
- **Pillar:** CLASH (two minds), PROOF (Show me why), TRIBE (club and rival),
  BUILD (the build story), GAME (FPL), HABIT (return and recap).
- **Format:** CLIP, SHORT, VIDEO, STORY, POST, THREAD, COMMENT, DM, INVITE,
  EMAIL, PITCH, LAUNCH, NOTE.

Concept numbers run on through the whole engine. The same concept keeps its
number across platforms.

**Every tracked link.** Build it with `python3 growth.py link <url>
<creative_id>`:

    ?utm_source=<beta|wa|email|tiktok|youtube|instagram|x|reddit|linkedin|hn|producthunt|press|creator|paid|fpl|web>
     &utm_medium=<organic_video|organic_social|referral|email|press|launch|paid>
     &utm_campaign=ft_growth_<YYYYMM>&utm_content=<creative_id>

A link to Today names the match (`?drop=`) and the AI Pundit (`?pundit=`), so
the recipient opens the show the sender heard, without losing their own
saved choice. The checker refuses an untracked fulltime.fm link, a link to a
thin rail, and a link to an AI Pundit who made no show for that match.

**The creative record** (kept in `local/creatives.csv` on the machine that
runs the engine, never committed): creative_id, concept, pillar, format,
hook, match, AI Pundits, call to action, landing url, approval (sent, posted
or skipped), published url, and the 24-hour, 72-hour and 7-day views,
shares, profile visits, link taps, visits, plays, finished shows and
sign-ups, then the learning and the next action.

**What counts, in order:**
1. Users (finished a show, left a way to reach them).
2. Finished shows per 1,000 reached.
3. Second-pundit plays per finished show.
4. Shares per view, and users per share.
5. Day-7 return.
6. Link taps and visits per 1,000 reached.
7. Watch time on clips.
8. Likes and follows.

A clip with 3,000 views and 40 finished shows beats one with 300,000 views
and none.

**Funnel diagnosis:**

| What the numbers show | Likely cause | Next test |
|---|---|---|
| Few match mornings with an OPEN gate | The pipeline, not distribution | A full-time session on the stored verdicts |
| Low reach, good finishes per reach | The hook | Ten new openings on the same clip |
| Reach, few link taps | Entertaining, no reason to act | Name the match and the AI Pundit sooner |
| Visits, few plays | The landing (no autoplay is right) | The first screen inside the in-app browser |
| Plays, few finished shows | The show's first minute | Report the drop-off point to a full-time session |
| Finished shows, no sign-ups | No reason to leave a way back | The sign-up prompt and the recap (D3) |
| Sign-ups, no shares | No share button, or a dull preview | P2 and P3 |
| Shares, few users per share | The preview or the link | The per-edition preview card |

**Decisions.** Each creative family gets one call at 24 and 72 hours, against
this account's own rolling median: SCALE, ITERATE, HOLD or KILL.
- **A winner** brings finished shows, or link taps per 1,000 reached at least
  one and a half times the median, with enough views to trust.
- **Scale within 24 hours:** keep the original, write its mechanism in one
  sentence, then five new hooks, the same idea for two more fanbases, and a
  WhatsApp line.
- **Kill** a concept after three clearly different hooks fail to move the
  signal it was meant to move.
- **The mix:** 70 in 100 on what has worked, 20 on close variations, 10 on new
  formats. Before the first open weekend ends, "what has worked" means this
  account's own first weekend.

## Sprint 0: the product changes that make it shareable

Each is full-time's to build, in a full-time session. The product job tracks
them every Wednesday and briefs the next one.

| # | Change | Why | Waits on |
|---|---|---|---|
| P0 | **Fill the rail**: at least 4 of 6 AI Pundits on a match | Nothing else is worth pushing to until it does | Nothing; full-time's pipeline work |
| P1 | Cover every Premier League match each weekend, Today opening on the listener's club | Fans share their own club | D2 |
| P2 | A share button on every edition, with a per-edition preview (the 1200 by 630 share card exists; Today serves one default cover) | A preview naming the AI Pundit and the match gets clicked | Nothing |
| P3 | WhatsApp-first share text per AI Pundit | The group chat is where football talk lives | Nothing |
| P4 | Sign-up after the first finished show: magic link, club pick, the morning nudge | Turns a listener into a user who can come back | D3 |
| P5 | "Send this to a rival fan" on The Wind-Up and The Doomer | Rivalry is football's sharing engine | Nothing; the copy passes the humour checks |
| P6 | Founding-listener number and a referral board | A real, honest reward that costs nothing | D3 |
| P7 | UTM per channel, verified in PostHog | Without it the month teaches nothing | Nothing; one test visit |
| P8 | Close the consent item | Unblocks open marketing and any paid test | D7 |

Never ship or promise personal shows, daily reliability, forecasts or a
price (full-time `docs/21-go-to-market-agent.md`, "Final gate").

## The calendar

From the document's research; the Monday report re-reads the week's
fixtures from a public source before relying on them.

| Week | Matches with shows | The engine's moves | Exit check |
|---|---|---|---|
| Fri 16 to Sun 18 Oct | Matchweek 7 | Sync, rail, the first packs, all held. Sprint 0 briefs. Confirm the beta tag reaches PostHog | The rail on Sunday and Monday mornings |
| Mon 19 to Sun 25 Oct | Including Chelsea v Spurs (Sat 24, 17:30) | If the gate opens: the first personal invites, share lines, first clips (D1) | 100 users; the first finish rate and K |
| Mon 26 Oct to Sun 1 Nov | Including Liverpool v Arsenal (Sun 1 Nov, 16:30) | The founding board if P6 shipped; creators if D5; build-up for Liverpool v Arsenal | 350 users |
| Mon 2 to Sun 8 Nov | Matchweek 10 (confirm) | Show HN on Tuesday 3 Nov if D4 is in force and that match's rail is full; Product Hunt and pitches; the FPL league if D6 | **1,000 users by Sunday 8 November** |
| Mon 9 to Sun 15 Nov | None: international break, 9 to 17 Nov | The weekly "six best arguments" to testers; the feedback push; the first December-bar reading | Day-7 return; 40% "very disappointed" |

## Rulings

The document asks Krish for seven decisions (its section 9). Each one gates
part of this engine, through `rulings.json`. A ruling is in force only when
Krish has made it, a full-time session has recorded it in full-time's
decision log, and this repository marks it approved with that heading as
evidence. Until then the engine drafts the gated work as held items, so
nothing waits on the drafting.

| Ruling | What it decides | What it opens here | Recommendation |
|---|---|---|---|
| D1 | "Invited testers only" read as "invite-led at scale": every tester and every shared edition invites others; fan channels open | TikTok, YouTube, Instagram, X, Reddit | Approve, to take effect when the rail gate opens |
| D2 | Cover every Premier League match each weekend | Nothing directly; the product brief | Approve after one rehearsal weekend fills the rail. About $60 a ten-match weekend at full-time's "roughly $6" a run, before narration |
| D3 | Sign-up and the morning recap for beta users | Nothing directly; the product brief and the user count | Approve |
| D4 | Name Full Time under Krish's own name | LinkedIn, Show HN, Product Hunt, press | Approve, with a written boundary from the Mindmake proof story |
| D5 | Paid creators (up to £600) and one paid test (up to £300) | Creators, ads | Approve only after D7, and after the gate has held open for two weekends |
| D6 | The FPL league, framed as a game | FPL | Approve |
| D7 | Close the PostHog and Google Analytics consent item, with counsel's check | Nothing directly; it is D5's precondition | Approve |

Every send, post, spend or publication still needs Krish's yes at the moment
it happens, whatever ruling is in force.

## Kill switches

| Risk | Signal | Response |
|---|---|---|
| A thin rail on a push day | The gate says HOLD | Hold every push; promote the latest full match instead, if there is one |
| A wrong fact goes out | Any report of a wrong score, name or fact | Stop the clip; escalate to a full-time session the same day; post the correction |
| A rights complaint (crests, data, a club) | A takedown or a letter | full-time's `docs/11-legal.md` runbook; crests come out in one place |
| A Reddit warning | A removed post or a moderator's message | Stop. Reply to the moderators. Never post again from another account |
| "AI slop" | Hostile comments | Lead with the disclosure, Show me why, and the withheld shows |
| Model spend runs away | A run over its ceiling | full-time's spend ceiling stops it; cut to the biggest matches |
| Vanity users | Sign-ups without a finished show | Count only users who meet "The goal" |

## The assumption ledger

| Belief | Confidence | Evidence | What changes it |
|---|---|---|---|
| The rail can reach 4 of 6 on most match mornings | Low | 16 Oct reading: three matches, one AI Pundit each | Two weekends of the gate's readings |
| Fans forward an AI Pundit's show to their club's group chat | Medium | The document's research on podcast recommendations; not yet this product | Users per sharing user once P2 ships |
| A fan who hears two AI Pundits comes back | Unknown | The December bar's second-pundit row | `pundit_switch_committed` among returners |
| Footage-free clips hold attention on football TikTok | Unknown | None yet | Watch time on the first ten clips |
| Krish's network can seed about 100 users | Medium | The document's channel map | Finished shows per invite after the first 50 |
| The build story lands with AI readers | Medium | The document's comparison with bulk AI-podcast farms | Show HN and Product Hunt results, if D4 |

The Monday report updates this table with what the week showed.

## What the engine never does

AGENTS.md has the full rules. In short: it never posts, sends, comments,
likes, follows, DMs, upvotes, uploads, boosts, pays or spends. It never
pushes a fan to a thin rail. It never treats a recommendation as a ruling. It
never invents a number, a quote, a score or a reaction. It never puts a
listener's details in this public repository. It never changes the full-time
repository or the site. Fixes go to Krish as drafts for a full-time build
session.
