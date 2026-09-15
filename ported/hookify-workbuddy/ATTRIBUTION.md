# 出处与改动

## 原项目

- **hookify** — Anthropic 官方 Claude Code 插件
- 仓库：https://github.com/anthropics/claude-plugins-official/tree/main/plugins/hookify
- 原作者：Anthropic, PBC
- 协议：Apache License 2.0（全文见 `LICENSE`，版权声明见 `NOTICE`）

本项目是 hookify 的**派生作品**。规则文件格式（`hookify.*.local.md`，YAML frontmatter + 消息体）与原版保持兼容，
目的是让同一份规则在 WorkBuddy、CodeBuddy、Claude Code 三个运行时通用。

## 为什么能移植

WorkBuddy 官方文档写明"Hook 机制完全兼容 Claude Code Hooks 规范"，7 个事件、stdin JSON、退出码、
`hookSpecificOutput` 字段同构；CodeBuddy 插件参考写明 `.codebuddy-plugin/` 兼容回退 `.claude-plugin/`，
`${CODEBUDDY_PLUGIN_ROOT}` 有别名 `${CLAUDE_PLUGIN_ROOT}`，且"插件在 CodeBuddy 与 WorkBuddy 间通用"。

## 改动清单

| 改动 | 原因 |
|---|---|
| `config_loader.py` + `rule_engine.py` 合并为 `core/hookify.py` | 单文件便于插件分发 |
| 规则目录改为 `<项目>/.codebuddy/` 优先，`.claude/` 兼容；项目根取自 stdin 的 `cwd` | 原版硬编码相对进程 cwd 的 `.claude/`，在 WorkBuddy 下找不到文件 |
| `UserPromptSubmit` 同时读 `prompt` 与 `user_prompt` | CodeBuddy 输入字段为 `prompt`，原版只读 `user_prompt` |
| `PostToolUse` 同时读 `tool_response` 与 `tool_result` | 同上 |
| 工具名映射抽成 `TOOL_EVENTS` 表，加入 IDE 模式别名 | 可扩展；别名为第三方报告，未经官方文档确认 |
| 输出统一带顶层 `continue`；PreToolUse 拒绝补 `permissionDecisionReason`；Stop 拒绝同时给 `decision/reason` 与 `continue/stopReason` | 兼容两套运行时对拒绝形态的读取 |
| **修复 `contains` / `not_contains` 不支持 `a\|b` 任一匹配** | 上游**已知未修**：issue [#5368](https://github.com/anthropics/claude-plugins-official/issues/5368)、[#5602](https://github.com/anthropics/claude-plugins-official/issues/5602)；修复 PR [#5601](https://github.com/anthropics/claude-plugins-official/pull/5601) 已关闭未合并。其自带 `require-tests-stop` 示例因此永远命中 |
| **修复非 bash/file 工具触发时规则全量加载** | 上游 open issue [#4787](https://github.com/anthropics/claude-plugins-official/issues/4787)（`event:file` 的 block 规则误拦 Read）与 [#3712](https://github.com/anthropics/claude-plugins-official/issues/3712)（`event:stop` 规则在每次 PreToolUse 触发）。根因同一处：`event_for_tool` 返回 None → `load_rules` 不过滤。现改为返回 `other`，仅 `event: all` 规则对此类工具生效 |
| 入口脚本自定位插件根（`__file__`），环境变量存在时优先 | 不依赖运行时一定注入 `*_PLUGIN_ROOT` |
| 移除 `/hookify` 斜杠命令与 conversation-analyzer 子代理 | 依赖 Claude Code 命令机制；"从描述生成规则"的职责并入 skill |
| 全部中文化：错误信息、示例、README、Skill | 面向中文用户 |
| 新增 16 个端到端测试，含 3 个上游 issue 回归用例 | 上游无测试 |

## 为什么不直接给上游提 PR

上游修复 PR [#5601](https://github.com/anthropics/claude-plugins-official/pull/5601) 于 2026-08-24 被 github-actions 机器人关闭，留言："This repo only accepts contributions from Anthropic team members." 该仓库不接受外部贡献。因此本移植版直接携带修复，并在此逐条注明来源，以便上游团队或后来者查证。

上游 hookify 相关 open issue（2026-09-15 查询）：#544、#3712、#4787、#5368、#5602。本版已处理 #3712、#4787、#5368、#5602；#544（字段名不匹配导致规则静默失效）描述较泛，本版的 `prompt`/`user_prompt`、`tool_response`/`tool_result` 兼容可能覆盖其部分场景，未逐一验证。

## 保留

规则文件格式、frontmatter 字段名、操作符名、事件名、"永远 exit 0"的安全设计——与原版一致。
