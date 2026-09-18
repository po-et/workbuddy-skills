#!/usr/bin/env bash
# ClawHub 批量发布脚本。
#
# 前提（由用户本人完成，本脚本不做，也不碰任何 token）：
#   npx clawhub login          # GitHub OAuth 设备码登录
#   npx clawhub whoami         # 确认登录成功
#
# 用法：
#   tools/clawhub_publish.sh <技能绝对路径> [<技能绝对路径> ...]
#   例：tools/clawhub_publish.sh "$PWD"/dist/clawhub/dockerfile-check "$PWD"/dist/clawhub/iteration-report
#
# 必须用绝对路径——实测过 `npx clawhub skill publish` 传相对路径会报 "Path must be a folder"
# （见 docs/clawhub-notes.md「实测：三个技能的 --dry-run 全部跑通」一节），tools/clawhub_prep.py
# 打印的建议命令本身就是绝对路径，从那里复制最安全。
#
# 环境变量：
#   DRY_RUN=1（默认）  只跑 --dry-run，不会真正发布，可以反复跑
#   DRY_RUN=0          真正发布——确认过 dry-run 结果、确认过 categories/topics 拼写之后再用
#   INTERVAL=75        每个技能发布之间等待的秒数（默认 75，参考 SkillHub 实测踩过的限流经验；
#                      ClawHub 官方没公布 skill publish 的具体配额数字，保守起见沿用同一间隔，
#                      见 docs/clawhub-notes.md「限流 / 配额」一节）
#   CLAWHUB_ARGS       附加透传给每次 `clawhub skill publish` 的参数，比如
#                      CLAWHUB_ARGS='--categories development --topics "foo,bar"'
#                      注意这一份参数会用于本次调用的*所有*技能；不同技能要传不同 categories/
#                      topics 时，不要用这个批量脚本，直接照 tools/clawhub_prep.py 结尾打印的
#                      每个技能各自的建议命令逐条手动跑（更适合只有 3 个技能这种小批量、
#                      需要每条都看一眼结果的场景）。
#
# 每个技能开始前打印 "--- <slug>  HH:MM:SS ---"，方便事后从终端记录里摘取发布时间和结果。
# ClawHub 没有类似 tools/record_skillids.py 那种官方"skillId"字段可抄，--json 输出里能看到的
# 是 slug / version / fingerprint 等字段（发布成功后是否会多一个 release/attempt id，
# 没有实测过，第一次真正发布后打开一次 --json 输出确认字段名，再决定要不要照 record_skillids.py
# 的思路另写一个登记脚本）；简单做法是把本脚本的输出整个 tee 到日志文件，之后人工摘
# slug/version/状态到 docs/submission-checklist.md，参照该文件里 SkillHub 那几节的格式。

set -euo pipefail

DRY_RUN="${DRY_RUN:-1}"
INTERVAL="${INTERVAL:-75}"
CLAWHUB_ARGS="${CLAWHUB_ARGS:-}"

if [ "$#" -eq 0 ]; then
  echo "用法: $0 <技能绝对路径> [<技能绝对路径> ...]" >&2
  echo "先跑 tools/clawhub_prep.py 生成目录，再把它结尾打印的绝对路径传进来。" >&2
  exit 1
fi

for dir in "$@"; do
  # 注意：下面两条提示信息里 ${dir} 后面故意用半角括号——实测过 $dir 后面紧跟中文全角括号
  # （不隔一个 ASCII 字符）会被这里的 bash/locale 组合误判成变量名的一部分，报
  # "unbound variable"（该错误变量名里能看到一个 U+FFFD 替换字符）。用 ${} 加半角括号更稳妥。
  case "$dir" in
    /*) : ;;
    *)
      echo "跳过非绝对路径: ${dir} (clawhub skill publish 对相对路径会报 'Path must be a folder'，见 docs/clawhub-notes.md)" >&2
      continue
      ;;
  esac
  if [ ! -d "$dir" ]; then
    echo "跳过不存在的目录: ${dir}" >&2
    continue
  fi
  slug="$(basename "$dir")"
  ts="$(date +%H:%M:%S)"
  echo "--- ${slug}  ${ts} ---"
  if [ "$DRY_RUN" = "1" ]; then
    # shellcheck disable=SC2086
    npx clawhub skill publish "$dir" --slug "$slug" --dry-run --json $CLAWHUB_ARGS
  else
    # shellcheck disable=SC2086
    npx clawhub skill publish "$dir" --slug "$slug" --json $CLAWHUB_ARGS
  fi
  echo
  if [ "$dir" != "${!#}" ]; then
    echo "等待 ${INTERVAL}s 再发下一个…"
    sleep "$INTERVAL"
  fi
done
