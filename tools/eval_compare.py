#!/usr/bin/env python3
"""评测分前后对比：只拿「评测时间晚于新版本上线时间」的技能说事。

用法：python3 tools/eval_compare.py [基线json] [slug ...]
  基线默认 docs/metrics/eval-items-2026-09-26.json（升级前各技能的评测总分 overall）
  slug 不给时，读 docs/metrics/upgrade-published-*.json 里发布过的全部技能
输出：逐个技能「升级前 → 现在」，以及已重评的均值变化、≥4.7 的个数变化；存 docs/metrics/eval-compare-<日期>.json
口径：总分 = 各维度子项均值的平均（与 eval_items 一致）；新版本尚未成为 latestVersion，或评测 createdAt 早于它，都记为「未重评」。
退出码：0 正常；1 参数/文件错误；130 中断。
"""
import datetime
import glob
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HDR = {"User-Agent": "skillhub-cli/0.1", "Accept": "application/json"}
NS = "indiv-captain"


def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request("https://api.skillhub.cn" + path, headers=HDR)
            return json.load(urllib.request.urlopen(req, timeout=25))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        time.sleep(3 * (i + 1))


def overall(ev):
    dims = []
    for dv in (ev.get("dimensions") or {}).values():
        sc = [iv["score"] for iv in ((dv or {}).get("items") or {}).values()
              if isinstance(iv, dict) and isinstance(iv.get("score"), (int, float))]
        if sc:
            dims.append(sum(sc) / len(sc))
    return round(sum(dims) / len(dims), 3) if dims else None


def main():
    args = sys.argv[1:]
    base_path = Path(args.pop(0)) if args and args[0].endswith(".json") else ROOT / "docs/metrics/eval-items-2026-09-26.json"
    try:
        base = json.loads(base_path.read_text("utf-8"))["overall"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"读不了基线 {base_path}：{e}", file=sys.stderr)
        return 1
    expected = {r["slug"]: r.get("new_version") for f in sorted(glob.glob(str(ROOT / "docs/metrics/upgrade-published-*.json")))
                for r in json.load(open(f, encoding="utf-8"))}
    slugs = args or sorted(expected)
    if not slugs:
        print("没有要对比的技能（先发布升级，或在命令行给 slug）", file=sys.stderr)
        return 1
    rows = []
    for i, s in enumerate(slugs):
        if i:
            time.sleep(0.6)
        d = get(f"/api/v1/skills/{s}?namespace={NS}") or {}
        lv = d.get("latestVersion") or {}
        ev = get(f"/api/v1/skills/{s}/evaluation?namespace={NS}") or {}
        now = overall(ev)
        want = expected.get(s)
        fresh = bool(ev.get("createdAt") and lv.get("createdAt") and ev["createdAt"] > lv["createdAt"]
                     and (not want or lv.get("version") == want))  # 新版本还在扫描队列时，评测的是旧版本
        rows.append({"slug": s, "name": (d.get("skill") or {}).get("displayName", ""), "latest": lv.get("version", ""),
                     "before": base.get(s), "now": now, "re_evaluated": fresh})
        tag = "已重评" if fresh else "未重评"
        print(f"{s:30s} v{lv.get('version', '-'):7s} {str(base.get(s) or '—'):6s} → {str(now or '—'):6s} {tag}  {rows[-1]['name']}")
    done = [r for r in rows if r["re_evaluated"] and r["before"] and r["now"]]
    if done:
        delta = sum(r["now"] - r["before"] for r in done) / len(done)
        print(f"\n已重评 {len(done)}/{len(rows)}：平均变化 {delta:+.3f}；≥4.7 的 {sum(r['before'] >= 4.7 for r in done)} → {sum(r['now'] >= 4.7 for r in done)}")
    else:
        print(f"\n{len(rows)} 个技能里还没有一个被重评（评测延迟 3 小时到 2 天不等）")
    p = ROOT / f"docs/metrics/eval-compare-{datetime.date.today()}.json"
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    print("已存", p.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
