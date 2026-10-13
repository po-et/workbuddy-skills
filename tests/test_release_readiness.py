"""Synthetic offline inputs exercise gate, evidence and output-preservation invariants."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills/release-readiness-check/scripts/release_check.py"
SPEC = importlib.util.spec_from_file_location("release_check_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CLEAN_DOCKERFILE = "FROM python:3.12-slim\nUSER 1000\n"


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="release-readiness-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project with spaces"
        self.project.mkdir()
        self.counter = 0

    def write(self, name, content):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def clean_project(self):
        self.write("Dockerfile", CLEAN_DOCKERFILE)
        self.write(".dockerignore", ".git\n")

    def cli(self, *args, output=None, default_output=False):
        self.counter += 1
        destination = output or self.base / f"report-{self.counter}.md"
        command = [sys.executable, str(SCRIPT), str(self.project), "--json"]
        if not default_output:
            command += ["--out", str(destination)]
        result = subprocess.run(command + list(args), capture_output=True, text=True, timeout=30,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertNotIn("Traceback", result.stderr)
        data = json.loads(result.stdout) if result.returncode in (0, 1) else None
        if default_output and data:
            self.addCleanup(shutil.rmtree, Path(data["report"]).parent)
        return result, data

    def item(self, data, key):
        return next(item for item in data["items"] if item["id"] == key)

    def receipt(self, data, name):
        return next(item for item in data["evidence"]["inputs"] if item["path"] == name)

    def test_clean_static_check_does_not_approve_release(self):
        self.clean_project()
        result, data = self.cli("--strict")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data["gate"]["blocked"])
        self.assertEqual(data["gate"]["production_readiness"], "unknown")
        self.assertFalse(data["gate"]["release_approved"])
        self.assertEqual(data["gate"]["scope"], "static_checks_only")
        self.assertEqual(data["gate"]["checked"], ["dockerfile"])
        self.assertNotIn("可以上线", Path(data["report"]).read_text())
        self.assertTrue(data["evidence"]["unchanged_during_checks"])

    def test_high_blocks_only_strict_and_does_not_expose_secret_value(self):
        value = "synthetic-value-must-not-be-exported-123"
        self.write("Dockerfile", CLEAN_DOCKERFILE + "ENV API_TOKEN=" + value + "\n")
        normal, normal_data = self.cli()
        strict, strict_data = self.cli("--strict")
        self.assertEqual(normal.returncode, 0)
        self.assertEqual(strict.returncode, 1)
        self.assertGreater(normal_data["total"]["high"], 0)
        self.assertEqual(strict_data["gate"]["verdict"], "no-go")
        self.assertNotIn(value, normal.stdout)
        self.assertNotIn(value, Path(normal_data["report"]).read_text())

    def test_warn_keeps_static_verdict_without_release_approval(self):
        self.write("Dockerfile", "FROM python:latest\n")
        result, data = self.cli("--strict")
        self.assertEqual(result.returncode, 0)
        self.assertGreater(data["total"]["warn"], 0)
        self.assertEqual(data["gate"]["verdict"], "go-with-warn")
        self.assertFalse(data["gate"]["release_approved"])

    def test_no_applicable_files_are_missing_evidence(self):
        self.write("notes.md", "Nothing executable here.\n")
        result, data = self.cli("--strict")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data["gate"]["verdict"], "unknown")
        self.assertTrue(all(item["status"] == "na" for item in data["items"]))

    def test_empty_dockerfile_is_unknown(self):
        self.write("Dockerfile", "# no parsed instructions\n")
        result, data = self.cli("--strict")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.item(data, "dockerfile")["reason_code"], "empty-input")

    def test_openapi_missing_baseline_blocks(self):
        self.write("openapi.json", json.dumps({"openapi": "3.0.3", "paths": {"/health": {"get": {}}}}))
        result, data = self.cli("--strict")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.item(data, "openapi")["reason_code"], "no-baseline")

    def test_baseline_does_not_exist_has_explicit_reason(self):
        self.write("openapi.json", json.dumps({"openapi": "3.0.3", "paths": {"/health": {"get": {}}}}))
        result, data = self.cli("--strict", "--openapi-base", str(self.base / "absent.json"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.item(data, "openapi")["reason_code"], "missing-base")
        self.assertTrue(any("missing" in gap for gap in data["gate"]["evidence_gaps"]))

    def test_invalid_empty_baseline_does_not_pass(self):
        self.write("openapi.json", json.dumps({"openapi": "3.0.3", "paths": {"/health": {"get": {}}}}))
        baseline = self.base / "previous.json"
        baseline.write_text("{}")
        result, data = self.cli("--strict", "--openapi-base", str(baseline))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.item(data, "openapi")["reason_code"], "skipped-invalid")
        self.assertEqual(self.receipt(data, str(baseline))["sha256"], hashlib.sha256(b"{}").hexdigest())

    def test_valid_baseline_deleted_operation_is_high(self):
        old = {"openapi": "3.0.3", "paths": {"/health": {"get": {}}, "/orders": {"get": {}}}}
        new = {"openapi": "3.0.3", "paths": {"/health": {"get": {}}}}
        baseline = self.base / "previous.json"
        baseline.write_text(json.dumps(old))
        self.write("openapi.json", json.dumps(new))
        result, data = self.cli("--strict", "--openapi-base", str(baseline))
        self.assertEqual(result.returncode, 1)
        self.assertGreater(self.item(data, "openapi")["counts"]["high"], 0)

    def test_old_skip_without_reason_still_runs_and_strict_blocks(self):
        self.clean_project()
        normal, data = self.cli("--skip", "env")
        strict, _ = self.cli("--skip", "env", "--strict")
        self.assertEqual(normal.returncode, 0)
        self.assertEqual(strict.returncode, 1)
        self.assertEqual(self.item(data, "env")["reason_code"], "missing-skip-reason")

    def test_reasoned_skip_is_recorded_without_approval(self):
        self.clean_project()
        result, data = self.cli("--skip", "env", "--skip-reason", "env=external review requested", "--strict")
        self.assertEqual(result.returncode, 0)
        item = self.item(data, "env")
        self.assertEqual(item["status"], "skipped")
        self.assertEqual(item["waiver"]["reason"], "external review requested")
        self.assertFalse(item["waiver"]["approval_verified"])
        self.assertFalse(data["gate"]["release_approved"])

    def test_all_skipped_never_become_a_pass(self):
        self.clean_project()
        args = ["--skip", ",".join(MODULE.ITEM_ORDER), "--strict"]
        for key in MODULE.ITEM_ORDER:
            args += ["--skip-reason", key + "=user-provided reason"]
        result, data = self.cli(*args)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data["gate"]["checked"], [])

    def test_invalid_skip_reason_and_limits_return_two(self):
        for args in (("--skip", "other"), ("--skip", "env", "--skip-reason", "bad"),
                     ("--skip", "env", "--skip-reason", "env="),
                     ("--skip-reason", "env=not skipped"),
                     ("--max-receipts", "0"), ("--max-receipt-bytes", "-1")):
            with self.subTest(args=args):
                result, _ = self.cli(*args)
                self.assertEqual(result.returncode, 2)

    def test_input_file_cannot_be_output_and_bytes_are_preserved(self):
        self.clean_project()
        path = self.project / "Dockerfile"
        before = path.read_bytes()
        result, data = self.cli(output=path)
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(data)
        self.assertEqual(path.read_bytes(), before)

    def test_existing_report_cannot_be_overwritten(self):
        self.clean_project()
        target = self.base / "old-report.md"
        target.write_text("KEEP EXISTING REPORT")
        result, _ = self.cli(output=target)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_text(), "KEEP EXISTING REPORT")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_output_symlink_cannot_overwrite_target(self):
        self.clean_project()
        target = self.base / "keep.md"
        target.write_text("KEEP")
        link = self.base / "symlink-report.md"
        link.symlink_to(target)
        result, _ = self.cli(output=link)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_text(), "KEEP")

    def test_output_parent_file_is_clean_error(self):
        self.clean_project()
        parent = self.base / "file-not-directory"
        parent.write_text("KEEP")
        result, _ = self.cli(output=parent / "report.md")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(parent.read_text(), "KEEP")

    def test_default_output_is_unique_per_run(self):
        self.clean_project()
        first, a = self.cli(default_output=True)
        second, b = self.cli(default_output=True)
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        self.assertNotEqual(a["report"], b["report"])
        self.assertTrue(Path(a["report"]).is_absolute())

    def test_receipts_bind_input_and_checker_bytes_and_change_with_input(self):
        self.clean_project()
        first, before = self.cli()
        self.assertEqual(first.returncode, 0)
        old_hash = self.receipt(before, "Dockerfile")["sha256"]
        self.assertEqual(old_hash, hashlib.sha256(CLEAN_DOCKERFILE.encode()).hexdigest())
        checker = next(r for r in before["evidence"]["checkers"] if r["path"] == "scripts/release_check.py")
        self.assertEqual(checker["sha256"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(len(before["evidence"]["checkers"]), 6)
        self.write("Dockerfile", CLEAN_DOCKERFILE + "# changed input\n")
        second, after = self.cli()
        self.assertEqual(second.returncode, 0)
        self.assertNotEqual(old_hash, self.receipt(after, "Dockerfile")["sha256"])

    def test_checker_receipt_changes_when_checker_bytes_change(self):
        self.clean_project()
        check_dir = self.base / "checks"
        shutil.copytree(SCRIPT.parent / "checks", check_dir)
        found = MODULE.discover(str(self.project))
        with mock.patch.object(MODULE, "CHECKS_DIR", str(check_dir)):
            before = MODULE.collect_receipts(str(self.project), found, None, set(), 128, 4 * 1024 * 1024)
            path = check_dir / "dockerfile_check.py"
            path.write_bytes(path.read_bytes() + b"\n# synthetic change\n")
            after = MODULE.collect_receipts(str(self.project), found, None, set(), 128, 4 * 1024 * 1024)
        self.assertNotEqual(before["checkers"][0]["sha256"], after["checkers"][0]["sha256"])
        self.assertFalse(MODULE.compare_receipts(before, after)["unchanged_during_checks"])

    def test_hash_receipt_limits_are_explicit_and_block_strict(self):
        self.clean_project()
        result, data = self.cli("--max-receipts", "1", "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(data["evidence"]["inputs"]), 1)
        self.assertEqual(data["evidence"]["omitted_count"], 1)
        self.write("Dockerfile", CLEAN_DOCKERFILE + "#" * 1000)
        result, data = self.cli("--max-receipt-bytes", "500", "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.receipt(data, "Dockerfile")["status"], "over-byte-limit")
        self.assertIsNone(self.receipt(data, "Dockerfile")["sha256"])

    def test_env_source_candidate_receipts_are_included(self):
        self.write(".env.example", "SAMPLE_OPTION=placeholder\n")
        self.write(".env", "SAMPLE_OPTION=placeholder\n")
        path = self.write("src/read_env.py", "import os\nprint(os.getenv('SAMPLE_OPTION'))\n")
        result, data = self.cli()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.receipt(data, "src/read_env.py")["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_changed_input_during_checks_is_missing_evidence(self):
        self.clean_project()
        original = MODULE.run_all

        def mutate(*args, **kwargs):
            items = original(*args, **kwargs)
            self.write("Dockerfile", CLEAN_DOCKERFILE + "# changed during checks\n")
            return items

        output = self.base / "changed-report.md"
        stdout = io.StringIO()
        argv = [str(SCRIPT), str(self.project), "--json", "--strict", "--out", str(output)]
        with mock.patch.object(MODULE, "run_all", side_effect=mutate), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            code = MODULE.main()
        data = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(data["evidence"]["unchanged_during_checks"])
        self.assertTrue(data["gate"]["blocked"])


if __name__ == "__main__":
    unittest.main()
