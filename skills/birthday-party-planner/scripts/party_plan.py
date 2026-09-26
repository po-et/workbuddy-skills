#!/usr/bin/env python3
"""生日方案的日期与预算核算：把生日换算成时间线上的具体日子，按起步比例拆预算，并检查输入是否合理。

只做日期和算术，不推荐任何商家，不联网，只用 Python 标准库。

用法：
  python3 party_plan.py --date 2026-10-17 --people 11 --kids 6 --budget 1000 --who 小孩 --venue 家里 --age 5
  python3 party_plan.py --date 2026-10-09 --people 12 --budget 300 --who 同事 --venue 办公室
  python3 party_plan.py --date 2026-10-17 --people 8             # 不给预算：只排时间线和数量
退出码：0 成功；1 参数错误（日期格式、人数、预算等）；2 写文件失败；3 日期已经过去；130 用户中断
"""

import argparse
import datetime as dt
import os
import re
import sys
import tempfile

WEEK = "一二三四五六日"
# 预算起步分配：类别、百分比、说明（与 SKILL.md 保持一致）
SPLIT = (
    ("餐饮与蛋糕", 45, "对人数最敏感，先算它"),
    ("场地", 15, "在家或办公室办就是 0，挪给餐饮"),
    ("布置", 10, "气球、横幅、桌布、照片墙"),
    ("活动与道具", 10, "游戏奖品、手工材料、音乐"),
    ("礼物与回礼", 10, "回礼按到场人数多备 2 份"),
    ("备用金", 10, "临时加人、补买东西都从这里出，不要省"),
)
DURATION = {"小孩": "1.5–2.5 小时", "伴侣": "半天到一天", "父母": "一顿饭加一小时",
            "同事": "15–30 分钟", "自己": "随意"}
WHO = tuple(DURATION)
VENUES = ("家里", "户外", "包间", "租用场地", "办公室")
FREE_VENUES = ("家里", "办公室")


class ArgError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)


