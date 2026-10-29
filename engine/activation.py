"""Whether Krish has held this engine (Ruling, Krish, 2026-10-29).

Not ready means a held activation state: no wake, no asks on his list, no
growth council move, and the bearer stays valid. Two sources say held, and
either is enough:

1. Control Center's directive. A held engine's directive carries HELD_RULE as
   its next action with no proposal, and may name the state outright
   (`activation.state`, `constraints.activation`, `held: true`).
2. The tracked file activation.json. It defaults to held: a missing,
   unreadable or unknown state is held. Only Krish releases it, recorded in an
   interactive session with his words and the date.

While held, a report carries no proposals and exactly one NOT_READY hold that
names what would make the engine ready. Nothing here releases anything.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / 'activation.json'
STATES = ('held', 'released')
HELD_PREFIX = 'Krish has held this engine'


def local_state(path=None):
    """'held' or 'released' from activation.json; anything else is held."""
    try:
        value = json.loads(Path(path or FILE).read_text(encoding='utf-8')).get('state')
    except (OSError, ValueError, AttributeError):
        return 'held'
    return value if value in STATES else 'held'


def _says_held(value):
    if value == 'held' or value is True:
        return True
    return isinstance(value, dict) and value.get('state') == 'held'


def directive_held(payload):
    """True when the directive Control Center sent says this engine is held."""
    if not isinstance(payload, dict):
        return False
    body = payload.get('directive') if isinstance(payload.get('directive'), dict) else {}
    constraints = body.get('constraints') if isinstance(body.get('constraints'), dict) else {}
    action = body.get('next_action') if isinstance(body.get('next_action'), dict) else {}
    instruction = action.get('instruction')
    return (_says_held(payload.get('activation')) or _says_held(body.get('activation'))
            or _says_held(constraints.get('activation')) or body.get('held') is True
            or body.get('status') == 'held'
            or (action.get('proposal_id') is None and isinstance(instruction, str)
                and instruction.startswith(HELD_PREFIX)))


def held(directive, path=None):
    """(is_held, sources): the sources that say held, in a fixed order."""
    sources = []
    if directive_held(directive):
        sources.append('control_center')
    if local_state(path) == 'held':
        sources.append('activation.json')
    return bool(sources), sources
