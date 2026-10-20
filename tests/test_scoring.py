import unittest

from weiqi.core.board import BLACK, WHITE, Board
from weiqi.core.scoring import (
    auto_dead_groups, compute_score, score_text, toggle_group_dead,
)


class ScoringTest(unittest.TestCase):
    def _walled_board(self):
        board = Board(9)
        for y in range(9):
            board.set(1, y, BLACK)
            board.set(7, y, WHITE)
        return board

    def test_area_score_with_walls(self):
        score = compute_score(self._walled_board(), set(), 7.5)
        self.assertEqual(score["black_stones"], 9)
        self.assertEqual(score["white_stones"], 9)
        self.assertEqual(score["black_territory"], 9)
        self.assertEqual(score["white_territory"], 9)
        self.assertEqual(score["black_area"], 18)
        self.assertEqual(score["white_area"], 18)
        self.assertEqual(score["white_total"], 25.5)
        self.assertEqual(score["winner"], "white")
        self.assertAlmostEqual(score["margin"], 7.5)

    def test_dead_stone_detection(self):
        board = self._walled_board()
        board.set(0, 0, WHITE)
        dead = auto_dead_groups(board)
        self.assertEqual(dead, {(0, 0)})
        alive = compute_score(board, set(), 7.5)
        killed = compute_score(board, dead, 7.5)
        self.assertEqual(alive["black_area"], 9)
        self.assertEqual(alive["white_area"], 19)
        self.assertEqual(killed["black_area"], 18)
        self.assertEqual(killed["white_area"], 18)

    def test_toggle_group_dead(self):
        board = self._walled_board()
        board.set(0, 0, WHITE)
        dead = toggle_group_dead(board, set(), 0, 0)
        self.assertEqual(dead, {(0, 0)})
        dead = toggle_group_dead(board, dead, 0, 0)
        self.assertEqual(dead, set())

    def test_score_text(self):
        score = compute_score(self._walled_board(), set(), 7.5)
        self.assertEqual(score_text(score), "白胜 7.5 点")

    def test_empty_board_komi(self):
        score = compute_score(Board(9), set(), 7.5)
        self.assertEqual(score["black_area"], 0)
        self.assertEqual(score["white_area"], 0)
        self.assertEqual(score["winner"], "white")
        self.assertAlmostEqual(score["margin"], 7.5)


if __name__ == "__main__":
    unittest.main()
