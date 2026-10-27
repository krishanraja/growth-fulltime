# Copy doctrine: how this engine applies the corpus

Before selecting a take or reviewing a clip, apply [Listening quality before growth production](docs/LISTENING-STANDARD.md). A caption cannot rescue dull source audio. Keep human listening approval separate from technical checks and preserve the exact published performance in the listening destination.

The source is [The Copywriting, Offers and Demand Corpus](knowledge/copywriting-offers-demand-corpus.md),
kept byte for byte ([manifest](knowledge/sources.json)). This file is how Full
Time's engine uses it: read it before drafting or reviewing any pack item.
Where they disagree, AGENTS.md, PLAYBOOK.md, EXECUTION-PLAN.md and this file
win (see the list at the end).

## The job copy does here

North Star: most new listeners arrive because a fan shared an AI Pundit's
take. So the unit of persuasion is **the take**: one AI Pundit's argument from
a published edition, quoted exactly. Copy has two jobs: make a take easy to
pass on, and make the first tap land on that exact edition. People buy a
change they already value (Part I, The governing principle); after a match,
fans want to hear it argued about and to have something to send the group
chat. "Demand before prose" (Final Operating Doctrine 1) means the match is
the demand: never write for a match the rail cannot serve (AGENTS.md, rule 3),
and never ask prose to rescue a weak take (Breakthrough Advertising).

## Audience, awareness and lead by surface

Awareness from Breakthrough Advertising; leads from Great Leads and Phase 7.

| Surface | Reader | Awareness of Full Time | Lead | Status |
|---|---|---|---|---|
| Brand short video: TikTok, Instagram Reels, YouTube Shorts (pushed daily, ruling 2) | Fans of the clubs in that match | Unaware | Story or Proclamation: the take itself, quoted | Per take once its show is published (ruling 1), after D7, handles and readiness |
| Derived brand cards and text: Threads, X, Facebook, WhatsApp Channel | Same | Unaware | Story or Proclamation | Derived from the vertical master (ruling 2) |
| WhatsApp share text, sent voluntarily by a listener | The listener's friends | Unaware of the product, warm to the sender | Story or Proclamation, short, in a fan's words | The North Star channel |
| Email to inbound or opted-in listeners | People who asked | Product aware to most aware | Offer: this edition, for this match, is up | Permission must cover the purpose |
| Site, feed and share previews | Someone who tapped a shared take | Solution or product aware for that match | Promise or Offer: the match and AI Pundit they were sent | Changes are briefs to full-time |
| Internal items (`site`, `other`) | Krish | Not persuasion | Plain status | Public lines still follow the copy rules |

**Sophistication.** Football opinion is crowded; bigger claims about analysis
will not be believed. Dramatise the experience and identify with the fan
(late-stage advice). The canon's mechanism, several AI Pundits arguing the same
match differently and disclosed as AI, is the second beat; the take leads.

## Rule of One and the take test (Great Leads, Reality in Advertising)

One reader (fans of this match), one take (one AI Pundit's quoted argument,
or exactly two for a clash), one emotion (the take's own), one promise (hear
the rest of the argument), one supporting fact (the real match, from the
rail), one action (the one tracked link). A clash is still one idea, "the
same match, argued two ways", and never a one-edition preview pretending to
be a comparison (PLAYBOOK.md, Creative).

The USP test becomes a take test; all three gates must pass. **Proposition:**
it says something concrete about a moment or decision, not a mood.
**Uniqueness:** a named AI Pundit's view that differs from the obvious reading
or from another AI Pundit on the same match. **Selling force:** a fan would
send it to a friend; if not, choose another take rather than decorate a weak
one. Positioning lines come from the synced canon (docs/01-brand.md,
docs/07-marketing.md); do not write a new brand promise here.

## Feature, benefit, proof (The Copywriter's Handbook)

| Feature (canon) | Consequence | Fan benefit | Allowed proof | Qualification |
|---|---|---|---|---|
| Several AI Pundits on one match | Different arguments about the same match | Hear your side and the other side | Two published editions of the same match, quoted exactly | Only when the rail has them |
| Exact edition link | The tap opens that AI Pundit's show for that match | No hunting | `growth.py link` validates the drop and AI Pundit | Real destination only |
| Published audio | The voice, not a summary | Hear it before deciding | The clip itself, timing reviewed | AI and synthetic voice disclosed |
| Pilot beta access | Listening as the live site describes it | Low effort to try | The live site | No price, timing, every-match or personalisation promise |

## Value Equation: the offer is the listen ($100M Offers)

Nothing is sold: the offer is the listen. Levers move by take and path only.

- **Dream outcome:** the match you care about, argued with conviction, and a
  line worth passing on. Raise it by choosing a stronger take.
