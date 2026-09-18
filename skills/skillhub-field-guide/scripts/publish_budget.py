#!/usr/bin/env python3
"""SkillHub 发布节奏规划器：把「我要发 N 个技能」换算成分批计划、退避策略和一段可直接跑的 bash 循环。

背景（2026-09 实测，出处见 SKILL.md）：
  * SkillHub 的发布限额**不是按日重置**。09-17 约第 100 次成功发布后全面拦截，
    +1 小时、+14.5 小时（本地日与 UTC 日都已翻篇）再试仍报「发布频率过高」，
    连未改动的对照技能也拦；同期读操作正常，与令牌无关。
  * 最符合的解释是**滚动 24 小时窗口、上限约 100 次**——这是推测，需确认。
    因此 --cap 与 --window 都是可调参数，默认值只是当前最佳猜测。
  * 单次发布间隔 75 秒基本够用；接近配额上限时会偶发限流，重试要等 10 分钟级别。
  * 失败的请求一样消耗配额，所以发布前必须本地校验，别拿线上额度当 linter。

纯标准库。用法见 --help。
"""
import argparse
import json
import sys
from datetime import datetime, timedelta

CAP_DEFAULT = 100        # 推测值，需确认
WINDOW_DEFAULT = 24      # 小时，推测值，需确认
INTERVAL_DEFAULT = 75    # 秒，实测够用
RESERVE_DEFAULT = 10     # 给重试与失败留的余量
BATCH_SIZE_DEFAULT = 25  # 单批上限，避免几小时内打满窗口
BATCH_GAP_DEFAULT = 60   # 分钟，批与批之间的间隔

BACKOFF_MINUTES = [10, 20, 40]


def plan(count, used, cap, window_h, interval, reserve, batch_size, batch_gap_min, start):
    """算出本轮可发多少、分几批、每批起止时间，以及排不下的部分什么时候能继续。"""
    usable = max(0, cap - reserve - used)
    this_round = min(count, usable)
    deferred = count - this_round

    batches, cursor = [], start
    remaining = this_round
    idx = 0
    while remaining > 0:
        idx += 1
        n = min(batch_size, remaining)
        # n 个发布之间有 n-1 个间隔；最后一个发完即结束
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
        # 窗口从「本轮最早一次发布」起算；如果 --used 那部分更早，实际释放会更早，
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
            "on_throttle_minutes": BACKOFF_MINUTES,
            "retry_same_item": True,
            "give_up_after_failures": len(BACKOFF_MINUTES),
        },
    }


def bash_template(p, dirs_var="SKILL_DIRS"):
    """一段可直接用的发布循环：串行、限流退避、记录 skillId、失败不跳过。"""
    itv = p["params"]["interval_seconds"]
    waits = " ".join(str(m * 60) for m in BACKOFF_MINUTES)
    return f"""#!/usr/bin/env bash
# SkillHub 发布循环（由 publish_budget.py 生成）
# 计划：本轮 {p['publish_this_round']} 个，分 {p['batch_count']} 批，间隔 {itv} 秒
# 前提：已完成 skillhub login；每个目录都已本地校验通过（无扩展名文件 / frontmatter / 版本号）
set -uo pipefail

HOST="https://api.skillhub.cn"
LOG="publish-log.csv"
INTERVAL={itv}
BACKOFFS=({waits})          # 限流后依次等待的秒数，对同一项重试，不跳过
CHANGELOG="${{CHANGELOG:-首次发布}}"

{dirs_var}=(
  # 一行一个待发布目录，按你希望的发布顺序排列
  # dist/skillhub/my-skill-a
  # dist/skillhub/my-skill-b
)

[ -f "$LOG" ] || echo "time,dir,result,skill_id,note" >> "$LOG"

publish_one() {{
  local dir="$1" attempt=0 out rc
  while :; do
    out="$(skillhub publish "$dir" --host "$HOST" --changelog "$CHANGELOG" 2>&1)"; rc=$?
    if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q 'skillId'; then
      local sid; sid="$(printf '%s' "$out" | grep -o 'skillId=[0-9]*' | head -1 | cut -d= -f2)"
      echo "$(date -Iseconds),$dir,ok,${{sid:-}}," >> "$LOG"
      echo "[ok]   $dir skillId=${{sid:-?}}"
      return 0
    fi
    if printf '%s' "$out" | grep -q '发布频率过高'; then
      if [ $attempt -ge ${{#BACKOFFS[@]}} ]; then
        echo "$(date -Iseconds),$dir,quota_exhausted,,连续 ${{#BACKOFFS[@]}} 次限流，判定配额耗尽" >> "$LOG"
        echo "[stop] $dir 连续限流，配额大概率已耗尽；停止本轮，等窗口释放后从这一项继续"
        return 2
      fi
      local w=${{BACKOFFS[$attempt]}}; attempt=$((attempt+1))
      echo "[wait] $dir 被限流，等 $((w/60)) 分钟后重试同一项（第 $attempt 次）"
      sleep "$w"; continue
    fi
    # 其它错误（409 slug 冲突 / 400 文件类型 / 版本号未升）不重试，留给人看
    echo "$(date -Iseconds),$dir,fail,,$(printf '%s' "$out" | head -1 | tr ',' ';')" >> "$LOG"
    echo "[fail] $dir -> $(printf '%s' "$out" | head -1)"
    return 1
  done
}}

for d in "${{{dirs_var}[@]}}"; do
  publish_one "$d"; rc=$?
  [ $rc -eq 2 ] && break       # 配额耗尽，整轮停下，别再烧额度
  sleep "$INTERVAL"
done

echo "完成。明细见 $LOG；下一轮最早可继续时间见规划输出的 resume_after。"
"""


