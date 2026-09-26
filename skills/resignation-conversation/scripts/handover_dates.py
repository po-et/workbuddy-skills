#!/usr/bin/env python3
"""离职交接倒排表：按「提出日」和「最后工作日」排出交接三阶段的具体日期，并核对与合同通知期是否对得上。

只做日期推算，不做任何法律判断：通知期按自然日还是工作日、从哪天起算，以劳动合同与 HR 答复为准。
不扣除法定节假日与调休（每年安排不同），只按周一到周五计工作日。只用 Python 标准库，不联网。

用法：
  python3 handover_dates.py --notice-date 2026-10-12 --last-day 2026-11-11 --notice-days 30
  python3 handover_dates.py --notice-date 2026-10-12 --last-day 2026-10-23 --out 交接倒排.md
退出码：0 成功；1 参数错误（日期格式等）；2 写文件失败；3 日期自相矛盾（最后工作日早于提出日）；130 用户中断
"""

import argparse
import datetime as dt
import os
import re
import sys
import tempfile

WEEK = "一二三四五六日"


class ArgError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)


def parse_date(text, name):
    m = re.match(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$", text or "")
    if not m:
        raise ArgError("%s「%s」看不懂：请写成 YYYY-MM-DD，例如 2026-10-12" % (name, text))
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise ArgError("%s「%s」不是真实存在的日期" % (name, text))


def day(d):
    return "%s（周%s）" % (d.isoformat(), WEEK[d.weekday()])


def span(days):
    if not days:
        return "—"
    if len(days) == 1:
        return day(days[0])
    return "%s — %s" % (day(days[0]), day(days[-1]))


def phases(workdays):
    """按工作日个数切三段：列清单 / 交接会与试做 / 收尾。天数不够时按比例压缩。"""
    n = len(workdays)
    if n >= 13:
        return workdays[:5], workdays[5:-8], workdays[-8:-3], workdays[-3:], "正常节奏"
    if n >= 6:
        return workdays[:2], [], workdays[2:-2], workdays[-2:], "不到三周，已压缩"
    if n >= 3:
        return workdays[:1], [], workdays[1:-1], workdays[-1:], "不到一周半，已大幅压缩"
    return workdays[:1], [], [], workdays[1:], "时间极短，只能边列清单边交接"


def build(notice, last, notice_days):
    total = (last - notice).days
    workdays = [notice + dt.timedelta(days=i) for i in range(total + 1)]
    workdays = [d for d in workdays if d.weekday() < 5]
    out = ["# 离职交接倒排表（日期核算）", ""]
    out.append("提出日：%s｜最后工作日：%s｜相隔 %d 个自然日；两头都算，周一到周五共 %d 天（未扣法定节假日与调休）"
               % (day(notice), day(last), total, len(workdays)))
    notes = []
    if notice_days is not None:
        earliest = notice + dt.timedelta(days=notice_days)
        if last < earliest:
            notes.append("最后工作日比「提出日 + %d 天」（%s）早 %d 天：要么顺延到 %s，要么和上级协商提前，"
                         "以公司书面确认为准" % (notice_days, day(earliest), (earliest - last).days, day(earliest)))
        else:
            notes.append("按你填的通知期 %d 天推算，最早可到 %s；你定的最后工作日不早于它" % (notice_days, day(earliest)))
    if last.weekday() >= 5:
        notes.append("最后工作日落在周%s，确认是不是应为前一个周五" % WEEK[last.weekday()])
    if notice.weekday() >= 5:
        notes.append("提出日落在周%s，谈话和书面提交一般放在工作日" % WEEK[notice.weekday()])
    for n in notes:
        out.append("- " + n)
    out.append("> 通知期按自然日还是工作日、从哪天起算，以劳动合同与 HR 答复为准；本表只做日期推算，不做法律判断。")
    out.append("")
    p1, mid, p2, p3, pace = phases(workdays)
    out += ["节奏：%s" % pace, "", "| 阶段 | 日期 | 做什么 |", "|---|---|---|"]
    out.append("| 列清单 | %s | 交接清单列完：事项、状态、下一步与截止日、接手人、资料位置、对接人；和上级约好对团队怎么说 |"
               % span(p1))
    if mid:
        out.append("| 按清单逐项交接 | %s | 正常工作，边做边把进行中的事交到接手人手上 |" % span(mid))
    if p2:
        out.append("| 交接会与试做 | %s | 至少开一次交接会；接手人按清单试做一轮，你在旁边答疑 |" % span(p2))
    if p3:
        out.append("| 收尾 | %s | 只做答疑和收尾：归还设备与资料，账号按流程移交或注销，最后一天发告别消息 |" % span(p3))
    return "\n".join(out) + "\n"


def write_atomic(path, content):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".md", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    p = Parser(description="离职交接倒排表：只做日期推算，不做法律判断。")
    p.add_argument("--notice-date", required=True, help="提出离职（当面谈 + 书面提交）的日期，YYYY-MM-DD")
    p.add_argument("--last-day", required=True, help="最后工作日，YYYY-MM-DD")
    p.add_argument("--notice-days", type=int, help="合同写的通知期天数（可选），用来核对最后工作日")
    p.add_argument("--out", help="写入这个 Markdown 文件（默认打印到屏幕）")
    try:
        a = p.parse_args(argv)
        notice = parse_date(a.notice_date, "--notice-date")
        last = parse_date(a.last_day, "--last-day")
        if a.notice_days is not None and not 0 <= a.notice_days <= 366:
            raise ArgError("--notice-days 要在 0 到 366 之间（按合同原文填天数）")
    except ArgError as exc:
        print("参数错误：%s\n用法示例：python3 handover_dates.py --notice-date 2026-10-12 --last-day 2026-11-11"
              % exc, file=sys.stderr)
        return 1
    if last < notice:
        print("日期矛盾：最后工作日 %s 早于提出日 %s。请核对两个日期，或确认是不是年份写错了。"
              % (day(last), day(notice)), file=sys.stderr)
        return 3
    report = build(notice, last, a.notice_days)
    if a.out:
        try:
            write_atomic(a.out, report)
        except OSError as exc:
            print("写不了输出文件 %s：%s" % (a.out, exc.strerror or exc), file=sys.stderr)
            return 2
        print("已写入 %s" % a.out)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有写任何文件。", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
