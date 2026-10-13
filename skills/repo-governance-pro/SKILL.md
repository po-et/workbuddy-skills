---
name: repo-governance-pro
description: 代码仓库治理助手。接手陌生 Git 仓库、交接项目、盘点仓库结构或检查 README、AGENTS、测试入口、构建配置与 CI 文件时，运行离线脚本，生成带 HEAD、分支、工作区状态、跟踪文件统计与有界 SHA-256 证据的 Markdown 和 JSON 报告。只读本地仓库，不执行项目代码，不联网，不读取未跟踪文件内容；文件存在不代表配置有效或测试通过。分支删除、绩效评价和业务代码修改不在本技能范围内。
author: Captain
homepage: https://github.com/po-et/workbuddy-skills
license: CC-BY-4.0 AND MIT
version: 0.1.3
display_name: "代码仓库治理"
display_name_en: "Repo Governance Pro"
description_zh: "给陌生 Git 仓库做一次离线、有证据的结构盘点：HEAD、分支、工作区状态、README/AGENTS/测试入口/构建/CI/依赖清单及有界文件哈希。输出 Markdown 与 JSON，不执行项目代码，不把文件存在当成测试通过。"
description_en: "Produce an offline Git repository inventory with HEAD, branch, worktree status, tracked documentation/test/build/CI/manifest paths and bounded file hashes. Export Markdown and JSON without running project code or treating file presence as passing tests."
tags:
  - "仓库治理"
  - "项目交接"
  - "代码仓库"
  - "证据报告"
examples_zh:
  - "刚接手一个老仓库，先给我一份可核对的结构盘点"
  - "交接前看看 README、测试入口和 CI 文件是否被跟踪"
  - "盘点这个仓库，生成 Markdown 和 JSON，不运行项目代码"
examples_en:
  - "Inventory this unfamiliar repository without executing its code"
  - "Show tracked documentation, test entry points and CI evidence"
  - "Create Markdown and JSON handover evidence outside the repository"
metadata:
  { "openclaw": { "requires": { "bins": ["git", "python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🏛️" } }
---

# 代码仓库治理

把“先看看仓库”落成两个可复核的文件：`inventory.md` 和 `inventory.json`。Python 3.9+ 与 Git 即可运行，无第三方依赖，无其他技能安装要求。

## 输入与输出

输入是一个本地 Git 工作区目录；从子目录传入也会盘点整个工作区。输出目录必须位于被盘点仓库外，已有同名报告拒绝覆盖。省略 `--out-dir` 会使用系统临时目录，终端返回报告的绝对路径。

```bash
# <skill-dir> 换成本技能安装目录；给实际路径加引号，兼容空格。
python3 "<skill-dir>/scripts/repo_inventory.py" \
  --repo "/path/to/project" \
  --out-dir "/path/to/reports/project-inventory"
```

从本技能目录运行的最短命令：

```bash
python3 scripts/repo_inventory.py --repo "/path/to/project"
```

报告包括：

1. 采集时的 HEAD、分支或 detached HEAD、工作区状态；未跟踪文件只计数，不列路径或读取内容。
2. 跟踪文件的一级目录与扩展名分布；README、AGENTS、测试、构建、CI、依赖清单按**路径规则**分类。
3. 分类文件的相对路径、可读取状态和 SHA-256；默认最多 64 项证据、每项最多 1 MiB。超限、删除、符号链接、子模块单独标明，不编造哈希。
4. 采集开始与结束的 HEAD、索引及工作区状态是否相同。发生变化时报告标注 `changed_during_collection`，不可当成同一时点的完整快照。

## 执行顺序

1. 确认用户给出的仓库目录，运行上述命令。不要执行仓库中的安装脚本、构建命令或测试；不要为盘点而拉取远端。
2. 先读 JSON 的 `snapshot.consistent`、`git.head`、`git.worktree` 和 `limits`。没有 HEAD 的空仓库也是有效输入；非 Git 目录或裸仓库会返回错误。
3. 根据 `signals` 中的路径与 `evidence` 定位缺口。写“未发现被跟踪的 CI 配置”，不要写“没有 CI”；写“存在测试路径”，不要写“测试已通过”。
4. 交付报告的**绝对路径链接**，附最多三项有路径证据的下一步建议。需要进一步核查文件内容或执行测试时，作为后续任务，不冒充本轮已验证。

退出码：`0` 两份报告已生成；`2` 输入、Git 查询或输出失败。`0` 只表示盘点完成，工作区可能是脏的，证据可能被截断，项目测试可能从未执行。

## 可调参数

```bash
python3 scripts/repo_inventory.py --repo "/path/to/project" \
  --out-dir "/path/to/reports/inventory" \
  --max-evidence 32 --max-file-bytes 524288
```

完整规则与 JSON 字段见 [报告契约](references/report-contract.md)，判读示例见 [示例](examples/handover.md)。

## 边界

- Git 查询只读，禁用可选锁和文件监控；不运行钩子、项目代码、网络访问或第三方服务，不改变索引、分支、代码。
- 不输出文件内容、提交作者、邮箱、远端地址或未跟踪路径。相对路径和分支名仍可能敏感；报告默认供本地审阅，公开前由使用者确认范围。
- 不跟随被跟踪文件及其父目录的符号链接，不遍历子模块。支持安全文件打开的系统上才计算内容哈希，其他系统如实标记 `safe_open_unavailable`。
- 不评分“AI 就绪度”，不从文件数量推断质量、风险、知识集中度、绩效、测试覆盖率或上线资格。
- 报告记录的是当前工作区文件哈希，不是 HEAD 中的 blob 哈希；脏文件、缺失文件与采集中变动均会标明。

本工具由本项目原创改写，不包含内网集成。正文 CC BY 4.0，代码 MIT：https://github.com/po-et/workbuddy-skills
