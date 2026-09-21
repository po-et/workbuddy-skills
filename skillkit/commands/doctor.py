"""skillkit doctor —— 发布前最后一道关：一次跑完 lint + build 试运行，给「能不能发」的结论。

存在的理由只有一条实测规律：**失败的发布请求一样消耗配额**。
线上额度不是 linter，doctor 才是。
"""

from __future__ import print_function

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .. import checks, output, rules
from ..skillpkg import SkillError, relpath_for_display, resolve_targets
from . import build as build_cmd
from . import lint as lint_cmd

HELP = "发布前体检：lint + build 试运行，给出能不能发的结论"

VERDICT_GO = "可以发"
VERDICT_RISK = "可以发，但先看下面的提醒"
VERDICT_STOP = "不要发"


def add_parser(subparsers):
    p = subparsers.add_parser(
        "doctor",
        help=HELP,
        description="对技能目录跑完整体检：格式校验 + 五维打分 + 生成发布副本的试运行，"
                    "最后给一句「能不能发」。发布配额有限且失败请求照样扣额度，"
                    "所以这一步不是可选项。",
        epilog="退出码：可以发为 0，不要发为 1。例：skillkit doctor skills/ --min 70",
    )
    p.add_argument("paths", nargs="+", help="技能目录、SKILL.md，或包含若干技能的上层目录")
    p.add_argument("--min", type=int, default=0, help="质量分门槛，低于它判为不要发（默认 0 = 不卡分数）")
    p.add_argument("--slug", default="", help="试算用的 slug（只在恰好一个技能时可用）")
    p.add_argument("--homepage", default="", help="试算用的 homepage")
    p.add_argument("--license", default=build_cmd.DEFAULT_LICENSE, dest="license_", help="试算用的 license")
    p.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    return p


def diagnose(directory, minimum=0, slug="", license_=build_cmd.DEFAULT_LICENSE, homepage=""):
    # type: (Any, int, str, str, str) -> Dict[str, Any]
    """对一个技能做完整体检。"""
    lint_result = lint_cmd.lint_one(directory)
    over = {"slug": slug} if slug else None
    with tempfile.TemporaryDirectory(prefix="skillkit-doctor-") as tmp:
        try:
            build_result = build_cmd.build_one(
                directory, Path(tmp), over, license_, homepage, dry_run=True)
        except SkillError as exc:
            build_result = {
                "slug": "", "removed": [], "ok": False,
                "findings": [checks.Finding(checks.FAIL, str(exc)).as_dict()],
                "counts": {checks.FAIL: 1, checks.WARN: 0, checks.PASS: 0},
            }

    every = _dedupe(lint_result["findings"] + build_result["findings"])
    blockers = [f for f in every if f["level"] == checks.FAIL]
    warnings = [f for f in every if f["level"] == checks.WARN]
    below = lint_result["total"] < minimum

    if blockers or below:
        verdict = VERDICT_STOP
    elif warnings:
        verdict = VERDICT_RISK
    else:
        verdict = VERDICT_GO

    reasons = [f["message"] for f in blockers]
    if below:
        reasons.append("质量分 %d 低于门槛 %d" % (lint_result["total"], minimum))

    return {
        "name": lint_result["name"],
        "path": relpath_for_display(Path(str(directory))),
        "verdict": verdict,
        "can_publish": verdict != VERDICT_STOP,
        "total": lint_result["total"],
        "scores": lint_result["scores"],
        "slug": build_result["slug"],
        "will_remove": build_result["removed"],
        "blockers": reasons,
        "warnings": [f["message"] for f in warnings],
        "tips": lint_result["tips"],
    }


def _dedupe(findings):
    # type: (List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """lint 与 build 会从两个角度撞上同一条规则（例如 version 不是 SemVer），只留第一条。"""
    out = []
    seen_rules = set()
    seen_msgs = set()
    for f in findings:
        if f["message"] in seen_msgs:
            continue
        key = (f["level"], f.get("rule"))
        if f.get("rule") and key in seen_rules:
            continue
        seen_msgs.add(f["message"])
        if f.get("rule"):
            seen_rules.add(key)
        out.append(f)
    return out


def run(args):
    try:
        targets = resolve_targets(args.paths)
    except SkillError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.slug and len(targets) != 1:
        print("--slug 只能在恰好一个技能时使用，当前匹配到 %d 个" % len(targets), file=sys.stderr)
        return 2

    results = [diagnose(d, args.min, args.slug, args.license_, args.homepage) for d in targets]
    stop = [r for r in results if not r["can_publish"]]

    if args.as_json:
        output.emit_json({
            "skills": results,
            "summary": {
                "count": len(results),
                "can_publish": len(results) - len(stop),
                "blocked": [r["name"] for r in stop],
                "threshold": args.min,
            },
        })
        return 1 if stop else 0

    _render(results, args)
    return 1 if stop else 0


def _render(results, args):
    for r in results:
        print(output.hr("="))
        print("%s  [%s]  %d 分  slug=%s"
              % (output.truncate_path(r["path"], 46), r["verdict"], r["total"], r["slug"] or "?"))
        dims = "  ".join("%s %d" % (k, v) for k, v in r["scores"].items())
        print("  " + dims)
        for msg in r["blockers"]:
            print("  ✗ %s" % msg)
        for msg in r["warnings"]:
            print("  ! %s" % msg)
        for tip in r["tips"][:5]:
            print("  → %s" % tip)
        if r["will_remove"]:
            print("  build 时会删掉（平台拒收）：%s" % "、".join(r["will_remove"]))
    print(output.hr("="))
    stop = [r for r in results if not r["can_publish"]]
    print("%d 个技能：%d 个可以发，%d 个不要发%s"
          % (len(results), len(results) - len(stop), len(stop),
             "（门槛 %d 分）" % args.min if args.min else ""))
    if stop:
        print("不要发：%s" % "、".join(r["name"] for r in stop))
    print("")
    print("提醒（都是实测踩出来的）：")
    for pit in _doctor_reminders():
        print("  · %s" % pit)


def _doctor_reminders():
    # type: () -> List[str]
    ids = ("version-must-increase", "failed-requests-cost-quota",
           "slug-global-unique", "throttle-retry-same-item")
    out = []
    for pit in rules.PITFALLS:
        if pit["id"] in ids:
            out.append("%s（%s）" % (pit["规则"], pit["置信度"]))
    return out
