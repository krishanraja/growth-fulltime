# North Star

Status: Current
Owner: Krish Raja
Last verified: 2026-10-18

> By 31 January 2027, most new Full Time listeners arrive because a fan shared an AI Pundit's take, not because anyone was invited. This engine knows which takes travel and makes more of them.

Set by Krish on 18 October 2026. It is not reached yet. It is what every session in this repository works toward.

This repository serves [Full Time's North Star](https://github.com/krishanraja/full-time/blob/main/docs/NORTH_STAR.md). The lines above are this repository's part of it.

## The number

**New listeners a week who arrived through a fan's shared link or clip**: 1,250 by 25 January 2027, on a front-loaded weekly ladder. Checkpoints: 16 Nov 2026: 49; 14 Dec 2026: 225; 11 Jan 2027: 738; 25 Jan 2027: 1,250.

```yaml north-star-metric
metric: "New listeners a week who arrived through a fan's shared link or clip"
unit: count
direction: up
target: 1250
deadline: 2027-01-25
ladder_shape: front-loaded
source: "Full Time share links joined to new listens"
status: active
ladder:
  - [2026-10-26, 5]
  - [2026-11-02, 16]
  - [2026-11-09, 30]
  - [2026-11-16, 49]
  - [2026-11-23, 76]
  - [2026-11-30, 112]
  - [2026-12-07, 161]
  - [2026-12-14, 225]
  - [2026-12-21, 310]
  - [2026-12-28, 419]
  - [2027-01-04, 559]
  - [2027-01-11, 738]
  - [2027-01-18, 965]
  - [2027-01-25, 1250]
```

Urgency (U1 to U5) is worked out every week from where the number stands against that week's target, by [the harness contract](https://github.com/krishanraja/ai-harness/blob/main/contract/north-star-metric.md). Set by Krish on 23 October 2026.

## How to use it

- Read it before any work, every session.
- Before you start, say which part of it the task moves. If the task moves nothing toward it, say so first and let Krish decide.
- Prefer the work that moves it furthest, and close each session by noting what moved.
- Only Krish changes this file. Record his ruling in the commit body as `Ruling (Krish, YYYY-MM-DD): ...`.
- When it is reached, say so and ask Krish for the next one.
