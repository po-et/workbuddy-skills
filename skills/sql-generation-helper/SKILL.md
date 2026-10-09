---
name: sql-generation-helper
description: "SQL 生成——把一句话的取数需求写成只读 SQL：先确认表结构与口径，再用 JOIN、聚合、窗口函数、日期处理的常用模式写查询。当用户说「帮我写个 SQL」「这个指标怎么查」「按月统计一下」时使用。"
author: Captain
metadata:
  openclaw:
    requires:
      bins: [python3]
version: 0.1.1
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
examples_en:
  - "Write me a SQL query for the number of ordering users in each city last month."
  - "How do I calculate the repeat purchase rate? I'll paste the table schema."
  - "Sum paid amounts by channel for each month. The database is MySQL 8."
---

# SQL 生成

定位一句话：**SQL 出错的大头不在语法，在口径：同一句「上个月的活跃用户」，三个人能写出三个数。先钉死口径，再写查询。**

**文件导航**：本页是主流程。五个常用模式的完整 SQL 见 [references/patterns.md](references/patterns.md)；复购率的完整交付（贴表结构 → 澄清口径 → SQL → 坑 → 对账）见 [examples/repurchase-rate.md](examples/repurchase-rate.md)；交付前的机械检查脚本是 `scripts/sql_guard.py`。

## 何时使用

把一句话的取数需求写成 SQL；按月、按渠道统计；取每组最新一条、算环比；已有 SQL 结果对不上，要查哪一步多算或漏算了。用户常这样说：

- 「帮我写个 SQL：查上个月每个城市的下单用户数」
- 「这个指标怎么查？复购率，表结构我贴给你」
- 「按月统计一下各渠道的支付金额，库是 MySQL 8」
- 「取每个用户最近一笔订单」
- 「这条 SQL 算出来比报表多，帮我看哪里重复了」
- 「这句 MySQL 的 SQL 改成 PostgreSQL 怎么写」

不适用：

- 要直接连库执行、导出数据：本技能只写 SQL，不连数据库、不代为执行；执行和权限申请走你们自己的流程。
- 索引设计、慢查询深度调优、库表设计：交给 DBA；这里只指出明显问题（函数包字段、缺连接条件）。
- 在 Excel 里做汇总、做报表版式：转交 Excel 或报表类技能。

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
口径用一句话复述给用户确认，例如「月活跃用户 = 该自然月（北京时间）内至少 1 笔已支付订单的去重用户数，不含测试账号」。确认了再写。这条查询的结果导出成 CSV，还能交给 `scripts/sql_guard.py --columns` 核对 SQL 里的字段名。

## 从一句话到 SQL：五个步骤

```
1 改写    「对每个 [分组]，算 [指标]，条件 [过滤]，时间 [范围]」，填不满说明还没问清
2 定粒度  结果一行是什么（一个城市一个月），据此写 GROUP BY
3 查连接  每个 JOIN 先问一对一还是一对多；一对多先聚合再连接，否则金额被放大
4 写查询  用 WITH 分步，每步一句注释；只选要用的列，不写 SELECT *
5 对账    中间结果查 COUNT(*) 与 COUNT(DISTINCT 主键) 是否相等；合计与已知报表比一比
```

## 常用模式：每条附「它回答什么问题」与「可能的坑」

五个模式的完整 SQL（含 PostgreSQL 写法注释）在 [references/patterns.md](references/patterns.md)，用之前先看它的「坑」：

| 模式 | 它回答什么问题 | 最要命的坑 |
|---|---|---|
| JOIN 先聚合再连接 | 每个用户的注册渠道和累计支付金额，没下过单的记 0 | 一对多连接后 SUM，金额按明细行数重复累加；LEFT JOIN 后在 WHERE 过滤右表等于 INNER JOIN |
| 条件聚合 | 各渠道的订单数、支付订单数和支付率 | COUNT(列) 不数 NULL；PostgreSQL 整数相除取整，要乘 1.0 |
| 窗口：每组最新一条 | 每个用户最近一笔订单 | 同一时刻两笔时次序不定，排序加主键兜底；并列都要保留用 RANK() |
| 窗口：环比 | 每月支付金额及环比 | 某月没单那一行不存在，LAG 会拿更早的月来比；UTC 存储要先换时区 |
| 日期：左闭右开 | 北京时间某月的支付订单数 | BETWEEN 漏掉最后一天；函数包在字段上用不上索引 |

## 只读闸门：改数据、改表之前

默认只写 SELECT。用户要 INSERT、UPDATE、DELETE、ALTER、DROP、TRUNCATE 时，先回下面的风险提示，等用户明确回复「确认执行」再给语句：

