from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout,
    QWidget,
)

from ..core.board import BLACK, WHITE, Board
from . import theme
from .help_content import HELP_PAGES

HIGHLIGHT_COLORS = {
    "green": QColor(46, 160, 67, 115),
    "blue": QColor(47, 111, 176, 115),
    "red": QColor(178, 58, 58, 115),
    "orange": QColor(214, 137, 32, 115),
    "gray": QColor(120, 120, 120, 115),
}

MARK_COLORS = {
    "green": QColor("#2E8B57"),
    "blue": QColor("#2F6FB0"),
    "red": QColor("#B23A3A"),
    "orange": QColor("#B06B16"),
    "black": QColor("#222222"),
    "white": QColor("#FFFFFF"),
}


class DiagramWidget(QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.size = int(data.get("size", 9))
        self.setFixedSize(300, 300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _in_bounds(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def _metrics(self):
        side = min(self.width(), self.height())
        margin = max(18.0, side * 0.09)
        cell = (side - 2.0 * margin) / max(1, self.size - 1)
        left = (self.width() - side) / 2.0 + margin
        top = (self.height() - side) / 2.0 + margin
        return left, top, cell, side

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        left, top, cell, _side = self._metrics()
        pad = cell * 0.55
        board_rect = QRectF(
            left - pad, top - pad,
            (self.size - 1) * cell + 2 * pad,
            (self.size - 1) * cell + 2 * pad,
        )
        gradient = QLinearGradient(
            board_rect.topLeft(), board_rect.bottomRight()
        )
        gradient.setColorAt(0.0, theme.BOARD_LIGHT)
        gradient.setColorAt(1.0, theme.BOARD_DARK)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(board_rect, cell * 0.22, cell * 0.22)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(90, 60, 25, 130), 1.0))
        painter.drawRoundedRect(board_rect, cell * 0.22, cell * 0.22)

        grid_pen = QPen(theme.GRID)
        grid_pen.setWidthF(max(0.9, cell * 0.03))
        painter.setPen(grid_pen)
        for index in range(self.size):
            px = left + index * cell
            py = top + index * cell
            painter.drawLine(
                QPointF(px, top),
                QPointF(px, top + (self.size - 1) * cell),
            )
            painter.drawLine(
                QPointF(left, py),
                QPointF(left + (self.size - 1) * cell, py),
            )

        try:
            stars = Board(self.size).star_points()
        except ValueError:
            stars = []
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(theme.GRID))
        for sx, sy in stars:
            painter.drawEllipse(
                QPointF(left + sx * cell, top + sy * cell),
                cell * 0.08, cell * 0.08,
            )

        for x, y, color_name in self.data.get("highlights", []):
            if not self._in_bounds(x, y):
                continue
            color = HIGHLIGHT_COLORS.get(color_name)
            if color is None:
                continue
            cx = left + x * cell
            cy = top + y * cell
            painter.setPen(QPen(color, max(1.2, cell * 0.04)))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(cx, cy), cell * 0.30, cell * 0.30)

        for x, y, color in self.data.get("stones", []):
            if not self._in_bounds(x, y) or color not in (BLACK, WHITE):
                continue
            self._draw_stone(
                painter, left + x * cell, top + y * cell, cell, color
            )

        for x, y, text, color_name in self.data.get("marks", []):
            if not self._in_bounds(x, y):
                continue
            self._draw_mark(
                painter, left + x * cell, top + y * cell, cell,
                text, color_name,
            )
        painter.end()

    def _draw_stone(self, painter, cx, cy, cell, color):
        radius = cell * 0.45
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 50)))
        painter.drawEllipse(
            QPointF(cx + cell * 0.035, cy + cell * 0.045),
            radius, radius,
        )
        gradient = QRadialGradient(
            QPointF(cx - radius * 0.35, cy - radius * 0.35), radius * 1.4
        )
        if color == BLACK:
            gradient.setColorAt(0.0, QColor("#777777"))
            gradient.setColorAt(0.45, QColor("#2A2A2A"))
            gradient.setColorAt(1.0, QColor("#050505"))
            border = QColor(0, 0, 0, 120)
        else:
            gradient.setColorAt(0.0, QColor("#FFFFFF"))
            gradient.setColorAt(0.65, QColor("#F1F1EC"))
            gradient.setColorAt(1.0, QColor("#C9C9C2"))
            border = QColor(90, 80, 60, 120)
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(border, 0.9))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

    def _draw_mark(self, painter, cx, cy, cell, text, color_name):
        if text in ("×", "x", "X"):
            color = MARK_COLORS.get(color_name, MARK_COLORS["red"])
            painter.setPen(QPen(color, max(1.6, cell * 0.06)))
            offset = cell * 0.22
            painter.drawLine(
                QPointF(cx - offset, cy - offset),
                QPointF(cx + offset, cy + offset),
            )
            painter.drawLine(
                QPointF(cx - offset, cy + offset),
                QPointF(cx + offset, cy - offset),
            )
            return
        color = MARK_COLORS.get(color_name, MARK_COLORS["red"])
        radius = cell * 0.22
        painter.setPen(QPen(color, max(1.2, cell * 0.035)))
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        font = QFont()
        font.setPointSizeF(max(7.0, cell * 0.30))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(color))
        painter.drawText(
            QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
            Qt.AlignCenter,
            text,
        )


