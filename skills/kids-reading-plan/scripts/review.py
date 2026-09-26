#!/usr/bin/env python3
"""月度复盘：从「阅读记录.csv」算出四个数，并按复盘表列出可以考虑的一处调整。只读记录，不改文件。

用法：
  python3 review.py 阅读记录.csv                      # 默认只算记录里最近的一个月
  python3 review.py 阅读记录.csv --month 2026-10      # 指定月份；--month all 算全部记录
  python3 review.py 阅读记录.csv --plan-minutes 20    # 带上计划的每日分钟，顺便对比

记录表列名：日期,书名,方式,分钟,读到哪,孩子说的一句话（最后一列可空）。
日期可写 2026-10-08、2026/10/8、2026年10月8日；「方式」写共读、自主，听书、电子书等也可以；
「读到哪」写页码或章节，读完写「读完」，不想读了写「放弃」。
格式不对的行会逐行说明并跳过，不会让整个复盘失败。
退出码：0 成功；1 参数错误或缺列；2 文件读写失败；3 选定月份没有有效记录；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import calendar
import collections
import csv
import datetime as dt
import re
import sys

NEEDED = ["日期", "书名", "方式", "分钟", "读到哪"]
DATE_RE = re.compile(r"^\s*(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?\s*$")


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def parse_date(text):
    m = DATE_RE.match(text or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def read_rows(path):
    for enc in ("utf-8-sig", "gb18030"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                return reader.fieldnames or [], list(reader)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, "既不是 UTF-8 也不是 GBK")


def main(argv=None):
    ap = ArgParser(description="阅读记录月度复盘：四个数 + 一处调整的候选")
    ap.add_argument("csv", help="阅读记录.csv")
    ap.add_argument("--month", help="要复盘的月份，如 2026-10；all 表示全部记录（默认最近一个月）")
    ap.add_argument("--plan-minutes", type=int, help="计划的每日分钟数（可选，用来对比）")
    a = ap.parse_args(argv)
    if a.month and a.month != "all" and not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", a.month):
        ap.error("--month 要写成 2026-10 这样的格式，或写 all")
    if a.plan_minutes is not None and not 1 <= a.plan_minutes <= 180:
        ap.error("--plan-minutes 请给 1 到 180 之间的整数")

    try:
        cols, rows = read_rows(a.csv)
    except FileNotFoundError:
        print("找不到记录表：%s（检查路径；路径里有空格时用引号包起来）" % a.csv, file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("读不出 %s 的文字：请用表格软件另存为「CSV UTF-8」再试。" % a.csv, file=sys.stderr)
        return 2
    except OSError as e:
        print("读取失败：%s（%s）" % (a.csv, e.strerror or e), file=sys.stderr)
        return 2
    missing = [c for c in NEEDED if c not in cols]
    if missing:
        ap.error("记录表缺少列「%s」。第一行应为：日期,书名,方式,分钟,读到哪,孩子说的一句话"
                 % "」「".join(missing))

    good, problems = [], []
    for line_no, r in enumerate(rows, 2):
        if not any((v or "").strip() for k, v in r.items() if k):
            continue
        day = parse_date(r.get("日期"))
        try:
            minutes = float((r.get("分钟") or "").strip())
        except ValueError:
            minutes = None
        if day is None:
            problems.append("第 %d 行：日期「%s」认不出，请写成 2026-10-08" % (line_no, r.get("日期")))
        elif minutes is None or not 0 <= minutes <= 600:
            problems.append("第 %d 行：分钟「%s」不是 0–600 之间的数字" % (line_no, r.get("分钟")))
        else:
            good.append((day, (r.get("书名") or "").strip(), (r.get("方式") or "").strip() or "未注明",
                         minutes, (r.get("读到哪") or "").strip()))
    for p in problems:
        print("跳过 " + p)
    if not good:
        print("没有有效的记录行。")
        return 3

    months = sorted({d.strftime("%Y-%m") for d, *_ in good})
    month = a.month or months[-1]
    if month != "all":
        good = [g for g in good if g[0].strftime("%Y-%m") == month]
        if not good:
            print("%s 没有记录（记录里有的月份：%s）。" % (month, "、".join(months)))
            return 3
        if not a.month and len(months) > 1:
            print("记录跨 %d 个月，默认只算最近的 %s；要算别的月份用 --month。" % (len(months), month))

    days = sorted({g[0] for g in good})
    mins = collections.Counter()
    for _, _, way, m, _ in good:
        mins[way] += m
    total = sum(mins.values())
    avg = total / len(days)
    # 按书名去重：同一天共读、自主各记一行时，一本书只算一次
    finished = {g[1] or g for g in good if g[4] == "读完"}
    dropped = {g[1] or g for g in good if g[4] == "放弃"} - finished
    finished, dropped = len(finished), len(dropped)
    titles = len({g[1] for g in good if g[1]})

    if month == "all":
        span = (days[-1] - days[0]).days + 1
        scope = "全部记录（%s 至 %s，共 %d 天）" % (days[0], days[-1], span)
    else:
        y, mo = int(month[:4]), int(month[5:])
        span = calendar.monthrange(y, mo)[1]
        today = dt.date.today()
        if (today.year, today.month) == (y, mo):
            span = today.day
            scope = "%s（本月已过 %d 天）" % (month, span)
        else:
            scope = "%s（共 %d 天）" % (month, span)

    print("\n复盘范围：%s" % scope)
    print("1 读书天数 %d 天（占 %d%%）" % (len(days), round(100 * len(days) / span)))
    print("2 读书日平均 %d 分钟" % round(avg))
    others = "".join("，%s %d" % (k, round(v)) for k, v in sorted(mins.items()) if k not in ("共读", "自主"))
    print("3 共读:自主 = %d : %d（分钟）%s" % (round(mins["共读"]), round(mins["自主"]), others))
    print("4 读完 %d 本，放弃 %d 本（记录里出现过 %d 个书名）" % (finished, dropped, titles))

    hints = []
    if len(days) < span / 2:
        hints.append("读书天数不到一半 → 锚点可能不对：换时段或缩短时长，不加量")
    if a.plan_minutes:
        ratio = avg / a.plan_minutes
        if avg * 1.2 < a.plan_minutes:
            hints.append("平均 %d 分钟，是计划 %d 分钟的 %d%% → 若天数够而分钟明显偏低，目标下调到约 %d 分钟（实际平均 × 1.2）"
                         % (round(avg), a.plan_minutes, round(100 * ratio), round(avg * 1.2)))
    if dropped and dropped >= finished:
        hints.append("放弃 %d 本 ≥ 读完 %d 本 → 难度或兴趣可能不对：用五指法复查，换兴趣入口" % (dropped, finished))
    print("\n复盘提示（下个月最多改一处，由家长结合孩子的反应决定）：")
    for h in hints or ["数字上没有触发调整规则；再看三个问题和孩子的状态，决定是否保持不变"]:
        print("- " + h)
    print("- 另外两条要靠观察：书名八成以上是同一类 → 加一本「同题材换体裁」；孩子开始抗拒 → 退回上个月的量")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。本脚本只读记录表，没有改动任何文件。", file=sys.stderr)
        sys.exit(130)
