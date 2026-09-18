# workbuddy-skills

> **CodeBuddy 写代码，WorkBuddy 干剩下的。**
>
> 面向中文研发团队的 Agent 技能目录：上线体检、线上排查、仓库治理、接口契约、研发方法论、Agent 上下文工程，
> 一共 **116 个技能**。带脚本的那些，不装 Agent 也能当命令行工具直接跑。

`116 个技能` ｜ `56 个带可执行脚本` ｜ `其中 42 个只依赖 python3 标准库` ｜ `遵循 Agent Skills 开放标准` ｜ `MIT`

遵循 [Agent Skills 开放标准](https://docs.openclaw.ai/tools/skills)（`SKILL.md`），可在 **WorkBuddy / Claude Code / OpenClaw**
等支持该标准的 Agent 中直接使用。上面几个数字都能自己数一遍：

```bash
ls -d skills/*/ ported/skills/*/ | wc -l                                      # 116
ls -d skills/*/scripts ported/skills/*/scripts | wc -l                        # 56
grep -l '"bins": \["python3"\]' skills/*/SKILL.md ported/skills/*/SKILL.md | wc -l   # 42
```

完整清单见 **[docs/SKILLS.md](docs/SKILLS.md)**。

```
skills/           原创 56 个：研发效能技能体系 + 连接器构建
ported/skills/    中文复刻 60 个：成熟外部项目，逐个附 ATTRIBUTION.md，保留原许可证
ported/connectors/  CLI-Anything 连接器（mermaid、drawio）
docs/             技能索引、生态缺口分析、平台实测记录、指标口径
tools/            打包、校验、发布、指标抓取脚本
```

---

## 30 秒上手

不用装 Agent，不用配环境，clone 下来就能跑。下面三条命令**都是实跑输出**（绝对路径较长，用 `…` 缩短）。

```bash
git clone https://github.com/po-et/workbuddy-skills.git && cd workbuddy-skills
```

### 1. 上线体检：这次发布能不能上？

一条命令把 Dockerfile、K8s 清单、SQL 迁移、OpenAPI 兼容、`.env` 配置五项一起查完，给一个三态结论。

```bash
python3 skills/release-readiness-check/scripts/release_check.py ../your-service --strict
```

```text
上线体检 · …/demo-service
  Dockerfile 体检         high 1 / warn 2 / info 5
  K8s 清单体检            high 0 / warn 5 / info 7
  SQL 迁移风险            high 0 / warn 0 / info 1
  OpenAPI 破坏性变更      不适用：没有找到 openapi*/swagger* 规范文件，本项不适用
  .env 一致性             high 2 / warn 0 / info 4

合计：high 3 / warn 7 / info 17；无法判断 0 项
门禁：不建议上线
报告：…/demo-service/release-report.md
```

`--strict` 下退出码为 `1`，可以直接接在 CI 里当发布门禁。报告里每条都带文件、行号和改法：

```text
- **[HIGH]** `DF006` · `Dockerfile:L5` — ENV 中疑似把敏感值写进镜像：API_TOKEN
  - → 改法：镜像层会永久保留该值；改用运行时注入（-e / secrets）或 BuildKit 的 --mount=type=secret
- **[HIGH]** `missing` · `.env.production` — .env.production 缺少示例中登记的 DB_PASSWORD
```

注意「无法判断」不等于「通过」：子脚本跑挂了、旧规范是空的，都会拦住门禁而不是放行。

### 2. curl 转代码：抓包完直接出代码

浏览器 DevTools 里 Copy as cURL，粘进来，出 8 种语言的请求代码，**凭据自动改读环境变量**。

```bash
python3 skills/curl-to-code/scripts/curl_to_code.py \
  "curl -X POST https://api.example.com/v2/issues \
   -H 'Authorization: Bearer abc123' -H 'Content-Type: application/json' \
   -d '{\"title\":\"支付超时\",\"severity\":\"P1\"}'"
```

````text
# POST https://api.example.com/v2/issues
· 请求头 2 个，请求体 json，不跟随重定向

## python-requests
```python
import os
import requests

url = "https://api.example.com/v2/issues"
headers = {
    "Authorization": "Bearer " + os.environ["API_TOKEN"],
    "Content-Type": "application/json",
}
payload = {
    "title": "支付超时",
    "severity": "P1",
}

resp = requests.post(url, headers=headers, json=payload, timeout=30, allow_redirects=False)
resp.raise_for_status()
```

## 环境变量（原值未写入代码）
  Authorization        → $API_TOKEN          原值 ***（6 字符）
````

`--all` 出全部 8 种语言（requests / urllib / fetch / axios / net-http / HttpClient / PHP curl / 可读 curl）。

### 3. 访问日志统计：昨晚到底谁在拖后腿

```bash
python3 skills/access-log-stats/scripts/access_log_stats.py access.log --group-ids --top 6
```

```text
共 4000 行（无法解析 0）；状态码：2xx 3723，3xx 65，4xx 32，5xx 180
高峰时段：17/Sep/2026:21（1840 次）

## 请求量 Top 6
        次数     占比   5xx    错误率     p50     p95     p99    >慢  接口
      1416  35.4%    93  6.57%     141     272     740     0  GET /api/v2/orders/:id
       810  20.2%     0   0.0%      47      86      89     0  GET /api/v2/users/:id/profile
       603  15.1%    40  6.63%    1076    1894    5096   327  GET /api/v2/search
       469  11.7%    47 10.02%     394    1214    1999    28  GET /api/v2/checkout
       371   9.3%     0   0.0%      10      19      20     0  GET /static/app.js
       331   8.3%     0   0.0%       3       5       5     0  GET /health
```

`--group-ids` 把路径里的数字和 UUID 归并成 `:id`，否则按接口聚合会被 ID 打散。支持标准输入，
`zcat access.log.*.gz | python3 …/access_log_stats.py -` 也行。

---

## 为什么是这些技能

AI 编程工具已经解决了「写代码」。但一个研发团队里，真正吃时间又没人愿意干的，是写代码之外的部分：

| 活 | 现状 | 每周耗时（估） |
|---|---|---|
| 迭代周报 / 向上汇报 | 手工拼 git log 和工单 | 1-2 小时 |
| 上线检查清单 | 每次重写，或者干脆不写 | 0.5-1 小时 |
| 线上问题排查取证 | 人肉在日志/监控/变更间跳 | 每次事故 15 分钟起 |
| 需求转技术方案 | 从零写 | 2-4 小时 |

这些活有个共同点：**流程固定、数据分散、产出有标准格式**。正好是 Agent 的主场。

而且它们是一个体系，不是一堆独立工具——一个技能的产出可以直接当下一个的输入：

```
iteration-report ──迭代区间──> release-readiness-check ──高风险项──> incident-brief
   本期交付了什么                  上线前查什么              出事时先查什么
```

三者共享同一套输出契约：结论可溯源、数据缺口单列、判断性内容显式标记。
这是「技能体系」与「技能合集」的区别，展开见 [docs/skills-strategy.md](docs/skills-strategy.md)。

---

## 技能目录

按**使用场景**分成 7 组，116 个全在下面。带 ⁺ 的是中文复刻（上游与许可证见 [docs/SKILLS.md](docs/SKILLS.md)），其余为原创。

「脚本」列：`✅ 零依赖` = 有可执行脚本且只需要 `python3`（标准库，不用 pip 装任何东西）；
`✅ +git` = 还需要本机有 `git`；`—` = 纯 `SKILL.md` 方法论技能，靠模型执行，不带脚本。

> 想要带依赖、SkillHub slug、复刻上游与许可证的完整版表格 → **[docs/SKILLS.md](docs/SKILLS.md)**

### 上线与发布检查 · 19 个

发版前把能静态查出来的事故一次查完，全部能当 CI 门禁。（原创 15，复刻 4）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`changelog`](skills/changelog/) | 按 tag 区间读 git 提交，按 Keep a Changelog 分组生成发布说明草稿，每条附 hash | ✅ +git |
| [`ci-config-review`](skills/ci-config-review/) | 离线扫 GitHub Actions / GitLab CI 的安全问题：未固定 SHA、脚本注入、权限过宽、secret 泄露 | ✅ 零依赖 |
| [`config-env-diff`](skills/config-env-diff/) | 多份配置拉平成键路径逐个对比，分「只有一方有 / 类型不同 / 值不同」，密钥自动脱敏 | ✅ 零依赖 |
| [`dep-outdated-check`](skills/dep-outdated-check/) | 七种依赖清单查落后多少版本，按主/次/补丁分级并给升级顺序建议 | ✅ 零依赖 |
| [`dep-vuln-check`](skills/dep-vuln-check/) | 解析六种锁文件查 OSV.dev 已知漏洞（免 API Key），给严重度与建议升级版本 | ✅ 零依赖 |
| [`docker-compose-check`](skills/docker-compose-check/) | docker-compose.yml 上线前体检：特权、docker.sock、明文密钥、镜像未固定、缺健康检查 | ✅ 零依赖 |
| [`dockerfile-check`](skills/dockerfile-check/) | Dockerfile 17 条最佳实践与安全规则体检，分级输出并附具体改法 | ✅ 零依赖 |
| [`env-sync-check`](skills/env-sync-check/) | .env.example、各环境 .env 与代码实际读取的变量三方对齐，顺带查示例文件里的真密钥 | ✅ 零依赖 |
| [`i18n-missing-keys`](skills/i18n-missing-keys/) | 多语言文案对齐：缺失键、多余键、空值、占位符不一致，外加代码里用了却没定义的键 | ✅ 零依赖 |
| [`k8s-manifest-check`](skills/k8s-manifest-check/) | K8s 清单生产就绪检查：安全基线、资源限制、探针、废弃 API、selector 匹配 | ✅ 零依赖 |
| [`license-check`](skills/license-check/) | 离线读 npm / Python / Go 依赖许可证，按 restricted 到宽松五级分类并出清单草稿 | ✅ 零依赖 |
| [`nginx-config-check`](skills/nginx-config-check/) | 自带指令解析器的 nginx 配置体检：TLS、安全响应头、代理超时、root/alias 误用 | ✅ 零依赖 |
| [`release-checklist`](skills/release-checklist/) | 对比两个版本的实际改动，生成带验证方式与回滚方案的可勾选上线清单 | ✅ +git |
| [`release-readiness-check`](skills/release-readiness-check/) | 上线前五分钟体检：Dockerfile / K8s / SQL 迁移 / OpenAPI / .env 五项一起跑，出三态门禁结论 | ✅ 零依赖 |
| [`sql-migration-check`](skills/sql-migration-check/) | 扫迁移 SQL 里会锁表、丢数据、让滚动部署报错的语句，给 MySQL / PG 各自的安全写法 | ✅ 零依赖 |
| [`ci-cd-zh`](ported/skills/ci-cd-zh/) ⁺ | 把质量门禁自动化：lint→类型→测试→构建→E2E 一个都不跳；预览部署、特性开关、分阶段发布 | — |
| [`deprecation-migration-zh`](ported/skills/deprecation-migration-zh/) ⁺ | 老系统 / 旧接口 / 旧字段安全下线：绞杀者与适配器模式、数据库 expand-contract 不停机改名 | — |
| [`security-hardening-zh`](ported/skills/security-hardening-zh/) ⁺ | 先威胁建模再加固：OWASP 防护模式、SSRF、依赖审计分诊、密钥轮换、LLM 输出当不可信输入 | — |
| [`shipping-launch-zh`](ported/skills/shipping-launch-zh/) ⁺ | 可逆、可观测、渐进地发布：发布前清单、开关生命周期、灰度绿黄红阈值、回滚条件 | — |

