#!/usr/bin/env python3
"""明细 CSV 体检：上透视表之前，先看出同物异名、空值、重复行、文本数字和混用的日期写法。

用法：
  python3 scripts/csv_profile.py 明细.csv
  python3 scripts/csv_profile.py 明细.csv --key 订单号          # 按关键列查重复
  python3 scripts/csv_profile.py 明细.csv --encoding gbk        # 自动识别失败时手动指定编码

只读不写：不改原文件，也不生成新文件。
退出码：0 体检完成（问题都写在报告里）；1 参数或内容有误（空文件、--key 列不存在）；
        2 文件读不了（不存在、是 Excel 文件、编码认不出来）；130 手动中断（Ctrl+C）。
只用 Python 标准库。
"""

import argparse
import collections
import csv
import io
import re
import sys
import unicodedata
from pathlib import Path

NUM_TEXT = re.compile(r"^\s*-?[\d,，]+(\.\d+)?\s*%?\s*$")
PLAIN_NUM = re.compile(r"^-?\d+(\.\d+)?$")
DATE_FORMS = [
    (re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"), "2026-09-01"),
    (re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$"), "2026/9/1"),
    (re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}$"), "2026.9.1"),
    (re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$"), "2026年9月1日"),
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"), "9/1/2026"),
    (re.compile(r"^\d{4}-\d{1,2}-\d{1,2}[ T]\d{1,2}:\d{2}(:\d{2})?$"), "2026-09-01 08:00"),
    (re.compile(r"^\d{5}$"), "46266 这类 Excel 日期序列号"),
]
SUFFIXES = ("区", "市", "省", "部", "店", "公司", "中心")


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FriendlyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/csv_profile.py 明细.csv --key 订单号）" % message, file=sys.stderr)
        sys.exit(1)


def read_text(path, encoding):
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls", ".numbers"):
        raise InputError(2, "%s 是表格文件，不是 CSV：在 Excel 或 WPS 里「另存为 CSV UTF-8」后再体检" % p.name)
    if not p.exists():
        raise InputError(2, "找不到文件 %s：检查路径和文件名" % path)
    if p.is_dir():
        raise InputError(2, "%s 是文件夹，请给出 CSV 文件路径" % path)
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise InputError(2, "读不了 %s（%s）：文件可能正被 Excel 打开，关掉后重试" % (path, exc.strerror or exc))
    if data[:2] == b"PK":
        raise InputError(2, "%s 其实是 Excel 文件（只是扩展名是 .csv）：用 Excel 另存为 CSV UTF-8" % p.name)
    if encoding:
        try:
            "".encode(encoding)
        except LookupError:
            raise InputError(1, "不认识的编码名「%s」：常见的是 utf-8、gbk" % encoding)
    encodings = [encoding] if encoding else ["utf-8-sig", "gb18030"]
    for enc in encodings:
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise InputError(2, "编码认不出来：用 --encoding 指定（常见 utf-8、gbk），或在 Excel 里另存为 CSV UTF-8")


def normalize(v):
    """去掉空白、全角半角差异和大小写后的样子，用来找「看着一样其实不一样」的值。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", v)).casefold()


def profile(text, key, max_values):
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    numbered, blank_lines = [], []
    for r in reader:
        (numbered if any(c.strip() for c in r) else blank_lines).append((reader.line_num, r))
    if not numbered:
        raise InputError(1, "文件是空的：确认导出时带上了表头和数据")
    header = [h.strip() for h in numbered[0][1]]
    body_lines = numbered[1:]
    body = [r for _, r in body_lines]
    if not body:
        raise InputError(1, "只有表头没有数据行：确认导出的筛选条件")

    key_cols = [c.strip() for c in key.split(",")] if key else []
    missing = [c for c in key_cols if c not in header]
    if missing:
        raise InputError(1, "--key 里的列 %s 不在表头里；表头是：%s" % ("、".join(missing), "、".join(header)))

    print("分隔符：%s　数据行数：%d　列数：%d" % ({",": "逗号", "\t": "制表符", ";": "分号"}[delim], len(body), len(header)))
    issues = []
    if blank_lines:
        issues.append("有 %d 个空行（第 %s 行等）：透视前删掉" % (len(blank_lines), "、".join(str(n) for n, _ in blank_lines[:5])))
    blanks = [i + 1 for i, h in enumerate(header) if not h]
    if blanks:
        issues.append("第 %s 列没有表头：透视表会拒绝，补上列名" % "、".join(map(str, blanks)))
    dup_heads = [h for h, n in collections.Counter(header).items() if h and n > 1]
    if dup_heads:
        issues.append("表头重复：%s——改成不同的名字" % "、".join(dup_heads))
    ragged = [n for n, r in body_lines if len(r) != len(header)]
    if ragged:
        issues.append("有 %d 行的列数和表头对不上（第 %s 行等）：多半是单元格里有分隔符或换行"
                      % (len(ragged), "、".join(map(str, ragged[:5]))))

    print("逐列：")
    for idx, name in enumerate(header):
        vals = [(r[idx] if idx < len(r) else "") for r in body]
        empty = sum(1 for v in vals if not v.strip())
        uniq = sorted(set(vals))
        shown = "、".join(repr(v) for v in uniq[:max_values]) + ("……" if len(uniq) > max_values else "")
        print("  %s：空值 %d，不同值 %d，前几个：%s" % (name or "(无表头)", empty, len(uniq), shown))
        if empty:
            issues.append("「%s」有 %d 个空值：确认是缺失数据还是允许留空；缺失不等于 0，取不到写待取数"
                          % (name or "(无表头)", empty))
        filled = [v for v in vals if v.strip()]
        texty = [v for v in filled if NUM_TEXT.match(v) and not PLAIN_NUM.match(v.strip())]
        if texty and len(texty) + sum(1 for v in filled if PLAIN_NUM.match(v.strip())) >= 0.8 * len(filled):
            issues.append("「%s」有 %d 个数字带千分位、百分号或空格（如 %r）：透视表会当成文本，先转成纯数字"
                          % (name, len(texty), texty[0]))
        forms = collections.OrderedDict()
        for v in filled:
            for pattern, label in DATE_FORMS:
                if pattern.match(v.strip()):
                    forms.setdefault(label, v)
                    break
        if len(forms) > 1 and sum(1 for v in filled if any(p.match(v.strip()) for p, _ in DATE_FORMS)) >= 0.8 * len(filled):
            issues.append("「%s」混用了 %d 种日期写法（%s）：统一成真日期再透视" % (name, len(forms), "、".join(forms)))
        groups = collections.defaultdict(set)
        for v in set(filled):
            groups[normalize(v)].add(v)
        same = [sorted(g) for g in groups.values() if len(g) > 1]
        for g in same[:5]:
            issues.append("「%s」里 %s 去掉空格和全半角差异后是同一个值：统一写法" % (name, " / ".join(repr(x) for x in g)))
        base = {}
        for v in sorted(set(filled), key=lambda x: (x != x.strip(), x)):   # 优先用没有多余空格的写法
            base.setdefault(normalize(v), v)
        for nv, v in sorted(base.items()):
            for suf in SUFFIXES:
                if nv.endswith(suf) and nv[:-len(suf)] in base:
                    issues.append("「%s」里 %r 和 %r 疑似同物异名（只差结尾的「%s」）：人工确认后统一"
                                  % (name, base[nv[:-len(suf)]], v, suf))

    dup = collections.Counter(tuple(r) for r in body)
    dups = sum(n - 1 for n in dup.values() if n > 1)
    print("完全重复的行：%d" % dups)
    if dups:
        issues.append("有 %d 行和别的行完全一样：确认是真实的重复记录还是导出重复" % dups)
    if key_cols:
        cols = key_cols
        pos = [header.index(c) for c in cols]
        keys = collections.Counter(tuple(r[i] if i < len(r) else "" for i in pos) for r in body)
        kd = [(k, n) for k, n in keys.items() if n > 1]
        print("按 %s 重复的键：%d 个" % ("+".join(cols), len(kd)))
        if kd:
            issues.append("按 %s 有 %d 个键出现不止一次（如 %s 出现 %d 次）：一对多还是重复导出？"
                          % ("+".join(cols), len(kd), "/".join(kd[0][0]), kd[0][1]))

    print("需要处理：" if issues else "需要处理：没有发现常见问题")
    for i, msg in enumerate(issues, 1):
        print("  %d. %s" % (i, msg))
    return 0


def main(argv=None):
    p = FriendlyParser(description="明细 CSV 体检：同物异名、空值、重复行、文本数字、日期写法。",
                       epilog="退出码：0 完成；1 参数或内容有误；2 文件读不了；130 手动中断。")
    p.add_argument("file", help="导出的明细 CSV")
    p.add_argument("--key", help="按哪几列判断重复，多列用逗号分隔，如 订单号 或 日期,门店")
    p.add_argument("--encoding", help="手动指定编码，如 utf-8、gbk")
    p.add_argument("--max-values", type=int, default=15, help="每列最多列出几个不同值，默认 15")
    args = p.parse_args(argv)
    try:
        if not 1 <= args.max_values <= 200:
            raise InputError(1, "--max-values 请给 1–200 之间的数")
        text, enc = read_text(args.file, args.encoding)
        print("文件：%s（编码 %s）" % (Path(args.file).name, enc))
        return profile(text, args.key, args.max_values)
    except InputError as exc:
        sys.stdout.flush()
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有改动任何文件", file=sys.stderr)
        sys.exit(130)
