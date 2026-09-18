# SkillHub 指标快照

目的：跟踪我们在 SkillHub（skillhub.cn）上 97 个已发布技能的下载/安装/收藏/评论等积累类 KPI，
每天存一份快照，方便按周对比增长。账号真实 handle `indiv-captain`（displayName
`user_a3a2e24a`，两者均由接口返回确认，非推测）。

## 结论先说：能拿到什么，拿不到什么

**能拿到（已用 2026-09-18 实测确认）：**

| 字段 | 说明 | 来源接口 |
|---|---|---|
| `downloads` 下载量 | 整数计数 | `GET /api/v1/skills/{slug}` -> `skill.stats.downloads` |
| `installs` 安装量 | 整数计数（目前观察到的技能几乎全是 0，因为 `skillhub install` 用得少） | 同上 -> `skill.stats.installs` |
| `stars` 收藏数 | 整数计数（页面上显示为"收藏"，不是 1-5 星评分） | 同上 -> `skill.stats.stars` |
| `comments` 评论数 | 整数计数 | 同上 -> `skill.stats.comments` |
| `versions` 版本数 | 该技能已发布的版本数 | 同上 -> `skill.stats.versions` |
| 是否进入搜索索引（可见性/上架） | 本仓库对"可见性"的操作定义，出处见 `docs/skillhub-growth.md`"82 个已发布技能 81 个进入搜索索引（=上架）" | `GET /api/v1/search?q={slug}`，看返回结果里 slug 和 namespace.handle 是否精确匹配 |
| AI 质量评测分 | 5 维度（adaptability/convention/effectiveness/reliability/trust）× 每维度 2-4 个子项，每个子项 1-5 分；网页技能详情页顶部显示的"★★★★☆ 4.5 优秀 (AI 评分)"就是这个分数的全部子项打平算术平均（已用 commit-message-cc 核对：15 个子项平均=4.5，页面显示也是 4.5，完全一致） | `GET /api/v1/skills/{slug}/evaluation`（非全部技能都已评测，未评测时 404） |
| 其它基础信息 | 展示名、分类、创建/更新时间、最新版本号、`claim_state`、`verified`、安全扫描状态（科恩/云鼎） | 同详情接口 |

**确认拿不到（不是没找对方法，是平台接口和网页都不提供）：**

- **查看量/浏览量（views/PV）**：CLI 全部子命令（`search` `skill rankings` `skill evaluation`
  `skill reports`）、三个被直接调用的原始接口（见下）、以及网页技能详情页（用浏览器实测
  `https://skillhub.cn/skills/indiv-captain/commit-message-cc`，页面只展示"14 次下载 / 0 次收藏 /
  tokens 预估消耗"，**没有任何"浏览/查看"计数**），都没有这个字段。据此判断 SkillHub 当前**不
  向开发者暴露浏览量**，不是我们权限不够或方法不对。
- **独立的 1-5 用户评分**：不存在"用户给技能打星"这种评分。唯一的"评分"是上面说的 AI 质量评测分，
  它评的是技能文档/脚本质量，不是用户满意度。`stars` 是收藏计数（可能几十几百），不是 1-5 分制。

如果以后确实需要浏览量这类数据，目前只有两条路，都不是本脚本能做的：

1. **问平台方**：在 open.workbuddy.cn / skillhub.cn 的开发者支持渠道询问是否有内部埋点数据可
   以开放；这属于"据公开信息推测不存在，但不能 100% 排除后台有、只是不对外"，需要平台方确认。
2. **浏览器人工核对**：定期打开每个技能详情页人工看一眼——但如上所述，页面本身也不显示浏览量，
   所以这条路目前**同样拿不到浏览量**，只能核对本脚本已抓到的下载/收藏数字有没有跑偏（页面渲染
   和接口是否一致）。这一步涉及登录态下的页面渲染，**需用户本人在浏览器里操作或明确授权**，本
   脚本不做浏览器自动化。

## 这些接口是怎么找到的，安全边界说明

`~/.local/bin/skillhub` 实际是个 12 行的 shell 包装，真正的 CLI 是
`~/.skillhub/skills_store_cli.py`（约 5800 行）。读它的源码可以确认：

- `skillhub search --json` 调用 `GET {host}/api/v1/search?q=...&limit=...`，但客户端函数
  `fetch_remote_search_results()` 把返回结果里的 `downloads/installs/stars` 等字段**过滤掉**了，
  只保留 slug/name/description/summary/version/namespace 再打印。
