---
title: 上线前五分钟体检：把 Dockerfile / K8s / SQL / OpenAPI / .env 五项检查串成一条 CI 门禁
summary: 用一个零依赖的「上线体检」Skill 让 WorkBuddy 一条命令跑完五类发布风险检查，第一次跑出 15 个 high，按报告的「→ 改法」逐条收敛到 0，最后把同一条命令接进 CI 当发布门禁；含一次误报、一次漏报和一次「修 warn 修出新 high」的真实过程。
author: po-et
date: "2026-09-18"
category: 研发效能
difficulty: 进阶
aside: false
outline: false
skills:
  - release-readiness-check
tags:
  - 上线检查
  - CI 门禁
  - Kubernetes
  - 数据库迁移
  - OpenAPI
  - 研发效能
---

# 上线前五分钟体检：把 Dockerfile / K8s / SQL / OpenAPI / .env 五项检查串成一条 CI 门禁

## 场景描述

后端服务发版前的风险排查。复盘过去几次线上问题，事后看**全都能在提交代码之前静态查出来**：镜像 `ENV` 里留了一行数据库密码（镜像层永久保留，换密码也删不掉历史层）；Deployment 没配 `resources`，高峰期把节点内存吃满；迁移脚本里一条没有 DEFAULT 的 `ADD COLUMN ... NOT NULL` 在有数据的表上直接失败，发布卡在一半；响应字段 `total_fee` 改名成 `amount`，两个下游调用方不知道；`.env.production` 少一个回调地址，服务起来了但回调静默丢弃。

这五类问题分属五个工具、五个人的习惯，没人会在发版前依次跑五遍，所以真实结局是都不跑。需要的不是更全的工具，而是**一条命令、一个结论、一个能塞进 CI 的退出码**。

## 想要完成的任务

输入：一个准备发布的后端服务代码仓库，本地已有（或部分已有）`Dockerfile`、K8s 部署清单（YAML）、SQL 迁移脚本、新旧两版 OpenAPI 规范、`.env.example` / `.env.production`。

目标和交付物：

1. 一条命令跑完五类发布风险检查：Dockerfile、K8s 清单、SQL 迁移、OpenAPI 兼容性、`.env` 配置一致性。
2. 一份 Markdown 报告：总览表 → 各项 top 问题 → 门禁结论，每条问题带「文件:行号 / 对象名 / 方法+路径」定位、规则号和「→ 改法」。
3. 一个可读的门禁结论（「不建议上线」/「可以上线，但先看一眼 warn」/「无法判断」）。
4. 同一条命令能接进 CI（`--strict`），有 high 时退出码 1，直接当发布门禁用。

这是演示项目 `orders-api` 的具体化目标，背后是一个更通用的任务：把「发版前应该做但没人会记得依次做五遍」的检查，压缩成「一条命令、一个结论、一个退出码」。

## 使用的 Skill

| Skill | 用途 | 来源或安装方式 |
| --- | --- | --- |
| `release-readiness-check` | 总入口。扫描目标目录，发现 Dockerfile、K8s 清单、SQL 迁移、OpenAPI 规范、`.env` 文件，逐项调用内置检查器并汇总成报告与门禁结论 | 开源（MIT），仓库 `https://github.com/po-et/workbuddy-skills`，技能目录 `skills/release-readiness-check/`。**尚未上架 WorkBuddy 或 SkillHub 应用市场**，需要把该目录复制到本地 Skill 目录后使用 |

`release-readiness-check` 内置五个检查器，装总入口这一个就够；需要单独调参数时可以只装对应的一个，来源与安装方式同上：`dockerfile-check`、`k8s-manifest-check`、`sql-migration-check`、`openapi-breaking-diff`、`env-sync-check`。

