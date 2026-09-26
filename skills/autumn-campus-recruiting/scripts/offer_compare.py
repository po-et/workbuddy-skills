#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""秋招 offer 相对比较：读你填写的 offer CSV，按你给的权重打分排序。

只做相对比较：不算个税、不算社保个人部分，结果不是到手收入。只用 Python 标准库。

用法：
  python3 offer_compare.py --template > offers.csv
  python3 offer_compare.py offers.csv --weights "现金=4,公积金=1,通勤=2,成长=3,兴趣=2"
  python3 offer_compare.py offers.csv --out result.md
  cat offers.csv | python3 offer_compare.py -

必填列：公司,城市,税前月薪,月数,公积金比例,单程通勤分钟,成长自评,兴趣自评
可选列：公积金基数（不填按税前月薪）、城市自评（1–5，把生活成本、户口、离家远近折算进去）
以 # 开头的行会被跳过（模板里的示例行就是这样）。

退出码：0 成功；1 输入内容或参数错误；2 文件读写失败；130 按了 Ctrl+C。
"""

import argparse
import csv
import io
import math
import os
import re
import sys
import tempfile

REQUIRED_COLS = ["公司", "城市", "税前月薪", "月数", "公积金比例", "单程通勤分钟", "成长自评", "兴趣自评"]
OPTIONAL_COLS = ["公积金基数", "城市自评"]

# 评分项，以及它依赖的列（列留空只在该项权重为 0 时允许）
CRITERIA = ["现金", "公积金", "通勤", "成长", "兴趣", "城市"]
CRITERION_COLS = {
    "现金": ["税前月薪", "月数"],
    "公积金": ["公积金比例"],
    "通勤": ["单程通勤分钟"],
    "成长": ["成长自评"],
    "兴趣": ["兴趣自评"],
    "城市": ["城市自评"],
}
ALIASES = {
    "薪资": "现金", "工资": "现金", "年薪": "现金", "cash": "现金", "salary": "现金",
    "hf": "公积金", "commute": "通勤", "growth": "成长", "interest": "兴趣", "city": "城市",
}
DEFAULT_COMMUTE_CAP = 120.0
CLOSE_GAP = 3.0  # 前两名相差不到这个分数，提示「接近」（经验提示，不是标准）
MAX_ERRORS = 10

TEMPLATE = (
    "公司,城市,税前月薪,月数,公积金比例,单程通勤分钟,成长自评,兴趣自评,公积金基数,城市自评\n"
    "#A公司（示例行：以#开头的行会被跳过，照格式填你自己的 offer）,上海,18000,15,7%,50,4,3,,4\n"
    "#B公司（示例行）,杭州,16000,16,12%,20,3,4,10000,4\n"
)


class UsageError(Exception):
    """参数错误，退出码 1。"""


class InputError(Exception):
    """CSV 内容错误，退出码 1。"""


class FileError(Exception):
    """文件读写失败，退出码 2。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError("参数错误：%s（用 --help 看用法）" % message)


def build_parser():
    p = Parser(
        prog="offer_compare.py",
        description="秋招 offer 相对比较：按你给的权重打分排序。不算个税，只做相对比较。",
        epilog="退出码：0 成功；1 输入或参数错误；2 文件读写失败；130 中断。",
    )
    p.add_argument("csv", nargs="?", help="offer CSV 路径；写 - 表示从标准输入读")
    p.add_argument("--weights", help="权重，如 \"现金=4,公积金=1,通勤=2,成长=3,兴趣=2\"；不给则等权")
    p.add_argument("--commute-cap", type=float, default=DEFAULT_COMMUTE_CAP,
                   help="单程通勤达到多少分钟记 0 分（默认 120）")
    p.add_argument("--out", help="把结果另存为 Markdown 文件（先写临时文件再替换）")
    p.add_argument("--template", action="store_true", help="打印 CSV 模板（表头 + 两行 # 示例）")
    return p


# ---------------------------------------------------------------- 读取

