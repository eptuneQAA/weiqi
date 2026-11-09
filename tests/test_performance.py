"""批次 D 的不变量测试：优化后语义不能变。"""

import unittest

from weiqi.core.board import BLACK, EMPTY, WHITE, Board
from weiqi.core.game import GameState, Phase


class BoardRollbackTest(unittest.TestCase):
    def test_suicide_leaves_board_untouched(self):
        board = Board(9)
        # 白把黑 (1,1) 围死：黑落进去是自杀
        for x, y in ((0, 1), (2, 1), (1, 0), (1, 2)):
            board.set(x, y, WHITE)
        before_grid = [row[:] for row in board.grid]
        before_captures = dict(board.captures)
        ok, err = board.play(1, 1, BLACK)
        self.assertFalse(ok)
        self.assertEqual(err, "禁止自杀")
        self.assertEqual(board.grid, before_grid)
        self.assertEqual(board.captures, before_captures)

    def test_capture_still_works(self):
        board = Board(9)
        # 黑子 (1,1) 四气被白占三，落第四子提掉
        board.set(1, 1, BLACK)
        for x, y in ((0, 1), (2, 1), (1, 0)):
            board.set(x, y, WHITE)
        ok, err = board.play(1, 2, WHITE)
        self.assertTrue(ok, err)
        self.assertEqual(board.get(1, 1), EMPTY)
        self.assertEqual(board.captures[WHITE], 1)

    def test_position_key_is_hashable_bytes(self):
        board = Board(9)
        board.set(2, 2, BLACK)
        key = board.position_key()
        self.assertIsInstance(key, bytes)
        self.assertEqual(len(key), 81)
        self.assertEqual(hash(key), hash(board.position_key()))


class GamePlaySemanticsTest(unittest.TestCase):
    def test_play_rejects_occupied_and_out_of_bounds(self):
        game = GameState(9)
        ok, _ = game.play(4, 4)
        self.assertTrue(ok)
        ok, err = game.play(4, 4)
        self.assertFalse(ok)
        self.assertEqual(err, "该位置已有棋子")
        ok, err = game.play(-1, 0)
        self.assertFalse(ok)
        self.assertEqual(err, "落子超出棋盘")
        # 失败不应留下副作用
        self.assertEqual(game.move_count, 1)

    def test_superko_still_detected(self):
        # 经典劫：白(2,1)只有一口气(2,2)；黑填气提子后，黑(2,2)也只剩一口气(2,1)
        game = GameState(9)
        board = game.board
        board.set(2, 1, WHITE)
        for x, y in ((1, 1), (3, 1), (2, 0)):
            board.set(x, y, BLACK)
        for x, y in ((1, 2), (3, 2), (2, 3)):
            board.set(x, y, WHITE)
        game.positions = {board.position_key()}
        ok, err = game.play(2, 2)          # 黑提白 (2,1)
        self.assertTrue(ok, err)
        self.assertEqual(game.board.get(2, 1), EMPTY)
        snapshot = [row[:] for row in game.board.grid]
        ok, err = game.play(2, 1)          # 白立刻提回 → 与原局面重复
        self.assertFalse(ok)
        self.assertEqual(err, "劫争：不能重复之前的局面")
        # 被拒绝的落子不能留下任何痕迹
        self.assertEqual(game.board.grid, snapshot)
        self.assertEqual(game.move_count, 1)

    def test_play_after_finish_rejected(self):
        game = GameState(9)
        game.resign(BLACK)
        self.assertEqual(game.phase, Phase.FINISHED)
        ok, err = game.play(4, 4)
        self.assertFalse(ok)
        self.assertEqual(err, "当前不能落子")


if __name__ == "__main__":
    unittest.main()
