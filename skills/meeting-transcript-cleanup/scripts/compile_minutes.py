#!/usr/bin/env python3
"""Compile annotated notes into source-linked minutes; Python standard library only.

The caller labels meaning. This program checks exact source anchors and reports
literal risk markers; it does not infer agreement, people, dates or authorization.
"""

import argparse
import csv
import datetime
import hashlib
import html
import io
import json
import re
import sys
from pathlib import Path


VERSION = "0.1.2"
STATES = {"confirmed", "proposed", "conditional", "cancelled", "disputed"}
STATE_LABELS = {
    "confirmed": "已记录确认", "proposed": "建议", "conditional": "有条件",
    "cancelled": "已取消", "disputed": "有分歧", "open": "未决",
}
# Literal alerts, deliberately conservative: a match is NOT a semantic verdict.
MARKERS = re.compile(
    r"如果|若|前提|条件|除非|建议|提议|考虑|尚未|还没|没有|不能|不要|不同意|"
    r"不通过|不做|未通过|取消|撤回|作废|待定|再议|待确认|否决|不反对|不保证|不确定|"
    r"暂不|不|没|未|但|不过|原则上|可能|倾向|\bif\b|\bunless\b|\bnot\b|\bcancell?ed\b|\bproposed\b",
    re.I,
)
ANONYMOUS = re.compile(r"^(?:说话人|发言人|讲话人|speaker)\s*\d+$", re.I)
DATES = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")


class InputError(ValueError):
    pass


def text_value(value, label, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InputError("%s 必须是非空文本%s" % (label, "或 null" if nullable else ""))
    if "\x00" in value:
        raise InputError("%s 不能包含 NUL" % label)
    return value


def exact_keys(value, required, optional, label):
    if not isinstance(value, dict):
        raise InputError("%s 必须是对象" % label)
    missing = set(required) - set(value)
    unknown = set(value) - set(required) - set(optional)
    if missing or unknown:
        raise InputError("%s 字段有误：缺少 %s；未知 %s" %
                         (label, sorted(missing), sorted(unknown)))


def iso_date(value, label):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InputError("%s 必须是 YYYY-MM-DD 或 null" % label)
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise InputError("%s 日期不存在" % label)
    return value


def decode_transcript(raw):
    encodings = ("utf-16",) if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "gb18030")
    for encoding in encodings:
        try:
            decoded = raw.decode(encoding)
            if not decoded.strip() or "\x00" in decoded:
                raise InputError("转写稿为空或含 NUL，请另存为文本")
            return decoded.splitlines(), encoding
        except UnicodeDecodeError:
            continue
    raise InputError("转写稿编码无法识别；支持 UTF-8、带 BOM 的 UTF-16、GB18030")


def anchor(value, lines, label):
    exact_keys(value, {"start_line", "end_line", "quote"}, set(), label)
    start, end = value["start_line"], value["end_line"]
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise InputError("%s 行号须为有效的 1 起始闭区间" % label)
    quote = text_value(value["quote"], label + ".quote")
    original = "\n".join(lines[start - 1:end])
    if quote != original:
        raise InputError("%s.quote 与 L%d-L%d 全部原文不一致，不能截取或改写引用" % (label, start, end))
    return {"start_line": start, "end_line": end, "quote": quote}


def detail_anchor(value, lines, sources, label):
    found = anchor(value, lines, label)
    if not any(s["start_line"] <= found["start_line"] <= found["end_line"] <= s["end_line"]
               for s in sources):
        raise InputError("%s 必须位于该事项 sources 的行号范围内" % label)
    return found


