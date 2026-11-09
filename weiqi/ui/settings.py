"""应用设置：QSettings 持久化 + 设置对话框。

只存界面偏好与默认值；对局本身走 SGF 文件。
"""

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QSpinBox, QVBoxLayout,
)

from ..core.board import BLACK, WHITE
from ..net.protocol import DEFAULT_TCP_PORT

ORGANIZATION = "weiqi"
APPLICATION = "weiqi"

DEFAULTS = {
    "board_size": 19,
    "difficulty": "普通",
    "human_color": BLACK,
    "komi": 7.5,
    "handicap": 0,
    "port": DEFAULT_TCP_PORT,
    "last_dir": "",
}


def settings():
    return QSettings(ORGANIZATION, APPLICATION)


def get(key):
    return settings().value(key, DEFAULTS.get(key))


def set_value(key, value):
    settings().setValue(key, value)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        form = QFormLayout()

        self.size_combo = QComboBox()
        for text, value in (("9 路", 9), ("13 路", 13), ("19 路", 19)):
            self.size_combo.addItem(text, value)
        index = self.size_combo.findData(int(get("board_size")))
        self.size_combo.setCurrentIndex(max(0, index))

        self.difficulty_combo = QComboBox()
        for text in ("入门", "普通", "较强"):
            self.difficulty_combo.addItem(text)
        difficulty = str(get("difficulty"))
        if self.difficulty_combo.findText(difficulty) >= 0:
            self.difficulty_combo.setCurrentText(difficulty)

        self.color_combo = QComboBox()
        self.color_combo.addItem("执黑", BLACK)
        self.color_combo.addItem("执白", WHITE)
        index = self.color_combo.findData(int(get("human_color")))
        self.color_combo.setCurrentIndex(max(0, index))

        self.komi_spin = QDoubleSpinBox()
        self.komi_spin.setRange(0.0, 30.0)
        self.komi_spin.setSingleStep(0.5)
        self.komi_spin.setDecimals(1)
        self.komi_spin.setValue(float(get("komi")))

        self.handicap_spin = QSpinBox()
        self.handicap_spin.setRange(0, 9)
        self.handicap_spin.setValue(int(get("handicap")))

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(int(get("port")))

        form.addRow("默认棋盘", self.size_combo)
        form.addRow("默认 AI 难度", self.difficulty_combo)
        form.addRow("默认执子", self.color_combo)
        form.addRow("贴目", self.komi_spin)
        form.addRow("默认让子数", self.handicap_spin)
        form.addRow("默认端口", self.port_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self):
        set_value("board_size", int(self.size_combo.currentData()))
        set_value("difficulty", self.difficulty_combo.currentText())
        set_value("human_color", int(self.color_combo.currentData()))
        set_value("komi", float(self.komi_spin.value()))
        set_value("handicap", int(self.handicap_spin.value()))
        set_value("port", int(self.port_spin.value()))
        super().accept()
