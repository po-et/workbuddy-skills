---
title: 上线前五分钟体检：把 Dockerfile / K8s / SQL / OpenAPI / .env 五项检查串成一条 CI 门禁
summary: 用一个零依赖的「上线体检」Skill 让 WorkBuddy 一条命令跑完五类发布风险检查，第一次跑出 13 个 high，按报告的「→ 改法」逐条收敛到 0，最后把同一条命令接进 CI 当发布门禁；含一次误报、一次漏报和一次「修 warn 修出新 high」的真实过程。
author: Captain
date: "2026-09-18"
category: 研发效能
difficulty: 进阶
skills:
  - release-readiness-check
  - dockerfile-check
  - k8s-manifest-check
  - sql-migration-check
  - openapi-breaking-diff
  - env-sync-check
tags:
  - 上线检查
  - CI 门禁
  - Kubernetes
  - 数据库迁移
  - OpenAPI
  - 研发效能
---

# 上线前五分钟体检：把五项检查串成一条 CI 门禁

## 一、场景

后端服务发版前的风险排查。复盘过去几次线上问题，事后看**全都能在提交代码之前静态查出来**：镜像 `ENV` 里留了一行数据库密码（镜像层永久保留，换密码也删不掉历史层）；Deployment 没配 `resources`，高峰期把节点内存吃满；迁移脚本里一条没有 DEFAULT 的 `ADD COLUMN ... NOT NULL` 在有数据的表上直接失败，发布卡在一半；响应字段 `total_fee` 改名成 `amount`，两个下游调用方不知道；`.env.production` 少一个回调地址，服务起来了但回调静默丢弃。

这五类问题分属五个工具、五个人的习惯，没人会在发版前依次跑五遍，所以真实结局是都不跑。需要的不是更全的工具，而是**一条命令、一个结论、一个能塞进 CI 的退出码**。

## 二、WorkBuddy 侧的配置

- **Skill**：`release-readiness-check`（上线体检，总入口）。五个检查器已内置在 `scripts/checks/` 里，装这一个就够；需要更细参数时再单独装 `dockerfile-check`、`k8s-manifest-check`、`sql-migration-check`、`openapi-breaking-diff`、`env-sync-check`。
- **模式**：普通任务模式即可，脚本本身不到一秒，模型负责读报告、判断真伪、给改法。
- **权限**：默认权限（只读本地目录 + 执行 `python3`）。
- **不需要**专家、连接器或 MCP，**不联网**。

技能做四件事：**发现 → 执行 → 汇总 → 判门禁**。它走一遍目标目录（跳过 `.git`、`node_modules`、`vendor`、`dist` 等），按特征归类文件：`Dockerfile*`、同时含 `apiVersion:` 与 `kind:` 的 YAML、`*.sql`、`openapi*/swagger*` 规范、根目录 `.env*`；逐项用子进程调用内置检查器（统一加 `--json`），把五种结果归一成 `severity / code / where / message / fix`；最后一条硬规则给结论：**有 high 就是「不建议上线」**。某一项挂了只标「执行失败」，其余四项照跑，并在结论里写明「结论只覆盖跑通的部分」。

| 检查项 | 看什么 | 典型 high |
|---|---|---|
| Dockerfile | 18 条最佳实践与安全规则 | `ENV`/`ARG` 把密钥写进镜像层 |
| K8s 清单 | 19 条生产就绪基线：资源、探针、安全上下文、镜像标签、selector 匹配 | 环境变量里明文写密码 |
| SQL 迁移 | 18 条锁表与不可逆风险规则，自动识别 MySQL / PostgreSQL 方言 | DROP COLUMN、无 WHERE 的 UPDATE/DELETE |
| OpenAPI 兼容 | 新旧两份规范的破坏性变更 | 删接口、响应字段不再保证返回 |
| .env 配置 | 示例文件、环境文件、代码三方对齐 | 环境文件缺了示例中登记的变量 |

## 三、操作步骤与真实输出

演示对象是一个按真实项目常见写法构造的最小服务 `orders-api`（11 个文件，域名统一 `example.com`）：`Dockerfile` 里 `ENV DB_PASSWORD=...`、`RUN apt-get update` 与 `install` 分开、`COPY . .` 在依赖安装之前；`k8s/deployment.yaml` 用 `:latest`、无 `resources`、无探针、`env` 明文密码；`migrations/0042_add_channel.sql` 一次性做了「加 NOT NULL 列 + 无 WHERE 回填 + DROP COLUMN + 建索引」；`api/openapi.json` 相对上一版删了 `DELETE /orders/{id}`、把 `page_size` 改必填、把 `total_fee` 改名成 `amount`；`.env.production` 比 `.env.example` 少一个 `ORDER_CALLBACK_URL`。

