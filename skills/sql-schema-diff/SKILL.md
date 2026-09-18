---
name: sql-schema-diff
description: 两份建表 SQL 的结构对比、数据库表结构 diff、mysqldump 与 pg_dump 对比、线上库和本地库表结构不一致、schema 漂移排查、新增表与删除表、新增列删除列、列类型变化、可空性变化、默认值变化、索引与唯一索引增删、外键增删、主键变化、自动生成 ALTER TABLE 迁移 SQL 草稿、标注哪些变更会锁表。当用户说「帮我对比一下这两份表结构」「线上和测试库的 schema 差在哪」「这次迭代改了哪些表」「生成一份迁移 SQL」「这个 DDL 会不会锁表」时使用。附脚本 scripts/schema_diff.py，纯标准库启发式解析 CREATE TABLE 与 CREATE INDEX 与 ALTER TABLE ADD CONSTRAINT，按 MySQL 或 PostgreSQL 方言产出迁移草稿，破坏性语句默认注释掉，支持 --json、--sql、--strict。
author: Captain
version: 0.1.0
display_name: "建表 SQL 结构对比"
display_name_en: "SQL Schema Diff"
description_zh: "不装任何依赖就能对比两份建表 SQL 的结构差异：新增与删除的表、列的增删与类型/可空/默认值/注释变化、索引与唯一索引、外键、主键；自动抹掉 dump 噪声（如 int(11) 与 int），按 MySQL 或 PostgreSQL 方言生成 ALTER TABLE 迁移草稿，并单独列出会锁表或可能失败的高危项。"
description_en: "Zero-dependency structural diff between two SQL schema dumps: added and removed tables, column additions, drops, type, nullability, default and comment changes, indexes and unique keys, foreign keys and primary keys; normalizes dump noise such as int(11) versus int, emits a MySQL or PostgreSQL ALTER TABLE migration draft, and flags the locking or failure-prone steps separately."
examples_zh:
  - "帮我对比一下这两份表结构，看看这次迭代改了哪些表"
  - "线上和测试库的 schema 差在哪，生成一份迁移 SQL"
  - "这个 DDL 会不会锁表，加唯一索引有没有风险"
examples_en:
  - "Diff these two schema dumps and tell me what changed"
  - "Generate a migration draft from old.sql to new.sql"
  - "Which of these DDL steps will lock the table?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🗃️" } }
---

# 建表 SQL 结构对比

把两份建表 SQL 摆在一起看清楚差异，并给出可执行的迁移草稿。适用于上线前核对线上与本地 schema、评审迭代改了哪些表、排查环境间的结构漂移、以及把 ORM 生成的 DDL 与真实库对账。纯标准库，不连数据库、不装驱动，只读两个文件。

## 用法

```bash
mysqldump --no-data -h prod-host dbname > old.sql        # 或 pg_dump -s -h host dbname > old.sql
python3 scripts/schema_diff.py old.sql new.sql
python3 scripts/schema_diff.py old.sql new.sql --sql > migrate.sql    # 只要迁移草稿
python3 scripts/schema_diff.py old.sql new.sql --json                 # 结构化输出
python3 scripts/schema_diff.py old.sql new.sql --strict               # 有 high 退出码 1
python3 scripts/schema_diff.py old.sql new.sql --dialect postgres     # 默认按内容自动判断方言
```

输出分三段：按表归组的差异清单（high/warn/info）、锁表与风险提示、迁移 SQL 草稿。草稿里删表、删列、删索引、删外键默认是注释掉的，需要人工确认后再放开。

## 流程

1. 先看 high。**high 必须评审**：删表、删列、改类型、主键变化、新增唯一索引、新增 NOT NULL 且没有默认值。这几类要么丢数据，要么在存量数据上直接失败。
2. 再看「锁表与风险提示」，它把 high 翻译成了操作建议：改类型与加 NOT NULL 会全表校验，大表走 gh-ost 或 pt-osc；加唯一索引前先 `GROUP BY` 查重；加外键前先查孤儿行；PostgreSQL 建索引记得 `CONCURRENTLY`，加外键先 `NOT VALID` 再 `VALIDATE`。
3. **warn 确认影响面**：默认值变化（存量行不会被改写，只影响之后的插入）、删索引（先确认没有查询依赖）、外键增删、表选项变化。
4. **info 一般可放行**：新增表、新增可空列、新增普通索引、注释变化。
5. 用 `--sql` 导出草稿后人工复核再执行；破坏性语句取消注释前，先确认代码里已经没有引用。改完可以把新 dump 再跑一次对比，确认迁移后两边一致。
6. 接 CI：对「仓库里的 schema 基线」与「迁移后库的 dump」跑 `--strict`，防止有人绕过迁移脚本直接改线上表。

## 规则一览

| 级别 | 变更类型 | 为什么 |
|---|---|---|
| high | 删表、删列、改类型、主键变化、新增唯一索引、新增 NOT NULL 无默认值 | 丢数据、重建表、或在存量数据上直接执行失败 |
| warn | 默认值变化、删索引、索引列变化、外键增删、表选项变化 | 影响行为或性能，需要确认影响面 |
| info | 新增表、新增可空列、新增普通索引、注释变化 | 一般可直接放行 |
| 归一化 | int(11) 与 int、integer 与 int、character varying 与 varchar、numeric 与 decimal、timestamp without time zone 与 timestamp、unsigned 修饰词顺序 | 抹掉 dump 版本差异带来的假差异 |

## 边界

- 启发式解析，不是完整 SQL 语法树。认得 CREATE TABLE、CREATE INDEX、ALTER TABLE ADD CONSTRAINT、ALTER COLUMN、COMMENT ON COLUMN；视图、触发器、存储过程、分区定义、CHECK 约束一律跳过，跳过条数会在报告开头写明，数字异常就说明该文件需要人工看。
- 触发器与存储过程体内的分号会被当成语句分隔符，导致跳过计数偏大，这不影响表结构对比结果。
- 迁移草稿是草稿，不做执行顺序编排（比如加外键前要先建被引用表的索引），也不生成回滚脚本；正式迁移请交给 Flyway、Liquibase、Alembic 这类工具，本工具只负责把差异和风险点摆出来。
- 只比结构，不比数据、不比权限、不比字符集校对规则的实际影响；跨方言对比（MySQL dump 比 PostgreSQL dump）虽然能跑，但类型体系不同，结果只能当参考。
- 表名按不带 schema 前缀的名字对齐，`public.` 与 `dbo.` 会被忽略；同名不同 schema 的表会被当成同一张表。
