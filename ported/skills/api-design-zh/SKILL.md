---
name: api-design-zh
description: API 设计、接口设计、REST 接口规范、模块边界契约、幂等键实现。当用户说「帮我设计这组接口」「REST 怎么命名」「错误码怎么统一」「分页怎么做」「PATCH 还是 PUT」「接口怎么向后兼容」「幂等键怎么实现才不重复扣款」「第三方返回要不要校验」时使用。原则：Hyrum 定律（一切可观察行为都会被依赖）、单版本规则、契约先行、统一错误语义、只在边界校验、只加不改、可预测命名、真正兑现幂等键（意图派生的键、原子占位、载荷校验、在途重复的处理、三态结果、保留期覆盖最长重试链）；附 REST 资源/分页/过滤/PATCH 模式与 TS 可辨识联合、输入输出分离、品牌类型。改编自 addyosmani/agent-skills 的 api-and-interface-design（MIT）。
author: Captain
version: 0.1.0
display_name: "API 与接口设计"
display_name_en: "API & Interface Design (zh)"
description_zh: "设计难以误用的稳定接口：Hyrum 定律、契约先行、统一错误、边界校验、只加不改、可预测命名，以及幂等键的完整实现要点；含 REST 与 TypeScript 模式。"
description_en: "Design stable interfaces that are hard to misuse: Hyrum's law, contract first, consistent errors, boundary validation, additive change, predictable naming, and a complete idempotency-key implementation; REST and TypeScript patterns."
examples_zh:
  - "给任务系统设计一套 REST 接口，含分页和错误格式"
  - "支付接口的幂等键应该怎么生成和存储"
  - "这个接口要加字段，怎么改才不破坏老客户端"
examples_en:
  - "Design REST endpoints for a task system with pagination and error format"
  - "How should a payment endpoint derive and store its idempotency key"
  - "Add a field to this endpoint without breaking old clients"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🔌" } }
---

# API 与接口设计

好接口让正确的事容易、错误的事困难。适用于 REST、GraphQL、模块边界、组件 props——任何一段代码和另一段代码说话的地方。

## 两条定律

- **Hyrum 定律**：用户够多时，系统的一切可观察行为都会被人依赖，不管契约怎么承诺。所以：对暴露什么要有意识；别泄漏实现细节；设计时就规划废弃（见「下线与迁移」）；测试不够——契约测试再完美，改动仍可能弄坏依赖未文档化行为的真实用户。
- **单版本规则**：别逼消费者在同一依赖的多个版本间选择（菱形依赖）。为"任何时刻只有一个版本"设计：扩展，不分叉。

## 六条原则

1. **契约先行。** 先定义接口再实现；每个方法一句话说明语义（创建并返回含服务端生成字段的对象；分页返回；找不到抛 NotFound；部分更新只改传入字段；删除幂等）。
2. **统一错误语义。** 选一种错误策略全站用：结构化错误体 `{error: {code, message, details?}}`；状态码约定 400 无效输入 / 401 未认证 / 403 无权限 / 404 不存在 / 409 冲突 / 422 校验失败 / 500 服务端错误（不暴露内部细节）。有的抛异常、有的返回 null、有的返回 `{error}`，消费者就无法预测。
3. **只在边界校验。** 外部输入进入的地方校验：路由处理器、表单提交、第三方响应解析（**第三方返回一律视为不可信**，先校验形状与内容再用于逻辑或渲染）、环境变量加载。内部函数之间共享类型契约，不再校验；自己数据库出来的数据不再校验。
4. **只加不改。** 新字段一律可选；不改已有字段类型，不删字段。
5. **可预测命名。** REST 路径用复数名词无动词；查询参数与响应字段 camelCase；布尔用 is/has/can 前缀；枚举 UPPER_SNAKE。团队已有约定则跟团队。
6. **真正兑现幂等键。** 接受 `Idempotency-Key` 只是契约，兑现它才是实现——接受了却处理马虎，比没有更糟，因为客户端会以为重试是安全的。

## 幂等键的实现要点

