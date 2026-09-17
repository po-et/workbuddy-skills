---
name: skillhub-publish-helper
description: SkillHub 技能发布助手：批量校验、清理、dry-run、按间隔发布、记录 skillId、查上架状态。当用户说「把这些技能发到 SkillHub」「SkillHub 发布报错 400 不允许的文件类型」「发布频率过高怎么办」「怎么用 CLI 发布 Skill」「批量发布并记录 ID」「我的技能上架了没」「skillhub publish 用法」时使用。脚本封装 5 条实测规则：frontmatter 必填 slug/version/displayName；无扩展名文件（LICENSE、NOTICE）会被 400 拒绝；连续请求触发限频，间隔 75 秒；发布后进机器审核，过审前搜索索引查不到；同 slug 改版本即更新。不经手你的 API Token（登录由你在终端完成）。
author: Captain
version: 0.1.0
display_name: "SkillHub 发布助手"
display_name_en: "SkillHub Publish Helper"
description_zh: "批量把技能发到 SkillHub：校验 frontmatter、剔除会被拒的文件、dry-run、75 秒间隔发布、CSV 记录 skillId、查是否上架；封装 5 条实测规则。"
description_en: "Batch-publish skills to SkillHub: lint frontmatter, drop files the platform rejects, dry-run, publish with 75s spacing, log skillIds to CSV, check listing status; encodes five field-tested rules."
examples_zh:
  - "把 skills/ 下这 6 个技能发到 SkillHub 并记录 ID"
  - "发布报 400 不允许的文件类型 LICENSE，怎么处理"
  - "查一下我发的技能哪些已经上架了"
examples_en:
  - "Publish these 6 skills to SkillHub and log the ids"
  - "Publish fails with 400 file type LICENSE not allowed, what now"
  - "Check which of my published skills are live"
metadata:
  { "openclaw": { "requires": { "bins": ["python3", "skillhub"] }, "os": ["darwin", "linux"], "emoji": "📤" } }
---

# SkillHub 发布助手

把"发一个技能到 SkillHub"变成一条命令，把踩过的坑变成校验规则。

## 五条实测规则（2026-09）

1. **frontmatter 必填** `slug`（kebab-case、全网唯一，冲突报 409）、`version`（SemVer）、`displayName`；建议 `summary`、`description`、`tags`、`license`、`homepage`。tags 直接参与站内搜索匹配，多写同义词。
2. **无扩展名文件会被拒**：目录里有 `LICENSE`、`NOTICE` 这类文件时报 `400 不允许的文件类型`。许可证写进 frontmatter 的 `license` 字段；来源说明用 `ATTRIBUTION.md`。
3. **限频**：连续 3 次请求（含失败的）后第 4 次报"发布频率过高"，间隔 ≥ 75 秒。
4. **审核**：发布后进机器审核（内容合规、漏洞扫描、模型安全），通过前搜索索引里查不到，详情页显示 skill not found；教程说 3–7 个工作日邮件通知。
5. **更新**：同 slug、改 `version` 再发即更新；`--dry-run` 不需要登录。

## 前置（你自己做，10 分钟）

skillhub.cn 登录 → 实名（人脸）→ 个人中心 API keys 创建 token → 终端执行 `skillhub login --key <token> --host https://api.skillhub.cn` → `skillhub auth whoami` 看到 handle。CLI 安装：`curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only`。**token 只在你的终端出现，本技能不读取它。**

## 执行流程

### 第 1 步：只校验不发布
```bash
python3 {baseDir}/scripts/publish_batch.py --dirs skills/a skills/b --no-publish
```
输出每个目录的 FAIL/WARN/OK：slug 格式、SemVer、displayName、无扩展名文件、`__pycache__`，然后跑 `--dry-run`。

### 第 2 步：发布并记录
```bash
python3 {baseDir}/scripts/publish_batch.py --dirs skills/a skills/b --out publish-log.csv --interval 75 --changelog "首次发布"
```
按间隔逐个发布，`publish-log.csv` 追加 slug / skillId / 时间 / 结果。跑之前用户要确认清单（发布是外发动作）。

### 第 3 步：查上架状态
```bash
python3 {baseDir}/scripts/publish_batch.py --status --handle <你的 handle> --slugs a b
```
用搜索索引判断：出现即上架；没出现就还在审核（或被拒，看邮件）。

## 建议
- 一个技能目录只放 SKILL.md、scripts/、references/、assets/；开放平台版和 SkillHub 版字段并存在同一个 frontmatter 里实测不冲突，但 `version` 只能出现一次。
- 描述与 tags 是长尾搜索的入口，写清"什么时候用"和同义词，但不要堆无关词（AI 评分会惩罚不准确的描述）。
- 复刻他人作品只搬 MIT/Apache 等宽松许可证的，`ATTRIBUTION.md` 写来源、许可证、改动。

## 常见问题
**409 slug 已被占用？** 换个更具体的 slug（加用途后缀，如 `-git`、`-zh`）。
**401 invalid api key？** token 失效，重新创建并 login。
**发布成功但详情页 not found？** 正常，审核中。

---
本技能与脚本开源：https://github.com/po-et/workbuddy-skills
