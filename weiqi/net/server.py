"""主机端 TCP 服务，持有唯一权威对局状态。"""

import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtNetwork import QHostAddress, QTcpServer

from ..core.board import BLACK, opponent
from ..core.game import GameState, Phase
from .protocol import (
    PROTOCOL_VERSION, ProtocolError, clean_chat_text, clean_name,
    decode_message, encode_message,
)


class GameServer(QObject):
    state_changed = pyqtSignal(dict)
    game_finished = pyqtSignal(dict)
    chat_received = pyqtSignal(dict)
    client_joined = pyqtSignal(dict)
    client_left = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(
        self, room_name, size=19, host_color=BLACK, host_name="主机",
        port=45679, komi=7.5, parent=None,
    ):
        super().__init__(parent)
        self.room_name = room_name
        self.host_color = host_color
        self.guest_color = opponent(host_color)
        self.host_name = host_name
        self.port = int(port)
        self.game = GameState(size, komi, BLACK)
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self._on_new_connection)
        self.socket = None
        self.buffer = b""
        self.client_ready = False
        self.guest_name = ""
        self.last_seen = time.monotonic()
        self.error_count = 0
        self.closing = False
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self._heartbeat)
        self.heartbeat.start(5000)

    def start(self):
        ok = self.server.listen(QHostAddress.AnyIPv4, self.port)
        if not ok:
            return False, self.server.errorString()
        self.port = self.server.serverPort()
        return True, ""

    def stop(self):
        self.closing = True
        self.heartbeat.stop()
        socket = self.socket
        self.socket = None
        if socket is not None:
            try:
                socket.write(encode_message(
                    {"type": "bye", "reason": "主机已关闭房间"}
                ))
                socket.flush()
                socket.disconnectFromHost()
            except Exception:
                pass
            socket.deleteLater()
        self.client_ready = False
        self.server.close()

    def _on_new_connection(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if self.socket is not None:
                try:
                    socket.write(encode_message(
                        {"type": "bye", "reason": "房间已有玩家"}
                    ))
                    socket.flush()
                except Exception:
                    pass
                socket.disconnectFromHost()
                socket.deleteLater()
                continue
            self.socket = socket
            self.buffer = b""
            self.client_ready = False
            self.last_seen = time.monotonic()
            socket.readyRead.connect(self._on_ready_read)
            socket.disconnected.connect(self._on_disconnected)

    def _on_ready_read(self):
        if self.socket is None:
            return
        self.buffer += bytes(self.socket.readAll())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                message = decode_message(line)
            except ProtocolError as exc:
                self._protocol_error(str(exc))
                continue
            self.last_seen = time.monotonic()
            self.error_count = 0
            self._handle(message)

    def _handle(self, message):
        message_type = message["type"]
        if not self.client_ready:
            if message_type != "hello":
                self._send_error("请先发送 hello")
                return
            try:
                version = int(message.get("version", 0))
                name = clean_name(message.get("name", ""))
            except (TypeError, ValueError, ProtocolError) as exc:
                self._send_error(str(exc))
                return
            if version != PROTOCOL_VERSION:
                self._send_error("协议版本不一致，请使用相同版本")
                self._disconnect_client("版本不一致")
                return
            self.guest_name = name
            self.client_ready = True
            state = self.game.snapshot()
            self._send({
                "type": "welcome",
                "version": PROTOCOL_VERSION,
                "room": self.room_name,
                "board_size": self.game.size,
                "komi": self.game.komi,
                "host_color": self.host_color,
                "guest_color": self.guest_color,
                "state": state,
            })
            self.client_joined.emit({"name": name, "state": state})
            return

        if message_type == "ping":
            self._send({"type": "pong"})
        elif message_type == "pong":
            pass
        elif message_type == "chat":
            try:
                text = clean_chat_text(message.get("text", ""))
            except ProtocolError as exc:
                self._send_error(str(exc))
                return
            self._broadcast_chat(self.guest_name, text)
        elif message_type == "move":
            self._guest_move(message)
        elif message_type == "pass":
            self._guest_pass()
        elif message_type == "resign":
            if self.game.phase == Phase.FINISHED:
                self._send_error("对局已结束")
                return
            self.game.resign(self.guest_color)
            self._after_change()
        elif message_type in ("mark_dead", "confirm_score"):
            self._send_error("只有主机可以操作数子")
        elif message_type == "leave":
            self._send({"type": "bye", "reason": "客机已离开"})
            self._disconnect_client("客机已离开", notify=True)
        else:
            self._send_error("未知消息类型")

    def _guest_move(self, message):
        if self.game.phase != Phase.PLAYING:
            self._send_move_result(False, "当前不能落子")
            return
        if self.game.turn != self.guest_color:
            self._send_move_result(False, "还没轮到你")
            return
        try:
            x = int(message.get("x"))
            y = int(message.get("y"))
        except (TypeError, ValueError):
            self._send_move_result(False, "坐标格式错误")
            return
        ok, err = self.game.play(x, y)
        self._send_move_result(ok, err)
        if ok:
            self._after_change()

    def _guest_pass(self):
        if self.game.phase != Phase.PLAYING:
            self._send_state()
            return
        if self.game.turn != self.guest_color:
            self._send_error("还没轮到你")
            return
        self.game.pass_turn()
        self._after_change()

    def host_play(self, x, y):
        if not self.client_ready:
            return False, "对手尚未加入"
        if self.game.phase != Phase.PLAYING:
            return False, "当前不能落子"
        if self.game.turn != self.host_color:
            return False, "还没轮到你"
        ok, err = self.game.play(x, y)
        if ok:
            self._after_change()
        return ok, err

    def host_pass(self):
        if not self.client_ready:
            return False, "对手尚未加入"
        if self.game.phase != Phase.PLAYING:
            return False, "当前不能停一手"
        if self.game.turn != self.host_color:
            return False, "还没轮到你"
        self.game.pass_turn()
        self._after_change()
        return True, ""

    def host_resign(self):
        if not self.client_ready:
            return False, "对手尚未加入"
        if self.game.phase == Phase.FINISHED:
            return False, "对局已结束"
        self.game.resign(self.host_color)
        self._after_change()
        return True, ""

    def host_mark_dead(self, points):
        if not self.client_ready:
            return False, "对手尚未加入"
        if self.game.phase != Phase.SCORING:
            return False, "当前不在数子阶段"
        self.game.set_dead_points(points)
        self._after_change()
        return True, ""

    def host_confirm_score(self):
        if not self.client_ready:
            return False, "对手尚未加入"
        if self.game.phase != Phase.SCORING:
            return False, "当前不在数子阶段"
        self.game.confirm_score()
        self._after_change()
        return True, ""

    def host_chat(self, text):
        try:
            clean = clean_chat_text(text)
        except ProtocolError as exc:
            return False, str(exc)
        self._broadcast_chat(self.host_name, clean)
        return True, ""

    def _broadcast_chat(self, name, text):
        message = {
            "type": "chat",
            "name": name,
            "text": text,
            "timestamp": int(time.time() * 1000),
        }
        self._send(message)
        self.chat_received.emit(message)

    def _after_change(self):
        state = self.game.snapshot()
        self._send({"type": "state", "state": state})
        self.state_changed.emit(state)
        if self.game.phase == Phase.FINISHED:
            result = self._result()
            self._send(dict(result, type="result"))
            self.game_finished.emit(result)

    def _result(self):
        return {
            "winner": self.game.winner,
            "reason": self.game.result_reason,
            "score": self.game.score,
            "resigned_by": self.game.resigned_by,
            "state": self.game.snapshot(),
        }

    def _send_move_result(self, ok, error):
        self._send({
            "type": "move_result",
            "ok": bool(ok),
            "error": error,
            "state": self.game.snapshot(),
        })

    def _send_state(self):
        self._send({"type": "state", "state": self.game.snapshot()})

    def _send_error(self, text):
        self._send({"type": "error", "message": text})
        self.error_count += 1
        if self.error_count > 5:
            self._disconnect_client("非法消息过多", notify=True)

    def _protocol_error(self, text):
        self._send_error(text)

    def _send(self, message):
        if self.socket is None:
            return
        try:
            self.socket.write(encode_message(message))
            self.socket.flush()
        except Exception:
            pass

    def _heartbeat(self):
        if self.socket is None or not self.client_ready:
            return
        if time.monotonic() - self.last_seen > 15.0:
            self._disconnect_client("连接超时", notify=True)
            return
        self._send({"type": "ping"})

    def _disconnect_client(self, reason, notify=False):
        socket = self.socket
        if socket is None:
            return
        self.socket = None
        was_ready = self.client_ready
        self.client_ready = False
        self.guest_name = ""
        self.error_count = 0
        try:
            socket.write(encode_message({"type": "bye", "reason": reason}))
            socket.flush()
            socket.disconnectFromHost()
        except Exception:
            pass
        socket.deleteLater()
        if notify and was_ready:
            self.client_left.emit(reason)

    def _on_disconnected(self):
        if self.socket is None:
            return
        self.socket.deleteLater()
        self.socket = None
        was_ready = self.client_ready
        self.client_ready = False
        self.guest_name = ""
        if was_ready and not self.closing:
            self.client_left.emit("对手已断开")
