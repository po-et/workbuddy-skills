---
name: skill-author-expert
description: "技能作者.Skill——服务想把技能发到 SkillHub、OpenClaw 这类技能市场的人，从选题一直覆盖到上架后看数据。只要用户的问题涉及技能的选题、编写、打包、发布与上架运营，即应触发本技能，无需用户明确指定。无论是不知道做什么题目、想知道这个题有没有人要、SKILL.md 每个字段填什么、描述怎么写才会被 Agent 自动调用、名字和 slug 撞了、上传报 400、frontmatter 解析失败、版本号被拒、发布频率过高、一天能发几个、发了两天没人下载、评测查不到、要不要升版本、被拒了怎么改，都从这里进。当用户说 发技能、上架、发布、技能市场、SkillHub、slug、抢注、撞名、frontmatter、打包、配额、限流、审核、AI 评分、下载量、收藏、触发面、描述、examples、tags、版本号、changelog、被拒 等任一说法时使用；本页的平台规律全部出自两天 97 次真实发布的实测，推测的一律标注。"
author: Captain
version: 0.1.1
display_name: "技能编写"
display_name_en: "Skill Author.Skill"
description_zh: "把技能从选题做到上架的整条链路做成清单：怎么判断题目有没有人要、SKILL.md 与 frontmatter 逐字段怎么填、描述与触发面怎么写、slug 撞名怎么办、打包与发布配额的坑、上架后看哪个数、版本与更新策略、常见被拒原因；附两天 97 次真实发布实测出的平台规律。"
description_en: "A complete checklist for shipping a skill to a marketplace—picking a topic with real demand, filling every SKILL.md frontmatter field, writing a description that actually triggers, dodging slug squatting, packaging and publish-quota traps, reading post-launch metrics, versioning, and the usual rejection reasons—backed by 97 real publishes."
tags:
  - "技能开发"
  - "SKILL.md"
  - "SkillHub"
  - "技能发布"
  - "触发面设计"
  - "slug 命名"
  - "发布配额"
  - "上架数据"
examples_zh:
  - "我想发技能到 SkillHub，这个题目有没有人要"
  - "上传报 400，frontmatter 解析失败，帮我查哪里不合规"
  - "发布频率过高，一天到底能发几个，帮我排节奏"
examples_en:
  - "I want to publish a skill—does this topic have real demand?"
  - "Upload returns 400 and the frontmatter fails to parse. What's wrong?"
  - "I hit the publish rate limit. How many can I ship today?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📦" } }
---

# 技能作者

定位一句话：**一个技能能不能被用，先看它会不会被选中；技能市场上拼的不是功能多，是描述准、包能过、名字不撞、数据看得懂。**
这一页覆盖技能作者的整份工作，从「做什么题」一直到「上架第三天该看哪个数」。

## 何时用

要开一个新技能、要改一个没人用的技能、包传不上去、配额被拦、想知道上架了没、想知道数据是不是真需求——先在下表对号入座。
表里的子技能装了就直接调用，没装就照本页的精简方法做，并告诉用户可以在市场里搜对应 slug 安装。

## 五步顺序（不要跳）

```
1 选题  同题有没有人做、我能不能做得更好 → 做不出差异就换题，别做第 12 个同题
2 写包  骨架四节（何时用 / 流程 / 输出契约 / 不做什么）+ frontmatter 逐字段填满
3 自检  本地跑完两把尺，一条 FAIL 都不许带上去，失败的上传也可能白烧配额
4 发布  按配额排队分批，撞限流就对同一项退避重试，不要跳过去发下一个
5 观测  第一天就接上每日快照，只看增量，不看累计
python3 tools/check_package.py skills/<你的技能>                    # 文件格式 + frontmatter + 密钥
python3 skills/skill-lint/scripts/skill_lint.py skills/<你的技能>   # 可发现性与结构打分，先过 85
```

## 两天 97 次发布实测出来的平台规律

标「推测」的是我们从行为反推的，平台没有任何字段确认，请当默认参数而不是事实。

