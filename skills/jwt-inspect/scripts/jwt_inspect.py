#!/usr/bin/env python3
"""JWT 调试：解码 header/payload、解释常见声明、算过期状态、安全体检、可选 HMAC 验签。纯标准库。

用法：
  python3 jwt_inspect.py eyJhbGciOi...
  echo "$TOKEN" | python3 jwt_inspect.py
  python3 jwt_inspect.py --header "Authorization: Bearer eyJhbGciOi..."
  JWT_SECRET=... python3 jwt_inspect.py --verify --tz Asia/Shanghai
退出码：0 正常；1 已过期 / 未生效 / 验签失败 / 严重安全问题（如 alg=none）/ 令牌无法解析。
"""
import argparse
import base64
import binascii
import datetime as dt
import hashlib
import hmac
import json
import os
import sys

# 常见声明的中文解释（RFC 7519 注册声明 + 业界高频自定义声明）
CLAIMS = {
    "iss": "签发方（Issuer），谁签发的这枚令牌",
    "sub": "主体（Subject），令牌代表的用户或服务 ID",
    "aud": "受众（Audience），这枚令牌打算给谁用；服务端必须校验",
    "exp": "过期时间（Expiration），此刻之后令牌无效",
    "nbf": "生效时间（Not Before），此刻之前令牌无效",
    "iat": "签发时间（Issued At）",
    "jti": "令牌唯一 ID，用于防重放或做黑名单",
    "typ": "令牌类型，通常是 JWT",
    "alg": "签名算法；服务端必须白名单校验，不能听令牌的",
    "kid": "密钥 ID，多密钥轮换时用来选公钥",
    "cty": "内容类型，嵌套 JWT 时才出现",
    "scope": "权限范围（空格分隔）",
    "scp": "权限范围（数组形式）",
    "azp": "被授权方（Authorized Party），通常是客户端 ID",
    "client_id": "客户端 ID",
    "auth_time": "用户实际完成认证的时间",
    "nonce": "OIDC 防重放随机串",
    "sid": "会话 ID",
    "roles": "角色列表",
    "email": "邮箱",
    "name": "显示名",
    "preferred_username": "用户名",
}
TIME_CLAIMS = ("exp", "nbf", "iat", "auth_time")
HMAC_ALGS = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}
# payload 里出现这些键多半是把敏感信息塞进了「只是 base64、人人可读」的载荷
SENSITIVE_KEYS = ("password", "passwd", "pwd", "secret", "credential", "id_card", "idcard",
                  "id_number", "bank", "card_no", "private_key", "access_key")
LONG_LIFE_DAYS = 30


def b64url_decode(s):
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def human_delta(seconds):
    """把秒数写成「3 天 4 小时」这类人话。"""
    seconds = int(abs(seconds))
    if seconds < 60:
        return f"{seconds} 秒"
    units = (("天", 86400), ("小时", 3600), ("分钟", 60))
    out = []
    for label, size in units:
        n, seconds = divmod(seconds, size)
        if n:
            out.append(f"{n} {label}")
        if len(out) == 2:
            break
    return " ".join(out) or "0 分钟"


def fmt_time(ts, tz):
    try:
        return dt.datetime.fromtimestamp(float(ts), tz).strftime("%Y-%m-%d %H:%M:%S %Z")
    except (TypeError, ValueError, OSError, OverflowError):
        return f"<不是合法时间戳: {ts!r}>"


def read_token(args):
    """令牌可来自参数、--header、或 stdin。"""
    raw = None
    if args.token:
        raw = args.token
    elif args.header:
        raw = args.header
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    if not raw:
        return None
    raw = raw.strip().strip('"').strip("'")
    if ":" in raw.split(".")[0]:               # "Authorization: Bearer xxx"
        raw = raw.split(":", 1)[1].strip()
    for prefix in ("Bearer ", "bearer ", "BEARER "):
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
    return raw.split()[0] if raw.split() else None


