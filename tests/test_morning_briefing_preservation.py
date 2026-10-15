"""Regression checks for original to-do and existing report preservation."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/morning-briefing/scripts/brief.py'
SOURCE = '- 合成今日事项 截止:2026-10-15 !\n- 合成未来事项不能丢 截止:2026-11-01\n'


class BriefPreservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'todo.txt'
        self.source.write_text(SOURCE, encoding='utf-8')
        self.output = self.root / 'brief.md'

    def cli(self, output=None, source=None, stdin=None):
        before = self.source.read_bytes()
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), str(source or self.source),
                                 '2026-10-15', '--out', str(output or self.output)],
                                input=stdin, text=True, capture_output=True)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertIn('合成未来事项不能丢', self.source.read_text())
        self.assertEqual(list(self.root.glob('.brief-*.tmp')), [])
        return result

    def test_new_report_written_with_original_future_task_preserved(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.output.read_text()
        self.assertIn('合成今日事项', report)
        self.assertNotIn('合成未来事项不能丢', report)
        self.assertTrue(report.startswith('# 晨间简报 2026-10-15'))

    def test_identical_input_output_rejected(self):
        result = self.cli(output=self.source)
        self.assertEqual(result.returncode, 2)
        self.assertIn('同一文件', result.stderr)

    def test_resolved_dotdot_alias_rejected(self):
        child = self.root / 'child'
        child.mkdir()
        result = self.cli(output=child / '..' / 'todo.txt')
        self.assertEqual(result.returncode, 2)
        self.assertIn('同一文件', result.stderr)

    def test_symbolic_link_to_input_rejected(self):
        self.output.symlink_to(self.source)
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('同一文件', result.stderr)
        self.assertTrue(self.output.is_symlink())

    def test_input_symlink_output_real_target_rejected(self):
        alias = self.root / 'input-link.txt'
        alias.symlink_to(self.source)
        result = self.cli(source=alias, output=self.source)
        self.assertEqual(result.returncode, 2)
        self.assertIn('同一文件', result.stderr)
        self.assertTrue(alias.is_symlink())

    def test_hard_link_to_input_rejected(self):
        self.output.hardlink_to(self.source)
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('硬链接', result.stderr)
        self.assertEqual(self.output.read_text(), SOURCE)

    def test_existing_other_report_preserved(self):
        self.output.write_text('合成已有报告', encoding='utf-8')
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('已存在', result.stderr)
        self.assertEqual(self.output.read_text(), '合成已有报告')

    def test_dangling_output_symlink_preserved(self):
        target = self.root / 'not-created.md'
        self.output.symlink_to(target)
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(target.exists())

    def test_stdin_new_report_does_not_require_input_path(self):
        result = self.cli(source='-', stdin=SOURCE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('合成今日事项', self.output.read_text())

    def test_target_created_during_atomic_commit_is_preserved(self):
        spec = importlib.util.spec_from_file_location('brief_preservation_regression', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_link = module.os.link

        def competing_create(temporary, target):
            Path(target).write_text('合成并发报告', encoding='utf-8')
            original_link(temporary, target)

        with mock.patch.object(module.os, 'link', side_effect=competing_create):
            with self.assertRaises(FileExistsError):
                module.write_atomic(self.output, '新简报', self.source)
        self.assertEqual(self.output.read_text(), '合成并发报告')
        self.assertEqual(self.source.read_text(), SOURCE)
        self.assertEqual(list(self.root.glob('.brief-*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
