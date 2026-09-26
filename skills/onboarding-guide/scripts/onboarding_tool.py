#!/usr/bin/env python3
"""入职指南小工具：按到岗日推算各反馈节点的日期；发给新人前检查还有哪些没填、有没有误写凭据。

用法：
  python3 onboarding_tool.py dates 2026-11-02                          # 默认节点：到岗前准备、第 1 天、第 1/2 周、第 30 天
  python3 onboarding_tool.py dates 2026-11-02 --checkpoints 30,60,90   # 试用期较长的加上第 60、90 天
  python3 onboarding_tool.py dates 2026-11-02 --holidays 2026-12-31 --workdays 2026-12-26
  python3 onboarding_tool.py check 入职指南.md                          # 列出剩余的【】/[待补]/[待确认]、链接和疑似凭据

日期规则（写死在脚本里，同样的输入每次输出一致）：
  到岗当天算第 1 天，第 N 天 = 到岗日 + (N - 1) 天；落在周末或 --holidays 里的日期往后顺延到下一个工作日；
  第 1 周复盘 = 到岗后的第一个周五（到岗当天就是周五则取下周五），第 2 周面谈 = 再过一周的周五，同样遇假顺延；
  到岗前准备 = 到岗日前 7 天、欢迎消息 = 到岗前一个工作日，遇假往前挪。
  --workdays 用来标出调休上班的周末。节假日脚本不内置，按公司或官方公布的日历自己传入。
退出码：0 成功（check：没有剩余占位符和疑似凭据）；1 参数错误；2 文件读不了；
        3 check 发现还有待填项或疑似凭据；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

WEEK = "一二三四五六日"
DATE_RE = re.compile(r"^\s*(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?\s*$")
PLACEHOLDER = re.compile(r"【[^】]*】|\[待补[^\]]*\]|\[待确认[^\]]*\]")
URL = re.compile(r"https?://[^\s)）」>\]，。；、]+")
SECRET = re.compile(r"(密码|口令|密钥|password|passwd|pwd|token|secret)\s*[:：=]\s*"
                    r"(?!【|\[|由|找|见|向|请|走|通过|联系|到|在)\S", re.I)


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def parse_date(text):
    m = DATE_RE.match(text or "")
    if not m:
        raise ValueError(text)
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_dates(raw, ap, flag):
    out = set()
    for part in re.split(r"[,，\s]+", raw or ""):
        if not part:
            continue
        p = Path(part).expanduser()
        items = p.read_text(encoding="utf-8").split() if p.is_file() else [part]
        for item in items:
            try:
                out.add(parse_date(item))
            except ValueError:
                ap.error("%s 里的「%s」不是日期，请写成 2026-10-01" % (flag, item))
    return out


def dates(a, ap):
    try:
        start = parse_date(a.start)
    except ValueError:
        ap.error("到岗日「%s」认不出，请写成 2026-11-02" % a.start)
    try:
        holidays = parse_dates(a.holidays, ap, "--holidays")
        workdays = parse_dates(a.workdays, ap, "--workdays")
    except (OSError, UnicodeDecodeError) as e:
        print("读不了日期文件：%s" % e, file=sys.stderr)
        return 2
    try:
        cps = sorted({int(x) for x in re.split(r"[,，\s]+", a.checkpoints) if x})
    except ValueError:
        ap.error("--checkpoints 要写成 30,60,90 这样的天数")
    if not cps or any(not 2 <= c <= 400 for c in cps):
        ap.error("--checkpoints 的天数要在 2 到 400 之间")

    def is_work(d):
        return d in workdays or (d.weekday() < 5 and d not in holidays)

    def forward(d):
        while not is_work(d):
            d += dt.timedelta(days=1)
        return d

    def backward(d):
        while not is_work(d):
            d -= dt.timedelta(days=1)
        return d

    if not is_work(start):
        print("注意：到岗日 %s 是周%s或假日，确认一下有没有写错。" % (start, WEEK[start.weekday()]), file=sys.stderr)
    first_fri = start + dt.timedelta(days=(4 - start.weekday()) % 7 or 7)
    rows = [
        ("到岗前一周", start - dt.timedelta(days=7), backward,
         "主管/导师", "确定导师；发起「第 1 天就要」的账号与设备申请；准备第一个小任务；把面谈放进双方日历"),
        ("到岗前一个工作日", start - dt.timedelta(days=1), backward,
         "导师", "发欢迎消息：几点到、到哪里、找谁、带什么、第一天怎么过"),
        ("第 1 天", start, None, "导师", "下班前 15 分钟：确认账号能用，记下还没开通的权限"),
        ("第 1 周复盘", first_fri, forward, "导师", "30 分钟：顺的、卡的、下周计划"),
        ("第 2 周面谈", first_fri + dt.timedelta(days=7), forward, "导师", "30 分钟面谈，对照第 2 周任务"),
    ]
    for c in cps:
        who, what = ("主管", "正式面谈，对照「第 30 天」目标") if c == 30 else ("主管", "面谈，对照第 %d 天的期望" % c)
        rows.append(("第 %d 天" % c, start + dt.timedelta(days=c - 1), forward, who, what))

    print("| 节点 | 日期 | 星期 | 负责人 | 做什么 |")
    print("|---|---|---|---|---|")
    for name, raw, adjust, who, what in rows:
        day = adjust(raw) if adjust else raw
        note = ""
        if day != raw:
            note = "（原定 %s，遇周末或假日%s）" % (raw, "顺延" if day > raw else "提前")
        print("| %s | %s%s | 周%s | %s | %s |" % (name, day, note, WEEK[day.weekday()], who, what))
    print("\n规则：到岗当天算第 1 天；节假日只按 --holidays 传入的计算%s。"
          % ("" if holidays else "（这次没有传入，节假日请自行核对）"))
    return 0


def check(a):
    path = Path(a.file).expanduser()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print("找不到文件：%s（检查路径；路径里有空格时用引号包起来）" % path, file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("%s 不是 UTF-8 文本；请另存为 UTF-8 的 .md 或 .txt 再检查。" % path, file=sys.stderr)
        return 2
    except OSError as e:
        print("读取失败：%s（%s）" % (path, e.strerror or e), file=sys.stderr)
        return 2
    holes, links, secrets = {}, [], []
    for n, line in enumerate(lines, 1):
        for m in PLACEHOLDER.findall(line):
            holes.setdefault(m, []).append(n)
        links += [(n, u) for u in URL.findall(line)]
        if SECRET.search(line):
            secrets.append((n, line.strip()[:40]))
    total = sum(len(v) for v in holes.values())
    print("待填：%d 处（%d 种）" % (total, len(holes)))
    for text, where in sorted(holes.items(), key=lambda kv: kv[1][0]):
        print("  第 %s 行  %s" % ("、".join(map(str, where[:6])) + ("…" if len(where) > 6 else ""), text))
    print("链接：%d 个，发出前逐个点开确认没失效（本工具不联网检查）" % len(links))
    for n, u in links:
        print("  第 %d 行  %s" % (n, u))
    if secrets:
        print("疑似写了凭据：%d 处——初始密码、密钥不要写进指南，改走公司规定的安全渠道" % len(secrets))
        for n, s in secrets:
            print("  第 %d 行  %s" % (n, s))
    todo = [t for t, bad in (("补齐待填项（补不了的移进「待你补充」清单）", holes), ("删掉凭据", secrets)) if bad]
    print("结论：%s" % ("先" + "、".join(todo) + "，再发" if todo else "可以发给新人"))
    return 3 if todo else 0


def main(argv=None):
    ap = ArgParser(description="入职指南小工具：推算节点日期 / 发前检查")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("dates", help="按到岗日推算反馈节点日期")
    d.add_argument("start", help="到岗日，如 2026-11-02")
    d.add_argument("--checkpoints", default="30", help="第 N 天面谈，逗号分隔（默认 30；试用期长的写 30,60,90）")
    d.add_argument("--holidays", help="放假日期，逗号分隔，或一个每行一个日期的文本文件")
    d.add_argument("--workdays", help="调休上班的周末日期，逗号分隔，或文本文件")
    c = sub.add_parser("check", help="发给新人前检查待填项、链接、疑似凭据")
    c.add_argument("file", help="入职指南文件（UTF-8 的 .md 或 .txt）")
    a = ap.parse_args(argv)
    if a.cmd == "dates":
        return dates(a, ap)
    if a.cmd == "check":
        return check(a)
    ap.error("请选择子命令：dates 或 check，例如 python3 onboarding_tool.py dates 2026-11-02")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。本工具不写任何文件，直接重跑即可。", file=sys.stderr)
        sys.exit(130)
