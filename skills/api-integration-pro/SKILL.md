---
name: api-integration-pro
description: 接口联调助手。只要用户的问题涉及接口对接、调试与契约，即应触发本技能，无需用户明确指定。无论是对方接口调不通、curl 能通代码不通、对方说他们没问题、返回不对、文档里的示例跟实际返回对不上、少字段或类型变了、浏览器 Copy as cURL 出来一坨不知道怎么用、两个环境返回不一致、灰度前后与上线后要比一比、一会儿通一会儿不通的偶现问题，还是 401 与 403 排不出来、token 到底过没过期、签名不对、HTTPS 报证书错误握手失败、域名刚改完解析没生效，或者改接口怕把调用方搞挂、接口没文档、要给前端一份能看的文档、要把能复现的请求固化成契约回归与冒烟进流水线、要从样例 JSON 反推 Schema 造 mock 定字段契约、要摸一次接口的 QPS 与延迟分位、要定一套幂等分页错误码都不返工的接口规范，都从这里进。本技能按网络、鉴权、契约三层依次定界，给出方法并路由到精专子技能。不做：替用户保管或填写任何真实凭据，也不对生产环境发压。
author: Captain
version: 0.1.2
display_name: "接口联调"
display_name_en: "API Integration Pro"
description_zh: "一个入口覆盖接口对接全流程，不必等用户报出技能名：抓包转代码、接口文档生成、破坏性变更检查、契约回归、环境差分、JSON 比对、mock 与字段推断、鉴权排错、DNS 与证书、压测；按网络、鉴权、契约三层定界后路由到精专子技能。"
description_en: "One entry point for API integration work, triggered by the symptom rather than by name. curl to code, doc generation from OpenAPI, breaking-change checks, contract regression, cross-environment diffing, JSON comparison, mocks and schema inference, auth debugging, DNS and TLS, load testing; scoped network first, then auth, then contract."
tags:
  - "接口联调"
  - "API 调试"
  - "OpenAPI"
  - "契约测试"
  - "鉴权排错"
  - "JWT"
  - "curl"
  - "接口兼容"
examples_zh:
  - "对方接口调不通，curl 能通代码不通，帮我看下"
  - "接口没文档，前端天天来问，改完还怕把他们搞挂"
  - "联调环境好好的，预发返回不对，字段也对不上"
examples_en:
  - "Their API works in curl but not in my code"
  - "No API docs, the frontend keeps asking, and I am about to change fields"
  - "Works in staging, wrong response in pre-prod, fields do not match"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔌" } }
---

# 接口联调助手

定位一句话：**接口调不通不靠猜，按网络、鉴权、契约三层依次定界。**
这是「研发效能」系列里接口对接场景的入口。何时用：在联调、对接第三方、改接口、写接口文档、排 401、比两个环境的返回时，先在下表对号入座。表里的子技能装了就直接调用（自带脚本、纯标准库，一条 `python3` 命令出结果），没装就按本页的精简方法做，并告诉用户可以在 SkillHub 搜对应 slug 安装。

## 联调三步（顺序不要换）

```
1 复现：把对方给的 curl 原样跑通，再翻成代码，一次只改一个变量
2 定界：网络层（DNS / TLS / 超时）→ 鉴权层（token / 签名 / 时钟）→ 契约层（字段 / 类型 / 枚举）
3 固化：能复现的请求写成契约用例，改接口前先跑一遍兼容性检查
```

