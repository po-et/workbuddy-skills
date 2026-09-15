# WorkBuddy 连接器规范速查

来源：https://open.workbuddy.cn/docs/connector（2026-09-15 抄录，以官方为准）。审核通常 10–15 分钟。

## 目录

```
<connector>/
├── connector-meta.json     必须
├── cli.json  或  mcp.json  必须（按 type）
├── icon.svg                必须（也接受 icon.png / icon.jpg，光栅建议 64×64，透明底）
├── token-schema.json       仅 MCP token 模式
└── skills/<name>/SKILL.md  CLI 强烈建议；MCP 可选
```

## connector-meta.json

```json
{
  "name": "任务管理",
  "name_zh": "任务管理",
  "name_en": "Task Manager",
  "description": "Create and manage tasks in WorkBuddy.",
  "description_zh": "通过自然语言创建、查询和更新任务。",
  "description_en": "Create, query, and update tasks with natural language.",
  "source": "task-manager",
  "type": "mcp",
  "version": "1.0.0",
  "minWorkbuddyVersion": "4.23.0",
  "examples_zh": ["创建一个明天下午到期的评审任务", "列出本周尚未完成的任务"],
  "examples_en": ["Create a review task due tomorrow afternoon", "List unfinished tasks for this week"]
}
```

- `source`：kebab-case，全局唯一
- `type`：`cli` | `mcp`
- `description*`：建议 20–100 字
- `examples_zh` / `examples_en`：字符串数组，各 2–5 条
- `minWorkbuddyVersion`：使用新字段时必填，semver 字符串

## cli.json

```json
{
  "runtime": { "type": "node", "version": "20" },
  "init":   { "darwin": "npm install -g your-cli", "linux": "npm install -g your-cli", "win32": "npm install -g your-cli" },
  "auth":   { "darwin": "your-cli auth login",  "linux": "your-cli auth login",  "win32": "your-cli.cmd auth login" },
  "unAuth": { "darwin": "your-cli auth logout", "linux": "your-cli auth logout", "win32": "your-cli.cmd auth logout" },
  "status": { "darwin": "your-cli auth status", "linux": "your-cli auth status", "win32": "your-cli.cmd auth status" },
  "statusMatch": "Logged in",
  "authUrlDomain": "example.com"
}
```

| 字段 | 必须 | 说明 |
|---|---|---|
| `init.{darwin,linux,win32}` | 是 | 每平台**一个字符串**命令 |
| `auth` / `unAuth` / `status` | 有鉴权时 | 同上形状；`status` 必须非破坏性 |
| `statusMatch` 或 `statusMatchJson` | 二选一 | 正则文本 / JSON 匹配 |
| `runtime` | 需要时 | `{"type","version"}`，v5.0.0+ |
| `npmRegistry` / `npmRegistries` | 可选 | npm 镜像回退 |
| `authUrlDomain` | 建议 | 限制可提取的鉴权域名 |
| `authQrModal` | 可选 | 内嵌鉴权链接弹窗 |
| `authDeviceFlow` | 可选 | OAuth 2.0 Device Flow，v5.0.0+ |

硬约束：鉴权过程不得超过 10 秒；WorkBuddy 提取到 URL 后立即终止鉴权子进程，OAuth 回调需 Device Code Flow 或后台守护。

## mcp.json

```json
{
  "mcpServers": {
    "your-service": {
      "type": "streamableHttp",
      "url": "https://example.com/mcp",
      "headers": { "Authorization": "Bearer ${SERVICE_TOKEN}" },
      "timeout": 30000
    }
  }
}
```

- `mcpServers` 只能有**一个** server
- 远程 `type`：`sse` | `streamableHttp`；本地 `stdio` 用 `command` + `args`
- 远程 `url` 必须 HTTPS
- `runtime`（v5.0.0+）、`disabledTools`（v4.22.15+）、`preAuth`（v5.0.0+，仅 cli）可选
- 服务端要求：30 秒内响应、≥99.9% 可用、最小权限鉴权

### token-schema.json（`auth_mode: "token"`）

```json
{
  "title": "Service Configuration",
  "description": "Credentials stored locally only.",
  "docUrl": "https://example.com/docs",
  "fields": [
    { "key": "API_KEY", "label": "Access Token", "type": "password", "required": true,
      "placeholder": "Your token", "description": "Personal access token for API." }
  ]
}
```

`fields[].key` 必须与 mcp.json 中 `${VAR}` 占位符完全一致（区分大小写）；敏感字段 `type: "password"`。

### OAuth（MCP）

服务端需提供：`/.well-known/oauth-protected-resource`、`/.well-known/oauth-authorization-server`、`/oauth/register`（RFC 7591）、`/oauth/authorize`（PKCE S256）、`/oauth/token`（refresh_token）。
回调 URI：`workbuddy://workbuddy/mcp/connector%3A<source>/oauth/callback` 或 `http://127.0.0.1:{port}/oauth/callback`。

## 提交前检查（官方清单）

- 目录结构符合规范；`source` kebab-case 且唯一
- 名称、描述、双语示例完整
- MCP：单 server，远程 HTTPS
- CLI：安装、鉴权、状态检查、登出在三平台验证；登录态重启后仍在；`unAuth` 真正清理凭证
- OAuth：元数据发现、动态注册、PKCE
- token 模式：占位符与字段 key 一致；密码字段标记
- Skill 准确覆盖全部核心能力
- **任何文件不含硬编码凭证**
- 图标清晰可辨；版本与最低 WorkBuddy 版本正确
- 超时、鉴权失败、参数错误的异常处理已覆盖
