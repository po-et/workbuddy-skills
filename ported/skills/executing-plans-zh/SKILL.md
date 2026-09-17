---
name: executing-plans-zh
description: 执行已写好的实施计划、按任务清单逐条落地、带检查点的批量执行、计划执行中遇到阻塞怎么办、什么时候该退回去重审计划。当用户说「按这份计划开始做」「计划写好了，执行吧」「照着 plan.md 一步步实现」「这份实施计划你来跑」「分任务执行并在关键点停一下」时使用。流程：先确保有隔离工作区 → 通读计划并带着批判眼光挑毛病，有疑问先提再动手 → 为每个任务建待办，逐条标记进行中、严格照步骤做、按计划跑验证、标记完成 → 全部完成后进入分支收尾。红线：碰到阻塞立刻停下来问，不要猜；不要跳过验证步骤；未经用户明确同意不在 main/master 上直接实现。若平台支持子代理，优先改用子代理驱动开发。
author: Captain
version: 0.1.0
display_name: "执行实施计划"
display_name_en: "Executing Plans (zh)"
description_zh: "把一份写好的实施计划在本会话里执行到底：先审计划再动手、逐任务执行与验证、遇阻即停不猜、完成后进入分支收尾。"
description_en: "Execute a written implementation plan end to end: review it critically first, run tasks one by one with their verifications, stop and ask on blockers, then hand off to branch finishing."
examples_zh:
  - "按这份计划开始做"
  - "照着 plan.md 一步步实现"
  - "这份实施计划你来跑，分任务执行"
examples_en:
  - "Execute this implementation plan task by task"
  - "Follow the plan and run each verification step"
  - "Start on the plan but stop if anything is unclear"
metadata:
  { "openclaw": { "requires": { "bins": ["git"] }, "os": ["darwin", "linux", "windows"], "emoji": "📋" } }
---

# 执行实施计划

装载计划、批判性审阅、执行全部任务、完成后汇报。

**开始时声明：**「我正在用执行实施计划技能来落地这份计划。」

**前置提示：** 这套方法在有子代理能力的环境里效果好得多。如果你的平台支持派发子代理，请改用「子代理驱动开发」技能（`subagent-driven-development-zh`），而不是本技能。

## 何时用

- 手上已有一份写好的实施计划（spec 已定、任务已拆）
- 要在**当前会话**里把它执行完，中间设几个检查点
- 没有子代理能力，或用户明确要求就在本会话内联执行

不适用：计划还没写（先去写计划）；任务之间强耦合、无法按条推进（先回去重新拆）。

## 流程

### 第 1 步：装载并审阅计划

1. 确保有隔离工作区：用「Git 工作树隔离工作区」技能（`using-git-worktrees-zh`）新建一个，或确认现有的可用
2. 读计划文件
3. **带着批判的眼光审**——把你对这份计划的疑问和担忧列出来
4. 有担忧：动手之前先跟用户提
5. 没有担忧：按计划条目建待办，开始执行

审阅时至少过一遍这四项：

- **占位符**：有没有「待定」「TODO」「补充细节」「同任务 N」这类没写实的步骤
- **覆盖度**：spec 里的每条要求，都能指到某个任务吗
- **类型一致**：后面任务用到的函数名、签名、字段名，跟前面任务定义的对得上吗
- **验证可执行**：每个任务给出的验证命令，在这个仓库里真的能跑吗

### 第 2 步：逐任务执行

对每个任务：

1. 标记为「进行中」
2. **严格照步骤做**（计划的步骤本来就被拆成了小口）
3. 按计划写明的方式跑验证
4. 标记为「已完成」

```bash
# 每个任务的收尾都跑它自己的验证命令，并保留证据
pytest tests/path/test_x.py -v      # 或项目自己的测试命令
git add -A && git commit -m "feat: task N - <任务名>"
```

### 第 3 步：开发收尾

全部任务完成并验证通过后：

- 声明：「我正在用开发分支收尾技能来完成这次工作。」
- **必需的后续技能：** 「开发分支收尾」（`finishing-a-development-branch-zh`）
- 按它的流程验证测试、给出选项、执行用户的选择

## 什么时候停下来求助

**出现以下情况立刻停止执行：**

- 撞上阻塞（依赖缺失、测试失败、指令含糊）
- 计划有致命缺口，根本没法开始
- 你看不懂某条指令
- 验证反复失败

**去问清楚，不要靠猜。**

## 什么时候退回前面的步骤

**回到第 1 步（审阅）的情形：**

- 用户根据你的反馈改了计划
- 根本思路需要重新考虑

**不要硬闯阻塞**——停下来问。

## 输出契约

每个任务完成时汇报一行：任务名、改动文件、验证命令与结果。全部完成后汇报：

```
计划执行完毕：<N>/<N> 个任务完成
测试：<命令> → <通过数>/<总数>，退出码 0
未决事项：<无 / 列表>
下一步：进入开发分支收尾
```

## 红线

- 先批判性审计划，再动手
- 严格照计划步骤做
- **不要跳过验证**
- 计划里点名要用某个技能时，就去用
- 遇阻即停，不猜
- **未经用户明确同意，绝不在 main/master 分支上直接开始实现**

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `executing-plans`（MIT）。改动见 ATTRIBUTION.md。
