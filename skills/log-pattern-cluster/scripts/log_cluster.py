#!/usr/bin/env python3
"""日志模板聚类：把海量日志按「模板」归并（数字、ID、IP、路径、时间等变量位抽象成占位符），输出出现次数最多/最少的模式。纯标准库。

用法：
  python3 log_cluster.py app.log [more.log ...] [--top 30] [--rare 20] [--level ERROR] [--json]
  cat app.log | python3 log_cluster.py -
"""
import argparse, collections, json, re, sys

SUBS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TS>"),
    (re.compile(r"\d{2}:\d{2}:\d{2}(?:[.,]\d+)?"), "<TIME>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}|\d{2}/[A-Za-z]{3}/\d{4}"), "<DATE>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<UUID>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b[0-9a-f]{24,64}\b", re.I), "<HASH>"),
    (re.compile(r"https?://\S+"), "<URL>"),
    (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "<EMAIL>"),
    (re.compile(r"(?<![\w/])(?:/[\w.\-]+){2,}"), "<PATH>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<HEX>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?(ms|s|us|ns|kb|mb|gb|b|%)\b", re.I), "<NUM><UNIT>"),
    (re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?![A-Za-z])"), "<NUM>"),
    (re.compile(r"\"[^\"]*\""), "<STR>"),
    (re.compile(r"'[^']*'"), "<STR>"),
]
LEVEL = re.compile(r"\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL|PANIC)\b")
PREFIX = re.compile(r"^(?:<TS>|<DATE> <TIME>|<TIME>)?\s*(?:\[[^\]]*\]\s*)*(?:\w+\s+)?")  # 去掉行首时间戳/线程/级别之类


def template(line):
    s = line.strip()
    for pat, rep in SUBS:
        s = pat.sub(rep, s)
    s = re.sub(r"\s+", " ", s)
    return s


def main():
    ap = argparse.ArgumentParser(description="日志模板聚类")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--rare", type=int, default=15, help="列出最少见的 N 个模板（新出现的异常常在这里）")
    ap.add_argument("--level", help="只看某级别及以上，如 WARN / ERROR")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    order = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    norm = lambda l: {"WARNING": "WARN", "CRITICAL": "FATAL", "PANIC": "FATAL"}.get(l, l)
    min_level = order.index(norm(a.level.upper())) if a.level else -1
    counts, examples, levels, total, kept = collections.Counter(), {}, collections.defaultdict(collections.Counter), 0, 0
    for f in a.files:
        fh = sys.stdin if f == "-" else open(f, encoding="utf-8", errors="replace")
        for line in fh:
            if not line.strip():
                continue
            total += 1
            lv = LEVEL.search(line)
            lvn = norm(lv.group(1)) if lv else None
            if min_level >= 0 and (lvn is None or order.index(lvn) < min_level):
                continue
            kept += 1
            t = template(line)
            counts[t] += 1
            examples.setdefault(t, line.strip()[:200])
            if lvn:
                levels[t][lvn] += 1
        if f != "-":
            fh.close()
    common = counts.most_common(a.top)
    rare = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))[:a.rare]
    if a.json:
        print(json.dumps({"total_lines": total, "analyzed": kept, "templates": len(counts),
                          "top": [{"count": c, "template": t, "example": examples[t], "levels": dict(levels[t])} for t, c in common],
                          "rare": [{"count": c, "template": t, "example": examples[t]} for t, c in rare]}, ensure_ascii=False, indent=2)); return
    print(f"共 {total} 行，分析 {kept} 行，归并为 {len(counts)} 个模板（压缩比 {kept / max(len(counts), 1):.0f}:1）")
    print(f"\n## 最常见的 {len(common)} 个模板")
    for t, c in common:
        lv = ",".join(f"{k}:{v}" for k, v in levels[t].most_common(2))
        print(f"  {c:>8}  {t[:140]}" + (f"   [{lv}]" if lv else ""))
    print(f"\n## 最少见的 {len(rare)} 个模板（新出现的错误常在这里）")
    for t, c in rare:
        print(f"  {c:>8}  {examples[t][:140]}")
    err = sum(c for t, c in counts.items() if levels[t].get("ERROR", 0) + levels[t].get("FATAL", 0) > 0)
    if err:
        print(f"\n含 ERROR/FATAL 的行：{err}；用 --level ERROR 只看错误模板")


if __name__ == "__main__":
    main()
