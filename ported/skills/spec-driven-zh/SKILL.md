---
name: spec-driven-zh
description: 规格驱动开发、先写 spec 再写代码、PRD 与需求文档、能力地图拆分。当用户说「新项目/新功能先写个 spec」「需求太模糊帮我写成文档」「写 PRD」「这个需求包了好几块怎么拆」「把'做快点'变成可验收的指标」时使用。门控流程：阶段 0 范围检查（一个需求捆了多个可独立测试的能力时先出能力地图：模块 id、依赖方向、构建顺序）→ 阶段 1 Specify（先亮出假设；六大要素：目标、命令、项目结构、代码风格、测试策略、边界三层；模板；把指令改写成成功标准）→ 阶段 2 Plan → 阶段 3 Tasks → 阶段 4 Implement，每阶段人审通过才进下一阶段；spec 是活文档。改编自 addyosmani/agent-skills 的 spec-driven-development（MIT）。
author: Captain
version: 0.1.0
display_name: "规格驱动开发（先 Spec 后代码）"
display_name_en: "Spec-Driven Development (zh)"
description_zh: "写代码前先写 spec：范围检查与能力地图、先亮假设、六要素模板（目标/命令/结构/风格/测试/边界）、把模糊需求改写成成功标准，Specify→Plan→Tasks→Implement 逐门人审。"
description_en: "Spec before code: scope check with a capability map, surface assumptions, a six-area template (objective/commands/structure/style/testing/boundaries), reframe vague asks as success criteria, human-gated Specify→Plan→Tasks→Implement."
examples_zh:
  - "给这个新功能写一份 spec，包含验收标准和边界"
  - "这个需求包了身份、计费、通知三块，先帮我出能力地图"
  - "把'让后台更快'改写成可验收的指标"
examples_en:
  - "Write a spec for this feature with acceptance criteria and boundaries"
  - "This request bundles identity, billing and notifications, give me a capability map first"
  - "Turn 'make the admin faster' into testable success criteria"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "📋" } }
---

# 规格驱动开发（先 Spec 后代码）

spec 是你和工程师之间的**共享事实来源**：做什么、为什么、怎么算做完。没有 spec 的代码是猜。
用于：新项目/新功能；需求模糊；改动跨多个模块；将要做架构决策；实现超过 30 分钟。不用于：单行修复、错别字、需求无歧义且自包含的改动。

## 门控流程
Specify → Plan → Tasks → Implement，每一步**人审通过**才进下一步。前面还有个只在需要时激活的阶段 0。

### 阶段 0：范围检查（只处理例外）
一个需求捆了多个**可独立测试的能力**时先拆：需求点名了各有消费者或数据的不同能力（身份、计费、通知、报表）；验收标准聚成可分别交付验证的几组；砍掉一个能力不用重写其他的需求。
**先出能力地图再写任何 spec**——小而可审：模块表（id / 职责 / 依赖）+ 构建顺序。模块 id 用 kebab-case、定了不改；依赖单向无环（互相依赖就是一个模块）；接口写在提供方模块的 spec 里。地图也要人审。然后按依赖顺序对每个模块跑 Specify→Plan→Tasks→Implement，各自一份 `SPEC-<id>.md`，地图是索引。

### 阶段 1：Specify
先亮假设：
```
我正在假设：1. 这是 Web 应用不是原生 2. 会话 cookie 不是 JWT 3. 数据库是 PostgreSQL 4. 只支持现代浏览器
→ 现在纠正我，否则按此进行。
```
不要默默补全模糊需求——spec 的全部意义就是在写代码前暴露误解。
六大要素：**目标**（做什么、为什么、给谁、成功是什么）；**命令**（完整可执行的构建/测试/lint/dev 命令，不只是工具名）；**项目结构**（源码、测试、文档在哪）；**代码风格**（一段真实代码胜过三段描述）；**测试策略**（框架、位置、覆盖预期、各层测什么）；**边界三层**（总是做：提交前跑测试、遵守命名、校验输入；先问：改 schema、加依赖、改 CI；绝不：提交密钥、改 vendor、未经批准删失败测试）。
模板小节：目标 / 技术栈 / 命令 / 项目结构 / 代码风格 / 测试策略 / 边界 / 成功标准 / 开放问题。项目已用 OpenSpec 等规格工具就沿用其格式，本技能只负责澄清、内容与审批门。
**把指令改写成成功标准**："让仪表盘更快" → LCP < 2.5s（4G）、首屏数据 < 500ms、CLS < 0.1 → "这些目标对吗？"

### 阶段 2：Plan
识别组件与依赖、实现顺序、风险与缓解、可并行与必须串行、阶段间验证检查点。机制细节以「实施计划与任务拆解」为准，产出 `tasks/plan.md` 与任务清单。计划要让人能说"对，就这么做"或"改 X"。

### 阶段 3：Tasks
每个任务一次会话可完成、有验收标准、有验证步骤（测试/构建/手工）、按依赖排序、不超过 ~5 个文件。

### 阶段 4：Implement
按「增量实现」与「测试驱动」逐任务做；用「上下文工程」只加载相关 spec 段落而不是整份 spec。

## 让 spec 活着
决策变了先改 spec 再实现；范围变了同步；spec 进版本控制；PR 引用它实现的 spec 小节。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "太简单不需要 spec" | 简单任务不需要长 spec，但需要验收标准；两行也行 |
| "写完代码再写 spec" | 那是文档不是规格；价值在写代码前逼出清晰 |
| "spec 拖慢我们" | 15 分钟的 spec 省几小时返工 |
| "需求反正会变" | 所以它是活文档；过时的 spec 也强过没有 |
| "用户知道自己要什么" | 清晰的请求也有隐含假设，spec 把它们暴露出来 |
| "一个大功能，拆是负担" | 验收标准能聚成独立组就该出十行地图，否则每个下游任务都得推理整份契约 |
| "计划阶段再拆" | 计划在 spec 内切任务；模块边界和依赖方向要在写 spec 前定 |

## 红灯
没有书面需求就写代码；问"要不要直接开始做"却没定义"做完"；实现任何 spec 或任务里没有的功能；架构决策没记录；"显然该做什么"所以跳过 spec；一份 spec 横跨多个可独立测试的能力；模块边界在实现中被隐式决定。

## 验收
- [ ] spec 覆盖六大要素　- [ ] 人已审批 spec　- [ ] 成功标准具体可测　- [ ] 边界三层已定义
- [ ] spec 存在仓库里　- [ ] 多能力需求先批了能力地图　- [ ] 每份模块 spec 对应地图里的 id

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `spec-driven-development`（MIT）。改动见 ATTRIBUTION.md。
