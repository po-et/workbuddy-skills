---
name: architecture-deepening-zh
description: 代码库架构体检、找出可以「加深」的浅模块、重构机会扫描、架构评审可视化 HTML 报告、前后对比图、模块深度与接缝分析、提升可测试性与 AI 可导航性。当用户说「帮我看看这个代码库哪里该重构」「架构上有什么问题」「哪些模块太薄」「出一份架构评审报告」「测试为什么这么难写」时使用。流程：先定范围（用户点名的方向，或从 git log 找热点，YAGNI）→ 读 CONTEXT.md 与 ADR → 派子代理有机地走代码库、记录摩擦（在多个小模块间跳来跳去、接口几乎和实现一样复杂、为可测试性抽出纯函数但 bug 藏在调用处、跨接缝泄漏、难测）→ 对可疑处做删除测试 → 写一个自包含 HTML 报告到系统临时目录（Tailwind + Mermaid CDN，每个候选一张卡：文件/问题/方案/收益/前后对比图/推荐强度 Strong·Worth exploring·Speculative）→ 报告结尾给首推 → 用户选一个后进入拷问循环并同步更新 CONTEXT.md / ADR。也覆盖「该合并加深」「测试特别难写」「有没有重构空间」这类说法。改编自 Matt Pocock 的 improve-codebase-architecture（MIT）。
author: Captain
version: 0.1.1
display_name: "架构加深体检（HTML 报告）"
display_name_en: "Improve Codebase Architecture (zh)"
description_zh: "扫描代码库找出把浅模块变深的重构机会，输出带前后对比图的自包含 HTML 架构评审报告（写到系统临时目录），用户选一个候选后进入拷问循环并同步维护 CONTEXT.md / ADR。目标是可测试性与 AI 可导航性。"
description_en: "Scan a codebase for deepening opportunities (shallow → deep modules), present them as a self-contained HTML report with before/after diagrams (written to the OS temp dir), then grill through the candidate the user picks while keeping CONTEXT.md / ADRs current. Aim: testability and AI-navigability."
tags:
  - "架构体检"
  - "重构机会"
  - "深模块"
  - "架构评审"
  - "HTML 报告"
  - "技术债"
examples_zh:
  - "扫一遍这个仓库，告诉我哪些模块该合并加深，出份报告"
  - "订单模块测试特别难写，看看是不是架构的问题"
  - "最近改得最多的那块代码有没有重构空间"
examples_en:
  - "Scan this repo for modules worth deepening, give me a report"
  - "Order module tests are painful, is it the architecture?"
  - "Any deepening opportunity in the most-changed area?"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🏗️" } }
---

# 架构加深体检

找出架构摩擦，提出**加深机会**：把浅模块变成深模块的重构。目标是可测试性和 AI 可导航性。

## 何时用
用户点名某个模块/子系统有摩擦、测试特别难写、或想要一份系统性的架构体检报告时用；日常小重构、已经知道要改哪几行代码时不需要这套流程，直接改就好。

每个候选卡片：
```
- [ ] 文件：涉及哪些文件/模块
- [ ] 问题：当前架构为什么造成摩擦
- [ ] 方案：会改什么
- [ ] 收益：局部性与杠杆，测试会怎样变好
- [ ] 前后对比图 + 推荐强度（Strong / Worth exploring / Speculative）
```

这项工作*以*项目的领域模型为依据，建立在一套共享的设计词汇上：
- 配合「深模块设计」技能的架构词汇（**模块、接口、深度、接缝、适配器、杠杆、局部性**）及其原则（删除测试、「接口就是测试面」、「一个适配器 = 假想接缝，两个 = 真接缝」）。每条建议都精确使用这些词，不滑向「组件」「服务」「API」「边界」。
- `CONTEXT.md` 里的领域语言给好接缝命名；`docs/adr/` 里的 ADR 记录了不该重新争论的决策。

## 流程

### 1. 探索

