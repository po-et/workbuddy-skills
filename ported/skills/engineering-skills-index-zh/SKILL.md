---
name: engineering-skills-index-zh
description: 工程实践技能系列的总入口与路由：按研发阶段选技能——需求访谈、创意打磨、规格驱动、约束驱动、任务拆解、增量实现、源驱动、质疑驱动、上下文工程、前端工程、API 设计、测试驱动、浏览器测试、系统化排错、五轴评审、代码化简、安全加固、性能优化、Git 工作流、CI/CD、下线迁移、文档 ADR、可观测性、上线发布。当用户说「我该用哪个技能」「按流程走一遍这个功能」「从需求到上线该怎么做」「有哪些工程实践技能」，或任务刚到手需要判断处于哪个阶段时使用。附六条始终生效的操作行为：亮出假设、主动管理困惑、有理由就反对、强制简单、范围纪律、验证不假设。也覆盖「按什么顺序用哪些技能」「有哪些工程实践技能可以装」「该走哪几步」这类说法。改编自 addyosmani/agent-skills 的 using-agent-skills（MIT），指向本系列的中文版技能。
author: Captain
version: 0.1.1
display_name: "工程实践技能系列·总入口"
display_name_en: "Engineering Skills Index (zh)"
description_zh: "25 个工程实践技能（Addy Osmani 系列中文版）的路由表：任务到手先判断阶段→选技能；六条始终生效的行为：亮假设、管困惑、敢反对、要简单、守范围、重验证。"
description_en: "Router for the 25-skill engineering series (Chinese edition of Addy Osmani's agent-skills): identify the phase, pick the skill; six always-on behaviours: surface assumptions, manage confusion, push back, enforce simplicity, keep scope, verify."
tags:
  - "技能路由"
  - "工程实践"
  - "研发流程"
  - "index"
  - "SDLC"
  - "技能总入口"
examples_zh:
  - "我要做一个新功能，从头到尾该按什么顺序用哪些技能"
  - "有哪些工程实践技能可以装"
  - "这个 bug 修复该走哪几步"
examples_en:
  - "New feature end to end, which skills in which order"
  - "What engineering-practice skills are available"
  - "Which steps for this bug fix"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🧭" } }
---

# 工程实践技能系列 · 总入口

这个系列把资深工程师在各研发阶段遵循的流程写成可执行的技能。任务到手先判断阶段，再用对应技能（SkillHub 上搜 slug 安装）。

## 任务 → 技能

| 情况 | 技能（slug） |
|---|---|
| 还不知道自己要什么 | 需求访谈 `interview-me-zh`（或按设计树追问：需求盘问官 `grill-me-zh`） |
| 有粗想法要变体与评估 | 创意打磨 `idea-refine-zh` |
| 新项目/功能/大改 | 规格驱动 `spec-driven-zh`（讨论→Spec→工单：`spec-and-tickets-zh`） |
| 没写下来的质量标准 | 约束驱动 `constraints-md-zh` |
| 有 spec 要拆任务 | 实施计划与任务拆解 `planning-tasks-zh` |
| 正在写代码 | 增量实现 `incremental-implementation-zh`；UI → 前端工程 `frontend-ui-zh`；接口 → API 设计 `api-design-zh`；需要更好的上下文 → 上下文工程 `context-engineering-zh`；要文档背书 → 源驱动 `source-driven-zh`；高风险/陌生代码 → 质疑驱动 `doubt-driven-zh` |
| 写/跑测试 | 测试驱动 `tdd-zh`；浏览器 → DevTools 测试 `browser-testing-devtools-zh` |
| 出问题了 | 系统化排错 `debug-triage-zh`；疑难 → Bug 诊断法 `diagnosing-bugs-zh` |
| 评审代码 | 五轴评审 `code-review-five-axis-zh` / 双轴评审 `code-review-zh`；太复杂 → 代码化简 `code-simplification-zh`；安全 → 安全加固 `security-hardening-zh`；性能 → 性能优化 `performance-optimization-zh` |
| 提交/分支/发版 | Git 工作流 `git-workflow-zh`；提交信息 `commit-message-cc`；Changelog `changelog-keep` |
| CI/CD | `ci-cd-zh`；配置安全审查 `ci-config-review` |
| 下线/迁移 | 下线与迁移 `deprecation-migration-zh` |
| 文档/ADR | `docs-and-adr-zh` |
| 日志/指标/告警 | 可观测性 `observability-zh` |
| 部署上线 | 上线发布 `shipping-launch-zh`；本次变更清单 `release-checklist-git` |

## 六条始终生效的行为
1. **亮出假设**：做任何非平凡的事之前列出"我正在假设：1… 2… 3… → 现在纠正我，否则按此进行"。默默补全模糊需求是最常见的失败。
2. **主动管理困惑**：遇到不一致、冲突、不清楚——**停**，说出具体困惑，摆出取舍或问题，等解决再继续。不要默默选一种解释。
3. **有理由就反对**：不当好好先生。指出问题、量化代价（"多 ~200ms"而不是"可能慢"）、给替代；对方知情后仍坚持则接受。
4. **强制简单**：完成前问——能更少行吗；抽象值回复杂度吗；资深工程师会不会说"你直接……不就行了"。1000 行能用 100 行做就是失败。
5. **范围纪律**：只碰被要求的。不删不懂的注释、不清理无关代码、不顺手重构相邻系统、不删看似未用的代码、不加规格外的功能。
6. **验证不假设**：每个技能都有验证步骤，没过就不算完成。"看起来对"永远不够，要证据（测试、构建输出、运行时数据）。项目级的"完成定义"（测试过、无回归、运行时验证、文档更新）叠加在每个任务的验收标准之上。

## 十种看似高效实则埋雷的错误
错误假设不核实；迷路了还往前冲；发现不一致不说；非显然决策不摆取舍；对有明显问题的方案说"好的"；把代码和 API 做复杂；改动与任务无关的代码或注释；删掉没完全理解的东西；"显然该做什么"所以不写 spec；"看起来对"所以跳过验证。

## 自检口诀
```
拿到任务：1) 判断处于哪个阶段 → 2) 查表选技能（slug）→ 3) 按技能流程执行、不跳验证 → 4) 有假设先亮出来
```

## 技能规则
开工前先查有没有适用技能；技能是工作流不是建议——按顺序做、不跳验证；多个技能可串联；拿不准就从 spec 开始。

## 一个功能的典型顺序
需求访谈 → 创意打磨 → 规格驱动 → 任务拆解 → 上下文工程 → 源驱动 → 增量实现（可观测性与之并行，不是之后）→ 质疑驱动 → 测试驱动 → 五轴评审 → 代码化简 → Git 工作流 → 文档 ADR → 下线迁移（如需）→ 上线发布。修 bug 可能只需：系统化排错 → 测试驱动 → 评审。

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `using-agent-skills`（MIT）。改动见 ATTRIBUTION.md。系列全部技能开源：https://github.com/po-et/workbuddy-skills
