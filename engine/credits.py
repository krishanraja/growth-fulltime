"""Prepaid credits, protocol 1.16.0 (docs/CONTROL-CENTER-BRIEF.md, "Prepaid credits").

The directive's optional `credits` block names this engine's share of each
prepaid pool. This runner holds no generator keys and spends nothing: the
share is spent by the daily scheduled session in jobs/credits.md, which
reserves and settles each spend through the Control Center connector. This
module reads the block, says it in the report's activity, and guards any spend
a run makes so it can never pass remaining_for_you. A missing block is unknown,
never a share of zero; a held engine spends nothing."""
import re

POOL = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
OBJECTIVE = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
MAX_SPENT = 40
VERSION = '1.16.0'


class CreditRefused(ValueError):
    """A spend the share does not allow. Its code is one of unknown, held, no_pool, over_share, bad_spend."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def read(directive):
    """The pools in the directive's credits block, or None when it is absent or unreadable (unknown)."""
    body = (directive or {}).get('directive') if isinstance(directive, dict) else None
    block = body.get('credits') if isinstance(body, dict) else None
    if not isinstance(block, dict) or not isinstance(block.get('pools'), list):
        return None
    pools = []
    for p in block['pools']:
        if not isinstance(p, dict) or not isinstance(p.get('pool'), str) or not POOL.match(p['pool']):
            continue
        left = p.get('remaining_for_you')
        if type(left) not in (int, float) or left < 0:
            continue
        pools.append({'pool': p['pool'], 'tool': str(p.get('tool') or p['pool']), 'unit': str(p.get('unit') or 'credits'),
                      'share': p.get('share'), 'remaining_for_you': left, 'use_by': p.get('use_by'),
                      'days_left': p.get('days_left')})
    return pools


def _amount(value, unit):
    return f'${value:.2f}' if unit == 'usd' else f'{round(value):,} {unit}'


def lines(pools, held):
    """One activity line per pool, or one line saying the block is unknown."""
    if pools is None:
        return ['Prepaid credits: no credits block today, so the share is unknown and nothing is spent.']
    if not pools:
        return []
    tail = (' Held, so none of it is spent until Krish releases the engine.' if held else
            ' Spent by the daily credits session (jobs/credits.md), never by this runner.')
    return [f'Prepaid credits: {p["tool"]} {_amount(p["remaining_for_you"], p["unit"])} left for Full Time '
            f'({p["share"] or "placed"} share), use by {p["use_by"]}.' + (tail if i == len(pools) - 1 else '')
            for i, p in enumerate(pools)]


class Guard:
    """What a run may spend: never past remaining_for_you less what this run already spent."""

    def __init__(self, pools, held):
        self.pools = {p['pool']: p for p in pools or []}
        self.known = pools is not None
        self.held = held
        self.spent = []

    def left(self, pool):
        used = sum(s['amount'] for s in self.spent if s['pool'] == pool)
        return max(0, self.pools[pool]['remaining_for_you'] - used)

    def reserve(self, pool, amount, asset, objective_key=None):
        if self.held:
            raise CreditRefused('held')
        if not self.known:
            raise CreditRefused('unknown')
        if pool not in self.pools:
            raise CreditRefused('no_pool')
        if (type(amount) not in (int, float) or amount <= 0 or not isinstance(asset, str) or not asset.strip()
                or len(asset) > 200 or (objective_key is not None and not OBJECTIVE.match(objective_key))
                or len(self.spent) >= MAX_SPENT):
            raise CreditRefused('bad_spend')
        if amount > self.left(pool) + 1e-9:
            raise CreditRefused('over_share')
        entry = {'pool': pool, 'amount': amount, 'asset': asset.strip(), 'objective_key': objective_key}
        self.spent.append(entry)
        return entry

    def credits_spent(self):
        return [dict(s) for s in self.spent]
