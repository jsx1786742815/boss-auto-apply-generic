import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class LayoutTests(unittest.TestCase):
    def test_stale_entrypoints_are_not_in_scripts(self):
        self.assertFalse((SCRIPTS / "boss_auto_apply_cdp_v22_api.py").exists())
        self.assertFalse((SCRIPTS / "boss_auto_apply_cdp_v21_bak.py").exists())

    def test_reference_guide_uses_current_entrypoint(self):
        guide = (ROOT / "references" / "usage_guide.md").read_text(encoding="utf-8")

        self.assertNotIn("chrome_cdp_starter.py", guide)
        self.assertIn("boss_auto_apply_cdp.py", guide)

    def test_skill_docs_do_not_reintroduce_cookie_login_checks(self):
        for relative in ("SKILL.md", "README.md", "AGENTS.md", "references/usage_guide.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("zp_at", text)
            self.assertNotIn("geek_zp_token", text)

    def test_troubleshooting_does_not_recommend_force_killing_chrome(self):
        guide = (ROOT / "references" / "cdp_troubleshooting.md").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("taskkill", guide.lower())
        self.assertNotIn("Stop-Process -Name chrome -Force", guide)


if __name__ == "__main__":
    unittest.main()