### 线上排查与可观测 · 18 个

出事时把日志、指标、变更对齐成证据；平时做巡检与容量摸底。（原创 13，复刻 5）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`access-log-stats`](skills/access-log-stats/) | Nginx / Apache / JSON 访问日志变接口级报表：QPS、P50/P95/P99、5xx、错误率、Top IP | ✅ 零依赖 |
| [`cron-explain`](skills/cron-explain/) | cron 表达式翻译成中文并按时区列出接下来 N 次运行，识别日/周「或」逻辑陷阱 | ✅ 零依赖 |
| [`dns-check`](skills/dns-check/) | 不依赖 dig：自己拼 DNS 报文查多种记录，并排对比多个解析器，验证解析改完是否生效 | ✅ 零依赖 |
| [`har-analyze`](skills/har-analyze/) | 读懂 DevTools 导出的 HAR：耗时与体积 Top N、阶段分解、按域名聚合，再给 9 类问题清单 | ✅ 零依赖 |
| [`http-bench-lite`](skills/http-bench-lite/) | 没装 ab / wrk 也能压：成功率、状态码分布、QPS 与 p50–p99 分位，并发与时长有硬上限 | ✅ 零依赖 |
| [`http-health-check`](skills/http-health-check/) | 并发巡检一批 URL：状态码、耗时阈值、关键字、HTTPS 证书剩余天数；异常退出码 1 | ✅ 零依赖 |
| [`incident-brief`](skills/incident-brief/) | 把变更、指标异常与人工观察对齐成时间线，按可疑度排候选并给反证；不下根因结论 | ✅ 零依赖 |
| [`log-anomaly`](skills/log-anomaly/) | 日志或指标 CSV 转时间序列，滑动基线 3σ 找出异常开始、峰值与恢复时间点 | ✅ 零依赖 |
| [`log-pattern-cluster`](skills/log-pattern-cluster/) | 日志按模板归并：最常见的模式是噪音，最少见的模式往往是新错误 | ✅ 零依赖 |
| [`log-timeline`](skills/log-timeline/) | 多个格式与时区都不同的日志合成一条时间线，附事件密度柱状图与错误爆发点 | ✅ 零依赖 |
| [`prometheus-rule-check`](skills/prometheus-rule-check/) | 不连 Prometheus 评审告警与录制规则：缺 for、rate 窗口不匹配、缺聚合致告警风暴 | ✅ 零依赖 |
| [`sql-slow-query-digest`](skills/sql-slow-query-digest/) | 慢查询日志按指纹聚合成 Top SQL 报表，标出无索引、无 WHERE、SELECT * 等问题 | ✅ 零依赖 |
| [`tls-cert-check`](skills/tls-cert-check/) | 批量巡检 HTTPS 证书：剩余天数、SAN 是否覆盖主机名、协议与签名算法、链是否完整 | ✅ 零依赖 |
| [`debug-triage-zh`](ported/skills/debug-triage-zh/) ⁺ | 出问题先停线保留证据，按复现→定位→最小化→修根因→回归→端到端六步分诊 | — |
| [`diagnosing-bugs-zh`](ported/skills/diagnosing-bugs-zh/) ⁺ | 六阶段调试纪律：先造能变红的反馈回路，再最小化、列可证伪假设、先写回归测试再修 | — |
| [`observability-zh`](ported/skills/observability-zh/) ⁺ | 先写值班会问的问题再埋点：结构化日志、关联 ID、RED/USE 指标、只对症状告警并链 runbook | — |
| [`performance-optimization-zh`](ported/skills/performance-optimization-zh/) ⁺ | 测量→定位→修→验证→守护：Web Vitals、N+1、索引形状、缓存雪崩；中性改动一律回退 | — |
| [`systematic-debugging-zh`](ported/skills/systematic-debugging-zh/) ⁺ | 任何 Bug 都先找根因再修：四阶段流程，含三次失败即质疑架构的熔断规则 | — |

