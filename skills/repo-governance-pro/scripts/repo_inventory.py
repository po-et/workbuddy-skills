#!/usr/bin/env python3
"""Offline, read-only inventory of tracked Git paths. Python 3.9+, stdlib only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile

PATH_LIMIT = 50
MAX_EVIDENCE = 64
MAX_FILE_BYTES = 1024 * 1024
CATEGORIES = ("readme", "agents", "tests", "build", "ci", "manifests")


class InventoryError(Exception):
    pass


def git(repo, *args, allow_failure=False):
    # Ignore injected Git directories/configuration/tracing; disable optional writes.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1")
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
               "-c", "core.untrackedCache=false", "-C", str(repo), *args]
    try:
        result = subprocess.run(command, capture_output=True, env=env, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise InventoryError("Git query unavailable or timed out") from None
    if result.returncode and not allow_failure:
        # Git stderr can contain local absolute paths or private configuration.
        raise InventoryError("Git query failed; verify the local working tree")
    return result


def repo_root(value):
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise InventoryError("Repository directory does not exist") from None
    if not path.is_dir():
        raise InventoryError("Repository input must be a directory")
    inside = git(path, "rev-parse", "--is-inside-work-tree", allow_failure=True)
    if inside.returncode or inside.stdout.strip() != b"true":
        raise InventoryError("Input is not a Git working tree (bare repositories are unsupported)")
    data = git(path, "rev-parse", "--show-toplevel").stdout
    return Path(os.fsdecode(data[:-1] if data.endswith(b"\n") else data)).resolve()


def index_entries(repo):
    raw = git(repo, "ls-files", "--stage", "-z").stdout
    entries = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, _object_id, stage = metadata.split()
        name = os.fsdecode(path)
        item = entries.setdefault(name, {"modes": set(), "stages": set()})
        item["modes"].add(mode.decode("ascii"))
        item["stages"].add(int(stage))
    return entries, raw


def worktree_status(repo):
    raw = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all",
              "--ignore-submodules=all").stdout
    records = raw.split(b"\0")
    counts = {"staged": 0, "unstaged": 0, "conflicts": 0, "untracked": 0}
    paths, i = [], 0
    conflicts = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    while i < len(records):
        entry = records[i]
        i += 1
        if not entry:
            continue
        code = entry[:2].decode("ascii")
        if code == "??":
            counts["untracked"] += 1
            continue
        if code == "!!":
            continue
        paths.append({"path": os.fsdecode(entry[3:]), "status": code})
        if code in conflicts:
            counts["conflicts"] += 1
        else:
            counts["staged"] += code[0] != " "
            counts["unstaged"] += code[1] != " "
        if "R" in code or "C" in code:
            i += 1  # porcelain -z adds an original path for rename/copy records.
    paths.sort(key=lambda item: item["path"])
    return {**counts, "dirty": bool(raw), "tracked_changes": paths[:PATH_LIMIT],
            "tracked_changes_omitted": max(0, len(paths) - PATH_LIMIT),
            "submodules": "not inspected"}, raw


def git_state(repo):
    head_result = git(repo, "rev-parse", "--verify", "HEAD", allow_failure=True)
    head = head_result.stdout.strip().decode("ascii") if head_result.returncode == 0 else None
    if head is not None and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head):
        raise InventoryError("Unsupported Git HEAD representation")
    branch_result = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", allow_failure=True)
    branch = os.fsdecode(branch_result.stdout[:-1]) if branch_result.returncode == 0 else None
    worktree, status_raw = worktree_status(repo)
    entries, index_raw = index_entries(repo)
    return {"head": head, "branch": branch, "detached": head is not None and branch is None,
            "worktree": worktree}, entries, (head, branch, status_raw, index_raw)


def categories(path):
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    lower_parts = tuple(p.lower() for p in parts)
    result = []
    if re.fullmatch(r"readme(?:\.(?:md|markdown|rst|txt))?", name):
        result.append("readme")
    if name == "agents.md":
        result.append("agents")
    if (any(p in {"test", "tests", "__tests__", "spec", "specs"} for p in lower_parts[:-1])
            or name.startswith("test_") or re.search(r"(?:_test\.(?:go|py)|[._](?:test|spec)\.[^.]+)$", name)):
        result.append("tests")
    if name in {"makefile", "gnumakefile", "cmakelists.txt", "dockerfile", "containerfile", "pom.xml",
                "build.gradle", "build.gradle.kts", "build.xml", "meson.build", "justfile"}:
        result.append("build")
    if (path.startswith(".github/workflows/") and name.endswith((".yml", ".yaml"))
            or name in {".gitlab-ci.yml", ".gitlab-ci.yaml", "jenkinsfile", "azure-pipelines.yml", "azure-pipelines.yaml"}
            or path.startswith(".circleci/") and name in {"config.yml", "config.yaml"}):
        result.append("ci")
    if (name in {"package.json", "pyproject.toml", "setup.py", "setup.cfg", "go.mod", "cargo.toml",
                 "gemfile", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts", "pipfile", "deno.json", "deno.jsonc"}
            or re.fullmatch(r"requirements(?:[-.][^/]*)?\.txt", name)):
        result.append("manifests")
    return result


def hash_evidence(root, path, item, maximum):
    result = {"path": path, "categories": categories(path), "git_modes": sorted(item["modes"])}
    if "120000" in item["modes"]:
        return {**result, "state": "symlink_skipped"}
    if "160000" in item["modes"]:
        return {**result, "state": "submodule_skipped"}
    # Walk relative to directory descriptors and refuse symlinks at every level.
    # Fail closed on platforms without the required safe-open primitives.
    if not (os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")):
        return {**result, "state": "safe_open_unavailable"}
    parts = PurePosixPath(path).parts
    if not parts or PurePosixPath(path).is_absolute() or any(p in {"..", "."} for p in parts):
        return {**result, "state": "unreadable"}
    descriptors = []
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in parts[:-1]:
            info = os.stat(part, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                return {**result, "state": "symlink_skipped"}
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            return {**result, "state": "symlink_skipped"}
        if not stat.S_ISREG(info.st_mode):
            return {**result, "state": "not_regular"}
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=directory)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            return {**result, "state": "not_regular"}
        result["bytes"] = before.st_size
        if before.st_size > maximum:
            return {**result, "state": "too_large"}
        digest, size = hashlib.sha256(), 0
        while True:
            block = os.read(fd, min(65536, maximum - size + 1))
            if not block:
                break
            size += len(block)
            if size > maximum:
                return {**result, "state": "too_large"}
            digest.update(block)
        after = os.fstat(fd)
        fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if fingerprint(before) != fingerprint(after) or size != before.st_size:
            return {**result, "state": "changed_while_reading"}
        return {**result, "state": "hashed", "sha256": digest.hexdigest()}
    except OSError as exc:
        state = "missing" if exc.errno in {errno.ENOENT, errno.ENOTDIR} else "symlink_skipped" if exc.errno == errno.ELOOP else "unreadable"
        return {**result, "state": state}
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def distribution(counter, limit):
    ordered = sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    return {"items": [{"name": name, "count": count} for name, count in ordered[:limit]],
            "groups_omitted": max(0, len(ordered) - limit)}


def inventory(root, maximum_evidence, maximum_bytes):
    before, entries, token_before = git_state(root)
    matches = {kind: [] for kind in CATEGORIES}
    top, extensions, types = Counter(), Counter(), Counter()
    candidates = []
    for path, item in sorted(entries.items()):
        parts = PurePosixPath(path).parts
        top[parts[0] if len(parts) > 1 else "(root files)"] += 1
        extensions[PurePosixPath(path).suffix.lower() or "(no extension)"] += 1
        kind = "symlinks" if "120000" in item["modes"] else "submodules" if "160000" in item["modes"] else "files"
        types[kind] += 1
        found = categories(path)
        for category in found:
            matches[category].append(path)
        if found:
            candidates.append(path)
    evidence = [hash_evidence(root, path, entries[path], maximum_bytes)
                for path in candidates[:maximum_evidence]]
    after, _entries_after, token_after = git_state(root)
    consistent = token_before == token_after and not any(
        item["state"] == "changed_while_reading" for item in evidence)
    return {"schema_version": 1, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "git": before,
            "tracked": {"count": len(entries), "types": {k: types[k] for k in ("files", "symlinks", "submodules")},
                        "top_level": distribution(top, 30), "extensions": distribution(extensions, 20)},
            "signals": {kind: {"count": len(paths), "paths": paths[:PATH_LIMIT],
                               "paths_omitted": max(0, len(paths) - PATH_LIMIT)} for kind, paths in matches.items()},
            "evidence": evidence,
            "limits": {"max_evidence": maximum_evidence, "max_file_bytes": maximum_bytes,
                       "path_list_limit": PATH_LIMIT, "evidence_candidates": len(candidates),
                       "evidence_omitted": max(0, len(candidates) - len(evidence))},
            "snapshot": {"consistent": consistent,
                         "state": "stable_at_checks" if consistent else "changed_during_collection",
                         "checks": ["HEAD", "branch", "tracked_index", "worktree_porcelain", "hashed_file_read_stability"],
                         "ending_head": after["head"], "ending_branch": after["branch"],
                         "limitations": "Non-atomic worktree observation; file content may change without changing Git status, and changes reverted between checks may be undetected."},
            "scope": {"network_used": False, "project_code_executed": False,
                      "file_contents_exported": False, "authors_exported": False,
                      "untracked_paths_exported": False, "quality_score": None,
                      "interpretation": "Path presence does not prove valid configuration, test execution, coverage, security or release readiness."}}


def cell(value):
    text = json.dumps(value, ensure_ascii=True) if isinstance(value, str) else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;")


def markdown(report):
    state, tracked = report["git"], report["tracked"]
    lines = ["# Repository inventory", "", "Offline tracked-path inventory; no project tests were run.", "",
             f"- HEAD: {cell(state['head'])}", f"- Branch: {cell(state['branch'])}",
             f"- Detached HEAD: {state['detached']}", f"- Worktree dirty: {state['worktree']['dirty']}",
             f"- Snapshot: {report['snapshot']['state']}", f"- Tracked paths: {tracked['count']}",
             "", "## Working tree", "", "| Status | Count |", "|---|---:|"]
    for key in ("staged", "unstaged", "conflicts", "untracked"):
        lines.append(f"| {key} | {state['worktree'][key]} |")
    lines += ["", "Untracked paths are counted only; submodule worktrees are not inspected.",
              "", "Tracked changes (bounded):", "", "| Relative path | Git status |", "|---|---|"]
    for item in state["worktree"]["tracked_changes"]:
        lines.append(f"| {cell(item['path'])} | {cell(item['status'])} |")
    lines += ["", f"Tracked change paths omitted: {state['worktree']['tracked_changes_omitted']}.",
              "", "## Tracked structure", "", "| Top-level group | Tracked paths |", "|---|---:|"]
    for item in tracked["top_level"]["items"]:
        lines.append(f"| {cell(item['name'])} | {item['count']} |")
    lines += ["", f"Top-level groups omitted: {tracked['top_level']['groups_omitted']}.",
              "", "| Extension | Tracked paths |", "|---|---:|"]
    for item in tracked["extensions"]["items"]:
        lines.append(f"| {cell(item['name'])} | {item['count']} |")
    lines += ["", f"Extension groups omitted: {tracked['extensions']['groups_omitted']}.",
              "", "## Path signals", "", "| Category | Tracked matches | Listed paths |", "|---|---:|---|"]
    for kind, signal in report["signals"].items():
        lines.append(f"| {kind} | {signal['count']} | {'; '.join(cell(p) for p in signal['paths'])} |")
    lines += ["", "## Bounded working-file evidence", "", "| Relative path | State | Bytes | SHA-256 |", "|---|---|---:|---|"]
    for item in report["evidence"]:
        lines.append(f"| {cell(item['path'])} | {item['state']} | {item.get('bytes', '')} | {item.get('sha256', '')} |")
    limits = report["limits"]
    lines += ["", f"Evidence limit: {limits['max_evidence']} paths, {limits['max_file_bytes']} bytes per file; "
              f"{limits['evidence_omitted']} candidates omitted. Category paths are capped at {PATH_LIMIT}.",
              "", "## Interpretation", "", report["scope"]["interpretation"], "",
              report["snapshot"]["limitations"], "",
              "File hashes refer to current working files, not HEAD blobs. Relative paths and branch names may still be sensitive.", ""]
    return "\n".join(lines)


def is_within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_reports(root, destination, report):
    if destination:
        out = Path(destination).expanduser().resolve()
    else:
        temp_root = Path(tempfile.gettempdir()).resolve()
        if is_within(temp_root, root):
            raise InventoryError("System temporary directory is inside the repository; choose an external --out-dir")
        out = Path(tempfile.mkdtemp(prefix="repo-inventory-", dir=temp_root))
    if is_within(out, root):
        raise InventoryError("Output directory must be outside the repository")
    targets = [out / "inventory.json", out / "inventory.md"]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise InventoryError("Report already exists; choose a new output directory")
    payloads = [json.dumps(report, ensure_ascii=True, indent=2) + "\n", markdown(report)]
    created = []
    try:
        out.mkdir(parents=True, exist_ok=True)
        for target, payload in zip(targets, payloads):
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                created.append(target)
                handle.write(payload)
    except OSError:
        for target in created:
            target.unlink(missing_ok=True)
        raise InventoryError("Could not create both reports without overwriting existing files") from None
    return targets


def bounded_positive(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if not 1 <= number <= 100000000:
        raise argparse.ArgumentTypeError("must be between 1 and 100000000")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Local Git working tree (or its subdirectory)")
    parser.add_argument("--out-dir", help="External output directory; default: new system temporary directory")
    parser.add_argument("--max-evidence", type=bounded_positive, default=MAX_EVIDENCE)
    parser.add_argument("--max-file-bytes", type=bounded_positive, default=MAX_FILE_BYTES)
    args = parser.parse_args()
    try:
        root = repo_root(args.repo)
        report = inventory(root, args.max_evidence, args.max_file_bytes)
        outputs = write_reports(root, args.out_dir, report)
    except (InventoryError, OSError, ValueError) as exc:
        print(f"repo_inventory: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"reports": [str(p) for p in outputs],
                      "snapshot_consistent": report["snapshot"]["consistent"],
                      "worktree_dirty": report["git"]["worktree"]["dirty"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
