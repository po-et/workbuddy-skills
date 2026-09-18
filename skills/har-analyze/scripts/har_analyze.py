#!/usr/bin/env python3
"""HAR 性能分析：请求数/体积/耗时总览，耗时与体积 Top N（含阶段分解），按域名与资源类型聚合，8 类问题清单。纯标准库。

用法：
  python3 har_analyze.py capture.har
  python3 har_analyze.py capture.har --slow-ms 300 --top 15
  python3 har_analyze.py capture.har --json
  python3 har_analyze.py capture.har --strict        # 有 high 级问题则退出码 1，用于 CI
  cat capture.har | python3 har_analyze.py -
HAR 来源：Chrome/Edge DevTools 网络面板右键「Save all as HAR」，或 Firefox「另存为 HAR」。
"""
import argparse
import collections
import json
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

# 资源类型：优先用 Chrome 的 _resourceType，否则按 MIME 归类
RT_MAP = {"document": "文档", "stylesheet": "样式", "script": "脚本", "image": "图片", "font": "字体",
          "xhr": "XHR", "fetch": "XHR", "media": "媒体", "manifest": "其他", "websocket": "其他",
          "other": "其他", "texttrack": "其他", "eventsource": "XHR", "preflight": "其他"}
TEXTUAL = {"文档", "样式", "脚本", "XHR"}
STATIC = {"样式", "脚本", "图片", "字体", "媒体"}
COMPRESS = ("gzip", "br", "deflate", "zstd", "compress")
PHASES = ["blocked", "dns", "connect", "ssl", "send", "wait", "receive"]


def classify(entry):
    rt = (entry.get("_resourceType") or "").lower()
    if rt in RT_MAP:
        return RT_MAP[rt]
    mime = ((entry.get("response") or {}).get("content") or {}).get("mimeType") or ""
    mime = mime.split(";")[0].strip().lower()
    if mime in ("text/html", "application/xhtml+xml"):
        return "文档"
    if mime == "text/css":
        return "样式"
    if "javascript" in mime or "ecmascript" in mime or mime == "text/jsx":
        return "脚本"
    if mime.startswith("image/"):
        return "图片"
    if mime.startswith("font/") or "font" in mime or "woff" in mime:
        return "字体"
    if mime.startswith(("video/", "audio/")):
        return "媒体"
    if "json" in mime or "xml" in mime or mime == "text/plain":
        return "XHR"
    return "其他"


def header(headers, name):
    name = name.lower()
    for h in headers or []:
        if (h.get("name") or "").lower() == name:
            return h.get("value") or ""
    return ""


def human(n):
    if n is None:
        return "-"
    n = float(n)
    for unit, step in (("B", 1), ("KB", 1024), ("MB", 1024 * 1024)):
        if n < step * 1024 or unit == "MB":
            return f"{n / step:.0f}{unit}" if unit == "B" else f"{n / step:.1f}{unit}"
    return f"{n:.0f}B"


