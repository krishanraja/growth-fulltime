# Job: numbers (every day)

Kind `numbers`. "Measurement" in `PLAYBOOK.md`. No drafts: one row per place
in `numbers`. Time for Krish: one minute to read the headline.

1. `python3 growth.py sync`. Use the `fulltime_sha` it prints.
2. Using the signed-in browser (`BROWSER.md`; reports and insights only,
   never a person's record), read **yesterday**, London time. Write down only
   what each page shows:

   | `platform` | Fields to fill, when shown |
   |---|---|
   | `rail` | `matches_live`, `newest_fill`, `best_fill` (from the sync, no browser needed) |
   | `posthog` | `visitors`, `play_started`, `listen_completed`, `pundit_switch_committed`, `signups`, `push_opt_in`, `playback_error` |
   | `posthog_beta` | the same fields, filtered to `utm_source = beta` (the December bar's testers) |
   | `ga4` | `users`, `sessions`, and the top source in the note |
   | `inbox` | `feedback_emails`, `wrong_fact_reports`, `very_disappointed`, `somewhat`, `not_bothered` (counts only, from krish@fulltime.fm) |
   | `tiktok` | `followers`, `views`, `profile_views` |
   | `youtube` | `subscribers`, `views`, `watch_hours` |
   | `instagram` | `followers`, `reach`, `shares`, `profile_visits`, `link_taps` |
   | `reddit` | `posts_live`, `comments`, `removed` (Krish's account, public view) |

   Each row's `note` says where you read it, plus the top source or the top
   creative id (PostHog's breakdown by `utm_content`). Leave a field out, or
   set it to `null`, when the page doesn't show it. Never estimate.

   With no signed-in browser, fill the `rail` row from the sync, read the
   public pages of Full Time's own accounts if any exist, and write the other
   rows with nulls and the note "dashboard not available".
3. Add up the window so far from the earlier numbers packs
   (`python3 growth.py read --days 31 --kind numbers`). Compare with the
   goal: users (PLAYBOOK, "The goal") against 1,000 by Sunday 8 November,
   and the December bar's rows that can be read daily (30 testers who
   finished a show; days in a row with a show by 07:00).
4. Headline: the one change that matters, in plain words, for example "Rail
   1 of 6 again, gate HOLD; 4 listens finished yesterday, 0 sign-ups; 0 of
   1,000". Check, then post.
