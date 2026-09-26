---
name: github-cli-ops
description: "GitHub 操作——用 gh 命令行查 issue 与 PR、看 CI 失败日志、发 release、用 gh api 取字段，改远端前先确认。当用户说「列一下 issue」「PR 的 CI 挂了」「发个 release」时使用。"
author: Captain
version: 0.1.1
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
examples_en:
  - "List the unassigned bug issues in cli/cli"
  - "The CI on this PR failed. Find out which step broke"
  - "How do I pull out a single field with gh api? I only need the latest release version"
---

# GitHub 操作

适用于用 `gh` 命令行查 issue 和 PR、看 CI、查或发 release、调 GitHub API。下文用公开仓库 cli/cli 演示，只读命令均已实测，换成你的 `owner/repo` 即可。**登录只由用户自己在终端运行 `gh auth login`**；命令退出码为 4 表示需要登录，请用户自己完成，不要让用户把 token 贴进对话。

## 何时使用

用户这样说时用：

- 「列一下 cli/cli 里没人认领的 bug issue」
- 「这个 PR 的 CI 挂了，帮我看是哪一步失败」
- 「最新 release 是哪个版本」「发个 release」
- 「gh api 怎么取字段，我只要一个版本号」
- 「帮我把 PR #123 合了」「把失败的 workflow 重跑一下」

需要用户给：仓库 `OWNER/REPO`，以及 issue、PR 或运行的编号（直接给链接也行）；本机已装 gh，并由用户自己登录。

不适用：