def compile_notes(notes, lines):
    exact_keys(notes, {"schema_version", "meeting", "decisions", "actions", "open_questions"}, set(), "notes")
    if notes["schema_version"] != "1":
        raise InputError("schema_version 须为字符串 1")
    exact_keys(notes["meeting"], {"title", "date"}, set(), "meeting")
    meeting = {"title": text_value(notes["meeting"]["title"], "meeting.title"),
               "date": iso_date(notes["meeting"]["date"], "meeting.date")}
    result = {"meeting": meeting, "decisions": [], "actions": [], "open_questions": []}
    used_ids = set()
    for category in ("decisions", "actions", "open_questions"):
        if not isinstance(notes[category], list):
            raise InputError("%s 必须是数组" % category)
        for number, item in enumerate(notes[category], 1):
            label = "%s[%d]" % (category, number)
            required = {"id", "text", "state", "sources"}
            if category == "actions":
                required |= {"owner", "owner_source", "due_text", "due_date", "due_source"}
            exact_keys(item, required, {"review_note"}, label)
            ident = text_value(item["id"], label + ".id")
            if ident in used_ids:
                raise InputError("重复事项 id：%s" % ident)
            used_ids.add(ident)
            text = text_value(item["text"], label + ".text")
            allowed_states = {"open"} if category == "open_questions" else STATES
            state = text_value(item["state"], label + ".state")
            if state not in allowed_states:
                raise InputError("%s.state 必须为 %s" % (label, sorted(allowed_states)))
            if not isinstance(item["sources"], list) or not item["sources"]:
                raise InputError("%s.sources 至少需要一处原文出处" % label)
            sources = [anchor(s, lines, "%s.sources[%d]" % (label, n))
                       for n, s in enumerate(item["sources"], 1)]
            entry = {"id": ident, "text": text, "state": item["state"], "sources": sources}
            if "review_note" in item:
                entry["review_note"] = text_value(item["review_note"], label + ".review_note")
            flags = []
            quote = "\n".join(s["quote"] for s in sources)
            markers = sorted(set(MARKERS.findall(quote)))
            if item["state"] == "confirmed" and markers:
                flags.append("确认记录的引用含字面条件/建议/否定线索：%s；仅提示核对，不判断语义" % "、".join(markers))
            if len(set(DATES.findall(quote))) > 1:
                flags.append("出处出现多个日期；可能是不同事项，也可能冲突，请结合上下文核对")
            if item["state"] in {"proposed", "conditional", "disputed"}:
                flags.append("记录为%s，不能当无条件确认" % STATE_LABELS[item["state"]])
            if category == "actions":
                owner = text_value(item["owner"], label + ".owner", nullable=True)
                due_text = text_value(item["due_text"], label + ".due_text", nullable=True)
                due_date = iso_date(item["due_date"], label + ".due_date")
                owner_source = item["owner_source"]
                due_source = item["due_source"]
                if owner is None:
                    if owner_source is not None:
                        raise InputError("%s.owner 为 null 时 owner_source 也须为 null" % label)
                    flags.append("负责人待认领；未从说话人编号推断姓名")
                else:
                    owner_source = detail_anchor(owner_source, lines, sources, label + ".owner_source")
                    if owner not in owner_source["quote"]:
                        raise InputError("%s.owner 未在 owner_source 原文中出现，不能猜姓名或身份" % label)
                    if ANONYMOUS.fullmatch(owner.strip()):
                        flags.append("负责人仍为匿名说话人编号，身份待确认")
                if due_text is None and due_date is None:
                    if due_source is not None:
                        raise InputError("%s 无截止信息时 due_source 须为 null" % label)
                    flags.append("截止时间待确认")
                else:
                    due_source = detail_anchor(due_source, lines, sources, label + ".due_source")
                    if due_text is not None and due_text not in due_source["quote"]:
                        raise InputError("%s.due_text 未在 due_source 原文中出现" % label)
                    if due_date is not None and due_date not in due_source["quote"]:
                        raise InputError("%s.due_date 必须在出处中按 YYYY-MM-DD 明写；脚本不换算相对时间" % label)
                    if due_date is None:
                        flags.append("截止原话未换算：%s；保留原文，具体日期待确认" % due_text)
                    if len(set(DATES.findall(due_source["quote"]))) > 1:
                        flags.append("截止依据出现多个日期，不能自动选择其中一个")
                entry.update(owner=owner, owner_source=owner_source, due_text=due_text,
                             due_date=due_date, due_source=due_source)
            entry["review_flags"] = list(dict.fromkeys(flags))
            entry["review_status"] = "needs_review" if flags else "anchors_validated"
            # Only an unflagged, explicitly confirmed decision enters the decision list.
            entry["included_as_confirmed_decision"] = (
                category == "decisions" and item["state"] == "confirmed" and not flags)
            result[category].append(entry)
    result["review_status"] = "needs_review" if any(
        item["review_flags"] for category in ("decisions", "actions", "open_questions")
        for item in result[category]) else "anchors_validated"
    return result


