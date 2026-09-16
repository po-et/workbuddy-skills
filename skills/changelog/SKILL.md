---
name: changelog
description: 从 Git 提交历史生成 Changelog、发布说明、Release Notes、版本更新日志、更新公告。当用户要「写 changelog」「生成发布说明」「这个版本改了什么」「整理 release notes」「更新日志怎么写」「从上个 tag 到现在的变更」「给用户看的版本说明」，或需要按 Keep a Changelog 格式分组（新增/修复/性能/重构/文档/破坏性变更）、需要把 Conventional Commits 转成用户视角的描述时使用。脚本按 tag 区间读取 git log 并分组，每条附短 hash；不规范的提交进「其他」等待改写而不是被丢掉；不会编造提交里没有的功能。
author: Captain
version: 0.1.0
display_name: "Changelog 生成器"
display_name_en: "Changelog Generator"
description_zh: "按 tag 区间读取 git 提交，按 Keep a Changelog 分组生成发布说明草稿，每条附 hash，不规范提交单独列出待改写。"
description_en: "Read commits between tags, group them Keep-a-Changelog style into release notes with hashes; non-conventional commits are listed for rewording, never dropped."
examples_zh:
  - "生成从 v1.2.0 到现在的 changelog"
  - "把这个版本的提交整理成给用户看的发布说明"
  - "按新增/修复/破坏性变更分组写一份更新日志"
examples_en:
  - "Generate a changelog from v1.2.0 to HEAD"
  - "Turn this release's commits into user-facing release notes"
  - "Write an update log grouped by added/fixed/breaking"
metadata:
  { "openclaw": { "requires": { "bins": ["git", "python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📜" } }
---

# Changelog 生成器

把一个版本区间内的提交，整理成**用户视角、可溯源**的发布说明。格式：Keep a Changelog；分组依据：Conventional Commits。

## 核心原则

1. **每条可溯源。** 每个条目附短 hash，用户视角的措辞可以改，hash 不能丢。
2. **不丢提交。** 不按规范写的提交进「其他」小节等待改写，而不是悄悄消失；改写后仍附 hash。
3. **用户视角。** "修复 NPE" → "修复导入空文件时崩溃的问题"。技术细节留给 hash 背后的提交。
4. **破坏性变更置顶**，并写清迁移方法。

## 执行流程

### 第 1 步：生成骨架

```bash
python3 {baseDir}/scripts/build_changelog.py --repo <仓库路径> --from <起点 tag 或提交> --to HEAD --version <版本号> --out out/CHANGELOG-draft.md
```

- 不给 `--from` 时自动取最近一个 tag；仓库没有 tag 会提示并使用全部历史。
- 默认隐藏 build / deps / ci / chore / test 类提交，`--include-chore` 显示；`--author` 每条附作者；`--lang en` 英文小节名；`--no-issues` 不提取工单号（提交里引用外部 issue 时用）。
- 输出末尾的 HTML 注释列出了缺口：隐藏了几条、多少条不规范。

### 第 2 步：改写（这一步由你做）

- 「其他」小节逐条改成用户视角的一句话，归入正确分组；不确定归属就问用户。
- 同一 scope 的多条小修合并成一条，hash 并列。
- 破坏性变更补迁移步骤（改什么配置、跑什么命令）。
- 给不同读者两版：给用户的（只保留 新增/修复/破坏性变更）、给团队的（全部）。

### 第 3 步：交付

Markdown，可直接粘进 `CHANGELOG.md` 顶部或 GitHub Release 描述。

## 输出契约

```
## [x.y.z] - YYYY-MM-DD
<sub>范围与提交数</sub>
### ⚠ 破坏性变更（若有）
### 新增
### 修复
### 性能
### 重构
### 文档
<!-- 缺口说明 -->
```

## 常见问题

**提交信息全是 "update"？** 全部落在「其他」，让用户逐条口述或读 diff 改写；同时建议团队用本系列的「Git 提交信息生成器」把源头规范化。
**要给公众号/公告用？** 只取「新增」「修复」两节，去掉 hash，加一句升级方式。
