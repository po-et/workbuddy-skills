---
name: api-contract-test
description: 接口契约回归测试、API 回归测试、接口冒烟、上线前接口验收、契约测试、JSON 字段断言、状态码校验、响应耗时门禁、把接口用例放进 CI 流水线。当用户说「写一组接口用例跑一遍看有没有回归」「上线前验一下这几个接口还对不对」「校验返回的 JSON 字段和状态码」「接口超过 800 毫秒就算失败」「用例里的 token 不想写死」时使用。附纯标准库脚本 scripts/api_contract_test.py，读 JSON 或 YAML 子集用例文件（base_url、method、path、headers、body、query 与 expect 断言），支持状态码、响应头、耗时上限，以及 $.data.id 这类 JSON 路径的 exists、equals、type、contains 断言，可顺序或并发执行；认证信息只从环境变量读取（用例里写 ${TOKEN} 引用，不落盘不打印），--json 出结构化结果，--strict 有失败退出码 1；另附 references/cases.example.json 模板。
author: Captain
version: 0.1.0
display_name: "接口契约回归"
display_name_en: "API Contract Test"
description_zh: "一条命令跑完一组接口用例：校验状态码、JSON 字段、响应头与耗时上限，支持并发；token 只从环境变量读取，--strict 可直接当 CI 门禁。"
description_en: "Run a suite of API cases in one command: assert status codes, JSON fields, response headers and latency budgets, with optional concurrency; tokens come only from env vars, and --strict works as a CI gate."
examples_zh:
  - "写一组接口用例跑一遍看有没有回归"
  - "上线前验一下这几个接口还对不对"
  - "校验返回的 JSON 字段和状态码，超时就算失败"
examples_en:
  - "Run these API cases and tell me what regressed"
  - "Verify these endpoints before we ship"
  - "Assert the response JSON fields, status code and latency"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# 接口契约回归

用一份可读的用例文件描述「接口应该长什么样」，一条命令跑完并给出通过/失败明细。适用于发布前冒烟、灰度后验收、依赖方接口变更后的回归、CI 里的接口门禁。纯 Python 标准库，不装 pytest、不装 requests。

## 用法

```bash
python3 scripts/api_contract_test.py cases.yaml
python3 scripts/api_contract_test.py cases.json --base-url https://staging.example.com
API_TOKEN=xxx python3 scripts/api_contract_test.py cases.json --concurrent 8 --strict
python3 scripts/api_contract_test.py cases.json --filter 用户 --json > result.json
```

参数：`--base-url` 覆盖用例里的基础地址（同一份用例跑多套环境）、`--filter` 按名字或路径挑用例、`--concurrent N` 并发、`--timeout-ms` 全局超时、`--json` 结构化输出、`--strict` 有失败或错误则退出码 1。

## 用例文件格式

JSON 与 YAML 子集都可以，字段完全一致；完整模板见 `references/cases.example.json`。

```yaml
base_url: https://api.example.com
timeout_ms: 5000
headers:
  Authorization: "Bearer ${API_TOKEN}"     # 只从环境变量取值
cases:
  - name: 用户详情字段契约
    method: GET
    path: /v1/users/1
    query:
      include: profile
    expect:
      status: 200                          # 也可以写成 [200, 201]
      max_ms: 800
      headers:
        Content-Type: json                 # 字符串即「包含」，也可写 {equals: ...}
      json:
        - path: $.data.id
          type: integer
        - path: $.data.roles[0]
          equals: admin
        - path: $.data.password
          exists: false
```

## 流程

1. 先写 3–5 条覆盖主链路的用例（登录态、正常查询、写入、越权、404），别一上来写全量。
2. 本地跑一遍确认全绿，再把用例文件提交进仓库，和接口代码放在一起演进。
3. 接口方改了契约时，脚本会精确指出是哪个字段、期望什么、实际什么；先判断是接口不该改，还是用例该跟着更新。
4. 进 CI：设置好 token 环境变量（GitHub Actions 用 secrets，GitLab CI 用 masked variable），命令加 `--strict`。
5. 灰度或多环境验收时用 `--base-url` 把同一份用例分别指向预发和生产，两次 `--json` 结果对比差异。

## 断言与输出一览

| 位置 | 断言 | 说明 |
|---|---|---|
| expect.status | 整数或整数数组 | 状态码，多值表示任一命中即可 |
| expect.max_ms | 数字 | 单条请求耗时上限，超过即失败 |
| expect.headers | 映射 | 字符串为「包含」，对象支持 equals 与 contains |
| expect.json | 列表 | 每项 `path` 加 exists / equals / type / contains |
| expect.body_contains | 字符串 | 非 JSON 响应时的兜底断言 |

`type` 支持 string、number、integer、boolean、array、object、null。`contains` 对字符串是子串、对数组是成员、对对象是键。输出每条用例的状态码、耗时与失败原因，末尾给出通过/失败/错误计数与 p50、最大耗时。

## 边界与常见问题

- JSON 路径只实现最小子集：点号取字段、`[i]` 取下标、`$['带空格的键']`；不支持通配符、过滤表达式、递归下降 `..`。要复杂匹配就拆成多条断言。
- YAML 只解析常用子集（映射、列表、标量、行内注释、引号字符串），不支持锚点、多文档、`|` 与 `>` 块标量。拿不准就用 JSON，字段完全一样。
- 用例里禁止写死密钥：只认 `${VAR}` 形式从环境变量取值，变量缺失时该用例标为「错误」并提示变量名；脚本不会把请求头内容打印出来。
- 不做登录编排、不做用例间取值传递（上一条的 id 喂给下一条），需要这类串联时请准备固定测试数据。
- 自签名证书的站点会因证书校验失败而报错，这是有意为之，不提供跳过校验的开关。
- `--concurrent` 只影响发请求的并发度，不改变输出顺序；对写接口做并发前先确认服务端幂等。
