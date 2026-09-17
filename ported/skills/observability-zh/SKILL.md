---
name: observability-zh
description: 可观测性与埋点、结构化日志、RED/USE 指标、分布式追踪、告警与 runbook。当用户说「怎么打日志」「加监控指标」「接入 OpenTelemetry」「告警怎么配才不吵」「线上出问题看不出发生了什么」「写 runbook」「上线前埋点该埋什么」时使用。流程：先写下值班会问的 2–4 个问题 → 为每个问题选信号（指标说"有没有问题"、追踪说"在哪"、日志说"为什么"）→ 结构化日志（事件名 + 字段，级别一致，关联 ID 必须，多入口写同一日志要标入口，绝不记密钥/PII）→ RED/USE 指标（标签低基数、只看百分位不看平均）→ OpenTelemetry 追踪 → 只对用户感受到的症状告警、每条可行动、链 runbook、只分 page/ticket 两级 → 验证埋点本身。改编自 addyosmani/agent-skills 的 observability-and-instrumentation（MIT）。
author: Captain
version: 0.1.0
display_name: "可观测性与埋点"
display_name_en: "Observability & Instrumentation (zh)"
description_zh: "先写值班会问的问题再埋点：结构化日志 + 关联 ID + 入口标识、RED/USE 指标与低基数标签、OpenTelemetry 追踪、只对症状告警并链 runbook、最后验证埋点本身。"
description_en: "Write the on-call questions first, then instrument: structured logs with correlation ids and entry-point fields, RED/USE metrics with bounded labels, OpenTelemetry traces, symptom-based alerts with runbooks, and verify the telemetry itself."
examples_zh:
  - "给支付重试功能设计日志、指标和告警"
  - "我们的告警天天响没人理，帮我重新设计"
  - "接入 OpenTelemetry 追踪，最少要改什么"
examples_en:
  - "Design logs, metrics and alerts for the payment retry feature"
  - "Our alerts fire daily and get ignored, redesign them"
  - "Add OpenTelemetry tracing with minimal changes"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "📡" } }
---

# 可观测性与埋点

看不见的代码没法运维。可观测性 = 从外部用代码发出的遥测回答"系统在干什么、为什么"。埋点不是上线后再补的东西，它和测试一样与功能一起写：功能没带遥测上线，第一个用户报 bug 就变成考古而不是一次查询。
用于任何跑在生产的功能、新服务/端点/后台任务/外部集成、事故排查太慢、配置或评审告警、评审含 I/O/重试/队列/跨服务调用的 PR。不用于此刻正在发生的故障（用「系统化排错」/「线上排查简报」）、优化已测量的慢（「性能优化」）、上线清单（「上线发布」）。

## 流程

### 1. 埋点前先定义"正常"
没有问题的遥测是噪音。写下值班工程师会问的 2–4 个问题："首次支付成功率 vs 重试后成功率？永久失败的原因分布（供应商错误/超时/校验）？供应商比平时慢吗？"→ 后面每个信号都必须回答其中一个。写不出问题就不要埋——你会什么都记、什么都学不到。

### 2. 每个问题选对信号
| 信号 | 回答 | 成本 |
|---|---|---|
| 结构化日志 | 这个具体案例发生了什么 | 按事件计，随流量增长 |
| 指标 | 总体上多常、多快 | 每序列固定，查询便宜 |
| 追踪 | 时间花在跨服务的哪一段 | 按请求计，通常采样 |
经验法则：指标告诉你**有**问题，追踪告诉你在**哪**，日志告诉你**为什么**。

### 3. 结构化日志
记事件不记散文：稳定的事件名 + 机器可读字段（`payment_failed` + paymentId/provider/errorCode/attempt），而不是字符串拼接。级别一致：error 破坏了不变量需要人处理；warn 降级但已处理（重试成功、走了兜底）；info 重要业务事件；debug 诊断细节，生产默认关。
**关联 ID 必须**：在系统边界生成或接受请求 ID，附到每条日志、每个 span、每个出站调用；没有它无法从交错的日志里还原一个请求。
**多个入口写同一份日志时标入口**：同一个任务被调度器、重放接口、手工 CLI 触发，日志行长得一样；在运行开始处与关联 ID 一起打上 `entryPoint`（scheduler / replay_endpoint / cli），并随关联 ID 一起跨越队列元数据、HTTP 头等边界——下游自己猜的入口只是提示不是归因。
**绝不记密钥、令牌、密码、完整 PII**：白名单字段，不记整个请求体。

