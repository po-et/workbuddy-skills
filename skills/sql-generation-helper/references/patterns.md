# 常用模式：每条附「它回答什么问题」与「可能的坑」

五个最常用的写法。每条开头一句「回答」说明它回答什么业务问题，结尾「坑」写这条 SQL 最容易出错的地方。方言默认 MySQL 8，PostgreSQL 写法写在注释里；交付前用 `python3 scripts/sql_guard.py 文件 --dialect 方言` 检查只读和常见坑。

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

## 怎么挑模式

| 需求里出现 | 用哪条 | 先确认什么 |
|---|---|---|
| 「每个用户的……」「累计」且要连多张表 | JOIN 先聚合再连接 | 每个 JOIN 是一对一还是一对多 |
| 「……率」「占比」「分渠道的订单数和支付数」 | 条件聚合 | 分子分母的口径；PostgreSQL 整数相除 |
| 「最新一条」「最近一次」「第一笔」 | 窗口：每组最新一条 | 并列时要一条还是都要 |
| 「环比」「同比」「比上月」 | 窗口：环比 | 有没有缺月；时区 |
| 「某月」「某天」「上周」 | 日期：左闭右开 | 时间字段存 UTC 还是本地时间、字段类型带不带时区 |