def md(value):
    escaped = html.escape(str(value), quote=False)
    escaped = re.sub(r"([\\`*\[\]_|#!])", r"\\\1", escaped)
    return escaped.replace("\r", "").replace("\n", " / ")


def source_label(sources):
    return "; ".join("L%d-L%d" % (s["start_line"], s["end_line"]) for s in sources)


def quote_block(item):
    out = []
    for source in item["sources"]:
        out.append("出处 L%d-L%d：" % (source["start_line"], source["end_line"]))
        out.extend("> " + md(line) for line in source["quote"].split("\n"))
    if item.get("review_note"):
        out.append("整理注：" + md(item["review_note"]))
    return out


def render_minutes(report):
    date = report["meeting"]["date"] or "待确认；相对时间保持原话"
    out = ["# %s｜会议纪要" % md(report["meeting"]["title"]), "",
           "会议日期：%s" % md(date),
           "核对状态：%s" % ("有待核对事项" if report["review_status"] == "needs_review" else "原文出处已校验"),
           "依据：%s｜原始文件 SHA-256：`%s`" %
           (md(report["source"]["filename"]), report["source"]["sha256"]),
           "", "> 事项内容与状态来自输入标注；脚本只核对出处和字面线索，不确认会议决策语义、截止换算或发送授权。", "",
           "## 一、决议", ""]
    confirmed = [d for d in report["decisions"] if d["included_as_confirmed_decision"]]
    if not confirmed:
        out.append("无已标注确认且未触发核对提示的决议。")
    for item in confirmed:
        out += ["- %s：%s" % (md(item["id"]), md(item["text"]))] + quote_block(item) + [""]
    out += ["", "## 二、待办记录", "", "包含有条件、待认领及取消事项；按状态列区分。",
            "", "| ID | 事项 | 负责人 | 截止信息 | 记录状态 | 核对状态 | 出处 |",
            "|---|---|---|---|---|---|---|"]
    for item in report["actions"]:
        owner = item["owner"] or "待认领"
        due = item["due_date"] or ((item["due_text"] + "（具体日期待确认）") if item["due_text"] else "待确认")
        if item["due_date"] and item["due_text"]:
            due += "；原话：" + item["due_text"]
        row = [item["id"], item["text"], owner, due, STATE_LABELS[item["state"]],
               "待核对" if item["review_flags"] else "出处已校验", source_label(item["sources"])]
        out.append("| " + " | ".join(md(cell) for cell in row) + " |")
    if not report["actions"]:
        out.append("| — | 无 | — | — | — | — | — |")
    for item in report["actions"]:
        out += ["", "### " + md(item["id"])] + quote_block(item)
    out += ["", "## 三、未决问题", ""]
    for item in report["open_questions"]:
        out += ["- %s：%s" % (md(item["id"]), md(item["text"]))] + quote_block(item) + [""]
    if not report["open_questions"]:
        out.append("无。")
    out += ["", "## 四、未确认或已取消的决议记录", ""]
    other = [d for d in report["decisions"] if not d["included_as_confirmed_decision"]]
    for item in other:
        out += ["- %s｜%s：%s" % (md(item["id"]), STATE_LABELS[item["state"]], md(item["text"]))] + quote_block(item) + [""]
    if not other:
        out.append("无。")
    out += ["", "## 五、待核对清单", ""]
    flags = [(item["id"], flag) for category in ("decisions", "actions", "open_questions")
             for item in report[category] for flag in item["review_flags"]]
    out += ["- %s：%s" % (md(ident), md(flag)) for ident, flag in flags] or ["无字面核对提示；不等同于主持人确认。"]
    out += ["", "可以交付并使用上述标记核对缺口；脚本不发送消息。实际发送遵守当前会话授权，已有授权无需重复确认。", ""]
    return "\n".join(out)