- `skillhub skill reports <slug> --json` 调用 `GET {host}/api/v1/skills/{slug}`，但命令实现
  `cmd_skill_reports()` 只从返回体里取 `securityReports`（科恩/云鼎安全报告）打印，其余字段
  （包括 `skill.stats.*`）被拿到了但没有打印出来。
- `skillhub skill evaluation <slug> --json` 调用 `GET {host}/api/v1/skills/{slug}/evaluation`，
  这个命令把完整响应体打印出来（外面套了层 `{"slug":..., "evaluation": {...}}`），是三个接口里
  唯一"整体透出"的。

也就是说，**下载/安装/收藏数不是 CLI 拒绝给、也不是需要更高权限才能看到的字段——它们本来就在
CLI 已经拿到的响应体里，只是 CLI 的这几个子命令在打印前把这些字段筛掉了**。本脚本没有绕过任何
鉴权：读 `cli_request_headers()` 可以确认，CLI 对这三个接口发请求时本来就**不带 Authorization**，
只带 `User-Agent` / 一个匿名 client-id / 调用方提示头；本脚本原样复现这几个请求头，不多加也不少加
任何鉴权信息。换句话说，这三个接口对已安装的 CLI 而言本来就是匿名可读的公开接口，本脚本只是直接
调用同一个接口、拿了 CLI 已经拿到但没打印全的字段，没有读取、使用或绕过登录令牌。

**局限**：这三个接口不是 SkillHub 公开 API 文档里正式列出的接口（据目前所知没有这样一份文档），
是从已安装 CLI 版本（2026.8.5）的实现细节里读出来的。平台没有对这几个接口的字段和稳定性做任何
承诺，未来可能变化而不通知；如果某天脚本大量报错或字段消失，先怀疑是接口变了，去重新读一遍
`~/.skillhub/skills_store_cli.py` 里对应的 `cmd_*` 函数。

## 快照怎么跑

```bash
# 全量：查 docs/submission-checklist.md「## SkillHub」小节里的全部 slug（目前 97 个）
python3 tools/metrics_snapshot.py

# 只查几个（调试/复核用）
python3 tools/metrics_snapshot.py --slugs commit-message-cc dev-workflow-pro

# 自定义输出路径
python3 tools/metrics_snapshot.py --out docs/metrics/skillhub-custom.csv

# 调试：只跑前 5 个，别真的查一遍全部
python3 tools/metrics_snapshot.py --limit 5
```

- 每个 slug 最多发 3 次请求（详情 / 搜索 / 评测），相邻两次请求间隔 **>= 1.3 秒**（`--sleep` 可调，
  但脚本会在低于 1.3 时打印警告）；全量跑一次（97 个 slug）大约 **7-9 分钟**。
- 输出是**追加写**：同一天多跑几次，`docs/metrics/skillhub-<日期>.csv` 里会有多行同一 slug、
  不同 `queried_at` 的记录，不会覆盖。如果只想留最后一次，按 `date + slug` 去重取最后一行即可
  （下面对比脚本示例已经这么做）。
- 详情接口查不到（404）的 slug，会跳过后面的搜索/评测两次请求（省配额），只记 `found=False` 和
  `error`。截至目前的实测，这只发生在 slug 从未真正创建成功的情况下，和"审核中/未过审"无关——
  已确认哪怕技能刚发布几小时、还在机器审核中，详情接口一样能查到真实的 downloads/installs 数字。
- 建议：每天固定跑一次（比如接入现有的"Sonnet 定时任务"机制），保留原始 CSV 不要删，长期趋势就是
  一堆按日期分文件的快照。

## 怎么按周对比

每份快照是独立的 `docs/metrics/skillhub-YYYY-MM-DD.csv`，同一 slug 跨文件按 `slug` 对齐即可算
增量。示例（纯标准库，不依赖 pandas）：

```python
import csv
from pathlib import Path

def last_snapshot(csv_path):
    """同一天可能追加了多次，同一 slug 只取最后一行"""
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    by_slug = {}
    for r in rows:
        by_slug[r["slug"]] = r  # 后面的覆盖前面的，保留最后一次
    return by_slug

old = last_snapshot("docs/metrics/skillhub-2026-09-18.csv")
new = last_snapshot("docs/metrics/skillhub-2026-09-25.csv")

for slug, new_row in sorted(new.items()):
    old_row = old.get(slug)
    if not old_row or not new_row["found"] or new_row["found"] != "True":
        continue
    d_downloads = int(new_row["downloads"] or 0) - int(old_row["downloads"] or 0)
    d_stars = int(new_row["stars"] or 0) - int(old_row["stars"] or 0)
    if d_downloads or d_stars:
        print(f"{slug:42s} downloads {old_row['downloads']:>4} -> {new_row['downloads']:>4} "
              f"({d_downloads:+d})   stars {old_row['stars']:>3} -> {new_row['stars']:>3} ({d_stars:+d})")
```

