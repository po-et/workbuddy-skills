---
name: wizard-zh
description: 生成交互式 bash 向导脚本，一步步带人完成只有人能做的手工操作：开通基础设施、配置凭证与 CI 密钥、在陌生的第三方后台点选、一次性迁移或切换。当用户说「写个脚本带我把这些环境变量配好」「新人接手要在十个后台里申请密钥，做个向导」「把这次迁移的手工步骤做成一步步确认的脚本」时使用；Agent 自己能做的步骤不要用它。附带 template.sh 库：分阶段进度、确认门、跨平台打开 URL（含 WSL）、隐藏密文输入、幂等写入 .env、写 GitHub secrets/variables、结束摘要——只需在 STAGES 标记之后编写阶段。流程：先读仓库（.env.example、README、docker-compose、CI 里的 secrets.* 引用）列出阶段与要采集的值让用户确认 → 写清每阶段的路径（打开哪个 URL、点什么、复制什么、写到哪、是否密文）→ 复制模板按依赖顺序写阶段 → bash -n / shellcheck 静态核对，不真跑。改编自 Matt Pocock 的 wizard（MIT）。
author: Captain
version: 0.1.0
display_name: "人工步骤向导生成器"
display_name_en: "Wizard Generator (zh)"
description_zh: "把只有人能做的手工流程（申请密钥、配 CI secrets、后台点选、切换迁移）做成分阶段确认的 bash 向导：自带进度、确认门、开 URL、密文输入、写 .env 与 GitHub secrets。"
description_en: "Turn human-only procedures (credentials, CI secrets, third-party dashboards, cutovers) into a staged bash wizard with progress, confirmation gates, URL opening, hidden secret entry, .env and GitHub secrets writes."
examples_zh:
  - "做一个向导脚本，带新同事把 .env.example 里的所有密钥申请并填好"
  - "这次数据库切换要人操作五步，做成带确认的脚本"
  - "把 CI 需要的 secrets 全部配置成一个向导"
examples_en:
  - "Build a wizard that walks a new teammate through every key in .env.example"
  - "This DB cutover has five manual steps, script them with confirmations"
  - "Make a wizard for all the secrets CI needs"
metadata:
  { "openclaw": { "requires": { "bins": ["bash"] }, "os": ["darwin", "linux"], "emoji": "🪄" } }
---

# 人工步骤向导生成器

**向导**是一个 bash 脚本，一步步带人完成一段手工流程——那种手做很烦、每次跟 AI 重新解释也很烦的流程：打开每个 URL、说清点哪里复制什么、采集值、写到该去的地方（`.env`、GitHub secrets）、每一步确认、显示还剩几步。可能是配置第三方服务、跑一次性迁移、把项目从一个状态切到另一个状态。

好用的交互已经由 `template.sh` 解决：分阶段进度、确认门、跨平台打开 URL（含 WSL）、隐藏密文输入、幂等的 `.env` 写入、`gh secret` / `gh variable` 写入、结束摘要。**你的工作只是界定流程并编写阶段**。`STAGES` 标记之上的库在每个向导里完全相同，这种一致性就是重点：永远不要手改它。
向导默认是一次性的：为一次运行而建，存到临时或 `scripts/` 路径，用完删掉。只有用户想要一条可重复的、住在仓库里的初始化路径时才提交。

## 流程

### 1. 界定流程
列出人必须做的每一步和沿途采集的每个值。**先读仓库，别冷启动地问**：初始化类看 `.env`、`.env.example`、`.env.*`、README、`docker-compose*`、框架配置、`.github/workflows/*`（每个 `secrets.*` / `vars.*` 引用都是向导必须产出的值）；迁移/切换类看当前状态、目标状态、二者之间不可逆的操作。
然后把有序的阶段列表和每阶段产出的值给用户确认，允许增删改序。
**完成标准**：每个阶段按序命名；每个采集值都知道 (a) 人从哪拿到 (b) 写到哪（`.env`、GitHub secret、两者、或不写——有的阶段是纯动作）(c) 是否密文（隐藏输入）。

### 2. 写清每阶段的路径
每阶段写下人要走的精确路径：打开哪个 URL、在那做什么、值显示在哪、填哪个变量，例如"控制台 → 开发者 → API 密钥 → 显示测试密钥 → 复制"。**不知道当前 UI 或确切命令时就说不知道**，问用户或查文档，绝不发明可能不存在的步骤。
**完成标准**：每个阶段都能追溯到陌生人也能照做的具体指令。

### 3. 编写向导
把 `template.sh` 复制到目标路径，把示例阶段替换为按依赖顺序的一个个 `stage`。用库里的助手：`stage`、`say`/`step`、`open_url`、`ask`/`ask_secret`、`write_env`、`set_secret`/`set_var`、`pause`/`confirm`。把 `TOTAL_STAGES` 设为你写的阶段数。
守住模板定下的标准：先打开 URL 再问它的值；密文一律 `ask_secret`；每个要持久化的值都 `write_env`；只把 CI 真正需要的值 `set_secret`；不可逆操作前 `confirm`。每个 `stage` 会清屏只显示当前步骤——一个阶段只做一件聚焦的事，别让人需要的信息滚出屏幕。不动标记之上的库。

### 4. 核对与交付
`bash -n <脚本>`；有 `shellcheck` 就跑；`chmod +x`。**不要自己端到端跑它**——它会打开浏览器并阻塞等人输入。改为静态追踪：第 1 步的每个值都被采集并落到第 1 步说的地方；每个 `set_secret` 的名字与 CI 里的 `secrets.*` 引用完全一致。告诉用户怎么运行。若是可重复的初始化路径，提交并在 README 链接，让下一个人跑脚本而不是问 AI。

## 模板速览
`template.sh` 随本技能附带（MIT）。结构：顶部库（进度/确认/打开 URL/输入/写入助手）→ `# ===== STAGES =====` 标记 → 你的阶段 → 结束摘要。阶段写法示意：
```bash
stage "申请支付网关测试密钥"
open_url "https://dashboard.example.com/developers/api-keys"
step "点「Reveal test key」，复制 sk_test_ 开头的值"
ask_secret STRIPE_TEST_KEY "粘贴测试密钥"
write_env STRIPE_TEST_KEY "$STRIPE_TEST_KEY"
set_secret STRIPE_TEST_KEY "$STRIPE_TEST_KEY"
confirm "已在网关后台把 webhook 指向 $WEBHOOK_URL 了吗？"
```

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `wizard`（MIT），`template.sh` 原样随附。改动见 ATTRIBUTION.md。
