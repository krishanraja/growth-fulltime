# Brief for full-time: share links that can be counted (27 October 2026)

For a full-time session, once Krish approves this brief. Growth does not change the product; this is the handoff. Plan: [ENGINE-V2](../docs/ENGINE-V2.md), phase 1.

## Why

The growth North Star is "New listeners a week who arrived through a fan's shared link or clip", with the source "Full Time share links joined to new listens" ([NORTH_STAR](../docs/NORTH_STAR.md)). That source does not exist yet. Today a fan who forwards `?drop=&pundit=` sends an untagged link, a fan who re-shares a brand clip passes on the brand post's `utm_source`, and nothing joins a first visit to a first finished show. Until this ships the number stays unmeasured (U4), and the weekly ladder (16 by 2 November, 49 by 16 November) cannot be read at all.

## What to build

1. **A share action on every edition.** Use the phone's own share sheet from the player and from Today. Each share mints a token `s`, stored server-side: the token (random, unguessable), a hashed anonymous sharer ID, `drop_id`, `pundit`, the asset type (show, clip or card), the target app if the share sheet reports it, and the time created. The shared URL keeps today's deep link: `https://fulltime.fm/?drop=<drop>&pundit=<pundit>&s=<token>`.
2. **The recipient lands on that AI Pundit's show** and may preview it. The shared choice never overwrites the recipient's own saved AI Pundit (brand system rule).
3. **First touch, stored once.** On a new anonymous identity's first visit, keep `s` and the `utm_*` tags with the landing time. Never overwrite them.
4. **The join, inside the product's own data.**
   - share-arrived new listener: an identity whose first finished show (actual playback completion, not a switch or a load) happens within 7 days of a first touch carrying a valid `s`;
   - brand-post new listener: the same with a `utm_content` creative ID and no `s`;
   - untokenised new listener: a new finished listener with neither.
5. **A weekly aggregate export**, read-only and authenticated, in the MEASUREMENT.md version 1 shape: `share_arrived_new_listeners`, `brand_post_new_listeners` (with a breakdown by `utm_content`), `untokenised_new_listeners` and `shares_created`, over whole London weeks, each with a versioned `query_ref`. Counts only: no person IDs, devices, addresses or event payloads leave the product.
6. **Per-edition share previews.** Open Graph title and image per edition, so a shared link shows the AI Pundit and the match, and the missing glyphs on the published share image are fixed.
7. **Close D7 before the first public post.** PostHog and Google Analytics consent, with counsel's check as `docs/11-legal.md` requires. Ruling (Krish, 2026-10-27): organic brand posts may recruit pilot testers before release, per take, once D7 is closed.

## Accept when

- One controlled journey works end to end: share from device A, open on device B, finish the show, and the export reports one share-arrived new listener for that week.
- A brand link with `utm_content` and no token counts as a brand-post arrival, never as a share.
- The export contains no person-level field, and its counts match a direct query for the same window.

## Not asked

No new paid link service or SaaS: native links are enough, and paid link tooling would be an owner decision. No change to the shows, the AI Pundits or the release bar.
