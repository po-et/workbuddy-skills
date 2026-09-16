---
name: log-anomaly
description: 日志突变检测、指标异常起点定位、错误率飙升时间点分析。当用户问「错误是什么时候开始变多的」「日志里 ERROR 什么时候飙升的」「这段指标的异常起点在哪」「帮我从 nginx / 应用日志里找故障开始时间」「告警之前多久就已经不对了」「把日志按分钟聚合看趋势」，或者要把故障起点和发布/变更记录对齐时使用。脚本对原始日志（ISO8601 / nginx / epoch 时间戳）按分钟聚合，或直接读 timestamp,value 的 CSV，用滑动基线 + 3σ + 连续点确认找出突变的开始、峰值与恢复时间；不是阈值告警，不需要外部服务。
author: Captain
version: 0.1.0
display_name: "日志突变检测"
display_name_en: "Log Anomaly Onset Detector"
description_zh: "把原始日志或指标 CSV 变成时间序列，用滑动基线 3σ 找出异常开始、峰值与恢复的时间点，用于和变更记录对齐。"
description_en: "Turn raw logs or metric CSVs into a time series and find when anomalies start, peak and recover using a sliding-baseline 3σ rule, so onsets can be matched against changes."
examples_zh:
  - "这个 app.log 里 ERROR 是从几点开始飙升的？"
  - "把 nginx 日志按分钟聚合，找 5xx 突变的时间点"
  - "这份接口耗时 CSV 的异常起点在哪，什么时候恢复的"
examples_en:
  - "When did ERROR lines start spiking in this app.log?"
  - "Bucket the nginx log per minute and find when 5xx jumped"
  - "Find the anomaly onset and recovery in this latency CSV"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📈" } }
---

# 日志突变检测

阈值告警只说"现在坏了"；这个技能回答"**什么时候开始坏的**"——只有起点时间才能和发布、配置、基础设施变更对上。

## 核心原则

1. **找起点，不找超标点。** 输出的是突变开始的时间、方向、幅度、恢复时间。
2. **连续确认，不信毛刺。** 默认连续 3 个点越过 3σ 才算突变，避免单点噪声。
3. **基线来自数据本身。** 不需要预设阈值；基线不足时明确说"无法判断"，不硬给结论。
4. **结论止于时间点。** 原因要靠变更记录与排查，本技能不猜根因。

## 执行流程

### 第 1 步：跑检测

原始日志（自动识别 ISO8601 / nginx `10/Sep/2026:14:00:00 +0800` / 秒级 epoch）：

```bash
python3 {baseDir}/scripts/log_anomaly.py --input app.log --bucket 60 --match "ERROR|Exception" --md out/anomaly.md --out out/anomaly.json
```

指标 CSV（`timestamp,value` 两列，也接受 `count`）：

```bash
python3 {baseDir}/scripts/log_anomaly.py --input latency.csv --sigma 3 --consecutive 3 --window 60 --md out/anomaly.md
```

参数：`--bucket` 聚合秒数；`--match` 只统计匹配行；`--sigma` 越界倍数；`--consecutive` 连续确认点数；`--window` 滑动基线长度；`--min-baseline` 最少基线点数。

### 第 2 步：解读（这一步由你做）

- 报告每个突变：开始时间（这是最重要的一行）、方向、峰值相对基线的倍数、是否恢复。
- 起点前后 30 分钟内的发布 / 配置 / 扩缩容 / 上游变更是首要嫌疑；建议用「线上排查简报」技能把变更与时间线合并。
- 没检出突变时按脚本提示排查参数，或指出"异常可能从数据开头就存在"。
- 多个突变要判断是否同一事件（恢复后再起）还是多起事件。

### 第 3 步：交付

Markdown 表 + 一句结论："X 时 Y 分开始异常，持续 Z 分钟，峰值是基线的 N 倍；建议核对该时刻前 30 分钟的变更。"

## 输出契约

```
# 突变检测：<文件>
- 输入行数 / 匹配行数 / 无法解析行数
- 序列点数与聚合粒度；参数
| # | 开始 | 方向 | 首点 z | 基线均值±σ | 峰值 | 恢复 |
下一步：与变更记录对齐
```

## 常见问题

**日志时间戳不是这三种格式？** 先用 `awk`/`sed` 把时间列转成 ISO8601，或导出成 CSV。
**多台机器的日志？** 先 `cat` 合并再跑；按机器分别跑可以看出是否只有单机异常。
**要看 QPS 而不是错误？** 去掉 `--match`，统计全部行。
