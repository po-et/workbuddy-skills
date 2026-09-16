# 来源与许可

- 来源：https://github.com/mattpocock/skills — `skills/engineering/code-review/SKILL.md`
- 许可证：MIT，Copyright (c) Matt Pocock
- 取回日期：2026-09-17

## 本版改动

- 全文中文化；Fowler 12 种坏味道整理为表格（表现 / 处理）。
- 原文用并行 sub-agent 分别评审两轴，本版改为同一会话内分两段独立评审并禁止合并重排，适配没有子代理的运行时。
- 原文依赖 `docs/agents/issue-tracker.md`（由 `/setup-matt-pocock-skills` 生成），本版改为按提交信息 / 用户路径 / 常见目录寻找 spec。
- 新增 `scripts/review_prep.py`：预扫调试遗留、疑似密钥（脱敏显示）、超长行、巨型文件、散弹式修改、有代码无测试、重复新增代码块、工单引用。

## MIT License（原文声明）

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
