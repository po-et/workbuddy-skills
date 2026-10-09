"""SQL guard regressions. These tests check text only and never connect to a database."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/sql-generation-helper/scripts/sql_guard.py'


class SQLGuardCLITest(unittest.TestCase):
    def run_cli(self, sql, dialect='mysql'):
        return subprocess.run([sys.executable, str(SCRIPT), '-', '--dialect', dialect],
                              input=sql, capture_output=True, text=True, timeout=10,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_executable_mysql_and_mariadb_comments_are_blocked(self):
        for marker in ('/*!', '/*!50000', '/*M!', '/*M!100100'):
            for dialect in ('mysql', 'mysql57'):
                with self.subTest(marker=marker, dialect=dialect):
                    result = self.run_cli(marker + ' UPDATE orders SET amount=0 */;', dialect)
                    self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                    self.assertIn('[B', result.stdout)
                    self.assertIn('只读闸门', result.stdout)
                    self.assertNotIn('结论：只读', result.stdout)

    def test_executable_comments_without_dialect_are_blocked(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '-'],
                                input='/*!50000 UPDATE orders SET amount=0 */;',
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_comment_markers_inside_strings_are_only_data(self):
        result = self.run_cli("SELECT '/*!50000 UPDATE orders SET amount=0 */' AS message;")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('[B', result.stdout)

    def test_normal_comments_and_replace_function_remain_readonly(self):
        sql = "SELECT REPLACE('UPDATE', 'DELETE', 'DROP') AS update_time; /* DROP TABLE orders */ -- DELETE FROM orders\n"
        result = self.run_cli(sql)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('[B', result.stdout)

    def test_mysql_double_dash_without_whitespace_does_not_hide_write(self):
        result = self.run_cli('SELECT 1--1; UPDATE orders SET amount=0;')
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn('[B01]', result.stdout)

    def test_mysql_double_dash_with_whitespace_is_a_comment(self):
        for gap in (' ', '\t'):
            with self.subTest(gap=gap):
                result = self.run_cli('SELECT 1; --' + gap + 'UPDATE orders SET amount=0;\n')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sqlite_double_dash_keeps_sqlite_comment_semantics(self):
        result = self.run_cli('SELECT 1--1; UPDATE orders SET amount=0;', 'sqlite')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_set_global_is_not_a_readonly_query(self):
        result = self.run_cli('SET GLOBAL max_connections=100;')
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn('结论：只读', result.stdout)

    def test_vacuum_file_write_is_not_a_readonly_query(self):
        result = self.run_cli("VACUUM INTO 'backup.sqlite';", 'sqlite')
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn('结论：只读', result.stdout)

    def test_existing_cte_write_detection_remains_blocked(self):
        result = self.run_cli('WITH moved AS (DELETE FROM orders RETURNING user_id) SELECT user_id FROM moved;', 'postgresql')
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_repurchase_example_and_reconciliations_remain_readonly(self):
        example = (ROOT / 'skills/sql-generation-helper/examples/repurchase-rate.md').read_text()
        blocks = re.findall(r'```sql\n(.*?)```', example, re.S)
        for sql in blocks[1:]:
            with self.subTest(sql=sql[:60]):
                result = self.run_cli(sql)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('[B', result.stdout)

    def test_file_input_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'query.sql'
            source.write_text('/*! UPDATE orders SET amount=0 */;')
            before = hashlib.sha256(source.read_bytes()).digest()
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), '--dialect', 'mysql'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
