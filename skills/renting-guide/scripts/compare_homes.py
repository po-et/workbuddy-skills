#!/usr/bin/env python3
"""几套房放在一起算账：入住先付多少、每月实付多少、每月通勤多少小时，并按预算、收入、通勤上限标出超了的。
只读，不改文件，只用 Python 标准库（3.6+）。不查房源、不联网、不评价房子好坏。

用法：
  python3 compare_homes.py homes.csv
  python3 compare_homes.py homes.csv --budget 3000 --income 9000 --max-commute 45
  python3 compare_homes.py --home "A 地铁口一居,4200,1,3,4200,350,25" --home "B 合租主卧,2600,1,1,0,300,50"
CSV 表头（顺序不限）：名称,月租,押几,付几,中介费,每月杂费,单程通勤分钟
算法：入住先付 = 月租 ×（押几 + 付几）+ 中介费
      每月实付 = 月租 + 每月杂费 + 中介费 ÷ 摊销月数（默认按一年租期摊，--agent-months 可改）
      每月通勤 = 单程分钟 × 2 × 工作日数 ÷ 60（默认每月 22 个工作日，--workdays 可改）

退出码：0 正常；1 参数或数据不合法（负数、缺列、不是数字，会指出第几行哪一列）；2 文件读不了；130 手动中断。
"""

import argparse
import csv
import io
import sys

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_INTERRUPT = 0, 1, 2, 130
FIELDS = ("名称", "月租", "押几", "付几", "中介费", "每月杂费", "单程通勤分钟")
ALIASES = {
    "名称": ("名称", "房源", "房子"),
    "月租": ("月租", "租金", "月租金"),
    "押几": ("押几", "押金月数", "押"),
    "付几": ("付几", "付款月数", "付"),
    "中介费": ("中介费", "服务费"),
    "每月杂费": ("每月杂费", "杂费", "水电杂费"),
    "单程通勤分钟": ("单程通勤分钟", "通勤分钟", "单程通勤", "通勤"),
}


def zh(message):
    for en, cn in (("the following arguments are required: ", "缺少必填参数："),
                   ("unrecognized arguments: ", "不认识的参数："),
                   ("invalid float value: ", "不是数字："),
                   ("invalid int value: ", "不是整数："),
                   ("expected one argument", "后面要跟一个值")):
        message = message.replace(en, cn)
    return message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % zh(message))
        sys.exit(EXIT_ARGS)


class BadInput(ValueError):
    pass


def number(text, where, field):
    s = (text or "").strip().replace(",", "").replace("，", "").replace("元", "").replace("分钟", "")
    if s == "":
        raise BadInput("%s「%s」是空的：没有就填 0" % (where, field))
    try:
        v = float(s)
    except ValueError:
        raise BadInput("%s「%s」写的是「%s」，不是数字" % (where, field, text))
    if v < 0:
        raise BadInput("%s「%s」是负数（%s）：金额、月数、分钟都不能为负，是不是多打了负号？" % (where, field, text))
    return v


def build(values, where):
    name = (values.get("名称") or "").strip()
    if not name:
        raise BadInput("%s没写名称：随便起个好记的名字，如「A 地铁口一居」" % where)
    h = {"名称": name}
    for f in FIELDS[1:]:
        h[f] = number(values.get(f), where, f)
    if h["月租"] == 0:
        raise BadInput("%s「月租」是 0：填每月房租金额" % where)
    for f in ("押几", "付几"):
        if h[f] != int(h[f]):
            raise BadInput("%s「%s」应是整数月数，你写的是 %g" % (where, f, h[f]))
        if h[f] > 12:
            raise BadInput("%s「%s」是 %g：这一列填月数（如押一付三，押几填 1、付几填 3），像是把金额填进来了"
                           % (where, f, h[f]))
    if h["付几"] == 0:
        raise BadInput("%s「付几」是 0：每次至少付一个月，月付填 1" % where)
    return h


def from_csv(text):
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        raise BadInput("文件是空的：第一行写表头 %s，下面每行一套房" % ",".join(FIELDS))
    header = [c.strip() for c in rows[0]]
    idx = {}
    for key, names in ALIASES.items():
        for i, h in enumerate(header):
            if h in names:
                idx[key] = i
                break
    missing = [f for f in FIELDS if f not in idx]
    if missing:
        raise BadInput("表头缺少：%s。当前表头：%s。可直接复制这行当表头：%s"
                       % ("、".join(missing), ",".join(header), ",".join(FIELDS)))
    homes = []
    for n, r in enumerate(rows[1:], start=2):
        vals = dict((k, r[i] if i < len(r) else "") for k, i in idx.items())
        homes.append(build(vals, "第 %d 行" % n))
    return homes


