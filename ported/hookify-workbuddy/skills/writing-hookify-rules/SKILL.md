---
name: writing-hookify-rules
description: 当用户想让 Agent「以后别再这样做」、要拦截危险命令、要在编辑敏感文件时提醒、要在结束前强制检查、要在提到上线时自动注入检查清单，或说「加个规则」「写个 hook」「禁止 rm -rf」「改 .env 之前提醒我」「没跑测试不许结束」「配置 hookify」时使用。适用于 WorkBuddy、CodeBuddy、Claude Code，同一份规则三处通用。
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["python3"] },
        "os": ["darwin", "linux", "win32"],
        "emoji": "🪝"
      }
  }
---

# 编写 hookify 规则

一条规则 = 一个 Markdown 文件：YAML frontmatter 定义"什么时候触发"，正文是"触发时给 Agent 看的话"。
不用改 `settings.json`，不用重启，写完下一次工具调用就生效。

## 文件放哪

`<项目根>/.codebuddy/hookify.<规则名>.local.md`

也认 `.claude/` 目录（Claude Code 兼容）。同名规则以 `.codebuddy/` 为准。建议把 `*.local.md` 加进 `.gitignore`。

## 最小规则

```markdown
---
name: block-dangerous-rm
enabled: true
event: bash
pattern: rm\s+-rf
action: block
---

⚠️ 检测到危险的 rm 命令，已拦截。请先确认路径，或改用更安全的方式。
```

## 字段

| 字段 | 必填 | 取值 |
|---|---|---|
| `name` | 是 | kebab-case，动词开头：`block-` / `warn-` / `require-` |
| `enabled` | 是 | `true` / `false`，关掉不用删文件 |
| `event` | 是 | `bash` 命令 · `file` 写文件 · `stop` 要结束时 · `prompt` 用户输入时 · `all` |
| `action` | 否 | `warn` 提醒但放行（默认）· `block` 拦截（PreToolUse）或阻止结束（Stop） |
| `pattern` | 二选一 | 简单模式：一条正则，`bash` 匹配命令、`file` 匹配写入内容、`prompt` 匹配用户输入 |
| `conditions` | 二选一 | 多条件，全部满足才触发 |

## 多条件

```markdown
---
name: warn-env-edits
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.env$
  - field: new_text
    operator: contains
    pattern: KEY|TOKEN|SECRET
---

你正在往 .env 写疑似凭证。确认已在 .gitignore。
```

`field` 按事件取：
- `bash`：`command`
- `file`：`file_path`、`new_text`、`old_text`、`content`
- `stop`：`transcript`（整段会话记录）、`reason`
- `prompt`：`user_prompt`

`operator`：`regex_match` · `contains` · `not_contains` · `equals` · `starts_with` · `ends_with`。
`contains` / `not_contains` 支持 `a|b|c`，任一命中即算。

## 四类典型规则

**拦截危险命令**（`bash` + `block`）：`rm\s+-rf`、`sudo\s+`、`chmod\s+777`、`dd\s+if=`、`git\s+push\s+.*--force`、`DROP\s+TABLE`

**敏感文件提醒**（`file` + `warn`）：`\.env$|credentials|secrets|\.pem$|id_rsa`

**完成前检查**（`stop` + `block`）：`transcript` `not_contains` `pytest|npm test`。会阻止会话结束，慎开。

**上下文注入**（`prompt` + `warn`）：用户说"上线"时把检查清单塞给 Agent。

## 写消息的原则

消息是给 Agent 看的，不是给人看的。要让它**知道接下来该怎么做**：

- 说明检测到什么、为什么有问题
- 给替代做法
- 需要人确认的，明确写"把命令贴给用户确认"

## 从一句话生成规则

用户说"以后别在 TypeScript 里用 console.log"→

1. 涉及哪个工具？写文件 → `event: file`
2. 匹配什么？文件名 `\.tsx?$` 且内容 `console\.log\(`
3. 拦还是提醒？提醒 → `action: warn`
4. 起名：`warn-console-log-ts`
5. 写进 `.codebuddy/hookify.warn-console-log-ts.local.md`

## 正则要点

- 用 `\s+` 不用空格：`rm\s+-rf` 才能匹配 `rm  -rf`
- 点要转义：`console\.log\(`
- YAML 里**不要加引号**，加了引号反斜杠要写两个
- 别写太宽：`log` 会匹配 `login`、`dialog`

## 常见问题

| 问题 | 原因 |
|---|---|
| 规则不生效 | 文件名少了 `hookify.` 前缀或 `.local.md` 后缀；或 `enabled: false` |
| `block` 没拦住 | `event: file` 的 block 只在 PreToolUse 生效；PostToolUse 只能提醒 |
| `stop` 规则把会话卡住 | 这是设计行为。改 `enabled: false` 或放宽 `pattern` |
| Windows 下不跑 | hooks 必须走 Git Bash；`hooks.json` 用 `python3 x.py` 不用直接执行 |

更多示例见插件 `examples/` 目录。
