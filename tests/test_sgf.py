"""SGF 读写测试。"""

import os
import tempfile
import unittest

from weiqi.core.board import BLACK, EMPTY, WHITE
from weiqi.core.game import GameState, Phase
from weiqi.core.sgf import SGFError, dumps, loads, load_file, save_file


class CoordinateTest(unittest.TestCase):
    def test_coordinate_mapping(self):
        # SGF 不跳过 i：p=16 列，d=4 行 → (15, 3)
        game = loads("(;GM[1]FF[4]SZ[19];B[pd];W[dd])")
        self.assertEqual(game.history[0], (BLACK, 15, 3))
        self.assertEqual(game.history[1], (WHITE, 3, 3))

    def test_out_of_range_rejected(self):
        with self.assertRaises(SGFError):
            loads("(;SZ[9];B[zz])")


class RoundTripTest(unittest.TestCase):
    def _game(self):
        game = GameState(9, 6.5)
        moves = [(2, 2), (6, 6), (2, 6), (6, 2), (4, 4)]
        for x, y in moves:
            ok, err = game.play(x, y)
            self.assertTrue(ok, err)
        ok, _ = game.play(1, 1)
        self.assertTrue(ok)
        return game

    def test_round_trip(self):
        game = self._game()
        text = dumps(game, black_name="黑方", white_name="白方")
        restored = loads(text)
        self.assertEqual(restored.size, game.size)
        self.assertEqual(restored.komi, game.komi)
        self.assertEqual(restored.history, game.history)
        self.assertEqual(
            restored.board.grid, game.board.grid
        )

    def test_passes_and_result_preserved(self):
        game = self._game()
        game.pass_turn()
        game.pass_turn()
        self.assertEqual(game.phase, Phase.SCORING)
        game.confirm_score()
        text = dumps(game)
        self.assertIn("RE[", text)
        restored = loads(text)
        self.assertEqual(restored.history, game.history)

    def test_comment_and_name_escaping(self):
        game = self._game()
        text = dumps(game, black_name="黑]方", comment="括号 ] 与反斜杠 \\ ")
        restored = loads(text)
        self.assertEqual(restored.history, game.history)

    def test_file_round_trip(self):
        game = self._game()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "对局.sgf")
            save_file(path, game)
            restored = load_file(path)
        self.assertEqual(restored.history, game.history)


class HandicapTest(unittest.TestCase):
    def test_ab_setup_sets_turn_to_white(self):
        game = loads("(;GM[1]FF[4]SZ[9]AB[cc][gg][cg][gc]KM[0.5])")
        self.assertEqual(game.turn, WHITE)
        self.assertEqual(game.board.get(2, 2), BLACK)
        self.assertEqual(game.board.get(6, 6), BLACK)
        self.assertEqual(game.move_count, 0)
        # 摆子后仍然可以正常落子
        ok, err = game.play(4, 4)
        self.assertTrue(ok, err)


class ParseEdgeCaseTest(unittest.TestCase):
    def test_main_line_variation(self):
        text = "(;SZ[9];B[cc](;W[gg];B[cg])(;W[gc]))"
        game = loads(text)
        self.assertEqual([move[1:] for move in game.history], [(2, 2), (6, 6), (2, 6)])

    def test_escaped_bracket_in_comment(self):
        game = loads("(;SZ[9]C[a\\]b];B[cc])")
        self.assertEqual(game.move_count, 1)

    def test_missing_root_paren(self):
        with self.assertRaises(SGFError):
            loads("SZ[9]")

    def test_unsupported_board_size(self):
        with self.assertRaises(SGFError):
            loads("(;SZ[17])")

    def test_illegal_move_raises(self):
        with self.assertRaises(SGFError):
            loads("(;SZ[9];B[cc];W[cc])")

    def test_unsupported_size_9_13_19_only(self):
        for size in (9, 13, 19):
            game = loads("(;SZ[{}])".format(size))
            self.assertEqual(game.size, size)


if __name__ == "__main__":
    unittest.main()
