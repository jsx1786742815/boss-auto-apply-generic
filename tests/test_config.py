# -*- coding: utf-8 -*-
"""profile.json 配置层测试 —— 保证「通用化」不会回归成写死行业默认值。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


from config import (  # noqa: E402
    CITY_CODES,
    ProfileError,
    city_to_code,
    list_templates,
    load_profile,
)


def write_profile(data):
    tmp = tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    return tmp.name


MINIMAL = {
    "keywords": ["前端开发", "React开发"],
    "score": {"strong_positive": ["react", "vue"]},
}


class CityCodeTests(unittest.TestCase):
    def test_accepts_chinese_city_name(self):
        self.assertEqual("101280600", city_to_code("深圳"))

    def test_accepts_shi_suffix(self):
        self.assertEqual("101010100", city_to_code("北京市"))

    def test_passes_through_nine_digit_code(self):
        self.assertEqual("101999999", city_to_code("101999999"))

    def test_unknown_city_raises_with_guidance(self):
        with self.assertRaises(ProfileError) as ctx:
            city_to_code("不存在市")

        self.assertIn("无法识别城市", str(ctx.exception))


class LoadProfileTests(unittest.TestCase):
    def test_missing_file_raises_guided_error(self):
        with self.assertRaises(ProfileError) as ctx:
            load_profile(str(ROOT / "definitely-not-here.json"))

        self.assertIn("未找到配置文件", str(ctx.exception))

    def test_minimal_profile_is_accepted_and_defaults_filled(self):
        prof = load_profile(write_profile(MINIMAL))

        self.assertEqual(["前端开发", "React开发"], prof["keywords"])
        self.assertEqual("101010100", prof["city_code"])  # 默认北京
        self.assertEqual(50, prof["max_apply"])
        self.assertEqual(45, prof["score"]["base"])

    def test_keywords_required(self):
        with self.assertRaises(ProfileError) as ctx:
            load_profile(write_profile({"score": {"strong_positive": ["x"]}}))

        self.assertIn("keywords", str(ctx.exception))

    def test_score_required(self):
        with self.assertRaises(ProfileError) as ctx:
            load_profile(write_profile({"keywords": ["x"]}))

        self.assertIn("score", str(ctx.exception))

    def test_empty_strong_positive_is_rejected(self):
        with self.assertRaises(ProfileError) as ctx:
            load_profile(write_profile(
                {"keywords": ["x"], "score": {"strong_positive": []}}))

        self.assertIn("strong_positive", str(ctx.exception))

    def test_blank_keywords_are_stripped_and_rejected_if_all_blank(self):
        with self.assertRaises(ProfileError):
            load_profile(write_profile(
                {"keywords": ["  ", ""], "score": {"strong_positive": ["x"]}}))

    def test_invalid_json_reports_parse_error(self):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8")
        tmp.write("{not json")
        tmp.close()

        with self.assertRaises(ProfileError) as ctx:
            load_profile(tmp.name)

        self.assertIn("不是合法 JSON", str(ctx.exception))

    def test_non_object_root_rejected(self):
        with self.assertRaises(ProfileError):
            load_profile(write_profile(["not", "an", "object"]))

    def test_daily_limit_never_below_run_cap(self):
        prof = load_profile(write_profile(
            dict(MINIMAL, max_apply=80, daily_limit=10)))

        self.assertEqual(80, prof["daily_limit"])

    def test_custom_city_and_salary_are_honoured(self):
        prof = load_profile(write_profile(
            dict(MINIMAL, city="深圳", salary_min_k=20, salary_max_k=60)))

        self.assertEqual("101280600", prof["city_code"])
        self.assertEqual(20, prof["salary_min_k"])
        self.assertEqual(60, prof["salary_max_k"])

    def test_industry_specific_fields_default_to_empty(self):
        """通用化关键：不含个人黑名单时必须是空表，不能残留数据行业黑名单。"""
        prof = load_profile(write_profile(MINIMAL))

        self.assertEqual([], prof["blacklist"])
        self.assertEqual([], prof["outsource_companies"])
        self.assertEqual([], prof["exclude_keywords"])
        self.assertEqual([], prof["negative_keywords"])


class TemplateTests(unittest.TestCase):
    def test_all_templates_load_and_validate(self):
        names = list_templates()
        self.assertIn("data", names)
        self.assertIn("frontend", names)
        self.assertGreaterEqual(len(names), 6)

        for name in names:
            path = ROOT / "templates" / f"{name}.json"
            prof = load_profile(str(path))
            self.assertTrue(prof["keywords"], f"{name} 关键词为空")
            self.assertTrue(prof["score"]["strong_positive"],
                            f"{name} strong_positive 为空")

    def test_no_template_leaks_another_industry_keywords(self):
        """前端模板不该出现数据行业关键词，反之亦然。"""
        frontend = load_profile(str(ROOT / "templates" / "frontend.json"))
        joined = " ".join(frontend["keywords"])
        self.assertNotIn("数据开发", joined)
        self.assertNotIn("数仓", joined)


if __name__ == "__main__":
    unittest.main()
