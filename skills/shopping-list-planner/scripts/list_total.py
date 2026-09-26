#!/usr/bin/env python3
"""购物清单核算：按超市动线排序、合计估价、对照预算上限，超支时按固定顺序列出可砍的候选。

输入一份 CSV（UTF-8 或 GB18030），表头必须有「分区,物品」，其余列可选：
  分区,物品,数量,估价,类型,库存,替代
  分区  超市八区之一：日用百货 / 粮油干货调料 / 饮料零食 / 蔬果 / 肉禽水产 / 冷藏乳品 / 冷冻 / 鸡蛋面包；
        也可以写搬家、露营等自定义分组，自定义分组按首次出现的顺序排在后面
  估价  这一行的总价（元），不知道就留空 → 输出标 [待补]，不替你编价格
  类型  必需 / 想要（留空按必需）
  库存  缺 / 快用完 / 有（留空按缺；「有」的直接划掉，列进「家里已有」）
只用 Python 标准库，不联网。

用法：
  python3 list_total.py list.csv --budget 400
  python3 list_total.py list.csv --budget 400 --out 清单.md
  python3 list_total.py list.csv                 # 不给预算：只排动线、不做预算判断
退出码：0 成功；1 参数错误；2 读写文件失败；3 清单内容有误（缺列、估价不是数字等）；130 用户中断
"""

import argparse
import csv
import io
import os
import sys
import tempfile

ROUTE = ["日用百货", "粮油干货调料", "饮料零食", "蔬果", "肉禽水产", "冷藏乳品", "冷冻", "鸡蛋面包"]
ALIAS = {"日用": "日用百货", "粮油": "粮油干货调料", "调料": "粮油干货调料", "干货": "粮油干货调料",
         "饮料": "饮料零食", "零食": "饮料零食", "水果": "蔬果", "蔬菜": "蔬果", "肉": "肉禽水产",
         "水产": "肉禽水产", "乳品": "冷藏乳品", "冷藏": "冷藏乳品", "易碎": "鸡蛋面包",
         "鸡蛋面包等易碎": "鸡蛋面包", "鸡蛋": "鸡蛋面包", "面包": "鸡蛋面包"}


class ArgError(Exception):
    pass


