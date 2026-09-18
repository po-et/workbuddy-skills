#!/usr/bin/env python3
"""TLS 证书批量巡检：到期天数、SAN 覆盖、信任链、协议与密钥强度；并发、纯标准库。

用法：
  python3 tls_check.py www.example.com api.example.com:8443
  python3 tls_check.py --file hosts.txt --warn-days 30 --crit-days 7 --json
  hosts.txt 每行：host[:port]，# 开头为注释，行尾可跟备注
退出码：有 crit 则 1；--strict 时 warn 也算失败。
实现：先按系统信任库做一次完整校验握手；失败时降级为不校验握手，仍抓回证书 DER 自行解析
      （最小 ASN.1 解析，取到期时间、颁发者、SAN、公钥算法与位数、签名算法），并把失败原因如实报出。
"""
import argparse, concurrent.futures as cf, datetime as dt, ipaddress, json, re, socket, ssl, sys

OIDS = {
    "2.5.4.3": "CN", "2.5.4.10": "O", "2.5.4.11": "OU", "2.5.4.6": "C", "2.5.4.7": "L", "2.5.4.8": "ST",
    "1.2.840.113549.1.1.1": "RSA", "1.2.840.10045.2.1": "EC", "1.3.101.112": "Ed25519", "1.3.101.113": "Ed448",
    "1.2.840.113549.1.1.5": "sha1WithRSA", "1.2.840.113549.1.1.11": "sha256WithRSA",
    "1.2.840.113549.1.1.12": "sha384WithRSA", "1.2.840.113549.1.1.13": "sha512WithRSA",
    "1.2.840.113549.1.1.10": "RSASSA-PSS", "1.2.840.10045.4.1": "ecdsa-with-SHA1",
    "1.2.840.10045.4.3.2": "ecdsa-with-SHA256", "1.2.840.10045.4.3.3": "ecdsa-with-SHA384",
    "1.2.840.10045.4.3.4": "ecdsa-with-SHA512",
}
CURVE_BITS = {"1.2.840.10045.3.1.7": ("P-256", 256), "1.3.132.0.34": ("P-384", 384), "1.3.132.0.35": ("P-521", 521),
              "1.3.132.0.10": ("secp256k1", 256), "1.2.840.10045.3.1.1": ("P-192", 192), "1.3.132.0.33": ("P-224", 224)}
WEAK_SIG = ("sha1WithRSA", "ecdsa-with-SHA1", "md5WithRSA")
SAN_OID, BC_OID, EKU_OID = "2.5.29.17", "2.5.29.19", "2.5.29.37"


# ---------------------------------------------------------------- 最小 ASN.1 / DER
def tlv(b, i):
    """读一个 TLV，返回 (tag, 内容, 下一位置)。"""
    tag = b[i]; i += 1
    n = b[i]; i += 1
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(b[i:i + k], "big"); i += k
    return tag, b[i:i + n], i + n


def items(b):
    out, i = [], 0
    while i < len(b):
        t, c, i = tlv(b, i)
        out.append((t, c))
    return out


