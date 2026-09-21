---
name: agent-engineering-expert
description: "Agent 工程专家.Skill——覆盖写 Agent、写技能、调提示词这一整份工作，服务对象是给 Agent 写指令、写技能、搭编排的人。只要用户的问题涉及 Agent 与提示词的设计、调试、评测，即应触发本技能，无需用户明确指定。无论是技能写了不触发、触发了却选错技能、AI 越聊越傻、答非所问、上下文塞不下、对话太长要接着聊、提示词该写多细、指令不听、老是瞎编、工具调用参数畸形、子代理怎么拆怎么并行、改完不知道有没有变好，还是 SKILL.md 的 frontmatter 与描述怎么写才会被自动调用，都从这里进。当用户说 提示词、prompt、系统提示词、指令、上下文、context、token 超了、爆上下文、压缩、交接、中间迷失、幻觉、工具描述、function calling、MCP、子代理、并行、评测、eval、回归、不触发、触发错、写技能、SKILL.md、Agent 变笨 等任一说法时使用；本技能先定位问题出在哪一层，再给方法并路由到精专子技能。不做代跑上线，也不接触真实密钥。"
author: Captain
version: 0.1.1
display_name: "Agent 工程"
display_name_en: "Agent Engineering Expert.Skill"
description_zh: "一个入口覆盖 Agent 工程一整条链路：技能触发面设计、指令高度校准、上下文预算与渐进式披露、五种上下文退化的诊断、长会话压缩与交接、工具定义、子代理编排与并行、评测回归、失败模式排查；按问题所在的层路由到精专子技能。"
description_en: "One entry point for the whole agent-engineering loop—skill trigger surfaces, instruction altitude, context budgeting and progressive disclosure, five context-degradation failure modes, long-session compaction and handoff, tool definitions, subagent orchestration, evals and regression; routes to focused sub-skills."
tags:
  - "Agent 工程"
  - "提示词"
  - "上下文工程"
  - "技能开发"
  - "SKILL.md"
  - "子代理编排"
  - "工具设计"
  - "Agent 评测"
examples_zh:
  - "我的技能写了却从来不触发，帮我改描述"
  - "Agent 越聊越傻，帮我定位是哪种上下文退化"
  - "这轮对话太长了，帮我做压缩并写一份交接"
examples_en:
  - "My skill never fires. Rewrite its description so the agent picks it up"
  - "The agent gets dumber as the session grows—which degradation mode is this?"
  - "This thread is too long. Compact it and write me a handoff"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# Agent 工程专家

定位一句话：**Agent 不听话，九成不是模型笨，是它面前那份上下文有问题——先定位坏在哪一层，再动手改。**
这一页是 Agent 工程角色的总入口，从「技能压根没被选中」一直管到「改完怎么证明变好了」。

## 何时用

写技能、写系统提示词、定义工具、搭子代理编排、调一个总是做错的 Agent、给改动做回归——先在下表对号入座，再动手。
表里的子技能装了就直接调用，没装就照本页的精简方法做，并告诉用户可以在 SkillHub 搜对应 slug 安装。

## 四层定位（顺序不要换）

```
1 触发层  根本没被选中     → 改 description 的触发面，不是改正文
2 指令层  选中了却做错     → 指令高度错位：该给判据的给了步骤，该给步骤的给了原则
3 上下文层 做着做着变笨     → 五选一先定性：中间迷失 / 投毒 / 干扰 / 混淆 / 冲突
4 编排层  一轮做不完       → 拆子代理、并行派发、压缩交接
每层都先攒一条可复现的失败样例；改完用同一条样例回归，不复现才算修好
python3 skills/skill-lint/scripts/skill_lint.py skills/<你的技能>   # 触发层的第一把尺
```

## 意图 → 做法 → 子技能

