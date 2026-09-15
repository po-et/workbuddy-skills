# hookify-workbuddy

> 用一个 Markdown 文件定义 Hook。拦截危险命令、提醒敏感文件、强制完成检查、自动注入上下文。
> **同一份规则在 WorkBuddy、CodeBuddy、Claude Code 三处通用。**

修改自 Anthropic 官方插件 [hookify](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/hookify)（Apache-2.0）。改动与理由见 [ATTRIBUTION.md](ATTRIBUTION.md)。

## 为什么需要它

WorkBuddy 的 Hooks 很强，但要在 `settings.json` 里写 JSON、写脚本、处理 stdin/stdout 协议。
hookify 把这件事变成：

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

保存到 `<项目>/.codebuddy/hookify.block-dangerous-rm.local.md`，下一次工具调用即生效。不重启，不改 settings。

## 为什么能三处通用

WorkBuddy 官方文档写明 Hook 机制"完全兼容 Claude Code Hooks 规范"；CodeBuddy 插件参考写明 `.codebuddy-plugin/` 兼容回退 `.claude-plugin/`，且"插件在 CodeBuddy 与 WorkBuddy 间通用"。
本项目在此基础上抹平了三处已知字段差异（`prompt`/`user_prompt`、`tool_response`/`tool_result`、规则目录），并修了上游一个 `not_contains` 不支持 `a|b` 的 bug。

## 安装

### 方式 A：手动接入 settings.json（最稳，已验证脚本行为）

1. 把本目录放到固定位置，例如 `~/.codebuddy/plugins/hookify-workbuddy/`
2. 把 [`hooks/hooks.json`](hooks/hooks.json) 里 `hooks` 一节合并进 `~/.codebuddy/settings.json`（或项目的 `.codebuddy/settings.json`），并把 `${CODEBUDDY_PLUGIN_ROOT}` 替换为实际绝对路径
3. 在项目根建 `.codebuddy/`，放入 `examples/` 里的规则文件试试

### 方式 B：作为插件安装

本目录已带 `.codebuddy-plugin/plugin.json`、`.workbuddy-plugin/plugin.json`、`.claude-plugin/plugin.json` 三份清单与 `hooks/hooks.json`，符合 CodeBuddy/WorkBuddy 插件目录规范。
【待确认】客户端内从本地目录或 GitHub 安装第三方插件的具体入口，以官方文档为准。

### 方式 C：Claude Code

```bash
claude plugin add /path/to/hookify-workbuddy
```

规则文件放 `.claude/` 或 `.codebuddy/` 均可。

## 写规则

见 [`skills/writing-hookify-rules/SKILL.md`](skills/writing-hookify-rules/SKILL.md)。装了本插件后，直接对 Agent 说"以后别在 TS 里用 console.log"，它会按这个 Skill 帮你生成规则文件。

四个开箱示例在 [`examples/`](examples/)：拦截 `rm -rf`、敏感文件提醒、未跑测试不许结束（默认关）、提到上线自动注入检查清单。

## 测试

```bash
python3 -m unittest tests.test_hooks -v
```

13 个端到端用例：以 stdin JSON 驱动真实入口脚本，覆盖 4 个事件 × 拒绝/提醒/放行、两套字段名兼容、目录优先级、坏规则文件不卡死 Agent。

## 安全设计

- 入口脚本**永远 exit 0**。hookify 自己出错绝不能把 Agent 卡死，错误通过 `systemMessage` 报告
- `block` 只在 PreToolUse（拦截工具调用）和 Stop（阻止结束）生效
- 规则文件是本地文件，不上传

## 协议

Apache License 2.0。原作者 Anthropic, PBC；派生改动 © 2026 Captain。见 `LICENSE`、`NOTICE`、`ATTRIBUTION.md`。
