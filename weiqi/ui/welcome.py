"""空状态欢迎页：把主操作直接摆出来，而不是只写在状态栏。"""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from . import theme


class WelcomeWidget(QWidget):
    new_game = pyqtSignal()
    host_game = pyqtSignal()
    join_game = pyqtSignal()
    open_sgf = pyqtSignal()
    open_path = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        card = QFrame()
        card.setObjectName("welcomeCard")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 24)
        card_layout.setSpacing(10)

        title = QLabel("围棋")
        title.setObjectName("welcomeTitle")
        subtitle = QLabel("人机对战 · 局域网双人 · 棋谱复盘")
        subtitle.setObjectName("welcomeSubtitle")
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(10)
        buttons = (
            ("开始人机对战", "选择棋盘、难度、执子与让子", self.new_game, True),
            ("创建局域网房间", "同网段对手可自动发现", self.host_game, False),
            ("加入局域网房间", "从房间列表或手动输入 IP", self.join_game, False),
            ("打开棋谱复盘", "载入 SGF 逐步查看（Ctrl+O）", self.open_sgf, False),
        )
        for index, (text, hint, signal, primary) in enumerate(buttons):
            button = QPushButton(text)
            button.setObjectName("primaryButton" if primary else "welcomeButton")
            button.setMinimumHeight(44)
            button.clicked.connect(signal)
            grid.addWidget(button, index // 2, index % 2)
            label = QLabel(hint)
            label.setObjectName("welcomeHint")
            label.setWordWrap(True)
            grid.addWidget(label, (index // 2) + 2, index % 2)
            grid.setRowStretch((index // 2) * 2 + 2, 0)
        card_layout.addLayout(grid)

        footer = QLabel("提示：Ctrl+N 开新局，Ctrl+S 保存棋谱，← → 复盘翻手，F1 查看帮助")
        footer.setObjectName("welcomeHint")
        footer.setWordWrap(True)
        card_layout.addSpacing(6)
        card_layout.addWidget(footer)

        self.recent_title = QLabel("最近的棋谱")
        self.recent_title.setObjectName("welcomeSection")
        card_layout.addSpacing(14)
        card_layout.addWidget(self.recent_title)
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(2)
        card_layout.addLayout(self.recent_layout)
        self.recent_title.setVisible(False)

        outer.addWidget(card, 0, Qt.AlignCenter)
        outer.addStretch(1)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QFrame#welcomeCard {
                background: %(panel)s;
                border: 1px solid %(border)s;
                border-radius: 12px;
            }
            QLabel#welcomeTitle { font-size: 26px; font-weight: bold; color: %(title)s; }
            QLabel#welcomeSubtitle { font-size: 13px; color: %(muted)s; }
            QLabel#welcomeHint { font-size: 11px; color: %(muted)s; }
            QPushButton#welcomeButton {
                padding: 10px 14px; border-radius: 6px;
                border: 1px solid %(border)s; background: %(button)s;
            }
            QPushButton#welcomeButton:hover { background: %(button_hover)s; }
            QLabel#welcomeSection { font-size: 12px; font-weight: bold; color: %(muted)s; }
            QPushButton#primaryButton {
                padding: 10px 14px; border-radius: 6px; border: none;
                background: %(primary)s; color: white; font-weight: bold;
            }
            QPushButton#primaryButton:hover { background: %(primary_hover)s; }
            """ % {
                "panel": theme.PANEL.name(),
                "border": theme.BORDER.name(),
                "title": theme.GRID.name(),
                "muted": theme.COORD.name(),
                "button": theme.PANEL.name(),
                "button_hover": theme.BOARD_LIGHT.name(),
                "primary": theme.PRIMARY.name(),
                "primary_hover": theme.PRIMARY_HOVER.name(),
            }
        )

    def set_recent(self, paths):
        """显示最近用过的棋谱（最多 5 个），点一下直接打开。"""
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        paths = list(paths)[:5]
        self.recent_title.setVisible(bool(paths))
        for path in paths:
            button = QPushButton(os.path.basename(path))
            button.setObjectName("recentButton")
            button.setFlat(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(path)
            button.clicked.connect(
                lambda _checked=False, target=path: self.open_path.emit(target)
            )
            self.recent_layout.addWidget(button)
