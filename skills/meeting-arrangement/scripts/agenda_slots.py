#!/usr/bin/env python3
"""议程排时：把「议题|类型|负责人|分钟|产出」逐项排成带起止时刻的议程表，并检查
合计时长、收尾复述、负责人和产出有没有缺；可选换算跨时区的各地时间。只用 Python 标准库。

用法：
  python3 agenda_slots.py --length 30 --start 14:00 --file agenda.txt
  python3 agenda_slots.py --length 30 --item "讨论与决策|决策|决策人|25|选定方案" --item "复述决定与待办|收尾|记录人|5|待办表"
  python3 agenda_slots.py --length 60 --start 09:00 --file agenda.txt --md --out agenda.md
  python3 agenda_slots.py --length 30 --start 14:00 --file agenda.txt --date 2026-10-13 --tz Asia/Shanghai --also-tz Europe/Berlin

agenda.txt 每行一项：议题|类型|负责人|分钟|产出（# 开头的行是注释；类型建议用 知会/讨论/决策，开场、收尾也可以）。
只做文本排版，不接入任何日历或会议系统。
退出码：0 成功（「提醒」不影响）；1 参数或议程内容有误；2 读写文件失败；130 被 Ctrl+C 中断。
"""
import argparse
import datetime as dt
import math
import os
import re
import sys
import unicodedata

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130
TIME_RE = re.compile(r"^\s*(\d{1,2})[:：](\d{2})\s*$")


class InputError(Exception):
    """输入有误，退出码 1。"""


