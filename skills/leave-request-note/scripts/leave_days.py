#!/usr/bin/env python3
"""请假天数计算：输入起止日期，输出自然日、其中周一至周五的天数，
以及按你标注的节假日（休）与调休上班日（班）修正后的工作日。只用 Python 标准库。

用法：
  python3 leave_days.py 2026-11-05 2026-11-11
  python3 leave_days.py 2026-11-05 2026-11-06 --from-half pm      # 5 日下午开始
  python3 leave_days.py 2026-11-05 2026-11-06 --to-half am        # 6 日上午结束
  python3 leave_days.py 2026-11-05 2026-11-11 --off 2026-11-09 --work 2026-11-08
  python3 leave_days.py 2026-11-05 2026-11-11 --calendar holidays.txt --json

脚本不内置任何年份的放假安排：法定节假日和调休上班日由你对照当年官方通知标注。
--calendar 文件每行一个日期加「休」或「班」，# 开头是注释（下面的日期只演示格式）：
  2026-11-09 休
  2026-11-08 班

退出码：0 成功；1 参数或日期有误；2 读不了 --calendar 文件；130 被 Ctrl+C 中断。
"""
import argparse
import datetime as dt
import json
import re
import sys

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130
WEEK = "一二三四五六日"
DATE_RE = re.compile(r"^\s*(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?\s*$")


class InputError(Exception):
    """用户输入有误，退出码 1。"""


class FileReadError(Exception):
    """文件读不了，退出码 2。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 leave_days.py --help\n" % message)


def parse_date(text, what):
    m = DATE_RE.match(text or "")
    if not m:
        raise InputError("%s「%s」不是日期；请写成 YYYY-MM-DD，例如 2026-11-05" % (what, text))
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise InputError("%s「%s」不存在（月份或日子超出范围），请核对日历" % (what, text))


def label(day):
    return "%s（周%s）" % (day.isoformat(), WEEK[day.weekday()])


def fmt(n):
    return ("%.1f" % n).rstrip("0").rstrip(".")


def read_calendar(path):
    """读 --calendar 文件，返回 (休的日期集合, 班的日期集合)。"""
    off, work = set(), set()
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        raise FileReadError("找不到节假日文件：%s（检查路径，或改用 --off/--work 直接标注）" % path)
    except (OSError, UnicodeDecodeError) as e:
        raise FileReadError("读不了节假日文件 %s：%s（请存成 UTF-8 文本）" % (path, e))
    for no, line in enumerate(lines, 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or parts[1] not in ("休", "班"):
            raise InputError("节假日文件第 %d 行「%s」格式不对：应为「日期 休」或「日期 班」" % (no, line))
        day = parse_date(parts[0], "节假日文件第 %d 行的日期" % no)
        (off if parts[1] == "休" else work).add(day)
    return off, work


def compute(start, end, from_half, to_half, off, work):
    if end < start:
        raise InputError("结束日期 %s 早于开始日期 %s：是不是起止写反了？想要的也许是 %s 至 %s"
                         % (end, start, end, start))
    if start == end and from_half == "pm" and to_half == "am":
        raise InputError("同一天既从下午开始又在上午结束，时间自相矛盾；只请半天请只写其中一个")
    clash = sorted(off & work)
    if clash:
        raise InputError("%s 同时被标成了「休」和「班」，请核对放假通知" % "、".join(map(str, clash)))

    days = [start + dt.timedelta(i) for i in range((end - start).days + 1)]
    notes = []

    def cut(counted):
        """按半天修正：counted(day) 判断这一天是否计入。"""
        total = float(sum(1 for d in days if counted(d)))
        if from_half == "pm" and counted(start):
            total -= 0.5
        if to_half == "am" and counted(end):
            total -= 0.5
        return total

    natural = cut(lambda d: True)
    weekdays = cut(lambda d: d.weekday() < 5)
    marked = bool(off or work)
    workdays = cut(lambda d: (d.weekday() < 5 and d not in off) or d in work) if marked else None

    off_in = sorted(d for d in off if start <= d <= end)
    work_in = sorted(d for d in work if start <= d <= end)
    for d in off_in:
        if d.weekday() >= 5:
            notes.append("%s本来就是周末，标「休」不影响工作日数" % label(d))
    for d in work_in:
        if d.weekday() < 5:
            notes.append("%s本来就是工作日，标「班」不影响工作日数" % label(d))
    outside = sorted(d for d in (off | work) if not start <= d <= end)
    if outside:
        notes.append("有 %d 个标注日期不在请假区间内，已忽略" % len(outside))
    if len(days) > 366:
        notes.append("区间超过一年，请确认起止没有写错年份")
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "from_half": from_half,
        "to_half": to_half,
        "natural_days": natural,
        "weekdays_mon_fri": weekdays,
        "workdays_after_marks": workdays,
        "off_in_range": [d.isoformat() for d in off_in],
        "work_in_range": [d.isoformat() for d in work_in],
        "notes": notes,
    }


def render(r, start, end):
    head = "请假起止：%s%s开始，至 %s%s结束" % (
        label(start), "下午" if r["from_half"] == "pm" else "上午",
        label(end), "上午" if r["to_half"] == "am" else "下午")
    lines = [
        head,
        "自然日：%s 天" % fmt(r["natural_days"]),
        "其中周一至周五：%s 天" % fmt(r["weekdays_mon_fri"]),
    ]
    if r["workdays_after_marks"] is None:
        lines.append("未标注节假日与调休：区间内如有法定节假日或调休上班日，用 --off / --work 标注后重算")
    else:
        lines.append("按你标注的休与班修正后的工作日：%s 天（休：%s；班：%s）" % (
            fmt(r["workdays_after_marks"]),
            "、".join(r["off_in_range"]) or "无", "、".join(r["work_in_range"]) or "无"))
    for n in r["notes"]:
        lines.append("注意：" + n)
    lines.append("核对：以上只按你给的日期计算；按工作日还是自然日计、半天怎么算，以本单位考勤口径为准。")
    return "\n".join(lines)


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数或日期有误；2 读不了 --calendar 文件；130 中断")
    ap.add_argument("start", help="开始日期，YYYY-MM-DD")
    ap.add_argument("end", help="结束日期，YYYY-MM-DD（含当天）")
    ap.add_argument("--from-half", choices=["am", "pm"], help="pm = 开始那天从下午开始")
    ap.add_argument("--to-half", choices=["am", "pm"], help="am = 结束那天上午结束")
    ap.add_argument("--off", action="append", default=[], metavar="DATE",
                    help="区间内的法定节假日（休），可写多次或用逗号分隔")
    ap.add_argument("--work", action="append", default=[], metavar="DATE",
                    help="区间内的调休上班日（班），可写多次或用逗号分隔")
    ap.add_argument("--calendar", metavar="FILE", help="节假日文件：每行「日期 休」或「日期 班」")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args(argv)

    try:
        start = parse_date(a.start, "开始日期")
        end = parse_date(a.end, "结束日期")
        off = {parse_date(x, "--off 日期") for v in a.off for x in v.split(",") if x.strip()}
        work = {parse_date(x, "--work 日期") for v in a.work for x in v.split(",") if x.strip()}
        if a.calendar:
            c_off, c_work = read_calendar(a.calendar)
            off |= c_off
            work |= c_work
        result = compute(start, end, a.from_half, a.to_half, off, work)
    except InputError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS
    except FileReadError as e:
        sys.stderr.write("文件错误：%s\n" % e)
        return EXIT_IO

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result, start, end))
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有写任何文件。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
