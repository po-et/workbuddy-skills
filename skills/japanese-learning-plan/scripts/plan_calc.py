#!/usr/bin/env python3
"""日语计划计算器：按本技能写死的算法排进度，并按四周复盘的实测数据给出调整。同样的输入，每次输出一致。

用法：
  python3 plan_calc.py plan --weeks 44 --lessons 48 --minutes 30             # 离考试 44 周，教材 48 课
  python3 plan_calc.py plan --exam-date 2027-06-30 --lessons 48 --minutes 60 --kana-done   # 日期仅为示例
  python3 plan_calc.py review --planned 5 --done 4 --words 32/50 --conj-rate 85 --conj-seconds 1.8 \\
                              --listen 6 --minutes 30 --lessons-left 44 --weeks-left 35

算法（与 SKILL.md 一致）：
  可用周数 = 离考试的周数 - 第一周五十音（已会五十音则不扣）- 最后四周总复习
  每周课数 = 教材总课数 ÷ 可用周数；新词每天 30 分钟版 8 个、60 分钟版 15 个
  复盘规则：完成率 < 80% 放慢新课先还复习账；单词对不到七成新词减三成；变形正确率 < 90% 或平均 > 2 秒
            每天从新课挪 5 分钟练变形卡；课文听懂不到五成从新课挪 10 分钟给听力并全改精听；
            全部达标且有余力新词加两成；有考试日期的用「剩余课数 ÷ 每周实际课数」算还要几周。
退出码：0 成功；1 参数错误（含数值超出合理范围）；3 时间排不开（可用周数不足）；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。本脚本不读写任何文件。
"""
import argparse
import datetime as dt
import math
import re
import sys

WORDS = {30: 8, 60: 15}


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def version_of(minutes, notes):
    """本技能只有 30、60 分钟两版日程；其余时长映射到其中一版并说明。"""
    if minutes < 30:
        notes.append("每天 %d 分钟低于 30 分钟版的需要：按 30 分钟版排，新课进度会慢于计划，"
                     "四周复盘时按实测再算 [待确认]" % minutes)
        return 30
    if minutes < 60:
        if minutes > 30:
            notes.append("每天 %d 分钟：按 30 分钟版的结构排，多出的 %d 分钟要赶进度就加给新课，"
                         "否则加给听力和复习 [待确认]" % (minutes, minutes - 30))
        return 30
    if minutes > 60:
        notes.append("每天 %d 分钟：按 60 分钟版的结构排，多出的 %d 分钟要赶进度就加给新课，"
                     "否则加给听力和复习 [待确认]" % (minutes, minutes - 60))
    return 60


def check_range(ap, name, value, lo, hi, unit=""):
    if value is not None and not lo <= value <= hi:
        ap.error("%s 应在 %s 到 %s%s 之间，收到的是 %s" % (name, lo, hi, unit, value))


def plan(a, ap):
    notes = []
    check_range(ap, "--minutes", a.minutes, 10, 600, " 分钟")
    check_range(ap, "--lessons", a.lessons, 1, 300, " 课")
    if a.weeks is None and not a.exam_date:
        ap.error("请给 --weeks（离考试几周）或 --exam-date（考试日期）；不考试的给一个自定的目标周数")
    start = dt.date.today()
    if a.start:
        try:
            start = dt.date.fromisoformat(a.start)
        except ValueError:
            ap.error("--start 要写成 2026-10-05 这样的日期")
    if a.exam_date:
        try:
            exam = dt.date.fromisoformat(a.exam_date)
        except ValueError:
            ap.error("--exam-date 要写成 2027-06-30 这样的日期")
        if exam <= start:
            ap.error("考试日期 %s 不晚于开始日期 %s，请核对" % (exam, start))
        weeks = (exam - start).days // 7
    else:
        weeks = a.weeks
        exam = start + dt.timedelta(weeks=weeks)
    check_range(ap, "离考试的周数", weeks, 1, 260, " 周")
    ver = version_of(a.minutes, notes)
    kana = 0 if a.kana_done else 1
    usable = weeks - kana - 4
    print("离考试 %d 周（%s → %s）；教材 %d 课；日程按 %d 分钟版" % (weeks, start, exam, a.lessons, ver))
    print("可用周数 = %d - %d（五十音）- 4（总复习）= %d 周" % (weeks, kana, usable))
    if usable < 1:
        print("排不开：扣掉%s最后四周总复习后没有周数学新课。可选：① 改考下一次；② 这次只熟悉题型，不求通过。"
              % ("五十音一周和" if kana else ""))
        return 3
    per_week = a.lessons / usable
    print("每周课数 = %d ÷ %d ≈ %.1f 课" % (a.lessons, usable, per_week))
    print("新词：每天 %d 个；学后第 1、2、4、7、15 天各复习一次" % WORDS[ver])
    new_start = start + dt.timedelta(weeks=kana)
    review_start = exam - dt.timedelta(weeks=4)
    print("关键日期：%s新课开始 %s；四周复盘 %s；总复习开始 %s；考前三个月（约 %s）起做官方样题"
          % ("五十音周 %s 至 %s；" % (start, new_start - dt.timedelta(days=1)) if kana else "",
             new_start,
             "、".join(str(new_start + dt.timedelta(weeks=4 * k)) for k in range(1, 4)) + "…",
             review_start, exam - dt.timedelta(days=91)))
    if per_week > 3:
        notes.append("每周要学 %.1f 课，节奏偏紧：第一个四周复盘时按实测课数重算，来不及就把阶段 6 的部分内容降为只求认得"
                     % per_week)
    for n in notes:
        print("注意：" + n)
    return 0


