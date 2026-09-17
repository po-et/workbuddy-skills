# 提交清单（需要本人账号的动作）

日期：2026-09-15。以下动作都需要你的账号，我无法代做。按顺序，前一步是后一步的前提。

## 0. 前提：开发者注册 ✅ 2026-09-15 个人认证已通过

- [ ] open.workbuddy.cn → 个人认证。**操作步骤与资料包见 [onboarding-walkthrough.md](onboarding-walkthrough.md)**。这一步卡住后面所有平台侧动作。
- [ ] SkillHub 发布需实名认证，同一账号体系

## 1. 开放平台发布 3 + 1 个原创技能 ✅ 2026-09-16 全部提交审核

| 技能 | 技能 ID | 版本 | 市场展示分类 | 类目 | 状态 |
|---|---|---|---|---|---|
| 迭代周报生成器 | `os_d38a73df48140dc3` | 0.1.1 | 开发工具；办公协同 | 工具 - 办公 | 审核中 |
| 上线检查清单 | `os_9407658dcf341900` | 0.1.0 | 开发工具；效率工具 | 工具 - 办公 | 审核中 |
| 线上排查简报 | `os_b8c4f2185c9ed808` | 0.1.0 | 开发工具；数据分析 | 工具 - 办公 | 审核中 |
| 连接器构建助手 | `os_f63d90ab5a462475` | 0.1.0 | 开发工具 | 工具 - 办公 | 审核中 |

审核结果走邮箱 / 平台通知 / 客户端通知。结果回来记到 `docs/review-feedback.md`。
【待确认】技能列表页对迭代周报显示 v0.1.0，而提交总览页为 0.1.1，疑为列表显示的是首次解析版本。

官方 Q&A 第 12 条：开放平台技能经严格审核与质量评测，端内主页品牌更完整，市场展示与 Agent 自动调用权重更高。入口 `/skill/publish`，仅 .zip ≤3MB，三步：配置技能 → 确认信息 → 提交审核。规则详见 [platform-notes.md](platform-notes.md)。

打包好的 zip 在本机 scratchpad `dist/` 目录（不入库）。每个包已剔除 `__pycache__`、`.keep`、LICENSE。

| 包 | 一句话描述（可直接用） | 分类建议 |
|---|---|---|
| `iteration-report.zip` | 迭代周报生成器：按交付价值重组 Git 与工单记录，每条可溯源，提交信息烂也能从 diff 反推 | 开发辅助 / 日常办公 |
| `release-checklist.zip` | 上线检查清单：从实际改了什么倒推该检查什么，规则可配置，每条可勾选可验证 | 开发辅助 |
| `incident-brief.zip` | 线上排查简报：日志、监控、变更、工单对齐成一条时间线，候选按可疑度排序，不下结论给证据链 | 开发辅助 |
| `build-workbuddy-connector.zip` | 为 WorkBuddy 做连接器：规范速查、脚手架、校验脚本、CLI-Anything 桥 | AI Agent 优化 |

- [ ] 审核承诺 7 个工作日，当前积压有延迟；结果走邮箱/平台/客户端通知。审核意见记录到 `docs/review-feedback.md`

## 2. 开放平台提交 mermaid 连接器 ✅ 2026-09-16 已提交审核

| 连接器 | 连接器 ID | 版本 | 类目 | 状态 |
|---|---|---|---|---|
| Mermaid 图表 | `oc_5da8a66ba4f23596` | 0.1.0 | 工具 - 办公 | 审核中 |
| draw.io 架构图 | `oc_1c196bbcd104c9b8` | 0.1.0 | 工具 - 办公 | 审核中 |

连接器包实测：仅 .zip ≤ **20MB**；`mermaid-connector/` 目录布局、`LICENSE`、`ATTRIBUTION.md` 均被解析器接受；`icon.svg` 直接作为头像；`examples_zh` 4 条全部带出；第二步只有「服务类目」一个必填下拉（无「市场展示分类」）。

