"""CLI regressions for log completeness and conservative pain review."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'date,week,session,run_min,talk,effort,pain,next_morning,note\n'


class SkillCLITest(unittest.TestCase):
    def run_cli(self, skill, script, content, *args):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'input.txt'
            p.write_text(content, encoding='utf-8')
            before = p.read_bytes()
            proc = subprocess.run([sys.executable, str(ROOT / 'skills' / skill / 'scripts' / script), str(p), *args],
                                  capture_output=True, text=True,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertEqual(before, p.read_bytes())
            self.assertNotIn('Traceback', proc.stderr)
            return proc

    def run_review(self, rows):
        return self.run_cli('running-for-beginners', 'run_review.py', HEADER + rows, '--today', '2026-10-06')

    def test_three_distinct_sessions_still_complete(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,\n2026-10-03,1,2,8,整句,4,0,0,\n2026-10-05,1,3,8,整句,4,0,0,\n')
        self.assertEqual(r.returncode, 0)
        self.assertIn('→ 进入下一周', r.stdout)

    def test_next_day_worsening_blocks_automatic_progress(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,1,1,\n2026-10-03,1,2,8,整句,4,1,1,\n2026-10-05,1,3,8,整句,4,1,3,\n')
        self.assertEqual(r.returncode, 3)
        self.assertNotIn('→ 进入下一周', r.stdout)
        self.assertIn('次日疼痛加重', r.stdout)

    def test_duplicate_sessions_fail_with_data_error(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,1,1,\n2026-10-03,1,1,8,整句,4,1,1,\n2026-10-05,1,1,8,整句,4,1,1,\n')
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('→ 进入下一周', r.stdout)

    def test_session_four_is_invalid(self):
        r = self.run_review('2026-10-05,1,4,8,整句,4,1,1,\n')
        self.assertEqual(r.returncode, 1)

    def test_mild_knee_pain_stops_instead_of_progressing(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,1,1,膝盖痛\n2026-10-03,1,2,8,整句,4,1,1,膝盖痛\n2026-10-05,1,3,8,整句,4,1,1,膝盖痛\n')
        self.assertEqual(r.returncode, 3)
        self.assertIn('暂停跑步', r.stdout)
        self.assertNotIn('→ 进入下一周', r.stdout)
        self.assertNotIn('→ 从断点接着跑', r.stdout)
        self.assertIn('低分也不是继续跑步的许可', r.stdout)

    def test_explicit_joint_pain_overrides_zero_numeric_score(self):
        for note in ('膝盖痛', '关节疼', 'pain in my knee', 'knee hurts'):
            with self.subTest(note=note):
                r = self.run_review(f'2026-10-01,1,1,8,整句,4,0,0,{note}\n2026-10-03,1,2,8,整句,4,0,0,\n2026-10-05,1,3,8,整句,4,0,0,\n')
                self.assertEqual(r.returncode, 3)
                self.assertIn('局部不适', r.stdout)
                self.assertNotIn('→ 进入下一周', r.stdout)

    def test_low_pain_without_site_still_requires_review(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,1,1,\n')
        self.assertEqual(r.returncode, 3)
        self.assertIn('暂停跑步', r.stdout)

    def test_muscle_soreness_is_not_an_automatic_injury_or_progress_pass(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,大腿肌肉酸胀\n2026-10-03,1,2,8,整句,4,0,0,\n2026-10-05,1,3,8,整句,4,0,0,\n')
        self.assertEqual(r.returncode, 0)
        self.assertIn('重复本周', r.stdout)
        self.assertIn('先确认不适已缓解', r.stdout)
        self.assertNotIn('→ 进入下一周', r.stdout)

    def test_negated_pain_does_not_hide_a_separate_positive_site(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,没有膝痛；脚踝疼\n')
        self.assertEqual(r.returncode, 3)
        self.assertIn('脚踝疼', r.stdout)

    def test_explicitly_no_knee_pain_does_not_trigger_a_false_stop(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,无膝痛\n2026-10-03,1,2,8,整句,4,0,0,膝盖不疼\n2026-10-05,1,3,8,整句,4,0,0,\n')
        self.assertEqual(r.returncode, 0)
        self.assertIn('→ 进入下一周', r.stdout)

    def test_prior_pain_cannot_be_cleared_automatically_by_later_zeroes(self):
        r = self.run_review('2026-09-24,1,1,8,整句,4,1,1,膝盖痛\n2026-10-01,2,1,8,整句,4,0,0,\n2026-10-03,2,2,8,整句,4,0,0,\n2026-10-05,2,3,8,整句,4,0,0,\n')
        self.assertEqual(r.returncode, 3)
        self.assertNotIn('→ 进入下一周', r.stdout)
        self.assertIn('恢复情况需确认', r.stdout)

    def test_week_eight_does_not_claim_thirty_minute_completion(self):
        r = self.run_review('2026-10-01,8,1,8,整句,4,0,0,\n2026-10-03,8,2,8,整句,4,0,0,\n2026-10-05,8,3,8,整句,4,0,0,\n')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('8 周完成', r.stdout)
        self.assertNotIn('每次 30 分钟', r.stdout)

    def test_incomplete_week_does_not_progress(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,\n')
        self.assertEqual(r.returncode, 0)
        self.assertNotIn('→ 进入下一周', r.stdout)

    def test_invalid_pain_record_blocks_recommendations_from_valid_rows(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,\n2026-10-03,1,2,8,整句,4,0,0,\n2026-10-05,1,3,8,整句,4,0,0,\n2026-10-06,2,1,8,整句,4,疼,1,膝痛\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn('先修正全部数据问题', r.stderr)
        self.assertNotIn('→ 进入下一周', r.stdout)
        self.assertNotIn('→ 从断点接着跑', r.stdout)

    def test_duplicate_pain_header_cannot_hide_pain(self):
        content = 'date,week,session,run_min,talk,effort,pain,pain,next_morning,note\n2026-10-01,1,1,8,整句,4,1,0,0,\n'
        r = self.run_cli('running-for-beginners', 'run_review.py', content)
        self.assertEqual(r.returncode, 1)
        self.assertIn('重复列名', r.stderr)

    def test_ragged_row_blocks_recommendations(self):
        r = self.run_review('2026-10-01,1,1,8,整句,4,0,0,\n2026-10-03,1,2,8,整句,4,0,0,\n2026-10-05,1,3,8,整句,4,0,0,\n2026-10-06,2,1,8,整句,4,0,0,膝,痛\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn('列数与表头不一致', r.stdout)
        self.assertNotIn('→ 进入下一周', r.stdout)


if __name__ == '__main__':
    unittest.main()
