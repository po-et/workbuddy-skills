---
name: api-diff
description: 接口差分测试、两个环境响应对比、上线前后接口回归、灰度 vs 线上对比。当用户说「对比一下预发和线上这批接口的返回」「新版本接口有没有改坏」「同一个请求打两个环境看差异」「接口回归测试」「A/B 环境响应 diff」「重构后接口输出是否一致」「迁移后数据对不对」时使用。脚本把一份用例（方法、路径、头、体）同时打到环境 A 与 B，逐字段深度对比 JSON（可忽略时间戳、trace id 等易变字段），报告状态码、耗时与差异路径；凭证只从环境变量读，不写入用例文件。
author: Captain
version: 0.1.0
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

上线前后最便宜的回归：**同样的请求，两个环境，逐字段比**。不需要写断言，差异本身就是问题清单。

## 核心原则

1. **凭证不落盘。** 认证头只从环境变量 `API_DIFF_HEADERS` 读；用例文件可以进仓库，token 不能。
2. **只打只读接口。** 默认 GET；要对比写接口必须用测试数据且用户明确同意。
3. **忽略要有理由。** 每个被忽略的字段（时间戳、请求 id）在报告里列出，别把真差异也忽略掉。
4. **差异不是错误。** 报告只说"不一样"，是不是 bug 由人判断；但状态码不同一定要置顶。

## 执行流程

### 第 1 步：准备用例

`cases.json`（示例见 `references/cases.example.json`）：

```json
[{"name": "订单详情", "method": "GET", "path": "/api/orders/1"},
 {"name": "搜索", "method": "POST", "path": "/api/search", "body": {"q": "test"}},
 {"name": "路径不同", "method": "GET", "path": "/v1/x", "path_b": "/v2/x"}]
```

用例来源：接口文档、网关访问日志里 QPS 最高的前 20 条、上次故障涉及的接口。

### 第 2 步：跑对比

```bash
API_DIFF_HEADERS='{"Authorization":"Bearer <token>"}' \
python3 {baseDir}/scripts/api_diff.py --a https://staging.example.com --b https://prod.example.com \
  --cases cases.json --ignore "updated_at,request_id,trace_id,^ts$" --md out/api-diff.md --out out/api-diff.json
```

`--ignore` 是字段名正则（逗号分隔）；退出码 0 表示全部一致。

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
- 用例数 / 一致 / 有差异 / 状态码不同 / 失败；忽略字段
| 用例 | 方法 路径 | 结论 | A 状态/耗时 | B 状态/耗时 | 差异数 |
## <用例名>：逐路径差异
## 结论：需修 / 预期 / 待确认
```

## 常见问题

**接口有分页或随机排序？** 用 `--ignore` 忽略排序字段，或在用例里固定 `sort`/`page_size` 参数。
**响应不是 JSON？** 按文本比较前 4000 字符。
**要比 gRPC？** 先用网关或 grpcurl 转成 JSON 再比。
