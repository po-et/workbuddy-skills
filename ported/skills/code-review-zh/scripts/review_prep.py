#!/usr/bin/env python3
"""代码评审预处理：把"机器能查的"先查完，评审者只看判断题。

零依赖。对比 <base>...HEAD（三点 diff，即与共同祖先比），输出：
  改动概览（文件/行数/提交）、遗留物（console.log/print/debugger/TODO）、疑似密钥、
  超长行、巨型改动文件、跨目录散弹式修改、有代码改动却没改测试、重复新增代码块、提交里的工单引用。
用法：python3 review_prep.py --repo . --base main [--out out/review.json] [--print]
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

MAX_DIFF = 400_000
LEFTOVER = re.compile(r"\b(console\.(log|debug)|debugger;?|print\(|pdb\.set_trace\(|breakpoint\(\)|binding\.pry|var_dump\(|dd\(|System\.out\.println)\b")
TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
SECRET = re.compile(r"(AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|(?i:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})")
TEST_HINT = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|(_test|\.test|\.spec|_spec)\.[a-z]+$|^test_", re.I)
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".kt", ".rb", ".rs", ".php", ".cs", ".swift", ".c", ".cc", ".cpp", ".h", ".scala", ".vue"}
ISSUE_RE = re.compile(r"(#\d+|[A-Z][A-Z0-9]+-\d+|![0-9]+)")


def git(args, repo):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{p.stderr.strip()}")
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", default=None, help="固定点：分支/tag/提交，默认 origin/main 或 main")
    ap.add_argument("--out"); ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    base = a.base
    if not base:
        for cand in ("origin/main", "main", "origin/master", "master"):
            if subprocess.run(["git", "rev-parse", "--verify", "-q", cand], cwd=a.repo, capture_output=True).returncode == 0:
                base = cand; break
    if not base:
        sys.exit("找不到默认基线，请用 --base 指定")
    git(["rev-parse", "--verify", base], a.repo)
    rng = f"{base}...HEAD"
    commits = [l for l in git(["log", "--oneline", f"{base}..HEAD"], a.repo).splitlines() if l]
    numstat = git(["diff", "--numstat", rng], a.repo).strip()
    if not numstat:
        sys.exit(f"{rng} 没有差异（基线可能就是 HEAD）")
    files = []
    for line in numstat.splitlines():
        ad, de, path = line.split("\t", 2)
        files.append({"path": path, "added": int(ad) if ad.isdigit() else 0, "deleted": int(de) if de.isdigit() else 0})
    diff = git(["diff", "-U0", "--no-color", rng], a.repo)
    truncated = len(diff.encode()) > MAX_DIFF
    diff = diff.encode()[:MAX_DIFF].decode(errors="ignore")

    findings = defaultdict(list)
    cur, win, dup_index = None, [], defaultdict(list)
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]; win = []; continue
        if line.startswith("+++ /dev/null") or line.startswith("---") or line.startswith("@@") or line.startswith("diff "):
            continue
        if not line.startswith("+"):
            continue
        s = line[1:]
        if LEFTOVER.search(s):
            findings["leftovers"].append({"file": cur, "line": s.strip()[:120]})
        if TODO.search(s):
            findings["todos"].append({"file": cur, "line": s.strip()[:120]})
        if SECRET.search(s):
            findings["secrets"].append({"file": cur, "line": re.sub(r"['\"][^'\"]{8,}['\"]", "'<REDACTED>'", s.strip())[:120]})
        if len(s) > 160 and cur and Path(cur).suffix in CODE_EXT:
            findings["long_lines"].append({"file": cur, "length": len(s)})
        norm = re.sub(r"\s+", " ", s).strip()
        if len(norm) >= 20 and cur and Path(cur).suffix in CODE_EXT:
            win.append(norm)
            if len(win) >= 6:
                key = hashlib.md5("\n".join(win[-6:]).encode()).hexdigest()
                dup_index[key].append(cur)
    # CLI 脚本里的 print 是正当输出：新增行含 argparse / __main__ 的文件不报 print(
    cli_files = {f for f in {x["file"] for x in findings["leftovers"]} if f and re.search(r"argparse|__main__", "".join(l for l in diff.split(f"+++ b/{f}", 1)[-1].split("\n+++ b/")[0].splitlines()))}
    findings["leftovers"] = [x for x in findings["leftovers"] if not (x["file"] in cli_files and x["line"].lstrip().startswith("print("))]
    dups = [{"files": sorted(set(v)), "occurrences": len(v)} for v in dup_index.values() if len(v) >= 2]
    dups = sorted({json.dumps(d, ensure_ascii=False): d for d in dups}.values(), key=lambda d: -d["occurrences"])[:10]

    code_files = [f for f in files if Path(f["path"]).suffix in CODE_EXT and not TEST_HINT.search(f["path"])]
    test_files = [f for f in files if TEST_HINT.search(f["path"])]
    big = [f for f in files if f["added"] + f["deleted"] > 300]
    top_dirs = Counter((Path(f["path"]).parts[0] if len(Path(f["path"]).parts) > 1 else ".") for f in files)
    shotgun = len(files) >= 15 and len(top_dirs) >= 5
    issues = sorted({m for c in commits for m in ISSUE_RE.findall(c)})

    signals = []
    if code_files and not test_files:
        signals.append(f"改了 {len(code_files)} 个源码文件但没有改任何测试文件")
    if big:
        signals.append("巨型改动文件：" + ", ".join(f"{f['path']}(+{f['added']}/-{f['deleted']})" for f in big[:5]))
    if shotgun:
        signals.append(f"散弹式修改嫌疑：{len(files)} 个文件横跨 {len(top_dirs)} 个顶层目录（{', '.join(d for d, _ in top_dirs.most_common(6))}）")
    if findings["secrets"]:
        signals.append(f"疑似硬编码密钥 {len(findings['secrets'])} 处（已脱敏显示）")
    if findings["leftovers"]:
        signals.append(f"调试遗留 {len(findings['leftovers'])} 处")
    if dups:
        signals.append(f"重复新增代码块 {len(dups)} 组")
    if not issues:
        signals.append("提交信息里没有工单/需求引用，Spec 轴需要用户提供来源")
    if truncated:
        signals.append("diff 超过 400KB 已截断，启发式结果不完整")

    result = {"base": base, "range": rng, "commits": commits, "stats": {"files": len(files), "added": sum(f["added"] for f in files), "deleted": sum(f["deleted"] for f in files),
              "code_files": len(code_files), "test_files": len(test_files)}, "issues": issues, "signals": signals,
              "findings": {k: v[:40] for k, v in findings.items()}, "duplicates": dups, "files": files}
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    if a.print or not a.out:
        print(f"范围 {rng}：{len(commits)} 提交，{len(files)} 文件，+{result['stats']['added']}/-{result['stats']['deleted']}；工单引用：{', '.join(issues) or '无'}")
        for s in signals:
            print("  ⚑ " + s)
        for k, label in (("secrets", "疑似密钥"), ("leftovers", "调试遗留"), ("todos", "TODO/FIXME")):
            for f in findings[k][:5]:
                print(f"  [{label}] {f['file']}: {f['line']}")
        if a.out:
            print(f"✓ 详情写入 {a.out}")


if __name__ == "__main__":
    main()