| 规律 | 实测依据 | 可信度 |
|---|---|---|
| 无扩展名文件会被拒收，可通过的只见过 md / py / yaml / csv | 目录里有 LICENSE 就报 `400 不允许的文件类型`；许可证只写进 frontmatter 的 license 字段，顺手清掉 `__pycache__` 与 `.DS_Store` | 实测事实，类型未穷举 |
| frontmatter 走严格 YAML，值里出现半角冒号加空格直接失败 | 原文 `mapping values are not allowed in this context`；整个值用双引号包住可解 | 实测事实 |
| 解析器强制 version / display_name / display_name_en / description_zh / description_en | 逐条报「缺少 Skill 中文展示名」等；其中 display_name 官方文档根本没记载 | 实测事实 |
| examples_zh 与 examples_en 每种语言最多 3 条 | 原文 `examples_zh 最多 3 个示例，当前 4 个` | 实测事实 |
| 同 slug 重传必须升版本号，草稿的版本也算数 | 原文「包内版本号 0.1.0 必须大于当前最新版本 0.1.0」 | 实测事实 |
| 热门英文词的 -zh 形式已被大面积抢注 | 复刻 superpowers 系列 10 个，8 个 -zh slug 已被他人占用，只能加限定词改名 | 实测事实 |
| slug 不是全网强唯一 | 我们有 3 个 slug 与别人的技能同名并存；判断「我的上架了没」必须用 slug 加 handle 精确匹配 | 并存是事实；成因推测，需确认 |
| 上架与 AI 评测是两条独立流水线 | 抽查 82 个全部进搜索索引、无一被拒；同一时刻 AI 评测只完成 26 个，次日覆盖率 100%。评测 404 不等于被拒 | 实测事实 |
| 短间隔会限频 | 连续 3 次请求（含失败的）后第 4 次即报「发布频率过高」；单次间隔 75 秒基本够用，接近上限时重试要等 10 分钟级 | 实测事实 |
| 发布配额约 100 次 / 滚动 24 小时，不按自然日重置；失败的请求是否也计入同样无从验证，保守起见按「计入」排预算 | 约第 100 次成功后全面拦截，+1 小时、+14.5 小时（跨本地日与 UTC 日）再试仍被拦，连一个字没改的对照技能也被拦；同期读操作正常，与令牌无关；平台不返回任何配额字段 | 推测，需确认 |
| 下载量约等于 Agent 自动调用次数，由描述的触发面决定 | 前 100 名里上架时长与下载量相关系数 r=0.06；上架 4 天进前百的案例存在；起量的描述都在指挥 Agent 主动触发；官方 Q&A 把「被 Agent 自动调用」列为可度量项 | 推测，需确认 |
| 品类决定天花板 | 前 100 分类分布 ai-agent 22、content-creation 15、office-efficiency 13、knowledge-management 11、design-media 11、dev-programming 只有 7 | 实测事实，样本有幸存者偏差 |
| 累计下载量里混着一条随时间线性增长的基线 | 95 个技能累计 1084 次、中位数 11、92.6% 挤在 6–20 区间，与内容特征完全对不上 | 分布是事实；「平台基线」是推测，需确认 |
| 指标口径有坑 | CLI 的 search 与 reports 会把 downloads / installs / stars / comments / versions 过滤掉不显示，详情接口的 stats 里其实有；查看量三处都不提供 | 实测事实 |
| 曝光取决于文本匹配，且需要 API Key 的技能会被站内筛选挡掉 | 搜索按 slug / name / description / summary / tags 做文本匹配，多词无命中时退回热门列表，所以关键词覆盖决定长尾曝光；站内有「不限 API Key」筛选项，写技能优先做零依赖、离线可跑的 | 实测事实 |