技能做四件事：**发现 → 执行 → 汇总 → 判门禁**。它走一遍目标目录（跳过 `.git`、`node_modules`、`vendor`、`dist` 等），按特征归类文件：`Dockerfile*`、同时含 `apiVersion:` 与 `kind:` 的 YAML、`*.sql`、`openapi*/swagger*` 规范、根目录 `.env*`；逐项用子进程调用内置检查器（统一加 `--json`），把五种结果归一成 `severity / code / where / message / fix`；最后按门禁规则给结论：**有 high 就是「不建议上线」；没有 high 但有项目拿不到证据（子脚本跑失败、规范不合格）同样不放行**——三态门禁，「无法判断」不等于「通过」。某一项挂了或证据不合格只标「无法判断」，其余四项照跑，并在结论里写明这一项没有进入「通过」的判断。

| 检查项 | 看什么 | 典型 high |
|---|---|---|
| Dockerfile | 18 条最佳实践与安全规则 | `ENV`/`ARG` 把密钥写进镜像层 |
| K8s 清单 | 19 条生产就绪基线：资源、探针、安全上下文、镜像标签、selector 匹配 | 环境变量里明文写密码 |
| SQL 迁移 | 18 条锁表与不可逆风险规则，自动识别 MySQL / PostgreSQL 方言 | DROP COLUMN、无 WHERE 的 UPDATE/DELETE |
| OpenAPI 兼容 | 新旧两份规范的破坏性变更 | 删接口、响应字段不再保证返回 |
| .env 配置 | 示例文件、环境文件、代码三方对齐 | 环境文件缺了示例中登记的变量 |

## 前置条件

- WorkBuddy 可正常使用，普通任务模式即可（脚本本身执行不到一秒，模型负责读报告、判断真伪、给改法）。
- 权限：默认权限即可——只读本地目标目录 + 执行 `python3`；不需要专家、连接器或 MCP，全程不联网。
- 操作系统：本文命令与终端回显为 macOS 本机实跑；检查器本身不依赖操作系统特性，Linux CI 环境同样适用——未在 Windows 上验证，**需确认**。
- 需要一个准备发布的目标项目，本地已有（或部分已有）`Dockerfile`、K8s 部署清单、SQL 迁移脚本、新旧两版 OpenAPI 规范、`.env.example` / `.env.production`；只覆盖其中几类也可以，未覆盖的检查项会显示「不适用」而不是报错（跟显式 `--skip` 的「已跳过」是两个不同的状态标签）。
- 不需要任何外部账号、API Key 或付费服务。

## 在 WorkBuddy 中的操作

演示对象是一个按真实项目常见写法构造的最小服务 `orders-api`（11 个文件，域名统一 `example.com`）：`Dockerfile` 里 `ENV DB_PASSWORD=...`、`RUN apt-get update` 与 `install` 分开、`COPY . .` 在依赖安装之前；`k8s/deployment.yaml` 用 `:latest`、无 `resources`、无探针、`env` 明文密码；`migrations/0042_add_channel.sql` 一次性做了「加 NOT NULL 列 + 无 WHERE 回填 + DROP COLUMN + 建索引」；`api/openapi.json` 相对上一版删了 `DELETE /orders/{id}`、把 `page_size` 改必填、把 `total_fee` 改名成 `amount`；`.env.production` 比 `.env.example` 少一个 `ORDER_CALLBACK_URL`。

**第 1 步：发任务。** 提示词见下一节「提示词或任务指令」。WorkBuddy 执行的命令：

```bash
python3 scripts/release_check.py . --openapi-base api/openapi.v1.json --out ./release-report.md
```

**第 2 步：第一次体检。** 五项检查逐项给出 high/warn/info 计数，合计 15 个 high，门禁结论「不建议上线」。完整回显见下一节「在 WorkBuddy 中的效果」。

**第 3 步：按报告里每条的「→ 改法」逐条改。** 报告每条都带改法，WorkBuddy 按项给出 diff，我判断哪几条是真问题：

- `DF006`：删掉 `ENV DB_PASSWORD`，改运行时注入。
- `K010`：`value:` 换成 `valueFrom.secretKeyRef`。
- `SM001/SM003/SM006`：一次性迁移拆成扩展-收缩两阶段，本次只做扩展：