- **Likelihood:** real match, exact quotation, named AI Pundit, AI disclosed.
  The clip is a sample (Scientific Advertising: "use samples or previews when
  experience collapses uncertainty").
- **Time delay:** the link opens the exact edition. Never promise when or how
  often shows appear (AGENTS.md, rule 5).
- **Effort:** one link, one action, a mobile path that works; Shorts links are
  not assumed clickable (PLAYBOOK.md, Work order 5).

A lever needing a product change (share metadata, exact-edition landing, a
way back) is a brief for full-time. Return listening (`returners_7d`) is the
product's continuity; it is never sold.

## Core Four on this engine's channels ($100M Leads)

| Lane | Here | Status |
|---|---|---|
| Warm one-to-one | Personal invites, Krish's contacts | Excluded |
| Warm one-to-many | Opted-in email; a brand channel's own followers | Permitted when permission and gates pass |
| Cold one-to-one | Cold email, DMs, press or creator pitches | Excluded |
| Cold one-to-many, organic | TikTok, Reels and Shorts daily, derived cards elsewhere (ruling 2) | Active per take once a format is ready (rulings 1 and 7) |
| Cold one-to-many, paid | Ads, boosts, paid creators, prizes | Excluded |
| Others to many (referrals) | Listeners sharing a take | The North Star |

"Hope is not a channel": draft share text a listener can send as is, brief
exact-edition share previews to full-time, and measure `shares_attempted` and
`attributed_new_completers`. One motion at a time is PLAYBOOK.md, Work order 5.

## Proof: what may appear in public copy (Phase 6 hierarchy)

Allowed, strongest first: **product demonstration** (rung 2: published audio
and exact transcript quotations, timing reviewed); **process and mechanism**
(rung 6: only what the synced canon says about how Full Time works); **match
facts** (clubs and score from the rail or live site; `growth.py check` refuses
a score that does not match).

Not allowed: observed outcomes, case studies and aggregate data (rungs 1, 3
and 4; MEASUREMENT.md rates are internal evidence, never public claims),
outside research and market statistics (rung 5), credentials (rung 7), and
testimonials or ratings (rung 8; none is approved). Argument (rung 9) appears
only in an AI Pundit's quoted words; unsupported assertion (rung 10) never.
The creative record (creative ID, drop, AI Pundit, source commit, asset
receipt with transcript timestamps) is this engine's proof card.

## Diagnose a weak draft: the persuasion chain

Fix the weakest link first (Part I); separate evidence from prose problems.

| Link | Question for a Full Time item | Usual fix |
|---|---|---|
| Relevance | Does it name the match this fan watched? | Name the clubs and the moment; no league or broadcaster marks |
| Attention | Is the first line the take? | Cut set-up and "we"; open on the quotation |
| Desire | Would a fan send this on? | Choose a different take |
| Difference | Is an AI Pundit's view visible, or two contrasting views? | Name the AI Pundit; pair a real opposite |
| Belief | Exact quote, real audio, right score, AI disclosed? | Re-read the transcript and rail |
| Value | Does the tap open that exact edition? | Rebuild the link with `growth.py link` |
| Safety | Is anything hidden or overstated? | Disclose AI; remove any implied promise |
| Timing | Is the only "why now" the match itself? | Remove invented deadlines |
| Action | One call to action, one tracked link? | Delete the second ask |

## Checklists (Part VIII, adapted)

**Before drafting:** gates read and holds known (AGENTS.md, rules 3 and 4);
surface, awareness and lead set from the table above; take passed the take
test, with exact quotation and timing checked; one reader, one take, one
action; proof only of the allowed kinds; experiment and creative ID known;
`whole_match` set to true or false (AGENTS.md, how the rulings run in code).

**Before handoff**, run the edit passes (Part IV, Phase 9):

- **A, Strategy:** one reader, one awareness level, one take, one action.
- **B, Evidence:** every claim traces to the transcript, rail, live site or
  canon; nothing invented; limits visible (beta, AI).
- **C, Flow:** each line earns the next; the take bridges to the link.
- **D, Clarity:** UK English, familiar words, "AI Pundit" exactly, within the
  channel limit, no em dashes.
- **E, Action:** one call to action, a tracked link from `growth.py link`, a
  mobile path that works.

Then run `python3 growth.py check` on a draft, or `python3 growth.py pack check` on a matchday pack (the floor), and score the rubric.

## Rubric for packs (Part VI, adapted)

Score 0 to 4 on each of the corpus's twelve dimensions. A 4 here means:

| Dimension | 4 for a Full Time item |
|---|---|
| Audience | Fans of one named match, on one surface |
| Desire | A take a fan would send on |
| Awareness fit | Lead matches the surface table |
| Differentiation | A named AI Pundit's view, or two contrasting views |
| Offer value | The tap opens the exact edition on a working mobile path |
| Proof | Exact quotation, published audio, verified match facts |
| Clarity | Understood in one read on a phone |
| Flow | Take, then mechanism, then link; nothing extra |
| Objections | "Is this AI?" and "Is this my match?" answered in the item |
| Ethics | AI disclosed; no betting, imitation, pressure or invented proof |
| Action | One call to action and one tracked link |
| Measurement | Creative ID, experiment ID where relevant, tracked destination |

Use the corpus's bands: 0 to 15 do not hand off, 16 to 27 major revision, 28
to 37 targeted correction, 38 and above test against the control. Ethics and
Action must score 4; less breaks AGENTS.md rules 6 and 7. A score never lifts
a hold or overrides `growth.py check`. Record the diagnosis in the item's
`why` in one line, for example `awareness unaware; lead story; weakest link
belief; rubric 33/48`. HOLD runs do not create items just to score them.

## Test record and learning ledger (Tested Advertising Methods, Phase 12)

The corpus's test record maps onto `growth.py experiment`, with no new fields:

| Corpus field | Engine field |
|---|---|
| test_id | experiment `id`, immutable; a changed test needs a new ID |
| decision_question, hypothesis | `hypothesis` |
| audience | `audience` |
| control, challenger | `changed_variable` (one only) plus creative IDs: same concept `C`, new hook `H` or version `V` |
| primary_metric | `primary_metric` from MEASUREMENT.md; platform attention is 24 and 72 hour triage only |
| guardrails | `guardrails`, always including no additional marketing cash |
| start_date, end_date | `duration_days` (seven or more), result `started_on` and `ended_on` |
| result | result `value` (null when missing), `sample`, `evidence_ref` |
| decision | adopt_challenger is `scale`, retest is `iterate`, keep_control is `kill` for the challenger or `hold`; underpowered results become inconclusive automatically |
| context, learning, next_test | weekly review findings, `kill_list` and `double_down` |

Test in this order: which take (AI Pundit and argument), then lead and hook,
then proof (which quotation, how long), then call to action and path. Market,
offer and price tests are briefs for full-time. Keep negative results: "record
context, not just winners" is how the engine learns which takes travel.

## Where this engine's rules change the corpus

Each change is recorded so no session "fixes" it back:

1. **No paid lane.** No ads, boosts, paid creators or prizes; £0 incremental
   marketing cash. The paid Core Four lane, paid scaling and the spend items
   in "Before scaling" do not apply.
2. **No cold outbound and no personal accounts.** No cold email, DMs, press or
   creator pitches ("Direct outreach structure" is unused). No personal social
   accounts, Krish's contacts, personal WhatsApp groups or personal invites.
3. **No invented scarcity, urgency, guarantees, testimonials, statistics or
   audience proof.** The $100M Offers enhancers (bonuses, value stacks,
   guarantees, scarcity, deadlines) are not used; the only "why now" is the
   real match. `growth.py check` refuses fake proof and urgency.
4. **Agents draft, Krish acts.** Calls to action, follow-ups and email
   sequences are drafted only. Nothing is sent, posted, published or
   scheduled; an approval binds one exact payload; publication is recorded
   only after a human action (AGENTS.md, rules 1 and 10).
5. **Offer, pricing and product changes are briefs.** Value Equation, offer
   canvas and Money Models work becomes a brief for full-time, never an
   engine action. Full Time is a free pilot beta: no price, timing,
   every-match or personalisation promises.
6. **No betting framing and no living-pundit imitation.** No football
   footage, player likenesses or broadcaster or league marks; AI and synthetic
   voices disclosed. Cashvertising's status and competition motives never
   lean on betting, fear or rivalry abuse.
7. **Full Time's voice beats the corpus's craft defaults.** UK English, "AI
   Pundit" exactly, simple words, one call to action, no em dashes, no filler,
   channel limits. Long-copy advice, the 500 to 800 word lead and the headline
   grid are thinking tools, not output.
8. **Gates still hold.** The per-take gate (ruling 1: the exact show published,
   four of six only for a whole-match post) and rule 4 (verified brand identity,
   channel rulings) apply whatever the rubric says. "Validate in market" comes only after the gates
   pass and Krish acts.
9. **Market statistics stay in the documents.** No figure cited in the corpus
   enters public copy (as knowledge/README.md, item 4, for the playbook).
10. **Behaviour is measured the engine's way.** Revenue, lead cost, payback
    and lifetime value do not apply; there is no revenue. Outcomes follow
    MEASUREMENT.md, missing stays missing, and a rubric score is never a
    performance claim.
11. **Research is narrow and aggregate.** Interviews, reviews, communities and
    voice-of-customer records become aggregate data and at most three public
    sources a run. No person-level records or personal inspection, and never
    quote a listener.
12. **No sales conversations.** Browne's discovery and close steps, the sales
    discovery guide and the objection matrix's price rows do not apply.
13. **Templates are thinking tools.** Part V templates add no pack,
    experiment or report fields; contracts and the protocol are unchanged.
