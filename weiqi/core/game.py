from enum import Enum

from .board import BLACK, EMPTY, WHITE, Board, opponent
from .scoring import auto_dead_groups, compute_score


class Phase(Enum):
    PLAYING = "playing"
    SCORING = "scoring"
    FINISHED = "finished"


# 让子固定位置，按标准顺序取前 N 个（(x, y)，0 起算）
HANDICAP_POINTS = {
    9: [(6, 2), (2, 6), (6, 6), (2, 2), (4, 2), (2, 4), (6, 4), (4, 6), (4, 4)],
    13: [(9, 3), (3, 9), (9, 9), (3, 3), (6, 3), (3, 6), (9, 6), (6, 9), (6, 6)],
    19: [
        (15, 3), (3, 15), (15, 15), (3, 3), (9, 3), (3, 9), (15, 9), (9, 15),
        (9, 9),
    ],
}


class GameState:
    def __init__(self, size=19, komi=7.5, first_color=BLACK, handicap=0):
        self.size = size
        self.komi = komi
        self.first_color = first_color
        self.board = Board(size)
        self.turn = first_color
        self.phase = Phase.PLAYING
        self.history = []
        self.positions = {self.board.position_key()}
        self.consecutive_passes = 0
        self.dead_points = set()
        self.score = None
        self.winner = None
        self.result_reason = ""
        self.resigned_by = None
        self.handicap = 0
        if handicap:
            self.setup_handicap(handicap)

    def setup_handicap(self, count):
        """摆放让子，并由白方先行（中国规则：让子棋白先）。"""
        points = HANDICAP_POINTS.get(self.size, [])
        count = max(0, min(int(count), len(points)))
        if count < 2:
            return 0
        for x, y in points[:count]:
            self.board.set(x, y, BLACK)
        self.handicap = count
        self.turn = WHITE
        self.first_color = WHITE
        self.positions = {self.board.position_key()}
        self.history = []
        return count

    @property
    def last_move(self):
        for _color, x, y in reversed(self.history):
            if x is not None:
                return (x, y)
        return None

    @property
    def move_count(self):
        return len(self.history)

    def is_legal(self, x, y, color=None):
        if self.phase != Phase.PLAYING:
            return False, "当前不能落子"
        color = self.turn if color is None else color
        if color != self.turn:
            return False, "还没轮到你"
        if not self.board.in_bounds(x, y):
            return False, "落子超出棋盘"
        if self.board.get(x, y) != EMPTY:
            return False, "该位置已有棋子"
        test = self.board.copy()
        ok, err = test.play(x, y, color)
        if not ok:
            return False, err
        if test.position_key() in self.positions:
            return False, "劫争：不能重复之前的局面"
        return True, ""

    def play(self, x, y):
        ok, err = self.is_legal(x, y)
        if not ok:
            return False, err
        test = self.board.copy()
        ok, err = test.play(x, y, self.turn)
        if not ok:
            return False, err
        self.board = test
        self.positions.add(test.position_key())
        self.history.append((self.turn, x, y))
        self.consecutive_passes = 0
        self.turn = opponent(self.turn)
        return True, ""

    def pass_turn(self):
        if self.phase != Phase.PLAYING:
            return False, "当前不能停一手"
        self.history.append((self.turn, None, None))
        self.consecutive_passes += 1
        if self.consecutive_passes >= 2:
            self.start_scoring()
        else:
            self.turn = opponent(self.turn)
        return True, ""

    def start_scoring(self):
        if self.phase != Phase.PLAYING:
            return
        self.phase = Phase.SCORING
        self.dead_points = auto_dead_groups(self.board)
        self.score = compute_score(self.board, self.dead_points, self.komi)

    def set_dead_points(self, points):
        if self.phase != Phase.SCORING:
            return False
        valid = set()
        for x, y in points:
            if self.board.in_bounds(x, y) and self.board.get(x, y) != EMPTY:
                valid.add((int(x), int(y)))
        self.dead_points = valid
        self.score = compute_score(self.board, self.dead_points, self.komi)
        return True

    def confirm_score(self):
        if self.phase != Phase.SCORING:
            return False
        if self.score is None:
            self.score = compute_score(self.board, self.dead_points, self.komi)
        self.phase = Phase.FINISHED
        self.winner = self.score["winner"]
        self.result_reason = "数子"
        return True

    def resign(self, color):
        if self.phase != Phase.PLAYING:
            return False
        self.phase = Phase.FINISHED
        self.winner = "white" if color == BLACK else "black"
        self.resigned_by = color
        self.result_reason = "认输"
        return True

    def undo(self, count=2):
        if self.phase != Phase.PLAYING:
            return False
        if count < 1 or count > len(self.history):
            return False
        records = self.history[:-count]
        fresh = GameState(self.size, self.komi, self.first_color)
        for _color, x, y in records:
            if x is None:
                fresh.pass_turn()
            else:
                ok, _ = fresh.play(x, y)
                if not ok:
                    return False
        self.board = fresh.board
        self.turn = fresh.turn
        self.phase = fresh.phase
        self.history = fresh.history
        self.positions = fresh.positions
        self.consecutive_passes = fresh.consecutive_passes
        self.dead_points = set()
        self.score = None
        self.winner = None
        self.result_reason = ""
        self.resigned_by = None
        return True

    def snapshot(self):
        moves = []
        for color, x, y in self.history:
            moves.append({"color": color, "x": x, "y": y})
        return {
            "size": self.size,
            "komi": self.komi,
            "first_color": self.first_color,
            "handicap": self.handicap,
            "turn": self.turn,
            "phase": self.phase.value,
            "moves": moves,
            "captures": {
                "black": self.board.captures[BLACK],
                "white": self.board.captures[WHITE],
            },
            "dead_points": [[x, y] for x, y in sorted(self.dead_points)],
            "score": self.score,
            "winner": self.winner,
            "reason": self.result_reason,
            "resigned_by": self.resigned_by,
        }

    @classmethod
    def from_snapshot(cls, data):
        game = cls(
            int(data["size"]), float(data["komi"]), int(data["first_color"]),
            int(data.get("handicap", 0) or 0),
        )
        for move in data.get("moves", []):
            if move.get("x") is None:
                game.pass_turn()
            else:
                ok, err = game.play(int(move["x"]), int(move["y"]))
                if not ok:
                    raise ValueError("无法恢复棋局：" + err)
        if (
            data.get("phase") in (Phase.SCORING.value, Phase.FINISHED.value)
            and game.phase == Phase.SCORING
        ):
            game.set_dead_points(data.get("dead_points", []))
        if data.get("phase") == Phase.FINISHED.value:
            if data.get("resigned_by") is not None:
                game.resign(int(data["resigned_by"]))
            else:
                game.confirm_score()
        return game
