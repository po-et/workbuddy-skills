# 出处与改动

## 原项目

- **CLI-Anything** — https://github.com/HKUDS/CLI-Anything（Apache License 2.0，全文见 `LICENSE`）
- 项目作者：Yuhao Yang, Tianyu Fan, Chao Huang（HKUDS）。技术报告：*CLI-Anything: Towards Agent-Native Computer Use*, arXiv:2606.03854
- 本连接器封装的 harness：`drawio/agent-harness`，PyPI 包 `cli-anything-drawio` 1.0.0；registry 署名 contributor：[zhangxilong-43](https://github.com/zhangxilong-43)

## 本连接器做了什么

只做封装与本地化，**不修改 harness 代码**，安装走 PyPI。

| 文件 | 内容 |
|---|---|
| `connector-meta.json` | 按 WorkBuddy 连接器规范编写，中英双语示例 |
| `cli.json` | 三平台 PyPI 安装、状态检查、Python 运行时声明 |
| `icon.svg` | 自绘图标 |
| `skills/drawio/SKILL.md` | 依据 harness 自带文档重写：中文化、加触发词、按实测给出完整命令序列、补布局与错误处理 |

## 实测记录

2026-09-16，macOS，Python 3.12，draw.io 桌面版已安装：`project new` → `shape add` ×2 → `connect add` → `export render` 产出 PNG 3.9KB、SVG 15KB。空白项目导出会失败（draw.io 不渲染空图），已写入 SKILL.md 错误表。

## 已知事项

- 导出依赖本机 draw.io 桌面版；无桌面版时只能产出 `.drawio` 文件
- `runtime.type: "python"`、`minWorkbuddyVersion: "5.0.0"` 取值与 mermaid 连接器一致，待审核验证
- 未在 WorkBuddy 客户端内实际安装验证
