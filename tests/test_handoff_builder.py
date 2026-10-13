import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "ported/skills/handoff-doc-zh"
SCRIPT = SKILL / "scripts/build_handoff.py"
spec = importlib.util.spec_from_file_location("handoff_builder", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "workspace"
        self.root.mkdir()
        (self.root / "synthetic-verification.txt").write_text("fixture\n")
        self.data = json.loads((SKILL / "examples/state.json").read_text())

    def tearDown(self):
        self.temp.cleanup()

    def build(self, data=None):
        return mod.build(self.data if data is None else data, self.root)

    def test_reported_in_progress_is_consistent(self):
        r = self.build()
        self.assertEqual(r["record_integrity"], "consistent")
        self.assertEqual(r["reported_status"], "in_progress")
        self.assertFalse(r["verifications"][0]["executed_by_builder"])

    def test_hash_mismatch_preserves_actual(self):
        self.data["artifacts"][0]["sha256"] = "0" * 64
        r = self.build()
        self.assertEqual(r["artifacts"][0]["check"], "hash_mismatch")
        self.assertEqual(len(r["artifacts"][0]["observed_sha256"]), 64)
        self.assertEqual(r["record_integrity"], "needs_review")

    def test_hash_match(self):
        h = self.build()["artifacts"][0]["observed_sha256"]
        self.data["artifacts"][0]["sha256"] = h
        self.assertEqual(self.build()["artifacts"][0]["check"], "hash_match")

    def test_missing_artifact_never_invents_evidence(self):
        (self.root / "synthetic-verification.txt").unlink()
        r = self.build()
        self.assertIsNone(r["artifacts"][0]["observed_sha256"])
        self.assertIn("evidence_unavailable", r["verifications"][0]["record_issues"])

    def test_parent_path_rejected(self):
        self.data["artifacts"][0]["path"] = "../elsewhere"
        with self.assertRaises(mod.InputError):
            self.build()

    def test_symlink_not_read(self):
        target = self.base / "outside.txt"
        target.write_text("do not read")
        (self.root / "synthetic-verification.txt").unlink()
        (self.root / "synthetic-verification.txt").symlink_to(target)
        self.assertEqual(self.build()["artifacts"][0]["check"], "symlink_not_read")

    def test_size_limit(self):
        self.assertEqual(mod.build(self.data, self.root, 1)["artifacts"][0]["check"], "size_limit")

    def test_completed_with_open_items_is_conflict(self):
        self.data["reported_status"] = "completed"
        self.assertEqual(self.build()["record_integrity"], "needs_review")

    def test_missing_verification_time(self):
        del self.data["verifications"][0]["observed_at"]
        self.assertIn("missing_observation_time", self.build()["verifications"][0]["record_issues"])

    def test_naive_time_rejected(self):
        self.data["verifications"][0]["observed_at"] = "2026-01-01T00:00:00"
        with self.assertRaises(mod.InputError):
            self.build()

    def test_next_item_cannot_be_invented(self):
        self.data["next_item_id"] = "missing"
        with self.assertRaises(mod.InputError):
            self.build()

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(mod.InputError):
            json.loads('{"a":1,"a":2}', object_pairs_hook=mod.pairs)

    def test_secret_rejected_without_echo(self):
        self.data["goal"] = "password=synthetic-demo-value"
        with self.assertRaises(mod.InputError) as e:
            self.build()
        self.assertNotIn("synthetic-demo-value", str(e.exception))

    def test_bool_schema_version_rejected(self):
        self.data["schema_version"] = True
        with self.assertRaises(mod.InputError):
            self.build()

    def cli(self, data=None, out=None):
        state = self.base / "input.json"
        state.write_text(json.dumps(self.data if data is None else data))
        return subprocess.run([sys.executable, "-B", str(SCRIPT), str(state), "--root", str(self.root),
                               "--out", str(out or self.base / "out")], capture_output=True, text=True)

    def test_cli_outputs_and_keeps_workspace_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        r = self.cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(Path(out["markdown"]).is_absolute())
        self.assertTrue(Path(out["json"]).exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertEqual(self.cli().returncode, 2)  # does not overwrite

    def test_cli_warn_still_delivers(self):
        self.data["verifications"][0]["reported_status"] = "failed"
        r = self.cli()
        self.assertEqual(r.returncode, 1)
        self.assertTrue((self.base / "out/handoff.md").exists())

    def test_cli_no_writes_with_bad_input(self):
        self.data["progress_percent"] = 100
        r = self.cli()
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.base / "out").exists())

    def test_cli_refuses_output_inside_workspace(self):
        self.assertEqual(self.cli(out=self.root / "report").returncode, 2)
        self.assertFalse((self.root / "report").exists())


if __name__ == "__main__":
    unittest.main()
