#!/usr/bin/env python3
"""域名解析巡检：自己拼 DNS 报文走 UDP/TCP 查询，多解析器对比、TTL、CNAME 链、期望值校验。纯标准库。

用法：
  python3 dns_check.py www.example.com
  python3 dns_check.py example.com --type A,MX,TXT --server 8.8.8.8 --server 223.5.5.5
  python3 dns_check.py www.example.com --expect 93.184.215.14 --json
退出码：0 全部正常；1 解析失败（超时 / NXDOMAIN / SERVFAIL）、与 --expect 不一致，
        或加了 --fail-on-empty、--fail-on-diff 时命中对应条件。
"""
import argparse
import json
import random
import socket
import struct
import sys
import time

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}
TYPE_NAMES = {v: k for k, v in TYPES.items()}
RCODES = {0: "NOERROR", 1: "FORMERR（报文格式错）", 2: "SERVFAIL（解析器自己出错）",
          3: "NXDOMAIN（域名不存在）", 4: "NOTIMP（不支持）", 5: "REFUSED（拒绝应答）"}
FALLBACK_SERVERS = ["8.8.8.8", "1.1.1.1"]


# ------------------------------------------------------------------ 报文构造与解析

def encode_name(name):
    out = b""
    for label in name.rstrip(".").split("."):
        if not label:
            continue
        try:
            b = label.encode("idna")          # 中文域名转 punycode
        except (UnicodeError, ValueError):
            b = label.encode("ascii", "ignore")
        if len(b) > 63:
            raise ValueError(f"标签超过 63 字节: {label}")
        out += bytes([len(b)]) + b
    return out + b"\x00"


def build_query(name, qtype, qid, rd=True):
    """头部 12 字节：ID / 标志 / QDCOUNT / ANCOUNT / NSCOUNT / ARCOUNT。标志位 0x0100 = 期望递归。"""
    header = struct.pack(">HHHHHH", qid, 0x0100 if rd else 0, 1, 0, 0, 0)
    return header + encode_name(name) + struct.pack(">HH", qtype, 1)   # QCLASS=1 (IN)


def read_name(data, off):
    """解析域名，支持 0xC0 压缩指针；返回（域名，指针后的偏移）。"""
    labels, jumped, orig, hops = [], False, off, 0
    while True:
        if off >= len(data):
            raise ValueError("报文被截断")
        length = data[off]
        if length & 0xC0 == 0xC0:
            if off + 1 >= len(data):
                raise ValueError("压缩指针越界")
            ptr = struct.unpack(">H", data[off:off + 2])[0] & 0x3FFF
            if not jumped:
                orig = off + 2
            off, jumped = ptr, True
            hops += 1
            if hops > 32:
                raise ValueError("压缩指针成环")
            continue
        off += 1
        if length == 0:
            break
        labels.append(data[off:off + length])
        off += length
    return ".".join(l.decode("utf-8", "replace") for l in labels), (orig if jumped else off)


def parse_rdata(data, rtype, off, rdlen):
    end = off + rdlen
    if rtype == 1 and rdlen == 4:
        return socket.inet_ntoa(data[off:end])
    if rtype == 28 and rdlen == 16:
        return socket.inet_ntop(socket.AF_INET6, data[off:end])
    if rtype in (2, 5, 12):
        return read_name(data, off)[0] or "."
    if rtype == 15:
        pref = struct.unpack(">H", data[off:off + 2])[0]
        return f"{pref} {read_name(data, off + 2)[0] or '.'}"        # "0 ." 是 RFC 7505 空 MX
    if rtype == 16:
        parts, p = [], off
        while p < end:
            n = data[p]
            parts.append(data[p + 1:p + 1 + n].decode("utf-8", "replace"))
            p += 1 + n
        return "".join(parts)
    if rtype == 6:
        mname, p = read_name(data, off)
        rname, p = read_name(data, p)
        serial, refresh, retry, expire, minimum = struct.unpack(">IIIII", data[p:p + 20])
        return f"{mname} {rname} serial={serial} refresh={refresh} retry={retry} expire={expire} minimum={minimum}"
    if rtype == 257 and rdlen >= 2:
        flags, taglen = data[off], data[off + 1]
        tag = data[off + 2:off + 2 + taglen].decode("ascii", "replace")
        return f"{flags} {tag} {data[off + 2 + taglen:end].decode('utf-8', 'replace')}"
    return data[off:end].hex()


