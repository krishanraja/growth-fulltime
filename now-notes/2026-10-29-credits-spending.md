# 2026-10-29: the credits step is built

Status: the runner reads the directive's `credits` into its activity (absent means unknown and nothing is spent), its guard refuses any spend past `remaining_for_you` or while held, and a report carries `credits_spent` at 1.16.0 only when a run spent, proved against the stand-in. The share itself is spent by one daily scheduled session (`docs/CREDITS-SESSION.md`) through Control Center's `reserve_credit_spend` and `settle_credit_spend`. The engine is held, so that session spends nothing until Krish releases it.

Next: when Krish releases the engine, enable its credits session and check the first settled spend lowers `remaining_for_you`.

North Star check (2026-10-29): holds.
