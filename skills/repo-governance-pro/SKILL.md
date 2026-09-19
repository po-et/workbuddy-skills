---
name: repo-governance-pro
description: 代码仓库治理助手，覆盖「代码写完之后仓库怎么管」的整片活：技术债盘点（TODO / FIXME / HACK 有多少、谁欠的、欠多久了）、代码热点与缺陷高发文件、知识集中度与 bus factor、隐性耦合、分支列表几百条怎么清、分支策略与版本 tag、代码归属与 CODEOWNERS、评审人怎么定、评审流程怎么走、收到评审意见怎么回、提交信息规范与 Conventional Commits、PR / MR 描述怎么写、新人接手陌生仓库从哪看起、仓库体检与季度大扫除。当用户提到技术债、TODO、重构优先级、代码热点、谁维护这块、bus factor、分支清理、删分支、陈旧分支、CODEOWNERS、评审、code review、CR、PR 描述、MR 描述、提交规范、commit lint、仓库治理、接手项目等任一话题，但不确定该用哪个专门技能时使用。不做：直接改代码。
author: Captain
version: 0.1.0
display_name: "代码仓库治理助手"
display_name_en: "Repo Governance Pro"
description_zh: "一个入口管住仓库本身：技术债盘点、代码热点与知识集中度、分支清理、代码归属与 CODEOWNERS、评审流程、提交规范、PR 描述；按意图路由到带脚本的精专子技能，只读不改代码。"
description_en: "One entry point for the repository itself: tech-debt inventory, code hotspots and bus factor, branch cleanup, ownership and CODEOWNERS, review workflow, commit conventions, PR descriptions; routes to focused sub-skills, read-only."
tags:
  - "技术债"
  - "代码评审"
  - "分支清理"
  - "代码热点"
  - "提交规范"
  - "CODEOWNERS"
  - "PR 描述"
  - "仓库治理"
examples_zh:
  - "刚接手一个五年的老仓库，想先看代码热点和谁在维护，从哪下手"
  - "分支清理和技术债盘点都没人做过，帮我来一次仓库治理大扫除"
  - "团队想立提交规范和评审规矩，从哪一步开始落地"
examples_en:
  - "Just inherited a five-year-old repo, where do I look first"
  - "Hundreds of stale branches and unaudited tech debt, run a repo cleanup"
  - "We want commit conventions and a review process, where do we start"
