---
name: access-log-stats
description: 访问日志统计分析、Nginx / Apache access.log 分析、按接口统计 QPS 与 P95/P99 耗时、错误率、5xx 最多的接口、最慢的接口、Top 客户端 IP、JSON 行日志分析、性能排查前的全貌。当用户说「分析一下 nginx 日志哪些接口最慢」「统计各接口的请求量和错误率」「P99 是多少」「哪些 IP 请求最多」「从访问日志看看昨晚的故障」时使用。附纯标准库脚本 scripts/access_log_stats.py：自动识别 combined 格式（含尾部 rt= / request_time 耗时）与 JSON 行（字段名可配置），--group-ids 把路径里的数字/UUID 归并成 :id 按接口聚合，输出请求量 Top、P50/P95/P99/max、慢请求数、5xx/4xx、错误率、状态码分布、高峰时段、Top IP；支持 stdin 与 --json。
author: Captain
version: 0.1.0
display_name: "访问日志统计"
display_name_en: "Access Log Stats"
description_zh: "一条命令把 Nginx/Apache/JSON 访问日志变成接口级报表：请求量、占比、P50/P95/P99、慢请求、5xx 与错误率、高峰时段、Top IP；路径 ID 自动归并；纯 Python 标准库。"
description_en: "Turn Nginx/Apache/JSON access logs into a per-endpoint report in one command: volume, share, P50/P95/P99, slow requests, 5xx and error rate, peak hour, top IPs; path IDs auto-grouped; pure Python stdlib."
examples_zh:
  - "分析 access.log，按接口给我请求量、P95 和错误率"
  - "哪些接口 5xx 最多、哪些最慢"
  - "这份 JSON 格式的网关日志按 path 字段统计一下"
examples_en:
  - "Analyze access.log: per-endpoint volume, P95 and error rate"
  - "Which endpoints have the most 5xx and which are slowest?"
  - "Summarize this JSON gateway log by its path field"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📊" } }
---

# 访问日志统计

把访问日志变成接口级报表：谁最忙、谁最慢、谁在报错、谁在刷。性能排查、容量评估、故障复盘第一步。

## 用法

```bash
python3 scripts/access_log_stats.py /var/log/nginx/access.log --group-ids --top 20
zcat access.log.*.gz | python3 scripts/access_log_stats.py - --group-ids
python3 scripts/access_log_stats.py gateway.jsonl --format json --path-key uri --status-key code --time-key latency --time-unit ms
python3 scripts/access_log_stats.py access.log --slow-ms 500 --json > stats.json
```

耗时字段：Nginx 在 log_format 末尾加 `rt=$request_time`（秒）即可被识别；JSON 日志默认读 `duration_ms`（毫秒），可用 `--time-key/--time-unit` 指定。没有耗时字段时只统计量与状态码。

## 流程

1. 先看「请求量 Top」：占比高的接口决定容量；错误率列直接定位故障接口。
2. 看「P95 最慢」：P95 与 P50 差距大的接口有长尾（缓存穿透、慢 SQL、下游超时）；配合 `--slow-ms` 数慢请求。
3. 看「5xx 最多」与高峰时段：错误集中在某时段说明是容量或依赖故障，均匀分布说明是代码问题。
4. 「Top IP」异常集中时检查爬虫/攻击/失控的重试客户端。
5. 需要按时间切片对比时，先用 grep 按时间段切出日志再分别统计。

## 边界

- combined 格式按标准 Nginx/Apache 正则解析；自定义 log_format 请转 JSON 或调整正则。
- `--group-ids` 只归并纯数字、UUID、≥16 位十六进制的路径段；`/users/alice` 这类字符串 ID 不会归并。
- 百分位按内存排序计算，千万行级别日志建议先按时间或接口切分。
