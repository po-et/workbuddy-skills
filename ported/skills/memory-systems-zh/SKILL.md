---
name: memory-systems-zh
description: Agent 记忆系统设计、跨会话知识保留、长期记忆、实体追踪与身份一致、时间有效性（事实会过期）、向量检索 vs 知识图谱 vs 时态知识图谱、记忆整理与合并、记忆框架选型（Mem0 / Zep-Graphiti / Letta / LangMem / Cognee / 文件系统）、记忆基准（LoCoMo / LongMemEval / DMR）。当用户说「Agent 怎么记住上次会话的事」「用什么记忆框架」「同一个人在不同对话里怎么保持一致」「过期的记忆污染了回答」「要不要上知识图谱」时使用。核心：记忆是从易失的上下文窗口到持久存储的光谱，默认选满足检索需求的最浅一层（先文件系统原型，再向量+元数据，再时态图谱，最后自管理记忆）；检索策略按查询形状匹配（语义 / 实体遍历 / 时间过滤 / 混合）；周期性整理——失效但不删除；记忆按需即时加载并放在注意力偏好位置；为检索失败设计兜底。附实现参考（向量库、属性图、时态图、整理器）。改编自 Agent Skills for Context Engineering 的 memory-systems（MIT）。
author: Captain
version: 0.1.0
display_name: "Agent 记忆系统设计"
display_name_en: "Memory Systems (zh)"
description_zh: "让 Agent 跨会话保持连续性：记忆分层（工作 / 短期 / 长期 / 实体 / 时态图谱）、按检索形状选框架、从最浅一层起步只在检索质量不够时加结构、追踪时间有效性、整理但不丢历史、为检索失败兜底。附框架对照、基准提示与实现参考。"
description_en: "Give agents continuity across sessions: memory layers (working / short-term / long-term / entity / temporal KG), pick frameworks by retrieval shape, start with the shallowest layer and add structure only when retrieval fails, track temporal validity, consolidate without discarding, design for retrieval failure. With framework comparison, benchmark notes and implementation reference."
examples_zh:
  - "给我们的客服 Agent 设计一个跨会话记忆方案"
  - "Mem0、Graphiti、Cognee 该选哪个"
  - "用户上个月说住上海，这个月说搬到深圳，记忆系统怎么处理"
examples_en:
  - "Design cross-session memory for our support agent"
  - "Mem0 vs Graphiti vs Cognee, which one?"
  - "User said Shanghai last month, Shenzhen now: how should memory handle it?"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# Agent 记忆系统设计

记忆是让 Agent 跨会话保持连续性、对积累的知识做推理的持久层。简单的 Agent 完全依赖上下文当记忆，会话一结束状态全丢。成熟的 Agent 实现分层记忆架构，在即时上下文需求与长期知识保留之间取平衡。从向量库到知识图谱再到时态知识图谱，是对结构化记忆逐步加大投入以换取更好检索与推理的演进。

## 什么时候用

- 构建必须跨会话持久化知识的 Agent
- 在记忆框架之间选型（Mem0、Zep/Graphiti、Letta、LangMem、Cognee）
- 需要跨对话维持实体一致性
- 对积累的知识做推理
- 设计可在生产中扩展的记忆架构
- 对照基准（LoCoMo、LongMemEval、DMR）评估记忆系统

不用于：文件草稿纸、运行日志、工具输出卸载；对话压缩或人可读的交接摘要→「上下文压缩」「会话交接单」；单条轨迹内的遮蔽、前缀缓存、token 预算。

## 核心概念

把记忆看作从**易失的上下文窗口**到**持久存储**的光谱。默认选满足检索需求的最简单一层——基准证据表明对某些记忆负载，工具复杂度远不如可靠检索重要。只在检索质量下降，或 Agent 需要多跳推理、关系遍历、时间旅行查询时才加结构（图谱、时间有效性）。

## 框架版图

按 Agent 需要的主导检索模式选框架，再用基准数据验证：

| 框架 | 架构 | 适合 | 代价 |
|---|---|---|---|
| Mem0 | 向量库 + 图记忆，可插拔后端 | 多租户系统、广泛集成 | 多代理场景不够专门 |
| Zep/Graphiti | 时态知识图谱，双时态模型 | 需要关系建模 + 时间推理的企业 | 高级功能锁在云版 |
| Letta | 自编辑记忆、分层存储（上下文内/核心/归档） | 完整的 Agent 自省、有状态服务 | 简单场景过于复杂 |
| Cognee | 可定制 ECL 流水线的多层语义图 | 会演化学习的记忆、多跳推理 | 摄入期处理重 |
| LangMem | LangGraph 工作流的记忆工具 | 已在 LangGraph 上的团队 | 与 LangGraph 强耦合 |
| 文件系统 | 带命名约定的纯文件 | 简单 Agent、原型 | 无语义搜索、无关系 |

需要双时态建模（既记事件何时发生、也记何时被摄入）选 Zep/Graphiti；优先快速上生产、托管基础设施选 Mem0；需要深度自省选 Letta；需要稠密的多层语义图且各环节可定制选 Cognee。

**基准：** 各系统在 DMR、LoCoMo、HotPotQA（多跳）上各有公开的高分或基线，但没有一个基准是决定性的。按**检索形状**比较，不按品牌；基准数字是有日期的证据，做产品声明前必须重测。稳定的设计规则：先浅、量检索质量、简单层失效才加语义或图结构。

## 记忆分层（决策点）

选满足持久化需求的最浅一层，每深一层都增加基础设施与运维成本：

