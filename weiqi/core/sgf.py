"""SGF（FF[4]）读写：让对局可以保存、复盘、分享。

只处理主分支（第一个变体），足以覆盖本项目产生的棋谱与常见残局/让子谱。
坐标遵循 SGF 约定：a-z 依次对应第 1-n 路，**不跳过 i**。
"""

from datetime import datetime

from .board import BLACK, EMPTY, WHITE, Board
from .game import GameState, Phase

SGF_LETTERS = "abcdefghijklmnopqrstuvwxyz"

REASON_TEXT = {
    "resigned": "R",
    "scoring": "",
}


class SGFError(ValueError):
    """棋谱内容无法解析。"""


def _coord_to_sgf(x, y):
    return SGF_LETTERS[x] + SGF_LETTERS[y]


def _sgf_to_coord(value):
    if len(value) != 2:
        raise SGFError("坐标长度错误：{!r}".format(value))
    try:
        x = SGF_LETTERS.index(value[0])
        y = SGF_LETTERS.index(value[1])
    except ValueError:
        raise SGFError("坐标包含非法字符：{!r}".format(value))
    return x, y


def _escape(value):
    return value.replace("\\", "\\\\").replace("]", "\\]")


def _result_text(game):
    if game.phase != Phase.FINISHED or not game.winner:
        return ""
    if game.winner == "draw":
        return "0"
    side = "B" if game.winner == "black" else "W"
    if game.resigned_by is not None:
        return "{}+R".format(side)
    if game.score:
        return "{}+{:.1f}".format(side, game.score["margin"])
    return "{}+".format(side)


def dumps(game, black_name="黑", white_name="白", date=None, comment=""):
    """把 GameState 序列化成 SGF 文本。"""
    root = [
        "GM[1]",
        "FF[4]",
        "CA[UTF-8]",
        "AP[weiqi:1.1]",
        "SZ[{}]".format(game.size),
        "KM[{:g}]".format(game.komi),
        "PB[{}]".format(_escape(black_name)),
        "PW[{}]".format(_escape(white_name)),
        "DT[{}]".format(date or datetime.now().strftime("%Y-%m-%d")),
        "RU[Chinese]",
    ]
    result = _result_text(game)
    if result:
        root.append("RE[{}]".format(result))
    if game.handicap:
        from .game import HANDICAP_POINTS

        points = HANDICAP_POINTS.get(game.size, [])[: game.handicap]
        root.append("HA[{}]".format(game.handicap))
        root.append(
            "AB" + "".join("[{}]".format(_coord_to_sgf(x, y)) for x, y in points)
        )
    if game.first_color == WHITE and not game.handicap:
        root.append("PL[W]")
    parts = ["(;" + "".join(root)]
    for color, x, y in game.history:
        tag = "B" if color == BLACK else "W"
        if x is None:
            parts.append(";{}[]".format(tag))
        else:
            parts.append(";{}[{}]".format(tag, _coord_to_sgf(x, y)))
    if comment:
        parts.append("C[{}]".format(_escape(comment)))
    elif game.dead_points and game.phase != Phase.PLAYING:
        dead = " ".join(_coord_to_sgf(x, y) for x, y in sorted(game.dead_points))
        parts.append("C[死子：{}]".format(_escape(dead)))
    parts.append(")")
    return "".join(parts) + "\n"


def _skip_variation(text, index):
    """从 '(' 开始跳过一整个变体（含嵌套）。"""
    depth = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise SGFError("变体括号不匹配")


def _read_value(text, index):
    """读取 '[' 之后到匹配的 ']' 之间的值，处理转义。"""
    if index >= len(text) or text[index] != "[":
        raise SGFError("属性缺少 '['")
    index += 1
    buffer = []
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            if nxt == "\n":
                index += 2
                continue
            buffer.append(nxt)
            index += 2
            continue
        if char == "]":
            return "".join(buffer), index + 1
        buffer.append(char)
        index += 1
    raise SGFError("属性值未闭合")


