#!/usr/bin/env python3
"""表格合并：把一个文件夹里表头相同的 CSV 合成一张，末列标来源文件。只读原文件，不改动。

用法：
  python3 merge_csv.py 门店报表                                   # 输出到当前目录的 合并结果.csv
  python3 merge_csv.py 门店报表 --out ~/Desktop/9月合并.csv
  python3 merge_csv.py 门店报表 --pattern "*-9月.csv" --source-col 门店文件

编码：默认依次尝试 UTF-8、GBK（GB18030），每个文件用了哪种会打印出来；输出为 UTF-8 带 BOM，Excel 直接打开不乱码。
会跳过并说明原因：空文件、表头和第一个文件不同、有行比表头多出内容、编码无法识别。
.xlsx/.xls 不读：在表格软件里另存为「CSV UTF-8」后再合并，或改用 Power Query。
退出码：0 成功；1 参数错误；2 文件读写失败；3 没有可合并的数据；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import csv
import os
import sys
import tempfile
import unicodedata
from pathlib import Path

ENCODINGS = {"auto": ("utf-8-sig", "gb18030"), "utf-8": ("utf-8-sig",), "gbk": ("gb18030",)}
ENC_LABEL = {"utf-8-sig": "UTF-8", "gb18030": "GBK"}


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def read_rows(path, encodings):
    last = None
    for enc in encodings:
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.reader(f)), ENC_LABEL[enc]
        except UnicodeDecodeError as e:
            last = e
    raise last


def pad(text, width=28):
    """按显示宽度补空格（中文算两格），让打印的清单对齐。"""
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(1, width - w)


def clean(row):
    """只去掉行尾的空单元格（导出时常见的多余逗号），单元格内容原样保留。"""
    row = list(row)
    while row and not row[-1].strip():
        row.pop()
    return row


def describe_diff(want, got):
    miss = [c for c in want if c not in got]
    extra = [c for c in got if c not in want]
    parts = []
    if miss:
        parts.append("少了 " + "、".join(miss))
    if extra:
        parts.append("多了 " + "、".join(extra))
    return "；".join(parts) or "列的顺序不同"


def atomic_write_csv(path, rows):
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".csv", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(rows)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    ap = ArgParser(description="合并表头相同的 CSV，末列标来源文件")
    ap.add_argument("folder", help="放 CSV 的文件夹")
    ap.add_argument("--pattern", default="*.csv", help="只合并匹配的文件（默认 *.csv）")
    ap.add_argument("--recursive", action="store_true", help="连子文件夹一起找")
    ap.add_argument("--out", default="合并结果.csv", help="输出文件（默认当前目录 合并结果.csv）")
    ap.add_argument("--source-col", default="来源文件", help="来源列的列名（默认 来源文件）")
    ap.add_argument("--encoding", choices=sorted(ENCODINGS), default="auto", help="默认 auto")
    a = ap.parse_args(argv)

    folder = Path(a.folder).expanduser()
    if not folder.is_dir():
        print("找不到文件夹：%s（检查路径；路径里有空格时用引号包起来）" % folder, file=sys.stderr)
        return 2
    out = Path(a.out).expanduser().resolve()
    if not out.parent.is_dir():
        print("输出位置的文件夹不存在：%s" % out.parent, file=sys.stderr)
        return 2
    finder = folder.rglob if a.recursive else folder.glob
    files = sorted(p for p in finder(a.pattern)
                   if p.is_file() and not p.name.startswith((".", "~$")) and p.resolve() != out)
    excel = sorted(p.name for p in finder("*.xls*") if p.is_file() and not p.name.startswith("~$"))
    if excel:
        print("注意：有 %d 个 Excel 文件没有读（%s）。需要的话先另存为「CSV UTF-8」。"
              % (len(excel), "、".join(excel[:5]) + ("…" if len(excel) > 5 else "")))
    if not files:
        print("在 %s 里没找到匹配 %s 的文件。" % (folder, a.pattern))
        return 3

    header, rows, report, skipped = None, [], [], []
    for p in files:
        name = str(p.relative_to(folder))
        try:
            data, enc = read_rows(p, ENCODINGS[a.encoding])
        except UnicodeDecodeError:
            skipped.append((name, "编码无法识别：用表格软件另存为「CSV UTF-8」"))
            continue
        except OSError as e:
            skipped.append((name, "读取失败：%s" % (e.strerror or e)))
            continue
        data = [(i, clean(r)) for i, r in enumerate(data, 1)]
        data = [(i, r) for i, r in data if r]         # 去掉整行空白，保留原行号
        if not data:
            skipped.append((name, "空文件"))
            continue
        h, body = [c.strip() for c in data[0][1]], data[1:]
        if header is None:
            header = h
            if a.source_col in header:
                ap.error("表头里已经有「%s」这一列，请用 --source-col 换个列名" % a.source_col)
        if h != header:
            skipped.append((name, "表头不同（%s）" % describe_diff(header, h)))
            continue
        long_rows = [i for i, r in body if len(r) > len(header)]
        if long_rows:
            skipped.append((name, "第 %d 行比表头多出内容，可能有未加引号的逗号" % long_rows[0]))
            continue
        rows += [r + [""] * (len(header) - len(r)) + [name] for _, r in body]
        report.append((name, len(body), enc))

    for name, n, enc in report:
        print("合并 %s%6d 行  %s" % (pad(name), n, enc))
    for name, why in skipped:
        print("跳过 %s%s" % (pad(name), why))
    if not report:
        print("没有可合并的数据（%d 个文件都被跳过）。" % len(skipped))
        return 3
    try:
        atomic_write_csv(out, [header + [a.source_col]] + rows)
    except OSError as e:
        print("结果写不进去：%s（%s）。文件是不是正在 Excel 里打开？" % (out, e.strerror or e), file=sys.stderr)
        return 2
    print("\n共 %d 行，来自 %d 个文件，跳过 %d 个。结果：%s" % (len(rows), len(report), len(skipped), out))
    print("核对：上面各文件行数相加应等于 %d；再随机抽 3 行和原表对一下。" % len(rows))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。结果文件没有写入，原文件未改动，重跑即可。", file=sys.stderr)
        sys.exit(130)
