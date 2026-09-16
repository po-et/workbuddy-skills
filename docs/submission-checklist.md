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
