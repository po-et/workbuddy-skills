#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""问卷统计：把你自己收集的问卷 CSV 统计成「人数 + 占比 + 有效 n」的 Markdown 表格。

只统计文件里真实存在的回答，不补数据、不外推。只用 Python 标准库。

用法：
  python3 survey_tally.py answers.csv
  python3 survey_tally.py answers.csv --skip "序号,提交时间" --multi "Q3" --sep "┋"
  python3 survey_tally.py answers.csv --order "Q5=很不方便|不太方便|一般|比较方便|很方便"
  python3 survey_tally.py answers.csv --source "本队 2026 年 7 月线下问卷" --out tables.md

约定：每行一份答卷，每列一道题；多选题一个单元格里用分隔符隔开多个选项。
列名像个人信息（姓名、电话、身份证、住址、微信等）的列默认跳过；含手机号、身份证号、邮箱样式内容的列一律不输出。

退出码：0 成功；1 输入内容或参数错误；2 文件读写失败；130 按了 Ctrl+C。
"""

import argparse
import csv
import io
import os
import re
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_UP

DEFAULT_SEP = "┋;；|"
DEFAULT_MAX_OPTIONS = 15
SMALL_N = 30  # 经验阈值：有效回答少于这个数，建议正文以人数表述
# 列名（去掉括号里的说明后）以这些词结尾，视为个人信息列
SENSITIVE_SUFFIXES = ("姓名", "名字", "称呼", "昵称", "联系人", "手机号", "手机号码", "电话", "联系方式", "身份证",
                      "身份证号", "住址", "门牌号", "微信", "微信号", "QQ", "QQ号", "邮箱", "学号")
ALL_UNIQUE_MIN = 6  # 有效回答不少于这个数且人人答案都不同，视为编号、姓名或开放题
# 单元格里出现手机号、身份证号、邮箱样式的内容，整列不统计、不输出
PII_VALUE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)\d{17}[\dXx](?!\d)|[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")


class UsageError(Exception):
    """参数错误，退出码 1。"""


class InputError(Exception):
    """CSV 内容错误，退出码 1。"""


class FileError(Exception):
    """文件读写失败，退出码 2。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError("参数错误：%s（用 --help 看用法）" % message)


def build_parser():
    p = Parser(
        prog="survey_tally.py",
        description="问卷统计：输出人数、占比和有效 n 的 Markdown 表格。只统计文件里真实存在的回答。",
        epilog="退出码：0 成功；1 输入或参数错误；2 文件读写失败；130 中断。",
    )
    p.add_argument("csv", help="问卷 CSV 路径（每行一份答卷）；写 - 表示从标准输入读")
    p.add_argument("--cols", help="只统计这些列，逗号分隔；不给则统计全部列（减去 --skip）")
    p.add_argument("--skip", help="不统计的列，逗号分隔，如 序号,提交时间")
    p.add_argument("--multi", help="多选题列，逗号分隔")
    p.add_argument("--sep", default=DEFAULT_SEP, help="多选题分隔符，任一字符都算（默认 ┋;；|）")
    p.add_argument("--order", action="append", default=[],
                   help="按指定顺序列选项，如 \"Q5=很不方便|不太方便|一般|比较方便|很方便\"；可写多次")
    p.add_argument("--max-options", type=int, default=DEFAULT_MAX_OPTIONS,
                   help="不同答案超过这个数的列视为开放题或编号列，默认跳过（默认 15）")
    p.add_argument("--source", help="数据来源说明，会写在每张表下面，如「本队 2026 年 7 月线下问卷」")
    p.add_argument("--out", help="把结果另存为 Markdown 文件（先写临时文件再替换）")
    return p


def split_names(text):
    if not text:
        return []
    return [x.strip() for x in re.split(r"[,，]", text) if x.strip()]