### 4. 指标
请求型服务每个端点和每个外部依赖都埋 **RED**：速率、错误率、时延（直方图，不是平均）；资源（队列、连接池、主机）用 **USE**：利用率、饱和度、错误。
**基数是失败模式**：每个标签组合一条时间序列。标签只能来自小而固定的集合（路由模板、状态类别 `5xx`、供应商名）；用户 ID、原始 URL、错误文本、请求 ID 永远不能当标签——它们属于日志和追踪。平均值永远不看，只看 p50/p95/p99：平均掩盖了过得很惨的那 1%。

### 5. 分布式追踪
用 OpenTelemetry（厂商中立），自动埋点几乎零代码覆盖 HTTP、gRPC、常见数据库客户端；只在有意义的内部单元（`applyDiscounts`、`chargeProvider`）加手工 span 并附值班会筛选的属性；上下文必须跨过每个异步边界（HTTP 头、队列消息元数据），否则追踪在缝隙处死掉；默认低比例头采样，后端支持尾采样就保留 100% 的错误。

### 6. 告警
对**用户感受到的症状**告警：错误率 > 1% 持续 5 分钟、p99 > 2s、队列积压 > 10 分钟 → 该 page；CPU 85%、某 pod 重启、磁盘 70% → 看板，不 page。基于原因的告警在没事时响、在你没预料的故障时沉默。
每条告警：**可行动**（响应是"忽略，会自愈"就删掉）；**链 runbook**（哪怕三行：意味着什么、第一条要跑的查询、升级给谁）；阈值与持续时间有 SLO 或历史数据依据；**只分两级**：page（用户可感，立刻处理）和 ticket（降级，本周处理），第三级会变成噪音。
Runbook 最小三行：`意味着 / 先查 / 升级给`，存 `docs/runbooks/` 按告警命名；只在第一条检查不足以决定时加步骤；每次用过的事故结案时更新它。

### 7. 验证遥测本身
埋点是代码，也会错。完成前：预发强制触发错误 → 按 requestId 能在日志找到且字段结构化（不是 `[object Object]`）；打测试流量 → 指标序列带预期标签且数值合理；在追踪 UI 里跟一个请求跨服务走通无断 span；每条新告警临时降阈值触发一次 → 到达正确渠道、runbook 链接可用。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "能跑了再加日志" | "之后"会变成"第一次事故之后"，那是发现自己瞎了最贵的时刻 |
| "日志越多越可观测" | 非结构化噪音让事故更慢；三条可查询事件胜过三百行散文 |
| "先用 console.log" | 不能过滤、关联、告警；结构化 logger 只多花五分钟 |
| "出事看看看板就行" | 没有问题驱动的看板给你看一切，除了答案 |
| "重要的都告警，以后再调" | 吵的寻呼机训练人忽略它；调整永远不会发生 |
| "用户 ID 当标签方便排查" | 也会让指标后端倒下；高基数属于日志和追踪 |
| "两个服务用不着追踪" | 两个服务就已经有日志答不了的跨服务时延问题 |

## 红灯
带重试/队列/外部调用的 PR 零新遥测；字符串拼接的日志；没有关联 ID；多入口写一份日志却没有入口字段；用户 ID/原始 URL/错误文本当指标标签；时延只有平均；每天响却被直接确认的告警；对原因（CPU、内存）page 人而用户可见错误率没人管；日志里有密钥或整个请求体；"我机器上好的"是生产健康的唯一证据。

## 验收
- [ ] 值班问题已写下且每个信号对应其一　- [ ] 日志全部结构化、事件名稳定、每行有关联 ID　- [ ] 多入口日志有入口字段且随关联 ID 传播
- [ ] 抽查实际日志无密钥/PII　- [ ] 每个新端点与外部依赖有 RED 指标且标签有界　- [ ] 时延是直方图、p95/p99 可查
- [ ] 一个请求能在追踪 UI 端到端跟完　- [ ] 每条新告警基于症状、链 runbook、测发过一次　- [ ] 预发注入的故障仅凭遥测就能定位

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `observability-and-instrumentation`（MIT）。改动见 ATTRIBUTION.md。
