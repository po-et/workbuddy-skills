---
name: prototype-zh
description: 用一次性原型回答设计问题、验证状态机或业务逻辑是否合理、快速做几个 UI 方案对比、可分享的单文件 HTML 演示、状态模型演练、界面多方案切换。当用户说「先做个原型试试」「这个状态机对不对我想点一点看看」「给这个页面出三个版本比较一下」「做个 demo 给产品经理感受一下」时使用。两条分支：逻辑原型（单个自包含 HTML：自由按钮 + 分页引导剧本，纯逻辑模块可直接移植进真实代码）与 UI 原型（同一路由上通过 ?variant= 切换的多个结构迥异方案 + 浮动切换条，优先挂在已有页面里）。六条通用规则：一开始就标明是原型；一条命令能跑；默认不持久化；不打磨（无测试无抽象）；每步暴露状态；完成后把结论并入真实代码、原型进一次性分支作一手资料。也覆盖「试各种顺序」「完全不同的布局」「感受一下审批流程」这类说法。改编自 Matt Pocock 的 prototype（MIT）。
author: Captain
version: 0.1.1
display_name: "一次性原型（逻辑 / UI）"
display_name_en: "Prototype (zh)"
description_zh: "原型是回答一个问题的一次性代码。逻辑问题→单文件 HTML 演示（自由按钮 + 引导剧本，纯逻辑模块可移植）；外观问题→同一路由上 ?variant= 切换的多个结构迥异 UI 方案。附两条分支的完整流程与反模式。"
description_en: "A prototype is throwaway code that answers one question. Logic question → single-file HTML demo (free-play buttons + guided walkthroughs, liftable pure module); look question → several structurally different UI variants on one route switched via ?variant=. Full process and anti-patterns for both branches."
tags:
  - "原型设计"
  - "prototype"
  - "一次性代码"
  - "UI 方案对比"
  - "状态机验证"
examples_zh:
  - "退款状态机我拿不准，做个能点的 demo 让我试各种顺序"
  - "设置页出三个完全不同的布局让我挑"
  - "做个单文件 HTML 给产品经理感受一下审批流程"
examples_en:
  - "Not sure about the refund state machine, build a clickable demo"
  - "Give me three radically different layouts for settings"
  - "Single-file HTML so the PM can feel the approval flow"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# 一次性原型

原型是**回答一个问题的一次性代码**。问题决定形状。

## 何时用
拿不准一个状态机/业务逻辑对不对、或想让人在几个截然不同的 UI 方案里挑一个时用。已经确定要怎么做、只是要正式实现，不需要先做原型。

## 流程
选分支（逻辑 → LOGIC.md；外观 → UI.md）→ 按对应分支产出可分享的一次性代码 → 应用六条通用规则 → 完成后把验证过的决策并入真实代码、原型归档到一次性分支。

## 产出
```
逻辑原型 → 单文件 HTML（自由按钮 + 分页引导剧本，纯逻辑模块可直接移植进真实代码）
UI 原型   → 同一路由上 ?variant= 切换的多个结构迥异方案 + 浮动切换条
```
两者都必须在顶部明确标出"这是原型"，且完成后把结论并入真实代码、原型本身进一次性分支存档。

## 选分支

从用户的话、周围代码，或直接问，判断要回答哪个问题：

- **「这个逻辑 / 状态模型对不对？」** → [LOGIC.md](LOGIC.md)。做一个可分享的单文件 HTML（自由按钮 + 分页引导剧本），把状态机推过纸面上难推理的用例，非开发者也能自己点。
- **「这个应该长什么样？」** → [UI.md](UI.md)。在同一路由上生成几个**结构迥异**的 UI 方案，通过 URL 参数和浮动底栏切换。

两条分支产物完全不同，选错整个原型就白做。问题确实模糊又找不到用户时，按周围代码选（后端模块 → 逻辑；页面或组件 → UI），并在原型顶部写明假设。

## 两条分支共用的规则

1. **从第一天起就是一次性的，并且明确标出来。** 原型代码放在它将来要服务的模块或页面旁边，让上下文一目了然；命名要让随便一个读者都看出这是原型不是产品。UI 类一次性路由遵守项目现有的路由约定，不发明新的顶层结构。
2. **一条命令能跑。** UI 原型从项目任务运行器的一条命令启动（`pnpm <name>`、`python <path>`、`bun <path>` 等）；逻辑演示是双击就能开的单个 HTML。总之启动不用动脑。
3. **默认不持久化。** 状态放内存。持久化是原型要*检验*的东西，不是它该依赖的东西。问题明确涉及数据库时，用临时库或带「PROTOTYPE，可删」名字的本地文件。
4. **不打磨。** 不写测试，错误处理只到能跑为止，不抽象。目的是快学到东西。
5. **暴露状态。** 每次动作（逻辑）或每次切换方案（UI）后，把完整相关状态打印或渲染出来，让用户看到变了什么。
6. **完成后归档。** 把验证过的决策并入真实代码，再把原型本身作为**一手资料**保存：提交到 main 之外的一次性分支，在实现工单上留一个指向该分支的上下文指针。结论（判定与它回答的问题）也记进工单或提交。main 分支只保留验证过的决策。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `prototype`（MIT）。改动见 ATTRIBUTION.md。
