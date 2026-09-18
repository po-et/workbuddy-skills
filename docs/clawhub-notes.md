# ClawHub（clawhub.ai）发布规则调研笔记

> **渠道状态（2026-09-18）：搁置。** 用户没有 ClawHub 账号；注册需本人完成。
> 本文档与 `tools/clawhub_prep.py` / `tools/clawhub_publish.sh` / `docs/clawhub-publish-runbook.md`
> 保持可用状态，有账号后即可直接走 runbook 发布。

日期：2026-09-18。只读调研，未登录、未发布。信息来源以官方仓库 `docs/*.md` 原文抓取为主（比通用网页摘要更可信），`npx clawhub --help` 系列为本机实测（CLI v0.23.3）。凡两个来源打架的地方，两边都列出来，标"需确认"，不替 ClawHub 下结论。

## 已确认（附来源 URL）

### 目录 / 文件

- 一个技能就是一个文件夹，唯一必需文件是 `SKILL.md`（或 `skill.md`；旧名 `skills.md` 也认）。可选：任意支持文件、`.clawhubignore`（忽略发布用，旧名 `.clawdhubignore`）、`.gitignore`（也生效）。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)
- **发布接受文件夹内任意扩展名的常规文件**（"Publish accepts all regular files in the skill folder, regardless of extension"），隐藏路径、软链接、macOS 元数据会被忽略。这一点和 SkillHub 不同（见下方对比表）。
  来源：同上，"Skill files" 节
- **`.pyc` / `.pyo` / `.pyd` 文件会被直接拒收**（发布阶段拒绝，不进安全扫描）。官方给出的原因：腾讯朱雀实验室的 A.I.G 扫描器 0.2.1 版本还不能解析打包后的 Python 字节码，在 [CVE-2026-84809](https://nvd.nist.gov/vuln/detail/CVE-2026-84809) 修复前 ClawHub 用这条规则兜底；ClawScan 自己也会独立检测打包字节码。
  来源：[docs/security-audits.md](https://github.com/openclaw/clawhub/blob/main/docs/security-audits.md)。**这条直接决定了本仓库 `__pycache__` 必须清理，不是可做可不做的防御性动作。**
- 单包总大小上限 **50MB**；`SKILL.md` 加最多约 40 个"有边界的 UTF-8 文件"会被纳入摘要/向量索引（软上限，超出的文件仍能下载，只是不参与检索文本）。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)，"Skill files" / "Limits" 节

### SKILL.md frontmatter

- 官方原文："Markdown with optional YAML frontmatter."——**frontmatter 整体被称为"可选"**，服务端在发布时从中提取元数据。正文对字段语义的强约束只落在两个字段上：
  - `name`：面向可移植 Agent Skill 的建议是"应该和父目录同名，用 1–64 位小写字母、数字或连字符"。
  - `description`：会被用作 UI / 搜索里的技能摘要。
  官方"Basic frontmatter"示例把 `name` / `description` / `version` 三者放在一起展示，但正文没有用"必填"字样单独强调 `version`。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)
- `metadata.openclaw`（别名 `metadata.clawdbot`、`metadata.clawdis`）是**可选**字段，用来声明技能运行时依赖：`requires.env` / `requires.bins` / `requires.anyBins` / `requires.config` / `primaryEnv` / `envVars`（每项含 name/required/description）/ `always` / `skillKey` / `emoji` / `homepage` / `os` / `install`（`brew`/`node`/`go`/`uv`）/ `nix` / `config`。安全扫描会核对"声明的依赖"与"代码实际用到的依赖"是否一致，不一致会被标记为 metadata mismatch。
  来源：同上，"Frontmatter metadata" / "Full field reference" 节
