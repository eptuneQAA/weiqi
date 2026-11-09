"""AI 基准：固定局面下统计单位时间的 playout 数，用于对比优化前后。

用法：python3 tools/bench_ai.py [难度] [棋盘] [秒数]
"""

import sys
import time

sys.path.insert(0, ".")

from weiqi.ai.engine import AIEngine
from weiqi.core.board import BLACK
from weiqi.core.game import GameState


def build_position(size=19):
    """摆一个中盘局面：双方各十几个子，避免开局/终局特例。"""
    game = GameState(size, 7.5, BLACK)
    points = []
    step = size // 4
    for i in range(4):
        for j in range(4):
            points.append((2 + i * step + (j % 2), 2 + j * step))
    for x, y in points:
        ok, _err = game.play(x, y)
        if not ok:
            continue
    return game


def main():
    difficulty = sys.argv[1] if len(sys.argv) > 1 else "普通"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 19
    seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

    game = build_position(size)
    engine = AIEngine(difficulty, seed=1234)
    engine.config = dict(engine.config)
    engine.config["time"] = seconds

    counter = {"n": 0}
    original = engine._playout_value

    def counting(*args, **kwargs):
        counter["n"] += 1
        return original(*args, **kwargs)

    engine._playout_value = counting

    started = time.monotonic()
    move = engine.choose_move(game)
    elapsed = time.monotonic() - started
    playouts = counter["n"]
    print(
        "{}: playout={} 用时={:.2f}s 速度={:.0f} playout/s 选点={}".format(
            difficulty, playouts, elapsed, playouts / max(elapsed, 1e-6), move
        )
    )


if __name__ == "__main__":
    main()
