---
name: using-git-worktrees-zh
description: 用 git worktree 开隔离工作区、动手改代码前先把当前分支保护起来、执行实施计划前准备干净工作树、判断自己是不是已经在工作树里、区分工作树与子模块、工作树目录必须被 gitignore。当用户说「开个工作树做这个需求」「别动我当前分支」「并行开几个分支同时改」「这活先隔离出来做」「准备一个干净的实现环境」「worktree 怎么用」时使用。四步：先检测是否已在隔离工作区（比较 git-dir 与 git-common-dir，并排除子模块）→ 优先用平台自带的工作树工具，没有才退回 git worktree add → 自动识别项目类型装依赖 → 跑一遍基线测试确认起点是绿的。红线：目录没被忽略就别建、别绕过平台原生工具、基线测试失败要报告而不是硬着头皮往下做。
author: Captain
version: 0.1.0
display_name: "Git 工作树隔离工作区"
display_name_en: "Using Git Worktrees (zh)"
description_zh: "动手前先确保工作发生在隔离工作区：检测是否已隔离、优先用平台原生工具、退回 git worktree、装依赖、跑基线测试，并附速查表与常见借口反驳。"
description_en: "Ensure work happens in an isolated workspace: detect existing isolation, prefer native worktree tooling, fall back to git worktree, install dependencies, verify a clean test baseline; includes a quick-reference table."
examples_zh:
  - "开个工作树做这个需求，别动我当前分支"
  - "并行开几个分支同时改"
  - "准备一个干净的实现环境"
examples_en:
  - "Set up an isolated worktree before we start this feature"
  - "Am I already inside a linked worktree or a submodule"
  - "Create a clean workspace and verify the baseline tests pass"
