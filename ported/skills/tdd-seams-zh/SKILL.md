---
name: tdd-seams-zh
description: 接缝驱动的测试驱动开发、红绿循环、集成风格测试、只在约定的接缝上写测试、什么时候该 mock、避免实现耦合测试与同义反复测试、垂直切片而非横向切片。当用户说「用 TDD 做这个功能」「先写测试」「红绿重构」「这个测试是不是测到实现细节了」「该不该 mock 数据库」「测试一重构就挂」时使用。核心规则：测试只验公开接口的行为，不碰内部；写任何测试前先列出要测的接缝并与用户确认；先红后绿、一次一片；重构不在红绿循环里、属于评审阶段；mock 只在系统边界（外部 API、时间/随机、有时是数据库/文件系统），永不 mock 自己的模块；期望值必须来自独立的真相来源（已知字面量、算例、规格）。附好坏测试对照与可 mock 性设计（依赖注入、SDK 式接口）。改编自 Matt Pocock 的 tdd（MIT）；与 addyosmani 版 tdd-zh 互补。
author: Captain
version: 0.1.0
display_name: "接缝驱动 TDD"
display_name_en: "TDD at Seams (zh)"
description_zh: "红→绿循环的参考手册：什么是好测试、测试写在哪（预先约定的接缝）、三大反模式（实现耦合、同义反复、横向切片）、循环规则（先红后绿、一次一片、重构不在循环里）；附好坏测试对照与系统边界 mock 指南。"
description_en: "Reference for the red→green loop: what a good test is, where tests go (pre-agreed seams), three anti-patterns (implementation-coupled, tautological, horizontal slicing), loop rules (red before green, one slice at a time, refactoring outside the loop); with good/bad test examples and boundary-only mocking guidance."
examples_zh:
  - "用 TDD 实现购物车结算，先跟我确认要测哪些接缝"
  - "这个测试 mock 了内部的 paymentService，是不是测偏了"
  - "该 mock 数据库还是用测试库？"
examples_en:
  - "TDD the cart checkout, confirm seams with me first"
  - "This test mocks the internal paymentService, is it off?"
  - "Mock the database or use a test DB?"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🔴" } }
---

# 接缝驱动 TDD

TDD 是红 → 绿的循环。本技能是让这个循环产出**值得保留的测试**的参考：什么是好测试、测试写在哪、反模式、循环的规则。每一节在每个循环都适用：循环之前和之中都要对照，而不是事后。

探索代码库时读 `CONTEXT.md`（如果有），让测试名和接口词汇与项目的领域语言一致；尊重所触区域的 ADR。

## 什么是好测试

测试通过**公开接口**验证行为，不验实现细节。代码可以整个换掉，测试不该动。好测试读起来像规格：「用户可以用有效购物车结算」准确告诉你存在什么能力，而且它不关心内部结构，所以重构后仍然存活。

示例见 [tests.md](tests.md)，mock 指南见 [mocking.md](mocking.md)。

## 接缝：测试写在哪

**接缝**是你测试所在的公开边界：不伸手进内部就能观察行为的那个接口。测试住在接缝上，永远不对着内部写。

**只在预先约定的接缝上测。** 写任何测试之前，先写下要测的接缝，与用户确认。没确认的接缝不写测试。你不可能测所有东西，所以事先约定接缝，测试精力才会落在关键路径和复杂逻辑上，而不是每一个边角。

问：「公开接口是什么？我们该测哪些接缝？」

接口本身的形状还有疑问时（模块多深、接缝该在哪、接口该暴露什么），配合「深模块设计」技能的词汇：模块、接口、深度、接缝、适配器、杠杆、局部性。它是参考，不是要跑的流程。

## 反模式

- **实现耦合**：mock 内部协作者、测私有方法，或通过旁路验证（直接查数据库而不是走接口）。特征：重构后行为没变，测试却挂了。
- **同义反复**：断言用与代码相同的方式重新算出期望值（`expect(add(a, b)).toBe(a + b)`、按同样方法手推的快照、常量等于自己），于是构造上必然通过，永远不可能与代码意见相左。期望值必须来自**独立的真相来源**：已知的字面量、一个算例、规格。
- **横向切片**：先写完所有测试再写所有实现。批量测试验证的是*想象中*的行为：你测的是东西的*形状*而不是面向用户的行为，测试对真实变化变得不敏感，而且在理解实现之前就锁死了测试结构。改用**垂直切片**：一个测试 → 一个实现 → 重复，每个测试都是一颗**曳光弹**，回应上一轮教你的东西。

## 循环的规则

- **先红后绿。** 先写会失败的测试，再写刚好够让它通过的代码。不预支未来的测试，不加投机的功能。
- **一次一片。** 每个循环：一个接缝、一个测试、一个最小实现。
- **重构不在循环里。** 它属于评审阶段（见代码评审技能），不属于红 → 绿的实现循环。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `tdd`（MIT）。改动见 ATTRIBUTION.md。
