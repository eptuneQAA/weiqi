"""UDP 房间广播与发现。"""

import json
import logging
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtNetwork import QAbstractSocket, QHostAddress, QUdpSocket

from .protocol import DISCOVERY_MAGIC, DISCOVERY_PORT, PROTOCOL_VERSION

logger = logging.getLogger(__name__)


class RoomBroadcaster(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QUdpSocket(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._broadcast)
        self.payload = None

    def start(self, room, tcp_port, board_size, host_color):
        self.payload = {
            "magic": DISCOVERY_MAGIC,
            "version": PROTOCOL_VERSION,
            "room": room,
            "tcp_port": int(tcp_port),
            "board_size": int(board_size),
            "host_color": int(host_color),
        }
        self._broadcast()
        self.timer.start(2000)

    def _broadcast(self):
        if not self.payload:
            return
        data = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        self.socket.writeDatagram(
            data, QHostAddress(QHostAddress.Broadcast), DISCOVERY_PORT
        )

    def stop(self):
        self.timer.stop()
        self.payload = None
        self.socket.close()


class RoomListener(QObject):
    rooms_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QUdpSocket(self)
        self.socket.readyRead.connect(self._read_pending)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._cleanup)
        self.rooms = {}

    def start(self):
        flags = (
            QAbstractSocket.ShareAddress | QAbstractSocket.ReuseAddressHint
        )
        ok = self.socket.bind(QHostAddress.AnyIPv4, DISCOVERY_PORT, flags)
        if ok:
            self.timer.start(2000)
        else:
            logger.warning("无法监听 UDP 发现端口 %s", DISCOVERY_PORT)
        return ok

    def stop(self):
        self.timer.stop()
        self.socket.close()
        self.rooms.clear()

    def current_rooms(self):
        return self._sorted_rooms()

    def _read_pending(self):
        now = time.monotonic()
        changed = False
        while self.socket.hasPendingDatagrams():
            size = self.socket.pendingDatagramSize()
            data, host, _port = self.socket.readDatagram(size)
            try:
                info = json.loads(bytes(data).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(info, dict):
                continue
            if info.get("magic") != DISCOVERY_MAGIC:
                continue
            if info.get("version") != PROTOCOL_VERSION:
                continue
            tcp_port = info.get("tcp_port")
            room_name = info.get("room")
            board_size = info.get("board_size")
            if not isinstance(tcp_port, int) or not isinstance(room_name, str):
                continue
            if board_size not in (9, 13, 19):
                continue
            ip = host.toString()
            self.rooms[(ip, tcp_port)] = {
                "room": room_name,
                "ip": ip,
                "port": tcp_port,
                "board_size": board_size,
                "host_color": info.get("host_color", 1),
                "seen": now,
            }
            changed = True
        if changed:
            self.rooms_changed.emit(self._sorted_rooms())

    def _cleanup(self):
        now = time.monotonic()
        expired = [
            key for key, value in self.rooms.items()
            if now - value["seen"] > 5.0
        ]
        for key in expired:
            del self.rooms[key]
        if expired:
            self.rooms_changed.emit(self._sorted_rooms())

    def _sorted_rooms(self):
        values = list(self.rooms.values())
        values.sort(key=lambda item: (item["room"], item["ip"], item["port"]))
        return values
