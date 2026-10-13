"""CLI invariants using local synthetic Git fixtures only; no project code is run."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills/repo-governance-pro/scripts/repo_inventory.py"
spec = importlib.util.spec_from_file_location("repo_inventory_under_test", SCRIPT)
inventory_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory_module)


@unittest.skipUnless(shutil.which("git"), "Git is required")
class RepositoryInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="repo-inventory-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "project with spaces"
        self.repo.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="Synthetic Fixture", GIT_AUTHOR_EMAIL="fixture@example.com",
                        GIT_COMMITTER_NAME="Synthetic Fixture", GIT_COMMITTER_EMAIL="fixture@example.com")
        self.git("init", "-b", "main")
        self.write("README.md", "DO_NOT_EXPORT_CONTENT_OR_AUTHOR_01993\n")
        self.write("AGENTS.md", "Synthetic instructions only.\n")
        self.write("pyproject.toml", "# manifest presence is not valid configuration\n")
        self.write("Makefile", "all:\n\t@echo do-not-run\n")
        self.write(".github/workflows/check.yml", "# no executable workflow\n")
        self.write("tests/test_order.py", "raise RuntimeError('never execute project tests')\n")
        self.commit()

    def git(self, *args, check=True):
        result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(self.repo), *args],
                                capture_output=True, env=self.env, check=check)
        return result.stdout

    def write(self, name, content):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-m", "Synthetic fixture")

    def fingerprint(self):
        paths = [self.repo / ".git" / name for name in ("index", "HEAD", "config")]
        return {str(p): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in paths}

    def cli(self, *, repo=None, output=None, args=(), env=None):
        destination = output or self.base / ("reports-" + str(len(list(self.base.glob("reports-*")))))
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo or self.repo),
                                 "--out-dir", str(destination), *args], capture_output=True, text=True,
                                env={**self.env, **(env or {})}, timeout=20)
        self.assertNotIn("Traceback", result.stderr)
        data = json.loads((destination / "inventory.json").read_text()) if result.returncode == 0 else None
        return result, data, destination

    def evidence(self, data, name):
        return next(item for item in data["evidence"] if item["path"] == name)

    def test_clean_repository_reports_signals_and_no_content_or_author(self):
        before = self.fingerprint()
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.fingerprint())
        self.assertFalse(data["git"]["worktree"]["dirty"])
        self.assertEqual(data["git"]["branch"], "main")
        self.assertEqual(data["tracked"]["count"], 6)
        self.assertTrue(data["snapshot"]["consistent"])
        for signal in ("readme", "agents", "tests", "build", "ci", "manifests"):
            self.assertEqual(data["signals"][signal]["count"], 1)
        self.assertEqual(self.evidence(data, "README.md")["sha256"],
                         hashlib.sha256((self.repo / "README.md").read_bytes()).hexdigest())
        for path in (destination / "inventory.json", destination / "inventory.md"):
            body = path.read_text()
            for sensitive in ("DO_NOT_EXPORT_CONTENT_OR_AUTHOR", "Synthetic Fixture", "fixture@example.com", str(self.repo)):
                self.assertNotIn(sensitive, body)
        self.assertIn("no project tests were run", (destination / "inventory.md").read_text())
        self.assertIsNone(data["scope"]["quality_score"])

    def test_dirty_status_counts_staged_unstaged_and_untracked_without_exporting_untracked_paths(self):
        self.write("README.md", "changed working-file content")
        self.write("tests/test_added.py", "not executed")
        self.git("add", "tests/test_added.py")
        self.write("private-token-should-not-appear.txt", "private content")
        before = self.fingerprint()
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.fingerprint())
        status = data["git"]["worktree"]
        self.assertTrue(status["dirty"])
        self.assertEqual((status["staged"], status["unstaged"], status["untracked"]), (1, 1, 1))
        self.assertNotIn("private-token-should-not-appear", (destination / "inventory.json").read_text())
        self.assertEqual(self.evidence(data, "README.md")["sha256"], hashlib.sha256(b"changed working-file content").hexdigest())

    def test_detached_head_is_explicit(self):
        head = self.git("rev-parse", "HEAD").strip().decode()
        self.git("checkout", "--detach", head)
        result, data, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(data["git"]["detached"])
        self.assertIsNone(data["git"]["branch"])
        self.assertEqual(data["git"]["head"], head)

    def test_empty_repository_is_supported_without_head(self):
        empty = self.base / "empty"
        subprocess.run(["git", "init", "-b", "main", str(empty)], check=True, env=self.env, capture_output=True)
        result, data, _ = self.cli(repo=empty)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(data["git"]["head"])
        self.assertFalse(data["git"]["detached"])
        self.assertEqual(data["tracked"]["count"], 0)

    def test_non_repository_and_missing_input_fail_without_reports(self):
        for source in (self.base, self.base / "missing"):
            result, data, destination = self.cli(repo=source)
            self.assertEqual(result.returncode, 2)
            self.assertIsNone(data)
            self.assertFalse(destination.exists())

    def test_bare_repository_is_rejected(self):
        bare = self.base / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, env=self.env, capture_output=True)
        result, data, _ = self.cli(repo=bare)
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(data)
        self.assertIn("bare", result.stderr)

    def test_subdirectory_input_still_inventories_full_worktree(self):
        result, data, _ = self.cli(repo=self.repo / "tests")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["tracked"]["count"], 6)
        self.assertEqual(data["signals"]["readme"]["paths"], ["README.md"])

    def test_output_in_repository_is_rejected_without_mutation(self):
        inside = self.repo / "reports"
        result, data, _ = self.cli(output=inside)
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(data)
        self.assertFalse(inside.exists())
        self.assertIn("outside", result.stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_output_symlink_resolving_into_repository_is_rejected(self):
        alias = self.base / "alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        result, _, _ = self.cli(output=alias / "reports")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.repo / "reports").exists())

    def test_existing_reports_are_never_overwritten(self):
        result, _, destination = self.cli()
        self.assertEqual(result.returncode, 0)
        original = (destination / "inventory.json").read_bytes()
        again, data, _ = self.cli(output=destination)
        self.assertEqual(again.returncode, 2)
        self.assertIsNone(data)
        self.assertEqual((destination / "inventory.json").read_bytes(), original)

    def test_deleted_tracked_file_has_missing_evidence(self):
        (self.repo / "README.md").unlink()
        result, data, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["signals"]["readme"]["count"], 1)
        self.assertEqual(self.evidence(data, "README.md")["state"], "missing")
        self.assertNotIn("sha256", self.evidence(data, "README.md"))
        self.assertEqual(data["git"]["worktree"]["unstaged"], 1)

    def test_spaces_newlines_and_rename_records_do_not_split_paths(self):
        old, new = "tests/test old\nname.py", "tests/test new\nname.py"
        self.write(old, "fixture")
        self.commit()
        self.git("mv", old, new)
        self.write("README.md", "also changed")
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(new, data["signals"]["tests"]["paths"])
        changes = {i["path"]: i["status"] for i in data["git"]["worktree"]["tracked_changes"]}
        self.assertEqual(changes[new], "R ")
        self.assertEqual(changes["README.md"], " M")
        self.assertIn("test new\\nname.py", (destination / "inventory.md").read_text())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_tracked_leaf_symlink_is_not_read(self):
        external = self.base / "outside-secret.txt"
        external.write_text("OUTSIDE_SECRET_DO_NOT_READ")
        target = self.repo / "README.md"
        target.unlink()
        target.symlink_to(external)
        self.commit()
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = self.evidence(data, "README.md")
        self.assertEqual(evidence["state"], "symlink_skipped")
        self.assertNotIn("sha256", evidence)
        self.assertNotIn("OUTSIDE_SECRET", (destination / "inventory.json").read_text())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_parent_directory_symlink_cannot_read_outside_worktree(self):
        self.write("nested/README.md", "inside")
        self.commit()
        shutil.rmtree(self.repo / "nested")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "README.md").write_text("external secret")
        (self.repo / "nested").symlink_to(outside, target_is_directory=True)
        result, data, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.evidence(data, "nested/README.md")["state"], "symlink_skipped")
        self.assertNotIn("sha256", self.evidence(data, "nested/README.md"))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO unavailable")
    def test_special_file_is_not_opened_or_blocking(self):
        path = self.repo / "README.md"
        path.unlink()
        os.mkfifo(path)
        result, data, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.evidence(data, "README.md")["state"], "not_regular")

    def test_file_and_evidence_limits_are_explicit(self):
        self.write("README.md", "x" * 20)
        result, data, _ = self.cli(args=("--max-file-bytes", "16", "--max-evidence", "4"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(data["evidence"]), 4)
        self.assertEqual(data["limits"]["evidence_omitted"], 2)
        self.assertEqual(self.evidence(data, "README.md")["state"], "too_large")
        self.assertNotIn("sha256", self.evidence(data, "README.md"))

    def test_path_lists_are_bounded_without_losing_total(self):
        for number in range(55):
            self.write(f"docs/{number:02d}/README.md", "fixture")
        self.commit()
        result, data, _ = self.cli(args=("--max-evidence", "2"))
        self.assertEqual(result.returncode, 0, result.stderr)
        signal = data["signals"]["readme"]
        self.assertEqual(signal["count"], 56)
        self.assertEqual(len(signal["paths"]), 50)
        self.assertEqual(signal["paths_omitted"], 6)
        self.assertEqual(len(data["evidence"]), 2)

    def test_invalid_limits_fail_with_cli_error(self):
        for value in ("0", "-1", "no", "100000001"):
            result, _, _ = self.cli(args=("--max-evidence", value))
            self.assertEqual(result.returncode, 2)

    def test_injected_git_environment_cannot_redirect_inventory(self):
        result, data, _ = self.cli(env={"GIT_DIR": str(self.base / "wrong"), "GIT_WORK_TREE": str(self.base)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["tracked"]["count"], 6)

    def test_fsmonitor_and_project_code_are_not_executed(self):
        marker = self.base / "must-not-exist"
        hook = self.base / "fsmonitor-hook.sh"
        hook.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\n")
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        result, data, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse(data["scope"]["project_code_executed"])

    def test_markdown_escapes_html_pipe_and_control_chars_in_paths(self):
        path = "tests/<script>|name\tfile.py"
        self.write(path, "fixture")
        self.commit()
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(path, data["signals"]["tests"]["paths"])
        markdown = (destination / "inventory.md").read_text()
        self.assertNotIn("<script>", markdown)
        self.assertIn("&lt;script&gt;&#124;name\\tfile.py", markdown)

    def test_snapshot_change_is_flagged_without_claiming_consistency(self):
        real_state = inventory_module.git_state
        calls = 0

        def changing_state(root):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.write("README.md", "changed between checks")
            return real_state(root)

        with mock.patch.object(inventory_module, "git_state", side_effect=changing_state):
            data = inventory_module.inventory(self.repo, 64, 1024)
        self.assertFalse(data["snapshot"]["consistent"])
        self.assertEqual(data["snapshot"]["state"], "changed_during_collection")

    def test_unsupported_safe_open_platform_does_not_hash(self):
        with mock.patch.object(inventory_module.os, "supports_dir_fd", set()):
            result = inventory_module.hash_evidence(self.repo, "README.md", {"modes": {"100644"}}, 1024)
        self.assertEqual(result["state"], "safe_open_unavailable")
        self.assertNotIn("sha256", result)

    def test_submodule_evidence_does_not_traverse(self):
        result = inventory_module.hash_evidence(self.repo, "README.md", {"modes": {"160000"}}, 1024)
        self.assertEqual(result["state"], "submodule_skipped")
        self.assertNotIn("sha256", result)

    def test_merge_conflict_counts_unique_tracked_path_and_exports_no_conflict_content(self):
        self.git("checkout", "-b", "fixture-side")
        self.write("README.md", "side conflict content\n")
        self.commit()
        self.git("checkout", "main")
        self.write("README.md", "main conflict content\n")
        self.commit()
        self.git("merge", "fixture-side", check=False)
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["tracked"]["count"], 6)
        self.assertEqual(data["git"]["worktree"]["conflicts"], 1)
        self.assertEqual(self.evidence(data, "README.md")["state"], "hashed")
        self.assertNotIn("side conflict content", (destination / "inventory.json").read_text())

    @unittest.skipUnless(os.name == "posix", "POSIX filenames required")
    def test_non_utf8_filename_roundtrips_without_crashing(self):
        raw = os.fsencode(self.repo / "tests") + b"/test_\xff.py"
        try:
            with open(raw, "wb") as handle:
                handle.write(b"fixture")
        except OSError as exc:
            self.skipTest(f"Filesystem refuses non-UTF-8 filename (errno={exc.errno})")
        self.commit()
        result, data, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        path = os.fsdecode(b"tests/test_\xff.py")
        self.assertIn(path, data["signals"]["tests"]["paths"])
        self.assertEqual(self.evidence(data, path)["state"], "hashed")

    def test_untracked_readme_does_not_enter_tracked_signals(self):
        self.write("untracked/README.md", "do not read")
        result, data, destination = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["signals"]["readme"]["paths"], ["README.md"])
        self.assertEqual(data["git"]["worktree"]["untracked"], 1)
        self.assertNotIn("untracked/README.md", (destination / "inventory.json").read_text())

    def test_default_output_is_external_and_paths_are_absolute(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo)],
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        targets = [Path(p) for p in response["reports"]]
        self.addCleanup(shutil.rmtree, targets[0].parent)
        self.assertTrue(all(p.is_absolute() and p.is_file() for p in targets))
        self.assertFalse(targets[0].is_relative_to(self.repo))


if __name__ == "__main__":
    unittest.main()
