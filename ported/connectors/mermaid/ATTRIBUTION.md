# 出处与改动

## 原项目

- **CLI-Anything** — Making ALL Software Agent-Native
- 仓库：https://github.com/HKUDS/CLI-Anything（Apache License 2.0，全文见 `LICENSE`）
- 项目作者：Yuhao Yang, Tianyu Fan, Chao Huang（HKUDS）。技术报告：*CLI-Anything: Towards Agent-Native Computer Use*, arXiv:2606.03854
- 本连接器封装的 harness：`mermaid/agent-harness`，registry 署名 contributor：[getmored-create](https://github.com/getmored-create)

## 本连接器做了什么

CLI-Anything 提供的是**通用 agent-native CLI**；WorkBuddy 需要的是**连接器包**（`connector-meta.json` + `cli.json` + `icon.svg` + `skills/`）。
本目录只做封装与本地化，**不修改 harness 代码**，安装时从原仓库拉取。

| 文件 | 内容 |
|---|---|
| `connector-meta.json` | 按 WorkBuddy 开放平台连接器规范编写的元信息，中英双语示例 |
| `cli.json` | 三平台安装命令、非破坏性状态检查、Python 运行时声明 |
| `icon.svg` | 自绘图标 |
| `skills/mermaid/SKILL.md` | 依据 harness 自带 `skills/SKILL.md` 改写：中文化、加入 WorkBuddy 触发词、按实测修正命令序列、补充图型选择表与错误处理 |

## 实测记录

2026-09-15，macOS，Python 3.12：从 `mermaid/agent-harness` 源码安装 → `project new` → `diagram set` → `export render out.svg` 成功产出 13.9 KB SVG（经 mermaid.ink 渲染）。

## 已知事项

- harness 自带文档写 `pip install cli-anything-mermaid`，但该包**未发布到 PyPI**（2026-09-15 查证），故 `cli.json.init` 使用 git 子目录安装。首次安装会克隆整个 CLI-Anything 仓库（pip 已启用 blob 过滤），耗时取决于网络。
- `minWorkbuddyVersion` 取 `5.0.0`，因 `runtime` 字段为 v5.0.0+ 特性。【待确认】
- `runtime.type: "python"` 的取值参照规范示例中的 `"node"` 类推。【待确认】
- 尚未在 WorkBuddy 客户端内实际安装验证，仅完成规范校验与 CLI 端到端实测。
