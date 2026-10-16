# Job: the product and the share loop (Wednesday)

Kind `conversion`. "Sprint 0" and "The loops" in `PLAYBOOK.md`. Time for
Krish: about 10 minutes. Every fix here is a draft: a brief for a full-time
build session, or exact clicks for Krish. You never change the site, the
full-time repository, PostHog, Vercel or Supabase.

1. `python3 growth.py sync`. Use the `fulltime_sha` it prints. Read
   full-time's `docs/product-state.json` (shipped behaviour and gaps) and
   `docs/09-growth.md` (the events) from the sync, so each fix names the file
   or route it touches.
2. **The rail first.** If the push gate is HOLD, the first item is the rail:
   - which matches published, with how many AI Pundits each;
   - which AI Pundits failed on the newest match, as far as public pages
     and full-time's commits show it;
   - the brief for a full-time session: read the stored verdicts
     (`harness_runs`) for that drop before touching any prompt, as
     full-time's AGENTS.md orders, cheapest instrument first.

   Never propose a paid pipeline run. Spending is Krish's call, quoted
   with its arithmetic by the session that runs it.
3. **Walk the fan's path** (read only), on a phone-sized window and inside
   the in-app browsers if the signed-in browser offers them:
   - open a tracked share link for a full match; does the preview (title,
     image) name the AI Pundit and the match, or is it the default cover?
     (Read the page's `og:` tags.)
   - play a show; is there a share button; does the shared link open the
     same match and AI Pundit for the recipient without overwriting their
     own choice?
   - finish a show; is there anything to sign up for, and a reason to come
     back?
   - do the `utm_` tags reach PostHog (once Krish confirms one test visit)?
4. **Sprint 0 status.** Mark each of P1 to P8 (PLAYBOOK, "Sprint 0") done,
   in a pull request, not started, or waiting on a ruling, with what you saw
   on the live site and in `local/state/FULLTIME-NOW.md` (open pull requests,
   recent commits).
5. One item per fix, at most 6, the biggest blocker to 1,000 first:
   - `platform: site` (a brief for a full-time session) or `other` (clicks
     for Krish);
   - `target_url`: the exact page;
   - `why`: what it costs now, in fans lost;
   - `text`: the brief: what to change, where (file or route from
     product-state), how to prove it (the event or readback), and what it
     must not change (the no-scroll frame, the evidence gates, the AI
     disclosure). Start each line of new public words with `Copy:`,
     `Headline:` or `Title:`.
6. Headline: for example "Product: rail 1 of 6 is the blocker; share button
   still missing; 2 of 8 Sprint 0 items done". Check, then post.
