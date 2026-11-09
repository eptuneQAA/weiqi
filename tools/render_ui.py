"""用 offscreen 渲染窗口截图，便于在没有点击的情况下检查布局。"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

sys.path.insert(0, "/home/UOS/weiqi")

from weiqi.core.board import BLACK
from weiqi.ui.main_window import MainWindow

app = QApplication(sys.argv)
window = MainWindow(discovery_enabled=False)
window.resize(1040, 780)
window.show()
app.processEvents()

# 1) 空闲欢迎页
window.grab().save("/tmp/ui-idle.png")

# 2) 进行中的人机对局（手动落几子）
window._start_ai_game(19, "普通", BLACK, komi=7.5, handicap=0)
for x, y in ((3, 3), (15, 15), (3, 15), (15, 3), (9, 9), (2, 2)):
    if window.game.turn != window.human_color:
        window.game.turn = window.human_color
    ok, err = window.game.play(x, y)
    if not ok:
        print("落子失败", x, y, err)
window._update_ui()
app.processEvents()
window.grab().save("/tmp/ui-game.png")

# 3) 复盘页（走 SGF 复盘的分支）
window._stop_session()
from weiqi.core import sgf

game = window.game
sgf.save_file("/tmp/_ui_check.sgf", game)
window._open_sgf_path("/tmp/_ui_check.sgf")
app.processEvents()
window.grab().save("/tmp/ui-review.png")

window.close()
print("saved")
