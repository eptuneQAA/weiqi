from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient,
)
from PyQt5.QtWidgets import QSizePolicy, QWidget

from ..core.board import BLACK, EMPTY
from . import theme

LETTERS = "ABCDEFGHJKLMNOPQRST"


class BoardWidget(QWidget):
    point_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = None
        self.size = 19
        self.last_move = None
        self.interactive = False
        self.marking = False
        self.dead_points = set()
        self.hover = None
        self.hover_color = BLACK
        self.setMinimumSize(460, 460)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(
        self, board, last_move=None, interactive=False, marking=False,
        dead_points=None, hover_color=BLACK,
    ):
        self.board = board
        self.size = board.size
        self.last_move = last_move
        self.interactive = interactive
        self.marking = marking
        self.dead_points = set(dead_points or set())
        self.hover_color = hover_color
        self.hover = None
        self.update()

    def _metrics(self):
        side = min(self.width(), self.height())
        margin = max(22.0, side * (1.55 / (self.size + 2.0)))
        length = max(1.0, side - 2.0 * margin)
        cell = length / max(1, self.size - 1)
        left = (self.width() - side) / 2.0 + margin
        top = (self.height() - side) / 2.0 + margin
        return left, top, cell, side

    def _pixel_to_point(self, pos):
        left, top, cell, _side = self._metrics()
        x = int(round((pos.x() - left) / cell))
        y = int(round((pos.y() - top) / cell))
        if not (0 <= x < self.size and 0 <= y < self.size):
            return None
        cx = left + x * cell
        cy = top + y * cell
        if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= (cell * 0.48) ** 2:
            return x, y
        return None

    def paintEvent(self, _event):
        if self.board is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), theme.BACKGROUND)
        left, top, cell, _side = self._metrics()
        pad = cell * 0.75
        board_rect = QRectF(
            left - pad, top - pad,
            (self.size - 1) * cell + 2 * pad,
            (self.size - 1) * cell + 2 * pad,
        )
        gradient = QLinearGradient(board_rect.topLeft(), board_rect.bottomRight())
        gradient.setColorAt(0.0, theme.BOARD_LIGHT)
        gradient.setColorAt(1.0, theme.BOARD_DARK)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(board_rect, cell * 0.25, cell * 0.25)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(90, 60, 25, 120), 1.2))
        painter.drawRoundedRect(board_rect, cell * 0.25, cell * 0.25)

        grid_pen = QPen(theme.GRID)
        grid_pen.setWidthF(max(1.0, cell * 0.035))
        painter.setPen(grid_pen)
        for index in range(self.size):
            px = left + index * cell
            py = top + index * cell
            painter.drawLine(
                QPointF(px, top), QPointF(px, top + (self.size - 1) * cell)
            )
            painter.drawLine(
                QPointF(left, py), QPointF(left + (self.size - 1) * cell, py)
            )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(theme.GRID))
        for sx, sy in self.board.star_points():
            painter.drawEllipse(
                QPointF(left + sx * cell, top + sy * cell),
                cell * 0.10, cell * 0.10,
            )

        font = QFont()
        font.setPointSizeF(max(7.0, cell * 0.30))
        painter.setFont(font)
        painter.setPen(QPen(theme.COORD))
        for index in range(self.size):
            px = left + index * cell
            painter.drawText(
                QRectF(px - cell / 2, top - cell * 1.35, cell, cell * 0.9),
                Qt.AlignCenter, LETTERS[index],
            )
            painter.drawText(
                QRectF(
                    left - cell * 1.55,
                    top + index * cell - cell / 2,
                    cell, cell,
                ),
                Qt.AlignCenter, str(index + 1),
            )

        for y in range(self.size):
            for x in range(self.size):
                color = self.board.grid[y][x]
                if color != EMPTY:
                    self._draw_stone(
                        painter, left + x * cell, top + y * cell,
                        cell, color, x, y,
                    )

        if self.last_move is not None:
            lx, ly = self.last_move
            if 0 <= lx < self.size and 0 <= ly < self.size:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(theme.ACCENT))
                painter.drawEllipse(
                    QPointF(left + lx * cell, top + ly * cell),
                    cell * 0.11, cell * 0.11,
                )

        if self.interactive and self.hover is not None:
            hx, hy = self.hover
            if self.board.grid[hy][hx] == EMPTY:
                painter.setPen(Qt.NoPen)
                color = QColor(
                    theme.BLACK_STONE
                    if self.hover_color == BLACK else theme.WHITE_STONE
                )
                color.setAlpha(95)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(
                    QPointF(left + hx * cell, top + hy * cell),
                    cell * 0.44, cell * 0.44,
                )

    def _draw_stone(self, painter, cx, cy, cell, color, x, y):
        radius = cell * 0.46
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 55)))
        painter.drawEllipse(
            QPointF(cx + cell * 0.04, cy + cell * 0.05), radius, radius
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
        painter.setPen(QPen(border, 1.0))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        if (x, y) in self.dead_points:
            painter.setPen(QPen(theme.ACCENT, max(1.5, cell * 0.06)))
            offset = radius * 0.55
            painter.drawLine(
                QPointF(cx - offset, cy - offset),
                QPointF(cx + offset, cy + offset),
            )
            painter.drawLine(
                QPointF(cx - offset, cy + offset),
                QPointF(cx + offset, cy - offset),
            )

    def mouseMoveEvent(self, event):
        if not (self.interactive or self.marking):
            if self.hover is not None:
                self.hover = None
                self.update()
            return
        point = self._pixel_to_point(event.pos())
        if point != self.hover:
            self.hover = point
            self.update()

    def leaveEvent(self, _event):
        if self.hover is not None:
            self.hover = None
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        point = self._pixel_to_point(event.pos())
        if point is not None:
            self.point_clicked.emit(point[0], point[1])
