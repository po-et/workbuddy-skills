---
name: constraints-md-zh
description: 约束驱动开发、把项目质量标准写成可机械检查的 CONSTRAINTS.md、防止 Agent 悄悄降低标准。当用户说「定一下我们的质量标准」「加质量门禁」「覆盖率定多少合适」「AI 老是加 ts-ignore / 跳过测试来变绿」「怎么防止代理为了通过而放水」「性能/无障碍预算怎么定」时使用。流程：先探测（栈、测试器、linter、现有覆盖率、CI、代理框架）再问；四个带默认值的问题；写 CONSTRAINTS.md（底线：不新增抑制注释、不留桩、不跳测、无密钥、本文件不为通过而被削弱；带数字与检查命令的维度；只测量不强制的棘轮；带负责人与到期日的例外）；每个维度装事实标准工具；按 BUILD/VERIFY/REVIEW/SHIP 阶段与成本分配；守住标准本身的五种放水动作；至少一个外部约束；没数字就棘轮；合理默认值表；三级升级。改编自 addyosmani/agent-skills 的 constraint-driven-development（MIT）。
author: Captain
version: 0.1.0
display_name: "约束驱动开发（CONSTRAINTS.md）"
display_name_en: "Constraint-Driven Development (zh)"
description_zh: "把质量标准写成能机械检查的 CONSTRAINTS.md：底线 + 带数字与命令的维度 + 棘轮 + 有期限的例外；按阶段与成本分配检查；盯住 Agent 放水的五种动作；至少一个外部约束。"
description_en: "Write the quality bar as a mechanically checkable CONSTRAINTS.md: a floor, dimensions with numbers and commands, ratchets, expiring exceptions; place checks by phase and cost; watch the five ways agents lower the bar; keep at least one external constraint."
examples_zh:
  - "给这个项目定一份质量约束，AI 写的代码必须过"
  - "覆盖率现在 62%，标准定 80% 合理吗"
  - "AI 为了让 CI 变绿删了测试，怎么防"
examples_en:
  - "Set up quality constraints this project's AI-written code must pass"
  - "Coverage is 62%, is an 80% bar reasonable"
  - "The agent deleted tests to make CI green, how do I prevent that"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "📏" } }
---

# 约束驱动开发（CONSTRAINTS.md）

其他技能描述"好"长什么样，都活在 Agent 读了也未必照做的散文里，且不跨会话。本技能产出不同的东西：**这个项目**的标准，带数字，活过对话，可机械检查。
原因：你自己写代码时，读一遍就知道好不好；Agent 一下午写的比你一周读的多，判断只能从脑子里搬进围绕循环运行的检查——它们要存在、要有你真选的数字、要在离工作足够近的地方触发，让 Agent 修自己的输出。规格驱动说做什么，测试驱动证明它能用，约束驱动定义"好到能上线"是什么。

用于：新项目或大功能且质量标准没写下来；用户要"定标准/加门禁/别让代理发垃圾"；Agent 的产出没人逐行看；CI 有检查但没人说得清哪些拦合并；覆盖率/性能/无障碍每个 PR 都在吵而不是定一次；要跑自主循环而唯一防线是 Agent 自己写的测试套件。不用于：已有 CONSTRAINTS.md 且不改（读它照做）；一次性脚本与原型；用户此刻要的是评审或建流水线。**访谈需要在线的人**，CI/自主运行里只应用底线并标记给人。

## 流程
1. **先探测再问**：栈（package.json / pyproject / go.mod / Cargo）、测试器、现有 linter、今日覆盖率、CI、代理框架（.claude/ .codex/ AGENTS.md）。两行汇报发现，只问剩下的。
2. **四个问题，每个带默认值**（"不知道"也是完整答案）：Q1 底线之外要强制哪些——覆盖率/安全扫描/性能预算/无障碍/架构边界？猜 (a)(b)；说清成本（性能与无障碍要有可访问 URL，架构要写规则文件）。Q2 中途检查失败是阻塞还是警告？猜阻塞；默认底线阻塞、其余头两周警告。Q3 有目标数字还是测今天的值然后守住？猜测量；默认测量并守住（棘轮）。Q4 能容忍的最慢检查时长？猜 90 秒；默认任务结束 90 秒、CI 不限。**到四个为止。**
3. **写 CONSTRAINTS.md**（仓库根，任何框架的 Agent 都能读，改动进评审）：
   - 底线（始终强制、无需安装）：不新增抑制注释（`@ts-ignore` `eslint-disable` `# noqa` `# type: ignore`）；不留未实现的桩（`throw new Error("Not implemented")`、空 catch）；不跳过或删除测试除非提交信息写理由；源码无密钥；**本文件不为让某次改动通过而被削弱**。
   - 带数字的维度表：维度 / 规则 / 检查命令 / 运行时机（类型零错误 `tsc --noEmit` 每次编辑；lint 零错误；密钥 `gitleaks detect --redact`；改动行覆盖率 ≥ 80%；代码安全无高危 `semgrep`；依赖无高危 `osv-scanner`；无障碍零严重 `axe`；性能 LCP ≤ 2500ms、CLS ≤ 0.1 `lighthouse`）。**每行都要有产出裁决的命令，有数字没命令的是愿望不是约束。**
   - 只测量不强制：项目覆盖率 今日值 不得下降；主包体积 今日值 不得增长。
   - 例外表：ID / 规则 / 路径 / 原因 / 负责人 / 到期日。
   然后在 AGENTS.md / CLAUDE.md 加一行：写代码前读 CONSTRAINTS.md，不为让改动通过而削弱它。
