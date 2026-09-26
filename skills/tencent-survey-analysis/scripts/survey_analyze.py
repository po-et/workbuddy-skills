#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""问卷导出数据（腾讯问卷等导出的 CSV，或 Excel 另存的 CSV）的清洗与统计。

自动识别列的常见形态（导出格式以腾讯问卷当前版本为准，认不出的列会列出来请你确认）：
  单选   一列，取值是有限几个选项
  多选   ① 一列里用 ┋ | ; ； 、 , 等分隔多个选项；② 每个选项一列（列名形如「题干-选项」「题干:选项」「题干(选项)」），
         单元格是 1/0、选中/未选中、√ 或选项文字
  量表   一列 0–10 的整数，或「非常不满意…非常满意」「非常不同意…非常同意」这类标签
  开放题 一列自由文本
  元信息 序号、提交时间、答题时长、IP 等，不参与统计
输出：清洗记录、列识别结果、逐题频数与占比、量表均值/标准差/前两档占比（0–10 且题干含「推荐」时给 NPS）、
      交叉表（--cross 两列）、开放题关键词粗筛。

用法：
  python3 survey_analyze.py data.csv
  python3 survey_analyze.py data.csv --cross "Q1 您的身份" "Q5 整体满意度" --invited 300 --min-seconds 60
  python3 survey_analyze.py data.csv --type "Q9 年龄=numeric" --format json -o result.json

