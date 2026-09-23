#!/usr/bin/env python3
"""改名实验读数：先核对新版本是否已上线（过了安全扫描），再对比改名前后的搜索名次。

用法：python3 tools/readout_rename.py [基线json]   # 只读，约 1 分钟；默认读批次 A 基线
基线：docs/metrics/rename-baseline-2026-09-21.json（改名前名次，同一查询词）
原则：latestVersion 没变的技能只报「未上线」，不拿它的名次说事。
"""
import json, time, urllib.request, urllib.parse, pathlib, datetime, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/metrics/rename-baseline-2026-09-21.json"
HDR = {"User-Agent": "skillhub-cli/0.1", "Accept": "application/json"}
NEW_VERSION = "0.1.1"  # 批次 A 与两个先行实验统一升到这个版本


def get(path):
    req = urllib.request.Request("https://api.skillhub.cn" + path, headers=HDR)
    return json.load(urllib.request.urlopen(req, timeout=25))


def search(q, limit=20):
    return get("/api/v1/search?" + urllib.parse.urlencode({"q": q, "limit": limit})).get("results", [])


def is_ours(x):
    ns = x.get("namespace") or {}
    return (isinstance(ns, dict) and ns.get("handle") == "indiv-captain") or str(x.get("slug", "")).startswith("@indiv-captain/")


def bare(x):
    ns = x.get("namespace") or {}
    return (ns.get("publicSlug") if isinstance(ns, dict) else None) or x.get("publicSlug") or str(x.get("slug", "")).split("/")[-1]


def main():
    rows = json.load(open(BASE))
    out = []
    print(f"读数时间 {datetime.datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'技能':26s} {'查询':10s} {'线上版':7s} {'改名前':6s} {'改名后':6s} 说明")
    for i, r in enumerate(rows):
        if i:
            time.sleep(1.2)
        d = get(f"/api/v1/skills/{r['slug']}")
        lv = (d.get("latestVersion") or {}).get("version") or ""
        live = lv == r.get("new_version", NEW_VERSION)
        name = (d.get("skill") or {}).get("displayName", "")
        rank = None
        if live:
            time.sleep(1.2)
            hits = [j + 1 for j, x in enumerate(search(r["query"])) if is_ours(x) and bare(x) == r["slug"]]
            rank = hits[0] if hits else None
        before = r.get("rank_before")
        note = "未上线（仍在扫描队列）" if not live else ("进前 3" if rank and rank <= 3 else ("进前 10" if rank and rank <= 10 else "未进前 20" if rank is None else ""))
        print(f"{r['slug']:26s} {r['query']:10s} {lv or '-':7s} {str(before or '—'):6s} {str(rank or '—') if live else '·':6s} {note}  {name}")
        out.append({**r, "latest_version": lv, "live": live, "rank_after": rank, "read_at": datetime.datetime.now().isoformat(timespec="minutes")})
    live_rows = [o for o in out if o["live"]]
    if live_rows:
        top3 = sum(1 for o in live_rows if o["rank_after"] and o["rank_after"] <= 3)
        print(f"\n已上线 {len(live_rows)}/{len(out)}：进前 3 的 {top3} 个；改名前这些技能进前 3 的 {sum(1 for o in live_rows if o['rank_before'] and o['rank_before'] <= 3)} 个")
        tag = BASE.stem.replace("rename-baseline", "").strip("-")
        p = ROOT / f"docs/metrics/rename-readout-{tag + '-' if tag else ''}{datetime.date.today()}.json"
        json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)
        print("已存", p.relative_to(ROOT))
    else:
        print("\n没有一个上线，今天不读数。")


if __name__ == "__main__":
    main()