class FileError(Exception):
    """文件读写失败，退出码 2。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 agenda_slots.py --help\n" % message)


def parse_time(text):
    m = TIME_RE.match(text or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise InputError("开始时间「%s」应写成 24 小时制 HH:MM，例如 14:00" % text)
    return int(m.group(1)) * 60 + int(m.group(2))


def parse_items(lines, where):
    items = []
    for no, raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 5:
            raise InputError("%s第 %d 行应有 5 段「议题|类型|负责人|分钟|产出」，实际 %d 段：%s"
                             % (where, no, len(parts), line))
        topic, kind, owner, mins, output = parts
        if not topic:
            raise InputError("%s第 %d 行没有议题" % (where, no))
        if not mins.isdigit() or int(mins) <= 0:
            raise InputError("%s第 %d 行的分钟数「%s」应是正整数" % (where, no, mins))
        items.append({"topic": topic, "kind": kind or "—", "owner": owner, "mins": int(mins),
                      "output": output or "—"})
    if not items:
        raise InputError("议程是空的：用 --file 或 --item 至少给一项")
    return items


def read_lines(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return list(enumerate(f.read().splitlines(), 1))
    except FileNotFoundError:
        raise FileError("找不到议程文件：%s" % path)
    except (OSError, UnicodeDecodeError) as e:
        raise FileError("读不了议程文件 %s：%s（请存成 UTF-8 文本）" % (path, e))


def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, w):
    return s + " " * max(0, w - width(s))


def hhmm(total):
    total %= 24 * 60
    return "%02d:%02d" % (total // 60, total % 60)


def check(items, length):
    notes = []  # (级别, 文字)
    total = sum(i["mins"] for i in items)
    if total > length:
        raise InputError("各项合计 %d 分钟，超过会议时长 %d 分钟：删一项、压缩知会项，或把会议延长" % (total, length))
    if total < length:
        notes.append(("提醒", "各项合计 %d 分钟，还剩 %d 分钟没排：留作机动，或把会议缩短到 %d 分钟"
                      % (total, length - total, total)))
    else:
        notes.append(("通过", "各项合计 %d 分钟，与会议时长一致" % total))
    if length > 90:
        notes.append(("提醒", "会议超过 90 分钟：拆成两场，或先用文档把知会部分消化掉"))
    need = min(5, math.ceil(length * 0.1))
    last = items[-1]
    if ("复述" in last["topic"] or "待办" in last["topic"]) and last["mins"] >= need:
        notes.append(("通过", "最后一项「%s」%d 分钟，留给复述决定与待办" % (last["topic"], last["mins"])))
    else:
        notes.append(("提醒", "最后至少留 %d 分钟复述决定与待办（议题写成「复述决定与待办」）" % need))
    for n, i in enumerate(items, 1):
        if not i["owner"]:
            notes.append(("提醒", "第 %d 项「%s」没有负责人：没有具体负责人，就是没人负责" % (n, i["topic"])))
        if i["output"] == "—" and n != 1:
            notes.append(("提醒", "第 %d 项「%s」没写产出：开完不知道结论是什么" % (n, i["topic"])))
        if i["kind"] == "知会" and i["mins"] > 10:
            notes.append(("提醒", "第 %d 项是知会、占 %d 分钟：能写进会前材料的不在会上念" % (n, i["mins"])))
    return notes


def zone_lines(date_text, tz, also, start, length):
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:
        raise InputError("跨时区换算需要 Python 3.9 以上（zoneinfo）")
    try:
        day = dt.date.fromisoformat(date_text)
    except ValueError:
        raise InputError("--date「%s」应写成 YYYY-MM-DD" % date_text)
    names = [tz] + [z.strip() for z in also.split(",") if z.strip()]
    try:
        zones = [(n, ZoneInfo(n)) for n in names]
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise InputError("时区名不认识：%s（用 IANA 名称，如 Asia/Shanghai、Europe/Berlin；"
                         "Windows 可能要先 pip install tzdata）" % e)
    begin = dt.datetime.combine(day, dt.time(start // 60, start % 60), tzinfo=zones[0][1])
    end = begin + dt.timedelta(minutes=length)
    out = []
    for name, z in zones:
        b, e = begin.astimezone(z), end.astimezone(z)
        odd = b.hour < 7 or e.hour * 60 + e.minute > 21 * 60 or e.date() != b.date()
        tail = "  ← 当地不在 07:00–21:00 之间，确认对方能参加" if odd else ""
        out.append("  %s  %s %s–%s%s" % (pad(name, 20), b.strftime("%m-%d"), b.strftime("%H:%M"),
                                          e.strftime("%H:%M"), tail))
    return out


def render(items, length, start, title, md):
    rows, t = [], 0
    for i in items:
        rel = "%02d–%02d" % (t, t + i["mins"])
        clock = "%s–%s" % (hhmm(start + t), hhmm(start + t + i["mins"])) if start is not None else ""
        rows.append((rel, clock, i))
        t += i["mins"]
    head = "【%d 分钟%s】" % (length, " · " + title if title else "")
    if start is not None:
        head += "%s–%s" % (hhmm(start), hhmm(start + length))
    if md:
        lines = [head, "", "| 时段 | 时刻 | 议题 | 类型 | 负责人 | 产出 |", "|---|---|---|---|---|---|"]
        for rel, clock, i in rows:
            lines.append("| %s | %s | %s | %s | %s | %s |" % (rel, clock or "—", i["topic"], i["kind"],
                                                         i["owner"] or "[待补]", i["output"]))
        return lines
    tw = max(width(i["topic"]) for i in items) + 2
    ow = max(width(i["owner"] or "[待补]") for i in items) + 2
    lines = [head]
    for rel, clock, i in rows:
        lines.append("%s  %s%s%s%s%s" % (rel, clock + "  " if clock else "", pad(i["topic"], tw),
                                          pad(i["kind"], 6), pad(i["owner"] or "[待补]", ow), i["output"]))
    return lines


def write_atomic(path, text):
    tmp = path + ".part"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise FileError("写不了 %s：%s" % (path, e))


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数或议程内容有误；2 读写文件失败；130 中断")
    ap.add_argument("--length", type=int, required=True, help="会议时长（分钟）")
    ap.add_argument("--start", help="开始时间 HH:MM（24 小时制）；不给就只排相对时段")
    ap.add_argument("--file", help="议程文件，每行「议题|类型|负责人|分钟|产出」")
    ap.add_argument("--item", action="append", default=[], help="直接给一项，可写多次")
    ap.add_argument("--title", default="", help="标题里显示的会议类型或名称")
    ap.add_argument("--md", action="store_true", help="输出 Markdown 表格")
    ap.add_argument("--out", help="另存到文件（先写临时文件再改名）")
    ap.add_argument("--date", help="会议日期 YYYY-MM-DD；跨时区换算时必填（夏令时会影响结果）")
    ap.add_argument("--tz", default="Asia/Shanghai", help="开始时间所在时区（默认 Asia/Shanghai）")
    ap.add_argument("--also-tz", default="", help="要换算的其他时区，逗号分隔，如 Europe/Berlin,America/New_York")
    a = ap.parse_args(argv)

    try:
        if a.length <= 0 or a.length > 480:
            raise InputError("--length 应在 1–480 分钟之间，收到 %d" % a.length)
        start = parse_time(a.start) if a.start else None
        lines = read_lines(a.file) if a.file else []
        items = parse_items(lines, "议程文件") if a.file else []
        if a.item:
            items += parse_items(list(enumerate(a.item, 1)), "--item ")
        if not items:
            raise InputError("议程是空的：用 --file 或 --item 至少给一项")
        notes = check(items, a.length)
        out = render(items, a.length, start, a.title, a.md)
        if a.also_tz:
            if start is None or not a.date:
                raise InputError("跨时区换算需要同时给 --start 和 --date")
            out += ["", "各地时间："] + zone_lines(a.date, a.tz, a.also_tz, start, a.length)
        out += ["", "检查："] + ["  [%s] %s" % n for n in notes]
        text = "\n".join(out) + "\n"
        if a.out:
            write_atomic(a.out, text)
    except InputError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS
    except FileError as e:
        sys.stderr.write("文件错误：%s\n" % e)
        return EXIT_IO
    sys.stdout.write(text)
    if a.out:
        print("已写入 %s" % a.out)
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有写出半截文件。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