class HelpPage(QWidget):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #FFFFFF;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 28)
        layout.setSpacing(12)
        title = QLabel(page["title"])
        title_font = QFont("", 15, QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #8D5F24;")
        layout.addWidget(title)
        body = QLabel(page["html"])
        body.setTextFormat(Qt.RichText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setOpenExternalLinks(False)
        body_font = QFont("", 11)
        body.setFont(body_font)
        body.setStyleSheet("color: #2B2B2B;")
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(body)
        for diagram in page.get("diagrams", []):
            widget = DiagramWidget(diagram)
            layout.addWidget(widget, 0, Qt.AlignHCenter)
            caption = QLabel(diagram.get("caption", ""))
            caption.setWordWrap(True)
            caption.setAlignment(Qt.AlignCenter)
            caption.setFont(QFont("", 9))
            caption.setStyleSheet("color: #7A6A52;")
            layout.addWidget(caption)
        layout.addStretch(1)


class HelpDialog(QDialog):
    def __init__(self, initial_page="quickstart", parent=None):
        super().__init__(parent)
        self.setWindowTitle("新手帮助")
        self.resize(960, 700)
        self.setMinimumSize(780, 560)
        self.setSizeGripEnabled(True)
        self.pages = HELP_PAGES
        self._build_ui()
        self.go_to_page(initial_page)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(8)
        header = QLabel("围棋新手帮助")
        header.setFont(QFont("", 17, QFont.Bold))
        header.setStyleSheet("color: #5D3F18;")
        subtitle = QLabel(
            "从零开始：先看“快速开始”，再按章节了解规则和操作。"
        )
        subtitle.setFont(QFont("", 10))
        subtitle.setStyleSheet("color: #7A6A52;")
        outer.addWidget(header)
        outer.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(190)
        self.sidebar.setFrameShape(QFrame.NoFrame)
        self.sidebar.setStyleSheet(
            "QListWidget { background: #FBF7EF; border: 1px solid #E2D7C3;"
            " border-radius: 6px; padding: 6px; }"
            "QListWidget::item { padding: 9px 8px; border-radius: 4px; }"
            "QListWidget::item:selected { background: #E6BE75;"
            " color: #2B2B2B; }"
        )
        for index, page in enumerate(self.pages):
            item = QListWidgetItem(
                "{}. {}".format(index + 1, page["title"])
            )
            self.sidebar.addItem(item)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: #FFFFFF;")
        self.scrolls = []
        for page in self.pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(HelpPage(page))
            scroll.setStyleSheet("QScrollArea { background: #FFFFFF; }")
            self.stack.addWidget(scroll)
            self.scrolls.append(scroll)
        self.sidebar.currentRowChanged.connect(self._on_row_changed)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        bottom = QHBoxLayout()
        self.page_label = QLabel("")
        self.page_label.setStyleSheet("color: #7A6A52;")
        self.prev_button = QPushButton("上一节")
        self.next_button = QPushButton("下一节")
        self.close_button = QPushButton("关闭")
        self.prev_button.clicked.connect(self._previous)
        self.next_button.clicked.connect(self._next)
        self.close_button.clicked.connect(self.accept)
        bottom.addWidget(self.page_label)
        bottom.addStretch(1)
        bottom.addWidget(self.prev_button)
        bottom.addWidget(self.next_button)
        bottom.addWidget(self.close_button)
        outer.addLayout(bottom)

    def go_to_page(self, page_id):
        for index, page in enumerate(self.pages):
            if page["id"] == page_id:
                self.sidebar.setCurrentRow(index)
                return
        if self.pages:
            self.sidebar.setCurrentRow(0)

    def _on_row_changed(self, row):
        if row < 0 or row >= len(self.pages):
            return
        self.stack.setCurrentIndex(row)
        self.page_label.setText(
            "第 {} / {} 节".format(row + 1, len(self.pages))
        )
        self.prev_button.setEnabled(row > 0)
        self.next_button.setEnabled(row < len(self.pages) - 1)
        self.scrolls[row].verticalScrollBar().setValue(0)

    def _previous(self):
        row = self.sidebar.currentRow()
        if row > 0:
            self.sidebar.setCurrentRow(row - 1)

    def _next(self):
        row = self.sidebar.currentRow()
        if row < len(self.pages) - 1:
            self.sidebar.setCurrentRow(row + 1)
