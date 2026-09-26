# 部署顺序：Docker → 应用只听本机 → Nginx 反代 → 域名 → HTTPS

原则：**对外只开 80/443，由 Nginx 统一接入；应用、数据库一律只听 127.0.0.1。** 每一步做完先验证再往下走。

## 1. Docker（需要容器时）

- 安装：按 Docker 官方文档中你的发行版对应的安装章节操作；也可以在控制台选带 Docker 的应用镜像（有哪些镜像以控制台列表为准）。
- 验证：`sudo docker run --rm hello-world`。
- 免 sudo：`sudo usermod -aG docker deploy`，重新登录生效。注意 docker 组约等于 root 权限，只加自己的运维账号。
- 拉镜像慢：腾讯云文档里有镜像加速相关章节（在容器镜像服务或云服务器文档中），地址与适用范围以官方为准。

端口映射只有三种写法：

| 用途 | 写法 | 说明 |
|---|---|---|
| 要被 Nginx 反代的应用 | `-p 127.0.0.1:3000:3000` | 只有本机能访问 |
| 数据库、缓存 | 不写 ports，或 `-p 127.0.0.1:5432:5432` | 同一 compose 网络里的容器直接用服务名访问 |
| 禁止 | `-p 6379:6379` | Docker 写的转发规则不经过 ufw，等于对全网开放 |

compose 片段（密码放 `.env`，`.env` 不提交进仓库）：

```yaml
services:
  app:
    image: [你的镜像]
    restart: unless-stopped
    env_file: .env
    ports:
      - "127.0.0.1:3000:3000"
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
  db:
    image: postgres:16
    restart: unless-stopped
    env_file: .env
    volumes:
      - dbdata:/var/lib/postgresql/data
volumes:
  dbdata:
```

不用 Docker 时同理：让应用监听 `127.0.0.1:3000`（多数框架有 host/bind 参数），并用 systemd 或进程管理工具保证开机自启、崩溃重启。

## 2. Nginx 反代

```bash
sudo apt install -y nginx        # RHEL 系：sudo dnf install -y nginx
```

站点配置：Ubuntu/Debian 放 `/etc/nginx/sites-available/example.com` 再软链到 `sites-enabled/`；RHEL 系放 `/etc/nginx/conf.d/example.com.conf`。

```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    client_max_body_size 20m;          # 上传报 413 时调这里

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/example.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
curl -I http://127.0.0.1:3000      # 应用本身通不通
curl -I -H 'Host: example.com' http://127.0.0.1   # 经 Nginx 通不通
```

需要 WebSocket 时再加 `Upgrade` / `Connection` 两个头，写法见 Nginx 官方文档的 WebSocket proxying 一节。

常见报错：

| 现象 | 常见原因 | 查法 |
|---|---|---|
| 502 Bad Gateway | 应用没起来，或端口、地址对不上 | `ss -tlnp \| grep 3000`；`sudo tail -n 50 /var/log/nginx/error.log` |
| 502 且日志有 Permission denied | SELinux 不让 Nginx 连本地端口（RHEL 系 enforcing 时） | `sudo setsebool -P httpd_can_network_connect 1` |
| 413 Request Entity Too Large | 上传超过 `client_max_body_size` | 调大该值后 `nginx -t` 再 reload |
| 单页应用刷新 404 | 静态托管没回退到 index.html | `location / { try_files $uri /index.html; }` |
| 改了配置不生效 | 没 reload，或改的文件没被 include | `sudo nginx -T \| grep server_name` 看实际加载了什么 |

## 3. 域名与备案

- 在你的 DNS 服务商处把域名的 A 记录指向公网 IP（DNS 解析产品的操作以其控制台为准）；验证：`dig +short example.com`，或转 `dns-check` 技能。
- 国内地域对外提供网站服务通常需要备案，以官方要求为准；流程与材料见腾讯云文档中心「网站备案」相关章节。

## 4. HTTPS

前提：域名已解析到本机；控制台防火墙放行 80 和 443（ACME 的 HTTP 验证要用 80）。

**路一：ACME 客户端（以 certbot 为例）**。certbot 官方推荐的安装方式见其文档；Ubuntu/Debian 也可以用系统软件源：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com --redirect   # --redirect 顺带加 80→443 跳转
sudo certbot renew --dry-run      # 演练续期；装包时一般已带定时续期任务
```

**路二：云厂商 SSL 证书服务**：在控制台申请证书，下载 Nginx 格式文件放到 `/etc/nginx/ssl/`（权限 600），在 server 块里写 `listen 443 ssl;`、`ssl_certificate`、`ssl_certificate_key`。免费证书的有效期与数量以官方为准；到期前要手动更换，在日历里设提醒。

验证与巡检：

```bash
curl -I https://example.com
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -enddate
```

证书链、协议版本的深入检查可转 `tls-cert-check` 技能。
