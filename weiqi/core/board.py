"""棋盘基础规则：落子、提子、气、禁入点。"""

EMPTY = 0
BLACK = 1
WHITE = 2

STAR_POINTS = {
    9: (2, 4, 6),
    13: (3, 6, 9),
    19: (3, 9, 15),
}


def opponent(color):
    return WHITE if color == BLACK else BLACK


def color_name(color):
    return "黑" if color == BLACK else "白"


class Board:
    def __init__(self, size=19):
        if size not in STAR_POINTS:
            raise ValueError("棋盘大小只支持 9、13、19")
        self.size = size
        self.grid = [[EMPTY for _ in range(size)] for _ in range(size)]
        self.captures = {BLACK: 0, WHITE: 0}

    def copy(self):
        other = Board.__new__(Board)
        other.size = self.size
        other.grid = [row[:] for row in self.grid]
        other.captures = dict(self.captures)
        return other

    def in_bounds(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def get(self, x, y):
        return self.grid[y][x]

    def set(self, x, y, color):
        self.grid[y][x] = color

    def neighbors(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self.in_bounds(nx, ny):
                yield nx, ny

    def group_and_liberties(self, x, y):
        color = self.grid[y][x]
        if color == EMPTY:
            return set(), set()
        stones = set()
        liberties = set()
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in stones:
                continue
            stones.add((cx, cy))
            for nx, ny in self.neighbors(cx, cy):
                value = self.grid[ny][nx]
                if value == EMPTY:
                    liberties.add((nx, ny))
                elif value == color and (nx, ny) not in stones:
                    stack.append((nx, ny))
        return stones, liberties

    def play(self, x, y, color):
        if not self.in_bounds(x, y):
            return False, "落子超出棋盘"
        if self.grid[y][x] != EMPTY:
            return False, "该位置已有棋子"
        self.grid[y][x] = color
        captured_stones = []
        for nx, ny in self.neighbors(x, y):
            if self.grid[ny][nx] == opponent(color):
                stones, liberties = self.group_and_liberties(nx, ny)
                if not liberties:
                    for sx, sy in stones:
                        self.grid[sy][sx] = EMPTY
                    captured_stones.extend(stones)
        captured = len(captured_stones)
        self.captures[color] += captured
        _own_stones, own_liberties = self.group_and_liberties(x, y)
        if not own_liberties:
            # 回滚：恢复被提的子并拿掉刚落的子，避免整盘 grid 拷贝
            for sx, sy in captured_stones:
                self.grid[sy][sx] = opponent(color)
            self.grid[y][x] = EMPTY
            self.captures[color] -= captured
            return False, "禁止自杀"
        return True, ""

    def is_legal(self, x, y, color):
        if not self.in_bounds(x, y) or self.grid[y][x] != EMPTY:
            return False
        test = self.copy()
        ok, _ = test.play(x, y, color)
        return ok

    def position_key(self):
        # bytes 比 tuple-of-tuples 构造和哈希都快得多，且可直接进 set 判重
        return b"".join(bytes(row) for row in self.grid)

    def star_points(self):
        if self.size == 9:
            return [(2, 2), (2, 6), (4, 4), (6, 2), (6, 6)]
        if self.size == 13:
            return [(3, 3), (3, 9), (6, 6), (9, 3), (9, 9)]
        coords = STAR_POINTS[19]
        return [(x, y) for y in coords for x in coords]
