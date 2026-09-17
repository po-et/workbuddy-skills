#!/usr/bin/env python3
"""不稳定（flaky）测试识别：汇总多次运行的 JUnit XML 报告，找出时而通过时而失败的用例。纯标准库。

用法：
  python3 flaky_finder.py reports/            # 递归读取所有 *.xml（每个文件或子目录视为一次运行）
  python3 flaky_finder.py run1.xml run2.xml run3.xml
  python3 flaky_finder.py reports/ --min-runs 3 --json --top 20
判定：同一用例在 ≥ min-runs 次运行中既有通过也有失败/错误 → flaky；始终失败 → 稳定失败；给出失败率、最近状态、常见失败信息与耗时。
"""
import argparse, collections, glob, json, os, re, sys
import xml.etree.ElementTree as ET


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for f in sorted(glob.glob(os.path.join(p, "**", "*.xml"), recursive=True)):
                yield f
        else:
            yield p


def run_key(path, roots):
    """把文件归到一次「运行」：优先用一级子目录名，否则用文件名。"""
    for r in roots:
        if os.path.isdir(r) and os.path.abspath(path).startswith(os.path.abspath(r)):
            rel = os.path.relpath(path, r)
            parts = rel.split(os.sep)
            return parts[0] if len(parts) > 1 else os.path.splitext(parts[0])[0]
    return os.path.splitext(os.path.basename(path))[0]


def parse(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    out = []
    for tc in root.iter("testcase"):
        name = f"{tc.get('classname') or ''}::{tc.get('name') or ''}".strip(":")
        status, msg = "pass", ""
        for tag, st in (("failure", "fail"), ("error", "error"), ("skipped", "skip")):
            el = tc.find(tag)
            if el is not None:
                status = st
                msg = (el.get("message") or (el.text or "").strip().splitlines()[0] if (el.get("message") or el.text) else "")[:160]
                break
        try:
            dur = float(tc.get("time") or 0)
        except ValueError:
            dur = 0.0
        out.append((name, status, msg, dur))
    return out


def main():
    ap = argparse.ArgumentParser(description="flaky 测试识别")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--min-runs", type=int, default=2, help="至少出现在多少次运行中才判定（默认 2）")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    runs = collections.OrderedDict()
    for f in iter_files(a.paths):
        cases = parse(f)
        if not cases:
            continue
        runs.setdefault(run_key(f, a.paths), []).extend(cases)
    if len(runs) < 2:
        print(f"只识别到 {len(runs)} 次运行，至少需要 2 次（把每次运行的报告放在不同子目录或用不同文件名）", file=sys.stderr)
        sys.exit(2)
    hist = collections.defaultdict(list)   # name -> [(run, status, msg, dur)]
    for rk, cases in runs.items():
        for name, st, msg, dur in cases:
            hist[name].append((rk, st, msg, dur))
    flaky, always_fail, slow = [], [], []
    for name, h in hist.items():
        real = [x for x in h if x[1] != "skip"]
        if len(real) < a.min_runs:
            continue
        n_fail = sum(1 for x in real if x[1] in ("fail", "error"))
        n_pass = len(real) - n_fail
        durs = [x[3] for x in real]
        msgs = collections.Counter(x[2] for x in real if x[1] in ("fail", "error") and x[2])
        rec = {"test": name, "runs": len(real), "failures": n_fail, "fail_rate": round(n_fail / len(real), 2),
               "last_status": real[-1][1], "avg_time": round(sum(durs) / len(durs), 3), "max_time": round(max(durs), 3),
               "common_message": msgs.most_common(1)[0][0] if msgs else "", "pattern": "".join("✗" if x[1] in ("fail", "error") else "✓" for x in real)}
        if n_fail and n_pass:
            flaky.append(rec)
        elif n_fail and not n_pass:
            always_fail.append(rec)
        if max(durs) > 0 and min(durs) > 0 and max(durs) / min(durs) >= 5 and max(durs) >= 1:
            slow.append({"test": name, "min_time": round(min(durs), 3), "max_time": round(max(durs), 3)})
    flaky.sort(key=lambda r: (-r["fail_rate"], -r["runs"]))
    always_fail.sort(key=lambda r: -r["runs"])
    slow.sort(key=lambda r: -r["max_time"])
    total = len(hist)
    if a.json:
        print(json.dumps({"runs": list(runs), "total_tests": total, "flaky": flaky[:a.top], "always_failing": always_fail[:a.top], "unstable_duration": slow[:a.top]}, ensure_ascii=False, indent=2)); return
    print(f"运行次数：{len(runs)}（{', '.join(list(runs)[:6])}{'…' if len(runs) > 6 else ''}）；用例总数：{total}")
    print(f"\n不稳定用例（{len(flaky)}）：时而通过时而失败")
    for r in flaky[:a.top]:
        print(f"  {r['fail_rate']:>5.0%}  {r['pattern']:<12} {r['test']}\n         最近：{r['last_status']}；均耗时 {r['avg_time']}s；常见信息：{r['common_message'] or '-'}")
    print(f"\n稳定失败（{len(always_fail)}）：每次都失败，不是 flaky，是真坏了")
    for r in always_fail[:a.top]:
        print(f"  {r['pattern']:<12} {r['test']}  —  {r['common_message'] or '-'}")
    if slow:
        print(f"\n耗时波动大（{len(slow)}）：最快与最慢相差 ≥ 5 倍，可能依赖外部资源或存在竞争")
        for r in slow[:a.top]:
            print(f"  {r['min_time']}s ~ {r['max_time']}s  {r['test']}")
    if flaky:
        print("\n建议：按失败率从高到低处理；先看常见失败信息（超时/连接/断言随机值）；隔离到 quarantine 分组并加重试只是止血，根因通常是共享状态、时间依赖、顺序依赖或外部服务。")


if __name__ == "__main__":
    main()
