from datetime import datetime
import os

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QDialog, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ..ai.engine import AIEngine
from ..core.board import BLACK, EMPTY, WHITE, color_name, opponent
from ..core.game import GameState, Phase
from ..core.scoring import score_text, toggle_group_dead
from ..core import sgf
from ..net.client import GameClient
from ..net.discovery import RoomBroadcaster, RoomListener
from ..net.server import GameServer
from .board_widget import BoardWidget
from .chat_widget import ChatWidget
from .dialogs import (
    HostGameDialog, JoinGameDialog, NewGameDialog, ResultDialog,
)
from .help_dialog import HelpDialog
from .settings import SettingsDialog, get as get_setting, set_value
from .welcome import WelcomeWidget
from . import theme

MODE_IDLE = "idle"
MODE_AI = "ai"
MODE_HOST = "host"
MODE_GUEST = "guest"
MODE_REVIEW = "review"


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
        self.review_game = None
        self.review_moves = []
        self.review_index = 0
        self.review_path = ""
        self.setWindowTitle("围棋")
        self.resize(1040, 780)
        geometry = get_setting("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._build_ui()
        self._build_menu()
        self._update_ui()
        self._refresh_recent()
        self.stack.setFocus()
        self.statusBar().showMessage("请选择：人机对战 / 创建房间 / 加入房间")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        self.stack = QStackedWidget()
        self.welcome = WelcomeWidget()
        self.welcome.new_game.connect(self._new_ai_game)
        self.welcome.host_game.connect(self._create_host)
        self.welcome.join_game.connect(self._join_host)
        self.welcome.open_sgf.connect(self._open_sgf)
        self.welcome.open_path.connect(self._open_sgf_path)
        self.board_widget = BoardWidget()
        self.board_widget.point_clicked.connect(self._on_point_clicked)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.board_widget)
        layout.addWidget(self.stack, 1)

        side = QWidget()
        side.setFixedWidth(320)
        side_layout = QVBoxLayout(side)
        side_layout.setSpacing(8)
        title = QLabel("对局信息")
        title.setObjectName("sideTitle")
        side_layout.addWidget(title)

        self.info_form = QFormLayout()
        self.info_form.setLabelAlignment(Qt.AlignLeft)
        self.info_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.info_form.setHorizontalSpacing(18)
        self.info_form.setVerticalSpacing(6)
        self.mode_label = QLabel("未开始")
        self.board_label = QLabel("—")
        self.komi_label = QLabel("—")
        self.turn_label = QLabel("—")
        self.move_label = QLabel("0")
        self.capture_label = QLabel("黑 0 / 白 0")
        self.room_label = QLabel("—")
        self.room_label.setWordWrap(True)
        for caption, widget in (
            ("模式", self.mode_label),
            ("棋盘", self.board_label),
            ("贴目", self.komi_label),
            ("轮到", self.turn_label),
            ("手数", self.move_label),
            ("提子", self.capture_label),
            ("房间", self.room_label),
        ):
            self.info_form.addRow(caption, widget)
        self.info_panel = QWidget()
        self.info_panel.setLayout(self.info_form)
        side_layout.addWidget(self.info_panel)
        self.idle_hint = QLabel(
            "还没有开始对局。\n从左侧选择一种模式，或按 Ctrl+N 开始人机对战。"
        )
        self.idle_hint.setWordWrap(True)
        self.idle_hint.setObjectName("welcomeHint")
        self.idle_hint.setVisible(False)
        side_layout.addWidget(self.idle_hint)
        self.score_label = QLabel("")
        self.score_label.setWordWrap(True)
        self.score_label.setObjectName("scoreLabel")
        side_layout.addWidget(self.score_label)
        side_layout.addSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.new_button = QPushButton("新对局")
        self.new_button.setObjectName("primaryButton")
        self.new_button.setShortcut(QKeySequence.New)
        self.pass_button = QPushButton("停一手")
        self.resign_button = QPushButton("认输")
        self.undo_button = QPushButton("悔棋")
        self.confirm_button = QPushButton("确认数子")
        self.save_button = QPushButton("保存棋谱")
        self.new_button.clicked.connect(self._new_ai_game)
        self.pass_button.clicked.connect(self._pass)
        self.resign_button.clicked.connect(self._resign)
        self.undo_button.clicked.connect(self._undo)
        self.confirm_button.clicked.connect(self._confirm_score)
        self.save_button.clicked.connect(self._save_sgf)
        grid.addWidget(self.new_button, 0, 0, 1, 2)
        grid.addWidget(self.pass_button, 1, 0)
        grid.addWidget(self.undo_button, 1, 1)
        grid.addWidget(self.resign_button, 2, 0)
        grid.addWidget(self.save_button, 2, 1)
        grid.addWidget(self.confirm_button, 3, 0, 1, 2)
        side_layout.addLayout(grid)
        side_layout.addStretch(1)

        self.chat = ChatWidget()
        self.chat.message_sent.connect(self._send_chat)
        self.chat.setVisible(False)
        side_layout.addWidget(self.chat)
        layout.addWidget(side)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(
            """
            QLabel#sideTitle { font-size: 15px; font-weight: bold; }
            QPushButton#primaryButton {
                background: %(primary)s; color: white; border: none;
                border-radius: 6px; padding: 9px 14px; font-weight: bold;
            }
            QPushButton#primaryButton:hover { background: %(primary_hover)s; }
            QPushButton#primaryButton:disabled {
                background: #cfc7b6; color: #f5f1e8;
            }
            QPushButton {
                padding: 7px 10px; border-radius: 5px;
                border: 1px solid %(border)s; background: #ffffff;
            }
            QPushButton:hover { background: %(hover)s; }
            QPushButton:disabled {
                color: #a89f8e; background: #f2ede2; border-color: #e6dfd0;
            }
            QLabel#scoreLabel { color: %(accent)s; }
            """ % {
                "primary": theme.PRIMARY.name(),
                "primary_hover": theme.PRIMARY_HOVER.name(),
                "accent": theme.ACCENT.name(),
                "border": theme.BORDER.name(),
                "hover": theme.BOARD_LIGHT.name(),
            }
        )

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("文件")
        open_action = QAction("打开棋谱…", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.setStatusTip("打开 SGF 棋谱复盘（Ctrl+O）")
        open_action.triggered.connect(self._open_sgf)
        file_menu.addAction(open_action)
        save_action = QAction("保存棋谱…", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip("把当前对局保存为 SGF（Ctrl+S）")
        save_action.triggered.connect(self._save_sgf)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        game_menu = self.menuBar().addMenu("对局")
        new_action = QAction("人机对战…", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.setStatusTip("开始一盘人机对局（Ctrl+N）")
        new_action.triggered.connect(self._new_ai_game)
        game_menu.addAction(new_action)
        host_action = QAction("创建局域网房间…", self)
        host_action.triggered.connect(self._create_host)
        game_menu.addAction(host_action)
        join_action = QAction("加入局域网房间…", self)
        join_action.triggered.connect(self._join_host)
        game_menu.addAction(join_action)
        game_menu.addSeparator()

        self.undo_action = QAction("悔棋", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self._undo)
        game_menu.addAction(self.undo_action)
        self.pass_action = QAction("停一手", self)
        self.pass_action.setShortcut(QKeySequence("P"))
        self.pass_action.triggered.connect(self._pass)
        game_menu.addAction(self.pass_action)
        self.resign_action = QAction("认输", self)
        self.resign_action.triggered.connect(self._resign)
        game_menu.addAction(self.resign_action)
        self.confirm_action = QAction("确认数子", self)
        self.confirm_action.triggered.connect(self._confirm_score)
        game_menu.addAction(self.confirm_action)
        game_menu.addSeparator()

        self.prev_action = QAction("上一手", self)
        self.prev_action.setShortcut(QKeySequence(Qt.Key_Left))
        self.prev_action.triggered.connect(lambda: self._review_step(-1))
        game_menu.addAction(self.prev_action)
        self.next_action = QAction("下一手", self)
        self.next_action.setShortcut(QKeySequence(Qt.Key_Right))
        self.next_action.triggered.connect(lambda: self._review_step(1))
        game_menu.addAction(self.next_action)
        self.first_action = QAction("回到开局", self)
        self.first_action.setShortcut(QKeySequence("Home"))
        self.first_action.triggered.connect(lambda: self._review_goto(0))
        game_menu.addAction(self.first_action)
        self.last_action = QAction("跳到末手", self)
        self.last_action.setShortcut(QKeySequence("End"))
        self.last_action.triggered.connect(
            lambda: self._review_goto(len(self.review_moves))
        )
        game_menu.addAction(self.last_action)

        settings_menu = self.menuBar().addMenu("设置")
        options_action = QAction("选项…", self)
        options_action.triggered.connect(self._show_settings)
        settings_menu.addAction(options_action)

        help_menu = self.menuBar().addMenu("帮助")
        help_action = QAction("新手帮助", self)
        help_action.setShortcut(QKeySequence.HelpContents)
        help_action.setStatusTip("打开图文新手帮助（F1）")
        help_action.triggered.connect(
            lambda _checked=False: self._show_help("quickstart")
        )
        help_menu.addAction(help_action)
        rules_action = QAction("规则说明", self)
        rules_action.triggered.connect(
            lambda _checked=False: self._show_help("board")
        )
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

    def _start_ai_game(self, size, difficulty, color, komi=7.5, handicap=0):
        self._stop_session()
        self.mode = MODE_AI
        self.human_color = color
        self.ai_color = opponent(color)
        self.game = GameState(size, komi, BLACK, handicap)
        self.ai_engine = AIEngine(difficulty)
        self.last_ai_config = {
            "size": size, "difficulty": difficulty, "color": color,
            "komi": komi, "handicap": handicap,
        }
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
        defaults = {
            "size": get_setting("board_size"),
            "difficulty": get_setting("difficulty"),
            "color": get_setting("human_color"),
            "komi": get_setting("komi"),
            "handicap": get_setting("handicap"),
        }
        dialog = NewGameDialog(self, defaults)
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()
        set_value("board_size", values["size"])
        set_value("difficulty", values["difficulty"])
        set_value("human_color", values["color"])
        set_value("komi", values["komi"])
        set_value("handicap", values["handicap"])
        self._start_ai_game(**values)

    def _create_host(self):
        defaults = {
            "size": get_setting("board_size"),
            "color": get_setting("human_color"),
            "komi": get_setting("komi"),
            "port": get_setting("port"),
        }
        dialog = HostGameDialog(self, defaults)
        if dialog.exec_() != QDialog.Accepted:
            return
        room, size, host_color, port, komi = dialog.values()
        set_value("board_size", size)
        set_value("human_color", host_color)
        set_value("port", port)
        self._start_host_session(room, size, host_color, port, komi)

    def _start_host_session(self, room, size, host_color, port, komi=7.5):
        self._stop_session()
        server = GameServer(
            room, size, host_color, "主机", port, komi, self
        )
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
        self._update_ui()
        self._refresh_status()

    def _on_client_joined(self, message):
        self.guest_joined = True
        name = message.get("name", "客机")
        self.chat.set_enabled(True)
        self.chat.add_system("{} 加入了房间".format(name))
        self._update_ui()
        self._refresh_status()

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
        else:
            self._refresh_status()

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
        if self.game.phase != Phase.PLAYING:
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

    def _refresh_status(self):
        if self.game.phase == Phase.PLAYING:
            if (
                self.mode == MODE_AI
                and self.game.turn == self.ai_color
            ):
                self.statusBar().showMessage("AI 思考中…")
            elif self._is_local_turn():
                self.statusBar().showMessage("轮到你落子")
            else:
                self.statusBar().showMessage("等待对手落子")
        elif self.game.phase == Phase.SCORING:
            if self._can_mark_dead():
                self.statusBar().showMessage("数子阶段：点击死子标记，确认后结束")
            else:
                self.statusBar().showMessage("等待主机确认数子")

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
            MODE_HOST: "主机", MODE_GUEST: "客机", MODE_REVIEW: "复盘",
        }
        self.stack.setCurrentWidget(
            self.welcome if self.mode == MODE_IDLE else self.board_widget
        )
        self.info_panel.setVisible(self.mode != MODE_IDLE)
        self.idle_hint.setVisible(self.mode == MODE_IDLE)
        self.mode_label.setText(mode_names.get(self.mode, "未开始"))
        self.board_label.setText(
            "—" if self.mode == MODE_IDLE else "{} 路".format(self.game.size)
        )
        self.komi_label.setText(
            "—" if self.mode == MODE_IDLE
            else "{:g}".format(self.game.komi)
        )
        if self.mode == MODE_REVIEW:
            self.turn_label.setText(
                "第 {} / {} 手".format(self.review_index, len(self.review_moves))
            )
        elif self.mode == MODE_IDLE:
            self.turn_label.setText("—")
        elif phase == Phase.PLAYING:
            if self.mode in (MODE_HOST, MODE_GUEST) and not self._is_connected():
                self.turn_label.setText("等待对手…")
            else:
                side = color_name(self.game.turn)
                if self.mode == MODE_AI:
                    role = "你" if self.game.turn == self.human_color else "AI"
                else:
                    role = "你" if self.game.turn == self.human_color else "对手"
                self.turn_label.setText("{}（{}方）".format(role, side))
        elif phase == Phase.SCORING:
            self.turn_label.setText("数子阶段")
        else:
            self.turn_label.setText("对局结束")
        captures = self.game.board.captures
        self.capture_label.setText(
            "黑 {} / 白 {}".format(captures[BLACK], captures[WHITE])
        )
        self.move_label.setText(str(self.game.move_count))
        if self.mode == MODE_HOST and self.server is not None:
            self.room_label.setText(
                "{} : {}".format(self.server.room_name, self.server.port)
            )
        elif self.mode == MODE_GUEST:
            self.room_label.setText("客机模式")
        elif self.mode == MODE_AI:
            self.room_label.setText("本地人机")
        elif self.mode == MODE_REVIEW:
            self.room_label.setText("棋谱文件")
        else:
            self.room_label.setText("—")
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
        self.save_button.setEnabled(bool(self.game.history) or bool(self.game.handicap))
        self.chat.set_enabled(self._chat_available())
        self.pass_action.setEnabled(interactive)
        self.resign_action.setEnabled(self._can_resign())
        self.undo_action.setEnabled(self._can_undo())
        self.confirm_action.setEnabled(marking)
        reviewing = self.mode == MODE_REVIEW
        self.prev_action.setEnabled(reviewing and self.review_index > 0)
        self.next_action.setEnabled(
            reviewing and self.review_index < len(self.review_moves)
        )
        self.first_action.setEnabled(reviewing and self.review_index > 0)
        self.last_action.setEnabled(
            reviewing and self.review_index < len(self.review_moves)
        )

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
            else:
                self._refresh_status()

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
        self._refresh_status()

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
        self.statusBar().showMessage("对局结束")
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
            self._start_ai_game(**self.last_ai_config)

    def _show_error(self, text):
        self.statusBar().showMessage(str(text), 5000)

    def _show_help(self, page_id="quickstart"):
        dialog = HelpDialog(page_id, self)
        dialog.exec_()

    def _show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.statusBar().showMessage("设置已保存", 3000)

    # ---------- SGF 存取与复盘 ----------

    def _default_dir(self):
        directory = str(get_setting("last_dir") or "")
        if directory and os.path.isdir(directory):
            return directory
        return os.path.expanduser("~")

    def _open_sgf(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "打开棋谱", self._default_dir(),
            "SGF 棋谱 (*.sgf);;所有文件 (*)",
        )
        if not path:
            return
        self._open_sgf_path(path)

    def _open_sgf_path(self, path):
        try:
            game = sgf.load_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "无法打开棋谱", str(exc))
            return
        self._stop_session()
        self.mode = MODE_REVIEW
        self.review_game = game
        self.review_moves = list(game.history)
        self.review_index = len(self.review_moves)
        self.review_path = path
        self.result_shown = True
        set_value("last_dir", os.path.dirname(path))
        self._apply_review()
        self._refresh_recent()
        self.statusBar().showMessage(
            "复盘：{}（共 {} 手，← → 逐步查看）".format(
                os.path.basename(path), len(self.review_moves)
            ),
            6000,
        )

    def _refresh_recent(self, limit=5):
        """扫描上次目录里的 SGF，作为欢迎页的"最近棋谱"。"""
        directory = self._default_dir()
        entries = []
        try:
            for name in os.listdir(directory):
                if not name.lower().endswith(".sgf"):
                    continue
                full = os.path.join(directory, name)
                if os.path.isfile(full):
                    entries.append((os.path.getmtime(full), full))
        except OSError:
            entries = []
        entries.sort(reverse=True)
        self.welcome.set_recent([path for _mtime, path in entries[:limit]])

    def _save_sgf(self):
        if not self.game.history and not self.game.handicap:
            QMessageBox.information(self, "保存棋谱", "当前没有可保存的对局。")
            return
        default_name = os.path.join(
            self._default_dir(),
            "围棋-{}.sgf".format(datetime.now().strftime("%Y%m%d-%H%M")),
        )
        path, _filter = QFileDialog.getSaveFileName(
            self, "保存棋谱", default_name, "SGF 棋谱 (*.sgf)"
        )
        if not path:
            return
        if not path.lower().endswith(".sgf"):
            path += ".sgf"
        try:
            sgf.save_file(path, self.game)
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        set_value("last_dir", os.path.dirname(path))
        self._refresh_recent()
        self.statusBar().showMessage("已保存：{}".format(path), 5000)

    def _apply_review(self):
        game = GameState(
            self.review_game.size, self.review_game.komi, BLACK,
            self.review_game.handicap,
        )
        for color, x, y in self.review_moves[: self.review_index]:
            # 复盘时按棋谱里的颜色走，允许跨过中途的停一手/数子状态
            if game.phase != Phase.PLAYING:
                game.phase = Phase.PLAYING
            game.turn = color
            if x is None:
                game.pass_turn()
                continue
            ok, _err = game.play(x, y)
            if not ok:
                break
        self.game = game
        self._update_ui()

    def _review_step(self, delta):
        if self.mode != MODE_REVIEW:
            return
        self._review_goto(self.review_index + delta)

    def _review_goto(self, index):
        if self.mode != MODE_REVIEW:
            return
        index = max(0, min(len(self.review_moves), int(index)))
        if index == self.review_index:
            return
        self.review_index = index
        self._apply_review()
        self.statusBar().showMessage(
            "复盘：第 {} / {} 手".format(self.review_index, len(self.review_moves))
        )

    def _show_about(self):
        QMessageBox.information(
            self, "关于",
            "围棋\n桌面围棋软件，支持人机对战与局域网对战。\n"
            "PyQt5 / Python 3.7",
        )

    def closeEvent(self, event):
        set_value("geometry", self.saveGeometry())
        self._stop_session()
        super().closeEvent(event)
