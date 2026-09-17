#!/usr/bin/env python3
"""技术债标记盘点：汇总代码里的 TODO / FIXME / HACK / XXX / BUG / DEPRECATED 等标记，结合 git blame 给出年龄与作者。纯标准库。

用法：
  python3 todo_scan.py [目录] [--no-blame] [--json] [--md report.md] [--top 30]
"""
import argparse, collections, datetime as dt, json, os, re, subprocess, sys

GIT = os.environ.get("GIT_BIN", "git")
TAGS = ["FIXME", "BUG", "HACK", "XXX", "TODO", "DEPRECATED", "OPTIMIZE", "REVIEW", "TEMP", "WORKAROUND"]
PAT = re.compile(r"(?:#|//|/\*|\*|--|<!--|;|\"\"\"|''')\s*\b(" + "|".join(TAGS) + r")\b[:(\s-]*(?:\(([^)]*)\))?[:\s-]*(.*)", re.I)
SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "__pycache__", ".next", "target", ".idea", ".vscode", "coverage"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".go", ".java", ".kt", ".rb", ".php", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".swift", ".scala",
            ".sh", ".bash", ".sql", ".yml", ".yaml", ".toml", ".html", ".vue", ".css", ".scss", ".lua", ".ex", ".exs", ".dart", ".m", ".mm", ".tf"}


def blame_line(root, path, line):
    try:
        out = subprocess.run([GIT, "-C", root, "blame", "-L", f"{line},{line}", "--porcelain", "--", path], capture_output=True, text=True, timeout=10).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None, None
    author = re.search(r"^author (.+)$", out, re.M)
    ts = re.search(r"^author-time (\d+)$", out, re.M)
    if not ts:
        return None, None
    return (author.group(1) if author else None), dt.datetime.fromtimestamp(int(ts.group(1)))


def main():
    ap = argparse.ArgumentParser(description="技术债标记盘点")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--no-blame", action="store_true", help="不查 git blame（更快）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", help="写 Markdown 报告到文件")
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    is_git = subprocess.run([GIT, "-C", root, "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode == 0
    use_blame = is_git and not a.no_blame
    items = []
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if os.path.splitext(fn)[1] not in CODE_EXT:
                continue
            p = os.path.join(r, fn)
            try:
                lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                m = PAT.search(line)
                if not m:
                    continue
                tag = m.group(1).upper()
                rel = os.path.relpath(p, root)
                item = {"file": rel, "line": i, "tag": tag, "owner": (m.group(2) or "").strip() or None, "text": m.group(3).strip()[:120]}
                if use_blame:
                    author, when = blame_line(root, rel, i)
                    item["author"] = author
                    item["age_days"] = (dt.datetime.now() - when).days if when else None
                    item["date"] = when.date().isoformat() if when else None
                items.append(item)
    by_tag = collections.Counter(x["tag"] for x in items)
    by_dir = collections.Counter(x["file"].split("/")[0] if "/" in x["file"] else "." for x in items)
    by_author = collections.Counter(x.get("author") or "?" for x in items) if use_blame else collections.Counter()
    ages = [x["age_days"] for x in items if x.get("age_days") is not None]
    oldest = sorted([x for x in items if x.get("age_days") is not None], key=lambda x: -x["age_days"])[:a.top]
    prio = {"FIXME": 0, "BUG": 0, "HACK": 1, "XXX": 1, "WORKAROUND": 1, "TEMP": 1, "TODO": 2, "DEPRECATED": 2, "OPTIMIZE": 3, "REVIEW": 3}
    urgent = sorted(items, key=lambda x: (prio.get(x["tag"], 3), -(x.get("age_days") or 0)))[:a.top]
    summary = {"total": len(items), "by_tag": dict(by_tag.most_common()), "by_dir": dict(by_dir.most_common(15)), "by_author": dict(by_author.most_common(10)),
               "median_age_days": (sorted(ages)[len(ages) // 2] if ages else None), "over_180_days": sum(1 for d in ages if d > 180)}
    if a.json:
        print(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=2)); return
    L = [f"# 技术债标记盘点（{os.path.basename(root)}，{dt.date.today()}）", "",
         f"共 {len(items)} 处标记" + (f"；中位年龄 {summary['median_age_days']} 天，超过半年的 {summary['over_180_days']} 处" if ages else "") + "。", "",
         "## 按类型", "", "| 类型 | 数量 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in by_tag.most_common()] + ["", "## 按目录（前 15）", "", "| 目录 | 数量 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in by_dir.most_common(15)]
    if use_blame:
        L += ["", "## 按作者（前 10，按 blame）", "", "| 作者 | 数量 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in by_author.most_common(10)]
        L += ["", f"## 最老的 {len(oldest)} 处", "", "| 年龄(天) | 类型 | 位置 | 内容 |", "|---|---|---|---|"] + [f"| {x['age_days']} | {x['tag']} | `{x['file']}:{x['line']}` | {x['text'] or '-'} |" for x in oldest]
    L += ["", f"## 建议优先处理的 {len(urgent)} 处（FIXME/BUG > HACK/XXX/WORKAROUND > TODO，同级按年龄）", "", "| 类型 | 位置 | 内容 | 作者 |", "|---|---|---|---|"] + [f"| {x['tag']} | `{x['file']}:{x['line']}` | {x['text'] or '-'} | {x.get('author') or x.get('owner') or '-'} |" for x in urgent]
    L += ["", "## 处理建议", "", "- 每处标记要么变成工单（附链接写回注释），要么当场修掉，要么删掉注释；超过半年没人动的 TODO 通常已经不是计划而是遗迹。",
          "- 新增标记统一写法 `TODO(owner, #工单): 说明`，便于本工具归属与追踪。", "- 把本报告接进 CI 每周产出一次，跟踪总量与「超过半年」两个数字。"]
    out = "\n".join(L)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(out + "\n"); print(f"已写入 {os.path.abspath(a.md)}")
    else:
        print(out)


if __name__ == "__main__":
    main()