class ListError(Exception):
    """清单内容问题，退出码 3。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)


def read_csv(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise OSError("无法识别文件编码，请另存为 UTF-8 的 CSV")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ListError("清单是空的：至少要有表头和一行物品")
    missing = [c for c in ("分区", "物品") if c not in rows[0]]
    if missing:
        raise ListError("缺少列：%s。表头示例：分区,物品,数量,估价,类型,库存,替代" % "、".join(missing))
    return rows


def parse_price(raw, lineno):
    s = (raw or "").strip().replace("¥", "").replace("￥", "").replace("元", "").strip()
    if not s:
        return None
    try:
        value = float(s)
    except ValueError:
        raise ListError("第 %d 行估价「%s」不是数字，请写成 12 或 12.5；不知道就留空" % (lineno, raw))
    if value < 0:
        raise ListError("第 %d 行估价是负数（%s），请改正" % (lineno, raw))
    return value


def load_items(rows):
    items, notes = [], []
    for i, row in enumerate(rows, 2):  # 第 1 行是表头
        name = (row.get("物品") or "").strip()
        if not name:
            continue
        zone = (row.get("分区") or "").strip() or "未分区"
        zone = ALIAS.get(zone, zone)
        qty = (row.get("数量") or "").strip()
        if not qty:
            qty = "[待补]"
            notes.append("第 %d 行「%s」没写数量，已标 [待补]" % (i, name))
        kind = (row.get("类型") or "必需").strip()
        if kind not in ("必需", "想要"):
            notes.append("第 %d 行类型「%s」不认识，按「必需」处理" % (i, kind))
            kind = "必需"
        stock = (row.get("库存") or "缺").strip()
        items.append({"line": i, "zone": zone, "name": name, "qty": qty, "kind": kind,
                      "stock": stock, "alt": (row.get("替代") or "").strip(),
                      "price": parse_price(row.get("估价"), i)})
    if not items:
        raise ListError("没有读到任何物品：检查「物品」列是否填写")
    return items, notes


def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def build(items, notes, budget, reserve):
    have = [it for it in items if it["stock"] == "有"]
    todo = [it for it in items if it["stock"] != "有"]
    custom = []
    for it in todo:
        if it["zone"] not in ROUTE and it["zone"] not in custom:
            custom.append(it["zone"])
    order = ROUTE + custom
    known = [it for it in todo if it["price"] is not None]
    unknown = [it for it in todo if it["price"] is None]
    total = sum(it["price"] for it in known)

    out = []
    if budget is None:
        status = "未给预算：只排动线和数量，不做预算判断"
    else:
        cap = budget * (1 - reserve)
        if total > budget:
            status = "超出上限 %s 元" % fmt(total - budget)
        elif total > cap:
            status = "没超上限，但动用了机动 %s 元" % fmt(total - cap)
        else:
            status = "预算内，余量 %s 元（已先扣机动）" % fmt(cap - total)
        if unknown:
            status += "；另有 %d 项估价 [待补]，合计只算已填的" % len(unknown)
    out.append("购物清单核算｜状态：%s" % status)
    out.append("")
    base = len(ROUTE) if any(it["zone"] in ROUTE for it in todo) else 0
    for zone in order:
        rows = [it for it in todo if it["zone"] == zone]
        if not rows:
            continue
        # 超市八区用固定编号，和店里的走法一一对应；自定义分组接在后面编号
        n = ROUTE.index(zone) + 1 if zone in ROUTE else base + custom.index(zone) + 1
        out.append("【%d %s】" % (n, zone))
        for it in rows:
            price = "估价 %s" % fmt(it["price"]) if it["price"] is not None else "估价 [待补]"
            extra = [price]
            if it["kind"] == "想要":
                extra.append("想要")
            if it["stock"] == "快用完":
                extra.append("快用完")
            if it["alt"]:
                extra.append("替代：%s" % it["alt"])
            out.append("- [ ] %s × %s｜%s" % (it["name"], it["qty"], "｜".join(extra)))
    out.append("")
    out.append("家里已有、已划掉：%s" % ("、".join(it["name"] for it in have) or "无"))
    line = "合计 %s 元（已填估价 %d 项，[待补] %d 项）" % (fmt(total), len(known), len(unknown))
    if budget is not None:
        line += "｜上限 %s 元｜机动 %s 元（%s%%）｜可用 %s 元" % (
            fmt(budget), fmt(budget * reserve), fmt(reserve * 100), fmt(budget * (1 - reserve)))
    out.append(line)

    if budget is not None and total > budget * (1 - reserve):
        over = total - budget * (1 - reserve)
        wants = sorted([it for it in known if it["kind"] == "想要"], key=lambda x: -x["price"])
        saved = sum(it["price"] for it in wants)
        out.append("")
        out.append("要压回可用额，需要省 %s 元。按这个顺序砍（只列候选，砍哪项你定）：" % fmt(over))
        if wants:
            out.append("1 先砍「想要」：%s——全砍可省 %s 元，%s" % (
                "、".join("%s（估 %s）" % (it["name"], fmt(it["price"])) for it in wants),
                fmt(saved), "够了" if saved >= over else "还不够"))
        else:
            out.append("1 先砍「想要」：清单里没有标「想要」的项")
        alts = [it for it in todo if it["alt"] and it["kind"] == "必需"]
        out.append("2 换替代：%s" % ("、".join("%s → %s" % (it["name"], it["alt"]) for it in alts)
                                    or "没有写替代品的项，可在单价高的项旁补一个"))
        top = sorted([it for it in known if it["kind"] == "必需"], key=lambda x: -x["price"])[:3]
        out.append("3 减数量：先看估价最高的必需项——%s；买够这几天的量就行" % (
            "、".join("%s × %s（估 %s）" % (it["name"], it["qty"], fmt(it["price"])) for it in top)
            or "没有已估价的必需项"))
        out.append("4 最后才动「必需」")
    if notes:
        out.append("")
        out.append("提示：")
        out += ["- " + x for x in notes]
    return "\n".join(out) + "\n"


def write_atomic(path, content):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".md", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    p = Parser(description="购物清单核算：动线排序、合计、对照预算上限，只读输入。")
    p.add_argument("csv", help="清单 CSV：分区,物品,数量,估价,类型,库存,替代")
    p.add_argument("--budget", type=float, help="预算上限（元），不给就不做预算判断")
    p.add_argument("--reserve", type=float, default=0.1, help="机动比例，默认 0.1（留一成）")
    p.add_argument("--out", help="写入这个 Markdown 文件（默认打印到屏幕）")
    try:
        a = p.parse_args(argv)
        if a.budget is not None and a.budget <= 0:
            raise ArgError("--budget 要大于 0；没有预算就不写这个参数")
        if not 0 <= a.reserve < 1:
            raise ArgError("--reserve 要在 0 到 1 之间，例如 0.1")
    except ArgError as exc:
        print("参数错误：%s\n用法：python3 list_total.py 清单.csv [--budget 400] [--out 清单.md]" % exc,
              file=sys.stderr)
        return 1
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.csv):
        print("参数错误：--out 不能和输入的 CSV 是同一个文件", file=sys.stderr)
        return 1
    try:
        items, notes = load_items(read_csv(a.csv))
    except FileNotFoundError:
        print("读不到文件：%s（检查路径和文件名）" % a.csv, file=sys.stderr)
        return 2
    except IsADirectoryError:
        print("%s 是文件夹，请指定清单 CSV 文件" % a.csv, file=sys.stderr)
        return 2
    except OSError as exc:
        print("读取失败：%s" % exc, file=sys.stderr)
        return 2
    except (ListError, csv.Error) as exc:
        print("清单有误：%s" % exc, file=sys.stderr)
        return 3
    report = build(items, notes, a.budget, a.reserve)
    if a.out:
        try:
            write_atomic(a.out, report)
        except OSError as exc:
            print("写不了输出文件 %s：%s" % (a.out, exc.strerror or exc), file=sys.stderr)
            return 2
        print("已写入 %s" % a.out)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有写任何文件。", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
