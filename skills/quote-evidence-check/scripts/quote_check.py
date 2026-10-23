#!/usr/bin/env python3
"""Check two confirmed, structured quotes; all arithmetic uses integer cents."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

VERSION = "0.1.0"
MAX_INPUT_BYTES = 1_048_576
MAX_AMOUNT_CENTS = 99_999_999_999  # 999,999,999.99 yuan per fee
FEES = {
    "vehicle": "裸车价", "quoteTax": "报价税费", "insurance": "保险",
    "registration": "上牌", "service": "服务费",
    "mandatoryExtras": "强制装潢及附加项", "other": "其他费用",
}
CONDITIONS = {"model": "车型/配置", "payment": "付款方式", "scope": "费用范围"}
AMOUNT_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?\Z")


class InputError(ValueError):
    """An explicit schema, precision, size, or JSON error."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"JSON 存在重复键：{key!r}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise InputError(f"JSON 不允许非有限数字：{value}")


def load_document(text):
    if not isinstance(text, str):
        raise InputError("输入必须是 UTF-8 JSON 文本")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InputError("输入包含无效 Unicode 字符") from exc
    if len(encoded) > MAX_INPUT_BYTES:
        raise InputError("输入超过 1 MiB 上限")
    try:
        return json.loads(text, object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except json.JSONDecodeError as exc:
        raise InputError(f"JSON 格式错误，行 {exc.lineno}，列 {exc.colno}") from exc
    except (RecursionError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("JSON 嵌套过深或数字格式无效") from exc


def _keys(value, expected, path):
    if not isinstance(value, dict):
        raise InputError(f"{path} 必须是对象")
    missing = set(expected) - value.keys()
    extra = value.keys() - set(expected)
    if missing or extra:
        details = []
        if missing:
            details.append("缺少键 " + ", ".join(sorted(missing)))
        if extra:
            details.append("未知键 " + ", ".join(sorted(extra)))
        raise InputError(f"{path}：{'；'.join(details)}")


def _text(value, path, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise InputError(f"{path} 必须是长度不超过 {maximum} 的字符串")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InputError(f"{path} 包含无效 Unicode 字符") from exc


def parse_amount(value, path="amount"):
    """Return cents or None; never coerce numbers, bool, or unknown to zero."""
    if value is None:
        return None
    if not isinstance(value, str) or not AMOUNT_PATTERN.fullmatch(value):
        raise InputError(f"{path} 必须是非负十进制元字符串，最多两位小数；未知用 null")
    whole, dot, fraction = value.partition(".")
    cents = int(whole) * 100 + int((fraction + "00")[:2])
    if cents > MAX_AMOUNT_CENTS:
        raise InputError(f"{path} 超过每项 999999999.99 元上限")
    return cents


def validate_document(document):
    _keys(document, {"schema_version", "quotes"}, "root")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise InputError("schema_version 必须是整数 1")
    _keys(document["quotes"], {"A", "B"}, "quotes")
    for quote_id in ("A", "B"):
        quote = document["quotes"][quote_id]
        base = f"quotes.{quote_id}"
        _keys(quote, {"conditions", "fees"}, base)
        _keys(quote["conditions"], CONDITIONS, base + ".conditions")
        _keys(quote["fees"], FEES, base + ".fees")
        for kind, names, value_key in (("fees", FEES, "amount"),
                                      ("conditions", CONDITIONS, "value")):
            for field in names:
                item = quote[kind][field]
                path = f"{base}.{kind}.{field}"
                _keys(item, {value_key, "confirmed", "source"}, path)
                if type(item["confirmed"]) is not bool:
                    raise InputError(f"{path}.confirmed 必须是布尔值")
                _text(item["source"], path + ".source", 20_000)
                if kind == "fees":
                    parse_amount(item["amount"], path + ".amount")
                elif item["value"] is not None:
                    _text(item["value"], path + ".value", 500)
    return document


def money(cents):
    if cents is None:
        return None
    sign = "-" if cents < 0 else ""
    absolute = abs(cents)
    return f"{sign}{absolute // 100}.{absolute % 100:02d}"


def signed_money(cents):
    return ("+" if cents > 0 else "") + money(cents)


def _status(item, key):
    value = item[key]
    if value is None or (isinstance(value, str) and not value.strip()):
        return "missing"
    if not item["confirmed"]:
        return "unconfirmed"
    if not item["source"].strip():
        return "source_missing"
    return "confirmed"


def _question(quote_id, field, code):
    label = FEES.get(field, CONDITIONS.get(field, field))
    if code == "condition_mismatch":
        text = f"请核实 A/B 的{label}是否同条件；只有取得明确的新报价/补充来源并确认后再比较。"
    elif code.endswith("source_missing"):
        text = f"请补充 {quote_id} 的{label}的原文出处或用户补充来源，并重新确认。"
    elif code.endswith("unconfirmed"):
        text = f"请核对 {quote_id} 的{label}与对应来源，明确确认或修正候选内容。"
    elif field in FEES:
        text = f"请补充 {quote_id} 的{label}的明确金额（可明确为 0）与来源，并确认。"
    else:
        text = f"请补充 {quote_id} 的{label}与来源，并确认。"
    return {"quote": quote_id, "field": field, "reason": code, "text": text}


def check_quotes(document, include_source=False):
    validate_document(document)
    result = {
        "schema_version": 1, "checker_version": VERSION,
        "export_mode": "include_source" if include_source else "omit_source",
        "export_notice": ("包含原文及自由文本条件，请自行核查分享范围。" if include_source else
                          "省略原文模式：不含 source 和自由文本条件；不承诺任意数据脱敏。"),
        "currency": "CNY", "scope": "recorded_seven_fields",
        "comparable": False, "quotes": {}, "blockers": [], "questions": [],
        "comparison_delta_cents": None, "comparison_delta": None, "fee_differences": [],
    }

    def block(quote_id, field, code):
        result["blockers"].append({"code": code, "quote": quote_id, "field": field})
        result["questions"].append(_question(quote_id, field, code))

    for quote_id in ("A", "B"):
        original = document["quotes"][quote_id]
        quote = {"fees": {}, "conditions": {}, "known_subtotal_cents": 0,
                 "known_subtotal": None, "complete_total_cents": None, "complete_total": None}
        fee_complete = True
        for field in FEES:
            item = original["fees"][field]
            cents = parse_amount(item["amount"])
            status = _status(item, "amount")
            exported = {"amount": money(cents), "amount_cents": cents,
                        "confirmed": item["confirmed"], "status": status}
            if include_source:
                exported["source"] = item["source"]
            quote["fees"][field] = exported
            if cents is not None:
                quote["known_subtotal_cents"] += cents
            if status != "confirmed":
                fee_complete = False
                block(quote_id, field, "fee_" + status)
        quote["known_subtotal"] = money(quote["known_subtotal_cents"])
        if fee_complete:
            quote["complete_total_cents"] = quote["known_subtotal_cents"]
            quote["complete_total"] = quote["known_subtotal"]
        for field in CONDITIONS:
            item = original["conditions"][field]
            status = _status(item, "value")
            exported = {"confirmed": item["confirmed"], "status": status}
            if include_source:
                exported.update(value=item["value"], source=item["source"])
            quote["conditions"][field] = exported
            if status != "confirmed":
                block(quote_id, field, "condition_" + status)
        result["quotes"][quote_id] = quote

    for field in CONDITIONS:
        left = document["quotes"]["A"]["conditions"][field]
        right = document["quotes"]["B"]["conditions"][field]
        # No semantic inference: only exact text after trimming outer whitespace.
        if (_status(left, "value") == _status(right, "value") == "confirmed"
                and left["value"].strip() != right["value"].strip()):
            block("A/B", field, "condition_mismatch")

    result["comparable"] = not result["blockers"]
    if result["comparable"]:
        delta = (result["quotes"]["B"]["complete_total_cents"]
                 - result["quotes"]["A"]["complete_total_cents"])
        result["comparison_delta_cents"] = delta
        result["comparison_delta"] = money(delta)
        for field in FEES:
            field_delta = (result["quotes"]["B"]["fees"][field]["amount_cents"]
                           - result["quotes"]["A"]["fees"][field]["amount_cents"])
            result["fee_differences"].append(
                {"field": field, "delta_cents": field_delta, "delta": money(field_delta)})
    return result


def _literal_block(text):
    """Keep user source as literal Markdown, even if it contains fences/HTML."""
    runs = re.findall(r"`+", text)
    fence = "`" * max(3, max((len(run) + 1 for run in runs), default=3))
    return f"{fence}text\n{text}\n{fence}"


def render_markdown(result):
    status_labels = {"confirmed": "已确认", "missing": "缺失", "unconfirmed": "未确认",
                     "source_missing": "缺少来源"}
    lines = ["# 两份报价核对报告", "", result["export_notice"], ""]
    if result["comparable"]:
        delta = result["comparison_delta_cents"]
        relation = "高于" if delta > 0 else "低于" if delta < 0 else "等于"
        lines += [f"**在已确认录入范围内，B {relation} A，差额 B − A = {signed_money(delta)} 元。**", ""]
    else:
        lines += ["**无法完整比较：存在缺项、未确认、来源缺失或条件不齐/不一致；不据此排名。**", ""]
    lines += ["金额单位：元；仅比较指定七项录入费用，不代表实际交易全部费用。",
              "已知小计包含已录入但可能尚未确认的金额；不能据此判断谁更便宜。", "",
              "| 报价 | 已知小计 | 七项已确认合计 |", "|---|---:|---:|"]
    for quote_id in ("A", "B"):
        quote = result["quotes"][quote_id]
        lines.append(f"| {quote_id} | {quote['known_subtotal']} | {quote['complete_total'] or '未齐'} |")
    lines += ["", "| 费用字段 | A 金额 | A 状态 | B 金额 | B 状态 |", "|---|---:|---|---:|---|"]
    for field, label in FEES.items():
        left, right = (result["quotes"][q]["fees"][field] for q in ("A", "B"))
        values = [left["amount"] if left["amount"] is not None else "未报价",
                  status_labels[left["status"]],
                  right["amount"] if right["amount"] is not None else "未报价",
                  status_labels[right["status"]]]
        lines.append(f"| {label} | {' | '.join(values)} |")
    lines += ["", "| 条件字段 | A 状态 | B 状态 |", "|---|---|---|"]
    mismatches = {b["field"] for b in result["blockers"] if b["code"] == "condition_mismatch"}
    for field, label in CONDITIONS.items():
        statuses = [status_labels[result["quotes"][q]["conditions"][field]["status"]] for q in ("A", "B")]
        marker = "（两边文本不一致）" if field in mismatches else ""
        lines.append(f"| {label}{marker} | {' | '.join(statuses)} |")
    if result["comparable"]:
        lines += ["", "## 差额组成（B − A）", "", "| 费用字段 | 差额（元） |", "|---|---:|"]
        for item in result["fee_differences"]:
            lines.append(f"| {FEES[item['field']]} | {signed_money(item['delta_cents'])} |")
    lines += ["", "## 待核实/追问", ""]
    lines += [f"- {q['text']}" for q in result["questions"]] or ["- 本次输入没有待核实项。"]
    if result["export_mode"] == "include_source":
        lines += ["", "## 原文及自由文本条件", ""]
        for quote_id in ("A", "B"):
            lines += [f"### 报价 {quote_id}", ""]
            for field, label in CONDITIONS.items():
                item = result["quotes"][quote_id]["conditions"][field]
                lines += [f"**{label}**", _literal_block(item["value"] or "（缺失）"),
                          "来源：", _literal_block(item["source"]), ""]
            for field, label in FEES.items():
                lines += [f"**{label}来源**", _literal_block(result["quotes"][quote_id]["fees"][field]["source"]), ""]
    lines += ["", "本工具不验证来源真伪；确认仅记录输入者的明确核对状态。",
              "不从金额推断税收政策、贷款利息或金融推荐。本报告不是报价承诺或交易建议。", ""]
    return "\n".join(lines)


def _write_report(path, text, overwrite):
    """Write owner-readable files atomically, refusing accidental overwrite."""
    target = Path(path)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".quote-report-", delete=False) as handle:
            temporary_name = handle.name
            os.chmod(temporary_name, 0o600)
            handle.write(text)
        if overwrite:
            os.replace(temporary_name, target)
        else:
            os.link(temporary_name, target)
            os.unlink(temporary_name)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 结构化报价 JSON；- 表示标准输入")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--include-source", action="store_true", help="主动包含来源原文和自由文本条件")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已有报告（仍禁止覆盖输入）")
    args = parser.parse_args(argv)
    try:
        outputs = [p for p in (args.json_output, args.markdown_output) if p is not None]
        resolved = [p.resolve() for p in outputs]
        if len(set(resolved)) != len(resolved):
            raise InputError("JSON 与 Markdown 输出必须是不同路径")
        if args.input != "-" and Path(args.input).resolve() in resolved:
            raise InputError("输出路径不能覆盖输入 JSON")
        for output in outputs:
            if output.exists() and not args.overwrite:
                raise InputError(f"输出已存在：{output}；更换路径或明确使用 --overwrite")
        if args.input == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with open(args.input, "rb") as handle:
                raw = handle.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise InputError("输入超过 1 MiB 上限")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InputError("输入不是有效 UTF-8") from exc
        result = check_quotes(load_document(text), include_source=args.include_source)
        json_report = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        markdown_report = render_markdown(result)
        if args.json_output:
            _write_report(args.json_output, json_report, args.overwrite)
        if args.markdown_output:
            _write_report(args.markdown_output, markdown_report, args.overwrite)
        if not outputs:
            sys.stdout.write(json_report)
        return 0
    except (InputError, OSError) as exc:
        print(f"输入/文件错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
