import socket

from PyQt5.QtCore import Qt
from PyQt5.QtNetwork import QAbstractSocket, QNetworkInterface
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout,
)

from ..core.board import BLACK, WHITE
from ..net.protocol import DEFAULT_TCP_PORT, MAX_NAME_LENGTH


def local_ip_addresses():
    addresses = []
    for address in QNetworkInterface.allAddresses():
        if address.protocol() != QAbstractSocket.IPv4Protocol:
            continue
        if address.isLoopback():
            continue
        ip = address.toString()
        if ip not in addresses:
            addresses.append(ip)
    try:
        for info in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET
        ):
            ip = info[4][0]
            if ip not in addresses and not ip.startswith("127."):
                addresses.append(ip)
    except OSError:
        pass
    if not addresses:
        addresses.append("127.0.0.1")
    return addresses


def default_room_name():
    name = socket.gethostname().strip() or "主机"
    return "{}的房间".format(name[:20])


def default_player_name():
    name = socket.gethostname().strip() or "玩家"
    return name[:MAX_NAME_LENGTH]


class NewGameDialog(QDialog):
    def __init__(self, parent=None, defaults=None):
        super().__init__(parent)
        defaults = defaults or {}
        self.setWindowTitle("新对局（人机）")
        form = QFormLayout()
        self.size_combo = QComboBox()
        for text, value in (("9 路", 9), ("13 路", 13), ("19 路", 19)):
            self.size_combo.addItem(text, value)
        size_index = self.size_combo.findData(int(defaults.get("size", 19)))
        self.size_combo.setCurrentIndex(max(0, size_index))
        self.difficulty_combo = QComboBox()
        for text in ("入门", "普通", "较强"):
            self.difficulty_combo.addItem(text)
        difficulty = str(defaults.get("difficulty", "普通"))
        if self.difficulty_combo.findText(difficulty) >= 0:
            self.difficulty_combo.setCurrentText(difficulty)
        self.color_combo = QComboBox()
        self.color_combo.addItem("执黑", BLACK)
        self.color_combo.addItem("执白", WHITE)
        color_index = self.color_combo.findData(int(defaults.get("color", BLACK)))
        self.color_combo.setCurrentIndex(max(0, color_index))
        self.komi_spin = QDoubleSpinBox()
        self.komi_spin.setRange(0.0, 30.0)
        self.komi_spin.setSingleStep(0.5)
        self.komi_spin.setDecimals(1)
        self.komi_spin.setValue(float(defaults.get("komi", 7.5)))
        self.handicap_spin = QSpinBox()
        self.handicap_spin.setRange(0, 9)
        self.handicap_spin.setValue(int(defaults.get("handicap", 0)))
        form.addRow("棋盘大小", self.size_combo)
        form.addRow("AI 难度", self.difficulty_combo)
        form.addRow("我方执子", self.color_combo)
        form.addRow("贴目", self.komi_spin)
        form.addRow("让子数", self.handicap_spin)
        hint = QLabel("让子 2 子及以上时由白方先行，贴目通常设为 0.5。")
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def values(self):
        return {
            "size": int(self.size_combo.currentData()),
            "difficulty": self.difficulty_combo.currentText(),
            "color": int(self.color_combo.currentData()),
            "komi": float(self.komi_spin.value()),
            "handicap": int(self.handicap_spin.value()),
        }


