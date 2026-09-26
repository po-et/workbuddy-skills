#!/usr/bin/env python3
"""两周作息表：由固定起床时间和需要睡多久，逐天算出见光、咖啡因截止、放下手机、
开始睡前流程和计划上床的钟点；整体作息晚一个半小时以上的，可按「每 3–4 天提前 15–30 分钟」分步排。
只做作息安排，不做诊断。只用 Python 标准库。

用法：
  python3 sleep_schedule.py --wake 07:00 --start 2026-10-12
  python3 sleep_schedule.py --wake 07:00 --need 8 --start 2026-10-12 --md
  python3 sleep_schedule.py --wake 07:00 --current-wake 09:00 --start 2026-10-12 --days 21 --csv plan.csv

计算规则：计划上床 = 起床 − 需要睡多久 − 15 分钟入睡缓冲；放下手机、开始睡前流程 = 计划上床前 60 分钟
（睡前流程从第二周开始）；咖啡因截止 = 计划上床前 8 小时，再往前取整到半点；见光 = 起床后 30 分钟内开始。
退出码：0 成功；1 参数有误；2 写不了 --csv 文件；130 被 Ctrl+C 中断。
"""
import argparse
import csv
import datetime as dt
import io
import os
import re
import sys
import unicodedata

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130
TIME_RE = re.compile(r"^\s*(\d{1,2})[:：](\d{2})\s*$")
COLUMNS = ("天", "日期", "起床", "见光开始不晚于", "咖啡因截止", "放下手机", "开始睡前流程", "计划上床", "当日重点")


class InputError(Exception):
    """参数有误，退出码 1。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 sleep_schedule.py --help\n" % message)


def parse_time(text, what):
    m = TIME_RE.match(text or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise InputError("%s「%s」应写成 24 小时制 HH:MM，例如 07:00" % (what, text))
    return int(m.group(1)) * 60 + int(m.group(2))


def hhmm(total):
    total %= 24 * 60
    return "%02d:%02d" % (total // 60, total % 60)


def build(a, notes):
    target = parse_time(a.wake, "--wake")
    try:
        start = dt.date.fromisoformat(a.start)
    except ValueError:
        raise InputError("--start「%s」应写成 YYYY-MM-DD" % a.start)
    if not 4 <= a.need <= 12:
        raise InputError("--need %g 小时不像一晚需要的睡眠；脚本只接受 4–12 小时" % a.need)
    if not 7 <= a.need <= 9:
        notes.append("多数成年人需要 7–9 小时；%g 小时先按日志观察，有疑问问医生" % a.need)
    if target < 4 * 60 or target >= 12 * 60:
        notes.append("起床时间 %s 不在常见范围：倒班、夜班的作息本表不直接适用，请和医生一起定" % hhmm(target))
    if not 1 <= a.days <= 60:
        raise InputError("--days 应在 1–60 之间")
    if not 15 <= a.step <= 30 or not 3 <= a.every <= 4:
        raise InputError("分步规则是每 3–4 天提前 15–30 分钟：--step 取 15–30，--every 取 3–4")

    current = parse_time(a.current_wake, "--current-wake") if a.current_wake else None
    stepping = False
    if current is not None:
        gap = current - target
        if gap <= 0:
            notes.append("现在的起床时间不晚于目标，不需要分步，从第 1 天起按 %s 起床" % hhmm(target))
        elif gap < 90:
            notes.append("现在比目标晚 %d 分钟，不到一个半小时：不用分步，七天都按 %s 起床，困了再上床"
                         % (gap, hhmm(target)))
        else:
            stepping = True
            steps = -(-gap // a.step)  # 向上取整
            reach = (steps - 1) * a.every + 1
            notes.append("分步：每 %d 天提前 %d 分钟，第 %d 天到达目标起床时间 %s"
                         % (a.every, a.step, reach, hhmm(target)))
            if reach > a.days:
                notes.append("--days %d 天内到不了目标，建议 --days %d" % (a.days, reach + 13))

    need = int(round(a.need * 60))
    rows = []
    prev = current if stepping else target
    for i in range(1, a.days + 1):
        wake = max(target, current - a.step * ((i - 1) // a.every + 1)) if stepping else target
        bed = wake - need - 15
        caffeine = (bed - 8 * 60) // 30 * 30
        week2 = i >= 8
        focus = "钉起床、早见光" if i <= 7 else "困了再上床"
        if i == 14:
            focus += "；用日志复盘"
        if wake != prev:
            focus = "起床提前到 %s；" % hhmm(wake) + focus
        prev = wake
        rows.append((str(i), (start + dt.timedelta(days=i - 1)).strftime("%m-%d"), hhmm(wake), hhmm(wake + 30),
                     hhmm(caffeine), hhmm(bed - 60), hhmm(bed - 60) if week2 else "—（第二周起）", hhmm(bed), focus))
    return rows


def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def render(rows, md):
    if md:
        out = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        return out
    table = [COLUMNS] + list(rows)
    ws = [max(width(r[c]) for r in table) for c in range(len(COLUMNS))]
    return ["  ".join(r[c] + " " * (ws[c] - width(r[c])) for c in range(len(COLUMNS))).rstrip()
            for r in table]


def write_csv(path, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    w.writerows(rows)
    tmp = path + ".part"
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            f.write(buf.getvalue())
        os.replace(tmp, path)
    except OSError as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise IOError("写不了 %s：%s（目录是否存在、文件是否正被表格软件打开）" % (path, e))


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数有误；2 写不了 --csv 文件；130 中断")
    ap.add_argument("--wake", required=True, help="一周七天都做得到的起床时间，HH:MM")
    ap.add_argument("--start", required=True, help="第 1 天的日期，YYYY-MM-DD")
    ap.add_argument("--need", type=float, default=7.5, help="需要睡多久（小时，默认 7.5）")
    ap.add_argument("--days", type=int, default=14, help="排多少天（默认 14）")
    ap.add_argument("--current-wake", help="现在实际的起床时间；比目标晚 90 分钟以上时按分步排")
    ap.add_argument("--step", type=int, default=30, help="分步时每次提前多少分钟（15–30，默认 30）")
    ap.add_argument("--every", type=int, default=4, help="分步时每几天提前一次（3–4，默认 4）")
    ap.add_argument("--md", action="store_true", help="输出 Markdown 表格")
    ap.add_argument("--csv", help="另存为 CSV（UTF-8 带 BOM）")
    a = ap.parse_args(argv)

    notes = []
    try:
        rows = build(a, notes)
    except InputError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS
    for n in notes:
        print("注意：" + n)
    if notes:
        print()
    print("第 0 天：定好起床时间和需要睡多久；闹钟放到下床才够得着的地方；建好睡眠日志表")
    print("\n".join(render(rows, a.md)))
    if a.csv:
        try:
            write_csv(a.csv, rows)
        except IOError as e:
            sys.stderr.write("文件错误：%s\n" % e)
            return EXIT_IO
        print("已写入 %s" % a.csv)
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），CSV 没有写出半截文件。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
