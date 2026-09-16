# workbuddy-skills

> **CodeBuddy 写代码，WorkBuddy 干剩下的。**
>
> 面向研发团队的 Agent 技能体系，加上 WorkBuddy 生态缺的基础设施：Hooks 规则引擎、连接器构建工具、把成熟外部 CLI 接进来的桥。

遵循 [Agent Skills 开放标准](https://docs.openclaw.ai/tools/skills)（SKILL.md），可在 **WorkBuddy / OpenClaw / Claude Code** 等支持该标准的 Agent 中直接使用。

```
skills/     原创：研发效能技能体系 + 连接器构建
ported/     精选移植：成熟外部项目，保留署名，有实质改造，附测试
docs/       生态缺口分析、额度实测协议、设计稿
```

---

## 为什么是这些技能

AI 编程工具已经解决了「写代码」。但一个研发团队里，真正吃时间又没人愿意干的，是写代码之外的部分：

| 活 | 现状 | 每周耗时（估） |
|---|---|---|
| 迭代周报 / 向上汇报 | 手工拼 git log 和工单 | 1-2 小时 |
| 上线检查清单 | 每次重写，或者干脆不写 | 0.5-1 小时 |
| 线上问题排查取证 | 人肉在日志/监控/变更间跳 | 每次事故 15 分钟起 |
| 需求转技术方案 | 从零写 | 2-4 小时 |

这些活有个共同点：**流程固定、数据分散、产出有标准格式**。正好是 Agent 的主场。

---

## 技能列表

| 技能 | 状态 | 说明 |
|---|---|---|
| [`iteration-report`](skills/iteration-report/) | ✅ 可用 | 迭代周报生成器。按交付价值重组，每条可溯源，提交信息烂也能用 |
| [`incident-brief`](skills/incident-brief/) | ✅ v0.1 | 线上排查简报。时间线对齐 + 候选排序，**不下结论，给证据链** |
| [`release-checklist`](skills/release-checklist/) | ✅ 可用 | 上线检查清单。从实际改了什么倒推该检查什么 |
| `tech-design-draft` | 🚧 规划中 | 需求转技术方案骨架 |
| [`build-workbuddy-connector`](skills/build-workbuddy-connector/) | ✅ 可用 | 为 WorkBuddy 做连接器：规范速查、脚手架、校验脚本、CLI-Anything 桥 |

### 它们是一个体系，不是三个独立工具

```
iteration-report ──迭代区间──> release-checklist ──高风险项──> incident-brief
   本期交付了什么              上线要检查什么           出事时先查什么
```

三个技能共享输出契约：结论可溯源、数据缺口单列、判断性内容显式标记。
一个技能的产出可以直接作为下一个的输入 —— 这是「技能体系」与「技能合集」的区别。

---

## 精选移植（ported/）

不是搬运，是补缺口。每一项都满足：原项目成熟且开源、WorkBuddy 生态没有、保留原协议与署名、有实质改造、附测试。判断依据见 [生态缺口分析](docs/ecosystem-gap-analysis.md)。

| 项目 | 来源 | 状态 | 一句话 |
|---|---|---|---|
| [`hookify-workbuddy`](ported/hookify-workbuddy/) | Anthropic hookify（Apache-2.0） | ✅ 16 测试通过 | 用 Markdown 文件定义 Hooks。同一份规则在 WorkBuddy / CodeBuddy / Claude Code 通用。修了上游一个 bug |
| [`connectors/mermaid`](ported/connectors/mermaid/) | CLI-Anything（港大，Apache-2.0） | ✅ 规范校验通过，CLI 实测通过 | 零依赖画流程图/时序图/架构图，渲染 SVG/PNG。首个 CLI-Anything → WorkBuddy 连接器 |

不做的事：第 6 个 superpowers 中文版、第 6 个 awesome-workbuddy、无改动的批量上架。原因写在缺口分析里。

## 快速开始

```bash
git clone <repo> && cd workbuddy-skills
```

**WorkBuddy**：把 `skills/<name>/` 整个目录放进技能目录，或从 SkillHub 安装。

**OpenClaw / Claude Code**：软链到 skills 目录即可。

```bash
ln -s "$PWD/skills/iteration-report" ~/.agents/skills/iteration-report
```

### 试一下 iteration-report

```bash
cd skills/iteration-report
python3 scripts/collect_git.py --repo ~/your/repo \
  --since 2026-09-08 --until 2026-09-14 --out out/git.json
python3 scripts/render_report.py --git out/git.json \
  --template references/report-template.md --out out/report.md
```

Git 侧走本地 `git log`，**不需要任何 token**，内网 GitLab / 自建 Gitea 同样可用。
工单侧可选，支持 `file` / `github` / `gitlab` / `jira` 四种 provider。

---

## 设计原则

这几条贯穿所有技能，也是它们和「又一个 prompt 合集」的区别：

1. **可追溯** —— 每条结论必须挂得上原始数据（commit hash、工单号、日志行号）
2. **不编造** —— 数据缺失就写"数据缺失"，宁可少写不许脑补；缺口单列一节
3. **不替人下结论** —— 尤其是排查场景。给排序过的候选 + 反证 + 可验证推论，判断权留给人
4. **脚本做事实，模型做判断** —— 统计、采集、渲染全部脚本化。这既保证可复现，也省额度
5. **额度自觉** —— 每个技能都写明该用什么模式、什么时候 `/clear`

---

## 安全与合规

- 技能**不包含任何内网地址、凭证、生产数据**。凭证一律从环境变量读，配置里只写变量名
- 内部系统对接走 `file` provider 或独立私有适配器包，不入本仓库
- `incident-brief` 会读取日志与监控数据，使用云端模型前请先确认脱敏配置
- 安装任何第三方技能前先读代码。技能就是可执行代码

---

## 相关文档

- [生态缺口分析](docs/ecosystem-gap-analysis.md) —— 什么值得搬、什么不值得，带证据
- [额度实测协议](docs/credit-benchmark/) —— 可复现的 WorkBuddy 额度对比实验设计
- [incident-brief 设计稿](docs/design/incident-brief.md)
- [Skills 策略](docs/skills-strategy.md) —— 为什么不做"技能合集"而做"技能体系"

## 协议

- 原创部分：代码 [MIT](LICENSE)，文档 [CC BY 4.0](LICENSE-CONTENT)
- `ported/` 下各项目：沿用原项目协议（目前均为 Apache-2.0），各目录自带 LICENSE 与 ATTRIBUTION.md

## Buddy 应用（`buddy-apps/`）

Buddy 应用是开放平台里"可独立分发、面向终端用户"的品牌工作台，本质是一份网页表单配置（工作模式 + 场景胶囊 + 市场绑定 + 品牌资源），**个人开发者不能创建，需企业认证**。
`buddy-apps/devops-buddy/` 是首个应用「研发效能 Buddy」的完整配置包：把本仓库的 4 个技能、3 个专家、2 个连接器组装成 4 个工作模式与 8 个场景胶囊，图标与底图按官方设计规范生成。校验：

```bash
python3 tools/check_buddy_app.py buddy-apps/devops-buddy
```

调研与路线见 `docs/buddy-app-plan.md`。

## 渠道

个人开发者能走的全部提交/曝光渠道与当前状态见 `docs/channels.md`（SkillHub、开放平台、腾讯云征集、蓝皮书、ClawHub 等）。
