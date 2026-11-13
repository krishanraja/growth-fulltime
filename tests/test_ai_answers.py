"""Full Time's AI answers from AEO-Engine, the one specialist (protocol 1.22.0; Ruling, Krish, 2026-11-12)."""
import unittest

from engine import ai_answers


def directive(standing='absent', features=True):
    body = {'features': {'engine_state': True, 'krish_instruction': True, **({'ai_answers': True} if features else {})}}
    if standing != 'absent':
        body['ai_answers'] = {'standing': standing, 'rule': 'r'}
    return {'ok': True, 'directive': body}


class AiAnswersTest(unittest.TestCase):
    def test_full_times_standing_is_one_line_in_the_tiles_words(self):
        s = {'tracked': True, 'latest': {'as_of': '2026-11-08', 'asked': 20, 'cited_first': 0, 'share': 0}, 'request': None}
        self.assertEqual(ai_answers.lines(directive(s)), ['AI answers: cited first on 0 of 20 questions, 8 Nov.'])
        self.assertEqual(ai_answers.lines(directive(None)), ['AI answers: not tracked yet.'])
        self.assertEqual(ai_answers.line({'tracked': True, 'latest': None, 'request': {'state': 'open', 'questions': 1}}), 'AI answers: AEO tracks 1 question from its next research run.')

    def test_a_directive_that_serves_no_ai_answers_adds_nothing(self):
        self.assertEqual(ai_answers.lines(directive(features=False)), [])
        self.assertEqual(ai_answers.lines(None), [])


if __name__ == '__main__':
    unittest.main()