def parse_response(data, qid):
    if len(data) < 12:
        raise ValueError("响应长度不足 12 字节")
    rid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    if rid != qid:
        raise ValueError(f"响应 ID 不匹配（期望 {qid}，收到 {rid}），可能是串包或投毒")
    off = 12
    for _ in range(qd):
        _, off = read_name(data, off)
        off += 4
    sections = {"answers": an, "authority": ns, "additional": ar}
    out = {"rcode": flags & 0x0F, "truncated": bool(flags & 0x0200),
           "recursion_available": bool(flags & 0x0080), "authoritative": bool(flags & 0x0400),
           "answers": [], "authority": [], "additional": []}
    for key, count in sections.items():
        for _ in range(count):
            rname, off = read_name(data, off)
            rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", data[off:off + 10])
            off += 10
            try:
                value = parse_rdata(data, rtype, off, rdlen)
            except (ValueError, struct.error, OSError):
                value = data[off:off + rdlen].hex()
            off += rdlen
            out[key].append({"name": rname, "type": TYPE_NAMES.get(rtype, str(rtype)),
                             "ttl": ttl, "value": value})
    return out


# ------------------------------------------------------------------ 传输

def split_server(spec):
    """解析器写法：IP 或 IP#端口（dig 语法）；IPv6 直接写地址。"""
    host, _, port = spec.partition("#")
    return host.strip(), int(port) if port.strip() else 53


def udp_query(server, payload, timeout):
    host, port = split_server(server)
    fam = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(fam, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(payload, (host, port))
        while True:
            data, addr = s.recvfrom(4096)
            if addr[0] == host or fam == socket.AF_INET6:
                return data


def tcp_query(server, payload, timeout):
    host, port = split_server(server)
    fam = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(fam, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))
        s.sendall(struct.pack(">H", len(payload)) + payload)
        head = s.recv(2)
        if len(head) < 2:
            raise ValueError("TCP 响应头不完整")
        need = struct.unpack(">H", head)[0]
        buf = b""
        while len(buf) < need:
            chunk = s.recv(need - len(buf))
            if not chunk:
                raise ValueError("TCP 连接被提前关闭")
            buf += chunk
        return buf


