import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


from cdp_utils import build_search_url, ensure_zhipin_page, pick_cdp_page


class FakeCDP:
    def __init__(self, url):
        self.url = url
        self.expressions = []

    def eval(self, expression):
        self.expressions.append(expression)
        if expression == "window.location.href":
            return self.url
        return None


class PickCdpPageTests(unittest.TestCase):
    def test_prefers_zhipin_page_even_when_it_is_not_first(self):
        pages = [
            {"type": "page", "url": "https://example.com", "webSocketDebuggerUrl": "ws://first"},
            {"type": "page", "url": "https://www.zhipin.com/web/geek/jobs", "webSocketDebuggerUrl": "ws://boss"},
        ]

        self.assertEqual("ws://boss", pick_cdp_page(pages)["webSocketDebuggerUrl"])

    def test_falls_back_to_first_page_when_boss_is_not_open(self):
        pages = [
            {"type": "page", "url": "https://example.com", "webSocketDebuggerUrl": "ws://first"},
        ]

        self.assertEqual("ws://first", pick_cdp_page(pages)["webSocketDebuggerUrl"])

    def test_returns_none_for_empty_page_list(self):
        self.assertIsNone(pick_cdp_page([]))


class EnsureZhipinPageTests(unittest.TestCase):
    def test_reuses_existing_zhipin_page(self):
        cdp = FakeCDP("https://www.zhipin.com/web/geek/jobs?query=data")
        sleeps = []

        current = ensure_zhipin_page(cdp, "101010100", "数据开发", sleep=sleeps.append)

        self.assertIn("zhipin.com", current)
        self.assertEqual(["window.location.href"], cdp.expressions)
        self.assertEqual([], sleeps)

    def test_navigates_non_zhipin_page_before_preflight(self):
        cdp = FakeCDP("https://example.com")
        sleeps = []

        target = ensure_zhipin_page(cdp, "101010100", "数据开发", sleep=sleeps.append)

        self.assertIn("zhipin.com", target)
        self.assertEqual(2, len(cdp.expressions))
        self.assertIn("window.location.href='https://www.zhipin.com", cdp.expressions[1])
        self.assertEqual([5.0], sleeps)

    def test_search_url_encodes_keyword_and_city(self):
        url = build_search_url("数据开发", "101010100")

        self.assertIn("query=%E6%95%B0%E6%8D%AE%E5%BC%80%E5%8F%91", url)
        self.assertIn("city=101010100", url)

    def test_search_url_works_for_any_industry(self):
        """v23: 通用化后任意行业关键词都应正确拼接（不再假定数据行业）。"""
        url = build_search_url("UI设计师", "101020100")

        self.assertIn("city=101020100", url)
        self.assertIn("query=", url)
        self.assertNotIn("数据", url)


if __name__ == "__main__":
    unittest.main()
