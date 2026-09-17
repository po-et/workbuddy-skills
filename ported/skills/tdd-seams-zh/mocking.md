# 什么时候 mock

只在**系统边界** mock：
- 外部 API（支付、邮件等）
- 数据库（有时——优先用测试库）
- 时间/随机数
- 文件系统（有时）

不要 mock：
- 你自己的类/模块
- 内部协作者
- 任何你能控制的东西

## 为可 mock 性设计

在系统边界，把接口设计得容易 mock：

**1. 用依赖注入**

外部依赖从外面传进来，不在内部创建：

```typescript
// 容易 mock
function processPayment(order, paymentClient) {
  return paymentClient.charge(order.total);
}

// 难 mock
function processPayment(order) {
  const client = new PaymentClient(process.env.PAYMENT_KEY);
  return client.charge(order.total);
}
```

**2. 优先 SDK 式接口，而不是通用取数函数**

每个外部操作一个具体函数，而不是一个带条件逻辑的通用函数：

```typescript
// 好：每个函数可独立 mock
const api = {
  getUser: (id) => fetch(`/users/${id}`),
  getOrders: (userId) => fetch(`/users/${userId}/orders`),
  createOrder: (data) => fetch('/orders', { method: 'POST', body: data }),
};

// 坏：mock 里得写条件逻辑
const api = {
  fetch: (endpoint, options) => fetch(endpoint, options),
};
```

SDK 式意味着：
- 每个 mock 返回一种确定形状
- 测试准备里没有条件逻辑
- 一眼看出测试用到了哪些端点
- 每个端点各自类型安全
