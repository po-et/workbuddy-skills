---
name: database-ops-pro
description: 数据库运维助手。只要用户的问题涉及跟数据库较劲——查得慢、改不动、连不上，即应触发本技能，无需用户明确指定。无论是慢日志堆了一地、接口突然变慢、库 CPU 打满、这条 SQL 该加什么索引、要不要覆盖索引、大表扫全表、SELECT 星号与没有 WHERE，还是迁移脚本能不能上、会不会锁表丢数据、加非空列改列类型删列删表风险多大、大表加索引怕卡死要不要走在线 DDL、滚动发布期间新旧代码打架、DDL 变更要评审、MySQL 与 PostgreSQL 各自的安全写法是什么，或者预发和生产的表结构对不上、有人手改过库要出 ALTER 草稿、字段类型默认值与注释漂移、本地能连而测试环境连不上、连错了库、新人起不来服务、连接串密码写死在代码或配置里、带库数据的导出要脱敏后才能发出去、上线前想把数据库相关的检查一次过完，都从这里进。本技能判断意图，给出精简做法并路由到带脚本的子技能，全程只读不连库。不做：直连生产库执行任何 SQL，也不做数据建模与 ORM 映射。
author: Captain
version: 0.1.2
display_name: "数据库运维"
display_name_en: "Database Ops Pro"
description_zh: "一个入口管住数据库的糟心事，不必等用户报出技能名：慢查询与索引、迁移脚本的锁表与丢数据风险、两套环境的表结构对比与 ALTER 草稿、连接串与配置排查、导出数据脱敏；按意图路由到带脚本的精专子技能，全程只读不连库。"
description_en: "One entry point for database pain, triggered by the symptom rather than by name. Slow queries and indexes, migration risks like table locks and data loss, schema diffs across environments with ALTER drafts, connection and config troubleshooting, masking before sharing; read-only and never connects to a live database."
tags:
  - "慢查询"
  - "索引优化"
  - "SQL 迁移"
  - "锁表"
  - "表结构对比"
  - "数据库运维"
  - "MySQL"
  - "PostgreSQL"
examples_zh:
  - "接口突然变慢，库的 CPU 也高，这周四还要上一版迁移脚本，先查哪个"
  - "预发和生产的表结构好像不一样，帮我比一下再给个 ALTER 草稿"
  - "本地能连库，测试环境连不上，配置也看不出差在哪"
examples_en:
  - "API got slow, DB CPU is high, and a migration ships Thursday — what first?"
  - "Staging and prod schemas look different, diff them and draft the ALTER"
  - "Works locally, cannot connect on staging, and the configs look identical"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🗄️" } }
---

# 数据库运维助手

定位一句话：**业务代码交给编程助手，跟数据库较劲的活交给我。**
什么时候轮到我：用户手里有慢日志、迁移脚本、建表 SQL 或几份环境配置，问题跟「查得慢、改不动、连不上」有关。先判断卡在哪一环，用下表的方法直接干；表里的子技能已安装就调用它（更完整、带脚本），没安装就按本页的精简方法做，并告诉用户可以在 SkillHub 搜索安装。子技能都是纯 Python 标准库脚本，`python3` 直接跑，不装依赖、不连数据库，只读用户给的文件。

