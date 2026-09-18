---
name: skillhub-field-guide
description: SkillHub 发布配额、slug 抢注、文件格式与指标口径的实测避坑指南。当用户说「一天能发多少个技能」「发布频率过高怎么办」「配额多久才恢复」「是不是按天重置」「slug 被别人抢注了怎么改名」「400 不允许的文件类型」「frontmatter 解析失败」「版本号必须大于」「技能上架了没」「AI 评分一直查不到」「下载量怎么看」「要往 SkillHub 批量发技能」「帮我排个发布计划」时使用。附发布节奏规划器 scripts/publish_budget.py，输入待发数量与最近 24 小时已用次数，输出本轮能发多少、分几批、每批起止时间、限流退避策略，以及一段可直接跑的 bash 发布循环。所有配额数字均为实测基础上的推测值，需确认。
author: Captain
version: 0.1.0
display_name: "SkillHub 发布避坑指南"
display_name_en: "SkillHub Field Guide"
description_zh: "把 SkillHub 两天 97 次发布实测出来的规律做成可执行清单：发布前检查文件格式与 frontmatter、slug 怎么取名躲开抢注、配额怎么做预算与分批、限流怎么退避、下载量与 AI 评分怎么读才不自欺。附纯标准库的发布节奏规划器。"
description_en: "Field-tested playbook for publishing to SkillHub, distilled from 97 real publishes: pre-flight file and frontmatter checks, slug naming that dodges squatting, publish-quota budgeting and batching, throttle backoff, and how to read downloads and AI scores honestly. Ships a stdlib publish-pacing planner."
examples_zh:
  - "一天能发多少个技能，帮我按配额排个发布节奏"
  - "发布频率过高怎么办，等多久才能继续发"
  - "slug 被别人抢注了怎么改名，顺便帮我看发布前还要检查什么"
examples_en:
  - "How many skills can I publish today? Plan the batches for me"
  - "I hit the publish rate limit — how long until it clears?"
  - "My slug is taken. Rename it and check what else blocks publishing"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧭" } }
---

# SkillHub 发布避坑指南

2026-09-16 到 09-18，一个个人账号往 SkillHub 发了 97 个技能，撞了四堵墙。这个技能把那些墙变成发布前就能查、发布中就能算的清单。

**先说边界：下面所有关于「配额上限 100」「滚动 24 小时窗口」的数字都是推测值，需确认。** 平台不在响应里返回任何配额字段，我们只能从被拦的行为反推。凡是标了「推测」的，请当成默认参数而不是事实。

## 何时用

- 准备一次发多个技能，想知道今天能发几个、怎么排；
- 已经撞上「发布频率过高」，想知道等多久、要不要跳过当前这个；
- 上传报 `400 不允许的文件类型`、frontmatter 解析失败、版本号被拒；
- 想取的 slug 提示已被占用，需要一个既避开冲突又不牺牲可发现性的命名策略；
- 看到下载量涨了，想判断这是真需求还是平台基线；
- 分不清「上架了」和「AI 评测出分了」。

不适合：写技能内容本身（那是 skill-lint 的事）、处理账号登录与实名（只能你本人做）。

## 发布前检查清单

三条硬约束，全是被平台打回来才知道的。**失败的请求一样消耗配额**，所以这一步必须在本地做完。

### 1. 文件格式

- **无扩展名文件会被拒收**。目录里有 `LICENSE`、`NOTICE` 这类文件就报 `400 不允许的文件类型: LICENSE`。许可证只写进 frontmatter 的 `license` 字段。实测可通过的类型：`.md` / `.py` / `.yaml` / `.csv`。
- 顺手清掉 `__pycache__`、`.pyc`、`.DS_Store`。

### 2. frontmatter