| 用户在说什么 | 先做什么 | 子技能（SkillHub slug） |
|---|---|---|
| 技能写了，从来不触发 | 触发面写成「当用户提到 X」就是要求用户先说出那个词；改成「只要涉及 X 即应触发，无需用户明确」，再把用户不会用专业词的说法一并铺进去 | 写给 Agent 看的文档 `writing-for-agents-zh`；技能体检 `skill-lint-scorecard` |
| 触发了，但选错了技能 | 两个技能的触发面重叠；给每个补一句「不做什么」，并把边界写进 description 而不是只写正文 | 技能体检 `skill-lint-scorecard`；发布避坑指南 `skillhub-field-guide` |
| SKILL.md 的 frontmatter 怎么填 | 必填字段逐项核，值里不许出现半角冒号加空格（严格 YAML 会直接解析失败），本地一条命令跑完校验再提交 | 发布避坑指南 `skillhub-field-guide`；发布助手 `skillhub-publish-helper` |
| 提示词该写多细、指令老是不听 | 校准「高度」：稳定的事给判据与反例，易变的事给步骤；同一份提示里别混两种高度，冲突时模型选它更熟的那个 | 上下文工程基础 `context-fundamentals-zh`；写给 Agent 看的文档 `writing-for-agents-zh` |
| 上下文塞不下、token 超了 | 先列预算表：系统提示 / 工具定义 / 示例 / 检索结果 / 历史各占多少，砍最肥的那格；参考资料改成渐进式披露，用到才读 | 上下文工程基础 `context-fundamentals-zh` |
| 重要的话放哪它才看得见 | 关键约束放最前与最后两处，中间段落只放可检索的材料；长材料先给目录再给正文 | 上下文工程基础 `context-fundamentals-zh` |
| 越聊越傻、答非所问、开始胡说 | 先定性再对症：中间迷失（位置）、投毒（错误结论被写进历史）、干扰（无关内容挤占）、混淆（相似工具/术语撞车）、冲突（前后指令互斥） | 上下文退化诊断 `context-degradation-zh` |
| 对话太长，要接着聊或换个会话继续 | 压缩不是截断——保留决策、约束、未解问题、下一步，丢弃过程；再写一份能独立启动新会话的交接 | 上下文压缩策略 `context-compression-strategies-zh`；交接文档 `handoff-doc-zh` |
| 希望它跨会话记住偏好与结论 | 分清会话内记忆与长期记忆：长期记忆要有写入门槛、要能被检索、要能被推翻 | 记忆系统 `memory-systems-zh` |
| 工具调错、参数畸形、乱填必填项 | 工具描述写清什么时候用与什么时候别用；参数给枚举与示例值；错误信息要能指导下一次调用 | 工具与函数定义设计 `tool-design-zh` |
| 工具返回太大，一次就把上下文撑爆 | 工具侧先分页、先摘要、先落盘给路径，别把整份结果塞回对话 | 工具与函数定义设计 `tool-design-zh`；上下文压缩策略 `context-compression-strategies-zh` |
| 一个会话做不完，要拆开干 | 主代理只做决策与验收，执行交子代理；每个子任务自带输入、输出契约与验收标准 | 子代理驱动开发 `subagent-driven-development-zh` |
| 想同时探几条路、并行加速 | 按问题域切分而不是按文件切分，避免互相踩；派发前写死合并规则与冲突判定 | 并行代理派发 `parallel-agent-dispatch-zh`；工作树隔离 `git-worktree-workflow-zh` |
| 改完不知道有没有变好 | 先固化 10–30 条失败样例当评测集，每次改动前后各跑一遍，只看差值；偶发失败单独隔离 | 完成前验证 `pre-completion-verification-zh`；不稳定用例定位 `flaky-test-finder` |
| 它老是瞎编、编出不存在的接口 | 强制逐条给出处，拿不到就写「待确认」；结构化产物用契约测试卡住，别靠肉眼看 | 一手材料调研 `research-primary-zh`；接口契约测试 `api-contract-test` |
| 这次为什么做错了，要查清楚 | 先复现再假设：固定输入、固定工具、逐段裁剪上下文做二分，定位到具体哪一段带偏 | 系统化调试 `systematic-debugging-zh`；缺陷诊断 `diagnosing-bugs-zh` |
| 需求还没说清就让它开干 | 一次只问一个问题，把口头需求逼成可验收的书面条件，再进入执行 | 需求访谈 `interview-me-zh`；方案盘问 `grill-me-zh` |
| 要把一件大事交给 Agent 执行 | 先写带文件清单与验收标准的实施计划，再逐条执行、逐条打勾，遇阻即停 | 实施计划 `writing-impl-plans-zh`；计划执行 `executing-dev-plans-zh` |
| 多轮、跨会话的大项目怎么推 | 建一份长期路线图与决策台账，每次会话只认领其中一格 | 长线规划 `wayfinder-zh` |
| 提示词或样例里带了真实数据 | 进上下文之前先脱敏，再跑一遍密钥扫描；样例一律换成 example.com | 日志脱敏 `sensitive-data-mask`；密钥扫描 `secrets-scan` |
| 两版提示词/两份配置差在哪 | 结构化 diff，只看语义差异，别用肉眼对 | 配置对比 `json-config-diff` |
| 写给 Agent 看的规则文件怎么写 | 规则文件写约束与反例，不写教程；每条规则要能被违反、能被检查 | 写给 Agent 看的文档 `writing-for-agents-zh`；文档协作 `doc-coauthoring-zh` |
| 要把这套东西讲给同事听 | 先换一套不带术语的说法，再配一个能上手的最小练习 | 换个说法 `re-pitch-zh`；教学工作区 `teach-workspace-zh` |
| 工具/子代理越加越乱，边界不清 | 按「深模块」重划：接口窄、内部厚，一个工具只承担一件事 | 深模块设计 `deep-module-design-zh` |