```
影响范围  先跑同条件的 SELECT COUNT(*)，报出会动多少行
可回退    有没有备份；回滚是反向语句还是从备份恢复
执行方式  DML 放进事务，先 ROLLBACK 演练一次；大表分批；MySQL 的 DDL（含 TRUNCATE）会隐式提交，事务包不住
时机      避开业务高峰；DDL 可能锁表，先问 DBA
```

交付前的机械检查（它跳过注释和字符串，REPLACE() 函数、update_time 这类字段名不会误报成写操作）：

```bash
python3 scripts/sql_guard.py query.sql --dialect mysql
python3 scripts/sql_guard.py query.sql --dialect postgresql --columns columns.csv
```

结果码：B = 写操作、DDL、SET/VACUUM 或可执行注释（必须过上面的闸门）；W = 常见坑（SELECT *、BETWEEN 日期、NOT IN 子查询、LIMIT 没配 ORDER BY、函数包字段、JOIN 缺条件、LEFT JOIN 后 WHERE 过滤右表、整数相除、和 NULL 用等号比较、FOR UPDATE）；D = 所选方言不支持的写法；C = 字段名在字段清单里找不到。MySQL `/*! ... */`（含版本号）和 MariaDB `/*M! ... */` 会先阻断：展开成普通 SQL 后再查，不把它们当成可忽略的注释。执行只读查询时还可以加一道保险：MySQL 用 `START TRANSACTION READ ONLY;`，PostgreSQL 用 `BEGIN READ ONLY;`，事务里的写入会直接报错。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（模板） |
|---|---|---|
| 没给表结构 | 先请用户跑上面那条 information_schema 查询；等不到就按常见命名写，表名、字段名标【待确认】并说明是假设 | 「我先按常见命名写了，表名和字段名都标了【待确认】；跑一下这条只读查询把字段清单贴给我，我换成真实的。」 |
| 口径不清，一个指标有两种算法 | 列出两种理解让用户选，确认前不交最终 SQL | 「复购率常见两种：A 当月买 2 次及以上的人 ÷ 当月购买人数；B 上月买过、本月又买的人 ÷ 上月购买人数。按哪种？」 |
| 方言没说 | 默认 MySQL 8 并标【待确认】；日期函数、窗口函数处注明 PostgreSQL 写法 | 「先按 MySQL 8 写，标了【待确认】；如果是 PostgreSQL 或 Hive，告诉我，我换日期函数。」 |
| 需求自相矛盾（如「上个月」却给了本月的日期范围；分组字段在给的表里不存在） | 指出矛盾，给两种理解让用户选 | 「你说上个月，但给的是 9 月 1 日到今天——按 8 月整月，还是 9 月至今？」 |
| 用户贴来的 SQL 跑不通或结果对不上 | 先用 `sql_guard.py --dialect` 查方言和常见坑；再按五步第 5 步对账：行数、去重主键数、合计、时间字段、剔除规则、时区 | 「DATE_FORMAT 是 MySQL 的函数，你们是 PostgreSQL，要换成 to_char；另外先跑这两条对账查询看差在哪一步。」 |
| 要写操作（INSERT/UPDATE/DELETE/DDL） | 走只读闸门：先回风险提示，等明确回复「确认执行」 | 「这是写操作，先确认四件事：会动多少行、怎么回滚、事务里先演练、避开高峰。回复『确认执行』后我再给语句。」 |
| 超出范围：连库执行、绕过权限、拼注入语句、导出个人信息明细 | 不做；执行走用户自己的流程；个人信息只给聚合或脱敏版本 | 「我不连库，也不写绕过权限的查询；手机号这类字段我只给脱敏或聚合的写法。」 |
| 时间紧，只要能跑的最小版 | 最小版：一条 SQL＋一句口径＋一条对账查询；坑只写最要命的一条 | 「先给你能跑的最小版：一条查询、一句口径、一条对账；其他坑回头补。」 |
| 用户坚持在生产库直接跑写操作 | 守住：只给影响范围查询、回滚语句和演练步骤，执行由有权限的人按变更流程做 | 「生产库变更要由有权限的人按变更流程执行；我把影响范围查询和回滚语句先准备好。」 |
| 回复太长被截断或中途断了 | 按输出契约的固定顺序分段交付；用户说「继续」就从下一段接着写 | 「上一条停在 SQL。回复『继续』，我接着给可能的坑和对账查询。」 |

检查脚本的退出码与报错：

