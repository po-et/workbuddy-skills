# 个人开发者的 WorkBuddy 贡献渠道地图（2026-09-16 调研）

目标：**快速提交、看得到用户数、认识人**。Buddy 应用（需企业认证）已放弃，下表只列个人身份能走的渠道。

## 一张表

| 渠道 | 门槛 | 提交→上线 | 能看到什么 | 朋友圈价值 | 我们的状态 |
|---|---|---|---|---|---|
| **SkillHub**（skillhub.cn，腾讯官方技能市场） | 手机号/微信登录 + 人脸实名 | 机器审核（内容合规 + 科恩漏洞扫描 + 云鼎模型安全），**通过即自动上架**；CLI 3 条命令 | 下载量、收藏、AI 评分与评测报告、评论、版本历史、「近期飙升 / 下载热榜」 | 中：作者页 + 评论区；官方大赛按季办 | 4 个技能的发布副本已生成（`tools/skillhub_prep.py`），等你实名 |
| **开放平台**（open.workbuddy.cn） | 个人认证（已过） | 机器 + 人工审核，承诺 7 工作日 | 后台「运营数据」：安装量 / 调用量 / 活跃用户 / 人均频次 / 次周留存 / 专家错误率 | 低：无社交面；但客户端内权重高于 SkillHub（官方 Q&A Q12） | 9 个资产审核中 |
| **腾讯云开发者社区 · 有奖征集《WorkBuddy 行业应用指南》** | 写文章 + 填问卷 | 2026-09-02 10:00 → **10-08 23:59**；发布平台不限 | 阅读量（发布平台）；收录后署名进官方指南 | **高**：交流群 + 官方运营对接 + "共创者权益" | 案例 #1 草稿见 `docs/articles/02-…`，缺客户端截图 |
| **WorkBuddy 实战蓝皮书 · 社区案例集**（workbuddy.homes，AlephAITech 维护，非官方） | GitHub PR | 审核完整性/安全性/可读性后发布，仅 7 个案例 | 署名 + 链接 | **高**：维护者是 AI 圈 KOL（刘聪NLP、袋鼠帝、甲木、Joy），有微信群 | 同一案例改格式即可投 |
| **ClawHub**（clawhub.ai，OpenClaw 官方注册表） | `clawhub login`（GitHub 账号） | `clawhub skill publish` 即发，自动安全检查后进入安装面 | 安装数 | 中：海外 OpenClaw 用户 | 技能已带 openclaw metadata，等你登录 |
| **灵感**（客户端「更多 → 灵感」） | 无公开投稿入口 | 官方精选 + 社区贡献，卡片显示作者头像昵称 | 「做同款」次数不可见 | 中 | 据推测走征集/运营群，待确认 |
| **EdgeOne × WorkBuddy 挑战赛**（建站 Prompt/Skill） | GitHub PR | 本期已评奖（页面已标 Champion 等） | 作品池展示 | 中：Discord 社区 | 关注下一季 |
| **SkillHub 线上挑战赛** | 本期「宝藏母校」仅限高校师生，2026-08-12→09-18 | — | — | — | 不适用；关注下一季主题 |
| **腾讯云 TDP（开发者先锋）** | 申请制 | — | — | 高：内测资格 + 社群 | 申请条件待确认（页面抓取失败） |

## 为什么 SkillHub 是"快速提交 + 积攒用户"的主战场

- 累计已审核个人技能 **52,306** 个；腾讯官方 153 个技能 228.7 万次下载；开发编程类头部个人技能：编程专家 102 万、dev-expert 36 万、GitHub CLI 省 Token 只读工具集 6.2 万——**个人、开发者工具、纯 SKILL.md**，就是我们这一类。
- 审核是机器流水线，"全部通过才能自动上架"，不用排人工队。
- 技能页有「安装到本地 Agent · 支持 WorkBuddy」按钮，SkillHub 的下载直接变成 WorkBuddy 用户。
- 三种发布方式：网页 / CLI / Agent。CLI 版 frontmatter 必填 `slug`（全网唯一、kebab）、`version`（SemVer）、`displayName`；建议 `summary`、`description`、`tags`、`license`、`homepage`。
- 专家包（57 个，全部署名 SkillHub）目前只见官方发布，个人能否发待确认。
- SkillPay 按调用计费只对企业开放，个人变现路径未开放。

### 发布三步（你的操作，约 15 分钟）

1. skillhub.cn 右上角登录（手机号验证码或微信）→ 个人中心 → 实名认证（人脸核身）。
2. 个人中心 → API keys（`/dashboard/keys`）→ 创建 API key，复制 `skh_…`（只显示一次）。
3. 终端执行（token 只在你自己的终端里输入）：

```bash
curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only && echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc && skillhub --version
```

```bash
skillhub login --key "<你的 skh_ token>" --host https://api.skillhub.cn && skillhub auth whoami
```

之后的 dry-run 与发布由我在本机跑：`skillhub publish dist/skillhub/<slug> --host https://api.skillhub.cn --dry-run`。

## 腾讯云征集：一篇案例三处投

同一个"用 WorkBuddy 完成一项工作"的完整案例（≥800 字、≥3 张过程截图、四段：输入材料 / WorkBuddy 配置 / 操作步骤 / 产出物）可以同时投：
腾讯云征集（问卷提交链接，奖励可兼得：投稿奖 200–500 积分、阶段奖 1000 积分 + 100 元代金券每周 10 名、指南收录奖每篇 2,000 积分 + 500 元代金券 + 周边 + 共创者权益，同一作者可累积，满 3/6 篇阶梯）、蓝皮书 PR、掘金/知乎同步。
评审加分项写在规则里：写明使用了专家/专家团/Skill/连接器的具体层级；**公开 Skill 配置**——我们的技能本来就是开源的。
不予收录：未脱敏的公司材料、只有成品无过程、AI 编造。所以案例只用公开仓库。

## 顺序

1. 你做 SkillHub 实名 + API key（15 分钟）→ 我发 4 个技能 → 当天进审核，上架后有下载数。
2. 你在客户端跑一遍案例 #1 并截 3 张过程图（或授权我用 computer-use 操作客户端）→ 我定稿 → 发腾讯云社区 + 填问卷 + 蓝皮书 PR。
3. 你 `clawhub login` → 我发 ClawHub。
4. 每周一篇案例，10-08 前投 3 篇（满 3 篇触发阶梯奖）。
