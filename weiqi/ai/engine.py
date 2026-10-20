"""内置围棋 AI：战术启发式 + 时间受限蒙特卡洛搜索。"""

import math
import random
import time

from ..core.board import BLACK, EMPTY, WHITE, opponent
from ..core.game import Phase
from ..core.scoring import compute_ownership

DIFFICULTY = {
    "入门": {"time": 0.3, "top": 5, "playout": 0},
    "普通": {"time": 1.0, "top": 10, "playout": 40},
    "较强": {"time": 2.5, "top": 14, "playout": 60},
}


class AIEngine:
    def __init__(self, difficulty="普通", seed=None):
        if difficulty not in DIFFICULTY:
            raise ValueError("未知难度：" + str(difficulty))
        self.difficulty = difficulty
        self.config = DIFFICULTY[difficulty]
        self.random = random.Random(seed)

    def choose_move(self, game, cancel_check=None):
        if game.phase != Phase.PLAYING:
            return None
        if cancel_check is not None and cancel_check():
            return None
        color = game.turn
        moves = self._candidates(game, color)
        if not moves:
            return None
        ranked = self._rank_moves(game, moves, color)
        if not ranked:
            return None
        if self.config["playout"] <= 0:
            best_score = ranked[0][1]
            pool = [move for move, score in ranked if best_score - score <= 1.5]
            return self.random.choice(pool or [ranked[0][0]])
        return self._monte_carlo(game, ranked, color, cancel_check)

    def _candidates(self, game, color):
        board = game.board
        size = board.size
        stones = [
            (x, y)
            for y in range(size)
            for x in range(size)
            if board.grid[y][x] != EMPTY
        ]
        candidates = set()
        if not stones:
            candidates.update(board.star_points())
        else:
            for sx, sy in stones:
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        x, y = sx + dx, sy + dy
                        if board.in_bounds(x, y) and board.grid[y][x] == EMPTY:
                            candidates.add((x, y))
        if len(stones) < 6:
            candidates.update(board.star_points())
        result = []
        for x, y in candidates:
            ok, _ = game.is_legal(x, y, color)
            if ok and not self._is_own_eye(board, x, y, color):
                result.append((x, y))
        self.random.shuffle(result)
        return result

    def _is_own_eye(self, board, x, y, color):
        for nx, ny in board.neighbors(x, y):
            if board.grid[ny][nx] != color:
                return False
        bad_diagonals = 0
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if board.in_bounds(nx, ny) and board.grid[ny][nx] != color:
                bad_diagonals += 1
        return bad_diagonals <= 1

    def _rank_moves(self, game, moves, color):
        ranked = []
        for x, y in moves:
            ranked.append(((x, y), self._heuristic(game, x, y, color)))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[: max(1, self.config["top"])]

    def _heuristic(self, game, x, y, color):
        board = game.board
        trial = board.copy()
        ok, _ = trial.play(x, y, color)
        if not ok:
            return -9999.0
        captured = trial.captures[color] - board.captures[color]
        own_stones, own_liberties = trial.group_and_liberties(x, y)
        score = captured * 120.0 + min(len(own_liberties), 5) * 6.0
        score += len(own_stones) * 0.4
        for nx, ny in trial.neighbors(x, y):
            if trial.grid[ny][nx] == color:
                score += 1.5
            elif trial.grid[ny][nx] == opponent(color):
                stones, liberties = trial.group_and_liberties(nx, ny)
                if len(liberties) == 1:
                    score += 8.0
                elif len(liberties) == 2:
                    score += 2.0
                score += min(len(stones), 4) * 0.3
        last = game.last_move
        if last is not None:
            distance = max(abs(last[0] - x), abs(last[1] - y))
            score += max(0.0, 4.0 - distance)
        if (
            x == 0 or y == 0
            or x == board.size - 1 or y == board.size - 1
        ):
            if game.move_count < board.size * 2:
                score -= 6.0
        score += self.random.random() * 0.5
        return score

    def _monte_carlo(self, game, ranked, color, cancel_check):
        deadline = time.monotonic() + self.config["time"]
        stats = {move: [0, 0.0] for move, _score in ranked}
        total = 0
        while time.monotonic() < deadline:
            if cancel_check is not None and cancel_check():
                return None
            move = self._select(stats, total)
            stats[move][0] += 1
            total += 1
            reward = self._playout_value(
                game, move, color, deadline, cancel_check
            )
            if reward is None:
                return None
            stats[move][1] += reward
        if total == 0:
            return ranked[0][0]
        return max(
            stats,
            key=lambda move: (
                stats[move][0],
                stats[move][1] / max(stats[move][0], 1),
            ),
        )

    def _select(self, stats, total):
        untried = [
            move for move, value in stats.items() if value[0] == 0
        ]
        if untried:
            return self.random.choice(untried)
        log_total = math.log(max(total, 2))
        best_move = None
        best_value = -1.0
        for move, (visits, wins) in stats.items():
            value = wins / visits + 0.8 * math.sqrt(log_total / visits)
            if value > best_value:
                best_value = value
                best_move = move
        return best_move

    def _playout_value(self, game, move, color, deadline, cancel_check):
        board = game.board.copy()
        ok, _ = board.play(move[0], move[1], color)
        if not ok:
            return 0.0
        turn = opponent(color)
        passes = 0
        max_moves = 120 if board.size <= 9 else 80
        for _ in range(max_moves):
            if time.monotonic() >= deadline:
                break
            if cancel_check is not None and cancel_check():
                return None
            options = self._local_empty_points(board)
            if not options:
                passes += 1
                if passes >= 2:
                    break
                turn = opponent(turn)
                continue
            self.random.shuffle(options)
            played = False
            for x, y in options[:20]:
                if self._is_own_eye(board, x, y, turn):
                    continue
                moved, _ = board.play(x, y, turn)
                if moved:
                    played = True
                    passes = 0
                    turn = opponent(turn)
                    break
            if not played:
                passes += 1
                if passes >= 2:
                    break
                turn = opponent(turn)
        owner = compute_ownership(board, set())
        my_area = 0
        other_area = 0
        for y in range(board.size):
            for x in range(board.size):
                value = owner[y][x]
                if value == color:
                    my_area += 1
                elif value == opponent(color):
                    other_area += 1
        threshold = other_area + (game.komi if color == BLACK else 0.0)
        return 1.0 if my_area > threshold else 0.0

    def _local_empty_points(self, board):
        radius = 2
        points = []
        for y in range(board.size):
            for x in range(board.size):
                if board.grid[y][x] != EMPTY:
                    continue
                near = False
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        nx, ny = x + dx, y + dy
                        if (
                            board.in_bounds(nx, ny)
                            and board.grid[ny][nx] != EMPTY
                        ):
                            near = True
                            break
                    if near:
                        break
                if near:
                    points.append((x, y))
        return points
