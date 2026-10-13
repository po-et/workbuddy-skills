import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/sensitive-data-mask/scripts/mask_sensitive.py"
SAMPLE = "Synthetic log fixture: phone=19900000001 email=demo@example.com\n"


class MaskIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.src = self.base / "a.log"
        self.src.write_text(SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, input=None):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, input=input)

    def test_same_directory_force_does_not_truncate_source(self):
        r = self.run_cli(self.src, "--out-dir", self.base, "--force", "--json")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.src.read_text(), SAMPLE)

    def test_empty_suffix_refuses_alias(self):
        self.assertEqual(self.run_cli(self.src, "--suffix", "", "--force").returncode, 2)
        self.assertEqual(self.src.read_text(), SAMPLE)

    def test_output_hardlink_to_source_is_refused(self):
        out = self.base / "out"
        out.mkdir()
        (out / "a.log").hardlink_to(self.src)
        self.assertEqual(self.run_cli(self.src, "--out-dir", out, "--force").returncode, 2)
        self.assertEqual(self.src.read_text(), SAMPLE)

    def test_report_cannot_replace_source(self):
        self.assertEqual(self.run_cli(self.src, "--report", self.src, "--force").returncode, 2)
        self.assertFalse((self.base / "a.log.masked").exists())
        self.assertEqual(self.src.read_text(), SAMPLE)

    def test_report_cannot_replace_masked_output(self):
        self.assertEqual(self.run_cli(self.src, "--report", str(self.src) + ".masked").returncode, 2)
        self.assertEqual(self.src.read_text(), SAMPLE)

    def test_default_output_masks_and_source_hash_unchanged(self):
        before = hashlib.sha256(self.src.read_bytes()).hexdigest()
        r = self.run_cli(self.src, "--types", "phone,email", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        masked = Path(d["files"][0]["dst"]).read_text()
        self.assertNotIn("19900000001", masked)
        self.assertNotIn("demo@example.com", masked)
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(), before)
        self.assertEqual(d["total_hits"], 2)

    def test_existing_output_skipped_nonzero_and_preserved(self):
        out = Path(str(self.src) + ".masked")
        out.write_text("existing")
        r = self.run_cli(self.src, "--json")
        self.assertEqual(r.returncode, 1)
        d = json.loads(r.stdout)
        self.assertEqual(d["files"], [])
        self.assertEqual(d["batch_status"], "incomplete")
        self.assertEqual(out.read_text(), "existing")

    def test_force_replaces_only_independent_output(self):
        out = Path(str(self.src) + ".masked")
        out.write_text("existing")
        self.assertEqual(self.run_cli(self.src, "--force").returncode, 0)
        self.assertNotEqual(out.read_text(), "existing")
        self.assertEqual(self.src.read_text(), SAMPLE)

    def test_directory_preserves_nested_names(self):
        logs = self.base / "logs"
        for folder in ("east", "west"):
            (logs / folder).mkdir(parents=True)
            (logs / folder / "a.log").write_text(SAMPLE)
        out = self.base / "masked"
        r = self.run_cli(logs, "--out-dir", out, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((out / "east/a.log").exists())
        self.assertTrue((out / "west/a.log").exists())

    def test_explicit_files_same_name_collision_preflight(self):
        other = self.base / "other"
        other.mkdir()
        p = other / "a.log"
        p.write_text(SAMPLE)
        out = self.base / "masked"
        self.assertEqual(self.run_cli(self.src, p, "--out-dir", out).returncode, 2)
        self.assertFalse(out.exists())

    def test_bad_utf8_nonzero_does_not_replace_existing_output(self):
        self.src.write_bytes(b"valid prefix\n\xff")
        out = Path(str(self.src) + ".masked")
        out.write_text("preserve")
        r = self.run_cli(self.src, "--force", "--json")
        self.assertEqual(r.returncode, 2)
        d = json.loads(r.stdout)
        self.assertEqual(d["files"], [])
        self.assertEqual(d["total_hits"], 0)
        self.assertEqual(out.read_text(), "preserve")
        self.assertFalse(list(self.base.glob(".mask-*")))

    def test_in_place_requires_flag_and_preserves_mode(self):
        self.assertNotEqual(self.run_cli(self.src, "--in-place").returncode, 0)
        self.assertEqual(self.src.read_text(), SAMPLE)
        self.src.chmod(0o600)
        r = self.run_cli(self.src, "--in-place", "--yes", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("19900000001", self.src.read_text())
        self.assertEqual(self.src.stat().st_mode & 0o777, 0o600)

    def test_dry_run_writes_nothing(self):
        r = self.run_cli(self.src, "--dry-run", "--report", self.src, "--json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.src.read_text(), SAMPLE)
        self.assertEqual(len(list(self.base.iterdir())), 1)

    def test_stdin_result_only_on_stdout(self):
        r = self.run_cli("-", "--types", "email", "--json", input=SAMPLE)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("demo@example.com", r.stdout)
        self.assertEqual(json.loads(r.stderr)["total_hits"], 1)

    def test_mapping_report_has_no_plaintext_values(self):
        report = self.base / "map.json"
        r = self.run_cli(self.src, "--types", "phone,email", "--report", report, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("19900000001", report.read_text())
        self.assertNotIn("demo@example.com", report.read_text())
        self.assertTrue(json.loads(report.read_text()))

    def test_symlink_source_refused(self):
        link = self.base / "alias.log"
        link.symlink_to(self.src)
        self.assertEqual(self.run_cli(link, "--json").returncode, 2)
        self.assertEqual(self.src.read_text(), SAMPLE)


if __name__ == "__main__":
    unittest.main()
