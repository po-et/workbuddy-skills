#!/usr/bin/env python3
"""跑步日志周复盘：按进退规则和疼痛红绿灯，给每周一个结论，并写明依据。

用法：
  python3 scripts/run_review.py run_log.csv
  python3 scripts/run_review.py run_log.csv --today 2026-10-20     # 指定「今天」，用来判断中断了多久

run_log.csv 的表头（第一行）必须是：
  date,week,session,run_min,talk,effort,pain,next_morning,note
  date 日期（09-02 或 2026-09-02）；week 第几周；session 本周第几次（1–3）；run_min 实际跑步分钟；
  talk 说话测试（整句 / 几个词）；effort 吃力程度 0–10；pain 跑中疼痛 0–10；next_morning 次日早上疼痛 0–10；
  note 备注（疼在哪、睡得怎样、天气）

脚本不诊断伤痛，也不能确认肌肉酸胀是否正常。疼痛分数不是继续跑步的许可；记录了疼痛或局部膝/关节不适时暂停跑步，不自动进阶。
胸闷、胸痛、心慌、头晕这类红灯症状不等复盘，当场停跑，严重时拨打 120。
退出码：0 完成且没有疼痛停跑信号；1 表头或内容有误；2 文件读不了；
        3 存在疼痛或停跑信号，先核实恢复或就医；130 手动中断（Ctrl+C）。
只用 Python 标准库。
"""

import argparse
import csv
import datetime as dt
import io
import re
import sys
from pathlib import Path

FIELDS = ["date", "week", "session", "run_min", "talk", "effort", "pain", "next_morning", "note"]
TALK_OK = {"整句", "整句话", "能说整句", "能说整句话", "句子"}
TALK_HARD = {"几个词", "词", "说不出", "说不出话", "说不了整句"}
RED_WORDS = ("胸闷", "胸痛", "心慌", "心悸", "头晕", "眼黑", "晕倒", "冷汗", "气喘不上", "喘不上气",
             "肿", "卡住", "打软腿", "响声", "夜里疼", "夜里也疼", "按压疼", "骨头疼", "意识", "说话含糊")
NEGATION = ("不", "没", "无", "未")
LOCAL_DISCOMFORT = re.compile(r"(?:膝(?:盖)?|关节|脚踝|踝|跟腱|足跟|脚底|骨头).{0,6}?(?:疼|痛|不适|发紧|紧绷|有点紧)")
LOCAL_ENGLISH = re.compile(r"\b(?:knee|joint|ankle|achilles)\s+(?:pain|ache|hurts?|painful)\b|"
                           r"\b(?:pain|ache)\s+(?:in\s+)?(?:my\s+)?(?:knee|joint|ankle|achilles)\b", re.I)


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FriendlyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/run_review.py run_log.csv）" % message, file=sys.stderr)
        sys.exit(1)


