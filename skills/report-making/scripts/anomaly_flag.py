#!/usr/bin/env python3
"""按「先定规则再看数据」给指标序列标异常：环比超阈值且绝对变化够大，或超出近 N 期均值 ± k 倍标准差。

用法：
  python3 scripts/anomaly_flag.py 周汇总.csv --period 周 --value 销售额 --by 区域 --min-abs 30
  python3 scripts/anomaly_flag.py 周汇总.csv --period 周 --value 销售额 --out 周汇总_标注.csv

输入是已经汇总好的表：一期一行（有 --by 时是每个维度一期一行），按时间先后排好。
默认规则（和 SKILL.md 第 4 步一致，按业务波动调整）：
  规则一：环比变化超过 ±20%（--pct），且绝对变化不小于 --min-abs（小基数的 20% 没意义）
  规则二：超出前 8 期（--window）均值 ± 2 倍（--sigma）样本标准差；不足 8 期时跳过这条
两条规则都要求绝对变化不小于 --min-abs：小基数序列波动小、标准差也小，不设下限会被频繁标出。
上期为 0 或空时环比显示「—」，不参与规则一。

退出码：0 完成（标出的异常写在报告里）；1 参数或内容有误（列名不对、同一期出现两次、没有可用数字）；
        2 文件读写失败；130 手动中断（Ctrl+C）。写 --out 时先写临时文件再替换，中途失败不会留下半个文件。
只用 Python 标准库。
"""

import argparse
import csv
import io
import math
import os
import statistics
import sys
import tempfile
from pathlib import Path


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FriendlyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/anomaly_flag.py 周汇总.csv --period 周 --value 销售额）" % message,
              file=sys.stderr)
        sys.exit(1)


def read_rows(path):
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        raise InputError(2, "%s 是 Excel 文件：先另存为 CSV UTF-8" % p.name)
    if not p.is_file():
        raise InputError(2, "找不到文件 %s：检查路径和文件名" % path)
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise InputError(2, "读不了 %s（%s）：文件可能正被 Excel 打开" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise InputError(2, "编码认不出来：在 Excel 里另存为 CSV UTF-8")
    first = text.split("\n", 1)[0]
    try:
        delim = csv.Sniffer().sniff(first, delimiters=",;\t").delimiter
    except csv.Error:
        delim = ","
    reader = csv.reader(io.StringIO(text), delimiter=delim, strict=True)
    rows = []
    try:
        header = [h.strip() for h in next(reader, [])]
        if not header or any(not h for h in header):
            raise InputError(1, "表头有空列名：先补全列名再标异常")
        if len(set(header)) != len(header):
            raise InputError(1, "表头重复：改成不同的列名，避免金额列被覆盖")
        for values in reader:
            if not any(v.strip() for v in values):
                continue
            if len(values) != len(header):
                raise InputError(1, "第 %d 行有 %d 列，表头有 %d 列：核对分隔符，包含逗号的金额要加引号"
                                 % (reader.line_num, len(values), len(header)))
            rows.append((reader.line_num, dict(zip(header, values))))
    except csv.Error as exc:
        raise InputError(1, "第 %d 行 CSV 格式有误（%s）：检查引号和分隔符" % (reader.line_num, exc))
    if not header or not rows:
        raise InputError(1, "文件里没有表头或数据行")
    return header, rows


def to_number(raw):
    s = (raw or "").strip().replace(",", "").replace("，", "").replace(" ", "")
    if s.endswith("%"):
        s = s[:-1]
    value = float(s)
    if not math.isfinite(value):
        raise ValueError("不是有限数字")
    return value


def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".") if v is not None else "—"


def flag_series(points, pct, min_abs, window, sigma):
    """points: [(期, 值)] → [(期, 值, 环比或 None, 标记, 触发说明)]"""
    out = []
    for i, (period, value) in enumerate(points):
        prev = points[i - 1][1] if i else None
        reasons = []
        if value is None:                       # 这一期的值无效：不算环比，也不拿它当下一期的基数
            out.append((period, None, None, "", "值无效，已跳过"))
            continue
        mom = value / prev - 1 if prev not in (None, 0) else None
        if mom is not None and abs(mom) > pct / 100 and abs(value - prev) >= min_abs:
            reasons.append("环比超过 ±%g%% 且变化 %s ≥ %s" % (pct, fmt(abs(value - prev)), fmt(min_abs)))
        hist = [v for _, v in points[max(0, i - window):i] if v is not None]
        if i >= window and len(hist) == window:
            mean, sd = statistics.mean(hist), statistics.stdev(hist)
            if abs(value - mean) > sigma * sd and abs(value - mean) >= min_abs:
                reasons.append("超出前 %d 期均值 %s ± %g 倍标准差（标准差 %s）" % (window, fmt(mean), sigma, fmt(sd)))
        base = prev if prev is not None else (hist[-1] if hist else value)
        mark = ("▲" if value > base else "▼") if reasons else ""
        out.append((period, value, mom, mark, "；".join(reasons)))
    return out


def write_atomic(path, header, records):
    target, tmp = Path(path), None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".csv", dir=str(target.parent))
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(records)
        os.replace(tmp, target)
    except OSError as exc:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
        raise InputError(2, "写不了 %s（%s）：目标文件可能正被 Excel 打开，或文件夹没有写权限" % (path, exc.strerror or exc))


