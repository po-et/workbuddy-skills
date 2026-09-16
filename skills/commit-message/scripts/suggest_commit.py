#!/usr/bin/env python3
"""从暂存区（或工作区）diff 生成 Conventional Commits 提交信息候选。

零依赖、零 token：只用 git 与正则做"确定性"的部分——改了哪些文件、类型/范围的证据、
新增/删除的符号——把判断性的措辞留给模型。输出 JSON 给模型二次加工，或 --print 直接看摘要。

用法：
  python3 suggest_commit.py --repo . [--staged|--worktree] [--lang zh|en|both] [--out out/commit.json] [--print]
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

MAX_DIFF_BYTES = 200_000

DOC_EXT = {".md", ".rst", ".txt", ".adoc"}
TEST_HINT = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|(_test|\.test|\.spec|_spec)\.[a-z]+$|^test_", re.I)
CI_HINT = re.compile(r"^\.(github|gitlab-ci|circleci|travis)|^\.gitlab-ci\.yml$|^Jenkinsfile$|^\.buildkite/", re.I)
BUILD_HINT = re.compile(r"(^|/)(package(-lock)?\.json|pnpm-lock\.yaml|yarn\.lock|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|go\.(mod|sum)|Cargo\.(toml|lock)|pom\.xml|build\.gradle(\.kts)?|Gemfile(\.lock)?|composer\.(json|lock)|Dockerfile|Makefile)$", re.I)
CONFIG_HINT = re.compile(r"\.(ya?ml|toml|ini|cfg|conf|env(\.example)?|properties)$|(^|/)\.[a-z]+rc$", re.I)
FIX_WORDS = re.compile(r"\b(fix|bug|hotfix|patch|regression|npe|null ?pointer|crash|leak|typo|correct|wrong|error|exception|edge ?case|off[- ]by[- ]one)\b", re.I)
PERF_WORDS = re.compile(r"\b(perf|performance|faster|cache|cached|memo|lazy|optimi[sz]e|throughput|latency|n\+1|batch)\b", re.I)
SYMBOL_RE = re.compile(r"^\+\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|fn|func|interface|type|struct|enum|trait|impl)\s+([A-Za-z_][A-Za-z0-9_]*)")
REMOVED_SYMBOL_RE = re.compile(r"^-\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|fn|func|interface|type|struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)")

TYPE_ZH = {"feat": "新增功能", "fix": "修复缺陷", "docs": "文档", "test": "测试", "refactor": "重构", "perf": "性能",
           "build": "构建/依赖", "ci": "CI", "chore": "杂项", "style": "格式"}


def git(args, repo):
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{p.stderr.strip()}")
    return p.stdout


def collect(repo: str, mode: str):
    base = ["diff", "--cached"] if mode == "staged" else ["diff"]
    status = git([*base, "--name-status", "-M"], repo).strip()
    untracked = []
    if mode != "staged":
        untracked = [l for l in git(["ls-files", "--others", "--exclude-standard"], repo).splitlines() if l.strip()]
        status = "\n".join([status] + [f"A\t{u}" for u in untracked]).strip()
    if not status and mode == "auto":
        return None
    files = []
    for line in status.splitlines():
        parts = line.split("\t")
        code = parts[0][0]
        path = parts[-1]
        files.append({"status": {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied"}.get(code, code),
                      "path": path, "from": parts[1] if code in "RC" and len(parts) > 2 else None})
    numstat = git([*base, "--numstat", "-M"], repo).strip()
    added = deleted = 0
    for line in numstat.splitlines():
        a, d, _ = line.split("\t", 2)
        if a.isdigit():
            added += int(a)
        if d.isdigit():
            deleted += int(d)
    diff = git([*base, "-U0", "-M", "--no-color"], repo)
    for u in untracked:
        try:
            txt = (Path(repo) / u).read_text("utf-8", errors="ignore")
        except (OSError, IsADirectoryError):
            continue
        body = "\n".join("+" + l for l in txt.splitlines()[:400])
        diff += f"\n+++ b/{u}\n{body}\n"
        added += min(len(txt.splitlines()), 400)
    truncated = len(diff.encode()) > MAX_DIFF_BYTES
    diff = diff.encode()[:MAX_DIFF_BYTES].decode(errors="ignore")
    return files, added, deleted, diff, truncated


def classify_file(path: str) -> str:
    if TEST_HINT.search(path):
        return "test"
    if CI_HINT.search(path):
        return "ci"
    if BUILD_HINT.search(path):
        return "build"
    if Path(path).suffix.lower() in DOC_EXT or path.lower().startswith(("docs/", "doc/")):
        return "docs"
    if CONFIG_HINT.search(path):
        return "config"
    return "code"


def guess_scope(paths):
    """取最常见的"有意义的目录"作为 scope：跳过 src/lib/app/pkg 这类壳目录。"""
    shells = {"src", "lib", "app", "apps", "pkg", "packages", "internal", "cmd", "skills", "scripts", "docs", "tests", "test"}
    cands = Counter()
    for p in paths:
        parts = Path(p).parts[:-1]
        for part in parts:
            if part not in shells and not part.startswith("."):
                cands[part] += 1
                break
        else:
            if len(parts) >= 2 and parts[0] in shells:
                cands[parts[1]] += 1
    if not cands:
        return None, []
    scope, n = cands.most_common(1)[0]
    return (scope if n >= max(1, len(paths) // 2) else None), [s for s, _ in cands.most_common(3)]


def analyze(files, added, deleted, diff):
    kinds = Counter(classify_file(f["path"]) for f in files)
    code_files = [f for f in files if classify_file(f["path"]) == "code"]
    added_lines = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    removed_lines = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    text_added = "\n".join(added_lines)
    new_symbols, gone_symbols = [], []
    trivial = {"main", "git", "run", "init", "setup", "test", "tests", "helper", "util", "utils", "index", "app", "cli"}
    for l in added_lines:
        m = SYMBOL_RE.match(l)
        if m and m.group(1).lower() not in trivial and m.group(1) not in new_symbols:
            new_symbols.append(m.group(1))
    for l in removed_lines:
        m = REMOVED_SYMBOL_RE.match(l)
        if m and m.group(1) not in new_symbols:
            gone_symbols.append(m.group(1))

    reasons = []
    if not code_files:
        if kinds.get("test"):
            t = "test"; reasons.append("只改了测试文件")
        elif kinds.get("docs") and len(kinds) == 1:
            t = "docs"; reasons.append("只改了文档")
        elif kinds.get("ci"):
            t = "ci"; reasons.append("只改了 CI 配置")
        elif kinds.get("build"):
            t = "build"; reasons.append("只改了构建/依赖文件")
        else:
            t = "chore"; reasons.append("只改了配置或杂项文件")
    else:
        fix_hits = len(FIX_WORDS.findall(text_added))
        perf_hits = len(PERF_WORDS.findall(text_added))
        all_new = all(f["status"] == "added" for f in code_files)
        if all_new or (new_symbols and added > deleted * 3):
            t = "feat"; reasons.append("新增文件或新增符号明显多于删除" + (f"：{', '.join(new_symbols[:5])}" if new_symbols else ""))
        elif fix_hits >= 2 and fix_hits >= perf_hits:
            t = "fix"; reasons.append(f"新增行里出现 {fix_hits} 处修复类词汇")
        elif perf_hits >= 2:
            t = "perf"; reasons.append(f"新增行里出现 {perf_hits} 处性能类词汇")
        elif added and deleted and 0.6 <= added / max(deleted, 1) <= 1.6 and not new_symbols:
            t = "refactor"; reasons.append("增删行数相当且无新符号，像重构（需人工确认行为未变）")
        else:
            t = "feat"; reasons.append("默认按功能变更处理，请核对")
    breaking = bool(gone_symbols) or any(f["status"] == "deleted" and classify_file(f["path"]) == "code" for f in files)
    if breaking:
        reasons.append("删除了对外符号或源文件，可能是破坏性变更：" + ", ".join(gone_symbols[:5]))
    return t, reasons, new_symbols, gone_symbols, breaking, kinds


def build_candidates(t, scope, files, new_symbols, breaking, lang):
    prefix = f"{t}({scope})" if scope else t
    prefix += "!" if breaking else ""
    names = [Path(f["path"]).stem for f in files][:3]
    sym = new_symbols[0] if new_symbols else None
    zh = {
        "feat": [f"新增 {sym}" if sym else f"新增 {names[0]} 相关能力", f"支持 {', '.join(names)}"],
        "fix": [f"修复 {names[0]} 中的问题", f"修正 {sym} 的边界处理" if sym else "修正错误处理"],
        "docs": [f"更新 {names[0]} 文档", "补充使用说明"],
        "test": [f"补充 {names[0]} 测试", "增加边界用例"],
        "refactor": [f"重构 {names[0]}", f"整理 {', '.join(names)} 结构"],
        "perf": [f"优化 {names[0]} 性能", "减少重复计算"],
        "build": ["更新依赖版本", "调整构建配置"],
        "ci": ["调整 CI 流水线", "更新工作流配置"],
        "chore": [f"更新 {names[0]} 配置", "整理杂项文件"],
    }[t]
    en = {
        "feat": [f"add {sym}" if sym else f"add {names[0]}", f"support {', '.join(names)}"],
        "fix": [f"fix {names[0]} issue", f"handle edge case in {sym}" if sym else "correct error handling"],
        "docs": [f"update {names[0]} docs", "clarify usage"],
        "test": [f"add {names[0]} tests", "cover edge cases"],
        "refactor": [f"restructure {names[0]}", f"tidy {', '.join(names)}"],
        "perf": [f"speed up {names[0]}", "avoid repeated work"],
        "build": ["bump dependencies", "adjust build config"],
        "ci": ["adjust CI pipeline", "update workflow config"],
        "chore": [f"update {names[0]} config", "tidy misc files"],
    }[t]
    out = []
    if lang in ("zh", "both"):
        out += [f"{prefix}: {s}" for s in zh]
    if lang in ("en", "both"):
        out += [f"{prefix}: {s}" for s in en]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="只看暂存区（默认：有暂存用暂存，否则用工作区）")
    g.add_argument("--worktree", action="store_true", help="看工作区未暂存改动")
    ap.add_argument("--lang", choices=["zh", "en", "both"], default="both")
    ap.add_argument("--out", default=None)
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()

    mode = "staged" if a.staged else ("worktree" if a.worktree else "auto")
    res = collect(a.repo, "staged" if mode in ("staged", "auto") else "worktree")
    used = "staged"
    if res is None or (mode == "auto" and not res[0]):
        res = collect(a.repo, "worktree")
        used = "worktree"
    if not res or not res[0]:
        print("没有可提交的改动（暂存区和工作区都是空的）", file=sys.stderr)
        sys.exit(2)
    files, added, deleted, diff, truncated = res
    t, reasons, new_symbols, gone_symbols, breaking, kinds = analyze(files, added, deleted, diff)
    scope, scope_cands = guess_scope([f["path"] for f in files])
    cands = build_candidates(t, scope, files, new_symbols, breaking, a.lang)
    result = {
        "source": used,
        "files": files,
        "stats": {"files": len(files), "added": added, "deleted": deleted, "kinds": dict(kinds), "diff_truncated": truncated},
        "type": {"guess": t, "zh": TYPE_ZH[t], "reasons": reasons},
        "scope": {"guess": scope, "candidates": scope_cands},
        "breaking_change_suspected": breaking,
        "new_symbols": new_symbols[:20],
        "removed_symbols": gone_symbols[:20],
        "candidates": cands,
        "body_hints": [f"{f['status']} {f['path']}" + (f" (from {f['from']})" if f.get("from") else "") for f in files][:30],
        "rules": ["subject ≤ 50 字符、祈使语气、不加句号", "body 说明 why 而不是 what", "破坏性变更用 ! 与 BREAKING CHANGE: 页脚", "工单号放页脚 Refs: #123"],
    }
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    if a.print or not a.out:
        print(f"来源：{used}　文件 {len(files)}　+{added}/-{deleted}　类型 {t}（{TYPE_ZH[t]}）　范围 {scope or '—'}" + ("　⚠ 疑似破坏性变更" if breaking else ""))
        for r in reasons:
            print(f"  依据：{r}")
        print("候选：")
        for c in cands:
            print(f"  - {c}")
        if a.out:
            print(f"✓ 详情写入 {a.out}")


if __name__ == "__main__":
    main()
