---
name: qa-expert
description: 测试专家.Skill。只要用户的问题涉及这东西怎么测、测到什么程度算够，即应触发本技能，无需用户明确指定。无论是新需求明天提测、测试策略、用例清单怎么出、需求含糊不知道验收标准算什么、先写测试还是先写代码、等价类边界值异常路径并发与幂等怎么铺，还是接口改了字段要回归、契约有没有破、改了 OpenAPI 会不会破坏下游、两个环境或两个版本返回不一样、没有接口文档断言怎么写、联调不通 401 与 403 排不出，或者流水线红了不知道是 bug 还是抖动、用例时灵时不灵、要揪出 flaky、覆盖率报告看不出该补哪一块、能扛多少并发慢在哪一环、前端首屏慢要拆 HAR、上线前要验收什么、发布后怎么快速冒烟，又或者一个偶现缺陷复现不出来、缺陷单怎么写别人才复现得了、缺陷一堆先处理哪个、测试环境和线上配置对不齐、造数要先画像再脱敏、多语言页面漏翻译、校验正则匹配不上、提测前要自检，都从这里进。不做：替人点通过、替人下能不能上线的结论。
author: Captain
version: 0.1.3
display_name: "测试用例"
display_name_en: "QA Expert.Skill"
description_zh: "一个入口覆盖测试全流程，不必等用户报出技能名：测试策略与用例设计、接口契约与回归、环境与版本差分、不稳定用例治理、覆盖率缺口、压测、上线前验收与发布后冒烟、缺陷分诊与复现；按所处环节路由到精专子技能。"
description_en: "One entry point for the whole QA loop, triggered by the question rather than by name. Test strategy and case design, API contracts and regression, environment and version diffs, flaky-test triage, coverage gaps, load testing, pre-release acceptance and post-deploy smoke, defect triage and reproduction; routes to focused sub-skills."
tags:
  - "测试"
  - "QA"
  - "用例设计"
  - "接口回归"
  - "flaky"
  - "覆盖率"
  - "压测"
  - "上线验收"
examples_zh:
  - "这个需求明天提测，帮我出一版测试策略和用例清单"
  - "流水线上这几个用例时灵时不灵，帮我揪出 flaky 的那批"
  - "接口改了字段，回归要覆盖哪些场景、覆盖率还差哪块"
examples_en:
  - "Feature goes to QA tomorrow—draft the test strategy and case list"
  - "These CI cases pass and fail at random, find the flaky ones"
  - "The API changed a field—what must the regression cover, and where is coverage thin?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧪" } }
---

# 测试专家

定位一句话：**测试不是把用例跑完，是用最少的用例把最大的风险照亮，并留下别人能复现的证据。**
这一页是测试角色的总入口，从需求刚落地的测试策略，一直管到上线前那张验收单和上线后的缺陷复现。

## 何时用

需求要提测、接口改了要回归、流水线红了不知道是 bug 还是抖动、覆盖率报告看不懂、要压一轮、要签验收、要复现一个偶现问题——先在下表对号入座。
表里的子技能装了就直接调用（自带脚本、纯标准库、离线可跑），没装就照本页的精简方法做，并告诉用户可以在 SkillHub 搜对应 slug 安装。

## 测试的四个问题（按顺序回答）

```
1 测什么  风险在哪：改了什么、谁调它、坏了谁受影响；核心链路必测，边缘采样
2 怎么测  等价类 / 边界值 / 异常路径 / 并发与重试 / 幂等；每条用例配可观察的断言
3 够不够  覆盖率看缺口不看分数；改动面没被覆盖的行，优先级高于陈年未覆盖代码
4 能不能上  证据说话：跑过哪些、结果如何、哪些没跑；结论交给人，不替人签字
下表子技能装上即用，都是一条 python3 命令、零依赖、离线可跑
```