def review(a, ap):
    check_range(ap, "--planned", a.planned, 1, 100, " 课")
    check_range(ap, "--done", a.done, 0, 100, " 课")
    check_range(ap, "--conj-rate", a.conj_rate, 0, 100, "%")
    check_range(ap, "--conj-seconds", a.conj_seconds, 0.1, 60, " 秒")
    check_range(ap, "--listen", a.listen, 0, 10, " 成")
    check_range(ap, "--minutes", a.minutes, 10, 600, " 分钟")
    m = re.match(r"^(\d+)/(\d+)$", a.words or "")
    if not m or int(m.group(2)) == 0 or int(m.group(1)) > int(m.group(2)):
        ap.error("--words 写成「对的个数/抽查个数」，如 32/50，且前者不大于后者")
    right, total = int(m.group(1)), int(m.group(2))
    notes = []
    ver = version_of(a.minutes, notes)
    words_now = a.words_per_day or WORDS[ver]
    rate = a.done / a.planned
    wrate = right / total
    print("四周复盘：完成率 %d%%（%d/%d 课）；单词 %d%%（%d/%d）；变形正确率 %s、平均 %s；课文听懂约 %s"
          % (round(rate * 100), a.done, a.planned, round(wrate * 100), right, total,
             _fmt(a.conj_rate, "%"), _fmt(a.conj_seconds, " 秒"), _fmt(a.listen, " 成")))
    actions, missing = [], []
    if rate < 0.8:
        actions.append("完成率低于 80%：下四周放慢新课，先还复习账")
    if wrate < 0.7:
        actions.append("单词对不到七成：新词减三成，每天 %d → %d 个" % (words_now, round(words_now * 0.7)))
    if a.conj_rate is None and a.conj_seconds is None:
        missing.append("动词变形")
    elif (a.conj_rate is not None and a.conj_rate < 90) or (a.conj_seconds is not None and a.conj_seconds > 2):
        actions.append("变形正确率低于 90% 或平均超过 2 秒：每天从新课里挪 5 分钟练变形卡")
    if a.listen is None:
        missing.append("听力")
    elif a.listen < 5:
        actions.append("课文听懂不到五成：从新课里挪 10 分钟给听力，并全部改成精听")
    if not actions and not missing:
        actions.append("全部达标：如有余力，新词加两成，每天 %d → %d 个" % (words_now, round(words_now * 1.2)))
    print("调整：")
    for x in actions or ["已提供的几项都达标；补测%s后再判断是否加量" % "、".join(missing)]:
        print("- " + x)
    if missing:
        print("- 未提供：%s，相关规则没有判断 [待补]" % "、".join(missing))
    if a.lessons_left is not None and a.weeks_left is not None:
        weekly = a.done / 4
        if weekly <= 0:
            print("进度：这四周没有学完新课，先按上面的调整恢复节奏，下次复盘再算还要几周")
        else:
            need = math.ceil(a.lessons_left / weekly)
            print("进度：按实际每周 %.1f 课，剩余 %d 课还要约 %d 周；离总复习还有 %d 周——%s"
                  % (weekly, a.lessons_left, need, a.weeks_left,
                     "来得及" if need <= a.weeks_left else
                     "来不及。二选一：① 每天加时间；② 把阶段 6 的部分内容降为只求认得"))
    for n in notes:
        print("注意：" + n)
    return 0


def _fmt(x, unit):
    return ("%g%s" % (x, unit)) if x is not None else "未测"


def main(argv=None):
    ap = ArgParser(description="日语计划计算器：排进度 / 四周复盘调整")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan", help="按考试时间和教材课数排进度")
    p.add_argument("--weeks", type=int, help="离考试还有几周")
    p.add_argument("--exam-date", help="考试日期，如 2027-06-30（仅为示例；以官方公告为准）")
    p.add_argument("--start", help="开始日期，默认今天")
    p.add_argument("--lessons", type=int, required=True, help="教材总课数（以教材目录为准）")
    p.add_argument("--minutes", type=int, default=30, help="每天稳定能拿出的分钟数（默认 30）")
    p.add_argument("--kana-done", action="store_true", help="五十音已过关（各抽 20 个，1 分钟读对 18 个以上）")
    r = sub.add_parser("review", help="按四周复盘的实测数据给调整")
    r.add_argument("--planned", type=int, required=True, help="这四周计划学几课")
    r.add_argument("--done", type=int, required=True, help="实际学完几课")
    r.add_argument("--words", required=True, help="单词抽查：对的个数/抽查个数，如 32/50")
    r.add_argument("--conj-rate", type=float, help="动词变形正确率（%%，可选）")
    r.add_argument("--conj-seconds", type=float, help="变形平均每个几秒（可选）")
    r.add_argument("--listen", type=float, help="学过的课文音频不看原文能听懂几成（0–10，可选）")
    r.add_argument("--minutes", type=int, default=30, help="现在每天几分钟（默认 30）")
    r.add_argument("--words-per-day", type=int, help="现在每天几个新词（默认按日程版本：8 或 15）")
    r.add_argument("--lessons-left", type=int, help="剩余课数（可选，用来判断来不来得及）")
    r.add_argument("--weeks-left", type=int, help="离总复习还有几周（可选）")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        return plan(a, ap)
    if a.cmd == "review":
        return review(a, ap)
    ap.error("请选择子命令：plan 或 review，例如 python3 plan_calc.py plan --weeks 44 --lessons 48")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。本脚本不写文件，直接重跑即可。", file=sys.stderr)
        sys.exit(130)