metadata:
  { "openclaw": { "requires": { "bins": ["git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🌳" } }
---

# Git 工作树隔离工作区

确保工作发生在隔离的工作区里。优先用你所在平台自带的工作树工具，只有在没有原生工具时才手工建 git worktree。

**核心原则：先检测已有的隔离，再用原生工具，最后才退回 git；永远不要跟宿主环境对着干。**

**开始时声明：**「我正在用 Git 工作树技能准备隔离工作区。」

## 何时用

- 要动手改代码，但不希望污染用户当前分支
- 准备执行一份实施计划之前
- 需要同时推进多个分支
- 不确定自己现在是不是已经在隔离环境里

## 流程

### 第 0 步：检测是否已经隔离

**在创建任何东西之前，先确认你是不是已经在隔离工作区里。**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**子模块陷阱：** `GIT_DIR != GIT_COMMON` 在 git 子模块里同样成立。下结论说「已经在工作树里」之前，先排除子模块：

```bash
# 若这条命令输出了路径，说明你在子模块里，不是工作树，按普通仓库处理
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**若 `GIT_DIR != GIT_COMMON` 且不在子模块里：** 你已经在链接工作树里了，直接跳到第 2 步，**不要**再建一个。按分支状态汇报：

- 在分支上：「已在隔离工作区 `<路径>`，分支 `<名称>`。」
- 游离 HEAD：「已在隔离工作区 `<路径>`（游离 HEAD，由外部托管）。收尾时需要新建分支。」

**若 `GIT_DIR == GIT_COMMON`（或在子模块里）：** 你在普通仓库检出里。

用户是否已经在指令里表明过工作树偏好？没有的话，先征求同意再创建：

> 「要我准备一个隔离工作树吗？它能保护你当前分支不被改动。」

已声明过偏好就照做，不必再问。用户拒绝则就地工作，跳到第 2 步。

### 第 1 步：创建隔离工作区

**两种机制，按此顺序尝试。**

#### 1a. 平台原生工作树工具（首选）

用户已经同意开隔离工作区。你手上是否已经有创建工作树的能力？它可能叫 `EnterWorktree`、`WorktreeCreate`，也可能是一条 `/worktree` 命令或某个 `--worktree` 参数。有就用它，然后跳到第 2 步。

原生工具会自动处理目录位置、分支创建与清理。**有原生工具却用 `git worktree add`，会造出宿主环境看不见也管不了的幽灵状态。**

只有在确实没有原生工具时，才进入 1b。

#### 1b. 退回手工 git worktree

**仅当 1a 不适用时使用。**

**目录选择**（显式偏好永远优先于观察到的文件系统状态）：

1. 先看指令里有没有声明过工作树目录偏好，有就直接用，不必再问。
2. 再看项目里有没有现成的工作树目录：

   ```bash
   ls -d .worktrees 2>/dev/null     # 首选（隐藏目录）
   ls -d worktrees 2>/dev/null      # 备选
   ```

   找到就用；两个都在，`.worktrees` 优先。
3. 都没有，默认用项目根下的 `.worktrees/`。

**安全校验（仅针对项目内目录）——建工作树前必须确认该目录已被忽略：**

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

**若未被忽略：** 先写进 .gitignore 并提交这次改动，再往下做。
**为什么关键：** 否则会把整棵工作树的内容误提交进仓库。

**创建：**

```bash
path="$LOCATION/$BRANCH_NAME"
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

**沙箱回退：** 若 `git worktree add` 因权限被拒（沙箱限制），告诉用户沙箱挡住了工作树创建、你将就地工作，然后在原地完成安装与基线测试。

### 第 2 步：项目初始化

自动识别并执行对应的安装：

```bash
if [ -f package.json ]; then npm install; fi          # Node.js
if [ -f Cargo.toml ]; then cargo build; fi            # Rust
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi     # Python
if [ -f go.mod ]; then go mod download; fi            # Go
```

### 第 3 步：验证基线是绿的

```bash
# 用项目自己的命令，不要默认 npm test
npm test / cargo test / pytest / go test ./...
```

**测试失败：** 报告失败内容，询问是继续还是先查。
**测试通过：** 报告就绪。

## 输出契约

```
工作树就绪：<完整路径>
测试通过（<N> 个用例，0 失败）
可以开始实现 <功能名>
```

## 速查表

| 情形 | 动作 |
|------|------|
| 已在链接工作树中 | 跳过创建（第 0 步） |
| 在子模块中 | 按普通仓库处理（第 0 步的守卫） |
| 有平台原生工具 | 用它（1a） |
| 无原生工具 | 退回 git worktree（1b） |
| `.worktrees/` 已存在 | 用它（确认已忽略） |
| `worktrees/` 已存在 | 用它（确认已忽略） |
| 两者都在 | 用 `.worktrees/` |
| 都不存在 | 先查指令偏好，再默认 `.worktrees/` |
| 目录未被忽略 | 写进 .gitignore 并提交 |
| 创建时报权限错误 | 沙箱回退，就地工作 |
| 基线测试失败 | 报告失败并询问 |
| 无 package.json / Cargo.toml | 跳过依赖安装 |

## 常见借口与反驳

| 借口 | 现实 |
|------|------|
| 「一眼就知道我不在工作树里，不用检测」 | 跑第 0 步。宿主创建的隔离和子模块都能骗过肉眼，只有检测命令能定论。 |
| 「`git worktree add` 比翻找原生工具快」 | 原生工具负责位置、分支和清理。绕过它是头号错误——会留下宿主管不了的幽灵状态。 |
| 「工作树目录肯定已经被忽略了」 | 跑 `git check-ignore`。没被忽略就会把整棵树提交进仓库。 |
| 「目录叫什么都一样」 | 显式指令 > 现有项目内目录 > `.worktrees/` 默认值。 |
| 「环境是新的，基线测试可以先跳过」 | 基线不干净，之后每一次失败都说不清是谁造成的。先跑，失败了让用户定夺。 |

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `using-git-worktrees`（MIT）。改动见 ATTRIBUTION.md。
