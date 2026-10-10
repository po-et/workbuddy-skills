---
name: api-diff
description: 接口差分测试、两个环境响应对比、上线前后接口回归、灰度 vs 线上对比。当用户说「对比一下预发和线上这批接口的返回」「新版本接口有没有改坏」「同一个请求打两个环境看差异」「接口回归测试」「A/B 环境响应 diff」「重构后接口输出是否一致」「迁移后数据对不对」时使用。脚本把一份用例（方法、路径、头、体）同时打到环境 A 与 B，逐字段深度对比 JSON（可忽略时间戳、trace id 等易变字段），报告状态码、耗时与差异路径；凭证只从环境变量读，不写入用例文件。
author: Captain
version: 0.1.1
display_name: "接口差分测试"
display_name_en: "API Diff Testing"
description_zh: "同一批请求打到两个环境，逐字段深度对比 JSON 响应（可忽略易变字段），输出状态码、耗时与差异路径表，用于发布前后回归。"
description_en: "Send the same requests to two environments and deep-diff the JSON responses (with ignorable volatile fields), reporting status, latency and diff paths for release regression."
examples_zh:
  - "把这 20 个接口分别打到预发和线上，看返回有没有差异"
  - "重构后的服务和老服务响应是否一致，忽略 updated_at"
  - "灰度机器和全量机器的接口输出对比"
examples_en:
  - "Hit these 20 endpoints on staging and prod and diff the responses"
  - "Does the refactored service return the same as the old one, ignoring updated_at"
  - "Compare canary vs full-fleet API output"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔁" } }
---

# 接口差分测试

同样的请求，两个环境，逐字段比。输出行为变化清单，再按接口契约判断哪些变化需要修复。

## 先跑一个完整本地案例

```bash
python3 {baseDir}/examples/local_order_demo.py
```

它启动两台回环 HTTP 服务，实际发送 GET，先发现合成订单的金额、数量、布尔类型和缺失字段四处回归，再修正响应并重新请求，分别生成失败与通过报告。输入、差异路径、退出码和 SHA256 都可检查；不连接外部端点、不读取认证头。详见 [本地订单验收案例](examples/local-order-acceptance.md)。

## 核心原则

1. **认证头只从环境变量 `API_DIFF_HEADERS` 读。** 用例文件的 Authorization、Cookie、带 token/secret/api-key 的常见头会被拒绝；自定义凭证名称仍需人工检查。报告不会写入请求头，并遮蔽响应中回显的这些环境认证值；分享报告前仍需检查响应里的其他敏感业务字段。
2. **执行范围可核对。** 默认只允许回环地址的 GET/HEAD，不跟随重定向、不使用系统代理。核对外部 A/B 端点且任务已获授权后加 `--allow-external`；其他方法需用户已授权使用测试数据，再加 `--allow-write`。GET/HEAD 是方法限制，仍需核对接口实现是否只读。
3. **忽略要有理由。** 按完整字段名匹配正则，逐条列出实际忽略路径；`id` 不会匹配 `order_id`。常见金额/数量字段及其父级子树受保护，详见下方边界。
4. **差异不是错误。** 报告只说"不一样"，是不是 bug 由人判断；但状态码不同一定要置顶。

## 执行流程

### 第 1 步：准备用例

`cases.json`（示例见 `references/cases.example.json`）：

```json
[{"name": "订单详情", "method": "GET", "path": "/api/orders/DEMO-001"},
 {"name": "搜索", "method": "GET", "path": "/api/search?q=synthetic"},
 {"name": "路径不同", "method": "GET", "path": "/v1/x", "path_b": "/v2/x"}]
```

用例来源：接口文档、网关访问日志里 QPS 最高的前 20 条、上次故障涉及的接口。

### 第 2 步：跑对比

```bash
python3 {baseDir}/scripts/api_diff.py --a http://127.0.0.1:8001 --b http://127.0.0.1:8002 \
  --cases cases.json --ignore "updated_at,request_id,trace_id,^ts$" --md out/api-diff.md --out out/api-diff.json
```

这条命令适用于已启动的本地服务；首次试用直接执行上方演示脚本即可，无需先搭环境。

`--ignore` 是字段名全匹配正则（逗号分隔）。退出码 **0**：所有用例为 2xx 且响应一致；**1**：响应/状态差异、同码非 2xx、网络或解析失败；**2**：输入或执行范围无效、忽略规则命中保护字段。两端同为 500 不算通过；HEAD/204/205 无响应体可正常比较。JSON 布尔值与数字区分，`null` 与缺失区分，小数用 Decimal 精确比较；文本按完整响应字节比较。

如需访问已核对的外部环境，在命令中明确添加 `--allow-external`。认证头从环境变量注入，例如 `API_DIFF_HEADERS` 内容为 `{"Authorization":"Bearer <token>"}`，不要把真实值写入用例或可分享命令记录。

### 第 3 步：解读（这一步由你做）

- 状态码不同 → 最高优先级，逐条说明。
- 差异按路径归类：字段缺失 / 新增 / 值不同 / 数组长度不同；同一根路径下的多条合并说。
- 判断哪些是**预期差异**（新版本新增字段）与**可疑差异**（金额、状态、枚举值变化）。
- 耗时差异 > 2 倍的接口单独列出。

### 第 4 步：交付

差异表 + 三类结论：需要修的、预期内的、需要确认的；并把本次的 `--ignore` 规则写进报告以便复现。

## 输出契约

```
# 接口差分：A ↔ B
- 用例数 / 一致 / 有差异 / 状态码不同 / 失败 / 同码非 2xx / 拒绝的忽略规则
| 用例 | 方法 路径 | 结论 | A 状态/耗时 | B 状态/耗时 | 差异数 |
## <用例名>：逐路径差异
## 结论：需修 / 预期 / 待确认
```

## 常见问题

**接口有分页或随机排序？** 固定 `sort`/`page_size`；数组按位置比较，忽略排序字段不会重排数组。
**响应不是 JSON？** 按完整字节的 SHA256 比较，报告只展示有限预览，不会忽略第 4000 字符后的变化。
**要比 gRPC？** 先用网关或 grpcurl 转成 JSON 再比。
**能忽略金额或数量吗？** 脚本将字段名按下划线、分隔符和 camelCase 拆词，保护 `amount/quantity/qty/count/price/total/balance`；忽略父对象时也检查这些字段。命中后保留差异、报告拒绝路径并退出 2。这个命名规则不能识别 `money`、`库存` 或所有业务语义，仍需按实际接口契约复核。
**报告会截断吗？** 每个用例最多收集 200 条差异，JSON 留前 50 条，Markdown 展示前 30 条，并有截断提示；不能把显示数量当成全部差异数。响应本身会完整读入内存，适合普通 JSON 接口，不用于流式或巨型响应。
