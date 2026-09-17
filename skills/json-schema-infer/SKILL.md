---
name: json-schema-infer
description: 从样例 JSON 推断 JSON Schema、根据接口返回生成 schema、给没有文档的 API 补契约、JSONL 事件样本推断结构、识别可选字段与可空字段、枚举候选与格式（日期时间/邮箱/UUID/URL）、生成校验用 schema。当用户说「根据这几条返回帮我生成 JSON Schema」「这个接口没文档，从样例推一下结构」「哪些字段是可选的哪些可能为 null」「给这批事件数据生成校验 schema」时使用。附纯标准库脚本 scripts/schema_infer.py：合并多条样例（数组或 JSONL），输出 draft 2020-12 schema，含 required（可调阈值）、可空类型、嵌套对象与数组、枚举候选、format 识别，可选 minimum/maximum、maxLength、examples、additionalProperties=false 严格模式。
author: Captain
version: 0.1.0
display_name: "JSON Schema 推断"
display_name_en: "JSON Schema Infer"
description_zh: "把几条样例 JSON 变成一份可用的 JSON Schema（draft 2020-12）：合并多样本识别必填/可选/可空，嵌套对象与数组，枚举候选与常见 format，可选数值范围与长度；纯 Python 标准库。"
description_en: "Turn a few JSON samples into a usable JSON Schema (draft 2020-12): merge samples to detect required/optional/nullable, nested objects and arrays, enum candidates and common formats, optional numeric ranges and lengths; pure Python stdlib."
examples_zh:
  - "根据 samples.json 里的三条订单生成 JSON Schema"
  - "这个 JSONL 事件流里每个字段的类型和可选性是什么"
  - "生成一份严格的 schema（不允许额外字段）用于入参校验"
examples_en:
  - "Generate a JSON Schema from the three orders in samples.json"
  - "What are the types and optionality of fields in this JSONL event stream?"
  - "Produce a strict schema (no extra fields) for request validation"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# JSON Schema 推断

没有文档的接口、第三方回调、日志事件——先抓几条样例，推出一份 schema，再人工修正成契约。样例越多，required / 可空 / 枚举的判断越准。

## 用法

```bash
python3 scripts/schema_infer.py samples.json --title Order            # 数组或单个对象
python3 scripts/schema_infer.py events.jsonl --jsonl --required-threshold 0.95
curl -s https://api.example.com/orders/1 | python3 scripts/schema_infer.py - --strict --ranges --lengths
```

## 推断规则

- **类型**：按样例合并；整数与小数混合归为 number；出现 null 则类型带 `null`。
- **required**：字段出现比例 ≥ `--required-threshold`（默认 1.0，即每条样例都有）。
- **枚举**：字符串不同取值 ≤ `--enum-max`（默认 6）、样本 ≥ `--enum-min`（默认 3）、长度 ≤ 40 时给出 enum 候选。
- **format**：date-time、date、uuid、email、uri、ipv4（全部样例都匹配才标注）。
- **可选项**：`--strict` 输出 additionalProperties: false；`--ranges` 输出 minimum/maximum；`--lengths` 输出 maxLength；`--examples` 给字符串示例。

## 流程

1. 收集 5–20 条覆盖不同分支的样例（成功/失败、有/无可选字段、边界值）；样例太少会把偶然当规律。
2. 跑脚本，逐字段核对：枚举候选是不是真枚举（可能只是样本少）；minimum/maximum 只是样本范围，不是业务约束；`required` 里出现的字段是否真的保证存在。
3. 补上 description、业务约束（pattern、正整数、最大长度）与 `$id`，去掉 `x-inferred-from`。
4. 用作校验：接口入参用 `--strict`；解析第三方数据用宽松版（允许额外字段），避免对方加字段就崩。

## 边界

- 推断的是「样例长什么样」，不是「契约允许什么」；上线前必须人工审核。
- 不推断 oneOf/anyOf：同一字段多类型会输出类型数组。
- 空数组学不到 items；空对象学不到 properties。