def main(argv=None):
    p = FriendlyParser(description="给汇总好的指标序列标异常（环比阈值 + 近 N 期均值 ± k 倍标准差）。",
                       epilog="退出码：0 完成；1 参数或内容有误；2 文件读写失败；130 手动中断。")
    p.add_argument("file", help="汇总好的 CSV：一期一行（或每个维度一期一行），按时间排好")
    p.add_argument("--period", help="期次列名，默认第一列")
    p.add_argument("--value", help="指标列名，默认最后一列")
    p.add_argument("--by", help="维度列名，如 区域；不给就当成一条序列")
    p.add_argument("--pct", type=float, default=20, help="环比阈值（百分数），默认 20")
    p.add_argument("--min-abs", type=float, help="绝对变化下限，小于它的波动不算异常；不给按 0 处理")
    p.add_argument("--window", type=int, default=8, help="规则二看前几期，默认 8")
    p.add_argument("--sigma", type=float, default=2, help="规则二的标准差倍数，默认 2")
    p.add_argument("--out", help="另存一份带「环比、标记、触发规则」三列的 CSV")
    args = p.parse_args(argv)
    try:
        if not math.isfinite(args.pct) or not math.isfinite(args.sigma) or args.pct <= 0 or args.window < 2 or args.sigma <= 0:
            raise InputError(1, "--pct、--sigma 要是大于 0 的有限数字，--window 至少 2")
        if args.min_abs is not None and (not math.isfinite(args.min_abs) or args.min_abs < 0):
            raise InputError(1, "--min-abs 要是不小于 0 的有限数字")
        header, rows = read_rows(args.file)
        period_col = args.period or header[0]
        value_col = args.value or header[-1]
        for name, col in (("--period", period_col), ("--value", value_col), ("--by", args.by)):
            if col and col not in header:
                raise InputError(1, "%s 的列「%s」不在表头里；表头是：%s" % (name, col, "、".join(header)))
        if args.out and Path(args.out).resolve() == Path(args.file).resolve():
            raise InputError(1, "--out 不能和输入文件同名：原件只读，另存一份")
        min_abs = args.min_abs if args.min_abs is not None else 0.0

        series, skipped, seen = {}, [], set()
        for line, r in rows:
            group = (r.get(args.by) or "").strip() if args.by else "全部"
            period = (r.get(period_col) or "").strip()
            if not period or not group:
                raise InputError(1, "第 %d 行期次或维度为空：先补全再标异常" % line)
            try:
                value = to_number(r.get(value_col))
            except ValueError:
                skipped.append("第 %d 行 %s=%r 不是有限数字" % (line, value_col, r.get(value_col)))
                value = None
            if (group, period) in seen:
                raise InputError(1, "第 %d 行：%s %s 出现了两次——先汇总成一期一行再标异常" % (line, group, period))
            seen.add((group, period))
            series.setdefault(group, []).append((period, value))
        if not any(v is not None for pts in series.values() for _, v in pts):
            raise InputError(1, "没有可用的数字：%s" % "；".join(skipped[:3]))

        print("规则一：环比超过 ±%g%%；规则二：超出前 %d 期均值 ± %g 倍标准差；两条都要求绝对变化 ≥ %s"
              % (args.pct, args.window, args.sigma, fmt(min_abs)))
        if args.min_abs is None:
            print("  [待确认] 没给 --min-abs，小基数的变化也会被标出；按业务定一个「变化多少才值得看」的下限")
        for msg in skipped:
            print("  跳过：%s，这一期和下一期都不算环比（改成纯数字后重跑）" % msg)

        flagged, records = [], []
        for group, points in series.items():
            periods = [pp for pp, _ in points]
            if periods != sorted(periods):
                print("  [待确认] %s 的期次不是从小到大排的，按文件顺序计算；确认顺序是时间先后" % group)
            result = flag_series(points, args.pct, min_abs, args.window, args.sigma)
            if len(points) < args.window + 1:
                print("  %s 只有 %d 期，不足 %d 期，规则二跳过" % (group, len(points), args.window + 1))
            print("【%s】" % group)
            for period, value, mom, mark, why in result:
                mom_s = "—" if mom is None else "%+.1f%%" % (mom * 100)
                print("  %s  %s  环比 %s  %s%s" % (period, fmt(value), mom_s, mark or " ", ("  ← " + why) if why else ""))
                records.append([group, period, fmt(value), mom_s, mark, why])
                if mark:
                    flagged.append((group, period, value, mom_s, mark, why))

        print("标出的异常 %d 条（每条补上「原因—影响—动作」，原因没确认就写待查）：" % len(flagged))
        for group, period, value, mom_s, mark, why in flagged:
            print("  现象：%s %s %s %s，环比 %s（%s）｜原因：待查，负责人 ____｜影响：____｜动作：____"
                  % (group, period, value_col, mark, mom_s, why))
        if args.out:
            write_atomic(args.out, ["维度", "期", value_col, "环比", "标记", "触发规则"], records)
            print("已另存：%s" % args.out)
        return 0
    except InputError as exc:
        sys.stdout.flush()
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有写出任何文件", file=sys.stderr)
        sys.exit(130)
