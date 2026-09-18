#!/usr/bin/env python3
"""日志与数据脱敏（防御性工具）：把手机号、身份证、银行卡、邮箱、IP、URL 凭据参数、JWT、AK/SK、私钥块、
连接串密码、以及「收货地址/联系人」这类明确标注的中文 PII 替换掉，用于对外分享前处理。纯标准库。

用法：
  python3 mask_sensitive.py app.log                       # 写到 app.log.masked
  python3 mask_sensitive.py logs/ --mode hash --report map.tsv
  python3 mask_sensitive.py dump.csv --mode fake --keep-format
  cat app.log | python3 mask_sensitive.py - > shared.log
脱敏不等于合规：敏感数据外发仍需按公司流程走审批。
"""
import argparse
import hashlib
import json
import os
import re
import sys

_D5 = "-" * 5

CATEGORIES = {                                  # cat -> (占位标签, 中文名)
    "privatekey": ("PRIVKEY", "私钥块"),
    "jwt": ("JWT", "JWT"),
    "apikey": ("APIKEY", "AK/SK 类密钥"),
    "dbpass": ("DBPASS", "连接串/配置里的密码"),
    "urltoken": ("URLTOKEN", "URL 凭据参数"),
    "idcard": ("IDCARD", "身份证号"),
    "bankcard": ("BANKCARD", "银行卡号"),
    "phone": ("PHONE", "手机号"),
    "email": ("EMAIL", "邮箱"),
    "ip": ("IP", "IP 地址"),
    "cnname": ("NAME", "中文姓名字段"),
    "cnaddr": ("ADDR", "地址字段"),
}
ORDER = list(CATEGORIES)                        # 先粗后细：长串先替换，避免被短模式切碎

RE_PRIVKEY = re.compile(_D5 + r"BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY" + _D5 + r"[\s\S]{0,8000}?"
                        + _D5 + r"END (?:[A-Z0-9]+ )*PRIVATE KEY" + _D5)
RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
RE_APIKEY = re.compile(r"\b(?:AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}"
                       r"|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,})")
RE_DBURL = re.compile(r"\b([a-z][a-z0-9+.\-]{1,20})://([^:@/\s\"']{1,64}):([^@\s\"']{1,80})@")
RE_PWDKV = re.compile(r"(?i)\b(?:password|passwd|pwd|db_pass|mysql_pwd)[\"']?\s*[=:]\s*[\"']?([^\s,;&\"'\]}]{3,80})")
RE_URLTOKEN = re.compile(r"(?i)([?&](?:access_token|refresh_token|id_token|token|api_?key|app_?key|app_?secret"
                         r"|secret|sig|signature|auth|session_?id|session|ticket|code|password|passwd|pwd)=)"
                         r"([^&\s\"'<>)\]}]{4,})")
RE_IDCARD = re.compile(r"(?<![0-9Xx])\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9Xx])")
RE_CARD = re.compile(r"(?<![\d-])(?:\d[ -]?){15,18}\d(?![\d-])")
RE_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
RE_EMAIL = re.compile(r"\b[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+\b")
RE_IP = re.compile(r"(?<![\w.])((?:\d{1,3}\.){3}\d{1,3})(?![\w.])")
# 中文 PII 走保守策略：只处理「字段名 + 冒号」这种明确标注，绝不猜正文里的人名地名
RE_CNNAME = re.compile(r"((?:收货人|联系人|收件人|姓名|真实姓名|持卡人|开户人)\s*[:：]\s*)([^\s,，;；、|]{2,12})")
RE_CNADDR = re.compile(r"((?:收货地址|联系地址|家庭地址|详细地址|住址|通讯地址|地址)\s*[:：]\s*)([^\n,，;；|]{4,80})")
FAKE_SURNAME = "赵钱孙李周吴郑王冯陈"
TEXT_EXT = {".log", ".txt", ".csv", ".tsv", ".json", ".jsonl", ".md", ".out", ".err", ".yaml", ".yml", ".sql", ".conf", ".ini", ".xml"}


def luhn(digits):
    s, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        s += d
        alt = not alt
    return s % 10 == 0


def valid_ip(s):
    parts = s.split(".")
    return len(parts) == 4 and all(p.isdigit() and len(p) <= 3 and int(p) <= 255 for p in parts)


