---
name: cron-explain
description: cron 表达式解释、crontab 看不懂、这个定时任务什么时候跑、计算接下来几次运行时间、时区换算、校验 cron 写法是否合法、逐行解释一份 crontab。当用户说「这个 cron 表达式是什么意思」「0 2 * * 1-5 什么时候执行」「帮我写一个每周一早上 9 点的 cron」「crontab 里这些任务分别什么时候跑」「为什么我的定时任务没在预期时间触发」时使用。附纯标准库脚本 scripts/cron_explain.py：解析标准 5 字段（含 * , - / 月份与星期名、? 、7=周日、@daily 等别名），输出中文含义与接下来 N 次运行时间（可指定 --tz），提示「日与周同时限定取或」这一常见坑，支持 --file 逐行解释 crontab、--json。
author: Captain
version: 0.1.0
display_name: "cron 表达式解释器"
display_name_en: "Cron Explain"
description_zh: "把 cron 表达式翻译成中文，并按指定时区列出接下来 N 次运行时间；校验字段范围、识别日/周「或」逻辑陷阱；可逐行解释整份 crontab。纯 Python 标准库。"
description_en: "Translate a cron expression into plain Chinese and list its next N run times in a given timezone; validates fields, flags the day-of-month/day-of-week OR trap; can explain a whole crontab line by line. Pure Python stdlib."
examples_zh:
  - "0 2 * * 1-5 是什么意思，接下来三次什么时候跑"
  - "帮我写一个每月 1 号和 15 号早上 8 点半的 cron，并验证"
  - "解释一下这份 crontab 里每个任务的执行时间"
examples_en:
  - "What does 0 2 * * 1-5 mean and when are the next three runs?"
  - "Write a cron for 08:30 on the 1st and 15th, then verify it"
  - "Explain every job's schedule in this crontab"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "⏰" } }
---

# cron 表达式解释器

把 cron 表达式翻译成人话，并算出接下来几次运行时间。写 cron 时先用它验证，再放进 crontab / K8s CronJob / CI 定时触发。

## 用法

```bash
python3 scripts/cron_explain.py "0 2 * * 1-5"                       # 含义 + 下 5 次（本机时区）
python3 scripts/cron_explain.py "*/15 9-18 * * *" -n 10 --tz Asia/Shanghai
python3 scripts/cron_explain.py @daily
python3 scripts/cron_explain.py --file /etc/crontab -n 1              # 逐行解释一份 crontab
python3 scripts/cron_explain.py "0 9 13 * fri" --json
```

## 流程

1. **解释**：用户给表达式就直接跑脚本，把「含义」和「接下来 N 次」原样给用户；有「日与周同时限定」提示时要特别说明 cron 取的是「或」。
2. **反向生成**：用户描述需求（「每周一早上 9 点」）时，先写出表达式，再用脚本验证接下来几次时间是否符合描述，把验证结果一起给用户。
3. **排查没触发**：先用 `--tz` 按服务器时区算预期时间，对比任务日志；常见原因：服务器时区不是本地时区、日/周「或」逻辑、分钟字段写成了秒、K8s CronJob 的 `timeZone` 未设置。
4. **校验整份 crontab**：`--file` 逐行输出，非法行会以 ✗ 标出原因。

## 支持范围与边界

- 标准 5 字段：分 时 日 月 周；`*` `,` `-` `/`；月份名 jan–dec、星期名 sun–sat；`?` 视为 `*`；`7` 视为周日；`@yearly @monthly @weekly @daily @hourly`。
- 不支持 6 字段（含秒）与 Quartz 的 `L` `W` `#`，遇到会提示。
- 日与周同时限定时按 POSIX cron 语义取「或」（与多数 crond 一致）；部分实现（如某些调度框架）可能不同，以目标平台文档为准。
- 下次运行时间按分钟枚举、最多向前搜索五年；不存在的日期（2 月 30 日）会给出提示。