### 代码与仓库治理 · 22 个

提交、评审、分支、测试覆盖、技术债——仓库长期健康度。（原创 11，复刻 11）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`codeowners-suggest`](skills/codeowners-suggest/) | 从 git 历史推导各目录实际维护者，生成带占比注释的 CODEOWNERS 草稿 | ✅ +git |
| [`commit-message`](skills/commit-message/) | 从暂存区 diff 推断 Conventional Commits 的类型、范围与破坏性变更，给中英文候选 | ✅ +git |
| [`flaky-test-finder`](skills/flaky-test-finder/) | 汇总多次 JUnit XML 找时而通过时而失败的用例，给失败率、失败序列与常见报错 | ✅ 零依赖 |
| [`git-branch-cleanup`](skills/git-branch-cleanup/) | 只读分析本地与远端分支，分已合并 / 陈旧 / 受保护三类并生成待人工审阅的删除脚本 | ✅ +git |
| [`git-commit-lint`](skills/git-commit-lint/) | 按 Conventional Commits 体检一个提交范围，可做 CI 门禁与 commit-msg 钩子 | ✅ +git |
| [`git-hotspots`](skills/git-hotspots/) | 用 git 历史找缺陷高发文件、只有一个人在改的目录（bus factor）与隐性耦合 | ✅ +git |
| [`iteration-report`](skills/iteration-report/) | 从 Git 提交与工单生成可溯源的迭代周报：按交付价值重组，提交信息烂也能从 diff 反推 | ✅ +git |
| [`pr-description`](skills/pr-description/) | 从分支提交与 diff 生成 PR/MR 描述草稿：按区域分组、标出迁移与依赖风险、关联工单 | ✅ +git |
| [`secrets-scan`](skills/secrets-scan/) | 扫仓库里硬编码的密钥与口令，工作树加最近提交历史一起查，命中值脱敏后分级 | ✅ +git |
| [`test-coverage-gap`](skills/test-coverage-gap/) | 回答「该先给哪些文件补测试」：没有对应测试的源码按改动热度排序，叠加覆盖率报告 | ✅ +git |
| [`todo-debt-scan`](skills/todo-debt-scan/) | 汇总 TODO/FIXME/HACK 标记，结合 git blame 算作者与年龄，给优先处理清单 | ✅ 零依赖 |
| [`architecture-deepening-zh`](ported/skills/architecture-deepening-zh/) ⁺ | 扫代码库找把浅模块变深的重构机会，输出带前后对比图的自包含 HTML 架构评审报告 | — |
| [`code-review-five-axis-zh`](ported/skills/code-review-five-axis-zh/) ⁺ | 正确性 / 可读性 / 架构 / 安全 / 性能五轴评审，意见分级前缀，结构性问题给具名修法 | — |
| [`code-review-zh`](ported/skills/code-review-zh/) ⁺ | 标准轴（仓库规范 + Fowler 12 种坏味道）与 Spec 轴分开评审，附脚本预扫 | ✅ +git |
| [`code-simplification-zh`](ported/skills/code-simplification-zh/) ⁺ | 在不改变行为的前提下让代码更好读：五原则、一次一改跑测试、复核 | — |
| [`deep-module-design-zh`](ported/skills/deep-module-design-zh/) ⁺ | 用统一词汇设计深模块：小接口大实现、接缝位置、适配器；设计两次比较多个接口方案 | — |
| [`domain-modeling-zh`](ported/skills/domain-modeling-zh/) ⁺ | 打磨领域模型：挑战模糊用词、用场景压测边界、术语落定写进 CONTEXT.md，ADR 只记难逆转的权衡 | — |
| [`finishing-a-development-branch-zh`](ported/skills/finishing-a-development-branch-zh/) ⁺ | 实现完成后如何落地：先验证测试再给本地合并 / 发 PR / 原样保留三选一菜单 | — |
| [`git-workflow-zh`](ported/skills/git-workflow-zh/) ⁺ | 主干开发、短分支、原子提交、~100 行改动、worktree 并行、语义化版本与面向人的 changelog | — |
| [`merge-conflicts-zh`](ported/skills/merge-conflicts-zh/) ⁺ | 五步解 merge/rebase 冲突：追双方意图、逐块保留不发明行为；附 ours/theirs 方向陷阱 | — |
| [`receiving-code-review-zh`](ported/skills/receiving-code-review-zh/) ⁺ | 把评审意见当技术输入而非社交场合：看不懂就全停下来问，该反驳时用技术理由反驳 | — |
| [`using-git-worktrees-zh`](ported/skills/using-git-worktrees-zh/) ⁺ | 动手前先确保工作发生在隔离工作区：检测、建 worktree、装依赖、跑基线测试 | — |

