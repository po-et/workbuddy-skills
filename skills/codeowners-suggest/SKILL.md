---
name: codeowners-suggest
description: 生成 CODEOWNERS、根据 git 历史找每个目录的实际维护者、代码归属、评审人自动分配、谁该 review 这个目录、补齐缺失的代码负责人、GitHub / GitLab CODEOWNERS 草稿。当用户说「帮我生成一份 CODEOWNERS」「这个目录应该谁来评审」「按提交历史看各模块的负责人是谁」「补一下代码归属配置」时使用。附纯标准库脚本 scripts/codeowners_suggest.py：只读 git log，按目录（可调深度）统计各作者改动占比，占比达标者列为 owner（最多 N 人），父子目录 owner 相同自动合并规则，支持作者名到 @handle 的映射文件，输出带统计注释的 CODEOWNERS 草稿或 JSON。也覆盖「最近一年的提交」「实际上是谁在维护」「作者名映射成」这类说法。
author: Captain
version: 0.1.1
display_name: "CODEOWNERS 建议"
display_name_en: "CODEOWNERS Suggest"
description_zh: "从 git 历史推导各目录的实际维护者，生成带占比注释的 CODEOWNERS 草稿（GitHub/GitLab 通用），支持作者到 @handle 映射与父子规则合并；纯 Python 标准库，只读。"
description_en: "Derive each directory's de-facto maintainers from git history and generate an annotated CODEOWNERS draft (GitHub/GitLab), with author-to-@handle mapping and parent/child rule folding; pure Python stdlib, read-only."
tags:
  - "CODEOWNERS"
  - "代码归属"
  - "评审人分配"
  - "git 历史分析"
  - "代码治理"
examples_zh:
  - "根据最近一年的提交生成 CODEOWNERS 草稿"
  - "src/payment 目录实际上是谁在维护"
  - "把作者名映射成 GitHub 账号后输出到 .github/CODEOWNERS"
examples_en:
  - "Generate a CODEOWNERS draft from the last year of commits"
  - "Who actually maintains src/payment?"
  - "Map author names to GitHub handles and write .github/CODEOWNERS"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧭" } }
---

# CODEOWNERS 建议

「这个目录谁来评审」不该靠猜。脚本从 git 历史算出每个目录的实际维护者与占比，生成 CODEOWNERS 草稿；人工确认、映射账号后启用，PR 就能自动指派评审人。

## 何时用
仓库没有 CODEOWNERS 或已过期（人员转岗、目录重组）、想按提交历史而不是印象来分配评审人时用。团队已经很清楚谁该审哪块、只是想手写几行规则时，不需要跑脚本。

## 产出
一份可直接放进 `.github/CODEOWNERS`（或 `.gitlab/CODEOWNERS`）的草稿文件：每条规则上方带改动次数、作者数与各 owner 占比的注释；未映射账号的作者以 `<名字>` 占位并在文件末尾列出。`--json` 输出同样的数据供脚本消费。

## 用法

```bash
python3 scripts/codeowners_suggest.py                                  # 最近 12 个月，目录深度 2
python3 scripts/codeowners_suggest.py --since 6.months --depth 3 --min-share 30 --max-owners 2
python3 scripts/codeowners_suggest.py --map authors.json --out .github/CODEOWNERS
python3 scripts/codeowners_suggest.py --json
```

`authors.json`：`{"张三": "@zhangsan", "Li Si": "@lisi"}`；未映射的作者以 `<名字>` 占位并在末尾列出。

## 流程

1. 跑脚本看草稿：每条规则上方注释了改动次数、作者数与各 owner 占比。
2. 人工调整：占比高但已转岗的人换掉；bus factor 为 1 的目录补一位候补 owner（可配合「代码热点」技能）；跨团队目录用团队账号（`@org/team-payments`）。
3. 提供 `--map` 生成最终文件：GitHub 放 `.github/CODEOWNERS`（或根目录 / docs/），GitLab 放 `.gitlab/CODEOWNERS`；GitLab 的分节语法需手动加。
4. 在分支保护里开启「需要 code owner 评审」，并每季度重跑一次对比差异。

## 规则说明

- 目录按 `--depth` 聚合（默认 2 级）；根目录零散文件归到 `*`。
- 作者占比 ≥ `--min-share`（默认 25%）且排名前 `--max-owners` 的列为 owner；没人达标时取第一名。
- 子目录 owner 与父目录完全相同时省略子规则，保持文件精简。
- 合并提交不计；作者名以 git 记录为准，多名字请先配 .mailmap。

## 边界

- 改动多不等于最懂：批量格式化、机器人提交会拉高占比，必要时用 `.mailmap` 或先过滤。
- 只读 git，不调用平台 API，不会自动提交或修改分支保护。
