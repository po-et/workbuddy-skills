# 条件式等待

## 概述

抖动测试常常靠写死的延时去猜时序，于是制造出竞态：在快机器上通过，在高负载或 CI 上失败。

**核心原则：等你真正关心的那个条件，而不是猜它需要多久。**

## 何时用

- 测试里有写死的延时（`setTimeout`、`sleep`、`time.sleep()`）
- 测试抖动（有时过，高负载下失败）
- 并行跑测试时超时
- 在等某个异步操作完成

**不要用在：** 正在测试时序行为本身（防抖、节流的间隔）。用写死的超时时，**永远要写明为什么**。

## 核心写法

```typescript
// 改前：靠猜时间
await new Promise(r => setTimeout(r, 50));
const result = getResult();
expect(result).toBeDefined();

// 改后：等条件成立
await waitFor(() => getResult() !== undefined);
const result = getResult();
expect(result).toBeDefined();
```

## 常见场景

| 场景 | 写法 |
|------|------|
| 等事件 | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| 等状态 | `waitFor(() => machine.state === 'ready')` |
| 等数量 | `waitFor(() => items.length >= 5)` |
| 等文件 | `waitFor(() => fs.existsSync(path))` |
| 复合条件 | `waitFor(() => obj.ready && obj.value > 10)` |

## 通用实现

```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000
): Promise<T> {
  const startTime = Date.now();

  while (true) {
    const result = condition();
    if (result) return result;

    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`等待 ${description} 超时（${timeoutMs}ms）`);
    }

    await new Promise(r => setTimeout(r, 10)); // 每 10ms 轮询一次
  }
}
```

Python 等价写法：

```python
import time

def wait_for(condition, description, timeout=5.0, interval=0.01):
    deadline = time.monotonic() + timeout
    while True:
        result = condition()
        if result:
            return result
        if time.monotonic() > deadline:
            raise TimeoutError(f"等待 {description} 超时（{timeout}s）")
        time.sleep(interval)
```

## 常见错误

- **轮询太快：** `setTimeout(check, 1)` 白烧 CPU → 改成每 10ms
- **没有超时：** 条件永不成立就死循环 → 永远带超时，并给出清晰的错误信息
- **读到陈旧数据：** 在循环外缓存了状态 → 在循环内调用 getter 取新值

## 什么时候写死的超时是对的

```typescript
// 工具每 100ms 一个 tick，需要 2 个 tick 才能验证部分输出
await waitForEvent(manager, 'TOOL_STARTED'); // 先等触发条件
await new Promise(r => setTimeout(r, 200));  // 再等有依据的固定时长
// 200ms = 100ms 间隔的 2 个 tick —— 有依据且已写明
```

**三个必要条件：** 先等触发条件；时长基于已知的时序而非猜测；写注释说明为什么。

---
改编自 [obra/superpowers](https://github.com/obra/superpowers) 的 `systematic-debugging/condition-based-waiting.md`（MIT）。改动见 ATTRIBUTION.md。