### 接口与契约 · 9 个

接口的生成、对比、回归与兼容性把关。（原创 8，复刻 1）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`api-contract-test`](skills/api-contract-test/) | 一组接口用例跑完：校验状态码、JSON 字段、响应头与耗时上限，支持并发，--strict 当门禁 | ✅ 零依赖 |
| [`api-diff`](skills/api-diff/) | 同一批请求打到两个环境，逐字段深度对比 JSON 响应（可忽略易变字段），用于发布前后回归 | ✅ 零依赖 |
| [`curl-to-code`](skills/curl-to-code/) | curl 翻译成 8 种语言的请求代码，凭据自动改读环境变量；浏览器 Copy as cURL 直接粘 | ✅ 零依赖 |
| [`json-schema-infer`](skills/json-schema-infer/) | 几条样例 JSON 推断出 JSON Schema（draft 2020-12）：必填/可选/可空、枚举候选、常见 format | ✅ 零依赖 |
| [`jwt-inspect`](skills/jwt-inspect/) | 解开 JWT 逐条解释，exp/nbf 换算成还剩多久，顺带做 alg=none、超长有效期等安全体检 | ✅ 零依赖 |
| [`openapi-breaking-diff`](skills/openapi-breaking-diff/) | 对比两个 OpenAPI 3.x，把变更分成破坏性与非破坏性两组逐条列出，可作 CI 门禁 | ✅ 零依赖 |
| [`openapi-to-markdown`](skills/openapi-to-markdown/) | OpenAPI 3.x 变成能直接发出去的中文 Markdown 接口文档，$ref 与 allOf 自动展开 | ✅ 零依赖 |
| [`sql-schema-diff`](skills/sql-schema-diff/) | 对比两份建表 SQL 的结构差异并生成 ALTER TABLE 迁移草稿，单独列出会锁表的语句 | ✅ 零依赖 |
| [`api-design-zh`](ported/skills/api-design-zh/) ⁺ | 设计难以误用的稳定接口：Hyrum 定律、契约先行、统一错误、只加不改、幂等键实现要点 | — |

