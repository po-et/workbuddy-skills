# 来源与许可

- 来源：https://github.com/obra/superpowers — `skills/subagent-driven-development/`（SKILL.md、implementer-prompt.md、task-reviewer-prompt.md、re-review-prompt.md、scripts/sdd-workspace、scripts/task-brief、scripts/review-package）
- 许可证：MIT，Copyright (c) 2025 Jesse Vincent
- 取回日期：2026-09-17

## 本版改动

- 全文中文化（术语按中文语境改写），保留连续执行与「要裁决不要停摆」原则、四类停机条件、账本机制、冲突预扫表、选模型分级、主循环五步、五轮封顶与熔断裁决、终审与收尾裁决清单、借口反驳表。
- 三份子代理提示词模板复刻到 `references/`，三个 bash 脚本复刻到 `scripts/`，正文改用 `{baseDir}/` 引用。
- **脚本文件名补上 `.sh` 扩展名**（`sdd-workspace.sh`、`task-brief.sh`、`review-package.sh`），因为 SkillHub 上传拒绝无扩展名文件；脚本之间的互相调用也同步改名。
- 工作目录由 `.superpowers/sdd/<计划名>/` 改为与上游工具无关的 `.sdd/<计划名>/`，隔离语义与自我忽略的 `.gitignore` 机制保持不变。
- `task-brief.sh` 的 awk 匹配从只认英文 `Task N` 扩展为同时认中文「任务 N」，以适配中文实施计划。
- 原文 `superpowers:` 跨技能引用改为本仓中文技能名：`using-git-worktrees-zh`、`executing-plans-zh`、`finishing-a-development-branch-zh`；终审所用的 `../requesting-code-review/code-reviewer.md` 未复刻，改为指向本仓已有的中文代码评审技能（`code-review-zh` / `code-review-five-axis-zh`）。
- 原文的两张 graphviz `dot` 流程图未复刻；其分支信息已完整体现在「主循环」各步与修复循环的文字描述中。
- 原文结尾的 "Example Workflow" 长示例未复刻（它是一次具体会话的流水记录）；其中的规则已在正文各节写明。
- 新增「何时用」与「输出契约：收尾」两节小标题，并在「准备」一节补三条可直接执行的开场命令。

## MIT License（原文声明）

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