**扫描前先定范围：YAGNI。** 加深一个模块的回报是让它未来的改动更容易，所以格外看重最近改动过的部分。先决定*看哪里*再看：
- 用户点了方向（某个模块、子系统、痛点），就照做，跳过下面的推断。
- 否则往回走一段提交历史（`git log --oneline`）找热点：反复出现的文件和区域，让这些路径先吸引你的注意。改动分散、没有明显热点，就把网撒宽。

先读项目的领域术语表（`CONTEXT.md`）和你要触碰区域的 ADR。

然后派一个子代理走代码库。不要按僵硬的启发式，有机地探索，记下哪里让你感到摩擦：
- 理解一个概念需要在很多小模块之间跳来跳去？
- 哪些模块是**浅**的：接口几乎和实现一样复杂？
- 哪里为了可测试性抽出了纯函数，但真正的 bug 藏在它们被调用的方式里（没有**局部性**）？
- 哪些紧耦合的模块跨接缝泄漏？
- 代码库哪些部分没测试，或者通过当前接口很难测？

对任何怀疑是浅的东西做**删除测试**：删掉它会让复杂度集中，还是只是挪个地方？「会集中」就是你要的信号。

### 2. 用 HTML 报告呈现候选

写一个自包含的 HTML 文件到操作系统临时目录，不落进仓库。临时目录取 `$TMPDIR`，退回 `/tmp`（Windows 用 `%TEMP%`），写到 `<tmpdir>/architecture-review-<timestamp>.html`，每次运行一个新文件。替用户打开（Linux `xdg-open <path>`，macOS `open <path>`，Windows `start <path>`），并告诉他们**绝对路径**。

报告用 **Tailwind（CDN）** 排版，**Mermaid（CDN）** 画图——凡是图/流程/时序能可靠传达结构的地方。Mermaid 与手工 CSS/SVG 混用：关系是图状的（调用图、依赖、时序）用 Mermaid；想要更有编辑感的（质量图、剖面图、折叠动画）手写 div/SVG。每个候选都有**前后对比可视化**。要视觉化。

每个候选一张卡：
- **文件**：涉及哪些文件/模块
- **问题**：当前架构为什么造成摩擦
- **方案**：大白话说会改什么
- **收益**：用局部性和杠杆解释，以及测试会怎样变好
- **前后对比图**：并排、手绘、展示浅在哪、深到哪
- **推荐强度**：`Strong` / `Worth exploring` / `Speculative` 之一，渲染为徽章

报告结尾放**首推**一节：你会先做哪个候选、为什么。

**领域用 CONTEXT.md 的词，架构用「深模块设计」的词。** `CONTEXT.md` 定义了「Order」，就说「Order 接单模块」，不说「FooBarHandler」，也不说「Order 服务」。

**ADR 冲突**：候选与现有 ADR 矛盾时，只有摩擦真实到值得重开那份 ADR 才列出来。在卡片上明确标记（如警示框：*「与 ADR-0007 矛盾，但值得重开，因为……」*）。不要把 ADR 禁止的每个理论上的重构都列一遍。

HTML 脚手架、图型与样式指南见 [HTML-REPORT.md](HTML-REPORT.md)。

此时**不要**提出接口。文件写好后问用户：「想深入探索哪一个？」

### 3. 拷问循环

用户选定候选后，配合「拷问我」技能和他们一起走决策树：约束、依赖、加深后模块的形状、接缝背后是什么、哪些测试能活下来。

决策成形时副作用当场发生；配合「领域建模」技能保持领域模型最新：
- **加深后的模块要以 `CONTEXT.md` 里没有的概念命名？** 把术语加进 `CONTEXT.md`。文件不存在就惰性创建。
- **对话中把一个模糊术语磨尖了？** 当场更新 `CONTEXT.md`。
- **用户以承重的理由否决了候选？** 提议写 ADR，措辞如：*「要不要记成 ADR，免得以后的架构评审再提同样的建议？」* 只有理由是未来探索者避免重提所必需的才提议；跳过短暂的理由（「现在不值得」）和不言自明的。
- **想为加深后的模块探索备选接口？** 用「深模块设计」的「设计两次」并行子代理模式。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `improve-codebase-architecture`（MIT）。改动见 ATTRIBUTION.md。