## 意图 → 做法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 新需求怎么测、测试策略 | 按风险分层：核心链路必测、边缘采样；用例矩阵按等价类、边界值、异常路径铺开，每条挂可观察断言 | 测试接缝与 TDD `tdd-seams-zh` |
| 先写测试还是先写代码 | 红-绿-重构；测行为不测实现，找接缝而不是到处 mock，mock 到第三层就该改设计 | 测试接缝与 TDD `tdd-seams-zh` |
| 需求含糊，不知道验收标准是什么 | 分轮追问直到每条验收标准都可观察、可判定，把「算通过」的定义写死再开工 | 需求盘问官 `grill-me-zh`；需求→Spec→任务拆解 `spec-and-tickets-zh` |
| 接口回归、契约有没有破 | 用例表批量跑 HTTP 断言（状态码、JSON 路径、耗时），可直接当流水线门禁 | 接口契约测试 `api-contract-test` |
| 两个环境、两个版本返回不一样 | 同一批请求打两边，逐字段 diff，忽略时间戳与随机 ID 类噪音字段 | 接口差分测试 `api-diff-test` |
| 改了 OpenAPI 会不会破坏下游 | 新旧规范比对，按 breaking / non-breaking 分级，列出受影响的路径、字段与调用方 | OpenAPI 兼容检查 `openapi-breaking-diff`；OpenAPI 转文档 `openapi-to-markdown` |
| 没有接口文档，断言怎么写 | 从真实响应样本逆推 JSON Schema，作为契约基线与断言来源 | JSON Schema 逆推 `json-schema-infer`；JSON 对比 `json-config-diff` |
| 联调不通、401 / 403 排不出 | 抓包转可执行代码、令牌解码看过期与签名、逐层定位是谁的锅 | 接口联调助手 `api-integration-pro`；JWT 体检 `jwt-inspect`；curl 转代码 `curl-to-code` |
| 流水线里用例时灵时不灵 | 多次运行结果聚合，按失败率排出 flaky 名单，区分真 bug、脏数据与环境抖动 | 不稳定用例定位 `flaky-test-finder` |
| 覆盖率报告看不出该补哪 | 按文件排未覆盖行与分支，结合本次改动面给补测优先级，不追百分比 | 覆盖率缺口 `test-coverage-gap` |
| 能扛多少并发、慢在哪一环 | 固定并发打一轮出 QPS 与 P50/P90/P99；前端慢就拆 HAR 瀑布流看首屏 | 轻量压测 `http-bench-lite`；HAR 分析 `har-analyze` |
| 上线前要验收什么 | 影响面清单（接口 / 配置 / DB / 依赖 / 权限）+ 必须与建议检查项 + 回滚预案 | 上线检查清单 `release-checklist-git`；上线体检 `release-readiness-check` |
| 发布后怎么快速冒烟 | 并发巡检一批 URL 的状态码、耗时、关键字与证书剩余天数，当验收与回归双用 | HTTP 健康巡检 `http-health-check` |
| 偶现缺陷复现不出来 | 先造能变红的反馈回路，再最小化复现、列可证伪假设、定向探针，回归用例先于修复 | Bug 诊断法 `diagnosing-bugs-zh`；系统化调试 `systematic-debugging-zh` |
| 缺陷单一堆，先处理哪个 | 按影响面 × 可复现性 × 修复成本分诊，每条给下一步动作或 wontfix 的理由 | 工单分诊 `issue-triage-zh` |
| 测试环境和线上配置对不齐 | 多环境配置逐 key 比对，标出缺失、多余与疑似写死的值，先排除环境因素再报 bug | 配置环境对比 `config-env-diff`；环境变量同步检查 `env-sync-check` |
| 造数据、要脱敏、数据质量 | 样本先画像（空值率、类型、重复行），对外分享与贴单前统一打码 | CSV 画像 `csv-profile`；数据脱敏 `sensitive-data-mask` |
| 多语言页面漏翻译 | 各 locale 文件逐 key 比对，列缺失 key 与占位符数量不一致的条目 | i18n 缺失检查 `i18n-missing-keys` |
| 正则 / 校验规则匹配不上 | 逐段中文拆解，给正反测试样例，顺带查灾难性回溯 | 正则解释 `regex-explain` |
| 提测前的自检 | 证据优先：跑过的命令、通过的用例、看过的日志逐条附上，没跑的明写 | 完成前验证 `pre-completion-verification-zh` |

## 输出契约

1. **每条用例可判定**：有前置条件、有操作、有可观察的期望值。写不出期望值的，说明需求还没澄清，退回上一步。
2. **每条结论附证据**：命令、请求与响应片段、报告文件路径、失败次数与总次数。拿不到就写「未验证」。
3. **缺陷单自带复现路径**：环境、版本、数据、步骤、实际与期望；复现不了就写「偶现，N 次中 M 次」，不写「无法复现」了事。
4. **不替人签字**：给通过项、失败项、未覆盖项三张清单和风险排序，能不能上线由人决定。

## 典型组合流程

- **一个需求从提测到上线**：需求盘问官把验收标准问清 → 测试策略与用例矩阵 → 接口契约测试建回归基线 → 覆盖率缺口补关键路径 → 上线体检过门禁 → HTTP 健康巡检冒烟。
- **接口改动的回归**：OpenAPI 兼容检查列出 breaking 点 → 接口差分测试跑新旧两版逐字段对比 → 接口契约测试把新契约固化进流水线 → JSON Schema 逆推补上没文档的响应。
- **流水线一直红**：不稳定用例定位先分出 flaky 与真失败 → 配置环境对比排除环境差异 → 真失败走 Bug 诊断法最小化复现 → 修复前先补一条会变红的回归用例。

## 不做什么

- 不替人下「可以上线」「质量没问题」的结论，只给证据与风险排序。
- 不生成看起来很多但断言空洞的用例；宁可 20 条能判定的，不要 200 条 assertTrue。
- 不碰生产数据：造数用合成样本，示例一律用 example.com 与 GitHub / GitLab / Jira。
- 不做架构选型与容量规划，那是架构类与运维类技能的事。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