def read_text(path):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            raise FileError("找不到文件：%s（检查路径，或先用 --template 生成模板）" % path)
        except IsADirectoryError:
            raise FileError("%s 是文件夹，不是 CSV 文件" % path)
        except OSError as exc:
            raise FileError("读不了文件 %s：%s" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise FileError("文件既不是 UTF-8 也不是 GB18030 编码：请在表格软件里另存为「CSV UTF-8」")


UNIT_SUFFIXES = ("元/月", "/月", "个月", "分钟", "min", "薪", "元", "月", "分")


def parse_number(raw, col, line, errors):
    s = raw.strip()
    for ch in (",", "，", " ", "¥", "￥"):
        s = s.replace(ch, "")
    for suf in UNIT_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            s = s[:-len(suf)]
            break
    mult = 1.0
    if s[-1:] in ("k", "K"):
        mult, s = 1000.0, s[:-1]
    elif s.endswith("万"):
        mult, s = 10000.0, s[:-1]
    try:
        v = float(s) * mult
    except ValueError:
        errors.append("第 %d 行「%s」不是数字：%r" % (line, col, raw))
        return None
    if not math.isfinite(v):
        errors.append("第 %d 行「%s」不是有效数字：%r" % (line, col, raw))
        return None
    return v


def parse_ratio(raw, line, errors, warnings):
    s = raw.strip().replace(" ", "")
    pct = s.endswith("%") or s.endswith("％")
    if pct:
        s = s[:-1]
    v = parse_number(s, "公积金比例", line, errors)
    if v is None:
        return None
    if pct or v >= 1:
        v = v / 100.0
    if v < 0 or v > 0.5:
        errors.append("第 %d 行「公积金比例」%r 不合理：填单边比例，如 12%% 或 0.12" % (line, raw))
        return None
    if v > 0.12:
        warnings.append("第 %d 行公积金比例 %.1f%% 偏高：确认没有把单位和个人合计填进来"
                        "（脚本按单边比例 × 2 估算）" % (line, v * 100))
    return v


def load_rows(text):
    reader = csv.reader(io.StringIO(text))
    header = None
    for row in reader:
        if any(c.strip() for c in row):
            header = [c.strip().lstrip("\ufeff") for c in row]
            break
    if header is None:
        raise InputError("文件是空的：先用 --template 生成模板再填写")
    dup = sorted(set(h for h in header if h and header.count(h) > 1))
    if dup:
        raise InputError("表头有重复的列：%s" % "、".join(dup))
    missing = [c for c in REQUIRED_COLS if c not in header]
    if missing:
        raise InputError("缺少必填列：%s（表头应为：%s；可用 --template 生成）"
                         % ("、".join(missing), ",".join(REQUIRED_COLS)))
    rows, skipped, errors = [], 0, []
    for row in reader:
        line = reader.line_num
        if not any(c.strip() for c in row):
            continue
        if row[0].strip().startswith("#"):
            skipped += 1
            continue
        if len(row) > len(header):
            errors.append("第 %d 行比表头多了 %d 列：数字里是不是用了英文逗号（如 18,000）？改成 18000"
                          % (line, len(row) - len(header)))
            continue
        row = row + [""] * (len(header) - len(row))
        rows.append((line, dict((h, row[i].strip()) for i, h in enumerate(header) if h)))
    if errors:
        raise InputError("\n".join(errors[:MAX_ERRORS]))
    if not rows:
        raise InputError("没有可比较的 offer：除表头和 # 开头的行外没有数据")
    return header, rows, skipped


# ---------------------------------------------------------------- 权重

def available_criteria(header, rows):
    out = ["现金", "公积金", "通勤", "成长", "兴趣"]
    if "城市自评" in header and any(r["城市自评"] for _, r in rows):
        out.append("城市")
    return out


def parse_weights(spec, available, header):
    if spec is None:
        return dict((c, 1.0) for c in available), "未提供 --weights，已按各项等权计算 [待确认：请按你的真实优先级给权重]"
    weights = dict((c, 0.0) for c in available)
    seen = set()
    for item in re.split(r"[,，;；\s]+", spec.strip()):
        if not item:
            continue
        m = re.match(r"^(.+?)[=:：](.+)$", item)
        if not m:
            raise UsageError("权重「%s」格式不对，应写成 名称=数字，如 现金=4" % item)
        name, val = m.group(1).strip(), m.group(2).strip()
        name = ALIASES.get(name.lower(), name)
        if name not in CRITERIA:
            raise UsageError("不认识的权重名「%s」，可用：%s" % (name, "、".join(CRITERIA)))
        if name == "城市" and "城市" not in available:
            if "城市自评" in header:
                raise UsageError("给了「城市」权重，但「城市自评」列是空的：填上 1–5 分，或去掉城市权重")
            raise UsageError("给了「城市」权重，但 CSV 没有「城市自评」列：加上这一列（1–5 分），或去掉城市权重")
        if name in seen:
            raise UsageError("权重「%s」写了两次" % name)
        try:
            v = float(val)
        except ValueError:
            raise UsageError("权重「%s」的值不是数字：%r" % (name, val))
        if not math.isfinite(v) or v < 0:
            raise UsageError("权重「%s」必须是不小于 0 的数字" % name)
        weights[name] = v
        seen.add(name)
    if sum(weights.values()) <= 0:
        raise UsageError("权重全是 0，没法比较：至少给一项大于 0 的权重")
    zero = [c for c in available if weights[c] == 0]
    note = "未给或为 0 的项不参与打分：%s" % "、".join(zero) if zero else ""
    return weights, note


# ---------------------------------------------------------------- 校验与计算

def validate(rows, weights):
    errors, warnings, offers = [], [], []
    names = {}
    for line, r in rows:
        name = r["公司"]
        if not name:
            errors.append("第 %d 行「公司」为空" % line)
            continue
        if name in names:
            errors.append("第 %d 行公司「%s」与第 %d 行重复：同一公司不同城市请写成「%s-%s」这样区分"
                          % (line, name, names[name], name, r["城市"] or "城市"))
            continue
        names[name] = line
        for crit, cols in CRITERION_COLS.items():
            if weights.get(crit, 0) > 0:
                for col in cols:
                    if not r.get(col):
                        errors.append("第 %d 行「%s」为空：补上，或把「%s」权重设为 0" % (line, col, crit))
        o = {"line": line, "公司": name, "城市": r["城市"] or "[待补]"}
        o["月薪"] = parse_number(r["税前月薪"], "税前月薪", line, errors) if r["税前月薪"] else None
        o["月数"] = parse_number(r["月数"], "月数", line, errors) if r["月数"] else None
        o["比例"] = parse_ratio(r["公积金比例"], line, errors, warnings) if r["公积金比例"] else None
        o["基数"] = parse_number(r.get("公积金基数", ""), "公积金基数", line, errors) if r.get("公积金基数") else None
        o["通勤"] = parse_number(r["单程通勤分钟"], "单程通勤分钟", line, errors) if r["单程通勤分钟"] else None
        for col in ("成长自评", "兴趣自评", "城市自评"):
            o[col] = parse_number(r[col], col, line, errors) if r.get(col) else None
        if o["月薪"] is not None and o["月薪"] <= 0:
            errors.append("第 %d 行「税前月薪」必须大于 0" % line)
        elif o["月薪"] is not None and o["月薪"] < 1000:
            warnings.append("第 %d 行税前月薪 %.0f 不到 1000：确认单位是「元/月」，不是「千元」" % (line, o["月薪"]))
        if o["月数"] is not None and not 1 <= o["月数"] <= 24:
            errors.append("第 %d 行「月数」应在 1–24 之间，实际 %g" % (line, o["月数"]))
        elif o["月数"] is not None and o["月数"] < 12:
            warnings.append("第 %d 行月数 %g 少于 12：确认没有把年终奖月数单独填进来" % (line, o["月数"]))
        if o["基数"] is not None and o["基数"] <= 0:
            errors.append("第 %d 行「公积金基数」必须大于 0" % line)
        if o["通勤"] is not None and not 0 <= o["通勤"] <= 600:
            errors.append("第 %d 行「单程通勤分钟」应在 0–600 之间，实际 %g" % (line, o["通勤"]))
        for col in ("成长自评", "兴趣自评", "城市自评"):
            if o[col] is not None and not 1 <= o[col] <= 5:
                errors.append("第 %d 行「%s」应为 1–5 分，实际 %g" % (line, col, o[col]))
        offers.append(o)
    if errors:
        more = "\n……另有 %d 处问题未列出" % (len(errors) - MAX_ERRORS) if len(errors) > MAX_ERRORS else ""
        raise InputError("\n".join(errors[:MAX_ERRORS]) + more)
    for o in offers:
        o["年度现金"] = o["月薪"] * o["月数"] if o["月薪"] is not None and o["月数"] is not None else None
        base = o["基数"] if o["基数"] is not None else o["月薪"]
        if weights.get("公积金", 0) > 0 and base is None:
            raise InputError("第 %d 行算公积金需要「公积金基数」或「税前月薪」，两列都为空" % o["line"])
        o["公积金年额"] = base * o["比例"] * 2 * 12 if base is not None and o["比例"] is not None else None
    return offers, warnings


def raw_scores(offers, weights, cap):
    notes = []
    scores = [dict() for _ in offers]
    if weights.get("现金", 0) > 0:
        top = max(o["年度现金"] for o in offers)
        for s, o in zip(scores, offers):
            s["现金"] = o["年度现金"] / top
    if weights.get("公积金", 0) > 0:
        top = max(o["公积金年额"] for o in offers)
        for s, o in zip(scores, offers):
            s["公积金"] = o["公积金年额"] / top if top > 0 else 0.0
        if top <= 0:
            notes.append("各 offer 公积金都为 0，这一项不影响排序")
    if weights.get("通勤", 0) > 0:
        for s, o in zip(scores, offers):
            s["通勤"] = max(0.0, 1.0 - o["通勤"] / cap)
    for crit, col in (("成长", "成长自评"), ("兴趣", "兴趣自评"), ("城市", "城市自评")):
        if weights.get(crit, 0) > 0:
            for s, o in zip(scores, offers):
                s[crit] = (o[col] - 1.0) / 4.0
    return scores, notes


def totals(scores, weights):
    wsum = sum(weights.values())
    return [sum(weights[c] * s.get(c, 0.0) for c in weights if weights[c] > 0) / wsum * 100 for s in scores]


def ranking(offers, tot):
    idx = list(range(len(offers)))
    idx.sort(key=lambda i: (-round(tot[i], 9), -(offers[i]["年度现金"] or 0), i))
    return idx


def sensitivity(offers, scores, weights):
    base_top = ranking(offers, totals(scores, weights))[0]
    active = [c for c in CRITERIA if weights.get(c, 0) > 0]
    if len(offers) < 2:
        return base_top, []
    if len(active) < 2:
        return base_top, ["只有「%s」一项参与打分，排名完全由它决定，不做敏感性检查" % active[0]]
    flips, checked = [], 0
    for crit in active:
        for factor, label in ((1.5, "提高一半"), (0.5, "降低一半")):
            w2 = dict(weights)
            w2[crit] = weights[crit] * factor
            top = ranking(offers, totals(scores, w2))[0]
            checked += 1
            if top != base_top:
                flips.append("「%s」权重%s：第一名变成 %s" % (crit, label, offers[top]["公司"]))
    if not flips:
        flips = ["每项权重分别提高一半或降低一半（共 %d 种），第一名都是 %s，结论较稳" % (checked, offers[base_top]["公司"])]
    return base_top, flips


# ---------------------------------------------------------------- 输出

def money(v):
    return "—" if v is None else "{:,.0f}".format(v)


def num(v):
    return "—" if v is None else "%g" % v


def render(src, enc, skipped, offers, weights, weight_note, warnings, cap):
    scores, notes = raw_scores(offers, weights, cap)
    tot = totals(scores, weights)
    order = ranking(offers, tot)
    base_top, sens = sensitivity(offers, scores, weights)
    active = [c for c in CRITERIA if weights.get(c, 0) > 0]
    wsum = sum(weights.values())
    has_city = any(o["城市自评"] is not None for o in offers)
    out = ["## offer 相对比较（不算个税，只做相对比较）", ""]
    out.append("读取：%s（%s），%d 个 offer%s" % (
        src, "UTF-8" if enc == "utf-8-sig" else "GB18030", len(offers),
        "，跳过 %d 行 # 开头的行" % skipped if skipped else ""))
    out.append("权重（归一化后）：" + " ｜ ".join("%s %.2f" % (c, weights[c] / wsum) for c in active))
    if weight_note:
        out.append("说明：" + weight_note)
    out.append("")
    head = ["排名", "公司", "城市", "总分", "年度现金（税前）", "公积金年额（估）", "单程通勤", "成长", "兴趣"]
    if has_city:
        head.append("城市自评")
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "---|" * len(head))
    for rank, i in enumerate(order, 1):
        o = offers[i]
        cells = [str(rank), o["公司"], o["城市"], "%.1f" % tot[i], money(o["年度现金"]), money(o["公积金年额"]),
                 "—" if o["通勤"] is None else "%g 分钟" % o["通勤"], num(o["成长自评"]), num(o["兴趣自评"])]
        if has_city:
            cells.append(num(o["城市自评"]))
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    out.append("各项得分（0–1，1 为最好）：")
    out.append("")
    out.append("| 公司 | " + " | ".join(active) + " |")
    out.append("|" + "---|" * (len(active) + 1))
    for i in order:
        out.append("| %s | %s |" % (offers[i]["公司"], " | ".join("%.2f" % scores[i][c] for c in active)))
    out.append("")
    if len(offers) == 1:
        out.append("提示：只有 1 个 offer，排序没有意义，各项得分仅供参考。")
    else:
        gap = tot[order[0]] - tot[order[1]]
        if gap < CLOSE_GAP:
            out.append("提示：前两名只差 %.1f 分（不到 %g 分），属于接近——别只看分数，回到三个问题再想一次。"
                       % (gap, CLOSE_GAP))
        out.append("敏感性检查：")
        out.extend("- " + s for s in sens)
    if notes or warnings:
        out.append("")
        out.append("需要你核对：")
        out.extend("- " + s for s in notes + warnings)
    out.append("")
    out.append("假设与口径：")
    out.append("1. 年度现金 = 税前月薪 × 月数：不扣个税和社保个人部分，不含签字费、股票期权、补贴和不确定的绩效奖金，"
               "只用于相对比较，不是到手收入。")
    out.append("2. 公积金年额（估）= 缴存基数 × 比例 × 2 × 12：「× 2」按单位与个人同比例缴存估算；未填「公积金基数」时"
               "用税前月薪代替。实际基数、比例和当地上下限以合同和当地公积金管理中心为准。")
    out.append("3. 现金、公积金得分 = 本项 ÷ 各 offer 最高值（最高者记 1）。")
    out.append("4. 通勤得分 = 1 − 单程分钟 ÷ %g，不低于 0（单程 %g 分钟及以上记 0；--commute-cap 可改）。" % (cap, cap))
    out.append("5. 自评得分 = (自评 − 1) ÷ 4：1 分记 0，5 分记 1；自评是你自己的判断，脚本不替你评。")
    out.append("6. 总分 = Σ(权重 × 单项得分) ÷ Σ权重 × 100。")
    out.append("7. 城市本身不打分；生活成本、户口、离家远近等请折算进「城市自评」列。")
    out.append("")
    out.append("分数只帮你看清取舍，不替你做决定。")
    return "\n".join(out) + "\n"


