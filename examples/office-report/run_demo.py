#!/usr/bin/env python3
"""Run a synthetic Excel -> CSV -> one-page office report, entirely offline.

Requires existing openpyxl. Uses the repository's released merge, profile and
anomaly scripts without modifying them. --out-dir must be a new directory.
Exit 0 verified demonstration; 1 invalid data/options or existing directory;
2 filesystem/subprocess failure; 3 openpyxl unavailable. No dependency installs.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("月份", "区域", "渠道", "批次", "订单数", "退款订单数", "销售额")
KEY = FIELDS[:4]
PROVENANCE = ("来源文件", "来源工作表", "来源行")
RULES = {"pct": 20, "min_abs": 500, "window": 8, "sigma": 2,
         "predeclared": True, "metric": "销售额（元）", "group": "区域/渠道"}
CENT = Decimal("0.01")


class DemoError(Exception):
    pass


def dependencies():
    try:
        from openpyxl import Workbook, load_workbook
    except ImportError:
        raise DemoError("缺少 openpyxl；请使用已有该库的 Python 环境，本演示不安装依赖。")
    return Workbook, load_workbook


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value)


def write_csv(path, header, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def create_inputs(folder, Workbook):
    """72 synthetic region/channel/batch records; monetary cells are decimal text."""
    folder.mkdir()
    baseline = {
        ("华东", "线下"): [(60, 1, "7500.01"), (20, 1, "2500.00")],
        ("华东", "线上"): [(15, 1, "1500.01"), (5, 2, "500.01")],
        ("华西", "线下"): [(150, 1, "12000.02"), (50, 1, "4000.01")],
        ("华西", "线上"): [(75, 2, "5250.03"), (25, 3, "1750.01")],
    }
    files = []
    for region, filename in (("华东", "east.xlsx"), ("华西", "west.xlsx")):
        header = list(FIELDS) if region == "华东" else ["渠道", "销售额", "退款订单数", "月份", "批次", "订单数", "区域"]
        book = Workbook()
        sheet = book.active
        sheet.title = "明细"
        sheet.append(header)
        for month in range(1, 10):
            for channel in ("线下", "线上"):
                values = baseline[(region, channel)]
                if month == 9 and (region, channel) == ("华东", "线上"):
                    values = [(8, 2, "600.01"), (2, 2, "200.01")]
                if month == 9 and (region, channel) == ("华西", "线上"):
                    values = [(75, 2, "5250.03"), (25, None, None)]
                for batch, (orders, refunds, sales) in zip(("A", "B"), values):
                    record = dict(zip(FIELDS, ("2026-%02d" % month, region, channel, batch, orders, refunds, sales)))
                    sheet.append([record[key] for key in header])
        notes = book.create_sheet("说明")
        notes.append(["完全合成的演示数据；不是真实客户、腾讯平台调用或用户使用成果。"])
        notes.append(["仅明细表参与合并；金额存为两位小数文本并由 Decimal 解析。"])
        path = folder / filename
        book.save(path)
        book.close()
        files.append(path)
    return files


def load_table(path, sheet_name, load_workbook):
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        sheet = book[sheet_name]
        rows = sheet.iter_rows(values_only=True)
        header = next(rows)
        if any(not isinstance(name, str) or not name for name in header) or len(set(header)) != len(header):
            raise DemoError("表头为空或重复：%s" % path.name)
        result = []
        for number, values in enumerate(rows, 2):
            if not any(value is not None for value in values):
                continue
            if len(values) != len(header):
                raise DemoError("表头与数据列数不符：%s 第 %d 行" % (path.name, number))
            result.append((number, dict(zip(header, values))))
        return list(header), result
    finally:
        book.close()


def count(value, name, optional=False):
    if value is None:
        if optional:
            return None
        raise DemoError("%s 缺失，不能补零" % name)
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise DemoError("%s 必须为非负整数：%r" % (name, value))
    return int(value)


def money(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.quantize(CENT):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise DemoError("销售额必须为有限非负金额，最多两位小数：%r" % value)
    return number


def validate_rows(rows):
    if not rows:
        raise DemoError("没有明细数据")
    result, seen = [], set()
    for row in rows:
        if any(key not in row for key in FIELDS):
            raise DemoError("明细缺少必要列")
        if not isinstance(row["月份"], str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", row["月份"]):
            raise DemoError("月份必须为 YYYY-MM")
        if any(not isinstance(row[key], str) or not row[key].strip() or row[key] != row[key].strip() for key in KEY[1:]):
            raise DemoError("区域、渠道或批次缺失/有首尾空格；需明确口径后重跑")
        key = tuple(row[name] for name in KEY)
        if key in seen:
            raise DemoError("重复的月/区域/渠道/批次，拒绝重复计数：%s" % (key,))
        seen.add(key)
        item = dict(row)
        item["订单数"] = count(row["订单数"], "订单数")
        item["退款订单数"] = count(row["退款订单数"], "退款订单数", optional=True)
        item["销售额"] = money(row["销售额"])
        if item["退款订单数"] is not None and item["退款订单数"] > item["订单数"]:
            raise DemoError("退款订单数不能超过同一批次的订单数")
        result.append(item)
    return result


def summarize(bucket):
    orders = sum(row["订单数"] for row in bucket)
    missing_refunds = sum(row["退款订单数"] is None for row in bucket)
    missing_sales = sum(row["销售额"] is None for row in bucket)
    known_refunds = sum(row["退款订单数"] for row in bucket if row["退款订单数"] is not None)
    known_sales = sum((row["销售额"] for row in bucket if row["销售额"] is not None), Decimal(0))
    refunds = None if missing_refunds else known_refunds
    return {"rows": len(bucket), "orders": orders, "refunds": refunds,
            "refund_rate": str(Decimal(refunds) / Decimal(orders)) if refunds is not None and orders else None,
            "known_refunds": known_refunds, "missing_refund_rows": missing_refunds,
            "sales": None if missing_sales else format(known_sales, ".2f"),
            "known_sales": format(known_sales, ".2f"), "missing_sales_rows": missing_sales}


def aggregate_rows(rows):
    rows = validate_rows(rows)
    groups, monthly = {}, {}
    for row in rows:
        groups.setdefault(tuple(row[key] for key in FIELDS[:3]), []).append(row)
        monthly.setdefault(row["月份"], []).append(row)
    return {"synthetic_demo": True, "money_unit": "CNY", "refund_rate_method": "sum(refunds)/sum(orders); missing numerator => unknown",
            "groups": [dict(month=key[0], region=key[1], channel=key[2], **summarize(bucket)) for key, bucket in sorted(groups.items())],
            "monthly": [dict(month=month, **summarize(bucket)) for month, bucket in sorted(monthly.items())]}


def run_step(name, script, args, output):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], text=True, capture_output=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=40)
    write_text(output / (name + ".txt"), proc.stdout)
    if proc.stderr:
        write_text(output / (name + "-stderr.txt"), proc.stderr)
    if proc.returncode:
        raise DemoError("%s 失败（退出 %d），详情见 %s.txt / stderr：%s" % (name, proc.returncode, name, proc.stderr.strip()))
    return {"name": name, "script": str(script.relative_to(ROOT)), "script_sha256": digest(script),
            "exit_code": proc.returncode, "stdout_artifact": name + ".txt"}


def check_provenance(source_tables, merged_rows):
    original = {(str(path.resolve()), "明细", number): row for path, table in source_tables for number, row in table}
    seen = set()
    for row in merged_rows:
        try:
            key = tuple(row[field] for field in PROVENANCE)
        except KeyError:
            raise DemoError("合并结果没有完整来源列")
        if key in seen or key not in original or any(row.get(field) != original[key].get(field) for field in FIELDS):
            raise DemoError("来源记录重复/缺失或明细值与原件不符")
        seen.add(key)
    if seen != set(original):
        raise DemoError("原件与合并明细的行数/来源不一致")
    return len(seen)


def percent(rate):
    return "待取数" if rate is None else format(Decimal(rate) * 100, ".2f") + "%"


def report(summary, checks, flagged, missing):
    old, latest = summary["monthly"][-2:]
    year, month = latest["month"].split("-")
    observations = []
    for flag in flagged:
        if flag["期"] != latest["month"]:
            continue
        points = [row for row in summary["groups"] if row["region"] + "/" + row["channel"] == flag["维度"]]
        current = next(row for row in points if row["month"] == flag["期"])
        previous = next((row for row in points if row["month"] == old["month"]), None)
        if previous and previous["sales"] is not None and current["sales"] is not None:
            direction = "降" if Decimal(current["sales"]) < Decimal(previous["sales"]) else "升"
            observations.append("%s销售额由 %s %s至 %s（环比 %s）" %
                                (flag["维度"], format(Decimal(previous["sales"]), ",.2f"), direction,
                                 format(Decimal(current["sales"]), ",.2f"), flag["环比"]))
        else:
            observations.append("%s %s销售额被规则标出，需复核基线与原始记录" % (flag["维度"], flag["期"]))
    unknown = []
    if latest["missing_sales_rows"]:
        unknown.append("全量销售额")
    if latest["missing_refund_rows"]:
        unknown.append("全量退款数及退款率")
    if unknown:
        observations.append("%s存在缺失，%s暂待取数" % (latest["month"], "、".join(unknown)))
    if not observations:
        observations.append("本期未被固定销售额规则标出；筛查结果不代表经营正常或原因已解释")
    lines = ["# %s 年 %d 月区域渠道经营月报（合成演示）" % (year, int(month)), "",
             "完全合成的办公工作流验收，非用户案例；金额单位：元。异常是筛查现象，原因均待查。", "",
             "**结论：%s。**" % "；".join(observations), "",
             "| 指标 | %s | %s |" % (old["month"], latest["month"]), "|---|---:|---:|"]
    for label, before, after in (("订单数", old["orders"], latest["orders"]),
                                 ("退款订单数", old["refunds"], latest["refunds"] if latest["refunds"] is not None else "待取数"),
                                 ("退款率（总退款数/总订单数）", percent(old["refund_rate"]), percent(latest["refund_rate"])),
                                 ("销售额", old["sales"], latest["sales"] or "待取数；已知部分 " + latest["known_sales"])):
        lines.append("| %s | %s | %s |" % (label, before, after))
    lines += ["", "**需处理事项**", "", "| 现象 | 影响与动作 |", "|---|---|"]
    for row in flagged:
        lines.append("| %s %s 销售额 %s，环比 %s %s | 原因待查；核对该渠道两批次台账与统计口径后，再决定业务动作。 |" %
                     (row["维度"], row["期"], row["销售额"], row["环比"], row["标记"]))
    for row in missing:
        missing_fields = [label for field, label in (("销售额", "销售额"), ("退款订单数", "退款数")) if row[field] is None]
        lines.append("| %s/%s %s 批次 %s 缺失%s | 来源 inputs/%s · 明细第 %s 行；缺失指标补数前保留“待取数”，禁止补零或推断全渠道下跌。 |" %
                     (row["区域"], row["渠道"], row["月份"], row["批次"], "及".join(missing_fields),
                      Path(row["来源文件"]).name, row["来源行"]))
    lines += ["", "**验收与口径**：%d 行原件 → %d 行合并 → %d 个区域/渠道/月汇总行；%d 行来源逐一匹配。已知金额独立合计 %s，原件/明细/汇总三路一致；%d 份原件 SHA256 不变。金额用 Decimal，缺失指标整组记未知、另列已知小计；退款率不用行百分比均值。" %
              (checks["source_rows"], checks["merged_rows"], len(summary["groups"]), checks["provenance_rows_verified"],
               checks["known_sales_source"], len(checks["sources"])), "",
              "规则在生成输入前固定：环比绝对值 >20% 且金额变化 ≥500；或前 8 期均值 ±2 倍样本标准差且变化 ≥500。缺失不参与异常计算。8 期合成平稳基线用于展示规则，不代表真实经营波动。", "",
              "| 原件 | SHA256（运行前后相同） |", "|---|---|"]
    lines += ["| %s | `%s` |" % (row["file"], row["sha256_after"]) for row in checks["sources"]]
    lines += ["", "复核文件：[完整校验](verification.json) · [逐组/月汇总](summary.json) · [CSV 体检](profile.txt) · [异常标注](anomalies.csv) · [原件来源明细](details.csv)。"]
    return "\n".join(lines) + "\n"


def run(output):
    Workbook, load_workbook = dependencies()
    output.mkdir(parents=True, exist_ok=False)
    # Declared and saved before data generation; never tuned from observed values.
    write_json(output / "rules.json", RULES)
    inputs = create_inputs(output / "inputs", Workbook)
    hashes = {path: digest(path) for path in inputs}
    tables = [(path, load_table(path, "明细", load_workbook)[1]) for path in inputs]
    source_rows = [row for _, table in tables for _, row in table]
    steps = [run_step("merge", ROOT / "skills/excel-processing/scripts/merge_xlsx.py",
                      [*inputs, "--sheet", "明细", "--out", output / "merged.xlsx"], output)]
    _, table = load_table(output / "merged.xlsx", "合并明细", load_workbook)
    rows = [row for _, row in table]
    provenance = check_provenance(tables, rows)
    summary = aggregate_rows(rows)
    write_json(output / "summary.json", summary)
    write_csv(output / "details.csv", FIELDS + PROVENANCE, [[row.get(field) for field in FIELDS + PROVENANCE] for row in rows])
    write_csv(output / "grouped.csv", ("月份", "分组", "销售额"),
              [(row["month"], row["region"] + "/" + row["channel"], row["sales"]) for row in summary["groups"]])
    steps.append(run_step("profile", ROOT / "skills/report-making/scripts/csv_profile.py",
                          [output / "details.csv", "--key", ",".join(KEY), "--max-values", "5"], output))
    steps.append(run_step("anomaly", ROOT / "skills/report-making/scripts/anomaly_flag.py",
                          [output / "grouped.csv", "--period", "月份", "--value", "销售额", "--by", "分组",
                           "--pct", RULES["pct"], "--min-abs", RULES["min_abs"], "--window", RULES["window"],
                           "--sigma", RULES["sigma"], "--out", output / "anomalies.csv"], output))
    with (output / "anomalies.csv").open(encoding="utf-8-sig", newline="") as handle:
        flagged = [row for row in csv.DictReader(handle) if row["标记"]]
    source_sales = sum((Decimal(str(row["销售额"])) for row in source_rows if row["销售额"] is not None), Decimal(0))
    merged_sales = sum((Decimal(str(row["销售额"])) for row in rows if row["销售额"] is not None), Decimal(0))
    grouped_sales = sum((Decimal(row["known_sales"]) for row in summary["groups"]), Decimal(0))
    monthly_sales = sum((Decimal(row["known_sales"]) for row in summary["monthly"]), Decimal(0))
    source_orders = sum(row["订单数"] for row in source_rows)
    if not (source_sales == merged_sales == grouped_sales == monthly_sales and
            source_orders == sum(row["orders"] for row in summary["groups"]) == sum(row["orders"] for row in summary["monthly"])):
        raise DemoError("独立金额/订单汇总校验失败，不能生成业务结论")
    sources = [{"file": str(path.relative_to(output)), "sha256_before": hashes[path], "sha256_after": digest(path)} for path in inputs]
    if not all(item["sha256_before"] == item["sha256_after"] for item in sources):
        raise DemoError("原件 SHA256 已改变，不能声称只读验收")
    missing = [row for row in rows if row["销售额"] is None or row["退款订单数"] is None]
    checks = {"synthetic_demo": True, "source_rows": len(source_rows), "merged_rows": len(rows),
              "provenance_rows_verified": provenance, "source_hashes_unchanged": True, "sources": sources,
              "known_sales_source": format(source_sales, ".2f"), "known_sales_merged": format(merged_sales, ".2f"),
              "known_sales_grouped": format(grouped_sales, ".2f"), "known_sales_monthly": format(monthly_sales, ".2f"),
              "orders_source": source_orders, "anomaly_count": len(flagged),
              "missing_sales_rows": sum(row["销售额"] is None for row in rows),
              "missing_refund_rows": sum(row["退款订单数"] is None for row in rows),
              "steps": steps, "python_version": sys.version.split()[0],
              "openpyxl_version": sys.modules["openpyxl"].__version__, "skill_versions": {}}
    for slug in ("excel-processing", "report-making"):
        path = ROOT / "skills" / slug / "SKILL.md"
        match = re.search(r"^version:\s*([^\s]+)", path.read_text(), re.MULTILINE)
        checks["skill_versions"][slug] = {"version": match.group(1).strip("\"'") if match else None, "skill_md_sha256": digest(path)}
    write_text(output / "report.md", report(summary, checks, flagged, missing))
    checks["artifacts"] = [{"file": str(path.relative_to(output)), "sha256": digest(path)} for path in sorted(output.rglob("*")) if path.is_file()]
    write_json(output / "verification.json", checks)
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线合成办公工作流；只写新的输出目录，不安装依赖")
    parser.add_argument("--out-dir", required=True, help="全新的输出目录；已存在时拒绝覆盖")
    args = parser.parse_args(argv)
    output = Path(args.out_dir).expanduser().resolve()
    if output.exists():
        print("输出目录已存在，拒绝覆盖：%s；请换一个 --out-dir。" % output, file=sys.stderr)
        return 1
    try:
        checks = run(output)
        print(json.dumps({"synthetic_demo": True, "report": str(output / "report.md"),
                          "rows_verified": checks["provenance_rows_verified"], "anomalies": checks["anomaly_count"],
                          "missing_sales_rows": checks["missing_sales_rows"], "source_hashes_unchanged": True}, ensure_ascii=False, indent=2))
        return 0
    except DemoError as exc:
        print(str(exc), file=sys.stderr)
        return 3 if "缺少 openpyxl" in str(exc) else 1
    except (OSError, subprocess.SubprocessError) as exc:
        print("运行失败：%s；保留已有文件，请用新目录重跑。" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
