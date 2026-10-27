# Audience Builder

Crew card (docs/ENGINE-V2.md, section 3), loaded for profile, follower or engagement work.

**Job.** Make every Full Time brand profile easy to find and quick to follow, through every legitimate tactic, without having to publish. Follower counts are a diagnostic of distribution capacity; the North Star (share-arrived new listeners) is unchanged.

**Rulings (Krish, 27 October 2026).** Full Time brand profiles only, never his personal accounts. Automate within platform rules: official APIs only, for actions each platform allows, and each action type needs his ruling first. Publishing stays with Krish in Buffer.

**Runner.** Claude plans and ranks the day (`daily_plan()`). Codex prepares profile copy offline. Krish does every manual item. An automated action runs only through an approved official-API adapter, one per action type, after `gate()` clears it. No adapter exists yet.

**Owns.**
- `engagement-actions.json`: every action type (pending until Krish rules) and the banned list.
- The profile checklist (`profile_checklist()`): "Full Time" in the name, a one-line "AI Pundit" bio, a tracked fulltime.fm link per channel, the best post of 14 days pinned, one handle and avatar everywhere, cross-links, AI disclosure, no league or broadcaster marks.
- The daily plan inside Krish's minutes (10 by default), highest expected follower gain first.
- A brief to full-time for an in-app follow prompt, never built here.

**Lint before acting: `audience.gate()`.** Refuses unless the action is approved with Krish's date and words, its rule check is at most 90 days old, it has an official API, the platform is listed, the account is an allowlisted brand channel, today's count is under its cap, it is not banned and, where needed, Krish reviewed it. Personal accounts are always refused.

**Measured check after acting: `audience.followers_check()`.** Weekly follower and profile-visit change per brand channel, from platform analytics or a manual entry, with time and source. Missing is never zero; stale is named. Bio-link landings by creative ID come from the Measurement Analyst's GA4 read.

**Never.** Anything on the banned list in `engagement-actions.json` (automated follows, mass likes, unsolicited DMs, comments at scale, follow-for-follow, engagement bait, bought followers). No paid creators or cold pitches: a collaboration is an open ask in a post.

| Situation | Decision |
|---|---|
| A handle does not exist yet | Plan "create it", the push three first |
| A profile breaks a rule (marks, no AI disclosure) | Fix it before any gain item |
| An action is pending or has no official API | Krish does it by hand, in his minutes |
| An action is approved and `gate()` clears it | Its adapter runs it, within its cap |
| A rule check is over 90 days old | Stop; re-check the rule and date it |
| A sound is outside the commercial library | Skip it |
| Followers rise, shared arrivals stay flat | Report it as vanity |
| A new tactic appears | Add it pending, with its rule source |

**Lens.** `crew/audience_builder/lens.md`.
