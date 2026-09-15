---
name: build-workbuddy-connector
description: 当用户要为 WorkBuddy 做连接器、接入外部工具或服务、把一个命令行工具或 MCP 服务器上架到 WorkBuddy 连接器市场、写 connector-meta.json 或 cli.json 或 mcp.json、把 CLI-Anything 的 harness 封装成连接器、或问「怎么把 X 接进 WorkBuddy」「连接器怎么提交」「审核要什么」时使用。也用于校验一个已有连接器目录是否符合开放平台规范。
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["python3"] },
        "os": ["darwin", "linux", "win32"],
        "emoji": "🔌"
      }
  }
---

# 为 WorkBuddy 构建连接器

连接器是 WorkBuddy 接外部世界的标准包：一份元信息、一份接入配置、一个图标、一组 Skill。规范完整公开，审核 10–15 分钟。**大多数连接器不需要写代码，只需要把已有的 CLI 或 MCP 服务器按规范包起来。**

规范全文与字段形状见 `references/spec.md`，来源 https://open.workbuddy.cn/docs/connector。

## 第 1 步：先问清楚，再选形态

一次性问完，不要一个一个问：

1. 要接的东西是**命令行工具**、**MCP 服务器**、还是**只有 HTTP API**？
2. 需要登录吗？用什么方式（API key / OAuth / 本地会话）？
3. 跑在用户本机，还是远端服务？

| 情况 | 选 | 原因 |
|---|---|---|
| 已有可 `pip/npm install` 的 CLI，尤其带 `--json` 输出 | **CLI** | 最省事；WorkBuddy 负责安装、状态检查、调用 |
| 已有远程 MCP 服务器（HTTPS） | **MCP** | 用户零安装；一份部署服务所有人 |
| 只有 HTTP API，没有 CLI 也没有 MCP | 先包一层 MCP（远程 streamableHttp） | 规范默认推荐远程；本地 stdio 分发痛苦 |
| 要操作用户本机文件或桌面软件 | **CLI** | MCP 远程模式碰不到本机 |

拿不准时选 CLI。CLI-Anything 已经把 80 个桌面/服务软件做成了 agent-native CLI，可以直接封装，见下文。

## 第 2 步：写四个文件

```
<connector>/
├── connector-meta.json     元信息 + 双语示例
├── cli.json | mcp.json     按 type 二选一
├── icon.svg                透明底，小尺寸能认出
└── skills/<name>/SKILL.md  教 Agent 怎么用这个连接器
```

用脚手架生成骨架，再手改：

```bash
python3 {baseDir}/scripts/scaffold_connector.py --out ./my-connector --type cli \
  --source my-tool --name-zh "我的工具" --name-en "My Tool" \
  --desc-zh "一句话说清楚它能干什么，20 到 100 字" --desc-en "What it does, 20-100 chars" \
  --install "pip3 install my-tool" --status "my-tool --version" --status-match "my-tool" \
  --runtime python:3.10
```

关键字段的硬规则：

- `source`：kebab-case，**全局唯一**。建议加前缀避免撞名，如 `cli-anything-mermaid`
- `examples_zh` / `examples_en`：**字符串数组**，各 2–5 条，写用户真的会说的话
- `description*`：20–100 字。写"能干什么"，不写"是什么"
- `cli.json.init`：三个平台各**一个字符串**命令；`win32` 注意 `.cmd` 后缀
- 有鉴权就必须有 `unAuth` 和非破坏性的 `status`；`statusMatch` 与 `statusMatchJson` 二选一
- 鉴权过程 **10 秒内**必须完成，否则被杀
- `mcp.json`：**只能一个** server；远程必须 HTTPS
- 任何文件**不得含凭证**；MCP 用 `${VAR}` + `token-schema.json`

## 第 3 步：SKILL.md 决定连接器好不好用

WorkBuddy 调用连接器时读的是你的 SKILL.md。它要回答四个问题：

1. **什么时候用**——写进 `description`，用用户会说的中文触发词
2. **怎么调**——固定工作流，每条命令可复制，加 `--json`，用绝对路径
3. **出错怎么办**——常见错误对照表
4. **不能干什么**——前置条件、网络依赖、数据会发到哪

不要把 CLI 的 `--help` 全文贴进去。挑 Agent 真会用到的 5–8 条命令，给一条完整可跑的序列。

## 第 4 步：校验，再提交

```bash
python3 {baseDir}/scripts/validate_connector.py ./my-connector
```

0 FAIL 才提交。WARN 逐条看，多数是描述长度和缺平台。提交入口在 open.workbuddy.cn 开放平台后台。

## 桥：把 CLI-Anything 的 harness 封装成连接器

[CLI-Anything](https://github.com/HKUDS/CLI-Anything)（Apache-2.0）的 `registry.json` 每条有 `install_cmd`、`entry_point`、`skill_md`、`requires`，与连接器字段一一对应：

```bash
python3 {baseDir}/scripts/scaffold_connector.py --from-cli-anything /path/to/CLI-Anything/registry.json drawio \
  --harness-root /path/to/CLI-Anything --out ./drawio-connector
```

脚手架会读 registry 填元信息、把 `install_cmd` 写进 `init`、用 `<entry_point> --help` 做状态检查、复制 harness 自带的 SKILL.md。然后你要做三件事：

1. **核实安装命令真能装**。registry 里的 `install_cmd` 是 git 子目录安装；有的 harness 已发 PyPI（如 `cli-anything-drawio`、`cli-anything-n8n`），改成 PyPI 包名更快。有的 harness 文档写了 PyPI 但其实没发（如 mermaid），别信文档，`pip index versions <包名>` 查
2. **中文化并精简 SKILL.md**，补触发词、补错误处理，跑一遍命令序列确认准确
3. **署名**：保留 Apache LICENSE，`ATTRIBUTION.md` 写原项目、harness contributor、改动清单

完整样例见本仓库 `ported/connectors/mermaid/`。

## 常见错误

| 错误 | 后果 |
|---|---|
| `examples_zh` 写成对象数组 | 审核不过。必须是字符串数组 |
| `source` 用了下划线或大写 | 审核不过 |
| `init` 写成命令数组 | 审核不过。每平台一个字符串，多步用 `&&` |
| 鉴权走浏览器 OAuth 等回调 | 10 秒后被杀。用 Device Code Flow |
| SKILL.md 只有命令没有"什么时候用" | 连接器装上了但 Agent 永远不会主动调它 |
| 把内网地址写进 `mcp.json` | 审核不过，且泄露 |

---

结构参考了 Anthropic 官方 `mcp-server-dev` 插件的 build-mcp-server 技能（Apache-2.0）的分阶段问询法；规范内容全部来自 WorkBuddy 官方文档。