def h8(val, salt):
    return hashlib.sha256((salt + "\x00" + val).encode("utf-8")).hexdigest()[:8]


def _bytes(seed):
    i = 0
    while True:
        for b in hashlib.sha256(f"{seed}#{i}".encode()).digest():
            yield b
        i += 1


def shaped_ip(val, seed):
    """保持点分四段形态且每段仍 ≤ 255（直接 shaped 会造出 923.5.956.16 这种非法地址）。"""
    g, out = _bytes(seed), []
    for octet in val.split("."):
        n = len(octet)
        out.append(str(next(g) % 10) if n == 1 else
                   f"{next(g) % 90 + 10:02d}" if n == 2 else f"{next(g) % 156 + 100:03d}")
    return ".".join(out)


def shaped(orig, seed):
    """保持长度与字符形态（数字→数字、字母→字母、其余原样）的确定性替换。"""
    g, out = _bytes(seed), []
    for ch in orig:
        if ch.isdigit():
            out.append(chr(48 + next(g) % 10))
        elif "a" <= ch <= "z":
            out.append(chr(97 + next(g) % 26))
        elif "A" <= ch <= "Z":
            out.append(chr(65 + next(g) % 26))
        elif "一" <= ch <= "鿿":
            out.append("某")
        else:
            out.append(ch)
    return "".join(out)


def keep_ends(val, head, tail, stars=0):
    if len(val) <= head + tail:
        return "*" * len(val)
    return val[:head] + "*" * (stars or max(3, len(val) - head - tail)) + (val[len(val) - tail:] if tail else "")


def mask_value(val, cat, keep_subnet):
    if cat == "phone":
        return keep_ends(val, 3, 4, 4)
    if cat == "idcard":
        return keep_ends(val, 6, 4, 8)
    if cat == "bankcard":
        return keep_ends(val, 6, 4)
    if cat == "email":
        local, _, dom = val.partition("@")
        return keep_ends(local, min(2, len(local) - 1) if len(local) > 1 else 0, 0, 3) + "@" + dom
    if cat == "ip":
        p = val.split(".")
        return ".".join(p[:keep_subnet] + ["*"] * (4 - keep_subnet))
    if cat == "privatekey":
        return f"<{CATEGORIES[cat][0]}_REMOVED>"
    if cat == "cnname":
        return val[0] + "*" * (len(val) - 1)
    if cat == "cnaddr":
        return keep_ends(val, 3, 0, 6)
    return keep_ends(val, 2, 0, 6)                 # 密钥/密码/token 只留 2 位便于对照


def fake_value(val, cat, h):
    n = int(h, 16)
    tag = CATEGORIES[cat][0]
    if cat == "phone":
        return "199" + f"{n % 100000000:08d}"
    if cat == "idcard":
        return "110000" + "19900101" + f"{n % 1000:03d}" + "X"
    if cat == "bankcard":
        return "6222" + f"{n % 10 ** 12:012d}"
    if cat == "email":
        return f"user{h}@example.com"
    if cat == "ip":
        return f"203.0.113.{n % 254 + 1}"
    if cat == "cnname":
        return FAKE_SURNAME[n % len(FAKE_SURNAME)] + "某"
    if cat == "cnaddr":
        return f"某省某市某区示例路{n % 900 + 100}号"
    return f"<{tag}_FAKE_{h}>"


class Ctx:
    def __init__(self, a):
        self.mode, self.keep_format, self.keep_subnet, self.salt = a.mode, a.keep_format, a.keep_subnet, a.salt
        self.hits = {c: 0 for c in CATEGORIES}
        self.mapping = {}                          # (cat, hash8) -> {"to":…, "count":n}

    def sub(self, val, cat):
        h = h8(val, self.salt)
        shape = shaped_ip if cat == "ip" else shaped
        if self.mode == "mask":
            new = mask_value(val, cat, self.keep_subnet)
        elif self.mode == "hash":
            new = shape(val, h) if self.keep_format else f"<{CATEGORIES[cat][0]}:{h}>"
        else:
            new = fake_value(val, cat, h)
            if self.keep_format and cat != "privatekey":
                new = shape(val, h)
        self.hits[cat] += 1
        e = self.mapping.setdefault((cat, h), {"to": new, "count": 0})
        e["count"] += 1
        return new