```sql
-- 0042 扩展阶段：只加可空列 + 分批回填，不删旧列
ALTER TABLE orders ADD COLUMN channel VARCHAR(32);
UPDATE orders SET channel = 'web' WHERE channel IS NULL AND id <= 100000;
CREATE INDEX CONCURRENTLY idx_orders_channel ON orders (channel);
-- 收缩阶段（0044，等代码不再读写 source_legacy 且上线一周后）：
--   ALTER TABLE orders ALTER COLUMN channel SET NOT NULL;
--   ALTER TABLE orders DROP COLUMN source_legacy;
```

- OpenAPI 八条：不改设计，改兼容方式——接口加回来、`page_size` 恢复可选、`total_fee` 与 `amount` 同时保留且同时必返（`total_fee` 标 `deprecated`）、被收窄的 `status` 枚举值 `cancelled` 加回去，版本号 1.5.0 → 1.5.1。八条里有两条是 `response-enum-narrowed`（`GET /orders`、`GET /orders/{id}` 各一条，同一个 `status` 枚举收窄因为两个接口共用 `Order` schema），改法是同一个。
- `.env` 两条：生产补 `ORDER_CALLBACK_URL`；示例里的 `JWT_SIGNING_KEY` 换成 `<jwt-signing-key>` 这种一眼是占位符的写法（`DB_DSN` 这次没有被判成密钥，见「安全与限制」第 1 条）。

**第 4 步：复跑，确认收敛。** 复跑过程中出现的插曲见「遇到的问题」；终态回显见「在 WorkBuddy 中的效果」。

**第 5 步：接进 CI。** `--strict` 在有 high 时退出码 1。GitHub Actions 写法（两个分支都在 bash 下实跑验证过）：

```yaml
- name: 上线体检
  run: |
    # 技能目录 vendor 进仓库里，路径按你自己的放法改
    SCRIPT=vendor/release-readiness-check/scripts/release_check.py
    BASE_REF="${GITHUB_BASE_REF:-main}"
    if git show "origin/$BASE_REF:api/openapi.json" > /tmp/openapi-base.json 2>/dev/null; then
      python3 "$SCRIPT" . --openapi-base /tmp/openapi-base.json --out release-report.md --strict
    else
      echo "[warn] 取不到 origin/$BASE_REF 的 api/openapi.json，本次跳过 OpenAPI 比对"
      python3 "$SCRIPT" . --skip openapi --out release-report.md --strict
    fi
```

这一步踩的坑（空规范当 base 会制造假绿灯）见「遇到的问题」。

## 提示词或任务指令

```text
用上线体检给 ~/code/orders-api 做一次发布前检查，OpenAPI 的旧版本用 api/openapi.v1.json，
报告写到项目根目录，有 high 的逐条告诉我怎么改。
```

WorkBuddy 把这句自然语言指令翻译成「在 WorkBuddy 中的操作」第 1 步里 `release-readiness-check` 的那次调用。CI 里的调用是写死在 workflow 里的脚本命令，不是对话指令，见第 5 步的 YAML 片段。

## 在 WorkBuddy 中的效果

**第一次体检，真实回显**（2026-09-18 本机实跑）：

```text
上线体检 · /.../orders-api
  Dockerfile 体检         high 1 / warn 2 / info 7
  K8s 清单体检            high 1 / warn 5 / info 8
  SQL 迁移风险            high 3 / warn 0 / info 1
  OpenAPI 破坏性变更      high 8 / warn 0 / info 5
  .env 一致性             high 2 / warn 2 / info 1

合计：high 15 / warn 9 / info 22；无法判断 0 项
门禁：不建议上线
报告：/.../orders-api/release-report.md
```

三次连续运行的墙上时间 0.19s / 0.16s / 0.15s——「五分钟」是留给人读报告的。15 个 high 摘录：

