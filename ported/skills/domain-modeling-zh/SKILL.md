---
name: domain-modeling-zh
description: 领域建模、统一语言、术语表、CONTEXT.md 编写与维护、ADR 架构决策记录、限界上下文与 CONTEXT-MAP.md。当用户讨论代码库术语、说「这个概念到底叫什么」「我们的术语表在哪」「写一份 CONTEXT.md」「把这个决定记成 ADR」「订单和账单是不是两个上下文」时使用。规则：用户用词与术语表冲突时立刻指出；模糊或重载的词提出精确的规范术语；用具体场景压测概念边界；对照代码核实用户的说法；术语一确定就当场写进 CONTEXT.md（不攒批）；CONTEXT.md 只做术语表、不含实现细节；ADR 只在「难以逆转 + 没有上下文会令人费解 + 真实权衡」三条同时成立时才提议。附 CONTEXT.md 与 ADR 的极简格式。改编自 Matt Pocock 的 domain-modeling（MIT）。
author: Captain
version: 0.1.0
display_name: "领域建模与术语表"
display_name_en: "Domain Modeling (zh)"
description_zh: "在设计过程中主动打磨项目的领域模型：挑战与术语表冲突的用词、把模糊词磨成规范术语、用场景压测边界、术语落定就写进 CONTEXT.md；ADR 只记难逆转的真实权衡。附 CONTEXT.md / CONTEXT-MAP.md / ADR 格式。"
description_en: "Actively build and sharpen a project's domain model while designing: challenge terms that conflict with the glossary, sharpen fuzzy words into canonical terms, stress-test boundaries with scenarios, write resolved terms into CONTEXT.md immediately; ADRs only for hard-to-reverse real trade-offs. Includes CONTEXT.md / CONTEXT-MAP.md / ADR formats."
examples_zh:
  - "帮我给这个项目写一份 CONTEXT.md 术语表"
  - "「账户」在我们代码里到底指用户还是客户？"
  - "把「订单和账单用领域事件通信」记成 ADR"
examples_en:
  - "Write a CONTEXT.md glossary for this project"
  - "Does 'account' mean User or Customer in our code?"
  - "Record 'Ordering and Billing talk via domain events' as an ADR"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "📖" } }
---

# 领域建模与术语表

在设计过程中**主动**构建并打磨项目的领域模型。这是一门主动的功夫：挑战术语、编造边界场景、在术语表和决策成形的那一刻就把它们写下来。（只是*读* `CONTEXT.md` 找词用不算这门功夫，那是任何技能都该有的一行习惯。本技能用于你在**改变**模型的时候，而不是消费它的时候。）

## 文件结构

多数仓库只有一个上下文：

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

根目录有 `CONTEXT-MAP.md` 说明仓库有多个上下文，地图指向每个上下文的位置：

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← 系统级决策
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← 该上下文的决策
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

文件**按需惰性创建**：有东西要写才建。没有 `CONTEXT.md` 就在第一个术语落定时创建；没有 `docs/adr/` 就在第一份 ADR 需要时创建。

## 会话进行中

### 对照术语表挑战用词

用户用了与 `CONTEXT.md` 已有语言冲突的词，立刻指出：「术语表把『取消』定义为 X，但你现在的意思像是 Y。到底是哪个？」

### 磨尖模糊语言

用户用了含糊或重载的词，提出精确的规范术语：「你说『账户』，指的是 Customer 还是 User？这是两个东西。」

### 讨论具体场景

讨论领域关系时，用具体场景压力测试。编造探测边界的场景，逼用户把概念之间的边界说精确。

### 与代码交叉核对

用户陈述某东西如何工作时，检查代码是否同意。发现矛盾就摆出来：「你的代码取消的是整张订单，但你刚说可以部分取消。哪个是对的？」

### 当场更新 CONTEXT.md

术语一落定就更新 `CONTEXT.md`。不要攒一批：发生时就记录。格式见 [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md)。

`CONTEXT.md` 必须完全不含实现细节。不要把它当 spec、草稿纸或实现决策仓库。它是术语表，仅此而已。

### 谨慎提议 ADR

只有三条同时成立才提议写 ADR：
1. **难以逆转**：以后改主意代价不小
2. **没有上下文会令人费解**：未来的读者看代码会想「为什么要这么做？」
3. **真实权衡的结果**：确有备选方案，你出于具体原因选了这个

缺任何一条就跳过。格式见 [ADR-FORMAT.md](ADR-FORMAT.md)。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `domain-modeling`（MIT）。改动见 ATTRIBUTION.md。
