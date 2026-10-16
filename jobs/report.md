# Job: the weekly report (Monday 08:00)

Kind `report`. "Measurement" and "Decisions" in `PLAYBOOK.md`. Time for
Krish: about 15 minutes.

1. `python3 growth.py sync`. Use the `fulltime_sha` it prints. Note every
   canon change and every ruling recorded this week, from
   `local/state/FULLTIME-NOW.md`.
2. Read the week: `python3 growth.py read --days 8` (every pack, the daily
   numbers) and `local/creatives.csv` (what Krish posted and sent, and each
   creative's numbers).
3. Work out, from real numbers only, the playbook's weekly scorecard:
   - **users** (finished a show and left a way to reach them), by
     `utm_source`, against 1,000 by Sunday 8 November;
   - **the viral coefficient**: users who arrived through a shared link,
     divided by users who shared, when PostHog can show it;
   - **the funnel**: visit to play, play to finished show, finished show to
     sign-up;
   - **the second-pundit rate**: `pundit_switch_committed` among returning
     listeners;
   - **day-7 return**;
   - **rail fill**: the median number of AI Pundits per match this week, and
     how many match mornings the gate was OPEN;
   - **spend**: cash, and the model spend full-time's runs recorded (from
     its canon or numbers Krish shares; never estimated), per user;
   - **wrong-fact reports**: the target is zero.
4. **The December bar.** Read each row of the bar in full-time
   `docs/22-vision-and-beta.md` against this week's numbers, and say which
   rows pass, fail or cannot be read yet.
5. Write the report as items (`platform: other`), one short section each,
   answering:
   1. Is the rail full enough to push? If not, what is the one product fix
      that would fill it?
   2. Which AI Pundit gets finished, and which gets switched to?
   3. Which fanbase brought the most finished shows?
   4. Which format earned the most shares per view?
   5. Which step in the funnel loses the most fans?
   6. Which channel helped that last-click hides (the group chat)?
   7. Which creative family deserves ten derivatives?
   8. Which work took Krish's time and moved nothing?
   9. Which ruling, if Krish made it this week, would move the number most?
   10. What single constraint limits growth now: the rail, attention,
       sharing, sign-up, return, trust or rights?
6. Then:
   - **Scale, iterate, hold or kill**, for each creative family, channel and
     job, with the evidence.
   - **The assumption ledger** (PLAYBOOK): update each row's confidence and
     say which one moved.
   - **Next week**: the fixtures (read the week's Premier League fixtures
     from a public source today), the targets, the one concept family to
     lead with, and any job to change, for Krish to keep or kill.
7. End with one call and one counterpoint. Headline: the week in one plain
   line, for example "Week 2: 140 users of 1,000, rail median 4, the Doomer
   rival lines are the winner". Check, then post.
