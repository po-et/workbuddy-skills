# 示例：合并 PR 的完整确认流程

**示例**（仓库、编号、分支名和各项状态都是虚构的，用来演示流程和交付格式；命令参数已对照 `gh pr merge --help`、`gh pr view --help` 核对）

## 第一轮：用户提出要求

用户：「帮我把 OWNER/REPO 的 PR #123 合了，用 squash。」

合并会修改远端，所以先只读查状态，不直接执行：

```bash
gh pr view 123 -R OWNER/REPO --json state,isDraft,reviewDecision,mergeable,baseRefName,headRefName
gh pr checks 123 -R OWNER/REPO
```

假设查到：PR 是 OPEN、不是草稿、`reviewDecision` 为 APPROVED、`mergeable` 为 MERGEABLE，base 是 `main`，head 是 `fix-config-parser`，检查全部通过。

助手回复：

```text
PR #123 目前可以合并：已批准，检查全部通过，没有冲突。

变更预览
仓库：OWNER/REPO
命令：gh pr merge 123 -R OWNER/REPO --squash --delete-branch
效果：PR #123 压缩成一个提交合入 main，并删除分支 fix-config-parser
谁会知道：PR 参与者收到合并通知
能否撤销：合并撤不回，只能另开 PR 回退；分支可在 PR 页面恢复
回复「确认」后执行
```

## 第二轮：用户确认

用户：「确认。」

助手执行这一条命令，再用只读命令核对结果：

```bash
gh pr merge 123 -R OWNER/REPO --squash --delete-branch
gh pr view 123 -R OWNER/REPO --json state,mergedAt,url --jq '"\(.state) \(.mergedAt) \(.url)"'
```

交付：

> 已执行 `gh pr merge 123 -R OWNER/REPO --squash --delete-branch`，退出码 0。
> 新状态：MERGED，合并时间 2026-09-26T02:41:07Z；链接：（此处放上面命令返回的 `url` 字段，即 PR #123 的页面地址）。
> 分支 fix-config-parser 已删除；需要恢复可以在 PR 页面操作。

## 如果检查没过

假设 `gh pr checks 123 -R OWNER/REPO` 显示 `test` 这一项失败：

> PR #123 还有 1 项检查没过（`test`），现在合并需要绕过检查，我不做这一步。
> 我可以先按「CI 挂了」的流程查失败日志；修好、检查通过后，再给你合并的变更预览。

用户若回复「用 --admin 强行合并」：

> `--admin` 会用管理员权限绕过合并要求，绕过的正是这项检查，我不执行。确实要合并的话，请你在确认风险后自己操作。
