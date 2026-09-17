# 纵深防御式校验

## 概述

修掉一个由非法数据引起的 Bug 时，在一个地方加校验感觉就够了。但那一处检查会被别的代码路径、被重构、被 mock 绕过去。

**核心原则：在数据流经的每一层都加校验，让这个 Bug 在结构上不可能发生。**

## 为什么要多层

单点校验：「我们修好了这个 Bug」
多层校验：「我们让这个 Bug 不可能发生」

不同层拦住不同情况：入口校验拦住大部分；业务逻辑拦住边界情况；环境守卫挡住特定上下文里的危险动作；调试日志在其他层都失守时帮你定位。

## 四层

### 第 1 层：入口校验

**目的：** 在 API 边界就拒掉明显非法的输入。

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === '') {
    throw new Error('workingDirectory 不能为空');
  }
  if (!existsSync(workingDirectory)) {
    throw new Error(`workingDirectory 不存在：${workingDirectory}`);
  }
  if (!statSync(workingDirectory).isDirectory()) {
    throw new Error(`workingDirectory 不是目录：${workingDirectory}`);
  }
  // ... 继续
}
```

### 第 2 层：业务逻辑校验

**目的：** 确认这份数据对**这个操作**来说是讲得通的。

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) {
    throw new Error('初始化工作区需要 projectDir');
  }
  // ... 继续
}
```

### 第 3 层：环境守卫

**目的：** 在特定上下文里拦住危险操作。

```typescript
async function gitInit(directory: string) {
  // 测试环境下，拒绝在临时目录之外执行 git init
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    const tmpDir = normalize(resolve(tmpdir()));

    if (!normalized.startsWith(tmpDir)) {
      throw new Error(`测试期间拒绝在临时目录外执行 git init：${directory}`);
    }
  }
  // ... 继续
}
```

### 第 4 层：调试探针

**目的：** 留下事后取证用的上下文。

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  logger.debug('即将执行 git init', {
    directory,
    cwd: process.cwd(),
    stack,
  });
  // ... 继续
}
```

## 怎么套用

找到一个 Bug 之后：

1. **追踪数据流** —— 坏值从哪儿来？在哪儿被用？
2. **列出所有关卡** —— 数据经过的每一个点
3. **每层都加校验** —— 入口、业务、环境、调试
4. **逐层测试** —— 故意绕过第 1 层，确认第 2 层能拦住

## 例子

Bug：空的 `projectDir` 导致 `git init` 跑到了源码目录里。

**数据流：** 测试 setup 给出空字符串 → `Project.create(name, '')` → `WorkspaceManager.createWorkspace('')` → `git init` 跑在 `process.cwd()`。

**加的四层：** 入口校验非空/存在/可写；工作区管理器校验 projectDir 非空；测试环境下拒绝在临时目录外 git init；执行前打印堆栈。

**结果：** 全量测试通过，这个 Bug 无法再复现。

## 关键洞察

四层都有必要。测试期间，每一层都拦住过其他层漏掉的问题：不同代码路径绕过了入口校验；mock 绕过了业务逻辑检查；不同平台的边界情况需要环境守卫；调试日志暴露了结构性误用。

**不要只加一个校验点，每一层都加。**

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `systematic-debugging/defense-in-depth.md`（MIT）。改动见 ATTRIBUTION.md。