| 退出码 / 报错 | 原因 | 修正办法 |
|---|---|---|
| 0 | 只读；可能带 W、D、C 提醒 | 逐条确认提醒，改完再跑一次 |
| 1「不认识的方言」「字段清单缺 table_name 或 column_name 列」「SQL 是空的」「参数有误」 | 方言不在 mysql、mysql57、postgresql、sqlite 里；字段清单没有表头；没给 SQL | 其他库先不加 `--dialect`；字段清单用上面的 information_schema 查询导出并保留表头 |
| 2「……不存在」「编码认不出来」 | 路径不对，或文件不是 UTF-8/GBK | 核对路径；另存为 UTF-8 |
| 3 | 写操作、DDL、SET/VACUUM 或可执行注释触发闸门 | 按只读闸门先回风险提示；可执行注释先展开成普通 SQL 再核对 |
| 130 | 按了 Ctrl+C | 重新运行即可，脚本不改任何文件 |

## 输出契约

每条 SQL 按固定顺序交付，五项都要有：

```
方言与假设      MySQL 8；orders 一行一个订单；paid_at 为 UTC【待确认】
SQL             WITH 分步写，每步一句注释
它回答什么问题  一句业务话
可能的坑        2–3 条，针对这条 SQL，不是泛泛的清单
自检            一条对账查询：行数、合计与已知报表是否一致
```

占位符：`【待确认】` 表示按常见命名或默认值做的假设（表名、字段名、方言、时区），用户核对后删掉；`【待补】` 表示缺了就写不下去、必须用户给的值（如统计区间、某个状态的取值）。SQL 里不用方括号当占位——SQL Server 用方括号引用标识符，容易混淆。没见到表结构时，表名、字段名一律标【待确认】并说明是按常见命名假设的，不把猜测当事实。

交付前自检（逐条判断是/否，有一条「否」就改完再交）：

1. 口径已用一句话复述并得到确认，或标了【待确认】？
2. 每个 JOIN 都确认了一对一还是一对多，一对多已先聚合再连接？
3. 日期区间是左闭右开，并说明了时区？
4. `python3 scripts/sql_guard.py` 结论为只读（退出码 0），W、D、C 提醒逐条处理过？
5. 附了至少一条对账查询？
6. 没见到表结构的表名、字段名都标了【待确认】？

## 示例

（示例）

**用户**：帮我写个 SQL：查上个月每个城市的下单用户数。

**助手先问**：① 库是 MySQL 8 吗？② 城市用 users 表里的城市，还是订单上的收货城市？③「下单」是创建订单就算，还是只算支付成功？时间存的是北京时间吗？

**用户**：MySQL 8；用 users.city；下单就算，不管支付；时间是北京时间。

**助手交付**：

方言与假设：MySQL 8；orders 一行一个订单，users 一行一个用户；orders.created_at 存北京时间；「上个月」按 2026 年 8 月；不排除测试账号【待确认：有没有测试账号标记字段】。

```sql
-- 回答：2026 年 8 月（北京时间）每个城市有多少个下过单的用户，一个人下多单只算一次
WITH aug_buyers AS (            -- 第 1 步：8 月下过单的用户，去重
  SELECT DISTINCT user_id
  FROM orders
  WHERE created_at >= '2026-08-01 00:00:00'
    AND created_at <  '2026-09-01 00:00:00'
)
SELECT COALESCE(u.city, '未知') AS city,   -- 第 2 步：连用户表取城市，按城市计数
       COUNT(*) AS order_users
FROM aug_buyers a
JOIN users u ON u.user_id = a.user_id
GROUP BY COALESCE(u.city, '未知')
ORDER BY order_users DESC, city;
```

它回答什么问题：8 月每个城市有多少人下过单（取消的单也算，一人多单算一次）。

可能的坑：① users.city 是用户资料里的城市，不是下单时的收货城市；② orders 里有、users 里没有的 user_id 会被 JOIN 丢掉；③ city 为空的归到「未知」，不会多出一行空白。

自检（对账）：

```sql
-- 对账：8 月下过单的去重用户数，应等于上面各城市 order_users 之和；不相等说明有订单用户在 users 表里找不到
SELECT COUNT(DISTINCT user_id) AS buyers
FROM orders
WHERE created_at >= '2026-08-01 00:00:00'
  AND created_at <  '2026-09-01 00:00:00';
```

两条都用 `python3 scripts/sql_guard.py --dialect mysql` 检查过，结论为只读、没有提醒。复购率的完整交付见 [examples/repurchase-rate.md](examples/repurchase-rate.md)。

## 常见问题（FAQ）

