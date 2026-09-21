"""skillkit budget —— 发布配额与节奏规划。

背景（2026-09 实测，出处见 skillkit/rules.py 的坑点表）：
  * SkillHub 的发布限额**不是按自然日重置**。约第 100 次成功发布后全面拦截，
    +1 小时、+14.5 小时（本地日与 UTC 日都已翻篇）再试仍报「发布频率过高」，
    连未改动的对照技能也拦；同期读接口正常，与令牌无关。
  * 最符合的解释是**滚动 24 小时窗口、上限约 100 次** —— 这是**推测，需确认**。
    所以 --cap 与 --window 都是可调参数，默认值只是当前最佳猜测。
  * 单次发布间隔 75 秒基本够用；接近上限时会偶发限流，重试要等 10 分钟级别。
  * 失败的请求一样消耗配额。所以发布前必须本地校验，别拿线上额度当 linter。
"""

from __future__ import print_function

import sys
from datetime import datetime, timedelta
from typing import Any, Dict

from .. import output, rules

HELP = "发布配额与节奏规划（算清本轮能发多少、怎么分批、限流怎么退避）"


def add_parser(subparsers):
    p = subparsers.add_parser(
        "budget",
        help=HELP,
        description="把「我要发 N 个技能」换算成分批计划、退避策略，并给一段可直接跑的 bash 循环。",
        epilog="配额上限与窗口长度是实测基础上的推测值，需确认；平台不返回配额字段。"
               "例：skillkit budget --count 40 --used 12",
    )
    p.add_argument("--count", type=int, required=True, help="本次待发布的技能数量")
    p.add_argument("--used", type=int, default=0, help="最近 24 小时内已成功发布的次数（默认 0）")
    p.add_argument("--cap", type=int, default=rules.BUDGET_CAP_DEFAULT,
                   help="滚动窗口内的发布次数上限，默认 %d（推测值，需确认）" % rules.BUDGET_CAP_DEFAULT)
    p.add_argument("--window", type=float, default=rules.BUDGET_WINDOW_HOURS,
                   help="滚动窗口长度（小时），默认 %d（推测值，需确认）" % rules.BUDGET_WINDOW_HOURS)
    p.add_argument("--interval", type=int, default=rules.BUDGET_INTERVAL_SECONDS,
                   help="单次发布间隔（秒），默认 %d（实测够用）" % rules.BUDGET_INTERVAL_SECONDS)
    p.add_argument("--reserve", type=int, default=rules.BUDGET_RESERVE_DEFAULT,
                   help="预留给重试与失败的次数，默认 %d" % rules.BUDGET_RESERVE_DEFAULT)
    p.add_argument("--batch-size", type=int, default=rules.BUDGET_BATCH_SIZE, dest="batch_size",
                   help="单批最多发几个，默认 %d" % rules.BUDGET_BATCH_SIZE)
    p.add_argument("--batch-gap", type=int, default=rules.BUDGET_BATCH_GAP_MINUTES, dest="batch_gap",
                   help="批与批之间隔几分钟，默认 %d" % rules.BUDGET_BATCH_GAP_MINUTES)
    p.add_argument("--start", default="", help="起算时间 ISO8601，默认现在")
    p.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON（含 bash 模板）")
    p.add_argument("--no-bash", action="store_true", dest="no_bash", help="不输出 bash 模板")
    p.add_argument("--out", default="", help="把 bash 模板写到这个文件而不是 stdout")
    return p


# ---------------------------------------------------------------- 规划

def plan(count, used, cap, window_h, interval, reserve, batch_size, batch_gap_min, start):
    # type: (int, int, int, float, int, int, int, int, datetime) -> Dict[str, Any]
    """算出本轮可发多少、分几批、每批起止时间，以及排不下的部分什么时候能继续。"""
    usable = max(0, cap - reserve - used)
    this_round = min(count, usable)
    deferred = count - this_round

    batches = []
    cursor = start
    remaining = this_round
    idx = 0
    while remaining > 0:
        idx += 1
        n = min(batch_size, remaining)
        duration = timedelta(seconds=(n - 1) * interval)
        batches.append({
            "index": idx,
            "count": n,
            "start": cursor.isoformat(timespec="seconds"),
            "end": (cursor + duration).isoformat(timespec="seconds"),
            "duration_minutes": round(duration.total_seconds() / 60, 1),
        })
        cursor = cursor + duration + timedelta(minutes=batch_gap_min)
        remaining -= n

    resume = None
    if deferred:
        # 窗口从「本轮最早一次发布」起算。如果 --used 那部分更早发生，实际释放会更早，
        # 但我们不知道它们发生在什么时候，所以取保守估计。
        resume = (start + timedelta(hours=window_h)).isoformat(timespec="seconds")

    return {
        "params": {
            "count": count, "used_last_24h": used, "cap": cap, "cap_is_speculative": True,
            "window_hours": window_h, "window_is_speculative": True,
            "interval_seconds": interval, "reserve": reserve,
            "batch_size": batch_size, "batch_gap_minutes": batch_gap_min,
            "start": start.isoformat(timespec="seconds"),
        },
        "usable_now": usable,
        "publish_this_round": this_round,
        "deferred": deferred,
        "batch_count": len(batches),
        "batches": batches,
        "finish_at": batches[-1]["end"] if batches else None,
        "resume_after": resume,
        "backoff": {
            "normal_interval_seconds": interval,
            "on_throttle_minutes": list(rules.BUDGET_BACKOFF_MINUTES),
            "retry_same_item": True,
            "give_up_after_failures": len(rules.BUDGET_BACKOFF_MINUTES),
        },
    }


