---
name: secrets-scan
description: 仓库泄密自查、密钥硬编码扫描、secret scanning、提交历史查密钥、AK/SK 泄露排查、token 误提交、上线前安全自查、敏感信息检查。当用户说「看看仓库里有没有把密钥提交上去」「扫一下有没有硬编码的密码」「历史提交里是不是有 token」「上线前做一次泄密自查」「.env 是不是混进了真实密钥」时使用。附纯标准库脚本 scripts/secrets_scan.py：16 条规则覆盖 AWS AK/SK、GitHub/GitLab token、Slack token 与 webhook、私钥块、JWT、Google/Stripe/npm 密钥、带口令的数据库连接串与通用 api_key/secret/password 赋值，可选高熵字符串；命中值只显示前 4 后 4 位，给出文件行号、类型、级别与轮换改法；支持 --history N 扫最近提交、.secretsignore 忽略、--exclude、--json 与 --strict 门禁。
author: Captain
version: 0.1.0
display_name: "仓库泄密自查"
display_name_en: "Secrets Scan"
description_zh: "一条命令扫出仓库里硬编码的密钥与口令，工作树加最近提交历史一起查；命中值脱敏成前 4 后 4 位，按 high/warn/info 分级并给出轮换改法；纯 Python 标准库，可作 CI 门禁。"
description_en: "One command to find hardcoded secrets in your repo, scanning the working tree plus recent commit history; matches are masked to first four and last four characters, graded high/warn/info with rotation advice; pure Python stdlib, usable as a CI gate."
examples_zh:
  - "帮我做一次密钥硬编码扫描，看看仓库里有没有真凭据"
  - "提交历史查密钥，最近 50 个提交有没有误提交 token"
  - "上线前安全自查，把这个检查加进 CI 门禁，发现 high 就卡住发布"
examples_en:
  - "Scan this repository for hardcoded secrets"
  - "Check the last 50 commits for accidentally committed tokens"
  - "Add the secret scan to CI and fail the build on high findings"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "git"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔐" } }
---

# 仓库泄密自查

用于在代码进入评审、镜像或开源之前，自查仓库里有没有硬编码的密钥、口令与私钥。只读扫描，不联网、不上报、不改动文件；命中值一律脱敏，报告可以直接贴进工单。

## 用法

```bash
python3 scripts/secrets_scan.py                       # 扫当前目录工作树
python3 scripts/secrets_scan.py src/ config/          # 只扫指定目录或文件
python3 scripts/secrets_scan.py --history 50          # 额外扫最近 50 个提交的新增行
python3 scripts/secrets_scan.py --entropy             # 打开高熵字符串检测（info 级，噪声多）
python3 scripts/secrets_scan.py --min-severity warn   # 只看 high 与 warn
python3 scripts/secrets_scan.py --exclude fixtures --json
python3 scripts/secrets_scan.py --strict              # 有 high/warn 则退出码 1，用于 CI 门禁
```

git 路径可用环境变量 `GIT_BIN` 覆盖（默认 `git`），例如 `GIT_BIN=/usr/local/bin/git python3 scripts/secrets_scan.py --history 20`。

## 流程

1. 先跑一次不带参数的扫描，看 **high**：这些是形态明确的真凭据（AK/SK、token、私钥、带口令的连接串）。
2. 逐条确认是不是真密钥。**确认为真的第一步永远是吊销和轮换**，不是删代码——历史里已经存在，删文件不等于失效。
3. 轮换完再处理仓库：把值挪到环境变量或密钥管理服务，配置文件只留占位符，补 `.gitignore`。
4. 加 `--history N` 回扫历史，确认这枚密钥是什么时候、被谁带进来的，判断暴露窗口。
5. 误报写进 `.secretsignore`，然后把 `--strict` 挂到 CI 或 pre-commit 上，防止再次带入。

## 规则一览

| 级别 | 规则 | 命中形态 |
|---|---|---|
| high | SEC001 / SEC002 | AWS Access Key ID；AWS Secret Access Key 赋值 |
| high | SEC003 / SEC004 | GitHub token（含 fine-grained PAT）；GitLab Personal Access Token |
| high | SEC005 / SEC006 | Slack token；Slack Incoming Webhook URL |
| high | SEC007 | 私钥文件块（PEM 开头的 RSA/EC/OPENSSH 私钥） |
| high | SEC008 / SEC009 / SEC010 / SEC011 | Google API Key；Stripe 线上密钥；npm token；sk- 前缀平台密钥 |
| high | SEC012 | 数据库连接串含明文口令（mysql/postgres/mongodb/redis/amqp/jdbc 等） |
| warn | SEC013 / SEC014 | URL 内嵌基本认证口令；JWT |
| warn | SEC015 | 通用赋值 password/secret/api_key/token/client_secret = "…" |
| info | SEC016 | 高熵字符串（仅 `--entropy` 开启） |

占位符会自动跳过：`xxx`、`your_token`、`changeme`、`${VAR}`、`{{ .Values.x }}`、含 `example`/`dummy`/`placeholder` 的值，以及单行注释 `secrets-scan: ignore` / `pragma: allowlist secret`。

## 输出

文本模式按 `级别 / 规则号 / 文件:行号 / 类型 / 脱敏值 / 改法` 输出，末尾给 high、warn、info 小计；`--json` 输出 `worktree`、`history`、`summary` 三段，便于接告警或做趋势统计。脱敏规则固定为前 4 位加后 4 位，中间用 `*` 填充并附原始长度，报告不会泄露第二次。

## 忽略文件

仓库根目录放 `.secretsignore`，一行一条：

```text
# 路径 glob（匹配相对路径、文件名或任一路径段）
tests/fixtures/*
*.min.js
# re: 开头是「值白名单」正则，用于放过哈希、校验和这类误报
re:^[0-9a-f]{40}$
```

## 边界

- 正则启发式，**不做**语义判断：混淆过的密钥、拆成多段拼接的密钥、二进制文件里的密钥都扫不出来。
- 默认跳过 `.git`、`node_modules`、`vendor`、`dist`、`target` 等目录、常见二进制后缀与超过 2MB 的文件，可用 `--max-bytes` 调整。
- `--history N` 只看最近 N 个提交的**新增行**，不是全历史；要彻底清理历史请配合 `git filter-repo`，且清理前必须先完成轮换。
- 常见问题：CI 里 `--strict` 频繁挂掉，多半是测试夹具里的假密钥——把夹具目录写进 `.secretsignore` 或加 `--exclude`，不要为此关掉整条门禁。
- 本技能只做防御性自查，不提供任何利用、解密或外发能力。