def split_token(token):
    parts = token.split(".")
    if len(parts) == 5:
        raise ValueError("这是 5 段的 JWE（加密令牌），不是 JWS，本脚本只解 JWS")
    if len(parts) not in (2, 3):
        raise ValueError(f"JWT 应为 3 段（header.payload.signature），实际 {len(parts)} 段")
    if len(parts) == 2:
        parts = parts + [""]
    return parts


def decode_segment(seg, label):
    try:
        raw = b64url_decode(seg)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"{label} 不是合法 base64url：{e}") from e
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"{label} 解码后不是合法 JSON（这段大概率不是 JWT，或被截断了）：{e}") from e
    if not isinstance(obj, dict):
        raise ValueError(f"{label} 解码后不是 JSON 对象")
    return obj


def time_status(payload, now):
    """把 exp / nbf 换算成「还剩多久 / 过期多久」。"""
    st = {"expired": False, "not_yet_valid": False, "has_exp": "exp" in payload,
          "expires_in_sec": None, "valid_in_sec": None, "lifetime_sec": None}
    exp, nbf, iat = payload.get("exp"), payload.get("nbf"), payload.get("iat")
    if isinstance(exp, (int, float)):
        delta = exp - now
        st["expires_in_sec"] = delta
        st["expired"] = delta <= 0
        base = iat if isinstance(iat, (int, float)) else (nbf if isinstance(nbf, (int, float)) else None)
        if base is not None:
            st["lifetime_sec"] = exp - base
    if isinstance(nbf, (int, float)):
        delta = nbf - now
        st["valid_in_sec"] = delta
        st["not_yet_valid"] = delta > 0
    return st


def security_audit(header, payload, st, secret_on_cli):
    """安全体检：只看令牌本身能发现的问题，按严重程度给出处置建议。"""
    warns = []
    alg = str(header.get("alg", ""))
    if alg.lower() == "none":
        warns.append(("严重", "alg=none：签名被关闭，任何人都能伪造这枚令牌。服务端必须用算法白名单校验，"
                             "禁止按令牌自称的 alg 选择校验方式（CVE 级经典漏洞）"))
    if alg.upper().startswith("HS") and secret_on_cli:
        warns.append(("严重", "HS 系列密钥从命令行明文传入：会进 shell 历史、ps 输出与 CI 日志。"
                             "请改用环境变量 JWT_SECRET，例如 JWT_SECRET=xxx python3 jwt_inspect.py --verify"))
    if not st["has_exp"]:
        warns.append(("高", "缺少 exp：令牌永不过期，泄露后只能靠改密钥或黑名单止血，建议补上 exp"))
    life = st["lifetime_sec"]
    if life is not None and life > LONG_LIFE_DAYS * 86400:
        warns.append(("中", f"有效期 {human_delta(life)}，超过 {LONG_LIFE_DAYS} 天：访问令牌建议 15 分钟到几小时，"
                            "长期凭证交给 refresh token 并支持吊销"))
    if "aud" not in payload:
        warns.append(("低", "缺少 aud：多个服务共用同一签发方时，令牌可被跨服务重放，建议签发并校验 aud"))
    if "jti" not in payload and st["has_exp"] and life is not None and life > 86400:
        warns.append(("低", "缺少 jti：长效令牌没有唯一 ID，无法做吊销黑名单"))
    hit = [k for k in payload if any(s in str(k).lower() for s in SENSITIVE_KEYS)]
    if hit:
        warns.append(("高", f"payload 疑似含敏感字段 {hit}：JWT 载荷只是 base64 编码、不是加密，任何拿到令牌的人都能读"))
    if alg.upper() in ("HS256", "HS384", "HS512") and header.get("kid") is None:
        warns.append(("低", "没有 kid：密钥轮换时无法平滑切换，建议签发时带上"))
    order = {"严重": 0, "高": 1, "中": 2, "低": 3}
    return sorted(warns, key=lambda w: order.get(w[0], 9))


