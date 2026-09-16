#!/usr/bin/env python3
"""日志/指标突变检测：找"什么时候开始不对"，而不是"现在超没超阈值"。

两种输入：
  1) CSV：timestamp,value（ISO8601 时间戳）
  2) 原始日志文件：按行提取时间戳，按 --bucket 秒聚合成计数序列（可用 --match 正则只数 ERROR 等）
算法：滑动基线 + 3σ + 连续 N 个点确认（避免单点毛刺），输出每个突变点的时间、方向、幅度、前后均值。
零依赖。用法：
  python3 log_anomaly.py --input app.log --bucket 60 --match "ERROR|Exception" --out out/anomaly.json --md out/anomaly.md
  python3 log_anomaly.py --input metrics.csv --sigma 3 --consecutive 3 --window 30
"""
import argparse
import csv
import json
import re
import statistics as st
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

TS_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"),
    re.compile(r"(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}(?: [+-]\d{4})?)"),   # nginx/apache
    re.compile(r"\b(\d{10})(?:\.\d+)?\b"),                                       # epoch 秒
]


def parse_ts(s):
    s = s.strip()
    if re.fullmatch(r"\d{10}", s):
        return datetime.fromtimestamp(int(s), tz=timezone.utc)
    m = re.fullmatch(r"(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}:\d{2}:\d{2})(?: ([+-]\d{4}))?", s)
    if m:
        try:
            d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)}", "%d %b %Y %H:%M:%S")
            if m.group(5):
                sign = 1 if m.group(5)[0] == "+" else -1
                off = timedelta(hours=int(m.group(5)[1:3]), minutes=int(m.group(5)[3:5])) * sign
                d = d.replace(tzinfo=timezone(off))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    s = s.replace(",", ".").replace(" ", "T", 1) if re.match(r"\d{4}-\d{2}-\d{2} ", s) else s.replace(",", ".")
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load_csv(path):
    pts = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            keys = {k.lower().strip(): k for k in row}
            tk = keys.get("timestamp") or keys.get("time") or keys.get("ts") or keys.get("date")
            vk = keys.get("value") or keys.get("val") or keys.get("count") or keys.get("v")
            if not tk or not vk:
                sys.exit("CSV 需含 timestamp 与 value（或 count）两列")
            t = parse_ts(row[tk])
            if t is None:
                continue
            try:
                pts.append((t, float(row[vk])))
            except (TypeError, ValueError):
                continue
    pts.sort()
    return pts, {"lines": len(pts), "matched": len(pts), "unparsed": 0}


