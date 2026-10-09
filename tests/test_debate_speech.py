"""Observable CLI checks for debate timing; no network or manuscript changes."""

import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/debate-speech/scripts/speech_timer.py"
EXAMPLE = ROOT / "skills/debate-speech/examples/lilun-zhengfang-yibian.md"


class DebateSpeechTimerTests(unittest.TestCase):
    def run_cli(self, text, *args, encoding="utf-8"):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manuscript.txt"
            path.write_bytes(text.encode(encoding))
            before = hashlib.sha256(path.read_bytes()).digest()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), *args],
                text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ["manuscript.txt"])
            self.assertNotIn("Traceback", result.stderr)
            return result

    def test_existing_full_example_is_under_ninety_percent(self):
        text = re.search(r"### 1 立论稿全文.*?\n```\n(.*?)\n```", EXAMPLE.read_text(), re.S).group(1)
        result = self.run_cli(text, "250", "--limit", "3:00")
        self.assertEqual(result.returncode, 0)
        self.assertIn("全文 623 字，约 2 分 30 秒", result.stdout)
        self.assertIn("写到九成是 675 字", result.stdout)
        self.assertIn("[待核] 3 处", result.stdout)

    def test_english_word_rate_does_not_double_duration(self):
        result = self.run_cli("practice " * 300, "150", "--language", "en", "--limit", "2:00")
        self.assertEqual(result.returncode, 0)
        self.assertIn("全文 300 词，约 2 分 00 秒", result.stdout)
        self.assertIn("超过九成线 30 词", result.stdout)

    def test_compounds_accents_and_fullwidth_english_are_single_words(self):
        result = self.run_cli("don't one-size-fits-all café ＡＩ ２０２６", "150", "--language", "en")
        self.assertEqual(result.returncode, 0)
        self.assertIn("全文 5 词", result.stdout)

    def test_english_in_default_mode_warns_about_rate_unit(self):
        result = self.run_cli("practice " * 300, "150", "--limit", "2:00")
        self.assertEqual(result.returncode, 3)
        self.assertIn("--language en 后重跑", result.stdout)

    def test_overlong_chinese_reports_minimum_and_target_cuts(self):
        result = self.run_cli("【一辩立论】\n" + "论" * 900, "250", "--limit", "3:00")
        self.assertEqual(result.returncode, 3)
        self.assertIn("超出上限 150 字", result.stdout)
        self.assertIn("至少删到 750 字，最好删到 675 字", result.stdout)

    def test_titles_placeholders_and_punctuation_do_not_inflate_body(self):
        result = self.run_cli("【很长的准备标题】\n[待核：原文]\n[待补：事实]\n你好，世界！", "250")
        self.assertEqual(result.returncode, 0)
        self.assertIn("全文 4 字", result.stdout)
        self.assertIn("[待核] 1 处", result.stdout)
        self.assertIn("[待补] 1 处", result.stdout)

    def test_empty_body_is_content_error(self):
        result = self.run_cli("【立论】\n[待补：正文]", "250")
        self.assertEqual(result.returncode, 1)

    def test_mixed_text_requires_matching_equivalent_character_rate(self):
        result = self.run_cli("你好 AI don't", "250")
        self.assertEqual(result.returncode, 0)
        self.assertIn("全文 6 字", result.stdout)
        result = self.run_cli("你好 AI", "150", "--language", "en")
        self.assertEqual(result.returncode, 1)
        self.assertIn("中英混合稿", result.stderr)

    def test_invalid_rates_are_friendly_content_errors(self):
        for rate in ("nan", "inf", "0", "-2", "not-a-rate"):
            with self.subTest(rate=rate):
                result = self.run_cli("你好", "--rate", rate)
                self.assertEqual(result.returncode, 1)

    def test_fractional_rate_is_not_truncated_in_output(self):
        result = self.run_cli("你好", "250.5")
        self.assertEqual(result.returncode, 0)
        self.assertIn("按 250.5 字/分钟", result.stdout)

    def test_gbk_manuscript_is_supported(self):
        result = self.run_cli("你好世界", "250", encoding="gbk")
        self.assertEqual(result.returncode, 0)
        self.assertIn("全文 4 字", result.stdout)

    def test_english_default_rate_is_explicit_assumption(self):
        result = self.run_cli("practice", "--language", "en")
        self.assertEqual(result.returncode, 0)
        self.assertIn("[待确认] 没给语速，先按 150 词/分钟", result.stdout)


if __name__ == "__main__":
    unittest.main()
