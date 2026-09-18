---
name: openapi-to-markdown
description: OpenAPI 转 Markdown 接口文档、Swagger 生成中文 API 文档、接口文档自动生成、按 tag 分组的接口清单、参数表与响应字段表、给前端与外部调用方看的对接文档、接口文档与代码同步。当用户说「把这份 OpenAPI 生成一份中文接口文档」「swagger.json 转成 Markdown 给前端看」「导出接口文档要带参数表和示例」「只导出订单相关的接口」「接口文档和代码对不上，重新生成一份」时使用。附纯标准库脚本 scripts/openapi_to_markdown.py，解析本地 $ref、合并 allOf、展开 oneOf 与嵌套对象数组，输出目录、按 tag 分组的接口、方法与路径、参数表（名称、位置、必填、类型、说明、示例）、请求体字段表、各状态码响应字段表与自动合成的 JSON 示例；支持 --out 写文件、--tag 过滤、--json 输出中间结构、--strict 做文档完整性门禁。
author: Captain
version: 0.1.0
display_name: "接口文档生成"
display_name_en: "OpenAPI to Markdown"
description_zh: "一条命令把 OpenAPI 3.x 变成能直接发出去的中文 Markdown 接口文档：目录、按 tag 分组、参数与字段表、JSON 示例，$ref 与 allOf 自动展开；纯 Python 标准库。"
description_en: "Turn an OpenAPI 3.x spec into a ready-to-share Chinese Markdown API doc in one command: table of contents, tag grouping, parameter and field tables, JSON samples, with $ref and allOf resolved; pure Python stdlib."
examples_zh:
  - "把这份 OpenAPI 生成一份中文接口文档"
  - "swagger.json 转成 Markdown 给前端看"
  - "只导出订单相关的接口，带请求体字段表"
examples_en:
  - "Generate a Chinese Markdown API doc from this OpenAPI spec"
  - "Convert swagger.json to Markdown for the frontend team"
  - "Export only the order endpoints with request body tables"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📘" } }
---

# 接口文档生成

把 OpenAPI 3.x 规范变成一份可以直接贴进知识库、发给前端或外部调用方的中文 Markdown 文档。适用于对接前的接口交底、版本发布时的文档同步、把散落在代码注解里的接口定义集中成一页。纯 Python 标准库，不装 redoc、不起本地服务。

## 用法

```bash
python3 scripts/openapi_to_markdown.py openapi.json -o docs/api.md
python3 scripts/openapi_to_markdown.py openapi.json --tag 工单 --tag 用户
python3 scripts/openapi_to_markdown.py openapi.json --max-depth 6 --no-toc
python3 scripts/openapi_to_markdown.py openapi.json --json > api-model.json
python3 scripts/openapi_to_markdown.py openapi.json --strict           # 文档缺失则退出码 1
```

参数：`-o/--out` 输出文件（不给就打印到标准输出）、`--tag` 只导出指定分组（可重复或逗号分隔）、`--max-depth` 嵌套展开层数（默认 4）、`--no-toc` 去掉目录、`--json` 输出中间结构便于二次加工、`--strict` 把文档完整性当门禁。

YAML 规范需要 PyYAML；没装就先转成 JSON，脚本会给出提示。

## 输出结构

生成的 Markdown 依次是：标题与版本 → 服务地址 → 认证方式 → 目录 → 按 tag 分组的接口。每个接口输出：

| 区块 | 内容 |
|---|---|
| 标题 | `### GET /issues 查询工单列表`，已废弃的接口会加醒目标记 |
| 提示行 | 需要的认证方案、operationId |
| 请求参数表 | 名称、位置（路径/查询/请求头/Cookie）、必填、类型、说明（含枚举、默认值、长度与取值约束）、示例 |
| 请求体 | 内容类型、是否必填、字段表（点号表示嵌套，`[]` 表示数组元素）、合成的 JSON 请求示例 |
| 响应 | 每个状态码的说明、字段表与 2xx 的 JSON 响应示例 |

`--strict` 会把「接口缺 summary」「参数缺说明」「响应缺说明」「没有 2xx 响应」「$ref 解析不到」列成清单打到标准错误，适合放进 CI 盯住文档质量。

## 流程

1. 先不带参数跑一次，肉眼扫一遍目录和分组是否符合预期；tag 缺失的接口会被归到「未分类」，说明源文件该补 tag。
2. 看标准错误里的完整性提醒，回到 OpenAPI 源文件补 summary 与字段 description。**文档质量的根在规范文件，不在生成器**。
3. 用 `-o docs/api.md` 落盘，连同规范文件一起提交；接口有变更时重新生成，而不是手改 Markdown。
4. 对外交付时用 `--tag` 只导出对方需要的分组，避免把内部接口一并发出去。
5. 想接入自己的模板引擎就用 `--json` 拿中间结构，字段名都是稳定的英文键。

## 边界与常见问题

- 只支持 OpenAPI 3.x。Swagger 2.0 请先用 swagger2openapi 之类的工具转换，脚本检测到 paths 缺失会直接提示。
- 只解析本地 `$ref`（`#/components/...`）；跨文件与远程 URL 的 `$ref` 不会去下载，会记入完整性提醒里，请先用打包工具把规范合并成单文件。
- `oneOf` / `anyOf` 只展开第一个分支并在说明里标注共有几种，避免字段表爆炸；需要完整分支请在规范里补文字说明。
- 嵌套展开默认 4 层，循环引用（A 引用 B、B 又引用 A）靠深度上限截断，不做环检测，深层字段可能被截掉。
- 示例是按 schema 合成的占位值，不是真实数据；要真实示例请在规范里写 `example`，脚本会优先采用。
- 不做反向同步：改了 Markdown 不会回写规范文件，也不校验线上接口的真实返回，那是接口契约测试该做的事。
