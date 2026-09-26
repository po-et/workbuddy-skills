#!/usr/bin/env python3
"""买车算账：落地价明细、每年养车钱、贷款真实成本，输出一张 Markdown 预算表。
没给的项目写 [待补]，政策口径拿不准的写 [待确认]，不替你编数字。纯标准库，不联网。

用法：
  python3 scripts/car_cost.py 150000 15000 7 8          # 兼容旧写法：发票价 年里程 百公里油耗 油价
  python3 scripts/car_cost.py --price 15万 --km 15000 --consumption 7 --unit-price 8
  python3 scripts/car_cost.py --price 15万 --ev --km 15000 --consumption 15 --home-price 0.6 --fast-price 1.5 --home-share 80%
  python3 scripts/car_cost.py --price 15万 --insurance 5000 --plate 500 --addons 0 \
      --km 15000 --consumption 7 --unit-price 8 --maintenance 1000 --parking 3600 --misc 1000 --out 预算表.md
  python3 scripts/car_cost.py --loan-principal 10万 --loan-total 11.2万 --loan-fees 3000

金额可以写 150000、150,000、15万、15w、1.5万元、¥150000；比例可以写 0.8 或 80%。

退出码：
  0   算完了，数值都在常识范围内
  3   算完了，但有数值看起来异常（例如发票价只有 15 元，多半漏了「万」），先跟用户确认再用
  1   参数不对：看不懂的数字、负数、总还款额小于本金、一个参数重复给了
  2   --out 指定的文件写不进去
  130 用户按 Ctrl+C 中断
"""
import argparse
import math
import os
import sys
import tempfile

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_CHECK, EXIT_INTERRUPT = 0, 1, 2, 3, 130
TAX_RATE = 0.10      # 燃油车购置税口径：不含增值税车价的 10%（以当年政策为准）
VAT_DIVISOR = 1.13   # 发票价 ÷ 1.13 ≈ 不含增值税车价


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「写文件失败」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class InputProblem(Exception):
    """用户给的数看不懂或自相矛盾 → 退出码 1。"""


