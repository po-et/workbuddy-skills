---
name: agent-engineering-expert
description: "Agent 工程专家.Skill——覆盖写 Agent、写技能、调提示词这一整份工作，服务对象是给 Agent 写指令、写技能、搭编排的人。在需要调整技能触发、提示词、上下文、工具契约或子代理分工，以及比较改动前后评测结果时使用。按失败记录定位原因并实施任务范围内的改法；提供离线 JSONL 成对评估脚本，输出通过变化、回退、缺失证据及耗时与成本覆盖情况。没有前后执行记录时明确标记未验证，不代替模型执行器，也不自行扩大发布权限。"
author: Captain
version: 0.1.2
homepage: https://github.com/po-et/workbuddy-skills
license: "CC-BY-4.0 AND MIT"
display_name: "Agent 工程"
display_name_en: "Agent Engineering Expert.Skill"
description_zh: "从失败记录定位技能触发、指令、上下文与工具编排问题；离线比较同一组案例的前后 JSONL 记录，输出通过变化、回退、缺失案例与证据，以及已记录的耗时和成本覆盖情况。"
description_en: "Diagnose skill routing, instructions, context and tool orchestration from failure evidence. Compare paired before/after JSONL records offline, reporting pass changes, regressions, missing cases and evidence, and recorded latency/cost coverage."
tags:
  - "Agent 工程"
  - "提示词"
  - "上下文工程"
  - "技能开发"
  - "SKILL.md"
  - "子代理编排"
  - "工具设计"
  - "Agent 评测"
examples_zh:
  - "我的技能写了却从来不触发，帮我改描述"
  - "Agent 越聊越傻，帮我定位是哪种上下文退化"
  - "比较这两份 JSONL 评测记录，列出回退和缺失证据"
examples_en:
  - "My skill never fires. Rewrite its description so the agent picks it up"
  - "The agent gets dumber as the session grows—which degradation mode is this?"
  - "Compare these two JSONL eval logs and report regressions and missing evidence"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# Agent 工程专家

把 Agent 的问题变成可复现的案例、明确的修改和可核对的前后记录。失败可能来自输入、指令、工具、执行环境或模型；没有证据时保留为待确认原因。

## 先找到可验证的改动

保留用户选择的模型、工具、目标和已授权范围。用户已经提供失败案例或修改方案时直接使用；缺少会影响实施的信息时再补问，同时推进不依赖答案的工作。

| 观察 | 需要核对的材料 | 可交付的改动 |
|---|---|---|
| 技能没有被选中或选错 | 实际问法、候选技能描述、选择记录 | 用准确的能力和适用情境改描述，保留不该触发的反例 |
| 选中了但漏掉约束 | 输入、完整指令、失败输出 | 消除冲突，明确验收条件；脆弱操作才补固定步骤 |
| 长会话丢失信息 | 信息位置、历史长度、检索与工具返回 | 移出无关材料、按需读取参考资料，保留决策和未完成事项的交接 |
| 参数错误或工具结果不可用 | 工具定义、请求、返回及错误记录 | 收窄参数契约，给有效示例和可恢复的错误信息 |
| 子代理互相覆盖或遗漏 | 任务分工、输入输出、合并记录 | 明确文件或职责归属、依赖关系与合并方式，按实际独立性并行 |
| 改完不知道有没有变好 | 相同案例的前后执行记录及判据 | 用下方脚本核对成对结果；回到具体回退案例继续改 |

表中是排查方向，不是必须顺序。优先检查已有证据指向的原因；多项改动确有必要时可以一起实施，在报告中说明归因限制。规则文件、提示词和技能正文的交付要包含实际修改文本，不能只给建议。

## 离线比较评测记录

本技能带有纯 Python 标准库脚本，不发网络请求、不调用模型、不运行证据文件。将已有执行器产生的记录整理为 JSONL：每行一个案例，至少包含 `case_id` 和严格布尔值 `passed`。`evidence` 记录输出文件、测试记录或判定摘要；空缺会使比较不完整。可选 `latency_ms`、`cost` 必须是有限的非负数，缺失保持未知，真实 0 会保留。

输入细节、退出码和报告字段见 [references/input-contract.md](references/input-contract.md)。第一次运行可以在本技能目录内使用附带的合成样例：

```bash
python3 scripts/agent_eval_compare.py \
  --before assets/before.jsonl \
  --after assets/after.jsonl \
  --out-dir out/agent-eval-demo
```

替换为自己的两份执行记录即可；输出目录须不存在，原始记录不改动。产生 `comparison.json` 和 `comparison.md`，终端显示判定与输出位置。退出码可接入现有检查流程：

- `0`：案例集合和证据完整，记录中没有通过转失败的回退；不代表全部案例通过。
- `1`：存在回退，或案例/证据不完整；报告仍会写出。
- `2`：输入无效或无法写出报告；错误会说明文件与行号。

案例 ID 决定配对，文件行序不影响结果。重复 ID、重复 JSON 键、数字 `1` 冒充布尔值、NaN/Infinity、坏行、未知字段和负指标会被拒绝。不同案例集合会列出各自缺失的 ID，不能拿不同分母的通过率直接声称改进。

## 读报告并继续实施

报告同时列出原始布尔转换、带双方证据的新增通过、所有记录中的回退，以及未配对案例和缺失证据。只有案例与证据完整且没有回退时，才允许把新增通过写成“本组已记录案例的通过数增加”。证据是输入者提供的记录，脚本不会证明它真实、不会打开它，也不会证明评测覆盖了全部业务。

耗时和成本只在同一个案例两侧都记录时计算均值差，并单独报告每侧记录数、成对覆盖数和缺失 ID。指标不齐时不能声称整体更快或更省；成本的单位和计算口径由记录来源说明，脚本不猜测货币、token 或 API 价格。即使指标完整，也只能描述这组执行记录的变化，不能推出用户增长或模型能力结论。

交付修改后附上实际运行的输入路径、判据、前后版本、输出位置和回退清单。只有单次记录时可以先建立基线，不能补造“改前失败”；没有运行时标记“未执行”。合成样例仅演示脚本行为，不是 WorkBuddy 客户端或真实用户评测。

## 完成长会话和技能改写

需要交接时保留目标、用户约束、已完成改动、实际证据、未解问题和下一步；不把推测原因写成结论。改写技能时保留其实际能力和名称约定，将长表、输入契约与案例放入按需读取的资料；关键逻辑能稳定重复时才固化成脚本。

## 边界

处理真实项目材料时沿用用户的数据边界；随包公开的案例采用合成数据。发布、模型执行和外部消息遵循当前任务的权限，不由本技能追加无关审批步骤或替用户更换工具。离线记录比较不替代真实执行、判据审查和用户反馈；缺少这些材料时说明实际可验证的范围。

---
本技能新增比较器与样例为原创实现，未复制专有技能。正文 CC BY 4.0，代码 MIT：https://github.com/po-et/workbuddy-skills
