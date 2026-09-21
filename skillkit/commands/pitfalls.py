"""skillkit pitfalls —— 打印内置的平台规律表。

规则表就是这个工具的价值本体，所以让它可查。每条都标了置信度：
「实测」= 我们自己被拒/被接受过，有报错原文；「文档」= 平台文档写明；
「推测（需确认）」= 从现象反推，平台没确认过 —— 别当事实用。
"""

from __future__ import print_function

from .. import output, rules

HELP = "打印内置的平台规律表（区分实测 / 文档 / 推测）"


def add_parser(subparsers):
    p = subparsers.add_parser(
        "pitfalls",
        help=HELP,
        description="列出 skillkit 内置的平台规律与它们各自的处理方式。"
                    "这些规则驱动 lint / build / budget 的行为，改规则只改 skillkit/rules.py。",
        epilog="例：skillkit pitfalls --confidence 推测",
    )
    p.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    p.add_argument("--confidence", default="", help="只看某个置信度（实测 / 文档 / 推测 / 自设规则）")
    p.add_argument("--id", default="", dest="pit_id", help="只看某一条（按 id 精确匹配）")
    return p


def run(args):
    items = list(rules.PITFALLS)
    if args.confidence:
        items = [p for p in items if args.confidence in p["置信度"]]
    if args.pit_id:
        items = [p for p in items if p["id"] == args.pit_id]
    if not items:
        print("没有匹配的条目")
        return 1

    if args.as_json:
        output.emit_json(items)
        return 0

    for p in items:
        print(output.hr("="))
        print("[%s] %s" % (p["置信度"], p["id"]))
        print("  现象    ：%s" % p["现象"])
        print("  规则    ：%s" % p["规则"])
        print("  证据    ：%s" % p["证据"])
        print("  skillkit：%s" % p["skillkit"])
    print(output.hr("="))
    print("共 %d 条。标「推测」的没有被平台确认过，不要当事实引用。" % len(items))
    return 0