| 层 | 持久性 | 实现 | 何时用 |
|---|---|---|---|
| 工作记忆 | 仅上下文窗口 | 系统提示里的草稿区 | 始终——放在注意力偏好位置 |
| 短期 | 会话内 | 文件系统、内存缓存 | 中间工具结果、对话状态 |
| 长期 | 跨会话 | KV 存储 → 图数据库 | 用户偏好、领域知识、实体登记 |
| 实体 | 跨会话 | 实体登记 + 属性 | 维持身份（「张三」跨对话是同一个人） |
| 时态图谱 | 跨会话 + 历史 | 带有效区间的图 | 会变的事实、时间旅行查询、防上下文冲突 |

## 检索策略

按查询形状匹配：

| 策略 | 何时用 | 局限 |
|---|---|---|
| 语义（嵌入相似） | 直接的事实查询 | 多跳推理退化 |
| 实体（图遍历） | 「关于 X 的一切」 | 需要图结构 |
| 时间（有效性过滤） | 事实随时间变化 | 需要有效性元数据 |
| 混合（语义 + 关键词 + 图） | 整体准确率最高 | 基础设施最多 |

混合检索只取相关子图或记忆，减少活跃上下文。

## 记忆整理

周期性整理防止无限增长——不受控的堆积会逐渐拖垮检索质量。**失效但不丢弃**：时间旅行查询需要重建过去状态。触发条件：记忆数量阈值、检索质量下降、定时。实现见参考。

## 实践指引

**选架构：从最简单的可行层起步，只在检索质量下降时加复杂度。** 多数 Agent 第一天不需要时态知识图谱。升级路径：
1. **原型**：文件系统记忆，事实存成带时间戳的结构化 JSON，先验证 Agent 行为再投入基础设施。
2. **扩展**：需要语义搜索和多租户隔离时，上 Mem0 或带元数据的向量库——文件查找做不了相似度查询。
3. **复杂推理**：需要关系遍历、时间有效性或跨会话综合时加 Zep/Graphiti（通用关系、图简单易推理）或 Cognee（更稠密的多层语义图）。
4. **完全掌控**：Agent 必须自管理记忆、深度自省时用 Letta 或 Cognee，它们把记忆操作暴露为一等的 Agent 动作。

**与上下文集成。** 记忆按需即时加载，不预加载全部；取回的记忆放在注意力偏好位置（上下文开头或结尾）。

**错误恢复（按序应用）。** 检索为空：放宽（去掉实体过滤、拉宽时间范围），仍空则请用户澄清。结果过期：检查 `valid_until`，多数过期就先整理再重试。事实冲突：取 `valid_from` 最新的；置信度低时把冲突摆给用户。存储失败：写入排队重试，永远不让记忆写入阻塞 Agent 的回复。

## 示例

**偏好变化不被旧记忆覆盖：**
```python
m.add("用户偏好深色模式和 Python 3.12", user_id="alice")
m.add("用户切换到了浅色模式", user_id="alice")
results = m.search("用户偏好什么主题？", user_id="alice")  # 取回当前的浅色模式
```

**时态查询：**
```python
graph.create_temporal_relationship(
    source_id=user_node, rel_type="LIVES_AT", target_id=address_node,
    valid_from=datetime(2024, 1, 15), valid_until=datetime(2024, 9, 1),  # 已搬走
)
graph.query_at_time({"type": "LIVES_AT", "source_label": "User"}, query_time=datetime(2024, 3, 1))
```

## 准则

1. 从文件系统记忆起步；检索质量要求时才加复杂度
2. 任何会变的事实都追踪时间有效性
3. 追求准确率时用混合检索
4. 周期性整理——失效但不删除
5. 为检索失败设计：查不到时永远有兜底
6. 考虑持久记忆的隐私影响（保留策略、删除权）
7. 改动前后都对照 LoCoMo 或 LongMemEval 测
8. 生产环境监控记忆增长与检索延迟

## 坑

1. **把所有记忆塞进上下文**：昂贵且拖垮注意力。用带相关性过滤的即时检索。
2. **忽略时间有效性**：事实会过期，没有有效性追踪，过期信息投毒上下文。
3. **过早过度工程**：简单的文件记忆在某些基准上胜过专门工具。只在简单方法明确失败时加精巧。
4. **没有整理策略**：无限增长逐渐拖垮检索质量。设数量阈值或定时触发。
5. **嵌入模型不匹配**：写用一个模型、读用另一个，向量空间不可互换。每个记忆库钉死一个嵌入模型，换模型就全量重嵌。
6. **图 schema 僵硬**：固定节点类型和关系标签在领域演化时崩坏。用通用关系类型和灵活的属性包。
7. **过期记忆投毒**：与当前状态矛盾的旧记忆悄悄腐蚀行为。实现过期策略或置信度衰减，检测到矛盾就显式摆出来。
8. **记忆与语境错配**：话题相关但语境错误（讨论 Python 语言时取回关于蟒蛇的记忆）。记忆条目带会话或领域元数据，检索时过滤。

## 参考

- [references/implementation.md](references/implementation.md)：向量库、带元数据索引的向量库、属性图与实体登记、时态知识图谱与时间点查询、记忆整理器、记忆-上下文集成器、Mem0 / Graphiti / Cognee 快速上手。
- 同系列：上下文压缩（context-compression-zh）、上下文退化诊断（context-degradation-zh）、上下文工程基础（context-fundamentals-zh）。

---
改编自 [Agent Skills for Context Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) 的 `memory-systems`（MIT）。改动见 ATTRIBUTION.md。