- [ ] `dist/mermaid-connector.zip`（含 LICENSE 与 ATTRIBUTION，连接器包需要）
- [ ] 审核约 7 个工作日；**发布后不自动上架，需运营代上架**（Q&A Q4）。重点看审核意见里是否指出以下三个待确认项：
  - `cli.json.runtime.type: "python"` 取值是否被接受
  - `minWorkbuddyVersion: "5.0.0"` 是否合适
  - git 子目录安装命令在他们环境的耗时/成功率
- [ ] 过审后**自己装一次**，跑 SKILL.md 里的四步，确认在客户端内可用。这是第一个真实用户验证

## 3. 开放平台提交专家 ✅ 2026-09-16 专家团 + 2 个独立专家已提交审核

| 专家 | 专家 ID | 版本 | 市场展示分类 | 类目 | 状态 |
|---|---|---|---|---|---|
| 研发效能专家团（devops-team） | `oe_07e25196d28646b1` | 0.1.0 | 技术工程 | 工具 - 办公 | 审核中 ✅ |
| SRE 专家 沈工（sre-incident-expert） | `oe_2300ba3b6ab1a0c9` | 0.1.0 | 技术工程 | 工具 - 办公 | 审核中 |
| 测试专家 祁老师（qa-release-expert） | `oe_e8d119831f1070a9` | 0.1.0 | 项目质量 | 工具 - 办公 | 审核中 |

包内内置 iteration-report / release-checklist / incident-brief 三个技能；上传共 6 次才通过，踩出的规则见 platform-notes「专家（Expert）包实测」。

## 4. 发第一篇文章

- [ ] 草稿：`docs/articles/01-别再搬-superpowers-了.md`。所有"实测"均有仓库内测试或记录，未在客户端验证的事项已明写，**发布时不要删"诚实的边界"那节**
- [ ] 首发建议：腾讯云开发者社区（教程 1000 积分，精选 +2000，且是官方渠道）→ 同步掘金、知乎
- [ ] 文末仓库链接；文章链接回填到仓库 README

## 5. 可选：给上游 issue 留言

上游不收外部 PR（PR #5601 被机器人关闭）。若愿意，可在 issue #4787 或 #5368 下留一句"移植版已修，附回归测试"并给链接。这是最轻量的可见度动作，做不做都行。

## 6. 一次性动作：让我能跑真实运行时测试

- [ ] 终端执行 `claude login` 刷新 CLI 的 OAuth。之后我可以用 `claude -p --plugin-dir` 在真实 Claude Code 里跑一次 hookify 拦截，把"三处通用"从测试夹具验证升级为运行时验证

---

顺序：0 → 5（顺手）→ 1、2 并行 → 3。等 1、2 的审核反馈回来，再决定思源/幕布/drawio 连接器做不做。

## Buddy 应用（阻塞：需企业认证）

| 应用 | 状态 | 配置包 | 备注 |
|---|---|---|---|
| 研发效能 Buddy（DevOps Buddy） | 未创建——个人开发者无法创建，需企业认证 | `buddy-apps/devops-buddy/`（app.md 粘贴稿 + config.json + assets） | 绑定的 9 个资产须先过审；企业认证通过后走 创建审核 → 配置审核 |

## SkillHub（skillhub.cn，个人技能市场）— 2026-09-16 就绪，等实名

CLI 已装（`~/.local/bin/skillhub`，2026.8.5）；发布副本由 `tools/skillhub_prep.py` 生成到 scratchpad `dist/skillhub/`，四个全部 `--dry-run` 通过。

