#!/usr/bin/env python3
"""采集两个 Git 引用之间的差异。走本地 git，不需要 token。

用法:
    python3 collect_diff.py --repo ~/code/app --base v1.4.2 --head v1.5.0 \
        --out out/diff.json
"""
import argparse
import json
import os
import re
import subprocess
import sys

ISSUE_PATTERNS = [r"#(\d+)", r"\b([A-Z][A-Z0-9]+-\d+)\b"]
SEP, FSEP = "\x1e", "\x1f"


def run(cmd, cwd, check=True):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} 失败:\n{p.stderr.strip()}")
    return p.stdout


def ref_exists(repo, ref):
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                          cwd=repo, capture_output=True, text=True).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", required=True, help="基线：当前线上版本")
    ap.add_argument("--head", required=True, help="目标：准备发布的版本")
    ap.add_argument("--out", default="out/diff.json")
    a = ap.parse_args()

    repo = os.path.expanduser(a.repo)
    if not os.path.isdir(os.path.join(repo, ".git")):
        sys.exit(f"不是 git 仓库: {repo}")
    for ref in (a.base, a.head):
        if not ref_exists(repo, ref):
            sys.exit(f"引用不存在: {ref}　（先 git fetch --tags？）")

    rng = f"{a.base}..{a.head}"

    # 文件改动，含重命名与删除
    files = []
    for line in run(["git", "diff", "--name-status", "-M", rng], repo).splitlines():
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        status = cols[0][0]
        path = cols[-1]
        files.append({"status": status, "path": path,
                      "old_path": cols[1] if status == "R" and len(cols) == 3 else None})

    # 增删行
    added = deleted = 0
    for line in run(["git", "diff", "--numstat", rng], repo).splitlines():
        c = line.split("\t")
        if len(c) == 3:
            added += int(c[0]) if c[0].isdigit() else 0
            deleted += int(c[1]) if c[1].isdigit() else 0

    # 提交
    fmt = FSEP.join(["%h", "%an", "%aI", "%s"]) + SEP
    commits, issues = [], set()
    for rec in run(["git", "log", rng, f"--pretty=format:{fmt}", "--no-merges"],
                   repo).split(SEP):
        if not rec.strip():
            continue
        p = rec.strip("\n").split(FSEP)
        if len(p) < 4:
            continue
        short, author, date, subject = p[:4]
        found = []
        for pat in ISSUE_PATTERNS:
            found += re.findall(pat, subject)
        issues.update(found)
        commits.append({"short": short, "author": author, "date": date,
                        "subject": subject.strip(), "issues": found})

    payload = {
        "repo": os.path.basename(os.path.abspath(repo)),
        "base": a.base, "head": a.head,
        "summary": {
            "commits": len(commits),
            "authors": sorted({c["author"] for c in commits}),
            "files_changed": len(files),
            "added": added, "deleted": deleted,
            "added_files": sum(1 for f in files if f["status"] == "A"),
            "deleted_files": sum(1 for f in files if f["status"] == "D"),
            "renamed_files": sum(1 for f in files if f["status"] == "R"),
            "issues": sorted(issues),
        },
        "files": files,
        "commits": commits,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    s = payload["summary"]
    print(f"✓ {a.out}: {s['commits']} commits / {s['files_changed']} 文件 "
          f"(+{s['added']}/-{s['deleted']}) / 删除 {s['deleted_files']} 个文件 "
          f"/ {len(s['authors'])} 位作者")


if __name__ == "__main__":
    main()