metadata:
  { "openclaw": { "requires": { "bins": ["git", "python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🏛️" } }
---

# 代码仓库治理助手

定位一句话：**写代码交给编程助手，管仓库的活交给我。**
什么时候轮到我：问题的主语不是某一行代码，而是这个仓库——债有多少、谁在扛、分支能不能删、评审怎么走、提交与 PR 怎么写。先判断用户在治理的哪一环，用下表的方法直接干；表里的子技能已安装就调用它（更完整、带脚本），没安装就按本页的精简方法做，并告诉用户可以在 SkillHub 搜索安装。带脚本的子技能都是纯 Python 标准库，`python3` 直接跑，只读 git 历史，不改任何文件。

## 意图 → 方法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 这仓库欠了多少债、该先还哪笔 | TODO / FIXME / HACK 按类型、目录、作者、年龄统计，给优先处理清单与 Markdown 报告 | 技术债标记盘点 `todo-debt-scan` |
| 哪些文件最容易出事、谁在扛这个模块 | git 历史算改动频次与改动量找缺陷高发文件、单人维护目录（bus factor）、总是一起改的隐性耦合 | 代码热点与知识集中度 `git-hotspots` |
| 模块越改越难改、想要一份架构体检 | 找出把浅模块变深的重构机会，出带前后对比的 HTML 报告，落成 ADR | 架构加深体检 `architecture-deepening-zh` |
| 分支几百条，哪些能删 | 分已合并可删 / 陈旧需确认 / 受保护保留三类，附年龄、作者、领先提交数，生成待人工审阅的删除脚本 | git 分支清理助手 `git-branch-cleanup` |
| 分支怎么开、什么时候合、版本怎么打 | 主干开发 + 短分支 + 原子提交；tag 走语义化版本；worktree 并行 | Git 工作流与版本管理 `git-workflow-zh` |
| 这个目录该谁评审、CODEOWNERS 怎么写 | 从 git 历史推导实际维护者，生成带占比注释的 CODEOWNERS 草稿，支持父子规则合并 | CODEOWNERS 建议 `codeowners-suggest` |
| 提交信息乱七八糟、想立规范 | 按 Conventional Commits 体检一个提交区间（type、scope、首行宽度、BREAKING CHANGE），逐条给改法 | 提交信息规范检查 `git-commit-lint` |
| 这次改动的提交信息怎么写 | `type(scope)!: subject ≤50 字`，body 讲 why，破坏性变更用 `!` | Git 提交信息生成器 `commit-message-cc` |
| PR 描述懒得写、评审人看不懂改了啥 | 从提交与 diff 分组改动，标出迁移 / 依赖 / CI / 配置风险，关联工单，补测试与评审清单 | PR 描述生成 `pr-description` |
| 帮我评审这个 PR | 标准轴（仓库规范与坏味道）与 spec 轴（做的是不是要的）分开报，不合并的理由单独排序 | 代码评审（双轴）`code-review-zh` |
| 要更细的评审维度 | 正确性 / 可读性 / 架构 / 安全 / 性能五轴，意见分级前缀，结构性问题给具名修法 | 五轴代码评审 `code-review-five-axis-zh` |
| 我收到一堆评审意见，怎么回 | 当技术输入不当社交场合：看不懂就停下来问，该反驳用技术理由，逐条实施逐条验证 | 接收代码评审意见 `code-review-response-zh` |
| 这段代码太绕了 | 行为不变的前提下化简，一次一改跑一次测试 | 代码化简（行为不变）`code-simplification-zh` |

## 输出契约

1. **每条结论附来源**：文件路径加行号、commit 短 hash、作者与日期、分支名。拿不到来源就写「待确认」。
2. **不下最终结论的事**：这个分支能不能删、这笔债要不要还、这个 PR 能不能合——只列证据与选项，决定权在人。
3. **只读**：不删分支、不改代码、不动 CODEOWNERS 与钩子；需要执行的删除或改写一律输出成脚本，人工审阅后自己跑。
4. **点名要克制**：热点与 bus factor 是流程信号不是绩效材料，按目录与模块说，不按人排名。

## 典型组合流程

**① 接手陌生仓库的第一周**
`git-hotspots` 找出改得最勤的目录与单人维护区 → `todo-debt-scan` 看这些目录里积了什么债 → `codeowners-suggest` 确认能问谁 → 汇成一页「仓库现状」，含三个最危险的地方与各自的证据。

**② 团队规范落地**（别一次上五条规矩）
`git-commit-lint` 先体检最近 200 条提交，用真实数据说明问题 → 定最小 type / scope 清单 → 装 commit-msg 钩子并进 CI 门禁 → `pr-description` 生成的结构反过来当 PR 模板 → `codeowners-suggest` 定评审人，评审按 `code-review-zh` 双轴走。

**③ 季度仓库大扫除**
`git-branch-cleanup` 出三类分支清单，人工审阅后再执行删除脚本 → `todo-debt-scan` 挑 Top 10 债项 → 与 `git-hotspots` 的热点取交集，交集就是这季度真正该动的文件 → 用 `code-simplification-zh` 或 `architecture-deepening-zh` 处理 → 结论写进迭代周报 `iteration-report-git`。

自检口诀：
```
治理的活：1) 分清是债 / 人 / 分支 / 流程 → 2) 查表选子技能 → 3) 先出只读报告再动手 → 4) 热点与债取交集，只动交集
```

## 不做什么

- 不直接改代码、不执行删除、不替团队定考核指标；一切改动先出清单、由人确认。
- 不生成业务代码与测试代码——那是编程类与测试类技能的事。
- 不做故障排查、上线检查、周报这些流程活，那些找研发全能助手 `dev-workflow-pro`。
- 不接触任何未脱敏的内部系统信息；示例一律用 example.com 与 GitHub / GitLab / Jira。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
