---
name: lighthouse-server
description: "轻量服务器——把刚买的腾讯云轻量应用服务器配成能安全跑网站的机器：SSH 密钥、防火墙、Docker、Nginx 反代、HTTPS、快照与巡检，附体检脚本。当用户说「轻量服务器怎么配置」「服务器安全加固」「给服务器做个体检」时使用。"
author: Captain
version: 0.1.0
display_name: "轻量服务器"
display_name_en: "Lighthouse Server Setup"
description_zh: "腾讯云轻量应用服务器从零上手：首次登录的安全基线（密钥登录、关密码登录的回退办法、防火墙最小放行）、系统更新与非 root 用户、Docker 与 Nginx 反代与 HTTPS 的部署顺序、快照与备份、流量和磁盘巡检、备案提醒；附只读体检脚本输出风险清单。"
description_en: "Take a new Tencent Cloud Lighthouse instance from first login to a safely run web server: SSH keys with a rollback path, minimal firewall rules, updates, a sudo user, Docker, Nginx reverse proxy, HTTPS, snapshots and routine checks, plus a read-only audit script."
tags:
  - "轻量服务器"
  - "轻量应用服务器"
  - "腾讯云"
  - "Lighthouse"
  - "服务器安全加固"
  - "SSH"
  - "Nginx"
  - "HTTPS"
  - "Docker"
  - "云服务器"
examples_zh:
  - "刚买了腾讯云轻量服务器，第一步该做什么才安全？"
  - "轻量服务器想关掉密码登录只用密钥，怎么做才不会把自己锁在外面？"
  - "帮我给轻量服务器做个体检，这是 ss -tlnp 和 df -h 的输出"
examples_en:
  - "I just bought a Tencent Cloud Lighthouse server. How do I set it up securely to host a website?"
  - "Audit my server: here are my sshd_config and the output of ss -tlnp."
---

# 轻量服务器

定位一句话：**把刚开通的腾讯云轻量应用服务器，按「先保住登录 → 再关门 → 再上服务 → 最后留后路」的顺序配成能安全跑网站的机器，每一步都有验证和回退。**

## 何时使用

- 「刚买了腾讯云轻量服务器，第一步该做什么？」
- 「想关掉密码登录只用密钥，怎么做才不会把自己锁在外面？」
- 「服务器上要跑 Docker + Nginx + HTTPS，按什么顺序装？」
- 「帮我看看服务器有没有安全隐患」（用户贴 sshd_config、`ss -tlnp`、`df -h` 的输出）
- 「快照怎么打、磁盘和流量平时怎么盯？」

不适用：
- 逐行审查一份 Nginx 配置、排查证书链、查 DNS 解析 → 分别转 `nginx-config-check`、`tls-cert-check`、`dns-check` 技能；只问一个指令什么意思就直接简答。
- 疑似已被入侵（陌生进程、CPU 跑满、流量暴涨）→ 只给下方出错表里的止血三步，然后转腾讯云工单或安全专业人员，不在这里取证。
- 选套餐、比价格、算流量费 → 以腾讯云官网与控制台为准，本技能不报价。

## 总顺序（8 步，每步有完成标志）

| 步 | 做什么 | 完成标志 |
|---|---|---|
| 0 | 控制台给空机打一份快照 | 快照列表里能看到 |
| 1 | 首次登录、系统更新 | 更新完成；需要重启的已重启 |
| 2 | 建 sudo 用户、配 SSH 密钥 | 新开终端用密钥登录，`sudo whoami` 输出 root |
| 3 | 关密码登录、禁 root 直登（带回退） | `sshd -T` 显示期望值；新会话验证通过才关旧会话 |
| 4 | 防火墙只放行必需端口 | 控制台防火墙只剩 SSH 端口、80、443 |
| 5 | 装 Docker（如需），应用只听 127.0.0.1 | `ss -tlnp` 里应用端口是 127.0.0.1 |
| 6 | Nginx 反代 → 域名解析 → HTTPS | https 访问正常；续期演练通过 |
| 7 | 快照与机外备份、磁盘和流量巡检 | 体检脚本无「高」；备份恢复演练过 |

备案：国内地域对外提供网站服务通常需要备案，以官方要求为准。材料准备可和第 1–5 步并行，上线时间按备案进度倒排。

### 第 1–2 步：登录、更新、sudo 用户与密钥

登录用控制台的网页登录入口（名称以控制台为准）或本地 `ssh`；默认用户名因镜像而异（有的是 root，Ubuntu 类镜像常见 ubuntu），以镜像说明为准。

