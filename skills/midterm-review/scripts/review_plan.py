#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""期中复习：按各科考试日期、学分、难度、自评把握度，排出每日复习分配表。

只用 Python 标准库，不联网。

  python3 review_plan.py --start 2026-10-19 --hours 4 --weekend-hours 6 \
      --course "高等数学,2026-10-28,5,2,4" \
      --course "大学物理,10-30,4,3,4" \
      --course "C语言程序设计,11-02,3,4,3" --out plan.md

课程写法：名称,考试日期,学分,把握度(1-5)[,难度(1-5，省略按 3)]
也可以 --csv courses.csv，表头：课程,考试日期,学分,把握度,难度

规则（与 SKILL.md 一致，全部是经验值，可用参数调）：
  优先分 = 学分 × 难度 × (6 − 把握度)；≥36 为 A，≥16 为 B，其余为 C
  每天按「优先分 × 临近系数」分：距考试 ≥8 天 1.0，4–7 天 1.6，2–3 天 2.5，1 天 5.0
  每门课的应得时长逐天记账，按整块（--block，默认 1 小时）发给欠账最多的课；
  每天最多 3 门（--max-per-day）；次日要考的课当天先拿一块
  考试当天可用时长打折（--exam-day-factor，默认 0.5）

同样的输入永远得到同样的输出；只有省略 --start 时才读今天的日期。
退出码：0 成功；1 参数或数据有误；2 文件读写失败；130 手动中断。
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_INTERRUPT = 0, 1, 2, 130

WEEKDAYS = "一二三四五六日"
MAX_SPAN_DAYS = 60          # 开始日到最后一门考试超过这个天数，多半是年份写错
TIER_A, TIER_B = 36, 16     # 优先分阈值（经验值）
HEAVY_DAY_HOURS = 10        # 每天超过这个小时数给提醒
STAGES = (                  # (距考试天数下限, 临近系数, 阶段任务)
    (8, 1.0, "摸底补漏"),
    (4, 1.6, "专题+真题分章"),
    (2, 2.5, "整套模拟+错题"),
    (1, 5.0, "错题本+要点卡"),
)
CSV_HEADERS = {
    "课程": ("课程", "名称", "科目", "course", "name"),
    "考试日期": ("考试日期", "日期", "exam", "date"),
    "学分": ("学分", "credit", "credits"),
    "把握度": ("把握度", "把握", "confidence"),
    "难度": ("难度", "difficulty"),
}


class InputError(Exception):
    """参数或课程数据有误，退出码 1。"""


class Course(object):
    __slots__ = ("name", "exam", "credit", "confidence", "difficulty", "priority", "tier", "hours")

    def __init__(self, name, exam, credit, confidence, difficulty):
        self.name, self.exam = name, exam
        self.credit, self.confidence, self.difficulty = credit, confidence, difficulty
        self.priority = credit * difficulty * (6 - confidence)
        self.tier = "A" if self.priority >= TIER_A else ("B" if self.priority >= TIER_B else "C")
        self.hours = 0.0


# ---------------------------------------------------------------- 解析

_DATE_FULL = re.compile(r"^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?$")
_DATE_SHORT = re.compile(r"^(\d{1,2})[-/.月](\d{1,2})日?$")


