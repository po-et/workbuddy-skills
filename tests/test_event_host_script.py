"""Host timer CLI regressions using the published text example and boundary inputs."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/event-host-script/scripts/host_timer.py'


class HostTimerCLITest(unittest.TestCase):
    def run_cli(self, text='你好，欢迎大家。', *args):
        return subprocess.run([sys.executable, str(SCRIPT), '-', *args], input=text,
                              capture_output=True, text=True, timeout=10,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_zero_total_duration_is_rejected(self):
        for total in ('0', '0秒', '0分钟', '0:00', '0.001'):
            with self.subTest(total=total):
                result = self.run_cli('你好', '--total', total)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('全稿', result.stdout)

    def test_negative_and_nonfinite_total_duration_fail_cleanly(self):
        for total in ('-1', 'nan', 'inf', '-inf', '1e309', '9' * 400, '9' * 400 + '分钟'):
            with self.subTest(total=total[:30]):
                result = self.run_cli('你好', '--total=' + total)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_explicit_empty_total_is_rejected(self):
        result = self.run_cli('你好', '--total', '')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_documented_duration_formats_accept_valid_limits(self):
        for total in ('8:00', '480', '8分钟', '八分钟', '90秒', '两分半'):
            with self.subTest(total=total):
                result = self.run_cli('你好，欢迎大家。', '--total', total)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('在给定的', result.stdout)

    def test_real_total_limit_still_detects_overtime(self):
        result = self.run_cli('你好，欢迎大家。', '--total', '1秒')
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn('超出给定的', result.stdout)

    def test_roles_stage_notes_and_placeholders_are_excluded(self):
        result = self.run_cli('【开场 · 约 1 分钟】\nA：你好，[姓名]。（停两秒）\nB：欢迎大家。\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('全稿 6 字', result.stdout)
        self.assertIn('方括号占位 1 处', result.stdout)

    def test_annual_party_example_matches_documented_count(self):
        example = (ROOT / 'skills/event-host-script/examples/annual-party-dual-host.md').read_text()
        text = next(block for block in re.findall(r'```[^\n]*\n(.*?)```', example, re.S) if '【开场' in block)
        result = self.run_cli(text, '--total', '8:00')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('全稿 835 字', result.stdout)
        self.assertIn('3 分 48 秒', result.stdout)
        self.assertNotIn('需要处理：', result.stdout)

    def test_file_input_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'script.txt'
            source.write_text('【开场 · 约 1 分钟】\n你好，欢迎大家。\n')
            before = hashlib.sha256(source.read_bytes()).digest()
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), '--total', '8:00'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)


if __name__ == '__main__':
    unittest.main()
