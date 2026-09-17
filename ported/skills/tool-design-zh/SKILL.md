---
name: tool-design-zh
description: 给 Agent 设计工具、写 Agent 能据以路由的工具描述、工具 schema 与响应格式、参数命名规范、可自纠错的错误信息、MCP 服务器设计与命名、工具集合并与瘦身、决定该加还是删一个工具、架构减法（用少量原语工具替代一堆专用工具）。当用户说「Agent 老是选错工具」「怎么写工具描述」「我们有 17 个工具太乱了」「MCP 工具名怎么起」「错误信息怎么写 Agent 才会自己改」「要不要把这些工具合并」时使用。核心：工具是确定性系统与非确定性 Agent 之间的契约，描述必须单独就把契约说清；合并原则——人类工程师说不清该用哪个的，Agent 也说不清；描述回答四问（做什么/何时用/输入什么/返回什么）；动词-名词命名、跨工具一致；错误信息面向 Agent 恢复；响应提供 concise/detailed；MCP 用 ServerName:tool_name 全限定名。附最佳实践与架构减法案例参考。改编自 Agent Skills for Context Engineering 的 tool-design（MIT）。
author: Captain
version: 0.1.0
display_name: "面向 Agent 的工具设计"
display_name_en: "Tool Design for Agents (zh)"
description_zh: "把每个工具当作确定性系统与非确定性 Agent 之间的契约：描述单独说清做什么、何时用、输入、返回；合并重叠工具直到每个只有一个明确用途；一致的动词-名词命名；面向 Agent 恢复的错误信息；MCP 全限定名；必要时做架构减法。附审计清单。"
description_en: "Design each tool as a contract between deterministic code and a non-deterministic agent: the description alone states what/when/inputs/returns; consolidate overlapping tools until each has one purpose; consistent verb-noun naming; error messages built for agent recovery; fully-qualified MCP names; architectural reduction when warranted. With an audit checklist."
examples_zh:
  - "帮我重写这个工具的描述，Agent 总是用错"
  - "我们的 MCP 服务器有 17 个工具，Agent 一半时候选错，怎么合并"
  - "设计一下这个工具的错误返回，让 Agent 能自己修正参数"
examples_en:
  - "Rewrite this tool description, the agent keeps misusing it"
  - "Our MCP server has 17 tools and the agent picks wrong half the time"
  - "Design this tool's error payload so the agent can self-correct"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🔧" } }
---

# 面向 Agent 的工具设计

把每个工具设计成**确定性系统与非确定性 Agent 之间的契约**。与面向人的 API 不同，面向 Agent 的工具必须只靠描述就把契约说得毫无歧义：Agent 从描述推断意图、生成必须符合格式的调用。每一处歧义都是提示词工程救不回来的失败模式。

本技能的工作单元是**单个工具或一份工具目录**。项目形态、流水线架构、任务与模型的匹配归项目级技能；要不要引入子代理归多代理模式。本技能只管连接确定性代码与 Agent 的接口层。

## 什么时候用

- 写新的工具描述、schema 或响应格式
- 调试 Agent 选错工具或生成畸形调用
- 合并重叠的工具目录（经典的「我们有 17 个工具，Agent 一半时候选错」）
- 设计可让 Agent 自纠错的错误信息
- 跨目录统一工具与参数命名（MCP 命名空间、动词-名词）
- 按合并原则评估第三方工具该不该加

不用于：决定项目要不要用 LLM、流水线分几段；决定拆不拆子代理；在轨迹层面降低工具输出的 token 权重（观察遮蔽）。

## 核心概念

**合并原则**：人类工程师无法明确说出某情境该用哪个工具时，Agent 也做不到。缩减工具集直到每个工具只有一个无歧义的用途——Agent 靠比较描述选工具，任何重叠都引入选择错误。

**工具描述就是提示词工程。** 它不是给人看的文档，而是注入 Agent 上下文、直接引导推理的文本。写清做什么、何时用、返回什么，因为这三问正是 Agent 选工具时评估的东西。

