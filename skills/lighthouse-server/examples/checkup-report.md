# 示例：用体检脚本给一台轻量服务器做检查

> 以下输入是为演示构造的样例数据（公网地址用文档保留地址段），输出是脚本对这些样例的真实运行结果，未手改。

## 用户原话（示例）

> 帮我看看这台轻量服务器有没有安全问题。我把 /etc/ssh 整个目录拷下来了，还有 `ss -tulnp` 和 `df -hP` 的输出。

## 输入

`etc-ssh/sshd_config`：

```
Include /etc/ssh/sshd_config.d/*.conf

Port 22
PermitRootLogin yes
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM yes
X11Forwarding yes
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server

Match User backup
    PasswordAuthentication yes
```

`etc-ssh/sshd_config.d/50-cloud-init.conf`：

```
PasswordAuthentication yes
```

`ss.txt`（节选）：

```
tcp   LISTEN 0      4096   0.0.0.0:22               0.0.0.0:*     users:(("sshd",pid=812,fd=3))
tcp   LISTEN 0      511    0.0.0.0:80               0.0.0.0:*     users:(("nginx",pid=1235,fd=6),("nginx",pid=1234,fd=6))
tcp   LISTEN 0      4096   0.0.0.0:6379             0.0.0.0:*     users:(("docker-proxy",pid=2201,fd=4))
tcp   LISTEN 0      511    127.0.0.1:3000           0.0.0.0:*     users:(("node",pid=1502,fd=21))
tcp   LISTEN 0      4096   0.0.0.0:8080             0.0.0.0:*     users:(("java",pid=1720,fd=45))
tcp   LISTEN 0      80     *:3306                   *:*           users:(("mysqld",pid=990,fd=23))
tcp   ESTAB  0      0      203.0.113.10:22          198.51.100.7:51234 users:(("sshd",pid=3001,fd=4))
```

`df.txt`：

```
Filesystem      Size  Used Avail Use% Mounted on
tmpfs           197M  1.1M  196M   1% /run
/dev/vda2        40G   37G  1.6G  96% /
/dev/vda1       511M  6.1M  505M   2% /boot/efi
/dev/vdb1       100G   83G   18G  83% /data
```

## 命令

```bash
python3 scripts/server_checkup.py --sshd-config etc-ssh/sshd_config --ports-file ss.txt --df-file df.txt
```

## 脚本输出（退出码 0）

