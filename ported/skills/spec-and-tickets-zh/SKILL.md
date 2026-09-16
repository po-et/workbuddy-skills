---
name: spec-and-tickets-zh
description: 把讨论或需求写成技术 Spec，再拆成可独立交付的任务/工单。当用户说「把我们刚才聊的整理成 spec」「写需求文档」「拆任务」「拆成 story」「怎么排开发顺序」「生成 issue 列表」「拆分成可并行的子任务」「垂直切片」「这个需求怎么分给三个人」时使用。Spec 模板：问题陈述、方案、用户故事、实现决策、测试决策、范围外；拆分规则：每张工单是穿透所有层的"曳光弹"垂直切片、可独立演示、能塞进一个上下文窗口、声明阻塞关系；大范围机械重构走 expand–contract。输出本地 Markdown 工单文件与可导入 GitHub/Jira 的 JSON。改编自 Matt Pocock 的 to-spec 与 to-tickets（MIT），中文化并合并为一条流程。
author: Captain
version: 0.1.0
display_name: "需求→Spec→任务拆解"
display_name_en: "Spec and Tickets (zh)"
description_zh: "把讨论整理成 Spec（问题/方案/用户故事/实现与测试决策/范围外），再拆成带阻塞关系的垂直切片工单，输出 Markdown 与可导入 JSON。"
description_en: "Turn a discussion into a spec (problem, solution, user stories, implementation and testing decisions, out of scope), then split it into vertical-slice tickets with blocking edges, as Markdown and importable JSON."
examples_zh:
  - "把我们刚才讨论的登录改造整理成 spec"
  - "把这个 spec 拆成可以并行开发的工单，标出依赖"
  - "这个需求怎么拆才能每张任务都能单独演示"
examples_en:
  - "Turn our login redesign discussion into a spec"
  - "Split this spec into parallelisable tickets with dependencies"
  - "How do I slice this so every ticket is demoable on its own"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# 需求 → Spec → 任务拆解

两段一条龙：先把已经讨论清楚的东西**综合**成 Spec（不再盘问——要盘问用「需求盘问官」），再把 Spec **拆**成一组能独立交付、声明了阻塞关系的工单。

## 第一段：写 Spec

### 原则

- **综合，不采访。** 只写对话与代码里已经明确的内容；没定的写进「开放问题」而不是替用户决定。
- **用项目的词汇。** 先看仓库有没有术语表 / `CONTEXT.md` / ADR，用它们的叫法。
- **在最高的缝测试。** 先确定在哪一层验收这个功能（接口、CLI、UI），缝越少越好，理想是一条；新缝要用户点头。
- **不写文件路径与代码片段。** 它们过期最快。例外：原型产出的状态机、schema、类型形状比文字更精确，可以内联并注明来自原型。

### Spec 模板

```
## 问题陈述          用户视角的问题
## 方案              用户视角的解决方式
## 用户故事          长、编号：作为 <角色>，我想要 <功能>，以便 <收益>（尽量穷尽）
## 实现决策          涉及模块、接口变化、架构决策、schema/API 契约、关键交互
## 测试决策          什么算好测试（只测外部行为）、测哪些模块、仓库里的先例
## 范围外            明确不做什么
## 开放问题          还没定的
## 备注
```

写完落盘到 `docs/specs/<feature>.md`（或用户指定），再进入第二段。

## 第二段：拆工单

### 拆分规则（曳光弹垂直切片）

- 每张工单**穿透所有层**（schema → API → UI → 测试）打出一条窄而完整的路径；不是"先把数据库都建好"那种水平切片。
- 做完能**单独演示或验证**。
- 大小能**塞进一个全新的上下文窗口**完成。
- 需要"预重构"（先让改动变容易）的，单独一张放最前面。
- 每张声明 **阻塞它的工单**；没有阻塞的可以立刻开始。任何时刻"阻塞项全部完成"的工单集合就是可并行的前沿。

**例外：大范围机械重构**（改列名、改共享类型）一改就炸几千个调用点，切不出绿的垂直切片。走 **expand–contract**：先 expand（新旧并存，什么都不坏）→ 分批 migrate（按包/目录，每批一张工单，阻塞于 expand，批批 CI 绿）→ contract（删旧，阻塞于所有 migrate）。批次都绿不了时允许共用一条集成分支，只在最终"集成验证"工单承诺绿。

### 流程

1. 读 Spec 与代码（术语、ADR、可预重构点）。
2. 起草切片列表，每张：标题 / 阻塞于 / 交付什么（用户视角的端到端行为）。
3. **和用户对一遍**：粒度对不对、阻塞关系是不是真的、要不要合并或再拆。迭代到用户认可。
4. 落盘：`.scratch/<feature>/issues/<NN>-<slug>.md`，按依赖顺序从 01 编号，一张一文件；同时输出 `tickets.json` 便于导入工单系统。

### 工单模板（Markdown）

```
# <NN>: <标题>
**要做出什么：** 用户视角的端到端行为，不是分层实现清单
**阻塞于：** <编号/标题> 或 无（可立即开始）
**状态：** ready
- [ ] 验收标准 1
- [ ] 验收标准 2
```

### 导入 JSON

```json
[{"id": "01", "title": "…", "blocked_by": [], "delivers": "…", "acceptance": ["…"], "labels": ["ready-for-agent"]}]
```

GitHub 用 `gh issue create` 按依赖顺序建，再用 sub-issue / "blocked by" 关系；Jira 用 issue link "is blocked by"。不要关闭或修改父需求。

## 常见问题

**用户只想要 Spec 不要拆？** 第一段结束即可交付。
**已经有 Spec？** 直接第二段，但先按模板补齐缺的小节（尤其范围外与测试决策）。
**切片太多？** 合并到 5–9 张是常见舒适区；再多说明这是 epic，先拆成里程碑。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `to-spec` 与 `to-tickets`（MIT）。改动见 ATTRIBUTION.md。