def from_arg(text, k):
    parts = [p.strip() for p in text.replace("，", ",").split(",")]
    if len(parts) != len(FIELDS):
        raise BadInput("第 %d 个 --home 有 %d 项，应有 %d 项，按顺序：%s"
                       % (k, len(parts), len(FIELDS), ",".join(FIELDS)))
    return build(dict(zip(FIELDS, parts)), "第 %d 个 --home " % k)


def read_text(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise IOError("找不到文件：%s（检查路径，或先把表格另存为 CSV）" % path)
    except IsADirectoryError:
        raise IOError("%s 是文件夹，不是 CSV 文件" % path)
    except PermissionError:
        raise IOError("没有权限读取：%s" % path)
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise IOError("无法识别 %s 的编码：在表格软件里另存为「CSV UTF-8」再试" % path)


def main(argv=None):
    ap = Parser(description="几套房一起算账（只读）。退出码：0 正常，1 参数或数据不合法，2 文件读不了，130 中断")
    ap.add_argument("csv_file", nargs="?", help="房源 CSV；也可以不给文件、改用 --home")
    ap.add_argument("--home", action="append", default=[], help="一套房一行：名称,月租,押几,付几,中介费,每月杂费,单程通勤分钟")
    ap.add_argument("--budget", type=float, help="月租上限（元）")
    ap.add_argument("--income", type=float, help="每月到手收入（元）；月租超过三分之一会提示")
    ap.add_argument("--max-commute", type=float, help="单程通勤上限（分钟）")
    ap.add_argument("--workdays", type=float, default=22, help="每月通勤天数，默认 22")
    ap.add_argument("--agent-months", type=float, default=12, help="中介费按几个月摊，默认 12（一年租期）")
    args = ap.parse_args(argv)

    try:
        for name, v in (("预算", args.budget), ("收入", args.income), ("通勤上限", args.max_commute)):
            if v is not None and v <= 0:
                raise BadInput("%s应是正数，你写的是 %g" % (name, v))
        if not 0 < args.workdays <= 31:
            raise BadInput("每月通勤天数应在 1 到 31 之间，你写的是 %g" % args.workdays)
        if args.agent_months <= 0:
            raise BadInput("中介费摊销月数应大于 0")
        if not args.csv_file and not args.home:
            raise BadInput("没有房源：给一个 CSV 文件，或至少一个 --home")
        homes = []
        if args.csv_file:
            homes.extend(from_csv(read_text(args.csv_file)))
        for k, h in enumerate(args.home, start=1):
            homes.append(from_arg(h, k))
    except BadInput as exc:
        sys.stderr.write("输入不合法：%s\n" % exc)
        return EXIT_ARGS
    except IOError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE
    except csv.Error as exc:
        sys.stderr.write("CSV 格式有误：%s（检查是否有未闭合的引号）\n" % exc)
        return EXIT_FILE

    results = []
    for h in homes:
        rent = h["月租"]
        first = rent * (h["押几"] + h["付几"]) + h["中介费"]
        monthly = rent + h["每月杂费"] + h["中介费"] / args.agent_months
        hours = h["单程通勤分钟"] * 2 * args.workdays / 60.0
        flags = []
        if args.budget and rent > args.budget:
            flags.append("月租超预算 %d 元" % round(rent - args.budget))
        if args.income and rent > args.income / 3.0:
            flags.append("月租超过到手收入的三分之一")
        if args.max_commute and h["单程通勤分钟"] > args.max_commute:
            flags.append("单程通勤超上限 %d 分钟" % round(h["单程通勤分钟"] - args.max_commute))
        if h["单程通勤分钟"] > 180:
            flags.append("单程超过 3 小时，确认填的是单程分钟")
        results.append((h, first, monthly, hours, flags))
        line = "%s：入住先付 %d 元，每月约 %d 元，每月通勤 %.0f 小时" % (h["名称"], round(first), round(monthly), hours)
        if flags:
            line += "（%s）" % "；".join(flags)
        print(line)

    if len(results) >= 2:
        base = results[0]
        for h, first, monthly, hours, _ in results[1:]:
            d_money = base[2] - monthly
            d_hours = hours - base[3]
            text = "与「%s」相比，「%s」每月%s %d 元，通勤%s %.0f 小时" % (
                base[0]["名称"], h["名称"], "省" if d_money >= 0 else "多花", abs(round(d_money)),
                "多" if d_hours >= 0 else "少", abs(d_hours))
            if d_money > 0 and d_hours > 0:
                text += "，相当于每多通勤 1 小时省 %d 元" % round(d_money / d_hours)
            elif d_money < 0 and d_hours < 0:
                text += "，相当于每少通勤 1 小时多花 %d 元" % round(d_money / d_hours)
            print(text)
    print("每月省下的房租和多出来的通勤时间怎么换，值不值由你定；这张表只把账摆出来。")
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
