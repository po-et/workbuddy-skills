# 完整示例：每天早上 8 点前自动出一份行数统计（Linux 服务器，cron）

> 示例。目录、文件名都是虚构的；下面的输出是在示例目录上实际运行改好的脚本得到的（去掉了时间戳）。

## 1. 用户原话

> 每天定时跑一下这个统计，早上 8 点前要出结果

## 2. 助手先问（最多 3 个）

1. 统计什么、数据在哪、结果写到哪？
2. 在什么机器上跑：一直开着的 Linux 服务器，还是会关机的个人电脑？
3. 要不要登录或调接口（需要凭据吗）？

## 3. 用户补充

> 每天凌晨系统往 /data/export/in 导出几个 CSV，要统计每个文件有多少行，结果写到 /data/export/out。Linux 服务器，一直开着。不需要登录，也不调接口。

## 4. 交付物

**① 假设（默认值已标出）**

```
输入  /data/export/in/*.csv（凌晨导出完成）[待确认：导出最晚几点完成]
输出  /data/export/out/daily_count.csv，每天整份覆盖；日志 /data/export/job.log
失败  输入目录不存在或某个文件读不了：整次任务记完整报错并以退出码 3 结束，不写半截结果
重叠  上一轮没跑完就跳过本轮（锁文件 /data/export/job.lock）
环境  Linux、cron、/usr/bin/python3，只用标准库
```

**② 脚本**：用 `scripts/template_scheduled_job.py`，示例任务 `run_job()` 正好是「统计每个 CSV 的数据行数」，另存为 `/home/you/jobs/daily_count.py`。不需要凭据，所以删掉 `main()` 里检查 `REPORT_TOKEN` 的 4 行，并把 `run_job(workdir, token, a.dry_run)` 改成 `run_job(workdir, None, a.dry_run)`。改动全文（`diff` 输出）：

```
85,88d84
<     token = os.environ.get(TOKEN_ENV)
<     if not token:
<         log.error("缺少环境变量 %s：先在 job.env 里 export 再运行（crontab 行里先 . job.env），不要写进脚本", TOKEN_ENV)
<         return EXIT_IO
102c98
<         run_job(workdir, token, a.dry_run)
---
>         run_job(workdir, None, a.dry_run)
```

**③ 先手动跑两条命令**

```bash
python3 /home/you/jobs/daily_count.py --workdir /data/export --dry-run
python3 /home/you/jobs/daily_count.py --workdir /data/export
```

在示例目录（2 个 CSV）上的实际输出：

```
统计了 2 个文件
[dry-run] customers_0926.csv 2 行
[dry-run] orders_0926.csv 3 行
统计了 2 个文件
已写出 …/out/daily_count.csv
```

```
文件,行数,统计时间
customers_0926.csv,2,[运行时刻]
orders_0926.csv,3,[运行时刻]
```

**④ 定时**：先 `date` 确认服务器时区；8 点前要结果，排在 7:30。`crontab -e` 加一行，解释器和脚本都写绝对路径：

```
30 7 * * * /usr/bin/python3 /home/you/jobs/daily_count.py --workdir /data/export >> /data/export/cron.out 2>&1
```

**⑤ 核对方法**：第二天 8 点前看 `/data/export/out/daily_count.csv` 的「统计时间」是不是当天；`job.log` 里有没有「任务失败」；行数抽一个文件用 `wc -l` 对一下（`wc -l` 含表头，比表里多 1）。

**⑥ 回退**：删掉 crontab 里那一行即停；脚本只写 `out/` 和日志，不动 `in/` 里的导出文件。

**⑦ 运行说明**：改好的脚本在示例目录上实际跑过（手动两次）；cron 触发没有在你的服务器上验证过，第一天早上请按第 ⑤ 条看一眼。

## 5. 交付前自检

| 检查项 | 结果 |
|---|---|
| 先 dry-run 再真跑，输出与计划一致 | 是 |
| 重跑整份覆盖，不追加重复行 | 是 |
| 失败记完整报错并以非 0 退出 | 是 |
| 没有凭据写进脚本或日志 | 是（本任务不需要凭据） |
| cron 里用了绝对路径，时区已提醒确认 | 是 |
| 写明了哪些跑过、哪些没跑过 | 是 |