def bash_template(p, dirs_var="SKILL_DIRS"):
    # type: (Dict[str, Any], str) -> str
    """一段可直接用的发布循环：串行、限流退避、记录 skillId、失败不跳过。"""
    itv = p["params"]["interval_seconds"]
    waits = " ".join(str(m * 60) for m in rules.BUDGET_BACKOFF_MINUTES)
    return """#!/usr/bin/env bash
# SkillHub 发布循环（由 skillkit budget 生成）
# 计划：本轮 %(n)d 个，分 %(b)d 批，间隔 %(itv)d 秒
# 前提：已完成 skillhub login；每个目录都已 `skillkit doctor` 通过
set -uo pipefail

HOST="https://api.skillhub.cn"
LOG="publish-log.csv"
INTERVAL=%(itv)d
BACKOFFS=(%(waits)s)          # 限流后依次等待的秒数，对同一项重试，不跳过
CHANGELOG="${CHANGELOG:-首次发布}"

%(var)s=(
  # 一行一个待发布目录，按你希望的发布顺序排列
  # dist/skillhub/my-skill-a
  # dist/skillhub/my-skill-b
)

[ -f "$LOG" ] || echo "time,dir,result,skill_id,note" >> "$LOG"

publish_one() {
  local dir="$1" attempt=0 out rc
  while :; do
    out="$(skillhub publish "$dir" --host "$HOST" --changelog "$CHANGELOG" 2>&1)"; rc=$?
    if [ $rc -eq 0 ] && printf '%%s' "$out" | grep -q 'skillId'; then
      local sid; sid="$(printf '%%s' "$out" | grep -o 'skillId=[0-9]*' | head -1 | cut -d= -f2)"
      echo "$(date -Iseconds),$dir,ok,${sid:-}," >> "$LOG"
      echo "[ok]   $dir skillId=${sid:-?}"
      return 0
    fi
    if printf '%%s' "$out" | grep -q '发布频率过高'; then
      if [ $attempt -ge ${#BACKOFFS[@]} ]; then
        echo "$(date -Iseconds),$dir,quota_exhausted,,连续 ${#BACKOFFS[@]} 次限流，判定配额耗尽" >> "$LOG"
        echo "[stop] $dir 连续限流，配额大概率已耗尽；停止本轮，等窗口释放后从这一项继续"
        return 2
      fi
      local w=${BACKOFFS[$attempt]}; attempt=$((attempt+1))
      echo "[wait] $dir 被限流，等 $((w/60)) 分钟后重试同一项（第 $attempt 次）"
      sleep "$w"; continue
    fi
    # 其它错误（409 slug 冲突 / 400 文件类型 / 版本号未升）不重试，留给人看
    echo "$(date -Iseconds),$dir,fail,,$(printf '%%s' "$out" | head -1 | tr ',' ';')" >> "$LOG"
    echo "[fail] $dir -> $(printf '%%s' "$out" | head -1)"
    return 1
  done
}

for d in "${%(var)s[@]}"; do
  publish_one "$d"; rc=$?
  [ $rc -eq 2 ] && break       # 配额耗尽，整轮停下，别再烧额度
  sleep "$INTERVAL"
done

echo "完成。明细见 $LOG；下一轮最早可继续时间见规划输出的 resume_after。"
""" % {"n": p["publish_this_round"], "b": p["batch_count"], "itv": itv,
       "waits": waits, "var": dirs_var}


