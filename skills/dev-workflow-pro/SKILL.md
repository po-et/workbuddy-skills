---
name: dev-workflow-pro
description: 研发全能助手，覆盖写代码之外的整条研发流程：需求盘问与澄清、技术方案与 Spec、任务拆解与排期、Git 提交信息（Conventional Commits）、代码评审、合并冲突、上线检查清单与回滚预案、Changelog 与发布说明、迭代周报与向上汇报、线上故障排查与简报、日志突变定位、Bug 诊断与复现、依赖漏洞扫描（CVE/OSV）、复盘文档。当用户提到周报、月报、迭代报告、上线、发布、回滚、故障、告警、排查、复盘、commit、changelog、release notes、冲突、rebase、需求、spec、拆任务、评审、漏洞、依赖升级、架构图、时序图等任一研发流程事务，但不确定该用哪个专门技能时使用；本技能会判断意图、给出对应的精专方法，并指向可安装的子技能。不做：直接生成业务代码（用编程类技能）。
author: Captain
version: 0.1.0
display_name: "研发全能助手"
display_name_en: "Dev Workflow Pro"
description_zh: "一个入口覆盖代码之外的研发流程：需求盘问、Spec 与拆任务、提交信息、评审、解冲突、上线清单、Changelog、周报、故障排查、日志突变、Bug 诊断、依赖漏洞；按意图路由到精专子技能。"
description_en: "One entry point for everything after the code: requirement grilling, specs and tickets, commit messages, review, conflicts, release checklists, changelogs, iteration reports, incident triage, log anomalies, bug diagnosis, dependency vulnerabilities; routes to focused sub-skills."
examples_zh:
  - "这周要交周报、还要上线、还有个故障没复盘，先从哪个开始？"
  - "帮我把这个需求走一遍：问清楚、写 spec、拆任务"
  - "上线前把该做的检查都过一遍"
examples_en:
  - "I owe a weekly report, a release and a postmortem this week, where do I start?"
  - "Take this requirement end to end: grill, spec, tickets"
  - "Run every pre-release check we should do"
metadata:
  { "openclaw": { "requires": { "bins": ["git", "python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧰" } }
---

# 研发全能助手

定位一句话：**写代码交给编程助手，代码之外的活交给我。**
这是「研发效能」系列的入口。先判断用户在研发流程的哪一环，用下表的方法直接干；表里对应的子技能已安装就调用它（更完整、带脚本），没安装就按本页的精简方法做，并告诉用户可以在 SkillHub 搜索安装。

## 意图 → 方法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 「我想做 X」但细节没定；方案、决策 | 按设计树分轮追问，每题附推荐答案，事实自己查，决策落盘 | 需求盘问官 `grill-me-zh` |
| 把讨论写成需求 / spec / 拆任务 / 排期 | Spec 模板（问题/方案/用户故事/实现与测试决策/范围外）→ 垂直切片工单 + 阻塞关系 | 需求→Spec→任务拆解 `spec-and-tickets-zh` |
| commit message、提交规范 | `type(scope)!: subject ≤50 字`；body 讲 why；破坏性变更用 `!` | Git 提交信息生成器 `commit-message-cc` |
| 评审 PR / 看看这段改动 | 两个轴分开报：标准（规范与坏味道）与 spec（做的是不是要的）；不合并排名 | 上线检查清单 `release-checklist-git` |
| merge / rebase 冲突 | 看状态 → 追双方意图 → 逐块保留不发明 → 跑检查 → 完成；注意 rebase 里 ours/theirs 反向 | 合并冲突解决 `merge-conflicts-zh` |
| 要上线、发布、回滚预案 | 对比分支变更识别影响面（接口/配置/DB/依赖/权限）→ 必须/建议清单 → 回滚预案；不给"可以上线"的结论 | 上线检查清单 `release-checklist-git` |
| changelog、release notes、版本说明 | 按 tag 区间读提交，Keep a Changelog 分组，每条附 hash，不规范提交单独列出 | Changelog 生成器 `changelog-keep` |
| 周报、月报、迭代报告、给老板汇报 | 从 git log 与工单聚合，按交付价值重组，每条挂 commit/工单号，缺口明写 | 迭代周报生成器 `iteration-report-git` |
| 线上故障、告警、排查、简报 | 时间线（告警/症状/变更/操作）→ 可疑变更 → 假设按可能性排序附验证方法 → 建议动作 → 未知项 | 线上排查简报 `incident-brief-sre` |
| 错误什么时候开始变多的 | 日志按分钟聚合，滑动基线 3σ 找突变起点，对齐变更记录 | 日志突变检测 `log-anomaly-3sigma` |
| 疑难 bug、偶现、性能回退 | 先造能变红的反馈回路，再复现最小化、列可证伪假设、定向探针、回归测试先于修复 | Bug 诊断法 `diagnosing-bugs-zh` |
| 依赖有没有漏洞、该升级什么 | 解析锁文件查 OSV（免 key），按严重度给升级版本 | 依赖漏洞体检 `dep-vuln-check-osv` |
| 复盘、postmortem | 影响范围 / 时间线 / 根因（5 Why）/ 做对与做错 / 改进项（负责人+截止日） | 线上排查简报 `incident-brief-sre` |
| 画架构图、时序图、流程图 | 先确认组件边界与数据流方向，再出 Mermaid 源码与 SVG | WorkBuddy 连接器「Mermaid 图表」/「Draw.io」 |
| 做 WorkBuddy 连接器 | 规范速查 + 脚手架 + 校验器 | 连接器构建助手 `build-workbuddy-connector` |

## 共同的输出契约（整个系列一致）

1. **每条结论附来源**：commit 短 hash、工单号、文件路径、日志行、漏洞编号。拿不到来源就标「待确认」。
2. **不下最终结论的事**：能不能上线、根因是什么、要不要放弃合并——只列证据与选项，决定权在人。
3. **诚实的缺口**：每份产出末尾列出没拿到的数据、没跑的检查、没确认的假设。
4. **省积分**：确定性的部分（读 git、算统计、查 API）用脚本；推理用 Ask 模式；跑完一件事 `/clear`。

## 一次典型的"这周的活"

用户："这周要交周报、周四上线、还有上周的故障没复盘。"
顺序建议：① 故障复盘（记忆最新鲜、且上线前要确认是否已修）→ ② 上线检查清单（周四前留出修复时间）→ ③ 周报（把前两件事的结论直接引用进去）。每一步用对应子技能，最后周报里三件事互相引用 hash 与文档路径。

## 不做什么

- 不直接生成业务代码、不做算法题——那是编程类技能的事。
- 不接触任何未脱敏的公司内部系统信息；公开示例一律用 GitHub / GitLab / Jira。

---
本系列全部开源（正文 CC BY 4.0，代码 MIT）：https://github.com/po-et/workbuddy-skills 。复刻自他人作品的技能在各自目录的 ATTRIBUTION.md 注明来源。