def csv_cell(value):
    if value is None:
        return ""
    value = str(value)
    probe = value.lstrip("\ufeff \t\r\n")
    if value.startswith(("\t", "\r", "\n")) or probe.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def render_actions(report):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["meeting_title", "id", "action", "owner", "due_date", "due_text",
                     "record_state", "review_status", "review_flags", "source_lines", "source_quote"])
    for item in report["actions"]:
        row = [report["meeting"]["title"], item["id"], item["text"], item["owner"] or "待认领",
               item["due_date"] or "待确认", item["due_text"], item["state"], item["review_status"],
               "；".join(item["review_flags"]), source_label(item["sources"]),
               "\n".join(s["quote"] for s in item["sources"])]
        writer.writerow([csv_cell(value) for value in row])
    return output.getvalue()


def no_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InputError("JSON 中重复字段：%s" % key)
        value[key] = item
    return value


def run(transcript, notes_path, out_dir):
    transcript, notes_path, out_dir = Path(transcript), Path(notes_path), Path(out_dir)
    if out_dir.exists() or out_dir.is_symlink():
        raise InputError("输出目录已存在；请换一个新目录，避免覆盖报告或输入")
    raw = transcript.read_bytes()
    notes_raw = notes_path.read_bytes()
    lines, encoding = decode_transcript(raw)
    try:
        notes = json.loads(notes_raw.decode("utf-8-sig"), object_pairs_hook=no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("标注文件须为 UTF-8 JSON：%s" % exc)
    report = compile_notes(notes, lines)
    report.update(schema_version="1", compiler_version=VERSION,
                  source={"filename": transcript.name, "sha256": hashlib.sha256(raw).hexdigest(),
                          "encoding": encoding, "line_count": len(lines)},
                  annotations={"filename": notes_path.name, "sha256": hashlib.sha256(notes_raw).hexdigest()},
                  checks={"exact_source_anchors": True, "semantic_decision_verification": False,
                          "deadline_inference": False, "message_sent": False})
    contents = {"minutes.md": render_minutes(report), "actions.csv": render_actions(report),
                "minutes.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n"}
    # Validate and render before creating any directory; mkdir and mode x refuse races.
    out_dir.mkdir(parents=True, exist_ok=False)
    for name, content in contents.items():
        with (out_dir / name).open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="将原文与逐条标注编成可回查纪要、待办 CSV 和 JSON；不联网、不发送。")
    parser.add_argument("transcript", help="已有转写文本")
    parser.add_argument("--notes", required=True, help="UTF-8 JSON 结构化标注")
    parser.add_argument("--out-dir", required=True, help="须不存在的新输出目录")
    args = parser.parse_args(argv)
    try:
        report = run(args.transcript, args.notes, args.out_dir)
    except (InputError, OSError) as exc:
        print("无法生成纪要：%s" % exc, file=sys.stderr)
        return 2
    print("已生成 minutes.md / actions.csv / minutes.json；%s；目录 %s" %
          (report["review_status"], args.out_dir))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("已中断；原始输入未修改。如留下输出目录，请查看后使用新的目录重跑。", file=sys.stderr)
        sys.exit(130)
