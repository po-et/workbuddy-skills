---
name: sql-slow-query-digest
description: 慢查询日志摘要、慢 SQL 分析、MySQL slow log 分析、PostgreSQL 慢日志分析、pt-query-digest 精简替代、找出最耗时的 SQL、数据库变慢排查、索引缺失定位、SQL 指纹聚合。当用户说「帮我看看慢查询日志里哪些 SQL 最费时间」「数据库 CPU 打满了，从慢日志找元凶」「这份 slow.log 汇总一下」「哪些 SQL 扫了几百万行只返回几条」「按指纹把慢 SQL 归并统计」时使用。附纯标准库脚本 scripts/slow_query_digest.py，把 SQL 归一化成指纹（数字与字符串换问号、IN 列表折叠、空白压缩、统一小写）后聚合次数、总耗时、平均与最大耗时、平均扫描行数、首末出现时间与示例原句，按总耗时排序输出 Top N，并给出扫描返回比过高、无 WHERE、SELECT *、前导百分号 LIKE、深分页、锁等待等分级提示与改法；支持 stdin、--json 与 --strict 门禁。
author: Captain
version: 0.1.1
display_name: "慢查询分析"
display_name_en: "SQL Slow Query Digest"
description_zh: "一条命令把慢查询日志变成 Top SQL 报表：按指纹聚合次数与总耗时、平均扫描行数，并标出无索引、无 WHERE、SELECT * 等问题与改法；MySQL 与 PostgreSQL 通吃，纯 Python 标准库。"
description_en: "Turn slow query logs into a Top-SQL report in one command: fingerprint-level counts, total time and rows examined, plus graded hints for missing indexes, missing WHERE and SELECT *; MySQL and PostgreSQL, pure Python stdlib."
examples_zh:
  - "帮我看看慢查询日志里哪些 SQL 最费时间"
  - "这份 slow.log 汇总一下，按总耗时给我 Top 10"
  - "哪些 SQL 扫了几百万行只返回几条"
examples_en:
  - "Which SQL statements burn the most time in this slow log?"
  - "Digest slow.log and give me the top 10 by total time"
  - "Which queries scan millions of rows but return a handful?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🐢" } }
---

# 慢查询摘要

把几万行慢查询日志压成一页可执行的结论：哪几条 SQL 吃掉了大部分数据库时间、它们慢在哪、怎么改。适用于数据库变慢排查、大促前索引体检、慢日志值班巡检。纯 Python 标准库，不连数据库、不装 Percona Toolkit。

## 用法

```bash
python3 scripts/slow_query_digest.py /var/log/mysql/slow.log --top 10
python3 scripts/slow_query_digest.py pg.log --format postgres --sort avg
zcat slow.log.*.gz | python3 scripts/slow_query_digest.py -          # 读 stdin
python3 scripts/slow_query_digest.py slow.log --json > digest.json   # 机器可读
python3 scripts/slow_query_digest.py slow.log --strict               # 有 high 提示则退出码 1
```

格式默认自动识别：日志含 `# Query_time:` 块按 MySQL 解析，含 `duration: 123.4 ms  statement:` 行按 PostgreSQL 解析。常用参数：`--top N`、`--min-count N`（过滤偶发语句）、`--sort total|avg|max|count`、`--sample-len N`。

开启慢日志：MySQL 设 `slow_query_log=ON` 与 `long_query_time=1`；PostgreSQL 设 `log_min_duration_statement=1000`。

## 流程

1. 跑一次不带参数的默认输出，先看头部的「慢查询条数 / 指纹数 / 总耗时」，判断这份日志是否覆盖了故障时段。
2. 看 Top 1–3 的**总耗时占比**。优化顺序永远按总耗时，而不是按单条最慢：一条 5s 跑 1 次，不如一条 200ms 跑 5000 次值得治。
3. 逐条读 `[high]` 提示。扫描返回比高的先用 `EXPLAIN` 验证，再按 WHERE 与 ORDER BY 的列顺序建联合索引。
4. 用 `--sort max` 再看一遍，抓那些偶发但会打爆连接池的尖刺。
5. 改完索引或 SQL 后，切一份新时段的日志再跑一次，用两份 `--json` 结果对比总耗时是否下降。

## 输出与规则一览

每个指纹输出：次数、总耗时与占比、平均/最大耗时、平均扫描行与返回行、平均锁等待、首末出现时间、指纹与示例原句，以及分级提示。

| 级别 | 提示 | 触发条件与改法 |
|---|---|---|
| high | 扫描返回比过高 | 平均扫描 ≥1000 行且扫描/返回 ≥100，基本可判定没走对索引 |
| high | UPDATE/DELETE 无 WHERE | 全表写，必须带索引条件并分批 |
| warn | SELECT 无 WHERE | 全表扫描，至少加 LIMIT |
| warn | SELECT * | 改成按需列，便于走覆盖索引 |
| warn | LIKE 以 % 开头 | 前导通配符用不上 B+ 树索引 |
| warn | 平均锁等待 ≥100ms | 存在锁竞争，缩短事务 |
| info | ORDER BY 无 LIMIT、深分页 offset、无条件 COUNT(*)、JOIN 扫描行数大 | 见输出里的「→ 改法」 |

## 边界与常见问题

- 指纹归一化是文本级的：数字、引号字符串、`IN (...)` 列表与 `VALUES (...)` 会折叠成 `?`，因此参数不同但结构相同的 SQL 会合并。注释会被剥掉，`/*+ hint */` 也一并丢弃。
- 不解析 `EXPLAIN` 结果，也不连数据库，所以「没走索引」是根据扫描/返回比推断的，落地前请自己跑一次 `EXPLAIN` 确认。
- PostgreSQL 日志只认 `duration: … ms` 行，不统计 `Rows_examined`（PG 日志里没有），所以扫描行相关提示对 PG 不生效；多行语句按缩进续行合并。
- 不用它做实时监控：它是离线文件分析，采样窗口取决于你给的日志范围；日志被 logrotate 截断时先 `cat` 拼起来再喂进来。
- `--strict` 只在出现 high 提示时返回 1，适合放进定时巡检任务；不要用它拦截业务发布流水线，慢日志的内容和本次发布未必相关。