def verify(token, header, parts, args):
    """HS256/384/512 用环境变量 JWT_SECRET 做 HMAC 校验；RS/ES/PS 给出 openssl 命令。"""
    alg = str(header.get("alg", "")).upper()
    res = {"attempted": True, "alg": alg, "supported": alg in HMAC_ALGS, "ok": None, "detail": ""}
    if alg == "NONE":
        res["ok"] = False
        res["detail"] = "alg=none 没有签名可校验，直接判定不可信"
        return res
    if alg not in HMAC_ALGS:
        res["detail"] = (f"{alg or '未知算法'} 是非对称签名，校验需要公钥，本脚本只用 hmac/hashlib 不做非对称验签。"
                         "用下面的 openssl 命令验（把 pubkey.pem 换成你的公钥）")
        sha = "sha256"
        if alg.endswith("384"):
            sha = "sha384"
        elif alg.endswith("512"):
            sha = "sha512"
        res["openssl"] = (
            f"TOKEN='<把令牌粘这里，或 TOKEN=$(cat token.txt)>'\n"
            f"printf '%s' \"${{TOKEN%.*}}\" > jwt.in\n"
            f"sig=${{TOKEN##*.}}; pad=$(( (4 - ${{#sig}} % 4) % 4 ))\n"
            f"printf '%s%s' \"$sig\" \"$(printf '=%.0s' $(seq $pad))\" | tr '_-' '/+' | base64 -d > jwt.sig\n"
            f"openssl dgst -{sha} -verify pubkey.pem -signature jwt.sig jwt.in")
        if alg.startswith("ES"):
            res["openssl"] += ("\n# 注意：ES 系列签名是裸 R||S，openssl 需要 DER 编码，"
                               "直接验会报 bad signature，需先把 R/S 转成 DER")
        return res
    secret = os.environ.get("JWT_SECRET")
    if args.secret:
        secret = args.secret
    if not secret:
        res["ok"] = False
        res["detail"] = "没读到密钥：请设置环境变量 JWT_SECRET 后重试（别用命令行参数传密钥）"
        return res
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    expect = hmac.new(secret.encode(), signing_input, HMAC_ALGS[alg]).digest()
    try:
        actual = b64url_decode(parts[2])
    except (binascii.Error, ValueError):
        res["ok"] = False
        res["detail"] = "签名段不是合法 base64url"
        return res
    res["ok"] = hmac.compare_digest(expect, actual)
    res["detail"] = ("签名与提供的密钥匹配" if args.secret else "签名与 JWT_SECRET 匹配") if res["ok"] else "签名不匹配：密钥不对，或令牌被改过，或算法不是这个"
    if res["ok"] and len(secret) < 32:
        res["weak_secret"] = True
        res["detail"] += f"；但密钥只有 {len(secret)} 字符，HS256 建议 ≥ 32 字节随机串，短密钥可被离线爆破"
    return res


