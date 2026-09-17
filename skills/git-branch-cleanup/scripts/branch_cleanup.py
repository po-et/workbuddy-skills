#!/usr/bin/env python3
"""git 分支清理助手：列出已合并、长期不动、远端已删除的分支，生成可审阅的删除命令。只读，不执行删除。

用法：
  python3 branch_cleanup.py                       # 本地分支，基线自动检测（main/master/develop）
  python3 branch_cleanup.py --remote origin --stale-days 90
  python3 branch_cleanup.py --json
  python3 branch_cleanup.py --script cleanup.sh   # 生成删除脚本，人工确认后再执行
"""
import argparse, datetime as dt, json, os, re, subprocess, sys

GIT = os.environ.get("GIT_BIN", "git")
PROTECTED = re.compile(r"^(main|master|develop|dev|release/.*|hotfix/.*|prod|production|staging)$")


def git(*args):
    r = subprocess.run([GIT, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def detect_base(explicit):
    if explicit:
        return explicit
    for c in ("origin/main", "origin/master", "origin/develop", "main", "master", "develop"):
        if subprocess.run([GIT, "rev-parse", "--verify", "-q", c], capture_output=True).returncode == 0:
            return c
    sys.exit("找不到基线分支，请 --base 指定")


def main():
    ap = argparse.ArgumentParser(description="git 分支清理助手（只读）")
    ap.add_argument("--base")
    ap.add_argument("--remote", help="同时分析该远端的分支，如 origin")
    ap.add_argument("--stale-days", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--script", help="生成删除脚本路径")
    a = ap.parse_args()
    base = detect_base(a.base)
    current = git("rev-parse", "--abbrev-ref", "HEAD")
    git("fetch", "--prune", a.remote) if a.remote else None
    now = dt.datetime.now(dt.timezone.utc)
    merged_local = set(l.strip().lstrip("* ") for l in git("branch", "--merged", base).splitlines())
    rows = []
    fmt = "%(refname:short)%09%(committerdate:iso8601)%09%(authorname)%09%(upstream:short)%09%(upstream:track)"
    for line in git("for-each-ref", "--format=" + fmt, "refs/heads").splitlines():
        name, date, author, upstream, track = (line.split("\t") + ["", "", "", ""])[:5]
        d = dt.datetime.fromisoformat(date.replace(" ", "T", 1).replace(" ", "")) if date else now
        age = (now - d.astimezone(dt.timezone.utc)).days
        ahead = git("rev-list", "--count", f"{base}..{name}")
        rows.append({"branch": name, "remote": False, "age_days": age, "author": author, "ahead": int(ahead or 0),
                     "merged": name in merged_local, "upstream": upstream or None, "gone": "[gone]" in track,
                     "protected": bool(PROTECTED.match(name)) or name == current, "current": name == current})
    if a.remote:
        merged_remote = set(l.strip() for l in git("branch", "-r", "--merged", base).splitlines())
        for line in git("for-each-ref", "--format=%(refname:short)%09%(committerdate:iso8601)%09%(authorname)", f"refs/remotes/{a.remote}").splitlines():
            name, date, author = (line.split("\t") + ["", ""])[:3]
            short = name.split("/", 1)[1] if "/" in name else name
            if short == "HEAD":
                continue
            d = dt.datetime.fromisoformat(date.replace(" ", "T", 1).replace(" ", "")) if date else now
            age = (now - d.astimezone(dt.timezone.utc)).days
            ahead = git("rev-list", "--count", f"{base}..{name}")
            rows.append({"branch": name, "remote": True, "age_days": age, "author": author, "ahead": int(ahead or 0),
                         "merged": name in merged_remote, "upstream": None, "gone": False, "protected": bool(PROTECTED.match(short)) or name == base, "current": False})
    for r in rows:
        if r["protected"]:
            r["verdict"], r["reason"] = "keep", "受保护/当前分支/基线"
        elif r["merged"] or r["ahead"] == 0:
            r["verdict"], r["reason"] = "delete", "已合并到基线（无独有提交）"
        elif r["gone"]:
            r["verdict"], r["reason"] = "review", "远端分支已删除，本地仍有未合并提交"
        elif r["age_days"] >= a.stale_days:
            r["verdict"], r["reason"] = "review", f"超过 {a.stale_days} 天无提交，且有 {r['ahead']} 个未合并提交"
        else:
            r["verdict"], r["reason"] = "keep", "活跃"
    order = {"delete": 0, "review": 1, "keep": 2}
    rows.sort(key=lambda r: (order[r["verdict"]], -r["age_days"]))
    if a.json:
        print(json.dumps({"base": base, "branches": rows}, ensure_ascii=False, indent=2)); return
    print(f"基线 {base}；本地分支 {sum(1 for r in rows if not r['remote'])} 个" + (f"，远端 {a.remote} 分支 {sum(1 for r in rows if r['remote'])} 个" if a.remote else ""))
    for v, title in (("delete", "可删除（已合并）"), ("review", "需确认（陈旧或远端已删）"), ("keep", "保留")):
        sel = [r for r in rows if r["verdict"] == v]
        print(f"\n## {title}（{len(sel)}）")
        for r in sel[:60]:
            print(f"  {'远端 ' if r['remote'] else ''}{r['branch']:<40} {r['age_days']:>4} 天  +{r['ahead']:<3} {r['author'][:16]:<16} {r['reason']}")
        if len(sel) > 60:
            print(f"  … 共 {len(sel)} 个")
    cmds = []
    for r in rows:
        if r["verdict"] == "delete":
            if r["remote"]:
                cmds.append(f"git push {a.remote} --delete {r['branch'].split('/', 1)[1]}")
            else:
                cmds.append(f"git branch -d {r['branch']}")
    for r in rows:
        if r["verdict"] == "review" and not r["remote"]:
            cmds.append(f"# 需确认：git branch -D {r['branch']}   # {r['reason']}")
    if a.script:
        with open(a.script, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env bash\nset -e\n# 由 branch_cleanup.py 生成；逐行审阅后执行。已合并分支用 -d（安全），其余为注释。\n" + "\n".join(cmds) + "\n")
        print(f"\n删除脚本已写入 {os.path.abspath(a.script)}（{sum(1 for c in cmds if not c.startswith('#'))} 条可执行命令）")
    elif cmds:
        print("\n建议命令（未执行）：")
        for c in cmds[:30]:
            print("  " + c)


if __name__ == "__main__":
    main()
