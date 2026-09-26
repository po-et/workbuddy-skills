# 示例：新买的轻量服务器，第一天配成能跑网站的机器

> 对话与交付物均为示例。IP、域名用占位符和 example.com；控制台操作以腾讯云控制台为准。

## 对话

**用户**：刚买了腾讯云轻量服务器，Ubuntu 22.04，想跑一个 Node 写的小网站，域名 example.com 还在备案。第一步该干嘛？

**助手**：先确认两件事，其余我按默认写：
1. 你现在用哪个用户、怎么登录（控制台网页登录还是本地 ssh）？
2. Node 服务直接跑还是用 Docker？监听哪个端口？

**用户**：本地 ssh 登录 ubuntu 用户，用密码。直接跑，端口 3000。

**助手**：好。下面按「先保住登录 → 再关门 → 再上服务 → 最后留后路」给你分步清单。第 3 步会改 SSH 配置，我会先给你看要写的内容，你确认后再执行。

## 交付物

```
【现状】
镜像：Ubuntu 22.04｜登录：ubuntu 用户 + 密码（本地 ssh）｜服务：Node，监听 3000
域名：example.com（备案中）｜公网 IP：[待补]｜是否有 Include 行：[待确认，第 3 步先查]

【分步清单】
第 0 步 快照
  做：控制台给实例打快照，命名 init-空机（入口以控制台为准）
  验证：快照列表里能看到｜回退：无

第 1 步 系统更新
  做：sudo apt update && sudo apt upgrade -y
  验证：[ -f /var/run/reboot-required ] && echo 需要重启 → 有就 sudo reboot
  回退：回滚第 0 步快照（一般用不到）

第 2 步 SSH 密钥
  做（本机）：ssh-keygen -t ed25519 -C "my-laptop"
              ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@[公网IP]
  验证：新开终端 ssh ubuntu@[公网IP] 不再要密码；sudo whoami 输出 root
  回退：密钥装不上时，密码登录仍可用，先别进第 3 步

第 3 步 关密码登录、禁 root 直登
  先查：grep -n '^Include' /etc/ssh/sshd_config
  预览（有 Include 时写入 /etc/ssh/sshd_config.d/00-hardening.conf）：
      PasswordAuthentication no
      KbdInteractiveAuthentication no
      PermitRootLogin no
  你确认后执行：sudo tee ... ；sudo sshd -t；sudo sshd -T | grep -Ei '^(passwordauthentication|kbdinteractiveauthentication|permitrootlogin) '
               sudo systemctl reload ssh
  验证：保持旧终端不关；新终端 ssh ubuntu@[公网IP] 能进；
        ssh -o PubkeyAuthentication=no ubuntu@[公网IP] 被拒（Permission denied (publickey)）
  回退：旧终端里 sudo mv /etc/ssh/sshd_config.d/00-hardening.conf /root/ && sudo systemctl reload ssh；
        旧终端也断了 → 控制台 VNC 类登录进去做同样的事

第 4 步 防火墙
  做：控制台防火墙只保留 22、80、443，其余规则删除（以控制台为准）
  验证：本机 nc -vz [公网IP] 3000 应连不上
  回退：控制台里把规则加回来

第 5 步 应用只听本机
  做：Node 启动参数/代码里把监听地址改成 127.0.0.1:3000；用 systemd 托管，开机自启
  验证：ss -tlnp | grep 3000 显示 127.0.0.1:3000
  回退：改回原监听地址

第 6 步 Nginx 与 HTTPS
  现在：sudo apt install -y nginx；按 references/deploy-stack.md 写反代到 127.0.0.1:3000；sudo nginx -t && sudo systemctl reload nginx
  验证：curl -I -H 'Host: example.com' http://127.0.0.1 返回 200
  备案完成后：域名 A 记录指向 [公网IP] → sudo certbot --nginx -d example.com --redirect → sudo certbot renew --dry-run
  回退：删掉站点软链并 reload nginx

第 7 步 留后路
  做：再打一份快照「配置完成」；数据库（如有）每天导出到机器外
  验证：跑体检脚本没有「高」

【控制台待办】（都以腾讯云控制台为准）
□ 快照两份：init-空机、配置完成
□ 防火墙：22 / 80 / 443
□ 流量用量与告警：每周看一次
□ 备案：国内地域对外提供网站服务通常需要备案，以官方要求为准；按进度安排第 6 步后半段

【每周巡检】
sudo python3 server_checkup.py（无「高」）｜df -hP（< 80%）｜证书剩余天数（> 14 天）｜控制台流量与快照
```

## 为什么这样排

- 快照放第 0 步：后面任何一步翻车都能整机回到起点。
- 密钥放在关密码之前、并要求新终端验证：这是唯一能保证不被锁在外面的顺序。
- 防火墙在装服务之前收紧：服务一启动就处在只开三个端口的环境里，不会有「先裸奔几天」的窗口。
- 证书放在备案和域名解析之后：ACME 验证需要域名已经指向这台机器。