| slug | 源 | 版本 | 状态 |
|---|---|---|---|
| iteration-report-git | skills/iteration-report | 0.1.2 | **已发布** skillId 203311，2026-09-17 18:37，审核中 |
| release-checklist-git | skills/release-checklist | 0.1.0 | **已发布** skillId 203312，审核中 |
| incident-brief-sre | skills/incident-brief | 0.1.0 | **已发布** skillId 203313，审核中 |
| build-workbuddy-connector | skills/build-workbuddy-connector | 0.1.0 | **已发布** skillId 203315，审核中 |

- [x] 用户已实名并登录（handle `user_a3a2e24a`）
- [x] 2026-09-17 四个技能发布完成（`skillhub publish … --changelog "首次发布"`，间隔 75 秒）；技能页 `https://skillhub.cn/skills/user_a3a2e24a/<slug>`，审核中时详情页显示未找到
- [ ] 上架后把 URL 与下载数记回这里；开放平台在审的 iteration-report 仍是 0.1.1，过审后再用 0.1.2 更新

## 腾讯云开发者社区《WorkBuddy 行业应用指南》有奖征集 — 截止 2026-10-08 23:59

- [ ] 案例 #1：`docs/articles/02-案例-…迭代周报.md`（缺 4 张客户端过程截图 + 积分消耗）
- [ ] 案例 #2：上线检查清单（release-checklist）；案例 #3：故障简报（incident-brief）—— 满 3 篇触发阶梯奖
- [ ] 每篇：发布到腾讯云开发者社区（话题 #WorkBuddy #AI办公）→ 填「WorkBuddy 行业应用指南共创投稿问卷」→ 同稿 PR 到 AlephAITech/WorkBuddyGuide `docs/cases/submissions/<slug>/index.md` → 加共创群（备注 workbuddy共创）

### SkillHub 第一批（2026-09-17 19:32–19:43 发布，审核中）

| slug | skillId | 类型 |
|---|---|---|
| dev-workflow-pro | 203361 | 伞形入口 |
| commit-message-cc | 203362 | 原创+脚本 |
| changelog-keep | 203363 | 原创+脚本 |
| dep-vuln-check-osv | 203365 | 原创+脚本（OSV） |
| log-anomaly-3sigma | 203366 | 原创+脚本 |
| grill-me-zh | 203367 | MIT 复刻增强 |
| diagnosing-bugs-zh | 203368 | MIT 复刻增强 |
| merge-conflicts-zh | 203369 | MIT 复刻增强 |
| spec-and-tickets-zh | 203370 | MIT 复刻增强 |

### SkillHub 第二批（2026-09-17 发布，审核中）

| slug | skillId | 类型 |
|---|---|---|
| code-review-zh | 203374 | 第二批 |
| tech-design-review | 203376 | 第二批 |
| license-check-offline | 203377 | 第二批 |
| api-diff-test | 203378 | 第二批 |
| ci-config-review | 203379 | 第二批 |

### SkillHub 第四批（2026-09-16 21:07 前后发布，审核中）— skillId 待补（会话中断丢失输出）

| slug | 来源 |
|---|---|
| api-design-zh / code-simplification-zh / deprecation-migration-zh / docs-and-adr-zh | addyosmani/agent-skills（MIT） |

### SkillHub 第五批（2026-09-17 17:50–17:54 发布，审核中）

| slug | skillId |
|---|---|
| ci-cd-zh | 204519 |
| git-workflow-zh | 204525 |
| incremental-implementation-zh | 204526 |
| planning-tasks-zh | 204529 |

观察：skillId 从昨晚 203379 到今天 204529，平台约 1100 个/天的发布量。第一批 24 小时后仍未进入搜索索引（审核中）。

### SkillHub 第五/六批（2026-09-17 18:25–18:58，26 个，机器审核中）

