# 别再搬 superpowers 了：我查了一圈 WorkBuddy 生态，缺的不是技能

> 发布渠道建议：掘金 / 知乎 / 腾讯云开发者社区（冲精选）。标题可按平台微调。
> 所有"实测"均有仓库内测试或记录可查；未在 WorkBuddy 客户端内验证的事项已明写。

上周我打算给 WorkBuddy 生态做点贡献，第一反应和大多数人一样：把 Claude Code 那边成熟的东西搬过来。

查了三天，结论是：**技能层已经饱和，值得做的在另一层。** 把查证过程写下来，省得下一个人再走一遍。

## 先看数据

| 想搬的东西 | 查证结果 |
|---|---|
| Superpowers（17 万星的方法论技能框架） | 中文版**至少 5 个**（superpowers-zh 各种分叉），ClawHub 上还有 2 个。WorkBuddy 兼容 OpenClaw 技能，等于已经能装 |
| Anthropic 官方 docx / pptx / xlsx / pdf 技能 | 仓库 README 写得很清楚：**source-available，不是开源**。不能再分发 |
| awesome-workbuddy 类资源聚合 | 至少 5 个，其中一个作者是 semlinker |
| 通用办公技能 | SkillHub 官方口径 7 万+，精选 800 |

做第 6 个 superpowers 中文版、第 6 个 awesome 列表、第 70001 个 PPT 技能——没有任何人会记得。

## 那什么是空的

我换了个问法：**不问"外面有什么好东西"，问"WorkBuddy 的运行时有什么能力，而生态里没人用"。** 翻官方文档，三个发现：

**1. Hooks 是同一份协议。** WorkBuddy 官方文档原文："Hook 机制完全兼容 Claude Code Hooks 规范"。7 个事件、stdin JSON、退出码、`hookSpecificOutput` 字段全部同构。CodeBuddy 插件参考进一步写明：`.codebuddy-plugin/` 兼容回退 `.claude-plugin/`，`${CODEBUDDY_PLUGIN_ROOT}` 有别名 `${CLAUDE_PLUGIN_ROOT}`，"插件在 CodeBuddy 与 WorkBuddy 间通用"。

这意味着 Anthropic 官方那套 Apache-2.0 的 hook 基础设施可以**高保真移植**——而 SkillHub 上一个都没有，因为 WorkBuddy 的主力用户是办公人群，不知道这层存在。

**2. 连接器规范是公开的，且极简。** 一个 CLI 连接器就四个文件：`connector-meta.json`、`cli.json`、`icon.svg`、`skills/`。审核 10–15 分钟。

**3. 港大 CLI-Anything 是现成的桥。** 他们把 80 个桌面软件做成了 agent-native CLI（Apache-2.0，有 arXiv 技术报告，2461 个测试）。registry 里每条的 `install_cmd` / `entry_point` / `skill_md` 三个字段，正好对应连接器规范的 `cli.json.init` / 命令名 / `skills/`。**零适配成本。** 而且里面有思源笔记、幕布这样的中文工具。

## 于是我做了三样

**hookify-workbuddy**：移植 Anthropic 官方 hookify。用一个 Markdown 文件定义 Hook：

```markdown
---
name: block-dangerous-rm
enabled: true
event: bash
pattern: rm\s+-rf
action: block
---

⚠️ 检测到危险的 rm 命令，已拦截。
```

放到项目的 `.codebuddy/` 目录，下一次工具调用就生效，不改 settings，不重启。同一份规则在 WorkBuddy、CodeBuddy、Claude Code 三处通用。

移植过程抹平了三处字段差异（`prompt` vs `user_prompt`、`tool_response` vs `tool_result`、规则目录），写了 16 个端到端测试。

顺带把上游**三个 open issue** 的问题一起修了：`not_contains` 不支持 `a|b`（#5368、#5602，有个修复 PR 被关闭没合并，官方自带的"没跑测试不许结束"示例因此永远命中）；非 Bash/文件类工具触发时规则全量加载，`event:file` 的拦截规则会误拦 `Read`（#4787、#3712）。每个都有回归测试，改动清单和原协议都在仓库里。

为什么这些修复躺了几个月没进 main？去看了被关闭的修复 PR，关闭者是机器人，留言一句：**"This repo only accepts contributions from Anthropic team members."** 官方插件仓库不收外部 PR。社区报了 5 个 hookify 的 issue，交了修复，全部停在门外。这就是移植的意义——不只是搬到另一个平台，是把社区已经找到的答案真正交到用户手里。

**mermaid 连接器**：第一个 CLI-Anything → WorkBuddy 的桥。零外部依赖，画流程图、时序图、架构图，渲染 SVG/PNG。CLI 端到端实测通过。顺手发现 harness 文档写的 `pip install cli-anything-mermaid` 其实**没发到 PyPI**（只有 drawio 和 n8n 发了），安装命令得走 git 子目录——这种坑不实测发现不了。

**build-workbuddy-connector**：让别人也能做。规范速查逐字抄官方文档，一个校验脚本按规范检查连接器目录，一个脚手架带 `--from-cli-anything` 模式读 registry 一键生成骨架。

## 诚实的边界

- hookify 的行为验证靠的是我自己的测试夹具（stdin JSON 驱动真实入口脚本），**还没在 WorkBuddy 客户端里跑过**
- 连接器的 `runtime.type: "python"` 取值、`minWorkbuddyVersion` 是按规范示例类推的，**等第一次审核反馈**
- 所有"待确认"都写在各目录的 ATTRIBUTION.md 里

## 一个观察

在一个 7 万个技能的市场里，没有人记得住第 70001 个技能。但如果你是"把 Hooks 规则引擎带进 WorkBuddy 的人"、"把 80 个桌面软件接进 WorkBuddy 的人"，这个位置只有一个。

基建层的贡献比技能层难一点，但那正是它空着的原因。

---

仓库：https://github.com/po-et/workbuddy-skills
缺口分析全文（带来源）：`docs/ecosystem-gap-analysis.md`