也可以偷懒直接 `csvdiff` / Excel / 表格工具按 `slug` 对齐两份 CSV 做减法，效果一样，脚本只是给个
起点。

## 字段说明（CSV 表头）

| 列 | 含义 |
|---|---|
| `date` / `queried_at` | 快照日期 / 本行实际查询时间（ISO8601，带时区） |
| `slug` / `skill_id` / `skill_id_source` | slug；skillId（优先取自 `docs/submission-checklist.md` 里发布时记的号，记录里没有的话退而取评测接口返回的 `skillId`；`skill_id_source` 标明取自哪里，`doc` 或 `evaluation`） |
| `found` / `http_status` / `error` | 详情接口是否查到、HTTP 状态码、报错信息 |
| `display_name` / `category` / `created_at` / `updated_at` / `latest_version` / `claim_state` / `verified` / `owner_handle` | 详情接口里的基础信息，`owner_handle` 应恒为 `indiv-captain` |
| `downloads` / `installs` / `stars` / `comments` / `versions_count` | 核心计数指标 |
| `in_search_index` / `search_checked` | 是否已进入搜索索引（可见性）；`search_checked` 为 False 表示这次搜索检查本身失败（超时等），不代表"确认不可见" |
| `has_evaluation` / `eval_skill_id` / `eval_adaptability` / `eval_convention` / `eval_effectiveness` / `eval_reliability` / `eval_trust` / `eval_overall` | 是否已被 AI 评测；各维度均值（该维度下所有子项 1-5 分的算术平均）；`eval_overall` 是全部子项打平后的算术平均，口径与网页星级一致 |

## 已知局限 / 待确认事项

- **AI 评测覆盖率并非 100%**：`docs/skillhub-growth.md` 2026-09-17 的记录是"AI 评测像定时批处理，
  先只覆盖了 26 个"；本次实测覆盖率已明显更高（见下方基线数字），说明评测在持续批处理，具体多久
  跑一轮、什么时候能覆盖全部 97 个——未知，需要连续几天快照才能观察出规律。
- **`in_search_index` 有假阴性风险**：判定方法是拿 slug 原文去查搜索接口、看返回结果里有没有
  slug 和 namespace.handle 精确匹配的项。如果某个技能确实在索引里、但搜索排序把它挤到 limit=5
  之外（比如 slug 本身是很常见的词），会被误判为"未进索引"。目前 97 个里没观察到这种情况（见基线
  数字），但样本还小，不能保证以后不会发生。
- **本次基线 CSV 的 `eval_overall` 用了两种口径中较早的一种**：写脚本时第一版按"先对每个维度的
  子项取均值、再对 5 个维度均值取平均"计算 `eval_overall`；跑完基线快照后才用网页实测发现页面显示
  的"AI 评分"星级实际是"全部子项打平直接取算术平均"（两种算法通常只差 0.0x，但不完全相同），随即
  把脚本改成了后一种、和页面一致的口径。**`docs/metrics/skillhub-2026-09-18.csv` 这份基线文件里的
  `eval_overall` 是修复前的旧口径**，各维度分项（`eval_adaptability` 等）不受影响、两版算法算出来
  的都一样。下一次快照开始会是修复后的新口径，两份文件的 `eval_overall` 不能直接跨口径比较，其余
  字段（downloads/installs/stars/comments/in_search_index）不受此问题影响，可以直接比。
- **接口是从 CLI 实现细节里读出来的，不是官方公开文档承诺的**，前面"安全边界说明"一节已展开。
- **`installs` 目前几乎全是 0**：应该是因为 `skillhub install <slug>` 这条本地安装路径用得少
  （大多数人通过"发送 prompt 给 AI 安装"或网页下载 zip），不代表接口有问题。

## 基线快照（2026-09-18）

文件：[`docs/metrics/skillhub-2026-09-18.csv`](./skillhub-2026-09-18.csv)。查询
`docs/submission-checklist.md`「## SkillHub」小节里记录的全部 **97 个** slug，耗时约 8 分钟。