def render(p):
    q = p["params"]
    L = []
    L.append("SkillHub 发布节奏规划")
    L.append("=" * 52)
    L.append(f"待发 {q['count']} 个 | 最近 24 小时已发 {q['used_last_24h']} 次 | "
             f"配额上限 {q['cap']}（推测值，需确认，--cap 可调）")
    L.append(f"单次间隔 {q['interval_seconds']} 秒 | 安全余量 {q['reserve']} 次 | "
             f"单批上限 {q['batch_size']} 个 | 批间隔 {q['batch_gap_minutes']} 分钟 | "
             f"滚动窗口 {q['window_hours']} 小时（推测）")
    L.append("")
    L.append(f"本轮可发：{p['publish_this_round']} 个"
             f"（可用额度 = {q['cap']} - 已用 {q['used_last_24h']} - 余量 {q['reserve']} = {p['usable_now']}）")

    if p["publish_this_round"] == 0:
        L.append("")
        L.append("** 配额已用满，本轮一个都发不了。**")
        L.append(f"   现在发出去的请求只会失败，而失败的请求一样消耗配额——不要试。")
        L.append(f"   最早可继续时间（保守估计）：{p['resume_after']}")
        L.append("   注意：窗口按「最早那次消耗」起算。如果你那 %d 次是更早发生的，"
                 % q["used_last_24h"])
        L.append("   实际释放会比这个时间早；平台不返回配额字段，只能试探。")
        L.append("   试探方法：拿一个**已发布过、内容未改、只升补丁版本号**的对照技能去发，")
        L.append("   通了说明窗口已放行，再开始正式队列。")
    else:
        L.append(f"需要分 {p['batch_count']} 批，预计 {p['finish_at']} 发完")
        L.append("")
        L.append("批次计划")
        L.append("-" * 52)
        L.append(f"{'批':>3}  {'个数':>4}  {'开始':<19}  {'结束':<19}  {'耗时(分)':>8}")
        for b in p["batches"]:
            L.append(f"{b['index']:>3}  {b['count']:>4}  {b['start']:<19}  {b['end']:<19}  "
                     f"{b['duration_minutes']:>8}")
        if p["batch_count"] > 1:
            L.append("")
            L.append(f"批间留 {q['batch_gap_minutes']} 分钟不是为了礼貌——是为了不在几小时内把滚动")
            L.append("窗口打满。一晚上打满的代价是第二天同一时段之前你什么都发不了。")

    if p["deferred"] and p["publish_this_round"]:
        L.append("")
        L.append(f"本轮排不下：{p['deferred']} 个")
        L.append(f"最早可继续时间（保守估计）：{p['resume_after']}")
        L.append("这个时间基于「滚动 24 小时窗口」的推测，需确认；实际以对照技能试探为准。")

    L.append("")
    L.append("遇限流怎么办（退避策略）")
    L.append("-" * 52)
    L.append(f"1. 正常节奏：每次发布间隔 {q['interval_seconds']} 秒。")
    L.append("2. 报「发布频率过高」→ 对**同一项**等 %s 分钟重试，**不要跳过去发下一个**。"
             % BACKOFF_MINUTES[0])
    L.append("   跳过只会更快耗尽剩余额度，还把队列顺序搞乱。")
    L.append("3. 再失败 → 依次等 %s 分钟。" % "、".join(str(m) for m in BACKOFF_MINUTES[1:]))
    L.append(f"4. 连续 {len(BACKOFF_MINUTES)} 次都被限 → 判定配额耗尽，**停止本轮**，")
    L.append("   记下停在哪一项，等窗口释放后从那一项继续。")
    L.append("5. 409 slug 冲突 / 400 文件类型 / 版本号未升 → 这些不是限流，重试没用，改包。")
    L.append("")
    L.append("先跑一遍本地校验再进队列——失败的请求一样烧配额。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description="SkillHub 发布节奏规划器：算清本轮能发多少、怎么分批、限流怎么退避。",
        epilog="配额上限与窗口长度是 2026-09 实测基础上的推测值，需确认；平台不返回配额字段。")
    ap.add_argument("--count", type=int, required=True, help="本次待发布的技能数量")
    ap.add_argument("--used", type=int, default=0, help="最近 24 小时内已成功发布的次数（默认 0）")
    ap.add_argument("--cap", type=int, default=CAP_DEFAULT,
                    help=f"滚动窗口内的发布次数上限，默认 {CAP_DEFAULT}（推测值，需确认）")
    ap.add_argument("--window", type=float, default=WINDOW_DEFAULT,
                    help=f"滚动窗口长度（小时），默认 {WINDOW_DEFAULT}（推测值，需确认）")
    ap.add_argument("--interval", type=int, default=INTERVAL_DEFAULT,
                    help=f"单次发布间隔（秒），默认 {INTERVAL_DEFAULT}")
    ap.add_argument("--reserve", type=int, default=RESERVE_DEFAULT,
                    help=f"预留给重试与失败的次数，默认 {RESERVE_DEFAULT}")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT,
                    help=f"单批最多发几个，默认 {BATCH_SIZE_DEFAULT}")
    ap.add_argument("--batch-gap", type=int, default=BATCH_GAP_DEFAULT,
                    help=f"批与批之间隔几分钟，默认 {BATCH_GAP_DEFAULT}")
    ap.add_argument("--start", default=None, help="起算时间 ISO8601，默认现在")
    ap.add_argument("--json", action="store_true", help="输出 JSON（含 bash 模板）")
    ap.add_argument("--no-bash", action="store_true", help="不输出 bash 模板")
    ap.add_argument("--out", default=None, help="把 bash 模板写到这个文件而不是 stdout")
    a = ap.parse_args()

    if a.count < 1:
        sys.exit("--count 必须 >= 1")
    for name, v in (("--used", a.used), ("--reserve", a.reserve)):
        if v < 0:
            sys.exit(f"{name} 不能为负")
    for name, v in (("--cap", a.cap), ("--interval", a.interval),
                    ("--batch-size", a.batch_size)):
        if v < 1:
            sys.exit(f"{name} 必须 >= 1")

    start = datetime.fromisoformat(a.start) if a.start else datetime.now()
    p = plan(a.count, a.used, a.cap, a.window, a.interval, a.reserve,
             a.batch_size, a.batch_gap, start)

    script = "" if a.no_bash else bash_template(p)
    if a.out and script:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(script)

    if a.json:
        p["bash_template"] = script if not a.out else f"(已写入 {a.out})"
        print(json.dumps(p, ensure_ascii=False, indent=2))
        return

    print(render(p))
    if script and not a.out:
        print("\n" + "-" * 52)
        print("可直接用的发布循环（另存为 publish.sh 后 bash publish.sh）")
        print("-" * 52)
        print(script)
    elif a.out:
        print(f"\nbash 模板已写入 {a.out}")


if __name__ == "__main__":
    main()
