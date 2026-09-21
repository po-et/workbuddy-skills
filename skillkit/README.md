# skillkit

技能作者的命令行工具箱：**起草 → 体检 → 打包 → 排期 → 看数据**。

纯 Python 标准库，零第三方依赖，Python 3.9+，macOS / Linux / Windows 通用。
写它的原因很简单：这些规则是我们发了一百多个技能、被平台拒了几十次之后攒出来的，
与其把经验写成一篇没人会照着做的文章，不如做成一条能跑的命令。

```
skillkit new      从模板生成技能骨架（必填字段一个不少，坑点写在注释里）
skillkit lint     格式校验 + 五维质量打分 + 逐条改进建议
skillkit build    生成发布副本，自动处理已知的拒收规则
skillkit doctor   发布前体检：能不能发
skillkit budget   发布配额与节奏规划
skillkit stats    查询上架技能的真实指标（downloads / stars / AI 评测分）
skillkit pitfalls 打印内置的平台规律表（区分实测 / 文档 / 推测）
```

---

## 安装

**方式一：clone 下来直接用**（不装任何东西，纯标准库）

```bash
git clone https://github.com/po-et/workbuddy-skills.git
cd workbuddy-skills
python3 -m skillkit --help
```

想在任何目录下都能跑，加个别名就行：

```bash
alias skillkit='python3 -m skillkit'          # 需要 cd 到仓库根目录
# 或者
alias skillkit='PYTHONPATH=/path/to/workbuddy-skills python3 -m skillkit'
```

**方式二：装成命令**

```bash
cd workbuddy-skills
pip install -e .        # 之后直接 `skillkit ...`
```

`pyproject.toml` 在仓库根目录，只打包 `skillkit/` 这一个包，不会把 `skills/`、`tools/` 一起装进去。
没有任何运行时依赖，`pip install` 不会拉任何东西。

**跑测试**

```bash
python3 -m unittest skillkit.tests.test_cli -v
# 或
python3 -m unittest discover -s skillkit/tests -t .
```

68 个用例，覆盖每个子命令的正常路径与异常路径。测试全程不联网：
唯一涉及网络的 `stats` 把 HTTP 层换成假函数，并额外把 `urllib.request.urlopen` 换成
「一被调用就断言失败」，保证任何情况下都不会打到真实接口。

---

## 子命令

每个子命令都有 `--help`，输出中文。下面的输出都是真跑出来的，没有手改。

### skillkit new —— 生成骨架

```bash
$ skillkit new my-log-triage --dir skills --author Captain
创建 skills/my-log-triage/SKILL.md
创建 skills/my-log-triage/scripts/my_log_triage.py

注意：骨架刚生成就能拿到不低的 lint 分数 —— 那是**结构分**，说明模板形状对，不代表内容写好了。占位符不换掉，分数是假的。

接下来：
  1. 把 SKILL.md 里所有「（…）」占位符换成真内容，注释可以留着也可以删
  2. skillkit lint skills/my-log-triage        # 看格式有没有 FAIL、五维分多少
  3. skillkit doctor skills/my-log-triage      # 发布前最后一道：能不能发
  4. skillkit build skills/my-log-triage --out dist/skillhub --slug <全网唯一的 slug>
```

模板里 frontmatter 的每个字段都带注释，写清楚它是谁要求的、不填会报什么错。
例如：

```yaml
# display_name / display_name_en 官方文档里没写，是实测报错逼出来的。
...
# 每种语言**最多 3 条**，第 4 条会被解析器直接拒掉。显示为「试试这样问我」。
examples_zh:
  - "（用户会怎么问，第 1 条）"
```

### skillkit lint —— 校验 + 打分

```bash
$ skillkit lint skills/dockerfile-check
skills/dockerfile-check                         85 分  可发现性 17  结构 13  可执行性 20  合规 20  示例 15  0F/1W
    [WARN] 提醒：同名技能已存在于平台时须走草稿「编辑」重传，且 version 必须大于线上/草稿版本
    → tags 建议 6–12 个，中英混合含缩写
    → 正文缺『边界』一节
    → 正文仅 1471 字符，可能太薄
    → 示例与 description 关键词对不上，容易误触发

================================================================
1 个技能：0 FAIL / 1 WARN；平均 85.0 分，最低 85，最高 85
```

传上层目录会递归找 `SKILL.md`；`--quiet` 只打印有问题的：

