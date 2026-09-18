# 技能索引（全部 116 个）

本文件由 `skills/*/SKILL.md` 与 `ported/skills/*/SKILL.md` 的 frontmatter 实际内容整理而成，
是 [README](../README.md)「技能目录」一节的完整版——README 只给技能名与一句话，这里补上依赖、线上 slug 与复刻上游。

**读表说明**

- **技能**：链接指向仓库里的目录。`ported/skills/` 下的是中文复刻，上游与许可证见「来源」列。
- **脚本**：列出 `scripts/` 下的可执行文件；`—` 表示纯 SKILL.md 方法论技能，不带脚本。
- **依赖**：来自 frontmatter 的 `metadata.openclaw.requires.bins`。`python3` 指 Python 3 标准库，不需要 pip 装任何东西。
- **SkillHub slug**：已发布到 [skillhub.cn](https://skillhub.cn/) 的技能在这里给出线上 slug（与目录名不同时尤其注意）；
  `未发布` 表示尚未上架（发布配额有限，见 `docs/skillhub-growth.md`）。线上地址形如 `https://skillhub.cn/skills/indiv-captain/<slug>`。

## 上线与发布检查（19 个）

发版前把能静态查出来的事故一次查完，全部能当 CI 门禁。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`changelog`](../skills/changelog/) | 按 tag 区间读 git 提交，按 Keep a Changelog 分组生成发布说明草稿，每条附 hash | `build_changelog.py` | git + python3 | `changelog-keep` | 原创 |
| [`ci-config-review`](../skills/ci-config-review/) | 离线扫 GitHub Actions / GitLab CI 的安全问题：未固定 SHA、脚本注入、权限过宽、secret 泄露 | `ci_lint.py` | python3 | `ci-config-review` | 原创 |
| [`config-env-diff`](../skills/config-env-diff/) | 多份配置拉平成键路径逐个对比，分「只有一方有 / 类型不同 / 值不同」，密钥自动脱敏 | `config_env_diff.py` | python3 | `config-env-diff` | 原创 |
| [`dep-outdated-check`](../skills/dep-outdated-check/) | 七种依赖清单查落后多少版本，按主/次/补丁分级并给升级顺序建议 | `dep_outdated.py` | python3 | `dep-outdated-check` | 原创 |
| [`dep-vuln-check`](../skills/dep-vuln-check/) | 解析六种锁文件查 OSV.dev 已知漏洞（免 API Key），给严重度与建议升级版本 | `osv_check.py` | python3 | `dep-vuln-check-osv` | 原创 |
| [`docker-compose-check`](../skills/docker-compose-check/) | docker-compose.yml 上线前体检：特权、docker.sock、明文密钥、镜像未固定、缺健康检查 | `compose_check.py` | python3 | 未发布 | 原创 |
| [`dockerfile-check`](../skills/dockerfile-check/) | Dockerfile 17 条最佳实践与安全规则体检，分级输出并附具体改法 | `dockerfile_check.py` | python3 | `dockerfile-check` | 原创 |
| [`env-sync-check`](../skills/env-sync-check/) | .env.example、各环境 .env 与代码实际读取的变量三方对齐，顺带查示例文件里的真密钥 | `env_sync_check.py` | python3 | `env-sync-check` | 原创 |
| [`i18n-missing-keys`](../skills/i18n-missing-keys/) | 多语言文案对齐：缺失键、多余键、空值、占位符不一致，外加代码里用了却没定义的键 | `i18n_missing_keys.py` | python3 | `i18n-missing-keys` | 原创 |
| [`k8s-manifest-check`](../skills/k8s-manifest-check/) | K8s 清单生产就绪检查：安全基线、资源限制、探针、废弃 API、selector 匹配 | `k8s_check.py` | python3 | `k8s-manifest-check` | 原创 |
| [`license-check`](../skills/license-check/) | 离线读 npm / Python / Go 依赖许可证，按 restricted 到宽松五级分类并出清单草稿 | `license_check.py` | python3 | `license-check-offline` | 原创 |
| [`nginx-config-check`](../skills/nginx-config-check/) | 自带指令解析器的 nginx 配置体检：TLS、安全响应头、代理超时、root/alias 误用 | `nginx_check.py` | python3 | 未发布 | 原创 |
| [`release-checklist`](../skills/release-checklist/) | 对比两个版本的实际改动，生成带验证方式与回滚方案的可勾选上线清单 | `collect_diff.py`、`render_checklist.py` | git + python3 | `release-checklist-git` | 原创 |
| [`release-readiness-check`](../skills/release-readiness-check/) | 上线前五分钟体检：Dockerfile / K8s / SQL 迁移 / OpenAPI / .env 五项一起跑，出三态门禁结论 | `release_check.py` | python3 | `release-readiness-check` | 原创 |
| [`sql-migration-check`](../skills/sql-migration-check/) | 扫迁移 SQL 里会锁表、丢数据、让滚动部署报错的语句，给 MySQL / PG 各自的安全写法 | `sql_migration_check.py` | python3 | `sql-migration-check` | 原创 |
| [`ci-cd-zh`](../ported/skills/ci-cd-zh/) | 把质量门禁自动化：lint→类型→测试→构建→E2E 一个都不跳；预览部署、特性开关、分阶段发布 | — | — | `ci-cd-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`deprecation-migration-zh`](../ported/skills/deprecation-migration-zh/) | 老系统 / 旧接口 / 旧字段安全下线：绞杀者与适配器模式、数据库 expand-contract 不停机改名 | — | — | `deprecation-migration-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`security-hardening-zh`](../ported/skills/security-hardening-zh/) | 先威胁建模再加固：OWASP 防护模式、SSRF、依赖审计分诊、密钥轮换、LLM 输出当不可信输入 | — | — | `security-hardening-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`shipping-launch-zh`](../ported/skills/shipping-launch-zh/) | 可逆、可观测、渐进地发布：发布前清单、开关生命周期、灰度绿黄红阈值、回滚条件 | — | — | `shipping-launch-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |

