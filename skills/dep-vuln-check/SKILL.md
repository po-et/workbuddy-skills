---
name: dep-vuln-check
description: 依赖漏洞体检、第三方库安全扫描、供应链安全检查。当用户要「查一下项目依赖有没有漏洞」「扫描 CVE」「package-lock / requirements.txt / go.sum / Cargo.lock 安全检查」「这个版本的 lodash / django / log4j 有没有已知漏洞」「上线前依赖安全审计」「SCA 软件成分分析」「该升级哪些依赖」「npm audit / pip-audit 的替代」时使用。脚本解析锁文件后查询 OSV.dev（免费、无需 API Key、覆盖 npm/PyPI/Go/crates.io/RubyGems/Packagist），输出严重度、漏洞编号（CVE/GHSA）、建议升级版本；不检查自己写的代码，不会把"未收录"说成"安全"。
author: Captain
version: 0.1.0
display_name: "依赖漏洞体检"
display_name_en: "Dependency Vulnerability Check"
description_zh: "解析 npm/pip/go/cargo/gem/composer 锁文件，查询 OSV.dev 已知漏洞（免 API Key），输出严重度、CVE/GHSA 编号与建议升级版本。"
description_en: "Parse npm/pip/go/cargo/gem/composer lockfiles, query OSV.dev for known vulnerabilities (no API key), report severity, CVE/GHSA ids and the version to upgrade to."
examples_zh:
  - "扫描这个项目的依赖有没有已知漏洞"
  - "requirements.txt 里哪些包该升级？给我 CVE 编号"
  - "上线前做一次依赖安全审计，按严重度排序"
examples_en:
  - "Scan this project's dependencies for known vulnerabilities"
  - "Which packages in requirements.txt need upgrading? Include CVE ids"
  - "Run a pre-release dependency audit sorted by severity"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🛡️" } }
---

# 依赖漏洞体检

用 OSV.dev 的公开数据给项目的第三方依赖做一次已知漏洞检查。**免费、无需 Key、零第三方依赖**，需要能访问 `api.osv.dev`。

## 核心原则

1. **只报数据库里有的。** 每条漏洞附 OSV/GHSA/CVE 编号，用户可以自己去核。
2. **"未发现"不等于"安全"。** 报告里必须写明：未收录 ≠ 不存在；本工具不看你自己的代码；无固定版本的依赖没有被查。
3. **升级建议要可执行。** 给出「建议升级到」版本，同时提醒看变更日志确认兼容；大版本跳跃要单独标出。
4. **先修最严重的。** 按 CRITICAL → HIGH → MODERATE → LOW → UNKNOWN 排序，UNKNOWN 需要人工点开链接看。

## 执行流程

### 第 1 步：扫描

```bash
python3 {baseDir}/scripts/osv_check.py --path <仓库路径或锁文件> --md out/vulns.md --out out/vulns.json
```

自动发现：`package-lock.json`（v1/v2/v3）、`requirements*.txt`（仅 `==` 固定版本）、`poetry.lock`、`Pipfile.lock`、`go.mod` / `go.sum`、`Cargo.lock`、`Gemfile.lock`、`composer.lock`；跳过 `node_modules` / `.venv` / `vendor`。
`--max-details N` 控制抓取详情的漏洞条数（默认 200，每个包保证至少一条）；`--fail-on high` 让 CI 在存在高危时非零退出。

### 第 2 步：解读（这一步由你做）

- 把表格按严重度讲一遍：哪几个必须今天修（CRITICAL/HIGH 且有修复版本）、哪些可以排期、哪些是 UNKNOWN 需要人工看。
- 对每个要升级的依赖，说明从当前版本到建议版本是否跨大版本；跨大版本的提醒用户查迁移指南。
- 同一漏洞出现在多个别名（CVE / GHSA / PYSEC）时合并说，不要按条数吓人。
- 传递依赖（不是用户直接引入的）要说明升级路径：升级引入它的那个直接依赖。

### 第 3 步：交付

Markdown 报告 + 一份可执行的升级清单（命令级：`pip install "django>=6.0.8"` / `npm install lodash@latest`），并附上「未查到的依赖」清单。

## 输出契约

```
# 依赖漏洞体检
- 扫描文件 / 依赖总数 / 有漏洞的依赖 / 漏洞条目
| 严重度 | 依赖 | 当前版本 | 漏洞（编号+别名） | 建议升级到 | 来源文件 |
## 升级清单（命令）
## 未查到 / 需人工确认
## 说明（数据来源与局限）
```

## 常见问题

**没有锁文件？** 先 `npm i --package-lock-only` / `pip freeze > requirements.txt` 生成，再扫。
**内网不能访问 api.osv.dev？** 脚本会明确报错退出码 3；可把锁文件拷到能联网的机器扫，不要为此传任何凭证。
**Maven / Gradle？** 暂不解析（需要依赖解析树）；可用 `mvn dependency:list` 导出后手工整理成 `requirements` 风格再查，或提需求。