```bash
$ skillkit lint skills/ --min 70 --quiet
全部 81 个技能都没有 FAIL，也都达到了 70 分门槛。
```

**五个维度**各 20 分：可发现性（description 是否说清什么时候用、触发词与同义词、tags 数量）、
结构（何时用 / 流程 / 产出 / 边界四节、篇幅）、可执行性（命令块、引用的脚本真的存在）、
合规（必填字段、无扩展名文件、复刻有 ATTRIBUTION、无密钥）、示例（数量与描述一致性）。

**FAIL 与 WARN 的区别**：FAIL = 按实测传上去会被拒或解析失败；WARN = 不会被拒，但影响展示、
审核或后续重传。退出码只受 FAIL 与 `--min` 影响，所以可以直接当 CI 门禁：

```bash
skillkit lint skills/ --min 70 --json > lint.json || exit 1
```

### skillkit build —— 生成发布副本

```bash
$ skillkit build skills/dockerfile-check skills/iteration-report \
    --out dist/skillhub --homepage https://github.com/po-et/workbuddy-skills
OK   skills/dockerfile-check                 ->  dist/skillhub/dockerfile-check
OK   skills/iteration-report                 ->  dist/skillhub/iteration-report

2 个技能，0 个有 FAIL
发布前先跑一次 `skillkit doctor`；失败的发布请求一样消耗配额。
```

产出的 `SKILL.md` 头部：

```yaml
---
slug: dockerfile-check
displayName: "Dockerfile 体检"
version: 0.1.2
summary: "一条命令给 Dockerfile 做体检：17 条最佳实践与安全规则，分级输出并附具体改法；纯 Python 标准库，可作 CI 门禁。"
license: MIT
homepage: https://github.com/po-et/workbuddy-skills
name: dockerfile-check
description: Dockerfile 体检、Dockerfile 最佳实践检查、镜像瘦身……
author: Captain
display_name: "Dockerfile 体检"
...
```

**源目录一个字节都不动。** SkillHub 用 `slug / displayName / summary`，开放平台用
`name / display_name / description_zh`，两套并存在同一份 frontmatter 里目前没出过事，
但把 SkillHub 专用字段写回源目录，等于让源目录同时伺候两个平台的口径。

自动处理掉的东西：删 `LICENSE / NOTICE / ATTRIBUTION / COPYING`（无扩展名文件实测 400），
清 `__pycache__` 与 `.pyc/.pyo/.pyd`，去掉源 frontmatter 里重复的 `version` / `tags`。

改 slug：`--slug`（单个）、`--tags`，或批量用 `--map`：

```json
{ "iteration-report": { "slug": "iteration-report-git", "tags": ["周报", "迭代汇报", "Git"] },
  "json-diff": "json-config-diff" }
```

`--dry-run` 只算不写，用于发布前预检。

### skillkit doctor —— 能不能发

```bash
$ skillkit doctor ./dns-check --min 70
================================================================
./dns-check  [不要发]  93 分  slug=dns-check
  可发现性 17  结构 20  可执行性 20  合规 16  示例 20
  ✗ 缺少 display_name_en（文档未记载，但解析器强制：「缺少 Skill 英文展示名」）
  ✗ version 应为 x.y.z: '0.1'
  ! 提醒：同名技能已存在于平台时须走草稿「编辑」重传，且 version 必须大于线上/草稿版本
  ! 技能包内含 LICENSE（SkillHub 实测拒收无扩展名文件；skillkit build 会自动删掉它，许可证写进 frontmatter 的 license 字段）
  ! 建议字段缺失: homepage
  → tags 建议 6–12 个，中英混合含缩写
  → 无扩展名文件会被 SkillHub 拒绝: LICENSE
  build 时会删掉（平台拒收）：LICENSE
================================================================
1 个技能：0 个可以发，1 个不要发（门槛 70 分）
不要发：dns-check

提醒（都是实测踩出来的）：
  · 一次成功解析就会在服务端创建草稿并占用 name；重传必须先递增 version，草稿版本也算数（实测）
  · SkillHub 的 slug 全网唯一，先到先得；冲突时只能换名重发，重试没用（实测）
  · 失败的发布请求一样消耗配额 —— 不要拿线上额度当 linter（实测）
  · 遇「发布频率过高」对同一项等 10/20/40 分钟重试；连续三次被限判定配额耗尽，停止本轮（实测）
```