退出码：0 成功；1 参数错误（列名找不到、--type 写错等）；2 文件读写错误；130 用户中断。
"""

import argparse
import csv
import difflib
import io
import json
import math
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_INT = 0, 1, 2, 130

TYPES = ("single", "multi", "scale", "open", "numeric", "meta", "skip")
TYPE_LABEL = {"single": "单选", "multi": "多选", "scale": "量表", "open": "开放题", "numeric": "数值",
              "meta": "元信息", "skip": "跳过", "unknown": "待确认", "empty": "空列"}
MISSING = {"", "(跳过)", "（跳过）", "跳过", "(空)", "（空）", "-", "--", "—", "n/a", "na", "null", "none", "(未填)", "未填"}
UNSELECTED = {"0", "否", "未选中", "未选", "n", "no", "false", "f", "×"}
SELECTED = {"1", "是", "选中", "已选", "√", "✓", "✔", "y", "yes", "true", "t"}
STRICT_SEPS = ("┋", "|", ";", "；")
LOOSE_SEPS = ("、", ",", "，")
META_NAMES = set("序号 编号 答卷编号 答卷id id 提交时间 开始时间 结束时间 填写时间 答题时间 提交答卷时间 答题时长 用时 "
                 "所用时间 填写时长 ip ip地址 openid 用户id 用户标识 昵称 设备 浏览器 操作系统 ua useragent".split())
DURATION_RE = re.compile(r"(答题时长|用时|所用时间|填写时长|duration)", re.I)
SCALE_HINT = re.compile(r"(满意|评分|打分|评价|推荐|程度|同意|量表|分值|几分|星级|NPS|rating|score|likely)", re.I)
MULTI_HINT = re.compile(r"(多选|可多选|多项|multiple|select all)", re.I)
SINGLE_HINT = re.compile(r"(单选|single)", re.I)
OPEN_HINT = re.compile(r"(建议|意见|想法|为什么|原因|描述|说说|请注明|补充|反馈|comment|suggest)", re.I)
NPS_HINT = re.compile(r"(推荐|NPS|recommend)", re.I)
LIKERT = (
    {"非常不满意": 1, "很不满意": 1, "不满意": 2, "比较不满意": 2, "一般": 3, "满意": 4, "比较满意": 4, "非常满意": 5, "很满意": 5},
    {"非常不同意": 1, "完全不同意": 1, "不同意": 2, "比较不同意": 2, "一般": 3, "中立": 3, "不确定": 3, "同意": 4,
     "比较同意": 4, "非常同意": 5, "完全同意": 5},
    {"非常不重要": 1, "不重要": 2, "不太重要": 2, "一般": 3, "重要": 4, "比较重要": 4, "非常重要": 5},
)
STOP_EDGE = set("的了是在和也就都而及与着或被把让给对向从吗呢吧啊呀哦嗯很太更最还又再我你他她它们这那哪有没不能会要想说个些")
STOP_GRAMS = set("一个 一些 这个 那个 什么 没有 可以 觉得 希望 比较 非常 还是 就是 因为 所以 但是 如果 已经 不是 有点 一下 "
                 "自己 我们 你们 他们 大家 东西 时候 感觉 现在 目前 然后 其实 应该 需要 建议 问题 暂无 没什么".split())
EN_STOP = set("the a an and or to of in on for is are be it this that with as at by from i you we they my our "
              "your not no very so too can could would should more most please".split())


class UserError(Exception):
    def __init__(self, message, code=EXIT_ARGS):
        Exception.__init__(self, message)
        self.code = code


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_ARGS)


# ---------------------------------------------------------------- 读取与写出

def read_csv(path, encoding=None):
    try:
        raw = open(path, "rb").read()
    except FileNotFoundError:
        raise UserError("找不到文件：%s" % path, EXIT_FILE)
    except OSError as exc:
        raise UserError("读取失败：%s（%s）" % (path, exc), EXIT_FILE)
    if raw[:2] in (b"PK", b"\xd0\xcf"):
        raise UserError("这看起来是 Excel 文件（.xlsx/.xls），请在 Excel/WPS 里另存为「CSV UTF-8」再试", EXIT_FILE)
    text, enc = None, encoding
    if encoding:
        try:
            text = raw.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise UserError("按 %s 解码失败：%s" % (encoding, exc), EXIT_FILE)
    else:
        for enc in ("utf-8-sig", "gb18030"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise UserError("无法识别编码，请用 --encoding 指定（常见 utf-8 / gb18030）", EXIT_FILE)
    try:
        delim = csv.Sniffer().sniff(text[:4096], delimiters=",\t;").delimiter
    except csv.Error:
        delim = ","
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise UserError("只有表头没有数据行（或文件不是 CSV）：%s" % path, EXIT_FILE)
    header = [h.strip() or "未命名列%d" % (i + 1) for i, h in enumerate(rows[0])]
    seen = {}
    for i, h in enumerate(header):
        if h in seen:
            seen[h] += 1
            header[i] = "%s_%d" % (h, seen[h])
        else:
            seen[h] = 1
    data = []
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        data.append([c.strip() for c in r[:len(header)]])
    return header, data, enc.replace("-sig", "")


def atomic_write(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=folder)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise UserError("写文件失败：%s（%s）" % (path, exc), EXIT_FILE)


# ---------------------------------------------------------------- 小工具

def is_missing(v):
    return v.strip().lower() in MISSING


def to_num(v):
    try:
        x = float(v.replace("分", "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def parse_seconds(v):
    v = v.strip()
    if not v:
        return None
    m = re.match(r"^(\d+):(\d{1,2})(?::(\d{1,2}))?$", v)
    if m:
        a, b, c = int(m.group(1)), int(m.group(2)), m.group(3)
        return a * 3600 + b * 60 + int(c) if c is not None else a * 60 + b
    total, hit = 0.0, False
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(小时|时|分钟|分|秒|h|m|s)", v, re.I):
        hit = True
        total += float(num) * {"小时": 3600, "时": 3600, "h": 3600, "分钟": 60, "分": 60, "m": 60}.get(unit.lower(), 1)
    if hit:
        return total
    n = to_num(v)
    return n


def norm_header(h):
    return re.sub(r"[（(\[【].*?[)）\]】]", "", h).strip().lower().replace(" ", "")


def split_header(h):
    m = re.match(r"^(.*\S)\s*[（(\[【]([^（(\[【]+)[)）\]】]$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    idx = max(h.rfind(s) for s in ("—", "–", "-", "_", ":", "：", "|", "/"))
    if 0 < idx < len(h) - 1:
        stem, opt = h[:idx].strip(), h[idx + 1:].strip()
        if stem and opt:
            return stem, opt
    return None, None


def mean_sd(xs):
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
    return round(m, 2), round(sd, 2)


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def fmt_num(x):
    if x is None:
        return "—"
    return str(int(x)) if float(x).is_integer() else ("%.2f" % x).rstrip("0").rstrip(".")


# ---------------------------------------------------------------- 列识别

def detect_multi_sep(values, header):
    hinted = bool(MULTI_HINT.search(header))
    for sep in STRICT_SEPS + LOOSE_SEPS:
        with_sep = [v for v in values if sep in v]
        if not with_sep:
            continue
        tokens = [t.strip() for v in values for t in v.split(sep) if t.strip()]
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        distinct = len(freq)
        avg_len = sum(len(t) for t in tokens) / max(1, len(tokens))
        if sep in STRICT_SEPS:
            if distinct <= 25 and avg_len <= 20:
                return sep
        else:
            repeated = sum(1 for c in freq.values() if c >= 2)
            if (hinted or len(with_sep) >= 0.3 * len(values)) and distinct <= 15 and repeated >= 0.6 * distinct \
                    and avg_len <= 12:
                return sep
    return None


def likert_map(values):
    distinct = set(values)
    for table in LIKERT:
        if len(distinct) >= 2 and distinct <= set(table):
            return table
    return None


def detect_type(header, values):
    """values：去掉缺失后的取值。返回 (类型, 信息)。"""
    if norm_header(header) in META_NAMES or DURATION_RE.search(header):
        return "meta", {"why": "列名像元信息"}
    if not values:
        return "empty", {"why": "没有任何有效取值"}
    n = len(values)
    distinct = set(values)
    sep = detect_multi_sep(values, header)
    if sep:
        return "multi", {"sep": sep, "why": "单元格用「%s」分隔多个选项" % sep}
    nums = [to_num(v) for v in values]
    if all(x is not None for x in nums):
        ints = all(float(x).is_integer() for x in nums)
        if ints and set(nums) <= {0.0, 1.0}:
            return "single", {"why": "只有 0/1，按选中/未选中统计"}
        if ints and min(nums) >= 0 and max(nums) <= 10 and len(set(nums)) <= 11:
            span = "%s–%s 的整数" % (fmt_num(min(nums)), fmt_num(max(nums)))
            if SCALE_HINT.search(header):
                return "scale", {"why": span + "，题干含量表类用词"}
            return "scale", {"why": span + "（题干没有量表用词，已列入待确认）", "confirm": True}
        return "unknown", {"why": "数值型，取值 %s–%s 共 %d 种，不像选项也不像量表" % (
            fmt_num(min(nums)), fmt_num(max(nums)), len(set(nums))), "suggest": "numeric"}
    table = likert_map(values)
    if table:
        return "scale", {"why": "量表标签（按 1–5 换算）", "likert": table}
    ratio = len(distinct) / float(n)
    avg_len = sum(len(v) for v in values) / float(n)
    if SINGLE_HINT.search(header) and len(distinct) <= 30:
        return "single", {"why": "题干标注单选"}
    if MULTI_HINT.search(header) and len(distinct) <= 30:
        return "single", {"why": "题干标注多选但没有分隔符，按单选统计（已列入待确认）", "confirm": True}
    if len(distinct) <= 12 and ratio <= 0.6 and avg_len <= 25:
        return "single", {"why": "%d 种取值，重复度高" % len(distinct)}
    if OPEN_HINT.search(header) or avg_len >= 6 or ratio > 0.8:
        return "open", {"why": "自由文本（%d 条回答里有 %d 种不同内容）" % (n, len(distinct))}
    return "unknown", {"why": "%d 种取值、平均 %.0f 字，判断不了" % (len(distinct), avg_len), "suggest": "single 或 open"}


def is_binaryish(v, opt):
    s = v.strip().lower()
    return s in SELECTED or s in UNSELECTED or s in MISSING or s == opt.lower()


def find_groups(header, data, meta_idx):
    """相邻、同题干、单元格都是 0/1 或选项文字的列，归成一道「每选项一列」的多选题。"""
    groups, i = [], 0
    while i < len(header):
        stem, _ = split_header(header[i])
        if not stem or i in meta_idx:
            i += 1
            continue
        j = i
        while j + 1 < len(header) and split_header(header[j + 1])[0] == stem and (j + 1) not in meta_idx:
            j += 1
        if j > i:
            members = list(range(i, j + 1))
            ok = True
            for k in members:
                opt = split_header(header[k])[1]
                if opt.startswith("其他"):
                    continue
                if not all(is_binaryish(row[k], opt) for row in data):
                    ok = False
                    break
            if ok and any(row[k].strip().lower() not in UNSELECTED and not is_missing(row[k])
                          for row in data for k in members):
                groups.append({"stem": stem, "members": members, "options": [split_header(header[k])[1] for k in members]})
        i = j + 1
    return groups


# ---------------------------------------------------------------- 问题对象

class Question(object):
    def __init__(self, title, qtype, cols, info):
        self.title, self.type, self.cols, self.info = title, qtype, cols, info

    def answers(self, row):
        """返回这一行在本题的取值列表；未作答返回 []。"""
        if self.type == "multi" and len(self.cols) > 1:
            picked = []
            for k, opt in zip(self.cols, self.info["options"]):
                v = row[k].strip()
                if v and v.lower() not in UNSELECTED and not is_missing(v):
                    picked.append(opt)
            return picked
        v = row[self.cols[0]].strip()
        if is_missing(v):
            return []
        if self.type == "multi":
            return [t.strip() for t in v.split(self.info["sep"]) if t.strip()]
        if self.type == "scale" and not self.info.get("likert") and to_num(v) is not None:
            return [fmt_num(to_num(v))]
        return [v]

    def score(self, value):
        if self.info.get("likert"):
            return self.info["likert"].get(value)
        return to_num(value)

    def order(self, counts):
        if self.type == "scale":
            keys = set(counts)
            if not self.info.get("likert") and self.info.get("range"):
                lo, hi = self.info["range"]
                if float(lo).is_integer() and float(hi).is_integer() and hi - lo <= 10:
                    keys |= set(str(v) for v in range(int(lo), int(hi) + 1))
            return sorted(keys, key=lambda v: (self.score(v) if self.score(v) is not None else 1e9, v))
        return sorted(counts, key=lambda v: (-counts[v], v))


def build_questions(header, data, overrides, no_group):
    meta_idx = set(i for i, h in enumerate(header) if norm_header(h) in META_NAMES or DURATION_RE.search(h))
    groups = [] if no_group else find_groups(header, data, meta_idx)
    group_of = {}
    for g in groups:
        for k in g["members"]:
            group_of[k] = g
    col_override = {}
    for name, t in overrides.items():
        stems = [g for g in groups if g["stem"] == name]
        if stems:
            stems[0]["override"] = t
            continue
        idx = resolve_col(name, header)
        col_override[idx] = t
        if idx in group_of:
            g = group_of[idx]
            for k in g["members"]:
                group_of.pop(k, None)
            groups.remove(g)
    questions, done = [], set()
    for i, h in enumerate(header):
        if i in done:
            continue
        if i in group_of:
            g = group_of[i]
            done.update(g["members"])
            t = g.get("override", "multi")
            info = {"options": g["options"], "why": "%d 列同题干、单元格为 0/1 或选项文字" % len(g["members"])}
            others = [row[k] for k in g["members"] if g["options"][g["members"].index(k)].startswith("其他")
                      for row in data]
            info["other_text"] = sorted(set(v for v in others if v and not is_binaryish(v, "其他")))
            questions.append(Question(g["stem"], "multi" if t == "multi" else t, g["members"], info))
            continue
        values = [row[i] for row in data if not is_missing(row[i])]
        if i in col_override:
            t = col_override[i]
            info = {"why": "由 --type 指定"}
            if t == "multi":
                sep = detect_multi_sep(values, h) or next((s for s in STRICT_SEPS + LOOSE_SEPS
                                                           if any(s in v for v in values)), "┋")
                info["sep"] = sep
            if t == "scale":
                info["likert"] = likert_map(values)
                if not info["likert"] and any(to_num(v) is None for v in values):
                    raise UserError("「%s」里有非数字取值，不能按量表统计；可改成 single" % h)
            questions.append(Question(h, t, [i], info))
            continue
        t, info = detect_type(h, values)
        questions.append(Question(h, t, [i], info))
    return questions


def starts_with(full, name):
    """「Q1」匹配「Q1 您的身份」，但不匹配「Q10 年龄」。"""
    return full.startswith(name) and (len(full) == len(name) or not (name[-1].isdigit() and full[len(name)].isdigit()))


def not_found(name, pool, pref):
    if len(pref) > 1:
        return "找不到唯一的列「%s」；以它开头的有多个：%s" % (name, "、".join("「%s」" % c for c in pref[:5]))
    close = difflib.get_close_matches(name, sorted(set(pool)), n=3, cutoff=0.4)
    return "找不到列「%s」%s" % (name, ("；是不是：" + "、".join("「%s」" % c for c in close)) if close else "")


def resolve_col(name, header):
    """按列名（或唯一的开头几个字）找列，返回列下标。"""
    if name in header:
        return header.index(name)
    pref = [h for h in header if starts_with(h, name)]
    if len(pref) == 1:
        return header.index(pref[0])
    raise UserError(not_found(name, header, pref))


# ---------------------------------------------------------------- 清洗

def clean(header, data, args):
    log = [("导出原始行", len(data), "")]
    seen, kept, dup = set(), [], 0
    for row in data:
        key = tuple(row)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        kept.append(row)
    log.append(("去掉完全相同的行", -dup, "同一份答卷重复导出或重复提交"))
    data = kept
    if args.dedupe_by:
        idx = resolve_col(args.dedupe_by, header)
        seen, kept, dup = set(), [], 0
        for row in data:
            key = row[idx].strip()
            if key and key in seen:
                dup += 1
                continue
            seen.add(key)
            kept.append(row)
        log.append(("按「%s」去重" % header[idx], -dup, "保留首次出现"))
        data = kept
    if args.min_seconds is not None:
        if args.duration_col:
            idx = resolve_col(args.duration_col, header)
        else:
            cands = [i for i, h in enumerate(header) if DURATION_RE.search(h)]
            if not cands:
                raise UserError("没找到答题时长列，用 --duration-col 指定，或去掉 --min-seconds")
            idx = cands[0]
        kept, fast, unknown = [], 0, 0
        for row in data:
            s = parse_seconds(row[idx])
            if s is None:
                unknown += 1
                kept.append(row)
            elif s < args.min_seconds:
                fast += 1
            else:
                kept.append(row)
        note = "「%s」< %s 秒（阈值由你指定）" % (header[idx], fmt_num(args.min_seconds))
        if unknown:
            note += "；%d 行时长读不出，保留" % unknown
        log.append(("去掉答题过快", -fast, note))
        data = kept
    return data, log


def straightliners(questions, data):
    cols = [q for q in questions if q.type == "scale" and len(q.cols) == 1]
    vals = []
    for q in cols:
        scores = [q.score(v) for row in data for v in q.answers(row)]
        scores = [s for s in scores if s is not None]
        if scores and min(scores) >= 1 and max(scores) <= 5:
            vals.append(q)
    if len(vals) < 4:
        return [], len(vals)
    flagged = []
    for n, row in enumerate(data):
        answers = [q.score(q.answers(row)[0]) for q in vals if q.answers(row)]
        if len(answers) == len(vals) and len(set(answers)) == 1:
            flagged.append(n)
    return flagged, len(vals)


# ---------------------------------------------------------------- 统计

def keywords(texts, top):
    df, example, shown = {}, {}, {}
    for t in texts:
        grams = set()
        for run in re.findall(r"[\u4e00-\u9fff]+", t):
            for n in (2, 3, 4):
                for i in range(len(run) - n + 1):
                    g = run[i:i + n]
                    if g[0] in STOP_EDGE or g[-1] in STOP_EDGE or g in STOP_GRAMS:
                        continue
                    grams.add(g)
        for w in re.findall(r"[A-Za-z][A-Za-z0-9+#]+", t):
            if w.lower() not in EN_STOP:
                shown.setdefault(w.lower(), w)
                grams.add(w.lower())
        for g in grams:
            df[g] = df.get(g, 0) + 1
            example.setdefault(g, t)
    cands = [g for g, c in df.items() if c >= 2]
    keep = []
    for g in sorted(cands, key=lambda x: (-len(x), -df[x], x)):
        if any(g in h and df[h] >= 0.8 * df[g] for h in keep):
            continue
        keep.append(g)
    keep.sort(key=lambda g: (-df[g], -len(g), g))
    return [{"keyword": shown.get(g, g), "count": df[g], "example": example[g]} for g in keep[:top]]


def analyze_question(q, data, top):
    res = {"title": q.title, "type": q.type, "label": TYPE_LABEL.get(q.type, q.type), "why": q.info.get("why", "")}
    if q.type in ("meta", "skip", "empty", "unknown"):
        return res
    answered = [q.answers(row) for row in data]
    answered = [a for a in answered if a]
    n = len(answered)
    res["n"] = n
    if q.type == "open":
        texts = [a[0] for a in answered]
        res["keywords"] = keywords(texts, top)
        res["samples"] = [t for t in texts if len(t) >= 4][:3]
        return res
    if q.type == "numeric":
        xs = [to_num(a[0]) for a in answered if to_num(a[0]) is not None]
        m, sd = mean_sd(xs)
        res.update({"n": len(xs), "mean": m, "sd": sd, "median": median(xs),
                    "min": min(xs) if xs else None, "max": max(xs) if xs else None})
        return res
    counts = {}
    for a in answered:
        for v in a:
            counts[v] = counts.get(v, 0) + 1
    if q.type == "scale" and not q.info.get("likert"):
        q.info["range"] = scale_range([q.score(v) for v in counts if q.score(v) is not None])
    res["table"] = [{"option": v, "count": counts.get(v, 0), "pct": pct(counts.get(v, 0), n)} for v in q.order(counts)]
    if q.type == "multi":
        res["avg_picks"] = round(sum(len(a) for a in answered) / float(n), 2) if n else 0
        if q.info.get("other_text"):
            res["other_text"] = q.info["other_text"][:10]
    if q.type == "scale":
        xs = [q.score(a[0]) for a in answered if q.score(a[0]) is not None]
        m, sd = mean_sd(xs)
        lo, hi = (1, 5) if q.info.get("likert") else q.info["range"]
        top2 = [x for x in xs if x >= hi - 1]
        res.update({"mean": m, "sd": sd, "median": median(xs), "range": [lo, hi], "top2_pct": pct(len(top2), len(xs)),
                    "top2_from": hi - 1})
        if q.info.get("likert"):
            res["likert"] = "非常不…=1 … 非常…=5（按标签换算）"
        if (lo, hi) == (0, 10) and NPS_HINT.search(q.title):
            pro = pct(sum(1 for x in xs if x >= 9), len(xs))
            det = pct(sum(1 for x in xs if x <= 6), len(xs))
            res["nps"] = {"promoters_pct": pro, "detractors_pct": det, "nps": round(pro - det, 1)}
    return res


def scale_range(xs):
    if not xs:
        return 0, 0
    lo, hi = min(xs), max(xs)
    if lo >= 1 and hi <= 5:
        return 1, 5
    if lo >= 1 and hi <= 7:
        return 1, 7
    if lo >= 0 and hi <= 10:
        return 0, 10
    return lo, hi


def crosstab(qa, qb, data):
    cells, row_n, b_counts, a_counts, b_scores = {}, {}, {}, {}, {}
    for row in data:
        av, bv = qa.answers(row), qb.answers(row)
        if not av or not bv:
            continue
        for a in av:
            row_n[a] = row_n.get(a, 0) + 1
            a_counts[a] = a_counts.get(a, 0) + 1
            for b in bv:
                cells[(a, b)] = cells.get((a, b), 0) + 1
            if qb.type == "scale" and qb.score(bv[0]) is not None:
                b_scores.setdefault(a, []).append(qb.score(bv[0]))
        for b in bv:
            b_counts[b] = b_counts.get(b, 0) + 1
    rows = [a for a in qa.order(a_counts) if a in row_n]
    cols = qb.order(b_counts)
    out = []
    for a in rows:
        n = row_n[a]
        out.append({"row": a, "n": n, "small": n < 5,
                    "cells": [{"col": b, "count": cells.get((a, b), 0), "row_pct": pct(cells.get((a, b), 0), n)}
                              for b in cols],
                    "mean": mean_sd(b_scores.get(a, []))[0] if qb.type == "scale" else None})
    return {"a": qa.title, "b": qb.title, "cols": cols, "rows": out, "b_is_scale": qb.type == "scale",
            "b_is_multi": qb.type == "multi", "a_is_multi": qa.type == "multi"}


# ---------------------------------------------------------------- 输出

def cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def short(t, n=30):
    t = t.replace("\n", " ")
    return t if len(t) <= n else t[:n] + "…"


def render_md(doc):
    L = ["# 问卷数据分析：%s" % doc["source"], ""]
    L += ["## 样本与清洗", "", "| 步骤 | 行数 | 说明 |", "|---|---|---|"]
    for step, n, note in doc["cleaning"]:
        L.append("| %s | %s | %s |" % (step, n if step == "导出原始行" else "%+d" % n, cell(note)))
    L.append("| **有效样本** | **%d** | |" % doc["valid_n"])
    s = doc["sample"]
    L.append("")
    if s.get("invited"):
        L.append("回收率 = 回收 %d ÷ 发放 %d = %.1f%%；有效率 = 有效 %d ÷ 回收 %d = %.1f%%。" % (
            s["collected"], s["invited"], s["response_rate"], doc["valid_n"], s["collected"], s["valid_rate"]))
    else:
        L.append("没有给 --invited（发放数），不计算回收率；有效率 = 有效 %d ÷ 回收 %d = %.1f%%。" % (
            doc["valid_n"], s["collected"], s["valid_rate"]))
    if s["straightline"]["checked"]:
        L.append("直线作答（%d 道 1–5 分量表全部同一分值）：%d 行%s。" % (
            s["straightline"]["scale_cols"], s["straightline"]["flagged"],
            "，已删除" if s["straightline"]["dropped"] else "，仅标记未删除（加 --drop-straightline 删除）"))
    if doc["valid_n"] < 30:
        L.append("有效样本不足 30：只报人数和占比，不做推断，百分比请同时写出人数。")
    L += ["", "## 列识别结果", "", "| 列 / 题 | 识别为 | 依据 |", "|---|---|---|"]
    for q in doc["questions"]:
        L.append("| %s | %s | %s |" % (cell(q["title"]), q["label"], cell(q["why"])))
    L += ["", "## 需要你确认的列", ""]
    if doc["confirm"]:
        for c in doc["confirm"]:
            L.append("- 「%s」：%s。%s" % (c["title"], c["why"], c["how"]))
    else:
        L.append("（无）")
    L += ["", "## 逐题结果"]
    for q in doc["questions"]:
        if q["type"] in ("meta", "skip", "empty", "unknown"):
            continue
        L.append("")
        if q["type"] == "open":
            L.append("### %s（开放题，n=%d）" % (q["title"], q["n"]))
            L.append("")
            if q["keywords"]:
                L += ["关键词粗筛（2–4 字片段按提及人数排序，机器粗切，需人工复核）：", "",
                      "| 关键词 | 提及人数 | 占本题回答 | 例句 |", "|---|---|---|---|"]
                L += ["| %s | %d | %.1f%% | %s |" % (cell(k["keyword"]), k["count"], pct(k["count"], q["n"]),
                                                  cell(short(k["example"]))) for k in q["keywords"]]
            else:
                L.append("回答太少或太分散，没有被 2 人以上共同提到的关键词。")
            if q["samples"]:
                L += ["", "示例回答（前 3 条）："] + ["- %s" % cell(short(t, 60)) for t in q["samples"]]
            continue
        if q["type"] == "numeric":
            L.append("### %s（数值，n=%d）" % (q["title"], q["n"]))
            L.append("")
            L.append("均值 %s，标准差 %s，中位数 %s，最小 %s，最大 %s。" % tuple(
                fmt_num(q[k]) for k in ("mean", "sd", "median", "min", "max")))
            continue
        head = {"single": "单选", "multi": "多选", "scale": "量表"}[q["type"]]
        extra = ""
        if q["type"] == "multi":
            extra = "，人均选 %s 项；占比按作答人数算，合计可超过 100%%" % fmt_num(q["avg_picks"])
        if q["type"] == "scale":
            extra = "，量程 %s–%s" % (fmt_num(q["range"][0]), fmt_num(q["range"][1]))
        L.append("### %s（%s，n=%d%s）" % (q["title"], head, q["n"], extra))
        L.append("")
        if q["type"] == "scale":
            L.append("均值 %.2f，标准差 %.2f，中位数 %s，前两档（≥%s）占 %.1f%%%s。" % (
                q["mean"], q["sd"], fmt_num(q["median"]), fmt_num(q["top2_from"]), q["top2_pct"],
                "；" + q["likert"] if q.get("likert") else ""))
            if q.get("nps"):
                L.append("NPS = 推荐者（9–10）%.1f%% − 贬损者（0–6）%.1f%% = %.1f。" % (
                    q["nps"]["promoters_pct"], q["nps"]["detractors_pct"], q["nps"]["nps"]))
            L.append("")
        L += ["| 选项 | 人数 | 占比 |", "|---|---|---|"]
        L += ["| %s | %d | %.1f%% |" % (cell(r["option"]), r["count"], r["pct"]) for r in q["table"]]
        if q.get("other_text"):
            L.append("")
            L.append("「其他」填写内容（最多 10 条）：" + "；".join(short(t, 20) for t in q["other_text"]))
    for ct in doc["crosstabs"]:
        L += ["", "## 交叉表：%s × %s" % (ct["a"], ct["b"]), ""]
        heads = [cell(c) for c in ct["cols"]]
        extra_head = " | 均值" if ct["b_is_scale"] else ""
        L.append("| %s ＼ %s | %s | n%s |" % (cell(short(ct["a"], 12)), cell(short(ct["b"], 12)), " | ".join(heads),
                                           extra_head))
        L.append("|" + "---|" * (len(heads) + 2 + (1 if ct["b_is_scale"] else 0)))
        for r in ct["rows"]:
            cells = " | ".join("%d（%.0f%%）" % (c["count"], c["row_pct"]) for c in r["cells"])
            mean = ""
            if ct["b_is_scale"]:
                mean = " | %.2f" % r["mean"] if r["mean"] is not None else " | —"
            L.append("| %s%s | %s | %d%s |" % (cell(r["row"]), " *" if r["small"] else "", cells, r["n"], mean))
        L.append("")
        L.append("括号内是行百分比；* 表示该行 n<5，谨慎解读。%s" % (
            "列变量是多选，行百分比合计可超过 100%。" if ct["b_is_multi"] else ""))
    return "\n".join(L) + "\n"


def parse_overrides(items):
    out = {}
    for item in items:
        if "=" not in item:
            raise UserError("--type 的写法是 列名=类型，收到：%r" % item)
        name, t = item.rsplit("=", 1)
        name, t = name.strip(), t.strip().lower()
        if t not in TYPES:
            raise UserError("--type 类型只能是 %s，收到：%r" % ("/".join(TYPES), t))
        out[name] = t
    return out


def main(argv=None):
    ap = ArgParser(description="问卷导出 CSV 清洗与统计：单选/多选/量表/开放题识别、频数占比、量表均值、交叉表、关键词粗筛")
    ap.add_argument("path", help="导出的 CSV（Excel 请先另存为 CSV UTF-8）")
    ap.add_argument("--type", action="append", default=[], metavar="列名=类型",
                    help="手动指定列类型：" + "/".join(TYPES) + "；可写题干（每选项一列的多选题）")
    ap.add_argument("--cross", nargs=2, action="append", default=[], metavar=("行变量", "列变量"),
                    help="交叉表，可重复；列名可写开头几个字，唯一匹配即可")
    ap.add_argument("--invited", type=int, help="发放份数（定向发放时才有），用于计算回收率")
    ap.add_argument("--min-seconds", type=float, help="答题时长低于该秒数的答卷视为无效（不给就不过滤）")
    ap.add_argument("--duration-col", help="答题时长列名（默认自动找含「答题时长/用时」的列）")
    ap.add_argument("--dedupe-by", help="按这一列去重（如用户标识列），保留首次出现")
    ap.add_argument("--drop-straightline", action="store_true", help="删除直线作答（默认只标记）")
    ap.add_argument("--no-group", action="store_true", help="不把「每选项一列」的相邻列合并成多选题")
    ap.add_argument("--top", type=int, default=10, help="开放题关键词最多列几个，默认 10")
    ap.add_argument("--encoding", help="文件编码；默认先试 utf-8 再试 gb18030")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("-o", "--output", help="写入文件（先写临时文件再替换）；不给就打印")
    args = ap.parse_args(argv)
    try:
        if args.invited is not None and args.invited <= 0:
            raise UserError("--invited 必须是正整数")
        if args.min_seconds is not None and args.min_seconds < 0:
            raise UserError("--min-seconds 不能为负数")
        if args.top < 1:
            raise UserError("--top 至少为 1")
        overrides = parse_overrides(args.type)
        header, raw, enc = read_csv(args.path, args.encoding)
        data, log = clean(header, raw, args)
        if not data:
            raise UserError("清洗后没有剩下任何答卷，检查 --min-seconds 等阈值")
        questions = build_questions(header, data, overrides, args.no_group)
        flagged, scale_cols = straightliners(questions, data)
        dropped = False
        if flagged and args.drop_straightline:
            data = [row for n, row in enumerate(data) if n not in set(flagged)]
            log.append(("去掉直线作答", -len(flagged), "%d 道 1–5 分量表全部同一分值" % scale_cols))
            dropped = True
        results = [analyze_question(q, data, args.top) for q in questions]
        confirm = []
        for q in questions:
            if q.type == "unknown":
                how = "要当数值统计：--type \"%s=numeric\"" % q.title if q.info.get("suggest") == "numeric" else \
                    "请用 --type \"%s=single\" 或 =open 指定" % q.title
                confirm.append({"title": q.title, "why": q.info["why"], "how": how + "；不需要就 =skip"})
            elif q.type == "empty":
                confirm.append({"title": q.title, "why": "整列为空", "how": "确认是否导出不完整，或这道题没人答"})
            elif q.info.get("confirm"):
                confirm.append({"title": q.title, "why": q.info["why"],
                                "how": "如果它其实是普通选项或计数，用 --type \"%s=single\"" % q.title})
        crosstabs = []
        for a, b in args.cross:
            qa, qb = find_question(a, questions, header), find_question(b, questions, header)
            for q in (qa, qb):
                if q.type not in ("single", "multi", "scale"):
                    raise UserError("交叉表只支持单选/多选/量表，「%s」是%s；可用 --type 改类型" % (
                        q.title, TYPE_LABEL.get(q.type, q.type)))
            crosstabs.append(crosstab(qa, qb, data))
        collected = len(raw)
        doc = {
            "source": os.path.basename(args.path), "encoding": enc, "cleaning": log, "valid_n": len(data),
            "sample": {"collected": collected, "invited": args.invited,
                       "response_rate": pct(collected, args.invited) if args.invited else None,
                       "valid_rate": pct(len(data), collected),
                       "straightline": {"checked": scale_cols >= 4, "scale_cols": scale_cols, "flagged": len(flagged),
                                        "dropped": dropped}},
            "questions": results, "confirm": confirm, "crosstabs": crosstabs,
        }
        text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_md(doc)
        if args.output:
            atomic_write(args.output, text)
            sys.stderr.write("已写入 %s\n" % args.output)
        else:
            sys.stdout.write(text)
        return EXIT_OK
    except UserError as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return exc.code


def find_question(name, questions, header):
    """--cross 用：先按题目（含「每选项一列」多选题的题干）找，再按列找到所属题目。"""
    titles = [q.title for q in questions]
    if name in titles:
        return questions[titles.index(name)]
    pref = [t for t in titles if starts_with(t, name)]
    if len(pref) == 1:
        return questions[titles.index(pref[0])]
    if len(pref) > 1:
        raise UserError(not_found(name, titles, pref))
    try:
        idx = resolve_col(name, header)
    except UserError:
        raise UserError(not_found(name, titles + header, []))
    for q in questions:
        if idx in q.cols:
            return q
    raise UserError("找不到题目「%s」" % name)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(EXIT_INT)
