---
name: github-cli-ops
description: "GitHub 操作——用 gh 命令行查 issue 与 PR、看 CI 失败日志、发 release、用 gh api 取字段，改远端前先确认。当用户说「列一下 issue」「PR 的 CI 挂了」「发个 release」时使用。"
author: Captain
version: 0.1.0
display_name: "GitHub 操作"
display_name_en: "GitHub CLI Ops"
description_zh: "用 gh 命令行处理 GitHub 日常：筛 issue、看 PR 状态与 checks、看 workflow 失败日志、查 release、用 gh api 加 --jq 取字段。命令分只读与会修改远端两类，写操作先给变更预览、等确认再执行；登录由用户自己运行 gh auth login。"
description_en: "Handle everyday GitHub work with the gh CLI, split into read-only queries and remote-changing commands that always wait for explicit confirmation."
tags:
  - "GitHub"
  - "gh命令行"
  - "gh cli"
  - "issue"
  - "pull request"
  - "CI检查"
  - "GitHub Actions"
  - "release"
  - "gh api"
examples_zh:
  - "帮我列一下 cli/cli 里没人认领的 bug issue"
  - "这个 PR 的 CI 挂了，帮我看是哪一步失败"
  - "gh api 怎么取字段，我只要最新 release 的版本号"
---

# GitHub 操作

适用于用 `gh` 命令行查 issue 和 PR、看 CI、查或发 release、调 GitHub API。下文用公开仓库 cli/cli 演示，只读命令均已实测，换成你的 `owner/repo` 即可。**登录只由用户自己在终端运行 `gh auth login`**；命令退出码为 4 表示需要登录，请用户自己完成，不要让用户把 token 贴进对话。

## 先判断什么

1. **只读还是会改远端**：只读命令直接跑；建、改、关、评论、审批、合并、重跑、发布，以及非 GET 的 `gh api`，都要先给「变更预览」，等用户明确回复「确认」再执行。
2. **目标仓库对不对**：不写 `-R` 时，gh 按当前目录的 git 远端推断仓库。实测在一个远端指向 cli/cli 的空目录里，`gh issue list` 直接列出了 cli/cli 的 issue——在错的目录里执行写操作，就是改错仓库。所以一律显式写 `-R`。
3. **给人看还是给程序用**：给人看用默认表格；要统计、筛选、拼报告，用 `--json 字段 --jq 表达式`（gh 内置 jq，不用另装）。

## 只读查询（放心跑）

```bash
# 仓库概况
gh repo view cli/cli --json name,stargazerCount,defaultBranchRef --jq '"\(.name) ★\(.stargazerCount) 默认分支 \(.defaultBranchRef.name)"'
# issue：按标签筛；用 GitHub 搜索语法筛「没人认领、按最近更新排」；看详情和评论
gh issue list -R cli/cli --label bug --limit 10
gh issue list -R cli/cli --search "no:assignee sort:updated-desc" --limit 10
gh issue view 14394 -R cli/cli --comments
# PR：状态、审批、失败的检查项、改了哪些文件
gh pr list -R cli/cli --state open --limit 10
gh pr view 14509 -R cli/cli --json state,reviewDecision,statusCheckRollup --jq '{state, reviewDecision, failed: [.statusCheckRollup[] | select(.conclusion=="FAILURE") | .name]}'
gh pr checks 14509 -R cli/cli
gh pr diff 14509 -R cli/cli --name-only
# CI：最近失败的运行 → 哪个 job 哪一步 → 只看失败步骤的日志
gh run list -R cli/cli --status failure --limit 5
gh run view 35762769045 -R cli/cli
gh run view 35762769045 -R cli/cli --log-failed | grep -iE 'error|fail' | head -20
# release
gh release list -R cli/cli --limit 5
gh release view -R cli/cli --json tagName,publishedAt --jq '"\(.tagName) \(.publishedAt)"'
# gh api：REST 接口加 --jq 取字段；带 -f 参数查询时必须写 -X GET
gh api repos/cli/cli --jq '.stargazers_count'
gh api -X GET search/issues -f q='repo:cli/cli is:issue is:open label:bug' --jq '.total_count'
gh api rate_limit --jq '.resources.core.remaining'
```

