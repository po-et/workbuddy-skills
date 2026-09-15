# WorkBuddy 生态缺口分析：什么值得搬，什么不值得

日期：2026-09-15。检索日 2026-09-14/15。
标注：【事实】有来源；【推断】我的判断；【待确认】未核实。

## 一句话结论

【推断】WorkBuddy 生态缺的不是"更多技能"，而是**运行时基础设施**（Hooks 规则引擎、连接器构建指南）和**把成熟外部 CLI 接进来的桥**。技能层已经饱和，基建层几乎空白。

---

## 候选清单与判定

| 候选 | 成熟度 | WorkBuddy 已有？ | 协议 | 判定 |
|---|---|---|---|---|
| Superpowers 方法论技能 | 174k★，7 个月 | **已有**：superpowers-zh 至少 5 个中文版；ClawHub 两个版本；WorkBuddy 兼容 OpenClaw 技能 | MIT | ❌ 饱和，做第 6 个无意义 |
| Anthropic 官方 docx/pptx/xlsx/pdf | 官方 | WorkBuddy 内置 Office 能力 | **source-available，非开源** | ❌ 协议禁止再分发 |
| awesome-workbuddy 聚合仓库 | — | 至少 5 个（semlinker 等） | — | ❌ 饱和 |
| 通用办公技能 | — | SkillHub 7 万+，精选 800 | — | ❌ 第 70001 个价值为零 |
| **Anthropic hookify**（Hooks 规则引擎） | 官方插件，纯标准库 Python | **无**。WorkBuddy Hooks 官方文档写明"完全兼容 Claude Code Hooks 规范" | Apache 2.0 | ✅ **运行时契约相同，可高保真移植** |
| **CLI-Anything**（港大，80 个 agent-native CLI） | arXiv 技术报告，2461 测试 | **无**。WorkBuddy CLI 连接器规范 = connector-meta.json + cli.json + icon + skills/，CLI-Anything 的 install_cmd / entry_point / skill_md 三字段一一对应 | Apache 2.0 | ✅ **零适配成本的桥**，思源/幕布是中文工具 |
| Anthropic mcp-server-dev / plugin-dev | 官方 | 无 WorkBuddy 版连接器构建指南 | Apache 2.0 | ✅ 借鉴结构，按 WorkBuddy 规范重写 |
| Anthropic skill-creator | 官方，含 eval | 外部已有 4+ 个 SKILL.md linter | Apache 2.0 | ⚠ 新颖度低，可做 SkillHub 专用薄层 |
| MCP 服务器 | 22k+ 个 | WorkBuddy 已内置 80+ 连接器，8 大类 | — | ⚠ 缺口小 |

---

## 为什么 Hooks 是最大缺口

【事实】WorkBuddy Hooks 官方文档：配置在 `~/.codebuddy/settings.json` 或 `<项目>/.codebuddy/settings.json`；7 个事件（SessionStart / SessionEnd / PreToolUse / PostToolUse / UserPromptSubmit / Stop / PreCompact）；stdin JSON、退出码 0/1/2、stdout JSON 的 `hookSpecificOutput.permissionDecision` 等字段，与 Claude Code 同构；原文"Hook 机制完全兼容 Claude Code Hooks 规范"；提供 `CLAUDE_PROJECT_DIR` 兼容变量。

【事实】CodeBuddy（同一 Agent 基座）插件格式：`.codebuddy-plugin/plugin.json`，兼容回退 `.workbuddy-plugin/` 与 `.claude-plugin/`；`${CODEBUDDY_PLUGIN_ROOT}` 与别名 `${CLAUDE_PLUGIN_ROOT}`；官方文档明确"插件在 CodeBuddy 与 WorkBuddy 间通用"。

【事实】Anthropic hookify：用 `.local.md` 文件（YAML frontmatter + 消息体）定义规则，PreToolUse 拦截危险命令、PostToolUse 提醒、Stop 完成检查、UserPromptSubmit 上下文注入。依赖仅 `re / json / os / glob / dataclasses`。

【推断】这意味着：**一份规则文件可以同时在 WorkBuddy、CodeBuddy、Claude Code 三个运行时生效**。这是"AI 基建"层面的贡献，不是又一个技能。

已知差异（移植时必须处理）：

| 项 | Claude Code / hookify 原版 | WorkBuddy / CodeBuddy | 来源 |
|---|---|---|---|
| UserPromptSubmit 输入字段 | `user_prompt` | `prompt` | CodeBuddy hooks 参考 |
| PostToolUse 结果字段 | `tool_result` | `tool_response` | 同上 |
| 规则文件目录 | `.claude/` | `.codebuddy/` | WorkBuddy Hooks 文档 |
| 插件根变量 | `CLAUDE_PLUGIN_ROOT` | `CODEBUDDY_PLUGIN_ROOT`（有别名） | CodeBuddy 插件参考 |
| Windows | — | 强制 Git Bash，建议 `python3 x.py` 而非直接执行 | CodeBuddy hooks 指南 |
| 顶层 `continue` | 可省略 | 第三方移植报告称需显式 `true` | 【待确认】GitHub PR 转述 |
| IDE 模式工具名 | `Bash` | 有报告称为 `execute_command` | 【待确认】同上 |

---

## 为什么 CLI-Anything 是最好的桥

【事实】WorkBuddy CLI 连接器规范（open.workbuddy.cn/docs/connector）：

```
connector/
├── connector-meta.json   # name_zh/name_en, description_*, source(kebab), type:"cli", version, examples_zh/en(2-5)
├── cli.json              # init.{darwin,linux,win32}, auth/unAuth/status(可选), statusMatch, runtime
├── icon.svg
└── skills/<name>/SKILL.md
```

审核 10–15 分钟。

【事实】CLI-Anything registry.json 每条含 `install_cmd`、`entry_point`、`skill_md`、`requires`、`contributors`。映射关系：

| CLI-Anything | WorkBuddy 连接器 |
|---|---|
| `install_cmd` | `cli.json.init.{platform}` |
| `entry_point` | Skill 里调用的命令名 |
| `skill_md` | `skills/<name>/SKILL.md`（已按 Agent Skills 规范写好） |
| `requires` | SKILL.md 前置条件 |
| `contributors` | 必须署名 |

【推断】首批最优候选：
1. **mermaid** — `requires: None`，零外部依赖，研发场景（架构图）直接可用
2. **siyuan（思源笔记）** — 中文工具，本地 HTTP API
3. **mubu（幕布）** — 中文工具
4. **drawio** — 架构图
5. **n8n** — 55+ 命令，v2.4.7，自动化

---

## 不做的事

- 不做第 6 个 superpowers-zh
- 不做第 6 个 awesome-workbuddy
- 不搬 source-available 的 Anthropic 文档技能
- 不无改动地批量上架技能

## 署名规范

Apache 2.0 与 MIT 均要求保留版权声明。本仓库对每个移植项：保留原 LICENSE 全文；`ATTRIBUTION.md` 写明原项目、原作者、原协议、改动清单；文件头标注"修改自"。CLI-Anything 额外按 CITATION.cff 引用技术报告（arXiv:2606.03854）并署名各 harness 的 contributors。
