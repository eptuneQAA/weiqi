"""端到端冒烟：真实窗口对象 + 真实 AI 线程走一遍落子流程。

用法：QT_QPA_PLATFORM=offscreen python3 tools/e2e_ai_game.py
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

sys.path.insert(0, "/home/UOS/weiqi")

from weiqi.core.board import BLACK
from weiqi.ui.main_window import MainWindow

app = QApplication(sys.argv)
window = MainWindow(discovery_enabled=False)
window.show()

# 9 路入门：人执黑，AI 执白，走 6 手
window._start_ai_game(9, "入门", BLACK, komi=7.5, handicap=0)
print("开局阶段:", window.game.phase.value, "轮到:", window.game.turn)

deadline = time.monotonic() + 60
moves = 0
for point in ((2, 2), (6, 6), (2, 6), (6, 2)):
    # 等到轮到人
    while time.monotonic() < deadline and window.game.turn != window.human_color:
        app.processEvents()
        time.sleep(0.01)
    before = window.game.move_count
    window._on_point_clicked(*point)
    app.processEvents()
    if window.game.move_count == before:
        print("人落子失败:", point)
    # 等 AI 回一手
    while time.monotonic() < deadline and window.game.turn == window.ai_color:
        app.processEvents()
        time.sleep(0.01)
    moves = window.game.move_count
    print("第 {} 手后：黑 {} / 白 {}".format(
        moves, window.game.board.captures[1], window.game.board.captures[2]
    ))

window._update_ui()
app.processEvents()
window.grab().save("/tmp/ui-e2e.png")
print("总手数:", window.game.move_count, "状态:", window.statusBar().currentMessage())
window.close()
print("E2E OK")