- 平台用**严格 YAML** 解析。未加引号的值里出现半角冒号加空格（`: `）会直接报 `mapping values are not allowed in this context`。**整个值用双引号包住**，或改用全角冒号。
- 必填（解析器强制）：`version`（SemVer）、`display_name`、`display_name_en`、`description_zh`、`description_en`；SkillHub 侧另需 `slug`、`displayName`。
- **同 slug 重传必须升版本号**，版本号不大于线上或草稿的最新版本会被拒。批量重发前先统一自增。

### 3. slug 选名策略

热门英文名的 `-zh` 形式是重灾区。复刻 superpowers 系列 10 个，**8 个的 `-zh` slug 已被他人占用**，只能改名（`brainstorming-zh` → `brainstorming-spec-zh`、`writing-plans-zh` → `writing-impl-plans-zh`、`using-git-worktrees-zh` → `git-worktree-workflow-zh` 等）。

策略：**加一个说明用途的限定词**。`brainstorming-spec-zh` 比 `brainstorming-zh` 既避开了冲突，语义也更准——这不是退而求其次。

还有一个反直觉的点：**slug 并不是全网强唯一的**。我们有 3 个 slug 与其他账号的技能同名并存（推测与早期渠道导入的历史数据有关，需确认）。后果是**光搜 slug 关键词会搜到别人的技能**，判断"我的上架了没"必须用 `slug + namespace.handle` 精确匹配。注意 handle 不一定等于页面上显示的名字。

### 一条命令跑完前置校验

```bash
python3 tools/check_package.py skills/<你的技能>          # 文件格式 + frontmatter + 密钥扫描
python3 skills/skill-lint/scripts/skill_lint.py skills/<你的技能> --min 85
skillhub publish <目录> --host https://api.skillhub.cn --dry-run   # dry-run 不需要登录
```

## 发布节奏规划

### 配额的真实行为

**不是按日重置。** 09-17 约第 100 次成功发布后全面拦截；此后 +1 小时、+14.5 小时（本地日与 UTC 日都已翻篇）再试仍报「发布频率过高」，**连一个字都没改的对照技能也被拦**；同期读操作（搜索、评测查询）完全正常，**与令牌无关**。

最符合的解释：**滚动 24 小时窗口，上限约 100 次**——推测，需确认。

单次间隔 **75 秒**基本够用；接近配额上限时会偶发限流，重试要等 **10 分钟**级别。

### 第 1 步：算预算

```bash
python3 {baseDir}/scripts/publish_budget.py --count 40 --used 12
```

`--count` 待发数量，`--used` 最近 24 小时已成功发布的次数。可调参数：`--cap 100`（配额上限，推测值）、`--window 24`（窗口小时数，推测值）、`--interval 75`、`--reserve 10`（留给重试）、`--batch-size 25`、`--batch-gap 60`。

### 第 2 步：看分批计划

输出包含：本轮能发多少（`可用额度 = cap - 已用 - 余量`）、分几批、每批的起止时间、排不下的有多少、最早什么时候能继续。

**批间留 60 分钟不是礼貌，是为了不在几小时内把窗口打满。** 一晚上打满的代价是第二天同一时段之前你什么都发不了。

配额已用满时，脚本会直接告诉你"本轮一个都发不了"，并给出试探方法：**拿一个已发布过、内容未改、只升了补丁版本号的对照技能去试**，通了说明窗口已放行。这个对照技能同时也是排除"是不是我包有问题"的实验手段。

### 第 3 步：拿 bash 循环去发

```bash
python3 {baseDir}/scripts/publish_budget.py --count 40 --used 12 --out publish.sh
bash publish.sh          # 填好 SKILL_DIRS 之后
python3 {baseDir}/scripts/publish_budget.py --count 40 --json   # 给程序用
```

生成的循环是串行的，自带退避：报「发布频率过高」→ 对**同一项**等 10、20、40 分钟重试，**不跳过去发下一个**（跳过只会更快耗尽额度还打乱队列）；连续 3 次仍被限 → 判定配额耗尽，整轮停下，记下停在哪一项。409 slug 冲突、400 文件类型、版本号未升这些不是限流，重试没用，改包。

