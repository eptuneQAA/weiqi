"""JSON 行协议与输入校验。"""

import json

PROTOCOL_VERSION = 1
DISCOVERY_MAGIC = "WEIQI_DISCOVERY"
DISCOVERY_PORT = 45678
DEFAULT_TCP_PORT = 45679
MAX_CHAT_LENGTH = 500
MAX_NAME_LENGTH = 20


class ProtocolError(ValueError):
    pass


def encode_message(message):
    text = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def decode_message(line):
    if isinstance(line, bytes):
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            raise ProtocolError("消息不是 UTF-8 编码")
    else:
        text = line
    text = text.strip()
    if not text:
        raise ProtocolError("空消息")
    try:
        data = json.loads(text)
    except ValueError:
        raise ProtocolError("JSON 格式错误")
    if not isinstance(data, dict):
        raise ProtocolError("消息必须是对象")
    if not isinstance(data.get("type"), str):
        raise ProtocolError("缺少消息类型")
    return data


def clean_name(name):
    if not isinstance(name, str):
        raise ProtocolError("名称格式错误")
    value = name.strip()
    if not 1 <= len(value) <= MAX_NAME_LENGTH:
        raise ProtocolError("名称长度需为 1-20 字符")
    if any(ord(ch) < 32 for ch in value):
        raise ProtocolError("名称包含控制字符")
    return value


def clean_chat_text(text):
    if not isinstance(text, str):
        raise ProtocolError("聊天内容格式错误")
    value = text.strip()
    if not value:
        raise ProtocolError("聊天内容为空")
    if len(value) > MAX_CHAT_LENGTH:
        raise ProtocolError("聊天内容不能超过 500 字符")
    if any(ord(ch) < 32 for ch in value):
        raise ProtocolError("聊天内容包含控制字符")
    return value
