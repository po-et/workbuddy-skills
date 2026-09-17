---
name: finishing-a-development-branch-zh
description: 开发分支收尾、功能做完了怎么合、本地合并还是发 PR、工作树用完怎么清理、游离 HEAD 下怎么收尾、丢弃分支的确认流程。当用户说「这个功能做完了」「可以合了吗」「帮我收尾这个分支」「合回主干还是提 PR」「工作树能删了吗」「分支收尾」「这次改动怎么落地」时使用。六步：跑全量测试（红了就停，菜单只在全绿之后出现）→ 检测环境（普通仓库 / 命名分支工作树 / 游离 HEAD）→ 确认基线分支 → 原样给出三选一或两选一菜单并等用户回答 → 执行所选项 → 清理工作区。红线：合并目标要先确认；合并后要在合并结果上重跑测试；工作树里有未提交文件时禁止自作主张 --force 删除；丢弃工作必须用户明确要求并输入确认词。
author: Captain
version: 0.1.0
display_name: "开发分支收尾"
display_name_en: "Finishing a Development Branch (zh)"
description_zh: "实现完成后如何落地：先验证测试再给菜单，本地合并/发 PR/原样保留三选一，按工作树归属决定清理方式，丢弃工作需显式确认。"
description_en: "Land completed work safely: verify tests, detect the workspace state, present the merge/PR/keep menu, execute the choice, and clean up the worktree only when it is ours to clean."
examples_zh:
  - "这个功能做完了，帮我收尾这个分支"
  - "合回主干还是提 PR"
  - "工作树能删了吗"
examples_en:
  - "The feature is done, how should we land it"
  - "Merge locally or open a pull request"
  - "Clean up the worktree now that the PR is up"
