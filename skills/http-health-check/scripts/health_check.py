#!/usr/bin/env python3
"""服务健康巡检：并发请求一批 URL，报告状态码、耗时、TLS 证书到期、内容关键字；纯标准库。

用法：
  python3 health_check.py https://a.example.com/health https://b.example.com/
  python3 health_check.py --file endpoints.txt --timeout 5 --expect-ms 800 --json
  endpoints.txt 每行：URL [期望状态码] [必须包含的关键字]，# 开头为注释
"""
import argparse, concurrent.futures as cf, datetime as dt, json, socket, ssl, sys, time, urllib.error, urllib.request

HEADERS = {"User-Agent": "health-check/0.1"}


def tls_days_left(host, port, timeout):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as s:
            cert = s.getpeercert()
    exp = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.timezone.utc)
    return (exp - dt.datetime.now(dt.timezone.utc)).days, exp.date().isoformat()


def probe(url, expect, keyword, timeout):
    r = {"url": url, "ok": False, "status": None, "ms": None, "error": None, "tls_days": None, "tls_expires": None, "keyword_ok": None}
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
            r["status"] = resp.status
    except urllib.error.HTTPError as e:
        r["status"] = e.code; body = b""
    except Exception as e:  # 超时、DNS、连接拒绝、TLS 错误
        r["error"] = f"{type(e).__name__}: {e}"; body = b""
    r["ms"] = round((time.perf_counter() - t0) * 1000)
    if keyword is not None:
        r["keyword_ok"] = keyword.encode() in body
    if url.startswith("https://"):
        host = url.split("/")[2]
        h, _, p = host.partition(":")
        try:
            r["tls_days"], r["tls_expires"] = tls_days_left(h, int(p or 443), timeout)
        except Exception as e:
            r["tls_error"] = f"{type(e).__name__}"
    r["ok"] = r["error"] is None and r["status"] == expect and (r["keyword_ok"] in (None, True))
    return r


def main():
    ap = argparse.ArgumentParser(description="HTTP 健康巡检")
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--timeout", type=float, default=8)
    ap.add_argument("--expect-ms", type=int, default=1000, help="耗时超过此值标 slow")
    ap.add_argument("--tls-warn-days", type=int, default=21)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    targets = []
    for u in a.urls:
        targets.append((u, 200, None))
    if a.file:
        for line in open(a.file, encoding="utf-8"):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(maxsplit=2)
            url = parts[0]
            expect = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 200
            kw = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 and not parts[1].isdigit() else None)
            targets.append((url, expect, kw))
    if not targets:
        ap.error("请给出 URL 或 --file")
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(lambda t: probe(t[0], t[1], t[2], a.timeout), targets))
    for r, (_, expect, _) in zip(results, targets):
        r["expect"] = expect
        r["slow"] = r["ms"] is not None and r["ms"] > a.expect_ms and r["error"] is None
        r["tls_warn"] = r["tls_days"] is not None and r["tls_days"] < a.tls_warn_days
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"巡检 {len(results)} 个端点  {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        for r in results:
            flag = "✓" if r["ok"] and not r["slow"] and not r["tls_warn"] else "✗" if not r["ok"] else "!"
            st = r["status"] if r["status"] is not None else "-"
            extra = []
            if r["error"]: extra.append(r["error"])
            elif r["status"] != r["expect"]: extra.append(f"期望 {r['expect']}")
            if r["keyword_ok"] is False: extra.append("关键字缺失")
            if r["slow"]: extra.append(f"慢（>{a.expect_ms}ms）")
            if r["tls_days"] is not None:
                extra.append(f"证书剩 {r['tls_days']} 天" + ("⚠" if r["tls_warn"] else ""))
            print(f"  {flag} {st:>3} {str(r['ms']) + 'ms':>7}  {r['url']}  {'；'.join(extra)}")
        bad = [r for r in results if not r["ok"]]
        print(f"\n异常 {len(bad)} / 慢 {sum(1 for r in results if r['slow'])} / 证书告警 {sum(1 for r in results if r['tls_warn'])}")
    sys.exit(1 if any(not r["ok"] for r in results) else 0)


if __name__ == "__main__":
    main()
