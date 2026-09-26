# 会修改远端的命令写法

下面每一条都**会修改远端，执行前确认**：先按 SKILL.md 里的「变更预览」格式给用户看，拿到明确的「确认」再执行，一次确认只对应一条命令。

这些命令只对照 `--help` 核对过参数，没有实际执行；`OWNER/REPO` 和编号换成真实值。

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

## 留后路的写法

- PR 先开 `--draft`。
- release 先存 `--draft`，确认内容无误后再用 `gh release edit v1.2.0 -R OWNER/REPO --draft=false` 发布。
- 关错的 issue 用 `gh issue reopen 123 -R OWNER/REPO` 重新打开。
- 以上补救命令同样会修改远端，执行前确认。
- `gh workflow run` 可能触发部署，先问清这个 workflow 做什么。

## 执行前先用只读命令核对的项目

| 要执行的操作 | 先查什么（只读） |
|---|---|
| 合并 PR | `gh pr view 123 -R OWNER/REPO --json state,isDraft,reviewDecision,mergeable,baseRefName,headRefName`，再看 `gh pr checks 123 -R OWNER/REPO` |
| 关闭 issue | `gh issue view 123 -R OWNER/REPO`，确认编号和标题对得上 |
| 重跑 CI | `gh run view 456789 -R OWNER/REPO`，确认是哪一次运行、哪个 workflow |
| 发 release | `gh release list -R OWNER/REPO --limit 5`，确认版本号没有重复 |
