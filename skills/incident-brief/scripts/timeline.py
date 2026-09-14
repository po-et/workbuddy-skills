#!/usr/bin/env python3
"""把变更、异常起点、手工观察事件合并成一条对齐的时间线。

这一步交付整个技能 80% 的价值：一张对齐的时间线，人往往自己就能看出问题。

用法:
    python3 timeline.py --changes out/changes.json --anomaly out/anomaly.json \
        --manual manual-events.csv --out out/timeline.md
"""
import argparse
import csv
import json
import os
from datetime import datetime, timezone

# 可能成为原因的事件类型 → 风险权重；症状类事件权重为 0，不参与候选排序
RISK = {"config": 3, "release": 2, "deployment": 2, "pull_request": 2,
        "commit": 1, "ops": 1}
SYMPTOM_KINDS = {"alert", "user_report", "anomaly", "manual"}

KIND_LABEL = {
    "release": "发布", "deployment": "部署", "pull_request": "合并 PR",
    "commit": "提交", "config": "配置变更", "anomaly": "指标异常",
    "manual": "人工观察", "alert": "告警", "user_report": "用户报障",
    "ops": "人工操作",
}


def parse_ts(s):
    s = (s or "").strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def load_json(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rows_from_changes(data):
    if not data:
        return [], ["未提供 GitHub 变更数据（releases / deployments / 合并 PR），"
                    "自动采集的变更源未覆盖"]
    out = []
    for e in data.get("events", []):
        t = parse_ts(e["time"])
        if not t:
            continue
        out.append({"t": t, "source": e["repo"], "kind": e["kind"],
                    "title": e["title"], "url": e.get("url", ""),
                    "risk": e.get("risk_weight", 1)})
    gaps = [f"GitHub {e['source']}（{e['repo']}）采集失败：{e['error']}"
            for e in data.get("errors", [])]
    return out, gaps


def rows_from_anomaly(data):
    if not data:
        return [], ["未提供指标数据，异常起点未知"]
    r = data.get("result")
    if not r:
        return [], [f"指标异常起点未定位：{data.get('note', '原因未知')}"]
    t = parse_ts(r["anomaly_start"])
    arrow = "↑" if r["direction"] == "up" else "↓"
    return [{"t": t, "source": "监控", "kind": "anomaly",
             "title": (f"**指标异常起点** {arrow} 首值 {r['first_value']}"
                       f"（基线 {r['baseline']['mean']}±{r['baseline']['stdev']}，"
                       f"{r['rule']}）"),
             "url": "", "risk": 0}], []


def rows_from_manual(path):
    if not path or not os.path.exists(path):
        return [], ["未提供人工观察事件（告警触发、用户报障、人工操作等）"]
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            t = parse_ts(row.get("timestamp"))
            if not t:
                continue
            kind = (row.get("kind") or "manual").strip()
            out.append({"t": t, "source": row.get("source") or "人工",
                        "kind": kind,
                        "title": row.get("event") or "", "url": row.get("url") or "",
                        "risk": 0 if kind in SYMPTOM_KINDS else RISK.get(kind, 1)})
    return out, []


def render(rows, gaps, anchor):
    lines = ["# 对齐时间线\n"]
    if not rows:
        return "\n".join(lines + ["_无事件。_"])

    lines += ["| 时刻 | 相对异常 | 来源 | 类型 | 事件 |", "|---|---|---|---|---|"]
    for r in rows:
        if anchor:
            delta = (r["t"] - anchor).total_seconds()
            sign = "+" if delta >= 0 else "-"
            d = abs(delta)
            rel = (f"{sign}{int(d)}s" if d < 120 else
                   f"{sign}{d/60:.1f}min" if d < 7200 else f"{sign}{d/3600:.1f}h")
            if abs(delta) < 1:
                rel = "**0**"
        else:
            rel = "—"
        title = r["title"]
        if r["url"]:
            title = f"[{title}]({r['url']})"
        lines.append(f"| {r['t'].strftime('%H:%M:%S')} | {rel} | {r['source']} | "
                     f"{KIND_LABEL.get(r['kind'], r['kind'])} | {title} |")

    if anchor:
        near = [r for r in rows
                if r["risk"] > 0 and abs((r["t"] - anchor).total_seconds()) <= 900]
        lines.append("\n## 异常起点前后 15 分钟内的变更\n")
        if near:
            lines.append("下列变更时间上接近异常起点，是候选排序的起点。"
                         "**时间接近不等于因果**，必须逐个找反证。\n")
            for r in sorted(near, key=lambda x: abs((x["t"] - anchor).total_seconds())):
                d = (r["t"] - anchor).total_seconds()
                when = "早于异常" if d < 0 else "晚于异常"
                lines.append(f"- `{r['t'].strftime('%H:%M:%S')}` "
                             f"（{when} {abs(d):.0f}s，风险权重 {r['risk']}）"
                             f" {r['source']} — {r['title']}")
                if d > 0:
                    lines.append("  - ⚠ 晚于异常起点，通常**不可能是原因**，除非存在延迟生效")
        else:
            lines.append("_窗口内无变更事件。异常可能来自外部依赖、流量变化或未纳入采集的变更源。_")

    lines.append("\n## 数据缺口\n")
    lines += ([f"- {g}" for g in gaps] if gaps else ["- 无"])
    lines.append("\n---\n_本文件为事实汇总，不含判断。候选排序与简报见 SKILL.md 第 4、5 步。_")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--changes")
    ap.add_argument("--anomaly")
    ap.add_argument("--manual")
    ap.add_argument("--out", default="out/timeline.md")
    a = ap.parse_args()

    rows, gaps = [], []
    for fn, arg in ((rows_from_changes, load_json(a.changes)),
                    (rows_from_anomaly, load_json(a.anomaly))):
        r, g = fn(arg)
        rows += r
        gaps += g
    r, g = rows_from_manual(a.manual)
    rows += r
    gaps += g

    rows.sort(key=lambda x: x["t"])
    anchor = next((x["t"] for x in rows if x["kind"] == "anomaly"), None)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(rows, gaps, anchor) + "\n")

    print(f"✓ {a.out}: {len(rows)} 个事件"
          + (f"，锚点 {anchor.strftime('%H:%M:%S')}" if anchor else "，无异常锚点")
          + (f"，{len(gaps)} 个数据缺口" if gaps else ""))


if __name__ == "__main__":
    main()
