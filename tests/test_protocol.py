import unittest

from weiqi.net.protocol import (
    PROTOCOL_VERSION, ProtocolError, clean_chat_text, clean_name,
    decode_message, encode_message,
)


class ProtocolTest(unittest.TestCase):
    def test_roundtrip_unicode(self):
        message = {"type": "chat", "name": "小明", "text": "你好"}
        line = encode_message(message)
        self.assertTrue(line.endswith(b"\n"))
        self.assertEqual(decode_message(line), message)

    def test_decode_rejects_invalid_json(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"{not json}\n")

    def test_decode_rejects_non_object(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"[1, 2, 3]\n")

    def test_decode_requires_type(self):
        with self.assertRaises(ProtocolError):
            decode_message(b'{"x": 1}\n')

    def test_clean_name(self):
        self.assertEqual(clean_name("  小明  "), "小明")
        with self.assertRaises(ProtocolError):
            clean_name("")
        with self.assertRaises(ProtocolError):
            clean_name("x" * 21)

    def test_clean_chat_text(self):
        self.assertEqual(clean_chat_text("  你好  "), "你好")
        with self.assertRaises(ProtocolError):
            clean_chat_text("   ")
        with self.assertRaises(ProtocolError):
            clean_chat_text("x" * 501)
        with self.assertRaises(ProtocolError):
            clean_chat_text("恶意\n换行")

    def test_version_constant(self):
        self.assertEqual(PROTOCOL_VERSION, 1)


if __name__ == "__main__":
    unittest.main()