### 数据处理 · 4 个

入仓前体检、配置对比、正则、脱敏这类一次性数据活。（原创 4，复刻 0）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`csv-profile`](skills/csv-profile/) | CSV/TSV 入仓前体检：逐列类型、空值率、分位数，汇总全空列、常量列、重复行、疑似 PII | ✅ 零依赖 |
| [`json-diff`](skills/json-diff/) | 两份 JSON 按扁平路径列差异，数组可按业务键配对避免位移误报，密钥自动脱敏 | ✅ 零依赖 |
| [`regex-explain`](skills/regex-explain/) | 正则翻译成中文并逐 token 拆解，8 类风险提示（灾难性回溯等），输出 VERBOSE 注释版 | ✅ 零依赖 |
| [`sensitive-data-mask`](skills/sensitive-data-mask/) | 对外分享前脱敏：手机号、身份证、银行卡、JWT、AK/SK、连接串密码，三种替换策略 | ✅ 零依赖 |

### 研发流程方法论 · 31 个

从想法到上线的工作方法：澄清需求、写 Spec、拆任务、TDD、验证。（原创 2，复刻 29）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`dev-workflow-pro`](skills/dev-workflow-pro/) | 总入口：按意图把需求盘问、Spec、评审、上线、排查等路由到精专子技能 | — |
| [`tech-design-review`](skills/tech-design-review/) | 按 QA / SRE / 安全 / 数据 / 成本五视角审技术方案，意见分阻塞/建议/疑问三级 | — |
| [`brainstorming-zh`](ported/skills/brainstorming-zh/) ⁺ | 动手前把想法谈成设计：分级、逐条提问、方案对比、写 spec 并自查；先拿批准再实现 | — |
| [`browser-testing-devtools-zh`](ported/skills/browser-testing-devtools-zh/) ⁺ | 让 Agent 在真实浏览器里验证：UI/网络/性能三条排查流程、截图回归、console 零错误 | — |
| [`constraints-md-zh`](ported/skills/constraints-md-zh/) ⁺ | 把质量标准写成能机械检查的 CONSTRAINTS.md：底线 + 带数字的维度 + 棘轮 + 有期限的例外 | — |
| [`doc-coauthoring-zh`](ported/skills/doc-coauthoring-zh/) ⁺ | 和用户一起写方案与决策文档：先转移上下文，逐节共创，最后用零上下文读者 Agent 验收 | — |
| [`docs-and-adr-zh`](ported/skills/docs-and-adr-zh/) ⁺ | 记录决策而不只是代码：ADR 何时写与模板、注释只写 why、README 与 Changelog 结构 | — |
| [`doubt-driven-zh`](ported/skills/doubt-driven-zh/) ⁺ | 非平凡决策先让冷上下文审稿者来推翻：只给产物与契约做对抗性提示，三轮封顶 | — |
| [`engineering-skills-index-zh`](ported/skills/engineering-skills-index-zh/) ⁺ | 25 个工程实践技能的路由表：任务到手先判断阶段再选技能，附六条始终生效的行为 | — |
| [`executing-plans-zh`](ported/skills/executing-plans-zh/) ⁺ | 把写好的实施计划执行到底：先审计划再动手、逐任务验证、遇阻即停不猜 | — |
| [`frontend-ui-zh`](ported/skills/frontend-ui-zh/) ⁺ | 做出像设计感工程师做的界面：组件架构、避开八种 AI 默认审美、WCAG 2.1 AA、移动优先 | — |
| [`grill-me-zh`](ported/skills/grill-me-zh/) ⁺ | 按设计树分轮追问，每题附推荐答案；事实自己查、决策交给你，落盘 decisions.md | — |
| [`idea-refine-zh`](ported/skills/idea-refine-zh/) ⁺ | 粗糙点子磨成方案：HMW 重述、七种透镜生成变体、压力测试，产出含不做清单的一页纸 | — |
| [`incremental-implementation-zh`](ported/skills/incremental-implementation-zh/) ⁺ | 功能切成可独立验证的薄片，实现→测试→验证→提交循环；未完成功能放开关后面 | — |
| [`interview-me-zh`](ported/skills/interview-me-zh/) ⁺ | 动手前把真实意图问出来：一句话假设 + 置信度，一次一问，拿到明确的是才停 | — |
| [`planning-tasks-zh`](ported/skills/planning-tasks-zh/) ⁺ | 从 spec 到可执行任务：依赖图、垂直切片、每个任务带验收与验证步骤、大小 XS–L | — |
| [`prototype-zh`](ported/skills/prototype-zh/) ⁺ | 原型是回答一个问题的一次性代码：逻辑问题走单文件 HTML 演示，外观问题走多 UI 变体 | — |
| [`re-pitch-zh`](ported/skills/re-pitch-zh/) ⁺ | 上一条没讲明白时用简化技术表达重讲：短句、一句一意、只用项目术语表里的词 | — |
| [`research-primary-zh`](ported/skills/research-primary-zh/) ⁺ | 只查一手来源（官方文档、源码、规范），每个主张附引用，写成仓库约定位置的 Markdown | — |
| [`source-driven-zh`](ported/skills/source-driven-zh/) ⁺ | 框架相关代码一律先查官方文档：识别版本→抓页面→按文档实现→引用来源，查不到标 UNVERIFIED | — |
| [`spec-and-tickets-zh`](ported/skills/spec-and-tickets-zh/) ⁺ | 讨论整理成 Spec，再拆成带阻塞关系的垂直切片工单，输出 Markdown 与可导入 JSON | — |
| [`spec-driven-zh`](ported/skills/spec-driven-zh/) ⁺ | 写代码前先写 spec：六要素模板，把模糊需求改写成成功标准，四阶段逐门人审 | — |
| [`tdd-seams-zh`](ported/skills/tdd-seams-zh/) ⁺ | 红→绿循环参考手册：测试写在预先约定的接缝上，三大反模式与系统边界 mock 指南 | — |
| [`tdd-zh`](ported/skills/tdd-zh/) ⁺ | 先写失败的测试再写代码，修 bug 先复现；测状态不测交互、DAMP、少 mock、AAA | — |
| [`teach-workspace-zh`](ported/skills/teach-workspace-zh/) ⁺ | 把一个目录变成学习工作台：任务书、术语表、每课一个 HTML 小课与速查卡 | — |
| [`to-questionnaire-zh`](ported/skills/to-questionnaire-zh/) ⁺ | 把用户独自答不了的决策变成 Markdown 问卷，交给掌握信息的人异步填 | — |
| [`triage-zh`](ported/skills/triage-zh/) ⁺ | Issue 与外部 PR 推过一个小状态机：分类、验证、写 Agent 能直接执行的简报 | — |
| [`verification-before-completion-zh`](ported/skills/verification-before-completion-zh/) ⁺ | 任何「完成/修好/通过」的说法都必须有本轮新跑出来的证据；五步门禁与借口反驳表 | — |
| [`wayfinder-zh`](ported/skills/wayfinder-zh/) ⁺ | 超出一次会话的大事画成共享地图：命名目的地，建决策工单，每次会话清一片迷雾 | — |
| [`wizard-zh`](ported/skills/wizard-zh/) ⁺ | 只有人能做的手工流程（申请密钥、配 CI secrets）做成分阶段确认的 bash 向导 | — |
| [`writing-plans-zh`](ported/skills/writing-plans-zh/) ⁺ | 把 spec 写成零上下文工程师能照做的实施计划，每步 2–5 分钟并附真实代码与验证命令 | — |

