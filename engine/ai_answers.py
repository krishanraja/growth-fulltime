"""Full Time's AI answers, from AEO-Engine, the one specialist (protocol 1.22.0).

Ruling (Krish, 2026-11-12): "AEO-Engine becomes the one specialist that every
venture's growth engine calls for its AI-answer work. Each venture's tile
shows its own AI-answer standing ..."

This engine never asks an AI assistant itself. AEO-Engine already researches
Full Time's buyer questions every fortnight (its `full-time` subject), so the
runner only says Full Time's standing in one line, read from the directive
(`ai_answers`), and a session that wants other questions tracked asks AEO
through Control Center (`POST answers`, protocol 1.22.0). While Krish holds
this engine, its standing still reads and nothing is asked.
"""


def standing(directive):
    body = (directive or {}).get('directive') or {}
    block = body.get('ai_answers')
    return block.get('standing') if isinstance(block, dict) else None


def served(directive):
    body = (directive or {}).get('directive') or {}
    return bool((body.get('features') or {}).get('ai_answers')) or isinstance(body.get('ai_answers'), dict)


def _day(ymd):
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    try:
        y, m, d = (int(x) for x in str(ymd)[:10].split('-'))
        return f'{d} {months[m - 1]}'
    except (ValueError, IndexError):
        return str(ymd)


def line(s):
    """Full Time's AI answers in one line, the words Control Center's tile uses."""
    if not s:
        return 'AI answers: not tracked yet.'
    latest = s.get('latest')
    if latest:
        n = latest.get('asked')
        return f'AI answers: cited first on {latest.get("cited_first")} of {n} question{"" if n == 1 else "s"}, {_day(latest.get("as_of"))}.'
    request = s.get('request') or {}
    if request.get('state') == 'open':
        n = request.get('questions')
        return f'AI answers: AEO tracks {n} question{"" if n == 1 else "s"} from its next research run.'
    return 'AI answers: tracked, not asked yet.' if s.get('tracked') else 'AI answers: not tracked yet.'


def lines(directive):
    """The runner's AI-answer line, or none when the directive serves no AI answers."""
    return [line(standing(directive))] if served(directive) else []