**第 1 步：发任务。**

```text
用上线体检给 ~/code/orders-api 做一次发布前检查，OpenAPI 的旧版本用 api/openapi.v1.json，
报告写到项目根目录，有 high 的逐条告诉我怎么改。
```

WorkBuddy 执行的命令：

```bash
python3 scripts/release_check.py . --openapi-base api/openapi.v1.json --out ./release-report.md
```

**第 2 步：第一次体检。** 真实回显（2026-09-18 本机实跑）：

```text
上线体检 · /.../orders-api
  Dockerfile 体检         high 1 / warn 2 / info 7
  K8s 清单体检            high 1 / warn 5 / info 8
  SQL 迁移风险            high 3 / warn 0 / info 1
  OpenAPI 破坏性变更      high 6 / warn 0 / info 5
  .env 一致性             high 2 / warn 2 / info 1

合计：high 13 / warn 9 / info 22
门禁：不建议上线（有 high）
报告：/.../orders-api/release-report.md
```

三次连续运行的墙上时间 0.19s / 0.16s / 0.15s——「五分钟」是留给人读报告的。13 个 high 摘录：

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
- **[HIGH]** `response-field-removed` · `GET /orders/{id}` — 响应 200 字段 total_fee 被移除
- **[HIGH]** `response-field-no-longer-required` · `GET /orders/{id}` — 响应 200 字段 total_fee 不再保证返回
- **[HIGH]** `secret-in-example` · `.env.example` — 示例文件第 2 行的 DB_DSN 看起来是真实密钥
- **[HIGH]** `missing` · `.env.production` — .env.production 缺少示例中登记的 ORDER_CALLBACK_URL
```

报告每项最多列 10 条，K8s 实际 14 条，单跑 `python3 scripts/k8s_check.py k8s/` 看到多出来的是 `K011`（未指定 namespace）、`K012`（NodePort 对外暴露）、`K019`（default ServiceAccount 自动挂载 token）。

**第 3 步：按「→ 改法」逐条改。** 报告每条都带改法，WorkBuddy 按项给出 diff，我判断哪几条是真问题：

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

- OpenAPI 六条：不改设计，改兼容方式——接口加回来、`page_size` 恢复可选、`total_fee` 与 `amount` 同时保留且同时必返（`total_fee` 标 `deprecated`）、被收窄的 `status` 枚举值 `cancelled` 加回去，版本号 1.5.0 → 1.5.1。
- `.env` 两条：生产补 `ORDER_CALLBACK_URL`；示例里的 `DB_DSN` 换成 `<postgresql://user:pass@host:5432/orders>` 这种一眼是占位符的写法。

**第 4 步：复跑，遇到「修 warn 修出一个新 high」。** high 从 13 掉到 1，而这个 1 是我自己造出来的：为了消掉「代码读了但示例没登记」的 warn，我把 `PAYMENT_TIMEOUT_MS` 写进了 `.env.example`，于是 `.env.production` 立刻变成 `missing`。这个检查器的语义很硬——**示例登记的变量，每个环境文件都必须有**，它不认「代码里有默认值所以可以不配」。我认同这个取向（靠默认值兜底的超时参数正是最容易在某个环境被忘掉的），所以补进 `.env.production` 而不是从示例里删。终态：

```text
  Dockerfile 体检         high 0 / warn 2 / info 7
  K8s 清单体检            high 0 / warn 5 / info 8
  SQL 迁移风险            high 0 / warn 0 / info 0
  OpenAPI 破坏性变更      high 0 / warn 0 / info 5
  .env 一致性             high 0 / warn 1 / info 1

合计：high 0 / warn 8 / info 21
门禁：可以上线，但先看 warn
```

OpenAPI 剩下的 5 条 info 全是纯新增（新增可选参数 `channel`、响应新增 `amount` 与 `channel`），可以直接抄进变更日志发给调用方。

**第 5 步：接进 CI。** `--strict` 在有 high 时退出码 1（实测：修之前 `echo $?` 得 1，修完得 0）。GitHub Actions 写法（两个分支都在 bash 下实跑验证过）：

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

