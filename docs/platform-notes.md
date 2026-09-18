# 开放平台实测规则（登录后台所见）

日期：2026-09-15。来源：open.workbuddy.cn 控制台页面与平台公告原文。与公开文档不一致处已标出。

## 审核

- 流程（公告《上架 Q&A》Q1）：**机器审核**（基础安全审核、内容安全审核、质量检测）→ **人工审核**（类目资质审核）→ 通过后进入「待发布」
- 时效：承诺 7 个工作日；09-04 公告《关于资产审核时效的说明》称"新增提交量持续高于当前的审核处理能力……短期内可能存在一定延迟"
- 结果通知：邮箱 + 开放平台通知 + WorkBuddy 客户端通知
- **质量检测四维度**（Q2 原文）：任务完成度、指令遵从性、事实辨别性、规则遵从性。不通过则"对文件中提供的信息做精修调整，并可以接入 WorkBuddy 进行使用调试"
- ZIP 解析失败（Q3）：复制页面失败原因，交给 WorkBuddy 定位修改

## 渠道差异：开放平台技能 vs SkillHub（Q12 原文）

> 开放平台上传的技能，会经过严格的审核和质量评测，更有保障。这些 skill，在 workbuddy 端内拥有更完善的主页呈现品牌，以及在技能市场展示和被 Agent 自动调用时，拥有更高的权重。

**结论：主发布渠道改为开放平台「发布管理 → 技能」，SkillHub 作为补充。**

## 连接器（Q4）

发布后**不自动上架**，需运营代为上架，预计 7 个工作日；后续将支持自动上架。

## 商业化（Q9）

> 平台商业化正在规划中，敬请期待~

官方确认分成尚未开放，与 09-08 缺口分析一致。

## 个人开发者权限（Q11）

Buddy 应用、硬件接入需企业认证；个人可发专家、技能、连接器。

## 上传与资料限制（页面实测）

| 项 | 页面实测 | 公开文档 | 备注 |
|---|---|---|---|
| 技能代码包 | 仅 .zip，≤ 3MB，平台自动开包解析并生成技能 ID | — | 发布流程三步：配置技能 → 确认信息 → 提交审核 |
| 开发者头像 | **≤ 100KB**，JPG/PNG | 512×512，≤ 5000KB | **不一致**，以页面为准 |
| 简介 | 20–120 字符 | 同 | 一致 |
| 联系方式 | 至少 1 项，至多 5 项 | 同 | 一致 |

## 控制台路径

`/dashboard`、`/skill/publish`、`/expert/publish`、`/connector/publish`、`/settings/cert-info`、`/settings/developer`、`/operations`、`/application/all/credit`（积分兑换）

## 技能包 SKILL.md 的平台必填字段（2026-09-15 上传实测 + 2026-09-16 核对官方文档）

上传按 Agent Skills 公开规范编写的技能包，平台解析失败，逐条报缺：

```
缺少 Skill 版本号（version），请在 SKILL.md frontmatter 中填写
缺少 Skill 中文展示名（display_name），请在 SKILL.md frontmatter 中填写
缺少 Skill 英文展示名（display_name_en），请在 SKILL.md frontmatter 中填写
缺少 Skill 中文描述（description_zh），请在 SKILL.md frontmatter 中填写
缺少 Skill 英文描述（description_en），请在 SKILL.md frontmatter 中填写
```

对照官方 `/docs/skill`（2026-09-16 核对）：

| 字段 | 官方文档 | 解析器 | 备注 |
|---|---|---|---|
| `version` | 必填 | 必填 | 重传须递增（文档未写） |
| `description_zh` / `description_en` | 必填 | 必填 | 文档要求"简洁介绍" |
| `author` | 必填 | **未强制**（缺失仍解析通过） | 建议填开发者昵称 |
| `display_name` / `display_name_en` | **未记载** | 必填 | 市场展示名由此带出 |
| `examples_zh` / `examples_en` | **未记载** | 可选，各≤3 | 显示为「试试这样问我」 |
| `allowed-tools` / `disable-model-invocation` / `user-invocable` | 可选 | — | 与 Claude Code 同名字段 |

结论：**按公开规范或按官方文档写都会解析失败**，必须同时满足文档字段 + 解析器额外要求。zip 内 `<技能名>/SKILL.md` 目录布局被接受；加上这些字段后 `claude plugin validate` 仍通过。

### 示例提问字段（第二次上传实测）

提交总览页的「试试这样问我」来自 frontmatter 的 **`examples_zh` / `examples_en`**（字符串数组），可选但强烈建议填；解析器校验：

```
examples_zh 最多 3 个示例，当前 4 个
examples_en 最多 3 个示例，当前 4 个
```

即**每种语言最多 3 条**。字段命名与连接器 `connector-meta.json` 一致。