def build_rules(a):
    R = [("privatekey", RE_PRIVKEY, 0, None), ("jwt", RE_JWT, 0, None), ("apikey", RE_APIKEY, 0, None),
         ("dbpass", RE_DBURL, 3, None), ("dbpass", RE_PWDKV, 1, None), ("urltoken", RE_URLTOKEN, 2, None),
         ("idcard", RE_IDCARD, 0, None),
         ("bankcard", RE_CARD, 0, (lambda s: True) if a.loose_card else (lambda s: luhn(re.sub(r"[ -]", "", s)))),
         ("phone", RE_PHONE, 0, None), ("email", RE_EMAIL, 0, None), ("ip", RE_IP, 1, valid_ip),
         ("cnname", RE_CNNAME, 2, None), ("cnaddr", RE_CNADDR, 2, None)]
    keep = set(a.types.split(",")) if a.types else set(CATEGORIES)
    skip = set(a.skip.split(",")) if a.skip else set()
    bad = (keep | skip) - set(CATEGORIES)
    if bad:
        sys.exit(f"未知类别 {sorted(bad)}；可选 {list(CATEGORIES)}")
    return [r for r in R if r[0] in keep and r[0] not in skip]


def mask_text(text, rules, ctx):
    for cat, pat, grp, ok in rules:
        def rep(m, cat=cat, grp=grp, ok=ok):
            val = m.group(grp)
            if val is None or (ok and not ok(val)):
                return m.group(0)
            whole, s = m.group(0), m.start(0)
            gs, ge = m.start(grp) - s, m.end(grp) - s
            return whole[:gs] + ctx.sub(val, cat) + whole[ge:]
        text = pat.sub(rep, text)
    return text


def chunks(fh, n=2000):
    """按行成块读取；私钥块跨行，遇到 BEGIN 就攒到 END 再切，避免把多行匹配切断。"""
    buf, hold = [], False
    begin, end, key = _D5 + "BEGIN", _D5 + "END", "PRIVATE KEY"
    for line in fh:
        buf.append(line)
        if begin in line and key in line:
            hold = True
        elif end in line and key in line:
            hold = False
        if len(buf) >= n and not hold:
            yield "".join(buf)
            buf = []
    if buf:
        yield "".join(buf)


def process(src, dst, rules, ctx, dry):
    out = None if dry else (sys.stdout if dst == "-" else open(dst, "w", encoding="utf-8", newline=""))
    fh = sys.stdin if src == "-" else open(src, encoding="utf-8", errors="replace", newline="")
    try:
        for ch in chunks(fh):
            masked = mask_text(ch, rules, ctx)
            if out:
                out.write(masked)
    finally:
        if fh is not sys.stdin:
            fh.close()
        if out and out is not sys.stdout:
            out.close()


