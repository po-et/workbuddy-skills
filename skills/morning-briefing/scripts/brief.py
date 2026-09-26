#!/usr/bin/env python3
"""晨间简报骨架：把待办按「影响大 > 有人在等 > 截止早」排序，查日程时间重叠，
输出固定段落的 Markdown 骨架；消息要点和天气由助手再并进去。纯标准库，不联网。

用法：
  python3 scripts/brief.py todo.txt 2026-09-24            # 第二个参数指定「今天」，避免隔夜或时区错位
  python3 scripts/brief.py todo.txt 2026-09-24 --week     # 周一版：多出「本周还要到期」
  python3 scripts/brief.py - 2026-09-24 < todo.txt         # 从标准输入读
  python3 scripts/brief.py --demo                          # 用内置样例跑一遍（样例同 SKILL.md）
  python3 scripts/brief.py todo.txt 2026-09-24 --out 简报.md   # 另存为文件

待办写法（一行一件）：截止:9-24（也认 2026-09-24、9/24、9月24日、今天、明天、后天），! 表示影响大，
@人名 表示这个人在等你，等:人名 表示你在等他；全角 ！ ： 也认；以 10:00 或 10:00-11:00 开头的行算日程。

退出码：
  0   简报骨架已生成
  3   简报已生成，但有看不懂的日期或时间（已列进「风险与冲突」并标 [待确认]），先跟用户核对
  1   参数不对，或待办为空
  2   待办文件读不了，或 --out 写不进去
  130 用户按 Ctrl+C 中断
"""
import argparse
import datetime as dt
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_CHECK, EXIT_INTERRUPT = 0, 1, 2, 3, 130
WEEKDAY = "一二三四五六日"
DEMO_TODO = """\
- 交季度预算表 截止:9-24 ! @张经理
- 报销单补签 截止:9-23
- 课表调整回复 截止:明天 @李老师
- 合同终稿 截止:9-25 ！ 等:小王
- 整理发票 截止:9-30
- 学 Python 第三章
- 10:00-11:00 项目周会
- 10:30-11:00 牙医复诊
- 15:00 客户电话
"""
DEMO_DATE = "2026-09-24"
NO_DEADLINE = 99


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「文件读不了」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class ReadProblem(Exception):
    """文件读不了 → 退出码 2。"""


def parse_today(text):
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text.strip())
    if not m:
        raise ValueError("「今天」的日期「%s」看不懂：写成 2026-09-24" % text)
    try:
        return dt.date(*(int(x) for x in m.groups()))
    except ValueError:
        raise ValueError("「今天」的日期「%s」不是真实存在的日期" % text)


def days_left(line, today, problems):
    """距截止几天；没写截止返回 99；看不懂的记进 problems 并返回 99。"""
    m = re.search(r"截止[:：](\S+)", line)
    if not m:
        return NO_DEADLINE
    word = m.group(1)
    if word in ("今天", "明天", "后天"):
        return ("今天", "明天", "后天").index(word)
    try:
        cn = re.fullmatch(r"(\d{1,2})月(\d{1,2})[日号]?", word)
        parts = [int(x) for x in (cn.groups() if cn else re.split("[-/]", word))]
        y, mo, d = ([today.year] + parts)[-3:]
        when = dt.date(y, mo, d)
        if len(parts) == 2 and (today - when).days > 180:  # 年底写「1-05」多半指明年
            when = dt.date(y + 1, mo, d)
            problems.append("「截止:%s」按 %d 年理解，不对请写全年份" % (word, when.year))
        return (when - today).days
    except (ValueError, TypeError):
        problems.append("截止日期「%s」看不懂（%s），暂按没有截止处理" % (word, line))
        return NO_DEADLINE


