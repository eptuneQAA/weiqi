import unittest

from weiqi.core.board import BLACK, WHITE
from weiqi.ui.help_content import HELP_PAGES

REQUIRED_PAGES = [
    "quickstart", "board", "liberties", "ko", "eyes", "scoring",
    "controls", "ai", "lan", "faq", "glossary",
]
VALID_HIGHLIGHT_COLORS = {"green", "blue", "red", "orange", "gray"}
VALID_MARK_COLORS = {
    "green", "blue", "red", "orange", "black", "white",
}


class HelpContentTest(unittest.TestCase):
    def test_required_pages_and_unique_ids(self):
        ids = [page["id"] for page in HELP_PAGES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, REQUIRED_PAGES)

    def test_pages_have_useful_content(self):
        for page in HELP_PAGES:
            self.assertTrue(page["title"].strip())
            self.assertGreater(len(page["html"].strip()), 100, page["id"])
            self.assertNotIn("http://", page["html"])
            self.assertNotIn("https://", page["html"])

    def test_core_terms_are_explained(self):
        combined = "\n".join(
            page["title"] + page["html"] for page in HELP_PAGES
        )
        for term in (
            "气", "提子", "禁入点", "劫", "两只真眼",
            "贴目 7.5", "人机", "局域网",
        ):
            self.assertIn(term, combined)

    def test_diagram_data_is_valid(self):
        for page in HELP_PAGES:
            for diagram in page["diagrams"]:
                self.assertTrue(diagram["caption"].strip())
                size = diagram.get("size", 9)
                self.assertIn(size, (9, 13, 19))
                for x, y, color in diagram.get("stones", []):
                    self.assertTrue(0 <= x < size, (page["id"], x, y))
                    self.assertTrue(0 <= y < size, (page["id"], x, y))
                    self.assertIn(color, (BLACK, WHITE))
                for x, y, color in diagram.get("highlights", []):
                    self.assertTrue(0 <= x < size, (page["id"], x, y))
                    self.assertTrue(0 <= y < size, (page["id"], x, y))
                    self.assertIn(color, VALID_HIGHLIGHT_COLORS)
                for x, y, text, color in diagram.get("marks", []):
                    self.assertTrue(0 <= x < size, (page["id"], x, y))
                    self.assertTrue(0 <= y < size, (page["id"], x, y))
                    self.assertTrue(text.strip())
                    self.assertIn(color, VALID_MARK_COLORS)


if __name__ == "__main__":
    unittest.main()
