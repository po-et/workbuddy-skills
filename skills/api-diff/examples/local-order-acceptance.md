# 一条订单接口，先发现差异，再修正后复验

这是公开合成案例：两台本地 HTTP 服务分别返回旧版本与新版本订单响应。只使用 `127.0.0.1` 随机端口和 GET，不连接腾讯 API 或任何线上服务，不读取用户认证头。

在已安装的技能目录中执行：

```bash
python3 {baseDir}/examples/local_order_demo.py
```

脚本会打印输出目录。也可用 `--out /tmp/my-api-diff-demo` 指定一个新目录；已有报告不会被覆盖。

| 阶段 | 实际动作 | 可审查产物 | CLI 退出码 |
|---|---|---|---|
| 发现回归 | 同一 GET 请求打到旧/新两个本地服务 | `regressed.md`、`regressed.json` | 1 |
| 修正复验 | 新服务切到修正后的合成响应，重新发送请求 | `repaired.md`、`repaired.json` | 0 |
| 验证过程 | 检查差异路径、两次结果和输入 SHA256 | `verification.json` | 演示脚本全部符合预期时为 0 |

四个真实差异位置来自实际 HTTP 响应比较：

| 路径 | 旧响应 | 回归响应 | 含义 |
|---|---|---|---|
| `$.paid_amount` | 19900 | 18900 | 实付金额，单位是分 |
| `$.items[0].quantity` | 2 | 3 | 商品数量发生变化 |
| `$.can_refund` | boolean | number | `true` 被变成 `1`，JSON 类型不一致 |
| `$.note` | `null` | 字段缺失 | 缺失与显式空值不同 |

仅忽略 `id,request_id,updated_at`。这些正则按完整字段名匹配：`id` 不会忽略 `order_id`；报告保留 `$.id`、`$.request_id`、`$.updated_at` 的实际忽略路径。演示的第二轮恢复金额、数量、布尔类型和 `note`，三项响应噪音仍然变化，结果应为 `same`。

直接运行 `api_diff.py` 时，两端同为 HTTP 500、解析失败、网络错误均不能得到退出码 0。常见业务字段名中的 `amount/quantity/qty/count/price/total/balance` 及含这些字段的子树不能被忽略；匹配时报告列出拒绝路径并退出 2。这是字段命名保护，不能识别 `money`、`库存` 或所有自定义业务含义。上线前仍需按自己的响应契约复核忽略规则。

数组按原顺序比较，未做排序归一化；本案例没有压测、客户端自动触发或真人使用成果。差异证明行为变化，最终是否为缺陷需要结合业务契约判断。

实现依据：[Python JSON 文档](https://docs.python.org/3/library/json.html)说明默认解码器允许非有限数字和重复键；本技能采用严格解析，并以 Decimal 比较响应中的小数。[Python urllib 文档](https://docs.python.org/3/library/urllib.request.html)说明重定向处理可定制；本技能关闭自动重定向，防止请求转到未核对的端点。
