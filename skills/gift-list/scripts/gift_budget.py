#!/usr/bin/env python3
"""多人送礼预算核对：合计是否超总预算、超了从哪几项减；顺带查出
「老师档位不是 0」「同事超过 100 元」「同一群人差距太大」「职场送现金等价物」这类要改的行。
纯标准库，不联网，只读不写。

用法：
  python3 scripts/gift_budget.py 礼物清单.csv 3000
  python3 scripts/gift_budget.py 礼物清单.csv 3千 --json

CSV 表头（至少要有「对象」和「预算」两列，其余列有就用）：
  对象,关系,场合,档位,方向（品类）,限制与备注,预算,状态
用 Excel 另存的 CSV（UTF-8 或 GBK）都能读。

退出码：
  0   合计没超总预算，也没有要改的行
  3   超了总预算，或有要改/要确认的行（会列出从哪几项减、哪几行要改）——不是程序出错
  1   参数不对，或表头缺「对象」「预算」列
  2   文件读不了（不存在、没权限、编码认不出）
  130 用户按 Ctrl+C 中断
"""
import argparse
import csv
import io
import json
import re
import sys

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_ATTENTION, EXIT_INTERRUPT = 0, 1, 2, 3, 130
DONE_STATES = ("已订", "已买", "已送", "已寄", "已写", "已付")
CASH_LIKE = re.compile(r"现金|红包|购物卡|储值卡|礼品卡|充值卡|代金券|卡券")
WORK_RELATIONS = ("同事", "上级", "领导", "老师", "客户", "下属")
HEADER_HINT = "对象,关系,场合,档位,方向（品类）,限制与备注,预算,状态"


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「文件读不了」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class InputProblem(Exception):
    """表头或数字不对 → 退出码 1。"""


class ReadProblem(Exception):
    """文件读不了 → 退出码 2。"""


def parse_money(text):
    """'3000' / '3,000' / '3千' / '0.3万' / '¥800' / '800元' → float；看不懂返回 None。"""
    s = str(text or "").strip().replace(",", "").replace("，", "").replace(" ", "")
    s = s.lstrip("¥￥").rstrip("元块")
    mult = 1
    if s[-1:] in ("万", "w", "W"):
        mult, s = 10000, s[:-1]
    elif s[-1:] in ("千", "k", "K"):
        mult, s = 1000, s[:-1]
    try:
        v = float(s) * mult
    except ValueError:
        return None
    return v if v >= 0 else None


def read_rows(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        raise ReadProblem("找不到文件：%s。确认路径，或直接把清单粘到对话里。" % path)
    except IsADirectoryError:
        raise ReadProblem("%s 是目录，请给 CSV 文件。" % path)
    except PermissionError:
        raise ReadProblem("没有权限读取 %s。" % path)
    except OSError as e:
        raise ReadProblem("读取 %s 失败：%s" % (path, e))
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ReadProblem("%s 的编码认不出来：用 Excel「另存为 CSV UTF-8」后再试。" % path)
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise InputProblem("%s 里没有数据行。第一行应是表头：%s" % (path, HEADER_HINT))
    headers = [h.strip() for h in (rows[0].keys()) if h]
    for need in ("对象", "预算"):
        if need not in headers:
            raise InputProblem("表头缺「%s」列（现在是：%s）。第一行应是：%s" % (need, ",".join(headers), HEADER_HINT))
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items() if k} for r in rows]


