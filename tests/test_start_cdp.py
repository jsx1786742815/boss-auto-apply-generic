import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


import start_cdp_v2


class StartCdpTests(unittest.TestCase):
    def test_default_args_do_not_request_restart(self):
        args = start_cdp_v2.parse_args([])

        self.assertFalse(args.restart)

    def test_restart_requires_explicit_flag(self):
        args = start_cdp_v2.parse_args(["--restart"])

        self.assertTrue(args.restart)

    def test_chrome_command_targets_isolated_profile_and_boss_page(self):
        cmd = start_cdp_v2.build_chrome_command(
            chrome="chrome.exe",
            user_data=r"C:\Temp\UserData-CDP",
            port=9223,
            start_url="https://www.zhipin.com/web/geek/jobs",
        )

        self.assertIn("--remote-debugging-port=9223", cmd)
        self.assertIn(r"--user-data-dir=C:\Temp\UserData-CDP", cmd)
        self.assertEqual("https://www.zhipin.com/web/geek/jobs", cmd[-1])

    def test_pid_output_parser_ignores_noise(self):
        pids = start_cdp_v2.parse_pid_output("123\n\nnot-a-pid\n456\n")

        self.assertEqual([123, 456], pids)

    def test_start_script_does_not_use_taskkill(self):
        source = (SCRIPTS / "start_cdp_v2.py").read_text(encoding="utf-8").lower()

        self.assertNotIn("taskkill", source)


if __name__ == "__main__":
    unittest.main()