metadata:
  { "openclaw": { "requires": { "bins": ["git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🚢" } }
---

# 开发分支收尾

**核心原则：验证测试 → 检测环境 → 给出选项 → 执行选择 → 清理工作区。**

**开始时声明：**「我正在用开发分支收尾技能来完成这次工作。」

## 何时用

实现已完成、测试应当全绿、需要决定这批改动怎么落地时使用。测试还没过、功能还没做完的，不要进这个流程。

## 流程

### 第 1 步：验证测试

跑项目的全量测试套件（`npm test` / `cargo test` / `pytest` / `go test ./...`，以仓库自己的命令为准）。

**测试失败**：报告失败并停下——菜单只在全绿之后才出现：

```
测试失败（<N> 个）。必须先修复才能收尾：

[列出失败项]
```

**测试通过**：进入第 2 步。

### 第 2 步：检测环境

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
# 现在就取，趁还在工作区里：第 5 步会切目录，而第 6 步的清理需要这个值
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

| 状态 | 菜单 | 清理方式 |
|------|------|----------|
| `GIT_DIR == GIT_COMMON`（普通仓库） | 标准三选一 | 没有工作树要清 |
| `GIT_DIR != GIT_COMMON`，命名分支 | 标准三选一 | 按归属清理（见第 6 步） |
| `GIT_DIR != GIT_COMMON`，游离 HEAD | 两选一（无本地合并） | 由外部托管，原样留着 |

### 第 3 步：确认基线分支

基线分支就是这次工作从哪儿分出来的——通常写在计划里、对话里，或分支的上游里。不确定就问：「这个分支是从 <你的最佳猜测> 分出来的，对吗？」**合并前必须确认：合错基线的代价很大。**

### 第 4 步：给出选项

**普通仓库与命名分支工作树——原样给出这三项：**

```
实现完成。你想怎么处理？

1. 本地合并回 <基线分支>
2. 推送并创建 Pull Request
3. 分支原样保留（我自己后面处理）

选哪个？
```

**游离 HEAD——原样给出这两项：**

```
实现完成。你当前处于游离 HEAD（工作区由外部托管）。

1. 推送为新分支并创建 Pull Request
2. 原样保留（我自己后面处理）

选哪个？
```

菜单要**照抄**——简洁，且每一项都来自上面的列表。**丢弃工作不在菜单里**，只在用户明确提出时才走那条路。给完菜单就等回答：怎么落地是用户的决定。

### 第 5 步：执行所选项

#### 选项 1：本地合并

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"

# 先合并，确认成功再删任何东西
git checkout <基线分支>
git pull
git merge <功能分支>

# 在合并结果上重跑测试
<测试命令>
```

合并结果测试失败：停下，工作树和分支原样留着，去排查——还没推送，合并是本地的、可恢复的。

合并结果全绿后：先清理工作树（第 6 步），再删分支：

```bash
git branch -d <功能分支>
```

#### 选项 2：推送并建 PR

```bash
git push -u origin <功能分支>
# 游离 HEAD 时，给远端分支起名：
# git push origin HEAD:refs/heads/<新分支名>
```

然后用代码托管平台的工具（有 CLI 就用 CLI，否则用推送时打印出来的创建链接）对着 <基线分支> 建 PR，遵循仓库自己的 PR 模板与约定，并把 URL 报给用户。

**工作树保留**——用户要在里面处理 PR 上的评审意见。

#### 选项 3：原样保留

汇报：「保留分支 <名称>。工作树保留在 <路径>。」

#### 如果用户明确要求丢弃这次工作

这条路只在用户**明确提出**丢弃时才存在。先确认：

```
这将永久删除：
- 分支 <名称>
- 全部提交：<提交列表>
- 工作树 <路径>

请输入 discard 确认。
```

**等到这个确认词**才动手。收到后：

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git branch -D <功能分支>
```

（删分支前先执行第 6 步的工作树清理。）

### 第 6 步：清理工作区

**只在选项 1 与已确认的丢弃时执行。** 选项 2 和 3 永远保留工作树。两条路径都已经切到主仓库根目录（工作树必须从外部删除），并使用第 2 步在切目录之前取到的 `GIT_DIR` / `GIT_COMMON` / `WORKTREE_PATH`。

**若 `GIT_DIR == GIT_COMMON`：** 普通仓库，没有工作树要清，完成。

**若 `WORKTREE_PATH` 位于 `.worktrees/` 或 `worktrees/` 下：** 这棵工作树是隔离工作区技能建的，清理归我们：

```bash
git worktree remove "$WORKTREE_PATH"
git worktree prune   # 自愈：顺带清掉失效登记
```

**若删除被拒绝**（`contains modified or untracked files`）：工作树里有别处不存在的文件——未提交的计划、笔记、草稿。**绝不要自作主张加 `--force`。** 把代价摆给用户看，然后问：

```bash
git -C "$WORKTREE_PATH" status --porcelain -uall
```

```
工作树删除被拒绝——这些文件从未提交过：

<文件列表>

1. 清理前先提交到 <分支>
2. 移动到 <主仓库根目录>
3. 直接删除（不可恢复）

选哪个？
```

按用户的选择处理后，再删工作树。

**其他情况：** 这个工作区归宿主环境所有——原样留着。平台若提供退出工作区的工具，用它。

## 输出契约（速查）

| 选项 | 合并 | 推送 | 保留工作树 | 清理分支 |
|------|------|------|-----------|---------|
| 1. 本地合并 | 是 | - | - | 是 |
| 2. 创建 PR | - | 是 | 是 | - |
| 3. 原样保留 | - | - | 是 | - |
| 丢弃（仅限明确要求） | - | - | - | 是（强制） |

## 红线与常见借口反驳

| 借口 | 现实 |
|------|------|
| 「这轮早些时候测试过了」 | 在你即将落地的那棵树上跑。绿色只证明它跑过的那棵树。 |
| 「他们明显是想合并的」 | 落地方式是用户的决定。给菜单，然后等。 |
| 「这功能他们好像不要了，我提议丢弃吧」 | 菜单就是完整的。丢弃只在用户明说时发生。 |
| 「『行，删了吧』算确认了」 | 只有输入 `discard` 这个词才授权删除。 |
| 「PR 已经提了，工作树是多余的」 | 评审意见要在那棵工作树里改。工作落地前它得留着。 |
| 「旁边那棵工作树看着也没用了，顺手清了」 | 只清 `.worktrees/` 或 `worktrees/` 下的，其余都归宿主。 |
| 「删除被拒，`--force` 只是把清理做完」 | 被拒说明有文件只存在于那棵树里，`--force` 会永久销毁它们。给用户看，然后问。 |
| 「合并结果失败大概是偶发」 | 合并结果失败就全停。分支和工作树原地不动，去查。 |
| 「基线分支显然是 main」 | 确认分叉点或直接问。合错基线代价很大。 |
| 「推送被拒，force push 能解决」 | 被拒说明远端动过了。去查；force push 只在用户明确要求时做。 |

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `finishing-a-development-branch`（MIT）。改动见 ATTRIBUTION.md。
