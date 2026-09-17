#!/usr/bin/env python3
"""SkillHub 差集扫描：把外部候选技能逐个查 SkillHub，判断"有没有 / 有没有中文版"。

输入（任选，可多个）：
  --clawhub <explore --json 文件>      ClawHub 榜单（slug/description/downloads）
  --github <tsv: repo\tbranch\tpath>    GitHub 仓库里的 SKILL.md 列表（名称取目录名）
  --names <文本文件，每行 slug 或名称>  手工候选
输出：CSV（candidate, source, popularity, present_en, present_zh, hits）+ 终端摘要。
判定：SkillHub 搜索结果的 slug/name 与候选的 token 重叠率 ≥ 0.6 视为"有"；命中项名称含中文视为"有中文版"。
用法：python3 tools/gap_scan.py --clawhub harvest/clawhub_downloads.json --github harvest/github_skills.tsv --out harvest/gaps.csv
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLI = str(Path.home() / ".local/bin/skillhub")
CJK = re.compile(r"[一-鿿]")
STOP = {"skill", "skills", "agent", "ai", "the", "and", "for", "with", "to", "a", "of", "zh", "cn", "en", "claude", "code", "pro", "plus", "v2", "v3", "tool", "tools", "helper", "assistant", "generator", "expert", "master"}


def tokens(s: str):
    s = re.sub(r"[^a-z0-9一-鿿]+", " ", (s or "").lower())
    return {t for t in s.split() if t and t not in STOP and len(t) > 1}


def search(q: str, limit=8):
    try:
        out = subprocess.run([CLI, "search", *q.split()[:6], "--json", "--search-limit", str(limit)], capture_output=True, text=True, timeout=25).stdout
        d = json.loads(out[out.index("{"):])
        return d.get("results") or []
    except Exception:
        return []


def judge(cand: str, results):
    ct = tokens(cand)
    if not ct:
        return False, False, []
    hits = []
    for r in results:
        name, slug = r.get("name") or "", r.get("publicSlug") or r.get("slug") or ""
        rt = tokens(slug) | tokens(name)
        if not rt:
            continue
        overlap = len(ct & rt) / len(ct)
        if overlap >= 0.6 or cand.lower().replace("-", " ") in (name.lower() + " " + slug.lower().replace("-", " ")):
            hits.append((name, slug, bool(CJK.search(name))))
    return bool(hits), any(h[2] for h in hits), hits[:4]


def load_candidates(a):
    cands = []
    if a.clawhub:
        for f in a.clawhub:
            d = json.load(open(f))
            items = d if isinstance(d, list) else (d.get("skills") or d.get("items") or d.get("results") or [])
            for it in items:
                slug = it.get("slug") or it.get("name") or ""
                st = it.get("stats") or {}
                pop = st.get("downloads") or st.get("installs") or it.get("downloads") or it.get("downloadCount") or it.get("installs") or it.get("stars") or 0
                cands.append((slug, f"clawhub:{Path(f).stem.split('_')[-1]}", pop, (it.get("description") or it.get("summary") or "")[:120]))
    if a.github:
        for f in a.github:
            for line in Path(f).read_text().splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                repo, _, path = parts[:3]
                name = Path(path).parent.name if Path(path).parent.name not in ("", ".") else repo.split("/")[-1]
                if name.startswith(".") or name in ("skills", "src", "templates", "template", "examples", "example", "docs", "tests"):
                    continue
                cands.append((name, f"github:{repo}", 0, path))
    if a.names:
        for f in a.names:
            for line in Path(f).read_text().splitlines():
                if line.strip() and not line.startswith("#"):
                    cands.append((line.strip(), f"names:{Path(f).stem}", 0, ""))
    seen, out = set(), []
    for c in cands:
        k = c[0].lower()
        if k and k not in seen:
            seen.add(k); out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clawhub", nargs="*"); ap.add_argument("--github", nargs="*"); ap.add_argument("--names", nargs="*")
    ap.add_argument("--out", required=True); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cands = load_candidates(a)
    if a.limit:
        cands = cands[:a.limit]
    print(f"候选 {len(cands)} 个，开始查 SkillHub…", file=sys.stderr)
    def work(c):
        name, src, pop, extra = c
        res = search(name.replace("-", " ").replace("_", " "))
        en, zh, hits = judge(name, res)
        return {"candidate": name, "source": src, "popularity": pop, "present_en": int(en), "present_zh": int(zh),
                "hits": " | ".join(f"{h[0]}({h[1]})" for h in hits), "extra": extra}
    rows = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, row in enumerate(ex.map(work, cands), 1):
            rows.append(row)
            if i % 50 == 0:
                print(f"  {i}/{len(cands)}", file=sys.stderr)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    n = len(rows); en = sum(r["present_en"] for r in rows); zh = sum(r["present_zh"] for r in rows)
    print(f"\n候选 {n}：SkillHub 已有 {en}（其中有中文版 {zh}）；完全没有 {n - en}；有英文无中文 {en - zh}")
    print("完全没有的（按热度，前 30）：")
    for r in sorted([r for r in rows if not r["present_en"]], key=lambda r: -float(r["popularity"] or 0))[:30]:
        print(f"  {r['candidate'][:36]:36s} {r['source'][:32]:32s} pop={r['popularity']}")
    print("有英文无中文（按热度，前 60）：")
    for r in sorted([r for r in rows if r["present_en"] and not r["present_zh"]], key=lambda r: -float(r["popularity"] or 0))[:60]:
        print(f"  {r['candidate'][:36]:36s} {r['source'][:32]:32s} pop={r['popularity']}")


if __name__ == "__main__":
    main()
