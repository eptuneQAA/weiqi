"""批次 A 的加固测试：代理绕过、单条消息上限、认输阶段限制。"""

import sys
import unittest

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QNetworkProxy

from weiqi.core.board import BLACK
from weiqi.core.game import GameState, Phase
from weiqi.net import protocol
from weiqi.net.client import GameClient
from weiqi.net.server import GameServer

APP = QCoreApplication.instance() or QCoreApplication(sys.argv)


class ProxyBypassTest(unittest.TestCase):
    """局域网连接不能走系统代理，否则开着代理客户端时永远连不上。"""

    def test_client_socket_disables_proxy(self):
        client = GameClient()
        self.addCleanup(client.deleteLater)
        self.assertEqual(client.socket.proxy().type(), QNetworkProxy.NoProxy)

    def test_server_disables_proxy(self):
        server = GameServer("房间", 9, BLACK, "主机", 0)
        self.addCleanup(server.deleteLater)
        self.assertEqual(server.server.proxy().type(), QNetworkProxy.NoProxy)


class MessageSizeTest(unittest.TestCase):
    def test_oversized_line_is_rejected(self):
        line = b'{"type":"chat","text":"' + b"x" * (protocol.MAX_LINE_BYTES + 10) + b'"}'
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_message(line)

    def test_oversized_text_line_is_rejected(self):
        line = '{"type":"chat","text":"' + "x" * (protocol.MAX_LINE_BYTES + 10) + '"}'
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_message(line)

    def test_normal_line_still_parses(self):
        self.assertEqual(
            protocol.decode_message(b'{"type":"ping"}'), {"type": "ping"}
        )


class ResignPhaseTest(unittest.TestCase):
    def test_cannot_resign_while_scoring(self):
        game = GameState(9)
        game.pass_turn()
        game.pass_turn()
        self.assertEqual(game.phase, Phase.SCORING)
        self.assertFalse(game.resign(BLACK))
        self.assertEqual(game.phase, Phase.SCORING)

    def test_cannot_resign_after_finish(self):
        game = GameState(9)
        self.assertTrue(game.resign(BLACK))
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertFalse(game.resign(BLACK))


if __name__ == "__main__":
    unittest.main()
