#!/usr/bin/env python3
"""7 天屏幕记录小结：按用途、结束方式、睡前、卧室汇总，并按「先判断」第 3 步的顺序指出先解决哪一两件事。

输入 CSV（UTF-8 或 GB18030），表头与 SKILL.md 的记录表一致，括号里的提示可有可无：
  日期,设备,时段,做什么(学习/创作/联系/消遣),分钟,在哪,怎么结束(自己停/提醒后停/哭闹)
必需列：日期、做什么、分钟、怎么结束；时段写成 19:30-20:10（或只写开始时间），用来判断睡前。
时长数字是公开的常见建议，不是诊断标准；本脚本不判断孩子是否「成瘾」。只用 Python 标准库，不联网。

用法：
  python3 screen_log.py log.csv --age 8 --bedtime 21:30
  python3 screen_log.py log.csv --age 8 --out 小结.md
退出码：0 成功；1 参数错误；2 读写文件失败；3 记录内容有误（缺列、分钟不是数字等）；130 用户中断
"""

import argparse
import csv
import io
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict

USES = ("学习", "创作", "联系", "消遣")
ENDS = ("自己停", "提醒后停", "哭闹")
REQUIRED = ("日期", "做什么", "分钟", "怎么结束")
TIME_RE = re.compile(r"(\d{1,2})[:：](\d{2})")


class ArgError(Exception):
    pass


class LogError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)


