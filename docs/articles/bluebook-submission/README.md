# WorkBuddy 实战蓝皮书 · 社区案例集 投稿包

目标仓库：**AlephAITech/WorkBuddyGuide**（站点 workbuddy.homes，社区维护，非腾讯官方）
投稿路径：`docs/cases/submissions/<slug>/index.md`（依据 `docs/channels.md` 与 `docs/submission-checklist.md` 的记录）
审核维度：完整性 / 安全性 / 可读性（依据 `docs/channels.md`）

## 本目录里有什么

| 路径 | 说明 |
|---|---|
| `release-readiness-gate/index.md` | 案例 #2 的蓝皮书体例版（≈2,350 中文字），可直接复制成上游的 `docs/cases/submissions/release-readiness-gate/index.md` |
| `PR-BODY.md` | PR 描述草稿，`gh pr create --body-file` 直接用 |
| 案例 #1（迭代周报） | 还没做蓝皮书版；上游 slug 计划用 `git-iteration-report`（见 `../02-案例-…迭代周报.md` 的投稿注释） |

## 【需确认】三件事，提 PR 之前先核对

我手上**没有**上游 CONTRIBUTING 的原文，以下按现有记录推断，动手前用第 0 步的命令核实：

1. **frontmatter 字段集**：`release-readiness-gate/index.md` 沿用了案例 #1 同一套字段（`title / summary / author / date / category / difficulty / skills / tags`）。依据只是我们自己案例 #1 的写法，**不是**上游文档；上游若有必填字段（如 `sidebar`、`order`、`cover`、`slug`）或对 `category` / `difficulty` 有取值枚举，按上游的来。
2. **默认分支名**：命令里写的是 `main`，需确认不是 `master`。
3. **配图约定**：`index.md` 目前**不引用任何图片**，这样即使截图没到位也能提。若要配图，需要确认上游把图放哪（同目录 `./assets/` 还是全站 `public/`）以及引用写法；确认后把 `docs/articles/03-assets/` 里的图复制进去并加相对引用。

另外，腾讯云征集与蓝皮书是两个独立渠道，**同一篇可兼投**（依据 `docs/channels.md`）；蓝皮书这份已按体例改写，不必等腾讯云那边定稿。

## 提 PR 的完整命令序列（不要直接跑，先做第 0 步）

变量先定好，后面所有命令复用：

```bash
SLUG=release-readiness-gate
SRC=/Users/limit/AI/My-Research/workbuddy-skills/docs/articles/bluebook-submission
UPSTREAM=AlephAITech/WorkBuddyGuide
ME=po-et                      # GitHub 账号
WORK=~/code/WorkBuddyGuide    # fork 的本地克隆位置
```

### 第 0 步：核对上游约定（只读，先跑这几条）

```bash
gh auth status                                         # 确认已登录且有 repo 权限
gh repo view "$UPSTREAM"                               # 看仓库说明与默认分支
gh api "repos/$UPSTREAM" --jq '.default_branch'        # 默认分支名（下面 BASE 用它）
gh api "repos/$UPSTREAM/contents/docs/cases/submissions" --jq '.[].name'   # 已有投稿的 slug 命名风格
gh api "repos/$UPSTREAM/contents/CONTRIBUTING.md" --jq '.content' | base64 -d | head -80
# 抄一份现成案例的 frontmatter 作对照（把 <existing-slug> 换成上一条列出来的任一个）
gh api "repos/$UPSTREAM/contents/docs/cases/submissions/<existing-slug>/index.md" --jq '.content' | base64 -d | head -30
```

核对完，如果字段集和我们的不一致，**改 `release-readiness-gate/index.md` 的 frontmatter**，别改上游。

### 第 1 步：fork + 克隆

```bash
BASE=$(gh api "repos/$UPSTREAM" --jq '.default_branch')
gh repo fork "$UPSTREAM" --clone=false                 # 已 fork 过会提示并跳过
git clone "https://github.com/$ME/WorkBuddyGuide.git" "$WORK"
cd "$WORK"
git remote add upstream "https://github.com/$UPSTREAM.git"
git fetch upstream
```

### 第 2 步：开分支

```bash
cd "$WORK"
git checkout -B "case/$SLUG" "upstream/$BASE"
```

### 第 3 步：复制投稿目录

```bash
mkdir -p "$WORK/docs/cases/submissions/$SLUG"
cp -R "$SRC/$SLUG/." "$WORK/docs/cases/submissions/$SLUG/"
ls -la "$WORK/docs/cases/submissions/$SLUG"             # 应只有 index.md
head -20 "$WORK/docs/cases/submissions/$SLUG/index.md"  # 确认 frontmatter 没被破坏
```

### 第 4 步（可选）：本地起站点看一眼渲染

```bash
cd "$WORK"
cat package.json                       # 先看 scripts 里真实的命令名，下面两条按它改
npm ci
npm run docs:dev                       # VitePress 常见是 docs:dev / dev；【需确认】
# 浏览器打开 http://localhost:5173/cases/submissions/release-readiness-gate/ 之类的路径
```

### 第 5 步：提交并推送

```bash
cd "$WORK"
git add "docs/cases/submissions/$SLUG"
git commit -m "docs(cases): 新增案例「上线前五分钟体检——把五项检查串成一条 CI 门禁」

- 五项检查（Dockerfile / K8s / SQL 迁移 / OpenAPI / .env）一条命令跑完
- 全部命令与输出为 2026-09-18 本机实跑，演示项目仅用 example.com
- 含误报、漏报与 CI 假绿灯三处边界说明

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push -u origin "case/$SLUG"
```

（`Co-Authored-By` 那行是我这边的署名规范；你若不想带，删掉再提交，不影响投稿。）

### 第 6 步：开 PR

```bash
gh pr create \
  --repo "$UPSTREAM" \
  --base "$BASE" \
  --head "$ME:case/$SLUG" \
  --title "docs(cases): 新增案例「上线前五分钟体检——把五项检查串成一条 CI 门禁」" \
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

- 维护者有微信群（依据 `docs/channels.md`：刘聪NLP、袋鼠帝、甲木、Joy）。PR 提了之后在群里说一句比干等要快。
- 同一篇的腾讯云社区版（带截图）发布后，可以在 PR 描述里补一条外链，增加「完整性」这一项的分数。
