#!/usr/bin/env python3
"""KPI 指标表自查：权重合计、单项范围、结果类占比、口径是否留空、红线是否混进权重。
只读，不改文件，只用 Python 标准库（3.6+）。

用法：
  python3 kpi_check.py kpi.csv
  python3 kpi_check.py kpi.csv --json
表头至少要有：指标、权重、口径；有「类型」列时，再查结果类权重合计是否不低于 60%。
权重可以写 35、35% 或 0.35（全部不超过 1 且合计约等于 1 时按比例理解，会提示）。
权重填 0 的行视为「只观察、不考核」，不计入指标个数，也不查 10%–40% 范围。

退出码：0 全部通过；1 参数错误；2 文件读不了；3 发现需要修改的问题；130 手动中断。
"""

import argparse
import csv
import io
import json
import sys

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_FOUND, EXIT_INTERRUPT = 0, 1, 2, 3, 130

# 表头别名：左边是规范名，右边是可以接受的写法
COLUMNS = {
    "指标": ("指标", "指标名称", "KPI", "kpi"),
    "类型": ("类型", "指标类型"),
    "权重": ("权重", "权重%", "权重(%)", "权重（%）"),
    "口径": ("口径", "计算口径", "定义", "口径定义"),
}
REQUIRED = ("指标", "权重", "口径")
W_MIN, W_MAX, RESULT_MIN = 10.0, 40.0, 60.0
COUNT_MIN, COUNT_MAX = 3, 6
# 最容易刷、也和价值无关的数：不要考
DO_NOT_SCORE = ("代码行数", "提交次数", "加班时长")


def zh(message):
    """把 argparse 的英文报错换成中文。"""
    for en, cn in (("the following arguments are required: ", "缺少必填参数："),
                   ("unrecognized arguments: ", "不认识的参数："),
                   ("invalid float value: ", "不是数字："),
                   ("invalid int value: ", "不是整数："),
                   ("invalid choice: ", "不在可选范围内："),
                   ("expected one argument", "后面要跟一个值")):
        message = message.replace(en, cn)
    return message


class Parser(argparse.ArgumentParser):
    """参数错误统一用退出码 1（argparse 默认是 2，和「文件读不了」撞车）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % zh(message))
        sys.exit(EXIT_ARGS)


def read_text(path):
    """按 UTF-8（含 BOM）读，失败再按 GB18030（兼容 GBK，Excel 另存 CSV 常见）读。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise IOError("找不到文件：%s（检查路径和文件名，或先把表格另存为 CSV）" % path)
    except IsADirectoryError:
        raise IOError("%s 是文件夹，不是 CSV 文件" % path)
    except PermissionError:
        raise IOError("没有权限读取：%s" % path)
    for enc, label in (("utf-8-sig", "UTF-8"), ("gb18030", "GB18030/GBK")):
        try:
            return raw.decode(enc), label
        except UnicodeDecodeError:
            continue
    raise IOError("无法识别 %s 的编码：请在表格软件里另存为「CSV UTF-8」再试" % path)


def find_columns(header):
    mapping = {}
    cleaned = [(h or "").strip() for h in header]
    for key, aliases in COLUMNS.items():
        for i, h in enumerate(cleaned):
            if h in aliases or h.replace(" ", "") in aliases:
                mapping[key] = i
                break
    return mapping