def render(tok, header, payload, st, warns, ver, tz, args):
    print("JWT 解析（不校验签名也能看，下面的内容任何人拿到令牌都能读）")
    print(f"  段长度：header {len(tok[0])} / payload {len(tok[1])} / signature {len(tok[2])} 字符\n")
    print("Header")
    print(json.dumps(header, ensure_ascii=False, indent=2))
    for k in header:
        if k in CLAIMS:
            print(f"    {k:<8} {CLAIMS[k]}")
    print("\nPayload")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("\n声明解释")
    for k, v in payload.items():
        meaning = CLAIMS.get(k, "自定义声明（业务方自己约定的字段）")
        if k in TIME_CLAIMS and isinstance(v, (int, float)):
            print(f"    {k:<8} {fmt_time(v, tz)}  — {meaning}")
        else:
            shown = json.dumps(v, ensure_ascii=False)
            print(f"    {k:<8} {shown[:80]}  — {meaning}")
    print("\n时间状态")
    if st["expires_in_sec"] is None:
        print("    exp   无（令牌永不过期）")
    elif st["expired"]:
        print(f"    exp   已过期 {human_delta(st['expires_in_sec'])}（{fmt_time(payload['exp'], tz)}）")
    else:
        print(f"    exp   还剩 {human_delta(st['expires_in_sec'])}（{fmt_time(payload['exp'], tz)}）")
    if st["valid_in_sec"] is not None:
        if st["not_yet_valid"]:
            print(f"    nbf   未生效，还要等 {human_delta(st['valid_in_sec'])}（{fmt_time(payload['nbf'], tz)}）")
        else:
            print(f"    nbf   已生效 {human_delta(st['valid_in_sec'])}（{fmt_time(payload['nbf'], tz)}）")
    if st["lifetime_sec"] is not None:
        print(f"    有效期 {human_delta(st['lifetime_sec'])}")
    print(f"    当前时间 {dt.datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    if warns:
        print("\n安全体检")
        for level, msg in warns:
            print(f"    [{level}] {msg}")
    else:
        print("\n安全体检  未发现明显问题")
    if ver:
        print("\n签名校验")
        if ver["ok"] is True:
            print(f"    ✓ {ver['alg']}  {ver['detail']}")
        elif ver["ok"] is False:
            print(f"    ✗ {ver['alg']}  {ver['detail']}")
        else:
            print(f"    - {ver['alg']}  {ver['detail']}")
        if ver.get("openssl"):
            print("\n    " + ver["openssl"].replace("\n", "\n    "))
    reasons = []
    if st["expired"]:
        reasons.append("已过期")
    if st["not_yet_valid"]:
        reasons.append("未到生效时间")
    if ver and ver["ok"] is False:
        reasons.append("验签失败")
    if any(lv == "严重" for lv, _ in warns):
        reasons.append("存在严重安全问题")
    print(f"\n结论：{'有问题（' + '、'.join(reasons) + '）' if reasons else '可用'}")
    if not args.verify:
        print("提示：本次未验签，只解码。要验 HS256 请 JWT_SECRET=... 加 --verify")


def main():
    ap = argparse.ArgumentParser(description="JWT 解码与体检")
    ap.add_argument("token", nargs="?", help="JWT 字符串；省略则从 stdin 读")
    ap.add_argument("--header", help='形如 "Authorization: Bearer eyJ..." 的整行，自动剥掉前缀')
    ap.add_argument("--verify", action="store_true", help="HS256/384/512 用环境变量 JWT_SECRET 验签")
    ap.add_argument("--secret", help="不推荐：明文密钥，会进 shell 历史，脚本会警告")
    ap.add_argument("--tz", help="时间显示时区，如 Asia/Shanghai；默认本机时区")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tz = None
    if args.tz:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(args.tz)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"时区 {args.tz!r} 不可用：{e}")
    else:
        tz = dt.datetime.now().astimezone().tzinfo

    token = read_token(args)
    if not token:
        ap.error("没拿到令牌：给个位置参数、或 --header、或从管道喂进来")
    try:
        parts = split_token(token)
        header = decode_segment(parts[0], "header")
        payload = decode_segment(parts[1], "payload")
    except ValueError as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        else:
            print(f"✗ 解析失败：{e}")
        sys.exit(1)

    now = dt.datetime.now(dt.timezone.utc).timestamp()
    st = time_status(payload, now)
    warns = security_audit(header, payload, st, bool(args.secret))
    ver = verify(token, header, parts, args) if args.verify else None
    bad = (st["expired"] or st["not_yet_valid"] or (ver is not None and ver["ok"] is False)
           or any(lv == "严重" for lv, _ in warns))

    if args.json:
        print(json.dumps({
            "ok": not bad, "header": header, "payload": payload,
            "claims": {k: {"value": v, "meaning": CLAIMS.get(k, "自定义声明"),
                           "time": fmt_time(v, tz) if k in TIME_CLAIMS and isinstance(v, (int, float)) else None}
                       for k, v in payload.items()},
            "time_status": {**st,
                            "exp_at": fmt_time(payload["exp"], tz) if isinstance(payload.get("exp"), (int, float)) else None,
                            "nbf_at": fmt_time(payload["nbf"], tz) if isinstance(payload.get("nbf"), (int, float)) else None,
                            "expires_in_human": human_delta(st["expires_in_sec"]) if st["expires_in_sec"] is not None else None},
            "warnings": [{"level": lv, "message": m} for lv, m in warns],
            "verify": ver,
        }, ensure_ascii=False, indent=2))
    else:
        render(parts, header, payload, st, warns, ver, tz, args)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
