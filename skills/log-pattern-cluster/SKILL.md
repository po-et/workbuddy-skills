---
name: log-pattern-cluster
description: 日志聚类、日志模板归并、海量日志降噪、找出最常见和最少见的日志模式、新出现的错误是什么、把变量位（时间/ID/IP/路径/数字）抽象后统计、故障排查时快速看日志全貌。当用户说「这几百万行日志帮我归一下类」「日志里最多的是什么」「有没有新出现的错误」「把日志按模式统计一下」「ERROR 日志都是哪几种」时使用。附纯标准库脚本 scripts/log_cluster.py：把时间戳、UUID、IP、哈希、URL、邮箱、路径、十六进制、带单位数字、数字、引号字符串替换为占位符后按模板计数，输出最常见与最少见的模板（含示例行与级别分布），支持 --level 过滤、stdin、--json；与「日志异常检测」技能互补。
author: Captain
version: 0.1.0
display_name: "日志模板聚类"
display_name_en: "Log Pattern Cluster"
description_zh: "把海量日志按模板归并：变量位抽象成占位符后计数，输出最常见的模式（噪音在哪）与最少见的模式（新错误在哪），支持按级别过滤；纯 Python 标准库，单文件即用。"
description_en: "Cluster large logs by template: abstract variable slots into placeholders, count templates, show the most common patterns (where the noise is) and the rarest (where new errors hide), with level filtering; pure Python stdlib, single file."
examples_zh:
  - "把 app.log 按模板聚类，看看最常见的 20 种日志"
  - "只看 ERROR 级别，有没有新出现的错误模式"
  - "这个 5G 的日志文件先给我一个全貌"
examples_en:
  - "Cluster app.log by template and show the top 20 patterns"
  - "ERROR level only: any newly appearing error patterns?"
  - "Give me an overview of this 5GB log file first"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧬" } }
---

# 日志模板聚类

几百万行日志通常只有几十种「模板」。把时间、ID、IP、数字这些变量位抽象掉再计数，最常见的模板告诉你噪音在哪，最少见的模板往往就是新出现的错误。

## 用法

```bash
python3 scripts/log_cluster.py app.log --top 30 --rare 20
python3 scripts/log_cluster.py app.log worker.log --level ERROR
zcat app.log.gz | python3 scripts/log_cluster.py -
python3 scripts/log_cluster.py app.log --json > clusters.json
```

## 流程

1. 先跑全量看压缩比与前 30 个模板：占比最高的几种若是无信息量的 INFO，考虑降级或采样，日志费用立减。
2. `--level ERROR`（或 WARN）看错误模板分布；「最少见」列表里只出现一两次的模板优先看——新错误、偶发 panic、边角异常都在这。
3. 故障时对比故障前后两个时间段的聚类结果（分别跑一次），新增或激增的模板就是线索；数量激增的具体判定可配合「日志异常检测」技能的 3σ 方法。
4. 把高频模板整理成告警规则或仪表盘的分类依据。

## 变量位识别

时间戳、日期、时间、UUID、IP(:端口)、24–64 位十六进制哈希、URL、邮箱、路径（≥2 段）、0x 十六进制、带单位数字（ms/s/kb/mb/%…）、数字、单双引号字符串。字母紧贴的数字（如 `E3`、`v2`）保留，作为分类信息。

## 边界

- 纯正则模板化，不做 Drain 那类树状学习；对结构化 JSON 日志建议先用 jq 抽出 message 字段再聚类。
- 多行堆栈会按行分别归并；堆栈首行（异常类型 + 消息）通常足够定位。
- 极大文件逐行流式处理，内存占用与模板数成正比而非行数。