## 线上排查与可观测（18 个）

出事时把日志、指标、变更对齐成证据；平时做巡检与容量摸底。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`access-log-stats`](../skills/access-log-stats/) | Nginx / Apache / JSON 访问日志变接口级报表：QPS、P50/P95/P99、5xx、错误率、Top IP | `access_log_stats.py` | python3 | `access-log-stats` | 原创 |
| [`cron-explain`](../skills/cron-explain/) | cron 表达式翻译成中文并按时区列出接下来 N 次运行，识别日/周「或」逻辑陷阱 | `cron_explain.py` | python3 | `cron-explain` | 原创 |
| [`dns-check`](../skills/dns-check/) | 不依赖 dig：自己拼 DNS 报文查多种记录，并排对比多个解析器，验证解析改完是否生效 | `dns_check.py` | python3 | 未发布 | 原创 |
| [`har-analyze`](../skills/har-analyze/) | 读懂 DevTools 导出的 HAR：耗时与体积 Top N、阶段分解、按域名聚合，再给 9 类问题清单 | `har_analyze.py` | python3 | 未发布 | 原创 |
| [`http-bench-lite`](../skills/http-bench-lite/) | 没装 ab / wrk 也能压：成功率、状态码分布、QPS 与 p50–p99 分位，并发与时长有硬上限 | `http_bench.py` | python3 | 未发布 | 原创 |
| [`http-health-check`](../skills/http-health-check/) | 并发巡检一批 URL：状态码、耗时阈值、关键字、HTTPS 证书剩余天数；异常退出码 1 | `health_check.py` | python3 | `http-health-check` | 原创 |
| [`incident-brief`](../skills/incident-brief/) | 把变更、指标异常与人工观察对齐成时间线，按可疑度排候选并给反证；不下根因结论 | `changepoint.py`、`collect_changes.py`、`timeline.py` | python3 | `incident-brief-sre` | 原创 |
| [`log-anomaly`](../skills/log-anomaly/) | 日志或指标 CSV 转时间序列，滑动基线 3σ 找出异常开始、峰值与恢复时间点 | `log_anomaly.py` | python3 | `log-anomaly-3sigma` | 原创 |
| [`log-pattern-cluster`](../skills/log-pattern-cluster/) | 日志按模板归并：最常见的模式是噪音，最少见的模式往往是新错误 | `log_cluster.py` | python3 | `log-pattern-cluster` | 原创 |
| [`log-timeline`](../skills/log-timeline/) | 多个格式与时区都不同的日志合成一条时间线，附事件密度柱状图与错误爆发点 | `log_timeline.py` | python3 | 未发布 | 原创 |
| [`prometheus-rule-check`](../skills/prometheus-rule-check/) | 不连 Prometheus 评审告警与录制规则：缺 for、rate 窗口不匹配、缺聚合致告警风暴 | `promrule_check.py` | python3 | 未发布 | 原创 |
| [`sql-slow-query-digest`](../skills/sql-slow-query-digest/) | 慢查询日志按指纹聚合成 Top SQL 报表，标出无索引、无 WHERE、SELECT * 等问题 | `slow_query_digest.py` | python3 | 未发布 | 原创 |
| [`tls-cert-check`](../skills/tls-cert-check/) | 批量巡检 HTTPS 证书：剩余天数、SAN 是否覆盖主机名、协议与签名算法、链是否完整 | `tls_check.py` | python3 | 未发布 | 原创 |
| [`debug-triage-zh`](../ported/skills/debug-triage-zh/) | 出问题先停线保留证据，按复现→定位→最小化→修根因→回归→端到端六步分诊 | — | git | `debug-triage-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`diagnosing-bugs-zh`](../ported/skills/diagnosing-bugs-zh/) | 六阶段调试纪律：先造能变红的反馈回路，再最小化、列可证伪假设、先写回归测试再修 | — | — | `diagnosing-bugs-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`observability-zh`](../ported/skills/observability-zh/) | 先写值班会问的问题再埋点：结构化日志、关联 ID、RED/USE 指标、只对症状告警并链 runbook | — | — | `observability-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`performance-optimization-zh`](../ported/skills/performance-optimization-zh/) | 测量→定位→修→验证→守护：Web Vitals、N+1、索引形状、缓存雪崩；中性改动一律回退 | — | — | `performance-optimization-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`systematic-debugging-zh`](../ported/skills/systematic-debugging-zh/) | 任何 Bug 都先找根因再修：四阶段流程，含三次失败即质疑架构的熔断规则 | — | — | `systematic-debugging-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |

## 代码与仓库治理（22 个）

提交、评审、分支、测试覆盖、技术债——仓库长期健康度。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`codeowners-suggest`](../skills/codeowners-suggest/) | 从 git 历史推导各目录实际维护者，生成带占比注释的 CODEOWNERS 草稿 | `codeowners_suggest.py` | python3 + git | `codeowners-suggest` | 原创 |
| [`commit-message`](../skills/commit-message/) | 从暂存区 diff 推断 Conventional Commits 的类型、范围与破坏性变更，给中英文候选 | `suggest_commit.py` | git + python3 | `commit-message-cc` | 原创 |
| [`flaky-test-finder`](../skills/flaky-test-finder/) | 汇总多次 JUnit XML 找时而通过时而失败的用例，给失败率、失败序列与常见报错 | `flaky_finder.py` | python3 | `flaky-test-finder` | 原创 |
| [`git-branch-cleanup`](../skills/git-branch-cleanup/) | 只读分析本地与远端分支，分已合并 / 陈旧 / 受保护三类并生成待人工审阅的删除脚本 | `branch_cleanup.py` | python3 + git | `git-branch-cleanup` | 原创 |
| [`git-commit-lint`](../skills/git-commit-lint/) | 按 Conventional Commits 体检一个提交范围，可做 CI 门禁与 commit-msg 钩子 | `git_commit_lint.py` | python3 + git | 未发布 | 原创 |
| [`git-hotspots`](../skills/git-hotspots/) | 用 git 历史找缺陷高发文件、只有一个人在改的目录（bus factor）与隐性耦合 | `git_hotspots.py` | python3 + git | `git-hotspots` | 原创 |
| [`iteration-report`](../skills/iteration-report/) | 从 Git 提交与工单生成可溯源的迭代周报：按交付价值重组，提交信息烂也能从 diff 反推 | `collect_git.py`、`collect_issues.py`、`render_report.py` | git + python3 | `iteration-report-git` | 原创 |
| [`pr-description`](../skills/pr-description/) | 从分支提交与 diff 生成 PR/MR 描述草稿：按区域分组、标出迁移与依赖风险、关联工单 | `pr_describe.py` | python3 + git | `pr-description` | 原创 |
| [`secrets-scan`](../skills/secrets-scan/) | 扫仓库里硬编码的密钥与口令，工作树加最近提交历史一起查，命中值脱敏后分级 | `secrets_scan.py` | python3 + git | `secrets-scan` | 原创 |
| [`test-coverage-gap`](../skills/test-coverage-gap/) | 回答「该先给哪些文件补测试」：没有对应测试的源码按改动热度排序，叠加覆盖率报告 | `test_coverage_gap.py` | python3 + git | `test-coverage-gap` | 原创 |
| [`todo-debt-scan`](../skills/todo-debt-scan/) | 汇总 TODO/FIXME/HACK 标记，结合 git blame 算作者与年龄，给优先处理清单 | `todo_scan.py` | python3 | `todo-debt-scan` | 原创 |
| [`architecture-deepening-zh`](../ported/skills/architecture-deepening-zh/) | 扫代码库找把浅模块变深的重构机会，输出带前后对比图的自包含 HTML 架构评审报告 | — | — | `architecture-deepening-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`code-review-five-axis-zh`](../ported/skills/code-review-five-axis-zh/) | 正确性 / 可读性 / 架构 / 安全 / 性能五轴评审，意见分级前缀，结构性问题给具名修法 | — | git | `code-review-five-axis-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`code-review-zh`](../ported/skills/code-review-zh/) | 标准轴（仓库规范 + Fowler 12 种坏味道）与 Spec 轴分开评审，附脚本预扫 | `review_prep.py` | git + python3 | `code-review-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`code-simplification-zh`](../ported/skills/code-simplification-zh/) | 在不改变行为的前提下让代码更好读：五原则、一次一改跑测试、复核 | — | — | `code-simplification-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`deep-module-design-zh`](../ported/skills/deep-module-design-zh/) | 用统一词汇设计深模块：小接口大实现、接缝位置、适配器；设计两次比较多个接口方案 | — | — | `deep-module-design-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`domain-modeling-zh`](../ported/skills/domain-modeling-zh/) | 打磨领域模型：挑战模糊用词、用场景压测边界、术语落定写进 CONTEXT.md，ADR 只记难逆转的权衡 | — | — | 未发布 | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`finishing-a-development-branch-zh`](../ported/skills/finishing-a-development-branch-zh/) | 实现完成后如何落地：先验证测试再给本地合并 / 发 PR / 原样保留三选一菜单 | — | git | `dev-branch-finishing-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`git-workflow-zh`](../ported/skills/git-workflow-zh/) | 主干开发、短分支、原子提交、~100 行改动、worktree 并行、语义化版本与面向人的 changelog | — | git | `git-workflow-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`merge-conflicts-zh`](../ported/skills/merge-conflicts-zh/) | 五步解 merge/rebase 冲突：追双方意图、逐块保留不发明行为；附 ours/theirs 方向陷阱 | — | git | `merge-conflicts-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`receiving-code-review-zh`](../ported/skills/receiving-code-review-zh/) | 把评审意见当技术输入而非社交场合：看不懂就全停下来问，该反驳时用技术理由反驳 | — | git | `code-review-response-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`using-git-worktrees-zh`](../ported/skills/using-git-worktrees-zh/) | 动手前先确保工作发生在隔离工作区：检测、建 worktree、装依赖、跑基线测试 | — | git | `git-worktree-workflow-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |

## 接口与契约（9 个）

接口的生成、对比、回归与兼容性把关。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`api-contract-test`](../skills/api-contract-test/) | 一组接口用例跑完：校验状态码、JSON 字段、响应头与耗时上限，支持并发，--strict 当门禁 | `api_contract_test.py` | python3 | 未发布 | 原创 |
| [`api-diff`](../skills/api-diff/) | 同一批请求打到两个环境，逐字段深度对比 JSON 响应（可忽略易变字段），用于发布前后回归 | `api_diff.py` | python3 | `api-diff-test` | 原创 |
| [`curl-to-code`](../skills/curl-to-code/) | curl 翻译成 8 种语言的请求代码，凭据自动改读环境变量；浏览器 Copy as cURL 直接粘 | `curl_to_code.py` | python3 | 未发布 | 原创 |
| [`json-schema-infer`](../skills/json-schema-infer/) | 几条样例 JSON 推断出 JSON Schema（draft 2020-12）：必填/可选/可空、枚举候选、常见 format | `schema_infer.py` | python3 | `json-schema-infer` | 原创 |
| [`jwt-inspect`](../skills/jwt-inspect/) | 解开 JWT 逐条解释，exp/nbf 换算成还剩多久，顺带做 alg=none、超长有效期等安全体检 | `jwt_inspect.py` | python3 | 未发布 | 原创 |
| [`openapi-breaking-diff`](../skills/openapi-breaking-diff/) | 对比两个 OpenAPI 3.x，把变更分成破坏性与非破坏性两组逐条列出，可作 CI 门禁 | `openapi_diff.py` | python3 | `openapi-breaking-diff` | 原创 |
| [`openapi-to-markdown`](../skills/openapi-to-markdown/) | OpenAPI 3.x 变成能直接发出去的中文 Markdown 接口文档，$ref 与 allOf 自动展开 | `openapi_to_markdown.py` | python3 | 未发布 | 原创 |
| [`sql-schema-diff`](../skills/sql-schema-diff/) | 对比两份建表 SQL 的结构差异并生成 ALTER TABLE 迁移草稿，单独列出会锁表的语句 | `schema_diff.py` | python3 | 未发布 | 原创 |
| [`api-design-zh`](../ported/skills/api-design-zh/) | 设计难以误用的稳定接口：Hyrum 定律、契约先行、统一错误、只加不改、幂等键实现要点 | — | — | `api-design-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |

