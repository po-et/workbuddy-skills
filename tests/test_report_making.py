"""Report-making CLI regressions; generated data is synthetic and local only."""
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/report-making/scripts/anomaly_flag.py'


class AnomalyCLITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_cli(self, text, *args):
        source = self.root / 'input.csv'
        source.write_text(text, encoding='utf-8')
        before = hashlib.sha256(source.read_bytes()).digest()
        proc = subprocess.run([sys.executable, str(SCRIPT), str(source), *args],
                              capture_output=True, text=True,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).digest())
        self.assertNotIn('Traceback', proc.stderr)
        return proc

    def output_rows(self):
        with (self.root / 'output.csv').open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))

    def test_constant_history_still_flags_absolute_jump(self):
        text = '期,值\n' + ''.join(f'W{i:02d},100\n' for i in range(1, 9)) + 'W09,130\n'
        r = self.run_cli(text, '--pct', '50', '--min-abs', '10', '--out', str(self.root / 'output.csv'))
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.output_rows()
        self.assertTrue(all(not row['标记'] for row in rows[:-1]))
        self.assertEqual(rows[-1]['标记'], '▲')

    def test_nonfinite_values_are_skipped_without_polluting_history(self):
        for invalid in ('nan', 'NaN%', 'inf', '-inf', '1e999'):
            with self.subTest(invalid=invalid):
                text = '期,值\nW01,100\nW02,' + invalid + '\nW03,120\n'
                r = self.run_cli(text, '--out', str(self.root / 'output.csv'))
                self.assertEqual(r.returncode, 0, r.stderr)
                rows = self.output_rows()
                self.assertEqual(rows[1]['值'], '—')
                self.assertEqual(rows[1]['环比'], '—')
                self.assertEqual(rows[2]['环比'], '—')

    def test_all_invalid_values_fail_cleanly(self):
        r = self.run_cli('期,值\nW01,nan\nW02,inf\n')
        self.assertEqual(r.returncode, 1)

    def test_ambiguous_csv_structure_is_rejected(self):
        for text in ('期,值,值\nW01,100,900\nW02,120,300\n',
                     '期,\nW01,100\n', '期,值\nW01,100,unexpected\n',
                     '期,值\n,,unexpected\nW02,150\n',
                     '期,值\nW01\n', '期,值\nW01,"100\n'):
            with self.subTest(text=text):
                r = self.run_cli(text, '--out', str(self.root / 'output.csv'))
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertFalse((self.root / 'output.csv').exists())

    def test_empty_period_or_group_is_rejected(self):
        for text, args in (('期,值\n,100\nW02,150\n', ()),
                           ('区域,期,值\n,W01,100\n华东,W02,150\n', ('--by', '区域', '--period', '期'))):
            with self.subTest(text=text):
                self.assertEqual(self.run_cli(text, *args).returncode, 1)

    def test_thresholds_must_be_finite_and_valid(self):
        for flag, value in (('--pct', 'nan'), ('--pct', 'inf'), ('--sigma', 'nan'),
                            ('--sigma', 'inf'), ('--min-abs', '-10'),
                            ('--min-abs', 'nan'), ('--min-abs', 'inf')):
            with self.subTest(flag=flag, value=value):
                self.assertEqual(self.run_cli('期,值\nW01,100\nW02,150\n', flag, value).returncode, 1)

    def test_delimiters_and_standard_change(self):
        for delimiter in (',', ';', '\t'):
            with self.subTest(delimiter=delimiter):
                text = delimiter.join(('期', '值')) + '\n' + '\n'.join(
                    delimiter.join(row) for row in [('W01', '100'), ('W02', '90'), ('W03', '150')])
                r = self.run_cli(text, '--min-abs', '10', '--out', str(self.root / 'output.csv'))
                self.assertEqual(r.returncode, 0, r.stderr)
                rows = self.output_rows()
                self.assertEqual([row['标记'] for row in rows], ['', '', '▲'])
                self.assertEqual(rows[-1]['环比'], '+66.7%')

    def test_grouped_series_remain_independent(self):
        r = self.run_cli('区域,期,值\n华东,W01,100\n华西,W01,200\n华东,W02,150\n华西,W02,210\n',
                         '--by', '区域', '--period', '期', '--min-abs', '10', '--out', str(self.root / 'output.csv'))
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = self.output_rows()
        self.assertEqual([(row['维度'], row['期']) for row in rows if row['标记']], [('华东', 'W02')])

    def test_zero_previous_value_has_no_percentage(self):
        r = self.run_cli('期,值\nW01,0\nW02,100\n', '--out', str(self.root / 'output.csv'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.output_rows()[-1]['环比'], '—')

    def test_refuses_to_overwrite_source(self):
        r = self.run_cli('期,值\nW01,100\nW02,150\n', '--out', str(self.root / 'input.csv'))
        self.assertEqual(r.returncode, 1)


class ProfileCLITest(unittest.TestCase):
    def test_missing_observation_is_not_reported_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'observations.csv'
            source.write_text('技能,期,下载数\ncoding-for-beginners,2026-09-26,\ncoding-for-beginners,2026-10-09,45\n', encoding='utf-8')
            before = source.read_bytes()
            r = subprocess.run([sys.executable, str(SCRIPT.with_name('csv_profile.py')), str(source)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(source.read_bytes(), before)
            self.assertNotIn('需要处理：没有发现常见问题', r.stdout)
            self.assertIn('取不到写待取数', r.stdout)


if __name__ == '__main__':
    unittest.main()
