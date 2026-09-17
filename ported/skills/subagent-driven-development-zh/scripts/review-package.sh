#!/usr/bin/env bash
# 生成评审包：提交列表、变更统计、以及带较多上下文的净 diff，写进一个文件，
# 评审人一次 Read 即可读全。用记录下来的每任务 BASE（而不是 HEAD~1），
# 才能保证多提交任务不被截断。
#
# 用法：review-package.sh PLAN_FILE BASE HEAD [OUTFILE]
# 默认 OUTFILE：<仓库根>/.sdd/<计划文件名>/review-<base7>..<head7>.diff
# （按区间命名，修复后的复审会拿到一个全新的独立文件）
set -euo pipefail

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
  echo "用法：review-package.sh PLAN_FILE BASE HEAD [OUTFILE]" >&2
  exit 2
fi

plan=$1
base=$2
head=$3
[ -f "$plan" ] || { echo "计划文件不存在：$plan" >&2; exit 2; }

git rev-parse --verify --quiet "$base" >/dev/null || { echo "BASE 无效：$base" >&2; exit 2; }
git rev-parse --verify --quiet "$head" >/dev/null || { echo "HEAD 无效：$head" >&2; exit 2; }

if [ $# -eq 4 ]; then
  out=$4
else
  dir=$("$(cd "$(dirname "$0")" && pwd)/sdd-workspace.sh" "$plan")
  out="$dir/review-$(git rev-parse --short "$base")..$(git rev-parse --short "$head").diff"
fi

{
  echo "# 评审包：${base}..${head}"
  echo
  echo "## 提交"
  git log --oneline "${base}..${head}"
  echo
  echo "## 变更文件"
  git diff --stat "${base}..${head}"
  echo
  echo "## Diff"
  git diff -U10 "${base}..${head}"
} > "$out"

commits=$(git rev-list --count "${base}..${head}")
echo "已写入 ${out}：${commits} 个提交，$(wc -c < "$out" | tr -d ' ') 字节"
