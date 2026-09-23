---
name: sql-generation-helper
description: "SQL 生成——把一句话的取数需求写成只读 SQL：先确认表结构与口径，再用 JOIN、聚合、窗口函数、日期处理的常用模式写查询。当用户说「帮我写个 SQL」「这个指标怎么查」「按月统计一下」时使用。"
author: Captain
version: 0.1.0
display_name: "SQL 生成"
display_name_en: "SQL Generation"
description_zh: "把自然语言的取数需求写成 SQL：先确认表结构与字段口径，再写查询；给出 JOIN、聚合、窗口函数、日期处理的常用模式，每条 SQL 附「它回答什么问题」与「可能的坑」（NULL、重复行、时区）。只写只读查询，改数据、改表先给风险提示并等确认。"
description_en: "Turn plain-language data questions into read-only SQL: confirm schema and metric definitions first, use proven JOIN, aggregation, window-function and date patterns, and ship every query with the question it answers and its pitfalls (NULLs, duplicate rows, time zones)."
tags:
  - "SQL生成"
  - "SQL"
  - "写SQL"
  - "取数"
  - "数据查询"
  - "MySQL"
  - "PostgreSQL"
  - "窗口函数"
  - "text2sql"
  - "数据分析"
examples_zh:
  - "帮我写个 SQL：查上个月每个城市的下单用户数"
  - "这个指标怎么查？复购率，表结构我贴给你"
  - "按月统计一下各渠道的支付金额，库是 MySQL 8"
---

# SQL 生成

定位一句话：**SQL 出错的大头不在语法，在口径：同一句「上个月的活跃用户」，三个人能写出三个数。先钉死口径，再写查询。**
何时用：把一句话的取数需求写成 SQL；按月、按渠道统计；取每组最新一条、算环比；已有 SQL 结果对不上，要查哪一步多算或漏算了。

## 先确认：表结构与口径

动笔前拿齐五样，缺哪样问哪样，一次最多问 3 个：

```
方言    MySQL 8 / PostgreSQL / Hive……日期函数、窗口函数的写法各不相同
表结构  建表语句或字段清单；拿不到就请用户跑下面这条只读查询
粒度    每张表一行是什么：一个订单？订单里的一件商品？一个用户一天的快照？
口径    指标 = 分子 / 分母；按哪个时间字段（下单 / 支付）；排除什么（测试单、取消单、退款）
时区    时间存的是 UTC 还是本地时间；报表按哪个时区切天
```
```sql
-- 回答：orders、users 各有哪些字段、什么类型、能否为空（MySQL、PostgreSQL 通用）
-- 坑：多个库有同名表时结果会混在一起，加 table_schema 条件
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name IN ('orders', 'users')
ORDER BY table_name, ordinal_position;
```
口径用一句话复述给用户确认，例如「月活跃用户 = 该自然月（北京时间）内至少 1 笔已支付订单的去重用户数，不含测试账号」。确认了再写。

## 从一句话到 SQL：五个步骤

```
1 改写    「对每个 [分组]，算 [指标]，条件 [过滤]，时间 [范围]」，填不满说明还没问清
2 定粒度  结果一行是什么（一个城市一个月），据此写 GROUP BY
3 查连接  每个 JOIN 先问一对一还是一对多；一对多先聚合再连接，否则金额被放大
4 写查询  用 WITH 分步，每步一句注释；只选要用的列，不写 SELECT *
5 对账    中间结果查 COUNT(*) 与 COUNT(DISTINCT 主键) 是否相等；合计与已知报表比一比
```

## 常用模式：每条附「它回答什么问题」与「可能的坑」

