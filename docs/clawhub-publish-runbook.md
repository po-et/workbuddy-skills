# ClawHub 发布 Runbook（代理执行部分）

只覆盖用户登录**之后**、由代理执行的分步操作。规则依据见 [clawhub-notes.md](clawhub-notes.md)；生成/校验用 [`tools/clawhub_prep.py`](../tools/clawhub_prep.py)（先读它），批量发布用 [`tools/clawhub_publish.sh`](../tools/clawhub_publish.sh)。

**代理不做的事**：不执行 `clawhub login` / `clawhub logout`，不接触任何 token（`npx clawhub token` 也不要跑），不改 `skills/`、`ported/skills/` 里的源文件。

## 0. 前提（用户本人完成）

```bash
npx clawhub login      # GitHub OAuth 设备码登录，会打印一个验证 URL，用户自己在浏览器里授权
npx clawhub whoami      # 确认已登录；代理可以帮忙跑这一条确认状态，因为它不需要凭证输入
```

`whoami` 返回正常（不是 401/Unauthorized）之后，后面的步骤才能真正发布成功；`--dry-run` 不需要登录也能跑（2026-09-18 实测过，见 clawhub-notes.md），所以步骤 1–2 即使还没登录也可以先做。

## 1. 生成发布副本

```bash
cd /Users/limit/AI/My-Research/workbuddy-skills
python3 tools/clawhub_prep.py --out dist/clawhub dockerfile-check iteration-report handoff-doc-zh
```

- 输出到 `dist/clawhub/<slug>/`，不改 `skills/`、`ported/skills/` 里的源文件。
- 会清掉 `__pycache__` 和 `.pyc/.pyo/.pyd`（ClawHub 硬性拒收，见 clawhub-notes.md），并在 `metadata.openclaw` 里补一个 `homepage`（如果原来没有的话）。
- 脚本自带 `check()`：`FAIL` 开头说明有硬伤（name/description 缺失、超 50MB、含字节码文件），必须先修；`!` 开头是提醒（比如 `os` 里写的是 `"windows"` 这个未经交叉确认的枚举值），不阻塞发布，但发布前建议看一眼。
- 要发布更多技能，就在命令行后面加名字；`--strip-extensionless` 默认关闭（ClawHub 本身不要求，见脚本头部注释），一般不需要加。

## 2. 本地校验

ClawHub 没有单独的 `clawhub skill validate` 命令（`package validate` 是插件专用的），能用的本地校验只有两层：

1. 上一步 `clawhub_prep.py` 自带的 `check()`（已经跑过了）。
2. `clawhub skill publish --dry-run`——**必须用绝对路径**，`clawhub_prep.py` 结尾打印的命令本身就是绝对路径，直接复制粘贴：

```bash
python3 tools/clawhub_prep.py --out dist/clawhub dockerfile-check iteration-report handoff-doc-zh 2>&1 | tail -20
# 复制脚本打印的三条 "npx clawhub skill publish /Users/.../dist/clawhub/<slug> ... --dry-run" 逐条跑
```

预期每条返回 `"ok": true, "status": "would-publish"`（2026-09-18 对这三个技能实测过，见 clawhub-notes.md）。**注意 `--dry-run` 不校验 `--categories`/`--topics` 是否合法**——分类必须是官方 14 个固定 slug 之一，拼错了 dry-run 不会提醒，只有真正发布时才会报错，所以这一步之外还要人工核对一遍 `tools/clawhub_prep.py` 里 `CATEGORIES` 字典的值是不是在这个列表里：`integrations`/`automation`/`research`/`development`/`productivity`/`communication`/`creative`/`knowledge`/`agents`/`operations`/`security`/`finance`/`lifestyle`/`other`。

## 3. 逐个发布（间隔）

ClawHub 官方没公布 `skill publish` 的具体配额数字，保守起见沿用 SkillHub 实测出来的节奏：**间隔 ≥60–75 秒**，出现 429 或类似"too many"的提示就再放慢。

第一批只有 3 个技能，建议**逐条手动跑、每条看一眼结果**，而不是无人值守跑批量脚本——这样发现 slug 冲突或分类报错能立刻停下来处理，不会连续踩坑：

