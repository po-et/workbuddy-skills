#!/usr/bin/env python3
"""背单词排期：按「学后第 1、2、4、7、15 天复习、每第 7 天复盘」生成排期表；
给了每天分钟数就算每天新词数，给了词表总量、自测正确率和考试日期就做可行性检查。只用标准库。

用法：
  python3 vocab_plan.py --start 2026-10-01 --days 30
  python3 vocab_plan.py --start 2026-10-01 --minutes 40 --total 5500 --known-pct 45 --exam 2027-04-19 --show 21
  python3 vocab_plan.py --start 2026-10-01 --days 60 --per-day 16 --csv plan.csv

规则：第 D 天复习第 D-1、D-2、D-4、D-7、D-15 天学的组；每第 7 天是复盘日，不学新词、复习照常；
给了 --exam 时，考前最后 15 天不学新词（冲刺），考前最后 3 天只看错词本。
退出码：0 成功；1 参数或输入有误；2 写不了 --csv 文件；130 被 Ctrl+C 中断。
"""
import argparse
import csv
import datetime as dt
import io
import math
import os
import re
import sys

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130
GAPS = (1, 2, 4, 7, 15)
REST_EVERY = 7
SPRINT_DAYS = 15
LAST_DAYS = 3


class InputError(Exception):
    """输入有误，退出码 1。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 vocab_plan.py --help\n" % message)


def parse_date(text, what):
    m = re.match(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$", text or "")
    if not m:
        raise InputError("%s「%s」不是日期，请写成 YYYY-MM-DD，例如 2026-10-01" % (what, text))
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise InputError("%s「%s」不存在，请核对日历" % (what, text))


def build_rows(start, days, per_day, exam_days):
    """逐天生成排期。exam_days=离考试的天数（考试当天不排），None 表示没有考试日期。"""
    rows, done = [], set()
    for d in range(1, days + 1):
        left = None if exam_days is None else exam_days - d + 1  # 含当天，距考试还剩几天
        sprint = left is not None and left <= SPRINT_DAYS
        last = left is not None and left <= LAST_DAYS
        rest = d % REST_EVERY == 0
        due = ["D%d" % (d - k) for k in GAPS if d - k in done]
        if sprint:
            new = "冲刺·复盘日" if rest else "冲刺·不学新词"
        elif rest:
            new = "复盘日"
        else:
            new = "D%d组" % d
            done.add(d)
        if last:
            review, note = "只看错词本", "考前最后 %d 天" % LAST_DAYS
        else:
            review = " ".join(due) or "—"
            note = "复习后加一次旧词抽查" if sprint else ""
        rows.append({
            "day": d,
            "date": start + dt.timedelta(days=d - 1),
            "new": new,
            "count": per_day if (per_day and new.endswith("组")) else "",
            "review": review,
            "note": note,
        })
    return rows


def plan_numbers(a, notes):
    """算每天新词数与可行性，返回 (per_day, 文字段落列表)。"""
    out = []
    per_day = None
    if a.per_day is not None:
        if a.per_day <= 0:
            raise InputError("--per-day 要大于 0")
        per_day = a.per_day
        out.append("每天新词：%d 个（你指定的）" % per_day)
    elif a.minutes is not None:
        if a.minutes <= 0:
            raise InputError("--minutes 要大于 0：按最忙的那一天也能保证的分钟数填")
        if a.divisor <= 0:
            raise InputError("--divisor 要大于 0（默认 2.5）")
        per_day = int(a.minutes // a.divisor)
        if per_day == 0:
            raise InputError("每天 %g 分钟连 1 个新词都排不下（至少 %g 分钟）；先只做复习，或挤出更多时间"
                             % (a.minutes, a.divisor))
        if a.minutes > 240:
            notes.append("每天 %g 分钟超过 4 小时，长期很难坚持，请确认" % a.minutes)
        out.append("每天新词：%g 分钟 ÷ %g = %d 个（向下取整；用时是估计，第一周按实际计时修正，"
                   "复习明显更慢就把 --divisor 调大）" % (a.minutes, a.divisor, per_day))
    return per_day, out


def feasibility(a, per_day, days, exam_days, notes):
    out = []
    if a.total is None:
        return out
    if a.total <= 0:
        raise InputError("--total 要大于 0：词表词条总数以考试大纲或词表实际收词为准")
    known = a.known_pct
    if known is None:
        known = 0.0
        notes.append("[待确认] 没给自测正确率，按已会 0% 算；从词表均匀抽 100 个词自测后用 --known-pct 重算")
    if not 0 <= known <= 100:
        raise InputError("--known-pct 是百分数，应在 0–100 之间，收到 %g" % known)
    gap = int(round(a.total * (100 - known) / 100.0))
    out.append("缺口：%d × (1 − %g%%) = %d 词" % (a.total, known, gap))
    if gap == 0:
        out.append("结论：自测全会，不需要新词；只做复习和主动用词练习。")
        return out
    if not per_day:
        out.append("没给 --minutes 或 --per-day，算不出要多少天。")
        return out
    need = math.ceil(gap / float(per_day))
    out.append("需要学新词的天数：%d ÷ %d = %d 天（向上取整）" % (gap, per_day, need))
    if exam_days is None:
        out.append("没给考试日期（--exam），不做够不够的判断。")
        return out
    if exam_days <= SPRINT_DAYS:
        out.append("结论：离考试只有 %d 天，都在最后 %d 天的冲刺期内，按规则不再学新词："
                   "只复习已学的词和错词本，每天加一次旧词抽查。" % (exam_days, SPRINT_DAYS))
        return out
    window = exam_days - SPRINT_DAYS
    rest = window // REST_EVERY
    avail = window - rest
    out.append("可学新词的天数：离考试 %d 天 − 最后 %d 天 = %d 天，去掉其中的复盘日 %d 天 = %d 天"
               % (exam_days, SPRINT_DAYS, window, rest, avail))
    if need <= avail:
        out.append("结论：够用，还富余 %d 天。" % (avail - need))
    else:
        want = math.ceil(gap / float(avail))
        mins = math.ceil(want * a.divisor)
        out.append("结论：不够，差 %d 天。二选一：每天加到 %d 分钟（每天 %d 个，约 %d 天学完）；"
                   "或把低频词降级为「只认不拼」，只保证见词知义。"
                   % (need - avail, mins, want, math.ceil(gap / float(want))))
    return out


def render_rows(rows):
    lines = []
    for r in rows:
        new = r["new"] + ("（%s词）" % r["count"] if r["count"] else "")
        tail = "  " + r["note"] if r["note"] else ""
        lines.append("第%d天 %s 新学 %s 复习 %s%s" % (r["day"], r["date"].strftime("%m/%d"),
                                                 new, r["review"], tail))
    return lines


def write_csv(path, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["天数", "日期", "新学", "词数", "要复习的组", "备注", "用时(分)", "错词", "完成"])
    for r in rows:
        w.writerow([r["day"], r["date"].isoformat(), r["new"], r["count"], r["review"], r["note"], "", "", ""])
    tmp = path + ".part"
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:  # 带 BOM，Excel 打开不乱码
            f.write(buf.getvalue())
        os.replace(tmp, path)
    except OSError as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise IOError("写不了 %s：%s（检查目录是否存在、有没有写权限、文件是否正被 Excel 打开）" % (path, e))


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数或输入有误；2 写不了 --csv 文件；130 中断")
    ap.add_argument("--start", required=True, help="第 1 天的日期，YYYY-MM-DD")
    ap.add_argument("--days", type=int, help="要排多少天（默认 30；给了 --exam 时默认排到考试前一天）")
    ap.add_argument("--exam", help="考试日期，YYYY-MM-DD；最后 15 天不学新词，最后 3 天只看错词本")
    ap.add_argument("--minutes", type=float, help="每天能保证的分钟数，用来算每天新词数")
    ap.add_argument("--divisor", type=float, default=2.5, help="每天新词数 = 分钟数 ÷ 这个数（默认 2.5）")
    ap.add_argument("--per-day", type=int, help="直接指定每天新词数（优先于 --minutes）")
    ap.add_argument("--total", type=int, help="词表词条总数")
    ap.add_argument("--known-pct", type=float, help="自测正确率，百分数 0–100")
    ap.add_argument("--show", type=int, default=0, help="只在屏幕上显示前 N 天（0 = 全部；CSV 总是全部）")
    ap.add_argument("--csv", help="另存完整排期为 CSV（UTF-8 带 BOM）")
    a = ap.parse_args(argv)

    notes = []
    try:
        start = parse_date(a.start, "--start")
        exam_days = None
        if a.exam:
            exam = parse_date(a.exam, "--exam")
            exam_days = (exam - start).days
            if exam_days <= 0:
                raise InputError("考试日期 %s 不晚于开始日期 %s，请核对" % (exam, start))
        days = a.days if a.days is not None else (exam_days or 30)
        if not 1 <= days <= 1000:
            raise InputError("--days 应在 1–1000 之间，收到 %d" % days)
        if exam_days is not None and days > exam_days:
            notes.append("--days %d 超过了离考试的 %d 天，已排到考试前一天为止" % (days, exam_days))
            days = exam_days
        if a.show < 0:
            raise InputError("--show 不能是负数")
        per_day, head = plan_numbers(a, notes)
        head += feasibility(a, per_day, days, exam_days, notes)
    except InputError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS

    rows = build_rows(start, days, per_day, exam_days)
    for line in head:
        print(line)
    for n in notes:
        print("注意：" + n)
    if head or notes:
        print()
    shown = rows[: a.show] if a.show else rows
    print("\n".join(render_rows(shown)))
    if len(shown) < len(rows):
        print("……共 %d 天，只显示前 %d 天；完整排期用 --csv 另存" % (len(rows), len(shown)))
    if a.csv:
        try:
            write_csv(a.csv, rows)
        except IOError as e:
            sys.stderr.write("文件错误：%s\n" % e)
            return EXIT_IO
        print("已写入 %s（%d 天）" % (a.csv, len(rows)))
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），CSV 没有写出半截文件。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
