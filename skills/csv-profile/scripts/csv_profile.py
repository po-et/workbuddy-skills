#!/usr/bin/env python3
"""CSV/TSV 数据画像：嗅探分隔符与编码，逐列给出类型、空值、唯一值、Top 取值、数值分位数与时间范围，并汇总数据质量问题。纯标准库。

用法：
  python3 csv_profile.py data.csv [--rows 200000] [--top 5] [--json]
  python3 csv_profile.py data.tsv --delimiter tab --encoding gbk --no-header
  cat data.csv | python3 csv_profile.py -
"""
import argparse
import collections
import csv
import json
import math
import os
import re
import sys
from datetime import datetime

ENCODINGS = ["utf-8-sig", "utf-8", "gbk", "gb18030"]
NULL_TOKENS = {"", "na", "n/a", "null", "none", "nil", "nan", "-", "--", "\\n", "\\N", "无", "未知", "unknown"}

RE_INT = re.compile(r"^[+-]?\d{1,19}$")
RE_FLOAT = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+(?:\.\d+)?[eE][+-]?\d+)$")
RE_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
RE_URL = re.compile(r"^(?:https?|ftp)://\S+$", re.I)
RE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
RE_HEXID = re.compile(r"^[0-9a-f]{16,64}$", re.I)
RE_CODEID = re.compile(r"^(?=.*\d)[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
RE_YYYYMMDD = re.compile(r"^(?:19|20)\d{6}$")
BOOL_T = {"true", "yes", "y", "t", "是", "真", "on"}
BOOL_F = {"false", "no", "n", "f", "否", "假", "off"}

# 逐值日期时间格式（不含纯 8 位数字，那个在列级别再判，避免把订单号当日期）
DT_FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
           "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y年%m月%d日",
           "%d/%b/%Y:%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%H:%M:%S", "%H:%M"]

PII_FORMS = [
    ("手机号", re.compile(r"^1[3-9]\d{9}$")),
    ("身份证号", re.compile(r"^\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]$")),
    ("银行卡号", re.compile(r"^\d{16,19}$")),
    ("邮箱", RE_EMAIL),
]
PII_NAME_HINT = re.compile(r"(手机|电话|phone|mobile|tel|身份证|idcard|id_card|证件|邮箱|email|mail|银行卡|bank|card|"
                           r"地址|address|addr|姓名|name|真实姓名|收货人|联系人)", re.I)
ID_NAME_HINT = re.compile(r"(^id$|_id$|id$|编号|序号|单号|流水号|uuid|guid|code$|no$|sn$)", re.I)


def norm(v):
    return v.strip() if isinstance(v, str) else ""


def to_dt(s):
    """尽力把字符串解析成 datetime；解析不出返回 None。"""
    t = re.sub(r"[.,]\d+", "", s)
    t = re.sub(r"\s*(?:Z|[+-]\d{2}:?\d{2})$", "", t).strip()
    for f in DT_FMTS:
        try:
            return datetime.strptime(t, f)
        except ValueError:
            continue
    return None


def kind_of(s):
    """单值类型：邮箱 / URL / ID / 布尔 / 整数 / 小数 / 日期时间 / 文本。"""
    if RE_EMAIL.match(s):
        return "邮箱"
    if RE_URL.match(s):
        return "URL"
    if RE_UUID.match(s) or RE_HEXID.match(s):
        return "ID"
    low = s.lower()
    if low in BOOL_T or low in BOOL_F:
        return "布尔"
    if RE_INT.match(s):
        return "整数"
    if RE_FLOAT.match(s):
        return "小数"
    if to_dt(s):
        return "日期时间"
    return "文本"


def sniff_encoding(path):
    raw = open(path, "rb").read(262144)
    for enc in ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def sniff_delimiter(sample):
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        pass
    lines = [l for l in sample.splitlines()[:30] if l.strip()]
    best, best_score = ",", -1.0
    for d in [",", "\t", ";", "|"]:
        counts = [l.count(d) for l in lines]
        if not counts or max(counts) == 0:
            continue
        mode = collections.Counter(counts).most_common(1)[0]
        score = mode[0] * (mode[1] / len(counts))          # 每行字段多且各行一致者胜
        if score > best_score:
            best, best_score = d, score
    return best


