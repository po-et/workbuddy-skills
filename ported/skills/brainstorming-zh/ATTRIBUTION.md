# 来源与许可

- 来源：https://github.com/obra/superpowers — `skills/brainstorming/`（SKILL.md、spec-document-reviewer-prompt.md）
- 许可证：MIT，Copyright (c) 2025 Jesse Vincent
- 取回日期：2026-09-17

## 本版改动

- 全文中文化（术语按中文语境改写），保留硬门禁、三条路线定级、反模式与红线表、三套清单、设计做法各节、spec 自查四项与用户复核门。
- Spec 评审提示词复刻到 `references/spec-reviewer-prompt.md`，正文改用 `{baseDir}/references/` 引用。
- 原文 `superpowers:writing-plans` 改为本仓中文技能名 `writing-plans-zh`；原文点名禁止调用的 `frontend-design` / `mcp-builder` 改为通用表述「任何其他实现类技能」。
- Spec 默认存放路径由 `docs/superpowers/specs/` 改为与上游工具无关的 `docs/specs/`。
- **未复刻可视化辅助的浏览器服务端**（原文 `scripts/server.cjs`、`start-server.sh`、`stop-server.sh`、`helper.js`、`frame-template.html` 与 `visual-companion.md`）。本版把这一节改写为与平台无关的能力描述，保留原文最关键的两条规则——按需提议且提议必须独立成一条消息、以及逐题判断「看图是否比读文字更清楚」。需要那套服务端的用户请直接参考上游仓库。
- 原文的 graphviz `dot` 流程图未复刻；其分支信息已完整体现在「三条路线」与三套清单中。
- 新增「何时用」与「输出契约」两节，把三条路线各自的交付物显式化。
- 「探索项目现状」一步由纯文字说明补成可直接执行的命令片段，并把「找不到现成流程就不是有界任务」这条原文判据落到命令上。

## MIT License（原文声明）

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
