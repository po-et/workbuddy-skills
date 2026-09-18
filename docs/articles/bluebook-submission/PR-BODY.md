## 投稿：上线前五分钟体检——把五项检查串成一条 CI 门禁

新增一个案例到 `docs/cases/submissions/release-readiness-gate/index.md`。

**做的是什么**：发版前用一个零依赖的 Skill（`release-readiness-check`）一条命令跑完五类静态检查——Dockerfile、K8s 清单、SQL 迁移、OpenAPI 兼容性、`.env` 配置一致性——汇总成一份带「能不能上线」结论的报告，再把同一条命令接进 CI 当发布门禁（`--strict`，有 high 退出码 1）。

**案例包含**：

- 完整过程：第一次跑出 13 个 high（含镜像明文密码、无 WHERE 的 UPDATE、NOT NULL 无 DEFAULT 的加列、被删的接口、生产少配的变量），按报告里的「→ 改法」逐条收敛到 0，门禁结论从「不建议上线」变成「可以上线，但先看 warn」。
- 一段「修 warn 修出一个新 high」的真实插曲，以及为什么该按工具的语义补配置、而不是改示例文件绕过。
- 三处边界：一次误报（占位符 DSN 被判成密钥）、一次漏报（`JWT_SIGNING_KEY` 与响应枚举收窄都没报出来）、一个 CI 假绿灯（用空 JSON 当 OpenAPI base 会让所有接口算成「新增」，必须改用 `--skip openapi`）。
- 可直接抄的 GitHub Actions 片段（两个分支都实跑验证过）。

**关于数据真实性**：文中所有命令、终端回显、规则号与报告片段都是 2026-09-18 在本机对演示项目实跑的真实结果；耗时用 `/usr/bin/time -p` 连测三次（0.19s / 0.16s / 0.15s）。演示项目 `orders-api` 是为本文构造的最小服务，全部文件内容都写在案例里，读者可逐字复现同样的输出。

**脱敏**：不涉及任何真实业务系统、内部域名或数据，域名统一使用 `example.com`，仓库链接只有公开的 `github.com/po-et/workbuddy-skills`。

**技能开源**：MIT，https://github.com/po-et/workbuddy-skills ，总入口在 `skills/release-readiness-check/`，五个单项检查器分别是 `dockerfile-check`、`k8s-manifest-check`、`sql-migration-check`、`openapi-breaking-diff`、`env-sync-check`。

格式方面如果和案例集的约定有出入（frontmatter 字段、目录命名、配图位置），我按你们的要求改，直接在 PR 里说就行。

🤖 Generated with [Claude Code](https://claude.com/claude-code)
