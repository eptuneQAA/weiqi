"""测试包初始化：先建 QApplication，供所有用例共享。

必须在任何用例导入之前创建，否则 test_network 会先建一个 QCoreApplication，
UI 测试再想建窗口就会报 "Cannot create a QWidget without QApplication"。
offscreen 平台让测试无需真实显示器，也不会弹出窗口。
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

APPLICATION = QApplication.instance() or QApplication(sys.argv)
