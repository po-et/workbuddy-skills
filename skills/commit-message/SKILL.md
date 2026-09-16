---
name: commit-message
description: 生成 Git 提交信息（Conventional Commits 规范）。当用户要写 commit message、提交说明、提交信息、git commit -m、想让提交记录规范化、需要判断这次改动该用 feat/fix/refactor/docs/chore 哪种类型、要确定 scope 范围、想知道是不是破坏性变更（BREAKING CHANGE）、或者提到「帮我写提交信息」「这次改动怎么提交」「commit 怎么写」「规范一下 git log」时使用。脚本从暂存区或工作区 diff 确定性地推断类型、范围、新增/删除的符号并给出中英文候选，模型只做措辞润色；不猜没改过的东西，不写空话。
author: Captain
version: 0.1.0
display_name: "Git 提交信息生成器"
display_name_en: "Commit Message Generator"
description_zh: "从暂存区 diff 推断 Conventional Commits 的类型、范围与破坏性变更，给出中英文提交信息候选，subject 不超 50 字、body 讲 why。"
description_en: "Infer Conventional Commit type, scope and breaking changes from the staged diff and propose zh/en commit messages; subject ≤ 50 chars, body explains why."
examples_zh:
  - "帮我给暂存的改动写一条提交信息"
  - "这次改动算 feat 还是 fix？给我规范的 commit message"
  - "把工作区的修改按 Conventional Commits 拆成提交说明"
examples_en:
  - "Write a commit message for my staged changes"
  - "Is this a feat or a fix? Give me a conventional commit"
  - "Draft commit messages for my working-tree changes"
metadata:
  { "openclaw": { "requires": { "bins": ["git", "python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "✍️" } }
---

# Git 提交信息生成器

把一次改动写成**读 log 的人能看懂、工具能解析**的提交信息。规范：Conventional Commits 1.0。

## 核心原则

1. **只写 diff 里有的事。** 脚本列出的文件、符号、统计是唯一事实来源；没改的功能一个字不提。
2. **subject 讲做了什么，body 讲为什么。** subject ≤ 50 字符、祈使语气、不加句号；body 写动机、取舍、影响面。
3. **类型判断有依据。** 脚本给出的 `type.reasons` 必须在回复里复述一遍，让用户能反驳。
4. **破坏性变更宁可多标。** 删了对外符号、改了接口签名、删了配置项，就用 `!` 并写 `BREAKING CHANGE:` 页脚。

## 执行流程

### 第 1 步：采集

```bash
python3 {baseDir}/scripts/suggest_commit.py --repo <仓库路径> --out out/commit.json --print
```

默认看暂存区；暂存区为空则看工作区（含未跟踪的新文件）。`--staged` / `--worktree` 可强制。
输出：文件列表与状态、增删行数、类型猜测与依据、scope 候选、新增/删除的函数或类名、破坏性变更嫌疑、中英文候选。
diff 超过 200KB 会截断并标记 `diff_truncated`，此时提醒用户拆分提交。

### 第 2 步：润色（这一步由你做）

- 从候选里选一条或重写，保持 `type(scope): subject` 格式；scope 用脚本给的候选，没有就省略。
- body 用 2–4 个要点：为什么改、怎么改的、影响谁；每个要点对应 `body_hints` 里的文件。
- 工单号放页脚 `Refs: #123`；破坏性变更放页脚 `BREAKING CHANGE: <迁移方法>`。
- 改动里混了两类不相关的事（比如 feat + 大段 docs）→ 建议拆成两次提交，并各给一条信息。

### 第 3 步：交付

给出**最终提交信息**（可直接 `git commit -F`）和一行"依据"。用户要英文就只给英文；默认中文 subject + 英文 type。

## 输出契约

```
<type>(<scope>)<!>: <subject ≤ 50 字符>

- 为什么：…
- 改了什么：…
- 影响：…

Refs: #123
BREAKING CHANGE: …（仅在有时）
```

## 类型速查

| type | 用于 | 不用于 |
|---|---|---|
| feat | 用户可感知的新能力 | 内部重构 |
| fix | 修正错误行为 | 改样式 |
| refactor | 行为不变的结构调整 | 顺手改了行为 |
| perf | 可度量的性能提升 | 未度量的"优化" |
| docs / test / build / ci / chore / style | 各自字面含义 | 混入代码行为变化 |

## 常见问题

**脚本说 refactor 但我加了功能？** 以你为准，脚本的判断只是证据链；把依据改成你的理由。
**一次提交改了 40 个文件？** 先按 `scope.candidates` 拆，再逐个生成。
**要英文？** `--lang en`。
