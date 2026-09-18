#!/usr/bin/env python3
"""提交信息规范检查：对一个提交范围按 Conventional Commits 校验，统计 type 分布。纯标准库。

用法：
  python3 git_commit_lint.py                                  # 默认范围 origin/main..HEAD
  python3 git_commit_lint.py --range main..HEAD --strict       # 有 error 则退出码 1（CI 门禁）
  python3 git_commit_lint.py --message-file .git/COMMIT_EDITMSG  # commit-msg 钩子校验单条
git 可执行路径从环境变量 GIT_BIN 读取（默认 git）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
HEADER = re.compile(r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^()]*)\))?(?P<bang>!)?:\s(?P<desc>.+)$")
SCOPE_OK = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
BREAKING = re.compile(r"^BREAKING[ -]CHANGE\s*:", re.M)
BANNED_TOKENS = ["wip", "tmp", "temp", "fixup", "squash", "asdf", "xxx", "临时", "先提一下", "调试代码"]
LOW_INFO = {"fix", "fixes", "fix bug", "fix bugs", "bugfix", "bug fix", "update", "updates", "update code",
            "change", "changes", "misc", "cleanup", "clean up", "test", "tests", "minor", "minor fix",
            "refactor", "refactor code", "improve", "improvements", "修改", "修改代码", "更新", "更新代码",
            "提交", "提交代码", "修复bug", "修复 bug", "优化", "优化代码", "调整", "重构", "初始化"}
SEP, REC = "\x1f", "\x1e"


def width(s):
    """显示宽度，CJK 全角字符算 2 列（git log 里的实际占位）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def git(args, repo):
    exe = os.environ.get("GIT_BIN", "git")
    try:
        return subprocess.run([exe] + args, cwd=repo, capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit(f"找不到 git 可执行文件 {exe!r}；用 GIT_BIN 指定路径，例如 "
                 "GIT_BIN=/usr/local/bin/git python3 git_commit_lint.py")


def read_commits(rng, repo, limit):
    args = ["log", f"--format=%H{SEP}%h{SEP}%an{SEP}%aI{SEP}%P{SEP}%B{REC}"]
    if limit:
        args.append(f"-n{limit}")
    args.append(rng)
    r = git(args, repo)
    if r.returncode != 0:
        msg = next((l for l in (r.stderr or "").splitlines() if l.strip()), "未知错误").strip()
        sys.exit(f"git log {rng} 失败：{msg}\n"
                 "提示：本地没有 origin/main 时改用 --range main..HEAD 或 --range HEAD~10..HEAD；"
                 "浅克隆的 CI 需要 fetch-depth 0。")
    out = []
    for rec in r.stdout.split(REC):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split(SEP)
        if len(parts) < 6:
            continue
        h, short, author, date, parents = parts[:5]
        raw = SEP.join(parts[5:]).strip("\n")
        out.append({"sha": h, "short": short, "author": author, "date": date,
                    "parents": parents.split(), "subject": raw.split("\n")[0] if raw else "", "raw": raw})
    return out


def strip_comments(text):
    lines = []
    for ln in text.splitlines():
        if ln.startswith("#"):
            continue
        if ln.startswith("# ------------------------ >8"):
            break
        lines.append(ln)
    return "\n".join(lines).strip("\n")


def lint(c, opt):
    """返回 [(level, rule, message, fix)]；level 为 error / warn / info。"""
    out = []
    raw = (c.get("raw") or c.get("subject") or "").strip("\n")
    lines = raw.split("\n")
    subject = lines[0] if lines else ""
    body = "\n".join(lines[2:]) if len(lines) > 2 else ""
    if len(lines) > 1 and lines[1].strip() and len(c.get("parents", [])) <= 1:
        out.append(("error", "CM007", "标题与正文之间缺少空行",
                    "第 2 行必须是空行，否则 git log --oneline 会把整段当成标题"))
    if len(c.get("parents", [])) > 1:
        if not opt["allow_merge"]:
            out.append(("warn", "CM012", "merge 提交", "用 rebase 保持线性历史，或加 --allow-merge 忽略"))
        return out
    if not subject.strip():
        out.append(("error", "CM006", "提交信息为空", "写成 type(scope): 一句话说明本次改动"))
        return out
    m = HEADER.match(subject)
    if not m:
        out.append(("error", "CM001", f"首行不符合 Conventional Commits 格式 {subject[:60]!r}",
                    f"写成 <type>(<scope>): <说明>，type 取 {'/'.join(opt['types'][:5])} 等；冒号后要有一个空格"))
        return out
    t, scope, bang, desc = m.group("type"), m.group("scope"), bool(m.group("bang")), m.group("desc")
    if t not in opt["types"]:
        low = t.lower()
        hint = f"；是不是想写 {low}？" if low in opt["types"] else ""
        out.append(("error", "CM002", f"type {t!r} 不在白名单 {'/'.join(opt['types'])}",
                    f"换成白名单里的 type{hint}"))
    if scope is not None:
        if not scope.strip():
            out.append(("error", "CM003", "scope 为空括号", "要么写具体模块名，要么整个括号去掉"))
        elif not SCOPE_OK.match(scope):
            out.append(("error", "CM003", f"scope {scope!r} 格式不合法",
                        "scope 用小写字母、数字与 . _ - /，例如 (api)、(user-center)"))
    if width(subject) > opt["max_subject"]:
        out.append(("error", "CM004", f"首行显示宽度 {width(subject)} 列，超过 {opt['max_subject']}（中文算 2 列）",
                    "把细节挪到正文，首行只留一句结论"))
    if desc.rstrip().endswith((".", "。")):
        out.append(("error", "CM005", "首行以句号结尾", "去掉结尾的句号"))
    if len(desc.strip()) < 5 and not re.search(r"[一-鿿]{3,}", desc):
        out.append(("warn", "CM013", f"主题过短 {desc!r}", "一句话说清改了什么、为什么改"))
    norm = re.sub(r"[\s.。!！]+$", "", desc.strip().lower())
    if norm in LOW_INFO:
        out.append(("error", "CM010", f"主题 {desc.strip()!r} 没有信息量",
                    "写清楚改了什么对象、达成什么效果，例如 fix(auth): 刷新 token 过期时间的判断逻辑"))
    for w in opt["banned"]:
        pat = rf"\b{re.escape(w)}\b" if w.isascii() else re.escape(w)
        if re.search(pat, desc, re.I):
            out.append(("error", "CM010", f"主题含禁止词 {w!r}",
                        "临时提交在推之前用 git rebase -i 合并改写掉"))
            break
    for i, ln in enumerate(body.split("\n"), 1):
        if width(ln) > opt["max_body"] and not ln.lstrip().startswith(("http", "```", "|")):
            out.append(("warn", "CM008", f"正文第 {i} 行显示宽度 {width(ln)} 列，超过 {opt['max_body']}",
                        "正文按 72–100 列折行，便于 git log 阅读"))
            break
    has_break = bool(BREAKING.search(body))
    if has_break and not bang:
        out.append(("error", "CM009", "正文有 BREAKING CHANGE 但首行没有 ! 标记",
                    "写成 feat(api)!: ...，让破坏性变更在 git log 一行里就能看见"))
    if bang and not has_break:
        out.append(("warn", "CM009", "首行有 ! 但正文没有 BREAKING CHANGE 段落",
                    "正文加一段 BREAKING CHANGE: 说明影响与迁移方式"))
    if re.match(r"^[A-Z][a-z]", desc):
        out.append(("warn", "CM011", f"主题首字母大写 {desc.split()[0]!r}",
                    "Conventional Commits 约定主题小写开头"))
    if t == "revert" and not re.search(r'^This reverts commit [0-9a-f]{7,40}|^revert', body + subject, re.I | re.M):
        out.append(("info", "CM014", "revert 提交建议保留 git revert 自动生成的正文",
                    "正文里写明 This reverts commit <sha> 以便追溯"))
    return out


def main():
    ap = argparse.ArgumentParser(description="提交信息规范检查（Conventional Commits）")
    ap.add_argument("--range", default="origin/main..HEAD", help="提交范围，默认 origin/main..HEAD")
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--message-file", help="校验单个提交信息文件（commit-msg 钩子用）")
    ap.add_argument("--max-count", type=int, default=0, help="最多检查多少条提交")
    ap.add_argument("--types", default=",".join(TYPES), help="type 白名单，逗号分隔")
    ap.add_argument("--max-subject", type=int, default=72)
    ap.add_argument("--max-body", type=int, default=100)
    ap.add_argument("--banned", default=",".join(BANNED_TOKENS), help="禁止词，逗号分隔")
    ap.add_argument("--allow-merge", action="store_true", help="不对 merge 提交告警")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 error 则退出码 1（CI 门禁）")
    a = ap.parse_args()
    opt = {"types": [t.strip() for t in a.types.split(",") if t.strip()],
           "banned": [w.strip() for w in a.banned.split(",") if w.strip()],
           "max_subject": a.max_subject, "max_body": a.max_body, "allow_merge": a.allow_merge}

    if a.message_file:
        raw = strip_comments(open(a.message_file, encoding="utf-8").read())
        commits = [{"sha": "-", "short": "MSG", "author": "", "date": "", "parents": [],
                    "subject": raw.split("\n")[0] if raw else "", "body": "", "raw": raw}]
        rng = a.message_file
    else:
        commits = read_commits(a.range, a.repo, a.max_count)
        rng = a.range

    results, types_count = [], {}
    for c in commits:
        issues = lint(c, opt)
        m = HEADER.match(c["subject"])
        if m and len(c.get("parents", [])) <= 1:
            types_count[m.group("type")] = types_count.get(m.group("type"), 0) + 1
        results.append({"sha": c["short"], "author": c["author"], "date": c["date"], "subject": c["subject"],
                        "issues": [{"level": l, "rule": r, "message": msg, "fix": fx} for l, r, msg, fx in issues]})
    errors = sum(1 for r in results for i in r["issues"] if i["level"] == "error")
    warns = sum(1 for r in results for i in r["issues"] if i["level"] == "warn")
    bad = sum(1 for r in results if any(i["level"] == "error" for i in r["issues"]))

    if a.json:
        print(json.dumps({"range": rng, "commits": len(results), "errors": errors, "warns": warns,
                          "bad_commits": bad, "types": types_count, "results": results},
                         ensure_ascii=False, indent=2))
        sys.exit(1 if (a.strict and errors) else 0)

    print(f"范围 {rng} · 提交 {len(results)} 条")
    if not results:
        print("这个范围里没有提交，确认分支与 --range 是否正确。")
        sys.exit(0)
    for r in results:
        if not r["issues"]:
            print(f"  ✓ {r['sha']}  {r['subject'][:70]}")
            continue
        lv = "✗" if any(i["level"] == "error" for i in r["issues"]) else "!"
        print(f"  {lv} {r['sha']}  {r['subject'][:70]}")
        for i in r["issues"]:
            print(f"        [{i['level']}] {i['rule']} {i['message']}")
            print(f"            → {i['fix']}")
    if types_count:
        print("\n类型分布：" + "，".join(f"{k} {v}" for k, v in sorted(types_count.items(), key=lambda x: -x[1])))
    print(f"合计 error {errors} / warn {warns}，{bad}/{len(results)} 条提交需要修改")
    if errors:
        print("改法：最近一条用 git commit --amend，更早的用 git rebase -i <base> 选 reword；"
              "已推送的分支改写后需要 git push --force-with-lease，主干分支不要改写。")
    sys.exit(1 if (a.strict and errors) else 0)


if __name__ == "__main__":
    main()
