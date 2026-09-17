# 反向追溯根因

## 概述

Bug 常常在调用栈很深的地方才显形（在错误目录里执行了 git init、文件被创建到了错误位置、数据库用错了路径打开）。你的本能是在报错的那一行修，但那是在治症状。

**核心原则：沿调用链一路往回追，找到最初的触发点，在源头修。**

## 何时用

- 报错发生在执行链深处，而不是入口
- 堆栈显示调用链很长
- 不清楚非法数据是从哪儿来的
- 需要找出是哪个测试/哪段代码触发了问题

判定：能往回追吗？能——追到最初触发点，并叠加纵深防御；不能（追到死路）——才在症状点修，并写清楚原因。

## 追溯步骤

### 1. 观察症状

```
Error: git init failed in ~/project/packages/core
```

### 2. 找直接原因

**哪一行代码直接导致了它？**

```typescript
await execFileAsync('git', ['init'], { cwd: projectDir });
```

### 3. 问：谁调用了它

```typescript
WorktreeManager.createSessionWorktree(projectDir, sessionId)
  → 被 Session.initializeWorkspace() 调用
  → 被 Session.create() 调用
  → 被 Project.create() 处的测试调用
```

### 4. 继续往上追

**传进来的值是什么？**

- `projectDir = ''`（空字符串！）
- 空字符串作为 `cwd` 会退化成 `process.cwd()`
- 那正是源码目录

### 5. 找到最初触发点

**空字符串是哪儿来的？**

```typescript
const context = setupCoreTest();        // 返回 { tempDir: '' }
Project.create('name', context.tempDir); // 在 beforeEach 之前就被访问了！
```

## 手工追不动时：加探针

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  console.error('DEBUG git init:', {
    directory,
    cwd: process.cwd(),
    nodeEnv: process.env.NODE_ENV,
    stack,
  });

  await execFileAsync('git', ['init'], { cwd: directory });
}
```

**关键：** 在测试里用 `console.error()`，不要用日志库（可能被吞掉）。

**跑起来并抓取：**

```bash
npm test 2>&1 | grep 'DEBUG git init'
```

**分析堆栈：** 找测试文件名 → 找触发调用的行号 → 归纳规律（是同一个测试吗？同一个参数吗？）。

## 找出是哪个测试污染了环境

某个东西在跑测试时冒出来，但不知道是哪个测试干的，就做二分：

```bash
# 逐个跑测试文件，每跑完一个就检查污染物是否出现，出现即停
for f in $(git ls-files 'src/**/*.test.ts'); do
  npm test -- "$f" >/dev/null 2>&1
  if [ -e .git/POLLUTION_MARKER ] || [ -d ./unexpected-dir ]; then
    echo "污染者：$f"; break
  fi
done
```

## 真实例子：空的 projectDir

**症状：** `.git` 被创建在 `packages/core/`（源码目录）里。

**追溯链：**

1. `git init` 跑在 `process.cwd()` ← cwd 参数为空
2. WorktreeManager 收到空的 projectDir
3. Session.create() 传进去一个空字符串
4. 测试在 beforeEach 之前访问了 `context.tempDir`
5. setupCoreTest() 初始返回 `{ tempDir: '' }`

**根因：** 顶层变量初始化时访问了还没赋值的东西。

**修复：** 把 tempDir 改成 getter，在 beforeEach 之前访问就抛错。

**并叠加纵深防御：** 入口校验目录、工作区管理器校验非空、测试环境下拒绝在临时目录之外执行 git init、执行前打印堆栈。

## 关键原则

```
找到直接原因
  → 还能往上追一层吗？
      能 → 继续往回追 → 这是源头吗？
                            不是 → 继续追
                            是   → 在源头修 → 每一层加校验 → Bug 结构上不可能再现
      不能 → 绝不要只修报错出现的那一行（要写清楚为什么追不动）
```

## 加探针的小技巧

- **在测试里：** 用 `console.error()`，日志库可能被静音
- **在危险操作之前打印**，不要等它失败之后
- **带上上下文：** 目录、cwd、环境变量、时间戳
- **抓堆栈：** `new Error().stack` 能给出完整调用链

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `systematic-debugging/root-cause-tracing.md`（MIT）。改动见 ATTRIBUTION.md。
