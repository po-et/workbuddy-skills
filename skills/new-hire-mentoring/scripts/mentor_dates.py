#!/usr/bin/env python3
"""带教节点日期表：每周一对一（默认 13 次）和第 30/60/90 天节点，标出星期几；
落在周末的给出「挪到前一个工作日」的建议。入职日算第 1 天。纯标准库，不联网。

用法：
  python3 scripts/mentor_dates.py 2026-10-08 2026-10-09             # 入职日、第一次正式一对一
  python3 scripts/mentor_dates.py 2026-10-08 2026-10-09 --weeks 12
  python3 scripts/mentor_dates.py 2026-10-08 2026-10-09 --out 带教日程.md   # 另存为文件

日期可以写 2026-10-08、2026/10/08、2026.10.08 或 20261008。
法定节假日和调休脚本不认识（不内置任何假期表），以官方通知为准，落在假期的同样挪到前一个工作日。

退出码：
  0   日期表已生成，没有落在周末的节点
  3   日期表已生成，但有节点落在周末或第一次一对一排得太晚，先看「需要调整」
  1   参数不对：日期写法看不懂、一对一早于入职日、--weeks 超出 1–26
  2   --out 指定的文件写不进去
  130 用户按 Ctrl+C 中断
"""
import argparse
import datetime as dt
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_CHECK, EXIT_INTERRUPT = 0, 1, 2, 3, 130
WEEKDAY = "一二三四五六日"


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「写文件失败」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class InputProblem(Exception):
    """日期看不懂或前后矛盾 → 退出码 1。"""


def parse_date(text, what):
    s = text.strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s) or re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if not m:
        raise InputProblem("%s「%s」看不懂：请写成 2026-10-08 这样的年-月-日" % (what, text))
    try:
        return dt.date(*(int(x) for x in m.groups()))
    except ValueError:
        raise InputProblem("%s「%s」不是真实存在的日期" % (what, text))


def label(d):
    return "%s 周%s" % (d.isoformat(), WEEKDAY[d.weekday()])


def previous_workday(d):
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def build(start, first, weeks):
    notes, rows = [], []
    if first < start:
        raise InputProblem("第一次一对一 %s 早于入职日 %s，两个日期是不是写反了" % (first, start))
    if (first - start).days > 7:
        notes.append("第一次正式一对一在入职 %d 天后；建议放在第一周周末前，先对齐 30 天目标" % (first - start).days)
    for w in range(1, weeks + 1):
        rows.append(("第%d次一对一" % w, first + dt.timedelta(weeks=w - 1)))
    for n in (30, 60, 90):
        rows.append(("第%d天节点" % n, start + dt.timedelta(days=n - 1)))
    rows.sort(key=lambda r: (r[1], r[0]))

    lines = ["# 带教节点日期（入职日 %s 记为第 1 天）" % label(start), "",
             "| 事项 | 日期 | 调整建议 |", "|---|---|---|"]
    for name, d in rows:
        tip = ""
        if d.weekday() >= 5:
            tip = "落在周末 → 挪到 %s" % label(previous_workday(d))
            notes.append("%s落在周末，建议挪到 %s" % (name, label(previous_workday(d))))
        lines.append("| %s | %s | %s |" % (name, label(d), tip))
    lines += ["", "说明：只识别周末；法定节假日和调休以官方通知为准，落在假期的同样挪到前一个工作日。",
              "一对一不取消，要改期也只改一次。"]
    if notes:
        lines += ["", "## 需要调整"] + ["- [待确认] " + n for n in notes]
    return "\n".join(lines) + "\n", notes


def write_atomic(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".mentor_dates-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp, 0o666 & ~mask)  # mkstemp 默认 0600，改回普通文件权限
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = Parser(description="带教节点日期表（每周一对一 + 30/60/90 天节点）")
    ap.add_argument("start", help="入职日，如 2026-10-08")
    ap.add_argument("first", help="第一次正式一对一的日期，如 2026-10-09")
    ap.add_argument("--weeks", type=int, default=13, help="一对一排几次（默认 13 次，约 90 天）")
    ap.add_argument("--out", help="另存为文件（先写临时文件再替换，不会留下半截文件）")
    args = ap.parse_args(argv)
    if not 1 <= args.weeks <= 26:
        ap.error("--weeks 应在 1 到 26 之间，现在是 %d" % args.weeks)
    try:
        text, notes = build(parse_date(args.start, "入职日"), parse_date(args.first, "第一次一对一"), args.weeks)
    except InputProblem as e:
        sys.stderr.write("输入有问题：%s\n" % e)
        return EXIT_INPUT
    if args.out:
        try:
            write_atomic(args.out, text)
        except OSError as e:
            sys.stderr.write("写文件失败：%s（%s）。换个目录或文件名再试；日期表如下：\n" % (args.out, e.strerror or e))
            sys.stdout.write(text)
            return EXIT_IO
        print("已保存：%s" % os.path.abspath(args.out))
    sys.stdout.write(text)
    return EXIT_CHECK if notes else EXIT_OK


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有写出任何文件。\n")
        sys.exit(EXIT_INTERRUPT)