## 要点

### 工具-Agent 接口

**工具即契约。** 人调 API 会读文档、懂惯例；Agent 只能从一段描述推断整个契约。放进格式示例、期望模式、显式约束，调用方需要知道的一样都别漏——Agent 调用前不能反问。

**命名空间。** 目录变大时按前缀分组：数据库操作走 `db_*`，网页交互走 `web_*`。没有命名空间，Agent 得在平铺列表里评估每一个，数量越多准确率越低。

### 合并原则

**单个综合工具**替代多个重叠的窄工具：不是分别实现 `list_users`、`list_events`、`create_event`，而是一个 `schedule_event` 内部完成找空闲和排期，免去 Agent 按正确顺序串调用的负担。合并之所以有效：每个工具都在争夺选择时的注意力、消耗上下文预算，重叠制造歧义。

**不该合并的情况**：行为根本不同、服务不同语境、必须能独立调用。过度合并制造另一种问题：一个工具参数太多、模式太多，Agent 难以正确参数化。

### 架构减法

把合并原则推到极致：移除大多数专用工具，换成原语级的通用能力。生产证据表明这可能胜过精巧的多工具架构。

**文件系统 Agent 模式。** 用一个命令执行工具提供直接的文件系统访问，替代为数据探索、schema 查找、查询校验各建一个的自定义工具。Agent 用 grep、cat、find、ls 探索系统。之所以行：文件系统是模型深度理解的成熟抽象；标准工具行为可预测；Agent 可以灵活串联原语而不是被限死在预定义流程里；文件里的好文档替代了摘要工具。

**什么时候减法胜出**：数据层文档完善、结构一致；模型推理能力足够；专用工具在限制而非赋能模型；维护脚手架的时间超过改进结果的时间。**什么时候别减**：底层数据混乱、文档差；领域需要模型缺乏的专门知识；安全约束必须限制 Agent 动作；操作确实受益于结构化流程。

**为未来的模型而建。** 设计能从模型进步中受益的最小架构，而不是把当前局限锁进去的复杂架构。问每个工具：它是在赋能新能力，还是在限制模型本可以自己完成的推理？作为「护栏」建的工具常随模型进步变成负债。案例见 [references/architectural_reduction.md](references/architectural_reduction.md)。

### 描述工程

每个描述回答四问：
1. **做什么**——精确陈述，避免「有助于」「可用于」这类空话。
2. **何时用**——直接触发（「用户询问价格」）和间接信号（「需要当前市场费率」）。
3. **接受什么输入**——每个参数的类型、约束、默认值、格式示例。
4. **返回什么**——输出格式、结构、成功示例、错误情况。

默认值反映常见用例：减少 Agent 指定参数的负担，防止漏参数出错。

### 响应格式、错误信息、schema

提供 **concise / detailed** 两种响应格式：concise 只返回关键字段，适合确认；detailed 返回完整对象，适合完整上下文驱动决策的场景。在描述里写明何时用哪种。

错误信息服务两类读者：调试的开发者和恢复的 Agent。对 Agent，每条错误必须**可执行**——说明哪里错、怎么改：可重试的给重试指引，输入错误给正确格式示例，缺字段的点名缺什么。只说「失败」等于零恢复信号。

统一 schema：工具名用动词-名词（`get_customer`、`create_order`）；参数名跨工具一致（永远 `customer_id`，不要一会 `id` 一会 `identifier`）；返回字段名一致。

### MCP 命名

MCP 环境一律用全限定名 `ServerName:tool_name`（如 `GitHub:create_issue`），否则多服务器并存时 Agent 可能找不到工具。所有工具引用都带服务器前缀。

### 用 Agent 优化工具

把观察到的工具失败喂回给一个 Agent：它在多样任务上尝试使用工具，收集失败模式和摩擦点，分析缺了什么信息、什么歧义导致误用，提出改进后的描述，再对同一组任务测试。形成「使用产生失败数据 → 数据改进描述 → 失败减少」的回路。

