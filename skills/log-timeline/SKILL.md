---
name: log-timeline
description: 多文件日志时间线重建、故障复盘、把几个服务的日志按时间合到一起、应用日志与 Nginx 日志和 syslog 对齐、跨时区日志统一、故障那几分钟到底发生了什么、谁先谁后、错误爆发点在哪、每秒事件密度、这三个文件时间格式不一样怎么对齐、错误是什么时候开始暴增的。当用户说「把这几个日志按时间线合起来」「复盘一下这次故障」「10 点到 10 点 05 分之间发生了什么」「先后顺序是什么」「哪台机器先报错」时使用。附纯标准库脚本 scripts/log_timeline.py，自动识别 ISO8601、带毫秒的常见格式、syslog、Nginx 与 Unix 毫秒时间戳并归一到 --tz，按时间排序合并并标注来源别名与级别，支持 --from/--to 时间窗、--grep、--level、无时间戳续行归并、ASCII 事件密度柱状图、错误爆发点检测与 --json。
author: Captain
version: 0.1.1
display_name: "日志时间线重建"
display_name_en: "Log Timeline"
description_zh: "把多个格式不同、时区不同的日志文件合成一条时间线：自动识别 ISO8601/syslog/Nginx/Unix 毫秒时间戳并归一到同一时区，按时间排序并标注来源与级别，附每桶事件密度柱状图、各文件首末事件与错误爆发点，故障复盘一条命令出结果。纯 Python 标准库。"
description_en: "Merge logs with different formats and time zones into one timeline: auto-detects ISO8601, syslog, Nginx and Unix-millis timestamps, normalizes to one zone, sorts and tags each line with its source and level, plus an ASCII event-density histogram, per-file first/last events and error-burst detection. Pure stdlib."
examples_zh:
  - "帮我做一次故障复盘，把这三个文件的日志按时间线合起来"
  - "这三个文件时间格式不一样怎么对齐，统一到 +08:00 看"
  - "错误是什么时候开始暴增的，给我每秒的事件密度"
examples_en:
  - "Merge these three logs into one timeline for the incident review"
  - "Different timestamp formats — normalize them all to +08:00"
  - "When did errors start spiking? Show the per-second density"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "⏱️" } }
---

# 日志时间线重建

故障复盘最费时间的一步，是把应用日志、接入层日志、系统日志按真实时间顺序拼起来 —— 它们格式不同、时区可能不同、有的甚至没有年份。这个技能一条命令给出一条合并时间线、一张事件密度图和错误爆发点。

## 用法

```bash
python3 scripts/log_timeline.py app.log nginx.log sys.log --tz +08:00
python3 scripts/log_timeline.py *.log --from "10:00:00" --to "10:05:00" --bucket 1s
python3 scripts/log_timeline.py app.log nginx.log --level ERROR --http-5xx
python3 scripts/log_timeline.py a.log b.log --grep "timeout|refused" --limit 50
python3 scripts/log_timeline.py app.log --assume-tz +08:00 --tz UTC      # 裸时间戳按东八区读，输出 UTC
python3 scripts/log_timeline.py *.log --no-timeline                      # 只要密度图与统计
python3 scripts/log_timeline.py *.log --json > timeline.json
zcat app.log.gz | python3 scripts/log_timeline.py - --bucket 10s
```

## 何时用

- 故障复盘要还原「几点几秒发生了什么、谁先出问题」；
- 一次请求横跨网关、应用、中间件，日志分散在多个文件；
- 手上的日志格式和时区不统一，肉眼对不齐；
- 想知道错误是从哪一秒开始暴增、持续了多久、什么时候恢复。

## 识别的时间戳

| 形态 | 例子 | 说明 |
| --- | --- | --- |
| ISO8601 | `2026-09-18T10-00-00.123+08:00` 同形状 | 带 Z 或偏移时按行内时区解读 |
| 常见日志 | `2026-09-18 10:00:00.123` | 无时区，按 `--assume-tz` 解读 |
| 斜杠日期 | `2026/09/18 10:00:00` | 同上 |
| Nginx | `[18/Sep/2026:10:00:00 +0800]` | 用行内偏移 |
| syslog | `Sep 18 10:00:00` | 没有年份，用 `--year` 补，默认当前年 |
| Unix 毫秒/秒 | `1789696800000`、`1789696800` | 按 UTC 解读后转换，常见于 JSON 日志 |

每行只取位置最靠前的那个匹配（默认只在前 200 字符里找，`--prefix` 可调），避免把消息正文里的时间当成行时间。**没有时间戳的行按「续行」并入上一条**（堆栈、多行 SQL 不会丢），时间线里用 `»` 标记；`--no-cont` 可丢弃。

## 流程

1. 先不带过滤跑一遍，看「输入文件」一节：每个文件识别了多少行、用的哪种格式、首末事件时间。**未识别行数很高说明格式没覆盖**，先确认时间戳形态再往下看。
2. 检查时区。带偏移的文件自动处理；裸时间戳按 `--assume-tz`（默认等于 `--tz`）解读，跨机房日志务必显式指定，否则会整体错几小时。
3. 看「事件密度」找异常窗口，再用 `--from/--to` 收窄到故障那几分钟，`--bucket 1s` 看清先后顺序。
4. 看「错误爆发点」定位起点，配合 `--grep` 提取同一关键词在各文件里的出现顺序 —— 谁先报错，基本就指向根因方向。
5. 把结论时间线贴进复盘文档；需要程序化处理时用 `--json`（含 files/timeline/density/bursts 四段）。

## 输出

- **输入文件**：短别名（A/B/C，带颜色）、行数、识别数、续行数、未识别数、首末事件、格式与级别分布。
- **合并时间线**：`HH:MM:SS.mmm 别名 级别 消息`，跨天插入日期分隔行，消息默认截断到 120 字符（`--width` 可调）。
- **事件密度**：每桶计数 + ASCII 柱状图 + 该桶错误数，中间的空桶保留，断流看得见。
- **错误爆发点**：ERROR/FATAL 数超过全程均值 + 2σ 且不少于 3 条的桶，最多 5 个，附示例行。

## 边界与常见问题

- 需要把全部事件读进内存排序；单次几百万行请先用 `--from/--to` 之外的手段（`grep`/`sed` 切片）缩小输入。
- 访问日志没有级别字段，默认级别显示 `-`；加 `--http-5xx` 可把 HTTP 5xx 的行当 ERROR 计入爆发检测。
- syslog 没有年份，跨年日志请显式 `--year`，否则 12 月的日志会被放到今年。
- 机器之间时钟漂移不会被纠正，工具只按写入的时间戳排序；毫秒级结论前先确认 NTP 是否同步。
- `--bucket` 给得过细（如 1s 跨几小时）会产生大量空桶，超过 2000 桶时自动只列有事件的桶。
- 不做模板聚类与相似日志归并，那用「日志模板聚类」技能；也不做指标突变检测，那用「日志异常检测」技能。
