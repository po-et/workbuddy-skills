---
name: pr-description
description: 生成 PR 描述、写 Merge Request 说明、根据分支提交和 diff 自动整理改动内容、PR 模板填充、变更说明、评审前准备。当用户说「帮我写这个 PR 的描述」「根据我这个分支的改动生成 MR 说明」「按模板整理一下这次改动的背景/内容/测试/风险」「提 PR 前帮我总结一下」时使用。附纯标准库脚本 scripts/pr_describe.py：自动找基线分支（origin/main 等），读取提交与 diff，按区域分组文件（核心代码/接口/前端/数据库迁移/配置/依赖/测试/CI/部署/文档），提取关联工单号、Conventional Commits 类型与 BREAKING 标记，生成含标题建议、背景、改动内容、测试清单、风险与回滚、关联工单、评审清单的 Markdown 草稿；支持 --base/--head/--out/--format github|gitlab。
author: Captain
version: 0.1.0
display_name: "PR 描述生成"
display_name_en: "PR Description Generator"
description_zh: "从分支的提交与 diff 自动生成 PR/MR 描述草稿：按区域分组改动、标出迁移/依赖/CI/配置风险、关联工单、测试与评审清单；Agent 再补上动机与验证步骤。纯 Python 标准库，只读 git。"
description_en: "Generate a PR/MR description draft from the branch's commits and diff: changes grouped by area, migration/dependency/CI/config risks flagged, linked issues, test and review checklists; the agent then fills in motivation and verification. Pure Python stdlib, read-only git."
examples_zh:
  - "帮我给当前分支写一份 PR 描述"
  - "对比 origin/develop 生成 MR 说明，写到 PR.md"
  - "这次改动的风险点和测试清单帮我整理出来"
examples_en:
  - "Write a PR description for the current branch"
  - "Generate an MR description against origin/develop into PR.md"
  - "Summarize the risks and test checklist for this change"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "📝" } }
---

# PR 描述生成

从 git 里读出这个分支相对基线的提交与改动，生成一份结构化的 PR/MR 描述草稿。脚本负责「事实」（改了什么、动了哪些敏感区域、关联哪些工单）；Agent 负责补「判断」（为什么改、怎么验证、风险怎么兜底）。

## 用法

```bash
python3 scripts/pr_describe.py                          # 自动找 origin/main、origin/master、origin/develop…
python3 scripts/pr_describe.py --base origin/develop --out PR.md
python3 scripts/pr_describe.py --format gitlab
```

## 流程

1. 跑脚本得到草稿。
2. 补「背景 / 动机」：结合工单、需求文档或对话，一两句话说清要解决的问题；不要复述文件列表。
3. 补「测试」：写明实际跑过的命令与结果（不是打算跑的），必要时附截图；无测试改动要说明原因。
4. 核对「风险与回滚」里脚本标出的项：数据库迁移、依赖变化、CI/部署配置、环境配置、无测试、改动过大；每项写处理方式或明确「已评估无影响」。
5. 标题采用脚本建议或按 Conventional Commits 自己写；破坏性变更在标题加 `!` 并在描述里写迁移说明。
6. 把结果贴进 PR/MR；GitHub 用 `Closes #123` 自动关联工单。

## 输出结构

标题建议 → 背景/动机 → 改动内容（按区域分组 + 提交记录）→ 测试清单 → 风险与回滚 → 关联工单 → 评审清单 → 统计（提交数、文件数、增删行）。

## 边界

- 只读 git，不调用远端 API，不创建 PR；创建可配合 `gh pr create --body-file PR.md` 或 `glab mr create`。
- 区域分组按路径与文件名的常见约定推断，特殊目录结构可能归错类，人工调整即可。
- 工单号识别 `#123`、`ABC-123`、`fixes #123` 等常见写法。
