# 案例 #2「上线前五分钟体检」需要的 5 张过程截图

对应文章：`../03-案例-上线前五分钟体检-把五项检查串成一条-CI-门禁.md`
占位语法：文章里已写好 `![图N：说明](03-assets/N-xxx.png)`，把图按下列文件名放进本目录即可。

征集规则要求「≥3 张过程截图」「过程而非成品」（依据 `docs/channels.md`），所以图 2、图 4 是必需的两张；图 1、3、5 建议补齐到 5 张。

| # | 文件名 | 谁来截 | 截哪个界面 | 画面里必须出现什么 |
|---|---|---|---|---|
| 1 | `1-skill-install.png` | Captain（需登录客户端） | WorkBuddy 客户端 →「专家·技能·连接器 → 技能」里「上线体检」的详情页；或技能市场里 `release-readiness-check` 的详情页 | 技能名「上线体检」、作者署名、描述里「五项检查」字样。若尚未上架，退而截本地技能目录中的 `release-readiness-check/SKILL.md`（要能看到 frontmatter 的 `name` 与 `display_name`） |
| 2 | `2-task-run.png` | Captain（需登录客户端） | WorkBuddy 任务对话页，第一次体检那一轮 | 上半：我发的任务原文（「用上线体检给 …/orders-api 做一次发布前检查…」）；下半：脚本回显那一屏，**必须能看到 `合计：high 13 / warn 9 / info 22` 与 `门禁：不建议上线（有 high）`** 这两行。这是全文最关键的一张 |
| 3 | `3-report-overview.png` | Captain（或我本地生成后由你确认） | 生成的 `release-report.md`，在客户端内预览或编辑器里打开 | 「一、总览」那张五行表格（含合计行 13 / 9 / 22）+ 「三、门禁结论」那段「**不建议上线**」。可以是同一屏两段，或上下拼图 |
| 4 | `4-fix-suggestion.png` | Captain（需登录客户端） | WorkBuddy 针对 SQL 三条 high 给出改法的那段对话 | 要能看出它把一次性迁移拆成「扩展-收缩」两阶段：可空列 → 带 WHERE 的分批回填 → `CREATE INDEX CONCURRENTLY`，以及 `SET NOT NULL` / `DROP COLUMN` 留到 0044。规则号 `SM001`/`SM003`/`SM006` 最好在画面里 |
| 5 | `5-ci-gate.png` | Captain（需 GitHub 账号操作一次 PR） | GitHub Actions 里 `release-gate` 这个 job 失败的运行记录 | 红色失败态、日志里 `门禁：不建议上线（有 high）`、以及 `release-report` artifact 那一栏。没有现成 CI 时可跳过此图，并把文章里图 5 的占位行一并删掉（不要留空图） |

## 硬性要求

- **脱敏**：画面里不得出现任何公司内部域名、系统名、仓库名、工单号、人名、头像昵称之外的身份信息。演示项目一律用 `orders-api` + `example.com`，仓库链接只出现公开的 `github.com/po-et/workbuddy-skills`。
- **过程 > 成品**：征集规则明确「只有成品无过程」不予收录，所以图 2 和图 4 必须是对话过程，不要只截最终报告。
- **真实**：不要重排或美化输出文字。文章正文引用的数字（13 / 9 / 22 → 0 / 8 / 21）必须和截图里一致；如果你在自己机器上跑出不同数字，告诉我，我改正文。
- 格式 PNG，宽度建议 ≥ 1200px，深浅色主题任选但五张保持一致。

## 复现演示项目的办法

文章第三节已列出 `orders-api` 的全部 11 个文件内容（`Dockerfile`、`k8s/*.yaml`、`migrations/0042_add_channel.sql`、`api/openapi.json` 与 `api/openapi.v1.json`、`.env.example`、`.env.production`、`app/config.py`）。需要我把这份演示项目落到一个可直接打开的目录（例如 `~/code/orders-api`）供你截图，说一声即可——它只在本机 scratchpad 里，不入库。
