#!/usr/bin/env python3
"""代码热点与知识集中度分析：用 git 历史找出改动最频繁 × 体量最大的文件（热点）、只有一个人懂的目录（bus factor）、总是一起改的文件对（隐性耦合）。纯标准库，只读 git。

用法：
  python3 git_hotspots.py [--since 12.months] [--top 20] [--path src/] [--json] [--md report.md]
"""
import argparse, collections, itertools, json, math, os, subprocess, sys

GIT = os.environ.get("GIT_BIN", "git")
SKIP = (".lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", ".min.js", ".map", ".snap", ".svg", ".png", ".jpg")


def git(*args):
    r = subprocess.run([GIT, *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args[:2])} 失败：{r.stderr.strip()}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser(description="代码热点分析")
    ap.add_argument("--since", default="12.months")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--path", default=".")
    ap.add_argument("--min-pair", type=int, default=5, help="共同修改次数阈值")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md")
    a = ap.parse_args()
    log = git("log", f"--since={a.since}", "--format=%x01%an", "--name-only", "--no-merges", "--", a.path)
    commits, cur_author, cur_files = [], None, []
    for line in log.splitlines():
        if line.startswith("\x01"):
            if cur_files:
                commits.append((cur_author, cur_files))
            cur_author, cur_files = line[1:].strip(), []
        elif line.strip() and not line.endswith(SKIP):
            cur_files.append(line.strip())
    if cur_files:
        commits.append((cur_author, cur_files))
    if not commits:
        sys.exit("该时间范围内没有提交")
    changes, authors = collections.Counter(), collections.defaultdict(collections.Counter)
    pairs = collections.Counter()
    for author, files in commits:
        for f in files:
            changes[f] += 1; authors[f][author] += 1
        if len(files) <= 30:
            for x, y in itertools.combinations(sorted(set(files)), 2):
                pairs[(x, y)] += 1
    # 文件行数
    loc = {}
    for f in changes:
        p = os.path.join(a.path, f) if a.path != "." else f
        if os.path.isfile(f):
            try:
                with open(f, "rb") as fh:
                    loc[f] = sum(1 for _ in fh)
            except OSError:
                pass
    hot = []
    for f, n in changes.items():
        if f not in loc:
            continue  # 已删除的文件不算热点
        score = n * math.log2(loc[f] + 1)
        top_author, top_n = authors[f].most_common(1)[0]
        hot.append({"file": f, "changes": n, "loc": loc[f], "score": round(score, 1), "authors": len(authors[f]), "main_author": top_author, "main_share": round(top_n / n * 100)})
    hot.sort(key=lambda r: -r["score"])
    # 目录级 bus factor
    dir_auth = collections.defaultdict(collections.Counter)
    for f, ac in authors.items():
        d = f.split("/")[0] if "/" in f else "."
        for au, n in ac.items():
            dir_auth[d][au] += n
    bus = []
    for d, ac in dir_auth.items():
        total = sum(ac.values())
        top = ac.most_common(1)[0]
        # 覆盖 50% 改动所需最少人数
        acc, k = 0, 0
        for _, n in ac.most_common():
            acc += n; k += 1
            if acc >= total / 2:
                break
        bus.append({"dir": d, "changes": total, "authors": len(ac), "bus_factor": k, "top_author": top[0], "top_share": round(top[1] / total * 100)})
    bus.sort(key=lambda r: (r["bus_factor"], -r["changes"]))
    coupled = [{"a": x, "b": y, "together": n, "ratio": round(n / min(changes[x], changes[y]) * 100)} for (x, y), n in pairs.most_common(200)
               if n >= a.min_pair and os.path.dirname(x) != os.path.dirname(y)]
    coupled.sort(key=lambda r: (-r["ratio"], -r["together"]))
    out = {"commits": len(commits), "files": len(changes), "hotspots": hot[:a.top], "bus_factor": bus[:a.top], "coupled": coupled[:a.top]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2)); return
    L = [f"# 代码热点报告（最近 {a.since}，{len(commits)} 个提交，{len(changes)} 个文件）", "",
         f"## 热点文件 Top {min(a.top, len(hot))}（改动次数 × log2 行数）", "", "| 分数 | 改动 | 行数 | 作者数 | 主要作者(占比) | 文件 |", "|---|---|---|---|---|---|"]
    L += [f"| {r['score']} | {r['changes']} | {r['loc']} | {r['authors']} | {r['main_author']} ({r['main_share']}%) | `{r['file']}` |" for r in hot[:a.top]]
    L += ["", "## 知识集中度（目录级 bus factor：覆盖一半改动所需人数，越小越危险）", "", "| bus factor | 目录 | 改动 | 作者数 | 主要作者(占比) |", "|---|---|---|---|---|"]
    L += [f"| {r['bus_factor']} | `{r['dir']}` | {r['changes']} | {r['authors']} | {r['top_author']} ({r['top_share']}%) |" for r in bus[:a.top]]
    L += ["", f"## 跨目录隐性耦合（共同修改 ≥ {a.min_pair} 次，按耦合率）", "", "| 耦合率 | 共同修改 | 文件 A | 文件 B |", "|---|---|---|---|"]
    L += [f"| {r['ratio']}% | {r['together']} | `{r['a']}` | `{r['b']}` |" for r in coupled[:a.top]] or ["（无）"]
    L += ["", "## 怎么用", "", "- 热点文件：改得多又大的文件是缺陷密度最高的地方，优先补测试、拆分职责；评审这些文件的 PR 要更仔细。",
          "- bus factor = 1 的目录：只有一个人在改，安排结对/轮换与文档，避免离职即失忆。",
          "- 高耦合率的文件对：改 A 几乎总要改 B，说明边界划错了，考虑合并或抽出共享抽象。"]
    text = "\n".join(L)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text + "\n"); print(f"已写入 {os.path.abspath(a.md)}")
    else:
        print(text)


if __name__ == "__main__":
    main()
