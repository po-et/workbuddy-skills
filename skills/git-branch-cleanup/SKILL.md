---
name: git-branch-cleanup
description: git 分支清理、删除已合并分支、找出长期不动的陈旧分支、远端已删除但本地还在的分支、分支太多难管理、仓库分支治理。当用户说「帮我清理一下本地分支」「哪些分支已经合并可以删了」「远端有一堆没人动的分支」「生成一个删分支的脚本我看看再执行」时使用。附纯标准库脚本 scripts/branch_cleanup.py：只读分析，自动识别基线分支，把本地（可选远端）分支分成可删除（已合并/无独有提交）、需确认（超过 N 天无提交或远端已删但本地有未合并提交）、保留（受保护/当前/活跃），显示年龄、作者、领先提交数，生成逐行可审阅的删除脚本（已合并用 -d，其余仅注释）；不执行任何删除。也覆盖「已经合并可以删了」「没动的分支」「我确认后再跑」这类说法。
author: Captain
version: 0.1.1
display_name: "git 分支清理助手"
display_name_en: "Git Branch Cleanup"
description_zh: "只读分析本地与远端分支：已合并可删、陈旧需确认、受保护保留三类，附年龄/作者/领先提交数，生成人工审阅后再执行的删除脚本；不自动删除任何东西。纯 Python 标准库。"
description_en: "Read-only analysis of local and remote branches into delete (merged), review (stale or upstream gone) and keep (protected/active), with age, author and ahead-count, generating a deletion script for human review; never deletes anything itself. Pure Python stdlib."
tags:
  - "git 分支清理"
  - "分支治理"
  - "已合并分支"
  - "陈旧分支"
  - "git housekeeping"
examples_zh:
  - "看看本地哪些分支已经合并可以删了"
  - "分析 origin 上超过 90 天没动的分支"
  - "生成一个清理分支的脚本，我确认后再跑"
examples_en:
  - "Which local branches are merged and safe to delete?"
  - "Analyze origin branches idle for over 90 days"
  - "Generate a branch cleanup script for me to review before running"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🌿" } }
---

# git 分支清理助手

分支多到看不过来时，先分类再动手：**已合并**的安全删，**陈旧但有未合并提交**的要人确认，**受保护/活跃**的不碰。脚本只读，删除命令生成到脚本里由人执行。

## 何时用
本地或远端分支多到看不过来、想知道哪些能安全删、或要定期做分支治理时用。只想删一两个自己知道的分支，直接 `git branch -d` 即可，不需要跑分析。

## 产出
一份三分类清单（可删除/需确认/保留，各带年龄、作者、领先提交数），以及可选的 `--script` 生成的删除脚本——已合并分支写成可执行的 `git branch -d`，其余仅以注释形式列出待人工确认，脚本本身不会执行任何删除。

## 用法

```bash
python3 scripts/branch_cleanup.py                                  # 本地分支，自动识别 origin/main 等基线
python3 scripts/branch_cleanup.py --remote origin --stale-days 90   # 连远端一起分析（会 fetch --prune）
python3 scripts/branch_cleanup.py --script cleanup.sh              # 生成删除脚本
python3 scripts/branch_cleanup.py --json
```

## 流程

1. 跑脚本看三类清单。「可删除」= 已合并到基线或没有独有提交；「需确认」= 超过阈值天数无提交、或远端已删但本地有未合并提交。
2. 「需确认」逐个问分支作者（脚本列出了作者与领先提交数）；确认无用的改成 `-D`，有价值的先合并或打 tag 留档。
3. 用 `--script` 生成脚本，人工逐行审阅后执行；远端删除是 `git push origin --delete <branch>`，请再三确认。
4. 定期（每季度）跑一次；把 `--stale-days` 与受保护分支规则写进团队约定。

## 判定规则

| 类别 | 条件 | 生成命令 |
|---|---|---|
| 可删除 | 已合并到基线，或相对基线无独有提交 | `git branch -d` / `git push <remote> --delete` |
| 需确认 | 远端已删除（[gone]）但本地有未合并提交；或超过 `--stale-days` 无提交且有未合并提交 | 仅注释 `# git branch -D …` |
| 保留 | main/master/develop/release/*/hotfix/*/prod/staging、当前分支、基线；或活跃 | 无 |

## 边界

- 「已合并」按 `git branch --merged <基线>` 判断；squash 合并的分支不会被识别为已合并，会落在「需确认」里（领先提交数 > 0），需人工核对 PR 状态。
- 远端分析需要 fetch 权限；不会推送任何删除。
- 受保护分支的匹配规则在脚本顶部 `PROTECTED`，按团队约定调整。
