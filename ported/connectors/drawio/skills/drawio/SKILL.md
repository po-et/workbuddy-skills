---
name: drawio
description: 用 draw.io 画图并导出。当用户要画架构图、系统拓扑、部署图、流程图、时序关系图、ER 图，或说「画个架构图」「用 draw.io 画」「导出 drawio 文件」「加个节点连到 X」「导出 PNG/SVG/PDF」时使用。通过 cli-anything-drawio 命令行完成：新建项目、添加 15 种图形、连线、分页、导出 PNG/SVG/PDF/VSDX、保存可继续编辑的 .drawio 文件。需要本机安装 draw.io 桌面版用于渲染导出。
---

# draw.io 架构图

把自然语言描述变成 draw.io 图：图形、连线、导出，并留下可继续编辑的 `.drawio` 文件。

## 前置条件

- 命令 `cli-anything-drawio` 已由连接器安装（Python 3.10+，PyPI 包）
- **导出 PNG/SVG/PDF 需要本机安装 draw.io 桌面版**（渲染走 draw.io 自带的命令行导出）。没有桌面版时仍可建图、保存 `.drawio` 文件，只是不能渲染成图片
- 渲染在本地完成，图内容不上传

## 固定工作流

所有命令加 `--json`，用绝对路径，每步检查返回码。图形 ID 从 `shape add` / `shape list` 的返回里取。

```bash
# 1. 新建项目（--project 指向的 .json 是工作状态文件）
cli-anything-drawio --json project new -o /abs/path/arch.json

# 2. 加图形：rectangle rounded ellipse diamond triangle hexagon cylinder cloud
#    parallelogram process document callout note actor text
cli-anything-drawio --json --project /abs/path/arch.json shape add rectangle --label "网关" --x 80 --y 80
cli-anything-drawio --json --project /abs/path/arch.json shape add rectangle --label "订单服务" --x 360 --y 80
cli-anything-drawio --json --project /abs/path/arch.json shape add cylinder --label "MySQL" --x 360 --y 260

# 3. 连线（用上一步返回的 id；style: straight orthogonal curved entity-relation）
cli-anything-drawio --json --project /abs/path/arch.json connect add <网关id> <订单服务id> --label "HTTP"
cli-anything-drawio --json --project /abs/path/arch.json connect add <订单服务id> <MySQLid> --style orthogonal

# 4. 导出（png / svg / pdf / vsdx / xml）
cli-anything-drawio --json --project /abs/path/arch.json export render /abs/path/arch.png --format png --overwrite
cli-anything-drawio --json --project /abs/path/arch.json export render /abs/path/arch.svg --format svg --overwrite

# 5. 保存可继续编辑的 .drawio 文件
cli-anything-drawio --json --project /abs/path/arch.json project save /abs/path/arch.drawio
```

导出成功的 JSON 含 `output`、`format`、`file_size`。**导出后确认文件存在再交付。**

## 布局怎么摆

先把用户描述整理成节点和关系，再决定坐标：

| 图型 | 布局 |
|---|---|
| 分层架构（网关 → 服务 → 存储） | 每层一行，`--y` 每层 +180，同层 `--x` 每个 +280 |
| 流程图 | 从上到下，判断用 `diamond`，`--y` 每步 +160 |
| 部署/拓扑 | 按机房或集群分列，`cloud` 表示外部依赖 |

默认图形 120×60；文字长的加 `-w 160`。中文标签直接写，不需要转义。

## 迭代修改

```bash
cli-anything-drawio --json --project /abs/path/arch.json shape list          # 看现有图形和 id
cli-anything-drawio --json --project /abs/path/arch.json shape label <id> "新文字"
cli-anything-drawio --json --project /abs/path/arch.json shape move <id> --x 500 --y 80
cli-anything-drawio --json --project /abs/path/arch.json connect list
cli-anything-drawio --json --project /abs/path/arch.json session undo
```

## 常见错误

| 现象 | 处理 |
|---|---|
| `draw.io export failed (exit 1)` 且图是空的 | 空白图无法导出，先加图形 |
| `draw.io export failed` 且图不空 | 本机未安装 draw.io 桌面版或未在 PATH；改为 `project save` 交付 `.drawio` 文件并告知用户 |
| 连线失败 | ID 用错，先 `shape list` 取真实 id |
| 图形重叠 | 按上表重排 `--x/--y`，或 `shape move` |

## 与研发技能的衔接

`tech-design-draft` 出技术方案时的架构图用本技能；只要流程图/时序图且不需要可编辑源文件时，`mermaid` 连接器零依赖更快。

---

### 出处

本连接器封装 [CLI-Anything](https://github.com/HKUDS/CLI-Anything) 的 drawio harness（Apache-2.0，PyPI 包 `cli-anything-drawio` 1.0.0）。
harness 作者：[zhangxilong-43](https://github.com/zhangxilong-43)；项目：HKUDS（Yang, Fan, Huang），技术报告 arXiv:2606.03854。
命令序列已于 2026-09-16 在 macOS + draw.io 桌面版实测（加图形、连线、导出 PNG/SVG）。改动见连接器根目录 `ATTRIBUTION.md`。
