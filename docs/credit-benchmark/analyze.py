#!/usr/bin/env python3
"""分析额度实测数据，产出可直接引用的文章素材。

用法:
    python3 analyze.py --input runs.csv --out report/
"""
import argparse
import csv
import os
import statistics as st
from collections import defaultdict

MODES = ["Ask", "Plan", "Craft"]
CTX = ["fresh", "accumulated"]


def load(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if not r.get("run_id") or r["run_id"].startswith("EXAMPLE"):
                continue
            try:
                r["credits"] = int(r["credits_before"]) - int(r["credits_after"])
                r["wall_seconds"] = float(r["wall_seconds"] or 0)
                r["quality_score"] = float(r["quality_score"] or 0)
            except (ValueError, TypeError):
                print(f"[warn] 跳过数据不全的行: {r['run_id']}")
                continue
            if r["credits"] < 0:
                print(f"[warn] {r['run_id']} 额度差为负，请核对")
            rows.append(r)
    return rows


def med(vals):
    return st.median(vals) if vals else None


def fmt(v, unit=""):
    return f"{v:.0f}{unit}" if v is not None else "—"


def check_controls(rows, out):
    """控制变量自查：跨版本/跨时段的数据不可比，必须先警告。"""
    versions = {r["wb_version"] for r in rows}
    slots = {r["time_slot"] for r in rows}
    warns = []
    if len(versions) > 1:
        warns.append(f"⚠ 数据跨 {len(versions)} 个版本（{', '.join(sorted(versions))}），"
                     "跨版本不可直接比较，需分版本单独分析")
    if len(slots) > 1:
        warns.append(f"⚠ 数据跨 {len(slots)} 个时段（{', '.join(sorted(slots))}），"
                     "客户端存在夜间折扣，跨时段不可直接比较")
    counts = defaultdict(int)
    for r in rows:
        counts[(r["task_id"], r["mode"], r["context_state"])] += 1
    thin = [k for k, v in counts.items() if v < 3]
    if thin:
        warns.append(f"⚠ {len(thin)} 个格子重复次数 < 3，中位数不稳定："
                     + ", ".join("/".join(k) for k in thin[:6])
                     + (" …" if len(thin) > 6 else ""))
    return warns


def table_by_mode(rows):
    """模式 × 上下文 额度中位数矩阵 —— 文章主表。"""
    lines = ["# 额度消耗：模式 × 上下文状态\n",
             "单位 Credits，取中位数。括号内为样本数。\n"]
    tasks = sorted({r["task_id"] for r in rows})
    for t in tasks:
        sub = [r for r in rows if r["task_id"] == t]
        lines.append(f"\n## {t}\n")
        lines.append("| 模式 | " + " | ".join(CTX) + " |")
        lines.append("|---|" + "---|" * len(CTX))
        for m in MODES:
            cells = []
            for c in CTX:
                vals = [r["credits"] for r in sub
                        if r["mode"] == m and r["context_state"] == c]
                cells.append(f"{fmt(med(vals))} (n={len(vals)})" if vals else "—")
            lines.append(f"| {m} | " + " | ".join(cells) + " |")

        allv = [r["credits"] for r in sub]
        if len(allv) >= 2 and min(allv) > 0:
            lines.append(f"\n极差：最贵 {max(allv)} / 最省 {min(allv)} = "
                         f"**{max(allv)/min(allv):.1f} 倍**")
    return "\n".join(lines)


def table_cost_quality(rows):
    """回答最容易被质疑的问题：省下的额度有没有牺牲质量。"""
    lines = ["# 额度 vs 输出质量\n",
             "省额度如果牺牲质量就没有意义。这张表用来回答这个质疑。\n",
             "| 任务 | 模式 | 上下文 | 额度中位数 | 质量中位数 | 完成率 | n |",
             "|---|---|---|---|---|---|---|"]
    groups = defaultdict(list)
    for r in rows:
        groups[(r["task_id"], r["mode"], r["context_state"])].append(r)
    for (t, m, c), g in sorted(groups.items()):
        done = sum(1 for r in g if r["completed"].lower() in ("yes", "y", "true", "1"))
        lines.append(
            f"| {t} | {m} | {c} | {fmt(med([r['credits'] for r in g]))} | "
            f"{med([r['quality_score'] for r in g]):.1f} | "
            f"{done}/{len(g)} | {len(g)} |")
    return "\n".join(lines)


def summary(rows, warns):
    lines = ["# 结论速查\n"]
    if warns:
        lines.append("## 数据可比性警告\n")
        lines.extend(f"- {w}" for w in warns)
        lines.append("")
    lines.append(f"- 有效样本：{len(rows)} 次运行")
    lines.append(f"- 任务：{', '.join(sorted({r['task_id'] for r in rows}))}")

    lines.append("\n## 可直接引用的句子\n")
    for t in sorted({r["task_id"] for r in rows}):
        sub = [r for r in rows if r["task_id"] == t]
        cheap = min(sub, key=lambda r: r["credits"], default=None)
        dear = max(sub, key=lambda r: r["credits"], default=None)
        if cheap and dear and cheap["credits"] > 0 and cheap is not dear:
            ratio = dear["credits"] / cheap["credits"]
            lines.append(
                f"- **{t}**：`{dear['mode']} + {dear['context_state']}` 消耗 "
                f"{dear['credits']} Credits，`{cheap['mode']} + {cheap['context_state']}` "
                f"消耗 {cheap['credits']}，相差 **{ratio:.1f} 倍**"
                f"（质量分 {dear['quality_score']:.0f} vs {cheap['quality_score']:.0f}）")

    lines.append("\n## 发表前必须一起给出\n")
    vs = sorted({r["wb_version"] for r in rows})
    ss = sorted({r["time_slot"] for r in rows})
    lines.append(f"- 版本：{', '.join(vs)}")
    lines.append(f"- 时段：{', '.join(ss)}")
    lines.append("- 局限：单机、单账号，不代表所有场景")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="runs.csv")
    ap.add_argument("--out", default="report")
    a = ap.parse_args()

    rows = load(a.input)
    if not rows:
        raise SystemExit("没有有效数据。先按 README 第 5 节跑实验并填 runs.csv。")

    warns = check_controls(rows, a.out)
    os.makedirs(a.out, exist_ok=True)
    for name, content in [("by_mode.md", table_by_mode(rows)),
                          ("cost_quality.md", table_cost_quality(rows)),
                          ("summary.md", summary(rows, warns))]:
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(content + "\n")

    for w in warns:
        print(w)
    print(f"✓ {len(rows)} 条有效数据 → {a.out}/(by_mode|cost_quality|summary).md")


if __name__ == "__main__":
    main()
