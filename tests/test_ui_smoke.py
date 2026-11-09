"""UI 冒烟测试：无显示器环境（offscreen）下构造窗口并走关键流程。

不做像素校验，只保证控件能建起来、SGF 存取/复盘/让子不抛异常。

注意：必须在 QApplication 下运行。`python3 -m unittest discover -s tests -t .`
会让 tests 包被正确导入、由 tests/__init__.py 提前创建 QApplication；
若用不带 -t . 的方式单独跑 discover，test_network 会先创建 QCoreApplication，
此模块会被跳过而不是崩溃。
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from weiqi.core import sgf
from weiqi.core.game import GameState
from weiqi.ui.main_window import MODE_REVIEW, MainWindow

APP = None


def setUpModule():
    global APP
    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        APP = instance
        return
    if instance is not None:
        raise unittest.SkipTest(
            "已存在非 QApplication 的 Qt 实例；请用 "
            "`python3 -m unittest discover -s tests -t .` 运行"
        )
    APP = QApplication(sys.argv)


class MainWindowSmokeTest(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(discovery_enabled=False)
        self.addCleanup(self.window.close)
        self.addCleanup(self.window.deleteLater)

    def test_window_builds_with_expected_controls(self):
        self.assertEqual(self.window.windowTitle(), "围棋")
        for name in (
            "board_widget", "chat", "mode_label", "capture_label",
            "move_label", "undo_action", "pass_action", "resign_action",
            "prev_action", "next_action",
        ):
            self.assertTrue(hasattr(self.window, name), name)
        self.assertFalse(self.window.board_widget.interactive)
        self.assertFalse(self.window.undo_action.isEnabled())
        self.assertFalse(self.window.resign_action.isEnabled())

    def test_ai_game_with_handicap_starts_as_white(self):
        self.window._start_ai_game(9, "入门", 1, komi=0.5, handicap=4)
        self.assertEqual(self.window.game.turn, 2)   # 让子棋白方先行
        self.assertEqual(self.window.game.handicap, 4)
        self.assertEqual(self.window.game.komi, 0.5)
        stones = sum(
            1 for row in self.window.game.board.grid for value in row if value == 1
        )
        self.assertEqual(stones, 4)

    def test_review_flow_loads_sgf(self):
        game = GameState(9)
        for x, y in ((2, 2), (6, 6), (2, 6), (6, 2)):
            ok, err = game.play(x, y)
            self.assertTrue(ok, err)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.sgf")
            sgf.save_file(path, game)
            loaded = sgf.load_file(path)
        self.window._stop_session()
        self.window.mode = MODE_REVIEW
        self.window.review_game = loaded
        self.window.review_moves = list(loaded.history)
        self.window.review_index = len(loaded.history)
        self.window._apply_review()
        self.assertEqual(self.window.game.move_count, 4)
        self.window._review_goto(0)
        self.assertEqual(self.window.game.move_count, 0)
        self.window._review_step(1)
        self.assertEqual(self.window.game.move_count, 1)
        self.assertFalse(self.window.board_widget.interactive)

    def test_save_skips_empty_game_without_crashing(self):
        from PyQt5.QtWidgets import QMessageBox

        calls = []
        original = QMessageBox.information
        QMessageBox.information = staticmethod(
            lambda *args, **kwargs: calls.append(args)
        )
        try:
            self.window._save_sgf()
        finally:
            QMessageBox.information = original
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
