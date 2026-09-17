---
name: triage-zh
description: 工单分诊、Issue 与外部 PR 的分诊状态机、给 AI Agent 写可执行的「Agent 简报」、维护「不做清单」（.out-of-scope 知识库）防止同一需求反复被提。当用户说「帮我分诊一下 issue」「看看哪些 issue 需要处理」「把 #42 标成 ready-for-agent」「这个需求之前是不是拒过」「给这个 issue 写个 Agent 简报」「外部 PR 怎么处理」时使用。适用 GitHub Issues、GitLab Issues、Jira 等任何工单系统。规则：每条分诊评论以「本内容由 AI 在分诊时生成」开头；两个类别角色（bug / enhancement）+ 五个状态角色（needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix），每个工单恰好一类别一状态；分诊前先查「是否已实现」与「是否曾拒绝」；先验证再拷问；wontfix 分三种（已实现 / 拒绝 bug / 拒绝需求→写入 .out-of-scope）。附 Agent 简报模板与不做清单格式。改编自 Matt Pocock 的 triage（MIT）。
author: Captain
version: 0.1.0
display_name: "工单分诊状态机"
display_name_en: "Issue & PR Triage (zh)"
description_zh: "把 Issue 和外部 PR 推过一个小状态机：分类、验证、必要时拷问、写 Agent 能直接执行的简报；拒绝的需求进 .out-of-scope 知识库防止再被提。适用 GitHub/GitLab/Jira。"
description_en: "Move issues and external PRs through a small state machine: categorize, verify, grill if needed, write agent-ready briefs; rejected enhancements go into a .out-of-scope knowledge base. Works with GitHub/GitLab/Jira."
examples_zh:
  - "看看有哪些 issue 需要我处理"
  - "分诊 #42，看是给 Agent 做还是人来做"
  - "把 #57 标成 wontfix，这个功能我们不做"
examples_en:
  - "Show me issues that need attention"
  - "Triage #42: agent or human?"
  - "Mark #57 wontfix, we won't build that"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🩺" } }
---

# 工单分诊状态机

把工单系统里的 Issue（以及外部 PR）推过一个小小的状态机。**PR 就是带代码的 Issue**：同样的角色、同样的状态、同样的流程，只在标注「PR 场景」处略有差异。用户说 `#42` 时，按工单系统的规则解析成 Issue 或 PR。

分诊过程中发到工单系统的每条评论都**必须**以这句开头：

```
> *本内容由 AI 在分诊时生成。*
```

参考文档：
- [AGENT-BRIEF.md](AGENT-BRIEF.md)：怎样写一份经得起时间的 Agent 简报
- [OUT-OF-SCOPE.md](OUT-OF-SCOPE.md)：`.out-of-scope/` 不做清单知识库的用法

## 角色

两个**类别**角色：
- `bug`：有东西坏了
- `enhancement`：新功能或改进

五个**状态**角色：
- `needs-triage`：等维护者评估
- `needs-info`：等提交者补充信息
- `ready-for-agent`：已完整定义，可交给 AI Agent 离线完成
- `ready-for-human`：需要人来实现
- `wontfix`：不处理

PR 场景下同样的状态对着代码读：`ready-for-agent` = 已附简报、Agent 该对这个 diff 做下一步；`ready-for-human` = 可以由人合并了。

每个分诊过的工单**恰好**带一个类别角色和一个状态角色。状态冲突时先标出来问维护者，不要擅自动。

这些是规范角色名，工单系统里的实际标签名可能不同（比如 Jira 里可能是自定义字段）。开始前让用户给出映射；没有映射就问，不要猜。

状态流转：未打标签的工单先进 `needs-triage`；从那里去 `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`；`needs-info` 在提交者回复后回到 `needs-triage`。维护者随时可以覆盖；看到不寻常的流转先问再动。

## 调用方式

