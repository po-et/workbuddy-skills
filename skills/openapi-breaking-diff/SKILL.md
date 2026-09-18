---
name: openapi-breaking-diff
description: OpenAPI / Swagger 规范对比、接口破坏性变更检查、API 兼容性检查、发布前确认接口改动会不会影响调用方、API 变更日志生成、CI 里拦截不兼容的接口变更。当用户说「这次接口改动有没有 breaking change」「对比两个版本的 openapi.json」「新版 API 兼容旧客户端吗」「帮我列一下接口变更通知调用方」「把 API 兼容性检查加进 CI」时使用。附纯标准库脚本 scripts/openapi_diff.py（YAML 需可选的 PyYAML）：解析本地 $ref、allOf、嵌套对象与数组，识别删除接口、删除/新增必填参数、参数类型与枚举收窄、请求体变必填、请求字段变必填/改类型/枚举收窄、响应 2xx 移除、响应字段移除/改类型/变可空/不再必返、响应字段枚举收窄（response-enum-narrowed，含数组元素与嵌套对象字段）、content-type 移除、全局 security 变化；新增接口/可选参数/响应字段归为非破坏性；支持 --json 与 --strict 门禁。
author: Captain
version: 0.1.1
display_name: "OpenAPI 破坏性变更检查"
display_name_en: "OpenAPI Breaking Change Diff"
description_zh: "对比两个 OpenAPI 3.x 规范，把变更分成「破坏性」与「非破坏性」两组逐条列出（接口、参数、请求体、响应字段、请求/响应两侧的枚举收窄、content-type、security），可作 CI 门禁；纯 Python 标准库。"
description_en: "Diff two OpenAPI 3.x specs and list every change as breaking or non-breaking (operations, params, request bodies, response fields, enum narrowing on both request and response sides, content types, security); usable as a CI gate; pure Python stdlib."
examples_zh:
  - "对比 openapi-v1.json 和 openapi-v2.json，列出破坏性变更"
  - "这次 PR 改了接口定义，会不会影响老客户端"
  - "在 CI 里跑 API 兼容性检查，有 breaking 就失败"
examples_en:
  - "Diff openapi-v1.json vs openapi-v2.json for breaking changes"
  - "Will this PR's API changes break old clients?"
  - "Run the API compatibility check in CI, fail on breaking"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔀" } }
---

# OpenAPI 破坏性变更检查

对比新旧两份 OpenAPI 3.x 规范，把每一处变更归入**破坏性**（老客户端会挂）或**非破坏性**（只增不改），输出逐条清单。发布前跑一遍，破坏性变更走版本升级或兼容期。

## 何时用

- PR 改了接口定义，要在合并前知道会不会打挂老客户端。
- 发版前生成一份「破坏性 / 非破坏性」清单，破坏性的走版本升级或兼容期，非破坏性的直接进变更日志通知调用方。
- CI 里加一道兼容性门禁：出现破坏性变更就失败，需要显式豁免才能过。

不适合：判断业务语义变化（同名字段含义变了、枚举值含义变了）——这仍然要靠评审。

## 用法

```bash
python3 scripts/openapi_diff.py openapi-old.json openapi-new.json
python3 scripts/openapi_diff.py old.yaml new.yaml            # YAML 需要 pip install pyyaml
python3 scripts/openapi_diff.py old.json new.json --json
python3 scripts/openapi_diff.py old.json new.json --strict   # CI：有破坏性变更退出码 1
```

拿旧版规范：从上一个 tag 取（`git show v1.4.0:docs/openapi.json > /tmp/old.json`），或从线上服务的 `/openapi.json` 下载。

## 流程

1. 跑脚本，先看「破坏性变更」：每条带位置（方法 + 路径）与原因。
2. 逐条决定：**撤回**（其实不必改）、**兼容改法**（新增字段保留旧字段、可选而非必填、新版本路径 /v2）、或**确认破坏并走流程**（变更公告、迁移期、监控旧字段调用量）。
3. 「非破坏性变更」直接进变更日志；`removed-response`（非 2xx）与 `body-field-removed` 归在这里但值得看一眼。
4. 在 CI 里对 PR 产出的规范与主干规范做 `--strict` 对比，破坏性变更需要显式豁免（如提交信息带 `BREAKING CHANGE:`）。

## 判定规则

| 破坏性 | 非破坏性 |
|---|---|
| 删除接口；删除参数；新增必填参数；可选参数变必填 | 新增接口；新增可选参数；标记 deprecated |
| 参数类型/格式改变；参数枚举移除取值（`param-enum-narrowed`） | 新增可选请求字段 |
| 请求体变必填；请求字段变必填、改类型、枚举收窄（`body-enum-narrowed`）；请求 content-type 移除 | 请求字段被移除（多数服务端忽略未知字段，仍提示确认） |
| 2xx 响应被移除；响应 content-type 移除 | 非 2xx 响应被移除 |
| 响应字段移除、改类型、变可空、不再必返；**响应字段枚举收窄**（`response-enum-narrowed`） | 响应新增字段 |
| 全局 security 变化 | servers 变化（提示确认） |

## 边界与不做的事

- 只解析本地 `$ref`（`#/components/...`），不拉远程引用；`allOf` 合并属性，`oneOf/anyOf` 不展开。
- 对象嵌套最多 6 层；数组以 `[].字段` 表示。
- **枚举收窄请求侧与响应侧都查。** 响应里某字段的 `enum` 取值变少记为 `response-enum-narrowed`（破坏性）——客户端可能正依赖被删掉的那个取值（`status` 去掉 `cancelled` 这类），嵌套对象字段与数组元素字段（`items.[].kind`）同样覆盖。只有一侧写了 `enum`（另一侧没写）不算收窄，因为无法判断取值范围是否真的变小。
- 不比较 description / example 等文档性字段；不判断业务语义变化（同名字段含义变了、枚举取值含义变了，都查不出来）。
- 不校验规范本身是否合法：一份空规范（`{}`、没有 `paths`）比对出来就是「无变更」，别把它当成「兼容」。CI 里请确认两份输入都是真规范；用 `release-readiness-check` 这个总入口跑时，它会先校验两份规范、不合格直接判「无法判断」而不是放行。
- Swagger 2.0 请先转成 OpenAPI 3（如 swagger2openapi）。
