---
name: planning-tasks-zh
description: 实施计划与任务拆解、依赖图、垂直切片排序、任务大小估算、检查点。当用户说「有 spec 了帮我拆成任务」「这个任务太大不知道从哪开始」「排一下实现顺序」「哪些能并行做」「写个实施计划」「估一下工作量」时使用。流程：只读的计划模式（不写代码）→ 画依赖图 → 垂直切片而非分层 → 每个任务写描述/验收标准/验证步骤/依赖/涉及文件/大小 → 排序并每 2–3 个任务设检查点。任务大小 XS–L 表，XL 必拆；输出 tasks/plan.md 与 tasks/todo.md（或项目指定的工单系统）；绝不覆盖仍有未完成项的旧计划。改编自 addyosmani/agent-skills 的 planning-and-task-breakdown（MIT）。
author: Captain
version: 0.1.0
display_name: "实施计划与任务拆解"
display_name_en: "Planning & Task Breakdown (zh)"
description_zh: "从 spec 到可执行任务：只读计划模式、依赖图、垂直切片、每个任务带验收与验证步骤、大小 XS–L、检查点；写入 tasks/plan.md 与 todo.md，不覆盖未完成的旧计划。"
description_en: "From spec to executable tasks: read-only plan mode, dependency graph, vertical slices, acceptance and verification per task, XS–L sizing, checkpoints; written to tasks/plan.md and todo.md without clobbering an unfinished plan."
examples_zh:
  - "把这份 spec 拆成可以逐个实现的任务并排序"
  - "这个功能哪些部分能并行给两个人做"
  - "写一份带检查点的实施计划"
examples_en:
  - "Break this spec into ordered implementable tasks"
  - "Which parts of this feature can two people do in parallel"
  - "Write an implementation plan with checkpoints"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🗺️" } }
---

# 实施计划与任务拆解

把工作拆成**小的、可验证、带明确验收标准**的任务。拆得好，Agent 稳定交付；拆不好，一团乱麻。每个任务要能在一次专注会话里实现、测试、验证。
（与本系列「需求→Spec→任务拆解」的区别：那个从讨论产出 Spec 再拆工单；这个假设 spec 已有，专注计划文档、依赖、大小与检查点。）

## 流程

### 第 1 步：进入计划模式（只读）
读 spec 与相关代码；识别现有模式与约定；画组件依赖；记录风险与未知。**计划期间不写代码。** 产出是 `tasks/plan.md` 与任务清单。

### 第 2 步：画依赖图
schema → 模型/类型 → 接口 → 前端客户端 → UI；校验逻辑、种子数据/迁移挂在相应节点。实现顺序自底向上。

### 第 3 步：垂直切片
不是"先建全部表、再写全部接口、再做全部 UI"，而是"用户能注册（表 + 接口 + UI）→ 能登录 → 能创建任务 → 能看列表"。每片交付可工作可测试的功能。

### 第 4 步：写任务
```
## 任务 N：<标题>
描述：一段话说明做成什么
验收标准：- [ ] 可测试的条件 ×2–3
验证：- [ ] 测试通过（仓库的定向测试命令）- [ ] 构建成功 - [ ] 手工检查什么
依赖：任务号或"无"
可能涉及文件：…
大小：S / M / L
```

### 第 5 步：排序与检查点
依赖先满足；每个任务结束系统可工作；每 2–3 个任务一个检查点（测试全过、构建无错、核心流程端到端、请人评审再继续）；高风险任务靠前（早失败）。

## 任务大小

| 大小 | 文件 | 范围 |
|---|---|---|
| XS | 1 | 单个函数或配置 |
| S | 1–2 | 一个组件或端点 |
| M | 3–5 | 一个功能切片 |
| L | 5–8 | 多组件功能 |
| XL | 8+ | **太大，继续拆** |

再拆的信号：超过一次专注会话（约 2 小时 Agent 工作）；验收标准写不进 3 条以内；跨两个独立子系统；标题里出现"和"。

## 输出文件

- `tasks/plan.md`：计划文档（概述、架构决策、分阶段任务清单与检查点、风险与缓解、开放问题）。
- 任务清单目标：默认 `tasks/todo.md`；项目规则或用户指定工单系统（GitHub Issues / Jira / Linear）时，每任务一个工单，依赖用工单系统的关联，检查点也建工单或写进计划文档，并在 plan.md 注明"任务在 X 追踪"。
- **绝不覆盖仍有未完成项的旧计划**：同一项工作在修订 → 原地更新；不同工作 → **停下来问**，旧任务可能正在另一个会话里做。外部工单同理，不批量关闭别人的。

## 并行

可并行：独立功能切片、已实现功能的测试、文档。必须串行：数据库迁移、共享状态变更、依赖链。需协调：共享接口契约的功能——先定契约再并行。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "边做边想" | 那是返工的来源；10 分钟计划省几小时 |
| "任务很明显" | 写下来照样能暴露隐藏依赖与遗漏边界 |
| "计划是负担" | 计划就是任务；没计划的实现只是打字 |
| "我脑子里记得住" | 上下文有限；写下来的计划能跨会话与压缩 |
| "旧计划过时了，直接覆盖" | 未完成项可能正在别处进行；覆盖会毁掉只存在于那里的状态 |

## 红灯

没有书面任务清单就开始实现；覆盖别的工作的未完成计划；项目指定了工单系统却写 todo.md（或两边都写）；任务只写"实现功能"没有验收标准；没有验证步骤；全是 XL；没有检查点；没考虑依赖顺序。

## 验收

- [ ] 每个任务有验收标准与验证步骤　- [ ] 依赖已识别并排序　- [ ] 任务记录在任务清单目标
- [ ] 没有未经确认覆盖旧计划　- [ ] 单任务不超过 ~5 个文件　- [ ] 阶段间有检查点　- [ ] 人已评审批准计划

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `planning-and-task-breakdown`（MIT）。改动见 ATTRIBUTION.md。
