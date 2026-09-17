#!/usr/bin/env bash
# 解析并确保「一份计划专属」的工作目录存在，用于存放该计划的短期产物：
# 任务简报、实现者报告、评审包、进度账本。打印该目录的绝对路径。
#
# 一份计划一个目录（.sdd/<计划文件名>/），这样同一个工作树里的后续计划
# 永远不会读到或覆盖另一份计划的产物。把陈旧账本误当成当前进度，会让
# 协调者跳过整段已完成的任务序列 —— 按计划隔离目录，从结构上消除这种失败。
#
# 工作目录放在工作树里（而不是 .git/ 下），因为不少 Agent 运行时把 .git/
# 视为受保护路径、拒绝写入，那会导致实现者子代理写不了自己的报告文件。
# 在 .sdd/ 下放一个自我忽略的 .gitignore，就能让每份计划的工作目录都不
# 出现在 git status 里、也不会被误提交，且不需要改动任何已跟踪文件。
#
# 用法：sdd-workspace.sh PLAN_FILE
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "用法：sdd-workspace.sh PLAN_FILE" >&2
  exit 2
fi

plan=$1
[ -f "$plan" ] || { echo "计划文件不存在：$plan" >&2; exit 2; }

slug=$(basename "$plan" .md)
[ -n "$slug" ] && [ "$slug" != "." ] && [ "$slug" != ".." ] \
  || { echo "无法从该路径推导出工作目录名：$plan" >&2; exit 2; }

root=$(git rev-parse --show-toplevel)
base="$root/.sdd"
dir="$base/$slug"
mkdir -p "$dir"
printf '*\n' > "$base/.gitignore"
cd "$dir" && pwd