```bash
# 服务器上：更新（OpenCloudOS/TencentOS/CentOS 系用 sudo dnf upgrade -y，老系统用 yum）
sudo apt update && sudo apt upgrade -y
[ -f /var/run/reboot-required ] && echo "需要重启：sudo reboot"
# 服务器上：建日常用的 sudo 用户（已有 ubuntu 这类 sudo 用户可跳过；RHEL 系把 sudo 组换成 wheel）
sudo adduser deploy && sudo usermod -aG sudo deploy
# 自己电脑上：生成密钥并装到服务器（此时密码登录还开着）
ssh-keygen -t ed25519 -C "my-laptop"
ssh-copy-id -i ~/.ssh/id_ed25519.pub deploy@[公网IP]
```

私钥（不带 .pub 的文件）只留在自己电脑并设口令，不上传服务器、不发给任何人、不提交进仓库。

### 第 3 步：关密码登录（预览 → 确认 → 执行）

两条规则：sshd 对同一关键字取**第一次读到的值**，主配置开头的 `Include sshd_config.d/*.conf` 先被读，云镜像有时在里面放 `PasswordAuthentication yes`；改完一律以 `sudo sshd -T` 为准。

1. 保留一个已登录的终端不关（救命会话）。
2. 把要写入的三行给用户看，确认后执行：

```bash
sudo tee /etc/ssh/sshd_config.d/00-hardening.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sudo sshd -t && sudo sshd -T | grep -Ei '^(passwordauthentication|kbdinteractiveauthentication|permitrootlogin) '
sudo systemctl reload ssh      # RHEL 系：sudo systemctl reload sshd
```

3. 新开终端验证：密钥能登录；`ssh -o PubkeyAuthentication=no deploy@[公网IP]` 应被拒。
4. 回退：救命会话里 `sudo mv /etc/ssh/sshd_config.d/00-hardening.conf /root/ && sudo systemctl reload ssh`；救命会话也断了，用控制台的 VNC 类登录（不走 SSH，入口名称以控制台为准）进去做同样的事；再不行就重置密码或绑定密钥，最后才回滚第 0 步快照（快照之后的数据会丢）。

没有 Include 行的老系统、`sshd -t` 报 Bad configuration option、改 SSH 端口、限定登录账号，见 [references/ssh-hardening.md](references/ssh-hardening.md)。

### 第 4 步：防火墙最小放行

- 轻量应用服务器的防火墙在控制台、实例之外（云服务器 CVM 里对应的是安全组；名称与入口以腾讯云控制台为准）：只留 SSH 端口、80、443；数据库、Redis、管理面板不对外。有固定出口 IP 时把 SSH 来源限定为它。
- 系统内防火墙可选；开 ufw 前必须先放行 SSH：`sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable`。
- Docker 的 `-p 6379:6379` 会绕过 ufw 直接对外：数据库类容器写 `-p 127.0.0.1:6379:6379` 或不映射，外层靠控制台防火墙兜底。

### 第 5–6 步：Docker → Nginx 反代 → HTTPS

顺序：应用只听 `127.0.0.1:端口` → Nginx 监听 80 反代过去 → 域名解析到公网 IP（备案按要求）→ 申请证书开 443 → 80 跳 443。HTTPS 两条通用路：ACME 客户端（如 certbot）自动申请与续期；或在云厂商的 SSL 证书服务申请后下载部署（免费证书的有效期与数量以官方为准）。Docker 端口写法、Nginx 反代配置、certbot 命令、502/413 排查见 [references/deploy-stack.md](references/deploy-stack.md)。

### 第 7 步：快照、备份与日常巡检

改 SSH、防火墙或升级大版本前先打快照；快照和实例同账号同地域，不能代替机外备份，数据库另做导出存到机器外并演练恢复。快照数量与费用、套餐流量与超出后的规则以官方为准。每周 5 分钟巡检表、安全清理磁盘、流量查看见 [references/backup-monitoring.md](references/backup-monitoring.md)。

## 体检脚本（只读）

`scripts/server_checkup.py` 读 sshd 配置（跟随 Include，按「先读到的生效」）、监听端口（`ss`/`netstat` 的输出，可存成文件再喂）和磁盘占用，输出按 高/中/低/提示 排序的风险清单，并列出脚本看不到、需人工核对的项（控制台防火墙、快照、流量、备案）。不改任何配置，相同输入输出相同。

```bash
# 服务器上直接跑（sudo 才看得到进程名和完整 sshd 配置）
sudo python3 scripts/server_checkup.py
# 或把输出存成文件，在任何电脑上跑
sudo sshd -T > sshd_effective.txt; ss -tulnp > ports.txt; df -hP > df.txt
python3 scripts/server_checkup.py --sshd-effective sshd_effective.txt --ports-file ports.txt --df-file df.txt --format md --out report.md
```

