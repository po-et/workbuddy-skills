---
name: dep-outdated-check
description: 依赖过期检查、哪些依赖落后了几个大版本、升级依赖前摸底、多语言依赖清单（requirements.txt / pyproject / package.json / go.mod / Cargo.toml / Gemfile / composer.json）对比公共注册表最新版本、未固定版本的依赖、技术债盘点。当用户说「看看我们的依赖有哪些该升级了」「哪些包落后了主版本」「升级前先列个清单」「requirements 里哪些没锁版本」时使用。附纯标准库脚本 scripts/dep_outdated.py（需联网）：解析七种清单，并发查询 PyPI / npm / Go proxy / crates.io / RubyGems / Packagist 的最新稳定版，按主版本/次版本/补丁/未固定分级输出并给升级策略；支持 HTTPS_PROXY 与 PyPI/npm 兼容私有源、--json。与「依赖漏洞检查」技能互补。
author: Captain
version: 0.1.0
display_name: "依赖过期检查"
display_name_en: "Dependency Outdated Check"
description_zh: "一条命令查清项目依赖落后了多少：解析 Python / Node / Go / Rust / Ruby / PHP 七种清单，并发查询公共注册表最新稳定版，按主/次/补丁/未固定分级并给升级顺序建议；纯 Python 标准库，需联网。"
description_en: "One command to see how far your dependencies lag: parses seven manifest types across Python / Node / Go / Rust / Ruby / PHP, queries public registries concurrently for the latest stable version, grades by major/minor/patch/unpinned with an upgrade order; pure Python stdlib, needs network."
examples_zh:
  - "检查当前项目的依赖哪些落后了主版本"
  - "requirements.txt 和 package.json 里哪些包该升级"
  - "升级前给我一份分级清单，主版本的单独列"
examples_en:
  - "Which dependencies in this project lag a major version?"
  - "Which packages in requirements.txt and package.json should be upgraded?"
  - "Give me a graded upgrade list, majors separately"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📦" } }
---

# 依赖过期检查

升级依赖之前先知道落后了多少。脚本读清单、查注册表、按落后程度分级；主版本单独处理，次版本与补丁可以批量。

## 用法

```bash
python3 scripts/dep_outdated.py                       # 当前目录自动找清单
python3 scripts/dep_outdated.py backend/ frontend/package.json
python3 scripts/dep_outdated.py --json > outdated.json
HTTPS_PROXY=http://proxy:3128 python3 scripts/dep_outdated.py
PIP_INDEX_URL=https://mirror.example.com/simple NPM_REGISTRY=https://npm.example.com python3 scripts/dep_outdated.py
```

## 流程

1. 跑脚本看分级：**主版本**逐个升级，先读 CHANGELOG / 迁移指南的 breaking 部分，各自一个 PR；**次版本 / 补丁**可批量升级后跑全量测试；**未固定**的先锁版本或引入 lockfile。
2. 与「依赖漏洞检查」技能配合：有漏洞的优先，其余按落后程度排期。
3. 把脚本接进每周定时任务，输出 `--json` 后统计「主版本落后数」的趋势。

## 支持的清单与注册表

| 清单 | 生态 | 查询源 |
|---|---|---|
| requirements*.txt、pyproject.toml（PEP 621 / Poetry） | Python | PyPI Simple JSON API（可换私有源） |
| package.json（dependencies / devDependencies） | Node | npm registry（可换私有源） |
| go.mod（直接依赖） | Go | proxy.golang.org |
| Cargo.toml | Rust | crates.io |
| Gemfile | Ruby | rubygems.org |
| composer.json | PHP | packagist.org |

## 边界

- 只比较「当前写法 vs 最新稳定版」，不解析语义化范围能否已覆盖（`^4.17.0` 与 5.x 仍算主版本落后）；lockfile 里的实际安装版本请用各生态自带命令（`pip list --outdated`、`npm outdated`）。
- 预发布版本（rc / beta / alpha）不算最新。
- Go 的 `// indirect` 依赖跳过；私有 Go 模块无法从公共代理查询，会标「查询失败」。
- 需要联网；企业内网请配置代理或私有源。
