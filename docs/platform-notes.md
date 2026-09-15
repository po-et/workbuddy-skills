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

## 技能包 SKILL.md 的平台专有必填字段（2026-09-15 上传实测）

上传按 Agent Skills 公开规范编写的技能包，平台解析失败，逐条报缺：

```
缺少 Skill 版本号（version），请在 SKILL.md frontmatter 中填写
缺少 Skill 中文展示名（display_name），请在 SKILL.md frontmatter 中填写
缺少 Skill 英文展示名（display_name_en），请在 SKILL.md frontmatter 中填写
缺少 Skill 中文描述（description_zh），请在 SKILL.md frontmatter 中填写
缺少 Skill 英文描述（description_en），请在 SKILL.md frontmatter 中填写
```

即开放平台在 `name` / `description` 之外**额外要求 5 个字段**：`version`、`display_name`、`display_name_en`、`description_zh`、`description_en`。公开文档与 Agent Skills 规范均未提及。

- zip 内 `<技能名>/SKILL.md` 的目录布局被接受（解析器找到了文件，只报字段缺失）
- 加上这 5 个字段后 `claude plugin validate` 仍通过，未知字段不影响 Claude Code 兼容性
- 本仓库四个技能已全部补齐；`CONTRIBUTING.md` 同步要求

### 示例提问字段（第二次上传实测）

提交总览页的「试试这样问我」来自 frontmatter 的 **`examples_zh` / `examples_en`**（字符串数组），可选但强烈建议填；解析器校验：

```
examples_zh 最多 3 个示例，当前 4 个
examples_en 最多 3 个示例，当前 4 个
```

即**每种语言最多 3 条**。字段命名与连接器 `connector-meta.json` 一致。