维护者用自然语言描述想干什么，你解释并执行：
- 「看看有什么需要我处理的」
- 「看下 #42」（Issue 或 PR）
- 「把 #42 标成 ready-for-agent」
- 「有哪些可以给 Agent 领走的？」

## 展示待处理项

查询工单系统，按最旧在前分三桶展示：
1. **未打标签**：从未分诊。
2. **`needs-triage`**：评估中。
3. **`needs-info` 且提交者在上次分诊记录之后有新动静**：需要重新评估。

PR 在范围内时，把外部 PR 也放进这三桶，每行标 `[PR]` 或 `[issue]`。自动发现只列**外部**贡献者的 PR（谁算外部由工单配置定义），协作者自己的进行中 PR 不算分诊工作。这个过滤只作用于自动发现；被点名的 PR 不管谁提的都分诊。

每项给计数和一行摘要，让维护者挑。

## 分诊一个具体工单

1. **收集上下文。** 通读工单全文（正文、评论、标签、作者、日期；PR 还要读 diff）。解析已有的分诊记录，别把已解决的问题再问一遍。用项目的领域术语表探索代码库，尊重相关区域的 ADR。对代码库做两项检查：(a) **冗余检查**：按领域概念（不只是工单原话的措辞）搜索是否已有实现，并报告你查了哪里；找到了就是「已实现型 wontfix」（见第 5 步）。(b) **既往拒绝检查**：读 `.out-of-scope/*.md`，把相似的翻出来。
2. **给建议。** 告诉维护者你推荐的类别与状态、理由，以及与请求相关的代码库摘要（含是否已实现）。等指示。
3. **验证主张。** 拷问之前先核实说法站得住脚。bug：按提交者的步骤复现。PR：确认 diff 做到了它声称的事——签出、跑相关测试或命令。汇报结果：已确认（附代码路径）、失败、或细节不足（这是很强的 `needs-info` 信号）。验证过的主张能写出强得多的 Agent 简报。
4. **拷问（按需）。** 请求需要打磨时，配合「拷问我」与「领域建模」技能，一轮一轮提问把它磨成形；随着决策落地，同步更新 `CONTEXT.md` / ADR。
5. **落实结果：**
   - `ready-for-agent`：发一条 Agent 简报评论（[AGENT-BRIEF.md](AGENT-BRIEF.md)）。
   - `ready-for-human`：结构同 Agent 简报，但说明为什么不能委托给 Agent（判断题、需要外部权限、设计决策、手工测试）。
   - `needs-info`：发分诊记录（模板见下）。
   - `wontfix`：关闭工单，评论内容取决于**原因**：
     - **已实现**：代码库里已经有了。指出它在哪；**不要**写进 `.out-of-scope/`（那是给「拒绝的需求」用的，不是「已建成的功能」）。
     - **拒绝（bug）**：礼貌解释后关闭。
     - **拒绝（需求）**：写入 `.out-of-scope/`，评论里链接过去，然后关闭（[OUT-OF-SCOPE.md](OUT-OF-SCOPE.md)）。
   - `needs-triage`：打上角色。有部分进展可以选择性留评论。

## 快速覆盖状态

维护者说「把 #42 标成 ready-for-agent」，信任他直接打角色。先确认你将做的事（改角色、评论、关闭），再执行。跳过拷问。如果没经过拷问就要进 `ready-for-agent`，问一句要不要写 Agent 简报。

## needs-info 模板

```markdown
## 分诊记录

**目前已确认：**

- 要点 1
- 要点 2

**还需要你（@提交者）补充：**

- 问题 1
- 问题 2
```

把拷问中已经解决的内容全部记在「目前已确认」下，别让工作白费。问题必须具体、可回答，不能是「请补充更多信息」。

## 续接之前的分诊

工单上已有分诊记录时，先读，看提交者有没有回答未决问题，给出更新后的全貌再继续。不要重复问已解决的问题。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `triage`（MIT）。改动见 ATTRIBUTION.md。