def render(p):
    # type: (Dict[str, Any]) -> str
    q = p["params"]
    backoff = rules.BUDGET_BACKOFF_MINUTES
    L = ["SkillHub 发布节奏规划", output.hr("=", 52)]
    L.append("待发 %d 个 | 最近 24 小时已发 %d 次 | 配额上限 %d（推测值，需确认，--cap 可调）"
             % (q["count"], q["used_last_24h"], q["cap"]))
    L.append("单次间隔 %d 秒 | 安全余量 %d 次 | 单批上限 %d 个 | 批间隔 %d 分钟 | "
             "滚动窗口 %g 小时（推测）"
             % (q["interval_seconds"], q["reserve"], q["batch_size"],
                q["batch_gap_minutes"], q["window_hours"]))
    L.append("")
    L.append("本轮可发：%d 个（可用额度 = %d - 已用 %d - 余量 %d = %d）"
             % (p["publish_this_round"], q["cap"], q["used_last_24h"], q["reserve"], p["usable_now"]))

    if p["publish_this_round"] == 0:
        L.append("")
        L.append("** 配额已用满，本轮一个都发不了。**")
        L.append("   现在发出去的请求只会失败，而失败的请求一样消耗配额——不要试。")
        L.append("   最早可继续时间（保守估计）：%s" % p["resume_after"])
        L.append("   注意：窗口按「最早那次消耗」起算。如果你那 %d 次是更早发生的，"
                 % q["used_last_24h"])
        L.append("   实际释放会比这个时间早；平台不返回配额字段，只能试探。")
        L.append("   试探方法：拿一个**已发布过、内容未改、只升补丁版本号**的对照技能去发，")
        L.append("   通了说明窗口已放行，再开始正式队列。")
    else:
        L.append("需要分 %d 批，预计 %s 发完" % (p["batch_count"], p["finish_at"]))
        L.append("")
        L.append("批次计划")
        L.append(output.hr("-", 52))
        L.append("%3s  %4s  %-19s  %-19s  %8s" % ("批", "个数", "开始", "结束", "耗时(分)"))
        for b in p["batches"]:
            L.append("%3d  %4d  %-19s  %-19s  %8s"
                     % (b["index"], b["count"], b["start"], b["end"], b["duration_minutes"]))
        if p["batch_count"] > 1:
            L.append("")
            L.append("批间留 %d 分钟不是为了礼貌——是为了不在几小时内把滚动窗口打满。"
                     % q["batch_gap_minutes"])
            L.append("一晚上打满的代价是第二天同一时段之前你什么都发不了。")

    if p["deferred"] and p["publish_this_round"]:
        L.append("")
        L.append("本轮排不下：%d 个" % p["deferred"])
        L.append("最早可继续时间（保守估计）：%s" % p["resume_after"])
        L.append("这个时间基于「滚动 24 小时窗口」的推测，需确认；实际以对照技能试探为准。")

    L.append("")
    L.append("遇限流怎么办（退避策略）")
    L.append(output.hr("-", 52))
    L.append("1. 正常节奏：每次发布间隔 %d 秒。" % q["interval_seconds"])
    L.append("2. 报「发布频率过高」→ 对**同一项**等 %d 分钟重试，**不要跳过去发下一个**。" % backoff[0])
    L.append("   跳过只会更快耗尽剩余额度，还把队列顺序搞乱。")
    L.append("3. 再失败 → 依次等 %s 分钟。" % "、".join(str(m) for m in backoff[1:]))
    L.append("4. 连续 %d 次都被限 → 判定配额耗尽，**停止本轮**，" % len(backoff))
    L.append("   记下停在哪一项，等窗口释放后从那一项继续。")
    L.append("5. 409 slug 冲突 / 400 文件类型 / 版本号未升 → 这些不是限流，重试没用，改包。")
    L.append("")
    L.append("先跑一遍 `skillkit doctor` 再进队列——失败的请求一样烧配额。")
    return "\n".join(L)


# ---------------------------------------------------------------- 入口

def run(args):
    if args.count < 1:
        print("--count 必须 >= 1", file=sys.stderr)
        return 2
    for name, v in (("--used", args.used), ("--reserve", args.reserve)):
        if v < 0:
            print("%s 不能为负" % name, file=sys.stderr)
            return 2
    for name, v in (("--cap", args.cap), ("--interval", args.interval),
                    ("--batch-size", args.batch_size)):
        if v < 1:
            print("%s 必须 >= 1" % name, file=sys.stderr)
            return 2
    if args.window <= 0:
        print("--window 必须 > 0", file=sys.stderr)
        return 2

    try:
        start = datetime.fromisoformat(args.start) if args.start else datetime.now()
    except ValueError as exc:
        print("--start 不是合法的 ISO8601 时间: %s" % exc, file=sys.stderr)
        return 2

    p = plan(args.count, args.used, args.cap, args.window, args.interval,
             args.reserve, args.batch_size, args.batch_gap, start)

    script = "" if args.no_bash else bash_template(p)
    if args.out and script:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(script)

    if args.as_json:
        p["bash_template"] = script if not args.out else "(已写入 %s)" % args.out
        output.emit_json(p)
        return 0

    print(render(p))
    if script and not args.out:
        print("")
        print(output.hr("-", 52))
        print("可直接用的发布循环（另存为 publish.sh 后 bash publish.sh）")
        print(output.hr("-", 52))
        print(script)
    elif args.out:
        print("")
        print("bash 模板已写入 %s" % args.out)
    return 0