### Agent 与上下文工程 · 13 个

写给 Agent 的工程学：上下文、记忆、工具设计、子代理与技能本身。（原创 3，复刻 10）

| 技能 | 干什么 | 脚本 |
|---|---|---|
| [`build-workbuddy-connector`](skills/build-workbuddy-connector/) | 按 WorkBuddy 开放平台规范构建连接器：规范速查、骨架生成、目录校验、CLI-Anything 封装 | ✅ 零依赖 |
| [`skill-lint`](skills/skill-lint/) | 五维度给 SKILL.md 打分并给修改建议：可发现性、结构、可执行性、合规、示例 | ✅ 零依赖 |
| [`skillhub-publish-helper`](skills/skillhub-publish-helper/) | 批量发技能到 SkillHub：校验 frontmatter、剔除会被拒的文件、限速发布、CSV 记 skillId | ✅ +skillhub |
| [`context-compression-zh`](ported/skills/context-compression-zh/) ⁺ | 长会话压缩怎么压才不丢关键信息：优化每任务 token、结构化强制章节、先保产物轨迹 | — |
| [`context-degradation-zh`](ported/skills/context-degradation-zh/) ⁺ | 在级联之前诊断上下文失效：中间迷失、投毒、干扰、混淆、冲突五种模式各有检测信号 | — |
| [`context-engineering-zh`](ported/skills/context-engineering-zh/) ⁺ | 让 Agent 在对的时候看到对的信息：五层上下文与规则文件模板、75% 开始修剪、信任分级 | — |
| [`context-fundamentals-zh`](ported/skills/context-fundamentals-zh/) ⁺ | 上下文是推理时模型可见的全部状态：当有限的注意力预算而非储物箱，关键约束放首尾 | — |
| [`dispatching-parallel-agents-zh`](ported/skills/dispatching-parallel-agents-zh/) ⁺ | 把互相独立的问题一次性分派给多个子代理：怎么切分、提示词四要素、回收后冲突检查 | — |
| [`handoff-doc-zh`](ported/skills/handoff-doc-zh/) ⁺ | 当前对话压成下一个 Agent 能直接接手的交接单：只引用不重复、脱敏、附建议技能 | — |
| [`memory-systems-zh`](ported/skills/memory-systems-zh/) ⁺ | 让 Agent 跨会话保持连续性：记忆分层、按检索形状选框架、从最浅一层起步、追踪时间有效性 | — |
| [`subagent-driven-development-zh`](ported/skills/subagent-driven-development-zh/) ⁺ | 一份实施计划驱动子代理流水线：每任务一个全新实现者、任务级双判定评审、账本抗压缩 | ✅ bash |
| [`tool-design-zh`](ported/skills/tool-design-zh/) ⁺ | 把工具当作确定性系统与 Agent 之间的契约：合并重叠工具、一致命名、面向恢复的错误信息 | — |
| [`writing-for-agents-zh`](ported/skills/writing-for-agents-zh/) ⁺ | 让技能、AGENTS.md、规则文件每次都被正确读取：上下文指针措辞、信息层级、渐进披露 | — |

