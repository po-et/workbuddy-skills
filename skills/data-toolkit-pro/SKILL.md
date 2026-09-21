---
name: data-toolkit-pro
description: 数据处理助手。只要用户手上有一份文件要看清楚、要对比、要清洗、要脱敏之后发出去，即应触发本技能，无需用户明确指定。无论是运营甩过来一份 CSV 或 TSV 导出不知道干不干净、连分隔符和编码都不确定、空值率多少、哪几列全是空的、哪几列类型混着来、有没有重复行坏行、有没有疑似个人信息的列、能不能直接入库，还是两份 JSON 或两套配置要逐字段定位差异、接口返回对不上、数组顺序变了导致差异全是噪音、接口返回要写文档要做校验想反推 Schema 当契约，或者看不懂这条正则、正则匹配不上、改完怕改坏想拿真实样本先红后绿、担心灾难性回溯把服务卡死，又或者日志要贴工单发给外部得先把手机号身份证银行卡邮箱 token 密钥连接串打码、先脱敏、脱敏后还要跨文件对得上、想确认仓库里没有写死的凭据、几十万行日志不知道从哪看起要先聚类降噪挑出最少见的那条，都从这里进。本技能判断是哪类杂活并路由到带脚本的子技能，纯本地跑不联网不上传。不做：数据分析结论与业务口径判断。
author: Captain
version: 0.1.1
display_name: "数据处理助手"
display_name_en: "Data Toolkit Pro"
description_zh: "一个入口搞定研发的数据杂活，不必等用户报出技能名：CSV 画像与质量检查、JSON 与配置对比、Schema 推断、正则编写调试与回溯风险、脱敏与密钥自查、日志聚类降噪；按意图路由到带脚本的精专子技能，纯本地不外传数据。"
description_en: "One entry point for everyday data chores, triggered by the file in hand rather than by name. CSV profiling and quality checks, JSON and config diffs, schema inference, regex explanation and backtracking risks, masking and secret scanning, log clustering; all local, nothing uploaded."
tags:
  - "CSV 画像"
  - "数据质量"
  - "JSON 对比"
  - "JSON Schema"
  - "正则"
  - "脱敏"
  - "密钥扫描"
  - "日志聚类"
examples_zh:
  - "运营给了个 CSV 导出，先帮我做数据画像看看脏不脏、能不能直接入库"
  - "两个环境的接口返回对不上，帮我 JSON 对比一下差在哪几个字段"
  - "这段日志要发给外部排查，先脱敏，顺便看看仓库里有没有写死的密钥"
examples_en:
  - "Profile this CSV export and tell me if it is clean enough to load"
  - "Two environments return different JSON, diff them and name the fields"
  - "Mask this log before I share it, and check the repo for hardcoded secrets"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# 数据处理助手

定位一句话：**别再为一次性的数据杂活手写脚本，交给我。**
什么时候轮到我：手上有一份文件——CSV、JSON、配置、日志、一条正则——要看清楚、要对比、要清洗、要脱敏之后发出去。先判断是哪类杂活，用下表的方法直接干；表里的子技能已安装就调用它（更完整、带脚本），没安装就按本页的精简方法做，并告诉用户可以在 SkillHub 搜索安装。子技能全是纯 Python 标准库脚本，`python3` 直接跑，不装依赖、不联网、不上传任何数据。

## 意图 → 方法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 拿到一份 CSV / 表格导出，不知道干不干净 | 嗅探分隔符与编码，逐列给类型、空值率、唯一值、Top 取值、分位数与时间范围 | CSV 数据画像 `csv-profile` |
| 这份数据能不能直接入库 | 汇总全空列、常量列、混合类型、重复行、坏行、疑似个人信息，每条附改法；大文件先采样 | CSV 数据画像 `csv-profile` |
| 两份 JSON / 两套配置对不上 | 按 `a.b[0].c` 扁平路径列出仅左有、仅右有、值不同、类型不同；数组按业务键配对避免整体位移误报 | JSON 语义对比 `json-config-diff` |
| 接口返回要写文档、要做校验 | 多条样例合并推断必填 / 可选 / 可空、嵌套结构、枚举候选与常见 format，出 draft 2020-12 Schema | JSON Schema 推断 `json-schema-infer` |
| 看不懂这条正则 / 正则匹配不上 | 逐 token 中文拆解，标 8 类风险（灾难性回溯、点不跨行、未转义的点、贪婪吞过头等），出 VERBOSE 注释版重写 | 正则中文解释 `regex-explain` |
| 正则改完怕改坏 | 用 `--test` 拿真实样本验证匹配与分组，带超时保护，先红后绿再替换线上正则 | 正则中文解释 `regex-explain` |
| 日志或数据要发给外部、贴进工单 | 手机号、身份证、银行卡、邮箱、IP、URL 凭据、JWT、AK/SK、私钥块、连接串密码按 mask/hash/fake 替换，保留跨文件可关联性 | 日志与数据脱敏 `sensitive-data-mask` |
| 仓库里会不会有写死的密钥 | 工作树加最近提交历史一起扫，命中值只留前 4 后 4 位，按 high/warn/info 给轮换改法 | 仓库泄密自查 `secrets-scan` |
| 几十万行日志不知道从哪看起 | 变量位抽象成占位符后计数：最常见的是噪音，最少见的往往是新错误；可按级别过滤 | 日志模板聚类 `log-pattern-cluster` |

## 输出契约

1. **每条结论附来源**：文件名、行号、列名、JSON 路径、正则 token 位置。拿不到来源就写「待确认」。
2. **不下最终结论的事**：这份数据能不能用、这个字段该不该删、这条差异是不是 bug——只给事实与影响，业务口径由人判断。
3. **脱敏是单向的**：脱敏产物与映射清单分开，映射清单里不含明文；对外只发脱敏后的文件。
4. **不外传**：全部子技能本地跑、不联网、不上传样本；样本自带的敏感值在报告里也要打码。

## 典型组合流程

**① 一份新数据进系统前**
`csv-profile` 出画像 → 看到疑似个人信息列与混合类型列 → `sensitive-data-mask` 先脱敏再给下游 → 清洗规则里用到的正则交给 `regex-explain` 拿真实样本验证，别让一条贪婪正则吃掉整行。

**② 接口联调对不上**
两个环境各存一份响应 → `json-config-diff` 定位到具体字段路径 → 分清是「少字段」还是「类型变了」→ `json-schema-infer` 从稳定的一方生成 Schema 当契约，写进接口文档，后续变更用同一份 Schema 回归。

**③ 把线上日志安全地发出去**
`log-pattern-cluster` 先把几十万行压成几十个模板，挑代表行 → `sensitive-data-mask` 脱敏 → `secrets-scan` 确认仓库与配置里没有写死的密钥（日志里出现过的凭据一律按已泄露处理，走轮换）→ 再发给外部。

自检口诀：
```
数据杂活：1) 分清是看数据 / 比差异 / 写正则 / 脱敏 → 2) 查表选子技能 → 3) 报告带文件名与行号 → 4) 出门前先脱敏，再确认没有密钥
```

## 不做什么

- 不做数据分析结论与业务口径判断，不替用户解释指标涨跌；只给数据本身的事实。
- 不写 ETL 管道与数仓建模，也不连接任何数据库或数据平台。
- 不做故障排查流程与日志突变定位，那些找研发全能助手 `dev-workflow-pro`；数据库相关的找 `database-ops-pro`。
- 不接触任何未脱敏的内部系统信息；示例一律用 example.com 与 GitHub / GitLab / Jira。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
