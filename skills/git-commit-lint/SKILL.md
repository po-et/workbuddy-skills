---
name: git-commit-lint
description: 提交信息规范检查、Conventional Commits 校验、commit message lint、commitlint 的零依赖替代、提交历史体检、commit-msg 钩子、在 CI 里拦掉不规范提交、type 分布统计。当用户说「检查一下这个分支的提交信息规不规范」「提交信息格式不对能不能在 CI 拦掉」「按 Conventional Commits 校验一下 commit」「给仓库装个 commit-msg 钩子」「这次迭代都提了些什么类型的改动」时使用。附纯标准库脚本 scripts/git_commit_lint.py，对 origin/main..HEAD 或指定范围逐条校验 type 白名单、scope 格式、首行显示宽度与句号结尾、标题与正文之间的空行、正文行宽、BREAKING CHANGE 与感叹号标记的一致性、wip 与临时提交这类无信息主题，并统计 type 分布；git 路径从环境变量 GIT_BIN 读取，--message-file 校验单条可做 commit-msg 钩子，--json 结构化输出，--strict 有错误退出码 1。
author: Captain
version: 0.1.0
display_name: "提交信息规范检查"
display_name_en: "Git Commit Lint"
description_zh: "一条命令按 Conventional Commits 体检一个提交范围：type、scope、首行宽度、空行、BREAKING CHANGE 一致性与无信息主题，逐条给改法；可做 CI 门禁与 commit-msg 钩子，纯 Python 标准库。"
description_en: "Lint a commit range against Conventional Commits in one command: type, scope, header width, blank line, BREAKING CHANGE consistency and low-information subjects, each with a fix; works as a CI gate or commit-msg hook, pure Python stdlib."
examples_zh:
  - "检查一下这个分支的提交信息规不规范"
  - "提交信息格式不对能不能在 CI 拦掉"
  - "这次迭代都提了些什么类型的改动"
examples_en:
  - "Lint the commit messages on this branch"
  - "Fail CI when a commit message breaks the convention"
  - "Show the commit type distribution for this iteration"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "📝" } }
---

# 提交信息规范检查

按 Conventional Commits 逐条体检提交信息，指出问题并给出改法，适用于合并前自查、CI 门禁、commit-msg 钩子与迭代回顾时的 type 分布统计。纯 Python 标准库，不装 Node、不装 commitlint。

## 用法

```bash
python3 scripts/git_commit_lint.py                                   # 默认 origin/main..HEAD
python3 scripts/git_commit_lint.py --range main..HEAD --strict        # CI 门禁
python3 scripts/git_commit_lint.py --range HEAD~20..HEAD --json       # 结构化结果
python3 scripts/git_commit_lint.py --message-file .git/COMMIT_EDITMSG --strict
GIT_BIN=/usr/local/bin/git python3 scripts/git_commit_lint.py --repo ../other-repo
```

参数：`--range` 提交范围、`--repo` 仓库路径、`--types` 覆盖 type 白名单、`--max-subject`（默认 72 列）、`--max-body`（默认 100 列）、`--banned` 自定义禁止词、`--allow-merge` 放过 merge 提交、`--max-count` 限制条数。

## 规则一览

| 级别 | 规则 | 检查点 |
|---|---|---|
| error | CM001 | 首行不是 `<type>(<scope>)!: <说明>`，或冒号后缺空格 |
| error | CM002 | type 不在白名单（feat fix docs style refactor perf test build ci chore revert） |
| error | CM003 | scope 为空括号，或含大写与非法字符 |
| error | CM004 | 首行显示宽度超过 72 列（中文按 2 列算） |
| error | CM005 | 首行以句号或。结尾 |
| error | CM006 / CM007 | 提交信息为空；标题与正文之间缺空行 |
| error | CM009 | 正文有 BREAKING CHANGE 却没有 `!` 标记 |
| error | CM010 | 主题是 wip、tmp、update、修改、优化 这类无信息内容或含禁止词 |
| warn | CM008 / CM011 / CM012 / CM013 | 正文行过宽；主题首字母大写；merge 提交；主题过短 |
| warn | CM009 | 有 `!` 但正文没有 BREAKING CHANGE 段落 |
| info | CM014 | revert 提交建议保留 `This reverts commit <sha>` 正文 |

## 流程

1. 提 PR 前先跑一次默认范围，把 error 清零；warn 按团队口味决定是否处理。
2. 按输出里的「→ 改法」改：最近一条用 `git commit --amend`，更早的用 `git rebase -i <base>` 选 reword。
3. 已推送的分支改写后用 `git push --force-with-lease`；主干分支的历史不要改写，遗留问题在下次提交时纠正即可。
4. 迭代回顾时看「类型分布」：feat 与 fix 的比例反映这个迭代是在做新功能还是在还债；chore 比例过高通常意味着提交粒度不合理。

## 接入 CI 与 commit-msg 钩子

```bash
# CI（仓库需完整历史，GitHub Actions 里设 fetch-depth: 0）
python3 scripts/git_commit_lint.py --range origin/${BASE_BRANCH}..HEAD --strict

# 本地钩子：写完提交信息立刻校验，不合规直接拒绝提交
printf '#!/bin/sh\npython3 "$PWD/scripts/git_commit_lint.py" --message-file "$1" --strict\n' > .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

## 边界与常见问题

- 默认范围 `origin/main..HEAD` 在本地没有 origin 或主干叫 master 时会失败，脚本会提示改用 `--range main..HEAD`；CI 浅克隆要把 fetch-depth 设为 0，否则范围里看不到提交。
- 只看提交信息，不看 diff：说明文字和实际改动是否一致，脚本判断不了，仍然需要人来评审。
- merge 提交默认只报 warn 且不再检查其余规则，`--allow-merge` 可以完全忽略；revert 提交按普通提交校验。
- 不自动改写历史，也不替你执行 rebase，所有修改都由你确认后手动执行；脚本本身不做任何写操作。
- 中文主题按显示宽度计算，72 列约等于 36 个汉字；团队若习惯更长的标题用 `--max-subject` 调整，不要靠关掉规则来绕过。