```markdown
- **[HIGH]** `DF006` · `Dockerfile:L10` — ENV 中疑似把敏感值写进镜像：DB_PASSWORD
  - → 改法：镜像层会永久保留该值；改用运行时注入（-e / secrets）或 BuildKit 的 --mount=type=secret
- **[HIGH]** `K010` · `k8s/deployment.yaml Deployment/orders-api` — 容器 orders-api 的环境变量 DB_PASSWORD 以明文 value 写入清单
  - → 改法：改用 valueFrom.secretKeyRef 引用 Secret
- **[HIGH]** `SM003` · `migrations/0042_add_channel.sql:L2` — 新增列 channel 为 NOT NULL 但没有 DEFAULT
  - → 改法：先加可空列 → 回填 → 再设 NOT NULL，或提供 DEFAULT
- **[HIGH]** `SM006` · `migrations/0042_add_channel.sql:L4` — UPDATE/DELETE 没有 WHERE
- **[HIGH]** `SM001` · `migrations/0042_add_channel.sql:L6` — DROP COLUMN 会永久删除该列数据
- **[HIGH]** `removed-operation` · `DELETE /orders/{id}` — 接口被删除
- **[HIGH]** `param-now-required` · `GET /orders` — 参数 query:page_size 由可选变为必填
- **[HIGH]** `response-enum-narrowed` · `GET /orders` — 响应 200 字段 items.[].status 枚举移除了 ['cancelled']
- **[HIGH]** `response-enum-narrowed` · `GET /orders/{id}` — 响应 200 字段 status 枚举移除了 ['cancelled']
- **[HIGH]** `response-field-no-longer-required` · `GET /orders/{id}` — 响应 200 字段 total_fee 不再保证返回
- **[HIGH]** `response-field-removed` · `GET /orders/{id}` — 响应 200 字段 total_fee 被移除
- **[HIGH]** `secret-in-example` · `.env.example` — 示例文件第 10 行的 JWT_SIGNING_KEY 看起来是真实密钥
- **[HIGH]** `missing` · `.env.production` — .env.production 缺少示例中登记的 ORDER_CALLBACK_URL
```

（以上摘录 13 条，另有 `GET /orders` 的 `response-field-removed`/`response-field-no-longer-required`（`total_fee`）未列出，共 15 条 high；完整列表见正文文章「15 个 high 逐条摘录」一节。）

报告每项最多列 10 条，K8s 实际 14 条，单跑 `python3 scripts/k8s_check.py k8s/` 看到多出来的是 `K011`（未指定 namespace）、`K012`（NodePort 对外暴露）、`K019`（default ServiceAccount 自动挂载 token）。

**终态**（按「→ 改法」逐条改完并处理完插曲后复跑）：

```text
  Dockerfile 体检         high 0 / warn 2 / info 7
  K8s 清单体检            high 0 / warn 5 / info 8
  SQL 迁移风险            high 0 / warn 0 / info 0
  OpenAPI 破坏性变更      high 0 / warn 0 / info 5
  .env 一致性             high 0 / warn 1 / info 1

合计：high 0 / warn 8 / info 21；无法判断 0 项
门禁：可以上线，但先看一眼 warn
```

OpenAPI 剩下的 5 条 info 全是纯新增（新增可选参数 `channel`、响应新增 `amount` 与 `channel`），可以直接抄进变更日志发给调用方。

**CI 门禁验证**：`--strict` 退出码随 high 计数变化——修之前 `echo $?` 得 1，修完得 0（本机实测）。

**产出物**：一份 Markdown 报告（总览表 → 各项 top 问题 → 门禁结论）+ 一个退出码 + 可选 JSON（`{target, generated, report, total, gate, items[]}`，`gate` 含 `verdict/blocked/headline/why`，`items[]` 每项含 `status / reason / targets / counts / findings`，可直接喂给机器人）。报告能贴进上线单，因为它满足评审要的三件事：**每条有位置（文件:行号 / 对象名 / 方法+路径）、有规则号、有改法**。

| | 第一次 | 修完 high | 终态 |
|---|---:|---:|---:|
| high | 15 | 1 | **0** |
| warn | 9 | 1 | 8 |
| info | 22 | — | 21 |
| 门禁结论 | 不建议上线 | 不建议上线 | 可以上线，但先看一眼 warn |
| `--strict` 退出码 | 1 | 1 | 0 |

15 个 high 里，靠人工 checklist 能稳定抓住的大概只有 Dockerfile 那条明文密码（因为它最出名）。`SM003`、`param-now-required`、`missing` 这三类是典型的「上线当晚才发现」。

## 验收标准