class HostGameDialog(QDialog):
    def __init__(self, parent=None, defaults=None):
        super().__init__(parent)
        defaults = defaults or {}
        self.setWindowTitle("创建局域网房间")
        form = QFormLayout()
        self.room_edit = QLineEdit(default_room_name())
        self.room_edit.setMaxLength(30)
        self.size_combo = QComboBox()
        for text, value in (("9 路", 9), ("13 路", 13), ("19 路", 19)):
            self.size_combo.addItem(text, value)
        size_index = self.size_combo.findData(int(defaults.get("size", 19)))
        self.size_combo.setCurrentIndex(max(0, size_index))
        self.color_combo = QComboBox()
        self.color_combo.addItem("主机执黑", BLACK)
        self.color_combo.addItem("主机执白", WHITE)
        color_index = self.color_combo.findData(int(defaults.get("color", BLACK)))
        self.color_combo.setCurrentIndex(max(0, color_index))
        self.komi_spin = QDoubleSpinBox()
        self.komi_spin.setRange(0.0, 30.0)
        self.komi_spin.setSingleStep(0.5)
        self.komi_spin.setDecimals(1)
        self.komi_spin.setValue(float(defaults.get("komi", 7.5)))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(int(defaults.get("port", DEFAULT_TCP_PORT)))
        ip_label = QLabel("、".join(local_ip_addresses()))
        ip_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("房间名称", self.room_edit)
        form.addRow("棋盘大小", self.size_combo)
        form.addRow("主机执子", self.color_combo)
        form.addRow("贴目", self.komi_spin)
        form.addRow("TCP 端口", self.port_spin)
        form.addRow("本机 IP", ip_label)
        hint = QLabel("客机可手动输入上方 IP 与端口，或通过自动发现加入。")
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def values(self):
        room = self.room_edit.text().strip() or default_room_name()
        return (
            room,
            int(self.size_combo.currentData()),
            int(self.color_combo.currentData()),
            int(self.port_spin.value()),
            float(self.komi_spin.value()),
        )


class JoinGameDialog(QDialog):
    def __init__(self, listener=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加入局域网房间")
        self.listener = listener
        self.rooms = []
        self._signature = None
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(120)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self._refresh)
        list_row = QHBoxLayout()
        list_title = QLabel("自动发现的房间")
        list_row.addWidget(list_title)
        list_row.addStretch(1)
        list_row.addWidget(self.refresh_button)
        self.ip_edit = QLineEdit("127.0.0.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(DEFAULT_TCP_PORT)
        self.name_edit = QLineEdit(default_player_name())
        self.name_edit.setMaxLength(MAX_NAME_LENGTH)
        self.ip_edit.textEdited.connect(
            lambda _text: self.list_widget.setCurrentRow(-1)
        )
        self.port_spin.valueChanged.connect(
            lambda _value: self.list_widget.setCurrentRow(-1)
        )
        form = QFormLayout()
        form.addRow("主机 IP", self.ip_edit)
        form.addRow("端口", self.port_spin)
        form.addRow("我的昵称", self.name_edit)
        if listener is None:
            hint_text = "自动发现不可用，请手动输入主机 IP 和端口。"
            self.refresh_button.setEnabled(False)
        else:
            hint_text = "点击列表中的房间，或手动输入 IP 和端口。"
            self.update_rooms(listener.current_rooms())
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(list_row)
        layout.addWidget(self.list_widget)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self.resize(460, 420)

    def _refresh(self):
        if self.listener is not None:
            self.update_rooms(self.listener.current_rooms())

    def update_rooms(self, rooms):
        signature = [
            (
                room.get("ip"), room.get("port"), room.get("room"),
                room.get("board_size"),
            )
            for room in rooms
        ]
        if signature == self._signature:
            return
        self._signature = signature
        selected = None
        current = self.list_widget.currentItem()
        if current is not None:
            room = current.data(Qt.UserRole)
            selected = (room["ip"], int(room["port"]))
        self.rooms = list(rooms)
        self.list_widget.clear()
        restore_row = -1
        for index, room in enumerate(self.rooms):
            item = QListWidgetItem(
                "{}   {}:{}   {} 路".format(
                    room["room"], room["ip"], room["port"],
                    room["board_size"],
                )
            )
            item.setData(Qt.UserRole, room)
            self.list_widget.addItem(item)
            if (room["ip"], int(room["port"])) == selected:
                restore_row = index
        self.list_widget.setCurrentRow(restore_row)

    def accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入昵称。")
            return
        super().accept()

    def values(self):
        item = self.list_widget.currentItem()
        if item is not None:
            room = item.data(Qt.UserRole)
            return room["ip"], int(room["port"]), self.name_edit.text().strip()
        return (
            self.ip_edit.text().strip() or "127.0.0.1",
            int(self.port_spin.value()),
            self.name_edit.text().strip(),
        )


class ResultDialog(QDialog):
    def __init__(self, text, allow_replay=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("对局结果")
        self.replay = False
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if allow_replay:
            replay_button = QPushButton("再来一局")
            replay_button.clicked.connect(self._on_replay)
            buttons.addWidget(replay_button)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)

    def _on_replay(self):
        self.replay = True
        self.accept()