def read_text(path):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            raise FileError("找不到文件：%s（检查路径；问卷平台导出的文件先另存为 CSV）" % path)
        except IsADirectoryError:
            raise FileError("%s 是文件夹，不是 CSV 文件" % path)
        except OSError as exc:
            raise FileError("读不了文件 %s：%s" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise FileError("文件既不是 UTF-8 也不是 GB18030 编码：请在表格软件里另存为「CSV UTF-8」")


def load(text):
    reader = csv.reader(io.StringIO(text))
    header = None
    for row in reader:
        if any(c.strip() for c in row):
            header = [c.strip().lstrip("\ufeff") for c in row]
            break
    if header is None:
        raise InputError("文件是空的，没有表头")
    blank_names = [i + 1 for i, h in enumerate(header) if not h]
    if blank_names:
        raise InputError("第 %s 列没有列名：给每道题一个列名（如 Q1）" % "、".join(map(str, blank_names)))
    dup = sorted(set(h for h in header if header.count(h) > 1))
    if dup:
        raise InputError("表头有重复的列名：%s" % "、".join(dup))
    rows, skipped_blank, errors = [], 0, []
    for row in reader:
        if not any(c.strip() for c in row):
            skipped_blank += 1
            continue
        if len(row) > len(header):
            errors.append("第 %d 行比表头多了 %d 列：某个答案里是不是有英文逗号？导出时选「带引号」或把逗号换成中文逗号"
                          % (reader.line_num, len(row) - len(header)))
            continue
        row = row + [""] * (len(header) - len(row))
        rows.append([c.strip() for c in row])
    if errors:
        raise InputError("\n".join(errors[:10]))
    if not rows:
        raise InputError("只有表头，没有答卷")
    return header, rows, skipped_blank


def parse_orders(specs, header):
    orders = {}
    for spec in specs:
        m = re.match(r"^(.+?)[=＝](.+)$", spec.strip())
        if not m:
            raise UsageError("--order「%s」格式不对，应写成 列名=选项1|选项2|…" % spec)
        col, opts = m.group(1).strip(), [o.strip() for o in m.group(2).split("|") if o.strip()]
        if col not in header:
            raise UsageError("--order 里的列「%s」不在表头里" % col)
        if len(set(opts)) != len(opts):
            raise UsageError("--order 里「%s」的选项有重复" % col)
        orders[col] = opts
    return orders


def pct(count, n):
    value = (Decimal(count) * 100 / Decimal(n)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return value


def tally(values, multi, sep_chars):
    counts, first_seen, answered = {}, {}, 0
    splitter = re.compile("[%s]" % re.escape(sep_chars)) if multi else None
    for v in values:
        if not v:
            continue
        opts = [o.strip() for o in splitter.split(v)] if multi else [v]
        opts = [o for o in opts if o]
        if not opts:
            continue
        answered += 1
        for o in dict.fromkeys(opts):  # 同一份答卷里重复的选项只算一次
            if o not in counts:
                counts[o] = 0
                first_seen[o] = len(first_seen)
            counts[o] += 1
    return counts, first_seen, answered


def header_sensitive(col):
    base = re.sub(r"[（(][^）)]*[）)]", "", col).strip().lower()
    return any(base.endswith(w.lower()) for w in SENSITIVE_SUFFIXES)


def render(src, enc, header, rows, skipped_blank, args, orders):
    cols_arg, skip_arg, multi_arg = split_names(args.cols), split_names(args.skip), split_names(args.multi)
    for name, names in (("--cols", cols_arg), ("--skip", skip_arg), ("--multi", multi_arg)):
        unknown = [c for c in names if c not in header]
        if unknown:
            raise UsageError("%s 里的列不在表头里：%s（现有列：%s）" % (name, "、".join(unknown), "、".join(header)))
    if not args.sep:
        raise UsageError("--sep 不能为空")
    if args.max_options < 2:
        raise UsageError("--max-options 至少为 2")
    explicit = set(cols_arg) | set(multi_arg) | set(orders)
    targets = cols_arg if cols_arg else [c for c in header if c not in skip_arg]
    total = len(rows)
    source = args.source or "[待补：如「本队 2026 年 7 月在某社区的线下问卷」]"
    out = ["# 问卷统计（只统计文件里真实存在的回答）", ""]
    out.append("来源文件：%s（%s）；答卷 %d 份%s" % (
        src, "UTF-8" if enc == "utf-8-sig" else "GB18030", total,
        "，跳过空行 %d 行" % skipped_blank if skipped_blank else ""))
    out.append("数据来源：%s" % source)
    skipped_cols, done = [], 0
    for col in targets:
        idx = header.index(col)
        values = [r[idx] for r in rows]
        if any(PII_VALUE_RE.search(v) for v in values):
            skipped_cols.append("%s：含手机号、身份证号或邮箱样式的内容，不统计也不输出；报告里不要出现这类信息" % col)
            continue
        if header_sensitive(col) and col not in cols_arg:
            skipped_cols.append("%s：列名像个人信息，已跳过（确需统计用 --cols 指定）；报告里不要出现可识别个人的信息" % col)
            continue
        multi = col in multi_arg
        counts, first_seen, n = tally(values, multi, args.sep)
        if n == 0:
            skipped_cols.append("%s：没有任何回答" % col)
            continue
        if n >= ALL_UNIQUE_MIN and len(counts) == n and not multi and col not in explicit:
            skipped_cols.append("%s：每份答卷的答案都不一样，疑似编号、姓名或开放题，未统计（确需统计用 --cols 指定）" % col)
            continue
        if len(counts) > args.max_options and col not in explicit:
            skipped_cols.append("%s：%d 个不同答案，疑似开放题或编号列，未统计（开放题先人工归类编码；"
                                "确需统计用 --cols 指定）" % (col, len(counts)))
            continue
        order = sorted(counts, key=lambda o: (-counts[o], first_seen[o]))
        missing_opts = []
        if col in orders:
            listed = orders[col]
            missing_opts = [o for o in listed if o not in counts]
            order = listed + [o for o in order if o not in listed]
        done += 1
        out.append("")
        out.append("## %s%s" % (col, "（多选）" if multi else ""))
        out.append("")
        out.append("有效回答 n=%d，未作答 %d" % (n, total - n))
        out.append("")
        out.append("| 选项 | 人数 | 占比 |")
        out.append("|---|---|---|")
        shown = Decimal(0)
        for o in order:
            c = counts.get(o, 0)
            p = pct(c, n)
            shown += p
            out.append("| %s | %d | %s%% |" % (o.replace("|", "／"), c, p))
        notes = []
        if multi:
            notes.append("多选题：占比 = 选该项的人数 ÷ 回答该题的人数，各项相加会超过 100%。")
        elif shown != Decimal("100.0"):
            notes.append("占比四舍五入到 0.1%%，合计为 %s%%，不是 100.0%% 属正常。" % shown)
        if n < SMALL_N:
            notes.append("样本较少（n<%d，经验阈值）：正文建议写「%d 人中有 x 人」，不要外推到总体。" % (SMALL_N, n))
        if missing_opts:
            notes.append("--order 里列出、但没人选的选项：%s（按 0 人列出）。" % "、".join(missing_opts))
        notes.append("数据来源：%s，n=%d。" % (source, n))
        out.append("")
        out.extend("注：" + t for t in notes)
    if skipped_cols:
        out.append("")
        out.append("## 未统计的列")
        out.append("")
        out.extend("- " + s for s in skipped_cols)
    if done == 0:
        raise InputError("没有可统计的列：" + "；".join(skipped_cols) if skipped_cols else "没有可统计的列")
    return "\n".join(out) + "\n"


def write_atomic(path, text):
    target = os.path.abspath(path)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".survey_tally-", suffix=".tmp", dir=os.path.dirname(target))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)  # mkstemp 默认 600，改回普通文件权限
        os.replace(tmp, target)
    except OSError as exc:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise FileError("写不了文件 %s：%s（检查文件夹是否存在、有没有写权限）" % (path, exc.strerror or exc))


def main(argv=None):
    args = build_parser().parse_args(argv)
    text, enc = read_text(args.csv)
    header, rows, skipped_blank = load(text)
    orders = parse_orders(args.order, header)
    report = render("标准输入" if args.csv == "-" else os.path.basename(args.csv), enc,
                    header, rows, skipped_blank, args, orders)
    sys.stdout.write(report)
    if args.out:
        write_atomic(args.out, report)
        sys.stderr.write("已写入 %s\n" % args.out)
    return 0


def run(argv=None):
    try:
        return main(argv)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有写任何文件。\n")
        return 130
    except (UsageError, InputError) as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return 1
    except FileError as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(run())
