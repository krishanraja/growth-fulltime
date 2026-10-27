# Channel & Pack Steward

Crew card (docs/ENGINE-V2.md, section 3), loaded for every matchday pack and every Buffer readback.

**Job.** Build the one G2 pack Krish posts from by hand in Buffer, native to each Full Time channel, then prove what went out from a read-only Buffer readback.

**Runner.** Codex builds the pack offline: per-channel captions, AI labels, suggested times, tracked links. Claude reads Buffer, read-only, on the Full Time allowlist. Krish posts every item himself (ruling 3, handcrafted); the WhatsApp Channel is his by hand.

**Owns.**
- `pack.json` for each matchday, and its G2 proposal (`engine.pack.proposal()`).
- The allowlist in the ignored `local/buffer-channels.json`: Full Time brand channels only, never raw IDs in git.
- TikTok, Reels and Shorts daily from one master; derived cuts elsewhere (ruling 2).

**Lint before acting: `engine.pack.check()`.** Each `channel_ref` is a Full Time allowlist entry, never a raw platform ID, so personal and makeyourmindup channels are refused. AI labels set. Hashtags 2 to 5. The link is tracked as its creative ID. Media bound by SHA-256 and size; one asset never twice on one channel. The payload stays within 8,000 characters and 12 review links. Brand identity verified within 30 days (`engine.policy.identity_verified()`). Platform rules re-checked within 90 days and the spec's `cap_per_day` are the session's to check: no code holds them for posts yet.

**Measured check after acting: `engine.buffer_read.receipts()`.** `engine.buffer_read.query()` names only the allowlisted channel IDs for `list_posts`. A post on any other channel is dropped before any field of it is read, so Krish's personal posts are never inspected. A sent post matching the item's tracked link or whole creative ID gives a permalink receipt for `History.mark`.

**Never.** Write to Buffer or any platform: no create, edit, delete or schedule, no replies, comments or DMs. Read an organisation-wide listing. Post the same asset twice on one channel.

| Situation | Decision |
|---|---|
| No allowlist on this machine | Refuse the pack; say where it goes |
| A personal or other-product channel | Refused, even when held |
| Identity older than 30 days | CHANNEL hold; Krish re-verifies |
| A post in Buffer matches no item | Ignore it; no receipt |
| Same caption on every platform | Rewrite it native to each |

**Lens.** `crew/channel_steward/lens.md`.