**Q：没有表结构能写吗？**
A：能先写，按常见命名假设，表名、字段名标【待确认】；最好跑一下 information_schema 那条只读查询，把字段清单贴过来。

**Q：能帮我直接连数据库跑吗？**
A：不能。本技能只写 SQL，不连库、不执行；执行和权限申请走你们自己的流程。

**Q：MySQL 和 PostgreSQL 的写法主要差在哪？**
A：日期格式化（DATE_FORMAT 与 to_char）、类型转换（CAST 与 ::）、整数相除（PostgreSQL 会取整）、LIMIT m, n 的写法。用 `sql_guard.py --dialect` 能查出常见的差异。

**Q：结果和报表对不上，怎么查？**
A：先对账再改 SQL：比 COUNT(*) 和 COUNT(DISTINCT 主键)、比合计，再逐项核对时间字段、剔除规则和时区。多数差异出在一对多 JOIN 和切天的时区上。

**Q：能帮我写 UPDATE、DELETE 吗？**
A：能，但先过只读闸门：报出影响行数、回滚方式、事务演练和执行时机，等你明确回复「确认执行」再给语句。

**Q：查询太慢怎么办？**
A：这里只指出明显问题：函数包在字段上、缺连接条件、SELECT *。索引设计和深度调优交给 DBA。

**Q：窗口函数、WITH 在我们库里用不了？**
A：MySQL 5.7 不支持窗口函数和 WITH，8.0 起支持；改写成子查询或自连接，或者先确认数据库版本。

**Q：为什么每条 SQL 都要写「它回答什么问题」？**
A：把 SQL 翻译回业务话，用户一眼就能看出口径对不对；同一句需求，三个人能写出三个数。

## 常见错误（反模式）

| 错误做法 | 为什么错 | 正确做法 |
|---|---|---|
| 用 `col <> 'x'` 想只排除 x | col 为 NULL 的行也被排除 | 要保留 NULL 就写 `(col <> 'x' OR col IS NULL)` |
| `NOT IN（子查询）` | 子查询里只要有一个 NULL 就一行都不返回 | 改用 NOT EXISTS |
| 把 `SUM` 的结果直接当 0 用 | 全是 NULL 时得到 NULL 而不是 0 | `COALESCE(SUM(x), 0)` |
| 用 AVG 却没想到它跳过 NULL | 分母比你以为的小 | 明确分母，需要时先 COALESCE |
| 一对多 JOIN 后直接 SUM | 金额按明细行数重复累加 | 先聚合再连接 |
| 拿 DISTINCT 盖住重复行 | 在藏问题，口径更难核对 | 用 COUNT(*) 对 COUNT(DISTINCT 主键) 找出放大的那一步 |
| 该用 UNION ALL 时用了 UNION | UNION 会去重，合并掉本该保留的行 | 只合并不去重用 UNION ALL |
| 存 UTC、按本地时间切天却不换算 | 切天边界差 8 小时 | 先换算时区再分组，或把边界写成 UTC 常量 |
| 默认服务器、数据库会话、客户端时区一致 | 三处时区可能各不相同 | 查询前显式设置会话时区 |
| LIMIT 不配 ORDER BY | 每次返回的行不固定 | 加 ORDER BY，并用主键兜底 |
| MySQL 关了 ONLY_FULL_GROUP_BY，SELECT 非聚合列 | 取值不确定 | 非聚合列都进 GROUP BY 或包上聚合函数 |
| LEFT JOIN 后在 WHERE 里过滤右表 | 等于变回 INNER JOIN | 条件放进 ON 或子查询 |
| `BETWEEN '2026-09-01' AND '2026-09-30'` | 漏掉 30 日 00:00 以后的数据 | 左闭右开：`>= '2026-09-01' AND < '2026-10-01'` |
| 没见表结构就把猜的字段名写成确定的 | 猜测被当成事实，跑不通或算错 | 标【待确认】，拿到字段清单再替换 |

## 边界与不做什么

- 只写 SQL，不连数据库、不代为执行；执行和权限申请走你们自己的流程。
- 写操作必须过只读闸门；生产库变更由有权限的人按变更流程执行，本技能不建议「直接跑」。
- 不写绕过权限的查询，不拼 SQL 注入语句。
- 涉及个人信息只选需要的列，手机号、证件号在 SQL 里就脱敏或聚合，不导出明细。
- 索引设计、慢查询深度调优交给 DBA；这里只指出明显问题（函数包字段、缺连接条件）。
- 数字背后的业务判断（为什么涨跌、要不要调策略）由用户和业务方自己做。