def _parse_properties(text, index):
    props = {}
    while index < len(text):
        char = text[index]
        if char in " \t\r\n":
            index += 1
            continue
        if char in ";()":
            break
        if not (char.isalpha() and char.isupper()):
            raise SGFError("非法的属性名起始字符：{!r}".format(char))
        name = char
        index += 1
        while index < len(text) and text[index].isalpha() and text[index].isupper():
            name += text[index]
            index += 1
        values = []
        while index < len(text) and text[index] == "[":
            value, index = _read_value(text, index)
            values.append(value)
        props[name] = values
    return props, index


def _parse_nodes(text, index=0):
    """解析集合，返回主分支节点列表。

    SGF 约定第一个变体就是主分支，所以遇到 '(' 时把第一个变体并入主分支，
    其余变体整体跳过。
    """
    while index < len(text) and text[index] != "(":
        if text[index] in " \t\r\n":
            index += 1
            continue
        raise SGFError("棋谱必须以 '(' 开头")
    if index >= len(text):
        raise SGFError("棋谱为空")
    index += 1
    nodes = []
    seen_node = False
    took_variation = False
    while index < len(text):
        char = text[index]
        if char in " \t\r\n":
            index += 1
            continue
        if char == ";":
            props, index = _parse_properties(text, index + 1)
            nodes.append(props)
            seen_node = True
            continue
        if char == "(":
            if not seen_node:
                raise SGFError("棋谱缺少根节点")
            if took_variation:
                index = _skip_variation(text, index)
                continue
            nested, index = _parse_nodes(text, index)
            nodes.extend(nested)
            took_variation = True
            continue
        if char == ")":
            return nodes, index + 1
        raise SGFError("无法识别的字符：{!r}".format(char))
    raise SGFError("棋谱括号未闭合")


def _first(node, name, default=""):
    values = node.get(name) or []
    return values[0] if values else default


def loads(text):
    """把 SGF 文本解析为 GameState（主分支）。"""
    if not isinstance(text, str):
        raise SGFError("棋谱必须是文本")
    nodes, _ = _parse_nodes(text.lstrip("\ufeff"))
    if not nodes:
        raise SGFError("棋谱没有节点")
    root = nodes[0]

    size_text = _first(root, "SZ", "19")
    size_text = size_text.split(":")[0]
    try:
        size = int(size_text)
    except ValueError:
        raise SGFError("棋盘尺寸无效：{!r}".format(size_text))
    if size not in (9, 13, 19):
        raise SGFError("只支持 9、13、19 路棋盘，收到 {}".format(size))

    try:
        komi = float(_first(root, "KM", "7.5"))
    except ValueError:
        komi = 7.5

    game = GameState(size, komi, BLACK)

    setup_black = root.get("AB") or []
    setup_white = root.get("AW") or []
    if setup_black or setup_white:
        _apply_setup(game, setup_black, setup_white)

    for node in nodes[1:]:
        for tag, color in (("B", BLACK), ("W", WHITE)):
            if tag not in node:
                continue
            value = _first(node, tag, "")
            if value == "":
                game.pass_turn()
                continue
            x, y = _sgf_to_coord(value)
            ok, err = game.play(x, y)
            if not ok:
                raise SGFError("第 {} 手无法落子：{}".format(game.move_count + 1, err))

    palette = _first(root, "PL", "")
    if palette == "W" and not game.history:
        game.first_color = WHITE
        game.turn = WHITE
    return game


def _apply_setup(game, black_points, white_points):
    """处理 AB/AW（让子或残局摆子）：直接摆子并交给白方先行。"""
    board = game.board
    for value in black_points:
        x, y = _sgf_to_coord(value)
        if board.in_bounds(x, y):
            board.set(x, y, BLACK)
    for value in white_points:
        x, y = _sgf_to_coord(value)
        if board.in_bounds(x, y):
            board.set(x, y, WHITE)
    board.captures[BLACK] = 0
    board.captures[WHITE] = 0
    game.positions = {board.position_key()}
    game.turn = WHITE if black_points else BLACK
    game.first_color = BLACK


def load_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return loads(handle.read())


def save_file(path, game, **kwargs):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(dumps(game, **kwargs))