| slug | skillId | 发布时间 |
|---|---|---|
| engineering-skills-index-zh | 204558 | 18:23:58 |
| interview-me-zh | 204562 | 18:25:13 |
| idea-refine-zh | 204563 | 18:26:29 |
| spec-driven-zh | 204565 | 18:27:44 |
| source-driven-zh | 204566 | 18:29:00 |
| tdd-zh | 204570 | 18:30:16 |
| debug-triage-zh | 204572 | 18:31:31 |
| observability-zh | 204575 | 18:32:47 |
| security-hardening-zh | 204578 | 18:34:02 |
| performance-optimization-zh | 204582 | 18:35:18 |
| shipping-launch-zh | 204584 | 18:36:34 |
| code-review-five-axis-zh | 204587 | 18:37:49 |
| context-engineering-zh | 204589 | 18:39:05 |
| constraints-md-zh | 204591 | 18:40:21 |
| doubt-driven-zh | 204593 | 18:41:37 |
| browser-testing-devtools-zh | 204595 | 18:42:52 |
| frontend-ui-zh | 204598 | 18:44:08 |
| skillhub-publish-helper | 204604 | 18:46:51 |
| skill-lint-scorecard | 204607 | 18:48:06 |
| teach-workspace-zh | 204610 | 18:49:22 |
| deep-module-design-zh | 204613 | 18:50:38 |
| writing-for-agents-zh | 204615 | 18:51:53 |
| wayfinder-zh | 204618 | 18:53:09 |
| wizard-zh | 204621 | 18:54:25 |
| research-primary-zh | 204624 | 18:55:40 |
| handoff-doc-zh | 204626 | 18:56:56 |

### SkillHub 第七批（2026-09-17 19:07–19:16，7 个，机器审核中）

| slug | skillId | 发布时间 |
|---|---|---|
| triage-zh | 204663 | 19:07:47 |
| prototype-zh | 204689 | 19:10:18 |
| tdd-seams-zh | 204717 | 19:11:34 |
| architecture-deepening-zh | 204740 | 19:12:49 |
| to-questionnaire-zh | 204742 | 19:14:05 |
| re-pitch-zh | 204744 | 19:15:21 |

### SkillHub 第八/九批（Context-Engineering、doc-coauthoring、原创脚本）（2026-09-17，8 个，机器审核中）

| slug | skillId | 发布时间 |
|---|---|---|
| tool-design-zh | 204748 | 19:20:31 |
| context-fundamentals-zh | 204750 | 19:21:47 |
| context-degradation-zh | 204752 | 19:23:02 |
| memory-systems-zh | 204754 | 19:25:34 |
| doc-coauthoring-zh | 204755 | 19:26:49 |
| issue-triage-zh | 204759 | 19:29:34 |
| dockerfile-check | 204761 | 19:30:50 |
| sql-migration-check | 204763 | 19:32:05 |

冲突（需换 slug 重发）：context-compression-zh

### SkillHub 第十批（cron / OpenAPI）（2026-09-17，2 个，机器审核中）

| slug | skillId | 发布时间 |
|---|---|---|
| cron-explain | 204770 | 19:34:52 |
| openapi-breaking-diff | 204772 | 19:36:08 |

### SkillHub 第十一批（原创脚本技能 + context-compression 改名）（2026-09-17，14 个，机器审核中）

| slug | skillId | 发布时间 |
|---|---|---|
| env-sync-check | 204775 | 19:38:56 |
| flaky-test-finder | 204777 | 19:40:12 |
| k8s-manifest-check | 204780 | 19:42:51 |
| pr-description | 204782 | 19:44:06 |
| context-compression-strategies-zh | 204784 | 19:45:22 |
| todo-debt-scan | 204788 | 19:48:07 |
| git-branch-cleanup | 204791 | 19:49:22 |
| http-health-check | 204794 | 19:52:01 |
| log-pattern-cluster | 204795 | 19:53:18 |
| access-log-stats | 204799 | 19:55:55 |
| git-hotspots | 204801 | 19:57:11 |
| json-schema-infer | 204805 | 20:00:01 |
| codeowners-suggest | 204807 | 20:01:17 |
| dep-outdated-check | 204810 | 20:04:04 |