- **键从意图派生，不从尝试派生。** 同一意图的多次重试键相同，不同意图键不同。`randomUUID()` 每次尝试一个新键 ✗；`userId:amount` 会把两笔合法的相同金额合并 ✗；带时间戳的键就是戴帽子的 UUID ✗；客户端生成一次、重试复用 ✓；`charge:v1:<orderId>` 从不可变标识派生 ✓。键来自客户端或触发事件，不来自做重试的那一层。
- **原子占位。** 先查后写是竞态：两个并发重试都读到"没见过"，都扣款。用唯一约束选出赢家：插入 `{key, state: in_progress, requestHash}`，唯一冲突则重放或拒绝；成功后更新为 succeeded 并存响应。不能在一次操作里保证唯一性的存储撑不起幂等。
- **校验载荷。** 同一个键带不同请求体是客户端 bug，必须大声失败（422），不能把第一个响应发给第二个请求。
- **决定在途重复怎么办。** 第一个还在跑第二个就到了——重试风暴下的常态。拒绝 409（最简单最安全）/ 有界等待 / 返回 202 + 状态 URL（长任务）。绝不因为第一个"看起来卡住"就放第二个过去。
- **结果有三态：成功、失败、未知。** 超时不告诉你效果是否发生。调用前先记录意图，这样调用与响应之间崩溃也留下证据让后续处理，而不是静默重试一次扣款。
- **保留期按最长重试链定。** 键必须活过每一条可能重投同一意图的路径：一周后重放的死信队列、服务商争议窗口。24 小时 TTL 配 7 天死信队列就是等着重复。

## REST 模式

资源：`GET/POST /api/tasks`、`GET/PATCH/DELETE /api/tasks/:id`、子资源 `/api/tasks/:id/comments`。
分页：请求 `?page=1&pageSize=20&sortBy=createdAt&sortOrder=desc`，响应 `{data, pagination: {page, pageSize, totalItems, totalPages}}`；列表接口一开始就分页。
过滤：查询参数 `?status=in_progress&assignee=u1&createdAfter=2026-01-01`。
部分更新：PATCH 只改传入字段。

## TypeScript 模式

可辨识联合表达状态变体（每个变体自带该状态才有的字段，消费者获得类型收窄）；输入类型与输出类型分离（输出含服务端生成字段）；ID 用品牌类型防止把 UserId 传给要 TaskId 的函数。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "文档以后再写" | 类型就是文档，先定义类型 |
| "现在不需要分页" | 有人有 100 条时就需要了；一开始就加 |
| "PATCH 麻烦，用 PUT" | PUT 每次要传整个对象；客户端要的是 PATCH |
| "需要时再做版本" | 无版本的破坏性变更会弄坏消费者；从一开始为扩展设计 |
| "没人用那个未文档化行为" | Hyrum 定律：可观察就有人依赖 |
| "维护两个版本就行" | 多版本让维护成本相乘并制造菱形依赖 |
| "内部接口不需要契约" | 内部消费者也是消费者；契约防耦合、让并行开发成为可能 |
| "接受了 Idempotency-Key 就够了" | 头是契约，把键与结果存起来才是实现 |
| "我们的队列保证恰好一次" | 跨消费者崩溃没有队列能保证；按至少一次 + 幂等处理设计 |
| "重复请求很少见" | 它们是相关的：依赖降级时重试激增，正是重复最可能、最贵的时候 |

## 红灯

同一端点按条件返回不同形状；错误格式不一致；校验散落在内部代码；改已有字段类型或删字段；列表无分页；REST 路径带动词；第三方响应不校验直接用；幂等键先 SELECT 再 INSERT；键由 UUID/时间戳派生；同键不同体静默返回首次响应；键保留期短于最长重投路径。

## 验收

- [ ] 每个端点有类型化的输入输出 schema 　- [ ] 错误响应单一格式 　- [ ] 只在边界校验
- [ ] 列表接口分页 　- [ ] 新字段可选、向后兼容 　- [ ] 命名一致 　- [ ] 类型/文档随实现一起提交
- [ ] 改状态的端点要么兑现幂等键，要么文档写明不可重试
- [ ] 键靠唯一约束原子占位 　- [ ] 同键不同体大声失败 　- [ ] 在途重复的响应是有意选择 　- [ ] 保留期覆盖最长重试路径

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `api-and-interface-design`（MIT）。改动见 ATTRIBUTION.md。