def oid(b):
    if not b:
        return ""
    parts, val = [str(b[0] // 40), str(b[0] % 40)], 0
    for x in b[1:]:
        val = (val << 7) | (x & 0x7F)
        if not x & 0x80:
            parts.append(str(val)); val = 0
    return ".".join(parts)


def asn1_time(tag, raw):
    s = raw.decode("ascii", "replace").strip()
    fmt = "%y%m%d%H%M%S" if tag == 0x17 else "%Y%m%d%H%M%S"
    s = s[:-1] if s.endswith("Z") else s.split("+")[0].split("-")[0]
    if len(s) == (10 if tag == 0x17 else 12):          # 没有秒
        fmt = fmt[:-2]
    return dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc)


def rdn(seq):
    """Name -> {'CN': ..., 'O': ...}"""
    out = {}
    for _, rdn_set in items(seq):
        for _, attr in items(rdn_set):
            kids = items(attr)
            if len(kids) >= 2:
                key = OIDS.get(oid(kids[0][1]), oid(kids[0][1]))
                out.setdefault(key, kids[1][1].decode("utf-8", "replace"))
    return out


def pubkey_info(spki):
    alg, bits = "?", None
    kids = items(spki)
    if len(kids) < 2:
        return alg, bits
    alg_kids = items(kids[0][1])
    name = OIDS.get(oid(alg_kids[0][1]), oid(alg_kids[0][1]))
    alg = name
    if name == "RSA":
        body = kids[1][1][1:]                            # BIT STRING 首字节是 unused bits
        try:
            _, seq, _ = tlv(body, 0)
            mod = items(seq)[0][1].lstrip(b"\x00")
            bits = len(mod) * 8
        except (IndexError, ValueError):
            pass
    elif name == "EC" and len(alg_kids) > 1:
        curve, b = CURVE_BITS.get(oid(alg_kids[1][1]), (None, None))
        alg, bits = f"EC {curve}" if curve else "EC", b
    elif name in ("Ed25519", "Ed448"):
        bits = 256 if name == "Ed25519" else 456
    return alg, bits


def parse_cert(der):
    """解析 DER 证书，取出巡检要用的字段；解析不出来的项留空而不是猜。"""
    c = {"subject": {}, "issuer": {}, "san": [], "san_ip": [], "not_before": None, "not_after": None,
         "key_alg": None, "key_bits": None, "sig_alg": None, "self_signed": None, "is_ca": None, "serial": None}
    _, cert, _ = tlv(der, 0)
    kids = items(cert)
    tbs = kids[0][1]
    c["sig_alg"] = OIDS.get(oid(items(kids[1][1])[0][1]), oid(items(kids[1][1])[0][1])) if len(kids) > 1 else None
    f = items(tbs)
    k = 0
    if f and f[0][0] == 0xA0:                             # [0] version
        k = 1
    c["serial"] = f[k][1].hex(); k += 1
    k += 1                                                # signature AlgorithmIdentifier
    issuer_raw = f[k][1]; c["issuer"] = rdn(issuer_raw); k += 1
    validity = items(f[k][1]); k += 1
    c["not_before"] = asn1_time(*validity[0])
    c["not_after"] = asn1_time(*validity[1])
    subject_raw = f[k][1]; c["subject"] = rdn(subject_raw); k += 1
    c["self_signed"] = issuer_raw == subject_raw
    c["key_alg"], c["key_bits"] = pubkey_info(f[k][1]); k += 1
    for tag, body in f[k:]:
        if tag != 0xA3:                                   # [3] extensions
            continue
        _, exts, _ = tlv(body, 0)
        for _, ext in items(exts):
            e = items(ext)
            o = oid(e[0][1])
            val = e[-1][1]
            if o == SAN_OID:
                _, names, _ = tlv(val, 0)
                for t, v in items(names):
                    if t == 0x82:
                        c["san"].append(v.decode("ascii", "replace"))
                    elif t == 0x87:
                        try:
                            c["san_ip"].append(str(ipaddress.ip_address(v)))
                        except ValueError:
                            pass
            elif o == BC_OID:
                try:
                    _, bc, _ = tlv(val, 0)
                    kk = items(bc)
                    c["is_ca"] = bool(kk and kk[0][0] == 0x01 and kk[0][1] == b"\xff")
                except (IndexError, ValueError):
                    pass
    return c


# ---------------------------------------------------------------- 主机名匹配
def host_matches(cert, host):
    try:
        ip = str(ipaddress.ip_address(host))
        return ip in cert["san_ip"], cert["san_ip"] or []
    except ValueError:
        pass
    names = cert["san"] or ([cert["subject"].get("CN")] if cert["subject"].get("CN") else [])
    h = host.lower().rstrip(".")
    for p in names:
        p = (p or "").lower().rstrip(".")
        if p.startswith("*."):
            first, _, rest = h.partition(".")
            if first and rest and rest == p[2:]:
                return True, names
        elif p == h:
            return True, names
    return False, names


# ---------------------------------------------------------------- 探测
def relaxed_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for setter in (lambda: setattr(ctx, "minimum_version", ssl.TLSVersion.MINIMUM_SUPPORTED),
                   lambda: ctx.set_ciphers("DEFAULT:@SECLEVEL=0")):
        try:
            setter()
        except (ValueError, AttributeError, ssl.SSLError):
            pass
    return ctx


def probe(target, timeout):
    host, _, p = target.rpartition(":")
    if not host or "]" in p:                              # 没写端口，或是 IPv6 字面量
        host, port = target, 443
    else:
        port = int(p) if p.isdigit() else 443
    host = host.strip("[]")
    r = {"target": target, "host": host, "port": port, "trusted": None, "verify_error": None, "error": None,
         "tls_version": None, "cipher": None, "days_left": None, "not_after": None, "not_before": None,
         "issuer": None, "subject": None, "san": [], "san_covers_host": None, "key": None, "sig_alg": None,
         "self_signed": None, "serial": None, "status": "ok", "notes": []}
    der = None
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            with ssl.create_default_context().wrap_socket(s, server_hostname=host) as t:
                r["trusted"] = True
                r["tls_version"], r["cipher"] = t.version(), (t.cipher() or [None])[0]
                der = t.getpeercert(binary_form=True)
    except ssl.SSLCertVerificationError as e:
        r["trusted"] = False
        r["verify_error"] = getattr(e, "verify_message", None) or str(e).split("] ")[-1]
    except ssl.SSLError as e:
        r["trusted"] = False
        r["verify_error"] = f"{type(e).__name__}: {getattr(e, 'reason', '') or e}"
    except (socket.gaierror, socket.timeout, OSError) as e:
        r["error"] = f"{type(e).__name__}: {e}"
        r["status"] = "crit"; r["notes"].append("连不上或握手失败")
        return r
    if der is None:                                       # 校验失败，降级再抓一次证书
        try:
            with socket.create_connection((host, port), timeout=timeout) as s:
                with relaxed_context().wrap_socket(s, server_hostname=host) as t:
                    r["tls_version"], r["cipher"] = t.version(), (t.cipher() or [None])[0]
                    der = t.getpeercert(binary_form=True)
        except (ssl.SSLError, socket.timeout, OSError) as e:
            r["error"] = f"{type(e).__name__}: {e}"
            r["status"] = "crit"; r["notes"].append("握手失败，拿不到证书")
            return r
    try:
        c = parse_cert(der)
    except (IndexError, ValueError, UnicodeDecodeError) as e:
        r["error"] = f"证书解析失败 {type(e).__name__}"
        r["status"] = "crit"; r["notes"].append("DER 解析失败，用 openssl s_client 手工确认")
        return r
    now = dt.datetime.now(dt.timezone.utc)
    r["not_after"] = c["not_after"].date().isoformat()
    r["not_before"] = c["not_before"].date().isoformat()
    r["days_left"] = (c["not_after"] - now).days
    r["issuer"] = c["issuer"].get("CN") or c["issuer"].get("O") or "?"
    r["subject"] = c["subject"].get("CN") or "?"
    r["san"] = c["san"] + c["san_ip"]
    r["self_signed"] = c["self_signed"]
    r["sig_alg"] = c["sig_alg"]
    r["serial"] = c["serial"]
    r["key"] = f"{c['key_alg']} {c['key_bits']}" if c["key_bits"] else (c["key_alg"] or "不可得")
    ok, _ = host_matches(c, host)
    r["san_covers_host"] = ok
    return r


def grade(r, warn_days, crit_days):
    if r["status"] == "crit":
        return r
    n = r["notes"]
    sev = "ok"

    def bump(level, note):
        nonlocal sev
        n.append(note)
        if level == "crit":
            sev = "crit"
        elif sev != "crit":
            sev = "warn"

    if r["days_left"] is not None and r["days_left"] < 0:
        bump("crit", f"已过期 {-r['days_left']} 天")
    elif r["days_left"] is not None and r["days_left"] <= crit_days:
        bump("crit", f"仅剩 {r['days_left']} 天")
    elif r["days_left"] is not None and r["days_left"] <= warn_days:
        bump("warn", f"剩 {r['days_left']} 天")
    if r["san_covers_host"] is False:
        bump("crit", "SAN 不覆盖该主机名")
    if r["trusted"] is False:
        if r["self_signed"]:
            bump("crit", "自签证书")
        elif r["verify_error"]:
            bump("crit", f"不受信任：{r['verify_error']}")
        else:
            bump("crit", "证书校验未通过")
    if r["tls_version"] in ("TLSv1", "TLSv1.1", "SSLv3"):
        bump("warn", f"协议过旧：{r['tls_version']}")
    if r["sig_alg"] in WEAK_SIG:
        bump("warn", f"弱签名算法：{r['sig_alg']}")
    key = r["key"] or ""
    m = re.search(r"(\d+)$", key)
    if key.startswith("RSA") and m and int(m.group(1)) < 2048:
        bump("warn", f"RSA 密钥仅 {m.group(1)} 位")
    if key.startswith("EC") and m and int(m.group(1)) < 256:
        bump("warn", f"EC 密钥仅 {m.group(1)} 位")
    r["status"] = sev
    return r


def load_targets(args):
    t = list(args.hosts)
    if args.file:
        for line in open(args.file, encoding="utf-8"):
            s = line.split("#")[0].strip()
            if s:
                t.append(s.split()[0])
    seen, out = set(), []
    for x in t:
        if x not in seen:
            seen.add(x); out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser(description="TLS 证书批量巡检")
    ap.add_argument("hosts", nargs="*", help="host[:port]，默认端口 443")
    ap.add_argument("--file", help="主机清单文件，每行一个 host[:port]")
    ap.add_argument("--warn-days", type=int, default=30)
    ap.add_argument("--crit-days", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=8)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 warn 也退出码 1")
    a = ap.parse_args()
    targets = load_targets(a)
    if not targets:
        ap.error("请给出主机或 --file")
    with cf.ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        results = list(ex.map(lambda t: probe(t, a.timeout), targets))
    results = [grade(r, a.warn_days, a.crit_days) for r in results]
    results.sort(key=lambda r: (r["days_left"] is not None, r["days_left"] if r["days_left"] is not None else 0, r["target"]))
    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("crit", "warn", "ok")}
    if a.json:
        print(json.dumps({"checked": len(results), "warn_days": a.warn_days, "crit_days": a.crit_days,
                          "summary": counts, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"巡检 {len(results)} 个目标  阈值 crit<{a.crit_days}d / warn<{a.warn_days}d  "
              f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        for r in results:
            flag = {"crit": "✗", "warn": "!", "ok": "✓"}[r["status"]]
            days = "-" if r["days_left"] is None else f"{r['days_left']}d"
            print(f"  {flag} {days:>6}  {r['not_after'] or '-':10}  {r['target']}")
            meta = [x for x in (r["issuer"] and f"颁发者 {r['issuer']}", r["tls_version"],
                                r["key"] and f"密钥 {r['key']}", r["sig_alg"]) if x]
            if meta:
                print(f"            {' | '.join(meta)}")
            if r["notes"]:
                print(f"            → {'；'.join(r['notes'])}")
            if r["error"]:
                print(f"            → {r['error']}")
        print(f"\n小计：crit {counts['crit']} / warn {counts['warn']} / ok {counts['ok']}")
    sys.exit(1 if counts["crit"] or (a.strict and counts["warn"]) else 0)


if __name__ == "__main__":
    main()