```sql
-- 【JOIN 先聚合再连接】回答：每个用户的注册渠道和累计支付金额，没下过单的记 0
WITH paid AS (
  SELECT user_id, SUM(amount) AS paid_amount
  FROM orders WHERE status = 'paid' GROUP BY user_id
)
SELECT u.user_id, u.channel, COALESCE(p.paid_amount, 0) AS paid_amount
FROM users u LEFT JOIN paid p ON p.user_id = u.user_id;
-- 坑：users 连 orders 再连订单明细后 SUM，金额按明细行数重复累加；
--     LEFT JOIN 后在 WHERE 里过滤右表字段，等于变回 INNER JOIN，条件要放进 ON 或子查询

-- 【条件聚合】回答：各渠道的订单数、支付订单数和支付率
SELECT COALESCE(channel, '未知') AS channel, COUNT(*) AS orders,
       SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS paid_orders,
       ROUND(SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 4) AS paid_rate
FROM orders GROUP BY COALESCE(channel, '未知');
-- 坑：COUNT(列) 不数 NULL、COUNT(*) 数；PostgreSQL 整数相除会取整，所以乘 1.0；
--     channel 为 NULL 的不合并，报表里会多出一行空白

-- 【窗口：每组最新一条】回答：每个用户最近一笔订单（MySQL 8+、PostgreSQL）
SELECT user_id, order_id, created_at FROM (
  SELECT user_id, order_id, created_at,
         ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC, order_id DESC) AS rn
  FROM orders
) t WHERE rn = 1;
-- 坑：同一时刻两笔订单时次序不定，排序里加主键兜底；并列都要保留就改用 RANK()

-- 【窗口：环比】回答：每月支付金额及环比
WITH m AS (
  SELECT DATE_FORMAT(paid_at, '%Y-%m') AS month, SUM(amount) AS amt  -- PostgreSQL：to_char(paid_at, 'YYYY-MM')
  FROM orders WHERE status = 'paid' GROUP BY 1
)
SELECT month, amt, amt * 1.0 / NULLIF(LAG(amt) OVER (ORDER BY month), 0) - 1 AS mom FROM m;
-- 坑：某月没单时那一行根本不存在，LAG 会拿更早的月来比，先生成完整月份表再 LEFT JOIN；
--     paid_at 存 UTC 时，月份边界差 8 小时，先换算时区再分组

-- 【日期：左闭右开】回答：北京时间 2026 年 9 月的支付订单数（paid_at 是不带时区的 DATETIME，存 UTC）
SELECT COUNT(*) AS paid_orders FROM orders
WHERE status = 'paid'
  AND paid_at >= '2026-08-31 16:00:00'  -- 北京时间 9 月 1 日 00:00
  AND paid_at <  '2026-09-30 16:00:00'; -- 北京时间 10 月 1 日 00:00
-- 坑：BETWEEN '2026-09-01' AND '2026-09-30' 会漏掉 30 日 00:00 以后的数据；
--     DATE(paid_at) = …… 把函数套在字段上，索引通常用不上，换算放在常量一侧；
--     带时区的类型（PostgreSQL timestamptz、MySQL TIMESTAMP）按会话时区解释字面量，
--     先 SET TIME ZONE 'Asia/Shanghai'（MySQL：SET time_zone = '+08:00'），再直接写北京时间
```

## 最常见的错误：NULL、重复行、时区

```
NULL    col <> 'x' 不返回 col 为 NULL 的行；NOT IN（子查询）里只要有一个 NULL 就一行都不返回，改用 NOT EXISTS；
        SUM 全是 NULL 得到 NULL 而不是 0；AVG 跳过 NULL，分母比你以为的小
重复行  一对多 JOIN 放大行数，拿 DISTINCT 盖住是在藏问题；UNION 去重、UNION ALL 不去重
时区    存 UTC、报本地，切天边界差 8 小时；服务器、数据库会话、客户端三处时区可能各不相同
其他    LIMIT 不配 ORDER BY 结果不稳定；MySQL 关了 ONLY_FULL_GROUP_BY 时，非聚合列取值不确定
```

## 只读闸门：改数据、改表之前

默认只写 SELECT。用户要 INSERT、UPDATE、DELETE、ALTER、DROP、TRUNCATE 时，先回下面的风险提示，等用户明确回复「确认执行」再给语句：

```
影响范围  先跑同条件的 SELECT COUNT(*)，报出会动多少行
可回退    有没有备份；回滚是反向语句还是从备份恢复
执行方式  DML 放进事务，先 ROLLBACK 演练一次；大表分批；MySQL 的 DDL（含 TRUNCATE）会隐式提交，事务包不住
时机      避开业务高峰；DDL 可能锁表，先问 DBA
```
```bash
# 交付前的机械检查：命中就走上面的确认（REPLACE() 这类同名函数会误报，人工看一眼）
grep -inwE 'insert|update|delete|merge|replace|drop|alter|truncate|create|grant|revoke' query.sql && echo "含写操作，先确认"
```
执行只读查询时还可以加一道保险：MySQL 用 `START TRANSACTION READ ONLY;`，PostgreSQL 用 `BEGIN READ ONLY;`，事务里的写入会直接报错。

## 输出契约

```
方言与假设      MySQL 8；orders 一行一个订单；paid_at 为 UTC【需确认】
SQL             WITH 分步写，每步一句注释
它回答什么问题  一句业务话
可能的坑        2–3 条，针对这条 SQL，不是泛泛的清单
自检            一条对账查询：行数、合计与已知报表是否一致
```
没见到表结构时，表名、字段名一律标【需确认】并说明是按常见命名假设的，不把猜测当事实。

## 边界与不做什么

- 只写 SQL，不连数据库、不代为执行；执行和权限申请走你们自己的流程。
- 写操作必须过只读闸门；生产库变更由有权限的人按变更流程执行，本技能不建议「直接跑」。
- 不写绕过权限的查询，不拼 SQL 注入语句。
- 涉及个人信息只选需要的列，手机号、证件号在 SQL 里就脱敏或聚合，不导出明细。
- 索引设计、慢查询深度调优交给 DBA；这里只指出明显问题（函数包字段、缺连接条件）。
- 数字背后的业务判断（为什么涨跌、要不要调策略）由用户和业务方自己做。