## 意图 → 方法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 接口变慢、库 CPU 打满、慢日志堆了一地 | 慢日志按 SQL 指纹聚合，按总耗时排序，标出全表扫描 / SELECT * / 无 WHERE，给出改法 | 慢查询摘要 `sql-slow-query-digest` |
| 这条 SQL 该加什么索引 | 先定 WHERE 与 ORDER BY 的列序，再看能否覆盖索引；不凭感觉加，用慢日志里的扫描行数验证 | 慢查询摘要 `sql-slow-query-digest` |
| 迁移脚本能不能上、会不会锁表丢数据 | 按 high/warn/info 扫 DDL（加非空列、改列类型、加索引、删列删表、大表 UPDATE），给 MySQL / PostgreSQL 各自的安全写法 | SQL 迁移风险检查 `sql-migration-check` |
| 滚动发布期间新旧代码都要能跑 | 扩展-收缩两步走：先加可空列与双写，发布完再回收旧列；一次迁移只做一个方向 | 下线与迁移 `deprecation-migration-zh` |
| 两个环境的表结构对不上 / 有人手改过库 | 抹掉 dump 噪声后比表、列、类型、可空、默认值、注释、索引、外键，生成 ALTER 草稿并单列高危项 | 建表 SQL 结构对比 `sql-schema-diff` |
| 连不上库、连错了库、配置看不出差在哪 | 两份配置拉平成键路径逐个比，分「只有一方有 / 类型不同 / 值不同」三类，密钥自动脱敏 | 多环境配置对比 `config-env-diff` |
| .env 少了库的配置、新人起不来服务 | 把 .env.example、各环境 .env、代码里真正读取的变量三方对齐，找缺失、未登记、僵尸项 | .env 一致性检查 `env-sync-check` |
| 连接串密码写死在代码或配置里了 | 工作树加最近提交历史一起扫，命中值只留前 4 后 4 位，按等级给轮换步骤 | 仓库泄密自查 `secrets-scan` |
| 要把带库数据的日志或导出发给外部 | 手机号、身份证、邮箱、连接串密码按 mask/hash/fake 替换，保留跨文件可关联性 | 日志与数据脱敏 `sensitive-data-mask` |
| 上线前想把数据库相关的检查一次过完 | 迁移、结构、配置、密钥四件套串起来跑，见下方组合流程 ② | 上线体检 `release-readiness-check` |

## 输出契约

1. **每条结论附来源**：慢日志行号、SQL 指纹、迁移文件名与行号、配置键路径。拿不到来源就写「待确认」。
2. **不下最终结论的事**：能不能上线、要不要加这个索引、字段类型该不该改——只列证据、代价与选项，决定权在 DBA 与业务负责人。
3. **风险分三项说**：预计锁表时长、是否可能丢数据、能否回滚。写「高危」必须说明在多大的表上高危。
4. **只读**：全部子技能只读文件，不连库、不执行 SQL、不改数据；需要跑在库上的命令（如在线 DDL）只给出命令，由人执行。

## 典型组合流程

**① 慢接口专项**（慢日志 → 索引方案 → 安全上线）
`sql-slow-query-digest` 出 Top SQL → 对 Top 3 逐条给索引改法 → 索引写成迁移脚本 → `sql-migration-check` 确认加索引这步的锁表风险 → 大表走在线 DDL（pt-osc / gh-ost / CREATE INDEX CONCURRENTLY）。

**② 上线前数据库体检**（四件套）
`sql-migration-check` 扫本次迁移 → `sql-schema-diff` 比预发与生产的建表 SQL，确认没有人手改出的漂移 → `config-env-diff` 比两套环境的数据库配置 → `secrets-scan` 确认连接串没写死。四步都过再进上线清单 `release-checklist-git`。

**③ 环境连不上排查**（先查配置，别一上来怀疑网络）
`env-sync-check` 看变量是不是少了 → `config-env-diff` 看值是不是指到了另一个库 → 仍未定位再查网络、账号权限与连接池上限，并把排查过程记进故障简报 `incident-brief-sre`。

自检口诀：
```
数据库的活：1) 分清是查得慢 / 改不动 / 连不上 → 2) 查表选子技能 → 3) 拿证据（日志行、文件行号、键路径）→ 4) 风险分级后交给人决定
```

## 不做什么

- 不连接任何数据库、不执行 SQL、不改数据；所有分析基于用户提供的日志、SQL 与配置文件。
- 不拍板「这条 SQL 必须这么写」，索引与字段类型的最终决定权在 DBA。
- 不写业务代码与 ORM 映射，也不做数据建模——那是编程类与领域建模技能的事。
- 不接触任何未脱敏的内部系统信息；示例一律用 example.com 与 GitHub / GitLab / Jira。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
