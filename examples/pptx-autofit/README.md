# PPT 自动缩小：100% 不等于缩小

维护者侧代理在 2026-10-28 的首次使用检查中复现两项问题：PPT 技能 0.1.2 把 `fontScale="100000"`（100%）误报成缩小，同时漏掉 `fontScale="62.500%"` 的真实缩小设置。旧免安装任务包的 `--input` 入口同样会误报 100%。

0.1.3 修复这两项判定。省略比例时按 100% 处理；仅减少行距不代表字号缩小。无效或超出支持范围的比例会提示待核对，不猜实际字号或静默报通过。缩小提示只描述文件中的比例，不推断实际溢出原因。

## 自己复跑

在仓库根目录运行，输出目录必须不存在：

```bash
python3 -B examples/pptx-autofit/verify_case.py --out-dir /tmp/pptx-autofit-result
```

脚本只使用 Python 标准库，从[既有四页合成修正版](../pptx-fonts/inputs/after.pptx)创建 20 份测试输入，每份只改第一页的 AutoFit 设置。它实际调用检查器，保存每份输入、人读可读的 JSON、stderr、退出码和 SHA256；输入和检查器保持不变。`verification.json` 对照预先声明的期望值，不能把执行过当作通过。

| 输入设置 | 期望 |
|---|---|
| 无 AutoFit、缺省比例、100000、100.000% | 不报字号缩小 |
| 仅 lnSpcReduction、100% 与行距缩减同时存在 | 不报字号缩小 |
| 62500 / 62.500%、1000 / 1%、99999 / 99.999% | 两种写法一致报告自动缩小 |
| 999、100001、0、负数、NaN%、未知文字、全角数字、6000 位整数 | 提示比例未确定，退出 3；不能崩溃或静默通过 |

边界依据见 [Microsoft FontScale 文档](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.normalautofit.fontscale?view=openxml-3.0.1)和 [NormalAutoFit 的百分比示例及行距说明](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.normalautofit?view=openxml-3.0.1)。当前解析范围是整数 1000–100000 与百分比 1%–100%；这不是对所有 OOXML 标准分支或格式的完整校验。

全部输入是公开合成材料，执行主体是维护者侧 AI。此次验证没有运行 PowerPoint/WPS，也没有在 WorkBuddy 客户端执行；不证明渲染效果、独立用户采用或市场自动发现。原案例的一处字号未知必须继续保留，退出 0 仅表示检查范围内未发现问题。
