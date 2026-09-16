---
name: merge-conflicts-zh
description: 解决 Git 合并冲突、rebase 冲突、cherry-pick 冲突。当用户说「merge 冲突了怎么办」「rebase 卡住了」「帮我解冲突」「<<<<<<< HEAD 这些怎么处理」「合并 main 到我的分支报冲突」「两个人改了同一个文件」「rebase --continue 一直失败」时使用。流程：先看状态与冲突文件，再追每一处改动的原始意图（提交信息、PR、工单），逐块保留双方意图、不发明新行为，跑项目自带的类型检查/测试/格式化，最后完成 merge 或 rebase。附完整 git 命令序列、冲突标记读法、ours/theirs 在 merge 与 rebase 里方向相反的坑、rerere。改编自 Matt Pocock 的 resolving-merge-conflicts（MIT），中文化并大幅扩充命令与检查清单。
author: Captain
version: 0.1.0
display_name: "合并冲突解决"
display_name_en: "Resolving Merge Conflicts (zh)"
description_zh: "五步解 merge/rebase 冲突：看状态、追双方意图、逐块保留不发明行为、跑检查、完成合并；附命令序列与 ours/theirs 方向陷阱。"
description_en: "Resolve merge/rebase conflicts in five steps: inspect, trace both intents, resolve hunk by hunk without inventing behaviour, run checks, finish; with command sequences and the ours/theirs direction trap."
examples_zh:
  - "我 rebase main 的时候冲突了，帮我解决"
  - "这个文件有三处 <<<<<<< 冲突标记，怎么合"
  - "cherry-pick 一个提交冲突了，走一遍流程"
examples_en:
  - "I hit conflicts rebasing onto main, help me resolve them"
  - "This file has three <<<<<<< markers, how do I merge them"
  - "A cherry-pick conflicted, walk me through it"
metadata:
  { "openclaw": { "requires": { "bins": ["git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔀" } }
---

# 合并冲突解决

冲突不是 bug，是两个人各自正确的改动在同一处相遇。目标：**双方意图都活下来**；做不到时选符合本次合并目标的一方，并记录取舍。

## 核心原则

1. **先懂再改。** 每一处冲突都要知道两边为什么改；不知道就去读提交、PR、工单。
2. **不发明新行为。** 解冲突不是重构，不顺手改逻辑。
3. **能解就解，不轻易 `--abort`。** 放弃是用户的决定，不是你的默认。
4. **合完必须跑检查。** 类型检查 → 测试 → 格式化，冲突解错最常见的表现是"编译过了但测试红了"。

## 执行流程

### 第 1 步：看清现状

```bash
git status                                   # 处于 merge / rebase / cherry-pick 哪种状态
git diff --name-only --diff-filter=U         # 冲突文件列表
git log --oneline --left-right --merge -- <文件>   # 只看涉及冲突的双方提交
git diff                                     # 冲突块（含 <<<<<<< / ======= / >>>>>>>）
```

冲突标记读法：`<<<<<<< HEAD` 到 `=======` 是**当前分支**的版本，`=======` 到 `>>>>>>> <ref>` 是**被合入**的版本。开启 `git config merge.conflictStyle zdiff3` 后中间还会显示共同祖先，解起来快一倍。

### 第 2 步：追每一处的原始意图

对每个冲突文件的每一块：`git log -p --follow -- <文件>` 找到两边各自的提交；读提交信息；有 PR/工单号就去看描述与讨论。写下一句话："A 方改这里是为了 X，B 方是为了 Y。"

### 第 3 步：逐块解决

- 两边意图不冲突（各改一行、各加一个分支）→ 都保留。
- 同一逻辑两种实现 → 选符合**本次合并目标**的一方（合 main 到特性分支：以 main 为准保住主线；把特性合回 main：以特性为准但不破坏主线新逻辑），并在提交信息里记录取舍。
- 一方删除、一方修改 → 问"删除的理由还成立吗"，通常需要用户拍板。
- 锁文件（package-lock / poetry.lock）冲突 → 不要手改，取一边后重新生成。

**方向陷阱**：`--ours` / `--theirs` 在 **merge** 里 ours = 当前分支；在 **rebase** 里 ours = 被 rebase 到的目标（上游），theirs = 你正在重放的提交。用之前先想清楚。

```bash
git checkout --ours -- <文件>      # 整个文件取一边（慎用）
git checkout --theirs -- <文件>
git add <文件>                     # 标记已解决
```

### 第 4 步：跑项目自带的检查

找出项目的检查命令（package.json scripts、Makefile、CI 配置），按序跑：类型检查 → 单元测试 → 格式化 / lint。修掉合并引入的问题；如果失败与本次冲突无关，说明并继续。

### 第 5 步：完成

```bash
git merge --continue          # 或 git commit（merge）
git rebase --continue         # rebase：重复 1–4 直到所有提交重放完
git cherry-pick --continue
```

开启 `git config rerere.enabled true`，同样的冲突第二次会自动解。

### 交付

一段摘要：冲突文件与块数、每块的取舍与理由、跑过的检查及结果、是否有需要用户确认的"删除 vs 修改"。

## 常见问题

**rebase 一直冲突同一处？** 每重放一个提交都会遇到，rerere 或先 squash 再 rebase。
**冲突块巨大（生成文件、压缩产物）？** 取一边后重新生成，不要逐行合。
**解完发现行为变了？** 回到第 2 步，你可能选错了一方；`git diff <merge-base> HEAD` 核对。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `resolving-merge-conflicts`（MIT）。改动见 ATTRIBUTION.md。
