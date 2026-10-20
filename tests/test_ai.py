import time
import unittest

from weiqi.ai.engine import AIEngine
from weiqi.core.game import GameState


class AITest(unittest.TestCase):
    def test_returns_legal_move_on_9(self):
        game = GameState(9)
        move = AIEngine("入门", seed=1).choose_move(game)
        self.assertIsNotNone(move)
        ok, err = game.is_legal(move[0], move[1])
        self.assertTrue(ok, err)

    def test_cancel_is_fast(self):
        game = GameState(19)
        start = time.monotonic()
        move = AIEngine("较强", seed=1).choose_move(
            game, cancel_check=lambda: True
        )
        self.assertIsNone(move)
        self.assertLess(time.monotonic() - start, 1.0)

    def test_finished_game_returns_none(self):
        game = GameState(9)
        game.pass_turn()
        game.pass_turn()
        self.assertIsNone(AIEngine("入门").choose_move(game))

    def test_respects_time_budget(self):
        game = GameState(9)
        start = time.monotonic()
        AIEngine("普通", seed=2).choose_move(game)
        self.assertLess(time.monotonic() - start, 3.0)


if __name__ == "__main__":
    unittest.main()