def hhmm(text):
    m = TIME_RE.search(text or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return None
    return h * 60 + mi


def fmt_t(minutes):
    return "%02d:%02d" % divmod(minutes % (24 * 60), 60)


def read_rows(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise OSError("无法识别文件编码，请另存为 UTF-8 的 CSV")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        raise LogError("文件是空的：第一行要是表头，从第二行起每段屏幕时间一行")
    names = [re.split(r"[（(]", h.strip())[0] for h in header]  # 去掉「做什么(学习/…)」里的括号提示
    missing = [c for c in REQUIRED if c not in names]
    if missing:
        raise LogError("缺少列：%s。表头示例：日期,设备,时段,做什么,分钟,在哪,怎么结束" % "、".join(missing))
    rows = []
    for lineno, values in enumerate(reader, 2):
        if not any(v.strip() for v in values):
            continue
        row = dict(zip(names, [v.strip() for v in values]))
        use = row.get("做什么", "")
        if use not in USES:
            raise LogError("第 %d 行「做什么」写的是「%s」，只能填：%s" % (lineno, use, " / ".join(USES)))
        try:
            minutes = int(float(row.get("分钟", "")))
        except ValueError:
            raise LogError("第 %d 行分钟「%s」不是数字，请写成 30 这样的整数" % (lineno, row.get("分钟", "")))
        if not 0 <= minutes <= 1440:
            raise LogError("第 %d 行分钟是 %d，超出一天的范围，请核对" % (lineno, minutes))
        row["分钟"] = minutes
        row["行"] = lineno
        rows.append(row)
    if not rows:
        raise LogError("只有表头，没有记录：每段屏幕时间写一行")
    return rows


def age_rule(age):
    if age is None:
        return None
    if age < 2:
        return ("0–2 岁", "尽量不看屏幕，和亲人视频通话除外", 0, None)
    if age <= 5:
        return ("2–5 岁", "每天不超过 1 小时，越少越好，大人陪着看", 60, None)
    if age <= 12:
        return ("6–12 岁", "非学习用途单次不超过 15 分钟，每天累计不超过 1 小时", 60, 15)
    return ("13 岁以上", "没有统一数字，看睡眠、运动、功课和面对面交往是否被挤掉", None, None)


def build(rows, age, bedtime):
    days = list(dict.fromkeys(r["日期"] for r in rows))  # 保持记录里的先后顺序
    total = sum(r["分钟"] for r in rows)
    by_use = Counter()
    for r in rows:
        by_use[r["做什么"]] += r["分钟"]
    ends = Counter(r["怎么结束"] if r["怎么结束"] in ENDS else "其他或没写" for r in rows)
    crying = ends.get("哭闹", 0)
    bedroom = [r for r in rows if "卧室" in r.get("在哪", "") or "床" in r.get("在哪", "")]
    latest = defaultdict(lambda: None)
    late = []
    for r in rows:
        times = TIME_RE.findall(r.get("时段", ""))
        start = hhmm(r.get("时段", ""))
        if start is None:
            continue
        end = hhmm(":".join(times[1])) if len(times) > 1 else start + r["分钟"]
        if start < 5 * 60:  # 凌晨开始的算作前一晚的深夜
            start, end = start + 24 * 60, end + 24 * 60
        if end < start:  # 跨过午夜
            end += 24 * 60
        if latest[r["日期"]] is None or end > latest[r["日期"]]:
            latest[r["日期"]] = end
        if bedtime is not None and end > bedtime - 60:
            late.append(r)

    pct = lambda part, whole: (100.0 * part / whole) if whole else 0.0
    out = ["# 7 天屏幕记录小结", ""]
    out.append("记录 %d 天，共 %d 段，合计 %d 分钟；日均 %.0f 分钟" % (len(days), len(rows), total, total / len(days)))
    out.append("按用途：" + "｜".join("%s %d 分钟（%.0f%%）" % (u, by_use[u], pct(by_use[u], total)) for u in USES))
    out.append("结束方式：" + "｜".join("%s %d 段" % (k, ends[k]) for k in ENDS + ("其他或没写",) if ends.get(k)))
    if latest:
        out.append("每天最晚用到：" + "｜".join("%s %s" % (d, fmt_t(latest[d])) for d in days if latest[d] is not None))
    if bedroom:
        out.append("在卧室或床上用：%d 段" % len(bedroom))

    rule = age_rule(age)
    if rule:
        label, text, daily_cap, single_cap = rule
        out += ["", "## 对照年龄常见建议（%s：%s）" % (label, text)]
        if daily_cap is not None:
            out.append("口径：学习和联系（和亲人视频）不计入，只算创作和消遣；这是上限参考，不是诊断标准。")
        fun = defaultdict(int)
        for r in rows:
            if r["做什么"] in ("创作", "消遣"):
                fun[r["日期"]] += r["分钟"]
        if daily_cap == 0:
            used = [d for d in days if fun[d] > 0]
            out.append("- 有创作或消遣的天数：%d/%d（常见建议是尽量不看）" % (len(used), len(days)))
        elif daily_cap is not None:
            over = [d for d in days if fun[d] > daily_cap]
            out.append("- 创作加消遣日均 %.0f 分钟；超过 %d 分钟的有 %d/%d 天"
                       % (sum(fun.values()) / len(days), daily_cap, len(over), len(days)))
        if single_cap is not None:
            longs = [r for r in rows if r["做什么"] in ("创作", "消遣") and r["分钟"] > single_cap]
            out.append("- 单次超过 %d 分钟的有 %d 段" % (single_cap, len(longs)))

    found = []
    if crying * 2 > len(rows):
        found.append("先练结束方式，不急着砍时长：哭闹结束 %d/%d 段，超过一半" % (crying, len(rows)))
    if bedtime is not None and late:
        found.append("先管睡前：有 %d 段用到了睡前 1 小时以内（%s 之后）" % (len(late), fmt_t(bedtime - 60)))
    if pct(by_use["消遣"], total) >= 80:
        found.append("先安排替代活动：消遣占 %.0f%%，到了八成以上" % pct(by_use["消遣"], total))
    out += ["", "## 先解决哪一两件事（按「先判断」第 3 步的顺序对号入座）"]
    if found:
        out.append("- 先解决：" + found[0])
        if len(found) > 1:
            out.append("- 再解决：" + found[1])
        for extra in found[2:]:
            out.append("- 之后再说：" + extra)
    else:
        out.append("- 记录里没有触发前三条（哭闹过半、睡前在用、消遣八成以上）；从下面两项人工判断，或只从超出年龄参考的部分入手")
    out.append("- 记录表看不出来、要你判断的两项：内容合不合适（合适就不动，不合适先管内容）；有没有挤掉作业或户外（挤掉了先定时段）")
    notes = []
    if bedtime is None:
        notes.append("没给入睡时间，无法判断「睡前 1 小时」：加 --bedtime 21:30 这样的参数再跑一次 [待确认]")
    if bedroom:
        notes.append("有 %d 段在卧室或床上用：常见建议是设备不进卧室过夜" % len(bedroom))
    if len(days) < 7:
        notes.append("只记了 %d 天，结论仅供参考；建议记满 7 天再定规则" % len(days))
    if ends.get("其他或没写"):
        notes.append("有 %d 段「怎么结束」没写或不是 自己停 / 提醒后停 / 哭闹，没算进哭闹比例" % ends["其他或没写"])
    if notes:
        out += ["", "## 提示"] + ["- " + n for n in notes]
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
    p = Parser(description="7 天屏幕记录小结（常见建议对照，不做诊断）。")
    p.add_argument("csv", help="记录表 CSV：日期,设备,时段,做什么,分钟,在哪,怎么结束")
    p.add_argument("--age", type=int, help="孩子年龄（0–17），用来对照常见建议")
    p.add_argument("--bedtime", help="孩子平时几点睡，HH:MM，用来判断睡前 1 小时")
    p.add_argument("--out", help="写入这个 Markdown 文件（默认打印到屏幕）")
    try:
        a = p.parse_args(argv)
        if a.age is not None and not 0 <= a.age <= 17:
            raise ArgError("--age 要在 0 到 17 之间；本技能按未成年人的常见建议对照，成年子女不适用")
        bedtime = None
        if a.bedtime:
            if not re.match(r"^\d{1,2}[:：]\d{2}$", a.bedtime.strip()) or hhmm(a.bedtime) is None:
                raise ArgError("--bedtime「%s」看不懂，请写成 21:30 这样的时间" % a.bedtime)
            bedtime = hhmm(a.bedtime)
        if a.out and os.path.abspath(a.out) == os.path.abspath(a.csv):
            raise ArgError("--out 不能和输入的记录表是同一个文件")
    except ArgError as exc:
        print("参数错误：%s\n用法：python3 screen_log.py 记录.csv [--age 8] [--bedtime 21:30] [--out 小结.md]"
              % exc, file=sys.stderr)
        return 1
    try:
        rows = read_rows(a.csv)
    except FileNotFoundError:
        print("读不到文件：%s（检查路径和文件名）" % a.csv, file=sys.stderr)
        return 2
    except IsADirectoryError:
        print("%s 是文件夹，请指定记录表 CSV 文件" % a.csv, file=sys.stderr)
        return 2
    except OSError as exc:
        print("读取失败：%s" % exc, file=sys.stderr)
        return 2
    except (LogError, csv.Error) as exc:
        print("记录表有误：%s" % exc, file=sys.stderr)
        return 3
    report = build(rows, a.age, bedtime)
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