def collect(paths, a):
    files = []
    for p in paths:
        if p == "-":
            files.append("-")
        elif os.path.isdir(p):
            exts = {e if e.startswith(".") else "." + e for e in a.ext.split(",")} if a.ext else TEXT_EXT
            for root, dirs, fns in os.walk(p):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
                for fn in sorted(fns):
                    if fn.endswith(a.suffix) or os.path.splitext(fn)[1].lower() not in exts:
                        continue
                    files.append(os.path.join(root, fn))
        else:
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser(description="日志与数据脱敏（对外分享前处理）")
    ap.add_argument("paths", nargs="+", help="文件 / 目录 / - 表示标准输入")
    ap.add_argument("--mode", choices=["mask", "hash", "fake"], default="mask",
                    help="mask 保留前后若干位；hash 用 sha256 前 8 位（同一 salt 下可关联）；fake 用稳定的假值")
    ap.add_argument("--keep-format", action="store_true", help="保持原值长度与字符形态（数字→数字、字母→字母）")
    ap.add_argument("--keep-subnet", type=int, default=0, choices=[0, 1, 2, 3], help="IP 保留前 N 段网段，默认 0 全遮")
    ap.add_argument("--salt", default="", help="哈希盐值；同一 salt 跨文件/跨次运行结果一致，留空则易被穷举反推")
    ap.add_argument("--types", help="只处理这些类别，逗号分隔")
    ap.add_argument("--skip", help="跳过这些类别，逗号分隔")
    ap.add_argument("--loose-card", action="store_true", help="银行卡不校验 Luhn，任何 16–19 位数字串都当卡号")
    ap.add_argument("--in-place", action="store_true", help="原地覆盖（破坏性操作，必须同时加 --yes）")
    ap.add_argument("--yes", action="store_true", help="确认执行 --in-place")
    ap.add_argument("--suffix", default=".masked", help="默认输出文件后缀")
    ap.add_argument("--out-dir", help="输出到该目录（保持原文件名）")
    ap.add_argument("--ext", help="目录模式下处理的扩展名，逗号分隔，默认常见文本类型")
    ap.add_argument("--force", action="store_true", help="允许覆盖已存在的输出文件")
    ap.add_argument("--report", help="写出映射清单（原值哈希 → 替换值，不含原值明文）")
    ap.add_argument("--dry-run", action="store_true", help="只统计命中，不写任何文件")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.in_place and not a.yes:
        sys.exit("--in-place 会覆盖原文件且不可撤销；确认后请加 --yes（建议先不带 --in-place 跑一遍看统计）")
    rules, ctx = build_rules(a), Ctx(a)
    files = collect(a.paths, a)
    if not files:
        sys.exit("没有匹配到任何文件")
    done = []
    for src in files:
        if src == "-":
            process("-", "-", rules, ctx, a.dry_run)
            done.append({"src": "<stdin>", "dst": "<stdout>"})
            continue
        if a.dry_run:
            dst = "-"
        elif a.in_place:
            dst = src + ".tmp-mask"
        elif a.out_dir:
            os.makedirs(a.out_dir, exist_ok=True)
            dst = os.path.join(a.out_dir, os.path.basename(src))
        else:
            dst = src + a.suffix
        if dst not in ("-",) and os.path.exists(dst) and not a.force and not a.in_place:
            print(f"跳过 {src}：{dst} 已存在（加 --force 覆盖）", file=sys.stderr)
            continue
        process(src, None if a.dry_run else dst, rules, ctx, a.dry_run)
        if a.in_place and not a.dry_run:
            os.replace(dst, src)
            dst = src
        done.append({"src": src, "dst": "(dry-run)" if a.dry_run else dst})
    total = sum(ctx.hits.values())
    rep = [{"category": c, "hash": h, "replacement": v["to"], "count": v["count"]}
           for (c, h), v in sorted(ctx.mapping.items())]
    if a.report and not a.dry_run:
        if a.report.endswith(".json"):
            json.dump(rep, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        else:
            with open(a.report, "w", encoding="utf-8") as f:
                f.write("# 原值哈希 → 替换值（不含原值明文）\tmode=%s\tsalt=%s\n" % (a.mode, "set" if a.salt else "empty"))
                f.write("category\torig_sha256_8\treplacement\tcount\n")
                for r in rep:
                    f.write(f"{r['category']}\t{r['hash']}\t{r['replacement']}\t{r['count']}\n")
    summary = {"mode": a.mode, "keep_format": a.keep_format, "files": done, "total_hits": total,
               "distinct_values": len(ctx.mapping),
               "by_category": [{"category": c, "label": CATEGORIES[c][1], "hits": ctx.hits[c],
                                "distinct": sum(1 for k in ctx.mapping if k[0] == c)}
                               for c in ORDER if ctx.hits[c]],
               "report": a.report if (a.report and not a.dry_run) else None}
    stream = sys.stderr if "-" in files else sys.stdout      # 脱敏结果走 stdout，统计走 stderr，方便管道
    if a.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2), file=stream)
    else:
        print(f"模式 {a.mode}{'（保持格式）' if a.keep_format else ''} · 处理 {len(done)} 个输入 · "
              f"命中 {total} 处 / {len(ctx.mapping)} 个不同取值", file=stream)
        if total:
            print(f"\n{'类别':<14}{'命中':>6}{'不同取值':>10}", file=stream)
            for r in summary["by_category"]:
                print(f"{r['label']:<14}{r['hits']:>6}{r['distinct']:>10}", file=stream)
        else:
            print("  ✓ 没有命中任何敏感形态（也可能是模式没覆盖，别只依赖工具结论）", file=stream)
        for d in done:
            print(f"  {d['src']} → {d['dst']}", file=stream)
        if a.report and not a.dry_run:
            print(f"映射清单 {a.report}", file=stream)
        print("提醒：脱敏不等于合规，敏感数据外发仍需走审批；发出前请人工抽样复核。", file=stream)


if __name__ == "__main__":
    main()
