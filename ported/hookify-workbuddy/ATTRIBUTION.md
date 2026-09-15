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
| **修复 `contains` / `not_contains` 不支持 `a\|b` 任一匹配** | 上游 bug：其自带 `require-tests-stop` 示例用 `not_contains: npm test\|pytest`，`\|` 被当字面串，规则永远命中 |
| 入口脚本自定位插件根（`__file__`），环境变量存在时优先 | 不依赖运行时一定注入 `*_PLUGIN_ROOT` |
| 移除 `/hookify` 斜杠命令与 conversation-analyzer 子代理 | 依赖 Claude Code 命令机制；"从描述生成规则"的职责并入 skill |
| 全部中文化：错误信息、示例、README、Skill | 面向中文用户 |
| 新增 13 个端到端测试 | 上游无测试 |

## 保留

规则文件格式、frontmatter 字段名、操作符名、事件名、"永远 exit 0"的安全设计——与原版一致。
