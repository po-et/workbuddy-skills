# 报价核对输入与输出

## 输入 v1

顶层只允许两个键：`schema_version`（整数 `1`）和 `quotes`。`quotes` 只允许 `A`、`B`，每份报价只允许 `fees`、`conditions`，所有列出的键均必填。任何层级未知键、缺键、重复 JSON 键或不合法类型均报错。

费用键固定为：

| 键 | 中文含义 |
|---|---|
| `vehicle` | 裸车价 |
| `quoteTax` | 报价中已给出的税费，不是计算税率 |
| `insurance` | 保险 |
| `registration` | 上牌 |
| `service` | 服务费 |
| `mandatoryExtras` | 强制装潢及附加项 |
| `other` | 其他费用 |

每项费用必须且只能含：

```json
{"amount":"5000.00","confirmed":true,"source":"合成原文第 7 行：保险 5000 元"}
```

- `amount` 为非负、最多两位小数的十进制**元字符串**，或未知值 `null`。不接受 JSON 数字、布尔值、负数、正负号、指数、NaN/Infinity、空字符串、逗号、单位符号、前导零或超过两位小数。`"0"`、`"0.0"`、`"0.00"` 均明确为零。
- 每项最高 `999999999.99` 元。这是工具边界，不是车价事实。
- `confirmed` 为严格布尔值。`null` 即使错误标为 `true` 仍缺失，不能放行。
- `source` 为字符串，最多 20000 字符。未知项可用空字符串；已知且已确认的项仍须非空来源才可放行。来源内容不由程序验证真伪。

条件键固定为 `model`（车型/配置）、`payment`（付款条件）、`scope`（费用范围）。每项只能含：

```json
{"value":"合成星河 标准款","confirmed":true,"source":"公开合成原文：车型/配置：合成星河 标准款"}
```

`value` 是最多 500 字符的字符串或 `null`；空白文本视为缺失。`confirmed` 与 `source` 约定同上。只有去掉首尾空白后文本完全相等，才视为两边同条件；本工具不推断语义等价。发生付款/配置/范围差异时，应拿到明确补充报价再核对，不能仅为放行而把文本改成一样。

整个输入为 UTF-8，最多 1 MiB。完整有效示例见 `assets/`；未知项同样保留三个键，如 `{"amount":null,"confirmed":false,"source":"公开合成原文：服务费待确认"}`。

## 执行与文件行为

```bash
python3 scripts/quote_check.py assets/synthetic-complete.json
python3 scripts/quote_check.py assets/synthetic-complete.json --json-output report.json --markdown-output report.md
python3 scripts/quote_check.py assets/synthetic-complete.json --include-source --markdown-output full-report.md
```

不指定输出路径时向标准输出写 JSON。`-` 输入从标准输入读取。正常核对（包括不可比较）退出码 `0`；JSON/schema/文件错误退出码 `2`，错误写标准错误。已有报告默认拒绝覆盖；明确使用 `--overwrite` 后可覆盖报告，但永远不能把输入当作输出、或让两个输出指向同一路径。单个输出文件原子写入，权限设为仅拥有者可读写；两个输出不是跨文件事务。

## 输出

- 金额同时以规范的两位元字符串和整数分输出。`known_subtotal` 是所有已录入有效金额之和，**可以包含未确认候选**；未知不参与加法，但仍以 `null` 保留，绝不视为零。
- `complete_total` 仅在当前报价七项金额都已确认且有来源时给出；这是七项已确认合计，条件不一致时仍不能用来排名。
- `comparable` 仅在两边七项费用与三类条件均明确/已确认/有来源，且三类条件一致时为 `true`。
- 不可比较时 `comparison_delta`、`comparison_delta_cents` 为 `null`，`fee_differences` 为空。可比较时差额按 `B − A`，正数 B 高，负数 B 低；七项差额保留明确的零。
- `blockers` 使用标准字段、报价标识与原因码：`fee_missing`、`fee_unconfirmed`、`fee_source_missing`、`condition_missing`、`condition_unconfirmed`、`condition_source_missing`、`condition_mismatch`。`questions` 为对应的通用追问，不插入私人原文。
- 默认 `export_mode=omit_source`，没有 `source` 或条件 `value`。主动 `--include-source` 后为 `include_source`，JSON 和 Markdown 含原文及自由文本条件。Markdown 将这些内容作为字面文本显示，不能当作可执行 HTML。
- 输出是核对报告，不是可直接导入的输入格式。程序不提供自动文本提取、历史确认同步、原文真伪验证或报告重新导入功能。

## 合成样例预期

| 样例 | A 小计 | B 小计 | 是否可比较 | 预期差额 B−A |
|---|---:|---:|---|---:|
| `synthetic-missing.json` | 115500.00 | 112500.00 | 否：B 服务费未知 | `null` |
| `synthetic-complete.json` | 115500.00 | 118500.00 | 是 | +3000.00 |
| `synthetic-payment-mismatch.json` | 114400.00 | 112400.00 | 否：付款方式不同 | `null` |
| `synthetic-cent-complete.json` | 101388.00 | 101388.01 | 是 | +0.01 |

税费均为合成报价输入值，不代表税收规则。数据为维护者验证所用，不是独立真人使用或成交证据。