字段名记不住时，`gh issue list -R cli/cli --json` 不带字段会列出全部可用字段。

## 会修改远端的操作（执行前确认）

下面每一条都**会修改远端，执行前确认**。这些命令只对照 `--help` 核对过参数，没有实际执行；`OWNER/REPO` 和编号换成真实值。

```bash
# 会修改远端，执行前确认
gh issue create -R OWNER/REPO --title "标题" --body-file issue.md --label bug
gh issue comment 123 -R OWNER/REPO --body "已复现，排查中"
gh issue close 123 -R OWNER/REPO --reason "not planned" --comment "说明原因"
gh pr create -R OWNER/REPO --base main --head my-branch --title "标题" --body-file pr.md --draft
gh pr review 123 -R OWNER/REPO --approve
gh pr merge 123 -R OWNER/REPO --squash --delete-branch
gh run rerun 456789 -R OWNER/REPO --failed
gh workflow run ci.yml -R OWNER/REPO --ref main
gh release create v1.2.0 -R OWNER/REPO --title "v1.2.0" --generate-notes --draft --verify-tag
gh api -X POST repos/OWNER/REPO/issues/123/comments -f body='内容'
```

执行前按这个格式给用户看，一次确认只对应一条命令：

```text
变更预览
仓库：OWNER/REPO
命令：gh pr merge 123 -R OWNER/REPO --squash --delete-branch
效果：PR #123 压缩成一个提交合入 main，并删除分支 my-branch
谁会知道：PR 参与者收到合并通知
能否撤销：合并撤不回，只能另开 PR 回退；分支可在 PR 页面恢复
回复「确认」后执行
```

能留后路就留：PR 先开 `--draft`；release 先存 `--draft`，再用 `gh release edit v1.2.0 --draft=false` 发布；关错的 issue 用 `gh issue reopen` 打开（这两条同样会修改远端，执行前确认）。`gh workflow run` 可能触发部署，先问清这个 workflow 做什么。

## 最常见的坑

1. **`gh api` 带参数自动变 POST**：帮助文档写明，加了 `-f`/`-F` 参数，默认方法就从 GET 变成 POST。只想查询时必须写 `-X GET`，否则轻则报 Not Found，重则对接受 POST 的接口真的建出东西。
2. **列表默认有条数上限**：`issue list`、`pr list`、`release list` 默认 30 条，`run list` 默认 20 条。要总数用 `search/issues` 的 `total_count`，或调大 `--limit`。
3. **`gh pr checks` 退出码 8**：表示还有检查在跑，脚本里别当成失败；要等结果加 `--watch`。
4. **日志别整份拉**：`--log` 输出全部步骤，实测 cli/cli 一次单元测试运行就有 5765 行；先 `gh run view` 找到失败的 job，再用 `--log-failed`。
5. **凭据**：token 只存在 gh 的登录状态，或用户自己配置的环境变量 `GH_TOKEN` 里；不在命令行里写 token，不执行任何会打印 token 的命令。

## 输出契约

- 只读查询：先给结论（例如「3 个检查失败，都在 Lint 这一步」），再附原始命令方便复跑；列表结果注明用了多大的 `--limit`、查询时间。
- 写操作：先给变更预览，拿到明确「确认」才执行；执行后回报链接和新状态。批量写（例如一次关 20 个 issue）先列清单，分批确认。

## 边界与不做什么

- 不替用户登录，不读取、不打印 token；权限不够时说明缺什么权限，由用户自己处理。
- 删除仓库、改可见性、改分支保护、设置 secrets、管理组织成员这类高危操作只做说明，由用户自己在网页上完成。
- 不在别人的仓库批量评论、开 issue 或 @ 人，遵守对方的贡献指南；不帮忙绕过 CI 检查或审批强行合并。