def width(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def padr(s, n):
    s = str(s)
    return s + " " * max(0, n - width(s))


def padl(s, n):
    s = str(s)
    return " " * max(0, n - width(s)) + s


def shorten(url, n=62):
    sp = urlsplit(url)
    short = (sp.path or "/") + (("?" + sp.query) if sp.query else "")
    # 只在非 https 时保留协议，这样 http→https 跳转能一眼看出来
    short = ("" if sp.scheme in ("https", "") else sp.scheme + "://") + f"{sp.netloc}{short}"
    return short if len(short) <= n else short[: n - 15] + "…" + short[-14:]


def parse_time(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def transfer_size(resp):
    ts = resp.get("_transferSize")
    if isinstance(ts, (int, float)) and ts >= 0:
        return int(ts)
    body, head = resp.get("bodySize") or 0, resp.get("headersSize") or 0
    total = max(body, 0) + max(head, 0)
    if total == 0:
        total = max((resp.get("content") or {}).get("size") or 0, 0)
    return int(total)


def load(path):
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8-sig", errors="replace").read()
    except OSError as e:
        sys.exit(f"读不到文件：{e}")
    try:
        har = json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"不是合法 JSON，HAR 文件可能被截断：{e}")
    log = har.get("log") if isinstance(har, dict) else None
    if not isinstance(log, dict) or not isinstance(log.get("entries"), list):
        sys.exit("不像 HAR 文件：缺少 log.entries（DevTools 网络面板右键 Save all as HAR 导出）")
    return log


def analyze(log, a):
    entries, pages = log["entries"], log.get("pages") or []
    rows, starts, ends = [], [], []
    for e in entries:
        req, resp = e.get("request") or {}, e.get("response") or {}
        url = req.get("url") or "-"
        t0 = parse_time(e.get("startedDateTime"))
        dur = e.get("time")
        dur = float(dur) if isinstance(dur, (int, float)) and dur >= 0 else 0.0
        tm = e.get("timings") or {}
        row = {
            "url": url, "host": urlsplit(url).netloc or "-", "method": req.get("method") or "-",
            "status": int(resp.get("status") or 0), "type": classify(e), "time": dur,
            "transfer": transfer_size(resp), "content": max((resp.get("content") or {}).get("size") or 0, 0),
            "mime": ((resp.get("content") or {}).get("mimeType") or "-").split(";")[0],
            "enc": header(resp.get("headers"), "content-encoding").lower(),
            "cache_control": header(resp.get("headers"), "cache-control"),
            "expires": header(resp.get("headers"), "expires"),
            "etag": header(resp.get("headers"), "etag") or header(resp.get("headers"), "last-modified"),
            "location": header(resp.get("headers"), "location"),
            "from_cache": bool((e.get("cache") or {}).get("afterRequest")) or (resp.get("_transferSize") == 0 and resp.get("status") == 200),
            "timings": {p: (float(tm[p]) if isinstance(tm.get(p), (int, float)) and tm[p] >= 0 else 0.0) for p in PHASES},
            "started": t0,
        }
        rows.append(row)
        if t0:
            starts.append(t0); ends.append(t0.timestamp() * 1000 + dur)

    wall = (max(ends) - min(s.timestamp() * 1000 for s in starts)) if starts else None
    page_timings = {}
    if pages:
        pt = pages[0].get("pageTimings") or {}
        for k, label in (("onContentLoad", "DOMContentLoaded"), ("onLoad", "onLoad")):
            v = pt.get(k)
            if isinstance(v, (int, float)) and v >= 0:
                page_timings[label] = float(v)

    first_party = ""
    doc = next((r for r in rows if r["type"] == "文档"), None)
    if pages and pages[0].get("title", "").startswith("http"):
        first_party = urlsplit(pages[0]["title"]).netloc
    if not first_party and doc:
        first_party = doc["host"]
    if not first_party and rows:
        first_party = rows[0]["host"]

    by_host = collections.defaultdict(lambda: {"n": 0, "transfer": 0, "time": 0.0})
    by_type = collections.defaultdict(lambda: {"n": 0, "transfer": 0, "content": 0, "time": 0.0})
    for r in rows:
        for bucket, key in ((by_host, r["host"]), (by_type, r["type"])):
            b = bucket[key]
            b["n"] += 1; b["transfer"] += r["transfer"]; b["time"] += r["time"]
            if "content" in b:
                b["content"] += r["content"]

    # ---------------- 问题清单
    issues = []

    def add(level, code, title, items, hint):
        if items:
            issues.append({"level": level, "code": code, "title": title, "items": items, "hint": hint})

    bad = [r for r in rows if r["status"] >= 400]
    add("high", "H1", f"{len(bad)} 个请求返回 4xx/5xx",
        [f"{r['status']} {r['method']} {shorten(r['url'])}" for r in sorted(bad, key=lambda r: -r["status"])],
        "5xx 先查服务端与网关日志；4xx 多为鉴权过期、路径拼错或跨域预检失败")

    by_url = collections.Counter((r["method"], r["url"]) for r in rows)
    dups = [(k, c) for k, c in by_url.items() if c > 1]
    add("warn", "H2", f"{len(dups)} 个 URL 被重复请求",
        [f"×{c}  {m} {shorten(u)}" for (m, u), c in sorted(dups, key=lambda x: -x[1])],
        "同一 URL 重复拉取通常是组件重复挂载或没做请求去重/缓存，先合并再谈优化")

    chains = []
    for r in rows:
        if 300 <= r["status"] < 400 and r["location"]:
            chain, cur, seen = [f"{r['status']} {shorten(r['url'])}"], r, {r["url"]}
            while True:
                nxt = next((x for x in rows if x["url"] == cur["location"] or x["url"].rstrip("/") == (cur["location"] or "").rstrip("/")), None)
                if not nxt or nxt["url"] in seen:
                    break
                seen.add(nxt["url"]); chain.append(f"{nxt['status']} {shorten(nxt['url'])}")
                if not (300 <= nxt["status"] < 400 and nxt["location"]):
                    break
                cur = nxt
            if not chain[1:] and r["location"]:
                chain.append(f"→ {shorten(r['location'])}")
            chains.append((r, chain))
    hop_cost = sum(r["time"] for r, _ in chains)
    add("warn" if len(chains) > 1 else "info", "H3", f"{len(chains)} 条重定向（共耗时 {hop_cost:.0f}ms）",
        [" → ".join(c) for _, c in chains],
        "能改就直接请求最终地址；HTTP→HTTPS、少/多一个斜杠、www 跳转这三类最常见")

    uncompressed = [r for r in rows
                    if r["type"] in TEXTUAL and r["content"] >= a.min_compress * 1024
                    and not any(c in r["enc"] for c in COMPRESS) and r["status"] == 200]
    add("warn", "H4", f"{len(uncompressed)} 个文本资源没开压缩",
        [f"{human(r['content']):>8}  {r['type']}  {shorten(r['url'])}" for r in sorted(uncompressed, key=lambda r: -r["content"])],
        f"文本类一般能压掉 60–80%（预计省 {human(sum(r['content'] for r in uncompressed) * 0.7)}）；在网关/CDN 打开 gzip 或 brotli")

    nocache = [r for r in rows if r["type"] in STATIC and r["status"] == 200
               and not r["cache_control"] and not r["expires"]]
    add("warn", "H5", f"{len(nocache)} 个静态资源缺缓存头",
        [f"{human(r['transfer']):>8}  {r['type']}  {shorten(r['url'])}" + ("" if r["etag"] else "  （连 ETag 也没有）") for r in sorted(nocache, key=lambda r: -r["transfer"])],
        "带指纹的静态资源给 cache-control 里的 max-age 一年加 immutable；不带指纹的至少给 ETag 走协商缓存")

    third = [r for r in rows if r["host"] != first_party and r["host"] != "-"]
    third_hosts = collections.Counter(r["host"] for r in third)
    add("warn" if len(third) > a.third_party_max else "info", "H6",
        f"第三方请求 {len(third)} 个（阈值 {a.third_party_max}），来自 {len(third_hosts)} 个域名",
        [f"{c:>4} 个请求  {human(sum(r['transfer'] for r in third if r['host'] == h)):>8}  {h}" for h, c in third_hosts.most_common()],
        "每个新域名都要付 DNS+TCP+TLS 的握手成本；能自托管的自托管，能延后加载的延后")

    bigimg = [r for r in rows if r["type"] == "图片" and r["transfer"] > a.img_kb * 1024]
    add("warn", "H7", f"{len(bigimg)} 张图片超过 {a.img_kb:g}KB",
        [f"{human(r['transfer']):>8}  {r['mime']:<12} {shorten(r['url'])}" for r in sorted(bigimg, key=lambda r: -r["transfer"])],
        "换 WebP/AVIF、按容器宽度下发多尺寸、首屏外的图片加 loading 懒加载")

    blocked = [r for r in rows if r["timings"]["blocked"] > a.blocked_ms]
    add("warn" if len(blocked) > 3 else "info", "H8", f"{len(blocked)} 个请求排队等待超过 {a.blocked_ms:g}ms",
        [f"blocked {r['timings']['blocked']:>7.0f}ms  总 {r['time']:>7.0f}ms  {shorten(r['url'])}" for r in sorted(blocked, key=lambda r: -r["timings"]["blocked"])],
        "同域并发连接数被打满（HTTP/1.1 一般 6 个）：合并请求、拆域名，或升到 HTTP/2 多路复用")

    slow = [r for r in rows if r["time"] > a.slow_ms]
    add("warn", "H9", f"{len(slow)} 个请求慢于 {a.slow_ms:.0f}ms",
        [f"{r['time']:>8.0f}ms  wait {r['timings']['wait']:>6.0f}ms  {shorten(r['url'])}" for r in sorted(slow, key=lambda r: -r["time"])],
        "wait 占大头是服务端处理慢；receive 占大头是响应体太大或带宽不足；connect/ssl 占大头是握手没复用")

    order = {"high": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda i: (order[i["level"]], i["code"]))
    return {
        "rows": rows, "wall_ms": wall, "page_timings": page_timings, "first_party": first_party,
        "totals": {"requests": len(rows), "transfer": sum(r["transfer"] for r in rows),
                   "content": sum(r["content"] for r in rows), "time_sum": sum(r["time"] for r in rows),
                   "from_cache": sum(1 for r in rows if r["from_cache"])},
        "by_host": by_host, "by_type": by_type, "issues": issues,
        "creator": (log.get("creator") or {}).get("name", "-"),
    }


def report(res, a):
    t = res["totals"]
    print(f"共 {t['requests']} 个请求，传输 {human(t['transfer'])}（解压后 {human(t['content'])}），"
          f"耗时累计 {t['time_sum'] / 1000:.2f}s"
          + (f"，墙上时间 {res['wall_ms'] / 1000:.2f}s" if res["wall_ms"] else ""))
    line = [f"首方域名 {res['first_party'] or '-'}"]
    for k, v in res["page_timings"].items():
        line.append(f"{k} {v:.0f}ms")
    if t["from_cache"]:
        line.append(f"命中缓存 {t['from_cache']} 个")
    print("· " + "，".join(line))

    rows = res["rows"]
    n = min(a.top, len(rows))
    print(f"\n## 耗时 Top {n}（单位 ms）")
    print("  " + padl("总耗时", 8) + padl("blocked", 9) + padl("dns", 6) + padl("connect", 8)
          + padl("ssl", 6) + padl("send", 6) + padl("wait", 8) + padl("receive", 8) + "  " + padr("状态", 6) + "请求")
    for r in sorted(rows, key=lambda r: -r["time"])[:n]:
        g = r["timings"]
        print("  " + padl(f"{r['time']:.0f}", 8) + padl(f"{g['blocked']:.0f}", 9) + padl(f"{g['dns']:.0f}", 6)
              + padl(f"{g['connect']:.0f}", 8) + padl(f"{g['ssl']:.0f}", 6) + padl(f"{g['send']:.0f}", 6)
              + padl(f"{g['wait']:.0f}", 8) + padl(f"{g['receive']:.0f}", 8) + "  "
              + padr(r["status"], 6) + shorten(r["url"]))

    print(f"\n## 体积 Top {n}")
    print("  " + padl("传输", 9) + padl("解压后", 10) + "  " + padr("类型", 6) + padr("压缩", 8) + "请求")
    for r in sorted(rows, key=lambda r: -r["transfer"])[:n]:
        print("  " + padl(human(r["transfer"]), 9) + padl(human(r["content"]), 10) + "  "
              + padr(r["type"], 6) + padr(r["enc"] or ("无" if r["type"] in TEXTUAL else "-"), 8) + shorten(r["url"]))

    print("\n## 按域名")
    print("  " + padl("请求", 6) + padl("传输", 10) + padl("耗时", 10) + "  域名")
    for h, b in sorted(res["by_host"].items(), key=lambda kv: -kv[1]["transfer"]):
        mark = "（首方）" if h == res["first_party"] else ""
        print("  " + padl(b["n"], 6) + padl(human(b["transfer"]), 10) + padl(f"{b['time']:.0f}ms", 10) + "  " + h + mark)

    print("\n## 按资源类型")
    print("  " + padl("请求", 6) + padl("传输", 10) + padl("解压后", 10) + padl("耗时", 10) + "  类型")
    for k, b in sorted(res["by_type"].items(), key=lambda kv: -kv[1]["transfer"]):
        print("  " + padl(b["n"], 6) + padl(human(b["transfer"]), 10) + padl(human(b["content"]), 10)
              + padl(f"{b['time']:.0f}ms", 10) + "  " + k)

    real = [i for i in res["issues"] if i["items"]]
    print(f"\n## 问题清单（{sum(1 for i in real if i['level'] == 'high')} high / "
          f"{sum(1 for i in real if i['level'] == 'warn')} warn / {sum(1 for i in real if i['level'] == 'info')} info）")
    if not real:
        print("  没发现明显问题。")
    for i in real:
        print(f"\n  [{i['level']}] {i['code']} {i['title']}")
        for it in i["items"][: a.top]:
            print(f"      {it}")
        if len(i["items"]) > a.top:
            print(f"      …… 还有 {len(i['items']) - a.top} 条（--top 调大查看）")
        print(f"      → {i['hint']}")


def main():
    ap = argparse.ArgumentParser(description="HAR 性能分析")
    ap.add_argument("file", help="HAR 文件路径，写 - 从标准输入读")
    ap.add_argument("--slow-ms", type=float, default=500, help="慢请求阈值，默认 500ms")
    ap.add_argument("--top", type=int, default=10, help="各榜单条数，默认 10")
    ap.add_argument("--blocked-ms", type=float, default=100, help="排队阻塞阈值，默认 100ms")
    ap.add_argument("--img-kb", type=float, default=200, help="大图阈值，默认 200KB")
    ap.add_argument("--min-compress", type=float, default=10, help="判定未压缩的最小体积（KB），默认 10")
    ap.add_argument("--third-party-max", type=int, default=20, help="第三方请求数告警阈值，默认 20")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="存在 high 级问题时退出码 1")
    a = ap.parse_args()

    res = analyze(load(a.file), a)
    if a.json:
        out = {"summary": {**res["totals"], "wall_ms": res["wall_ms"], "page_timings": res["page_timings"],
                           "first_party": res["first_party"], "creator": res["creator"]},
               "slowest": [{k: r[k] for k in ("url", "method", "status", "type", "time", "timings")}
                           for r in sorted(res["rows"], key=lambda r: -r["time"])[: a.top]],
               "largest": [{k: r[k] for k in ("url", "type", "transfer", "content", "enc")}
                           for r in sorted(res["rows"], key=lambda r: -r["transfer"])[: a.top]],
               "by_host": {h: b for h, b in sorted(res["by_host"].items(), key=lambda kv: -kv[1]["transfer"])},
               "by_type": dict(res["by_type"]),
               "issues": [{k: i[k] for k in ("level", "code", "title", "items", "hint")} for i in res["issues"] if i["items"]]}
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    else:
        report(res, a)
    if a.strict and any(i["level"] == "high" and i["items"] for i in res["issues"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