`doctor` = `lint` + `build --dry-run`，三种结论：**可以发** / **可以发，但先看下面的提醒** / **不要发**。
退出码：可以发 0，不要发 1。

这个命令存在的理由只有一条实测规律：**失败的发布请求一样消耗配额**。线上额度不是 linter。

### skillkit budget —— 发布节奏

```bash
$ skillkit budget --count 40 --used 12 --start 2026-09-21T20:00:00 --no-bash
SkillHub 发布节奏规划
====================================================
待发 40 个 | 最近 24 小时已发 12 次 | 配额上限 100（推测值，需确认，--cap 可调）
单次间隔 75 秒 | 安全余量 10 次 | 单批上限 25 个 | 批间隔 60 分钟 | 滚动窗口 24 小时（推测）

本轮可发：40 个（可用额度 = 100 - 已用 12 - 余量 10 = 78）
需要分 2 批，预计 2026-09-21T21:47:30 发完

批次计划
----------------------------------------------------
  批    个数  开始                   结束                      耗时(分)
  1    25  2026-09-21T20:00:00  2026-09-21T20:30:00      30.0
  2    15  2026-09-21T21:30:00  2026-09-21T21:47:30      17.5

批间留 60 分钟不是为了礼貌——是为了不在几小时内把滚动窗口打满。
一晚上打满的代价是第二天同一时段之前你什么都发不了。

遇限流怎么办（退避策略）
----------------------------------------------------
1. 正常节奏：每次发布间隔 75 秒。
2. 报「发布频率过高」→ 对**同一项**等 10 分钟重试，**不要跳过去发下一个**。
   跳过只会更快耗尽剩余额度，还把队列顺序搞乱。
3. 再失败 → 依次等 20、40 分钟。
4. 连续 3 次都被限 → 判定配额耗尽，**停止本轮**，
   记下停在哪一项，等窗口释放后从那一项继续。
5. 409 slug 冲突 / 400 文件类型 / 版本号未升 → 这些不是限流，重试没用，改包。

先跑一遍 `skillkit doctor` 再进队列——失败的请求一样烧配额。
```

配额用满时它会直接告诉你别试：

```bash
$ skillkit budget --count 5 --used 95 --start 2026-09-21T20:00:00 --no-bash
...
本轮可发：0 个（可用额度 = 100 - 已用 95 - 余量 10 = 0）

** 配额已用满，本轮一个都发不了。**
   现在发出去的请求只会失败，而失败的请求一样消耗配额——不要试。
   最早可继续时间（保守估计）：2026-09-22T20:00:00
   ...
   试探方法：拿一个**已发布过、内容未改、只升补丁版本号**的对照技能去发，
   通了说明窗口已放行，再开始正式队列。
```

去掉 `--no-bash` 会附一段可直接用的发布循环（串行、限流退避、记 skillId、失败不跳项），
`--out publish.sh` 可以直接写文件。

### skillkit stats —— 真实指标

```bash
$ skillkit stats commit-message-cc dev-workflow-pro --namespace indiv-captain
slug                                   downloads  installs   stars  comments     AI分 搜索索引
------------------------------------------------------------------------------------------------
commit-message-cc                             31         0       0         0     4.5 已收录
dev-workflow-pro                              81         0       0         0     4.4 已收录
------------------------------------------------------------------------------------------------
查到 2/2；下载合计 112，收藏合计 0
说明：downloads 极可能约等于「Agent 自动调用次数」而非人工点击下载（推测，需确认）；stars 是收藏计数，不是 1–5 星评分；浏览量平台不提供。
```

为什么要自己发请求：`skillhub search` 的客户端函数会把结果里的 `downloads / installs / stars`
**过滤掉**，只留 slug/name/description/summary/version/namespace；`skill reports` 拿到了完整响应体，
却只打印安全扫描字段。这些数字本来就在响应里，是 CLI 打印前筛掉的。本命令直接 GET 同一批
只读接口（`/api/v1/skills/{slug}`、`/api/v1/search`、`/api/v1/skills/{slug}/evaluation`），
请求头与官方 CLI 对这几个接口的请求方式一致 —— 只有 `Accept` 与 `User-Agent`，**不带任何鉴权头**。

`--csv` 可以把结果按天追加进 CSV 做趋势；`--no-search` / `--no-eval` 少发请求。

### skillkit pitfalls —— 规则表