### 版本号与重复上传（第三次上传实测）

- 一次成功解析即在服务端创建**草稿**并占用技能 `name`；再走「创建」上传同名包会报：`技能 "<name>" 已存在，请携带其 assetId 发布新版本`
- 正确路径：技能列表 → 该草稿「编辑」→ 第一步重新上传（URL 形如 `/skill/publish/<assetId>?action=create&step=1&entry=2`）
- 重传时 **`version` 必须大于当前最新版本**，草稿的版本也算：`包内版本号 "0.1.0" 必须大于当前最新版本 "0.1.0"`
- 结论：每次重新打包上传前先递增 `version`；本仓库 iteration-report 因此从 0.1.1 起

### 第二步表单实测（2026-09-16）

- 字段：识别信息（只读）/ 市场展示名称（由 display_name 带出）/ **市场展示分类\***（多选，13 项：OPC·一人公司、办公协同、开发工具、投资理财、效率工具、内容创作、信息资讯、教育学习、数据分析、网站部署、生活服务、商业运营、知识与学习）/ 头像（可选，512×512 ≤500KB）/ **服务类目\***（1–5 项，微信小程序式级联，如 工具 → 办公）/ 能力介绍（由 description_zh 带出）/ 版本号（由 version 带出）
- 分类下拉为多选且选后不关闭，此时点击页面其他控件会被浮层截胡；关闭需点空白处
- 「创建」流程的客户端草稿存于 sessionStorage，按标签页隔离；同一标签页连续发布会带出上一个包，**每个新技能用新标签页**最省事
- 提交后列表状态：草稿 → 审核中，可「撤回」

### 连接器上传实测（2026-09-16）

- 入口 `/connector/all` → 创建 → `/connector/publish?action=create&step=1`；仅 .zip，**≤ 20MB**（技能是 3MB）
- 包内顶层目录布局（`mermaid-connector/connector-meta.json` …）、`LICENSE`、`ATTRIBUTION.md` 均被接受，未报多余文件
- 第二步：市场展示名称（由 `name_zh` 带出）/ 头像（`icon.svg` 直接生效）/ **服务类目\***（唯一必填下拉）/ 能力介绍（`description_zh`）/ 试试这样问我（`examples_zh`，4 条全部显示，未报上限）
- 无「市场展示分类」字段
- 提交后列表状态「审核中」，可「撤回」；官方 Q&A：过审后需运营代上架，约 7 个工作日

### 专家（Expert）包实测（2026-09-16）

- 文档 `/docs/expert` 只写 `teamInfo{leadAgent,memberAgents}`；解析器实测报 `members 为必填数组`，且元素须为对象（Go 结构 `teamMemberJSON`：`id / name{en,zh} / profession{en,zh} / avatar / role∈{lead,member}`），完整结构在 `/docs/expert-team`
- Team 型专家须在根目录提供 **settings.json**（解析器原文），文档仅标「设置主理人（必须）」；**官方模板 trading-team.zip 里文件名是 `setting.json`（单数）**——两个都放
- 官方专家团模板 `categoryId` 为 `00-ExpertTeam`，单专家模板用 `01-Design`，两者都不在文档 15 项表中；**解析器实测拒绝 `00-ExpertTeam`**（"不在合法分类列表中，请参考开发规范第八节"），即两份官方模板的分类值均已过时，以文档表为准（专家团用 `02-Engineering` 通过）
- 主理人文件名须含专家团前缀，不可用通用 `team-lead`
- 官方模板本身过不了文档规则：中文简介超 40–50、头像文件缺失、主理人 .md 无 frontmatter、成员 displayName/profession 为普通字符串——说明解析器对 agent frontmatter 宽松
- 专家包可内置 `skills/`（模板自带），可内置 `rules/`；`tools/pack.py` 会把 agents 引用的仓库技能自动打进包
- 专家包 ≤ 20MB

### 专家发布第二步实测（2026-09-16）

- 字段：识别信息 / 专家职称（由 profession.zh 带出）/ 专家花名（由 displayName.zh 带出）/ **市场展示分类\*** / 头像（由 avatar 带出）/ **服务类目\***（同技能，级联）/ 能力介绍（由 displayDescription.zh 带出）
- **专家的「市场展示分类」是另一套 17 项**，与技能的 13 项不同：开学季、高校新生攻略、腾讯专家、产品设计、技术工程、金融投资、全球发展、教育学习、游戏空间、数据智能、营销增长、内容创作、销售商务、运营人力、项目质量、法务安全、行业顾问（前两项为当季活动类目）
- 总览页会显示「擅长领域」= plugin.json 的 tags；「试试这样问我」= quickPrompts
- 解析器对 agent .md 的 frontmatter 用**严格 YAML**：未加引号的值含 `: ` 直接报 `mapping values are not allowed in this context`

