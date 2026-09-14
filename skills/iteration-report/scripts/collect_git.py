#!/usr/bin/env python3
"""采集 Git 提交数据，输出结构化 JSON。

只依赖本地 git CLI，不需要任何 token —— 内网 GitLab / 自建 Gitea 同样可用。

用法:
    python3 collect_git.py --repo ~/code/foo --repo ~/code/bar \
        --since 2026-09-08 --until 2026-09-14 --out out/git.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

# 从提交信息里提取工单号。按需增删。
ISSUE_PATTERNS = [
    r"#(\d+)",                      # GitHub / Gitea:  #123
    r"\b([A-Z][A-Z0-9]+-\d+)\b",    # Jira:            PROJ-123
    r"!(\d+)",                      # GitLab MR:       !123
]

SEP = "\x1e"   # record separator
FSEP = "\x1f"  # field separator


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed in {cwd}:\n{p.stderr.strip()}")
    return p.stdout


def extract_issues(text):
    found = []
    for pat in ISSUE_PATTERNS:
        found.extend(re.findall(pat, text))
    # 去重保序
    seen, out = set(), []
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def collect_repo(repo, since, until, branch):
    repo = os.path.expanduser(repo)
    if not os.path.isdir(os.path.join(repo, ".git")):
        raise RuntimeError(f"不是 git 仓库: {repo}")

    name = os.path.basename(os.path.abspath(repo))
    fmt = FSEP.join(["%H", "%h", "%an", "%ae", "%aI", "%s", "%b", "%P"]) + SEP

    rev = branch if branch else "HEAD"
    raw = run(
        ["git", "log", rev, f"--since={since}", f"--until={until} 23:59:59",
         f"--pretty=format:{fmt}", "--no-merges"],
        repo,
    )

    commits = []
    for rec in raw.split(SEP):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split(FSEP)
        if len(parts) < 8:
            continue
        full, short, author, email, date, subject, body, parents = parts[:8]

        stat = run(["git", "show", "--numstat", "--format=", full], repo)
        files, added, deleted = 0, 0, 0
        for line in stat.splitlines():
            cols = line.split("\t")
            if len(cols) != 3:
                continue
            files += 1
            if cols[0].isdigit():
                added += int(cols[0])
            if cols[1].isdigit():
                deleted += int(cols[1])

        msg = f"{subject}\n{body}"
        commits.append({
            "repo": name,
            "hash": full,
            "short": short,
            "author": author,
            "email": email,
            "date": date,
            "subject": subject.strip(),
            "body": body.strip(),
            "issues": extract_issues(msg),
            "files_changed": files,
            "added": added,
            "deleted": deleted,
            "is_merge": len(parents.split()) > 1,
            # 提交信息质量：过短或纯通用词 → 需要从 diff 反推
            "msg_quality": msg_quality(subject.strip(), body.strip()),
        })
    return commits


GENERIC = {"fix", "update", "updates", "change", "changes", "wip", "tmp",
           "test", "commit", "修改", "更新", "修复", "提交", "调整", "优化"}


def msg_quality(subject, body):
    s = subject.strip()
    if not s:
        return "empty"
    if s.lower().strip(" .:：") in GENERIC:
        return "generic"
    if len(s) < 8 and not body:
        return "too_short"
    return "ok"


def risk_signals(commits):
    """识别风险信号，供第 3 步重组时参考。"""
    signals = []
    by_file = defaultdict(set)
    for c in commits:
        if c["files_changed"] > 30:
            signals.append({
                "type": "large_change",
                "commit": c["short"], "repo": c["repo"],
                "detail": f"单次改动 {c['files_changed']} 个文件",
            })
        low = (c["subject"] + " " + c["body"]).lower()
        for kw in ("revert", "hotfix", "rollback", "回滚", "紧急"):
            if kw in low:
                signals.append({
                    "type": "hotfix_or_revert",
                    "commit": c["short"], "repo": c["repo"],
                    "detail": f"提交信息命中关键词 '{kw}'",
                })
                break
    return signals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", required=True, help="仓库路径，可重复")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    ap.add_argument("--until", required=True, help="YYYY-MM-DD")
    ap.add_argument("--branch", default=None, help="指定分支，默认当前 HEAD")
    ap.add_argument("--out", default="out/git.json")
    a = ap.parse_args()

    all_commits, errors = [], []
    for r in a.repo:
        try:
            all_commits.extend(collect_repo(r, a.since, a.until, a.branch))
        except Exception as e:                      # noqa: BLE001
            errors.append({"repo": r, "error": str(e)})
            print(f"[warn] {e}", file=sys.stderr)

    authors = sorted({c["author"] for c in all_commits})
    payload = {
        "window": {"since": a.since, "until": a.until},
        "repos": a.repo,
        "errors": errors,
        "summary": {
            "commits": len(all_commits),
            "authors": len(authors),
            "author_list": authors,
            "files_changed": sum(c["files_changed"] for c in all_commits),
            "added": sum(c["added"] for c in all_commits),
            "deleted": sum(c["deleted"] for c in all_commits),
            "issues": sorted({i for c in all_commits for i in c["issues"]}),
            "poor_messages": sum(1 for c in all_commits if c["msg_quality"] != "ok"),
        },
        "risk_signals": risk_signals(all_commits),
        "commits": all_commits,
    }

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    s = payload["summary"]
    print(f"✓ {a.out}: {s['commits']} commits / {s['authors']} authors / "
          f"{s['poor_messages']} 条提交信息需反推 / {len(payload['risk_signals'])} 个风险信号")


if __name__ == "__main__":
    main()