## 数据处理（4 个）

入仓前体检、配置对比、正则、脱敏这类一次性数据活。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`csv-profile`](../skills/csv-profile/) | CSV/TSV 入仓前体检：逐列类型、空值率、分位数，汇总全空列、常量列、重复行、疑似 PII | `csv_profile.py` | python3 | 未发布 | 原创 |
| [`json-diff`](../skills/json-diff/) | 两份 JSON 按扁平路径列差异，数组可按业务键配对避免位移误报，密钥自动脱敏 | `json_diff.py` | python3 | 未发布 | 原创 |
| [`regex-explain`](../skills/regex-explain/) | 正则翻译成中文并逐 token 拆解，8 类风险提示（灾难性回溯等），输出 VERBOSE 注释版 | `regex_explain.py` | python3 | 未发布 | 原创 |
| [`sensitive-data-mask`](../skills/sensitive-data-mask/) | 对外分享前脱敏：手机号、身份证、银行卡、JWT、AK/SK、连接串密码，三种替换策略 | `mask_sensitive.py` | python3 | 未发布 | 原创 |

## 研发流程方法论（31 个）

从想法到上线的工作方法：澄清需求、写 Spec、拆任务、TDD、验证。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`dev-workflow-pro`](../skills/dev-workflow-pro/) | 总入口：按意图把需求盘问、Spec、评审、上线、排查等路由到精专子技能 | — | git + python3 | `dev-workflow-pro` | 原创 |
| [`tech-design-review`](../skills/tech-design-review/) | 按 QA / SRE / 安全 / 数据 / 成本五视角审技术方案，意见分阻塞/建议/疑问三级 | — | — | `tech-design-review` | 原创 |
| [`brainstorming-zh`](../ported/skills/brainstorming-zh/) | 动手前把想法谈成设计：分级、逐条提问、方案对比、写 spec 并自查；先拿批准再实现 | — | — | `brainstorming-spec-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`browser-testing-devtools-zh`](../ported/skills/browser-testing-devtools-zh/) | 让 Agent 在真实浏览器里验证：UI/网络/性能三条排查流程、截图回归、console 零错误 | — | — | `browser-testing-devtools-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`constraints-md-zh`](../ported/skills/constraints-md-zh/) | 把质量标准写成能机械检查的 CONSTRAINTS.md：底线 + 带数字的维度 + 棘轮 + 有期限的例外 | — | — | `constraints-md-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`doc-coauthoring-zh`](../ported/skills/doc-coauthoring-zh/) | 和用户一起写方案与决策文档：先转移上下文，逐节共创，最后用零上下文读者 Agent 验收 | — | — | `doc-coauthoring-zh` | 复刻 · [anthropics/skills](https://github.com/anthropics/skills) · Apache-2.0 |
| [`docs-and-adr-zh`](../ported/skills/docs-and-adr-zh/) | 记录决策而不只是代码：ADR 何时写与模板、注释只写 why、README 与 Changelog 结构 | — | — | `docs-and-adr-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`doubt-driven-zh`](../ported/skills/doubt-driven-zh/) | 非平凡决策先让冷上下文审稿者来推翻：只给产物与契约做对抗性提示，三轮封顶 | — | — | `doubt-driven-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`engineering-skills-index-zh`](../ported/skills/engineering-skills-index-zh/) | 25 个工程实践技能的路由表：任务到手先判断阶段再选技能，附六条始终生效的行为 | — | — | `engineering-skills-index-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`executing-plans-zh`](../ported/skills/executing-plans-zh/) | 把写好的实施计划执行到底：先审计划再动手、逐任务验证、遇阻即停不猜 | — | git | `executing-dev-plans-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`frontend-ui-zh`](../ported/skills/frontend-ui-zh/) | 做出像设计感工程师做的界面：组件架构、避开八种 AI 默认审美、WCAG 2.1 AA、移动优先 | — | — | `frontend-ui-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`grill-me-zh`](../ported/skills/grill-me-zh/) | 按设计树分轮追问，每题附推荐答案；事实自己查、决策交给你，落盘 decisions.md | — | — | `grill-me-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`idea-refine-zh`](../ported/skills/idea-refine-zh/) | 粗糙点子磨成方案：HMW 重述、七种透镜生成变体、压力测试，产出含不做清单的一页纸 | — | — | `idea-refine-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`incremental-implementation-zh`](../ported/skills/incremental-implementation-zh/) | 功能切成可独立验证的薄片，实现→测试→验证→提交循环；未完成功能放开关后面 | — | git | `incremental-implementation-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`interview-me-zh`](../ported/skills/interview-me-zh/) | 动手前把真实意图问出来：一句话假设 + 置信度，一次一问，拿到明确的是才停 | — | — | `interview-me-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`planning-tasks-zh`](../ported/skills/planning-tasks-zh/) | 从 spec 到可执行任务：依赖图、垂直切片、每个任务带验收与验证步骤、大小 XS–L | — | — | `planning-tasks-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`prototype-zh`](../ported/skills/prototype-zh/) | 原型是回答一个问题的一次性代码：逻辑问题走单文件 HTML 演示，外观问题走多 UI 变体 | — | — | `prototype-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`re-pitch-zh`](../ported/skills/re-pitch-zh/) | 上一条没讲明白时用简化技术表达重讲：短句、一句一意、只用项目术语表里的词 | — | — | `re-pitch-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`research-primary-zh`](../ported/skills/research-primary-zh/) | 只查一手来源（官方文档、源码、规范），每个主张附引用，写成仓库约定位置的 Markdown | — | — | `research-primary-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`source-driven-zh`](../ported/skills/source-driven-zh/) | 框架相关代码一律先查官方文档：识别版本→抓页面→按文档实现→引用来源，查不到标 UNVERIFIED | — | — | `source-driven-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`spec-and-tickets-zh`](../ported/skills/spec-and-tickets-zh/) | 讨论整理成 Spec，再拆成带阻塞关系的垂直切片工单，输出 Markdown 与可导入 JSON | — | — | `spec-and-tickets-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`spec-driven-zh`](../ported/skills/spec-driven-zh/) | 写代码前先写 spec：六要素模板，把模糊需求改写成成功标准，四阶段逐门人审 | — | — | `spec-driven-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`tdd-seams-zh`](../ported/skills/tdd-seams-zh/) | 红→绿循环参考手册：测试写在预先约定的接缝上，三大反模式与系统边界 mock 指南 | — | — | `tdd-seams-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`tdd-zh`](../ported/skills/tdd-zh/) | 先写失败的测试再写代码，修 bug 先复现；测状态不测交互、DAMP、少 mock、AAA | — | — | `tdd-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`teach-workspace-zh`](../ported/skills/teach-workspace-zh/) | 把一个目录变成学习工作台：任务书、术语表、每课一个 HTML 小课与速查卡 | — | — | `teach-workspace-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`to-questionnaire-zh`](../ported/skills/to-questionnaire-zh/) | 把用户独自答不了的决策变成 Markdown 问卷，交给掌握信息的人异步填 | — | — | `to-questionnaire-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`triage-zh`](../ported/skills/triage-zh/) | Issue 与外部 PR 推过一个小状态机：分类、验证、写 Agent 能直接执行的简报 | — | — | `issue-triage-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`verification-before-completion-zh`](../ported/skills/verification-before-completion-zh/) | 任何「完成/修好/通过」的说法都必须有本轮新跑出来的证据；五步门禁与借口反驳表 | — | — | `pre-completion-verification-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`wayfinder-zh`](../ported/skills/wayfinder-zh/) | 超出一次会话的大事画成共享地图：命名目的地，建决策工单，每次会话清一片迷雾 | — | — | `wayfinder-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`wizard-zh`](../ported/skills/wizard-zh/) | 只有人能做的手工流程（申请密钥、配 CI secrets）做成分阶段确认的 bash 向导 | — | bash | `wizard-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`writing-plans-zh`](../ported/skills/writing-plans-zh/) | 把 spec 写成零上下文工程师能照做的实施计划，每步 2–5 分钟并附真实代码与验证命令 | — | — | `writing-impl-plans-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |

## Agent 与上下文工程（13 个）

写给 Agent 的工程学：上下文、记忆、工具设计、子代理与技能本身。

| 技能 | 干什么 | 脚本 | 依赖 | SkillHub slug | 来源 |
|---|---|---|---|---|---|
| [`build-workbuddy-connector`](../skills/build-workbuddy-connector/) | 按 WorkBuddy 开放平台规范构建连接器：规范速查、骨架生成、目录校验、CLI-Anything 封装 | `scaffold_connector.py`、`validate_connector.py` | python3 | `build-workbuddy-connector` | 原创 |
| [`skill-lint`](../skills/skill-lint/) | 五维度给 SKILL.md 打分并给修改建议：可发现性、结构、可执行性、合规、示例 | `skill_lint.py` | python3 | `skill-lint-scorecard` | 原创 |
| [`skillhub-publish-helper`](../skills/skillhub-publish-helper/) | 批量发技能到 SkillHub：校验 frontmatter、剔除会被拒的文件、限速发布、CSV 记 skillId | `publish_batch.py` | python3 + skillhub | `skillhub-publish-helper` | 原创 |
| [`context-compression-zh`](../ported/skills/context-compression-zh/) | 长会话压缩怎么压才不丢关键信息：优化每任务 token、结构化强制章节、先保产物轨迹 | — | — | `context-compression-strategies-zh` | 复刻 · [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) · MIT |
| [`context-degradation-zh`](../ported/skills/context-degradation-zh/) | 在级联之前诊断上下文失效：中间迷失、投毒、干扰、混淆、冲突五种模式各有检测信号 | — | — | `context-degradation-zh` | 复刻 · [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) · MIT |
| [`context-engineering-zh`](../ported/skills/context-engineering-zh/) | 让 Agent 在对的时候看到对的信息：五层上下文与规则文件模板、75% 开始修剪、信任分级 | — | — | `context-engineering-zh` | 复刻 · [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) · MIT |
| [`context-fundamentals-zh`](../ported/skills/context-fundamentals-zh/) | 上下文是推理时模型可见的全部状态：当有限的注意力预算而非储物箱，关键约束放首尾 | — | — | `context-fundamentals-zh` | 复刻 · [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) · MIT |
| [`dispatching-parallel-agents-zh`](../ported/skills/dispatching-parallel-agents-zh/) | 把互相独立的问题一次性分派给多个子代理：怎么切分、提示词四要素、回收后冲突检查 | — | — | `parallel-agent-dispatch-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`handoff-doc-zh`](../ported/skills/handoff-doc-zh/) | 当前对话压成下一个 Agent 能直接接手的交接单：只引用不重复、脱敏、附建议技能 | — | — | `handoff-doc-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |
| [`memory-systems-zh`](../ported/skills/memory-systems-zh/) | 让 Agent 跨会话保持连续性：记忆分层、按检索形状选框架、从最浅一层起步、追踪时间有效性 | — | — | `memory-systems-zh` | 复刻 · [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) · MIT |
| [`subagent-driven-development-zh`](../ported/skills/subagent-driven-development-zh/) | 一份实施计划驱动子代理流水线：每任务一个全新实现者、任务级双判定评审、账本抗压缩 | `review-package.sh`、`sdd-workspace.sh`、`task-brief.sh` | git + bash | `subagent-driven-development-zh` | 复刻 · [obra/superpowers](https://github.com/obra/superpowers) · MIT |
| [`tool-design-zh`](../ported/skills/tool-design-zh/) | 把工具当作确定性系统与 Agent 之间的契约：合并重叠工具、一致命名、面向恢复的错误信息 | — | — | `tool-design-zh` | 复刻 · [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) · MIT |
| [`writing-for-agents-zh`](../ported/skills/writing-for-agents-zh/) | 让技能、AGENTS.md、规则文件每次都被正确读取：上下文指针措辞、信息层级、渐进披露 | — | — | `writing-for-agents-zh` | 复刻 · [mattpocock/skills](https://github.com/mattpocock/skills) · MIT |

---

## 统计（116 个）

| 口径 | 数量 |
|---|---:|
| 技能总数 | 116 |
| 原创（`skills/`） | 56 |
| 中文复刻（`ported/skills/`，全部带 ATTRIBUTION） | 60 |
| 带可执行脚本 | 56（55 个 Python，1 个 Bash） |
| 其中只需 `python3`（标准库） | 42 |
| 其中需 `python3` + `git` | 12 |
| 其中需要第三方 CLI | 1（`skillhub-publish-helper` 需 `skillhub`） |
| 纯 SKILL.md 方法论技能 | 60 |
| 已发布到 SkillHub | 96 |

`openapi-breaking-diff`、`openapi-to-markdown`、`release-readiness-check` 三个在**输入是 YAML 时**需要 PyYAML（输入 JSON 时纯标准库），
`iteration-report`、`release-checklist` 有 PyYAML 就用、没有就走内置的极简解析器。其余带脚本的技能全程只用标准库。

复刻上游分布（按 ATTRIBUTION.md 统计）：

| 上游 | 个数 | 许可证 |
|---|---:|---|
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 25 | MIT |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 19 | MIT |
| [obra/superpowers](https://github.com/obra/superpowers) | 10 | MIT |
| [muratcankoylan/Agent-Skills-for-Context-Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering) | 5 | MIT |
| [anthropics/skills](https://github.com/anthropics/skills) | 1 | Apache-2.0 |

许可证合计：MIT 59 个，Apache-2.0 1 个。每个复刻目录下都有 `ATTRIBUTION.md`，写明来源文件、许可证与改了什么。