**这里有个坑值得单独说**：一开始我把「取不到旧规范」的兜底写成 `|| echo '{}' > /tmp/openapi-base.json`。实测空规范当 base，所有接口都被算成「新增」，该项返回 `high 0 / warn 0 / info 3`，**给出一个漂亮的假绿灯**。兜底必须是 `--skip openapi`（报告会明写「跳过」，门禁结论也会注明覆盖范围），不能喂空文件。

## 四、产出物

一份 Markdown 报告（总览表 → 各项 top 问题 → 门禁结论）+ 一个退出码 + 可选 JSON（`{target, generated, report, total, items[]}`，`items[]` 每项含 `status / reason / targets / counts / findings`，可直接喂给机器人）。报告能贴进上线单，因为它满足评审要的三件事：**每条有位置（文件:行号 / 对象名 / 方法+路径）、有规则号、有改法**。

| | 第一次 | 修完 high | 终态 |
|---|---:|---:|---:|
| high | 13 | 1 | **0** |
| warn | 9 | 1 | 8 |
| info | 22 | — | 21 |
| 门禁结论 | 不建议上线 | 不建议上线 | 可以上线，但先看 warn |
| `--strict` 退出码 | 1 | 1 | 0 |

13 个 high 里，靠人工 checklist 能稳定抓住的大概只有 Dockerfile 那条明文密码（因为它最出名）。`SM003`、`param-now-required`、`missing` 这三类是典型的「上线当晚才发现」。

## 五、边界（这部分请一定读完）

1. **误报真实存在。** `.env.example` 里 `DB_DSN=postgresql://user:pass@localhost:5432/orders` 被判成 `secret-in-example`（high），其实是占位符。密钥启发式看的是「变量名命中 PASSWORD/SECRET/TOKEN/API_KEY/PRIVATE_KEY/ACCESS_KEY/CREDENTIAL/DSN/DATABASE_URL，且值不是 `${...}`/`<...>`/`xxx`/`your-*`/`changeme`/`placeholder`/`example`/`dummy`/`redacted` 这些占位形态，且长度 ≥ 12」。**不要为了清零去改坏配置**，这是这类工具最容易被用错的地方。
2. **漏报更危险。** 同一份示例里 `JWT_SIGNING_KEY=8f14e45fceea167a5a36dedd4bea2543`（32 位十六进制，非常像真密钥）**没有**被判成密钥——名字匹配的是 `API_KEY / PRIVATE_KEY / ACCESS_KEY` 这几种带前缀的写法，`JWT_SIGNING_KEY` 不在名单里。同理，把响应字段 `status` 的枚举值 `cancelled` 删掉属于响应枚举收窄，工具也没报——枚举收窄规则只覆盖参数与请求字段。**报告干净 ≠ 没问题**，密钥扫描要另配专门工具，接口语义变化仍要靠评审。
3. **不替代专业工具。** hadolint、kubeconform、OPA/Conftest、DBA 评审的规则集更全更准。这套技能的定位是提交代码之前的第一道快速门禁：零依赖、0.2 秒、五类一起、有退出码。
4. **几个硬限制**，否则会「跑了但其实没查」：OpenAPI 项必须给 `--openapi-base`，只有一份规范时会跳过；Helm/Kustomize 模板不展开，带 `{{ }}` 的 YAML 会被标为模板跳过，要先 `helm template` 渲染；`.env` 只看目标目录根部，`deploy/prod/.env` 要单独跑一次；YAML 格式的 OpenAPI 需要 PyYAML，没有就先转 JSON；K8s 的最小 YAML 解析不支持锚点合并 `<<: *x` 与多行 flow 集合。
5. **分级取舍由团队定。** high 必须清零并作为 CI 门禁；warn 每条有人认领；info（如 `K011` 未指定 namespace、`K019` default SA、`DF015` CMD shell 形式）每季度扫一次，挑几条升级成团队基线，不要每次发布都纠结。

## 六、怎么复用

1. **装技能**：SkillHub 搜索 `release-readiness-check`（总入口，五个检查器已内置）；单项技能 slug：`dockerfile-check`、`k8s-manifest-check`、`sql-migration-check`、`openapi-breaking-diff`、`env-sync-check`。也可以直接从开源仓库取目录放进本地技能目录。
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
