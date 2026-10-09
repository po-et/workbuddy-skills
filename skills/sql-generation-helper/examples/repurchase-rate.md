# 示例：复购率怎么查（完整交付）

> 这是示例。表结构、字段名为演示而设，不对应任何真实系统；换成你的库时，按你贴出的表结构重写。SQL 的逻辑在一份演示数据上跑过（SQLite 里把 DATE_FORMAT 换成 strftime），两条对账查询都能照常返回。

## 1 用户原话

> 这个指标怎么查？复购率，表结构我贴给你。库是 MySQL 8。
>
> ```sql
> CREATE TABLE users (
>   user_id    BIGINT PRIMARY KEY,
>   city       VARCHAR(32),
>   is_test    TINYINT NOT NULL DEFAULT 0,   -- 1 = 测试账号
>   created_at DATETIME NOT NULL
> );
> CREATE TABLE orders (
>   order_id   BIGINT PRIMARY KEY,
>   user_id    BIGINT NOT NULL,
>   status     VARCHAR(16) NOT NULL,         -- created / paid / cancelled / refunded
>   amount     DECIMAL(12,2) NOT NULL,
>   created_at DATETIME NOT NULL,
>   paid_at    DATETIME NULL                 -- 北京时间
> );
> ```

## 2 助手先问（口径没定，先不写最终 SQL）

> 表结构清楚了，方言是 MySQL 8。「复购率」常见两种算法，先确认用哪种：
> 1. **A 当月复购**：当月支付 2 笔及以上的用户数 ÷ 当月有支付的用户数；
>    **B 次月回购**：上月支付过、本月又支付的用户数 ÷ 上月支付的用户数。
> 2. 看哪几个月？按自然月切，对吗？
> 3. 退款单（status = refunded）算不算一次购买？

## 3 用户补充

> 用 A。看最近半年，4 月到 9 月，自然月。只算 status = 'paid' 的，退款的不算，测试账号也去掉。

## 4 交付物

**方言与假设**：MySQL 8；orders 一行一个订单，users 一行一个用户；paid_at 是北京时间的 DATETIME（你在建表注释里写了）；只算 status = 'paid'；排除 users.is_test = 1。

**口径复述**：某月复购率 = 该自然月（北京时间）内支付成功 2 笔及以上的非测试用户数 ÷ 该月支付成功过的非测试用户数；退款单不计入。

**SQL**

```sql
-- 回答：2026 年 4–9 月每个自然月（北京时间）的复购率 = 当月支付 2 笔及以上的用户数 ÷ 当月有支付的用户数
WITH user_month AS (          -- 第 1 步：每个用户每个月支付了几笔（排除测试账号）
  SELECT DATE_FORMAT(o.paid_at, '%Y-%m') AS month,
         o.user_id,
         COUNT(*) AS paid_orders
  FROM orders o
  JOIN users u ON u.user_id = o.user_id
  WHERE o.status = 'paid'
    AND u.is_test = 0
    AND o.paid_at >= '2026-04-01 00:00:00'
    AND o.paid_at <  '2026-10-01 00:00:00'
  GROUP BY DATE_FORMAT(o.paid_at, '%Y-%m'), o.user_id
)
SELECT month,                 -- 第 2 步：按月汇总，分子分母都在同一张中间表里
       COUNT(*) AS paying_users,
       SUM(CASE WHEN paid_orders >= 2 THEN 1 ELSE 0 END) AS repeat_users,
       ROUND(SUM(CASE WHEN paid_orders >= 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 4) AS repeat_rate
FROM user_month
GROUP BY month
ORDER BY month;
```

**它回答什么问题**：4 月到 9 月，每个月有多少人付过钱、其中多少人当月付了两次及以上、占比多少。

**可能的坑**

1. 9 月还没过完（数据截至今天），当月复购率会偏低；报表里写明「9 月截至某日」，别和整月比。
2. orders 里有、users 里没有的 user_id 会被 JOIN 悄悄丢掉——对账 2 专门查这个。
3. 退款后又重新支付的订单，如果系统把原单改成 refunded、另生成新单，同一次购买可能只算一笔；status 的流转规则【待确认】。

**自检：对账查询**

```sql
-- 对账 1：9 月有支付的非测试用户数，应等于结果里 2026-09 那一行的 paying_users
SELECT COUNT(DISTINCT o.user_id) AS paying_users_sep
FROM orders o
JOIN users u ON u.user_id = o.user_id
WHERE o.status = 'paid'
  AND u.is_test = 0
  AND o.paid_at >= '2026-09-01 00:00:00'
  AND o.paid_at <  '2026-10-01 00:00:00';

-- 对账 2：orders 里的 user_id 在 users 表里都找得到吗？结果应为 0，否则 JOIN 会悄悄丢单
SELECT COUNT(*) AS orphan_orders
FROM orders o
LEFT JOIN users u ON u.user_id = o.user_id
WHERE u.user_id IS NULL;
```

**`python3 scripts/sql_guard.py repurchase.sql --dialect mysql` 的输出**

```
检查 repurchase.sql（方言：mysql）
结论：只读，没发现常见的坑（不代表口径正确，仍要跑对账查询）
```

**交付前自检**

| 检查项 | 结果 |
|---|---|
| 口径已用一句话复述并得到确认 | 是（用户选了 A） |
| 每个 JOIN 已确认一对一还是一对多，一对多先聚合 | 是（orders 对 users 是多对一，按用户和月份聚合后再算） |
| 日期区间左闭右开，并说明了时区 | 是（北京时间 DATETIME） |
| sql_guard.py 结论为只读，退出码 0 | 是 |
| 附了对账查询 | 是（两条） |
| 没见到表结构的表名、字段名标了【待确认】 | 不适用（用户贴了建表语句） |
