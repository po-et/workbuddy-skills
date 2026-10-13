# 输入与输出契约

比较器只读取两个 UTF-8 JSONL 文件（接受 UTF-8 BOM），不发网络请求、不运行模型，也不打开 `evidence` 指向的文件。空白行忽略；每份文件须至少有一条案例。

## 每行字段

| 字段 | 类型 | 要求 |
|---|---|---|
| `case_id` | 字符串 | 必填、非空、两侧一致才能配对；不允许首尾空白或控制字符；每份文件内部唯一 |
| `passed` | JSON 布尔值 | 必填，只能是 `true` / `false`；`0`、`1`、字符串和 `null` 均无效 |
| `evidence` | 字符串 | 建议记录输出位置、测试记录或判定摘要；缺字段、空字符串、全空白均记为缺少证据；其他类型无效 |
| `latency_ms` | JSON 数字 | 可选，有限且非负；不存在表示未知，`0` 是真实记录；`null`、字符串和布尔值无效 |
| `cost` | JSON 数字 | 可选，有限且非负；单位和计算口径由用户记录说明，两侧须一致；未知则省略 |

未知字段会拒绝，避免把拼错的指标静默丢弃。重复 JSON 键、重复案例 ID、NaN/Infinity、浮点溢出、负指标、坏 JSON、非对象行和缺必填字段会报文件与行号并退出 `2`。先将执行器的额外数据映射到这个契约，原始执行输出另行保存。

```json
{"case_id":"tool-schema","passed":true,"evidence":"synthetic: schema assertion passed","latency_ms":160,"cost":0.001}
```

评测判据、模型和版本、温度、工具环境、重复次数、耗时定义、成本单位属于记录来源的说明。比较前先确保口径相同；脚本无法从布尔值证明这些条件一致。多次运行可按 `case_id` 纳入明确的重复编号，例如 `tool-schema-run-01`，避免选择性保留成功次数。

## 运行

在本技能目录内先用合成样例验证输出：

```bash
python3 scripts/agent_eval_compare.py --before assets/before.jsonl --after assets/after.jsonl --out-dir out/agent-eval-demo
```

实际使用把两个输入替换为执行器导出的文件。输出目录必须不存在，不覆盖旧报告；输入文件原样保留。生成 `comparison.json` 与 `comparison.md`，其中包含两份输入文件的 SHA-256 指纹。

| 退出码 | 含义 |
|---|---|
| `0` | 同一案例集合，所有案例两侧有证据，且记录中无 `true → false`；仍可能存在未通过案例 |
| `1` | 有 `true → false`，或两侧案例不一致，或任一侧缺少证据；正常生成报告 |
| `2` | 输入无效或读取/写入错误；在输入无效时不创建输出目录 |

## 报告字段

- `comparison_complete`：案例集合完全相同且两侧所有案例有非空证据。证据存在不等于证据经验证。
- `paired.recorded_false_to_true`：布尔记录中出现的新增通过，包括缺证据的记录。`newly_passed_with_both_evidence` 只列双方都有证据的部分。
- `paired.regressions_true_to_false`：记录中的所有通过转失败，即使证据缺失也列出并使退出码为 `1`。
- `missing`：缺少改前/改后案例、缺少证据的 ID；不把新增案例当作新增通过，不把删去的失败案例当改进。
- `pass_gain_supported_for_recorded_case_set`：仅当比较完整、无回退且成对通过数增加时为 `true`。它只支持描述本组已记录案例，不证明整体模型能力或真实用户效果。
- `metrics`：每侧记录数、双方都有该指标的成对案例 ID、缺失 ID，以及仅针对这些指标对的前后均值和差值。均值与差值用十进制字符串输出（28 位有效数计算），没有指标对时为 `null`。任何缺失指标都不填 `0`。
- `whole_comparison_metric_coverage_complete`：比较本身完整且所有成对案例都有该指标时为 `true`。指标不齐时不能声称整体更快或更省；完整覆盖也只支持这组运行记录的观察。
- `cases`：两侧案例并集和原始字段，按 ID 排序；Markdown 中对记录文本转义，证据字符串不作为指令执行。

附带样例是作者构造的三条记录：通过数从 2 增至 3，耗时和成本都只有 2/3 成对覆盖。其用途是验证配对、计数与缺失处理，不是 WorkBuddy 客户端实测或用户采用证据。
