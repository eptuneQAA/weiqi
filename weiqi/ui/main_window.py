from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction, QDialog, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ..ai.engine import AIEngine
from ..core.board import BLACK, EMPTY, WHITE, color_name, opponent
from ..core.game import GameState, Phase
from ..core.scoring import score_text, toggle_group_dead
from ..net.client import GameClient
from ..net.discovery import RoomBroadcaster, RoomListener
from ..net.server import GameServer
from .board_widget import BoardWidget
from .chat_widget import ChatWidget
from .dialogs import (
    HostGameDialog, JoinGameDialog, NewGameDialog, ResultDialog,
)

MODE_IDLE = "idle"
MODE_AI = "ai"
MODE_HOST = "host"
MODE_GUEST = "guest"


class AIWorker(QThread):
    move_ready = pyqtSignal(object)

    def __init__(self, engine, snapshot, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.snapshot = snapshot
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        move = None
        try:
            game = GameState.from_snapshot(self.snapshot)
            move = self.engine.choose_move(
                game, cancel_check=lambda: self.cancelled
            )
        except Exception:
            move = None
        self.move_ready.emit(move)


class MainWindow(QMainWindow):
    def __init__(self, discovery_enabled=True, parent=None):
        super().__init__(parent)
        self.discovery_enabled = discovery_enabled
        self.mode = MODE_IDLE
        self.game = GameState(19)
        self.human_color = BLACK
        self.ai_color = WHITE
        self.ai_engine = None
        self.ai_worker = None
        self.ai_generation = 0
        self.last_ai_config = None
        self.server = None
        self.client = None
        self.broadcaster = None
        self.listener = None
        self.guest_joined = False
        self.client_connected = False
        self.result_shown = False
        self.local_name = ""
        self.setWindowTitle("围棋")
        self.resize(1040, 780)
        self._build_ui()
        self._build_menu()
        self._update_ui()
        self.statusBar().showMessage("请选择：人机对战 / 创建房间 / 加入房间")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        self.board_widget = BoardWidget()
        self.board_widget.point_clicked.connect(self._on_point_clicked)
        layout.addWidget(self.board_widget, 1)
        side = QWidget()
        side.setFixedWidth(312)
        side_layout = QVBoxLayout(side)
        title = QLabel("对局信息")
        title.setFont(QFont("", 11, QFont.Bold))
        side_layout.addWidget(title)
        self.mode_label = QLabel("模式：未开始")
        self.turn_label = QLabel("—")
        self.capture_label = QLabel("提子：黑 0 / 白 0")
        self.move_label = QLabel("手数：0")
        self.room_label = QLabel("")
        self.room_label.setWordWrap(True)
        self.score_label = QLabel("")
        self.score_label.setWordWrap(True)
        for widget in (
            self.mode_label, self.turn_label, self.capture_label,
            self.move_label, self.room_label, self.score_label,
        ):
            side_layout.addWidget(widget)
        side_layout.addSpacing(8)
        grid = QGridLayout()
        self.new_button = QPushButton("新对局")
        self.pass_button = QPushButton("停一手")
        self.resign_button = QPushButton("认输")
        self.undo_button = QPushButton("悔棋")
        self.confirm_button = QPushButton("确认数子")
        self.new_button.clicked.connect(self._new_ai_game)
        self.pass_button.clicked.connect(self._pass)
        self.resign_button.clicked.connect(self._resign)
        self.undo_button.clicked.connect(self._undo)
        self.confirm_button.clicked.connect(self._confirm_score)
        grid.addWidget(self.new_button, 0, 0)
        grid.addWidget(self.pass_button, 0, 1)
        grid.addWidget(self.resign_button, 1, 0)
        grid.addWidget(self.undo_button, 1, 1)
        grid.addWidget(self.confirm_button, 2, 0, 1, 2)
        side_layout.addLayout(grid)
        self.chat = ChatWidget()
        self.chat.message_sent.connect(self._send_chat)
        self.chat.setVisible(False)
        side_layout.addWidget(self.chat, 1)
        layout.addWidget(side)

    def _build_menu(self):
        game_menu = self.menuBar().addMenu("对局")
        for text, slot in (
            ("人机对战", self._new_ai_game),
            ("创建局域网房间", self._create_host),
            ("加入局域网房间", self._join_host),
        ):
            action = QAction(text, self)
            action.triggered.connect(slot)
            game_menu.addAction(action)
        game_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        game_menu.addAction(quit_action)
        help_menu = self.menuBar().addMenu("帮助")
        rules_action = QAction("规则说明", self)
        rules_action.triggered.connect(self._show_rules)
        help_menu.addAction(rules_action)
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _cancel_ai(self):
        self.ai_generation += 1
        worker = self.ai_worker
        self.ai_worker = None
        if worker is not None:
            worker.cancel()
            worker.wait()

    def _stop_session(self):
        self._cancel_ai()
        if self.server is not None:
            self.server.stop()
            self.server.deleteLater()
            self.server = None
        if self.client is not None:
            self.client.close()
            self.client.deleteLater()
            self.client = None
        self._stop_broadcaster()
        if self.listener is not None:
            self.listener.stop()
            self.listener.deleteLater()
            self.listener = None
        self.guest_joined = False
        self.client_connected = False
        self.chat.set_enabled(False)

    def _stop_broadcaster(self):
        if self.broadcaster is not None:
            self.broadcaster.stop()
            self.broadcaster.deleteLater()
            self.broadcaster = None

    def _start_ai_game(self, size, difficulty, color):
        self._stop_session()
        self.mode = MODE_AI
        self.human_color = color
        self.ai_color = opponent(color)
        self.game = GameState(size, 7.5, BLACK)
        self.ai_engine = AIEngine(difficulty)
        self.last_ai_config = (size, difficulty, color)
        self.result_shown = False
        self.local_name = ""
        self.chat.setVisible(False)
        self.chat.clear()
        self._update_ui()
        if self.game.turn == self.ai_color:
            self._start_ai()
        else:
            self.statusBar().showMessage("轮到你落子")

    def _new_ai_game(self):
        dialog = NewGameDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        size, difficulty, color = dialog.values()
        self._start_ai_game(size, difficulty, color)

    def _create_host(self):
        dialog = HostGameDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        room, size, host_color, port = dialog.values()
        self._start_host_session(room, size, host_color, port)

    def _start_host_session(self, room, size, host_color, port):
        self._stop_session()
        server = GameServer(room, size, host_color, "主机", port, 7.5, self)
        ok, err = server.start()
        if not ok:
            QMessageBox.warning(
                self, "无法创建房间",
                "端口 {} 启动失败：{}".format(port, err),
            )
            server.deleteLater()
            self.mode = MODE_IDLE
            self.game = GameState(19)
            self.chat.setVisible(False)
            self._update_ui()
            return
        self.server = server
        server.state_changed.connect(self._apply_snapshot)
        server.game_finished.connect(self._on_remote_finished)
        server.chat_received.connect(self._on_chat)
        server.client_joined.connect(self._on_client_joined)
        server.client_left.connect(self._on_client_left)
        server.error_occurred.connect(self._show_error)
        self.mode = MODE_HOST
        self.human_color = host_color
        self.ai_color = opponent(host_color)
        self.game = server.game
        self.result_shown = False
        self.guest_joined = False
        self.local_name = "主机"
        self.chat.setVisible(True)
        self.chat.clear()
        self.chat.set_enabled(False)
        if self.discovery_enabled:
            self.broadcaster = RoomBroadcaster(self)
            self.broadcaster.start(room, server.port, size, host_color)
        self._update_ui()
        self.statusBar().showMessage("房间已创建，等待对手加入…")

    def _join_host(self):
        listener = None
        if self.discovery_enabled:
            candidate = RoomListener(self)
            if candidate.start():
                listener = candidate
            else:
                candidate.deleteLater()
        dialog = JoinGameDialog(listener, self)
        if listener is not None:
            listener.rooms_changed.connect(dialog.update_rooms)
        if dialog.exec_() != QDialog.Accepted:
            if listener is not None:
                listener.stop()
                listener.deleteLater()
            return
        ip, port, name = dialog.values()
        if listener is not None:
            listener.stop()
            listener.deleteLater()
        self._start_guest_session(ip, port, name)

    def _start_guest_session(self, ip, port, name):
        self._stop_session()
        client = GameClient(self)
        client.welcome_received.connect(self._on_welcome)
        client.state_changed.connect(self._apply_snapshot)
        client.game_finished.connect(self._on_remote_finished)
        client.chat_received.connect(self._on_chat)
        client.disconnected.connect(self._on_client_disconnected)
        client.error_occurred.connect(self._show_error)
        self.client = client
        self.mode = MODE_GUEST
        self.local_name = name
        self.client_connected = False
        self.result_shown = False
        self.chat.setVisible(True)
        self.chat.clear()
        self.chat.set_enabled(False)
        self._update_ui()
        self.statusBar().showMessage("正在连接 {}:{}…".format(ip, port))
        try:
            client.connect_to_host(ip, port, name)
        except Exception as exc:
            self._show_error(str(exc))

    def _on_welcome(self, message):
        try:
            self.game = GameState.from_snapshot(message["state"])
        except (KeyError, TypeError, ValueError) as exc:
            self._show_error("无法同步棋局：" + str(exc))
            return
        self.human_color = int(message.get("guest_color", WHITE))
        self.ai_color = opponent(self.human_color)
        self.client_connected = True
        self.chat.set_enabled(True)
        self.chat.add_system("已加入房间：{}".format(message.get("room", "")))
        self.statusBar().showMessage("已加入房间，等待落子")
        self._update_ui()

    def _on_client_joined(self, message):
        self.guest_joined = True
        name = message.get("name", "客机")
        self.chat.set_enabled(True)
        self.chat.add_system("{} 加入了房间".format(name))
        self.statusBar().showMessage("对手已加入：{}".format(name))
        self._update_ui()

    def _on_client_left(self, reason):
        self.guest_joined = False
        self._stop_broadcaster()
        self.chat.set_enabled(False)
        self.chat.add_system(reason)
        self.statusBar().showMessage(reason)
        self._update_ui()

    def _on_client_disconnected(self, reason):
        was_connected = self.client_connected
        self.client_connected = False
        self.chat.set_enabled(False)
        self.chat.add_system(reason)
        self.statusBar().showMessage(reason)
        self._update_ui()
        if not was_connected:
            QMessageBox.warning(self, "连接失败", reason)

    def _apply_snapshot(self, data):
        if not isinstance(data, dict):
            return
        try:
            self.game = GameState.from_snapshot(data)
        except (KeyError, TypeError, ValueError) as exc:
            self._show_error("同步棋局失败：" + str(exc))
            return
        self._update_ui()
        if self.game.phase == Phase.FINISHED:
            self._stop_broadcaster()
            if not self.result_shown:
                self._show_result_from_game()

    def _on_remote_finished(self, message):
        if self.result_shown:
            return
        self._show_result(
            message.get("score"),
            message.get("reason", "") or self.game.result_reason,
        )

    def _is_connected(self):
        if self.mode == MODE_HOST:
            return self.guest_joined
        if self.mode == MODE_GUEST:
            return self.client_connected
        return self.mode == MODE_AI

    def _is_local_turn(self):
        if self.game.phase != Phase.PLAYING:
            return False
        if self.mode == MODE_AI:
            return self.game.turn == self.human_color
        if self.mode == MODE_HOST:
            return self.guest_joined and self.game.turn == self.human_color
        if self.mode == MODE_GUEST:
            return self.client_connected and self.game.turn == self.human_color
        return False

    def _can_mark_dead(self):
        if self.game.phase != Phase.SCORING:
            return False
        if self.mode == MODE_AI:
            return True
        return self.mode == MODE_HOST and self.guest_joined

    def _can_resign(self):
        if self.game.phase not in (Phase.PLAYING, Phase.SCORING):
            return False
        return self._is_connected()

    def _can_undo(self):
        return (
            self.mode == MODE_AI
            and self.game.phase == Phase.PLAYING
            and bool(self.game.history)
            and (
                self.game.turn == self.human_color
                or self.ai_worker is not None
            )
        )

    def _chat_available(self):
        if self.mode == MODE_HOST:
            return self.guest_joined
        if self.mode == MODE_GUEST:
            return self.client_connected
        return False

    def _update_ui(self):
        phase = self.game.phase
        interactive = phase == Phase.PLAYING and self._is_local_turn()
        marking = phase == Phase.SCORING and self._can_mark_dead()
        self.board_widget.set_state(
            self.game.board, self.game.last_move, interactive, marking,
            self.game.dead_points, self.human_color,
        )
        mode_names = {
            MODE_IDLE: "未开始", MODE_AI: "人机对战",
            MODE_HOST: "主机", MODE_GUEST: "客机",
        }
        self.mode_label.setText(
            "模式：{}".format(mode_names.get(self.mode, "未开始"))
        )
        if self.mode == MODE_IDLE:
            self.turn_label.setText("—")
        elif phase == Phase.PLAYING:
            if self.mode in (MODE_HOST, MODE_GUEST) and not self._is_connected():
                self.turn_label.setText("等待对手…")
            else:
                self.turn_label.setText(
                    "轮到：{}方".format(color_name(self.game.turn))
                )
        elif phase == Phase.SCORING:
            self.turn_label.setText("数子阶段")
        else:
            self.turn_label.setText("对局结束")
        captures = self.game.board.captures
        self.capture_label.setText(
            "提子：黑 {} / 白 {}".format(captures[BLACK], captures[WHITE])
        )
        self.move_label.setText("手数：{}".format(self.game.move_count))
        if self.mode == MODE_HOST and self.server is not None:
            self.room_label.setText(
                "房间：{}  端口：{}".format(
                    self.server.room_name, self.server.port
                )
            )
        elif self.mode == MODE_GUEST:
            self.room_label.setText("客机模式")
        else:
            self.room_label.setText("")
        if phase == Phase.SCORING and self.game.score:
            score = self.game.score
            self.score_label.setText(
                "黑 {} 点 / 白 {} + {:.1f} = {:.1f} 点".format(
                    score["black_area"], score["white_area"],
                    score["komi"], score["white_total"],
                )
            )
        else:
            self.score_label.setText("")
        self.pass_button.setEnabled(interactive)
        self.resign_button.setEnabled(self._can_resign())
        self.undo_button.setEnabled(self._can_undo())
        self.confirm_button.setEnabled(marking)
        self.chat.set_enabled(self._chat_available())

    def _on_point_clicked(self, x, y):
        if self.game.phase == Phase.SCORING:
            if not self._can_mark_dead():
                return
            if self.game.board.get(x, y) == EMPTY:
                return
            new_dead = toggle_group_dead(
                self.game.board, self.game.dead_points, x, y
            )
            if self.mode == MODE_HOST and self.server is not None:
                ok, err = self.server.host_mark_dead(sorted(new_dead))
                if not ok:
                    self.statusBar().showMessage(err, 3000)
            else:
                self.game.set_dead_points(sorted(new_dead))
                self._update_ui()
                if self.game.score:
                    self.statusBar().showMessage(
                        score_text(self.game.score), 5000
                    )
            return
        if self.game.phase != Phase.PLAYING:
            return
        if not self._is_local_turn():
            self.statusBar().showMessage("还没轮到你", 3000)
            return
        if self.mode == MODE_AI:
            ok, err = self.game.play(x, y)
            if not ok:
                self.statusBar().showMessage(err, 3000)
                return
            self._update_ui()
            if self.game.phase == Phase.SCORING:
                self.statusBar().showMessage("双方停一手，进入数子", 5000)
            else:
                self._start_ai()
        elif self.mode == MODE_HOST:
            if self.server is None:
                return
            ok, err = self.server.host_play(x, y)
            if not ok:
                self.statusBar().showMessage(err, 3000)
        elif self.mode == MODE_GUEST:
            if self.client is None:
                return
            ok, err = self.game.is_legal(x, y)
            if not ok:
                self.statusBar().showMessage(err, 3000)
                return
            self.client.send_move(x, y)
            self.statusBar().showMessage("已发送落子", 1500)

    def _pass(self):
        if self.game.phase != Phase.PLAYING:
            return
        if self.mode == MODE_AI:
            if not self._is_local_turn():
                return
            self.game.pass_turn()
            self._update_ui()
            if self.game.phase == Phase.SCORING:
                self.statusBar().showMessage("双方停一手，进入数子", 5000)
            else:
                self._start_ai()
        elif self.mode == MODE_HOST and self.server is not None:
            ok, err = self.server.host_pass()
            if not ok:
                self.statusBar().showMessage(err, 3000)
        elif self.mode == MODE_GUEST and self.client is not None:
            if self._is_local_turn():
                self.client.send_pass()

    def _resign(self):
        if not self._can_resign():
            return
        answer = QMessageBox.question(
            self, "认输", "确定认输吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if self.mode == MODE_AI:
            self.game.resign(self.human_color)
            self._update_ui()
            self._show_result_from_game()
        elif self.mode == MODE_HOST and self.server is not None:
            self.server.host_resign()
        elif self.mode == MODE_GUEST and self.client is not None:
            self.client.send_resign()

    def _undo(self):
        if not self._can_undo():
            return
        self._cancel_ai()
        count = 1
        if (
            len(self.game.history) >= 2
            and self.game.history[-1][0] == self.ai_color
        ):
            count = 2
        if self.game.undo(count):
            self.result_shown = False
            self._update_ui()
            if self.game.turn == self.ai_color:
                self._start_ai()

    def _confirm_score(self):
        if not self._can_mark_dead():
            return
        if self.mode == MODE_AI:
            self.game.confirm_score()
            self._update_ui()
            self._show_result_from_game()
        elif self.mode == MODE_HOST and self.server is not None:
            self.server.host_confirm_score()

    def _start_ai(self):
        if self.mode != MODE_AI or self.game.phase != Phase.PLAYING:
            return
        if self.game.turn != self.ai_color or self.ai_engine is None:
            return
        if self.ai_worker is not None:
            return
        self.ai_generation += 1
        generation = self.ai_generation
        worker = AIWorker(self.ai_engine, self.game.snapshot(), self)
        worker.move_ready.connect(
            lambda move, value=generation: self._on_ai_move(move, value)
        )
        worker.finished.connect(worker.deleteLater)
        self.ai_worker = worker
        self.statusBar().showMessage("AI 思考中…")
        self._update_ui()
        worker.start()

    def _on_ai_move(self, move, generation):
        if generation != self.ai_generation or self.mode != MODE_AI:
            return
        self.ai_worker = None
        if self.game.phase != Phase.PLAYING or self.game.turn != self.ai_color:
            self._update_ui()
            return
        if move is None:
            self.game.pass_turn()
        else:
            ok, _err = self.game.play(move[0], move[1])
            if not ok:
                self.game.pass_turn()
        self._update_ui()
        if self.game.phase == Phase.SCORING:
            self.statusBar().showMessage("双方停一手，进入数子", 5000)

    def _send_chat(self, text):
        if not text:
            return
        if self.mode == MODE_HOST and self.server is not None:
            ok, err = self.server.host_chat(text)
            if not ok:
                self.statusBar().showMessage(err, 3000)
        elif self.mode == MODE_GUEST and self.client is not None:
            self.client.send_chat(text)

    def _on_chat(self, message):
        name = str(message.get("name", ""))
        text = str(message.get("text", ""))
        stamp = message.get("timestamp")
        if isinstance(stamp, (int, float)):
            time_text = datetime.fromtimestamp(
                stamp / 1000.0
            ).strftime("%H:%M")
        else:
            time_text = datetime.now().strftime("%H:%M")
        self.chat.add_message(
            name, text, time_text, is_self=(name == self.local_name)
        )

    def _show_result_from_game(self):
        self._show_result(self.game.score, self.game.result_reason)

    def _show_result(self, score, reason):
        if self.result_shown:
            return
        self.result_shown = True
        if score:
            text = score_text(score)
            text += (
                "\n\n黑：{} 点（{} 子 + {} 空）"
                "\n白：{} 点 + 贴目 {:.1f} = {:.1f} 点"
                "\n结束原因：{}"
            ).format(
                score["black_area"], score["black_stones"],
                score["black_territory"], score["white_area"],
                score["komi"], score["white_total"], reason or "数子",
            )
        elif self.game.winner:
            side = "黑" if self.game.winner == "black" else "白"
            text = "{}方获胜（{}）".format(side, reason or "对局结束")
        else:
            text = "对局结束（{}）".format(reason or "未知")
        allow_replay = self.mode == MODE_AI and self.last_ai_config is not None
        dialog = ResultDialog(text, allow_replay, self)
        dialog.exec_()
        if dialog.replay and self.last_ai_config is not None:
            size, difficulty, color = self.last_ai_config
            self._start_ai_game(size, difficulty, color)

    def _show_error(self, text):
        self.statusBar().showMessage(str(text), 5000)

    def _show_rules(self):
        QMessageBox.information(
            self, "规则说明",
            "采用中国规则数子，贴目 7.5。\n"
            "禁止自杀，禁止重复局面（位置超级劫）。\n"
            "双方连续停一手后进入数子阶段，"
            "可点击棋组标记死子，确认后计算胜负。\n"
            "局域网对战由主机校验落子；聊天消息仅当前房间可见。",
        )

    def _show_about(self):
        QMessageBox.information(
            self, "关于",
            "围棋\n桌面围棋软件，支持人机对战与局域网对战。\n"
            "PyQt5 / Python 3.7",
        )

    def closeEvent(self, event):
        self._stop_session()
        super().closeEvent(event)
