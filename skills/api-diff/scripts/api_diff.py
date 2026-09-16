#!/usr/bin/env python3
"""接口差分测试：同一批请求打到环境 A 与 B，逐字段对比响应。零依赖。

用例文件 cases.json：
[{"name": "订单详情", "method": "GET", "path": "/api/orders/1", "headers": {}, "body": null, "path_b": null}]
用法：
  API_DIFF_HEADERS='{"Authorization":"Bearer <token>"}' \
  python3 api_diff.py --a https://staging.example.com --b https://prod.example.com --cases cases.json \
      --ignore "updated_at,request_id,trace_id,^ts$" --md out/api-diff.md --out out/api-diff.json
凭证只从环境变量 API_DIFF_HEADERS 读，不写进用例文件。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def request(base, case, headers, timeout, path_key="path"):
    path = case.get(path_key) or case["path"]
    url = base.rstrip("/") + path
    h = {"User-Agent": "api-diff/0.1", **headers, **(case.get("headers") or {})}
    body = case.get("body")
    data = None
    if body is not None:
        data = json.dumps(body).encode() if not isinstance(body, str) else body.encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=case.get("method", "GET").upper(), headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(); status = r.status; ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw = e.read(); status = e.code; ctype = e.headers.get("Content-Type", "")
    except Exception as e:
        return {"status": None, "error": str(e)[:200], "ms": round((time.time() - t0) * 1000)}
    ms = round((time.time() - t0) * 1000)
    text = raw.decode("utf-8", errors="replace")
    parsed = None
    if "json" in ctype or text[:1] in "{[":
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
    return {"status": status, "content_type": ctype.split(";")[0], "json": parsed, "text": None if parsed is not None else text[:4000], "ms": ms, "bytes": len(raw)}


def ignored(key, patterns):
    return any(re.search(p, key) for p in patterns)


def deep_diff(x, y, patterns, path="$", out=None, limit=200):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if ignored(k, patterns):
                continue
            p = f"{path}.{k}"
            if k not in x:
                out.append({"path": p, "kind": "only_in_b", "b": _short(y[k])})
            elif k not in y:
                out.append({"path": p, "kind": "only_in_a", "a": _short(x[k])})
            else:
                deep_diff(x[k], y[k], patterns, p, out, limit)
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            out.append({"path": path, "kind": "length", "a": len(x), "b": len(y)})
        for i, (xi, yi) in enumerate(zip(x, y)):
            deep_diff(xi, yi, patterns, f"{path}[{i}]", out, limit)
    else:
        if x != y and not (isinstance(x, (int, float)) and isinstance(y, (int, float)) and x == y):
            out.append({"path": path, "kind": "value", "a": _short(x), "b": _short(y)})
    return out


def _short(v):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= 80 else s[:77] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--ignore", default="", help="逗号分隔的字段名正则，如 updated_at,request_id,^ts$")
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    patterns = [p.strip() for p in a.ignore.split(",") if p.strip()]
    headers = {}
    if os.environ.get("API_DIFF_HEADERS"):
        try:
            headers = json.loads(os.environ["API_DIFF_HEADERS"])
        except ValueError:
            sys.exit("API_DIFF_HEADERS 不是合法 JSON")
    cases = json.loads(Path(a.cases).read_text("utf-8"))
    results = []
    for c in cases:
        ra = request(a.a, c, headers, a.timeout)
        rb = request(a.b, c, headers, a.timeout, "path_b")
        diffs, verdict = [], "same"
        if ra.get("error") or rb.get("error"):
            verdict = "error"
        elif ra["status"] != rb["status"]:
            verdict = "status"
        elif ra["json"] is not None and rb["json"] is not None:
            diffs = deep_diff(ra["json"], rb["json"], patterns)
            verdict = "same" if not diffs else "diff"
        elif (ra.get("text") or "") != (rb.get("text") or ""):
            verdict = "diff"; diffs = [{"path": "$", "kind": "text", "a": (ra.get("text") or "")[:80], "b": (rb.get("text") or "")[:80]}]
        results.append({"name": c.get("name") or c["path"], "method": c.get("method", "GET"), "path": c["path"], "verdict": verdict,
                        "a": {k: ra.get(k) for k in ("status", "ms", "bytes", "error")}, "b": {k: rb.get(k) for k in ("status", "ms", "bytes", "error")}, "diffs": diffs[:50]})
    n = len(results); same = sum(r["verdict"] == "same" for r in results)
    md = [f"# 接口差分：{a.a} ↔ {a.b}", "", f"- 用例 {n}，一致 {same}，有差异 {sum(r['verdict']=='diff' for r in results)}，状态码不同 {sum(r['verdict']=='status' for r in results)}，请求失败 {sum(r['verdict']=='error' for r in results)}",
          f"- 忽略字段：{', '.join(patterns) or '无'}", "", "| 用例 | 方法 路径 | 结论 | A 状态/耗时 | B 状态/耗时 | 差异数 |", "|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['name']} | {r['method']} {r['path']} | {r['verdict']} | {r['a']['status']} / {r['a']['ms']}ms | {r['b']['status']} / {r['b']['ms']}ms | {len(r['diffs'])} |")
    for r in results:
        if r["diffs"]:
            md += ["", f"## {r['name']}"]
            for d in r["diffs"][:30]:
                md.append(f"- `{d['path']}` {d['kind']}：A=`{d.get('a', '')}` B=`{d.get('b', '')}`")
        elif r["verdict"] == "error":
            md += ["", f"## {r['name']}", f"- A: {r['a'].get('error') or 'ok'}；B: {r['b'].get('error') or 'ok'}"]
    text = "\n".join(md) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True); Path(a.md).write_text(text, "utf-8"); print(f"✓ {a.md}：{n} 用例，{same} 一致")
    else:
        print(text)
    sys.exit(0 if same == n else 1)


if __name__ == "__main__":
    main()
