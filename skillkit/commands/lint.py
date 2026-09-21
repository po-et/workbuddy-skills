"""skillkit lint —— 格式校验 + 五维打分 + 逐条改进建议。

把两件原本分开的事合并成一次调用：
  * 「会不会被平台拒」—— checks.py，产出 FAIL/WARN；
  * 「写得好不好」  —— scoring.py，产出 0–100 分与建议。
拒收是硬门槛，分数是软指标，所以退出码同时受两者影响（见 --min）。
"""

from __future__ import print_function

import sys
from typing import Any, Dict, List

from .. import checks, output, rules, scoring
from ..skillpkg import Skill, SkillError, relpath_for_display, resolve_targets

HELP = "校验技能包格式并打质量分（--json / --min 可做 CI 门禁）"


def add_parser(subparsers):
    p = subparsers.add_parser(
        "lint",
        help=HELP,
        description="对技能目录做格式校验（会不会被平台拒）与五维质量打分（写得好不好），"
                    "并给出逐条改进建议。可传多个目录，也可以传 skills/ 这样的上层目录递归。",
        epilog="退出码：有 FAIL 或有技能低于 --min 时为 1，否则 0。例：skillkit lint skills/ --min 70",
    )
    p.add_argument("paths", nargs="+", help="技能目录、SKILL.md，或包含若干技能的上层目录")
    p.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON（含 findings 与 tips）")
    p.add_argument("--min", type=int, default=0, help="质量分门槛，低于它退出码 1（默认 0 = 不卡分数）")
    p.add_argument("--max-tips", type=int, default=6, help="每个技能最多打印几条建议，默认 6；0 = 全部")
    p.add_argument("--quiet", action="store_true", help="只打印有 FAIL 或低于门槛的技能")
    p.add_argument("--no-score", action="store_true", help="只做格式校验，不打分")
    return p


def lint_one(directory):
    # type: (Any) -> Dict[str, Any]
    """对一个技能目录跑完整 lint，返回结构化结果。"""
    name = getattr(directory, "name", str(directory))
    try:
        skill = Skill.load(directory)
    except SkillError as exc:
        return {
            "name": name,
            "path": str(directory),
            "findings": [checks.Finding(checks.FAIL, str(exc)).as_dict()],
            "counts": {checks.FAIL: 1, checks.WARN: 0, checks.PASS: 0},
            "total": 0,
            "scores": dict((k, 0) for k in rules.SCORE_DIMENSIONS),
            "tips": [str(exc)],
            "ok": False,
        }
    findings = checks.check_skill(skill)
    score = scoring.score_skill(skill)
    counts = checks.counts(findings)
    return {
        "name": score["name"],
        "path": str(skill.dir),
        "findings": [f.as_dict() for f in findings],
        "counts": counts,
        "total": score["total"],
        "scores": score["scores"],
        "tips": score["tips"],
        "ok": counts[checks.FAIL] == 0,
    }


def run(args):
    try:
        targets = resolve_targets(args.paths)
    except SkillError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results = [lint_one(d) for d in targets]
    for r, d in zip(results, targets):
        r["path"] = relpath_for_display(d)

    failed = [r for r in results if not r["ok"]]
    below = [r for r in results if r["total"] < args.min]

    if args.as_json:
        output.emit_json({
            "skills": results,
            "summary": _summary(results, args.min),
        })
        return 1 if failed or below else 0

    _render(results, args)
    return 1 if failed or below else 0


def _summary(results, minimum):
    # type: (List[Dict[str, Any]], int) -> Dict[str, Any]
    totals = [r["total"] for r in results]
    return {
        "count": len(results),
        "fail": sum(r["counts"][checks.FAIL] for r in results),
        "warn": sum(r["counts"][checks.WARN] for r in results),
        "skills_with_fail": [r["name"] for r in results if not r["ok"]],
        "min_score": min(totals) if totals else 0,
        "max_score": max(totals) if totals else 0,
        "avg_score": round(sum(totals) / float(len(totals)), 1) if totals else 0,
        "threshold": minimum,
        "below_threshold": [r["name"] for r in results if r["total"] < minimum],
    }


def _render(results, args):
    shown = 0
    for r in sorted(results, key=lambda x: (x["ok"], x["total"])):
        interesting = (not r["ok"]) or r["total"] < args.min
        if args.quiet and not interesting:
            continue
        shown += 1
        head = output.pad(output.truncate_path(r["path"], 46), 46)
        if args.no_score:
            print("%s  %s" % (head, _count_tag(r)))
        else:
            dims = "  ".join("%s %d" % (k, v) for k, v in r["scores"].items())
            print("%s %3d 分  %s  %s" % (head, r["total"], dims, _count_tag(r)))
        for f in r["findings"]:
            if f["level"] == checks.PASS:
                continue
            print("    [%s] %s" % (f["level"], f["message"]))
        if not args.no_score:
            tips = r["tips"] if args.max_tips <= 0 else r["tips"][: args.max_tips]
            for t in tips:
                print("    → %s" % t)
            hidden = len(r["tips"]) - len(tips)
            if hidden > 0:
                print("    → （还有 %d 条建议，加 --max-tips 0 看全部）" % hidden)
        print("")

    s = _summary(results, args.min)
    if args.quiet and shown == 0:
        print("全部 %d 个技能都没有 FAIL，也都达到了 %d 分门槛。" % (s["count"], args.min))
        return
    print(output.hr("="))
    print("%d 个技能：%d FAIL / %d WARN；平均 %s 分，最低 %d，最高 %d"
          % (s["count"], s["fail"], s["warn"], s["avg_score"], s["min_score"], s["max_score"]))
    if s["skills_with_fail"]:
        print("有 FAIL（发上去会被拒）：%s" % "、".join(s["skills_with_fail"]))
    if s["below_threshold"]:
        print("低于 %d 分门槛：%s" % (args.min, "、".join(s["below_threshold"])))


def _count_tag(r):
    c = r["counts"]
    return "%dF/%dW" % (c[checks.FAIL], c[checks.WARN])
