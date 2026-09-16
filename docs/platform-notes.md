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
