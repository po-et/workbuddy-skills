#!/usr/bin/env python3
"""从 git 提交历史生成 Keep a Changelog 风格的发布说明草稿。

零依赖、零 token：解析 Conventional Commits（type(scope)!: subject），按类型分组，
每条附短 hash 与作者；不规范的提交进「其他」而不是丢掉；数据缺口明写。

用法：
  python3 build_changelog.py --repo . [--from v1.2.0] [--to HEAD] [--version 1.3.0] [--lang zh|en] [--out CHANGELOG-draft.md]
  不给 --from 时自动取最近一个 tag；仓库没有 tag 时取全部历史（会提示）。
"""
import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path

SEP, FSEP = "\x1e", "\x1f"
CC_RE = re.compile(r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s*(?P<subject>.+)$")
ISSUE_RE = re.compile(r"(#\d+|[A-Z][A-Z0-9]+-\d+)")

GROUPS = OrderedDict([
    ("breaking", {"zh": "⚠ 破坏性变更", "en": "BREAKING CHANGES", "types": set()}),
    ("feat", {"zh": "新增", "en": "Added", "types": {"feat", "feature"}}),
    ("fix", {"zh": "修复", "en": "Fixed", "types": {"fix", "bugfix", "hotfix"}}),
    ("perf", {"zh": "性能", "en": "Performance", "types": {"perf"}}),
    ("refactor", {"zh": "重构", "en": "Changed", "types": {"refactor", "style"}}),
    ("docs", {"zh": "文档", "en": "Documentation", "types": {"docs", "doc"}}),
    ("deps", {"zh": "构建与依赖", "en": "Build & Dependencies", "types": {"build", "deps", "ci", "chore"}}),
    ("test", {"zh": "测试", "en": "Tests", "types": {"test", "tests"}}),
    ("other", {"zh": "其他（未按规范书写的提交）", "en": "Other (non-conventional commits)", "types": set()}),
])
HIDE_DEFAULT = {"deps", "test"}


def git(args, repo):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{p.stderr.strip()}")
    return p.stdout


def latest_tag(repo):
    p = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], cwd=repo, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def commits(repo, rng):
    fmt = FSEP.join(["%h", "%H", "%an", "%ad", "%s", "%b"]) + SEP
    out = git(["log", "--no-merges", "--date=short", f"--format={fmt}", *rng], repo)
    res = []
    for rec in out.split(SEP):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        short, full, author, d, subject, body = (rec.split(FSEP) + [""] * 6)[:6]
        res.append({"short": short, "author": author, "date": d, "subject": subject.strip(), "body": body.strip()})
    return res


def classify(c, with_issues=True):
    m = CC_RE.match(c["subject"])
    breaking = "BREAKING CHANGE" in c["body"] or "BREAKING-CHANGE" in c["body"]
    if m:
        t = m.group("type").lower()
        scope, subject = m.group("scope"), m.group("subject").strip()
        breaking = breaking or bool(m.group("bang"))
        group = next((g for g, spec in GROUPS.items() if t in spec["types"]), "other")
    else:
        scope, subject, group = None, c["subject"], "other"
    issues = sorted(set(ISSUE_RE.findall(c["subject"] + " " + c["body"]))) if with_issues else []
    return {**c, "group": group, "breaking": breaking, "scope": scope, "subject": subject, "issues": issues}


def render(items, version, lang, rng_desc, include_hidden, with_author):
    L = "zh" if lang == "zh" else "en"
    lines = [f"## [{version}] - {date.today().isoformat()}", ""]
    if lang == "zh":
        lines.append(f"<sub>范围：{rng_desc}　提交 {len(items)} 条（不含 merge）</sub>")
    else:
        lines.append(f"<sub>Range: {rng_desc} · {len(items)} commits (merges excluded)</sub>")
    lines.append("")
    by = OrderedDict((g, []) for g in GROUPS)
    for it in items:
        if it["breaking"]:
            by["breaking"].append(it)
        by[it["group"]].append(it)
    non_cc = len(by["other"])
    for g, arr in by.items():
        if not arr or (g in HIDE_DEFAULT and not include_hidden):
            continue
        lines.append(f"### {GROUPS[g][L]}")
        for it in arr:
            scope = f"**{it['scope']}**: " if it["scope"] else ""
            refs = (" (" + ", ".join(it["issues"]) + ")") if it["issues"] else ""
            who = f" — {it['author']}" if with_author else ""
            lines.append(f"- {scope}{it['subject']}{refs} `{it['short']}`{who}")
        lines.append("")
    hidden = sum(len(by[g]) for g in HIDE_DEFAULT) if not include_hidden else 0
    notes = []
    if hidden:
        notes.append(f"已隐藏 {hidden} 条构建/依赖/测试类提交（--include-chore 可显示）" if lang == "zh" else f"{hidden} build/deps/test commits hidden (--include-chore to show)")
    if non_cc:
        notes.append(f"{non_cc} 条提交未按 Conventional Commits 书写，已归入「其他」，需人工改写成用户视角的描述" if lang == "zh" else f"{non_cc} commits are not Conventional Commits; listed under Other and need rewording")
    if notes:
        lines.append("<!-- " + "；".join(notes) + " -->")
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--from", dest="from_ref")
    ap.add_argument("--to", dest="to_ref", default="HEAD")
    ap.add_argument("--version", default="Unreleased")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--include-chore", action="store_true", help="显示构建/依赖/测试类提交")
    ap.add_argument("--author", action="store_true", help="每条附作者")
    ap.add_argument("--no-issues", action="store_true", help="不提取 #123 / PROJ-1 形式的工单号（提交里常引用外部 issue 时用）")
    ap.add_argument("--out")
    a = ap.parse_args()

    frm = a.from_ref or latest_tag(a.repo)
    if frm:
        rng, desc = [f"{frm}..{a.to_ref}"], f"{frm}..{a.to_ref}"
    else:
        rng, desc = [a.to_ref], f"全部历史..{a.to_ref}（仓库没有 tag）"
        print("提示：仓库没有 tag，使用全部历史；建议用 --from 指定起点", file=sys.stderr)
    items = [classify(c, not a.no_issues) for c in commits(a.repo, rng)]
    if not items:
        print("该范围内没有提交", file=sys.stderr)
        sys.exit(2)
    md = render(items, a.version, a.lang, desc, a.include_chore, a.author)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md, "utf-8")
        print(f"✓ {a.out}：{len(items)} 条提交，{sum(1 for i in items if i['group']=='other')} 条未按规范书写")
    else:
        print(md)


if __name__ == "__main__":
    main()