def parse_weight(text):
    s = (text or "").strip().replace("％", "%").rstrip("%").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def check(text):
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any((c or "").strip() for c in r)]
    if not rows:
        return {"error": "文件是空的：第一行应是表头（指标、类型、权重、口径），下面每行一个指标"}
    header, body = rows[0], rows[1:]
    cols = find_columns(header)
    missing = [k for k in REQUIRED if k not in cols]
    if missing:
        return {"error": "表头缺少：%s。当前表头是：%s。可以直接复制这行当表头：指标,类型,权重,口径"
                         % ("、".join(missing), ",".join(h.strip() for h in header))}

    def cell(r, key):
        i = cols.get(key)
        return (r[i] if i is not None and i < len(r) else "").strip()

    problems, notes, items = [], [], []
    for n, r in enumerate(body, start=2):
        name = cell(r, "指标") or "（第 %d 行未写指标名）" % n
        raw_w = cell(r, "权重")
        w = parse_weight(raw_w)
        if w is None:
            problems.append("第 %d 行「%s」：权重「%s」不是数字（写成 35、35%% 或 0.35）" % (n, name, raw_w))
        elif w < 0:
            problems.append("第 %d 行「%s」：权重是负数（%s）" % (n, name, raw_w))
        items.append({"row": n, "name": name, "type": cell(r, "类型"), "weight": w, "rule": cell(r, "口径")})

    weights = [it["weight"] for it in items if it["weight"] is not None and it["weight"] >= 0]
    if weights and all(w <= 1 for w in weights) and abs(sum(weights) - 1) < 0.011:
        for it in items:
            if it["weight"] is not None:
                it["weight"] *= 100
        notes.append("权重都不超过 1 且合计约为 1，已按比例理解（0.35 = 35%）；如果不是这个意思请改成百分数")

    scored = [it for it in items if it["weight"] is not None and it["weight"] > 0]
    watched = [it for it in items if it["weight"] == 0]
    total = sum(it["weight"] for it in scored)
    if abs(total - 100) > 0.01:
        problems.append("权重合计 %g%%，应为 100%%" % round(total, 2))
    if not COUNT_MIN <= len(scored) <= COUNT_MAX:
        problems.append("进考核的指标 %d 个，建议 %d–%d 个（太多等于没有重点，太少容易一项定生死）"
                        % (len(scored), COUNT_MIN, COUNT_MAX))
    if watched:
        notes.append("权重为 0、只观察不考核：%s" % "、".join(it["name"] for it in watched))

    seen = set()
    for it in items:
        name, w, rule = it["name"], it["weight"], it["rule"]
        if name in seen:
            problems.append("第 %d 行「%s」：指标名重复" % (it["row"], name))
        seen.add(name)
        if w is not None and w > 0 and not (W_MIN <= w <= W_MAX):
            why = "再低等于不考核" if w < W_MIN else "一项定生死，刷分动机最强"
            problems.append("第 %d 行「%s」：权重 %g%%，不在 %g%%–%g%% 之间（%s）" % (it["row"], name, w, W_MIN, W_MAX, why))
        if not rule:
            problems.append("第 %d 行「%s」：口径为空（写清分子、分母、周期、取数位置、剔除规则）" % (it["row"], name))
        elif rule.replace(" ", "") == name.replace(" ", ""):
            problems.append("第 %d 行「%s」：口径只是重复了指标名，换一个人读还是算不出同一个数" % (it["row"], name))
        if "待建数据" in rule and w:
            problems.append("第 %d 行「%s」：标了「待建数据」却有权重；取不到数的指标本期不进权重" % (it["row"], name))
        if any(bad in name for bad in DO_NOT_SCORE):
            problems.append("第 %d 行「%s」：最容易刷，也和价值无关，不要考；换成交付、质量或里程碑类结果指标" % (it["row"], name))
        if ("红线" in name or "一票否决" in name) and w:
            problems.append("第 %d 行「%s」：红线不进权重，单列为扣分或一票否决项" % (it["row"], name))

    result_total = None
    if "类型" in cols:
        result_total = sum(it["weight"] for it in scored if "结果" in it["type"])
        if scored and result_total < RESULT_MIN:
            problems.append("结果类权重合计 %g%%，低于 %g%%（过程指标用来预警和辅导，单独重押必被刷）"
                            % (round(result_total, 2), RESULT_MIN))
        untyped = [it["name"] for it in scored if not it["type"]]
        if untyped:
            notes.append("这些指标没填类型（结果/过程），没算进结果类合计：%s" % "、".join(untyped))
    else:
        notes.append("没有「类型」列，跳过结果类占比检查")

    return {"count": len(scored), "total": round(total, 2),
            "result_total": None if result_total is None else round(result_total, 2),
            "problems": problems, "notes": notes, "items": items}


def main(argv=None):
    ap = Parser(description="KPI 指标表自查（只读）。退出码：0 通过，1 参数错误，2 文件读不了，3 有问题要改，130 中断")
    ap.add_argument("csv_file", help="指标表 CSV，表头：指标,类型,权重,口径")
    ap.add_argument("--json", action="store_true", help="输出 JSON，便于程序处理")
    args = ap.parse_args(argv)

    try:
        text, enc = read_text(args.csv_file)
    except IOError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE
    try:
        res = check(text)
    except csv.Error as exc:
        sys.stderr.write("CSV 格式有误：%s（检查是否有未闭合的引号）\n" % exc)
        return EXIT_FILE

    if "error" in res:
        if args.json:
            print(json.dumps({"ok": False, "error": res["error"]}, ensure_ascii=False, indent=2))
        else:
            sys.stderr.write("无法检查：%s\n" % res["error"])
        return EXIT_ARGS

    if args.json:
        out = dict(res, ok=not res["problems"], encoding=enc)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        head = "读取 %s（%s）：进考核的指标 %d 个，权重合计 %g%%" % (args.csv_file, enc, res["count"], res["total"])
        if res["result_total"] is not None:
            head += "，其中结果类 %g%%" % res["result_total"]
        print(head)
        for p in res["problems"]:
            print("[需修改] " + p)
        for n in res["notes"]:
            print("[提示] " + n)
        print("结论：" + ("全部通过" if not res["problems"] else "%d 处需要修改" % len(res["problems"])))
    return EXIT_FOUND if res["problems"] else EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