## 意图 → 做法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 不知道做什么题目 | 别按「名字找空缺」，空缺早没了；能赢的是同题更好、带脚本、描述覆盖、成系列 | 选题澄清 `brainstorming-spec-zh`；一手材料调研 `research-primary-zh` |
| 这个题有没有人要 | 先看品类分布定天花板，再搜同题看密度与头部量级，最后写一句「我比现有的强在哪」，写不出就换题 | 发布避坑指南 `skillhub-field-guide`；一手材料调研 `research-primary-zh` |
| SKILL.md 怎么搭骨架 | 四节固定：何时用 / 流程 / 输出契约 / 不做什么；正文 1500–12000 字符，参考资料拆到 references | 写给 Agent 看的文档 `writing-for-agents-zh`；技能体检 `skill-lint-scorecard` |
| frontmatter 每个字段填什么 | 逐字段对照上表的必填清单；所有值用双引号包住躲开严格 YAML；examples 每语言最多 3 条 | 发布避坑指南 `skillhub-field-guide` |
| 描述与触发面怎么写 | 两段式：先「只要涉及某领域即应触发，无需用户明确指定」，再用顿号铺开用户不会用专业词的说法；长度 400–600 字 | 技能体检 `skill-lint-scorecard`；写给 Agent 看的文档 `writing-for-agents-zh` |
| 名字和 slug 怎么取、撞名了怎么办 | 加一个说明用途的限定词，不要在原名后面加数字；改完语义反而更准 | 发布避坑指南 `skillhub-field-guide` |
| 发布前自检 | 两把尺都跑：包校验必须 0 FAIL，打分先过 85 再谈发布；失败的上传也可能白烧配额 | 技能体检 `skill-lint-scorecard`；发布助手 `skillhub-publish-helper` |
| 上传报 400 或解析失败 | 按报错原文对号：无扩展名文件、`__pycache__`、值里的半角冒号加空格、缺必填字段、版本号没升 | 发布避坑指南 `skillhub-field-guide` |
| 一天能发几个、被限流了 | 按滚动窗口排预算与分批，批间留足间隔；撞限流对同一项退避重试，不要跳过去发下一个 | 发布避坑指南 `skillhub-field-guide`；发布助手 `skillhub-publish-helper` |
| 要批量发一串技能 | 生成发布副本、串行发、记 skillId、留一份 CSV 日志，中断能从断点续 | 发布助手 `skillhub-publish-helper` |
| 上架了没、评测怎么查不到 | 用 slug 加 handle 精确匹配判断是否进索引；评测 404 是慢批处理没跑完，不是被拒 | 发布避坑指南 `skillhub-field-guide` |
| 上架后该看哪个数 | 第一天就接每日快照，原始 CSV 一份别删；看第二份减第一份的增量，别看累计值 | 数据画像 `csv-profile`；配置对比 `json-config-diff` |
| 版本与更新策略 | 每次重传前先自增版本号；改了什么写进 changelog，描述与触发面的改动单独成条便于归因 | 更新日志 `changelog-keep`；提交规范 `git-commit-lint` |
| 常见被拒原因有哪些 | 文件类型、版本号没升、必填字段缺、描述与能力不符、依赖 API Key、包里带真实数据或密钥——全都能在本地查出来；打包前先脱敏，示例一律换成 example.com | 密钥扫描 `secrets-scan`；日志脱敏 `sensitive-data-mask` |
| 想复刻别人的技能 | 只搬 MIT 与 Apache-2.0，写清出处、许可证与改了什么；纯翻译已经饱和且低分，要加本地适配与脚本 | 协议合规 `license-check-offline` |
| 要不要写脚本、工具怎么定义 | 确定性的部分交脚本（读文件、算统计、比对），判断交模型，零依赖纯标准库离线可跑；工具描述写清什么时候用与什么时候别用，参数给枚举与示例值 | 脚本向导 `wizard-zh`；工具与函数定义设计 `tool-design-zh` |
| 正文写得像流水账、读者看不下去 | 先写结论再写依据，每节只回答一个问题，长段拆表 | 技术写作 `tech-writing-expert`；文档协作 `doc-coauthoring-zh` |
| 想做一个系列 | 伞形入口吃搜索，子技能吃口碑；伞形的描述覆盖全部关键词并路由，子技能各自精专 | 技能体检 `skill-lint-scorecard`；发布避坑指南 `skillhub-field-guide` |

## 输出契约

1. **事实与推测分开写**：凡是从行为反推的结论，句末必须带「推测，需确认」，并写清反推依据与可证伪的验证方法。
2. **每条建议落到具体字段或具体文件**：说「描述要写好」不算建议，要给出改后的整句。
3. **发布前的验收是两条命令的退出码**，不是感觉；包校验 0 FAIL 且打分过线才允许进发布队列。
4. **触发面与能力必须一一对应**：描述里写的每一类场景，正文都要有对应做法；写不出做法就从描述里删掉那一类。数据结论只用增量，引用下载量必须说明是哪两次快照之间的差值。

## 典型组合流程

- **从零发一个技能**：选题澄清定题 → 一手材料调研看同题密度 → 写给 Agent 看的文档搭骨架 → 技能体检打分改到 85 以上 → 包校验 0 FAIL → 发布助手排队发 → 第一天接上快照。
- **救一个没人用的技能**：技能体检先看可发现性失分项 → 按两段式重写描述与触发面 → 补 tags 与 examples → 升版本号重传 → 只改描述不改正文，三天后比增量，改动才可归因。
- **批量上一串技能 / 被拒之后**：统一自增版本号 → 逐个跑两把尺 → 按配额分批排期 → 串行发布并记 skillId → 撞限流按同一项退避；被拒就抄下报错原文对照上表定位，本地复现并修，升版本号，重发前先用一个已通过的对照包试探窗口是否放行。

## 不做什么

- 不替你执行发布、不经手 API Token、不代你登录或实名，这些只能在你自己的终端完成。
- 不把推测写成事实：配额上限、窗口长度、失败请求是否计数、下载量的真实含义都没有平台侧确认，本页给的是默认参数。
- 不教你把技能接不住的场景写进触发面换流量。那是骗调用——用户被路由到一个帮不上忙的技能，损害的是作者信誉与平台生态。
- 不做纯翻译搬运，也不做依赖 API Key 的技能；前者饱和低分，后者会被站内筛选直接挡掉。
- 不保证本页规律长期有效：样本只有一个个人账号、97 个 slug、两天、两份快照，接口随时可能变。

---
本系列全部开源（正文 CC BY 4.0，代码 MIT）：https://github.com/po-et/workbuddy-skills
