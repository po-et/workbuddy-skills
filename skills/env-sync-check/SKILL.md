---
name: env-sync-check
description: 环境变量配置一致性检查、.env.example 与 .env 对比、缺失环境变量、代码里读了但没登记的配置项、僵尸配置项、.env 里疑似真实密钥、新人搭环境总是缺变量、部署到新环境报「配置未设置」。当用户说「检查一下 .env 和 .env.example 是不是对得上」「哪些环境变量代码在用但示例里没有」「上线前核对一下环境配置」「新同事按 .env.example 起不来服务」时使用。附纯标准库脚本 scripts/env_sync_check.py：解析 .env 系列文件，扫描 Python / Node / Go / Java / Ruby / PHP / Rust / Shell / Compose 里的环境变量读取，输出五类问题（环境文件缺变量、未登记变量、代码读取未登记、示例登记未使用、疑似真实密钥）与重复定义，支持 --json 与 --strict 门禁。
author: Captain
version: 0.1.0
display_name: ".env 一致性检查"
display_name_en: "Env Sync Check"
description_zh: "让 .env.example、各环境 .env 与代码实际读取的变量三方对齐：找缺失、找未登记、找僵尸项、找示例文件里的真实密钥；多语言读取模式识别；纯 Python 标准库，可作 CI 门禁。"
description_en: "Keep .env.example, per-environment .env files and the variables your code actually reads in sync: find missing, unregistered and dead variables plus real secrets in example files; multi-language read-pattern detection; pure Python stdlib, CI-gate ready."
examples_zh:
  - "检查当前项目的 .env.production 是否缺少 .env.example 里的变量"
  - "找出代码里读取了但 .env.example 没登记的环境变量"
  - "上线前把环境变量核对加进 CI"
examples_en:
  - "Check whether .env.production is missing variables from .env.example"
  - "Find env vars the code reads that .env.example doesn't document"
  - "Add the env-var check to CI before release"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧾" } }
---

# .env 一致性检查

三方对齐：**示例文件**（`.env.example`）、**环境文件**（`.env`、`.env.production` …）、**代码实际读取的变量**。缺一个变量往往要到部署后才炸；示例文件里混进真实密钥则会被提交进仓库。

## 用法

```bash
python3 scripts/env_sync_check.py                                   # 当前目录：自动找示例与 .env*，扫描代码
python3 scripts/env_sync_check.py --example .env.example --env .env.production --env .env.staging --src .
python3 scripts/env_sync_check.py --json
python3 scripts/env_sync_check.py --strict                          # 有「缺变量」或「示例含真实密钥」则退出码 1
```

## 输出五类

| 级别 | 类型 | 含义 | 处理 |
|---|---|---|---|
| high | missing | 环境文件缺少示例登记的变量 | 补上，或从示例删除已废弃项 |
| high | secret-in-example | 示例文件里的值像真实密钥 | 换成占位符；若已提交，轮换该密钥 |
| warn | undocumented | 代码读取了但示例没登记 | 登记到示例并写注释说明用途 |
| warn | secret | 环境文件里像真实密钥 | 确认在 .gitignore 中、未被提交 |
| warn | duplicate | 同一文件重复定义 | 删多余的，后者生效易误导 |
| info | unregistered | 环境文件有、示例没有 | 视情况登记 |
| info | unused | 示例登记但代码没读 | 可能是框架/配置库间接读取；确认后删除僵尸项 |

## 流程

1. 跑脚本；先处理 high，再处理 undocumented（这是新人「起不来服务」的主要原因）。
2. 给示例文件里每个变量加一行注释：用途、格式、是否必填、示例值。
3. 加进 CI（`--strict`），并在 PR 模板里加「新增环境变量已登记到 .env.example」。

## 边界

- 读取模式靠正则识别常见写法（`os.environ["X"]`、`process.env.X`、`os.Getenv("X")`、`${X}` 等）；通过配置库（pydantic-settings、dotenv 自动注入、Spring `@Value`）间接读取的变量识别不到，会出现在 unused 里，需人工确认。
- 只匹配全大写的变量名；小写或动态拼接的名字不识别。
- 密钥判断是启发式（名字含 SECRET/TOKEN/KEY/PASSWORD 等且值不是占位符、长度 ≥ 12），可能误报。