```bash
$ skillkit pitfalls --confidence 推测
================================================================
[推测（需确认）] publish-quota-rolling
  现象    ：发布频率过高；换未改动的对照技能也拦
  规则    ：发布限额不是按自然日重置。09-17 约第 100 次成功发布后全面拦截，+1h、+14.5h（跨本地日与 UTC 日）再试仍拦，同期读接口正常
  证据    ：2026-09-17/18 实测；「滚动 24 小时窗口、上限约 100 次」是最符合的解释
  skillkit：budget 用 --cap/--window 建模，两个默认值都标注为推测值
...
共 2 条。标「推测」的没有被平台确认过，不要当事实引用。
```

---

## 这个工具替你避开的坑

下面每一条都标了**置信度**：
「实测」= 我们自己被拒/被接受过，有报错原文；「文档」= 平台文档写明；
「推测（需确认）」= 从现象反推，平台没确认过，**别当事实用**。
完整表在 `skillkit/rules.py` 的 `PITFALLS`，`skillkit pitfalls --json` 可机读。

### 打包与上传

| 坑 | 规则 | 置信度 | skillkit 的处理 |
|---|---|---|---|
| 上传 400「不允许的文件类型: LICENSE」 | SkillHub 拒收**无扩展名文件**，许可证只能写进 frontmatter 的 `license` | 实测 | `build` 自动删 LICENSE/NOTICE/ATTRIBUTION/COPYING；`lint` 对其它无扩展名文件给 WARN |
| 解析失败「缺少 Skill 中/英文展示名」 | `display_name` / `display_name_en` **官方文档没写**，解析器强制；`description` / `description_zh` / `description_en` / `version` 同样必填 | 实测 | `new` 模板预置全部字段；`lint` 缺任一项判 FAIL |
| `mapping values are not allowed in this context` | 平台用**严格 YAML**：未加引号的标量里出现「: 」直接炸，必须整体加双引号 | 实测 | `lint` 逐行扫描并指出行号 |
| 「包内版本号 0.1.0 必须大于当前最新版本 0.1.0」 | 一次成功解析就在服务端建草稿并占用 `name`，重传必须先递增 `version`，**草稿版本也算数** | 实测 | `lint` / `doctor` 恒定提醒 |
| 「examples_zh 最多 3 个示例，当前 4 个」 | 每种语言最多 3 条 | 实测 | `lint` 超过判 FAIL，缺失给 WARN |
| version 校验不过 | 只接受三段式 `x.y.z` | 文档 | `lint` / `build` 同一个正则 |
| ClawHub 发布被拒 | ClawHub 拒收 `.pyc/.pyo/.pyd`（扫描器解析不了字节码），但**接受**无扩展名文件 —— 和 SkillHub 正好相反 | 文档 + 实测 | `build` 统一清掉 `__pycache__` 与字节码 |

### 发布配额

| 坑 | 规则 | 置信度 | skillkit 的处理 |
|---|---|---|---|
| 「发布频率过高」，换未改动的对照技能也拦 | 限额**不按自然日重置**。约第 100 次成功发布后全面拦截，+1h、+14.5h（跨本地日与 UTC 日）再试仍拦，同期读接口正常 | **推测（需确认）**：「滚动 24 小时窗口、上限约 100 次」是最符合的解释，平台不返回配额字段 | `budget` 用 `--cap` / `--window` 建模，默认值明确标注为推测值 |
| 本地没校验就发，几次失败后额度见底 | **失败的请求一样消耗配额** | 实测 | `doctor` 就是为这条存在的 |
| 被限流后跳过去发下一个 | 要对**同一项**等 10 / 20 / 40 分钟重试；连续三次被限判定配额耗尽，停止本轮 | 实测 | `budget` 生成的 bash 模板内置这套退避，且不跳项 |
| 409 slug 冲突 | slug **全网唯一**，先到先得；重试没用，只能换名 | 实测 | `build --slug` / `--map` 换名；建议带用途后缀 |

### 数据与增长

