#!/usr/bin/env python3
"""Build a handoff from reported state; inspect artifacts, never execute commands."""
import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

KEYS = {"schema_version", "title", "goal", "reported_status", "decisions", "open_items",
        "next_item_id", "artifacts", "verifications", "unknowns", "suggested_skills"}
SECRET = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|"
                    r"(?i:\b(?:password|api_key|access_token|authorization)\b\s*[:=]\s*\S+)")


class InputError(ValueError):
    pass


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise InputError("重复 JSON 字段")
        result[key] = value
    return result


def string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field} 必须为非空字符串")
    if SECRET.search(value):
        raise InputError(f"{field} 疑似含凭证；先脱敏再生成")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise InputError(f"{field} 含控制字符")
    return value


def structure(value, required, optional, field):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise InputError(f"{field} 字段不符合契约")


def timestamp(value, field):
    string(value, field)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InputError(f"{field} 必须为带时区的 ISO 时间") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise InputError(f"{field} 必须带时区")
    if dt > datetime.now(timezone.utc):
        raise InputError(f"{field} 不能在未来")


def sha(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", value):
        raise InputError(f"{field} 必须为 SHA-256")
    return value.lower()


def inspect_artifact(root, item, max_bytes):
    structure(item, {"path", "role"}, {"sha256"}, "artifact")
    path_text = string(item["path"], "artifact.path")
    string(item["role"], "artifact.role")
    expected = sha(item["sha256"], "artifact.sha256") if "sha256" in item else None
    rel = Path(path_text)
    if rel.is_absolute() or ".." in rel.parts:
        raise InputError("artifact.path 必须为 root 内的相对路径")
    target = root / rel
    for part in [target, *target.parents]:
        if part == root:
            break
        if part.is_symlink():
            return {**item, "check": "symlink_not_read", "observed_sha256": None}
    if not target.is_file():
        return {**item, "check": "missing_or_not_file", "observed_sha256": None}
    if target.stat().st_size > max_bytes:
        return {**item, "check": "size_limit", "observed_sha256": None}
    h = hashlib.sha256()
    with target.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()
    return {**item, "observed_sha256": actual,
            "check": "hash_match" if expected == actual else "hash_mismatch" if expected else "hash_recorded"}


def build(data, root, max_bytes=16777216):
    structure(data, KEYS, set(), "state")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise InputError("schema_version 必须为 1")
    for key in ("title", "goal", "reported_status"):
        string(data[key], key)
    if data["reported_status"] not in {"in_progress", "blocked", "completed"}:
        raise InputError("reported_status 不在枚举中")
    for key in ("decisions", "open_items", "artifacts", "verifications", "unknowns", "suggested_skills"):
        if not isinstance(data[key], list):
            raise InputError(f"{key} 必须为数组")
    for key in ("unknowns", "suggested_skills"):
        for v in data[key]:
            string(v, key)
    for item in data["decisions"]:
        structure(item, {"decision", "reason", "source"}, set(), "decision")
        for k, v in item.items():
            string(v, "decision." + k)
    ids = set()
    for item in data["open_items"]:
        structure(item, {"id", "action", "acceptance"}, {"owner"}, "open_item")
        for k, v in item.items():
            string(v, "open_item." + k)
        if item["id"] in ids:
            raise InputError("open_items.id 重复")
        ids.add(item["id"])
    if ids:
        if data["next_item_id"] not in ids:
            raise InputError("next_item_id 必须指向一个未完项")
    elif data["next_item_id"] is not None:
        raise InputError("没有未完项时 next_item_id 必须为 null")
    artifacts = [inspect_artifact(root, item, max_bytes) for item in data["artifacts"]]
    artifact_map = {item["path"]: item for item in artifacts}
    if len(artifact_map) != len(artifacts):
        raise InputError("artifact.path 重复")
    issues = [f"文件 {a['path']}：{a['check']}" for a in artifacts
              if a["check"] not in {"hash_match", "hash_recorded"}]
    verification_rows = []
    for v in data["verifications"]:
        structure(v, {"command", "reported_result", "reported_status"}, {"observed_at", "evidence_path"}, "verification")
        for key in ("command", "reported_result", "reported_status"):
            string(v[key], "verification." + key)
        if v["reported_status"] not in {"passed", "failed", "not_run"}:
            raise InputError("verification.reported_status 不在枚举中")
        if "observed_at" in v:
            timestamp(v["observed_at"], "verification.observed_at")
        checks = []
        if v["reported_status"] != "not_run" and "observed_at" not in v:
            checks.append("missing_observation_time")
        if "evidence_path" in v:
            string(v["evidence_path"], "verification.evidence_path")
            a = artifact_map.get(v["evidence_path"])
            if not a or a["check"] not in {"hash_match", "hash_recorded"}:
                checks.append("evidence_unavailable")
        elif v["reported_status"] != "not_run":
            checks.append("missing_evidence_file")
        if v["reported_status"] == "failed":
            checks.append("reported_failure")
        issues.extend("验证记录：" + c for c in checks)
        verification_rows.append({**v, "record_issues": checks, "executed_by_builder": False})
    if data["reported_status"] == "completed" and ids:
        issues.append("状态称已完成，但仍有未完项")
    if data["reported_status"] == "completed" and not data["verifications"]:
        issues.append("状态称已完成，但没有验证记录")
    return {**data, "artifacts": artifacts, "verifications": verification_rows,
            "generated_at": datetime.now(timezone.utc).isoformat(), "artifact_root": str(root),
            "issues": issues, "record_integrity": "needs_review" if issues else "consistent",
            "scope": "状态由输入提供；仅核对文件与记录完整性。没有执行验证命令，也没有证明任务完成。"}


def md(value):
    return str(value).replace("\\", "\\\\").replace("`", "\\`").replace("|", "\\|").replace("\n", " / ")


def markdown(r):
    lines = [f"# 交接：{md(r['title'])}", "", md(r["scope"]), "",
             "## 目标与输入状态", md(r["goal"]), f"输入状态：{r['reported_status']}；记录完整性：{r['record_integrity']}",
             f"文件根目录：{md(r['artifact_root'])}", "", "## 已定决策"]
    lines += [f"- {md(d['decision'])}；理由：{md(d['reason'])}；来源：{md(d['source'])}" for d in r["decisions"]]
    lines += ["", "## 未完项与下一步"]
    lines += [f"- {'下一步 ' if d['id'] == r['next_item_id'] else ''}{md(d['id'])}：{md(d['action'])}；验收：{md(d['acceptance'])}；负责人：{md(d.get('owner', '待确认'))}" for d in r["open_items"]]
    lines += ["", "## 文件核对（未嵌入内容）"]
    lines += [f"- {md(a['path'])}：{md(a['role'])}；{a['check']}；SHA-256：{a['observed_sha256'] or '未读取'}" for a in r["artifacts"]]
    lines += ["", "## 输入提供的验证记录（命令未执行）"]
    lines += [f"- {md(v['command'])} → {md(v['reported_result'])}；{v['reported_status']}；时间：{md(v.get('observed_at', '缺失'))}；证据：{md(v.get('evidence_path', '缺失'))}；记录问题：{', '.join(v['record_issues']) or '无'}" for v in r["verifications"]]
    lines += ["", "## 坑与未知"] + ["- " + md(x) for x in r["unknowns"]]
    lines += ["", "## 建议技能"] + ["- " + md(x) for x in r["suggested_skills"]]
    lines += ["", "## 需复核的问题"] + ["- " + md(x) for x in r["issues"]]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("state", type=Path)
    p.add_argument("--root", type=Path, required=True, help="artifact paths resolve under this directory")
    p.add_argument("--out", type=Path, help="default: a new OS temporary directory")
    p.add_argument("--max-artifact-bytes", type=int, default=16777216)
    args = p.parse_args()
    try:
        if args.max_artifact_bytes < 1:
            raise InputError("max-artifact-bytes 必须大于 0")
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise InputError("root 不是目录")
        data = json.loads(args.state.read_text("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError("非有限 JSON 数字")))
        result = build(data, root, args.max_artifact_bytes)
        out = args.out.resolve() if args.out else Path(tempfile.mkdtemp(prefix="handoff-"))
        if out == root or root in out.parents:
            raise InputError("报告请输出到 artifact root 之外，避免改动被交接的工作区")
        if any((out / name).exists() for name in ("handoff.json", "handoff.md")):
            raise InputError("输出已存在，请指定新目录")
        out.mkdir(parents=True, exist_ok=True)
        (out / "handoff.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
        (out / "handoff.md").write_text(markdown(result), "utf-8")
        print(json.dumps({"markdown": str(out / "handoff.md"), "json": str(out / "handoff.json"),
                          "record_integrity": result["record_integrity"], "issue_count": len(result["issues"])}, ensure_ascii=False))
        return 1 if result["issues"] else 0
    except (ValueError, OSError, TypeError) as e:
        # JSON decoder errors include positions, never raw document excerpts.
        print("输入或路径错误：" + (str(e) if isinstance(e, InputError) else type(e).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