### 输出与验收

- `publish-log.csv`：每行 `time,dir,result,skill_id,note`，`result` 取 `ok` / `fail` / `quota_exhausted`。
- 验收标准：`ok` 的行数 == 计划发布数；出现 `quota_exhausted` 说明配额预算估低了，把 `--used` 按实际发生数重算再排下一轮。
- 上架判定：用搜索接口按 `slug + namespace.handle` 精确匹配，命中即已进索引。

## 指标解读的三个陷阱

**陷阱一：以为 CLI 拿不到下载量。** 官方 CLI 的 `search` / `skill reports` 子命令会把 `downloads` / `installs` / `stars` / `comments` / `versions` 这些字段**过滤掉不显示**，但它们本来就在 `GET /api/v1/skills/{slug}` 的 `stats` 里。想看就直接读详情接口。顺带一提：**查看量 / 浏览量平台不提供**，CLI、接口、网页详情页三处都没有这个字段。

**陷阱二：把 AI 评测当上架。** 这是两条独立的流水线。机器审核通过进搜索索引就算上架；AI 评测报告是另一条慢得多的批处理。实测抽查 82 个技能：**81 个已进索引（唯一那个"未可见"经复核是自己的记录残留，实际 82 个全部进了索引），无一被拒；同一时刻 AI 评测只完成 26 个**。第二天再查，评测覆盖率已是 100%。**看到评测 404 不要慌，那不是被拒。**

**陷阱三：把累计下载量当需求信号。** 95 个技能累计 1084 次下载，中位数 11，**88 个（92.6%）挤在 6–20 区间**；上架时长与下载量的相关系数 r = 0.41（Spearman 0.59），而 AI 评分与下载量 r = −0.13，基本无关；安装、收藏、评论三项**全部为 0**。

分布这么集中、又和内容特征对不上，**判断当前的累计下载量主要由上架时长与平台基线抓取驱动，不足以证明真实用户需求差异**（"平台基线抓取"这一条是推测，需确认——没有任何来源维度的数据能证实）。

**所以：看每日增量，不要看累计值。** 累计值里混着一个随时间线性增长的基线，读不出"哪个技能更受欢迎"。第一天就把快照接上定时任务，原始 CSV 一份别删，真正有价值的数字是第二份快照减第一份。

## 边界

- **不做**发布动作本身。脚本只生成计划和模板，`skillhub publish` 由你在自己的终端执行。
- **不经手** API Token。登录、实名、创建 token 全在你的终端完成。
- 配额上限、窗口长度、分桶方式（按账号还是按 IP）、失败请求是否计数——**都没有平台侧确认**，默认值只是当前最佳猜测，请按自己的实测调 `--cap` 和 `--window`。
- 本指南的观测接口是从已安装 CLI 的实现细节里读出来的，不是官方公开文档承诺的，随时可能变。脚本大面积报错时，第一怀疑对象是接口变了。
- 样本只有一个个人账号、97 个 slug、两天、一份快照。不要当成平台的普遍规律。

## 常见问题

**等了一小时还是发不了？** 正常。窗口按最早那次消耗起算，不按自然日。用对照技能试探，别硬发——失败请求一样烧配额。

**409 slug 已被占用？** 加限定词重取，别在原名上加数字后缀。

**发布成功但详情页查不到？** 机器审核中，正常，等进索引。

**搜到的是别人的同名技能？** slug 不是全网强唯一，用 handle 精确区分。

---

配套工具：`tools/skillhub_prep.py`（生成发布副本）、`tools/check_package.py`（提交前校验）、`tools/record_skillids.py`（记录 skillId）、`tools/metrics_snapshot.py`（每日指标快照）。完整实验记录见仓库 `docs/articles/04-实测-SkillHub-的发布配额-抢注与指标口径.md`。

本技能与脚本开源：https://github.com/po-et/workbuddy-skills