- 报告 summary 五项检查逐项给出 high/warn/info 计数（没有「无法判断」项），版式与 CLI 回显一致。
- 门禁结论文本随 high 计数变化：15 个 high → 「不建议上线」；high 清零后 → 「可以上线，但先看一眼 warn」。
- `--strict` 退出码随 high 计数、以及「无法判断」项数变化：有 high 或有「无法判断」项时 `echo $?` 为 1，全部项都有结论且无 high 后为 0（本机实测）。
- 报告中每条 high/warn 都带「文件:行号 / 对象名 / 方法+路径」定位 + 规则号 + 「→ 改法」，可以直接抄进上线单或变更日志。
- 此前 CI 用空 JSON 兜底 OpenAPI base 会把所有接口误判为「新增」（`high 0 / warn 0 / info 3`，假绿灯）；这个缺陷已经修了，现在这类不合格的 base 会被 `validate_spec` 拦下来，标成「无法判断（skipped-invalid）」而不是误判为「新增」，`--strict` 下同样拦截（本机实测 `echo $?` 为 1）。正确兜底仍然建议用 `--skip openapi`，语义更明确，报告里会显式注明「跳过」。

## 遇到的问题

- **「修 warn 修出一个新 high」**：high 从 15 掉到 1，而这个 1 是自己造出来的——为了消掉「代码读了但示例没登记」的 warn，把 `PAYMENT_TIMEOUT_MS` 写进了 `.env.example`，于是 `.env.production` 立刻变成 `missing`。这个检查器的语义很硬——**示例登记的变量，每个环境文件都必须有**，它不认「代码里有默认值所以可以不配」。这个取向是合理的（靠默认值兜底的超时参数正是最容易在某个环境被忘掉的），所以最终选择补进 `.env.production`，而不是从示例里删。
- **CI 假绿灯，此前的缺陷 + 已修复**：最初写这个案例时，把「取不到旧规范」的兜底写成 `|| echo '{}' > /tmp/openapi-base.json`。当时实测空规范当 base，所有接口都被算成「新增」，该项返回 `high 0 / warn 0 / info 3`，给出一个漂亮的假绿灯——哪怕这次发布删了接口，门禁也显示「可以上线」。这个问题后来在 release-readiness-check 里修掉了：OpenAPI 项比对前会先校验两份规范本身合不合格（有没有 `openapi`/`swagger` 版本号、`paths` 里有没有接口）。用同样的空 `{}` 文件复测（2026-09-18 本机实跑）：`OpenAPI 破坏性变更` 这一项现在显示「无法判断（skipped-invalid）：规范不合格，无法比对……」，总计 `high 7 / warn 9 / info 17；无法判断 1 项`，门禁「不建议上线」，`--strict` 退出码 1——不再是假绿灯，而是「无法判断」，现在整个工具是**三态门禁**：有 high → 不建议上线；没有 high 但有项目无法判断 → 同样不放行；全部项目都有结论且无 high → 才放行。「拿不到证据」不再等于「通过」，这条边界现在由代码保证。不过 CI 里仍然建议显式写 `--skip openapi`（语义比「凑巧被判成无法判断」更清楚），下面的 workflow 保留这个写法。

## 安全与限制

