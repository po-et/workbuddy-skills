#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国庆攻略：把出发/返程日期和每日行程整理成逐日时间线与预算合计。

只用 Python 标准库，不联网，不读写行程文件以外的任何东西。

  python3 golden_week_plan.py --template > itinerary.csv
  python3 golden_week_plan.py --depart 2026-10-02 --return 2026-10-05 --people 2 \
      --itinerary itinerary.csv --holiday 2026-10-01:2026-10-07 --budget 3000 --out plan.md

行程文件是 CSV（Excel 另存为 CSV 或直接用文本编辑器写都行），表头：
  日期,开始,结束,事项,类别,金额,备注
只有「日期」「事项」必填；# 开头的行是注释；金额填这一项全队合计，可写 148*2。
类别建议用：交通 住宿 餐饮 门票 购物 其他（写「高铁」「酒店」等会自动归类）。

同样的输入永远得到同样的输出（没有随机数，也不读当前日期）。
退出码：0 成功；1 参数或行程数据有误；2 文件读写失败；130 手动中断。
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_INTERRUPT = 0, 1, 2, 130

MAX_TRIP_DAYS = 31        # 超过就当成日期写错
LONG_TRIP_DAYS = 12       # 超过给提醒
MAX_HOLIDAY_DAYS = 15
MAX_ERRORS_SHOWN = 20
WEEKDAYS = "一二三四五六日"
CENT = Decimal("0.01")

STD_CATEGORIES = ("交通", "住宿", "餐饮", "门票", "购物", "其他")
CATEGORY_ALIASES = (
    ("交通", ("交通", "高铁", "动车", "火车", "机票", "飞机", "航班", "大巴", "客车", "打车",
              "网约车", "出租车", "地铁", "公交", "油费", "加油", "充电", "过路费", "停车",
              "自驾", "租车", "轮渡", "船票")),
    ("住宿", ("住宿", "酒店", "民宿", "宾馆", "客栈", "旅馆")),
    ("餐饮", ("餐饮", "早餐", "午餐", "晚餐", "早饭", "午饭", "晚饭", "夜宵", "小吃",
              "美食", "饮料", "吃饭", "餐")),
    ("门票", ("门票", "景区", "景点", "索道", "观光车", "演出", "博物馆", "预约")),
    ("购物", ("购物", "特产", "纪念品", "伴手礼")),
    ("其他", ("其他", "其它", "杂费", "保险")),
)
HEADER_ALIASES = {
    "日期": ("日期", "date", "day"),
    "开始": ("开始", "开始时间", "时间", "start", "time"),
    "结束": ("结束", "结束时间", "end"),
    "事项": ("事项", "行程", "安排", "内容", "item", "activity"),
    "类别": ("类别", "分类", "类型", "category", "type"),
    "金额": ("金额", "费用", "花费", "价格", "cost", "amount", "price"),
    "备注": ("备注", "说明", "note", "notes"),
}
DRIVE_WORDS = ("自驾", "高速", "开车", "油费", "加油", "过路费", "服务区")

TEMPLATE = """# 国庆行程模板（示例数据：地点与金额都是虚构的，换成你自己查到的实价）
# 金额填这一项全队合计，可写 单价*数量；开始/结束可空，空的排在当天最后
日期,开始,结束,事项,类别,金额,备注
2026-10-02,07:30,09:40,高铁 出发城市→目的地,交通,148*2,开车前30分钟到站
2026-10-02,12:00,13:00,午饭,餐饮,120,
2026-10-02,14:00,17:00,景区A（需提前预约）,门票,90*2,预约截图存手机
2026-10-02,,,酒店第1晚（国庆当晚实价）,住宿,680,写上免费取消截止时间
"""


class InputError(Exception):
    """用户输入（参数或行程文件）有误，退出码 1。"""


