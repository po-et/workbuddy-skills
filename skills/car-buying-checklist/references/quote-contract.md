# 两份报价核对：输入与输出契约

仅处理用户给定的两份报价。Python 3 标准库，离线；不查询价格、税率、政策或 APR，不判断报价真伪，不推荐车型、商家或融资。

## 输入

```bash
python3 scripts/compare_quotes.py --input examples/two-quotes-missing-fee.json --out-dir /tmp/car-missing-new
python3 scripts/compare_quotes.py --input examples/two-quotes-complete.json --out-dir /tmp/car-complete-new
```

`--out-dir` 必须是不存在的新目录，父目录必须存在。存在的目录、文件、符号链接一律拒绝，防止覆盖输入或旧报告。输入须为普通 UTF-8 JSON 文件，最多 1 MiB；不接受符号链接。失败退出 1，不生成报告；成功退出 0。重复 CLI 参数由解析器拒绝（退出 2）。只在全部校验成功后创建输出目录。

顶层对象：

| 字段 | 必填 | 含义 |
|---|---|---|
| `schema_version` | 是 | 数值 `1` |
| `notice` | 否 | 单行说明；样例明确标注合成数据 |
| `quotes` | 是 | 恰好两个对象，顺序保留，不能重复 id |

每份报价：

| 字段 | 必填 | 含义 |
|---|---|---|
| `id` | 是 | 1–300 字符单行标识；不需要填姓名、电话、车架号 |
| `source` | 是 | 用户提供的单行来源说明；脚本不验证其真实性 |
| `method` | 是 | `cash` 或 `finance` |
| `amounts` | 是 | 对象，允许 `price`、`tax`、`insurance`、`plate`、`addons` |
| `finance` | 贷款报价使用 | 对象，允许 `principal`、`total_repay`、`fees_outside_total` |
| `energy` | 否 | 对象，允许下表的年度能耗假设；不计入购车款项与贷款费用合计 |

金额单位统一为元。用普通 JSON 数字或十进制数字字符串，最多 12 位小数，范围 0–1e15；金融金额运算使用 Decimal。缺失字段与显式 null 都表示未知，输出仍保留 null；**0 只能表示明确录入零**。不接受万/w/货币符号（单报价旧脚本仍兼容），不接受布尔值、数组、NaN、Infinity、负数、未知字段或重复 JSON 键。

能源假设：`annual_km` 为全年公里数；`consumption_per_100` 为每百公里升数或度数，须大于 0；`unit_price` 为对应元/升或元/度。混合充电模式改用 `home_price`、`fast_price`、`home_share`（家充比例 0–1）；与 `unit_price` 互斥。字段缺失不猜默认值，年度能耗金额保留 null。里程可以是 0，完整输入时年度能耗为 0；单价 0 可以表示用户明确给定免费能耗。脚本不验证车辆实际能耗或充电损耗。

## 计算范围

- 购车款项：`price + tax + insurance + plate + addons`。税费与保险仅按录入值，没有政策推算。
- 已知还款差额：`total_repay - principal`，两者都已知才能计算，总还款额小于本金拒绝。
- 录入贷款费用：`total_repay - principal + fees_outside_total`。只计未包含在总还款额中的另收费用，避免重复；费用未知时 value=null，known_subtotal 仅是已知小计。
- 购车款项加贷款费用：前两项相加；**不是贷款本金再次加一遍**。不包含能耗、未来保养、折旧、未录入费用或现金时间价值，不称为全生命周期成本。
- 年度能耗：里程÷100×百公里能耗×单价；混合模式先按家充比例加权单价。与购车款项和贷款费用分列，不当作车型或融资决策。

仅在两边该范围输入完整时，列示 `B − A`。两边都是贷款且本金不同时，贷款费用及含贷款费用总计不列同口径差额。两边年度里程不同时，不列同口径年度能耗差额。现金与贷款可以在完整购车款项加已录入贷款费用范围并排列示，但不代表资金安排建议。

本金相同也不表示所有合同条件相同：期限、付款时间、利率类型、提前还款条款等不在此计算模型内，不做 APR 或融资优劣判断。

## 输出

`comparison.json` 金额输出为十进制字符串或 null，避免其他软件的浮点表示误差：

- `input_sha256`：输入原文件的 SHA256。
- `quotes[].amounts/finance_inputs`：录入金额与保留的 null。
- `purchase/finance_fee/recorded_total/annual_energy`：`complete`、`value`、`known_subtotal`、`missing_fields`、`formula`、`input_pointers`。
- `finance_fee.repayment_difference`：可计算的还款差额，缺必要输入时为 null。
- `quotes[].provenance`：每个字段的输入 JSON Pointer、用户来源说明、是否存在于输入、录入值。是溯源定位，不是来源认证。
- `comparisons`：是否能列同范围差额、不能比较的原因、`right_minus_left`。不排序，不输出「更划算」。

`comparison.md`：并排表、缺项、计算式、逐字段来源定位。`comparison.csv`：四个范围的完整性、金额与差额；缺项单元格为空，同时 complete=false，不能当 0。用户标识在 CSV 里防止以公式前缀执行；金额仍按十进制数字输出。

## 合成样例的验收

1. `two-quotes-missing-fee.json`：A 费用 15000；B 已知还款差额 10500、另收费用 null；B 费用 value=null、complete=false，贷款费用不能比较。
2. `two-quotes-complete.json`：B 另收费用补为 6000；B 费用 16500、complete=true，B − A=1500。
3. 两个样例的年度能耗都为 1755 元；A 按家充 80% 混合单价，B 统一单价 0.78。全部是演示输入，不是市场报价、真实用户或政策依据。

人工核对源报价的费用范围，避免把总还款额内已含的服务费再次填进 `fees_outside_total`。脚本无法从合同文本自动判断包含关系，不能将此字段缺失默认为 0。
