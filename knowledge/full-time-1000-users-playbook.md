# Full Time: The 1,000 Free Users in 30 Days Playbook

**Window:** Friday 16 October to Sunday 15 November 2026 · **Product:** fulltime.fm (AI Pundit football audio, Premier League only) · **Goal:** 1,000 free users at a CAC close to zero

***

## 1. The short version

Full Time already has the hardest part of a viral consumer product: an output people want to send to each other. One match becomes six shows, and each AI Pundit is built to start an argument. What it lacks is everything between "a show exists" and "a fan sends it to their group chat". Today has no share button, there is no sign-up prompt after a listen, and the only email capture is a legacy `/waitlist` route that still scrolls. The morning recap is switched off by `PRELAUNCH_MODE`, and only one match a day gets a show, so most fans on a Saturday hear nothing about their own club.

The playbook rests on five moves, in this order:

1. **Prove the rail fills before pushing anyone to it** (17–19 October). September mostly went unpublished (`NOW.md`). Going viral onto an empty rail turns attention into churn.
2. **Cover every Premier League match, not one a day.** Club tribalism drives football audio. Arseblog's Arsecast is the only single-club podcast to appear in every UK sports chart snapshot taken by Castfox in 2026. The measured model cost of a six-pundit run is 2.14 US dollars (`docs/06-ops.md`), so a full ten-match weekend costs roughly 21 dollars in model spend.[^1]
3. **Ship the share loop:** a share button on every edition, a per-edition preview card (the 1200×630 renderer already exists in `src/lib/pundit/share-card.server.ts` but Today doesn't use it), WhatsApp-first share text, and sign-up after the first finished show.
4. **Put vertical video where football and podcasts are found.** YouTube is now the most-used podcast service among US weekly consumers, at 37%. It has also just overtaken Spotify in the UK: 29% against 28%, with BBC Sounds at 15%. Podcast clips on social media are now the leading discovery route (51%), ahead of friends and family (40%), and 63% of clip viewers go on to the full show.[^2][^3][^4][^5][^6]
5. **Pick a few tentpole moments and let them carry the month:** Chelsea v Spurs (24 Oct), Liverpool v Arsenal (Sun 1 Nov, 16:30), and an AI-audience launch built on the "one person, twenty-five checks, about two dollars a run" story.[^7][^8]

**The calendar is shorter than a month.** Premier League matches in the window fall on 17–19 Oct, 23–25 Oct, 31 Oct–2 Nov and 6–8 Nov. The November international break then runs 9–17 November. That leaves about twelve match days and four weekends with shows. **In practice the deadline for 1,000 is Sunday 8 November**, and the break is for re-engagement, not acquisition.[^9][^10]

***

## 2. What the repository says (the constraints that matter)

### 2.1 Current product truth

| Area | State on 16 Oct 2026 | Growth implication |
|---|---|---|
| Lifecycle | Pilot beta, public release targeted for December (`docs/22-vision-and-beta.md`) | Open marketing is gated to a written December bar |
| Access | All six AI Pundits are free, with no account needed (`README.md`) | Zero-friction first listen is a big asset. "Sign up" has no reason to exist yet |
| Coverage | One Premier League match a day; a day with no finished Premier League match publishes nothing (`docs/18-world-class-pundit-system.md`) | Most fans on a Saturday get nothing for their club |
| Reliability | September mostly unpublished. A 12 Oct edition was live on the Reporter RSS feed (`NOW.md`) | Biggest single risk to any viral push |
| Sharing | `?pundit=` and `?drop=` deep links work and preserve the recipient's saved pundit. A share-card renderer exists. Today has no share UI | The loop is 80% built and 0% exposed |
| Retention hooks | Morning recap push is disabled under `PRELAUNCH_MODE`. Follows don't change the show (`product-state.json`) | No reason to return yet, and no habit trigger |
| Analytics | PostHog plus GA4 on every page. The consent item is open (`docs/11-legal.md`) | Needed for attribution. It also blocks paid ads and open marketing |
| Rights | Club crests and the free-tier analytics sources are used unlicensed, by founder ruling. No league marks, broadcast audio or footage (`docs/11-legal.md`) | More visibility means more takedown risk. Creative must stay footage-free |
| Disclosure | AI scripts and synthetic voices are disclosed, and this can't be removed by experiments | It becomes a selling point against "AI slop" competitors |

### 2.2 Rulings already on record that this goal collides with

The documentation is explicit, so the 1,000-user goal needs fresh founder rulings rather than a quiet override:

- **"Krish invites them himself, one at a time; paid promotion stays off"** (`docs/22-vision-and-beta.md`).
- **"Open marketing to football fans starts only when the December release bar … is met. Until then, growth is invited testers only"** (`docs/07-marketing.md`).
- **The consent item must close "before open marketing starts"** (`docs/22-vision-and-beta.md`, `docs/11-legal.md`).
- **The `never_publish` list in `NOW.md`** bars the product name, the domain, the sport, teams and the six AI Pundit names from Krish's anonymised Mindmake proof writing. A build-in-public push under Krish's own name has to separate that "room_face" proof story from the named B2C product. Otherwise LinkedIn, the strongest owned channel, can't name the product.

**The way through without breaking the December bar: "invite-led at scale".** Every tester gets invite links, and every shared edition is itself an invite. The public line stays "free beta, invite only for now", which `07-marketing.md` already approves. This keeps the December bar meaning what it says, which is open marketing, while letting a referral loop do the inviting. Paid ads and creator deals are the only parts that really count as open marketing, and they each need their own ruling (section 9).

***

## 3. Define "user" before chasing 1,000 of them

The current product has no sign-up moment, so "1,000 free users" is undefined until it is pinned down. Recommended north-star:

> **A user is a person who finishes at least one AI Pundit show (`listen_completed`) and leaves a way to reach them: a verified account email, or a push opt-in.**

Reasons:

- It counts real listeners, not page views. `docs/09-growth.md` already warns against optimising opens or page views alone.
- It produces a list the December release can talk to.
- It lines up with the December bar, which needs thirty or more testers who finish a show, a 40% return rate within seven days, and half of returners trying a second AI Pundit.

Track two numbers next to it:

- **Activated listeners:** `listen_completed`, by `utm_source`.
- **Second-pundit rate:** `pundit_switch_committed`. This is the evidence that the six-mind idea works.

**Build needed:** an inline prompt after the first `listen_completed`: "Want tomorrow's show for your club? Get the morning nudge." It runs Supabase magic-link auth plus a club pick. `PRELAUNCH_MODE` must allow the morning recap for signed-in beta users, or this prompt has nothing to offer.

***

## 4. The growth maths

### 4.1 The funnel

Every number below is a **planning assumption** to replace with PostHog readings after the first weekend. None is measured.

| Step | Assumed rate | Visitors needed for 1,000 users |
|---|---|---|
| Visit → press play | 50% | — |
| Play → finish a show | 45% | — |
| Finish → sign up (email or push) | 40% | — |
| **Visit → user** | **≈9%** | **≈11,000 unique visitors** |

Lifting play→finish matters more than lifting traffic. Short editions, a strong first ten seconds and no autoplay surprise all help. Tightening the finish→sign-up prompt from 40% to 60% cuts the traffic needed to about 7,400.

### 4.2 The viral coefficient

With \(i\) = shares sent per user and \(c\) = the share-to-user conversion rate, the viral coefficient is \(K = i \times c\). A seed of \(S\) users grows to roughly:

\[ \text{Total users} = \frac{S}{1-K} \]

| Seed users \(S\) | \(K\) | Total |
|---|---|---|
| 700 | 0.30 | 1,000 |
| 500 | 0.50 | 1,000 |
| 300 | 0.70 | 1,000 |

\(K = 0.3\) works out to, for example, three WhatsApp sends per user at a 10% conversion. That is realistic for a group-chat product with one-tap sharing and a club-specific hook. Robinhood's waitlist reportedly averaged about three referrals per user and reached 50,000 sign-ups in its first week on effectively no ad spend. That was a far more valuable offer than a free football show, so treat it as the top end of what is possible, not a forecast.[^11][^12]

### 4.3 Unit cost: content is nearly free, so spend it

| Item | Cost basis | Estimate for the window |
|---|---|---|
| Model spend, one six-pundit run | 2.14 USD measured (`docs/06-ops.md`) | — |
| Every match, four weekends (≈40 matches) | 40 × 2.14 | ≈86 USD |
| Caveat | The 2.14 figure came from the Anthropic/Haiku bench. The OpenAI fallback was measured far worse on caching in one session (`docs/06-ops.md`) | Budget 3–5× as a ceiling, so a few hundred USD at most |
| Narration (ElevenLabs) | Not measured per run in the repo | Measure on the first weekend |

Even at five times the measured cost, covering every match costs less than one week of modest paid social spend. **Full coverage is the cheapest growth lever in the playbook.**

***

## 5. The product changes that create virality (Sprint 0)

Ship these before the first push. Each one maps to a growth loop already written into `docs/09-growth.md`.

| # | Change | Why it matters | Effort |
|---|---|---|---|
| P1 | **Cover every Premier League match** (ten per weekend), with Today opening on the listener's club if they follow one, else the biggest match | Fans share their own club. One match a day leaves 18 of 20 fanbases with nothing | Ruling plus a scheduler change. The operator `?matchId=` override exists. Check that `daily_drops` allows more than one drop per date |
| P2 | **Share button on every edition**, using the existing 1200×630 share card with pundit cover, match seal and one approved line, plus per-edition `og:image` (Today currently serves one default cover from `__root.tsx`) | A WhatsApp or X preview that shows "The Doomer on Forest 1–2 Arsenal" gets clicked. A generic logo doesn't | Small. The renderer is built and tested |
| P3 | **WhatsApp-first share text, written per pundit**, e.g. "The Wind-Up has thoughts about your back four 👀 [link]" | The group chat is where football banter lives. Nearly two-thirds of podcast listeners get recommendations from friends, family or colleagues, and 72% say they are likely to act on them[^13] | Small |
| P4 | **Sign-up after the first finished show** (magic link plus club pick plus morning nudge) | Turns a listener into a user you can count. It also feeds return visits, which the December bar measures | Medium. Needs a `PRELAUNCH_MODE` ruling |
| P5 | **"Send this to a [rival] fan" on The Wind-Up and The Doomer** | Rivalry is football's natural sharing engine. Inviting a rival is both the joke and the referral | Small. Copy has to pass the humour-safety judge |
| P6 | **Founding-listener number** ("You're listener #312") shown after sign-up, with a referral link that moves you up a public "founding 1,000" board | Robinhood's queue position was "the entire game", and it needed no money or swag[^14][^15]. A real, honest reward costs nothing | Medium |
| P7 | **UTM per channel and per creator** (`utm_source=beta`, `wa`, `reddit`, `tiktok`, `hn`, `creator_x`), verified in PostHog | Without attribution the month teaches nothing. The docs already flag that the beta tag has never been confirmed in PostHog | Trivial |
| P8 | **Close the consent item fast.** Under the Data (Use and Access) Act 2025, analytics used only for aggregate statistics no longer needs opt-in consent. A clear notice and an easy opt-out are still required, and advertising uses are excluded[^16][^17][^18]. PostHog first-party analytics with an opt-out can likely use this exemption. GA4 sharing data with Google, and any ad pixel, need a proper consent banner | Unblocks open marketing and any paid test. Confirm with counsel, as `docs/11-legal.md` requires | Small to medium |

What not to ship: anything promising personal shows, daily reliability, forecasts or a price (`docs/21-go-to-market-agent.md`, final gate).

***

## 6. Channel playbook

Channels are ranked by expected users per pound and per hour. The contribution ranges are assumptions to test, not forecasts.

### 6.1 Channel map

| Channel | Mechanic | Assumed contribution | Cash cost |
|---|---|---|---|
| Krish's own network (WhatsApp, iMessage, LinkedIn DMs, Arsenal mates) | 150 personal invites, each asking the person to forward one show to their club group chat | 75–120 | £0 |
| Referral loop (P2, P3, P5, P6) | Every edition is an invite | +250–400 (at \(K\) ≈ 0.25–0.4) | £0 |
| Vertical video (TikTok, YouTube Shorts, Reels) | 2–3 pundit-versus-pundit audiograms per match day, ≈40 posts | 150–250 | £0 |
| Reddit, club subreddits | Disclosed founder participation and per-club editions in match-thread aftermath | 100–150 | £0 |
| AI and tech audience (Show HN, Product Hunt, AI newsletters, Podnews) | The build-in-public story | 150–250 | £0 |
| Fan micro-creators | "React to the AI Pundit" videos, labelled "Ad" | 100–200 | £300–£600 |
| FPL "Beat the AI Pundits" league | Six pundit-run FPL teams in a public classic league | 50–150 | £0 |
| Paid test (only after P8) | Boost the best organic clip | 25–170 | £300 |
| **Total seed before the loop** | | **≈750–1,300** | **≈£600–£900** |

### 6.2 Vertical video: the engine

Football discovery for under-30s happens in short-form video. TikTok discovery of podcasts is nearly seven times more common among 18–34s than among over-55s. Among people who found a favourite podcast through social media, 60% found it through content shared by someone they follow, against 33% through sponsored content. The #premierleague tag alone shows well over a billion TikTok views.[^19][^13]

Formats, all footage-free (no broadcast clips, no league marks):

- **"Same match, two minds" (15–25 seconds).** Split screen of two screenprint covers. The Romantic's line, then The Doomer's line, about the same scoreline. Captions burned in, with the score in the match seal. End card: "Pick your AI Pundit. fulltime.fm".
- **"Show me why" reveal (20 seconds).** A spicy claim, a tap, the checked fact, then the boundary line ("the data shows what happened, but not always why"). This teaches before it asks, as `09-growth.md` requires.
- **"The Wind-Up vs your club" (10–15 seconds), one per fanbase, posted the morning after.** Tribal, and easy to stitch or duet.
- **Full editions as YouTube videos** with a static or animated cover. YouTube is the top discovery surface: 40% of listeners say they discovered their favourite podcast there. Publish the Reporter RSS to Spotify, Apple and YouTube too, because UK listening is split across YouTube, Spotify and BBC Sounds.[^5][^20][^13]

Production: generate these automatically from the audio, script beats and SVG covers on the same 04:45 UTC run, so the clip is ready before fans wake up. A human approves each post, because the GTM manual forbids publishing without exact approval (`docs/21-go-to-market-agent.md`). Post by 07:30 London on match mornings.

Posting cadence: three clips each match morning across TikTok, Shorts and Reels from one Full Time account, plus one club-specific clip for the two biggest fanbases playing that day.

### 6.3 Reddit: earn the right first

The big communities are large and strict. r/soccer has about 8.8 million members, r/PremierLeague about 5.1 million and r/Gunners about 536,000.[^21][^22]

- r/soccer bans spam and points to the "10% of your history" rule of thumb. It also removes memes, surveys and fantasy-football threads. **Don't post Full Time there.**[^23][^24]
- Reddit's own policy sets no sitewide percentage. Each subreddit's moderators decide, some ban promotion entirely, and Reddit tells accounts that mostly post their own links to slow down or buy ads.[^25][^26]

How to do it well:

- Use Krish's real account in 3–5 club subreddits where he genuinely belongs (r/Gunners first).
- Comment in post-match threads with the actual argument, not a link.
- Only post a link after asking the moderators, ideally as a disclosed "I built an AI thing that argues about our match six ways. Mods OK'd it" post the morning after a big game.
- Never use multiple accounts, cross-post the same link, or ask for upvotes. These are standard ban triggers.[^27][^28]
- Expect one or two good posts in the month, not twenty.

### 6.4 AI and tech launch: the build-in-public story

The repository is an unusually strong story for AI-curious audiences:

- one founder;
- twenty-five gates on every edition;
- about two dollars per six-show run;
- "publish what passed, withhold what did not";
- failures left visible in the commit log (`NOW.md`).

It also lands as the opposite of the AI-podcast backlash. Inception Point AI makes about 3,000 episodes a week at roughly one dollar each and admits most aren't reviewed before release. That has drawn "slop" criticism, and the Castro app now hides its shows from search. Full Time's disclosure and evidence gates are the counter-position.[^29][^30]

Sequence:

1. **Show HN** on Tuesday 3 November, the morning after Liverpool v Arsenal, so all six shows from the weekend's biggest match are live.
2. **Product Hunt** the same week.
3. **Pitch Podnews and two or three AI newsletters** with the cost-per-show and evidence-gate angle.

NotebookLM is the reference case for AI audio. Its Audio Overviews spread because the outputs were worth sharing. Traffic rose 371% in September 2024 to 3.07 million monthly visits, driven by users sharing examples rather than a marketing push.[^31][^32]

This channel needs the `never_publish` ruling in section 2.2, because it names the product under Krish's name.

### 6.5 Fan micro-creators: reaction content

Pay five to ten club fan creators in the 10,000–100,000 follower range £50–£100 each to react on camera to their club's Wind-Up or Doomer edition. Stitch-style reaction is native to football TikTok, and UK lists track hundreds of football creators.[^33]

- **Label every paid post "Ad" upfront.** The ASA and CMA treat any payment or incentive as making it an ad, and the ASA prefers "Ad" over "sponsored", "#gifted" and "#aff".[^34][^35]
- **Label Krish's own posts as well.** Posts about his own product are covered too, because he is commercially connected to the brand.[^36]
- **Give each creator one UTM link.** Rebook the ones whose links produce finished shows, not views.
- **Priority fanbases:** Arsenal, Liverpool, Manchester United and Chelsea, which have the most tentpole matches in the window.

### 6.6 FPL "Beat the AI Pundits"

Almost 8.95 million managers had registered by the 2026/27 Gameweek 1 deadline, and more than 13 million played last season.[^37][^38]

How it works:

- Create a public FPL classic league with six manager entries, one per AI Pundit. Each team is picked by persona: The Numbers Guy by data, The Romantic on vibes, The Doomer full of defenders.
- Fans join with the league code.
- Each Monday's edition can mention the league table as a light segment.

Rules:

- It is a free game, not betting, and must never be presented as forecast performance (`product-state.json` prohibits forecast claims).
- Keep it off r/soccer, which removes fantasy threads.[^24]
- Push it in FPL communities and creator channels instead.
- Needs a ruling, because it puts pundit "picks" in public.

### 6.7 Paid test: last, small and honest

Only run this after P8 closes consent, since ad pixels sit outside the analytics exemption.[^16]

- UK Meta CPCs run roughly £0.30–£1.90 and CPMs £4–£15. TikTok CPMs are often lower.[^39][^40][^41]
- Boost the single best-performing organic clip with £300, split between TikTok Spark Ads and Meta, targeted at UK fans of the two clubs in that weekend's tentpole match.
- Stop if cost per finished show goes above £3.
- Needs a ruling, because paid promotion is currently off.

***

## 7. The 30-day calendar

Fixtures and kick-off times (UK time) come from BBC Sport, Sports Mole, SuperSport, Sky Sports and ESPN. Matchweek 10 (6–8 November) picks and kick-off times weren't confirmed in this research; check them before planning that weekend. Shows publish from the 04:45 UTC run, so a show is ready the morning after its match.[^8][^42][^43][^44][^7]

| Week | Matches with shows | Moves | Exit check |
|---|---|---|---|
| **Wk 0: Fri 16 – Sun 18 Oct** | Sat 17: Everton v Chelsea (12:30), Brentford v Liverpool, Fulham v Hull, Man City v Ipswich, Newcastle v Villa (17:30). Sun 18: Bournemouth v Sunderland, Brighton v Palace, Leeds v Man Utd (14:00), Forest v Arsenal (16:30)[^44] | Record rulings (section 9). Ship P2, P3 and P7. Test UTM tags in PostHog. Run every Saturday match as a private rehearsal; publish if they pass. No push yet | At least one edition by 07:00 on Sun and Mon. Rail ≥4 of 6 |
| **Wk 1: Mon 19 – Sun 25 Oct** | Sat 24: Villa v Man City (12:30), Arsenal v Everton, Coventry v Fulham, Chelsea v Spurs (17:30). Sun 25: Palace v Newcastle, Hull v Brentford, Liverpool v Brighton, Man Utd v Bournemouth, Sunderland v Leeds (16:30)[^44] | Ship P4 and P5. Send 150 personal invites from Sun 18 onward. First vertical clips on Sun 25. First r/Gunners comment work. Recruit creators | 100 users. Finish rate measured. First \(K\) reading |
| **Wk 2: Mon 26 Oct – Sun 1 Nov** | Sat 31: Chelsea v Man Utd and others[^45]. Sun 1: Villa v Fulham (14:00), **Liverpool v champions Arsenal (16:30)**[^7] | Ship P6, the founding-1,000 board. Creator reactions to Chelsea v Man Utd. Build up to Liverpool v Arsenal on both club subreddits (with mod OK) and TikTok | 350 users |
| **Wk 3: Mon 2 – Sun 8 Nov** | Matchweek 10 (confirm fixtures and times) | Mon 2: Liverpool–Arsenal six-way clip blitz. **Tue 3: Show HN, then Product Hunt and Podnews.** Launch the FPL league. Paid test if consent is closed | **1,000 users by Sun 8 Nov** |
| **Wk 4: Mon 9 – Sun 15 Nov (international break)** | None. International break 9–17 Nov[^10] | Weekly digest to the list: "the six best arguments of the month". First December-bar reading. Feedback push (the three questions). Replay the top shows on YouTube | Day-7 return rate. Sean Ellis "very disappointed" ≥40% |

***

## 8. Messaging kit

All of this is drawn from the approved copy in `docs/07-marketing.md` and `docs/21-go-to-market-agent.md`.

- **Core line:** "One match. Six AI Pundits. Pick the brain you fancy."
- **WhatsApp invite (Krish, personal):** "Built a thing: six AI pundits each make their own show about yesterday's game. Same facts, six arguments. The Doomer's take on [match] is brutal. Free beta, no account: [link]. Tell me which one you'd pick."
- **Rival share:** "The Wind-Up has a message for [rival] fans. [link]"
- **Founding listener:** "You're founding listener #[n]. Send a show to your group chat and climb the board."
- **AI audience:** "Six AI-made football shows a match, each gated by 25 checks, for about two dollars a run. What passed publishes; what didn't is withheld."
- **Always include:** "free beta", "AI-written, synthetic voices", and one call to action.
- **Never use:** "daily without fail", "your personal pundit", "unbiased", predictions, prices, "December launch", league logos or match footage.

***

## 9. Decisions needed (decision ledger)

| # | Decision | Recommendation | Why |
|---|---|---|---|
| D1 | Read "invited testers only" as "invite-led at scale" (testers and shares invite others) | **Approve** | Keeps the December bar honest while letting the loop run |
| D2 | Cover every Premier League match each weekend instead of one a day | **Approve** | Tribal sharing. About 21 USD per weekend at the measured cost |
| D3 | Turn on account sign-up and the morning recap for beta users under `PRELAUNCH_MODE` | **Approve** | No sign-up means no "users" to count and no return trigger |
| D4 | Split the `never_publish` proof narrative from named B2C marketing under Krish's name | **Approve, with a written boundary** | Unlocks LinkedIn, HN and Product Hunt |
| D5 | Paid creators (≤£600) and a paid ad test (≤£300) | **Approve, with consent closed first** | Paid promotion is currently off by ruling |
| D6 | FPL "Beat the AI Pundits" league | **Approve, framed as a game** | 9–13M FPL managers. No forecast claims |
| D7 | Close the PostHog/GA consent item using the DUAA analytics exemption plus a banner for GA and pixels | **Approve, with counsel check** | Blocks open marketing and paid ads |

Each external send, post, spend or publication still needs Krish's exact approval at the moment it happens, as `docs/21-go-to-market-agent.md` requires.

***

## 10. Risks and kill-switches

| Risk | Signal | Response |
|---|---|---|
| Empty or thin rail on a push day | Fewer than 4 of 6 pundits by 07:00 | Hold that day's push. Promote the latest full edition instead |
| A wrong fact goes viral | Any tester or comment reports a wrong score, name or fact | Pause the clip. Trace it to the gate. Post a public correction (the product's own doctrine) |
| Rights complaint (crests, data source, club) | Takedown or legal letter | Use the `docs/11-legal.md` takedown runbook. Crests come out in one place (`ClubCrest`) |
| Reddit ban | Removed posts or a mod warning | Stop. Message the mods. Never post again from another account |
| "AI slop" backlash | Hostile comments on clips | Lead with disclosure, Show me why, and withheld editions. That is the difference from bulk AI podcast farms[^29][^30] |
| Cost overrun on the OpenAI bench | Per-run spend above the ceiling | `PUNDIT_MAX_STEP_COST_USD` already stops runs. Cut to the top five matches |
| Vanity users | Sign-ups without `listen_completed` | Count only users who meet the section 3 definition |

***

## 11. Weekly scorecard

Read this every Monday from PostHog and the inbox:

- **Users:** finished a show plus email or push, by `utm_source`.
- **Viral coefficient \(K\):** share clicks that became users, divided by sharing users.
- **Funnel:** play rate, finish rate, sign-up rate.
- **Second-pundit rate:** `pundit_switch_committed`, among returners.
- **Day-7 return rate.**
- **Rail fill:** median published pundits per match.
- **Cash and model spend per user.**
- **Wrong-fact reports.** Target zero.

These line up with the December release bar in `docs/22-vision-and-beta.md`. Hitting 1,000 this way also builds the evidence for the December decision.

---

## References

1. [Best UK Sports Podcasts 2026: Top 20 Ranked by Data](https://www.castfox.net/blog/best-sports-podcasts-uk-2026) - **About this show:** The original Arsenal podcast from arseblog.com, out twice a week, usually Monda...

2. [Edison: Every Podcast Frequency Measure Hits Record](https://radioink.com/2026/06/05/edison-every-podcast-frequency-measure-hits-record/) - YouTube is now the most-used service for podcasts among weekly consumers at 37%, up from 31% two yea...

3. [Edison: YouTube overtakes Spotify as U.K.'s top podcast platform - RedTech](https://www.redtech.pro/youtube-overtakes-spotify-uk-podcast-platform-edison/amp/) - The company says Edison Podcast Metrics U.K. shows that 29% of weekly podcast listeners aged 15 and ...

4. [The Number 1 Podcast Platform - SSRS](https://ssrs.com/insights/number-one-podcast-platform/) - As of Q3 2026, YouTube has the highest percentage of U.S. weekly podcast consumers who say it’s the ...

5. [Youtube overtakes Spotify in the UK for podcasts](https://podnews.net/update/youtube-spotify-uk-pref) - - The data says 29% of weekly British podcast listeners, aged 15+, “choose YouTube as the service th...

6. [Podcast Pulse 2026: The format argument is over.](https://www.acast.com/en-ca/news-and-insights/podcast-pulse-2026-the-format-argument-is-over) - 51% of fans find new shows through podcast clips on social media.
40% find them through friends and ...

7. [Premier League fixtures on Sky Sports: Liverpool vs Man City and Arsenal plus Leeds vs Man Utd live in October and November](https://www.skysports.com/football/news/13574076/premier-league-fixtures-on-sky-sports-liverpool-vs-man-city-and-arsenal-plus-leeds-vs-man-utd-live-in-october-and-november) - Liverpool vs Arsenal - kick-off 4.30pm, live on *Sky Sports*

8. [Arsenal 2026-27 Fixtures - ESPN (UK)](https://www.espn.co.uk/football/team/fixtures/_/id/359/arsenal) - |Sun, 1 Nov|Liverpool|v|Arsenal|4:30 PM|English Premier League| |

9. [Three weeks without club football: What's really behind ...](https://www.thedailystar.net/sports/football/news/three-weeks-without-club-football-whats-really-behind-new-international-break-4278946) - The Premier League will resume on October 10, with Arsenal hosting Leeds United in matchweek 6.

10. [What are the key dates for the 2026-27 football season?](https://www.bbc.com/sport/football/articles/cd0m840p7d1o) - - International break: Monday, 9 November to Tuesday, 17 November, 2026

11. [Case Studied: Vol 38. Robinhood: Winning waitlist](https://vendry.beehiiv.com/p/robinhood) - That number grew to over 50,000 in the first week and reached nearly 1 million in the first year.

12. [7 Waitlist & Product Launch Statistics (Backed by Data)](https://waitlister.me/growth-hub/blog/waitlist-and-product-launch-statistics) - **Robinhood collected nearly 1 million waitlist signups before it launched — with effectively $0 in ...

13. [YouTube And Social Media Boost Podcast Discovery Study Suggests](https://www.forbes.com/sites/frankracioppi/2026/07/07/podcast-listeners-use-youtube--social-media-for-podcast-discovery/) - Among listeners who discovered a favorite podcast through social media, 60% found it through content...

14. [getlaunchlist.com › blog › waitlist-referral-programWaitlist Referral Programs: How to Build a Dropbox-Style ...](https://getlaunchlist.com/blog/waitlist-referral-program-guide) - Robinhood used a similar referral queue to amass roughly 1 million pre-launch signups.

15. [How Robinhood Got a Million People on Their Waitlist](https://waitlister.me/growth-hub/case-studies/robinhood) - The real testament to their strategy's effectiveness came over the following year, as their waitlist...

16. [UK Data (Use and Access) Act 2025: A Compliance Guide](https://usercentrics.com/knowledge-hub/data-use-and-access-act-2025-duaa-compliance/) - There are conditions, however: you must clearly explain the use, offer a simple, free way to opt out...

17. [Data (Use and Access) Act 2025 – Cookies - BM Insights](https://www.blakemorgan.co.uk/data-use-and-access-act-2025-cookies/) - These ‘low risk’ analytics cookies are **not** strictly necessary cookies – that exception disapplie...

18. [Schedules | ICO](https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-duaa-summary-of-the-changes/schedules/) - - the storage or access is for the sole purpose of enabling a service provider to collect informatio...

19. [#premierleague on TikTok — 2.3K videos, 1.2B views](https://tokgauge.com/id/tag/premierleague) - #premierleague on TikTok — 2.3K videos, 1.2B views

20. [People Discover Podcasts Via New Methods Impacting ...](https://www.forbes.com/sites/frankracioppi/2026/08/07/people-discover-podcasts-via-new-methods-impacting-what-shows-succeed/) - Among listeners who discovered a favorite podcast through social media, 60% found it through content...

21. [r/Gunners Stats: Subreddit Analytics & Growth](https://freesubstats.com/r/Gunners) - r/Gunners is a Soccer/Football subreddit in the World category with 536,238 members. Use this page t...

22. [r/PremierLeague](https://prowlo.com/tools/subreddit-stats/premierleague) - We don't have a promo-tolerance read for r/PremierLeague yet.

23. [Reddit](https://www.reddit.com/r/soccer/wiki/faq/) - You should read the reddit.com spam / self-promotion guidelines and then message the moderators to t...

24. [9: Please use factual and objective titles](https://www.reddit.com/r/soccer/wiki/rules/) - Threads requesting GIFs, and threads about betting, video games, surveys, fantasy football, kits, li...

25. [Reddit Self-Promotion Rules (2026): 6 Official Policies ...](https://www.mediafa.st/reddit-self-promotion-rules-guide) - The famous 10% rule is older guidance, not a current sitewide rule.

26. [How to Promote on Reddit Without Getting Banned (2026 Rules)](https://parsestream.com/guides/reddit-self-promotion-rules) - The famous 9:1 rule is not a Reddit rule.
It appears as “a widely used rule of thumb” in Reddiquette...

27. [The complete guide to Reddit self-promotion rules in 2026](https://redship.io/blog/reddit-self-promotion-rules) - The most commonly cited guideline is the 90/10 rule: roughly 90% of your activity should be genuine ...

28. [Reddit Self-Promotion Rules: The Complete Guide (2026)](https://getupvotes.com/reddit-self-promotion/) - The general rule is that **only 10% or less of your posting and conversation should link to your own...

29. [The Dollar Episode: Inception Point's Podcast Arbitrage](https://www.implicator.ai/the-dollar-episode-how-inception-point-ai-turned-podcasting-into-arbitrage/) - Inception Point AI produces 3,000 podcast episodes per week with eight employees, spending roughly $...

30. [Castro Hides AI Podcasts In Searches, But Creator Inception Point Defends Its Model.](https://www.podcastnewsdaily.com/news/castro-hides-ai-podcasts-in-searches-but-creator-inception-point-defends-its-model/article_210dfc76-0d85-4db2-aa41-f00481865682.html) - It reportedly has had 10 million downloads since launching in September 2023, with its roster of pro...

31. [NotebookLM's growth playbook: from accidental podcast to $9 ...](https://neodrop.ai/post/OBmUDtY2s0O) - People began posting their Audio Overviews to X and LinkedIn — not to explain the tool, but because ...

32. [NotebookLM Audio Overviews: AI Podcast Feature Explained ...](https://williamspurlock.com/blog/notebooklm-audio-overviews-podcast-october-2024/) - NotebookLM saw a staggering 371% traffic increase in September, jumping to 3.07 million monthly visi...

33. [Top 20 British Football TikTokers on TikTok (Sep 2026)](https://www.modash.io/find-influencers/tiktok/united-kingdom/football) - We found 656 football TikTokers in United Kingdom
...
237.3k

34. [Like, follow and subscribe to our influencer marketing advice](https://www.asa.org.uk/news/like-follow-and-subscribe-to-our-influencer-marketing-advice.html) - The disclosure can’t be hidden or in tiny font or obscured so consumers will struggle to see.

35. [Recognising ads: Social media and influencer marketing](https://www.asa.org.uk/advice-online/recognising-ads-social-media.html) - The CAP Advertising Guidance notes on 'Advertisement features' and 'Recognition of advertising: onli...

36. [Remit: Social media](https://www.asa.org.uk/advice-online/remit-social-media.html) - If an influencer receives payment or any other incentive (requested or unsolicited) from a brand, or...

37. [FPL Gameweek 1 Stats: Ownership, Captaincy & Chips](https://www.fantasyfootballfix.com/blog-index/fpl-gameweek-1-stats-ownership-captaincy-chips/) - A total of **8,945,344 managers** had registered an FPL team when the Gameweek 1 deadline passed.

38. [FPL basics explained: How to register - Premier League](https://www.premierleague.com/en/news/2173986) - Over 13million managers played the game last season and you can join them in 2026/27.

39. [Best Social Media Advertising Platforms for UK Businesses](https://fueler.io/blog/best-social-media-advertising-platforms-for-uk-businesses) - Average UK CPMs range from £9.00 to £18.00, while average CPCs fall between £0.65 and £1.90 dependin...

40. [Social Media Advertising UK Costs CPC CPM Platform Trends 2026](https://www.global-fin-info.com/social-media-advertising-uk/) - For a standard campaign, expect a **CPM (Cost Per Mille) of £6.50 to £12.00** on Meta, while **TikTo...

41. [peakdigital.online › meta-ads › facebook-ads-cost-ukHow Much Do Facebook Ads Cost In The UK? 2026 Prices](https://peakdigital.online/meta-ads/facebook-ads-cost-uk/) - |Cost per 1,000 impressions (CPM)|£4 to £15|Reach and awareness, billed per thousand views|

42. [www.sportsmole.co.uk › football › premier-leaguePremier League 2026-27 Fixtures - Football - Sports Mole](https://www.sportsmole.co.uk/football/premier-league/fixtures.html) - Leeds
Gameweek 7
...
Man Utd
Brighton

43. [Premier League Upcoming - SuperSport](https://supersport.com/football/tour/premier-league/fixtures) - Matchweek 8 | Villa Park
Aston Villa
Aston Villa
Manchester City

44. [Premier League - Scores & Fixtures - Football - BBC Sport](https://www.bbc.com/sport/football/premier-league/scores-fixtures/2026-10) - - Aston Villa versus Manchester City kick off 12:30
A VillaAston VillaAston Villa

45. [Full list of Premier League fixtures 2026/27: Every club ...](https://www.lbc.co.uk/article/premier-league-fixtures-2026-27-revealed-full-list-5Hjdbph_2/) - **Saturday, October, 17, 2026**
Bournemouth v Sunderland - 3pm