## 工具审计清单

每个工具加入 Agent 前过一遍：
1. **名字**：动词-名词；多领域目录加命名空间。
2. **描述**：说明做什么、何时用、返回什么。
3. **schema**：每个参数有类型、约束、默认值、示例值。
4. **返回形状**：成功与错误载荷都有文档、机器可读。
5. **恢复**：每个错误告诉 Agent 重试前该改什么。
6. **重叠**：没有别的工具有相同的激活场景。
7. **合并决策**：相邻的窄工具已合并，除非必须独立调用。
8. **token 影响**：大响应支持 concise 模式或文件引用模式。

## 示例

**设计良好：**
```python
def get_customer(customer_id: str, format: str = "concise"):
    """
    按 ID 取回客户信息。
    何时用：用户询问某客户详情；决策需要客户上下文；核验客户身份。
    参数：
        customer_id：格式 "CUST-######"（如 "CUST-000001"）
        format："concise" 关键字段，"detailed" 完整记录
    返回：含所请求字段的客户对象
    错误：
        NOT_FOUND：客户 ID 不存在
        INVALID_FORMAT：ID 必须匹配 CUST-######
    """
```

**设计糟糕：** `def search(query): """搜索数据库。"""` ——名字含糊（搜什么、为什么）；不知道哪个数据库、查询什么格式；不知道返回什么；没有使用语境；没有错误处理。后果：Agent 在该用更具体工具时调它、猜不出查询格式、解释不了结果、恢复不了失败。

## 准则

1. 描述回答做什么、何时用、返回什么
2. 用合并减少歧义
3. 提供响应格式选项
4. 错误信息面向 Agent 恢复
5. 建立并遵守一致的命名规范
6. 限制工具数量，用命名空间组织
7. 用真实的 Agent 交互测试工具设计
8. 基于观察到的失败模式迭代
9. 质疑每个工具是在赋能还是限制模型
10. 优先原语级通用工具而不是专用包装
11. 投资文档质量而不是工具的精巧
12. 建能从模型进步中受益的最小架构

## 坑

1. **含糊描述**：「在数据库里搜索客户信息」留下太多问题。写明数据库、查询格式、返回形状。
2. **神秘参数名**：`x`、`val`、`param1` 逼 Agent 猜。
3. **缺恢复指引**：「发生错误」没有恢复信号。每条错误都说明哪里错、下一步试什么。
4. **跨工具命名不一致**：`id` / `identifier` / `customer_id` 混用制造混乱。
5. **MCP 命名冲突**：两个服务器都暴露 `search`，Agent 无法区分。一律全限定名，新增提供方时审计冲突。
6. **描述腐烂**：API 演进后描述失真——参数增加、返回格式变化、错误码迁移。把描述当代码：版本化、API 变更时评审、对当前行为测试。
7. **过度合并**：一个工具承担太多流程，参数列表大到 Agent 选不对组合。超过 8–10 个参数或服务根本不同的用例就拆。
8. **参数爆炸**：太多可选参数压垮 Agent 的决策。给合理默认、把相关选项归成格式预设、把少用的参数移进 `options` 对象。
9. **缺错误上下文**：只说「输入无效」不说哪个输入、为什么、合法输入长什么样，Agent 无法自纠。每条错误都带无效值、期望格式和具体示例。

## 参考

- [references/best_practices.md](references/best_practices.md)：描述工程原则、命名规范、错误信息结构、响应格式模式、工具集合设计、测试与反模式、上线前清单。
- [references/architectural_reduction.md](references/architectural_reduction.md)：17 个专用工具 → 2 个原语工具的生产案例与对比数据、适用与不适用条件、设计原则。
- 同系列：上下文工程基础（context-fundamentals-zh）。

---
改编自 [Agent Skills for Context Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) 的 `tool-design`（MIT）。改动见 ATTRIBUTION.md。
