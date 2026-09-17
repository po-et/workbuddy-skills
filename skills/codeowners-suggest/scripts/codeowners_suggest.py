#!/usr/bin/env python3
"""根据 git 历史建议 CODEOWNERS：按目录统计最近 N 个月每位作者的改动次数，给出主要维护者与候补，生成 CODEOWNERS 草稿。纯标准库，只读 git。

用法：
  python3 codeowners_suggest.py [--since 12.months] [--depth 2] [--min-share 25] [--map authors.json] [--out CODEOWNERS]
  --map：{"Git 作者名": "@github-handle"} 的映射；没有映射的作者以 "# 待映射: 名字" 注释形式输出。
"""
import argparse, collections, json, os, subprocess, sys

GIT = os.environ.get("GIT_BIN", "git")


def git(*args):
    r = subprocess.run([GIT, *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git 失败：{r.stderr.strip()}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser(description="CODEOWNERS 建议")
    ap.add_argument("--since", default="12.months")
    ap.add_argument("--depth", type=int, default=2, help="目录聚合深度")
    ap.add_argument("--min-share", type=float, default=25, help="占比 ≥ 此百分比才列为 owner")
    ap.add_argument("--max-owners", type=int, default=3)
    ap.add_argument("--min-changes", type=int, default=5, help="目录改动少于此数不生成规则")
    ap.add_argument("--map", help="作者名到 @handle 的 JSON 映射文件")
    ap.add_argument("--out", help="写入文件（如 .github/CODEOWNERS）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    mapping = json.load(open(a.map, encoding="utf-8")) if a.map else {}
    log = git("log", f"--since={a.since}", "--no-merges", "--format=%x01%an", "--name-only")
    author, stats = None, collections.defaultdict(collections.Counter)
    for line in log.splitlines():
        if line.startswith("\x01"):
            author = line[1:].strip()
        elif line.strip() and author:
            parts = line.strip().split("/")
            d = "/".join(parts[:a.depth]) if len(parts) > 1 else "/"
            stats[d][author] += 1
            if len(parts) > 1 and a.depth > 1:
                stats[parts[0]][author] += 1  # 上一级也累计，便于回退规则
    rules, unmapped = [], set()
    for d, ac in sorted(stats.items(), key=lambda kv: kv[0]):
        total = sum(ac.values())
        if total < a.min_changes:
            continue
        owners = [(au, n) for au, n in ac.most_common(a.max_owners) if n / total * 100 >= a.min_share]
        if not owners:
            owners = ac.most_common(1)
        handles = []
        for au, n in owners:
            h = mapping.get(au)
            if not h:
                unmapped.add(au); h = f"<{au}>"
            handles.append((h, au, round(n / total * 100)))
        rules.append({"pattern": "*" if d == "/" else f"/{d}/", "changes": total, "authors": len(ac), "owners": handles})
    # 父目录与子目录 owner 相同则去掉子目录规则
    keep = []
    for r in rules:
        parent = next((p for p in rules if p is not r and r["pattern"].startswith(p["pattern"]) and p["pattern"] != "*"), None)
        if parent and [h for h, _, _ in parent["owners"]] == [h for h, _, _ in r["owners"]]:
            continue
        keep.append(r)
    if a.json:
        print(json.dumps({"rules": keep, "unmapped_authors": sorted(unmapped)}, ensure_ascii=False, indent=2)); return
    L = [f"# CODEOWNERS 草稿：由 git 历史（最近 {a.since}）自动建议，请人工确认后使用。",
         "# 规则：目录内改动占比 ≥ %d%% 的作者列为 owner；<名字> 表示尚未映射到 @handle。" % a.min_share, ""]
    for r in keep:
        L.append(f"# {r['changes']} 次改动，{r['authors']} 位作者；" + "，".join(f"{au} {s}%" for _, au, s in r["owners"]))
        L.append(f"{r['pattern']:<40} " + " ".join(h for h, _, _ in r["owners"]))
        L.append("")
    if unmapped:
        L.append("# 待映射作者（用 --map authors.json 提供 {\"作者名\": \"@handle\"}）：" + "，".join(sorted(unmapped)))
    text = "\n".join(L)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n"); print(f"已写入 {os.path.abspath(a.out)}")
    else:
        print(text)


if __name__ == "__main__":
    main()
