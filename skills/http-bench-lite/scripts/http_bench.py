#!/usr/bin/env python3
"""轻量 HTTP 压测：线程池 + urllib，统计成功率、状态码分布、QPS、延迟分位与传输量。纯标准库。

只用于压自己的服务与测试环境。目标不是 localhost / 回环 / 私网地址时，必须显式加 --yes。

用法：
  python3 http_bench.py http://127.0.0.1:8000/ -n 200 -c 10
  python3 http_bench.py http://127.0.0.1:8000/api -d 20 -c 20 --method POST --body '{"a":1}' \
      --header "Content-Type: application/json"
  python3 http_bench.py https://staging.example.com/health -n 500 -c 20 --yes --json
退出码：0 成功率达标；1 成功率低于 --min-success 或一个请求都没跑成；2 参数错误或安全闸门拦截。
"""
import argparse
import ipaddress
import json
import socket
import ssl
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_CONCURRENCY = 50      # 上限：这是自测工具，不是攻击工具
MAX_DURATION = 120        # 秒
MAX_REQUESTS = 50000
PCTS = (50, 90, 95, 99)


def die(msg):
    """参数错误 / 安全闸门统一走退出码 2。"""
    print(msg, file=sys.stderr)
    sys.exit(2)


def percentile(sorted_vals, pct):
    """最近秩法（nearest-rank），样本少时也不会给出插值出来的假精度。"""
    if not sorted_vals:
        return None
    k = max(1, min(len(sorted_vals), int(-(-pct * len(sorted_vals) // 100))))
    return sorted_vals[k - 1]


def is_local_target(host):
    """回环 / 私网 / .localhost 视为自有环境；解析失败按「非本地」处理，宁可多问一句。"""
    h = (host or "").strip("[]").lower()
    if h in ("localhost", "::1") or h.endswith(".localhost"):
        return True, "回环地址"
    try:
        ip = ipaddress.ip_address(h)
        addrs = [ip]
    except ValueError:
        try:
            addrs = [ipaddress.ip_address(ai[4][0]) for ai in socket.getaddrinfo(h, None)]
        except (socket.gaierror, ValueError):
            return False, "域名解析不出来，无法判断是不是自有环境"
    if not addrs:
        return False, "解析不到地址"
    if all(a.is_loopback for a in addrs):
        return True, "回环地址"
    if all(a.is_loopback or a.is_private for a in addrs):
        return True, "私网地址"
    return False, "公网地址（" + ", ".join(str(a) for a in addrs[:3]) + "）"


def build_request(args, body_bytes):
    req = urllib.request.Request(args.url, data=body_bytes, method=args.method.upper())
    req.add_header("User-Agent", "http-bench-lite/0.1")
    for h in args.header or []:
        if ":" not in h:
            die(f"--header 需要 K:V 形式，收到 {h!r}")
        k, _, v = h.partition(":")
        req.add_header(k.strip(), v.strip())
    if body_bytes and not any(k.lower() == "content-type" for k in req.headers):
        req.add_header("Content-Type", "application/octet-stream")
    return req


class Runner:
    def __init__(self, args, req, ctx):
        self.args, self.req, self.ctx = args, req, ctx
        self.lock = threading.Lock()
        self.issued = 0
        self.records = []
        self.deadline = None

    def _take_slot(self):
        with self.lock:
            if self.args.requests and self.issued >= self.args.requests:
                return False
            if self.deadline and time.monotonic() >= self.deadline:
                return False
            self.issued += 1
            return True

    def worker(self):
        local = []
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.ctx))
        while self._take_slot():
            status, nbytes, err = None, 0, None
            t0 = time.perf_counter()
            try:
                with opener.open(self.req, timeout=self.args.timeout) as resp:
                    body = resp.read()
                    status, nbytes = resp.status, len(body)
            except urllib.error.HTTPError as e:      # 4xx/5xx 也是完成的请求
                status = e.code
                try:
                    nbytes = len(e.read() or b"")
                except OSError:
                    nbytes = 0
            except urllib.error.URLError as e:       # 展开底层原因，URLError 本身看不出问题
                err = type(e.reason).__name__ if e.reason is not None else "URLError"
            except Exception as e:                   # noqa: BLE001 超时、TLS、协议错误
                err = type(e).__name__
            local.append((round((time.perf_counter() - t0) * 1000, 3), status, nbytes, err))
        with self.lock:
            self.records.extend(local)

    def run(self):
        if self.args.duration:
            self.deadline = time.monotonic() + self.args.duration
        threads = [threading.Thread(target=self.worker, daemon=True) for _ in range(self.args.concurrency)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return self.records, time.perf_counter() - t0


def summarize(records, wall, args):
    lat = sorted(r[0] for r in records if r[3] is None)
    statuses, errors = {}, {}
    total_bytes = 0
    ok = 0
    for ms, status, nbytes, err in records:
        if err:
            errors[err] = errors.get(err, 0) + 1
            continue
        statuses[status] = statuses.get(status, 0) + 1
        total_bytes += nbytes
        if 200 <= status < 400:
            ok += 1
    n = len(records)
    s = {
        "url": args.url, "method": args.method.upper(), "concurrency": args.concurrency,
        "requests": n, "completed": len(lat), "ok": ok,
        "success_rate": round(100.0 * ok / n, 2) if n else 0.0,
        "wall_sec": round(wall, 3),
        "qps": round(n / wall, 2) if wall > 0 else 0.0,
        "ok_qps": round(ok / wall, 2) if wall > 0 else 0.0,
        "bytes": total_bytes,
        "bytes_per_sec": round(total_bytes / wall) if wall > 0 else 0,
        "status_dist": {str(k): v for k, v in sorted(statuses.items(), key=lambda kv: str(kv[0]))},
        "errors": errors,
        "latency_ms": {},
    }
    if lat:
        s["latency_ms"] = {
            "min": lat[0], "avg": round(statistics.fmean(lat), 3),
            **{f"p{p}": percentile(lat, p) for p in PCTS},
            "max": lat[-1],
            "stdev": round(statistics.pstdev(lat), 3) if len(lat) > 1 else 0.0,
        }
    return s


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def render(s, args):
    print("\n结果")
    print(f"  请求 {s['requests']} 个  成功 {s['ok']}  成功率 {s['success_rate']}%  耗时 {s['wall_sec']}s")
    print(f"  吞吐 {s['qps']} QPS（仅成功 {s['ok_qps']} QPS）  传输 {human_bytes(s['bytes'])}"
          f"  {human_bytes(s['bytes_per_sec'])}/s")
    if s["status_dist"]:
        print("  状态码 " + "  ".join(f"{k} × {v}" for k, v in s["status_dist"].items()))
    if s["errors"]:
        print("  错误   " + "  ".join(f"{k} × {v}" for k, v in s["errors"].items()))
    lm = s["latency_ms"]
    if lm:
        print(f"  延迟   min {lm['min']}ms  avg {lm['avg']}ms  p50 {lm['p50']}ms  p90 {lm['p90']}ms"
              f"  p95 {lm['p95']}ms  p99 {lm['p99']}ms  max {lm['max']}ms")
        if lm["p99"] and lm["p50"] and lm["p99"] > lm["p50"] * 5:
            print("  提示   p99 是 p50 的 5 倍以上，长尾明显：看 GC、连接池、慢依赖或冷启动")
    if s["success_rate"] < 100:
        print("  提示   有失败请求，先看错误类型与状态码，再谈性能数字")


def main():
    ap = argparse.ArgumentParser(description="轻量 HTTP 压测（仅用于自有服务与测试环境）")
    ap.add_argument("url")
    ap.add_argument("-c", "--concurrency", type=int, default=10, help=f"并发数，默认 10，上限 {MAX_CONCURRENCY}")
    ap.add_argument("-n", "--requests", type=int, help=f"总请求数，默认 200，上限 {MAX_REQUESTS}")
    ap.add_argument("-d", "--duration", type=int, help=f"压测时长（秒），与 -n 二选一，上限 {MAX_DURATION}")
    ap.add_argument("--method", default="GET")
    ap.add_argument("--header", action="append", help='形如 "Content-Type: application/json"，可重复')
    ap.add_argument("--body", help="请求体字符串")
    ap.add_argument("--body-file", help="从文件读请求体")
    ap.add_argument("--timeout", type=float, default=10.0, help="单请求超时秒数，默认 10")
    ap.add_argument("--min-success", type=float, default=99.0, help="成功率低于此值退出码 1，默认 99")
    ap.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验（自签测试环境）")
    ap.add_argument("--yes", action="store_true", help="确认目标是自己的服务；非本地目标必须带")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.requests and args.duration:
        die("-n 与 -d 只能选一个")
    if not args.requests and not args.duration:
        args.requests = 200
    if args.concurrency < 1 or args.concurrency > MAX_CONCURRENCY:
        die(f"并发数须在 1–{MAX_CONCURRENCY} 之间（本工具用于自测，不做大流量压测）")
    if args.duration and not 1 <= args.duration <= MAX_DURATION:
        die(f"时长须在 1–{MAX_DURATION} 秒之间")
    if args.requests and not 1 <= args.requests <= MAX_REQUESTS:
        die(f"总请求数须在 1–{MAX_REQUESTS} 之间")

    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        die("URL 需带 http:// 或 https:// 与主机名")
    local, why = is_local_target(parsed.hostname)
    if not local and not args.yes:
        print(f"目标 {parsed.hostname} 是{why}，不是本地或私网地址。")
        print("本工具只用于压自己的服务与测试环境。确认这是你自己有权压测的目标后，加 --yes 重跑。")
        sys.exit(2)

    body_bytes = None
    if args.body_file:
        with open(args.body_file, "rb") as f:
            body_bytes = f.read()
    elif args.body:
        body_bytes = args.body.encode()

    ctx = ssl.create_default_context()
    if args.insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = build_request(args, body_bytes)

    plan = f"{args.requests} 个请求" if args.requests else f"持续 {args.duration} 秒"
    if not args.json:
        print("目标   " + args.url)
        print(f"参数   {args.method.upper()}  并发 {args.concurrency}  {plan}  超时 {args.timeout}s"
              + (f"  请求体 {len(body_bytes)}B" if body_bytes else "")
              + ("  已跳过证书校验" if args.insecure else ""))
        print(f"范围   {'本地/私网目标' if local else '已用 --yes 确认的目标'}（{why}）")
        print("开跑 …")

    records, wall = Runner(args, req, ctx).run()
    if not records:
        print("一个请求都没发出去，检查 URL 与参数")
        sys.exit(1)
    s = summarize(records, wall, args)
    s["target_is_local"] = local

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        render(s, args)
    sys.exit(0 if s["success_rate"] >= args.min_success else 1)


if __name__ == "__main__":
    main()