def looks_like_header(row):
    """首行全部非空、互不相同、且没有一个能解析成数字或日期时，视为表头。"""
    if not row or any(not norm(c) for c in row):
        return False
    if len(set(norm(c) for c in row)) != len(row):
        return False
    return not any(kind_of(norm(c)) in ("整数", "小数", "日期时间") for c in row)


def quantile(vals, q):
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return vals[int(k)]
    return vals[lo] * (hi - k) + vals[hi] * (k - lo)


def fnum(x):
    if x is None:
        return "-"
    if abs(x - round(x)) < 1e-9 and abs(x) < 1e18:
        return f"{int(round(x))}"
    return f"{x:.2f}" if abs(x) >= 1000 else f"{x:.4g}"


def width(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def pad(s, n):
    s = str(s)
    return s + " " * max(0, n - width(s))


class Col:
    def __init__(self, name, idx, max_uniq):
        self.name, self.idx, self.max_uniq = name, idx, max_uniq
        self.n = self.nulls = self.spaced = 0
        self.kinds = collections.Counter()
        self.vals = collections.Counter()
        self.uniq_overflow = False
        self.nums, self.lens = [], []
        self.dt_min = self.dt_max = None

    def add(self, raw):
        self.n += 1
        if raw is None:
            self.nulls += 1
            return
        s = norm(raw)
        if s and raw != s:
            self.spaced += 1
        if s.lower() in NULL_TOKENS:
            self.nulls += 1
            return
        k = kind_of(s)
        self.kinds[k] += 1
        if len(self.vals) < self.max_uniq or s in self.vals:
            self.vals[s] += 1
        else:
            self.uniq_overflow = True
        self.lens.append(len(s))
        if k in ("整数", "小数"):
            try:
                self.nums.append(float(s))
            except ValueError:
                pass
        if k == "日期时间":
            d = to_dt(s)
            if d:
                self.dt_min = d if self.dt_min is None or d < self.dt_min else self.dt_min
                self.dt_max = d if self.dt_max is None or d > self.dt_max else self.dt_max

    @property
    def filled(self):
        return self.n - self.nulls

    def profile(self, top):
        f = self.filled
        uniq = len(self.vals)
        main = self.kinds.most_common(1)[0] if self.kinds else ("空", 0)
        typ, ratio = main[0], (main[1] / f if f else 0)
        mixed = f > 0 and ratio < 0.95 and len(self.kinds) > 1
        # 列级细化
        if f == 0:
            typ = "全空"
        elif mixed:
            typ = "混合类型"
        elif typ == "整数":
            digits = set(self.vals)
            if digits <= {"0", "1"}:
                typ = "布尔(0/1)"
            elif all(RE_YYYYMMDD.match(v) and to_dt(f"{v[:4]}-{v[4:6]}-{v[6:]}") for v in self.vals) and not self.uniq_overflow:
                typ = "日期时间(YYYYMMDD)"
                for v in self.vals:
                    d = to_dt(f"{v[:4]}-{v[4:6]}-{v[6:]}")
                    self.dt_min = d if self.dt_min is None or d < self.dt_min else self.dt_min
                    self.dt_max = d if self.dt_max is None or d > self.dt_max else self.dt_max
            elif ID_NAME_HINT.search(self.name) and uniq == f and f > 1:
                typ = "ID"
        elif typ == "文本":
            if uniq <= max(10, int(f * 0.02)) and uniq * 2 <= f and uniq > 1:
                typ = "枚举"
            elif (ID_NAME_HINT.search(self.name) or all(RE_CODEID.match(v) for v in self.vals)) and uniq == f and f > 1:
                typ = "ID"
        if f and uniq == 1:
            typ = f"常量({typ})"
        p = {"column": self.name, "index": self.idx, "type": typ, "rows": self.n,
             "nulls": self.nulls, "null_pct": round(self.nulls / self.n * 100, 2) if self.n else 0.0,
             "unique": uniq, "unique_capped": self.uniq_overflow,
             "kinds": dict(self.kinds.most_common()),
             "top": [{"value": v, "count": c, "pct": round(c / f * 100, 2)} for v, c in self.vals.most_common(top)] if f else [],
             "values_with_space": self.spaced}
        if self.nums:
            s = sorted(self.nums)
            mean = sum(s) / len(s)
            var = sum((x - mean) ** 2 for x in s) / (len(s) - 1) if len(s) > 1 else 0.0
            p["numeric"] = {"count": len(s), "min": s[0], "p25": quantile(s, .25), "median": quantile(s, .5),
                            "p75": quantile(s, .75), "max": s[-1], "mean": mean, "std": math.sqrt(var),
                            "zeros": sum(1 for x in s if x == 0), "negatives": sum(1 for x in s if x < 0)}
        if self.lens and typ not in ("整数", "小数"):
            ls = sorted(self.lens)
            p["length"] = {"min": ls[0], "p50": quantile(ls, .5), "p95": quantile(ls, .95), "max": ls[-1],
                           "mean": round(sum(ls) / len(ls), 2)}
        if self.dt_min:
            p["time_range"] = {"min": self.dt_min.isoformat(sep=" "), "max": self.dt_max.isoformat(sep=" "),
                               "span_days": round((self.dt_max - self.dt_min).total_seconds() / 86400, 2)}
        # 疑似个人信息
        hits = []
        if f:
            for label, pat in PII_FORMS:
                m = sum(c for v, c in self.vals.items() if pat.match(v))
                if m and m / f >= 0.3:
                    hits.append({"form": label, "pct": round(m / f * 100, 1)})
        if hits or PII_NAME_HINT.search(self.name):
            p["pii"] = {"forms": hits, "name_hint": bool(PII_NAME_HINT.search(self.name))}
        return p


def profile_file(fh, a, source):
    sample = fh.read(65536)
    if fh.seekable():
        fh.seek(0)
    else:                                                  # stdin：样本已读走，拼回去
        import io
        fh = io.StringIO(sample + fh.read())
    delim = a.delimiter or sniff_delimiter(sample)
    reader = csv.reader(fh, delimiter=delim)
    head = []
    for row in reader:
        head.append((reader.line_num, row))
        if len(head) >= 2:
            break
    if not head:
        return {"file": source, "error": "文件为空"}
    first = head[0][1]
    has_header = (not a.no_header) and looks_like_header(first)
    header = [norm(c) or f"col{i + 1}" for i, c in enumerate(first)] if has_header else [f"col{i + 1}" for i in range(len(first))]
    dup_names = [n for n, c in collections.Counter(header).items() if c > 1]
    cols = [Col(h, i + 1, a.max_uniq) for i, h in enumerate(header)]
    ragged, seen, dup_rows, nrows, blank = [], collections.Counter(), 0, 0, 0
    pending = head[1:] if has_header else head

    def feed(row, lineno):
        nonlocal nrows, dup_rows, blank
        if not row or all(not norm(c) for c in row):
            blank += 1
            return
        nrows += 1
        if len(row) != len(header):
            if len(ragged) < 50:
                ragged.append({"line": lineno, "fields": len(row)})
        key = "\x00".join(norm(c) for c in row)
        seen[key] += 1
        if seen[key] == 2:
            dup_rows += 1
        for i, c in enumerate(cols):
            c.add(row[i] if i < len(row) else None)

    for lineno, row in pending:
        feed(row, lineno)
    for row in reader:
        feed(row, reader.line_num)
        if a.rows and nrows >= a.rows:
            break
    dup_total = sum(c - 1 for c in seen.values() if c > 1)
    profiles = [c.profile(a.top) for c in cols]
    issues = []

    def add(sev, code, msg, fix):
        issues.append({"severity": sev, "rule": code, "message": msg, "fix": fix})

    for p in profiles:
        nm = f"[{p['index']}]{p['column']}"
        if p["type"] == "全空":
            add("high", "C001", f"{nm} 整列为空", "确认上游是否漏写该字段，否则删除该列")
        elif p["type"].startswith("常量"):
            v = p["top"][0]["value"] if p["top"] else ""
            add("info", "C002", f"{nm} 是常量列，恒为 {v!r}", "常量列无信息量，入仓时可省略或改为表级元数据")
        if p["type"] == "混合类型":
            add("warn", "C003", f"{nm} 混合类型 {p['kinds']}", "统一上游格式或落库前显式转换，否则 SQL 比较与排序会出错")
        if p["nulls"] and p["null_pct"] >= 30 and p["type"] != "全空":
            add("warn", "C005", f"{nm} 空值 {p['nulls']} 行（{p['null_pct']}%）", "确认是业务允许为空还是采集丢失；下游聚合注意空值语义")
        if p["values_with_space"]:
            add("warn", "C006", f"{nm} 有 {p['values_with_space']} 个取值带前后空格", "入仓前 trim，否则 join 与 group by 会把「a」和「a 」当两个值")
        if "pii" in p:
            forms = "、".join(f"{h['form']}{h['pct']}%" for h in p["pii"]["forms"]) or "列名疑似"
            add("high" if p["pii"]["forms"] else "warn", "C007", f"{nm} 疑似个人信息（{forms}）",
                "对外共享前脱敏（可用「日志数据脱敏」技能），并确认存储与传输是否满足合规要求")
    pk = [p for p in profiles if p["nulls"] == 0 and p["rows"] > 1 and not p["unique_capped"]
          and p["unique"] == p["rows"] and p["type"] not in ("全空", "小数") and not p["type"].startswith("日期时间")]
    pk.sort(key=lambda p: (0 if (ID_NAME_HINT.search(p["column"]) or p["type"] == "ID") else 1, p["index"]))
    if pk:
        add("info", "C004", "唯一且无空值的列（主键/去重键候选）：" + "、".join(f"[{p['index']}]{p['column']}" for p in pk[:5]),
            "选一个做主键并加唯一索引；其余若本该重复，说明样本量不够或上游已去重")
    if dup_names:
        add("warn", "C008", f"表头有重复列名 {dup_names}", "重命名重复列，否则多数工具只会保留最后一列")
    if ragged:
        show = "、".join(f"第{r['line']}行({r['fields']}列)" for r in ragged[:5])
        add("high", "C009", f"{len(ragged)} 行字段数与表头（{len(header)} 列）不一致：{show}",
            "多为未转义的分隔符或换行；修正上游导出或用 --delimiter 指定正确分隔符")
    if dup_total:
        add("warn", "C010", f"完全重复的数据行 {dup_total} 行（涉及 {dup_rows} 组）", "确认是业务允许的重复还是导出重跑；去重后再入仓")
    if not has_header:
        add("info", "C011", "未识别到表头，列名用 col1..colN 占位", "确认首行是否为数据；若确有表头请去掉 --no-header")
    order = {"high": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda x: (order[x["severity"]], x["rule"]))
    return {"file": source, "encoding": "-", "delimiter": delim, "has_header": has_header,
            "columns": len(header), "data_rows": nrows, "blank_rows": blank,
            "duplicate_rows": dup_total, "sampled": bool(a.rows and nrows >= a.rows),
            "profiles": profiles, "issues": issues}


def render(r):
    if "error" in r:
        print(f"{r['file']}: {r['error']}")
        return
    d = {"\t": "TAB", ",": "','", ";": "';'", "|": "'|'"}.get(r["delimiter"], repr(r["delimiter"]))
    print(f"== {r['file']}")
    print(f"编码 {r['encoding']} · 分隔符 {d} · 表头 {'有' if r['has_header'] else '无'} · {r['columns']} 列 · "
          f"{r['data_rows']} 数据行{'（采样）' if r['sampled'] else ''} · 重复行 {r['duplicate_rows']}")
    print("\n## 列画像")
    w = max([width(p["column"]) for p in r["profiles"]] + [6])
    for p in r["profiles"]:
        cap = "+" if p["unique_capped"] else ""
        print(f" {p['index']:>3} {pad(p['column'], w)}  {pad(p['type'], 18)} 空 {p['nulls']}({p['null_pct']}%)  唯一 {p['unique']}{cap}")
        if p["top"]:
            tops = " | ".join(f"{t['value'][:24]} {t['count']}({t['pct']}%)" for t in p["top"])
            print(f"     Top{len(p['top'])}  {tops}")
        n = p.get("numeric")
        if n:
            print(f"     数值   min {fnum(n['min'])} / p25 {fnum(n['p25'])} / 中位 {fnum(n['median'])} / p75 {fnum(n['p75'])}"
                  f" / max {fnum(n['max'])} / 均值 {fnum(n['mean'])} / 标准差 {fnum(n['std'])}"
                  + (f" / 零值 {n['zeros']}" if n["zeros"] else "") + (f" / 负值 {n['negatives']}" if n["negatives"] else ""))
        L = p.get("length")
        if L:
            print(f"     长度   {L['min']}–{L['max']}（中位 {fnum(L['p50'])}，p95 {fnum(L['p95'])}，均值 {L['mean']}）")
        t = p.get("time_range")
        if t:
            print(f"     时间   {t['min']} → {t['max']}（跨 {t['span_days']} 天）")
        if p["type"] == "混合类型":
            print(f"     构成   {p['kinds']}")
    print("\n## 数据质量")
    if not r["issues"]:
        print("  ✓ 没有发现问题")
    for x in r["issues"]:
        print(f"  [{x['severity'].upper():4}] {x['rule']}: {x['message']}\n         → {x['fix']}")
    c = collections.Counter(x["severity"] for x in r["issues"])
    print(f"\n小计：high {c['high']} / warn {c['warn']} / info {c['info']}")


def main():
    ap = argparse.ArgumentParser(description="CSV/TSV 数据画像")
    ap.add_argument("files", nargs="+", help="CSV/TSV 文件，- 表示标准输入")
    ap.add_argument("--rows", type=int, default=0, help="只采样前 N 行数据（大文件用），0 为全量")
    ap.add_argument("--top", type=int, default=5, help="每列列出最常见的 N 个取值")
    ap.add_argument("--delimiter", help="强制分隔符，可写 tab / , / ; / |")
    ap.add_argument("--encoding", help="强制编码，默认按 utf-8-sig / utf-8 / gbk 顺序嗅探")
    ap.add_argument("--no-header", action="store_true", help="首行就是数据，不当表头")
    ap.add_argument("--max-uniq", type=int, default=50000, help="每列最多跟踪的唯一值数（超出后唯一数标 +）")
    ap.add_argument("--strict", action="store_true", help="存在 high 问题时退出码 1")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.delimiter:
        a.delimiter = {"tab": "\t", "\\t": "\t"}.get(a.delimiter.lower(), a.delimiter)
    csv.field_size_limit(10 ** 7)
    missing = [f for f in a.files if f != "-" and not os.path.isfile(f)]
    if missing:
        sys.exit(f"文件不存在：{missing}")
    forced, out = a.encoding, []
    for f in a.files:
        if f == "-":
            r = profile_file(sys.stdin, a, "<stdin>")
            r["encoding"] = "stdin"
        else:
            enc = forced or sniff_encoding(f)
            with open(f, encoding=enc, errors="replace", newline="") as fh:
                r = profile_file(fh, a, f)
            r["encoding"] = enc
        out.append(r)
    if a.json:
        print(json.dumps(out if len(out) > 1 else out[0], ensure_ascii=False, indent=2, default=str))
    else:
        for i, r in enumerate(out):
            if i:
                print()
            render(r)
    bad = any(x["severity"] == "high" for r in out for x in r.get("issues", []))
    sys.exit(1 if (a.strict and bad) else 0)


if __name__ == "__main__":
    main()
