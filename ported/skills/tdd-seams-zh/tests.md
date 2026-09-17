# 好测试与坏测试

## 好测试

**集成风格**：通过真实接口测，不 mock 内部零件。

```typescript
// 好：测可观察的行为
test("用户可以用有效购物车结算", async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe("confirmed");
});
```

特征：
- 测用户/调用方在乎的行为
- 只用公开 API
- 内部重构后存活
- 描述「做什么」，不是「怎么做」
- 每个测试一个逻辑断言

## 坏测试

**实现细节测试**：与内部结构耦合。

```typescript
// 坏：测实现细节
test("checkout 调用 paymentService.process", async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});
```

危险信号：
- mock 内部协作者
- 测私有方法
- 断言调用次数/顺序
- 行为没变的重构会弄挂测试
- 测试名描述「怎么做」而不是「做什么」
- 绕开接口、用外部手段验证

```typescript
// 坏：绕过接口去验证
test("createUser 写入数据库", async () => {
  await createUser({ name: "Alice" });
  const row = await db.query("SELECT * FROM users WHERE name = ?", ["Alice"]);
  expect(row).toBeDefined();
});

// 好：通过接口验证
test("createUser 之后用户可被取回", async () => {
  const user = await createUser({ name: "Alice" });
  const retrieved = await getUser(user.id);
  expect(retrieved.name).toBe("Alice");
});
```

**同义反复测试**：期望值复述了实现，测试构造上必然通过。

```typescript
// 坏：期望值用代码同样的算法重新算出来
test("calculateTotal 汇总行项目", () => {
  const items = [{ price: 10 }, { price: 5 }];
  const expected = items.reduce((sum, i) => sum + i.price, 0);
  expect(calculateTotal(items)).toBe(expected);
});

// 好：期望值是独立的已知字面量
test("calculateTotal 汇总行项目", () => {
  expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
});
```
