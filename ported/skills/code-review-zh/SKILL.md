---
name: code-review-zh
description: 代码评审、PR review、代码审查、看看这个分支改得对不对。当用户说「帮我 review 这个 PR」「评审一下这次改动」「从 main 到现在的代码有什么问题」「检查有没有代码坏味道」「这个改动符合需求吗」「合并前把关」，或提到 code review、代码走查、重构建议、Fowler 坏味道（重复代码、特性依恋、散弹式修改、基本类型偏执、过度设计…）时使用。两个轴分开评审、不互相掩盖：标准轴（仓库规范 + 12 种坏味道基线）与 Spec 轴（做的是不是需求要的、有没有多做）。脚本先把机器能查的查完：调试遗留、疑似密钥、超长行、巨型文件、散弹式修改、有代码没测试、重复代码块、工单引用。改编自 Matt Pocock 的 code-review（MIT），中文化并新增预处理脚本。
author: Captain
version: 0.1.0
display_name: "代码评审（双轴）"
display_name_en: "Code Review, Two Axes (zh)"
description_zh: "标准轴（仓库规范 + Fowler 12 种坏味道）与 Spec 轴（是否实现了需求、有无多做）分开评审；脚本预扫遗留物、密钥、重复块、测试缺失。"
description_en: "Review on two separate axes: Standards (repo conventions + 12 Fowler smells) and Spec (does it do what was asked, nothing more); a script pre-scans leftovers, secrets, duplicates and missing tests."
examples_zh:
  - "review 一下 feature/login 相对 main 的改动"
  - "这个 PR 有没有坏味道，符合需求 #123 吗"
  - "合并前帮我把关这次提交"
examples_en:
  - "Review feature/login against main"
  - "Any code smells in this PR, and does it satisfy issue #123?"
  - "Gate-check this change before merge"
metadata:
  { "openclaw": { "requires": { "bins": ["git", "python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔍" } }
---

# 代码评审（双轴）

对 `<固定点>...HEAD` 的改动做两个**互不合并**的评审：

- **标准轴**：代码是否符合本仓库的书面规范 + 坏味道基线。
- **Spec 轴**：代码是否忠实实现了需求/工单，有没有偷偷多做或少做。

一段代码可以一轴过一轴不过：规范完美但做错了事（标准过、Spec 不过）；正好做了需求但破坏了项目约定（Spec 过、标准不过）。分开报，谁也别遮住谁。

## 执行流程

### 第 1 步：钉住固定点，跑预处理

用户给的固定点（`main`、tag、SHA、`HEAD~5`）；没给就问。然后：

```bash
python3 {baseDir}/scripts/review_prep.py --repo <仓库> --base <固定点> --out out/review.json --print
```

脚本输出：提交列表与工单引用、改动统计、信号（有代码没测试 / 巨型文件 / 散弹式修改 / 疑似密钥（已脱敏）/ 调试遗留 / 重复新增代码块 / diff 截断）。固定点不存在或 diff 为空会在这里失败，不要带着坏输入往下走。

### 第 2 步：找 Spec 来源

顺序：提交信息里的工单号 → 用户给的路径 → `docs/` `specs/` `.scratch/` 下与分支同名的文件 → 问用户。用户说没有 spec，Spec 轴就报「无 spec，跳过」，不要自己脑补需求。

### 第 3 步：找标准来源

仓库里任何说明"代码该怎么写"的文件：`CONTRIBUTING.md`、`CODING_STANDARDS.md`、`.editorconfig`、lint 配置。**仓库规范优先于基线**：规范明确允许的，基线不报。工具已强制的（formatter、linter）不报。

坏味道基线（Fowler《重构》第 3 章，每条都是判断题，不是硬错误）：

| 坏味道 | 表现 | 处理 |
|---|---|---|
| 神秘命名 | 名字看不出干什么 | 改名；想不出诚实的名字说明设计不清 |
| 重复代码 | 同样的逻辑形状出现两次以上 | 抽出共享部分 |
| 特性依恋 | 方法总在碰别的对象的数据 | 把方法搬到它依恋的数据旁 |
| 数据泥团 | 几个字段总是一起出现 | 合成一个类型 |
| 基本类型偏执 | 用字符串/数字冒充领域概念 | 给概念一个小类型 |
| 重复的 switch | 对同一类型反复分支 | 多态或共享映射表 |
| 散弹式修改 | 一个逻辑改动散落在很多文件 | 聚到一个模块 |
| 发散式变化 | 一个模块因多种不相干原因被改 | 拆开 |
| 夸夸其谈的通用性 | 为不存在的需求加抽象/参数 | 删掉，等真需求 |
| 消息链 | `a.b().c().d()` | 在第一个对象上封装 |
| 中间人 | 只会转发的类/函数 | 去掉，直接调用 |
| 被拒绝的遗赠 | 子类无视大部分继承 | 改组合 |

### 第 4 步：两轴分别评审（各 400 字以内）

**标准轴**：逐文件/逐块列出 (a) 违反书面规范之处（引用规范文件与条款）；(b) 命中的基线坏味道（点名并引用代码块）。区分"硬违反"与"判断题"。把脚本的信号（遗留物、密钥、重复块、测试缺失）纳入。

**Spec 轴**：(a) 需求要而没做或只做一半的；(b) 需求没要但做了的（范围蔓延）；(c) 看似做了但实现方向不对的。每条引用 spec 原句。

### 第 5 步：汇总

按 `## 标准` `## Spec` 两个标题原样呈现，**不合并、不重排**。结尾一行：每轴几条、每轴最严重的一条。不选"总冠军"——那正是分轴要防的事。

## 输出契约

```
范围：<固定点>...HEAD，N 提交，M 文件，+a/-d；Spec 来源：<工单/文件/无>
## 标准
- [硬违反|判断题] 文件:行 — 规范/坏味道 — 建议
## Spec
- [缺失|多做|做错] 引用 spec 原句 — 现状 — 建议
一句话：标准 N 条（最严重：…）；Spec M 条（最严重：…）
```

## 常见问题

**改动很大？** 先按脚本 `files` 里的目录分组评审，或建议作者拆 PR。
**没有书面规范？** 只跑基线，并建议团队写一份 `CONTRIBUTING.md`。
**评审自己写的代码？** 也走一遍——脚本不认人。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `code-review`（MIT）。改动见 ATTRIBUTION.md。
