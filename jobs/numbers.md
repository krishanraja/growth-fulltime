# Job: numbers (every day)

Kind `numbers`. "Measurement" in `PLAYBOOK.md`. No drafts: one row per place
in `numbers`. Time for Krish: one minute to read the headline.

1. `python3 growth.py sync`. Use the `fulltime_sha` it prints.
2. Read **yesterday**, London time, from available Control Center aggregate
   sources first, through an approved read-only interface. Keep the metric's
   source, window, metric date and capture time in its note. A weekly active
   total is not a daily visitor count, and an older sample is not yesterday.
   Then use a Full Time branded signed-in dashboard for missing measures
   (`BROWSER.md`; reports and insights only, never a person's record). Write
   down only what the source shows:

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

   With no signed-in browser, retain verified backend aggregates that match
   the requested window and fill the `rail` row from the sync. Mark each
   unread measure null, naming its missing source or stale sample. Public
   Full Time brand pages can supply their own visible counts. Never read
   Krish's personal profiles or assume that another Gmail identity covers
   the product inbox.
3. Query distinct listeners over the whole window so far. Earlier numbers
   packs (`python3 growth.py read --days 31 --kind numbers`) provide history,
   not a deduplicated user count. Never add daily unique or rolling active
   counts. If the required completion/contact join is unavailable, say users
   cannot be measured yet. Compare verified users (PLAYBOOK, "The goal")
   against 1,000 by Sunday 8 November,
   and the December bar's rows that can be read daily (30 testers who
   finished a show; days in a row with a show by 07:00).
4. Headline: the one change that matters, in plain words, for example "Rail
   1 of 6 again, gate HOLD; 4 listens finished yesterday, 0 sign-ups; 0 of
   1,000". Check, then post. If the tool saves only a local checkpoint,
   report delivery as held; do not claim it landed in Control Center.
