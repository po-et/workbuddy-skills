---
name: sql-migration-check
description: SQL 迁移脚本上线前风险检查、数据库变更评审、DDL 锁表风险、丢数据风险、MySQL / PostgreSQL 在线 DDL 建议、扩展-收缩迁移。当用户说「帮我看看这个迁移 SQL 能不能直接上线」「这条 ALTER 会不会锁表」「数据库变更评审」「Flyway/Liquibase/Alembic/Django 的迁移文件有没有风险」「加 NOT NULL 列为什么失败」时使用。附纯标准库脚本 scripts/sql_migration_check.py：切分语句、自动识别方言，16 条规则——DROP TABLE/COLUMN、TRUNCATE、无 WHERE 的 UPDATE/DELETE、NOT NULL 无 DEFAULT 的新列、易变函数默认值、改列类型、RENAME、非 CONCURRENTLY 建索引、加外键/唯一约束、SET NOT NULL、无主键建表、MyISAM、显式 LOCK 等，每条给出对应方言的安全做法；支持目录递归、stdin、--json、--strict。
author: Captain
version: 0.1.1
display_name: "数据库迁移风险"
display_name_en: "SQL Migration Risk Check"
description_zh: "上线前扫一遍迁移 SQL：找出会锁表、丢数据、让滚动部署报错的语句，按 high/warn/info 分级并给出 MySQL / PostgreSQL 各自的安全写法；纯 Python 标准库。"
description_en: "Scan migration SQL before release: find statements that lock tables, lose data or break rolling deploys, graded high/warn/info with MySQL/PostgreSQL-specific safe alternatives; pure Python stdlib."
examples_zh:
  - "检查 migrations/ 目录下的迁移 SQL 有没有上线风险"
  - "这条 ALTER TABLE 加 NOT NULL 列会不会出问题"
  - "把迁移检查加进 CI，有 high 就拦截"
examples_en:
  - "Check the migration SQL under migrations/ for release risks"
  - "Will this ALTER TABLE adding a NOT NULL column break?"
  - "Gate CI on the migration check, block on high"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🗄️" } }
---

# SQL 迁移风险检查

上线前给迁移脚本做一次风险扫描：哪些语句会长时间锁表、永久丢数据、或让仍在运行的旧版本代码报错。输出分级问题、原语句和对应方言的安全做法。纯 Python 标准库，正则启发式，不连数据库。

## 用法

```bash
python3 scripts/sql_migration_check.py migrations/            # 目录递归所有 .sql
python3 scripts/sql_migration_check.py 0042_add_status.sql --dialect postgres
cat change.sql | python3 scripts/sql_migration_check.py -    # stdin
python3 scripts/sql_migration_check.py migrations/ --json --strict   # CI：有 high 退出码 1
```

ORM 生成的迁移（Alembic / Django / Flyway / Liquibase）先导出成 SQL 再检查：如 `alembic upgrade --sql`、`python manage.py sqlmigrate app 0042`。

## 流程

1. 跑脚本，**high** 必须处理：DROP、TRUNCATE、无 WHERE 的改删、NOT NULL 无 DEFAULT 的新列。
2. **warn** 评估表大小与业务时段：改列类型、RENAME、加外键/唯一约束、SET NOT NULL、非并发建索引。大表按输出建议改成多步（扩展-收缩、NOT VALID + VALIDATE、CONCURRENTLY、在线 DDL 工具）。
3. 把最终 SQL 与执行计划（预计行数、锁级别）写进变更单，交 DBA 评审。
4. 加进 CI：`--strict` 拦 high；warn 只报告。

## 规则一览

| 级别 | 规则 | 检查点 |
|---|---|---|
| high | SM001 / SM002 / SM006 | DROP TABLE / DROP COLUMN；TRUNCATE；UPDATE/DELETE 无 WHERE |
| high | SM003 | 新增 NOT NULL 列但无 DEFAULT（旧数据行导致失败或全表回填） |
| warn | SM004 / SM005 | 改列类型或定义；RENAME 表/列（旧代码立刻报错） |
| warn | SM007 / SM008 / SM009 / SM012 | 非 CONCURRENTLY 建索引（PG）；加外键；加唯一索引/约束；SET NOT NULL |
| warn | SM013 / SM015 / SM017 / SM018 | 建表无主键；易变函数默认值（PG 全表重写）；显式 LOCK；MyISAM |
| info | SM007 / SM011 / SM016 | MySQL 建索引未指定 ALGORITHM/LOCK；一条 ALTER 堆多个变更；删索引 |

## 边界

- 正则启发式，不解析完整 SQL 语法；复杂语句可能漏报或误报，输出里附原语句便于人工复核。
- 方言自动识别只依赖关键字特征（CONCURRENTLY、serial、`、ENGINE= 等），拿不准时用 `--dialect` 指定。
- 不评估表大小；「会不会真的锁很久」要结合行数与业务时段判断。
