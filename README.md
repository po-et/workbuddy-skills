# workbuddy-skills

> **CodeBuddy 写代码，WorkBuddy 干剩下的。**
>
> 面向研发团队的 Agent 技能集：把「不写代码但必须有人干」的活交出去 —— 迭代周报、上线检查、线上排查、技术方案。

遵循 [Agent Skills 开放标准](https://docs.openclaw.ai/tools/skills)（SKILL.md），可在 **WorkBuddy / OpenClaw / Claude Code** 等支持该标准的 Agent 中直接使用。

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

### 它们是一个体系，不是三个独立工具

```
iteration-report ──迭代区间──> release-checklist ──高风险项──> incident-brief
   本期交付了什么              上线要检查什么           出事时先查什么
```

三个技能共享输出契约：结论可溯源、数据缺口单列、判断性内容显式标记。
一个技能的产出可以直接作为下一个的输入 —— 这是「技能体系」与「技能合集」的区别。

---

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

## 协议

- 代码（`scripts/` 及 `*.py`）：[MIT](LICENSE)
- 文档、SKILL.md 正文、模板：[CC BY 4.0](LICENSE-CONTENT)

移植或改编自其他项目的内容，会在对应技能目录的 `SKILL.md` 底部注明出处与原协议。

---

## 相关文档

- [额度实测协议](docs/credit-benchmark/) —— 可复现的 WorkBuddy 额度对比实验设计
- [incident-brief 设计稿](docs/design/incident-brief.md)