def read_text(path):
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls", ".numbers"):
        raise InputError(2, "%s 是表格文件：在 Excel/WPS/Numbers 里另存为 CSV（UTF-8）再复盘" % p.name)
    if not p.is_file():
        raise InputError(2, "找不到 %s：检查路径；第一次用就新建这个文件，第一行写表头 %s" % (path, ",".join(FIELDS)))
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise InputError(2, "读不了 %s（%s）：文件可能正被其他软件打开" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise InputError(2, "编码认不出来：另存为 UTF-8 的 CSV")


def parse_int(raw, name, lo, hi):
    s = (raw or "").strip()
    if not re.fullmatch(r"\d+", s):
        raise ValueError("%s=%r 要填 %d–%d 的整数" % (name, raw, lo, hi))
    v = int(s)
    if not lo <= v <= hi:
        raise ValueError("%s=%s 超出 %d–%d" % (name, s, lo, hi))
    return v


def parse_date(raw, today):
    s = (raw or "").strip().replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            d = dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if fmt == "%m-%d":                     # 没写年份：按今年算，比今天还晚就算去年
            d = d.replace(year=today.year)
            if d > today:
                d = d.replace(year=today.year - 1)
        return d
    return None


def red_words(note):
    hits = []
    for w in RED_WORDS:
        for m in re.finditer(re.escape(w), note):
            if not any(n in note[max(0, m.start() - 3):m.start()] for n in NEGATION):
                hits.append(w)
                break
    return hits


def local_discomfort(note):
    """只识别明确局部不适记录，不把备注关键词解释成诊断；无法识别时仍以疼痛分数暂停。"""
    hits = []
    for part in re.split(r"[，,。；;\n]", note):
        for pattern in (LOCAL_DISCOMFORT, LOCAL_ENGLISH):
            for match in pattern.finditer(part):
                before = part[max(0, match.start() - 6):match.start()]
                phrase = match.group()
                # “没有膝痛”“膝盖不疼”是明确否定；“不但膝痛”不是否定。
                if re.search(r"(?:没有|无|未出现|未感到|不再)(?:明显)?$|\b(?:no|without)\s*$", before, re.I):
                    continue
                if re.search(r"(?:不疼|不痛|无痛|没有疼|没有痛)", phrase):
                    continue
                hits.append(phrase)
    return sorted(set(hits))


def load(text, today):
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in (reader.fieldnames or [])]
    if any(not h for h in header) or len(header) != len(set(header)):
        raise InputError(1, "表头有空列名或重复列名；核对表头后再复盘")
    missing = [f for f in FIELDS if f not in header]
    if missing:
        raise InputError(1, "表头缺少 %s。第一行应当正好是：%s" % ("、".join(missing), ",".join(FIELDS)))
    reader.fieldnames = header
    rows, problems = [], []
    seen = set()
    for r in reader:
        line = reader.line_num
        if None in r or any(v is None for v in r.values()):
            problems.append("第 %d 行：列数与表头不一致，先核对逗号与引号" % line)
            continue
        if not any((v or "").strip() for v in r.values() if isinstance(v, str)):
            continue
        try:
            talk = (r["talk"] or "").strip()
            if talk in TALK_OK:
                talk = "整句"
            elif talk in TALK_HARD:
                talk = "几个词"
            else:
                raise ValueError("talk=%r 要填「整句」或「几个词」" % r["talk"])
            run_min = float((r["run_min"] or "").strip())
            if not 0 <= run_min <= 90:
                raise ValueError("run_min=%s 超出 0–90 分钟" % r["run_min"])
            rec = {
                "line": line,
                "date": parse_date(r["date"], today),
                "week": parse_int(r["week"], "week", 1, 52),
                "session": parse_int(r["session"], "session", 1, 3),
                "run_min": run_min,
                "talk": talk,
                "effort": parse_int(r["effort"], "effort", 0, 10),
                "pain": parse_int(r["pain"], "pain", 0, 10),
                "next": parse_int(r["next_morning"], "next_morning", 0, 10),
                "note": (r.get("note") or "").strip(),
            }
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("could not convert"):
                msg = "run_min=%r 要填分钟数" % r["run_min"]
            problems.append("第 %d 行：%s，已跳过这一行" % (line, msg))
            continue
        if rec["date"] is None:
            problems.append("第 %d 行：date=%r 认不出来（写成 09-02 或 2026-09-02），这一行照常复盘，但不参与中断判断"
                            % (line, r["date"]))
        key = (rec["week"], rec["session"])
        if key in seen:
            raise InputError(1, "第 %d 行：week=%d、session=%d 重复；核对记录，不能把同一次跑步当成三次" % (line, *key))
        seen.add(key)
        rows.append(rec)
    return rows, problems