def parse_date(text, name):
    m = re.match(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$", text or "")
    if not m:
        raise ArgError("%s「%s」看不懂：请写成 YYYY-MM-DD，例如 2026-10-17（要带年份）" % (name, text))
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        raise ArgError("%s「%s」不是真实存在的日期，请核对月和日" % (name, text))


def day(d):
    return "%s（周%s）" % (d.isoformat(), WEEK[d.weekday()])


def cake_size(n):
    if n <= 4:
        return "6 寸（约 2–4 人）"
    if n <= 8:
        return "8 寸（约 4–8 人）"
    if n <= 12:
        return "10 寸（约 8–12 人）"
    return "超过 12 人：10 寸以上或两个蛋糕"


def split_budget(budget, venue):
    rows = []
    for name, pct, note in SPLIT:
        if name == "场地" and venue in FREE_VENUES:
            pct, note = 0, "在%s办，场地费为 0，已挪给餐饮与蛋糕" % venue
        elif name == "餐饮与蛋糕" and venue in FREE_VENUES:
            pct, note = 60, "含从场地挪过来的 15%；对人数最敏感，先算它"
        rows.append([name, pct, int(budget * pct // 100), note])
    rows[-1][2] += int(budget) - sum(r[2] for r in rows)  # 取整的零头归备用金，保证合计等于总预算
    return rows


def build(a, today):
    left = (a.date - today).days
    lines = ["# 生日方案核算：日期与预算", ""]
    lines.append("生日：%s，距今天 %d 天｜对象：%s｜场地：%s｜确定 %d 人，可能 %d 人"
                 % (day(a.date), left, a.who or "[待确认]", a.venue or "[待确认]", a.people, a.maybe))
    if a.who:
        lines.append("建议时长：%s" % DURATION[a.who])
    if left >= 14:
        pace = "时间充裕，按前 2 周 / 前 3 天 / 当天三段走"
    elif left >= 3:
        pace = "前 2 周那一段已经赶不上：今天就把定场地、发邀请、订蛋糕做完；造型蛋糕先问店家来不来得及"
    elif left >= 1:
        pace = "只剩 %d 天：出最小版（当天环节表 + 采购清单 + 一条备用方案 + 邀请短信）" % left
    else:
        pace = "就是今天：出最小版，只保蛋糕环节和吃的"
    lines.append("节奏：" + pace)
    lines += ["", "## 时间线上的具体日子", "", "| 节点 | 日期 | 要做的事 |", "|---|---|---|"]
    two_weeks = a.date - dt.timedelta(days=14)
    three_days = a.date - dt.timedelta(days=3)
    if two_weeks >= today:
        lines.append("| 前 2 周 | %s | 定时段、人数上限、预算、主题；定场地；发邀请（顺带问忌口与过敏）；订蛋糕；分工 |"
                     % day(two_weeks))
    elif left >= 3:
        lines.append("| 前 2 周（已过） | 今天 %s | 定场地、发邀请、订蛋糕、分工，今天做完 |" % day(today))
    if left >= 10:
        who = "受邀人（小朋友的邀请发给家长）" if a.who == "小孩" else "受邀人"
        lines.append("| 回复截止 | %s | 请%s在这天前回复能不能来 |" % (day(a.date - dt.timedelta(days=7)), who))
    if three_days >= today:
        lines.append("| 前 3 天 | %s | 二次确认人数；买齐不怕放的东西；户外的看天气预报；把环节表发给帮忙的人 |"
                     % day(three_days))
    lines.append("| 当天 | %s | 开场前 1 小时布置完；取蛋糕、买生鲜；控场的人按环节表盯时间 |" % day(a.date))

    total = a.people + a.maybe
    lines += ["", "## 数量参考", ""]
    extra = max(1, (a.people + 5) // 10)  # 多备一成，四舍五入，至少 1 份
    lines.append("- 吃的按 %d 人备（确定 %d 人多备一成，至少多 1 份）" % (a.people + extra, a.people))
    lines.append("- 蛋糕：%s，以店家说明为准（按确定加可能共 %d 人估）" % (cake_size(total), total))
    if a.who == "小孩":
        if a.kids:
            lines.append("- 回礼：%d 份（来的小朋友 %d 个 + 2）" % (a.kids + 2, a.kids))
            lines.append("- 看护：至少 %d 个大人专门看着（每 4–5 个孩子一个，孩子越小越按 4 个配）"
                         % (-(-a.kids // 5)))
        else:
            lines.append("- 回礼：来的小朋友人数 + 2 份（小朋友人数 [待确认]）")
            lines.append("- 看护：每 4–5 个孩子至少一个大人专门看着")
        if a.age:
            lines.append("- 请几个小朋友：学龄前常见经验「年龄 + 1」= %d 个，先照这个起步" % (a.age + 1))
    if a.venue == "户外":
        lines.append("- 户外：必须同时定好室内备选，前 3 天看天气预报")

    if a.budget is not None:
        rows = split_budget(a.budget, a.venue)
        lines += ["", "## 预算拆分（总预算 %d 元，起步比例，按实际调整）" % a.budget, "",
                  "| 类别 | 比例 | 金额（元） | 说明 |", "|---|---|---|---|"]
        for name, pct, amount, note in rows:
            lines.append("| %s | %d%% | %d | %s |" % (name, pct, amount, note))
        lines.append("| 合计 | 100%% | %d | 谁出钱：[待确认]（自己 / AA / 公费） |" % sum(r[2] for r in rows))
        per = a.budget / a.people
        lines.append("")
        lines.append("人均：%d ÷ %d ≈ %.1f 元" % (a.budget, a.people, per))
        if a.meal_price:
            food = rows[0][2]
            can = int(food // a.meal_price)
            if can < a.people:
                lines.append("注意：按你估的每人餐费 %.0f 元，餐饮预算 %d 元只够 %d 人；先减人数，或换成下午茶、在家办"
                             % (a.meal_price, food, can))
    else:
        lines += ["", "预算：[待补]（给了总预算再按比例拆）"]
    todo = []
    if not a.who:
        todo.append("寿星是谁（小孩 / 伴侣 / 父母 / 同事 / 自己）")
    if not a.venue:
        todo.append("在哪办（家里 / 户外 / 包间 / 租用场地 / 办公室）")
    if a.who == "小孩" and not a.age:
        todo.append("孩子几岁（决定请几个小朋友、游戏怎么排）")
    if todo:
        lines += ["", "## 还缺的信息 [待确认]", ""] + ["- " + t for t in todo]
    return "\n".join(lines) + "\n"


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
    p = Parser(description="生日方案的日期与预算核算（只做算术，不推荐商家）。")
    p.add_argument("--date", required=True, help="生日会日期，YYYY-MM-DD")
    p.add_argument("--people", type=int, required=True, help="确定来的人数（含寿星）")
    p.add_argument("--maybe", type=int, default=0, help="可能来的人数，默认 0")
    p.add_argument("--budget", type=int, help="总预算（元，整数）；不给就只排时间线")
    p.add_argument("--who", help="寿星：" + " / ".join(WHO))
    p.add_argument("--venue", help="场地：" + " / ".join(VENUES))
    p.add_argument("--age", type=int, help="寿星是小孩时填年龄")
    p.add_argument("--kids", type=int, help="寿星是小孩时，来的小朋友人数（不含寿星），用来算回礼和看护")
    p.add_argument("--meal-price", type=float, help="你估的每人餐费（元），用来检查预算够不够")
    p.add_argument("--today", help="以哪天为今天，YYYY-MM-DD，默认系统日期")
    p.add_argument("--out", help="写入这个 Markdown 文件（默认打印到屏幕）")
    try:
        a = p.parse_args(argv)
        a.date = parse_date(a.date, "--date")
        today = parse_date(a.today, "--today") if a.today else dt.date.today()
        if a.people < 1:
            raise ArgError("--people 至少是 1（确定来的人数，含寿星）")
        if a.maybe < 0:
            raise ArgError("--maybe 不能是负数")
        if a.budget is not None and a.budget <= 0:
            raise ArgError("--budget 要大于 0；还没定预算就先不写这个参数")
        if a.who and a.who not in WHO:
            raise ArgError("--who 只能是：%s" % " / ".join(WHO))
        if a.venue and a.venue not in VENUES:
            raise ArgError("--venue 只能是：%s" % " / ".join(VENUES))
        if a.age is not None and not 0 <= a.age <= 120:
            raise ArgError("--age 要在 0 到 120 之间")
        if a.kids is not None and not 0 <= a.kids < a.people:
            raise ArgError("--kids 不能是负数，也要小于 --people（确定人数含寿星和大人）")
        if a.meal_price is not None and a.meal_price <= 0:
            raise ArgError("--meal-price 要大于 0")
    except ArgError as exc:
        print("参数错误：%s\n用法示例：python3 party_plan.py --date 2026-10-17 --people 8 --budget 1000"
              % exc, file=sys.stderr)
        return 1
    if a.date < today:
        print("日期 %s 已经过去了（今天是 %s）。如果是补过生日，请给新的日期再算。" % (day(a.date), day(today)),
              file=sys.stderr)
        return 3
    report = build(a, today)
    if (a.date - today).days > 366:
        report += "\n提示：生日在一年以后，时间线里的日子先当参考，临近再算一次。\n"
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
