---
name: iteration-report
description: 生成研发迭代周报、迭代报告与复盘材料。从本地 Git 仓库提交记录与工单系统抓取原始数据，按「交付价值」而非提交流水重组，输出含完成事项、风险、遗留项与下期计划的结构化报告，每条结论可追溯到具体 commit 与工单。当用户要求写周报、月报、迭代报告、sprint report、版本交付报告、研发复盘、进展同步或向上汇报材料，或提到「这周做了什么」「迭代总结」「团队产出」「给老板汇报」时使用。支持多仓库多人聚合；当提交信息质量差时会从 diff 反推变更意图。不用于生成个人 OKR 或绩效自评。
version: 0.1.0
display_name: "迭代周报生成器"
display_name_en: "Iteration Report"
description_zh: "从 Git 提交与工单记录生成可溯源的迭代周报：按交付价值重组，风险与遗留单列，提交信息不规范时从 diff 反推。"
description_en: "Generate traceable iteration reports from Git history and issue trackers: grouped by delivered value, with risks and leftovers, and diff-based inference when commit messages are poor."
examples_zh:
  - "帮我生成上周的迭代周报"
  - "根据这个仓库最近两周的提交写一份迭代报告"
  - "把这个迭代的交付、风险、遗留整理成向上汇报材料"
  - "我们的提交信息写得很烂，能从改动里推断出做了什么吗"
examples_en:
  - "Generate last week's iteration report"
  - "Write a sprint report from this repo's commits in the last two weeks"
  - "Summarize this iteration's deliverables, risks and leftovers for a management update"
  - "Our commit messages are poor, infer what was done from the diffs"
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["git", "python3"] },
        "os": ["darwin", "linux", "win32"],
        "emoji": "📋"
      }
  }
---

# 迭代周报生成器

把一个迭代周期内散落在 Git 与工单系统里的原始记录，重组成一份**可验收、可追溯、可对比**的交付报告。

## 核心原则

1. **报价值，不报流水。** 读者要知道"这个迭代交付了什么业务价值"，不是"提交了 47 个 commit"。
2. **每条结论可追溯。** 每个完成项后面必须挂 commit 短 hash 或工单号，不许出现无法溯源的描述。
3. **不编造。** 数据里没有的，写"数据缺失"，绝不脑补。提交信息写得烂就从 diff 反推，并标注「推断」。
4. **可对比。** 结构固定，便于与上期 diff。

## 前置检查

执行前确认：

- 仓库路径可访问，且已 `git fetch`（本地 git log 路径**不需要任何 token**，内网 GitLab 同样可用）
- 时间窗口已明确（默认上一个自然周：周一 00:00 至周日 23:59）
- 若要接工单系统，`references/config.example.yaml` 已复制为 `config.yaml` 并填好

缺哪项就问用户，不要猜。

## 执行流程

### 第 1 步：采集 Git 数据

```bash
python3 {baseDir}/scripts/collect_git.py \
  --repo <仓库路径，可重复> \
  --since <YYYY-MM-DD> --until <YYYY-MM-DD> \
  --out out/git.json
```

产出每条提交的：hash、作者、时间、标题、正文、改动文件数、增删行数、关联工单号（从提交信息正则提取）、是否 merge。

### 第 2 步：采集工单数据（可选）

```bash
python3 {baseDir}/scripts/collect_issues.py --config config.yaml --out out/issues.json
```

适配器通过 `config.yaml` 的 `provider` 字段选择，默认 `github`（需 `GITHUB_TOKEN` 环境变量，只读权限即可）。
也支持 `gitlab` / `jira` / `file`。内部系统一律用 `file`：把导出的 CSV/JSON 放进来即可，
**不要把内网地址或凭证写进本仓库**。凭证只从环境变量读，配置里只写变量名。

### 第 3 步：重组（这一步由你做，不是脚本）

读 `out/git.json` 和 `out/issues.json`，按下列顺序重组：

1. **按工单/特性聚类**，不是按人也不是按时间。一个工单下的多个 commit 合并成一条交付项。
2. **判定交付价值**：这条改动让用户或团队能做什么以前做不到的事？写不出来的，归入"内部优化"。
3. **提交信息质量差时**：读该 commit 的改动文件列表和 diff 摘要，反推意图，输出时在该条目后标注 `（推断）`。
4. **识别风险信号**，命中即列入风险区：
   - 单个 commit 改动文件数 > 30
   - 出现 `revert`、`hotfix`、`rollback` 关键词
   - 同一文件在本期被 3 个以上不同作者修改
   - 工单在本期内多次重开
5. **遗留项**：本期开始但未关闭的工单，标注阻塞原因；查不到原因就写"原因未知，需确认"。

### 第 4 步：渲染

```bash
python3 {baseDir}/scripts/render_report.py \
  --git out/git.json --issues out/issues.json \
  --template {baseDir}/references/report-template.md \
  --out out/report.md
```

脚本只做骨架和统计。**判断性内容由你填进对应小节**，然后交付 Markdown。

## 输出契约

报告必须含且仅含这六节，顺序不变：

| 小节 | 内容 | 硬要求 |
|---|---|---|
| 一、本期交付 | 按价值聚类的交付项 | 每条挂 commit/工单号 |
| 二、数据概览 | 提交数、参与人数、改动规模、工单流转 | 纯统计，不加评论 |
| 三、风险 | 命中风险信号的项 | 每条给出信号依据 |
| 四、遗留 | 未关闭工单 + 阻塞原因 | 原因未知须明写 |
| 五、下期计划 | 来自工单系统的排期 | 无数据则写"待排期" |
| 六、数据说明 | 时间窗、仓库列表、缺失项 | 必须诚实列出缺口 |

## 额度控制

- 用 **Ask 模式**跑第 3 步的重组，不要用 Craft。重组是纯文本推理，Craft 会多花几倍额度。
- 跑完一份报告后 `/clear`。上下文累积是额度浪费的最大来源。
- 单仓库单周的 `git.json` 通常 < 50KB；超过 200KB 说明时间窗开太大，先缩小窗口分批跑。

## 常见问题

**提交信息全是 "fix" "update"？** 走第 3 步的反推路径，并在报告"六、数据说明"里注明"本期 N 条提交信息不可用，结论由 diff 推断"。这句话本身就是给团队的改进信号。

**跨多个仓库？** `--repo` 可重复传。渲染时按仓库分组再按价值聚类。

**要给不同对象看？** 同一份数据渲两版：给技术负责人的保留全部六节；给上级的只要第一、三、五节，且第一节压到 5 条以内。