⁺ = `ported/skills/` 下的中文复刻。不是翻译：每个都做了中文化 + 场景适配 + 输出契约对齐，
逐个目录附 `ATTRIBUTION.md` 写明来源文件、许可证与改了什么。上游分布：
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 25、
[mattpocock/skills](https://github.com/mattpocock/skills) 19、
[obra/superpowers](https://github.com/obra/superpowers) 10、
[muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) 5、
[anthropics/skills](https://github.com/anthropics/skills) 1；许可证 MIT 59 个、Apache-2.0 1 个。

---

## 怎么用

### A. 纯命令行，不装任何 Agent

**这是最被低估的一条路。**56 个技能自带可执行脚本，其中 42 个只要有 `python3` 就能跑
（标准库，不用 pip），可以直接当 CI 步骤、cron 任务或者临时排查工具用：

```bash
python3 skills/<技能名>/scripts/<脚本>.py --help
```

大多数脚本都支持 `--json`（机器可读）和非零退出码（CI 门禁）。三个例外要说明：
`openapi-breaking-diff`、`openapi-to-markdown`、`release-readiness-check` 在**输入是 YAML 时**需要 PyYAML，
输入 JSON 时不需要；`iteration-report`、`release-checklist` 有 PyYAML 就用、没有就退回内置的极简解析器。

### B. Claude Code / OpenClaw 等支持 `SKILL.md` 的 Agent

把技能目录软链或复制进 Agent 的技能目录即可，Agent 会按 `description` 自动触发：

```bash
# Claude Code
ln -s "$PWD/skills/release-readiness-check" ~/.claude/skills/release-readiness-check

# OpenClaw
ln -s "$PWD/skills/release-readiness-check" ~/.agents/skills/release-readiness-check
```

想一次装一整组，照着上面的表格挑目录名批量软链就行。

### C. WorkBuddy

两条路，都不需要你自己打包：

1. **SkillHub**（[skillhub.cn](https://skillhub.cn/)）：本仓库 96 个技能已上架在 `@indiv-captain` 名下，
   技能页有「安装到本地 Agent」按钮；装了官方 CLI 也可以 `skillhub install <slug>`。
   slug 与目录名不完全一致（例如 `release-checklist` 上线 slug 是 `release-checklist-git`），
   对照表在 [docs/SKILLS.md](docs/SKILLS.md)。
2. **本地目录**：把 `skills/<name>/` 整个目录放进 WorkBuddy 的技能目录。

如果你要把自己改造过的版本发到 WorkBuddy 开放平台，注意平台解析器对 frontmatter 有额外必填字段
（`version` / `display_name` / `display_name_en` / `description_zh` / `description_en`），
逐条实测记录在 [docs/platform-notes.md](docs/platform-notes.md)，打包用 `python3 tools/pack.py`。

---

## 设计原则

这几条贯穿全部 116 个技能，也是它们和「又一个 prompt 合集」的区别：

1. **零依赖** —— 能用标准库就不引第三方；不要 API Key、不要登录态、不联内网。42 个脚本只需要 `python3`。
2. **一条命令出结果** —— 不做需要来回对话才能用的技能。一条命令进去，一份结构化报告出来。
3. **可作 CI 门禁** —— 检查类技能都支持 `--json` 与非零退出码，能直接卡在合并/发布前。
4. **中文优先** —— 描述、输出、报告全中文，术语保留英文原词（`P99`、`breaking change`、`bus factor` 不硬译）。
5. **可追溯，不编造** —— 每条结论挂得上原始数据（commit hash、文件行号、日志行）；数据缺失就写「数据缺失」，
   缺口单列一节。排查类技能只给排序过的候选 + 反证，**不替人下根因结论**。
6. **脚本做事实，模型做判断** —— 统计、采集、渲染全部脚本化。既可复现，也省 token。
7. **复刻必署名** —— 只搬 MIT / Apache-2.0，逐个附 `ATTRIBUTION.md`，写明来源、许可证、改了什么。

---

## 安全与合规

- 技能**不包含任何内网地址、凭证、生产数据**。凭证一律从环境变量读，配置里只写变量名。
- 内部系统对接走 `file` provider 或独立私有适配器包，不入本仓库。
- `incident-brief`、`access-log-stats`、`log-*` 系列会读日志，使用云端模型前先跑 `sensitive-data-mask` 脱敏。
- `http-bench-lite` 对非本地目标必须显式确认；`git-branch-cleanup` 只生成删除脚本，不自动删任何东西。
- 安装任何第三方技能前先读代码。**技能就是可执行代码。**

---

## 相关文档

- **[技能索引 docs/SKILLS.md](docs/SKILLS.md)** —— 116 行完整表格：分组、一句话、脚本、依赖、SkillHub slug、复刻上游
- [生态缺口分析](docs/ecosystem-gap-analysis.md) —— 什么值得搬、什么不值得，带证据
- [SkillHub 增长打法](docs/skillhub-growth.md) —— 平台机制实测与发布节奏
- [指标口径与快照](docs/metrics/README.md) —— 能拿到哪些数、拿不到哪些数，以及为什么
- [平台实测记录](docs/platform-notes.md) —— 开放平台 / SkillHub 的字段要求与上传限制
- [Skills 策略](docs/skills-strategy.md) —— 为什么不做「技能合集」而做「技能体系」

关于下载量：截至 2026-09-18 的快照，SkillHub 上 97 个 slug **累计下载 1084 次**（口径与局限见
[docs/metrics/README.md](docs/metrics/README.md)）。这个数目前主要由上架时长和平台抓取驱动，
**不能用来比较技能之间的真实需求差异**；收藏、评论、`skillhub install` 安装量目前全部为 0。

---

## 贡献

欢迎提技能。提交前请读 [CONTRIBUTING.md](CONTRIBUTING.md)，几条硬性要求：

- 目录名 == `SKILL.md` 里的 `name`；`description` 要同时覆盖「做什么」和「什么时候用」（这是触发机制）
- 正文 < 5000 tokens，更长的内容拆到 `references/` 按需加载
- 逻辑优先写成 `scripts/` 下的脚本，不要写成长篇提示词
- 依赖写进 `metadata.openclaw.requires.bins`
- 不得包含任何内网地址、凭证、token、生产数据、真实用户信息
- 移植他人技能必须附 `ATTRIBUTION.md`，且只搬 MIT / Apache-2.0

发布前可以用本仓库自己的技能自检：`python3 skills/skill-lint/scripts/skill_lint.py <技能目录>`。

## 协议

- 原创部分：代码 [MIT](LICENSE)，文档 [CC BY 4.0](LICENSE-CONTENT)
- `ported/skills/` 下各技能：沿用上游许可证（MIT 59 个、Apache-2.0 1 个），各目录自带 `ATTRIBUTION.md`
- `ported/hookify-workbuddy/`、`ported/connectors/`：沿用原项目 Apache-2.0，各目录自带 LICENSE 与 ATTRIBUTION.md

## 其它

- `buddy-apps/devops-buddy/` —— 「研发效能 Buddy」应用配置包（Buddy 应用需企业认证，个人开发者不能创建）。
  校验：`python3 tools/check_buddy_app.py buddy-apps/devops-buddy`；调研见 [docs/buddy-app-plan.md](docs/buddy-app-plan.md)
- 个人开发者能走的全部提交/曝光渠道与当前状态：[docs/channels.md](docs/channels.md)
