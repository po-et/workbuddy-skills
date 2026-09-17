---
name: git-workflow-zh
description: Git 工作流、分支策略、原子提交、语义化版本、发布打 tag 与 changelog。当用户说「分支怎么管」「主干开发还是 gitflow」「提交太大怎么拆」「commit 该怎么分」「worktree 并行开发」「怎么用 git bisect 找坏提交」「版本号该升大版本还是小版本」「发布怎么打 tag」「changelog 和 git log 有什么区别」时使用。要点：主干开发 + 1–3 天短分支；早提交勤提交；原子提交；信息写 why；关注点分离；~100 行为宜；分支命名；worktree 并行；存档点模式；变更摘要（改了什么/故意没碰什么/顾虑）；提交前卫生；语义化版本与 tag 为准；面向人的 changelog。改编自 addyosmani/agent-skills 的 git-workflow-and-versioning（MIT）。
author: Captain
version: 0.1.0
display_name: "Git 工作流与版本管理"
display_name_en: "Git Workflow & Versioning (zh)"
description_zh: "主干开发、短分支、原子提交、写 why 的提交信息、~100 行的改动、worktree 并行、存档点模式、变更摘要、提交前卫生、语义化版本与 tag、面向人的 changelog。"
description_en: "Trunk-based development, short branches, atomic commits, why-focused messages, ~100-line changes, worktrees, the save-point pattern, change summaries, pre-commit hygiene, semver with tags, human-facing changelogs."
examples_zh:
  - "我们团队该用主干开发还是 gitflow"
  - "工作区改了一堆，帮我拆成干净的几个提交"
  - "这次改动算破坏性变更吗，版本号怎么升"
examples_en:
  - "Should we use trunk-based development or gitflow"
  - "Split my messy working tree into clean commits"
  - "Is this change breaking, how should I bump the version"
metadata:
  { "openclaw": { "requires": { "bins": ["git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🌿" } }
---

# Git 工作流与版本管理

Git 是安全网：提交是存档点，分支是沙盒，历史是文档。Agent 高速产出代码时，纪律化的版本控制是让改动可管理、可评审、可回退的机制。

## 核心原则

**主干开发（推荐）**：`main` 永远可部署；短分支 1–3 天内合回。长期分支是隐性成本——分叉、冲突、延迟集成。用 gitflow 的团队同样适用这里的提交纪律，纪律比分支模型重要。特性开关优于长分支；发布分支可接受（稳定发布时）。

1. **早提交、勤提交**：实现一片 → 测试 → 验证 → 提交 → 下一片。不要攒大改动。
2. **原子提交**：一个提交做一件逻辑上的事。
3. **信息写 why**：`feat: 注册接口增加邮箱校验` + 正文说明为什么、用了什么模式、和现有代码如何一致。类型：feat / fix / refactor / test / docs / chore（完整规范见本系列「Git 提交信息生成器」）。
4. **关注点分离**：格式化与行为变更分开；重构与功能分开——分开提交，最好分开 PR。
5. **控制大小**：~100 行易评审易回退；~300 行可接受；~1000 行要拆。

## 分支

从主干开分支；命名 `feature/…` `fix/…` `chore/…` `refactor/…`；合并后删除；未完成功能用开关而不是长分支。

## worktree 并行

`git worktree add ../project-feature-a feature/a` —— 多个 Agent 各自在独立目录、独立分支并行工作，不用切分支；实验失败直接删 worktree。

## 存档点模式

每做一处改动：测试过 → 提交 → 继续；测试挂 → 回到上一提交 → 调查。永远只丢一小步；Agent 跑偏时 `git reset --hard HEAD` 回到最近的好状态。

## 变更摘要（每次改完都给）

```
改了什么：文件 → 一句话
故意没碰的：文件 → 为什么（范围外 / 另开任务）
顾虑：严格校验会拒绝多余字段，请确认；新增依赖 X（体积）
```
「故意没碰」一节最重要——证明你守住了范围，没有顺手装修。

## 提交前卫生

看 `git diff --staged`；grep 密钥（password/secret/api_key/token）；跑测试、lint、类型检查；用 lint-staged + hooks 自动化。
生成文件：项目期望的才提交（锁文件、迁移）；不提交构建产物、`.env`、IDE 配置；`.gitignore` 覆盖 `node_modules/ dist/ .env *.pem`。

## 用 git 排查

`git bisect` 二分找坏提交；`git log --oneline -20`、`git diff HEAD~5..HEAD -- src/`；`git blame`；`git log --grep`。

## 发布与版本

提交是你追踪变化的方式，**版本**是消费者追踪变化的方式。一旦有人依赖你的代码，"main 最新"就不再是答案。
- **语义化版本** `MAJOR.MINOR.PATCH`：破坏性 → 大版本；向后兼容新功能 → 小版本；修复 → 补丁。数字是承诺：消费者依赖的行为变了就是大版本，不管 diff 多小（Hyrum 定律）；拿不准就当破坏性。
- **tag 为准**：`git tag -a v1.4.0 -m "Release 1.4.0"` 并推送；版本号从 tag 派生，不手改散落各处。
- **面向人的 changelog**：不是 `git log`；按 新增/变更/修复/废弃/移除/安全 分组，最新在上，每条写用户影响；**在做改动的那次提交里就写条目**，别到发布时考古。破坏性变更附迁移说明与废弃窗口（见「下线与迁移」）。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "功能做完再提交" | 一个巨型提交没法评审、排查、回退 |
| "信息无所谓" | 信息就是文档；未来的你和 Agent 要靠它 |
| "反正最后 squash" | squash 抹掉开发叙事；一开始就干净 |
| "分支麻烦" | 短分支免费；长分支才是问题 |
| "小修就升补丁" | 看消费者能观察到什么；行为变了就是大版本 |
| "changelog 就是提交日志" | 提交给你看，changelog 给消费者看，按影响筛选 |
| "发布时再写 changelog" | 到时靠回忆，一半都漏了 |

## 红灯

大量未提交改动；"fix""update""misc" 式信息；格式化混行为变更；没有 `.gitignore`；提交了 `node_modules` `.env` 产物；长期分叉的分支；对共享分支 force-push；破坏性变更只升小版本；发布无 tag 或版本手改与 tag 不一致；面向用户的发布没有 changelog。

## 验收

每次提交：一件事；信息写 why 且有类型；提交前测试通过；diff 无密钥；格式化不混行为；`.gitignore` 齐全。
每次发布：版本号与变更性质匹配；已打 tag 且版本从 tag 派生；changelog 有本版按影响分组的条目。

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `git-workflow-and-versioning`（MIT）。改动见 ATTRIBUTION.md。