样例输入与真实输出见 [examples/checkup-report.md](examples/checkup-report.md)。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（模板） |
|---|---|---|
| 缺关键信息 | 只问 3 个：镜像与版本、要跑什么服务、域名与备案进度；其余按「Ubuntu + 单站点 + 不用 Docker」默认，交付物里标 [待确认] | 「先告诉我三件事：镜像版本、要跑什么、备案到哪一步；其余按默认写，标 [待确认] 的你核对。」 |
| 贴的输出和描述矛盾（说关了密码登录，`sshd -T` 却是 yes） | 指出矛盾，给两种可能：被 `sshd_config.d/` 里的文件抢先设置 / 改完没重载；给核对命令 | 「你说已关密码登录，但 sshd -T 仍是 yes：要么 sshd_config.d 里有文件抢先生效，要么没重载。先跑 `sudo grep -rn PasswordAuthentication /etc/ssh/`。」 |
| 已经被锁在外面 | 按回退顺序：救命会话 → 控制台 VNC 类登录 → 重置密码或绑定密钥 → 回滚快照 | 「先别重装：用控制台的 VNC 类登录进去，把 00-hardening.conf 挪走再重载 sshd。」 |
| 疑似被入侵，超出本技能 | 止血三步：控制台防火墙收紧到只放自己的 IP；打快照留证；更换密钥和所有密码。然后转腾讯云工单或安全专业人员 | 「这超出配置范畴了。先做止血三步，再提工单或找安全人员，别急着删可疑文件。」 |
| 时间紧，只要最小可用版 | 降级为 4 件事：系统更新、密钥登录并关密码（含回退）、控制台防火墙只留 SSH/80/443、打一份快照 | 「今天只做四件：更新、密钥加关密码、防火墙三端口、快照；Docker 和 HTTPS 下一轮再做。」 |
| 坚持越界（数据库或面板对全网开放、搭违规服务） | 不给对全网开放的配置，给替代：SSH 隧道或只放行来源 IP；违规服务直接拒绝 | 「数据库对全网开放的配置我不写；用 SSH 隧道或只放行你的 IP，效果一样还安全。」 |
| 用户要贴密码、私钥、SecretKey | 立即劝阻；已贴出的建议轮换 | 「别贴密钥和密码，我用不到；已经贴了的请尽快更换。」 |

脚本退出码：

| 退出码 / 现象 | 原因 | 修正办法 |
|---|---|---|
| 0 | 体检完成 | — |
| 1 | 参数错误（选项拼错、`--format` 不是 text/md/json、磁盘阈值颠倒） | 按提示改，`-h` 看全部选项 |
| 2 | 指定的文件不存在、无权限、是目录，或报告写不进去 | 检查路径；sshd 配置需 sudo，或先另存成文件再传入 |
| 3 | 用了 `--strict` 且有「高」 | 按清单处理后重跑 |
| 130 | 按了 Ctrl-C | 重跑即可 |
| 报告说「没有识别到监听中的端口」 | 输出被截断，或不是 ss/netstat 的原样输出 | 重新 `ss -tulnp > ports.txt`，不要手工删列 |

## 输出契约

交付物按固定顺序：
1. **现状摘要**：镜像与版本、登录方式、要跑的服务与端口、域名与备案进度；公网 IP 用 [公网IP] 占位。
2. **分步清单**：按上面 0–7 步，每步写「做 → 验证 → 回退」；会改配置的步骤先给预览，等用户确认。
3. **体检结果**：脚本输出原文，或写「未提供」。
4. **控制台待办**：防火墙、快照、告警、流量，每条标「以腾讯云控制台为准」。
5. **每周巡检**：要看的项与正常标准。

占位符：用户需要提供的值写 [待补]（域名、用户名、IP）；推测的内容写 [待确认]（镜像默认用户、是否 socket 激活）。

交付前自检（逐条是/否）：
- [ ] 改登录方式、防火墙的每一步都有「验证」和「回退」？
- [ ] 关密码登录前要求了新会话密钥登录验证通过，并保留救命会话？
- [ ] 对外端口除 SSH、80、443 外，每个都写了理由？
- [ ] 控制台操作、配额、价格、备案的句子都标了以官方或控制台为准？
- [ ] 命令里没有真实 IP、密码、密钥，全部是占位符？

## 示例

**用户（示例）**：刚买了轻量服务器，Ubuntu 22.04，想跑一个 Node 写的小网站，域名 example.com 还在备案。