def analyse(rows, limit):
    items, flags = [], []
    for i, r in enumerate(rows, 2):  # 第 1 行是表头
        who, rel = r.get("对象", "") or "（没写对象）", r.get("关系", "")
        raw = r.get("预算", "")
        money = parse_money(raw)
        if money is None:
            rng = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–~～至]\s*(\d+(?:\.\d+)?)\s*元?\s*", raw or "")
            if rng:
                money = float(rng.group(2))
                flags.append("第 %d 行 %s：预算写的是范围「%s」，按上限 %.0f 计 [待确认]" % (i, who, raw, money))
            else:
                money = 0.0
                flags.append("第 %d 行 %s：预算「%s」不是数字，按 0 计 [待确认]" % (i, who, raw or "空"))
        items.append({"row": i, "who": who, "rel": rel, "money": money, "state": r.get("状态", ""),
                      "direction": r.get("方向（品类）", "") or r.get("方向", ""), "note": r.get("限制与备注", "")})
        if "老师" in rel and money > 0:
            flags.append("第 %d 行 %s：老师档位应为 0 元，只送心意、不送有价物品（以学校和当地规定为准）" % (i, who))
        if "同事" in rel and money > 100:
            flags.append("第 %d 行 %s：同事建议 100 元以内、全组统一，现在 %.0f 元" % (i, who, money))
        if "客户" in rel and money > 0 and not re.search(r"政策|上限|审批|规定", items[-1]["note"]):
            flags.append("第 %d 行 %s：客户礼先查本公司礼品政策（金额上限、审批登记），把上限写进备注" % (i, who))
        if any(w in rel for w in WORK_RELATIONS) and CASH_LIKE.search(items[-1]["direction"] + items[-1]["note"]):
            flags.append("第 %d 行 %s：职场、老师、客户不送现金、购物卡、储值卡这类现金等价物" % (i, who))
    # 同一群人差距太大（同一关系 ≥2 人且最高是最低的 2 倍以上）
    groups = {}
    for it in items:
        if it["rel"] and it["money"] > 0:
            groups.setdefault(it["rel"], []).append(it)
    for rel, members in groups.items():
        if len(members) >= 2:
            lo, hi = min(m["money"] for m in members), max(m["money"] for m in members)
            if hi > 2 * lo:
                flags.append("「%s」这一类 %d 人从 %.0f 到 %.0f 元，差距太大，同一群人尽量同档" % (rel, len(members), lo, hi))

    total = sum(it["money"] for it in items)
    cuts = []
    if total > limit:
        over = total - limit
        open_items = sorted((it for it in items if not any(s in it["state"] for s in DONE_STATES) and it["money"] > 0),
                            key=lambda it: -it["money"])
        covered = 0.0
        for it in open_items:
            if covered >= over:
                break
            cuts.append(it)
            covered += it["money"]
    return items, flags, total, cuts


def main(argv=None):
    ap = Parser(description="多人送礼预算核对（合计、超支削减建议、合规提醒）")
    ap.add_argument("csv", help="礼物清单 CSV 路径")
    ap.add_argument("limit", help="总预算，如 3000、3千、0.3万")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    limit = parse_money(args.limit)
    if limit is None or limit <= 0:
        ap.error("总预算「%s」看不懂：写成 3000、3千 或 0.3万" % args.limit)
    try:
        rows = read_rows(args.csv)
    except ReadProblem as e:
        sys.stderr.write("读取失败：%s\n" % e)
        return EXIT_IO
    except InputProblem as e:
        sys.stderr.write("清单有问题：%s\n" % e)
        return EXIT_INPUT
    except csv.Error as e:
        sys.stderr.write("清单有问题：CSV 格式坏了（%s），检查引号和逗号是否配对。\n" % e)
        return EXIT_INPUT

    items, flags, total, cuts = analyse(rows, limit)
    over = max(0.0, total - limit)
    if args.json:
        print(json.dumps({"total": total, "limit": limit, "over": over, "items": items, "flags": flags,
                          "cut_candidates": [c["who"] for c in cuts]}, ensure_ascii=False, indent=2))
    else:
        print("合计 %.0f 元 / 总预算 %.0f 元：%s" % (total, limit, "超出 %.0f 元" % over if over else "未超出"))
        for it in items:
            print("  - %s（%s）%.0f 元%s" % (it["who"], it["rel"] or "关系未写", it["money"],
                                          "，" + it["state"] if it["state"] else ""))
        if over:
            if cuts:
                print("超了先减这几项（按金额从高到低，已下单/已写好的不动）：")
                for c in cuts:
                    print("  - %s：%.0f 元 → 降一档，或换成体验、手写卡这类不花大钱的方向" % (c["who"], c["money"]))
            else:
                print("能减的都已经下单或写好：只能退换其中一项，或者追加预算。")
            print("超预算的清单不交付：先按上面减到 %.0f 元以内再定稿。" % limit)
        if flags:
            print("要改或要确认的行：")
            for f in flags:
                print("  - " + f)
    return EXIT_ATTENTION if (over or flags) else EXIT_OK


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有做任何改动。\n")
        sys.exit(EXIT_INTERRUPT)
