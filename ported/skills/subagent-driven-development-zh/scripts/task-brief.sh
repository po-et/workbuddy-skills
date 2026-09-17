#!/usr/bin/env bash
# 从实施计划里抽出某一个任务的完整正文，写进一个文件，让实现者一次读完，
# 这样任务正文就不必再经由协调者的上下文来回粘贴。
#
# 用法：task-brief.sh PLAN_FILE TASK_NUMBER [OUTFILE]
# 默认 OUTFILE：<仓库根>/.sdd/<计划文件名>/task-<N>-brief.md
set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
  echo "用法：task-brief.sh PLAN_FILE TASK_NUMBER [OUTFILE]" >&2
  exit 2
fi

plan=$1
n=$2
[ -f "$plan" ] || { echo "计划文件不存在：$plan" >&2; exit 2; }

if [ $# -eq 3 ]; then
  out=$3
else
  dir=$("$(cd "$(dirname "$0")" && pwd)/sdd-workspace.sh" "$plan")
  out="$dir/task-${n}-brief.md"
fi

# 同时匹配中文「任务 N」与英文「Task N」两种标题写法；跳过代码围栏内的内容
awk -v n="$n" '
  /^```/ { infence = !infence }
  !infence && /^#+[ \t]+(Task|任务)[ \t]*[0-9]+/ {
    intask = ($0 ~ ("^#+[ \t]+(Task|任务)[ \t]*" n "([^0-9]|$)"))
  }
  intask { print }
' "$plan" > "$out"

if [ ! -s "$out" ]; then
  echo "在 ${plan} 里找不到任务 ${n}（没有匹配「任务 ${n}」或「Task ${n}」的标题）" >&2
  exit 3
fi

echo "已写入 ${out}：$(wc -l < "$out" | tr -d ' ') 行"
