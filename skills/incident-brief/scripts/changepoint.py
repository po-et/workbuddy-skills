#!/usr/bin/env python3
"""在指标序列上找异常起点（变化点），而不是找超阈值点。

阈值告警只告诉你「现在坏了」；变化点告诉你「什么时候开始坏的」——
后者才能和变更记录对上。

输入 CSV 两列: timestamp,value （timestamp 为 ISO8601）

用法:
    python3 changepoint.py --input metrics.csv \
        --baseline-until 2026-09-14T13:50:00Z --out out/anomaly.json
"""
import argparse
import csv
import json
import os
import statistics as st
import sys
from datetime import datetime, timezone


def parse_ts(s):
    s = (s or "").strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load(path):
    pts = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            keys = {k.lower().strip(): k for k in row}
            tk = keys.get("timestamp") or keys.get("time") or keys.get("ts")
            vk = keys.get("value") or keys.get("val") or keys.get("v")
            if not tk or not vk:
                sys.exit("CSV 需含 timestamp 与 value 两列")
            t, v = parse_ts(row[tk]), row[vk]
            if t is None:
                continue
            try:
                pts.append((t, float(v)))
            except (TypeError, ValueError):
                continue
    pts.sort(key=lambda p: p[0])
    return pts


def detect(pts, baseline_until, sigma, consecutive):
    base = [v for t, v in pts if t <= baseline_until]
    if len(base) < 5:
        return None, f"基线样本仅 {len(base)} 个，不足 5 个，无法判断。请把 --baseline-until 往后挪或拉长采集窗口。"

    mu = st.mean(base)
    sd = st.pstdev(base)
    if sd == 0:
        sd = abs(mu) * 0.01 or 1e-9   # 基线完全平稳时给一个极小容差，避免除零

    hi, lo = mu + sigma * sd, mu - sigma * sd
    run_start, run = None, 0
    for t, v in pts:
        if t <= baseline_until:
            continue
        if v > hi or v < lo:
            run += 1
            if run == 1:
                run_start = (t, v)
            if run >= consecutive:
                return {
                    "anomaly_start": run_start[0].isoformat(),
                    "first_value": run_start[1],
                    "direction": "up" if run_start[1] > hi else "down",
                    "baseline": {"mean": round(mu, 4), "stdev": round(sd, 4),
                                 "n": len(base),
                                 "upper": round(hi, 4), "lower": round(lo, 4)},
                    "rule": f"连续 {consecutive} 点越出基线 ±{sigma}σ",
                }, None
        else:
            run, run_start = 0, None
    return None, "未检测到持续越界。可能异常幅度小于阈值、或基线窗口本身已包含异常。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--baseline-until", required=True,
                    help="基线期结束时刻，应早于告警时间")
    ap.add_argument("--sigma", type=float, default=3.0)
    ap.add_argument("--consecutive", type=int, default=3)
    ap.add_argument("--out", default="out/anomaly.json")
    a = ap.parse_args()

    bu = parse_ts(a.baseline_until)
    if not bu:
        sys.exit("--baseline-until 需为 ISO8601")

    pts = load(a.input)
    if not pts:
        sys.exit("没有读到有效数据点")

    result, note = detect(pts, bu, a.sigma, a.consecutive)
    payload = {
        "input": a.input,
        "points": len(pts),
        "range": {"from": pts[0][0].isoformat(), "to": pts[-1][0].isoformat()},
        "params": {"sigma": a.sigma, "consecutive": a.consecutive,
                   "baseline_until": a.baseline_until},
        "result": result,
        "note": note,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    if result:
        print(f"✓ {a.out}: 异常起点 {result['anomaly_start']}"
              f"（{result['direction']}，{result['rule']}，基线 n={result['baseline']['n']}）")
    else:
        print(f"✓ {a.out}: 未定位到异常起点 —— {note}")


if __name__ == "__main__":
    main()
