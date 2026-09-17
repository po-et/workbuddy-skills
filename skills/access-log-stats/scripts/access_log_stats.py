#!/usr/bin/env python3
"""访问日志统计：按接口汇总 QPS、状态码分布、P50/P95/P99 耗时、错误率、Top 客户端。支持 Nginx/Apache combined 格式（可带耗时字段）与 JSON 行日志。纯标准库。

用法：
  python3 access_log_stats.py access.log [--top 20] [--json]
  python3 access_log_stats.py access.log --format json --path-key path --status-key status --time-key duration_ms
  python3 access_log_stats.py access.log --slow-ms 1000 --group-ids
说明：--group-ids 把路径中的数字/UUID 段归并为 :id，便于按接口而不是按具体资源聚合。
"""
import argparse, collections, json, re, sys

COMBINED = re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>[A-Z]+) (?P<path>\S+)[^"]*" (?P<status>\d{3}) (?P<bytes>\S+)(?: "(?P<referer>[^"]*)" "(?P<ua>[^"]*)")?(?P<rest>.*)$')
TAIL_NUM = re.compile(r"(?:rt=|request_time=|upstream_response_time=|\s)(\d+(?:\.\d+)?)\s*$")
ID_SEG = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,})$", re.I)


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def normalize(path, group_ids):
    path = path.split("?", 1)[0]
    if not group_ids:
        return path
    return "/".join(":id" if ID_SEG.match(seg) else seg for seg in path.split("/"))


def parse_line(line, fmt, keys):
    if fmt == "json" or (fmt == "auto" and line.startswith("{")):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            return None
        g = lambda k: d.get(k) if k else None
        st = g(keys["status"]); t = g(keys["time"])
        return {"ip": g(keys["ip"]), "method": g(keys["method"]) or "", "path": str(g(keys["path"]) or "-"), "status": int(st) if st is not None else 0,
                "ms": float(t) * (1000 if keys["time_unit"] == "s" else 1) if t is not None else None, "hour": str(g(keys["ts"]) or "")[:13]}
    m = COMBINED.match(line)
    if not m:
        return None
    rest = m.group("rest") or ""
    tm = TAIL_NUM.search(rest)
    ms = float(tm.group(1)) * (1000 if keys["time_unit"] == "s" else 1) if tm else None
    return {"ip": m.group("ip"), "method": m.group("method"), "path": m.group("path"), "status": int(m.group("status")), "ms": ms, "hour": m.group("time")[:14]}


def main():
    ap = argparse.ArgumentParser(description="访问日志统计")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--format", choices=["auto", "combined", "json"], default="auto")
    ap.add_argument("--path-key", default="path"); ap.add_argument("--status-key", default="status"); ap.add_argument("--time-key", default="duration_ms")
    ap.add_argument("--method-key", default="method"); ap.add_argument("--ip-key", default="remote_addr"); ap.add_argument("--ts-key", default="time")
    ap.add_argument("--time-unit", choices=["ms", "s"], default=None, help="耗时字段单位；combined 尾部 rt= 默认秒，JSON 默认毫秒")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--slow-ms", type=float, default=1000)
    ap.add_argument("--group-ids", action="store_true", help="路径里的数字/UUID 段归并为 :id")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    keys = {"path": a.path_key, "status": a.status_key, "time": a.time_key, "method": a.method_key, "ip": a.ip_key, "ts": a.ts_key}
    total, unparsed = 0, 0
    per = collections.defaultdict(lambda: {"n": 0, "status": collections.Counter(), "times": [], "bytes": 0})
    ips, hours, status_all = collections.Counter(), collections.Counter(), collections.Counter()
    for f in a.files:
        fh = sys.stdin if f == "-" else open(f, encoding="utf-8", errors="replace")
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            fmt = a.format
            keys["time_unit"] = a.time_unit or ("ms" if (fmt == "json" or line.startswith("{")) else "s")
            r = parse_line(line, fmt, keys)
            if not r:
                unparsed += 1; continue
            key = f"{r['method']} {normalize(r['path'], a.group_ids)}".strip()
            e = per[key]; e["n"] += 1; e["status"][r["status"]] += 1
            if r["ms"] is not None:
                e["times"].append(r["ms"])
            status_all[r["status"] // 100 * 100] += 1
            if r["ip"]: ips[r["ip"]] += 1
            if r["hour"]: hours[r["hour"]] += 1
        if f != "-":
            fh.close()
    rows = []
    for key, e in per.items():
        ts = sorted(e["times"])
        err5 = sum(c for s, c in e["status"].items() if s >= 500); err4 = sum(c for s, c in e["status"].items() if 400 <= s < 500)
        rows.append({"endpoint": key, "count": e["n"], "share": round(e["n"] / max(total - unparsed, 1) * 100, 1), "5xx": err5, "4xx": err4,
                     "err_rate": round(err5 / e["n"] * 100, 2), "p50": pct(ts, 50), "p95": pct(ts, 95), "p99": pct(ts, 99), "max": ts[-1] if ts else None,
                     "slow": sum(1 for t in ts if t > a.slow_ms)})
    rows.sort(key=lambda r: -r["count"])
    span = len(hours)
    peak = hours.most_common(1)[0] if hours else None
    out = {"lines": total, "unparsed": unparsed, "status_classes": {str(k): v for k, v in sorted(status_all.items())}, "endpoints": rows[:a.top],
           "slowest": sorted([r for r in rows if r["p95"] is not None], key=lambda r: -r["p95"])[:a.top], "top_errors": sorted(rows, key=lambda r: -r["5xx"])[:10],
           "top_ips": ips.most_common(10), "peak_hour": peak}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2)); return
    print(f"共 {total} 行（无法解析 {unparsed}）；状态码：" + "，".join(f"{k}xx {v}" for k, v in sorted(status_all.items()) for k in [k // 100]))
    if peak:
        print(f"高峰时段：{peak[0]}（{peak[1]} 次）")
    has_t = any(r["p50"] is not None for r in rows)
    print(f"\n## 请求量 Top {min(a.top, len(rows))}")
    print(f"  {'次数':>8} {'占比':>6} {'5xx':>5} {'错误率':>6}" + (f" {'p50':>7} {'p95':>7} {'p99':>7} {'>慢':>5}" if has_t else "") + "  接口")
    for r in rows[:a.top]:
        t = f" {r['p50']:>7.0f} {r['p95']:>7.0f} {r['p99']:>7.0f} {r['slow']:>5}" if r["p50"] is not None else (" " * 30 if has_t else "")
        print(f"  {r['count']:>8} {r['share']:>5}% {r['5xx']:>5} {r['err_rate']:>5}%{t}  {r['endpoint']}")
    if has_t:
        print(f"\n## P95 最慢 Top 10")
        for r in out["slowest"][:10]:
            print(f"  p95 {r['p95']:>7.0f}ms  p99 {r['p99']:>7.0f}ms  max {r['max']:>7.0f}ms  n={r['count']:<6} {r['endpoint']}")
    if any(r["5xx"] for r in rows):
        print(f"\n## 5xx 最多 Top 10")
        for r in out["top_errors"][:10]:
            if r["5xx"]:
                print(f"  {r['5xx']:>6} 次（{r['err_rate']}%）  {r['endpoint']}")
    print(f"\n## 客户端 IP Top 10")
    for ip, c in out["top_ips"]:
        print(f"  {c:>8}  {ip}")


if __name__ == "__main__":
    main()