def parse_amount(text, what):
    """'15万' → 150000.0；'1.5w' → 15000.0；'150,000元' → 150000.0。"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("，", "").replace(" ", "")
    s = s.lstrip("¥￥").rstrip("元块")
    mult = 1
    if s[-1:] in ("万", "w", "W"):
        mult, s = 10000, s[:-1]
    elif s[-1:] in ("千", "k", "K"):
        mult, s = 1000, s[:-1]
    try:
        value = float(s) * mult
    except ValueError:
        raise InputProblem("%s「%s」看不懂：请写成阿拉伯数字，如 150000、15万、1.5w" % (what, text))
    if not math.isfinite(value):
        raise InputProblem("%s「%s」不是有效数字" % (what, text))
    if value < 0:
        raise InputProblem("%s不能是负数：%s" % (what, text))
    return value


def parse_share(text):
    if text is None:
        return None
    s = str(text).strip()
    try:
        v = float(s[:-1]) / 100 if s.endswith("%") else float(s)
    except ValueError:
        raise InputProblem("--home-share「%s」看不懂：写 0.8 或 80%%" % text)
    if not 0 <= v <= 1:
        raise InputProblem("--home-share 应在 0 到 1 之间（或 0%%–100%%），现在是 %s" % text)
    return v


def yuan(v):
    return "{:,.0f}".format(v)


def num(v):
    """7.0 → '7'，0.6 → '0.6'：算式里照用户写的样子显示。"""
    return ("%.4f" % v).rstrip("0").rstrip(".")


def total_cell(known, pending):
    if pending and not known:
        return "—（%d 项待补/待确认）" % pending
    return yuan(known) + (" 起（另有 %d 项待补/待确认）" % pending if pending else "")


def build(args):
    warnings, lines = [], []
    todo = "[待补]"
    price = parse_amount(args.price, "发票价")
    km = parse_amount(args.km, "年里程")
    cons = parse_amount(args.consumption, "百公里油耗/电耗")
    unit = parse_amount(args.unit_price, "油价/电价")
    home, fast = parse_amount(args.home_price, "家充电价"), parse_amount(args.fast_price, "快充电价")
    share = parse_share(args.home_share)
    extra = {k: parse_amount(getattr(args, k), label) for k, label in (
        ("insurance", "首年保险"), ("plate", "上牌等费用"), ("addons", "加装"),
        ("maintenance", "每年保养维修"), ("parking", "每年停车"), ("misc", "每年杂项"))}
    principal = parse_amount(args.loan_principal, "贷款本金")
    total_repay = parse_amount(args.loan_total, "总还款额")
    loan_fees = parse_amount(args.loan_fees, "另收的手续费、服务费")

    if price is None and km is None and principal is None and total_repay is None:
        raise InputProblem("至少给发票价（--price）、年里程（--km）或贷款两项中的一组，示例见 --help")

    # ---- 常识范围检查：只提醒，不擅自改数
    if price is not None and price < 10000:
        warnings.append("发票价只有 %s 元，是不是少写了「万」？已按 %s 元计算" % (yuan(price), yuan(price)))
    if cons is not None and (cons == 0 or cons > 50):
        warnings.append("百公里能耗 %s 看起来不对，确认单位是「升/百公里」或「度/百公里」" % num(cons))
    for label, v in (("油价/电价", unit), ("家充电价", home), ("快充电价", fast)):
        if v is not None and v > 50:
            warnings.append("%s %s 元看起来不对，确认单位是「元/升」或「元/度」，不是「分」" % (label, num(v)))
    if km is not None and km > 100000:
        warnings.append("年里程 %s 公里偏高，确认是一年的里程，不是总里程" % yuan(km))

    title = "# 预算表（按你给的数字计算；价格、税费、补贴以当地正式报价和现行政策为准）"
    lines.append(title)

    # ---- 落地价
    if price is not None:
        tax = price / VAT_DIVISOR * TAX_RATE
        rows = [("裸车价（发票价）", yuan(price), "你给的")]
        if args.ev:
            rows.append(("购置税", "[待确认：新能源减免额度与年份以当年政策为准]",
                         "不减免时按燃油车口径约 %s" % yuan(tax)))
        else:
            rows.append(("购置税", yuan(tax), "%s ÷ 1.13 × 10%%（燃油车口径，以当年政策为准）" % yuan(price)))
        for key, label, note in (("insurance", "首年保险", "交强险必须买；商业险拿两三家报价，比保额和免赔"),
                                 ("plate", "上牌等费用", "自己办还是代办、代办包含什么，写清楚"),
                                 ("addons", "加装", "只算你主动要的")):
            v = extra[key]
            rows.append((label, yuan(v) if v is not None else todo, "你给的" if v is not None else note))
        known = price + (0 if args.ev else tax) + sum(extra[k] or 0 for k in ("insurance", "plate", "addons"))
        pending = sum(1 for r in rows if r[1].startswith("["))
        total = total_cell(known, pending)
        lines += ["", "## 落地价", "| 项目 | 金额（元） | 算法 / 来源 |", "|---|---|---|"]
        lines += ["| %s | %s | %s |" % r for r in rows]
        lines.append("| **落地价合计** | %s | 裸车价 + 购置税 + 首年保险 + 上牌 + 加装 |" % total)

    # ---- 每年养车钱
    if km is not None or cons is not None or any(extra[k] is not None for k in ("maintenance", "parking", "misc")):
        rows, known = [], 0.0
        ins = extra["insurance"]
        rows.append(("保险", yuan(ins) if ins is not None else todo, "按首年报价估，续保价以保险公司为准"))
        known += ins or 0
        energy_note = None
        if km is not None and cons is not None and unit is not None:
            energy = km / 100 * cons * unit
            rows.append(("能耗", yuan(energy), "%s ÷ 100 × %s × %s" % (yuan(km), num(cons), num(unit))))
            known += energy
        elif km is not None and cons is not None and home is not None and fast is not None:
            all_home, all_fast = km / 100 * cons * home, km / 100 * cons * fast
            if share is not None:
                mixed = km / 100 * cons * (home * share + fast * (1 - share))
                rows.append(("能耗", yuan(mixed), "%s ÷ 100 × %s ×（家充 %s × %.0f%% + 快充 %s × %.0f%%）"
                             % (yuan(km), num(cons), num(home), share * 100, num(fast), (1 - share) * 100)))
                known += mixed
            else:
                rows.append(("能耗", "[待确认：家充占比]", "全家充约 %s；全靠快充约 %s" % (yuan(all_home), yuan(all_fast))))
            energy_note = "全家充每年约 %s 元，全靠快充约 %s 元，差 %s 元——能不能稳定家充是电车账的第一道题" % (
                yuan(all_home), yuan(all_fast), yuan(all_fast - all_home))
        else:
            rows.append(("能耗", todo, "需要：年里程、百公里油耗或电耗、单价"))
        for key, label, note in (("maintenance", "保养维修", "按保养手册的周期和项目问价"),
                                 ("parking", "停车", "小区、单位附近的月租或按次"),
                                 ("misc", "过路费、年检等杂项", "按自己的用车习惯估")):
            v = extra[key]
            rows.append((label, yuan(v) if v is not None else todo, "你给的" if v is not None else note))
            known += v or 0
        pending = sum(1 for r in rows if r[1].startswith("["))
        total = total_cell(known, pending)
        lines += ["", "## 每年养车钱", "| 项目 | 金额（元/年） | 算法 / 来源 |", "|---|---|---|"]
        lines += ["| %s | %s | %s |" % r for r in rows]
        lines.append("| **每年合计** | %s | 折旧不花现金，卖车时才体现；几年就换车的要一起算 |" % total)
        if energy_note:
            lines += ["", energy_note]

    # ---- 贷款
    if principal is not None or total_repay is not None:
        if principal is None or total_repay is None:
            raise InputProblem("算贷款成本要同时给 --loan-principal（贷款本金）和 --loan-total（总还款额）")
        if total_repay < principal:
            raise InputProblem("总还款额 %s 比贷款本金 %s 还少，检查是不是填反了" % (yuan(total_repay), yuan(principal)))
        fees = loan_fees or 0
        cost = total_repay - principal + fees
        lines += ["", "## 贷款的真实成本", "| 项目 | 金额（元） | 说明 |", "|---|---|---|",
                  "| 总还款额 | %s | 让销售书面写出 |" % yuan(total_repay),
                  "| 贷款本金 | %s | |" % yuan(principal),
                  "| 另收的手续费、服务费 | %s | 没含在总还款额里的，要正规发票 |" % yuan(fees),
                  "| **真实成本** | %s | %s − %s + %s |" % (yuan(cost), yuan(total_repay), yuan(principal), yuan(fees)),
                  "", "全款还是贷款属于你自己的资金安排，这里只把两种方案的总账算清楚。"]

    if warnings:
        lines += ["", "## 需要先确认"] + ["- [待确认] " + w for w in warnings]
    lines += ["", "说明：以上只是按你给的参数算出的结果，不代表任何车型、地区的实际价格。"]
    return "\n".join(lines) + "\n", warnings


def write_atomic(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".car_cost-", suffix=".tmp")
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
    ap = Parser(description="买车算账：落地价、每年养车钱、贷款真实成本")
    ap.add_argument("legacy", nargs="*", metavar="旧写法",
                    help="兼容原来的四个位置参数：发票价 年里程 百公里油耗或电耗 单价")
    ap.add_argument("--price", help="发票价（裸车价）")
    ap.add_argument("--ev", action="store_true", help="新能源车：购置税按当年政策，标 [待确认]")
    ap.add_argument("--km", help="年里程（公里）")
    ap.add_argument("--consumption", help="百公里油耗（升）或电耗（度）")
    ap.add_argument("--unit-price", help="油价（元/升）或统一电价（元/度）")
    ap.add_argument("--home-price", help="家里慢充电价（元/度）")
    ap.add_argument("--fast-price", help="外面快充电价（元/度）")
    ap.add_argument("--home-share", help="家充占比，0.8 或 80%%")
    for opt, text in (("--insurance", "首年保险"), ("--plate", "上牌等费用"), ("--addons", "加装"),
                      ("--maintenance", "每年保养维修"), ("--parking", "每年停车"), ("--misc", "每年过路费、年检等杂项")):
        ap.add_argument(opt, help=text)
    ap.add_argument("--loan-principal", help="贷款本金")
    ap.add_argument("--loan-total", help="总还款额（销售书面给的）")
    ap.add_argument("--loan-fees", help="没含在总还款额里的手续费、服务费")
    ap.add_argument("--out", help="把预算表另存为文件（先写临时文件再替换，不会留下半截文件）")
    args = ap.parse_args(argv)

    if args.legacy:
        if len(args.legacy) != 4:
            ap.error("旧写法要正好四个数：发票价 年里程 百公里油耗或电耗 单价（现在是 %d 个）" % len(args.legacy))
        for name, value in zip(("price", "km", "consumption", "unit_price"), args.legacy):
            if getattr(args, name) is not None:
                ap.error("--%s 和位置参数重复给了，只保留一种写法" % name.replace("_", "-"))
            setattr(args, name, value)

    try:
        text, warnings = build(args)
    except InputProblem as e:
        sys.stderr.write("输入有问题：%s\n" % e)
        return EXIT_INPUT
    if args.out:
        try:
            write_atomic(args.out, text)
        except OSError as e:
            sys.stderr.write("写文件失败：%s（%s）。换个目录或文件名再试；预算表如下：\n" % (args.out, e.strerror or e))
            sys.stdout.write(text)
            return EXIT_IO
        print("已保存：%s" % os.path.abspath(args.out))
    sys.stdout.write(text)
    return EXIT_CHECK if warnings else EXIT_OK


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
