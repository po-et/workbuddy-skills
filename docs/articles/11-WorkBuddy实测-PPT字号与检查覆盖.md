# WorkBuddy 实测：8 磅正文为什么没报错

作者：Captain。实测日期：2026-10-21。AI 辅助整理，使用公开合成 PPT，记录维护者侧验收。

一份 PPT 有两处 8 磅正文，旧版检查器却退出 0，显示“没发现问题”。原因在于字号写在段落默认属性和当前文本体的列表样式里。只检查文字片段自身的字号，会漏掉这些设置。这次给 WorkBuddy 的任务，就是把漏检位置、修正结果和未检查到的部分一起交出来。

维护者的 Codex 代理操作真实 **WorkBuddy 5.8.2 / Space-Bunny**，显式读取本地 `pptx-making` 0.1.2，分别运行两份四页 PPT 的人读与 JSON 检查。任务界面从 15:09 到 15:14，显示耗时 **5m22s**；这段时间是维护者任务记录。

![真实 WorkBuddy 客户端任务与检查结果](../assets/2026-10-21-pptx-case/workbuddy-client.png)

| 页 | 页内字号设置 | 原件 | 修正版 |
|---|---|---|---|
| 1 | 段落默认字号 | 8 磅，发现偏小 | 24 磅 |
| 2 | 当前文本体对应列表层级 | 8 磅，发现偏小 | 24 磅 |
| 3 | 文字片段覆盖段落默认值 | 24 磅，不误报 | 不变 |
| 4 | 三层页内设置均无字号 | 未确定 `null` | 不变 |

默认底线是 18 磅。新版检查原件的两次退出码均为 **3**，修正版均为 **0**。两份都有 8 处非空文字片段：7 处字号已确定，1 处未确定。修正版只能得出 `no_issues_in_checked_scope`，第 4 页仍需人工确认。

![原件第 1 页：8 磅正文，ArtifactTool 渲染](../assets/2026-10-21-pptx-case/before-slide-1.png)

![同页改为 24 磅，ArtifactTool 渲染](../assets/2026-10-21-pptx-case/after-slide-1.png)

两份 PPT 仅在第 1、2 页各改一处字号，从 8 改为 24。根代理独立重跑，四份标准输出逐字节一致；5 份技能源文件与 2 份输入的哈希未变。两份包结构检查均为 0 项问题，另行查看了 8 张 ArtifactTool 渲染图，尚未完成 PowerPoint GUI 验收。

检查器按文字片段、同段落默认属性、当前文本体对应列表层级的顺序读取字号；非法显式值保留为未知。母版、版式和主题继承不在范围内。客户端说明经过反馈校订，仍附[补充边界](../../examples/pptx-fonts/outputs/review-notes.md)：确定性输出、AI 解释和视觉验收需要分别核对。

21 项行为测试通过，doctor 100 分；另有独立的 20 次 CLI 探针、14 份 JSON 检查，不合并计数。[线上核验](../metrics/pptx-release-verified-2026-10-21.json)确认 `indiv-captain` 的 0.1.2 已公开，两项扫描均为 `benign`，5 份发布文件哈希一致；新版 AI 评测尚未确认。本次没有独立用户试用或市场自动发现证据。

在仓库根目录复跑，无需安装 Python 依赖：

```bash
python3 -B examples/pptx-fonts/verify_case.py
python3 -B skills/pptx-making/scripts/pptx_check.py examples/pptx-fonts/inputs/before.pptx --json
# 第二条预期退出 3：发现两处偏小文字
```

可复制给 WorkBuddy：

> 先读本仓库 skills/pptx-making/SKILL.md，实际检查 examples/pptx-fonts/inputs/before.pptx 和 after.pptx，分别保存人读输出、JSON 与真实退出码到全新目录。列出小字号页码、来源、已确定和未确定数量，保留原件与脚本。未知不能写成通过，不猜母版继承字号；无法运行就报告实际错误。

[完整输入、四份实际输出与安装说明](../../examples/pptx-fonts/README.md)均已保留。用自己的 PPT 检查后，重点回到演示软件确认未知项；遇到问题可附版本和脱敏样例提交[反馈](https://github.com/po-et/workbuddy-skills/issues/new?template=skill-feedback.md)。