def review(rows, today):
    weeks = {}
    for r in rows:
        weeks.setdefault(r["week"], []).append(r)
    any_stop = False
    for w in sorted(weeks):
        rs = sorted(weeks[w], key=lambda r: r["session"])
        pain = max(max(r["pain"], r["next"]) for r in rs)
        last = rs[-1]
        hard = last["talk"] != "整句" or last["effort"] >= 7
        next_worse = any(r["next"] > r["pain"] for r in rs)
        notes, basis = [], []
        red_hits = sorted({h for r in rs for h in red_words(r["note"])})
        local_hits = sorted({h for r in rs for h in local_discomfort(r["note"])})
        soreness = any(any(word in r["note"] for word in ("肌肉酸胀", "肌肉酸痛", "腿酸")) for r in rs)
        for r in rs:
            level = max(r["pain"], r["next"])
            if r["next"] > r["pain"] and level < 6:
                notes.append("第 %d 次：次日疼痛加重（%d 分，比跑时 %d 分更高），暂停跑步，不自动进阶；先核实恢复情况"
                             % (r["session"], r["next"], r["pain"]))
        if pain >= 6 or red_hits:
            act = "停跑，按红灯处理"
            basis.append("疼痛 %d 分，达到红灯（6 分及以上）" % pain if pain >= 6 else "")
            if red_hits:
                basis.append("备注里提到「%s」——如果当时确实出现，属于红灯症状" % "、".join(red_hits))
            basis.append("由医生判断，恢复跑步的时间也听医生或康复治疗师的")
            any_stop = True
        elif pain > 0 or local_hits:
            act = "暂停跑步，先核实疼痛与恢复"
            if pain > 0:
                basis.append("存在疼痛记录（最高 %d 分）；低分也不是继续跑步的许可" % pain)
            if local_hits:
                basis.append("备注提到局部不适「%s」；膝/关节痛不继续跑，不能自动进阶" % "、".join(local_hits))
            if next_worse:
                basis.append("次日疼痛加重，不能自动进阶")
            basis.append("脚本不能区分一般肌肉酸胀与伤痛；疼痛反复或持续应咨询医生或物理治疗师，严重疼痛或肿胀及时就医")
            any_stop = True
        elif any_stop:
            act = "暂停跑步，恢复情况需确认"
            basis.append("较早日志已有停跑信号；后续低分或零分不能自动证明伤痛已恢复，先人工核实")
        elif hard or soreness:
            act = "重复本周"
            if hard:
                why = []
                if last["talk"] != "整句":
                    why.append("说不了整句话")
                if last["effort"] >= 7:
                    why.append("吃力程度 %d 分（7 分及以上）" % last["effort"])
                basis.append("本周最后一次" + "、".join(why))
            if soreness:
                basis.append("备注有肌肉酸胀，不能据此判定正常恢复；先确认不适已缓解、没有局部或关节疼痛，不自动进阶")
            basis.append("重复不是失败")
        else:
            act = "进入下一周"
            basis.append("最后一次能说整句话、吃力程度 %d 分，疼痛最高 %d 分" % (last["effort"], pain))
            basis.append("只表示当前日志条件匹配，不保证进入新阶段；实际安排可以重复或延长")
        if len(rs) < 3 and act in ("进入下一周", "重复本周"):
            notes.append("本周只记了 %d 次：按计划跑完 3 次再下结论；漏一次顺延到下一个隔天，不在一天里补两次" % len(rs))
            if act == "进入下一周":
                act = "先跑完本周"
        print("第%d周 %d次 共跑%d分钟 最高疼痛%d → %s" % (w, len(rs), round(sum(r["run_min"] for r in rs)), pain, act))
        print("  依据：%s" % "；".join(b for b in basis if b))
        for n in notes:
            print("  提醒：%s" % n)

    dated = [r["date"] for r in rows if r["date"]]
    if any_stop:
        print("存在停跑信号：中断天数不构成恢复许可，不按距上次跑步的天数自动安排继续跑或进阶。")
    elif dated:
        gap = (today - max(dated)).days
        if gap >= 14:
            print("中断：距上次跑步 %d 天（两周以上）→ 退回两周再开始" % gap)
        elif gap >= 7:
            print("中断：距上次跑步 %d 天（一到两周）→ 退回一周再开始" % gap)
        elif gap >= 4:                         # 隔天跑、每周 3 次，正常最多隔 3 天
            print("中断：距上次跑步 %d 天（不到一周）→ 从断点接着跑" % gap)
    return 3 if any_stop else 0


def main(argv=None):
    p = FriendlyParser(description="跑步日志周复盘：进入下一周 / 重复本周 / 退回 / 停跑就医，并写明依据。",
                       epilog="退出码：0 无疼痛停跑信号；1 表头或内容有误；2 文件读不了；3 疼痛或停跑信号；130 手动中断。")
    p.add_argument("file", help="run_log.csv")
    p.add_argument("--today", help="今天的日期，如 2026-10-20；默认用电脑日期")
    args = p.parse_args(argv)
    try:
        today = dt.date.today()
        if args.today:
            try:
                today = dt.datetime.strptime(args.today.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise InputError(1, "--today 写成 2026-10-20 这样的格式")
        rows, problems = load(read_text(args.file), today)
        for msg in problems:
            print("数据问题：%s" % msg)
        if problems:
            raise InputError(1, "日志存在未确认记录；先修正全部数据问题，不生成继续跑步或进阶建议")
        if not rows:
            raise InputError(1, "没有一行有效记录：照表头逐列填写，数字只写阿拉伯数字，talk 写「整句」或「几个词」")
        code = review(rows, today)
        print("红灯症状（胸闷胸痛、心慌、头晕眼黑、冷汗、意识发懵）不等复盘，当场停下，严重时拨打 120。")
        return code
    except InputError as exc:
        sys.stdout.flush()
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有改动任何文件", file=sys.stderr)
        sys.exit(130)