def ask(server, name, rtype_name, timeout, retries, force_tcp=False):
    """一次查询：UDP 失败按 retries 重试，响应被截断自动转 TCP。"""
    qtype = TYPES[rtype_name]
    res = {"server": server, "name": name, "type": rtype_name, "error": None,
           "rcode": None, "rcode_text": None, "records": [], "ms": None,
           "truncated": False, "via": "tcp" if force_tcp else "udp", "attempts": 0}
    last_err = None
    for attempt in range(retries + 1):
        res["attempts"] = attempt + 1
        qid = random.randint(0, 0xFFFF)
        payload = build_query(name, qtype, qid)
        t0 = time.perf_counter()
        try:
            raw = tcp_query(server, payload, timeout) if force_tcp else udp_query(server, payload, timeout)
            parsed = parse_response(raw, qid)
            if parsed["truncated"] and not force_tcp:      # TC 位：改走 TCP 重查
                raw = tcp_query(server, payload, timeout)
                parsed = parse_response(raw, qid)
                res["via"], res["truncated"] = "tcp", True
            res["ms"] = round((time.perf_counter() - t0) * 1000, 1)
            res["rcode"] = parsed["rcode"]
            res["rcode_text"] = RCODES.get(parsed["rcode"], f"RCODE {parsed['rcode']}")
            res["authoritative"] = parsed["authoritative"]
            res["records"] = [r for r in parsed["answers"]]
            res["authority"] = parsed["authority"]
            return res
        except (socket.timeout, TimeoutError):
            last_err = f"超时（{timeout}s）"
        except OSError as e:
            last_err = f"{type(e).__name__}: {e}"
        except ValueError as e:
            last_err = str(e)
    res["error"] = last_err
    res["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return res


def system_servers():
    """从 /etc/resolv.conf 读本机解析器；读不到就用公共解析器兜底。"""
    out = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("nameserver") and len(line.split()) > 1:
                    out.append(line.split()[1])
    except OSError:
        pass
    return out or list(FALLBACK_SERVERS)


# ------------------------------------------------------------------ 分析

def cname_chain(name, records):
    """把 answer 段里的 CNAME 串成一条链。"""
    hops, cur, seen = [], name.rstrip(".").lower(), set()
    mapping = {r["name"].rstrip(".").lower(): r["value"].rstrip(".") for r in records if r["type"] == "CNAME"}
    while cur in mapping and cur not in seen:
        seen.add(cur)
        hops.append(mapping[cur])
        cur = mapping[cur].lower()
    return hops


def values_of(result, rtype):
    return sorted({r["value"] for r in result["records"] if r["type"] == rtype})


def min_ttl(result, rtype=None):
    ttls = [r["ttl"] for r in result["records"] if rtype is None or r["type"] == rtype]
    return min(ttls) if ttls else None


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser(description="域名解析巡检与切换验证")
    ap.add_argument("name", help="要查的域名")
    ap.add_argument("--type", default="A", help="记录类型，逗号分隔或 all，默认 A；可选 " + " ".join(TYPES))
    ap.add_argument("--server", action="append", help="指定解析器，可重复；支持 IP 或 IP#端口；默认读 /etc/resolv.conf")
    ap.add_argument("--expect", action="append", help="期望的 A/AAAA 值，可重复；不一致退出码 1")
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--retry", type=int, default=2, help="每次查询的重试次数，默认 2")
    ap.add_argument("--tcp", action="store_true", help="强制走 TCP")
    ap.add_argument("--no-dmarc", action="store_true", help="查 TXT 时不自动补查 _dmarc")
    ap.add_argument("--fail-on-diff", action="store_true", help="解析器之间结果不一致也算失败")
    ap.add_argument("--fail-on-empty", action="store_true", help="查到 NOERROR 但一条记录都没有（NODATA）也算失败")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    types = [t.strip().upper() for t in (list(TYPES) if a.type.lower() == "all" else a.type.split(","))]
    bad = [t for t in types if t not in TYPES]
    if bad:
        sys.exit(f"不支持的记录类型 {bad}，可选：{' '.join(TYPES)}")
    servers = a.server or system_servers()
    name = a.name.strip().rstrip(".")

    results, failures = {}, []
    for srv in servers:
        per_type = {}
        for t in types:
            r = ask(srv, name, t, a.timeout, a.retry, a.tcp)
            per_type[t] = r
            if r["error"]:
                failures.append(f"{srv} 查 {t} 失败：{r['error']}")
            elif r["rcode"] != 0:
                failures.append(f"{srv} 查 {t} 返回 {r['rcode_text']}")
            elif a.fail_on_empty and not r["records"]:
                failures.append(f"{srv} 查 {t} 无记录（NODATA）")
        if "TXT" in types and not a.no_dmarc:
            per_type["_DMARC"] = ask(srv, f"_dmarc.{name}", "TXT", a.timeout, a.retry, a.tcp)
        results[srv] = per_type

    # 解析器之间的差异（切换 DNS / 灰度生效核对用）
    diffs = {}
    for t in types:
        seen = {srv: tuple(values_of(results[srv][t], t)) for srv in servers if not results[srv][t]["error"]}
        uniq = set(seen.values())
        diffs[t] = {"consistent": len(uniq) <= 1, "by_server": {k: list(v) for k, v in seen.items()}}

    # 期望值校验
    expect_report = None
    if a.expect:
        want = sorted(set(a.expect))
        expect_report = {"want": want, "by_server": {}, "ok": True}
        for srv in servers:
            got = sorted(set(values_of(results[srv].get("A", {"records": []}), "A")
                             + values_of(results[srv].get("AAAA", {"records": []}), "AAAA")))
            hit = all(w in got for w in want)
            expect_report["by_server"][srv] = {"got": got, "ok": hit,
                                               "missing": [w for w in want if w not in got],
                                               "extra": [g for g in got if g not in want]}
            expect_report["ok"] &= hit
        if not expect_report["ok"]:
            failures.append("有解析器的结果与 --expect 不一致")

    # 邮件相关体检
    mail = {}
    if "TXT" in types:
        txts = []
        for srv in servers:
            txts += values_of(results[srv]["TXT"], "TXT")
        spf = [t for t in set(txts) if t.lower().startswith("v=spf1")]
        mail["spf"] = {"found": bool(spf), "records": spf}
        if not a.no_dmarc:
            dm = []
            for srv in servers:
                r = results[srv].get("_DMARC")
                if r and not r["error"]:
                    dm += [v for v in values_of(r, "TXT") if v.lower().startswith("v=dmarc1")]
            mail["dmarc"] = {"found": bool(dm), "records": sorted(set(dm))}
    if "MX" in types:
        mx = []
        for srv in servers:
            mx += values_of(results[srv]["MX"], "MX")
        mail["mx"] = {"found": bool(mx), "records": sorted(set(mx))}

    chains = {srv: cname_chain(name, results[srv][types[0]]["records"]) for srv in servers}
    diff_fail = a.fail_on_diff and any(not d["consistent"] for d in diffs.values())
    ok = not failures and not diff_fail

    if a.json:
        print(json.dumps({
            "name": name, "types": types, "servers": servers, "ok": ok,
            "results": {s: {t: r for t, r in per.items()} for s, per in results.items()},
            "consistency": diffs, "expect": expect_report, "mail": mail,
            "cname_chain": chains, "failures": failures,
        }, ensure_ascii=False, indent=2))
        sys.exit(0 if ok else 1)

    print(f"域名 {name}   类型 {','.join(types)}   解析器 {', '.join(servers)}")
    for srv in servers:
        print(f"\n[{srv}]")
        for t in types:
            r = results[srv][t]
            if r["error"]:
                print(f"  {t:<6} ✗ {r['error']}（重试 {r['attempts']} 次）")
                continue
            head = f"  {t:<6} {r['rcode_text']}  {r['ms']}ms  {r['via'].upper()}"
            recs = [x for x in r["records"] if x["type"] == t]
            cnames = [x for x in r["records"] if x["type"] == "CNAME"] if t != "CNAME" else []
            if r["rcode"] != 0:
                print(head + "  ✗")
                continue
            if not recs and not cnames:
                print(head + "  （无记录）")
                continue
            print(head)
            for x in cnames:
                print(f"         CNAME  {x['value']}  TTL {x['ttl']}")
            for x in recs:
                print(f"         {t:<5}  {x['value'][:100]}  TTL {x['ttl']}")
        ch = chains[srv]
        if ch:
            tail = "（每多一跳就多一次解析往返，超过两跳建议压平）" if len(ch) >= 2 else ""
            print(f"  CNAME 链 {' → '.join([name] + ch)}  {len(ch)} 跳{tail}")

    if len(servers) > 1:
        print("\n解析器一致性")
        for t in types:
            d = diffs[t]
            if d["consistent"]:
                print(f"  {t:<6} ✓ 各解析器结果一致")
            else:
                print(f"  {t:<6} ✗ 结果不一致（CDN/GeoDNS 按来源返回不同 IP 属正常；刚切过解析则等 TTL 过完再看）")
                for s, v in d["by_server"].items():
                    print(f"           {s} → {v or '（无记录）'}")

    if expect_report:
        print("\n期望值校验")
        for s, v in expect_report["by_server"].items():
            mark = "✓" if v["ok"] else "✗"
            extra = f"  缺 {v['missing']}" if v["missing"] else ""
            print(f"  {mark} {s} → {v['got'] or '（无记录）'}{extra}")

    if mail:
        print("\n邮件相关")
        if "mx" in mail:
            if mail["mx"]["records"] == ["0 ."]:
                print("  MX     ✓ Null MX（RFC 7505，本域明确声明不收邮件）")
            else:
                print(f"  MX     {'✓ ' + '; '.join(mail['mx']['records'][:3]) if mail['mx']['found'] else '✗ 没有 MX，收不了邮件'}")
        if "spf" in mail:
            print(f"  SPF    {'✓ ' + mail['spf']['records'][0][:80] if mail['spf']['found'] else '✗ 没有 SPF，易被伪造发件'}")
        if "dmarc" in mail:
            print(f"  DMARC  {'✓ ' + mail['dmarc']['records'][0][:80] if mail['dmarc']['found'] else '✗ 没有 DMARC，建议先用 p=none 观察'}")

    ttl = min((min_ttl(results[s][types[0]]) or 0) for s in servers) if servers else None
    if ttl:
        print(f"\n最小 TTL {ttl}s（切换解析前把 TTL 降到 60–300s，切换后再调回去）")
    print("结论：" + ("全部正常" if ok else "有问题 — " + "；".join(failures[:4]) or "解析器结果不一致"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
