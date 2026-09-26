#!/usr/bin/env python3
"""群聊活跃度统计：读取用户自己复制粘贴保存的聊天记录纯文本，按发言人统计条数、时段分布、沉默成员比例。

只在本机处理文本，不联网，不连接、不操作任何聊天软件。纯 Python 标准库，Python 3.8+。

能自动识别的行格式（每条消息的「头」，内容可以在同一行或下面几行）：
  2026-09-01 10:23:45 张三：内容           时间在前、冒号后是内容
  [2026/9/1 10:23] 张三: 内容               同上，带方括号
  张三 2026/9/1 10:23                        名字在前、时间在后，内容在下一行
  张三 10:23                                 只有时刻；日期取前面最近的日期行（如「2026年9月1日」）
  张三：内容                                 完全没有时间（只统计条数）
入群、撤回、拍一拍等系统提示不算发言，入群次数单独统计。识别不了的格式可用 --pattern 自定义正则
（命名分组 name 必填，date、time、text 可选）。

用法：
  python3 chat_stats.py chat.txt --member-count 180
  python3 chat_stats.py chat.txt --members members.txt --list-silent --format md --out report.md
  python3 chat_stats.py chat.txt --anonymize          # 发言人显示为 成员01、成员02……，便于分享报告

退出码：0 完成；1 参数错误；2 文件读写失败；3 没有识别到任何消息（格式不认识）；130 中断。
"""

import argparse
import datetime
import json
import math
import os
import re
import sys
import tempfile

DATE = r"(?:\d{4}[-/年.])?\d{1,2}[-/月.]\d{1,2}日?"
TIME = r"\d{1,2}:\d{2}(?::\d{2})?"
NAME = r"[^\s:：\[\]【】][^:：\[\]【】]{0,29}?"
HEADER_PATTERNS = (
    ("时间在前", re.compile(r"^[\[【]?(?P<date>%s)?\s*(?P<time>%s)[\]】]?\s*(?P<name>%s)\s*[:：]\s*(?P<text>.*)$"
                         % (DATE, TIME, NAME))),
    ("名字在前", re.compile(r"^(?P<name>%s)\s+(?P<date>%s)?\s*(?P<time>%s)\s*$" % (NAME, DATE, TIME))),
)
NO_TIME_PATTERN = re.compile(r"^(?P<name>[^\s:：][^:：]{0,19}?)\s*[:：]\s*(?P<text>.+)$")
DATE_LINE = re.compile(r"^[\s\-—=─·]*(?P<date>%s)\s*(?:星期.|周.)?[\s\-—=─·]*$" % DATE)
JOIN_RE = re.compile(r"(邀请.*加入了群聊|加入了群聊|通过扫描.*二维码加入群聊|通过.*邀请.*加入)")
SYSTEM_RE = re.compile(r"(撤回了一条消息|移出了群聊|被移出群聊|修改群名为|以下为新消息|以上为历史消息|拍了拍|"
                       r"领取了.*红包|与群里其他人都不是.*朋友关系|已成为新群主|开启了.*群聊邀请确认)")
WEEKDAYS = "一二三四五六日"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用 -h 查看用法。\n" % message)
        sys.exit(1)


class FileError(Exception):
    pass