| 指标 | 数值 |
|---|---|
| 查询 slug 总数 | 97 |
| 详情接口可查到 | 95（2 个查不到，原因已查清，见下） |
| 已进入搜索索引（可见/上架） | 95/95 = **100%** |
| **下载量合计** | **1084**（均值 11.4/个，中位数 11，最高 48，最低 0） |
| 安装量合计 | 0 |
| 收藏(stars)合计 | 0 |
| 评论合计 | 0 |
| 已被 AI 评测 | 95/95 = 100%（2026-09-17 记录还只有 26 个，评测批处理已基本追平发布量） |
| AI 评测分（旧口径，见下方局限说明） | 均值 4.51，范围 4.34–4.73 |

**安装量 / 收藏 / 评论目前全平台是 0**：说明这 97 个技能目前的用户互动还停留在"下载"这一步，
还没有人收藏、评论，也没有人用 `skillhub install` 走本地安装路径——这本身就是一个值得记录的
基线事实，不是脚本漏抓了字段（前面已确认这三个字段的接口路径和 downloads 是同一个响应体）。

**Top 10（按下载量）：**

| 下载量 | slug | 名称 |
|---:|---|---|
| 48 | `dev-workflow-pro` | 研发全能助手（伞形入口，符合"伞形技能吃搜索"的设计预期） |
| 26 | `diagnosing-bugs-zh` | Bug 诊断法 |
| 22 | `code-simplification-zh` | 代码化简（行为不变） |
| 16 | `grill-me-zh` | 需求盘问官 |
| 16 | `merge-conflicts-zh` | 合并冲突解决 |
| 16 | `api-design-zh` | API 与接口设计 |
| 16 | `deprecation-migration-zh` | 下线与迁移（扩展-收缩） |
| 15 | `changelog-keep` | Changelog 生成器 |
| 15 | `performance-optimization-zh` | 性能优化（先测量再优化） |
| 14 | `commit-message-cc` | Git 提交信息生成器 |

下载量为 0 的 2 个：`code-review-zh`（代码评审·双轴）、`pr-description`（PR 描述生成）。

**分类分布（`category` 字段，来自平台自动归类，不是我们自己设置的）**：`dev-programming` 56、
`ai-agent` 17、`it-ops-security` 15、`business-ops` 2、`knowledge-management` 2、其余 3 个类目各 1。

**两个查不到详情的 slug，已分别查明原因：**

1. **`triage-zh`**（`docs/submission-checklist.md` 记的 skillId 是 204663）：详情接口 404
   "Skill not found"。用 `skillhub search triage-zh` 核实后发现，`triage-zh` 这个 slug 现在属于
   **另一个账号** `@org-02qudk26/triage-zh`（企业组织号，不是我们），而我们的版本已改名发布为
   `issue-triage-zh`（在本次快照里 found=True，10 次下载，skillId 204759，与
   `docs/skillhub-growth.md` 里"slug 冲突两例（triage-zh → issue-triage-zh …）"的记录吻合）。据此
   判断：`submission-checklist.md` 第七批表格里那一行 `triage-zh | 204663 | 19:07:47` 很可能是当时
   冲突发布失败前/中的过程记录，没有清理掉，**这条记录本身有问题，不是本脚本或接口的问题**。
2. **`dockerfile-check`**（skillId 204761）：详情接口返回 **HTTP 566**，响应体是腾讯云 EdgeOne 的
   WAF 拦截页（"请求已被站点的安全策略拦截"）。用**官方 `skillhub` CLI**（`skillhub skill reports
   dockerfile-check`）直接复现了同样的 566，说明这不是本脚本请求方式的问题；另外用
   `skillhub search dockerfile-check` 确认这个技能确实在索引里、归属正确（`@indiv-captain`）。
   即：**这个 slug 的数据本身没有问题，只是详情接口这条路径当前被边缘安全策略拦了**，原因不明，
   建议下次快照重试；如果持续 566，需要找平台方反馈。

## 后续待办（未在本次任务范围内，留给下一次迭代）

- 目前只有 2026-09-18 这一份快照，还没有第二个时间点可以对比增长；下一次快照（建议 1 周后或
  接入每日定时任务）跑完就能看到第一组真实的周环比数字。
- `docs/submission-checklist.md` 里 `triage-zh` 那一行记录（skillId 204663）建议由维护该文档的人
  核实并更正/删除，本次任务范围只允许新增 `tools/metrics_snapshot.py` 和 `docs/metrics/` 下的文件，
  没有改动这份文档。