- 本地 git 操作（提交、变基、解决冲突）：那不是 gh 的活，直接给 git 命令，或转交 git 相关技能。
- GitLab、Gitee 等其他平台：本技能只覆盖 GitHub 的 gh 命令行。
- 删除仓库、改可见性、改分支保护、设置 secrets、管理组织成员：只做说明，由用户自己在网页上完成（见文末边界）。

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
# CI：最近失败的运行 → 哪个 job 哪一步 → 只看失败步骤的日志（用 python3 过滤，Windows 把 python3 换成 py）
gh run list -R cli/cli --status failure --limit 5
gh run view 35762769045 -R cli/cli
gh run view 35762769045 -R cli/cli --log-failed | python3 -c "import re,sys;L=[l.rstrip() for l in sys.stdin if re.search('error|fail',l,re.I)];print(*L[:20],sep='\n')"
# release
gh release list -R cli/cli --limit 5
gh release view -R cli/cli --json tagName,publishedAt --jq '"\(.tagName) \(.publishedAt)"'
# gh api：REST 接口加 --jq 取字段；带 -f 参数查询时必须写 -X GET
gh api repos/cli/cli --jq '.stargazers_count'
gh api -X GET search/issues -f q='repo:cli/cli is:issue is:open label:bug' --jq '.total_count'
gh api rate_limit --jq '.resources.core.remaining'
```

字段名记不住时，`gh issue list -R cli/cli --json` 不带字段会列出全部可用字段。只知道分支、不知道运行编号时，用 `gh run list -R OWNER/REPO --branch 分支名 --status failure --limit 1` 找到最近失败的那次。

## 会修改远端的操作（执行前确认）

建、改、关、评论、审批、合并、重跑、发布，以及非 GET 的 `gh api`，都**会修改远端，执行前确认**。常用命令的写法（issue、PR、run、workflow、release、`gh api -X POST`）和「执行前先查什么」见 [references/write-commands.md](references/write-commands.md)；那些命令只对照 `--help` 核对过参数，没有实际执行。

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

能留后路就留：PR 先开 `--draft`；release 先存 `--draft`，再用 `gh release edit v1.2.0 -R OWNER/REPO --draft=false` 发布；关错的 issue 用 `gh issue reopen` 打开（这两条同样会修改远端，执行前确认）。`gh workflow run` 可能触发部署，先问清这个 workflow 做什么。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话 |
|---|---|---|
| 没说仓库或编号 | 先问 `OWNER/REPO` 和编号（或直接要链接）；只读查询可先用当前目录推断的仓库，但结论里写明并标 [待确认]；写操作必须等用户给出明确仓库 | 「是哪个仓库、哪个 PR？直接把链接发我最省事。」 |
| 说「CI 挂了」但不知道是哪次运行 | 有 PR 号就先 `gh pr checks`；只有分支就 `gh run list --branch 分支 --status failure --limit 1` | 「给我 PR 号或分支名，我先找出失败的那次运行。」 |
| 要求自相矛盾（「合并这个 PR，但别动 main」） | 指出矛盾：合并一定会改 base 分支；给两种理解让用户选 | 「合并一定会改它的 base 分支。你是想①只批准不合并，还是②先把 base 换成别的分支再合并？」 |
| 未登录（退出码 4），或权限不够（HTTP 403、404） | 请用户自己运行 `gh auth login`；权限不够就说明缺什么，由用户处理 | 「需要先登录：请你在终端运行 gh auth login，不用把 token 发给我。」 |
| 超出范围（删库、改可见性、分支保护、secrets、组织成员） | 只说明要做什么、有什么影响，由用户在网页上自己完成 | 「这类高危操作我不执行；我可以先把影响列清楚，你在网页上自己操作。」 |
| 时间紧，只要最小可用版 | 最小版 = 一句结论 + 一条可复跑命令 + 失败步骤日志的前 20 行 | 「先给结论：……；复跑命令在下面，完整日志需要的话我再拉。」 |
| 用户坚持越界（贴 token、用 `--admin` 绕过检查强行合并、在别人仓库批量评论或 @ 人） | 守住边界，给能做的替代 | 「token 不要发在对话里；绕过检查强行合并我不做，我可以先帮你查清为什么没过。」 |
| 列表结果看起来不全 | 默认有条数上限；调大 `--limit`，或用 `total_count` 先数总数 | 「这是前 30 条（gh 默认上限），要总数我用 total_count 数一下。」 |

gh 的退出码与常见报错（退出码出自本机 gh 2.98.0 的 `gh help exit-codes` 与 `gh pr checks --help`）：

| 退出码 / 报错 | 原因 | 修正办法 |
|---|---|---|
| 0 | 成功 | —— |
| 1 | 命令失败：参数错、对象不存在、接口报错 | 看报错里的 HTTP 状态：404 多为仓库名或编号写错，或无权访问私有仓库；403 或 429 多为权限不足或触发限流（`gh api rate_limit --jq '.resources.core.remaining'` 看剩余额度）；422 是请求没通过校验，按报错里点名的字段改 |
| 2 | 命令运行中被取消（如按了 Ctrl+C） | 重新运行；写操作先用只读命令查它是否已经生效，再决定要不要重跑 |
| 4 | 需要登录 | 用户自己运行 `gh auth login` |
| 8（仅 `gh pr checks`） | 还有检查在跑 | 不当成失败；加 `--watch` 等结果 |
| 没写 `-R`，报错说找不到仓库或 git 远端 | gh 从当前目录推断仓库失败 | 显式写 `-R OWNER/REPO` |

## 输出契约

只读查询，按这个顺序交付：

1. **结论**：一句话，例如「3 个检查失败，都在 Lint 这一步」。
2. **证据**：失败的 job 与步骤名、日志关键行（不超过 20 行）。
3. **复跑命令**：原始命令，全部带 `-R`。
4. **查询条件**：仓库、用了多大的 `--limit`、查询时间。

写操作，按这个顺序交付：

1. **变更预览**（格式见上），一次只对应一条命令。
2. **等待**用户明确回复「确认」；没有确认就停在这一步。
3. **执行结果**：退出码、链接、新状态（用只读命令查一遍）。
4. 批量写（例如一次关 20 个 issue）：先列清单，分批确认，每批都给预览。

占位符：[待补] = 还不知道的仓库、编号、分支，命令里先写 `OWNER/REPO`、`123` 并标 [待补]；[待确认] = 从当前目录推断出来的仓库、还没核实的编号。

交付前自检（逐条答是或否）：

- [ ] 每条命令都显式写了 `-R OWNER/REPO`？
- [ ] 会改远端的命令都先给了变更预览、一次只对应一条，并拿到「确认」才执行？
- [ ] 带 `-f` 或 `-F` 的查询型 `gh api` 写了 `-X GET`？
- [ ] 列表结果写明了 `--limit`，没有把「前 30 条」说成「全部」？
- [ ] 全文没有 token，也没有让用户贴 token？

## 示例

**示例**（仓库、编号和日志内容都是虚构的，用来演示交付格式）

用户：「这个 PR 的 CI 挂了，帮我看是哪一步失败。」

助手：「哪个仓库、哪个 PR？发链接也行。」

用户：「OWNER/REPO 的 #123。」

助手依次运行（全部只读）：

```bash
gh pr checks 123 -R OWNER/REPO
gh pr view 123 -R OWNER/REPO --json headRefName --jq .headRefName
gh run list -R OWNER/REPO --branch fix-config-parser --status failure --limit 1
gh run view 456789 -R OWNER/REPO
gh run view 456789 -R OWNER/REPO --log-failed | python3 -c "import re,sys;L=[l.rstrip() for l in sys.stdin if re.search('error|fail',l,re.I)];print(*L[:20],sep='\n')"
```

交付：

> **结论**：PR #123 有 1 项检查失败——`test` 这个 job 的 `Run unit tests` 步骤；其余检查都已通过。
>
> **证据**（失败步骤日志的关键行）：
> ```text
> --- FAIL: TestParseConfig (0.00s)
>     config_test.go:42: want 3 fields, got 2
> FAIL
> ```
>
> **复跑命令**：`gh run view 456789 -R OWNER/REPO --log-failed`
>
> **查询条件**：OWNER/REPO，PR #123，运行 456789（`gh run list --limit 1` 找到的最近一次失败），查询时间 2026-09-26 10:30。
>
> 下一步：先在本地跑这个测试复现；要重跑这次 CI 属于会修改远端的操作，我会先给变更预览。

合并 PR 的完整确认流程（查状态 → 变更预览 → 确认 → 执行 → 回报）见 [examples/merge-with-confirmation.md](examples/merge-with-confirmation.md)。

## 常见问题（FAQ）

**Q：为什么每条命令都要写 `-R`？**
A：不写时 gh 按当前目录的 git 远端推断仓库；在错的目录里执行写操作，改的就是错的仓库。

**Q：我把 token 发给你，你帮我登录行吗？**
A：不行。token 不要出现在对话里；请你自己在终端运行 `gh auth login`，登录状态由 gh 保存。

**Q：`gh api` 只是查询，为什么报 Not Found，还像是在发 POST？**
A：加了 `-f` 或 `-F` 参数后，默认方法会从 GET 变成 POST。只想查询就写 `-X GET`。

**Q：列表为什么只有 30 条？**
A：`issue list`、`pr list`、`release list` 默认 30 条，`run list` 默认 20 条。调大 `--limit`，或用 `search/issues` 的 `total_count` 数总数。

**Q：`gh pr checks` 返回 8，是失败了吗？**
A：不是，8 表示还有检查在跑；要等结果就加 `--watch`。

**Q：能一次帮我关掉 50 个 issue 吗？**
A：能做，但要先列出清单，分批确认，每批都给变更预览，不会一口气全关。

**Q：日志太长看不过来怎么办？**
A：先用 `gh run view` 找到失败的 job，再用 `--log-failed` 只看失败步骤，最后用上面的 python3 过滤出含 error、fail 的前 20 行。

## 常见错误（反模式）

| 错误做法 | 为什么错 | 正确做法 |
|---|---|---|
| 查询型 `gh api` 带了 `-f` 却不写 `-X GET` | 帮助文档写明：加了 `-f`/`-F` 默认方法就变成 POST，轻则报 Not Found，重则对接受 POST 的接口真的建出东西 | 只想查询时一律写 `-X GET` |
| 把列表结果当成全部 | `issue list`、`pr list`、`release list` 默认 30 条，`run list` 默认 20 条 | 调大 `--limit`，或用 `search/issues` 的 `total_count` |
| 把 `gh pr checks` 的退出码 8 当失败 | 8 表示还有检查在跑，脚本里会误判 | 要等结果加 `--watch` |
| 日志整份拉 | `--log` 输出全部步骤，实测 cli/cli 一次单元测试运行就有 5765 行 | 先 `gh run view` 找到失败的 job，再用 `--log-failed` |
| 在命令行里写 token，或运行会打印 token 的命令 | token 会留在对话、终端历史和日志里 | token 只存在 gh 的登录状态，或用户自己配置的环境变量 `GH_TOKEN` 里 |
| 不写 `-R`，靠当前目录推断仓库 | 目录不对就改错仓库 | 每条命令都显式写 `-R OWNER/REPO` |
| 一次「确认」执行好几条写命令 | 用户确认的是其中一条，其余等于没确认 | 一次确认只对应一条命令；批量先列清单、分批确认 |
| 检查没过就用 `gh pr merge --admin` 强行合并 | `--admin` 用管理员权限绕过合并要求，绕过的正是 CI 和审批 | 先查清检查为什么没过，修好再合并 |

## 边界与不做什么

- 不替用户登录，不读取、不打印 token；权限不够时说明缺什么权限，由用户自己处理。
- 删除仓库、改可见性、改分支保护、设置 secrets、管理组织成员这类高危操作只做说明，由用户自己在网页上完成。
- 不在别人的仓库批量评论、开 issue 或 @ 人，遵守对方的贡献指南；不帮忙绕过 CI 检查或审批强行合并。
