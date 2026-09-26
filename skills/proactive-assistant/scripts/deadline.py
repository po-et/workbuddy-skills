#!/usr/bin/env python3
"""截止日倒计时：距截止几天、其中周一至周五几天、截止日星期几；多条时按紧急程度排序。
只按周一至周五算，法定节假日和调休不认识（不内置任何假期表），以官方通知为准。纯标准库，不联网。

用法：
  python3 scripts/deadline.py 2026-10-09                              # 今天到截止日
  python3 scripts/deadline.py 2026-10-09 --today 2026-09-24 --label 报名表
  python3 scripts/deadline.py 10-09 11-20                             # 只写月-日：按今天所在年份理解
  python3 scripts/deadline.py --file deadlines.txt --today 2026-09-24 # 每行「日期 事项」，如：2026-10-09 报名表

日期可以写 2026-10-09、2026/10/09、2026.10.09、10-09、10/09。

退出码：
  0   都还没到期
  3   有今天到期或已经逾期的事项——需要马上提醒用户
  1   参数不对：日期看不懂、既没给日期也没给 --file
  2   --file 指定的文件读不了
  130 用户按 Ctrl+C 中断
"""
import argparse
import datetime as dt
import re
import sys

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_URGENT, EXIT_INTERRUPT = 0, 1, 2, 3, 130
WEEKDAY = "一二三四五六日"
NOTE = "只按周一至周五算；法定节假日和调休以官方通知为准，提醒里要写明这一点。"


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「文件读不了」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class InputProblem(Exception):
    """日期看不懂 → 退出码 1。"""


def parse_date(text, today):
    """返回 (date, 备注)。只写月-日时按今天所在年份理解，并在备注里说明。"""
    s = text.strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    note = ""
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})", s) or re.fullmatch(r"(\d{1,2})月(\d{1,2})日?", s)
        if not m:
            raise InputProblem("日期「%s」看不懂：写成 2026-10-09，或只写月-日如 10-09" % text)
        y, (mo, d) = today.year, (int(x) for x in m.groups())
        note = "（只写了月日，按 %d 年理解；若指明年请写全年份）" % y
    try:
        return dt.date(y, mo, d), note
    except ValueError:
        raise InputProblem("日期「%s」不是真实存在的日期" % text)


def describe(deadline, today, label, note):
    days = (deadline - today).days
    workdays = sum((today + dt.timedelta(i)).weekday() < 5 for i in range(1, days + 1))
    wd = "星期" + WEEKDAY[deadline.weekday()]
    name = (label + "：") if label else ""
    if days < 0:
        text = "%s已逾期 %d 天（截止日 %s，%s）%s" % (name, -days, deadline, wd, note)
    elif days == 0:
        text = "%s今天到期（%s，%s）%s" % (name, deadline, wd, note)
    else:
        text = "%s距截止 %d 天，其中周一至周五 %d 天；截止日是%s（%s）%s" % (name, days, workdays, wd, deadline, note)
    return days, text


def read_file(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        raise OSError("找不到文件：%s" % path)
    except IsADirectoryError:
        raise OSError("%s 是目录，请给一个文本文件" % path)
    except PermissionError:
        raise OSError("没有权限读取 %s" % path)
    for enc in ("utf-8-sig", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise OSError("%s 的编码认不出来，请另存为 UTF-8" % path)


def main(argv=None):
    ap = Parser(description="截止日倒计时（周一至周五口径）")
    ap.add_argument("dates", nargs="*", help="截止日期，可以给多个")
    ap.add_argument("--today", help="把哪天当作今天（默认本机日期），如 2026-09-24")
    ap.add_argument("--label", help="事项名称，只给一个日期时使用")
    ap.add_argument("--file", help="每行「日期 事项」的文本文件")
    args = ap.parse_args(argv)
    if not args.dates and not args.file:
        ap.error("至少给一个截止日期，或用 --file 指定清单")

    try:
        today = dt.date.today()
        if args.today:
            today, _ = parse_date(args.today, today)
        entries = [(d, args.label if len(args.dates) == 1 else "") for d in args.dates]
        if args.file:
            try:
                content = read_file(args.file)
            except OSError as e:
                sys.stderr.write("读取失败：%s\n" % e)
                return EXIT_IO
            for no, line in enumerate(content.splitlines(), 1):
                line = line.strip(" -*\t")
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                entries.append((parts[0], parts[1] if len(parts) > 1 else "第 %d 行" % no))
        results = []
        for raw, label in entries:
            deadline, note = parse_date(raw, today)
            results.append(describe(deadline, today, label, note))
    except InputProblem as e:
        sys.stderr.write("输入有问题：%s\n" % e)
        return EXIT_INPUT

    results.sort(key=lambda r: r[0])
    print("今天按 %s（星期%s）算：" % (today, WEEKDAY[today.weekday()]))
    for _, text in results:
        print("- " + text)
    print(NOTE)
    return EXIT_URGENT if any(days <= 0 for days, _ in results) else EXIT_OK


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）。\n")
        sys.exit(EXIT_INTERRUPT)
