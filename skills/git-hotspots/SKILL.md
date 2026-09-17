---
name: git-hotspots
description: 代码热点分析、从 git 历史找改动最频繁的高风险文件、知识集中度与 bus factor、只有一个人懂的模块、总是一起改的文件（隐性耦合）、重构优先级、技术债定位、团队知识风险。当用户说「这个仓库哪些文件最容易出问题」「哪些模块只有一个人在维护」「改 A 总要改 B 是不是耦合了」「重构从哪开始」「出一份代码热点报告」时使用。附纯标准库脚本 scripts/git_hotspots.py：只读 git log，按「改动次数 × log2 行数」给出热点文件（含作者数与主要作者占比）、目录级 bus factor（覆盖一半改动所需人数）、跨目录共同修改的文件对与耦合率；支持 --since、--path、Markdown 报告与 --json。
author: Captain
version: 0.1.0
display_name: "代码热点与知识集中度"
display_name_en: "Git Hotspots"
description_zh: "用 git 历史回答三个问题：哪些文件改得多又大（缺陷高发）、哪些目录只有一个人在改（bus factor）、哪些文件总是一起改（隐性耦合）；输出 Markdown 报告；纯 Python 标准库，只读。"
description_en: "Answer three questions from git history: which files change often and are large (defect-prone), which directories depend on one person (bus factor), which files always change together (hidden coupling); Markdown report; pure Python stdlib, read-only."
examples_zh:
  - "分析最近一年的 git 历史，找出代码热点"
  - "哪些目录的 bus factor 是 1"
  - "看看 src/ 下哪些文件总是一起改"
examples_en:
  - "Analyze the last year of git history for code hotspots"
  - "Which directories have a bus factor of 1?"
  - "Which files under src/ always change together?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔥" } }
---

# 代码热点与知识集中度

git 历史里藏着代码库的体温：改得最勤的大文件是缺陷高发区，只有一个人改的目录是离职风险，总是一起改的文件是画错的边界。脚本只读 git log，几秒出报告。

## 用法

```bash
python3 scripts/git_hotspots.py                          # 最近 12 个月
python3 scripts/git_hotspots.py --since 6.months --path src/ --top 30 --md hotspots.md
python3 scripts/git_hotspots.py --min-pair 8 --json
```

## 报告三部分

1. **热点文件**：分数 = 改动次数 × log2(行数)。分数高说明既复杂又不稳定；作者数多而主要作者占比低说明谁都在碰、没人真正负责。
2. **知识集中度**：目录级 bus factor = 覆盖一半改动所需的最少人数。1 表示这块基本靠一个人；同时给出主要作者占比。
3. **隐性耦合**：跨目录、共同修改 ≥ N 次的文件对，耦合率 = 共同修改次数 / 两者中较少的改动次数。100% 表示改其一必改其二。

## 流程

1. 跑报告；把热点 Top 10 与近期缺陷列表对照，通常高度重合——这就是补测试与拆分的优先级。
2. bus factor = 1 且改动量大的目录：安排结对、代码走读、补 README/ADR；评审时要求第二个人参与。
3. 高耦合率的文件对：看是否该合并成一个模块、或抽出共享抽象，配合「深模块设计」技能讨论边界。
4. 每季度重跑一次，看热点是否在降温、bus factor 是否在上升。

## 边界

- 只统计当前仍存在的文件为热点；lockfile、压缩产物、图片等已跳过（脚本顶部 `SKIP`）。
- 行数按当前工作树读取，不是历史平均。
- 大提交（> 30 个文件）不参与耦合统计，避免批量格式化污染结果；作者按 git 作者名，同一人多个名字需先配置 .mailmap。