4. **每个维度装事实标准工具**，不自造检查器（类型 tsc/mypy；lint 现有配置；覆盖率测试器自带；代码安全 semgrep；密钥 gitleaks；依赖 osv-scanner；页面性能 lighthouse；包体积 size-limit；无障碍 axe-core；架构 dependency-cruiser；断言质量 stryker）。五个坑：gitleaks 的 `--redact` 不可省（否则密钥落进 Agent 记录）；lighthouse 与 axe 要能跑的 URL，没有就砍掉维度而不是编一个跑不了的检查；贵的检查限定到 diff（全仓 stryker 几小时会被关掉，改动文件一分钟内）；覆盖率不要跑第二遍测试，读已有 lcov 与 git diff 求交；semgrep 注册表规则免费跑但再分发要看许可。写进项目脚本：`check:fast`（类型 + lint + 密钥）、`check:task`（+ 覆盖率）、`check:full`（+ semgrep + osv）。CONSTRAINTS.md 是规范源，脚本是镜像，漂移以文件为准。
5. **接到生命周期**：BUILD 类型/lint/密钥/底线，几秒、只查改动文件；VERIFY 相关测试 + 改动行覆盖率，90 秒内；REVIEW 全部 + 守护检查，分钟级；SHIP 方向检查、无回退，CI。两条规则：限定到 diff（改动行覆盖率是 Agent 能推动的数字，项目覆盖率是它继承的）；成本决定位置（几秒以上的移出编辑循环）。**到处都跑是最大的错误**：拖住 Agent 的检查会被关掉，被关掉的门比没门更糟，因为标准看起来还在。
6. **守住标准本身**：Agent 不会精巧钻空子，它撞到红灯就走最便宜的路变绿。评审时盯五种动作：阈值动了（预算降低、级别下调、检查移出快速阶段——对比分支起点的 CONSTRAINTS.md）；测试变容易了（`.skip`、删测试文件、断言被抽走）；检查器被静音（新的 `@ts-ignore`/`eslint-disable`；四种要特别注意：`istanbul ignore` 把代码踢出覆盖率、`Stryker disable` 藏存活突变、`nosemgrep`、`gitleaks:allow`）；工作没做完（抛错的桩、把失败变沉默的空 catch、站在实现位置上的 TODO）；例外表多了一行没人讨论过。**收紧应无声，放松应大声。** 底线没有事实标准工具，Agent 会各写各的检查器；用一份 diff 范围的参考实现（退出码 0/1/2，按生态调整模式）而不是重造。
   按"Agent 能不能靠写不能用的代码通过它"给检查排序：外部（axe 编码 WCAG、osv 读漏洞库、lighthouse 测真浏览器——Agent 无法争辩）> 项目（你的 lint 规则、层边界，人拥有文件）> 套件（你自己的测试，最有用也唯一真循环）。全是第三种的标准不如有一个外部意见的；**确保至少一个外部约束。**
7. **没数字就棘轮**：62% 的代码库定 80% 只会得到永远红的构建和学会忽视红灯的团队。记录今天的值、拒绝变差，改善就更新，下降就是发现。这也回答了对训练的质疑：模型因通过测试被奖励，架构腐烂几个月才显形进不了权重——棘轮就是那个缺失的、写在构建看得见的地方的惩罚。

## 合理默认值
改动行覆盖率 ≥ 80%（够逼出测试、允许一行配置）；项目覆盖率 今日值不降；突变分数起步 ≥ 60%（80% 成熟）；依赖漏洞 无高危及以上；LCP ≤ 2500ms、CLS ≤ 0.1（Web Vitals 好的阈值）；无障碍 零 critical/serious；例外寿命 90 天；棘轮容差 0.5%。数字和理由一起写，没理由的阈值会被下一个撞上它的人删掉。

## 三级升级
1 只写下来（成本零，抓诚实错误，靠 Agent 遵守）→ 2 脚本化（`npm run check` 接到编辑后钩子与 CI，确定性、无新依赖）→ 3 工具支撑（处理 diff 范围、预算、棘轮、守护检查的专用运行器，检查 shell 超过约三十行时）。多数项目停在 2。首次可以只上底线（diff-only、无需安装），再逐个维度装工具；机器级安全工具可只在 CI 跑，在"运行时机"列写明。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "代码稳定了再加约束" | 代码会稳定在它移动时被允许的样子 |
| "测试就是约束" | 你写的测试只证明你同意自己；说不了新代码覆盖率、依赖风险、包体积 |
| "我们达不到 80%" | 那就别定 80%；定今天的数字并守住 |
| "会拖慢 Agent" | 只有把慢检查放进快循环才会；那是放置错误不是反对约束的理由 |
| "标准我记得" | Agent 不记得，而它写了大部分代码 |
| "约束会挡住发布" | 带负责人和日期的例外解封你；删掉约束解封所有人到永远 |

## 红灯
访谈超过四问或产出用户解释不了的配置；定了今天就过不了且没有达成计划的预算；有数字没工具；有事实标准却手搓检查器；所有约束都由项目自己的测试裁决；CONSTRAINTS.md 与它拦下的功能在同一提交里被改；例外无负责人或到期超过一年；Agent 提议放宽阈值而不是修代码；慢检查进了编辑循环且有人开始 `--no-verify`；写完没人再打开过。

## 验收
- [ ] CONSTRAINTS.md 存在且每个数字有理由　- [ ] 底线在当前代码库上无改动即可通过　- [ ] 选中的每个维度装了工具且命令今天能跑
- [ ] 每条约束写明运行时机，快速阶段几秒内　- [ ] 至少一个外部约束　- [ ] 只测量指标记录今日值与方向　- [ ] 例外有负责人与到期日
- [ ] AGENTS.md / CLAUDE.md 指向该文件　- [ ] 在当前分支试跑没有用户不同意的失败

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `constraint-driven-development`（MIT）。改动见 ATTRIBUTION.md。