def build(text, today, week):
    todo, cal, rep, risk, conf, problems = [], [], [], [], [], []
    for raw in text.splitlines():
        s = raw.strip(" -*\t\r\n")
        t = re.match(r"(\d{1,2}:\d\d)(?:-(\d{1,2}:\d\d))?\s*(.*)", s)
        if t:
            start, end = t.group(1).zfill(5), (t.group(2) or t.group(1)).zfill(5)
            bad = sorted({x for x in (start, end) if int(x[:2]) > 23 or int(x[3:]) > 59})
            if bad:
                problems.append("时间「%s」不存在（%s），没排进日程" % ("、".join(bad), s))
                continue
            if end < start:
                problems.append("「%s」结束早于开始，按只占开始时刻处理" % s)
                end = start
            cal.append((start, end, t.group(3)))
            continue
        if not s:
            continue
        n = re.sub(r"\s*(截止[:：]|等[:：]|@)\S+|\s*[!！]", "", s)
        left = days_left(s, today, problems)
        imp = bool(re.search("[!！]", s))
        todo.append((not imp, "@" not in s, left, n))  # 排序键：影响大 > 有人在等 > 截止早
        rep += ["%s：%s" % (p, n) for p in re.findall(r"@(\S+)", s)]
        risk += ["在等%s：%s，上午先催" % (p, n) for p in re.findall(r"等[:：](\S+)", s) if left <= 2]
    must = sorted(x for x in todo if x[2] <= 0 or (not x[0] and x[2] == 1))
    cal.sort()
    last = None
    for c in cal:
        if last and c[0] < last[1]:
            conf.append("时间冲突：%s %s 与 %s %s" % (last[0], last[2], c[0], c[2]))
        if not last or c[1] > last[1]:
            last = c
    if len(must) > 5:
        risk.append("必须完成 %d 件，超过 5 件，先砍或改期" % len(must))
    risk += ["[待确认] " + p for p in problems]

    def tag(x):
        left = x[2]
        k = "逾期%d天" % -left if left < 0 else ["今天", "明天"][left] if left < 2 else "%d天后" % left
        return "[%s]" % k + "[!]" * (not x[0]) + " " + x[3]

    out = []

    def sec(title, rows):
        out.append("## %s\n" % title + ("\n".join(rows) or "（无）"))

    out.append("# 晨间简报 %s 周%s" % (today, WEEKDAY[today.weekday()]))
    sec("今天必须完成", ["%d. %s" % (i, tag(x)) for i, x in enumerate(must, 1)])
    sec("有时间点的安排", ["- %s%s %s" % (a, "-" + b if b != a else "", n) for a, b, n in cal])
    sec("需要回复的人", ["- " + r for r in rep])
    sec("风险与冲突", ["- " + r for r in conf + risk])
    if week:
        sec("本周还要到期", ["- " + tag(x) for x in sorted(todo, key=lambda x: x[2])
                          if x not in must and 0 < x[2] <= 7])
    sec("一句话提醒", ["先做「%s」。" % must[0][3] if must else "今天没有硬截止，先做最重要的那件。"])
    return "\n".join(out) + "\n", problems


def read_todo(path):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            raise ReadProblem("找不到文件：%s。确认路径，或直接把待办粘到对话里。" % path)
        except IsADirectoryError:
            raise ReadProblem("%s 是目录，请给待办文本文件。" % path)
        except PermissionError:
            raise ReadProblem("没有权限读取 %s。" % path)
        except OSError as e:
            raise ReadProblem("读取 %s 失败：%s" % (path, e))
    for enc in ("utf-8-sig", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ReadProblem("%s 的编码认不出来，请另存为 UTF-8。" % ("标准输入" if path == "-" else path))


def write_atomic(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".brief-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp, 0o666 & ~mask)  # mkstemp 默认 0600，改回普通文件权限
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = Parser(description="晨间简报骨架（待办排序 + 日程冲突）")
    ap.add_argument("todo", nargs="?", help="待办文件；- 表示从标准输入读")
    ap.add_argument("date", nargs="?", help="把哪天当作今天，如 2026-09-24（默认本机日期）")
    ap.add_argument("--week", action="store_true", help="周一版：多出「本周还要到期」")
    ap.add_argument("--demo", action="store_true", help="用内置样例跑一遍")
    ap.add_argument("--out", help="另存为文件（先写临时文件再替换，不会留下半截文件）")
    args = ap.parse_args(argv)

    if args.demo:
        if args.todo and not args.date and re.match(r"\d", args.todo):
            args.date, args.todo = args.todo, None  # 允许 --demo 2026-09-24
        text, when = DEMO_TODO, args.date or DEMO_DATE
    else:
        if not args.todo:
            ap.error("缺待办文件。用法：python3 scripts/brief.py todo.txt 2026-09-24；试跑用 --demo")
        try:
            text = read_todo(args.todo)
        except ReadProblem as e:
            sys.stderr.write("读取失败：%s\n" % e)
            return EXIT_IO
        when = args.date
    if not text.strip():
        sys.stderr.write("待办是空的：先把待办、日程一行一件写进去，或把材料直接贴到对话里。\n")
        return EXIT_INPUT
    try:
        today = parse_today(when) if when else dt.date.today()
    except ValueError as e:
        ap.error(str(e))

    brief, problems = build(text, today, args.week)
    for p in problems:
        sys.stderr.write("[待确认] %s\n" % p)
    if args.out:
        try:
            write_atomic(args.out, brief)
        except OSError as e:
            sys.stderr.write("写文件失败：%s（%s）。换个目录或文件名再试；简报如下：\n" % (args.out, e.strerror or e))
            sys.stdout.write(brief)
            return EXIT_IO
        print("已保存：%s" % os.path.abspath(args.out))
    sys.stdout.write(brief)
    return EXIT_CHECK if problems else EXIT_OK


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有写出任何文件。\n")
        sys.exit(EXIT_INTERRUPT)