```
服务器体检报告

【输入】
  sshd：etc-ssh/sshd_config（共读 2 个文件，含 Include）
  端口：ss.txt（识别到 11 条监听）
  磁盘：df.txt（3 个挂载点）

【风险清单】（高 → 中 → 低 → 提示）
[高] SSH-01 root 可以用密码登录
      证据：PermitRootLogin yes（sshd_config:5）+ PasswordAuthentication yes（50-cloud-init.conf:1）
      建议：先建 sudo 用户并配好密钥，再设 PermitRootLogin no、PasswordAuthentication no
[高] SSH-02 允许密码登录，暴露在全网爆破之下
      证据：PasswordAuthentication yes（50-cloud-init.conf:1）
      建议：确认密钥能登录后设为 no；按 references/ssh-hardening.md 走，保留救命会话
[高] PORT-3306 3306 端口（MySQL）对外监听
      证据：tcp 3306 监听在所有网卡，进程 mysqld
      建议：改为只听 127.0.0.1（容器用 -p 127.0.0.1:3306:3306 或不映射端口）；并确认控制台防火墙没有放行 3306
[高] PORT-6379 6379 端口（Redis）对外监听
      证据：tcp 6379 监听在所有网卡，进程 docker-proxy
      建议：改为只听 127.0.0.1（容器用 -p 127.0.0.1:6379:6379 或不映射端口）；并确认控制台防火墙没有放行 6379
[高] DISK-/ 磁盘空间快满了
      证据：/ 空间 已用 96%
      建议：先 du 找大目录（日志、Docker 镜像、备份），确认后再清理；必要时扩容
[中] PORT-8080 应用端口直接对外，没经过 Nginx 与 HTTPS
      证据：tcp 8080 监听在所有网卡，进程 java
      建议：应用改听 127.0.0.1:8080，由 Nginx 反代并启用 HTTPS
[中] DOCKER-6379 Docker 映射的端口不受主机 ufw 规则约束
      证据：tcp 6379 监听在所有网卡，进程 docker-proxy
      建议：容器端口映射写成 127.0.0.1:6379:容器端口，外层靠控制台防火墙
[中] DISK-/data 磁盘空间占用偏高
      证据：/data 空间 已用 83%
      建议：排查增长来源，设置日志轮转与 Docker 日志上限
[低] SSH-08 开启了 X11 转发，服务器一般用不到
      证据：X11Forwarding yes（sshd_config:9）
      建议：设为 no
[提示] SSH-06 SSH 在默认 22 端口，扫描流量会比较多
      证据：Port 22
      建议：改端口只能降噪，不能替代密钥登录；要改就先在控制台防火墙放行新端口
[提示] SSH-09 没有限定哪些账号能 SSH 登录
      证据：未设置 AllowUsers / AllowGroups
      建议：可加 AllowUsers <你的用户>；写错会把所有人挡在外面，改后务必新开终端验证
[提示] SSH-10 存在 Match 条件块，上面的结论只针对全局设置
      证据：发现 1 个 Match 块
      建议：以 sudo sshd -T 的输出为准

【监听端口】
  tcp  22     所有网卡    sshd              对外（SSH，常规）
  tcp  53     仅本机      systemd-resolve   仅本机，正常
  udp  53     仅本机      systemd-resolve   仅本机，正常
  udp  68     所有网卡    systemd-network   系统客户端端口，正常
  tcp  80     所有网卡    nginx             对外（HTTP，常规）
  tcp  3000   仅本机      node              仅本机，正常
  tcp  3306   所有网卡    mysqld            对外（MySQL，风险）
  tcp  6379   所有网卡    docker-proxy      对外（Redis，风险）
  tcp  8080   所有网卡    java              对外（应用端口）

【磁盘】
  / 空间 已用 96%
  /boot/efi 空间 已用 2%
  /data 空间 已用 83%

【脚本看不到、需要人工核对】
  □ 控制台防火墙：只放行 SSH 端口、80、443（脚本看不到控制台规则，以腾讯云控制台为准）
  □ 快照与机外备份：最近 7 天内有，且做过一次恢复演练
  □ 流量：控制台里本月流量用量未接近套餐上限（计费与限速规则以官方为准）
  □ 备案：国内地域对外提供网站服务通常需要备案，以官方要求为准

汇总：高 5 / 中 3 / 低 1 / 提示 3
```

注意 SSH-02：主配置里明明写了 `PasswordAuthentication no`，但 `50-cloud-init.conf` 经 Include 先被读到，`yes` 抢先生效——这正是只改主配置不管用的典型原因。

## 助手的交付物（按输出契约）

```
【现状】Ubuntu [待确认]｜root 可密码登录｜对外：22、80、3306、6379、8080｜/ 分区 96%
【今天先做（按顺序）】
1. 控制台打快照（入口以控制台为准）
2. 磁盘：du 找出占用最大的目录，把清单发我确认后再清理（先保证 SSH 改配置时不会因磁盘满失败）
3. 3306 / 6379：MySQL 改 bind-address=127.0.0.1；Redis 容器改 -p 127.0.0.1:6379:6379；
   验证：ss -tlnp 里两者都是 127.0.0.1｜回退：改回原配置并重启服务
4. 控制台防火墙只留 22、80、443（以控制台为准）
5. SSH：密钥验证通过后写 00-hardening.conf（预览三行，等你确认）；sshd -T 核对；新终端验证｜回退见 references/ssh-hardening.md 第 6 节
6. 8080：Java 应用改听 127.0.0.1，由 Nginx 反代，再上 HTTPS
【之后】X11Forwarding no；AllowUsers 限定账号；每周跑一次体检脚本
```
