---
name: nginx-config-check
description: nginx 配置体检、nginx.conf 安全与性能检查、反向代理配置审查、server_tokens 泄露版本号、缺 gzip 压缩、listen 443 没开 http2、ssl_protocols 还允许 TLSv1 与 TLSv1.1、缺 HSTS 与 X-Frame-Options 与 X-Content-Type-Options 安全响应头、proxy_pass 没配 proxy_read_timeout 超时、缺 client_max_body_size 导致 413、server_name 重复被静默覆盖、location 里 root 与 alias 用混、alias 没以斜杠结尾的目录穿越、if is evil、access_log off、worker_processes 写死、upstream 没有 keepalive、autoindex on 列目录。当用户说「帮我看看这份 nginx 配置」「nginx 上线前检查一下」「为什么 502 或 413」「这个反代配置对不对」「nginx 安全加固」时使用。附脚本 scripts/nginx_check.py，纯标准库、自带指令解析器能展开 include 通配，16 条规则分 high/warn/info 并附改法，支持 --json 与 --strict。
author: Captain
version: 0.1.0
display_name: "nginx 配置体检"
display_name_en: "Nginx Config Check"
description_zh: "不装任何依赖就能给 nginx 配置做安全与性能体检：自带指令解析器（含 include 展开、块嵌套、注释与引号处理），按 nginx 的继承语义判断 TLS 协议、安全响应头、代理超时、日志、gzip、http2、server_name 冲突、root 与 alias 误用、if is evil、autoindex 列目录等 16 条规则，分级输出附改法，可作 CI 门禁。"
description_en: "Zero-dependency security and performance audit for nginx configs: a built-in directive parser (include expansion, nested blocks, comments, quotes) plus 16 inheritance-aware rules covering TLS protocols, security headers, proxy timeouts, logging, gzip, HTTP/2, duplicate server_name, root vs alias misuse, if-is-evil and directory listing; graded findings with fixes, CI-gate ready."
examples_zh:
  - "帮我看看这份 nginx 配置有没有安全问题"
  - "nginx 上线前检查一下，TLSv1.1 关了吗、安全响应头全不全"
  - "这个反代配置对不对，为什么上游挂了请求会一直卡住"
examples_en:
  - "Audit this nginx.conf for security issues"
  - "Check TLS protocols and security headers before we go live"
  - "Why does this reverse proxy hang when the upstream is down?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# nginx 配置体检

给 nginx 配置做一次上线前检查。适用于新站点上线、反向代理排障、安全加固与合规自查、接手别人写的 conf.d。脚本自带指令解析器，能展开 `include` 通配、处理块嵌套与引号注释，并按 nginx 的继承语义（http → server → location）判断指令是否真的生效，不需要装 nginx 或任何第三方库。

## 用法

```bash
python3 scripts/nginx_check.py /etc/nginx/nginx.conf
python3 scripts/nginx_check.py conf/nginx.conf --prefix conf     # include 相对路径的解析根
python3 scripts/nginx_check.py sites-enabled/app.conf --no-include
python3 scripts/nginx_check.py nginx.conf --json                 # 结构化输出
python3 scripts/nginx_check.py nginx.conf --strict                # 有 high/warn 退出码 1
```

输出按 high / warn / info 排序，按 server 与 location 归组，每条带规则号、文件行号与具体改法。

## 流程

1. 先跑一遍看 high。**high 必须处理**：`ssl_protocols` 还留着 TLSv1/TLSv1.1、`autoindex on` 列目录、`alias` 没以斜杠结尾（`/x../` 能拼出上级目录）。
2. **warn 上线前处理**：server_tokens 没关、443 没开 HTTP/2、缺 HSTS 与 X-Frame-Options 与 X-Content-Type-Options、proxy_pass 没配连接与读取超时、server_name 在同端口重复、location 里 root 与 location 前缀重复、location 内用 if、access_log off。
3. **info 按团队基线取舍**：gzip、client_max_body_size、worker_processes、upstream keepalive、proxy_set_header 透传、include 目标缺失。
4. 改完先 `nginx -t` 验证语法，再 `nginx -s reload`；本工具只做静态规则检查，不替代 `nginx -t`。
5. 接 CI：对仓库里的配置模板跑 `--strict`，例外在团队基线文档里登记。超时值、HSTS 的 max-age 这类要按业务实际 SLA 取值，别照抄示例。

## 规则一览

| 级别 | 规则 | 检查点 |
|---|---|---|
| high | N004 / N009 / N014 | ssl_protocols 含 TLSv1、TLSv1.1、SSLv2、SSLv3；location 以斜杠结尾而 alias 没有；autoindex on |
| warn | N001 / N003 / N004 / N005 | server_tokens 未关或被 server 覆盖成 on；listen 443 未启用 http2；TLS server 没写 ssl_protocols；缺 HSTS、X-Frame-Options、X-Content-Type-Options |
| warn | N006 / N008 / N009 / N010 / N011 | proxy_pass 缺 proxy_connect_timeout 或 proxy_read_timeout；同端口重复 server_name；location 与 root 尾部重复；location 内 if；access_log off |
| info | N002 / N007 / N012 / N013 / N015 / N016 | 未开 gzip；缺 client_max_body_size；worker_processes 非 auto；upstream 无 keepalive；include 目标缺失；反代未透传 Host 与 X-Forwarded-For |

## 边界

- 只做静态规则检查，不做语法校验、不连服务、不发请求；语法问题请交给 `nginx -t`，证书到期请用 tls-cert-check。
- 不求值变量，`map`、`geo`、`rewrite` 的运行时结果不做推演；`set` 出来的变量当普通字符串看。
- `include` 按「当前文件所在目录 → --prefix → /etc/nginx」的顺序找，找不到只提示不报错；`mime.types`、`fastcgi_params` 这类本机缺失属正常，已默认静音。
- 不判断指令是否存在于你当前的 nginx 版本或模块（例如 `http2 on;` 需要 1.25.1+），也不检查 stream/mail 块。
- 安全响应头只看 `add_header` 是否声明，不做重复声明与 `always` 参数的完整性推演；注意 location 里出现 add_header 会整体覆盖外层，工具已按这个语义判断，但仍建议在最内层集中声明。
