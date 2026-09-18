---
name: csv-profile
description: CSV 数据画像、TSV 数据画像、拿到一份 CSV 不知道里面有什么、先看数据质量再入仓、列类型推断、空值率统计、唯一值与枚举取值分布、数值列分位数（min/p25/中位/p75/max/均值/标准差）、日期列时间范围、疑似主键列、常量列、全空列、混合类型列、重复行、字段数不一致的坏行、取值带前后空格、疑似个人信息列（手机号/身份证/邮箱/银行卡）。当用户说「这个 CSV 里都有什么」「帮我看看这份数据干不干净」「这些列都是什么类型」「有没有重复行和空值」「入库前先体检一下」「大文件先采样看看」时使用。附纯标准库脚本 scripts/csv_profile.py，自动嗅探分隔符与 utf-8/utf-8-sig/gbk 编码、识别表头，逐列出画像并汇总数据质量问题清单，支持 --rows 采样、--top、--json、--strict 与 stdin。
author: Captain
version: 0.1.0
display_name: "CSV 数据画像"
display_name_en: "CSV Profile"
description_zh: "给 CSV/TSV 做一次入仓前体检：自动嗅探分隔符与编码，逐列给出类型、空值率、唯一值、Top 取值、数值分位数与时间范围，再汇总全空列、常量列、混合类型、重复行、坏行、疑似个人信息等质量问题并附改法；纯 Python 标准库，大文件可采样。"
description_en: "Pre-ingest health check for CSV/TSV: sniffs delimiter and encoding, profiles every column (type, null rate, cardinality, top values, numeric quantiles, time range), then lists quality issues — empty and constant columns, mixed types, duplicate rows, ragged rows, suspected PII — with fixes. Pure stdlib, samples large files."
examples_zh:
  - "这个 CSV 里都有什么，帮我出一份数据画像"
  - "入库前先体检一下这份订单数据，有没有空值和重复行"
  - "这份 TSV 是 gbk 编码的，帮我看看列类型推断对不对"
examples_en:
  - "What is in this CSV? Give me a column profile"
  - "Check this order data before ingest — nulls, duplicate rows?"
  - "This TSV is GBK encoded; verify the inferred column types"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📊" } }
---

# CSV 数据画像

拿到一份别人给的 CSV，第一件事不是写 SQL，是先看它到底长什么样。这个技能一条命令给出逐列画像和一份数据质量问题清单，用来决定「能不能直接入仓」「哪些列要清洗」「哪些列不能外发」。

## 用法

```bash
python3 scripts/csv_profile.py data.csv                       # 全量画像
python3 scripts/csv_profile.py big.csv --rows 200000          # 大文件只采样前 20 万行
python3 scripts/csv_profile.py data.tsv --delimiter tab --encoding gbk
python3 scripts/csv_profile.py raw.csv --no-header --top 10
python3 scripts/csv_profile.py data.csv --json > profile.json  # 给下游程序用
cat data.csv | python3 scripts/csv_profile.py -
python3 scripts/csv_profile.py data.csv --strict               # 有 high 问题则退出码 1，可当 CI 门禁
```

## 何时用

- 接到一份来源不明的数据文件，要判断字段含义与质量；
- 入仓/建表前定类型、定主键、定非空约束；
- 对外提供数据前确认有没有个人信息列；
- 上游换了导出脚本，怀疑格式变了（对比两次画像的类型与空值率）。

## 流程

1. 先跑一次不带参数的全量画像，看顶部一行的编码、分隔符、表头识别是否正确。识别错了用 `--delimiter` / `--encoding` / `--no-header` 显式指定，其余结论才有意义。
2. 看「列画像」：类型是否符合预期，空值率是否可接受，枚举列的取值集合是否只有预期的几种。
3. 看「数据质量」清单，按 high → warn → info 处理。high 通常意味着数据不能直接入仓。
4. 定主键：用 C004 给出的「唯一且无空值」候选列，配合业务语义选一个，建表时加唯一索引。
5. 有 C007 疑似个人信息时，外发前先用「日志与数据脱敏」技能处理。
6. 把这份画像贴进需求或数据接入文档，后续上游变更时重跑一次即可 diff。

## 输出

- **文件概览**：编码、分隔符、表头有无、列数、数据行数（是否采样）、完全重复行数。
- **逐列画像**：序号、列名、推断类型、空值数与占比、唯一值数（`+` 表示超出跟踪上限）、最常见 N 个取值及占比；数值列附 min/p25/中位/p75/max/均值/标准差与零值负值数；文本列附长度分布；日期列附时间范围与跨度天数；混合类型列附各类型构成。
- **数据质量清单**：规则号 + 现象 + 改法，末尾给 high/warn/info 小计。

## 类型推断

逐值判断邮箱、URL、ID（UUID / 长十六进制）、布尔、整数、小数、日期时间，其余算文本；再做列级细化：

- 某一类占比不足 95% 且存在两类以上 → **混合类型**；
- 整数列取值只有 0/1 → **布尔(0/1)**；全是合法 `YYYYMMDD` → **日期时间(YYYYMMDD)**；
- 文本列唯一值很少（≤ max(10, 2%) 且不超过半数行）→ **枚举**；
- 列名带 id/编号/单号 之类且全唯一 → **ID**；唯一值只有一个 → **常量(原类型)**；无非空值 → **全空**。

空值口径包含空串与 `NA`/`N/A`/`null`/`none`/`nan`/`-`/`无`/`未知` 这类占位符。

## 数据质量规则

| 规则 | 级别 | 含义 |
| --- | --- | --- |
| C001 | high | 整列为空 |
| C009 | high | 行字段数与表头不一致（给出行号与实际列数） |
| C007 | high/warn | 疑似个人信息列（手机号/身份证/银行卡/邮箱形态占比 ≥ 30%，或列名疑似） |
| C003 | warn | 混合类型列 |
| C005 | warn | 空值率 ≥ 30% |
| C006 | warn | 取值带前后空格 |
| C008 | warn | 表头重复列名 |
| C010 | warn | 完全重复的数据行 |
| C002 | info | 常量列 |
| C004 | info | 唯一且无空值的主键候选列 |
| C011 | info | 未识别到表头 |

## 边界与常见问题

- 分隔符嗅探基于首 64KB 样本，字段里含大量分隔符的脏文件可能误判，显式传 `--delimiter` 最稳。
- 编码按 utf-8-sig → utf-8 → gbk → gb18030 顺序试，都失败时用 utf-8 加 `errors=replace` 兜底，乱码字符会计入文本长度。
- 纯 8 位数字列在全部能解析成日期时会判成 `YYYYMMDD`，订单号恰好长这样时会被误判，看一眼 Top 取值即可确认。
- 个人信息识别是形态匹配，**只能用来提醒，不能当合规结论**；自由文本里的姓名地址、拼接过的证件号都识别不到。
- 全量模式会把每列的唯一值放进内存（默认每列最多跟踪 5 万个），数值列还会保留全部数值以算分位数；上亿行文件请用 `--rows` 采样，或先 split 再分别画像。
- 不做跨列一致性校验（比如省市是否匹配），也不猜业务含义；那属于数据建模，不是画像。
