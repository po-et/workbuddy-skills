# 来源与许可

- 来源：https://github.com/obra/superpowers — `skills/systematic-debugging/`（SKILL.md、root-cause-tracing.md、defense-in-depth.md、condition-based-waiting.md）
- 许可证：MIT，Copyright (c) 2025 Jesse Vincent
- 取回日期：2026-09-17

## 本版改动

- 全文中文化（术语按中文语境改写），保留铁律、四阶段流程、三次失败即质疑架构的熔断规则、红线清单与借口反驳表。
- 三份配套手法复刻到 `references/`，正文改用 `{baseDir}/references/*.md` 引用。
- 原文 `superpowers:test-driven-development` 与 `superpowers:verification-before-completion` 两处跨技能引用，改为本仓中文技能名（`tdd-zh`、`verification-before-completion-zh`）。
- 未复刻原文的 `find-polluter.sh` 与 `condition-based-waiting-example.ts`，改为在参考文档里内联等价的 bash 二分片段与 Python 版 `wait_for` 实现，避免引入可执行脚本依赖。
- 原文取证示例中的 macOS 代码签名命令改写为与平台无关的分层探针骨架；graphviz `dot` 判定图改写为中文文字判定，便于纯文本阅读。
- 新增「输出契约」一节，规定每个阶段结束时要给出的可核对结论。
- 原文中以第一人称引述的个人调试轶事与统计数字（某次会话的测试条数、通过率）已删除，不作为事实保留。

## MIT License（原文声明）

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
