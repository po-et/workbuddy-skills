# SSH 加固：密钥登录、关密码、禁 root 直登（每一步都能回退）

适用：Ubuntu / Debian 与 OpenCloudOS / TencentOS / CentOS 系镜像。命令都在服务器上执行（标「本机」的除外）。动手前先在控制台打一份快照。

## 0. 先记住两条规则

1. **sshd 对同一个关键字，取第一次读到的值。** 较新系统的主配置开头有 `Include /etc/ssh/sshd_config.d/*.conf`，目录里的文件按文件名顺序先被读。你在主配置后面写 `PasswordAuthentication no`，可能被 `sshd_config.d/` 里某个文件（云镜像有时会放一个）的 `yes` 抢先生效。
2. **以 `sudo sshd -T` 为准。** 它打印 sshd 实际生效的配置。改完不看它，等于没验证。

## 1. 准备密钥和救命会话

```bash
# 本机：生成密钥（已有就跳过），私钥建议设口令
ssh-keygen -t ed25519 -C "my-laptop"
# 本机：把公钥装到服务器（此时密码登录还开着）
ssh-copy-id -i ~/.ssh/id_ed25519.pub deploy@[公网IP]
# 本机：新开终端，确认不再询问密码
ssh deploy@[公网IP]
```

- 私钥是不带 `.pub` 的那个文件：只留在自己电脑，不上传服务器、不发给任何人、不提交进仓库。
- 控制台也能创建和绑定密钥（入口以腾讯云控制台为准）。绑定前看清提示：是否需要关机、是否会同时改变密码登录设置。
- **全程保留一个已登录的终端不关**，这是出问题时回退用的救命会话。

## 2. 看清现状

```bash
grep -n '^Include' /etc/ssh/sshd_config
sudo grep -rn -Ei 'passwordauthentication|permitrootlogin|kbdinteractive|challengeresponse' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null
sudo sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication|usepam|pubkeyauthentication|port) '
```

## 3. 修改：预览 → 用户确认 → 执行

**有 Include 行**：新建一个文件名以 `00-` 开头的文件，保证它最先被读到。先把下面三行给用户看，确认后再执行：

```bash
sudo tee /etc/ssh/sshd_config.d/00-hardening.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
```

**没有 Include 行**（较老的系统）：先备份，再把这三行写到主配置最前面，或改掉已有的同名行：

```bash
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%F)
```

几个说明：
- `KbdInteractiveAuthentication`：较老的 OpenSSH 用 `ChallengeResponseAuthentication`。下一步 `sshd -t` 报「Bad configuration option」时，把这一行换成 `ChallengeResponseAuthentication no`。只关 `PasswordAuthentication`、不关它，在 `UsePAM yes` 时仍可能通过键盘交互输入密码。
- `PermitRootLogin`：`no` 最严；暂时还需要 root 用密钥登录，就写 `prohibit-password`。

## 4. 校验，再重载

```bash
sudo sshd -t                     # 有语法错误会直接报出来；报错就别重载
sudo sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication) '
sudo systemctl reload ssh        # RHEL 系：sudo systemctl reload sshd
```

重载不会断开已经建立的会话。

## 5. 新开终端验证（三条都符合预期才关救命会话）

```bash
ssh deploy@[公网IP]                                       # 应能用密钥登录
ssh -o PubkeyAuthentication=no deploy@[公网IP]            # 应被拒：Permission denied (publickey)
ssh root@[公网IP]                                         # PermitRootLogin no 时应被拒
```

## 6. 回退（从轻到重）

| 情况 | 回退办法 |
|---|---|
| 新会话进不去，救命会话还在 | `sudo mv /etc/ssh/sshd_config.d/00-hardening.conf /root/ && sudo systemctl reload ssh`，查清原因再来 |
| 救命会话也断了 | 用控制台的 VNC 类登录（不经过 SSH，名称以控制台为准）进系统，做上一行同样的回退 |
| 系统账号密码也不记得 | 控制台重置密码或绑定新密钥（是否需要重启、会改变什么，以控制台提示为准） |
| 以上都不行 | 回滚到改动前的快照。快照之后写入的数据会丢，回滚前先确认 |

## 7. 改 SSH 端口（可选，只能降噪）

顺序不能乱：

1. 控制台防火墙放行新端口（如 2222）；系统里开了 ufw/firewalld 的也放行。
2. 在 `00-hardening.conf` 里写两行 `Port 22` 和 `Port 2222`，先双端口并存。
3. `sudo sshd -t`，然后让新端口生效：
   - 普通情况：`sudo systemctl restart ssh`（RHEL 系 `sshd`）。
   - Ubuntu 较新版本默认用 socket 激活，端口由 `ssh.socket` 监听：`sudo systemctl daemon-reload && sudo systemctl restart ssh.socket`，以发行版文档为准。
   - SELinux 为 enforcing 的系统（RHEL 系常见），还要 `sudo semanage port -a -t ssh_port_t -p tcp 2222`。
4. `ss -tlnp | grep -E ':(22|2222) '` 看实际在听哪些端口；新端口能登录后，去掉 `Port 22`，再在控制台关掉 22。

## 8. 可选增强

- 限定可登录账号：在 `00-hardening.conf` 加 `AllowUsers deploy`。写错会把所有人挡在外面，务必走完第 4–5 步。
- 挡爆破：控制台防火墙把 SSH 来源限定为自己的固定出口 IP；或用 fail2ban 之类工具（从发行版软件源安装，配置以其文档为准）。
- 看登录记录：`last -n 20`；`sudo journalctl -u ssh --since "7 days ago" | grep -E 'Accepted|Failed'`（RHEL 系把 `ssh` 换成 `sshd`）。