- **`metadata.openclaw` 与 `metadata.clawdbot` 哪个是"首选名字"，仓库内两份文档说法互相矛盾**：`docs/skill-format.md` 说"declare under `metadata.openclaw`（别名 clawdbot/clawdis）"，把 openclaw 当主名；`README.md` 却说"`metadata.clawdbot` is preferred, but `metadata.clawdis` and `metadata.openclaw` are accepted as aliases"，把 clawdbot 当主名。两边都确认 `openclaw` 这个键本身是有效的，所以功能上不影响本仓库现状（三个技能已经在用 `metadata.openclaw`），只是"哪个更官方"这一点本身自相矛盾，未做改动。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md) vs [README.md](https://github.com/openclaw/clawhub/blob/main/README.md)

### 发布命令与参数（`clawhub skill publish <path>`，本机 `--help` 实测 + 文档核对一致）

`--slug` `--name` `--owner` `--source-owner` `--migrate-owner` `--version` `--fork-of` `--changelog` `--tags`（默认 `"latest"`）`--categories` `--topics` `--dry-run` `--json` `--source-repo` `--source-commit` `--source-ref` `--source-path`。

- **`--tags` 不是关键词标签，是版本的 dist-tag**（类似 npm 的 `latest`/`beta`），"Tags are string pointers to a version"。真正对应 SkillHub"关键词标签"概念的是 `--topics`。这是最容易踩坑、和 SkillHub 语义差得最远的一个参数，命名相同但含义完全不同。
  来源：[docs/publishing.md](https://github.com/openclaw/clawhub/blob/main/docs/publishing.md)、`npx clawhub skill publish --help`
- `--categories`：最多 3 个，必须是固定枚举里的 slug，精确匹配（`Development` 会被拒，必须是 `development`）；枚举共 14 个：`integrations` `automation` `research` `development` `productivity` `communication` `creative` `knowledge` `agents` `operations` `security` `finance` `lifestyle` `other`。传了未知 slug 会导致**发布直接失败**。`other` 和具体分类同传时会被丢弃 `other`。首次发布不传 `--categories` 会被存成 `other`。
  来源：[docs/publishing.md](https://github.com/openclaw/clawhub/blob/main/docs/publishing.md)，"Skill catalog metadata" 节
- `--topics`：最多 5 个，自由词，每个 ≤48 字符，不能含不可见格式字符，重复项去重后再计数；以下词是保留词，会被拒绝：`approved` `audited` `certified` `clawhub` `community` `curated` `endorsed` `featured` `official` `officials` `openclaw` `recommended` `staff-pick` `trusted` `trusted-publisher` `verified`。
  来源：同上
- **`--dry-run` 不检查 `--categories`/`--topics` 的合法性**（"`--dry-run` does not check slugs; the registry validates them when the publish run"）——dry-run 过了不代表分类一定能发成功，这是本次调研发现的一个具体坑。
  来源：同上

### 版本 / 更新规则

- 每次发布生成一条新的**不可变**版本记录（"Publishing creates a new immutable version record"）。新技能从 `1.0.0` 起步，之后的改动**自动发下一个 patch 版本**；只有需要显式指定版本号时才传 `--version`。发布会跳过内容未变化的重复提交（"Publishing skips unchanged content"）；但单独改 `--categories`/`--topics` 即使文件没变也会产生新 patch 版本。
  来源：[docs/publishing.md](https://github.com/openclaw/clawhub/blob/main/docs/publishing.md)、[docs/quickstart.md](https://github.com/openclaw/clawhub/blob/main/docs/quickstart.md)
- Tag 是指向某个版本的字符串指针，`latest` 是常用值（类似 npm dist-tag）。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)

### slug / 命名

- 技能 slug 默认取自文件夹名，也可以在发布时用 `--slug` 显式指定，本质上就是 `name` 字段的取值规则：1–64 位小写字母/数字/连字符。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)
- 若 slug／owner handle／包 scope 已被占用且不是自己能管理的账号，发布会报"already claimed or reserved"类错误；如果认为该命名权本该归自己（品牌/项目名被占），走正式的 **Org / Namespace Claim** 流程（GitHub issue 模板 + 公开非敏感证据），不是简单换个后缀就能抢注/申诉。
  来源：[docs/namespace-claims.md](https://github.com/openclaw/clawhub/blob/main/docs/namespace-claims.md)、[docs/troubleshooting.md](https://github.com/openclaw/clawhub/blob/main/docs/troubleshooting.md)
- **实测（2026-09-18，`npx clawhub inspect <slug>`，未登录）：`dockerfile-check`、`iteration-report`、`handoff-doc-zh` 三个 slug 目前均返回 "Skill not found or unavailable to this account"，即未被占用。** 注册表状态会变，实际发布前建议再查一次。

### dry-run / 本地校验

- `clawhub skill publish <path> --dry-run`："Preview without publishing"。`clawhub sync --dry-run`："Show what would be published"。两者本机 `--help` 与文档描述一致。
  来源：`npx clawhub skill publish --help`、`npx clawhub sync --help`、[docs/publishing.md](https://github.com/openclaw/clawhub/blob/main/docs/publishing.md)
- **没有单独的 `clawhub skill validate` 命令**——`package validate` 是插件专用的（"Validate a local plugin package with the bundled Plugin Inspector"），不适用于技能。技能这边 `--dry-run` 就是最接近本地校验的手段。
  来源：`npx clawhub --help`、`npx clawhub package --help`

### 限流 / 配额

- 确认存在标准 429 限流机制：`Retry-After` / `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset`（或 `X-RateLimit-Reset`）响应头；文档举的场景主要是 search/install，以及"多人共用一个出口 IP 时匿名限额更容易触发，建议登录后重试"。
  来源：[docs/troubleshooting.md](https://github.com/openclaw/clawhub/blob/main/docs/troubleshooting.md)
- 本机实测佐证：连续 3 次 `npx clawhub inspect <slug>`（未登录）后，第三次返回里带 `(reset in 49s)` 倒计时字样，说明限流确实按较短周期计数，但**没有查到 `skill publish` 每日配额的具体数字**（不同于 SkillHub，本仓库 `docs/skillhub-growth.md` 记录过 SkillHub 约 100 次/天/账号的隐性上限，是实测出来的，非官方公布）。

### 审核方式

- 发布时服务端先做**结构校验**（元数据/名称/版本/文件/来源信息），校验不过**什么都不会发布**。校验通过后进入**自动化安全检查**，检查完成前新版本"可能不会出现在正常的安装和下载入口"，但记录已经创建（不是"审核通过才创建记录"，而是"创建了但可能先不公开可见"）。
  来源：[docs/publishing.md](https://github.com/openclaw/clawhub/blob/main/docs/publishing.md)
- 安全检查由 **ClawScan**（ClawHub 自研）整合三块信号：SkillSpector、**腾讯朱雀实验室 A.I.G** 扫描器、以及 ClawScan 自己的风险分析（参照 OWASP Agentic Skills Top 10：提示注入、工具滥用、凭证泄露、不安全执行、记忆/上下文投毒、过度授权等）。输出两个维度：审核状态 `Pass`/`Review`/`Warn`/`Malicious`/`Pending`/`Error`，风险等级 `Low`/`Medium`/`High`，以及带 `Info`~`Critical` 严重度的具体 finding，全部公开可见在技能详情页 `/<owner>/skills/<slug>/security-audit`。
  来源：[docs/security-audits.md](https://github.com/openclaw/clawhub/blob/main/docs/security-audits.md)
- 除自动扫描外还有社区举报 + 人工 moderation（可对发布方或具体版本下 moderation hold，隐藏内容；账号层面有基于"发布方滥用压力信号"的每日自动检测，触及阈值先自动警告，警告期后仍超阈值可能自动封禁）。
  来源：[docs/moderation.md](https://github.com/openclaw/clawhub/blob/main/docs/moderation.md)

### 登录方式

- 只支持 **GitHub OAuth**：`clawhub login` 走设备码流程（打印一次性验证码和 URL，另开浏览器授权，CLI 轮询拿 token），或用 ClawHub 网页 Settings 里生成的 API token 做无浏览器登录（`clawhub login --token`，适合 CI）。没有独立的邮箱/手机注册体系。
  来源：[docs/auth.md](https://github.com/openclaw/clawhub/blob/main/docs/auth.md)

### 许可证

- **所有发布到 ClawHub 的技能一律按 MIT-0 展示给下游使用者**（可用/改/再分发，含商用，且不要求署名），**不支持逐技能自定义许可证**，SKILL.md 里写别的许可证条款也不会生效。
  来源：[docs/skill-format.md](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)，"License" 节
- Acceptable Usage 明确把"违反许可证条款转发他人作品"列为不允许内容之一。
  来源：[docs/acceptable-usage.md](https://github.com/openclaw/clawhub/blob/main/docs/acceptable-usage.md)

### 版本信息

- 本机 `npx clawhub --help` 显示 `ClawHub CLI v0.23.3`；`npm view clawhub version` 同为 `0.23.3`；`homepage=https://clawhub.ai`，`repository=github.com/openclaw/clawhub`。

### 实测：三个技能的 `--dry-run` 全部跑通（未登录）

2026-09-18，用 `tools/clawhub_prep.py` 生成的 `dist/clawhub/{dockerfile-check,iteration-report,handoff-doc-zh}` 直接跑 `clawhub skill publish <path> --slug <slug> --version <v> --categories ... --topics ... --dry-run --json`，**全程没有执行 `clawhub login`，三个都返回 `"ok": true, "status": "would-publish"`**。说明 `--dry-run` 本身不需要登录态，可以直接当本地校验用。三条真实返回：

| slug | version | fileCount | latestVersion |
|---|---|---|---|
| dockerfile-check | 0.1.0 | 2 | null |
| iteration-report | 0.1.2 | 6 | null |
| handoff-doc-zh | 0.1.1 | 2 | null |

两个具体发现，供后续正式发布时注意：

1. **相对路径会报错**："Path must be a folder"——第一次用相对路径 `dist/clawhub/dockerfile-check` 调用直接失败，换成绝对路径就成功了。原因未深究（大概率是 `npx clawhub` 拉起临时包时的 cwd 解析问题），但结论很明确：**`clawhub skill publish` 一律传绝对路径**，`tools/clawhub_prep.py` 打印的建议命令本身就是绝对路径，直接复制不会踩这个坑，自己手改成相对路径会踩。
2. **`iteration-report` 的 `fileCount` 是 6，但目录里实际有 7 个文件**（`SKILL.md` + `skill-card.md` + 3 个 `scripts/*.py` + 2 个 `references/*`）。`dockerfile-check`（2 个文件，含 SKILL.md）和 `handoff-doc-zh`（2 个文件，含 SKILL.md）的 `fileCount` 都和实际文件数对得上，只有 `iteration-report` 少算了一个，具体是哪个文件、为什么，本次没有深究（`--dry-run` 没有类似 `inspect --files` 的清单输出可以对照）。**建议正式发布前用 `--json` 再核对一次 fileCount，如果和预期不符，发布后用 `clawhub inspect iteration-report --files` 确认哪个文件没进去。**

## 据公开信息推测（需确认）

- **`version` 是否真的会被服务端从 frontmatter 读取，还是完全由服务端/`--version` 参数决定**：`docs/skill-format.md` 的"Basic frontmatter"示例里放了 `version: 1.0.0`，但 `docs/publishing.md` 又说"新技能从 1.0.0 起步，后续自动发下一个 patch"，通篇没提"读取 frontmatter 里的 version 字段"这件事。不确定 frontmatter 里写的版本号会不会被直接采用、被忽略、还是仅供人读。本仓库三个技能现有 `version:` 未做改动，建议第一次发布前显式传 `--version <frontmatter 里的值>`，避免和 SkillHub/WorkBuddy 开放平台上的版本号错位。
- **`metadata.openclaw.os` 的取值枚举**：`docs/skill-format.md` 字段参考表给的示例是 `["macos"]`、`["linux"]`；但另一处摘要（`docs.openclaw.ai/tools/creating-skills`，本次经网页摘要获取、未见原始 Markdown）说平台过滤值是 Node.js `process.platform` 风格的 `darwin`/`linux`/`win32`；本仓库 `iteration-report` 已经在用 `"win32"`，而 `dockerfile-check`、`handoff-doc-zh` 用的是 `"windows"`。三种写法（`macos`/`windows`/`win32`）没有一个在两份文档里同时出现过，无法确认哪个是 ClawHub 实际校验接受的值，也不确定这个字段是否真的做强校验（不像 `--categories` 那样文档明确写了"未知值发布失败"）。本次**没有改动**任何技能现有的 `os` 取值，建议登录后先对一个技能跑真实发布或看解析结果再决定要不要统一改成 `win32`。
- **ClawHub 是否有 `skill publish` 的每日/每小时配额数字**：文档只给了通用 429 机制和响应头，没有给具体数字。参照 SkillHub 实测出来的"约 100 次/天/账号"经验，建议 ClawHub 这边也按保守节奏来（间隔 ≥60–75 秒，见下方 runbook），出现 429 或"too many"提示再降速，而不是假设某个具体数字。
- **`ported/skills/*-zh`（如 `handoff-doc-zh`）这类基于他人 MIT 协议作品二次改编、包内附 `ATTRIBUTION.md` 的技能，发布到强制 MIT-0 展示的 ClawHub 是否有额外合规要求**：ClawHub 官方文档只说了"不支持逐技能许可覆盖""不允许违反许可证条款转发他人作品"，没有专门讨论"改编自 MIT 项目、已附署名文件"这种场景。MIT 许可证本身允许再分发时使用更宽松的条款，只要求保留原作者的版权/许可声明；由于 `ATTRIBUTION.md` 是 `.md` 文件（本次脚本不会删除任何 `.md` 文件），随包发布后署名声明仍然存在，从许可证条款字面看应该是兼容的——但这是本文档作者的推理，不是 ClawHub 官方给出的结论，正式发布这类技能前建议自行确认一遍，或者第一批只发原创技能（`dockerfile-check`、`iteration-report` 均为原创，没有这个问题）。
- **`clawhub.ai/tdavis009/skills/clawhub-skill-guide`**：这是 ClawHub 上一个用户（`tdavis009`）自己发布的"技能"，内容是他对 scanner 合规规则的个人总结，**不是官方文档**，其中"skill-creator 内置指南说不要加额外 YAML 字段的说法已过时，ClawHub 其实需要 env/metadata 字段"这类表述只代表该用户个人经验，本文档未采信为事实，仅供交叉参考。

## 与 SkillHub 的关键差异

| 维度 | SkillHub（skillhub.cn） | ClawHub（clawhub.ai） |
|---|---|---|
| 唯一标识写在哪 | frontmatter 里的 `slug:` 字段，需全网唯一，本仓库脚本维护一张 slug 映射表加后缀避重 | 默认取文件夹名/`name`，也可发布时用 `--slug` 覆盖，**不需要写进 frontmatter** |
| "tags" 含义 | 关键词/话题标签，供文本检索匹配，建议 8–12 个中英文词 | **版本 dist-tag**（如 `latest`），和关键词无关；关键词对应的是 `--topics`（≤5，自由词）+ `--categories`（≤3，14 个固定分类之一） |
| 搜索机制 | CLI/站内按 `slug/name/description/summary/tags` 文本匹配，未命中退回热门列表（本仓库 `docs/skillhub-growth.md` 记录） | 向量/embedding 语义检索（`text-embedding-3-small`），`description` 本身就是主要检索输入 |
| 文件类型限制 | 无扩展名文件会被拒（本仓库实测过 400"不允许的文件类型: LICENSE"，见 `tools/skillhub_prep.py` 注释） | 官方文档明确接受任意扩展名文件；但拒收 `.pyc/.pyo/.pyd`（SkillHub 未见类似规则） |
| 包大小 | 未见 SkillHub 官方数字（本仓库另一处 3MB/20MB 限制是 WorkBuddy"开放平台"的规则，不是 SkillHub） | 总大小 ≤50MB，写在官方文档里 |
| 版本号从哪来 | frontmatter `version:` 自己写，SemVer 格式 | 服务端自动管理，新技能 1.0.0 起步、后续自动升 patch，`--version` 仅在需要显式指定时传 |
| 登录方式 | 实名认证（手机/邮箱），独立账号体系 | GitHub OAuth 设备码登录，无独立注册 |
| 许可证策略 | 未强制统一（本仓库脚本自报 `license: MIT`） | 平台强制全部 MIT-0 展示，不支持逐技能许可覆盖 |
| dry-run | 有（`skillhub publish ... --dry-run`，本仓库四个技能实测通过，见 `docs/submission-checklist.md`） | 有，但**不校验 `--categories`/`--topics` 合法性**，这部分只在真正发布时才验证 |
| 发布频率上限 | 实测约 100 次/天/账号（`docs/skillhub-growth.md` 记录，非官方公布） | 官方只给通用 429 机制，无公开具体数字（需确认） |
| 审核方式 | 三线机器审核：内容合规 / 漏洞扫描 / 云鼎模型安全，通过即自动上架 | ClawScan：SkillSpector + 腾讯朱雀 A.I.G + 风险分析（OWASP Agentic Skills Top 10），公开审核状态与风险等级 |
| metadata.openclaw | 不适用（SkillHub 没有这个字段体系） | 本仓库技能已经在用这个字段（`requires.bins`/`os`/`emoji`），**结构基本免改造** |

## 本仓库三个试跑技能现状核对

`skills/dockerfile-check`、`skills/iteration-report`、`ported/skills/handoff-doc-zh` 的 frontmatter 已经具备 `name`（与目录同名）、`description`（长且含中文触发场景词，对 ClawHub 的语义检索友好）、`version`（合法 SemVer）、`metadata.openclaw`（`requires.bins`/`os`/`emoji`，字段名与 ClawHub 原生 schema 一致）。相比 SkillHub 需要整段注入新字段头，**这三个技能理论上不改 frontmatter 也能发布**；`tools/clawhub_prep.py` 只做了"清掉 ClawHub 会拒收的内容"（`__pycache__`/字节码文件）和"顺手补一个 `metadata.openclaw.homepage`"两件事，细节见脚本内注释。
