#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""腾讯会议导出转写文本的宽松解析：按发言人聚合统计，挑出待办/决议/未决问题候选句，输出规范化转写。

逐行尝试这些常见形态（导出格式随版本变化，所以不假设固定格式）：
  A  张三 00:12:34          发言人 + 时间单独一行，内容在下面几行（也认「00:12:34 张三」）
  B  [00:12] 张三：内容      方括号时间在前（也认【】）
  C  张三（00:12:34）：内容   括号时间在后；冒号后没内容时，内容在下面几行
  D  00:12:34 张三：内容     时间在前、冒号分隔
  E  张三：内容              没有时间；同名出现 ≥2 次、且不是「结论：」这类小标题时才认
认不出的行原样保留并计数；--speakers 限定发言人名单，--pattern 传自定义正则（命名分组 name，可选 time/text）。

用法：
  python3 parse_transcript.py 转写.txt
  python3 parse_transcript.py 转写.txt --rename 发言人2=刘洋 --normalized 规范化.txt -o 解析.md
  python3 parse_transcript.py 转写.txt --format json

退出码：0 成功；1 参数错误；2 文件读写错误；3 一段发言都没认出来（格式不认识）；130 用户中断。
"""

import argparse
import json
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_NOPARSE, EXIT_INT = 0, 1, 2, 3, 130

TIME = r"(?:\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s+)?\d{1,2}:\d{2}(?::\d{2})?"
NAME = r"[^\s:：\[\]【】()（）\d<>《》\"“”'][^:：\[\]【】<>《》]{0,23}?"

PATTERNS = [
    ("B", re.compile(r"^[\[【]\s*(?P<time>%s)\s*[\]】]\s*(?P<name>%s)\s*[:：]\s*(?P<text>.*)$" % (TIME, NAME))),
    ("C", re.compile(r"^(?P<name>%s)\s*[（(]\s*(?P<time>%s)\s*[)）]\s*[:：]?\s*(?P<text>.*)$" % (NAME, TIME))),
    ("D", re.compile(r"^(?P<time>%s)\s+(?P<name>%s)\s*[:：]\s*(?P<text>.*)$" % (TIME, NAME))),
    ("A", re.compile(r"^(?P<name>%s)\s+(?P<time>%s)\s*$" % (NAME, TIME))),
    ("A", re.compile(r"^(?P<time>%s)\s+(?P<name>%s)\s*$" % (TIME, NAME))),
    ("E", re.compile(r"^(?P<name>%s)\s*[:：]\s*(?P<text>.+)$" % NAME)),
]

META_RE = re.compile(r"^(会议主题|主题|会议名称|会议时间|时间|日期|会议号|会议ID|会议 ID|参会人员?|与会人员?|"
                     r"主持人|记录人|地点|会议链接)\s*[:：]\s*(.*)$")
NOISE_RE = re.compile(r"^(?:[-—_=*#~·•.。\s]{3,}|[-—_=*#~·•\s]*(?:第\s*\d+\s*页(?:\s*/\s*共\s*\d+\s*页)?"
                      r"|Page\s*\d+(?:\s*of\s*\d+)?)[-—_=*#~·•\s]*|%s)$" % TIME, re.I)
BRACKETED_RE = re.compile(r"^[(（\[【][^)）\]】]*[)）\]】]$")
LABELS = set("结论 决议 决定 待办 行动项 TODO 议题 主题 会议主题 时间 会议时间 日期 地点 备注 问题 风险 背景 目标 "
             "参会人 参会人员 与会人 记录人 会议号 链接 附件 说明 注意 补充 另外 然后 比如 例如 总结 结果 原因 "
             "方案 进展 计划 下一步 首先 其次 最后 第一 第二 第三 http https".split())

ACTION_CUES = ("我来", "我负责", "我跟进", "我去", "我这边", "负责", "跟进", "落实", "牵头", "推进", "待办", "会后",
               "截止", "TODO", "DDL", "deadline", "I'll", "I will", "action item", "follow up")
FIRST_PERSON = ("我来", "我负责", "我跟进", "我去", "我这边", "I'll", "I will")
DECISION_CUES = ("决定", "定了", "定下来", "就这么定", "就这么办", "结论是", "结论：", "拍板", "达成一致", "同意",
                 "通过", "就按", "统一按", "采用", "agreed", "decided")
OPEN_CUES = ("待定", "再议", "再讨论", "还没定", "没定", "不确定", "待确认", "回头再", "下次再", "悬而未决",
             "不清楚", "要不要", "是否", "谁来", "怎么办", "TBD", "open question")
DEADLINE_RE = re.compile(
    r"(\d{1,2}\s*月\s*\d{1,2}\s*[日号]?(?:前|之前|以前)?"
    r"|\d{1,2}/\d{1,2}(?:前|之前)?"
    r"|(?<!上)(?:本|这|下下?)?(?:周|星期|礼拜)[一二三四五六日天](?:上午|中午|下午|晚上|下班)?(?:前|之前|以前)?"
    r"|(?:本|这|下下?)(?:周|个?月|季度)(?:内|底|末|初)?(?:前|之前)?"
    r"|(?:今天|明天|后天|今晚|明早|月底|月初|年底|周末)(?:上午|中午|下午|晚上|下班)?(?:[\d:：\s点半]*)?(?:前|之前|以前)?"
    r"|\d+\s*个?(?:工作日|天|周)(?:内|之内)"
    r"|by (?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day|by EOD|by end of (?:day|week))", re.I)
OWNER_RE = re.compile(r"(?:(?:由|让|请|交给)\s*([\u4e00-\u9fa5]{2,3}?|[A-Za-z]+)\s*(?:来|负责|跟进|处理|牵头|对接|看|出)"
                      r"|@\s*([\u4e00-\u9fa5A-Za-z]{2,12}))")
PRONOUNS = set("我们 你们 他们 她们 大家 谁来 各位 咱们".split())
SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])|(?<=[.])\s+")


class UserError(Exception):
    def __init__(self, message, code=EXIT_ARGS):
        Exception.__init__(self, message)
        self.code = code


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_ARGS)


# ---------------------------------------------------------------- 读取

def read_text(path, encoding=None):
    try:
        raw = sys.stdin.buffer.read() if path == "-" else open(path, "rb").read()
    except FileNotFoundError:
        raise UserError("找不到文件：%s" % path, EXIT_FILE)
    except OSError as exc:
        raise UserError("读取失败：%s（%s）" % (path, exc), EXIT_FILE)
    if encoding:
        try:
            return raw.decode(encoding), encoding
        except (LookupError, UnicodeDecodeError) as exc:
            raise UserError("按 %s 解码失败：%s" % (encoding, exc), EXIT_FILE)
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise UserError("无法识别文件编码，请用 --encoding 指定（常见 utf-8 / gb18030 / utf-16）", EXIT_FILE)


def atomic_write(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=folder)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            if "tmp" in locals() and os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise UserError("写文件失败：%s（%s）" % (path, exc), EXIT_FILE)


# ---------------------------------------------------------------- 解析

def base_name(name):
    return re.sub(r"\s*[（(][^)）]*[)）]\s*$", "", name.strip()).strip()


def time_info(text):
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?$", text or "")
    if not m:
        return None, None, 0
    a, b, c = m.group(1), m.group(2), m.group(3)
    has_date = bool(re.match(r"^\d{4}", text))
    if c is not None:
        return m.group(0), int(a) * 3600 + int(b) * 60 + int(c), 3
    return m.group(0), int(a) * 60 + int(b), 3 if has_date else 2


def candidate(line, custom):
    """返回 (形态, 名字, 时间文本, 正文) 或 None。"""
    if custom is not None:
        m = custom.match(line)
        if m and m.groupdict().get("name"):
            g = m.groupdict()
            return "P", g["name"].strip(), (g.get("time") or "").strip(), (g.get("text") or "").strip()
    for kind, rx in PATTERNS:
        m = rx.match(line)
        if not m:
            continue
        g = m.groupdict()
        text = (g.get("text") or "").strip()
        if kind == "E" and text.startswith("//"):
            return None
        return kind, g["name"].strip(), (g.get("time") or "").strip(), text
    return None


def parse(lines, renames, speakers, custom):
    cands = [None] * len(lines)
    counts = {}
    strong_names = set()
    for i, line in enumerate(lines):
        if not line.strip() or NOISE_RE.match(line.strip()) or BRACKETED_RE.match(line.strip()):
            continue
        c = candidate(line.strip(), custom)
        if c:
            cands[i] = c
            b = base_name(c[1])
            counts[b] = counts.get(b, 0) + 1
            if c[0] in ("B", "C", "D", "P") or (c[0] == "A" and time_info(c[2])[2] == 3):
                strong_names.add(b)

    outside = {}

    def accept(c):
        kind, name, t, _ = c
        b = base_name(name)
        if speakers:
            ok = b in speakers or renames.get(b, b) in speakers
            if not ok and kind in ("B", "C", "D", "P"):
                outside[b] = outside.get(b, 0) + 1
            return ok
        if b in LABELS or len(b) > 16:
            return False
        if kind in ("B", "C", "D", "P"):
            return True
        if kind == "A":
            return time_info(t)[2] == 3 or counts.get(b, 0) >= 2
        return b in strong_names or counts.get(b, 0) >= 2  # E

    turns, meta, unparsed = [], [], []
    stats = {"blank": 0, "continuation": 0, "kinds": {}}
    current = None
    for i, raw in enumerate(lines):
        line_no = i + 1
        line = raw.strip()
        if not line:
            stats["blank"] += 1
            continue
        c = cands[i]
        if c and accept(c):
            kind, name, t, text = c
            b = base_name(name)
            shown, secs, parts = time_info(t)
            current = {"line": line_no, "speaker": renames.get(b, b), "raw_name": name, "time": shown or "",
                       "secs": secs, "parts": parts, "kind": kind, "segments": []}
            if text:
                current["segments"].append((line_no, text))
            turns.append(current)
            stats["kinds"][kind] = stats["kinds"].get(kind, 0) + 1
            continue
        if current is None:
            m = META_RE.match(line)
            (meta if m else unparsed).append((line_no, raw.rstrip("\n")))
            continue
        if NOISE_RE.match(line) or BRACKETED_RE.match(line) or (c and base_name(c[1]) in LABELS):
            unparsed.append((line_no, raw.rstrip("\n")))
            continue
        current["segments"].append((line_no, line))
        stats["continuation"] += 1
    for t in turns:
        t["text"] = join_segments([s for _, s in t["segments"]])
    stats["outside_speakers"] = outside
    return turns, meta, unparsed, stats


def join_segments(parts):
    out = ""
    for p in parts:
        if out and not (is_cjk(out[-1]) and is_cjk(p[0])):
            out += " "
        out += p
    return out


def is_cjk(ch):
    return "\u4e00" <= ch <= "\u9fff" or ch in "，。！？；：、）》」"


# ---------------------------------------------------------------- 统计与候选

def speaker_stats(turns):
    exact = bool(turns) and all(t["parts"] == 3 for t in turns if t["secs"] is not None) and \
        any(t["secs"] is not None for t in turns)
    by = {}
    for idx, t in enumerate(turns):
        s = by.setdefault(t["speaker"], {"speaker": t["speaker"], "turns": 0, "chars": 0, "first": "", "last": "",
                                         "est_seconds": 0, "est_turns": 0, "empty_turns": 0})
        s["turns"] += 1
        n = len(re.sub(r"\s", "", t["text"]))
        s["chars"] += n
        if n == 0:
            s["empty_turns"] += 1
        if t["time"]:
            s["first"] = s["first"] or t["time"]
            s["last"] = t["time"]
        nxt = turns[idx + 1] if idx + 1 < len(turns) else None
        if exact and t["secs"] is not None and nxt is not None and nxt["secs"] is not None \
                and nxt["secs"] >= t["secs"]:
            s["est_seconds"] += nxt["secs"] - t["secs"]
            s["est_turns"] += 1
    total = sum(s["chars"] for s in by.values()) or 1
    rows = sorted(by.values(), key=lambda s: (-s["chars"], s["speaker"]))
    for s in rows:
        s["share"] = round(100.0 * s["chars"] / total, 1)
        if not exact or s["est_turns"] == 0:
            s["est_seconds"] = None
    return rows, exact


def find_candidates(turns):
    names = sorted({t["speaker"] for t in turns}, key=len, reverse=True)
    action, decision, open_q = [], [], []
    for t in turns:
        for line_no, seg in t["segments"]:
            for sent in [s.strip() for s in SENT_SPLIT.split(seg) if s and s.strip()]:
                low = sent.lower()
                base = {"line": line_no, "time": t["time"], "speaker": t["speaker"], "text": sent}
                deadlines = [m.group(0).strip() for m in DEADLINE_RE.finditer(sent)]
                has_cue = any(c.lower() in low for c in ACTION_CUES)
                due = any(re.search(r"(前|之前|以前|内|底|末)$", d) or d.lower().startswith("by") for d in deadlines)
                if has_cue or due:
                    owners = []
                    if any(c.lower() in low for c in FIRST_PERSON):
                        owners.append(t["speaker"])
                    for n in names:
                        if n in sent and n not in owners and n != t["speaker"]:
                            owners.append(n)
                    for m in OWNER_RE.finditer(sent):
                        who = m.group(1) or m.group(2)
                        if who in PRONOUNS or any(who in o or o in who for o in owners):
                            continue
                        owners.append(who)
                    item = dict(base)
                    item["owner_hint"] = owners
                    item["due_hint"] = deadlines
                    action.append(item)
                if any(c.lower() in low for c in DECISION_CUES):
                    decision.append(dict(base))
                if any(c.lower() in low for c in OPEN_CUES):
                    open_q.append(dict(base))
    return action, decision, open_q


# ---------------------------------------------------------------- 输出

def fmt_secs(n):
    if n is None:
        return "—"
    h, rem = divmod(int(n), 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_md(src, enc, lines, turns, meta, unparsed, stats, rows, exact, action, decision, open_q, max_unparsed):
    times = [t["time"] for t in turns if t["time"]]
    kinds = "、".join("%s×%d" % (k, v) for k, v in sorted(stats["kinds"].items()))
    out = ["# 转写解析结果：%s" % src, ""]
    out.append("- 编码 %s；共 %d 行（空行 %d）" % (enc.replace("-sig", ""), len(lines), stats["blank"]))
    out.append("- 识别发言 %d 段（行形态 %s）；续行并入上一段 %d 行；元信息 %d 行；**未解析 %d 行（原样保留在文末）**"
               % (len(turns), kinds or "无", stats["continuation"], len(meta), len(unparsed)))
    out.append("- 发言人 %d 位；时间范围 %s – %s" % (len(rows), times[0] if times else "—", times[-1] if times else "—"))
    out += ["", "## 按发言人统计", "", "| 发言人 | 发言段数 | 字数 | 字数占比 | 首次 | 末次 | 估算时长 |", "|---|---|---|---|---|---|---|"]
    for s in rows:
        out.append("| %s | %d | %d | %.1f%% | %s | %s | %s |" % (cell(s["speaker"]), s["turns"], s["chars"], s["share"],
                                                               s["first"] or "—", s["last"] or "—", fmt_secs(s["est_seconds"])))
    if not exact:
        out.append("")
        out.append("估算时长：时间戳只有两段或缺失，分不清「分:秒」还是「时:分」，不估算。")
    else:
        out.append("")
        out.append("估算时长 = 本段开始到紧接的下一段开始的间隔之和（下一段没有时间就不算），含停顿，仅供参考。")
    out += ["", "## 待办候选（负责人、截止时间都要人工确认）", "",
            "| # | 行 | 时间 | 发言人 | 原句 | 负责人线索 | 截止线索 |", "|---|---|---|---|---|---|---|"]
    for i, a in enumerate(action, 1):
        out.append("| %d | L%d | %s | %s | %s | %s | %s |" % (i, a["line"], a["time"] or "—", cell(a["speaker"]), cell(a["text"]),
                                                          cell("、".join(a["owner_hint"]) or "[待确认]"),
                                                          cell("、".join(a["due_hint"]) or "[待确认]")))
    for title, items in (("决议候选", decision), ("未决问题候选", open_q)):
        out += ["", "## %s" % title, "", "| # | 行 | 时间 | 发言人 | 原句 |", "|---|---|---|---|---|"]
        for i, a in enumerate(items, 1):
            out.append("| %d | L%d | %s | %s | %s |" % (i, a["line"], a["time"] or "—", cell(a["speaker"]), cell(a["text"])))
    out += ["", "## 元信息行（原样）", ""]
    out += ["- L%d：%s" % (n, t) for n, t in meta] or ["（无）"]
    out += ["", "## 未解析行（原样保留，共 %d 行）" % len(unparsed), ""]
    shown = unparsed[:max_unparsed]
    out += ["- L%d：%s" % (n, t) for n, t in shown] or ["（无）"]
    if len(unparsed) > len(shown):
        out.append("- ……其余 %d 行见 --format json" % (len(unparsed) - len(shown)))
    return "\n".join(out) + "\n"


def render_normalized(lines, turns, meta, unparsed):
    events = [(t["line"], "[%s] %s：%s" % (t["time"] or "--:--", t["speaker"], t["text"])) for t in turns]
    events += [(n, "〔元信息 L%d〕%s" % (n, t.strip())) for n, t in meta]
    events += [(n, "〔未解析 L%d〕%s" % (n, t.strip())) for n, t in unparsed]
    return "\n".join(text for _, text in sorted(events)) + "\n"


def parse_pairs(values, flag):
    out = {}
    for v in values or []:
        for item in re.split(r"[,，]", v):
            if not item.strip():
                continue
            if "=" not in item:
                raise UserError("%s 的写法是 旧名=新名，收到：%r" % (flag, item))
            old, new = [x.strip() for x in item.split("=", 1)]
            if not old or not new:
                raise UserError("%s 两边都不能为空：%r" % (flag, item))
            out[old] = new
    return out


def main(argv=None):
    ap = ArgParser(description="腾讯会议转写文本宽松解析：发言人统计 + 待办/决议/未决问题候选 + 规范化转写")
    ap.add_argument("path", help="转写文本路径（.txt/.md 等纯文本；写 - 表示从标准输入读）")
    ap.add_argument("--encoding", help="文件编码；默认依次尝试 utf-8、gb18030，带 BOM 的 utf-16 自动识别")
    ap.add_argument("--rename", action="append", default=[], help="改名，如 发言人2=刘洋；可重复或用逗号分隔")
    ap.add_argument("--speakers", help="限定发言人名单（逗号分隔），给了就只认名单里的名字")
    ap.add_argument("--pattern", help="自定义行正则，须含命名分组 name，可选 time、text")
    ap.add_argument("--format", choices=("md", "json"), default="md", help="输出格式，默认 md")
    ap.add_argument("-o", "--output", help="结果写入文件（先写临时文件再替换）；不给就打印")
    ap.add_argument("--normalized", help="另存规范化转写：每段一行「[时间] 发言人：内容」，未解析行原位保留")
    ap.add_argument("--max-unparsed", type=int, default=50, help="md 里最多列出的未解析行数，默认 50")
    args = ap.parse_args(argv)
    try:
        if args.max_unparsed < 0:
            raise UserError("--max-unparsed 不能为负数")
        renames = parse_pairs(args.rename, "--rename")
        speakers = set(x.strip() for x in re.split(r"[,，、]", args.speakers or "") if x.strip())
        custom = None
        if args.pattern:
            try:
                custom = re.compile(args.pattern)
            except re.error as exc:
                raise UserError("--pattern 不是合法正则：%s" % exc)
            if "name" not in custom.groupindex:
                raise UserError("--pattern 必须包含命名分组 (?P<name>...)")
        text, enc = read_text(args.path, args.encoding)
        lines = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        turns, meta, unparsed, stats = parse(lines, renames, speakers, custom)
        if not turns:
            sys.stderr.write("没有认出任何发言。前 5 个非空行：\n")
            for line in [l for l in lines if l.strip()][:5]:
                sys.stderr.write("  | %s\n" % line[:80])
            sys.stderr.write("可以：①用 --speakers 给出发言人名单；②用 --pattern 写一条正则；"
                             "③把导出格式改成「姓名 00:12:34」换行接内容。\n")
            return EXIT_NOPARSE
        if stats["outside_speakers"]:
            sys.stderr.write("提示：%d 行带时间的发言行，名字不在 --speakers 名单里（%s），已并入上一段；"
                             "如果他们也是发言人，请把名字加进名单。\n" % (
                                 sum(stats["outside_speakers"].values()), "、".join(sorted(stats["outside_speakers"]))))
        rows, exact = speaker_stats(turns)
        action, decision, open_q = find_candidates(turns)
        src = "标准输入" if args.path == "-" else os.path.basename(args.path)
        if args.format == "json":
            doc = {
                "source": src, "encoding": enc.replace("-sig", ""), "total_lines": len(lines), "blank_lines": stats["blank"],
                "turn_count": len(turns), "continuation_lines": stats["continuation"], "line_kinds": stats["kinds"],
                "meta": [{"line": n, "text": t} for n, t in meta],
                "unparsed": [{"line": n, "text": t} for n, t in unparsed],
                "speakers": rows, "duration_estimated": exact,
                "action_candidates": action, "decision_candidates": decision, "open_question_candidates": open_q,
                "turns": [{k: t[k] for k in ("line", "time", "speaker", "raw_name", "kind", "text")} for t in turns],
            }
            result = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        else:
            result = render_md(src, enc, lines, turns, meta, unparsed, stats, rows, exact, action, decision, open_q,
                               args.max_unparsed)
        if args.normalized:
            atomic_write(args.normalized, render_normalized(lines, turns, meta, unparsed))
        if args.output:
            atomic_write(args.output, result)
            sys.stderr.write("已写入 %s\n" % args.output)
        else:
            sys.stdout.write(result)
        return EXIT_OK
    except UserError as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(EXIT_INT)
