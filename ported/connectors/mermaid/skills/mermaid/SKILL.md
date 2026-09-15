---
name: mermaid
description: 用 Mermaid 生成并渲染图表。当用户要画流程图、时序图、架构图、状态图、类图、甘特图、ER 图、思维导图，或说「画个图」「把流程画出来」「生成架构图」「导出 SVG/PNG」「给个可编辑的图链接」时使用。通过 cli-anything-mermaid 命令行完成：新建项目、设置图源、渲染 SVG/PNG、生成 Mermaid Live 分享链接、撤销重做。无需安装任何桌面软件，渲染走 mermaid.ink 云端服务。
---

# Mermaid 图表

把自然语言描述变成图，产出 SVG/PNG 文件或可编辑的在线链接。

## 前置条件

- 命令 `cli-anything-mermaid` 已由连接器自动安装（Python 3.10+）
- 渲染需联网（走 `mermaid.ink`）。**图源文本会发送到该第三方服务**，含敏感信息的图请先脱敏或改用本地 mmdc

## 固定工作流

所有命令加 `--json`，用绝对路径，每步检查返回码。

```bash
# 1. 新建项目（可选样例：flowchart / sequence / class / state / er / gantt / mindmap ...）
cli-anything-mermaid --json project new --sample flowchart -o /abs/path/diagram.json

# 2. 写入图源（内联或从文件）
cli-anything-mermaid --json --project /abs/path/diagram.json diagram set --text "graph TD; A[需求]-->B[方案]; B-->C[上线]"
cli-anything-mermaid --json --project /abs/path/diagram.json diagram set --file /abs/path/src.mmd

# 3. 渲染
cli-anything-mermaid --json --project /abs/path/diagram.json export render /abs/path/out.svg --format svg
cli-anything-mermaid --json --project /abs/path/diagram.json export render /abs/path/out.png --format png

# 4. 分享链接（edit 可编辑 / view 只读）
cli-anything-mermaid --json --project /abs/path/diagram.json export share --mode edit
```

渲染成功的 JSON 含 `output`、`format`、`file_size`。**渲染后必须确认文件存在再交付。**

## 图源怎么写

先把用户的描述整理成节点和关系，再选图型：

| 用户在描述 | 用 |
|---|---|
| 步骤、分支、流程 | `graph TD`（上下）/ `graph LR`（左右） |
| 谁调用谁、请求响应 | `sequenceDiagram` |
| 服务、组件、依赖 | `graph LR` + 子图 `subgraph` |
| 状态流转 | `stateDiagram-v2` |
| 表与关系 | `erDiagram` |
| 排期 | `gantt` |

节点文字含中文、括号、斜杠时用引号包住：`A["订单服务 (v2)"]`。

## 迭代修改

用 `diagram show` 取回当前源，改后再 `diagram set`。改错了 `session undo`。

```bash
cli-anything-mermaid --json --project /abs/path/diagram.json diagram show
cli-anything-mermaid --json --project /abs/path/diagram.json session undo
```

## 常见错误

| 现象 | 处理 |
|---|---|
| 渲染返回非 0 / 无 `output` | 通常是图源语法错。`diagram show` 取回源，检查箭头、引号、保留字 |
| 中文乱码或节点显示为方块 | 给节点文字加引号 |
| 网络不可用 | 渲染依赖 mermaid.ink；给用户 `.mmd` 源文件并说明可用 Mermaid Live 打开 |
| 图太大不可读 | 拆成多张图，或用 `subgraph` 分组 |

## 与研发技能的衔接

`tech-design-draft` 出技术方案时，架构图与时序图交给本技能渲染；`incident-brief` 的时间线可用 `gantt` 或 `sequenceDiagram` 可视化。

---

### 出处

本连接器封装 [CLI-Anything](https://github.com/HKUDS/CLI-Anything) 的 mermaid harness（Apache-2.0）。
harness 作者：[getmored-create](https://github.com/getmored-create)；项目：HKUDS（Yang, Fan, Huang），技术报告 arXiv:2606.03854。
本 SKILL.md 依据 harness 自带文档改写并中文化，命令序列已在 2026-09-15 实测。改动见连接器根目录 `ATTRIBUTION.md`。
