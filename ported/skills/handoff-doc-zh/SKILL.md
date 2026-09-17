---
name: handoff-doc-zh
description: 会话交接文档、把当前对话压缩成下一个 Agent 能接手的交接单、上下文太长要换会话、把任务交给同事或另一个模型。当用户说「写个交接文档」「把现在的进度整理一下给下一个会话」「上下文快满了帮我总结」「我要把这个交给别人继续」「换个模型接着做」时使用。规则：存到系统临时目录而不是工作区（除非用户指定）；不重复已有产物（spec、计划、ADR、工单、提交、diff）的内容，只按路径或 URL 引用；脱敏一切密钥、密码与个人信息；用户说明了下一会话的用途就据此裁剪；必含「建议技能」一节。附交接模板：目标与当前状态、已定决策、未完成项与下一步、涉及文件与验证命令、坑与未知、建议技能。改编自 Matt Pocock 的 handoff（MIT），补充了完整模板。
author: Captain
version: 0.1.0
display_name: "会话交接单"
display_name_en: "Handoff Document (zh)"
description_zh: "把当前对话压缩成下一个 Agent 或同事能直接接手的交接单：只引用不重复已有产物、脱敏、按下一会话的用途裁剪、附建议技能；模板含状态/决策/下一步/文件/验证/坑。"
description_en: "Compress the current conversation into a handoff a fresh agent or teammate can pick up: reference existing artifacts instead of duplicating, redact secrets, tailor to the next session's purpose, list suggested skills; template with state/decisions/next steps/files/verification/gotchas."
examples_zh:
  - "写一份交接文档，下个会话要继续做接口联调"
  - "上下文快满了，把进度整理成交接单"
  - "把这个排查任务交给同事，给他写个接手说明"
examples_en:
  - "Write a handoff, the next session continues API integration"
  - "Context is nearly full, summarize progress into a handoff"
  - "Hand this investigation to a teammate, write the pickup notes"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🤝" } }
---

# 会话交接单

写一份交接文档，让一个**全新的** Agent（或同事）能接着做。默认保存到操作系统的临时目录（macOS/Linux `$TMPDIR` 或 `/tmp`，Windows `%TEMP%`），**不放进当前工作区**——除非用户指定路径。

## 规则
1. **只引用不重复**：spec、计划、ADR、工单、提交、diff 里已有的内容不再复述，写路径或 URL。交接单是索引 + 增量，不是第二份文档。
2. **脱敏**：API 密钥、密码、令牌、个人身份信息一律写 `<REDACTED>`；命令里的凭证改成环境变量名。
3. **按用途裁剪**：用户说明了下一会话的用途（"继续联调接口""写测试"），就围绕它组织，无关历史一句带过。
4. **必含「建议技能」**：点名下一个 Agent 该调用哪些技能、各用来干什么。
5. **状态要能核对**：写"测试 12/12 通过（`pytest tests/`）"而不是"测试都过了"；写 `git status` 的实际情况（哪些未提交）。

## 模板
```
# 交接：<任务名>　　<日期>
## 目标与当前状态
一句话目标；进度百分比或阶段；最后一步做到哪。
## 已定决策（含否决的备选）
- 决策 —— 理由 —— 出处（ADR/工单/对话）
## 未完成项与下一步（按顺序）
1. 具体动作 —— 完成标准
## 涉及文件与工作树状态
- 路径 —— 作用；`git status` 摘要（已提交 / 未提交 / 未跟踪）
## 验证命令与最近结果
- `命令` → 结果与时间
## 坑与未知
- 已知陷阱；未验证的假设；需要人决定的问题
## 建议技能
- <技能名>：用于 …
## 参考
- spec / 计划 / 工单 / PR 链接
```

## 流程
1. 读当前对话与工作树，列出产物清单（哪些已落盘）。
2. 按模板填写，长度以一屏到两屏为宜；能删的历史都删。
3. 脱敏检查：grep 密钥样字符串。
4. 保存到临时目录，把路径告诉用户；用户要放进仓库就改路径（并确认不含敏感信息）。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `handoff`（MIT）。改动见 ATTRIBUTION.md。