```bash
# 每条命令前手动记一下 "--- <slug>  HH:MM:SS ---"，方便事后登记
echo "--- dockerfile-check  $(date +%H:%M:%S) ---"
npx clawhub skill publish /Users/limit/AI/My-Research/workbuddy-skills/dist/clawhub/dockerfile-check \
  --slug dockerfile-check --version 0.1.0 \
  --categories development,security,operations \
  --topics "dockerfile,docker,container-security,lint,ci-gate" \
  --changelog "首次发布" --json
# 看到 status 是发布成功（不是 dry-run 预览）之后，等 ≥75 秒再发下一个

echo "--- iteration-report  $(date +%H:%M:%S) ---"
npx clawhub skill publish /Users/limit/AI/My-Research/workbuddy-skills/dist/clawhub/iteration-report \
  --slug iteration-report --version 0.1.2 \
  --categories productivity,development \
  --topics "sprint-report,git,changelog,standup" \
  --changelog "首次发布" --json

echo "--- handoff-doc-zh  $(date +%H:%M:%S) ---"
npx clawhub skill publish /Users/limit/AI/My-Research/workbuddy-skills/dist/clawhub/handoff-doc-zh \
  --slug handoff-doc-zh --version 0.1.1 \
  --categories agents,productivity \
  --topics "session-handoff,agent-handoff,context-management,chinese" \
  --changelog "首次发布" --json
```

`--version` 显式传成 frontmatter 里原有的版本号，不要留空——ClawHub 新技能不传 `--version` 时会直接从 `1.0.0` 起步（2026-09-18 dry-run 实测确认过），如果不传，会和 SkillHub / WorkBuddy 开放平台上这几个技能的版本号（0.1.x）错位。

之后如果要一次发一批（超过三五个、不需要每条都盯着看的场景），再用批量脚本，同样先 dry-run：

```bash
tools/clawhub_publish.sh /Users/limit/AI/My-Research/workbuddy-skills/dist/clawhub/*        # 默认 DRY_RUN=1，只预览
DRY_RUN=0 INTERVAL=75 tools/clawhub_publish.sh /Users/limit/AI/My-Research/workbuddy-skills/dist/clawhub/dockerfile-check   # 确认没问题后单个真发
```

`tools/clawhub_publish.sh` 只接受绝对路径（会自动跳过并提示相对路径），每个技能开始前打印 `--- <slug>  HH:MM:SS ---`；它不支持每个技能各自的 `--categories`/`--topics`（那样更适合像上面一样逐条手动跑），批量脚本适合"这批技能都用同一组 categories/topics，或者干脆不设"的场景。

## 4. 记录结果

ClawHub 的 `--json` 发布回执目前确认会带 `slug`/`version`/`fingerprint`/`fileCount` 这几个字段（dry-run 阶段实测到的字段，真正发布成功后是否多一个 release/attempt id 没有实测过，第一次真发布后看一眼输出再决定要不要抄）。参照 `docs/submission-checklist.md` 里已有的 "SkillHub（skillhub.cn……）" 小节格式，在同一个文件里加一节 "ClawHub（clawhub.ai）"，逐条记：

| slug | 来源 | 版本 | 发布时间 | 状态 |
|---|---|---|---|---|
| dockerfile-check | skills/dockerfile-check | 0.1.0 | HH:MM:SS | 已发布 / 审核中 |
| iteration-report | skills/iteration-report | 0.1.2 | HH:MM:SS | 已发布 / 审核中 |
| handoff-doc-zh | ported/skills/handoff-doc-zh | 0.1.1 | HH:MM:SS | 已发布 / 审核中 |

"状态"先填"已发布"（CLI 返回成功即代表版本记录已创建），安全扫描结果（`Pass`/`Review`/`Warn`/`Malicious`/`Pending`）要过一会儿去 `https://clawhub.ai/<owner>/skills/<slug>/security-audit` 页面看，扫描完成前技能可能不出现在正常搜索/安装入口，这是正常状态不是失败（见 clawhub-notes.md「审核方式」）。

## 已知坑速查

- **必须用绝对路径**，相对路径会报 `Path must be a folder`（实测）。
- **不传 `--version` 时新技能会变成 `1.0.0`**，不是 frontmatter 里的版本号（实测）；要保持版本号跨平台一致就显式传。
- **`--dry-run` 不检查 `--categories`/`--topics` 是否合法**，分类枚举拼错了只有真发布才报错。
- **`metadata.openclaw.os` 里 `"windows"` 还是 `"win32"` 还是 `"macos"` 没有交叉确认过**（本仓库技能目前两种写法都有），发布后如果技能页显示 OS 限制不对，去改这个值。
- **`ported/skills/*-zh`** 这类基于他人 MIT 作品改编、附 `ATTRIBUTION.md` 的技能，发布前确认 `ATTRIBUTION.md` 还在包里（`tools/clawhub_prep.py` 不会删 `.md` 文件），ClawHub 会把所有技能统一展示成 MIT-0——这不代表可以删掉对上游作者的署名文件。
- 发布是"创建了新的不可变版本记录"，不是"改了同一个文件"；发错了没法覆盖，只能发下一个 patch 版本或用 `clawhub delete`/`clawhub undelete` 处理，操作前想清楚。
