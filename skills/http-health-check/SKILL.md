---
name: http-health-check
description: 服务健康巡检、批量检查一组 URL 的状态码与耗时、TLS 证书到期提醒、接口可用性检查、发布后冒烟检查、定时巡检脚本、响应里必须包含某个关键字。当用户说「帮我检查这些服务是不是都正常」「发布完了跑一遍冒烟」「哪些域名的证书快过期了」「写个巡检脚本每天跑」「这个接口现在能不能访问、多快」时使用。附纯标准库脚本 scripts/health_check.py：并发请求 URL 列表（命令行或清单文件，每行可指定期望状态码与必含关键字），报告状态码、耗时、慢阈值、HTTPS 证书剩余天数与告警、错误原因；有异常退出码 1，可接 cron / CI；--json 便于接告警。
author: Captain
version: 0.1.0
display_name: "HTTP 健康巡检"
display_name_en: "HTTP Health Check"
description_zh: "一条命令并发巡检一批 URL：状态码是否符合预期、耗时是否超阈值、响应是否含关键字、HTTPS 证书还剩几天；异常退出码 1，可作发布后冒烟与定时巡检。纯 Python 标准库。"
description_en: "Probe a list of URLs concurrently in one command: expected status, latency threshold, response keyword, HTTPS certificate days left; non-zero exit on failure, suitable for post-deploy smoke tests and scheduled checks. Pure Python stdlib."
examples_zh:
  - "检查 endpoints.txt 里的服务是否都正常，超过 800ms 算慢"
  - "看看我们几个域名的 HTTPS 证书还剩多少天"
  - "发布后跑一遍冒烟检查，有问题就让流水线失败"
examples_en:
  - "Check every service in endpoints.txt, flag anything over 800ms"
  - "How many days are left on our domains' HTTPS certificates?"
  - "Run a post-deploy smoke check and fail the pipeline on errors"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🩺" } }
---

# HTTP 健康巡检

并发请求一批端点，报告状态码、耗时、关键字、证书到期。发布后冒烟、每日巡检、故障时快速定位「哪些挂了」都用它。

## 用法

```bash
python3 scripts/health_check.py https://api.example.com/health https://www.example.com/
python3 scripts/health_check.py --file endpoints.txt --timeout 5 --expect-ms 800 --tls-warn-days 30
python3 scripts/health_check.py --file endpoints.txt --json > result.json
```

清单文件 `endpoints.txt`，每行 `URL [期望状态码] [必含关键字]`：

```
# 核心服务
https://api.example.com/health 200 "ok"
https://admin.example.com/login 200
https://old.example.com/ 301
```

## 流程

1. 发布后立刻跑一遍，退出码非 0 就回滚或排查；输出里的 `✗` 带原因（超时、DNS、连接拒绝、状态码不符、关键字缺失）。
2. 定时巡检：cron 每 5 分钟跑 `--json`，把 `ok=false` 或 `tls_warn=true` 的条目推到告警渠道。
3. 证书：`--tls-warn-days` 默认 21 天，续期流程慢的团队调到 30–45。
4. 慢阈值 `--expect-ms` 按服务 SLO 设；持续 `!`（慢）但不 `✗` 的端点交给性能排查。

## 边界

- 只做 GET；需要鉴权的端点请用公开的健康检查路径，不要把令牌写进清单。
- 证书检查读的是 URL 主机的证书链末端证书；经 CDN 时看到的是 CDN 证书。
- 单次探测不是可用性统计；要算 SLA 请把 `--json` 结果入库后聚合。
