---
name: todo-debt-scan
description: 技术债盘点、代码里的 TODO / FIXME / HACK / XXX 汇总、按目录和作者统计、最老的 TODO 是谁留的、技术债报告、重构前摸底、代码健康度周报。当用户说「统计一下代码里有多少 TODO」「把技术债列出来」「哪些 FIXME 最老、谁留的」「出一份技术债报告」「重构前先看看坑在哪」时使用。附纯标准库脚本 scripts/todo_scan.py：扫描 30+ 种代码文件里的 TODO/FIXME/BUG/HACK/XXX/DEPRECATED/OPTIMIZE/WORKAROUND/TEMP 标记，识别 TODO(owner) 归属，结合 git blame 给出作者与年龄，输出按类型/目录/作者统计、最老清单、按优先级（FIXME/BUG > HACK/XXX > TODO，同级按年龄）排序的处理建议；支持 Markdown 报告、--json、--no-blame。
author: Captain
version: 0.1.0
display_name: "技术债标记盘点"
display_name_en: "TODO / Tech-Debt Scan"
description_zh: "汇总代码里的 TODO/FIXME/HACK 等标记，结合 git blame 算出每条的作者与年龄，按类型/目录/作者统计并给出优先处理清单与 Markdown 报告；纯 Python 标准库。"
description_en: "Aggregate TODO/FIXME/HACK markers across the codebase, enrich each with author and age via git blame, summarize by type/directory/author, and produce a prioritized list plus a Markdown report; pure Python stdlib."
examples_zh:
  - "扫一下这个仓库的 TODO 和 FIXME，出一份技术债报告"
  - "最老的 10 个 TODO 是什么、谁留的"
  - "按目录统计技术债标记，看看哪块最重"
examples_en:
  - "Scan this repo's TODO/FIXME markers and produce a tech-debt report"
  - "What are the 10 oldest TODOs and who left them?"
  - "Tech-debt markers by directory: which area is heaviest?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧹" } }
---

# 技术债标记盘点

把散落在注释里的 TODO / FIXME / HACK 收成一张表：多少、在哪、谁留的、多老。重构前摸底、季度技术债清理、代码健康度周报都用得上。

## 用法

```bash
python3 scripts/todo_scan.py                       # 当前目录，含 git blame（作者/年龄）
python3 scripts/todo_scan.py src/ --md tech-debt.md --top 50
python3 scripts/todo_scan.py --no-blame            # 大仓库先快速看总量
python3 scripts/todo_scan.py --json
```

## 流程

1. 跑脚本生成报告；先看「按类型」里的 FIXME/BUG 数量和「超过半年」的数量，这两个是健康度指标。
2. 「建议优先处理」清单从上往下过：每条要么修掉、要么建工单并把链接写回注释、要么确认过时直接删注释。
3. 「按作者」只用于找了解上下文的人，不用于考核。
4. 约定新写法 `TODO(owner, #工单): 说明`，脚本能识别括号里的归属。
5. 接进 CI 每周产出一次，跟踪总量与「超过半年」两个数字的趋势。

## 识别范围

- 标记：TODO、FIXME、BUG、HACK、XXX、DEPRECATED、OPTIMIZE、REVIEW、TEMP、WORKAROUND（不区分大小写）。
- 注释前缀：`#`、`//`、`/*`、`*`、`--`、`<!--`、`;`、三引号。
- 文件类型：30+ 种常见代码/配置/模板后缀；跳过 .git、node_modules、vendor、构建产物等目录。

## 边界

- 字符串里恰好出现的「TODO:」可能被当成标记；报告附位置便于人工剔除。
- git blame 逐行查询，万级标记的仓库会慢，先用 `--no-blame` 看总量，再对子目录开 blame。
- 年龄按最后一次修改该行的时间算；整理格式的提交会「刷新」年龄。
