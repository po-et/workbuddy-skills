---
name: ci-cd-zh
description: CI/CD 流水线搭建与自动化质量门禁。当用户说「帮我配一下 CI」「GitHub Actions 怎么写」「流水线太慢」「加个自动化测试门禁」「部署流程怎么自动化」「预览环境」「特性开关怎么用」「回滚流程」「CI 挂了怎么反馈给 AI 修」时使用。核心：左移（越早发现越便宜）、小批量更安全；门禁流水线 lint → 类型 → 单测 → 构建 → 集成 → E2E → 安全审计 → 体积；一个门都不能跳；CI 失败喂回 Agent 的闭环；预览部署、特性开关生命周期、分阶段发布与回滚工作流；环境与密钥管理；Dependabot；Build Cop；超过 10 分钟的优化顺序。也覆盖「项目配一套」「按优先级帮我提速」「预览环境和回滚」这类说法。改编自 addyosmani/agent-skills 的 ci-cd-and-automation（MIT）。
author: Captain
version: 0.1.1
display_name: "CI/CD 与自动化门禁"
display_name_en: "CI/CD & Automation (zh)"
description_zh: "把质量门禁自动化：lint→类型→测试→构建→集成→E2E→审计→体积一个都不跳；CI 失败喂回 Agent；预览部署、特性开关、分阶段发布与回滚；密钥管理与流水线提速顺序。"
description_en: "Automate quality gates end to end, feed CI failures back to the agent, use preview deploys, feature flags, staged rollouts and rollback workflows, manage secrets, and speed up pipelines in the right order."
tags:
  - "CI/CD"
  - "持续集成"
  - "自动化门禁"
  - "GitHub Actions"
  - "特性开关"
  - "部署流程"
examples_zh:
  - "给这个 Node 项目配一套 GitHub Actions 门禁"
  - "CI 要 20 分钟，按优先级帮我提速"
  - "设计一个带预览环境和回滚的部署流程"
examples_en:
  - "Set up GitHub Actions quality gates for this Node project"
  - "CI takes 20 minutes, speed it up in priority order"
  - "Design a deploy flow with previews and rollback"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "⚙️" } }
---

# CI/CD 与自动化门禁

## 何时用
项目还没有 CI、门禁不全、流水线太慢、要接特性开关或预览环境、或 CI 失败需要喂回 Agent 修复时用。已经有一套跑得好的流水线、只是单次调试某次失败，直接看报错即可，不必整套重搭。

CI/CD 是其他所有工程实践的**执行机制**：人和 Agent 漏掉的，它在每一次改动上稳定地抓出来。

两条原则：**左移**——lint 抓到的 bug 花几分钟，生产抓到的花几小时，把检查往上游挪（静态分析先于测试，测试先于预发，预发先于生产）；**更快即更安全**——3 个改动的发布比 30 个的好排查，频繁发布反而降低风险。

## 门禁流水线

PR 打开 → Lint → 类型检查 → 单元测试 → 构建 → 集成测试 → E2E（可选）→ 安全审计（依赖）→ 体积检查 → 可评审。
**一个门都不能跳。** lint 挂了修 lint，不是关规则；测试挂了修代码，不是跳过测试。

## 流水线要点（以 GitHub Actions 为例，其他平台同理）

- 触发：`pull_request` 到主干 + `push` 主干；官方 action 固定版本（最好固定 commit SHA，见「CI 配置审查」技能）；依赖缓存（setup-node 的 `cache`）。
- 集成测试：用 `services` 起数据库容器，加健康检查；**即便是 CI 专用测试库，凭证也走 Secrets**，不写死。
- E2E：Playwright 装浏览器 → 构建 → 跑；失败时上传报告产物。
- 密钥分层：`.env.example` 提交、`.env` 不提交、`.env.test` 可提交（无真实密钥）、CI 密钥在平台 Secrets、生产密钥在部署平台/密钥库。**CI 永远不持有生产密钥。**

## CI 失败喂回 Agent

CI 挂 → 复制失败输出 → 交给 Agent："流水线失败，错误如下：[具体错误]。修复并在本地验证后再推。" → Agent 修 → 推 → 再跑。
模式：lint 失败 → `lint --fix` 提交；类型错误 → 读位置修类型；测试失败 → 走「系统化排错」技能；构建错误 → 查配置与依赖。

## 部署策略

- **预览部署**：每个 PR 一个预览环境供手工验证。
- **特性开关**：部署与发布解耦——合并早、启用晚；关开关即回滚不用重新部署；1% → 10% → 100% 灰度；A/B。生命周期：创建 → 内测启用 → 灰度 → 全量 → **删除开关与死代码**（创建时就写清理日期，永生的开关是技术债）。
- **分阶段发布**：合并 → 预发自动部署 → 手工验证 → 生产（手动触发或预发通过后自动）→ 观察 15 分钟 → 有错回滚 / 干净结束。
- **回滚**：每次部署都可逆；准备一个 `workflow_dispatch` 的回滚工作流，输入要回到的版本。

## CI 之外的自动化

Dependabot/Renovate 每周开依赖 PR（限制同时打开数）；**Build Cop** 轮值——构建红了由值班人修或回退，而不是等肇事者；PR 规则：至少 1 个批准、必需状态检查、主干禁止 force-push、全绿自动合并。

## 流水线超过 10 分钟时按序优化

缓存依赖 → lint/类型/测试/构建拆成并行 job → 路径过滤只跑相关的（纯文档 PR 跳过 E2E）→ 矩阵分片测试 → 把慢测试移出关键路径改为定时跑 → 更大的 runner。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "CI 太慢" | 优化它，别跳过它；5 分钟的流水线省掉几小时排查 |
| "这改动太小，跳过 CI" | 小改动也会弄坏构建；对小改动 CI 本来就快 |
| "测试抖动，重跑就好" | 抖动掩盖真 bug、浪费所有人时间；修掉抖动 |
| "CI 以后再加" | 没有 CI 的项目会积累坏状态；第一天就配 |
| "手工测试够了" | 手工测试不可扩展、不可重复 |

## 红灯

项目没有 CI；CI 失败被忽略或静音；为了变绿在 CI 里禁用测试；不经预发直接上生产；没有回滚机制；密钥写在代码或 CI 配置里；流水线很慢却没人优化。

## 验收

```
- [ ] 门禁齐全（lint、类型、测试、构建、审计）　- [ ] 每个 PR 与主干 push 都跑
- [ ] 失败阻止合并（分支保护）　- [ ] CI 结果回流到开发循环　- [ ] 密钥在密钥管理器里
- [ ] 部署有回滚机制　- [ ] 测试流水线 10 分钟内
```

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `ci-cd-and-automation`（MIT）。改动见 ATTRIBUTION.md。
