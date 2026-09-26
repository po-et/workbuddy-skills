#!/usr/bin/env python3
"""到期提醒：把「事项,到期日」清单变成日历文件（.ics），导入后在到期前 N 天的指定时间弹出提醒。

用法：
  python3 ics_reminder.py 到期清单.csv                                   # 默认到期前 3 天 09:00 提醒
  python3 ics_reminder.py 到期清单.csv --days-before 7 --at 10:30 --out ~/Desktop/到期提醒.ics
  python3 ics_reminder.py 清单.csv --name-col 合同名称 --date-col 截止日期

CSV 至少两列，默认列名「事项」「到期日」。日期可写 2026-10-08、2026/10/8、2026.10.8、20261008、2026年10月8日。
格式不对的行、已经过去的日期、重复行会跳过并逐行说明。事项里的分号、逗号、反斜杠会按日历格式转义；
事项里有英文逗号时，CSV 里这一格要加英文双引号（表格软件导出时会自动加），否则会被当成多出一列。
同一事项同一天每次生成的 UID 相同，重复导入时多数日历会更新而不是重复添加（以各日历应用实际行为为准）。
退出码：0 成功；1 参数错误或缺列；2 文件读写失败；3 没有可写入的事项；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import csv
import datetime as dt
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

DATE_RE = re.compile(r"^\s*(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?\s*$")
COMPACT_RE = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})\s*$")


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def parse_date(text):
    m = DATE_RE.match(text) or COMPACT_RE.match(text)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line):
    """按日历格式每行不超过 75 字节折行，不切断中文字符。"""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        limit = 75 if not out else 74          # 续行开头有一个空格
        if size + n > limit:
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
    out.append(cur)
    return "\r\n ".join(out)


def trigger(days_before, hh, mm):
    """全天事件从当天 0 点算起；到期前 N 天 hh:mm 提醒 = 0 点往前 N 天再往后 hh:mm。"""
    minutes = days_before * 1440 - (hh * 60 + mm)
    sign = "-" if minutes > 0 else ""
    minutes = abs(minutes)
    d, rest = divmod(minutes, 1440)
    h, m = divmod(rest, 60)
    s = sign + "P"
    if d:
        s += "%dD" % d
    if h or m or not d:
        s += "T" + ("%dH" % h if h else "") + ("%dM" % m if m else "")
    return s if s not in ("P", "-P", "PT", "-PT") else "PT0M"


def read_csv(path):
    for enc in ("utf-8-sig", "gb18030"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, "既不是 UTF-8 也不是 GBK")


def main(argv=None):
    ap = ArgParser(description="把到期清单 CSV 变成可导入日历的 .ics 提醒")
    ap.add_argument("csv", help="到期清单 CSV")
    ap.add_argument("--out", help="输出 .ics（默认与 CSV 同目录的 到期提醒.ics）")
    ap.add_argument("--days-before", type=int, default=3, help="提前几天提醒（0–60，默认 3）")
    ap.add_argument("--at", default="09:00", help="提醒时刻 HH:MM（默认 09:00）")
    ap.add_argument("--name-col", default="事项", help="事项列名（默认 事项）")
    ap.add_argument("--date-col", default="到期日", help="日期列名（默认 到期日）")
    a = ap.parse_args(argv)

    if not 0 <= a.days_before <= 60:
        ap.error("--days-before 请给 0 到 60 之间的整数")
    m = re.match(r"^(\d{1,2}):(\d{2})$", a.at)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        ap.error("--at 要写成 HH:MM，例如 09:00")
    hh, mm = int(m.group(1)), int(m.group(2))

    src = Path(a.csv).expanduser()
    out = Path(a.out).expanduser() if a.out else src.with_name("到期提醒.ics")
    try:
        rows = read_csv(src)
    except FileNotFoundError:
        print("找不到文件：%s（检查路径；路径里有空格时用引号包起来）" % src, file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("读不出 %s 的文字：请用表格软件另存为「CSV UTF-8」再试。" % src, file=sys.stderr)
        return 2
    except OSError as e:
        print("读取失败：%s（%s）" % (src, e.strerror or e), file=sys.stderr)
        return 2
    if not rows:
        print("%s 里没有数据行。" % src)
        return 3
    cols = [c for c in (a.name_col, a.date_col) if c not in rows[0]]
    if cols:
        ap.error("CSV 里没有列「%s」；现有列：%s。用 --name-col/--date-col 指定列名"
                 % ("」「".join(cols), "、".join(k for k in rows[0] if k)))

    today = dt.date.today()
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trig = trigger(a.days_before, hh, mm)
    events, problems, seen = [], [], set()
    for line_no, row in enumerate(rows, 2):
        name = (row.get(a.name_col) or "").strip()
        raw = (row.get(a.date_col) or "").strip()
        if not name and not raw:
            continue
        day = parse_date(raw)
        if row.get(None):
            problems.append("第 %d 行「%s」：比表头多出一列——事项里有英文逗号时，整格加英文双引号或改用中文逗号"
                            % (line_no, name))
        elif not name:
            problems.append("第 %d 行：事项为空" % line_no)
        elif day is None:
            problems.append("第 %d 行「%s」：日期「%s」认不出，请写成 2026-10-08" % (line_no, name, raw))
        elif day < today:
            problems.append("第 %d 行「%s」：%s 已经过去，未写入" % (line_no, name, day.isoformat()))
        else:
            uid = hashlib.sha1(("%s|%s" % (name, day.isoformat())).encode("utf-8")).hexdigest()[:16]
            if uid in seen:
                problems.append("第 %d 行「%s」：与前面某行重复，只保留一条" % (line_no, name))
                continue
            seen.add(uid)
            events.append((day, name, uid))

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//example.com//reminder//CN", "CALSCALE:GREGORIAN"]
    for day, name, uid in sorted(events):
        lines += ["BEGIN:VEVENT", "UID:%s@example.com" % uid, "DTSTAMP:%s" % now,
                  "DTSTART;VALUE=DATE:%s" % day.strftime("%Y%m%d"),
                  "DTEND;VALUE=DATE:%s" % (day + dt.timedelta(days=1)).strftime("%Y%m%d"),
                  fold("SUMMARY:%s到期" % escape(name)),
                  "BEGIN:VALARM", "ACTION:DISPLAY", fold("DESCRIPTION:%s" % escape(name)),
                  "TRIGGER:%s" % trig, "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")

    for p in problems:
        print("跳过 " + p)
    if not events:
        print("没有可写入的事项。")
        return 3
    try:
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".ics", dir=str(out.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write("\r\n".join(lines) + "\r\n")
            os.replace(tmp, str(out))
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
    except OSError as e:
        print("写不进去：%s（%s）" % (out, e.strerror or e), file=sys.stderr)
        return 2
    first = sorted(events)[0]
    print("已写入 %d 条提醒，跳过 %d 行：%s" % (len(events), len(problems), out.resolve()))
    print("提醒时间：到期前 %d 天 %02d:%02d（TRIGGER:%s）。导入后抽一条核对，例如「%s」应在 %s %02d:%02d 弹出。"
          % (a.days_before, hh, mm, trig, first[1], (first[0] - dt.timedelta(days=a.days_before)).isoformat(), hh, mm))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。.ics 没有写入，重跑即可。", file=sys.stderr)
        sys.exit(130)
