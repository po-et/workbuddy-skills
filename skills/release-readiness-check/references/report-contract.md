# 静态报告契约

JSON 顶层保留 `target / generated / report / total / gate / items`，新增 `evidence`。

`gate.verdict` 保留旧枚举，兼容已有消费者：

| 枚举 | 本轮含义 |
|---|---|
| `no-go` | 静态规则发现 high，strict 阻断 |
| `unknown` | 检查或收据缺口，或没有任何可检项，strict 阻断 |
| `go-with-warn` | 有静态结论且未发现 high，有 warn，strict 不阻断 |
| `go` | 有静态结论且未发现 high / warn，strict 不阻断 |

旧 `go` 名称**不是**上线资格：读取 `scope=static_checks_only`、`production_readiness=unknown`、`release_approved=false`。`blocked=false` 只说明本脚本的静态门禁未阻断。正式批准状态没有由本工具核实。

`gate.unknown` 是未知检查项 ID；`evidence_gaps` 是文件收据缺口；`checked` 是已完成项；`configured_skips` 记录用户配置的跳过项。

每个 `items[]` 含：`id / title / skill / targets / status / reason_code / reason / notes / counts / findings`。状态为 `ok / unknown / na / skipped`。理由沿用旧 `n/a / user-skip / check-failed / skipped-invalid / no-baseline / missing-base / same-file / empty-input`，新增 `missing-skip-reason` 与 `unsafe-input`。带理由的跳过项含 `waiver.reason` 与 `approval_verified=false`。

## 收据

`evidence.inputs[]` 是有界候选输入收据，`checkers[]` 是五个内置检查器和聚合脚本收据。每项包含路径、关联检查项、状态、文件字节数（可取时）及 SHA-256（成功时）。不复制文件内容。

哈希状态包括 `hashed / missing / unreadable / symlink / not-regular / over-byte-limit / changed-while-hashing`；非 `hashed`、数量超限或检查前后收据变化均进入 `gaps`，strict 阻断。`limits.max_files` 限制输入收据数量；六份脚本收据另计，仍使用相同单文件字节上限。`candidate_count / omitted_count` 保留数量覆盖证据。

候选包含发现的 Dockerfile、K8s、SQL、OpenAPI、根部 .env，显式 OpenAPI 基线，Dockerfile 同目录已有 .dockerignore；执行 env 项时加入内置环境变量扫描器的代码候选。被用户跳过的直接输入仍保留收据。收据不是完整仓库或生产配置快照，规范目录中未比对的额外 OpenAPI 也只是候选哈希，不能读成已检查。

`unchanged_during_checks` 比较检查前后候选和有界哈希；不表示事务隔离，也不能排除中间改动后恢复。符号链接不生成内容哈希；可见不安全输入令关联检查项未知。超过数量限额的候选没有逐项收据，报告明确标记覆盖不足。

退出码 `0/1/2` 与 `gate` 相互独立：普通模式 `0` 仅为出报告成功；strict 模式 high、未知、缺收据时 `1`；参数或输出错误 `2`。输出路径采用独占创建，已有内容不会被覆盖。