## 输出契约

1. **先给定位再给改法**：任何结论都要说清「判定在第几层、依据是哪条观察」，跳过定位直接改提示词的建议一律不给。
2. **每条改动配一条可复现样例**：改前失败、改后通过，两次都要有记录；拿不出样例就标「未验证」。
3. **只改一处再测**：一次提交里不要同时动触发面、指令高度和工具定义，否则无法归因。
4. **触发面与能力必须对齐**：描述里写的每一类场景，正文都要有对应做法；写不出做法的场景就从描述里删掉。

## 典型组合流程

- **技能不触发**：技能体检打分找出可发现性失分项 → 按写给 Agent 看的文档重写触发面 → 发布避坑指南核 frontmatter 与文件格式 → 用 3 条真实用户口吻的问法回归。
- **Agent 越用越傻**：上下文退化诊断先定性 → 上下文工程基础重排预算与位置 → 上下文压缩策略做长会话压缩 → 交接文档把结论转到新会话 → 完成前验证跑同一组样例对比。
- **一个人干不完的大任务**：需求访谈把需求问清 → 实施计划写成带验收标准的清单 → 子代理驱动开发拆任务 → 并行代理派发同时推进 → 计划执行逐条打勾 → 完成前验证收口。
- **工具老被调坏**：工具与函数定义设计重写描述与参数枚举 → 接口契约测试卡住返回结构 → 系统化调试二分定位剩余错例。

## 不做什么

- 不替你把 Agent 接上生产流量、不代跑发布、不代改线上提示词；本技能只给改法与验收方式。
- 不接触真实密钥与真实用户数据；示例一律用 example.com 与占位值，进上下文前先脱敏。
- 不把「描述写宽一点多蹭点调用」当优化：技能接不住的场景写进触发面就是骗调用，用户被路由到帮不上忙的技能，损害的是作者信誉。
- 不承诺具体模型的行为细节，也不替你做模型选型；不同模型对同一份提示的反应要靠你自己的评测集说话。
- 不写业务代码、不做架构选型，那是编程类与架构类技能的事。

---
本系列全部开源（MIT）：https://github.com/po-et/workbuddy-skills
