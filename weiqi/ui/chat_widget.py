from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
    QWidget,
)

from ..net.protocol import MAX_CHAT_LENGTH
from . import theme


class ChatWidget(QWidget):
    message_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        title = QLabel("聊天")
        title.setFont(QFont("", 10, QFont.Bold))
        self.messages = QTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setAcceptRichText(False)
        self.messages.setMinimumHeight(150)
        self.messages.setStyleSheet(
            "QTextEdit { background: #FFFDF8; border: 1px solid #D8CBB4;"
            " border-radius: 4px; }"
        )
        self.input = QLineEdit()
        self.input.setMaxLength(MAX_CHAT_LENGTH)
        self.input.setPlaceholderText("输入消息…")
        self.input.returnPressed.connect(self._send)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self._send)
        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(self.send_button)
        layout.addWidget(title)
        layout.addWidget(self.messages, 1)
        layout.addLayout(row)
        self.set_enabled(False)

    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.message_sent.emit(text)

    def add_message(self, name, text, time_text, is_self=False):
        cursor = QTextCursor(self.messages.document())
        cursor.movePosition(QTextCursor.End)
        header = QTextCharFormat()
        header.setFontWeight(QFont.Bold)
        header.setForeground(
            QColor(theme.CHAT_SELF if is_self else theme.CHAT_OTHER)
        )
        cursor.insertText("{}  {}\n".format(name, time_text), header)
        body = QTextCharFormat()
        body.setForeground(QColor("#2B2B2B"))
        cursor.insertText(text + "\n", body)
        self.messages.setTextCursor(cursor)
        self.messages.ensureCursorVisible()

    def add_system(self, text):
        cursor = QTextCursor(self.messages.document())
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(theme.SYSTEM))
        fmt.setFontItalic(True)
        cursor.insertText("— {} —\n".format(text), fmt)
        self.messages.setTextCursor(cursor)
        self.messages.ensureCursorVisible()

    def set_enabled(self, enabled):
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if enabled:
            self.input.setPlaceholderText("输入消息…")
        else:
            self.input.setPlaceholderText("连接后可聊天")

    def clear(self):
        self.messages.clear()
        self.input.clear()
