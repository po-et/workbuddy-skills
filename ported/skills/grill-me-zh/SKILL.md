---
name: grill-me-zh
description: 需求盘问、方案拷问、动手前把想法问清楚。当用户说「盘问我」「拷问我这个方案」「grill me」「帮我把需求问清楚再写代码」「先别写，先跟我确认设计」「压力测试一下我的想法」「我这个决策有没有漏洞」，或者在写代码、写方案、做架构决策之前需要把所有隐含假设逐一确认时使用。按"设计树"分轮提问：每轮只问当前能问的问题，每题附推荐答案，能自己查的事实绝不问用户；所有分支问完、没有任何默默假设之后才动手。改编自 Matt Pocock 的 grilling（MIT），中文化并增加决策落盘与积分控制。
author: Captain
version: 0.1.0
display_name: "需求盘问官"
display_name_en: "Grill Me (zh)"
description_zh: "动手前按设计树分轮追问，每题附推荐答案，事实自己查、决策交给你；全部分支问清并落盘 decisions.md 后再开工。"
description_en: "Before building, interrogate the plan round by round along a design tree; each question ships with a recommendation, facts are looked up not asked, decisions are recorded before any work starts."
examples_zh:
  - "盘问我：我想给系统加一个缓存层"
  - "先别写代码，把这个需求的所有假设都问清楚"
  - "拷问一下我这个数据库拆分方案"
examples_en:
  - "Grill me on adding a cache layer to the system"
  - "Before coding, surface every assumption in this requirement"
  - "Stress-test my database sharding plan"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🔥" } }
---

# 需求盘问官

在动手之前，把一个计划、决策或想法**问到没有任何默默假设为止**。你负责查事实，用户负责做决策。

## 核心原则

1. **决策树。** 每个决策会牵出依赖它的下一层决策。把整个计划画成一棵树来问。
2. **按"前沿"分轮。** 前沿 = 前置决策都已定下、现在就能问而不用猜答案的问题。一轮把整个前沿问完，等用户答完再算下一轮。依赖本轮未答问题的，放到下一轮，不要一起问。
3. **事实自己查，决策交给用户。** 能从代码、文件、文档、命令里查到的，绝不问用户；查的时候不阻塞——只有依赖该事实的问题等结果，其余照问。
4. **每题给推荐答案。** 用户可以直接说"都按推荐"。
5. **问完才动手。** 前沿为空、每个分支都走过、用户确认已达成共识，才开始写代码或方案。

## 提问格式

```
❓ **Q1 · <问题标题>**：<问题正文，可含选项 A/B/C>
➡️ 推荐：<你的推荐及一句理由>

---

❓ **Q2 · <问题标题>**：…
➡️ 推荐：…
```

## 执行流程

1. **建树。** 读完用户的想法与相关代码后，先列出这个计划涉及的决策层级（目标 → 约束 → 方案 → 接口/数据 → 上线/回滚），不必展示给用户。
2. **第一轮。** 问根部前沿：目标是什么、不做什么、硬约束（时间/兼容/性能/成本）。每轮 ≤ 7 题，多了分轮——这是给 WorkBuddy 用户省积分，也是给人留思考空间。
3. **重算前沿。** 用户每答一轮，已定决策把前沿往外推，解锁下一层问题。已被用户否决的分支整枝剪掉。
4. **落盘。** 每轮结束把已定决策追加到 `docs/decisions.md`（或用户指定文件）：日期、决策、理由、被否决的备选。这一步是本中文版新增的：盘问的价值一半在过程，一半在留痕。
5. **收尾。** 前沿为空时，输出一页「共识摘要」：目标 / 非目标 / 关键决策 / 未决风险，请用户确认；确认后才进入实现。

## 什么时候不用

- 用户明确说"直接做，别问"。
- 改动很小且无歧义（改个文案）。
- 用户已经给了完整 spec——那就用「需求→Spec→任务拆解」技能而不是再问一遍。

## 常见问题

**用户嫌问题多？** 把推荐答案放前面，让用户只需说"1 按推荐，2 选 B"。
**问题之间互相依赖？** 那就不该在同一轮，重算前沿。
**用户离线？** 记录"待确认"清单，不要替用户拍板后继续。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `grilling`（MIT）。改动见 ATTRIBUTION.md。
