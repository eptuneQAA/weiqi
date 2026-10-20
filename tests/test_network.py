import sys
import time
import unittest

from PyQt5.QtCore import QCoreApplication

from weiqi.core.game import Phase
from weiqi.net.client import GameClient
from weiqi.net.server import GameServer

APP = QCoreApplication.instance() or QCoreApplication(sys.argv)


def wait_until(predicate, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    APP.processEvents()
    return predicate()


class NetworkTest(unittest.TestCase):
    def test_full_game_chat_and_scoring(self):
        server = GameServer("测试房间", 9, 1, "主机", 0, 7.5)
        ok, err = server.start()
        self.assertTrue(ok, err)
        client = GameClient()
        chats = []
        results = []
        welcomes = []
        errors = []
        client.welcome_received.connect(welcomes.append)
        client.chat_received.connect(chats.append)
        client.game_finished.connect(results.append)
        client.error_occurred.connect(errors.append)
        self.addCleanup(client.close)
        self.addCleanup(server.stop)
        client.connect_to_host("127.0.0.1", server.port, "客机")

        self.assertTrue(wait_until(lambda: bool(welcomes)), "未收到 welcome")
        self.assertTrue(wait_until(lambda: server.client_ready))
        self.assertEqual(welcomes[0]["guest_color"], 2)

        ok, err = server.host_play(4, 4)
        self.assertTrue(ok, err)
        self.assertTrue(wait_until(lambda: server.game.turn == 2))

        client.send_move(3, 3)
        self.assertTrue(
            wait_until(lambda: len(server.game.history) == 2)
        )
        self.assertEqual(server.game.turn, 1)
        self.assertFalse(errors)

        ok, _ = server.host_chat("主机消息")
        self.assertTrue(ok)
        self.assertTrue(
            wait_until(
                lambda: any(m["text"] == "主机消息" for m in chats)
            )
        )
        client.send_chat("客机消息")
        self.assertTrue(
            wait_until(
                lambda: any(m["text"] == "客机消息" for m in chats)
            )
        )

        server.host_pass()
        self.assertTrue(wait_until(lambda: server.game.turn == 2))
        client.send_pass()
        self.assertTrue(
            wait_until(lambda: server.game.phase == Phase.SCORING)
        )

        self.assertTrue(server.host_mark_dead([(4, 4)]))
        self.assertTrue(server.host_confirm_score())
        self.assertTrue(wait_until(lambda: bool(results)))
        self.assertEqual(results[0]["reason"], "数子")
        self.assertEqual(server.game.phase, Phase.FINISHED)


if __name__ == "__main__":
    unittest.main()
