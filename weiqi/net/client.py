"""客机端 TCP 连接、心跳与消息分发。"""

import logging
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtNetwork import QAbstractSocket, QTcpSocket

from .protocol import (
    PROTOCOL_VERSION, ProtocolError, clean_name, decode_message,
    encode_message,
)

logger = logging.getLogger(__name__)


def _friendly_socket_error(message):
    lower = message.lower()
    if "refused" in lower:
        return "连接被拒绝，请确认主机已创建房间且 IP、端口正确"
    if "timed out" in lower or "timeout" in lower:
        return "连接超时，请检查主机 IP 和网络"
    if "unreachable" in lower:
        return "无法访问主机，请检查网络连接"
    if "not found" in lower or "unknown" in lower:
        return "找不到主机，请检查 IP 地址"
    return message


class GameClient(QObject):
    welcome_received = pyqtSignal(dict)
    state_changed = pyqtSignal(dict)
    game_finished = pyqtSignal(dict)
    chat_received = pyqtSignal(dict)
    disconnected = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self._on_connected)
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.error.connect(self._on_socket_error)
        self.buffer = b""
        self.name = ""
        self.host = ""
        self.port = 0
        self.last_seen = time.monotonic()
        self.notified = False
        self.closing = False
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self._heartbeat)

    def connect_to_host(self, host, port, name):
        self.host = host
        self.port = int(port)
        self.name = clean_name(name)
        self.buffer = b""
        self.notified = False
        self.closing = False
        self.socket.connectToHost(host, self.port)

    def _on_connected(self):
        self.last_seen = time.monotonic()
        self.notified = False
        self.heartbeat.start(5000)
        logger.info("已连接主机 %s:%s", self.host, self.port)
        self._send({
            "type": "hello",
            "version": PROTOCOL_VERSION,
            "name": self.name,
        })

    def _on_ready_read(self):
        self.buffer += bytes(self.socket.readAll())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                message = decode_message(line)
            except ProtocolError as exc:
                self.error_occurred.emit(str(exc))
                continue
            self.last_seen = time.monotonic()
            self._handle(message)

    def _handle(self, message):
        message_type = message.get("type")
        if message_type == "welcome":
            if int(message.get("version", 0)) != PROTOCOL_VERSION:
                self._fail("协议版本不一致")
                return
            logger.info("已加入房间 %s", message.get("room", ""))
            self.welcome_received.emit(message)
        elif message_type == "state":
            state = message.get("state")
            if isinstance(state, dict):
                self.state_changed.emit(state)
        elif message_type == "move_result":
            if message.get("ok") and isinstance(message.get("state"), dict):
                self.state_changed.emit(message["state"])
            else:
                self.error_occurred.emit(message.get("error", "落子失败"))
        elif message_type == "result":
            self.game_finished.emit(message)
        elif message_type == "chat":
            self.chat_received.emit(message)
        elif message_type == "error":
            self.error_occurred.emit(message.get("message", "未知错误"))
        elif message_type == "ping":
            self._send({"type": "pong"})
        elif message_type == "pong":
            pass
        elif message_type == "bye":
            self._fail(message.get("reason", "主机已关闭房间"))

    def send_move(self, x, y):
        self._send({"type": "move", "x": int(x), "y": int(y)})

    def send_pass(self):
        self._send({"type": "pass"})

    def send_resign(self):
        self._send({"type": "resign"})

    def send_chat(self, text):
        self._send({"type": "chat", "text": text})

    def _send(self, message):
        if self.socket.state() != QAbstractSocket.ConnectedState:
            return
        try:
            self.socket.write(encode_message(message))
            self.socket.flush()
        except Exception:
            pass

    def _heartbeat(self):
        if self.socket.state() != QAbstractSocket.ConnectedState:
            return
        if time.monotonic() - self.last_seen > 15.0:
            self._fail("连接超时")
            return
        self._send({"type": "ping"})

    def _on_socket_error(self, _error):
        if not self.closing:
            self._fail(_friendly_socket_error(self.socket.errorString()))

    def _on_disconnected(self):
        self.heartbeat.stop()
        if not self.notified and not self.closing:
            self._fail("连接已断开")

    def _fail(self, reason):
        if self.notified:
            return
        self.notified = True
        self.heartbeat.stop()
        logger.warning("连接结束：%s", reason)
        self.disconnected.emit(reason)
        self.close()

    def close(self):
        self.closing = True
        self.heartbeat.stop()
        if self.socket.state() != QAbstractSocket.UnconnectedState:
            self.socket.disconnectFromHost()
        self.socket.close()