**助手先问**：现在用哪个用户、怎么登录？Node 直接跑还是用 Docker？

**用户**：本地 ssh 登录 ubuntu 用户，直接跑，端口 3000。

**交付物（节选，完整版见 [examples/first-day-setup.md](examples/first-day-setup.md)）**：

```
【现状】Ubuntu 22.04｜ubuntu 用户 + 密码登录｜Node 监听 3000｜example.com 备案中｜公网 IP [待补]
第 0 步 控制台打快照 init（入口以控制台为准）
第 1 步 sudo apt update && sudo apt upgrade -y；有 /var/run/reboot-required 就重启
第 2 步 本机 ssh-keygen -t ed25519 → ssh-copy-id ubuntu@[公网IP] → 新终端验证免密登录
第 3 步 预览 00-hardening.conf 三行 → 你确认后写入 → sshd -t、sshd -T 核对 → reload
        验证：新终端密钥可登、密码方式被拒｜回退：把该文件挪到 /root/ 后 reload
第 4 步 控制台防火墙只留 22、80、443（以控制台为准）
第 5 步 Node 改听 127.0.0.1:3000，ss -tlnp 核对
第 6 步 Nginx 反代 3000；备案完成后解析域名 → certbot --nginx → renew --dry-run
巡检   每周跑 server_checkup.py，看控制台流量用量与快照
```

## 常见问题（FAQ）

- **改了 SSH 端口就安全了吗？** 只能减少扫描噪音。真正的防线是密钥登录、关密码、防火墙只放行必需端口。
- **控制台防火墙和 ufw 都要开吗？** 控制台防火墙必开，它在机器外层；ufw 可选，开了就两边都要放行，并注意 Docker 映射的端口会绕过 ufw。
- **关了密码登录，换电脑怎么办？** 新电脑生成新密钥，用旧电脑或控制台网页登录把新公钥追加到 `~/.ssh/authorized_keys`；不要在设备之间拷私钥。
- **快照能代替备份吗？** 不能。快照和实例同账号同地域，误删、被勒索都可能一起受影响；数据库要另做导出存到机器外，并定期演练恢复。
- **能直接帮我在服务器上执行吗？** 不代为登录。我给命令、验证和回退，你执行后把输出贴回来；改配置的步骤先给预览，你确认再做。
- **体检脚本会改配置吗？** 不会。它只读文件和 `ss`、`df` 的输出，结果打印到屏幕或写到你指定的报告文件。
- **没备案能先部署吗？** 以官方要求为准。部署和自测可以先做，域名对外提供服务的时间按备案进度倒排。

## 常见错误（反模式）

- 改完 sshd 立刻断开会话 → 密钥没配好就把自己锁在外面 → 保留救命会话，新会话验证通过后再退出。
- 只改主配置 `sshd_config`，不看 `sshd_config.d/` → drop-in 先读先生效，改了等于没改 → 用 `00-` 开头的 drop-in，并用 `sshd -T` 核对。
- 控制台防火墙图省事放行全部端口 → 数据库、Redis、面板被全网扫描 → 只放 SSH、80、443，其余走 SSH 隧道。
- 数据库容器写 `-p 3306:3306` → 绕过 ufw 直接对外 → 绑 127.0.0.1 或不映射。
- 应用直接监听 0.0.0.0:8080 对外 → 没有 HTTPS、没有统一入口 → 应用只听本机，Nginx 反代并上证书。
- 只打快照、从不演练恢复 → 出事才发现备份不可用 → 数据库导出放机器外，每月恢复一次。
- 申请完证书不管续期 → 到期网站打不开 → `certbot renew --dry-run` 演练，巡检表里看剩余天数。
- 把密码、私钥、SecretKey 写进仓库或贴进聊天 → 泄露后收不回来 → 放环境变量或权限 600 的文件，已泄露的立即轮换。

## 边界与不做什么

- 不代为登录服务器或控制台，不索要、不保存密码与私钥；所有命令由用户执行，写操作先预览后确认。
- 控制台按钮位置、套餐价格、流量与快照的配额和计费、备案细则不下具体结论，以腾讯云控制台与官方文档为准；官方文档去腾讯云文档中心的「轻量应用服务器」（登录、防火墙、快照、密钥、流量相关章节）以及「网站备案」「SSL 证书」查。
- 不做入侵取证和渗透测试；疑似被入侵只给止血步骤并转专业人员。
- 不协助搭建违反法律法规或平台服务条款的服务，不提供规避备案等监管要求的办法。
- 体检脚本的结论是风险信号，不等于安全认证；它看不到控制台防火墙规则。