def load_log(path, bucket, match):
    rx = re.compile(match) if match else None
    counts, total, matched, unparsed = Counter(), 0, 0, 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            total += 1
            if rx and not rx.search(line):
                continue
            t = None
            for pat in TS_PATTERNS:
                m = pat.search(line)
                if m:
                    t = parse_ts(m.group(1))
                    if t:
                        break
            if not t:
                unparsed += 1
                continue
            matched += 1
            b = int(t.timestamp() // bucket * bucket)
            counts[b] += 1
    if not counts:
        sys.exit("没有解析到带时间戳的行（支持 ISO8601 / nginx 格式 / 秒级 epoch）")
    lo, hi = min(counts), max(counts)
    pts = [(datetime.fromtimestamp(b, tz=timezone.utc), float(counts.get(b, 0))) for b in range(lo, hi + bucket, bucket)]
    return pts, {"lines": total, "matched": matched, "unparsed": unparsed, "bucket_seconds": bucket, "buckets": len(pts)}


def detect(pts, sigma, consecutive, window, min_baseline):
    """滑动基线：对第 i 个点，用其前 window 个"正常"点做基线；连续 consecutive 个点越界才算突变。
    发现突变后基线冻结在突变前，直到序列回到基线范围内（连续 consecutive 个点在范围内）再解冻。"""
    events, state = [], "normal"
    baseline = []  # 最近的正常点
    run = []       # 连续越界点
    back = 0
    for i, (t, v) in enumerate(pts):
        if len(baseline) < min_baseline:
            baseline.append(v)
            continue
        base = baseline[-window:]
        mu, sd = st.mean(base), st.pstdev(base)
        sd = sd if sd > 0 else (abs(mu) * 0.05 or 0.5)
        z = (v - mu) / sd
        out = abs(z) >= sigma
        if state == "normal":
            if out:
                run.append((t, v, z))
                if len(run) >= consecutive:
                    t0, v0, z0 = run[0]
                    events.append({"start": t0.isoformat(), "direction": "up" if z0 > 0 else "down", "z": round(z0, 2),
                                   "baseline_mean": round(mu, 3), "baseline_sd": round(sd, 3), "first_value": v0,
                                   "confirmed_at": t.isoformat(), "end": None, "peak": max((r[1] for r in run), key=abs)})
                    state = "anomaly"; back = 0
            else:
                run.clear(); baseline.append(v)
        else:  # anomaly
            ev = events[-1]
            ev["peak"] = max(ev["peak"], v) if ev["direction"] == "up" else min(ev["peak"], v)
            if not out:
                back += 1
                if back >= consecutive:
                    ev["end"] = t.isoformat(); state = "normal"; run.clear(); back = 0
                    baseline.extend([v] * 1)
            else:
                back = 0
    for ev in events:
        ev["duration_note"] = "持续到序列末尾（未恢复）" if ev["end"] is None else None
    return events


def render_md(events, meta, args):
    lines = [f"# 突变检测：{Path(args.input).name}", "",
             f"- 输入：{meta.get('lines')} 行" + (f"，匹配 `{args.match}` {meta.get('matched')} 行" if args.match else "") + (f"，{meta.get('unparsed')} 行无法解析时间戳" if meta.get('unparsed') else ""),
             f"- 序列：{meta.get('buckets', meta.get('lines'))} 个点" + (f"（每 {meta.get('bucket_seconds')} 秒一桶）" if meta.get('bucket_seconds') else ""),
             f"- 参数：σ={args.sigma}，连续 {args.consecutive} 点确认，基线窗口 {args.window} 点，最少基线 {args.min_baseline} 点", ""]
    if not events:
        lines.append("未发现满足条件的突变。可能：序列本身平稳；或参数太严（试 --sigma 2.5 / --consecutive 2）；或异常从第一条数据就开始（此时没有「正常基线」，需要拉长采集窗口）。")
        return "\n".join(lines) + "\n"
    lines += ["| # | 开始 | 方向 | 首点 z | 基线均值±σ | 峰值 | 恢复 |", "|---|---|---|---|---|---|---|"]
    for i, e in enumerate(events, 1):
        lines.append(f"| {i} | {e['start']} | {'↑' if e['direction']=='up' else '↓'} | {e['z']} | {e['baseline_mean']}±{e['baseline_sd']} | {e['peak']} | {e['end'] or '未恢复'} |")
    lines += ["", "下一步：把每个「开始」时间与发布/配置/基础设施变更记录对齐（前后 30 分钟），这才是排查的起点。"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--bucket", type=int, default=60, help="日志聚合桶，秒（仅原始日志）")
    ap.add_argument("--match", help="只统计匹配此正则的行（如 'ERROR|Exception|5\\d\\d'）")
    ap.add_argument("--sigma", type=float, default=3.0)
    ap.add_argument("--consecutive", type=int, default=3)
    ap.add_argument("--window", type=int, default=60, help="滑动基线取最近多少个正常点")
    ap.add_argument("--min-baseline", type=int, default=10)
    ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    p = Path(a.input)
    if p.suffix.lower() == ".csv":
        pts, meta = load_csv(p)
    else:
        pts, meta = load_log(p, a.bucket, a.match)
    if len(pts) < a.min_baseline + a.consecutive:
        sys.exit(f"数据点太少（{len(pts)}），至少需要 {a.min_baseline + a.consecutive} 个")
    events = detect(pts, a.sigma, a.consecutive, a.window, a.min_baseline)
    md = render_md(events, meta, a)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"meta": meta, "params": vars(a), "events": events,
                                           "series_preview": [(t.isoformat(), v) for t, v in pts[:5]]}, ensure_ascii=False, indent=2, default=str), "utf-8")
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True)
        Path(a.md).write_text(md, "utf-8")
        print(f"✓ {a.md}：{len(events)} 个突变" + (f"，首个 {events[0]['start']}" if events else ""))
    else:
        print(md)


if __name__ == "__main__":
    main()
