# -*- coding: utf-8 -*-
"""评分与过滤的通用化测试 —— 确认代码里没有残留行业专属逻辑。

这是 v23 改造的核心不变式：同一份代码 + 不同 profile，应只放行各自行业的岗位。
"""
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import websocket  # noqa: F401
except ImportError:
    _stub = types.ModuleType("websocket")
    _stub.create_connection = lambda *a, **k: None
    sys.modules["websocket"] = _stub


import boss_auto_apply_cdp as B  # noqa: E402
from config import load_profile  # noqa: E402


FRONTEND_JOBS = [
    ("React前端开发工程师", "20-35K"),
    ("Vue前端开发", "15-30K"),
    ("Web前端工程师", "18-32K"),
]
DATA_JOBS = [
    ("数据开发工程师", "20-35K"),
    ("ETL工程师", "18-30K"),
]
IRRELEVANT = [
    ("销售代表", "8-15K"),
    ("Java后端开发工程师", "20-35K"),
]


class CrossIndustryScoringTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        # 避免污染其他测试模块的 _CFG
        B.configure({"score": {"base": 45, "strong_positive": ["x"]}})

    def _score_with(self, template, position, salary):
        prof = load_profile(str(ROOT / "templates" / template))
        B.configure(prof)
        return B.score_job(position, salary, "某公司"), prof["score_threshold"]

    def test_frontend_template_admits_frontend_jobs(self):
        for pos, sal in FRONTEND_JOBS:
            score, threshold = self._score_with("frontend.json", pos, sal)
            self.assertGreaterEqual(score, threshold,
                                    f"前端模板应放行「{pos}」，实际 {score} < {threshold}")

    def test_frontend_template_rejects_data_jobs(self):
        for pos, sal in DATA_JOBS:
            score, threshold = self._score_with("frontend.json", pos, sal)
            self.assertLess(score, threshold,
                            f"前端模板不应放行「{pos}」，实际 {score}")

    def test_data_template_admits_data_jobs(self):
        for pos, sal in DATA_JOBS:
            score, threshold = self._score_with("data.json", pos, sal)
            self.assertGreaterEqual(score, threshold,
                                    f"数据模板应放行「{pos}」，实际 {score} < {threshold}")

    def test_data_template_rejects_frontend_jobs(self):
        for pos, sal in FRONTEND_JOBS:
            score, threshold = self._score_with("data.json", pos, sal)
            self.assertLess(score, threshold,
                            f"数据模板不应放行「{pos}」，实际 {score}")

    def test_no_template_admits_irrelevant_jobs(self):
        for template in ("frontend.json", "data.json", "design.json", "qa.json"):
            for pos, sal in IRRELEVANT:
                score, threshold = self._score_with(template, pos, sal)
                self.assertLess(score, threshold,
                                f"{template} 不应放行无关岗位「{pos}」，实际 {score}")


class NoHardcodedIndustryTests(unittest.TestCase):
    def test_score_job_has_no_builtin_industry_words(self):
        """源码里不应再出现数据行业的强匹配词表。"""
        source = (SCRIPTS / "boss_auto_apply_cdp.py").read_text(encoding="utf-8")

        self.assertNotIn("strong_positive = ['spark'", source)
        self.assertNotIn("BLACKLIST_ALWAYS = [", source)
        self.assertNotIn("BLACKLIST_OUTSOURCE = [", source)

    def test_cdp_utils_has_no_default_city_or_keyword(self):
        source = (SCRIPTS / "cdp_utils.py").read_text(encoding="utf-8")

        self.assertNotIn("DEFAULT_CITY_CODE", source)
        self.assertNotIn("DEFAULT_KEYWORD", source)
        self.assertNotIn("101010100", source)

    def test_empty_config_does_not_silently_admit_jobs(self):
        """未 configure 时强匹配词表为空 —— 任何岗位都不该越过阈值。"""
        B.configure({"score": {"base": 45}})

        self.assertLess(B.score_job("数据开发工程师", "20-35K", "某公司"), 50)


if __name__ == "__main__":
    unittest.main()