| 坑 | 规则 | 置信度 | skillkit 的处理 |
|---|---|---|---|
| 官方 CLI 看不到下载量 | `downloads/installs/stars` 本来就在响应体里，是 CLI 打印前筛掉的；直接 GET 详情接口就能拿到（该接口对 CLI 本身也是匿名可读） | 实测（读 CLI 源码确认） | `stats` 直接走详情接口，不加任何鉴权头 |
| 想看浏览量 | 平台**不提供** PV：三个只读接口、排行榜字段表、网页详情页都没有；`stars` 是收藏计数，不是 1–5 星评分 | 实测（接口 + 网页双向核对） | `stats` 只报接口真返回的字段，不编派生指标 |
| 上架很久没量，新技能 4 天进前百 | `downloads` 极可能约等于「**Agent 自动调用次数**」，决定量级的是描述**触发面**有多宽，不是上架时长（前 100 样本相关系数 r = 0.06） | **推测（需确认）** | `lint` 的「可发现性」维度量的就是这件事 |
| 为了流量把接不住的场景写进触发面 | 触发面里的每一类场景，正文必须有对应处理方法；写不出方法的场景不许写进去 | 自设规则 | `lint` 检查示例与 description 关键词是否对得上 |

最后一条不是技术问题。把描述写成**准确覆盖技能真正能处理的场景**、并让 Agent 认得出来，
是正当优化；把技能接不住的场景也写进触发面去截流量，是骗调用 —— 用户被路由到一个帮不上忙的
技能，损害的是作者信誉和整个生态。这条规则 skillkit 只能提醒，管不住，靠你自己。

---

## 代码结构

```
skillkit/
├── __init__.py         版本号与总览
├── __main__.py         python3 -m skillkit 入口
├── cli.py              argparse 装配与分发，不含业务逻辑
├── rules.py            规则表与平台常量 —— 全工具唯一的真相源，含坑点表
├── frontmatter.py      frontmatter 切分 / YAML 子集解析 / 最小改动式改写
├── skillpkg.py         Skill 对象：装载、字段读取、文件遍历、目标解析
├── checks.py           格式校验（FAIL / WARN / PASS）
├── scoring.py          五维打分
├── template.py         new 用的骨架模板
├── output.py           JSON 输出、宽字符对齐、路径截断
├── commands/           每个子命令一个模块，只暴露 add_parser / run
│   ├── new.py  lint.py  build.py  doctor.py  budget.py  stats.py  pitfalls.py
├── tests/test_cli.py   68 个 unittest 用例
└── README.md
```

两条硬约束，改代码时请守住：

1. **规则只写在 `rules.py`。** 子命令里不许出现魔法数字、内联正则、硬编码的报错文案来源。
2. **frontmatter 只经 `frontmatter.py`。** 不许在别处再写一遍 `^---\n(.*?)\n---\n` 这种正则。

## 与仓库里原有脚本的关系

skillkit 是把 `tools/skillhub_prep.py`、`tools/check_package.py`、
`skills/skill-lint/scripts/skill_lint.py`、`skills/skillhub-field-guide/scripts/publish_budget.py`、
`tools/metrics_snapshot.py` 这几份脚本的能力抽出来重组的，**不是复制粘贴**：
frontmatter 解析、YAML 子集读写、规则表都只剩一份实现。

行为一致性是逐条验过的（2026-09-21，仓库内 81 个真实技能）：

| 对照 | 范围 | 结果 |
|---|---|---|
| `lint` 打分 vs `skill_lint.py` | 81 个技能 | 总分、五个分项、建议文案**全部一致**（0 处差异） |
| `lint` 校验 vs `check_package.py` | 81 个技能 | FAIL 与 WARN 集合**全部一致**，退出码一致 |
| `build` vs `skillhub_prep.py` | 81 个技能 | 产出目录 `diff -r` **零差异**（需用 `--map` 传入 prep 内置的 slug/tags 表） |
| `budget` vs `publish_budget.py` | 6 组参数 | 规划 JSON **完全相同** |
| `stats` vs `metrics_snapshot.py` | 2 个真实 slug | downloads / installs / stars / comments / 索引 / 评测分**全部相同** |

已知的有意差异（都是「多做一点」，不改变 FAIL 集合与退出码）：

- `lint` 对 LICENSE 之外的无扩展名文件也给 WARN（`check_package.py` 只针对 LICENSE）；
- `build` 额外清理 `.pyo/.pyd`（`skillhub_prep.py` 只清 `.pyc`），并在 `tags` 为空时省略该字段，
  而不是写一个悬空的 `tags:`；
- `build` 的 `license` / `homepage` 不再硬编码成本仓库地址，改成 `--license` / `--homepage` 参数
  （缺 homepage 时给 WARN）—— 这是为了让外部作者能用。

`tools/` 下的脚本还在被真实发布流程使用，skillkit **没有改动它们**。

## 许可

MIT。
