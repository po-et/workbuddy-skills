# WorkBuddy 实战蓝皮书 · 社区案例集 投稿包

目标仓库：**AlephAITech/WorkBuddyGuide**（3067 ★，站点 workbuddy.homes，社区维护，非腾讯官方；MIT 协议，默认分支 `main`）
投稿路径：`docs/cases/submissions/<slug>/index.md`

本文档已于 **2026-09-18** 用 `gh api` 只读核对过上游真实约定（不是从 `docs/channels.md` 的二手记录推断）。每条结论都标了依据；没查到依据的都标了「需确认」，不当事实用。

## 本目录里有什么

| 路径 | 说明 |
|---|---|
| `release-readiness-gate/index.md` | 案例正文，已按下方「已核实的上游约定」改写，可直接复制成上游的 `docs/cases/submissions/release-readiness-gate/index.md` |
| `PR-BODY.md` | PR 描述，已改写成 `.github/PULL_REQUEST_TEMPLATE/case.md` 的真实结构，`gh pr create --body-file` 直接用 |
| 案例 #1（迭代周报） | 还没做蓝皮书版，不在本次范围内 |

## 结论先说：上游接受这种投稿

`docs/cases/submissions/` 目录确实存在，已有 7 篇合并的社区投稿，且规则文档（`CONTRIBUTING.md` → 网站 [Case 投稿指南](https://workbuddy.homes/community/case-contributing)，源文件 `docs/community/case-contributing.md`）明确写着"真实的 WorkBuddy 实践案例请优先提交到 `docs/cases/submissions/<case-slug>/`"，流程就是 fork → 填模板 → PR，**没有**"先开 issue"之类的前置门槛。近期同类 PR 有合并的也有仍开着的，维护者会正常审核，不是走过场。

## 已核实的上游约定

### frontmatter 字段集（依据：`docs/community/case-contributing.md` 明文 + `.github/CASE_TEMPLATE.md` + 7 篇已合并投稿逐一核对）

必填字段（guide 原话："`title`、`summary`、`author`、`date`、`category`、`difficulty` 和 `skills` 是必填项。缺少必填字段时，网站构建会失败"）：

| 字段 | 取值风格 | 依据 |
|---|---|---|
| `title` | 完整句子，可以很长；**必须和正文 H1 逐字一致**（3 篇全文核对全部一致） | 7 篇实例 |
| `summary` | 一句话概括结果 | guide + 7 篇实例 |
| `author` | **GitHub 用户名**（`stephenlzc`、`nikola`、`JZCreative`、`KevinYoung-Kw`），不是昵称或显示名；唯一例外是官方示例案例 `author: WorkBuddy Guide 编辑组` | 7 篇实例（6/7 是真实 GitHub 用户名） |
| `date` | 带引号的 `"YYYY-MM-DD"` | 7 篇实例 |
| `category` | 自由文本，**没找到强制枚举的证据**（guide 只给了一个示例值，不是 schema）。已合并案例出现过的值：数据分析（×2）、内容创作、资讯整合、创意开发、职场效率、知识管理 | 7 篇实例，非穷举 |
| `difficulty` | 三档：入门（×4）、中等（×1）、进阶（×3），像是固定枚举但同样没找到 schema 文件确认 | 7 篇实例，非穷举 |
| `skills` | **列的是读者会去装的那个 Skill 名（1–3 个）**，不是把一个 Skill 内部的子模块/子脚本都列出来。例：`xlsx`、`wechat-publisher`、`AIHot`、或 `浏览器`/`本地文件读写`/`Python 代码执行` 这类 WorkBuddy 内置能力名 | 7 篇实例 |
| `tags` | guide 没把它列进"必填"，但 7 篇实例全都写了，5–6 个短标签 | 7 篇实例 |
| `aside: false` / `outline: false` | guide 的字段说明里没提，但 `CASE_TEMPLATE.md` 和 **7 篇实例全部**带了这两行 | 模板 + 7 篇实例 |

### 内容结构（依据：`docs/community/case-contributing.md` "内容结构"一节 + `.github/CASE_TEMPLATE.md`）

Guide 明文要求正文至少包含这 11 个部分（原文顺序）：**场景描述 → 想要完成的任务 → 使用的 Skill → 前置条件 → 在 WorkBuddy 中的操作 → 提示词或任务指令 → 在 WorkBuddy 中的效果 → 验收标准 → 遇到的问题 → 安全与限制 → 可以怎样复用**。

实测：`annual-report-digital-transformation`、`tea-shop-sales-analysis`、`jz-2025-showreel` 三篇严格按这个顺序用这些标题（一字不差，无中文数字编号）；`wechat-ima-knowledge` 基本一致（多了一节）；`wechat-format-publish`/`daily-ai-news` 把"遇到的问题"换成了"常见问题"仍然合并了；`vibe-resume` 明显偏离标准结构（换了一套口语化标题）也合并了——**说明有弹性，但最贴近 guide 原文、最像"标准答案"的还是那三篇**。

**我们的 `index.md` 已经改成这 11 节的标题和顺序**（原来是"一、场景 / 二、WorkBuddy 侧的配置 / …"六段式，现在拆成了 11 节，新增了此前没有的"前置条件""验收标准""遇到的问题"三节，"使用的 Skill"也改成了 guide 要求的三列表格）。

### 目录结构与图片（依据：`docs/community/case-contributing.md` + `.github/CASE_TEMPLATE.md` + 7 篇实例）

```text
docs/cases/submissions/<slug>/
├── index.md
└── assets/          # 截图/GIF，正文用相对路径 ./assets/xxx.png 引用
```

**⚠️ 我们目前没有任何图片，这是本次投稿最大的风险点，不是"需确认"，是已经找到了负面证据**：PR #14（`meeting-audio-diarization`，2026-07-20 提交至今仍未合并）唯一的评审意见就是维护者 **liucongg**（与 `docs/channels.md` 记录的"刘聪NLP"一致，本次已交叉验证）留言"是否可以补充在 workbuddy 里的截图"，此后再无进展。7 篇已合并案例**全部**带截图。是否要在提交前补至少一张终端输出截图（哪怕不是 WorkBuddy GUI 截图），请你决定；PR-BODY.md 里已经如实标注了这一项未完成，不会假装有图。

### PR 与提交约定（依据：`.github/PULL_REQUEST_TEMPLATE/case.md`、`.github/pull_request_template.md`（默认模板，未采用）、近 20 条 PR 的标题/合并记录）

- PR 描述必须用 **`.github/PULL_REQUEST_TEMPLATE/case.md`**（"Case 基本信息 / 为什么值得收录 / 完整性检查 / 结果证明 / 编辑授权" 五段），不是仓库根目录那份通用 `pull_request_template.md`。`PR-BODY.md` 已经按这个真实模板重写。
- PR 标题：4 篇已合并案例分别用了 `Add case: <标题>`、`Case: <标题>`、`提交社区 Case：<标题>`、`新增 Case：<标题>` 四种前缀，**没有统一成 `docs(cases): ...` 这种 conventional-commit 格式**——这是我们原来 README 里的猜测，已证伪。两篇合并 PR 的 squash 提交信息最终都变成了 `Add case: <标题>`（像是维护者合并时统一改的），但这是维护者的事，我们只需要选一个贴合惯例的原始 PR 标题，本文档选 `Case: <标题>`。
- 分支命名：已见的 case PR 分支名清一色 `case/<slug>`（含仍开着的几个），和我们原来的计划一致，不用改。
- 审核维度：guide 原话"社区案例主要审核真实性、完整性、安全性和可读性"（`docs/channels.md` 记录的"完整性/安全性/可读性"三项少了"真实性"，已在本文档订正）。
- 没有强制"先开 issue"。`content.yml` issue 模板是给内容建议用的，guide 的提交步骤直接是 fork → 模板 → PR。

### 本地构建（依据：`package.json` scripts 字段 + `CONTRIBUTING.md`）

`CONTRIBUTING.md` 要求的是 `npm install` → `npm run docs:build` → `npm run docs:preview`；`package.json` 确认这三个 script 名真实存在（`docs:build` = `vitepress build docs`，`docs:preview` = `vitepress preview docs --host 127.0.0.1`，另有 `docs:dev` 用于本地热更新）。`.nvmrc` 指定 Node `22`。

## 还缺什么信息（列出来问你，没有编）

1. **截图**：如上，assets/ 目前是空的。要不要补至少一张终端截图？
2. **`category: 研发效能`**：没找到强制枚举定义文件，无法 100% 确认这个值会被接受；从 7 个已合并案例的自由文本风格看应该没问题，但这是"据观察推测"，不是"查到规则确认"。
3. **是否有 Windows 环境验证**：正文"前置条件"里已如实标注"未在 Windows 上验证"。如果你在其他系统跑过，可以告诉我补充进去。

其余此前担心的点（default 分支是不是 main、frontmatter 字段集、配图放哪、目录命名规则）都已经用 `gh api` 实际查到，不再是"需确认"。

## 提 PR 的完整命令序列

变量先定好，后面所有命令复用：

```bash
export PATH="/Library/Developer/CommandLineTools/usr/bin:$PATH"   # 否则系统 git 被 Xcode 许可拦截，gh 会报错

GIT=/Library/Developer/CommandLineTools/usr/bin/git
SLUG=release-readiness-gate
SRC=/Users/limit/AI/My-Research/workbuddy-skills/docs/articles/bluebook-submission
UPSTREAM=AlephAITech/WorkBuddyGuide
ME=po-et                      # GitHub 账号（gh auth status 已确认登录为 po-et）
WORK=~/code/WorkBuddyGuide    # fork 的本地克隆位置
BASE=main                     # 已用 gh api repos/$UPSTREAM --jq '.default_branch' 确认，非 master
```

### 第 0 步：执行前快速复核（上游可能在我们核对之后有变动，建议重跑一次）

```bash
gh api "repos/$UPSTREAM" --jq '.default_branch'                              # 应该还是 main
gh api "repos/$UPSTREAM/contents/docs/cases/submissions" --jq '.[].name'     # 确认 release-readiness-gate 这个 slug 还没被人用掉
```

### 第 1 步：fork + 克隆

```bash
gh repo fork "$UPSTREAM" --clone=false                 # 已 fork 过会提示并跳过
$GIT clone "https://github.com/$ME/WorkBuddyGuide.git" "$WORK"
cd "$WORK"
$GIT remote add upstream "https://github.com/$UPSTREAM.git"
$GIT fetch upstream
```

### 第 2 步：开分支

```bash
cd "$WORK"
$GIT checkout -B "case/$SLUG" "upstream/$BASE"
```

### 第 3 步：复制投稿目录

```bash
mkdir -p "$WORK/docs/cases/submissions/$SLUG"
cp -R "$SRC/$SLUG/." "$WORK/docs/cases/submissions/$SLUG/"
ls -la "$WORK/docs/cases/submissions/$SLUG"             # 目前应只有 index.md（没有 assets/，见上面的风险提示）
head -25 "$WORK/docs/cases/submissions/$SLUG/index.md"  # 确认 frontmatter 没被破坏
```

### 第 4 步：本地构建验证（`CONTRIBUTING.md` 要求提交前确认构建成功，不是可选项）

```bash
cd "$WORK"
nvm use 22 2>/dev/null || true    # 仓库 .nvmrc 指定 Node 22
npm install
npm run docs:build                # 必须成功；同时检查内部链接、图片是否都能访问
npm run docs:preview              # 打开预览，人工看一眼 /cases/submissions/release-readiness-gate/ 页面渲染
```

### 第 5 步：提交并推送

```bash
cd "$WORK"
$GIT add "docs/cases/submissions/$SLUG"
$GIT -c user.name="Captain" -c user.email="42566883+po-et@users.noreply.github.com" commit -m "Add case: 上线前五分钟体检：把 Dockerfile / K8s / SQL / OpenAPI / .env 五项检查串成一条 CI 门禁

- 五项检查（Dockerfile / K8s / SQL 迁移 / OpenAPI / .env）一条命令跑完
- 全部命令与输出为 2026-09-18 本机实跑，演示项目仅用 example.com
- 含误报、漏报与 CI 假绿灯三处边界说明

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
$GIT push -u origin "case/$SLUG"
```

（`Co-Authored-By` 那行是我这边的署名规范；不想带就删掉再提交，不影响投稿。）

### 第 6 步：开 PR

PR 标题用已核实的惯例（`Case: <完整标题>`，见上文"PR 与提交约定"），正文用已经按真实模板重写的 `PR-BODY.md`：

```bash
gh pr create \
  --repo "$UPSTREAM" \
  --base "$BASE" \
  --head "$ME:case/$SLUG" \
  --title "Case: 上线前五分钟体检：把 Dockerfile / K8s / SQL / OpenAPI / .env 五项检查串成一条 CI 门禁" \
  --body-file "$SRC/PR-BODY.md"
gh pr view --repo "$UPSTREAM" --web     # 打开看一眼渲染
```

### 第 7 步：跟进

```bash
gh pr status --repo "$UPSTREAM"                     # 看维护者是否有 review
gh pr comment <PR号> --repo "$UPSTREAM" --body "…"  # 回复修改意见
```

合并后把案例页 URL 回填到 `docs/submission-checklist.md` 的「内容渠道投稿」一节，并把链接加进仓库 README。

## 顺手可做的两件事

- 维护者刘聪NLP（GitHub 账号 `liucongg`，本次已通过 PR #14 的真实评论交叉验证，和 `docs/channels.md` 的记录一致）在 PR 上出现过至少一次实际审核动作。PR 提了之后，`docs/channels.md` 记录的微信群路径仍然值得走一遍，比干等要快。
- 同一篇的腾讯云社区版（带截图）发布后，可以在 PR 描述里补一条外链，增加「完整性」这一项的分数（guide 原话里"真实性/完整性/安全性/可读性"四项审核维度之一）。
