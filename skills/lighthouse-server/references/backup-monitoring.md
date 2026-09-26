# 快照、备份与日常巡检

## 1. 快照

- 什么时候打：改 SSH 或防火墙前、系统大版本升级前、上线新版本前，再加每周固定一次。
- 快照不等于备份：快照和实例在同一账号、同一地域，账号出问题、误删实例、磁盘被勒索加密后又被新快照覆盖，都可能一起受影响。
- 回滚快照会用快照内容覆盖当前系统盘，快照之后写入的数据全部丢失；回滚前先把要留的数据拷走。
- 快照数量上限、是否收费、能否设置定期快照：以腾讯云控制台和「轻量应用服务器」文档的快照相关章节为准。

## 2. 数据备份（3-2-1：三份、两种介质、一份在机器外）

示例：每天 3:30 导出 PostgreSQL，保留 7 天。放进 deploy 用户的 crontab（`crontab -e`）：

```
30 3 * * * pg_dump -Fc -h 127.0.0.1 -U app appdb > /home/deploy/backup/appdb-$(date +\%F).dump
45 3 * * * find /home/deploy/backup -name 'appdb-*.dump' -mtime +7 -delete
```

- 第二行会删文件：先去掉 `-delete` 手动跑一次，看列出的是不是只有旧备份，确认后再加回去。
- 数据库口令放 `~/.pgpass`（权限 600）；MySQL 用 `mysqldump --single-transaction`，口令放 `~/.my.cnf`（权限 600）。不要把口令写在命令行或 crontab 里。
- 机器外一份：同步到对象存储（如腾讯云 COS，工具与鉴权方式以官方文档为准；SecretId/SecretKey 从环境变量或权限 600 的配置文件读，绝不进仓库），或定期下载到本地。
- 每月演练一次恢复：在新实例或本地把最新备份恢复出来，能查到最近的数据才算备份有效。

## 3. 磁盘

先看，再删：

```bash
df -hP                                                         # 各分区占用
sudo du -xh --max-depth=1 / 2>/dev/null | sort -h | tail -n 10 # 哪个目录最大，逐层往下钻
journalctl --disk-usage                                        # systemd 日志占用
docker system df                                               # 镜像、容器、卷各占多少
```

确认后再清理：

```bash
sudo journalctl --vacuum-size=200M     # 系统日志只留 200M
docker image prune                     # 只删悬空镜像；加 -a 会删所有没被容器使用的镜像，谨慎
sudo apt autoremove && sudo apt clean  # 旧内核与安装包缓存（RHEL 系：sudo dnf autoremove && sudo dnf clean all）
```

- 应用日志交给 logrotate 轮转；Docker 容器日志在 compose 的 `logging.options` 里设 `max-size` / `max-file`。
- 不手工删 `/var/lib/docker/`、数据库数据目录和不认识的文件；删之前让用户确认清单。
- 磁盘经常满：扩容云硬盘或把数据挪到数据盘（操作以控制台为准），不要靠反复删日志硬撑。

## 4. 流量

- 轻量应用服务器的套餐通常包含一定的月流量（控制台常称流量包）；超出后怎么计费或限速以官方为准。每周在控制台看一次用量，能设告警就设（腾讯云可观测平台，原云监控；名称与入口以官网为准）。
- 本机粗看：`cat /proc/net/dev`（开机以来各网卡累计收发字节）、`ip -s link`；需要按天统计可装 vnstat。
- 流量突然暴涨：先看访问日志里谁在大量请求：

```bash
sudo awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head
```

  访问日志的细分析可转 `access-log-stats` 技能；确认被盗刷就在控制台防火墙或 Nginx 里封禁来源，大文件改放对象存储并开防盗链。

## 5. 每周 5 分钟巡检表

| 项 | 命令或位置 | 正常标准 |
|---|---|---|
| 体检脚本 | `sudo python3 server_checkup.py` | 没有「高」 |
| 系统更新 | `apt list --upgradable`（RHEL 系 `dnf check-update`） | 安全更新已安装 |
| 磁盘 | `df -hP` | 各分区低于 80% |
| 证书 | `openssl s_client ... \| openssl x509 -noout -enddate` | 剩余 14 天以上 |
| 快照与备份 | 控制台快照列表、备份目录 | 最近 7 天内都有 |
| 流量 | 控制台流量用量 | 没接近套餐上限 |
| 登录记录 | `last -n 20`；`sudo journalctl -u ssh --since "7 days ago" \| grep Accepted` | 没有陌生来源的成功登录 |

## 6. 官方文档去哪查（章节名以文档目录为准）

- 腾讯云文档中心 →「轻量应用服务器」：登录 Linux 实例、防火墙、快照、密钥、流量包相关章节。
- 腾讯云文档中心 →「网站备案」「SSL 证书」「对象存储 COS」「腾讯云可观测平台」。
