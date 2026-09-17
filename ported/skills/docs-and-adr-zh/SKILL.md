---
name: docs-and-adr-zh
description: 架构决策记录（ADR）、技术文档、README 结构、注释规范、API 文档。当用户说「这个技术选型要不要记下来」「写一份 ADR」「为什么当初选了 X 没人记得」「README 怎么写」「注释应该写什么」「接口文档怎么组织」「给 AI 用的项目规则文件怎么写」时使用。核心：记录决策而不只是代码——上下文、约束、被否决的备选；ADR 何时写、先匹配仓库已有约定、模板与生命周期；注释只写 why 不写 what；已知坑要写在代码旁；README 五段结构；Changelog；给 Agent 看的文档。改编自 addyosmani/agent-skills 的 documentation-and-adrs（MIT）。
author: Captain
version: 0.1.0
display_name: "文档与 ADR"
display_name_en: "Documentation & ADRs (zh)"
description_zh: "记录决策而不只是代码：ADR 何时写与模板、先匹配仓库已有约定、注释只写 why、已知坑写在代码旁、README 与 Changelog 结构、给 Agent 看的规则文件。"
description_en: "Document decisions, not just code: when to write an ADR and its template, match existing repo conventions first, comment the why, gotchas next to the code, README and changelog structure, rules files for agents."
examples_zh:
  - "我们选了 PostgreSQL 而不是 MongoDB，帮我写成 ADR"
  - "给这个项目写一个合格的 README"
  - "这段代码的注释太多了，哪些该删哪些该留"
examples_en:
  - "We chose PostgreSQL over MongoDB, write it up as an ADR"
  - "Write a proper README for this project"
  - "Too many comments here, which stay and which go"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "📝" } }
---

# 文档与 ADR

最有价值的文档写的是 **why**：上下文、约束、取舍、被否决的备选。代码只能说明 what。这些上下文是未来的人和 Agent 在这个仓库工作时最缺的东西。

## 什么时候用 / 不用

用：做重要架构决策、在几种方案间选择、增改公开 API、上线改变用户可见行为的功能、新人（或 Agent）入职、同一件事反复解释第三遍。
不用：给显而易见的代码写注释；重复代码已经说明的事；给一次性原型写文档。

## ADR（架构决策记录）

**何时写**：选框架/库/重大依赖；设计数据模型或 schema；选鉴权策略；选 API 架构（REST / GraphQL / RPC）；选构建、托管、基础设施；任何回头代价高的决策。
**先匹配仓库已有约定**：看现有 ADR、项目说明、ADR 工具配置（如 `.adr-dir`）。已有约定优先于本模板——目录与格式（`docs/adr/*.md`、MADR、adr-tools）、编号与命名（延续序列，不要从 001 重来）、章节标题（沿用项目的）。证据冲突就指出来，不要悄悄引入第二套。没有约定才用下面的默认。

默认存 `docs/decisions/`，顺序编号：

```
# ADR-001：主数据库选用 PostgreSQL
## 状态        已接受 | 被 ADR-XXX 取代 | 已废弃
## 日期
## 上下文      需求与约束（关系型数据、ACID、全文检索、小团队需要托管服务……）
## 决策        PostgreSQL + 某 ORM
## 备选方案    每个备选：优点 / 缺点 / 否决理由
## 后果        正面与负面都写：获得什么、需要团队学什么、托管在哪
```

生命周期：提议 → 已接受 → 被取代/已废弃。**不删旧 ADR**，它们是历史上下文；决策变了就写新 ADR 引用并取代旧的。

## 行内注释

- 只写 **why**：「限流用滑动窗口，在窗口边界重置而不是固定周期，防止边界突发」；不写 **what**：「计数器加一」。
- 不给自解释的代码加注释；不留"以后再加错误处理"的 TODO（现在就加）；不留注释掉的代码（删，git 有历史）。
- **已知坑写在代码旁**：「必须在首次渲染前调用，否则 SSR 期间主题上下文不可用会闪烁；设计理由见 ADR-003」。

## API 文档

TypeScript 优先用类型 + 文档注释：参数、返回、抛出的错误类型、示例。REST 用 OpenAPI 描述请求体、响应码与 schema。类型与文档随实现一起提交。

## README 五段

一句话说明项目做什么 → 快速开始（克隆、安装、复制环境变量、启动）→ 命令表（dev / test / build / lint）→ 架构概览并链接 ADR → 贡献方式。

## Changelog

按版本与日期分组：新增 / 修复 / 变更，每条带工单号。本系列的「Changelog 生成器」可从 git 提交生成草稿。

## 给 Agent 看的文档

- 项目规则文件（CLAUDE.md / AGENTS.md 等）：写下约定，Agent 才会遵守——没写下来的等于不存在。
- Spec 保持更新，Agent 才做对的东西。
- ADR 让 Agent 理解过去为什么这么定，避免重新决策。
- 行内坑位注释防止 Agent 踩已知的坑。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "代码即文档" | 代码说 what，不说 why、不说否决了什么、不说约束 |
| "API 稳定了再写文档" | 写文档会让 API 更快稳定；文档是设计的第一个测试 |
| "没人看文档" | Agent 看；未来的工程师看；三个月后的你看 |
| "ADR 是负担" | 10 分钟的 ADR 省掉半年后 2 小时的重复争论 |
| "注释会过期" | 关于 why 的注释很稳定；关于 what 的才过期，所以只写前者 |

## 红灯

架构决策没有书面理由；公开 API 无文档无类型；README 不说怎么跑；注释掉的代码；躺了几周的 TODO；有重大架构选择的项目没有 ADR；文档复述代码而不是解释意图。

## 验收

- [ ] 重大架构决策都有 ADR 　- [ ] README 覆盖快速开始、命令、架构概览
- [ ] API 有参数与返回类型说明 　- [ ] 已知坑写在代码旁 　- [ ] 没有注释掉的代码 　- [ ] Agent 规则文件是最新的

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `documentation-and-adrs`（MIT）。改动见 ATTRIBUTION.md。