1. **误报真实存在，这次实跑抓到的例子换了一个。** 最初写这篇案例时，`.env.example` 里 `DB_DSN=postgresql://user:pass@localhost:5432/orders` 被判成 `secret-in-example`（high），其实是占位符——这条误报后来被 env-sync-check 自己的修复消掉了：密钥判断改成「名字 + 值」双重条件，连接串类的值现在只截取内嵌密码段判断（这里是 `pass`，4 个字符，长度不够 12），所以这次实跑 `DB_DSN` 完全没被提示。但双重判定换了个地方冒出新误报：`.env.production` 第 4 行的 `JWT_SIGNING_KEY=REPLACED_BY_SECRET_MANAGER` 被判成 `secret`（warn）——`SIGNING` 命中密钥命名，值长度够、字符混杂也够，占位符词表又没收录「REPLACED_BY_...」这种「真值由密钥管理系统接管」的写法。它其实不是密钥，是一句人话注释。**不要为了清零去改坏配置**，这是这类工具最容易被用错的地方；具体命中哪个变量会随规则版本变化。
2. **漏报也真实存在，但这次的两个例子都已经被修掉了。** 最初写这篇案例时有两处漏报：同一份示例里 `JWT_SIGNING_KEY=8f14e45fceea167a5a36dedd4bea2543`（32 位十六进制，非常像真密钥）没有被判成密钥——当时名字规则只认 `API_KEY / PRIVATE_KEY / ACCESS_KEY` 这几种带前缀的写法；响应字段 `status` 的枚举值 `cancelled` 被删掉属于响应枚举收窄，当时的枚举收窄规则只覆盖参数与请求字段，也没报。这两处后来都修了：env-sync-check 的密钥名字规则加了 `SIGNING`/`JWT` 前缀，这次实跑 `JWT_SIGNING_KEY` 在 `.env.example` 里被判成 `secret-in-example`（high）；openapi-breaking-diff 新增了 `response-enum-narrowed` 规则，`status` 枚举收窄在两个接口上各报了一条 high（这也是本文把 OpenAPI 的 6 个 high 更正为 8 个的原因）。**报告干净 ≠ 没问题**这条结论没变——规则覆盖范围会随版本变化，不是跑一次就能一劳永逸；密钥扫描仍要另配专门工具，接口语义变化仍要靠评审。
3. **不替代专业工具。** hadolint、kubeconform、OPA/Conftest、DBA 评审的规则集更全更准。这套技能的定位是提交代码之前的第一道快速门禁：零依赖、0.2 秒、五类一起、有退出码。
4. **几个硬限制**，否则会「跑了但其实没查」：OpenAPI 项必须给 `--openapi-base`，只有一份规范、或规范不合格时都会标为「无法判断」而不是被当成没有变更悄悄放行；Helm/Kustomize 模板不展开，带 `{{ }}` 的 YAML 会被标为模板跳过，要先 `helm template` 渲染；`.env` 只看目标目录根部，`deploy/prod/.env` 要单独跑一次；YAML 格式的 OpenAPI 需要 PyYAML，没有就先转 JSON；K8s 的最小 YAML 解析不支持锚点合并 `<<: *x` 与多行 flow 集合。
5. **分级取舍由团队定。** high 必须清零并作为 CI 门禁；warn 每条有人认领；info（如 `K011` 未指定 namespace、`K019` default SA、`DF015` CMD shell 形式）每季度扫一次，挑几条升级成团队基线，不要每次发布都纠结。

## 可以怎样复用

1. **装技能**：目前从开源仓库 `https://github.com/po-et/workbuddy-skills` 的 `skills/release-readiness-check/` 目录复制到本地 Skill 目录即可（总入口，五个检查器已内置）；单项技能同理，从对应子目录复制：`dockerfile-check`、`k8s-manifest-check`、`sql-migration-check`、`openapi-breaking-diff`、`env-sync-check`。尚未上架 WorkBuddy 或 SkillHub 应用市场。
2. **第一次跑别开 `--strict`**：存量项目大概率一片红，先出报告、把 high 列成表、分两三个迭代清掉，清零后再挂 CI，从此只拦新增。
3. **三条命令够用**：

```bash
python3 scripts/release_check.py . --openapi-base api/openapi.v1.json --out ./release-report.md  # 本地出报告
python3 scripts/release_check.py . --skip openapi --strict --out release-report.md               # CI 门禁
python3 scripts/k8s_check.py k8s/                                                                # 单项深挖
```

4. **别把它当唯一关卡。** 它的价值是「便宜到你每次都会跑」，不是「全」。

技能与全部脚本开源（MIT）：<https://github.com/po-et/workbuddy-skills>，总入口在 `skills/release-readiness-check/`。

---

**数据说明**：本文所有命令、终端回显、规则号与报告片段均为 2026-09-18 在本机对演示项目 `orders-api` 实跑的真实结果（耗时用 `/usr/bin/time -p` 连测三次）。演示项目为本文构造的最小服务，不涉及任何真实业务系统与数据，域名统一使用 `example.com`。
