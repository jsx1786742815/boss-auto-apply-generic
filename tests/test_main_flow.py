# -*- coding: utf-8 -*-
"""main() 启动顺序测试 —— 保证「首次引导」永远先于连 Chrome 出现。

这是 v23 的一个易回归点：profile 检查若排到 get_ws_url() 之后，
首次使用的用户（没配 profile、也没开 CDP Chrome）只会看到一屏 traceback，
看不到本该看到的引导话术。
"""
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


import boss_auto_apply_cdp as B  # noqa: E402


def memory_db():
    """内存库替身：避免单测在仓库里生成 data/applications.db。"""
    conn = sqlite3.connect(':memory:')
    conn.execute('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT, company TEXT, position TEXT, salary TEXT,
        apply_date TEXT DEFAULT (date('now')),
        score INTEGER DEFAULT 0, greeting TEXT, UNIQUE(job_id, company))''')
    conn.commit()
    return conn



class MainStartupOrderTests(unittest.TestCase):
    def test_missing_profile_is_reported_before_connecting_chrome(self):
        """没有 profile 时，必须在连 CDP 之前就返回。"""
        missing = str(ROOT / "definitely-not-a-profile.json")
        called = {'ws': False}

        def fake_ws():
            called['ws'] = True
            raise AssertionError("不该在这时连接 Chrome")

        with mock.patch.dict(os.environ, {'BOSS_PROFILE': missing}):
            with mock.patch.object(B, 'get_ws_url', side_effect=fake_ws):
                with mock.patch('builtins.print'):
                    B.main()

        self.assertFalse(called['ws'], '缺配置时不应尝试连接 Chrome CDP')

    def test_connection_failure_returns_cleanly_without_traceback(self):
        """Chrome 未启动时应给出提示并正常返回，而不是抛异常。"""
        profile = str(ROOT / 'templates' / 'frontend.json')

        with mock.patch.dict(os.environ, {'BOSS_PROFILE': profile}):
            with mock.patch.object(B, 'init_db', side_effect=memory_db):
                with mock.patch.object(B, 'get_ws_url',
                                       side_effect=ConnectionRefusedError(10061, 'refused')):
                    with mock.patch('builtins.print'):
                        # 不应抛出任何异常
                        B.main()

    def test_valid_profile_reaches_chrome_connection_step(self):
        """配置合法时应继续走到连接 Chrome 这一步。"""
        profile = str(ROOT / 'templates' / 'frontend.json')
        reached = {'ws': False}

        def fake_ws():
            reached['ws'] = True
            raise ConnectionRefusedError(10061, 'refused')

        with mock.patch.dict(os.environ, {'BOSS_PROFILE': profile}):
            with mock.patch.object(B, 'init_db', side_effect=memory_db):
                with mock.patch.object(B, 'get_ws_url', side_effect=fake_ws):
                    with mock.patch('builtins.print'):
                        B.main()

        self.assertTrue(reached['ws'], '配置合法时应当尝试连接 Chrome CDP')


if __name__ == '__main__':
    unittest.main()