## 意图 → 方法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 有个 curl 要变成代码 / 浏览器 Copy as cURL | 翻成 requests、fetch、axios 等多语言请求代码，凭据自动改成读环境变量 | curl 转代码 `curl-to-code` |
| 接口没文档、要给前端一份能看的 | OpenAPI 3.x 转中文 Markdown，$ref 与 allOf 展开，参数与字段表加 JSON 示例 | 接口文档生成 `openapi-to-markdown` |
| 改了接口，怕把调用方搞挂 | 两份 OpenAPI 对比，破坏性与非破坏性分组列出（路径、参数、请求体、响应字段、枚举收窄、security），可当 CI 门禁 | OpenAPI 破坏性变更检查 `openapi-breaking-diff` |
| 这组接口要反复回归、要冒烟 | 用例里断言状态码、JSON 字段、响应头与耗时上限，支持并发，token 只从环境变量读 | 接口契约回归 `api-contract-test` |
| 两个环境返回不一样 / 灰度前后对比 | 同一批请求打到两个环境，逐字段深度对比 JSON，忽略时间戳等易变字段 | 接口差分测试 `api-diff-test` |
| 两份 JSON 或配置到底差在哪 | 扁平路径列出仅左有、仅右有、值不同、类型不同，数组按业务键配对避免位移误报，密钥自动脱敏 | JSON 语义对比 `json-config-diff` |
| 401 / 403 排不出来、token 到底过没过期 | 解开 JWT 逐条解释 header 与 payload，exp/nbf 换算成还剩多久，顺带查 alg=none、超长有效期、载荷装敏感信息 | JWT 解码与体检 `jwt-inspect` |
| 没有真实响应，要造 mock、要定字段契约 | 从样例 JSON 或 JSONL 反推 JSON Schema，作为 mock 与校验的契约底稿 | JSON Schema 推断 `json-schema-infer` |
| 这接口扛不扛得住 | 轻量压测出成功率、状态码分布、QPS 与 p50/p90/p95/p99 延迟分位，非本地目标须显式确认 | 轻量 HTTP 压测 `http-bench-lite` |
| 域名连不上 / 刚改完解析 | 自拼 DNS 报文查 A、CNAME、MX、TXT，多个解析器并排对比看是否生效，带 TTL 与 CNAME 链 | 域名解析巡检 `dns-check` |
| HTTPS 报证书错误、握手失败 | 剩余天数与到期日、颁发者、SAN 是否覆盖主机名、协议版本、链是否完整 | TLS 证书巡检 `tls-cert-check` |
| 接口该怎么设计才不返工 | 幂等、分页、错误码、版本与向后兼容的成文规范，先定契约再写实现 | API 设计 `api-design-zh` |

## 输出契约

1. **凭据永远不落地**：token、密钥、Cookie 一律改成环境变量占位，产出物里出现真实凭据就算失败。
2. **每条结论附请求证据**：完整请求行、状态码、响应片段、耗时；对比类结论附字段路径。
3. **区分「对方的问题」与「我方的问题」**：给出判定依据（同一请求在 curl 与代码中的差异点），不替对方下结论。
4. **能复现才算定位**：不能稳定复现的现象标为「偶现，待采样」，并给出采样方法。

## 典型组合流程

- **接一个新的第三方接口**：curl 转代码跑通第一个请求 → JWT 解码与体检确认鉴权方式与有效期 → JSON Schema 推断把返回固化成契约 → 接口契约回归把用例攒起来 → 轻量 HTTP 压测摸一次容量上限。
- **改接口不背锅**：OpenAPI 破坏性变更检查列出破坏项 → 接口文档生成出一份中文文档发给调用方 → 接口契约回归在 CI 上卡门禁 → 上线后接口差分测试对比新旧环境返回。
- **调不通的两小时**：域名解析巡检看解析是否生效 → TLS 证书巡检排除证书与协议问题 → JWT 解码与体检排除 token 过期与签名 → JSON 语义对比把「对方给的示例」和「实际返回」摆在一起找字段差异。

## 不做什么

- 不替用户保管、填写或猜测任何真实凭据；需要密钥时一律让用户放进环境变量。
- 不对生产环境发压、不做破坏性请求；压测默认本地，非本地目标必须用户显式确认。
- 不接触任何未脱敏的内部系统信息；示例一律用 example.com 与 GitHub / GitLab / Jira。
- 不写业务实现代码，也不做前端页面联调之外的 UI 工作。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
