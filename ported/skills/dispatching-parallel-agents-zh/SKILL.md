---
name: dispatching-parallel-agents-zh
description: 并行派发子代理、把多个互不相干的问题同时交给多个 Agent 查、一次响应里发多个任务实现并发、子代理提示词怎么写、并行结果怎么合并。当用户说「这几个测试文件都挂了一起查」「多个模块同时出问题」「能不能并行处理」「同时派几个 Agent」「分头排查再汇总」「这些任务互相独立」时使用。判断标准是任务之间没有共享状态、没有先后依赖、单独看也能看懂；相关联的故障、需要全局视野的排查、还不知道坏在哪的探索式调试都不适合并行。要点：一个独立问题域派一个子代理；同一条响应里发出全部派发调用才是并发，一条一个就是串行；每个子代理的提示词必须聚焦、自包含、写明约束与产出格式；回收后要读摘要、查冲突、跑全量测试、抽查结论。
author: Captain
version: 0.1.0
display_name: "并行派发子代理"
display_name_en: "Dispatching Parallel Agents (zh)"
description_zh: "把多个互相独立的问题一次性分派给多个子代理并发处理：怎么判断能不能并行、怎么切分问题域、提示词四要素、回收后的冲突检查与全量验证。"
description_en: "Fan out independent problems to concurrent subagents: how to decide if they are truly independent, how to split problem domains, the four parts of a good agent prompt, and how to integrate and verify the results."
examples_zh:
  - "这几个测试文件都挂了一起查"
  - "多个模块同时出问题，能不能并行处理"
  - "分头排查再汇总"
examples_en:
  - "Three test files are failing for different reasons, fan them out"
  - "Can you investigate these independent modules in parallel"
  - "Dispatch one agent per failing subsystem and merge the results"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🧵" } }
---

# 并行派发子代理

你把任务派给拥有独立上下文的专职子代理。通过精确构造它们的指令与上下文，你保证它们专注并把事情做成。它们**不应该**继承你这次会话的上下文和历史——你要恰好给它需要的那些信息。这同时也保住了你自己的上下文，让它专心做协调。

**核心原则：一个独立问题域派一个子代理，让它们同时跑。**

多个互不相干的故障（不同测试文件、不同子系统、不同 Bug）挨个查是浪费时间——每一处排查都独立，本可以并行。

## 何时用

| 判断 | 结论 |
|------|------|
| 多处失败，但彼此相关（修好一个可能顺带修好其他） | 不并行，先合起来查 |
| 多处失败，彼此独立，且没有共享状态 | 一个问题域一个子代理，并行派发 |
| 独立但会互相干扰（改同一批文件、抢同一个端口或数据库） | 串行派发 |
| 还不知道坏在哪，属于探索式调试 | 不并行，先自己定位 |
| 需要通盘理解整个系统状态才能判断 | 不并行 |

**适合并行的典型信号：** 3 个以上测试文件因不同根因失败；多个子系统各自独立损坏；每个问题不看其他问题也能读懂。

## 流程

### 第 1 步：切分独立问题域

按「坏的是什么」分组，例如：

- 文件 A 的测试：工具审批流程
- 文件 B 的测试：批量完成行为
- 文件 C 的测试：中断功能

每个域相互独立——修工具审批不会影响中断相关的测试。

### 第 2 步：为每个域写一份聚焦的任务

每个子代理拿到四样东西：

1. **明确范围** —— 一个测试文件或一个子系统
2. **明确目标** —— 让这些测试通过
3. **约束** —— 不要改动其他代码
4. **产出格式** —— 你发现了什么、改了什么，一段摘要

### 第 3 步：并发派发

**在同一条响应里发出全部派发调用**，它们才会并行：

```text
子代理（通用型）："修复 agent-tool-abort.test.ts 的失败用例"
子代理（通用型）："修复 batch-completion-behavior.test.ts 的失败用例"
子代理（通用型）："修复 tool-approval-race-conditions.test.ts 的失败用例"
# 三个同时跑
```

一条响应里多次派发 = 并发执行；一条响应派一个 = 串行执行。

### 第 4 步：回收与整合

子代理返回后：

1. 逐份读摘要，弄清各自改了什么
2. 查冲突——有没有两个代理改了同一处代码
3. 跑全量测试，确认放在一起也成立
4. 抽查：子代理会犯成体系的错误（比如都用同一种错误修法）

```bash
# 冲突检查：看有没有文件被多于一个代理改过
git diff --name-only HEAD@{1}..HEAD | sort | uniq -d
git diff --stat

# 合并后必须重新跑全量测试（先发现仓库自己的命令，不要默认 npm test）
make test || pytest -q || npm test
```

## 子代理提示词模板

```markdown
修复 src/agents/agent-tool-abort.test.ts 中 3 个失败用例：

1. "should abort tool with partial output capture" —— 期望消息里含 'interrupted at'
2. "should handle mixed completed and aborted tools" —— 快速工具被中断而非完成
3. "should properly track pendingToolCount" —— 期望 3 条结果，实得 0 条

这些疑似时序或竞态问题。你的任务：

1. 读测试文件，弄清每个用例在验证什么
2. 定位根因——是时序问题还是真的有 Bug？
3. 修复方式：
   - 用基于条件的等待替换写死的超时
   - 若确有中断实现的缺陷，改实现
   - 若被测行为已变更，调整测试期望

不要靠调大超时糊弄过去，找真正的原因。

产出：一段摘要，说明根因与你的改动。
```

## 红线与常见错误

| 错误写法 | 正确写法 |
|----------|----------|
| 范围太大：「把所有测试修好」 | 具体：「修复 agent-tool-abort.test.ts」 |
| 没有上下文：「修一下那个竞态」 | 带上报错原文与用例名 |
| 没有约束：代理可能顺手重构全仓 | 写明「不要改动生产代码」「只改测试」 |
| 产出含糊：「修好就行」 | 写明「返回根因与改动清单」 |
| 让多个代理改同一批文件 | 改为串行，或先切开文件边界 |

**禁止**：把你这次会话的历史整段粘进子代理提示词。子代理只需要它自己的任务、它要碰的接口、以及全局约束，别的都不要。

## 输出契约

回收后你自己要产出：

- 每个子代理的一行结论（域、根因、改动位置）
- 冲突检查结果（有没有交叉改动）
- 全量测试的新鲜运行证据（命令、通过数、退出码）
- 仍然存疑、需要人决定的点

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `dispatching-parallel-agents`（MIT）。改动见 ATTRIBUTION.md。