def parse_date(text, ref_year=None):
    s = text.strip().replace(" ", "")
    m = _DATE_FULL.match(s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = _DATE_SHORT.match(s)
        if not m or ref_year is None:
            raise InputError("日期「%s」看不懂：请写成 2026-10-28（课程里也可以写 10-28）" % text)
        y, mo, d = ref_year, int(m.group(1)), int(m.group(2))
    try:
        return dt.date(y, mo, d)
    except ValueError:
        raise InputError("日期「%s」不存在（例如 11 月没有 31 日）" % text)


def parse_number(text, label, low, high):
    s = text.strip()
    try:
        value = float(s)
    except ValueError:
        raise InputError("%s「%s」不是数字" % (label, text))
    if not low <= value <= high:
        raise InputError("%s「%s」超出范围：应在 %g–%g 之间" % (label, text, low, high))
    return value


def make_course(fields, ref_year, where):
    fields = [f.strip() for f in fields]
    while fields and fields[-1] == "":
        fields.pop()
    if len(fields) not in (4, 5):
        raise InputError("%s：需要 4 或 5 项「名称,考试日期,学分,把握度[,难度]」，收到 %d 项"
                         % (where, len(fields)))
    name = fields[0]
    if not name:
        raise InputError("%s：课程名称是空的" % where)
    try:
        exam = parse_date(fields[1], ref_year)
        credit = parse_number(fields[2], "学分", 0.5, 20)
        confidence = parse_number(fields[3], "把握度", 1, 5)
        difficulty = parse_number(fields[4], "难度", 1, 5) if len(fields) == 5 else 3.0
    except InputError as exc:
        raise InputError("%s（%s）：%s" % (where, name, exc))
    return Course(name, exam, credit, confidence, difficulty)


def read_csv_courses(path, ref_year):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        raise IOError("找不到课程文件：%s" % path)
    except OSError as exc:
        raise IOError("读不了课程文件 %s：%s" % (path, exc.strerror or exc))
    text = None
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise IOError("课程文件编码认不出来：请用 UTF-8 另存一次")
    rows = [(no, ln) for no, ln in enumerate(text.splitlines(), 1)
            if ln.strip() and not ln.lstrip().startswith("#")]
    if len(rows) < 2:
        raise InputError("课程文件至少要有表头和一门课")
    head_no, head = rows[0]
    if "," not in head and "，" in head:
        raise InputError("第 %d 行表头用的是中文逗号「，」：请换成英文逗号「,」" % head_no)
    header = [h.strip().lower() for h in next(csv.reader([head]))]
    col = {}
    for idx, h in enumerate(header):
        for std, aliases in CSV_HEADERS.items():
            if h in aliases and std not in col:
                col[std] = idx
    missing = [k for k in ("课程", "考试日期", "学分", "把握度") if k not in col]
    if missing:
        raise InputError("课程文件表头缺少「%s」；读到的是：%s" % ("」「".join(missing), " | ".join(header)))
    order = ["课程", "考试日期", "学分", "把握度"] + (["难度"] if "难度" in col else [])
    courses = []
    for no, line in rows[1:]:
        cells = next(csv.reader([line]))
        fields = [cells[col[k]] if col[k] < len(cells) else "" for k in order]
        if len(fields) == 5 and not fields[4].strip():
            fields = fields[:4]
        courses.append(make_course(fields, ref_year, "第 %d 行" % no))
    return courses


# ---------------------------------------------------------------- 计算

def stage_for(days_left):
    for low, factor, task in STAGES:
        if days_left >= low:
            return factor, task
    return 0.0, "考试日"


def fmt_h(hours):
    return "%gh" % hours


def fmt_day(d):
    return "%02d-%02d 周%s" % (d.month, d.day, WEEKDAYS[d.weekday()])


def plan(courses, start, hours, weekend_hours, exam_factor, off_days, max_per_day, block_units):
    """逐天分配。每门课每天「应得」= 当天块数 × 权重占比，记进欠账；
    再以 block_units 个半小时为一块，每次把一块给欠账最多的课（次日要考的课先拿一块）。
    这样低优先的课不会每天碎成半小时，而是隔几天拿到一整块；结果完全确定、可复现。"""
    last = max(c.exam for c in courses)
    exam_days = {}
    for c in courses:
        exam_days.setdefault(c.exam, []).append(c)
    debt = dict((c.name, 0.0) for c in courses)
    rows = []
    d = start
    while d <= last:
        base = weekend_hours if d.weekday() >= 5 else hours
        note = []
        if d in off_days:
            avail = 0.0
            note.append("休息日（--off）")
        elif d in exam_days:
            avail = base * exam_factor
        else:
            avail = base
        if d in exam_days:
            note.insert(0, "★考试：" + "、".join(c.name for c in exam_days[d]))
        units = int(avail * 2 + 1e-9)
        active = sorted((c for c in courses if c.exam > d), key=lambda c: (c.exam, -c.priority, c.name))
        forced = [c for c in active if (c.exam - d).days == 1]
        tasks, got = {}, {}
        if units and active:
            weights = {}
            for c in active:
                factor, tasks[c.name] = stage_for((c.exam - d).days)
                weights[c.name] = c.priority * factor
            total_w = sum(weights.values())
            for c in active:
                debt[c.name] += units * weights[c.name] / total_w
            left = units
            queue = list(forced)
            while left > 0:
                if queue:
                    pick = queue.pop(0)
                else:
                    pool = active if len(got) < max_per_day else [c for c in active if c.name in got]
                    pick = max(pool, key=lambda x: (debt[x.name], -active.index(x)))
                n = min(block_units, left)
                got[pick.name] = got.get(pick.name, 0) + n
                debt[pick.name] -= n
                left -= n
        else:
            for c in active:
                tasks[c.name] = stage_for((c.exam - d).days)[1]
        parts = []
        for c in sorted(active, key=lambda x: (-got.get(x.name, 0), x.exam, x.name)):
            if c.name in got:
                h = got[c.name] / 2.0
                c.hours += h
                parts.append("%s %s（%s）" % (c.name, fmt_h(h), tasks[c.name]))
        rows.append((d, units / 2.0, parts, note, forced))
        d += dt.timedelta(days=1)
    return rows


def build_report(courses, start, rows, args, used_today):
    out = []
    add = out.append
    add("# 期中复习每日分配表（脚本生成）")
    add("")
    add("- 开始：%s%s；工作日 %s、周末 %s；考试当天按 %g%% 计；每块 %s；每天最多 %d 门"
        % (fmt_day(start), "（未给 --start，按今天）" if used_today else "",
           fmt_h(args.hours), fmt_h(args.weekend_hours), args.exam_day_factor * 100,
           fmt_h(args.block), args.max_per_day))
    add("- 规则：优先分 = 学分 × 难度 × (6 − 把握度)；A ≥ %d，B ≥ %d，其余 C（经验阈值）" % (TIER_A, TIER_B))
    add("")
    add("## 课程分级")
    add("")
    add("| 课程 | 考试日期 | 学分 | 难度 | 把握度 | 优先分 | 分级 | 分到总时长 |")
    add("|---|---|---:|---:|---:|---:|:---:|---:|")
    by_rank = sorted(courses, key=lambda c: (-c.priority, c.exam, c.name))
    for c in by_rank:
        add("| %s | %s | %g | %g | %g | %g | %s | %s |" % (
            c.name.replace("|", "\\|"), fmt_day(c.exam), c.credit, c.difficulty, c.confidence,
            round(c.priority, 1), c.tier, fmt_h(c.hours)))
    total = sum(c.hours for c in courses)
    add("")
    add("合计 %s。" % fmt_h(total))
    add("")
    add("## 每日分配")
    add("")
    add("| 日期 | 可用 | 分配（阶段任务） |")
    add("|---|---:|---|")
    warnings = []
    for d, avail, parts, note, forced in rows:
        label = fmt_day(d) + ("  " + "；".join(note) if note else "")
        cell = "；".join(parts) if parts else ("只翻要点卡和错题本" if any(c.exam == d for c in courses) else "—")
        add("| %s | %s | %s |" % (label, fmt_h(avail), cell))
        for c in forced:
            if avail == 0:
                warnings.append("%s 是「%s」考前一天，却没有可用时间：挪一下 --off 或加时长。"
                                % (fmt_day(d), c.name))
    add("")
    add("## 提醒")
    add("")
    for c in by_rank:
        if c.hours < args.min_hours:
            warnings.append("「%s」总共只分到 %s，低于保底 %s（约做一套题再订正的时间）："
                            "从分得最多的课挪一块给它，或加每日时长。"
                            % (c.name, fmt_h(c.hours), fmt_h(args.min_hours)))
    same_day = {}
    for c in courses:
        same_day.setdefault(c.exam, []).append(c.name)
    for day in sorted(same_day):
        if len(same_day[day]) > 1:
            warnings.append("%s 同一天考 %s：前一天主攻先考的那门，另一门只过要点卡和错题本。"
                            % (fmt_day(day), "、".join(same_day[day])))
    if max(args.hours, args.weekend_hours) > HEAVY_DAY_HOURS:
        warnings.append("每天安排超过 %d 小时，后面几天效率会掉；留出吃饭、运动和睡觉的时间。" % HEAVY_DAY_HOURS)
    for w in warnings:
        add("- ⚠ " + w)
    if any(len(parts) == 1 and avail >= 4 for _, avail, parts, _, _ in rows):
        add("- 只剩一门课的日子，表里的时长是上限：自测正确率稳定了就收工，把时间还给睡眠和运动。")
    add("- 每天第一块时间先做主动回忆（合上书写出来），再看课件；错题按「隔 1 天、隔 3 天、考前一天」重做。")
    add("- 考前一天只看错题本和要点卡，按清单准备证件与文具，按平时时间睡觉。")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 输出与入口

def write_atomic(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".plan-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def build_parser():
    p = argparse.ArgumentParser(
        description="期中复习：各科考试日期、学分、自评把握度 → 每日复习分配表（Markdown）。",
        epilog="退出码：0 成功；1 参数或数据有误；2 文件读写失败；130 手动中断。")
    p.add_argument("--course", action="append", default=[],
                   help="名称,考试日期,学分,把握度[,难度]，可重复；把握度与难度都是 1–5")
    p.add_argument("--csv", help="课程 CSV：表头 课程,考试日期,学分,把握度,难度")
    p.add_argument("--start", help="从哪天开始复习，默认今天（想要可复现的结果就写上）")
    p.add_argument("--hours", type=float, default=4.0, help="工作日每天可用小时数，默认 4")
    p.add_argument("--weekend-hours", type=float, help="周末每天可用小时数，默认同 --hours")
    p.add_argument("--exam-day-factor", type=float, default=0.5, help="考试当天可用时长的折扣，默认 0.5")
    p.add_argument("--off", action="append", default=[], help="这天不复习（如 10-24），可重复")
    p.add_argument("--max-per-day", type=int, default=3, help="每天最多复习几门，默认 3")
    p.add_argument("--block", type=float, default=1.0, help="一块复习时间多长（小时，0.5 的倍数），默认 1")
    p.add_argument("--min-hours", type=float, default=2.0, help="每门课总时长保底，低于就提醒，默认 2")
    p.add_argument("--out", help="把结果写进这个文件（默认打印到屏幕）")
    return p


def run(argv):
    args = build_parser().parse_args(argv)
    used_today = not args.start
    start = parse_date(args.start) if args.start else dt.date.today()
    if args.weekend_hours is None:
        args.weekend_hours = args.hours
    for label, value in (("--hours", args.hours), ("--weekend-hours", args.weekend_hours)):
        if not 0 <= value <= 16:
            raise InputError("%s 应在 0–16 之间，收到 %g" % (label, value))
    if args.hours == 0 and args.weekend_hours == 0:
        raise InputError("--hours 和 --weekend-hours 都是 0，排不出计划")
    if not 0 <= args.exam_day_factor <= 1:
        raise InputError("--exam-day-factor 应在 0–1 之间，收到 %g" % args.exam_day_factor)
    if not 1 <= args.max_per_day <= 6:
        raise InputError("--max-per-day 应在 1–6 之间，收到 %d" % args.max_per_day)
    if args.min_hours < 0:
        raise InputError("--min-hours 不能是负数")
    if not 0.5 <= args.block <= 3 or abs(args.block * 2 - round(args.block * 2)) > 1e-9:
        raise InputError("--block 应是 0.5–3 之间、0.5 的倍数，收到 %g" % args.block)

    courses = [make_course(re.split(r"[,，]", spec), start.year, "--course 第 %d 个" % (i + 1))
               for i, spec in enumerate(args.course)]
    if args.csv:
        courses += read_csv_courses(args.csv, start.year)
    if not courses:
        raise InputError("没有课程：用 --course \"高等数学,2026-10-28,5,2\" 或 --csv courses.csv")
    names = [c.name for c in courses]
    dup = sorted(set(n for n in names if names.count(n) > 1))
    if dup:
        raise InputError("课程名重复：%s（同一门课只写一次）" % "、".join(dup))
    for c in courses:
        if c.exam < start:
            raise InputError("「%s」的考试日期 %s 早于开始日期 %s：已经考完就删掉这门，写错了就改日期"
                             % (c.name, c.exam.isoformat(), start.isoformat()))
    span = (max(c.exam for c in courses) - start).days
    if span > MAX_SPAN_DAYS:
        raise InputError("最后一门考试离开始日 %d 天，超过 %d 天：检查年份或月份" % (span, MAX_SPAN_DAYS))
    off_days = set()
    for text in args.off:
        off_days.add(parse_date(text, start.year))

    rows = plan(courses, start, args.hours, args.weekend_hours, args.exam_day_factor,
                off_days, args.max_per_day, int(round(args.block * 2)))
    report = build_report(courses, start, rows, args, used_today)
    if args.out:
        try:
            write_atomic(args.out, report)
        except OSError as exc:
            raise IOError("写不进 %s：%s" % (args.out, exc.strerror or exc))
        print("已写入 %s（%d 门课，%d 天）" % (args.out, len(courses), len(rows)))
    else:
        sys.stdout.write(report)
    return EXIT_OK


def main(argv=None):
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except InputError as exc:
        print("输入有误：%s" % exc, file=sys.stderr)
        return EXIT_INPUT
    except IOError as exc:
        print("文件读写失败：%s" % exc, file=sys.stderr)
        return EXIT_IO
    except KeyboardInterrupt:
        print("\n已中断，没有写出任何文件。", file=sys.stderr)
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(main())
