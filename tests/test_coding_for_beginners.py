"""CLI behavior regressions for error search privacy and log completeness."""
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

    def test_unquoted_private_data_is_omitted_from_search_line(self):
        r = self.run_cli('coding-for-beginners', 'explain_error.py',
                         'ValueError: invalid account PRIVATE_ACCOUNT_123 at https://dummy.invalid?token=DUMMY_SECRET_456\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        line = next(line for line in r.stdout.splitlines() if line.startswith('拿去搜索的版本：'))
        self.assertEqual(line, '拿去搜索的版本：ValueError')

    def test_known_nameerror_template_remains_searchable(self):
        r = self.run_cli('coding-for-beginners', 'explain_error.py',
                         "NameError: name 'my_private_variable' is not defined. Did you mean: 'another_private_name'?\n")
        self.assertEqual(r.returncode, 0)
        line = next(line for line in r.stdout.splitlines() if line.startswith('拿去搜索的版本：'))
        self.assertEqual(line, "拿去搜索的版本：NameError: name '...' is not defined")

    def test_quoted_valueerror_template_remains_searchable(self):
        r = self.run_cli('coding-for-beginners', 'explain_error.py',
                         "ValueError: invalid literal for int() with base 10: 'private-account'\n")
        self.assertEqual(r.returncode, 0)
        line = next(line for line in r.stdout.splitlines() if line.startswith('拿去搜索的版本：'))
        self.assertEqual(line, "拿去搜索的版本：ValueError: invalid literal for int() with base 10: '...'")

    def test_custom_suffix_is_not_added_to_search(self):
        r = self.run_cli('coding-for-beginners', 'explain_error.py',
                         "ValueError: invalid literal for int() with base 10: 'x' customer ACCOUNT123\n")
        line = next(line for line in r.stdout.splitlines() if line.startswith('拿去搜索的版本：'))
        self.assertEqual(line, '拿去搜索的版本：ValueError')



if __name__ == '__main__':
    unittest.main()
