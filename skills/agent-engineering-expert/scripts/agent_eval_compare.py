#!/usr/bin/env python3
"""Compare recorded agent evaluations offline. Python stdlib; no model execution."""

import argparse
from decimal import Decimal, localcontext
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys


FIELDS = {"case_id", "passed", "evidence", "latency_ms", "cost"}
METRICS = ("latency_ms", "cost")


class InputError(ValueError):
    """Invalid input rather than a recorded regression or missing evidence."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise InputError("non-finite JSON number: " + value)


def load_records(path):
    """Read a nonempty JSONL file without following any evidence references."""
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise InputError("cannot read {}: {}".format(path, exc)) from exc
    records = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        location = "{}:{}".format(path, line_number)
        try:
            row = json.loads(line, object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
            if not isinstance(row, dict):
                raise InputError("each line must be a JSON object")
            unknown = sorted(set(row) - FIELDS)
            if unknown:
                raise InputError("unknown fields: " + ", ".join(unknown))
            case_id = row.get("case_id")
            if not isinstance(case_id, str) or not case_id.strip():
                raise InputError("case_id must be a nonempty string")
            if case_id != case_id.strip():
                raise InputError("case_id must not have surrounding whitespace")
            if any(ord(char) < 32 for char in case_id):
                raise InputError("case_id must not contain control characters")
            case_id.encode("utf-8")
            if case_id in records:
                raise InputError("duplicate case_id: " + case_id)
            if type(row.get("passed")) is not bool:
                raise InputError("passed must be JSON true or false (not 0/1)")
            if "evidence" in row and not isinstance(row["evidence"], str):
                raise InputError("evidence must be a string when present")
            if "evidence" in row:
                row["evidence"].encode("utf-8")
            for metric in METRICS:
                if metric in row:
                    value = row[metric]
                    if type(value) not in (int, float):
                        raise InputError(metric + " must be a JSON number when present")
                    if isinstance(value, float) and not math.isfinite(value):
                        raise InputError(metric + " must be finite")
                    if value < 0:
                        raise InputError(metric + " must be nonnegative")
            # Whitespace-only evidence is missing, but the original string is retained.
            records[case_id] = row
        except (InputError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            raise InputError("{}: {}".format(location, exc)) from exc
    if not records:
        raise InputError("{}: no case records".format(path))
    return records, hashlib.sha256(raw).hexdigest()


def has_evidence(record):
    return bool(record.get("evidence", "").strip())


def decimal_text(value):
    # Decimal strings avoid silently rounding cost totals into binary float output.
    if value == 0:
        return "0"
    return str(value.normalize())


def mean_text(values):
    if not values:
        return None
    with localcontext() as context:
        context.prec = 28
        total = sum((Decimal(str(value)) for value in values), Decimal(0))
        return decimal_text(total / Decimal(len(values)))


def metric_summary(name, before, after, paired_ids, complete):
    both = [case_id for case_id in paired_ids
            if name in before[case_id] and name in after[case_id]]
    before_mean = mean_text([before[case_id][name] for case_id in both])
    after_mean = mean_text([after[case_id][name] for case_id in both])
    delta = None
    if before_mean is not None:
        with localcontext() as context:
            context.prec = 28
            delta = decimal_text(Decimal(after_mean) - Decimal(before_mean))
    paired_coverage_complete = bool(paired_ids) and len(both) == len(paired_ids)
    return {
        "recorded_before_count": sum(name in row for row in before.values()),
        "recorded_after_count": sum(name in row for row in after.values()),
        "paired_with_metric_count": len(both),
        "paired_case_count": len(paired_ids),
        "paired_metric_case_ids": both,
        "missing_before_case_ids": [case_id for case_id in paired_ids
                                    if name not in before[case_id]],
        "missing_after_case_ids": [case_id for case_id in paired_ids
                                   if name not in after[case_id]],
        "before_mean_on_metric_pairs": before_mean,
        "after_mean_on_metric_pairs": after_mean,
        "mean_delta_after_minus_before": delta,
        "paired_metric_coverage_complete": paired_coverage_complete,
        "whole_comparison_metric_coverage_complete": complete and paired_coverage_complete,
        "number_representation": "decimal strings; null means no metric pairs",
        "interpretation": "Recorded observations only; absent values are not zero. Cost unit is supplied by the record source.",
    }


def compare(before, after, before_path, after_path, before_sha, after_sha):
    before_ids, after_ids = set(before), set(after)
    paired_ids = sorted(before_ids & after_ids)
    only_before = sorted(before_ids - after_ids)
    only_after = sorted(after_ids - before_ids)
    missing_evidence = {
        "before": sorted(case_id for case_id, row in before.items() if not has_evidence(row)),
        "after": sorted(case_id for case_id, row in after.items() if not has_evidence(row)),
    }
    complete = not (only_before or only_after or missing_evidence["before"]
                    or missing_evidence["after"])
    recorded_newly_passed = [case_id for case_id in paired_ids
                             if not before[case_id]["passed"] and after[case_id]["passed"]]
    newly_passed = [case_id for case_id in recorded_newly_passed
                    if has_evidence(before[case_id]) and has_evidence(after[case_id])]
    regressions = [case_id for case_id in paired_ids
                   if before[case_id]["passed"] and not after[case_id]["passed"]]
    before_pass_count = sum(before[case_id]["passed"] for case_id in paired_ids)
    after_pass_count = sum(after[case_id]["passed"] for case_id in paired_ids)
    gain_supported = complete and not regressions and after_pass_count > before_pass_count
    status = "regression" if regressions else ("incomplete" if not complete else "no_regression_detected")
    exit_code = 1 if regressions or not complete else 0
    return {
        "schema_version": "1.0",
        "comparison_status": status,
        "comparison_complete": complete,
        "exit_code": exit_code,
        "inputs": {
            "before": {"path": str(before_path), "sha256": before_sha, "case_count": len(before)},
            "after": {"path": str(after_path), "sha256": after_sha, "case_count": len(after)},
        },
        "paired": {
            "case_count": len(paired_ids),
            "case_ids": paired_ids,
            "recorded_before_pass_count": before_pass_count,
            "recorded_after_pass_count": after_pass_count,
            "recorded_pass_count_delta": after_pass_count - before_pass_count,
            "recorded_before_pass_rate": before_pass_count / len(paired_ids) if paired_ids else None,
            "recorded_after_pass_rate": after_pass_count / len(paired_ids) if paired_ids else None,
            "recorded_false_to_true": recorded_newly_passed,
            "newly_passed_with_both_evidence": newly_passed,
            "regressions_true_to_false": regressions,
            "unchanged_passed": [case_id for case_id in paired_ids
                                 if before[case_id]["passed"] and after[case_id]["passed"]],
            "unchanged_failed": [case_id for case_id in paired_ids
                                 if not before[case_id]["passed"] and not after[case_id]["passed"]],
        },
        "missing": {
            "missing_after_case_ids": only_before,
            "missing_before_case_ids": only_after,
            "missing_evidence_case_ids": missing_evidence,
        },
        "pass_gain_supported_for_recorded_case_set": gain_supported,
        "claim": ("本组已记录案例的通过数增加；不推断未覆盖案例、模型整体能力或真实用户效果。"
                  if gain_supported else "不作改进结论；仅报告记录中的变化、回退和完整性。"),
        "metrics": {name: metric_summary(name, before, after, paired_ids, complete) for name in METRICS},
        "cases": [{
            "case_id": case_id,
            "paired": case_id in before and case_id in after,
            "before": before.get(case_id),
            "after": after.get(case_id),
            "both_evidence_present": (case_id in before and case_id in after
                                      and has_evidence(before[case_id]) and has_evidence(after[case_id])),
        } for case_id in sorted(before_ids | after_ids)],
        "scope": "Offline comparison of self-reported execution records. Evidence strings are not read or independently verified. No network or live model execution.",
    }


def md_text(value):
    text = html.escape(str(value), quote=False)
    text = re.sub(r"([\\`*_\[\]{}()!|])", r"\\\1", text)
    return text.replace("\r", "").replace("\n", "<br>")


def ids_text(values):
    return ", ".join(md_text(value) for value in values) if values else "无"


def markdown(report):
    paired, missing = report["paired"], report["missing"]
    lines = [
        "# Agent 前后记录比较",
        "",
        "判定：`{}`；比较完整：{}；退出码：{}。".format(
            report["comparison_status"], "是" if report["comparison_complete"] else "否", report["exit_code"]),
        "",
        report["claim"],
        "",
        "## 成对通过记录",
        "",
        "{} 个同 ID 案例：改前通过 {}，改后通过 {}，通过数差 {}。".format(
            paired["case_count"], paired["recorded_before_pass_count"],
            paired["recorded_after_pass_count"], paired["recorded_pass_count_delta"]),
        "",
        "- 布尔记录中的 false → true：" + ids_text(paired["recorded_false_to_true"]),
        "- 双方有证据的新增通过：" + ids_text(paired["newly_passed_with_both_evidence"]),
        "- 记录中的回退 true → false：" + ids_text(paired["regressions_true_to_false"]),
        "- 改后缺少案例：" + ids_text(missing["missing_after_case_ids"]),
        "- 改前缺少案例：" + ids_text(missing["missing_before_case_ids"]),
        "- 改前缺少证据：" + ids_text(missing["missing_evidence_case_ids"]["before"]),
        "- 改后缺少证据：" + ids_text(missing["missing_evidence_case_ids"]["after"]),
        "",
        "## 已记录指标",
        "",
        "均值和差值只使用同 ID 且双方都提供该指标的案例。未知不补 0，真实 0 保留。",
        "",
        "| 指标 | 改前记录数 | 改后记录数 | 成对覆盖 | 改前均值 | 改后均值 | 均值差（后−前） |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in METRICS:
        metric = report["metrics"][name]
        lines.append("| {} | {} | {} | {}/{} | {} | {} | {} |".format(
            name, metric["recorded_before_count"], metric["recorded_after_count"],
            metric["paired_with_metric_count"], metric["paired_case_count"],
            metric["before_mean_on_metric_pairs"] if metric["before_mean_on_metric_pairs"] is not None else "未知",
            metric["after_mean_on_metric_pairs"] if metric["after_mean_on_metric_pairs"] is not None else "未知",
            metric["mean_delta_after_minus_before"] if metric["mean_delta_after_minus_before"] is not None else "未知"))
    for name in METRICS:
        metric = report["metrics"][name]
        lines.extend([
            "",
            "{} 缺失（改前）：{}；缺失（改后）：{}。".format(
                name, ids_text(metric["missing_before_case_ids"]), ids_text(metric["missing_after_case_ids"])),
            "",
        ])
    lines.extend([
        "指标不齐时不能声称整体更快或更省。成本单位、判定规则和执行条件由记录来源说明；脚本不猜测价格，也不执行模型。",
        "",
        "## 案例与证据",
        "",
        "| case_id | 改前 passed | 改后 passed | 改前 evidence | 改后 evidence |",
        "|---|---|---|---|---|",
    ])
    for case in report["cases"]:
        before, after = case["before"], case["after"]
        lines.append("| {} | {} | {} | {} | {} |".format(
            md_text(case["case_id"]),
            str(before["passed"]).lower() if before is not None else "未配对",
            str(after["passed"]).lower() if after is not None else "未配对",
            md_text(before.get("evidence", "")) if before is not None else "—",
            md_text(after.get("evidence", "")) if after is not None else "—"))
    lines.extend(["", "## 输入指纹", ""])
    for side in ("before", "after"):
        source = report["inputs"][side]
        lines.append("- {}：{}；SHA-256 `{}`；{} 条记录。".format(
            side, md_text(source["path"]), source["sha256"], source["case_count"]))
    lines.extend(["", "证据仅是输入者提供的字符串，未打开或独立验证。合成样例不代表真实用户或客户端使用。", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path, help="before JSONL records")
    parser.add_argument("--after", required=True, type=Path, help="after JSONL records")
    parser.add_argument("--out-dir", required=True, type=Path, help="new output directory; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        before, before_sha = load_records(args.before)
        after, after_sha = load_records(args.after)
        report = compare(before, after, args.before, args.after, before_sha, after_sha)
        if args.out_dir.exists():
            raise InputError("output directory already exists; refusing overwrite: " + str(args.out_dir))
        args.out_dir.mkdir(parents=True, exist_ok=False)
        (args.out_dir / "comparison.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (args.out_dir / "comparison.md").write_text(markdown(report), encoding="utf-8")
        print("{}; complete={}; exit={}; reports={}".format(
            report["comparison_status"], report["comparison_complete"], report["exit_code"], args.out_dir))
        return report["exit_code"]
    except (InputError, OSError, ValueError, ArithmeticError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