def read_text(path):
    last = None
    for enc in ("utf-8-sig", "gb18030"):
        try:
            with open(path, encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError as exc:
            last = exc
        except FileNotFoundError:
            raise FileError("找不到文件：%s" % path)
        except IsADirectoryError:
            raise FileError("这是目录，不是文件：%s" % path)
        except PermissionError:
            raise FileError("没有权限读取：%s" % path)
        except OSError as exc:
            raise FileError("读取失败：%s（%s）" % (path, exc))
    raise FileError("%s 的编码无法识别（%s），请另存为 UTF-8 文本" % (path, last))


def parse_date(text, year):
    """'2026-09-01' / '2026年9月1日' / '9月1日' -> date 或 None（缺年份且没给 --year 时）。"""
    if not text:
        return None
    nums = [int(x) for x in re.findall(r"\d+", text)]
    if len(nums) == 3:
        y, m, d = nums
    elif len(nums) == 2 and year:
        y, (m, d) = year, nums
    else:
        return None
    try:
        return datetime.date(y, m, d)
    except ValueError:
        return None


def clean_name(name):
    return name.strip().strip("\"'“”「」").strip()


def parse_chat(text, year, custom):
    """返回 (messages, joins, unparsed_samples, mode)。message = (name, date|None, hour|None)。"""
    lines = text.splitlines()
    patterns = [("自定义", custom)] if custom else list(HEADER_PATTERNS)
    has_time = custom is not None or any(p.match(l.strip()) for l in lines for _, p in HEADER_PATTERNS)
    if not has_time:
        patterns = [("无时间", NO_TIME_PATTERN)]
    messages, joins, unparsed = [], 0, []
    hits = {}
    current_date = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if JOIN_RE.search(line):
            joins += 1
            continue
        if SYSTEM_RE.search(line):
            continue
        m = DATE_LINE.match(line)
        if m and not custom:
            d = parse_date(m.group("date"), year)
            if d or not year:
                current_date = d
            continue
        hit = None
        for label, pat in patterns:
            hit = pat.match(line)
            if hit:
                hits[label] = hits.get(label, 0) + 1
                break
        if hit:
            g = hit.groupdict()
            name = clean_name(g.get("name") or "")
            if not name:
                continue
            d = parse_date(g.get("date"), year) if g.get("date") else current_date
            if g.get("date") and d:
                current_date = d
            hour = None
            if g.get("time"):
                hour = int(g["time"].split(":")[0])
                if hour > 23:
                    hour = None
            messages.append((name, d, hour))
            continue
        if not messages and len(unparsed) < 50:
            unparsed.append(line)       # 第一条消息之前识别不了的行；之后的算上一条消息的续行
    mode = max(hits, key=lambda k: (hits[k], k)) if hits else patterns[0][0]
    return messages, joins, unparsed, mode


def load_members(path):
    names = []
    for line in read_text(path).splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            names.append(clean_name(s))
    if not names:
        raise FileError("%s 里没有成员名（每行一个昵称）" % path)
    return sorted(set(names))


def build_report(messages, joins, args, members):
    counts = {}
    for name, _, _ in messages:
        counts[name] = counts.get(name, 0) + 1
    ranking = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    alias = {}
    if args.anonymize:
        width = max(2, len(str(len(ranking))))
        alias = {name: "成员%0*d" % (width, i) for i, (name, _) in enumerate(ranking, 1)}
    show = lambda n: alias.get(n, n)
    total = len(messages)
    speakers = len(ranking)
    top_k = max(1, int(math.ceil(speakers * 0.1)))
    top_share = sum(c for _, c in ranking[:top_k]) / float(total) if total else 0.0
    hours = [0] * 24
    has_hour = False
    weekdays = [0] * 7
    has_date = False
    dates = set()
    for _, d, h in messages:
        if h is not None:
            hours[h] += 1
            has_hour = True
        if d is not None:
            weekdays[d.weekday()] += 1
            dates.add(d)
            has_date = True
    peak = sorted(range(24), key=lambda h: (-hours[h], h))[:3] if has_hour else []
    report = {
        "total_messages": total,
        "speakers": speakers,
        "joins": joins,
        "date_range": [min(dates).isoformat(), max(dates).isoformat()] if dates else None,
        "active_days": len(dates),
        "top": [{"name": show(n), "count": c, "share": round(c / float(total), 4)} for n, c in ranking[:args.top]],
        "top10pct": {"speakers": top_k, "share": round(top_share, 4)},
        "active_min": args.active_min,
        "active_speakers": sum(1 for _, c in ranking if c >= args.active_min),
        "light_speakers": sum(1 for _, c in ranking if c <= 2),
        "hours": hours if has_hour else None,
        "peak_hours": peak,
        "weekdays": weekdays if has_date else None,
        "members": None,
        "notes": [],
    }
    if members is not None:
        member_set = set(members)
        silent = sorted(member_set - set(counts))
        outsiders = sorted(set(counts) - member_set)
        report["members"] = {"total": len(member_set), "silent": len(silent),
                             "silent_ratio": round(len(silent) / float(len(member_set)), 4),
                             "silent_names": [] if args.anonymize or not args.list_silent else silent,
                             "speakers_not_in_list": len(outsiders)}
        if outsiders:
            report["notes"].append("有 %d 个发言人不在成员名单里：多半是群昵称和名单写法不一致或中途改过名，"
                                   "沉默人数会因此偏多，核对名单后重跑" % len(outsiders))
    elif args.member_count:
        silent = args.member_count - speakers
        if silent < 0:
            report["notes"].append("发言人数（%d）超过了群成员数（%d）：可能有人改过昵称被算成两个人，"
                                   "或成员数填错了" % (speakers, args.member_count))
            silent = 0
        report["members"] = {"total": args.member_count, "silent": silent,
                             "silent_ratio": round(silent / float(args.member_count), 4),
                             "silent_names": [], "speakers_not_in_list": 0}
    else:
        report["notes"].append("没给 --member-count 或 --members，无法计算沉默成员比例")
    if not has_date and has_hour:
        report["notes"].append("记录里没有完整日期（缺年份时用 --year 指定），未统计星期分布")
    return report


def bar(n, peak, width=24):
    if peak <= 0 or n <= 0:
        return ""
    return "█" * max(1, int(round(n * width / float(peak))))


def render(report, fmt, mode, unparsed_count):
    if fmt == "json":
        out = dict(report)
        out["format_detected"] = mode
        return json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    md = fmt == "md"
    L = []
    h = (lambda t: "## " + t) if md else (lambda t: "【%s】" % t)
    L.append("# 群聊活跃度统计" if md else "群聊活跃度统计")
    L.append("")
    L.append(h("概况"))
    rng = report["date_range"]
    L.append("- 识别格式：%s；消息 %d 条；发言人 %d 位；时间范围 %s；有消息的天数 %d；入群提示 %d 次"
             % (mode, report["total_messages"], report["speakers"],
                "%s 至 %s" % tuple(rng) if rng else "未知", report["active_days"], report["joins"]))
    mem = report["members"]
    if mem:
        L.append("- 群成员 %d 人；统计期内发过言 %d 人（发言率 %.0f%%）；沉默 %d 人（沉默比例 %.0f%%）"
                 % (mem["total"], mem["total"] - mem["silent"], 100.0 * (mem["total"] - mem["silent"]) / mem["total"],
                    mem["silent"], 100.0 * mem["silent_ratio"]))
    L.append("- 发言 ≥ %d 条的 %d 人；只发过 1–2 条的 %d 人"
             % (report["active_min"], report["active_speakers"], report["light_speakers"]))
    L.append("- 前 10%%（%d 人）发言人贡献了 %.0f%% 的消息"
             % (report["top10pct"]["speakers"], 100.0 * report["top10pct"]["share"]))
    L.append("")
    L.append(h("发言排行"))
    if md:
        L.append("| 名次 | 发言人 | 条数 | 占比 |")
        L.append("|---|---|---|---|")
    for i, t in enumerate(report["top"], 1):
        if md:
            L.append("| %d | %s | %d | %.1f%% |" % (i, t["name"], t["count"], 100 * t["share"]))
        else:
            L.append("  %2d. %s  %d 条（%.1f%%）" % (i, t["name"], t["count"], 100 * t["share"]))
    if report["hours"]:
        L.append("")
        L.append(h("时段分布（按小时）"))
        peak = max(report["hours"])
        if md:
            L.append("```")
        for hr, n in enumerate(report["hours"]):
            if n:
                L.append("  %02d 点 %4d  %s" % (hr, n, bar(n, peak)))
        if md:
            L.append("```")
        L.append("- 高峰：%s" % "、".join("%02d 点" % x for x in report["peak_hours"]))
    if report["weekdays"]:
        L.append("")
        L.append(h("星期分布"))
        L.append("- " + "｜".join("周%s %d" % (WEEKDAYS[i], n) for i, n in enumerate(report["weekdays"])))
    if mem and mem["silent_names"]:
        L.append("")
        L.append(h("沉默成员名单（仅供群主核对，不要公开点名）"))
        L.append("- " + "、".join(mem["silent_names"]))
    notes = list(report["notes"])
    if unparsed_count:
        notes.append("有 %d 行在第一条消息之前或格式不认识，已跳过（用 --show-unparsed 查看）" % unparsed_count)
    if notes:
        L.append("")
        L.append(h("说明"))
        for n in notes:
            L.append("- " + n)
    L.append("")
    L.append("读数提示：高峰时段适合发公告和活动；沉默比例要和上月比趋势，公共事务群（班级、业主）以看通知为主，沉默高属正常。")
    return "\n".join(L) + "\n"


def write_atomic(path, content):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise FileError("输出目录不存在：%s" % directory)
    fd, tmp = tempfile.mkstemp(prefix=".chatstats-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise FileError("写入失败：%s（%s）" % (path, exc))


def build_parser():
    p = Parser(description="群聊活跃度统计（本地处理用户自己粘贴保存的聊天记录文本）。",
               epilog="退出码：0 完成；1 参数错误；2 文件读写失败；3 没有识别到任何消息；130 中断。")
    p.add_argument("chat", help="聊天记录文本文件（UTF-8 或 GBK）")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--member-count", type=int, help="群成员总数（用于算沉默比例）")
    g.add_argument("--members", help="成员名单文件，每行一个群昵称（用于算沉默比例、列沉默名单）")
    p.add_argument("--list-silent", action="store_true", help="列出沉默成员名单（需配合 --members；--anonymize 时不列）")
    p.add_argument("--top", type=int, default=10, help="发言排行显示前几名（默认 10）")
    p.add_argument("--active-min", type=int, default=5, help="统计期内发言达到几条算活跃（默认 5）")
    p.add_argument("--year", type=int, help="记录里的日期缺年份时，用这个年份（影响星期分布）")
    p.add_argument("--pattern", help="自定义消息头正则，命名分组 name 必填，date/time/text 可选")
    p.add_argument("--anonymize", action="store_true", help="发言人显示为 成员01、成员02……")
    p.add_argument("--format", choices=("text", "md", "json"), default="text", help="输出格式（默认 text）")
    p.add_argument("--out", help="写入文件（先写临时文件再替换）")
    p.add_argument("--show-unparsed", type=int, default=0, help="打印前 N 行没识别的内容，便于调整格式")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.member_count is not None and args.member_count <= 0:
        sys.stderr.write("参数错误：--member-count 必须大于 0\n")
        return 1
    if args.top <= 0 or args.active_min <= 0:
        sys.stderr.write("参数错误：--top 和 --active-min 必须大于 0\n")
        return 1
    if args.list_silent and not args.members:
        sys.stderr.write("参数错误：--list-silent 需要同时给 --members 成员名单\n")
        return 1
    custom = None
    if args.pattern:
        try:
            custom = re.compile(args.pattern)
        except re.error as exc:
            sys.stderr.write("参数错误：--pattern 不是合法正则（%s）\n" % exc)
            return 1
        if "name" not in custom.groupindex:
            sys.stderr.write("参数错误：--pattern 必须包含命名分组 (?P<name>...)\n")
            return 1
    try:
        text = read_text(args.chat)
        members = load_members(args.members) if args.members else None
    except FileError as exc:
        sys.stderr.write("文件错误：%s\n" % exc)
        return 2
    messages, joins, unparsed, mode = parse_chat(text, args.year, custom)
    if args.show_unparsed:
        for line in unparsed[:args.show_unparsed]:
            sys.stderr.write("未识别：%s\n" % line)
    if not messages:
        sys.stderr.write("没有识别到任何消息。支持的格式见 -h；也可以用 --pattern 自定义，"
                         "或先用 --show-unparsed 5 看看前几行长什么样。\n")
        return 3
    report = build_report(messages, joins, args, members)
    content = render(report, args.format, mode, len(unparsed))
    if args.out:
        try:
            write_atomic(args.out, content)
        except FileError as exc:
            sys.stderr.write("文件错误：%s\n" % exc)
            return 2
        print("已写入 %s：消息 %d 条，发言人 %d 位" % (args.out, report["total_messages"], report["speakers"]))
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(130)