### 第二批提交（2026-09-16 下午）

- 独立专家 sre-incident-expert（分类 技术工程）、qa-release-expert（分类 项目质量）、连接器 drawio（类目 工具-办公）一次解析通过，得益于 `tools/check_package.py` 已编码全部实测规则
- drawio 连接器：PyPI 安装（`pip3 install cli-anything-drawio`），本机 draw.io 桌面版实测 shape add / connect add / export png+svg 通过；空白图导出报错是 draw.io 行为
- 同一浏览器标签页连续「创建」会带出上一个包的客户端状态，**每个资产开一个新标签页**最稳

## Buddy 应用（2026-09-16 实测 + 文档）

- **个人认证账号不能创建。** `/buddy-app/all` 页面只有「筛选 / 创建」与「暂未发布」；点「创建」弹窗原文：
  「个人开发者无法创建Buddy应用，如需创建，请进行企业认证，成为企业开发者」，按钮「取消 / 去创建」（后者通向企业认证）。
  「设置 → 认证信息」页只显示个人信息，没有企业认证入口。
- **形态**：网页表单配置，五个模块——应用身份（名称/头像 256×256/描述/OAuth 列表/回调地址/可信来源）、
  首页（slogan、场景胶囊、工作模式 2–4 个各带 system prompt、内置连接器）、市场（专家/技能/连接器/精选场景）、
  其他（绑定鉴权、占位文案中英、模型选择与排序）、预览调试（导出配置 JSON；预览需指定版本客户端）。
  文档提醒：配置项多，每次退出前导出配置。
- **审核两段**：创建审核 → 配置审核。终端用户入口：客户端首页左上角应用入口（当前内测，欢迎页只是微信扫码加入名单）。
- **设计规范包** `https://codebuddy-platform-1258344699.cos.ap-beijing.myqcloud.com/open/static/files/buddy-app.zip`
  是 4 张规范图：首页（标题 + 模式 tab + 胶囊 + 输入框）、专家页（精选场景卡片）、icon 规则（16×16、线宽 1.2、有断口、圆角平滑 100%）、
  底图规则（1000×910：底图 670px 居顶 + 两层 670px 灰蒙层 0%→100% + 一层 910px 全局蒙层；日 #F2F2F2/#FFFFFF，夜 #242424）。
- 企业认证三条快速路径：腾讯云账号 / 微信公众号 / 企业法人实名（营业执照 + 法人人脸）。个体工商户可做腾讯云企业实名；
  WorkBuddy 是否接受个体工商户主体——待确认。
- 配置包与校验器：`buddy-apps/devops-buddy/`、`tools/check_buddy_app.py`。

## SkillHub（skillhub.cn）发布实测（2026-09-17）

- 登录：`skillhub login --key <skh_…> --host https://api.skillhub.cn`；`skillhub auth whoami` 输出 userId / handle / role，个人 handle 形如 `user_xxxxxxxx`（技能 URL 为 `/skills/<handle>/<slug>`）。
- **无扩展名文件被拒**：上传含 `LICENSE` 的目录报 `400 不允许的文件类型: LICENSE`。许可证只写 frontmatter `license: MIT`；`tools/skillhub_prep.py` 生成副本时会删掉 LICENSE / NOTICE / ATTRIBUTION。实测可通过的类型：md / py / yaml / csv。
- **限频**：连续 3 次请求（含失败的）后第 4 次即 `发布频率过高`；发布脚本每次间隔 75 秒。
- `--dry-run` 不需要登录即可做格式校验；frontmatter 必填 `slug`（kebab，全网唯一）、`version`（SemVer）、`displayName`。
- 与开放平台字段（`name` / `display_name` / `description_zh` …）并存在同一 frontmatter 里，dry-run 与上传均未报错；副本里去掉了重复的 `version` 键。

- 2026-09-18 观察：据实测（2026-09-18 14:32 复验）：SkillHub 的发布限额**不是按日重置**——2026-09-17 约第 100 次成功发布后即全面拦截，此后 00:54（+1 h）、14:32（+14.5 h，已跨本地日与 UTC 日）再试均报「发布频率过高」，连未改动的对照技能也拦；同期读操作（search/evaluation）完全正常，故与令牌无关。最符合的解释是**滚动 24 小时窗口约 100 次**（需最终确认）：昨天的配额消耗集中在 18:00–23:53，因此今天同一时段起才会逐步释放。对策：把发布当稀缺资源排队——单日不超过 90 次、不要集中在几小时内打满、遇限流按同一项等 10 分钟重试而不是跳过；产能瓶颈已从「造技能」转移到「发布配额」，后续应优先提升单个技能的质量与可发现性，而非堆数量。
