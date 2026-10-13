---
name: release-readiness-check
description: 上线前五分钟体检、发布前检查、上线卡点、release readiness、一条命令跑完 Dockerfile / K8s 清单 / SQL 迁移 / OpenAPI 兼容 / .env 配置五项检查并汇总成一份报告。 对本地目录做发布前静态检查，聚合五个内置检查器与有界 SHA-256 收据；用于发布评审前整理风险证据或 CI 静态门禁。结论只表示本轮静态 high 与证据缺口，不代表上线批准。支持带理由跳过、OpenAPI 基线、JSON、strict 与拒绝覆盖的 Markdown 输出。
author: Captain
homepage: https://github.com/po-et/workbuddy-skills
license: CC-BY-4.0 AND MIT
version: 0.1.3
display_name: "上线体检"
display_name_en: "Release Readiness Check"
description_zh: "离线聚合 Dockerfile、K8s、SQL、OpenAPI、.env 五类检查，输出风险与缺证据项、带理由跳过记录、输入与检查器 SHA-256 收据。报告不作上线批准；已有输出拒绝覆盖。"
description_en: "Aggregate five offline static checks with bounded input/checker SHA-256 receipts, explicit evidence gaps and reasoned skips. Export Markdown and JSON. Static results never approve production release; existing outputs are not overwritten."
examples_zh:
  - "发布评审前，给这个目录做一次静态风险检查并留证据"
  - "用上一版 OpenAPI 比对接口兼容，缺基线就标出来"
  - "CI 静态门禁遇到 high 或缺证据就返回失败"
examples_en:
  - "Create a static pre-release evidence report for this directory"
  - "Compare this API with its baseline and report missing evidence"
  - "Fail the static CI gate on high findings or evidence gaps"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🚦" } }
---

# 上线体检：发布前静态证据

给发布评审准备一份可复核的 Markdown 报告与 JSON 结果。Python 3.9+；常规检查和 JSON OpenAPI 只用标准库，**YAML OpenAPI 另需可选的 PyYAML**，缺依赖会标为缺证据。五个检查器已内置，无其他技能、API、账号或网络要求。

## 运行

将 `<skill-dir>` 换成安装目录，目标目录换成用户给出的项目路径。命令不运行项目代码、构建、部署或 SQL，只启动本技能内置检查脚本。

```bash
python3 "<skill-dir>/scripts/release_check.py" "/path/to/project" --json
python3 "<skill-dir>/scripts/release_check.py" "/path/to/project" \
  --openapi-base "/path/to/previous/openapi.json" --strict \
  --out "/path/to/reports/new-static-report.md"
```

省略 `--out` 会新建独立系统临时目录，返回报告的绝对路径。已有同名文件、目录或符号链接一律拒绝覆盖，包括输入文件和旧报告。需要重跑时换新输出路径。

当用户已决定跳过某项时记录理由，每项单独写一个参数：

```bash
python3 "<skill-dir>/scripts/release_check.py" "/path/to/project" \
  --skip env,openapi \
  --skip-reason 'env=部署平台注入，另附配置核验记录' \
  --skip-reason 'openapi=本项目没有本轮接口变更，基线另行复核' --strict
```

理由是用户配置的记录，**不证明豁免获得批准**。旧的 `--skip env` 仍能运行并出报告，但缺理由的项标为 `unknown`，strict 阻断。不要为得到成功退出码擅自添加跳过项。

## 判读与交付

1. 先看 `gate.headline`、`gate.unknown`、`gate.evidence_gaps`。有 high → **发现 high**；缺输入、缺基线、检查失败、无可检项或收据不足 → **缺静态检查证据**；其余 → **本轮静态检查未发现 high**。`production_readiness` 始终为 `unknown`，`release_approved` 始终为 `false`。
2. 阅读每项原因、覆盖路径与 warn。目录未发现某类文件只是 `na`；未解析出内容是 `unknown`。仅一项完成不代表整个发布得到验证。
3. 核对收据限额、输入与脚本哈希及检查前后变化。默认最多 128 份候选输入，每份哈希最多 4 MiB；超限、不可读、缺失和符号链接如实标记，不伪造哈希，strict 阻断。收据不包含文件内容；原有检查器的诊断可能含路径、变量名或 SQL 短片段，报告公开前确认范围。
4. 交付报告的绝对路径链接，按 high 与证据缺口指出下一步。修复后用新输出路径再查。运行时、回滚演练、真实业务验收和正式上线决策需使用者另行核实。

退出码：`0` 报告已生成（默认模式允许存在 high/缺口）；`1` 仅在 `--strict` 且有 high、检查未知或收据缺口；`2` 参数、输入目录、输出路径或执行异常。`0` 从来不表示批准上线。

详细字段和收据范围见 [报告契约](references/report-contract.md)。可复制的小样例见 [五分钟试用](examples/quick-check.md)。

## 检查范围

| 检查项 | 输入与规则边界 |
|---|---|
| Dockerfile | 发现 Dockerfile* / *.dockerfile，检查密钥写入、基础镜像标签、root 等静态模式 |
| K8s | 发现同时含 apiVersion 与 kind 的 YAML；内置简化解析器，Helm 模板不展开 |
| SQL | 发现 .sql；启发式识别 MySQL/PostgreSQL 迁移风险，不执行 SQL，不核对生产表规模 |
| OpenAPI | 需新旧两份有效规范；有多份新规范只比较排序后的第一份，其余明确提示未比较 |
| .env | 只比较根目录 .env* 与示例，并扫描代码中直接读取环境变量的模式，不解析框架间接注入 |

收据包括发现的输入、指定基线、Dockerfile 同目录已有 .dockerignore，以及执行 env 检查时的代码扫描候选；它们是工作区文件哈希，**不是完整仓库、Git blob、构建镜像或生产配置快照**。检查前后收据相同也不能排除检查中间短暂改动。可用 `--max-receipts` 与 `--max-receipt-bytes` 调整限额，检查器原有解析读取不受哈希限额限制。

本技能不联网；不运行项目安装脚本、构建命令、部署或数据库迁移。五类启发式检查不能替代 hadolint、kubeconform、OPA、DBA 评审或端到端测试。没有发现规则问题，也不等于不存在风险。

原创聚合与改写来自本项目，无内网集成。正文 CC BY 4.0，Python 代码 MIT；见 [许可](LICENSE.md)。
