# SkillHub 增长打法（2026-09-17 调研）

目标：在 skillhub.cn 积累下载量、收藏、曝光。个人账号 `user_a3a2e24a`（Captain Yang），已发布 4 个技能（审核中）。

## 1. 平台机制（实测 + 源码）

- **搜索**：CLI 与站内搜索按 `slug / name / description / summary / tags` 做文本匹配（CLI 源码 `skill_text()`），多词查询无命中时**退回热门列表**。所以描述与 tags 的关键词覆盖直接决定长尾曝光——102 万下载的「编程专家.Skill」就是一段覆盖几十个场景词的描述。
- **排序入口**：全部 / 近期飙升 / 下载量 / 最近上新；场景分类筛选；"不限 API Key" 筛选（需要 key 的技能会被过滤掉，**我们的技能一律不依赖 key**）。
- **技能页指标**：下载、收藏、AI 评分（1–5，附评测报告）、tokens 预估消耗、评论、版本历史。AI 评分由机器评测生成，有脚本、有明确触发条件、有输出契约的技能占优。
- **审核**：机器三线（内容合规 / 科恩漏洞扫描 / 云鼎模型安全），通过自动上架；无扩展名文件被拒；连续请求限频。
- **分类**：CLI 无法设置（payload 无此字段），当前显示「未分类」；是否由审核自动归类待观察。

## 2. 竞争态势（2026-09-17 探测，`skillhub search` 单关键词）

全球热门技能在 SkillHub **几乎都有人搬过中文版**：grill-me（Grill Me / 追问我 / Grill Pro）、caveman（含中文）、ponytail（Ponytail代码评审）、frontend-design ×4、mattpocock 全家桶（diagnosing-bugs / to-spec / teach / wayfinder，`user_0b46df4a`）、karpathy ×6、planning-with-files、taste、ui-ux-pro-max、hallmark、superpowers、mcp-builder…
批量搬运者：`user_3c6cb52e`（系统性中文化全球热门）、`kunlungrowth`（周报/简历/翻译/领域建模/单元测试/复盘/发布与上线…办公类批量）。
**结论：按"名字找空缺"这条路已经没有空缺；能赢的是"同题更好 + 带脚本 + 描述覆盖 + 系列化"。**
验证案例：「文章去AI味工具」（humanizer 中文复刻）23.6 万下载；「GitHub CLI 省 Token 只读工具集」（个人、开发编程、纯 SKILL.md + 预置函数）6.2 万。

## 3. 打法

1. **每个技能一段"场景词密集"的描述**：写清 什么时候用 + 覆盖的同义词/子任务（中英），但不堆砌无关词（AI 评分会惩罚"描述不准确"，平台审核明确要求"描述准确无虚假宣传"）。
2. **tags 8–12 个**：中文 + 英文 + 缩写（周报 / weekly report / 迭代报告 / sprint report）。
3. **有脚本就写脚本**：确定性部分（读 git、算统计、查 API）交给脚本，判断交给模型——既省用户积分又拿 AI 评分。
4. **系列化 + 伞形入口**：一个「研发全能助手」伞形技能覆盖全部关键词并路由到子技能；子技能各自精专。伞形技能吃搜索，子技能吃口碑。
5. **复刻规则**：只搬 MIT / Apache-2.0；`ATTRIBUTION.md` 写明来源、许可证、改了什么；中文化不是翻译，要加 WorkBuddy 适配（本地文件落盘、积分控制、输出契约）和脚本。
6. **节奏**：每次发布进「最近上新」，是免费曝光；每周 3–5 个，发布间隔 ≥75 秒。每个新技能同步发一条案例/文章带链接。
7. **不做**：需要 API Key 的技能（被筛掉）；纯翻译的搬运（已饱和且低分）；与公司内部相关的任何内容。

## 4. 第一批（9 个）

| # | 技能 | 类型 | 差异化 |
|---|---|---|---|
| 1 | Git 提交信息生成器 `commit-message` | 原创+脚本 | 从 diff 确定性推断 type/scope/符号，模型只润色 |
| 2 | Changelog 生成器 `changelog` | 原创+脚本 | Conventional Commits 分组，不规范提交不丢，缺口明写 |
| 3 | 依赖漏洞体检 `dep-vuln-check` | 原创+脚本 | OSV.dev 免 key，npm/pip/go/cargo 锁文件 |
| 4 | 日志突变检测 `log-anomaly` | 原创+脚本 | 复用 incident-brief 的滑动基线 3σ 算法 |
| 5 | 需求盘问官 `grill-me-zh` | MIT 复刻增强（mattpocock） | 决策落盘 docs/decisions.md、WorkBuddy 积分控制 |
| 6 | Bug 诊断法 `diagnosing-bugs-zh` | MIT 复刻增强 | 与 incident-brief 衔接 |
| 7 | 合并冲突解决 `merge-conflicts-zh` | MIT 复刻增强 | 附 git 命令序列与回退 |
| 8 | 需求→Spec→任务拆解 `spec-and-tickets-zh` | MIT 复刻增强（to-spec + to-tickets） | 输出可直接建工单的 JSON |
| 9 | 研发全能助手 `dev-workflow-pro` | 伞形入口 | 覆盖全部关键词，路由到 1–8 与已发布 4 个 |

指标记录：`docs/submission-checklist.md`（每周记一次下载/收藏/评分）。

## 进展（2026-09-17 晚）

- **复刻**：mattpocock 19 个（含 wave B/C）、addyosmani 25 个、Context-Engineering 5 个、Anthropic doc-coauthoring 1 个，全部中文化并附 ATTRIBUTION。
- **原创脚本技能（新一波，全部本地测试通过）**：dockerfile-check、sql-migration-check、cron-explain、openapi-breaking-diff、env-sync-check、flaky-test-finder、k8s-manifest-check（自带最小 YAML 解析）、pr-description、todo-debt-scan、git-branch-cleanup、http-health-check、log-pattern-cluster、access-log-stats、git-hotspots、json-schema-infer、codeowners-suggest、dep-outdated-check。选题原则：研发效能 / SRE 高频搜索词 + 纯标准库零依赖 + 一条命令出结果 + 可作 CI 门禁。
- **发布节奏**：每个技能 75 s 间隔的后台队列串行发布；slug 冲突两例（triage-zh → issue-triage-zh，context-compression-zh → context-compression-strategies-zh）说明热门英文词的 -zh 形式已开始被抢注，后续 slug 尽量带限定词。
- **累计**：约 80 个技能已 Published，全部处于机器审核中；skillId 明细见 submission-checklist.md。
- **下一步候选**：dep-outdated 私有源支持、k8s 检查补 PDB/HPA、把「五分钟体检」系列（Dockerfile / K8s / SQL / OpenAPI / .env）做成一个 umbrella 技能互相引流；审核通过后开始记录 查看/下载 周指标。