def write_atomic(path, text):
    target = os.path.abspath(path)
    folder = os.path.dirname(target)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".offer_compare-", suffix=".tmp", dir=folder)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)  # mkstemp 默认 600，改回普通文件权限
        os.replace(tmp, target)
    except OSError as exc:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise FileError("写不了文件 %s：%s（检查文件夹是否存在、有没有写权限）" % (path, exc.strerror or exc))


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.template:
        sys.stdout.write(TEMPLATE)
        return 0
    if not args.csv:
        raise UsageError("缺少 CSV 文件路径：python3 offer_compare.py offers.csv（没有文件先用 --template 生成）")
    if not args.commute_cap > 0:
        raise UsageError("--commute-cap 必须大于 0")
    text, enc = read_text(args.csv)
    header, rows, skipped = load_rows(text)
    avail = available_criteria(header, rows)
    weights, note = parse_weights(args.weights, avail, header)
    offers, warnings = validate(rows, weights)
    report = render("标准输入" if args.csv == "-" else os.path.basename(args.csv), enc, skipped,
                    offers, weights, note, warnings, args.commute_cap)
    sys.stdout.write(report)
    if args.out:
        write_atomic(args.out, report)
        sys.stderr.write("已写入 %s\n" % args.out)
    return 0


def run(argv=None):
    try:
        return main(argv)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有写任何文件。\n")
        return 130
    except (UsageError, InputError) as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return 1
    except FileError as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(run())