class Item(object):
    __slots__ = ("date", "start", "end", "title", "category", "amount", "note", "lineno")

    def __init__(self, date, start, end, title, category, amount, note, lineno):
        self.date, self.start, self.end = date, start, end
        self.title, self.category, self.amount = title, category, amount
        self.note, self.lineno = note, lineno


# ---------------------------------------------------------------- 解析

_DATE_FULL = re.compile(r"^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?$")
_DATE_SHORT = re.compile(r"^(\d{1,2})[-/.月](\d{1,2})日?$")
_TIME = re.compile(r"^(\d{1,2})[:：](\d{2})$|^(\d{2})(\d{2})$")
_AMOUNT_JUNK = re.compile(r"[¥￥元\s]")
_NUMBER = re.compile(r"^\d+(\.\d+)?$")


def parse_date(text, ref_year=None):
    s = text.strip().replace(" ", "")
    m = _DATE_FULL.match(s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = _DATE_SHORT.match(s)
        if not m or ref_year is None:
            raise InputError("日期「%s」看不懂：请写成 2026-10-02（行程文件里也可以写 10-02）" % text)
        y, mo, d = ref_year, int(m.group(1)), int(m.group(2))
    try:
        return dt.date(y, mo, d)
    except ValueError:
        raise InputError("日期「%s」不存在（例如 9 月没有 31 日）" % text)


def parse_time(text):
    s = text.strip()
    if not s:
        return None
    m = _TIME.match(s)
    if not m:
        raise InputError("时间「%s」看不懂：请写成 07:30" % text)
    h, mi = (m.group(1), m.group(2)) if m.group(1) is not None else (m.group(3), m.group(4))
    h, mi = int(h), int(mi)
    if h == 24 and mi == 0:
        return 24 * 60
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise InputError("时间「%s」超出范围：小时 0–23，分钟 0–59" % text)
    return h * 60 + mi


def parse_amount(text):
    s = _AMOUNT_JUNK.sub("", text.strip())
    if not s:
        return Decimal("0")
    if s.startswith("-"):
        raise InputError("金额「%s」是负数：退款或报销请写在备注里，金额填 0" % text)
    parts = re.split(r"[*xX×]", s)
    if len(parts) > 3 or not all(_NUMBER.match(p) for p in parts):
        raise InputError("金额「%s」看不懂：写数字，或 单价*数量（如 148*2）" % text)
    total = Decimal("1")
    for p in parts:
        total *= Decimal(p)
    return total.quantize(CENT, rounding=ROUND_HALF_UP)


def normalize_category(text):
    s = text.strip()
    if not s:
        return "其他"
    for std, aliases in CATEGORY_ALIASES:
        if s in aliases:
            return std
    for std, aliases in CATEGORY_ALIASES:
        if any(a in s for a in aliases):
            return std
    return s  # 自定义类别原样保留，排在标准类别之后


def parse_holiday(text, ref_year):
    parts = [p for p in re.split(r"[:~～至]", text.strip()) if p.strip()]
    if len(parts) != 2:
        raise InputError("--holiday 请写成 起始:结束，例如 2026-10-01:2026-10-07")
    start, end = parse_date(parts[0], ref_year), parse_date(parts[1], ref_year)
    if end < start:
        raise InputError("--holiday 的结束日 %s 早于起始日 %s" % (end, start))
    if (end - start).days + 1 > MAX_HOLIDAY_DAYS:
        raise InputError("--holiday 共 %d 天，超过 %d 天，像是日期写错了"
                         % ((end - start).days + 1, MAX_HOLIDAY_DAYS))
    return start, end


def read_text(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        raise IOError("找不到行程文件：%s（先用 --template 生成一份）" % path)
    except OSError as exc:
        raise IOError("读不了行程文件 %s：%s" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise IOError("行程文件编码认不出来：请用 UTF-8 另存一次")


def _map_header(cells):
    mapping = {}
    for idx, cell in enumerate(cells):
        key = cell.strip().lower()
        for std, aliases in HEADER_ALIASES.items():
            if key in aliases and std not in mapping:
                mapping[std] = idx
    return mapping


def parse_itinerary(text, ref_year):
    lines = [(no, ln) for no, ln in enumerate(text.splitlines(), 1)
             if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise InputError("行程文件是空的：至少要有表头和一行行程（可用 --template 生成模板）")
    head_no, head = lines[0]
    if "," in head:
        delim = ","
    elif "\t" in head:
        delim = "\t"
    elif "，" in head:
        raise InputError("第 %d 行表头用的是中文逗号「，」分隔：请把分隔符换成英文逗号「,」"
                         "（事项里的中文逗号可以保留）" % head_no)
    else:
        raise InputError("第 %d 行不像表头：需要「日期,开始,结束,事项,类别,金额,备注」" % head_no)
    header = next(csv.reader([head], delimiter=delim))
    col = _map_header(header)
    missing = [k for k in ("日期", "事项") if k not in col]
    if missing:
        raise InputError("表头缺少「%s」列；读到的表头是：%s"
                         % ("」「".join(missing), " | ".join(c.strip() for c in header)))

    items, errors = [], []
    for no, line in lines[1:]:
        cells = next(csv.reader([line], delimiter=delim))
        if len(cells) > len(header):
            if any(c.strip() for c in cells[len(header):]):
                errors.append("第 %d 行比表头多出 %d 列：金额或事项里的逗号请去掉，或给整格加英文双引号"
                              % (no, len(cells) - len(header)))
                continue
            cells = cells[:len(header)]

        def cell(key):
            idx = col.get(key)
            return cells[idx].strip() if idx is not None and idx < len(cells) else ""

        try:
            title = cell("事项")
            if not title:
                raise InputError("「事项」是空的")
            items.append(Item(
                date=parse_date(cell("日期"), ref_year),
                start=parse_time(cell("开始")),
                end=parse_time(cell("结束")),
                title=title,
                category=normalize_category(cell("类别")),
                amount=parse_amount(cell("金额")),
                note=cell("备注"),
                lineno=no,
            ))
        except InputError as exc:
            errors.append("第 %d 行：%s" % (no, exc))
    if errors:
        shown = errors[:MAX_ERRORS_SHOWN]
        more = len(errors) - len(shown)
        raise InputError("行程文件有 %d 处需要改：\n  %s%s" % (
            len(errors), "\n  ".join(shown), "\n  ……另有 %d 处" % more if more else ""))
    if not items:
        raise InputError("行程文件只有表头，没有行程")
    return items


# ---------------------------------------------------------------- 计算

def fmt_money(value):
    value = value.quantize(CENT, rounding=ROUND_HALF_UP)
    if value == value.to_integral_value():
        return "{:,}".format(int(value))
    return "{:,.2f}".format(value)


def fmt_time(minutes):
    if minutes is None:
        return ""
    if minutes == 24 * 60:
        return "24:00"
    day, rest = divmod(minutes, 24 * 60)
    label = "%02d:%02d" % divmod(rest, 60)
    return label + ("（次日）" if day else "")


def fmt_day(d):
    return "%s（周%s）" % (d.isoformat(), WEEKDAYS[d.weekday()])


def md_cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def day_label(d, holiday):
    if not holiday:
        return ""
    hs, he = holiday
    one = dt.timedelta(days=1)
    if d == hs - one:
        return "节前一天·出程高峰（经验）"
    if d == hs:
        return "假期第1天·出程高峰（经验）"
    if d == he:
        return "假期最后一天·返程高峰（经验）"
    if d == he - one:
        return "假期倒数第2天·返程高峰（经验）"
    if hs < d < he:
        return "假期第%d天" % ((d - hs).days + 1)
    return "假期外（请假或周末）"


def peak_hints(depart, ret, holiday):
    if not holiday:
        return ["未提供 --holiday，没有标注高峰日；放假与调休安排以国务院办公厅当年通知为准。"]
    hs, he = holiday
    one = dt.timedelta(days=1)
    hints = []
    if depart in (hs - one, hs):
        hints.append("⚠ 出发日 %s 落在经验上的出程高峰（节前一天、假期第1天）：能提前一天走最好；"
                     "走不了就避开当天上午，以导航的实时预测为准。" % depart.isoformat())
    else:
        hints.append("出发日 %s 不在经验出程高峰（节前一天、假期第1天）。" % depart.isoformat())
    if ret in (he - one, he):
        hints.append("⚠ 返程日 %s 落在经验上的返程高峰（假期最后两天）：能提前一天回最好；"
                     "回不了就早上出发，给路上多留时间。" % ret.isoformat())
    else:
        hints.append("返程日 %s 不在经验返程高峰（假期最后两天）。" % ret.isoformat())
    if ret < hs - one or depart > he:
        hints.append("⚠ 行程和你给的假期完全不重叠：确认年份和日期没有写错。")
    return hints


def find_overlaps(day_items):
    """day_items 已按开始时间排好。

    返回 (clashes, inside)：clashes 是「交叉重叠」的行号集合（真冲突，要改）；
    inside 是 {行号: 外层事项名}，表示整段落在另一项时段里（如游览中途吃午饭），只做标注。
    """
    clashes, inside = set(), {}
    outer_end, outer = None, None
    for it in day_items:
        if it.start is None:
            continue
        end = it.end
        if end is not None and end < it.start:
            end += 24 * 60  # 跨夜，例如 23:00–01:00 的夜车
        if outer_end is not None and it.start < outer_end:
            if end is None or end <= outer_end:
                inside[it.lineno] = outer.title
                continue
            clashes.add(it.lineno)
            clashes.add(outer.lineno)
        if end is not None and (outer_end is None or end > outer_end):
            outer_end, outer = end, it
    return clashes, inside


def build_report(depart, ret, people, items, holiday, budget, reserve_pct):
    lines = []
    add = lines.append
    trip_days = (ret - depart).days + 1
    add("# 国庆行程时间线与预算（脚本生成）")
    add("")
    add("- 出发 %s → 返程 %s，共 %d 天，%d 人" % (fmt_day(depart), fmt_day(ret), trip_days, people))
    if holiday:
        add("- 假期 %s 至 %s（按你提供的日期；以国务院办公厅当年放假通知为准）"
            % (holiday[0].isoformat(), holiday[1].isoformat()))
    add("")
    add("## 避峰提示")
    add("")
    for h in peak_hints(depart, ret, holiday):
        add("- " + h)
    add("")

    # ---- 每日时间线
    add("## 每日时间线")
    by_day = {}
    outside = []
    for it in items:
        if depart <= it.date <= ret:
            by_day.setdefault(it.date, []).append(it)
        else:
            outside.append(it)
    warnings = []
    empty_days = []
    for i in range(trip_days):
        d = depart + dt.timedelta(days=i)
        label = day_label(d, holiday)
        add("")
        add("### 第%d天 %s%s" % (i + 1, fmt_day(d), (" · " + label) if label else ""))
        add("")
        day_items = sorted(by_day.get(d, []),
                           key=lambda x: (x.start is None, x.start if x.start is not None else 0, x.lineno))
        if not day_items:
            add("（当天没有安排 [待补]）")
            empty_days.append(d.isoformat())
            continue
        clashes, inside = find_overlaps(day_items)
        add("| 时间 | 事项 | 类别 | 金额（元） | 备注 |")
        add("|---|---|---|---:|---|")
        subtotal = Decimal("0")
        for it in day_items:
            if it.start is None:
                when = "时间待定"
            elif it.end is None:
                when = fmt_time(it.start)
            else:
                end = it.end if it.end >= it.start else it.end + 24 * 60
                when = "%s–%s" % (fmt_time(it.start), fmt_time(end))
            note = it.note
            if it.lineno in clashes:
                note = ("⚠ 时间重叠 " + note).strip()
            elif it.lineno in inside:
                note = ("（在「%s」时段内）%s" % (inside[it.lineno], note)).strip()
            add("| %s | %s | %s | %s | %s |" % (when, md_cell(it.title), md_cell(it.category),
                                               fmt_money(it.amount), md_cell(note)))
            subtotal += it.amount
        add("")
        add("当天小计：%s 元" % fmt_money(subtotal))
        if clashes:
            warnings.append("%s 有 %d 项时间重叠（表里标了 ⚠），调整后再发给同行人。"
                            % (d.isoformat(), len(clashes)))

    if outside:
        add("")
        add("### 行程日期之外的条目（计入预算）")
        add("")
        add("| 日期 | 事项 | 类别 | 金额（元） | 备注 |")
        add("|---|---|---|---:|---|")
        for it in sorted(outside, key=lambda x: (x.date, x.lineno)):
            tag = "行前" if it.date < depart else "行后"
            add("| %s %s | %s | %s | %s | %s |" % (it.date.isoformat(), tag, md_cell(it.title),
                                                 md_cell(it.category), fmt_money(it.amount), md_cell(it.note)))
        warnings.append("有 %d 条不在 %s 至 %s 之间（多为提前付的票款或押金），确认不是日期写错。"
                        % (len(outside), depart.isoformat(), ret.isoformat()))

    # ---- 预算
    totals = {}
    for it in items:
        totals[it.category] = totals.get(it.category, Decimal("0")) + it.amount
    custom = sorted(c for c in totals if c not in STD_CATEGORIES)
    order = [c for c in STD_CATEGORIES if c in totals] + custom
    subtotal = sum(totals.values(), Decimal("0"))
    reserve = (subtotal * Decimal(str(reserve_pct)) / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
    grand = subtotal + reserve
    per_head = (grand / Decimal(people)).quantize(CENT, rounding=ROUND_HALF_UP)

    add("")
    add("## 预算合计")
    add("")
    add("| 类别 | 金额（元） | 占比 |")
    add("|---|---:|---:|")
    for c in order:
        share = "—" if subtotal == 0 else "%d%%" % int((totals[c] * 100 / subtotal).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))
        add("| %s | %s | %s |" % (md_cell(c), fmt_money(totals[c]), share))
    add("| **分项小计** | **%s** | 100%% |" % fmt_money(subtotal))
    add("| 应急预备金 %s%% | %s | |" % (("%g" % reserve_pct), fmt_money(reserve)))
    add("| **总计** | **%s** | |" % fmt_money(grand))
    add("| 人均（%d 人） | %s | |" % (people, fmt_money(per_head)))
    if budget is not None:
        budget_d = Decimal(str(budget)).quantize(CENT, rounding=ROUND_HALF_UP)
        add("")
        if grand <= budget_d:
            add("预算上限 %s 元：含预备金还剩 %s 元。" % (fmt_money(budget_d), fmt_money(budget_d - grand)))
        else:
            biggest = max(order, key=lambda c: (totals[c], -order.index(c)))
            add("⚠ 预算上限 %s 元：含预备金超出 %s 元。最大的一项是「%s」（%s 元），先从它或行程天数上砍。"
                % (fmt_money(budget_d), fmt_money(grand - budget_d), biggest, fmt_money(totals[biggest])))

    zero = [it for it in items if it.amount == 0]
    if zero:
        warnings.append("有 %d 条金额为 0 或没填（第 %s 行），确认是免费还是漏填。"
                        % (len(zero), "、".join(str(it.lineno) for it in zero[:10])))
    if empty_days:
        warnings.append("这几天没有安排：%s，补上或标成自由活动。" % "、".join(empty_days))
    if trip_days > LONG_TRIP_DAYS:
        warnings.append("行程共 %d 天，比一般黄金周长，确认请假天数和日期。" % trip_days)

    add("")
    add("## 提醒")
    add("")
    for w in warnings:
        add("- ⚠ " + w)
    text_blob = " ".join(it.title + " " + it.note + " " + it.category for it in items)
    if any(w in text_blob for w in DRIVE_WORDS):
        add("- 自驾：小型客车节假日免费通行的常见规则（车型范围、免费时段、按驶离出口还是驶入时间判定）"
            "一律以交通运输部当年通知为准；别为了卡免费时段专门挤零点。")
    add("- 火车票开售时间与候补规则以 12306 公告为准；景区预约与限流以景区官方渠道为准。")
    add("- 这是计划不是路况：出发前一晚和出发前 1 小时各看一次导航预测，再定几点出门。")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 输出

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
        description="国庆攻略：出发/返程日期 + 每日行程 CSV → 逐日时间线与预算合计（Markdown）。",
        epilog="退出码：0 成功；1 参数或行程数据有误；2 文件读写失败；130 手动中断。")
    p.add_argument("--template", action="store_true", help="打印一份行程 CSV 模板（示例数据）后退出")
    p.add_argument("--depart", help="出发日期，如 2026-10-02")
    p.add_argument("--return", dest="ret", help="返程日期，如 2026-10-05")
    p.add_argument("--people", type=int, default=1, help="同行人数，默认 1")
    p.add_argument("--itinerary", help="行程 CSV 文件路径")
    p.add_argument("--holiday", help="法定假期起止，如 2026-10-01:2026-10-07（以当年放假通知为准）")
    p.add_argument("--budget", type=float, help="总预算上限（元），可选")
    p.add_argument("--reserve", type=float, default=10.0, help="应急预备金占分项小计的百分比，默认 10")
    p.add_argument("--out", help="把结果写进这个文件（默认打印到屏幕）")
    return p


def run(argv):
    args = build_parser().parse_args(argv)
    if args.template:
        sys.stdout.write(TEMPLATE)
        return EXIT_OK
    missing = [flag for flag, val in (("--depart", args.depart), ("--return", args.ret),
                                      ("--itinerary", args.itinerary)) if not val]
    if missing:
        raise InputError("缺少参数 %s。示例：--depart 2026-10-02 --return 2026-10-05 --itinerary itinerary.csv"
                         % " ".join(missing))
    depart, ret = parse_date(args.depart), parse_date(args.ret)
    if ret < depart:
        raise InputError("返程 %s 早于出发 %s：是把两个日期写反了，还是返程月份写错了？"
                         % (ret.isoformat(), depart.isoformat()))
    if (ret - depart).days + 1 > MAX_TRIP_DAYS:
        raise InputError("行程 %d 天，超过 %d 天，像是年份或月份写错了"
                         % ((ret - depart).days + 1, MAX_TRIP_DAYS))
    if not 1 <= args.people <= 50:
        raise InputError("--people 应在 1–50 之间，收到 %d" % args.people)
    if not 0 <= args.reserve <= 50:
        raise InputError("--reserve 应在 0–50（百分比）之间，收到 %g" % args.reserve)
    if args.budget is not None and args.budget <= 0:
        raise InputError("--budget 应大于 0，收到 %g" % args.budget)
    holiday = parse_holiday(args.holiday, depart.year) if args.holiday else None
    items = parse_itinerary(read_text(args.itinerary), depart.year)
    report = build_report(depart, ret, args.people, items, holiday, args.budget, args.reserve)
    if args.out:
        try:
            write_atomic(args.out, report)
        except OSError as exc:
            raise IOError("写不进 %s：%s" % (args.out, exc.strerror or exc))
        print("已写入 %s（%d 条行程，%d 天）" % (args.out, len(items), (ret - depart).days + 1))
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
