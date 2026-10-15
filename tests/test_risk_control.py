import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import websocket  # noqa: F401
except ImportError:
    websocket_stub = types.ModuleType("websocket")
    websocket_stub.create_connection = lambda *args, **kwargs: None
    sys.modules["websocket"] = websocket_stub


import boss_auto_apply_cdp


class FakeCDP:
    def eval(self, expression, await_promise=False):
        if expression == "document.querySelectorAll('.job-card-box').length":
            return 1
        return None


class RiskControlTests(unittest.TestCase):
    @mock.patch.object(boss_auto_apply_cdp.time, "sleep", return_value=None)
    @mock.patch.object(
        boss_auto_apply_cdp,
        "fetch_joblist",
        return_value=([], "code_37:您的环境存在异常"),
    )
    def test_code_37_stops_collection_without_retry(self, fetch_joblist, _sleep):
        with self.assertRaises(boss_auto_apply_cdp.RiskControlError):
            boss_auto_apply_cdp.collect_all(
                FakeCDP(),
                ["数据开发"],
                "101010100",
                max_pages=5,
            )

        self.assertEqual(1, fetch_joblist.call_count)


if __name__ == "__main__":
    unittest.main()
