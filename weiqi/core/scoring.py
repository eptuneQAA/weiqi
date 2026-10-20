from .board import BLACK, EMPTY, WHITE, opponent


def _cleaned_grid(board, dead_points):
    grid = [row[:] for row in board.grid]
    for x, y in dead_points:
        if board.in_bounds(x, y) and grid[y][x] != EMPTY:
            grid[y][x] = EMPTY
    return grid


def compute_ownership(board, dead_points):
    grid = _cleaned_grid(board, dead_points)
    size = board.size
    owner = [[EMPTY for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            if grid[y][x] != EMPTY:
                owner[y][x] = grid[y][x]
    visited = [[False for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            if grid[y][x] != EMPTY or visited[y][x]:
                continue
            stack = [(x, y)]
            region = []
            borders = set()
            visited[y][x] = True
            while stack:
                cx, cy = stack.pop()
                region.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if not board.in_bounds(nx, ny):
                        continue
                    value = grid[ny][nx]
                    if value == EMPTY:
                        if not visited[ny][nx]:
                            visited[ny][nx] = True
                            stack.append((nx, ny))
                    else:
                        borders.add(value)
            if borders == {BLACK}:
                for rx, ry in region:
                    owner[ry][rx] = BLACK
            elif borders == {WHITE}:
                for rx, ry in region:
                    owner[ry][rx] = WHITE
    return owner


def compute_score(board, dead_points, komi):
    grid = _cleaned_grid(board, dead_points)
    owner = compute_ownership(board, dead_points)
    black_stones = white_stones = 0
    black_territory = white_territory = 0
    for y in range(board.size):
        for x in range(board.size):
            value = grid[y][x]
            if value == BLACK:
                black_stones += 1
            elif value == WHITE:
                white_stones += 1
            elif owner[y][x] == BLACK:
                black_territory += 1
            elif owner[y][x] == WHITE:
                white_territory += 1
    black_area = black_stones + black_territory
    white_area = white_stones + white_territory
    black_total = float(black_area)
    white_total = float(white_area) + float(komi)
    difference = black_total - white_total
    if abs(difference) < 1e-9:
        winner = "draw"
        margin = 0.0
    elif difference > 0:
        winner = "black"
        margin = difference
    else:
        winner = "white"
        margin = -difference
    return {
        "black_stones": black_stones,
        "white_stones": white_stones,
        "black_territory": black_territory,
        "white_territory": white_territory,
        "black_area": black_area,
        "white_area": white_area,
        "komi": float(komi),
        "black_total": black_total,
        "white_total": white_total,
        "winner": winner,
        "margin": margin,
        "dead_count": len(dead_points),
    }


def auto_dead_groups(board):
    original_owner = compute_ownership(board, set())
    dead = set()
    visited = set()
    for y in range(board.size):
        for x in range(board.size):
            color = board.grid[y][x]
            if color == EMPTY or (x, y) in visited:
                continue
            stones, liberties = board.group_and_liberties(x, y)
            visited |= stones
            if len(stones) > 3:
                continue
            has_eye = any(
                original_owner[ly][lx] == color for lx, ly in liberties
            )
            owner_without = compute_ownership(board, stones)
            all_opponent = bool(liberties) and all(
                owner_without[ly][lx] == opponent(color)
                for lx, ly in liberties
            )
            if not has_eye and all_opponent:
                dead |= stones
    return dead


def toggle_group_dead(board, dead_points, x, y):
    if not board.in_bounds(x, y) or board.get(x, y) == EMPTY:
        return set(dead_points)
    stones, _ = board.group_and_liberties(x, y)
    if stones <= dead_points:
        return set(dead_points) - stones
    return set(dead_points) | stones


def score_text(score):
    if score is None:
        return "对局结束"
    if score["winner"] == "draw":
        return "和棋"
    side = "黑" if score["winner"] == "black" else "白"
    return "{}胜 {:.1f} 点".format(side, score["margin"])
