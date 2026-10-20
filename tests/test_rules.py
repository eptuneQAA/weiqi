import unittest

from weiqi.core.board import (
    BLACK, EMPTY, WHITE, Board,
)
from weiqi.core.game import GameState, Phase


class BoardTest(unittest.TestCase):
    def test_capture_single_stone(self):
        board = Board(9)
        board.set(1, 1, WHITE)
        board.set(0, 1, BLACK)
        board.set(2, 1, BLACK)
        board.set(1, 0, BLACK)
        ok, err = board.play(1, 2, BLACK)
        self.assertTrue(ok, err)
        self.assertEqual(board.get(1, 1), EMPTY)
        self.assertEqual(board.captures[BLACK], 1)

    def test_suicide_is_illegal(self):
        board = Board(9)
        for x, y in ((0, 1), (2, 1), (1, 0), (1, 2)):
            board.set(x, y, WHITE)
        before = board.position_key()
        ok, err = board.play(1, 1, BLACK)
        self.assertFalse(ok)
        self.assertIn("自杀", err)
        self.assertEqual(board.position_key(), before)

    def test_group_and_liberties(self):
        board = Board(9)
        board.set(1, 1, BLACK)
        board.set(2, 1, BLACK)
        stones, liberties = board.group_and_liberties(1, 1)
        self.assertEqual(stones, {(1, 1), (2, 1)})
        self.assertEqual(len(liberties), 6)

    def test_out_of_bounds(self):
        board = Board(9)
        ok, err = board.play(9, 0, BLACK)
        self.assertFalse(ok)
        self.assertIn("超出", err)

    def test_star_points(self):
        self.assertEqual(len(Board(9).star_points()), 5)
        self.assertEqual(len(Board(13).star_points()), 5)
        self.assertEqual(len(Board(19).star_points()), 9)


class GameTest(unittest.TestCase):
    def test_turn_alternates(self):
        game = GameState(9)
        ok, err = game.play(4, 4)
        self.assertTrue(ok, err)
        self.assertEqual(game.turn, WHITE)
        self.assertEqual(game.board.get(4, 4), BLACK)

    def test_superko_forbids_repetition(self):
        game = GameState(9)
        game.board.set(1, 0, BLACK)
        game.board.set(2, 0, WHITE)
        game.board.set(1, 2, BLACK)
        game.board.set(2, 2, WHITE)
        game.board.set(0, 1, BLACK)
        game.board.set(1, 1, EMPTY)
        game.board.set(2, 1, BLACK)
        game.board.set(3, 1, WHITE)
        game.turn = WHITE
        game.positions = {game.board.position_key()}
        ok, err = game.play(1, 1)
        self.assertTrue(ok, err)
        self.assertEqual(game.turn, BLACK)
        ok, err = game.play(2, 1)
        self.assertFalse(ok)
        self.assertIn("劫争", err)

    def test_two_passes_enter_scoring(self):
        game = GameState(9)
        game.pass_turn()
        self.assertEqual(game.phase, Phase.PLAYING)
        game.pass_turn()
        self.assertEqual(game.phase, Phase.SCORING)
        self.assertIsNotNone(game.score)

    def test_resign(self):
        game = GameState(9)
        game.resign(BLACK)
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, "white")

    def test_undo(self):
        game = GameState(9)
        game.play(0, 0)
        game.play(1, 0)
        self.assertTrue(game.undo(2))
        self.assertEqual(game.board.get(0, 0), EMPTY)
        self.assertEqual(game.board.get(1, 0), EMPTY)
        self.assertEqual(game.turn, BLACK)

    def test_snapshot_roundtrip(self):
        game = GameState(9)
        game.play(4, 4)
        game.play(3, 3)
        restored = GameState.from_snapshot(game.snapshot())
        self.assertEqual(restored.board.position_key(), game.board.position_key())
        self.assertEqual(restored.turn, game.turn)
        self.assertEqual(restored.phase, game.phase)


if __name__ == "__main__":
    unittest.main()
