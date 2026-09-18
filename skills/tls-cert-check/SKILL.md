---
name: tls-cert-check
description: TLS 证书批量巡检、HTTPS 证书到期提醒、SSL 证书还有多久过期、证书剩余天数排序、SAN 是否覆盖域名、通配符证书匹配、自签证书与证书链不完整、颁发者是谁、协议版本 TLSv1.2 与 TLSv1.3、密钥算法 RSA 位数与 ECDSA 曲线、SHA-1 弱签名、握手失败原因排查、多域名多端口一次扫完。当用户说「帮我看看这些域名的证书还有多久到期」「证书快过期了吗」「批量巡检一下 HTTPS 证书」「为什么浏览器说这个证书不安全」「证书到期告警接进 CI」时使用。附脚本 scripts/tls_check.py，纯标准库并发拉取证书，先按系统信任库完整校验、失败再降级抓证书并如实报出原因，内置最小 ASN.1 解析读出到期日、SAN、公钥与签名算法，按剩余天数排序，--warn-days 与 --crit-days 分级，支持 --json 与 --strict。
author: Captain
version: 0.1.0
display_name: "TLS 证书巡检"
display_name_en: "TLS Certificate Check"
description_zh: "不装任何依赖就能批量巡检 HTTPS 证书：并发拉取证书链末端，报告剩余天数与到期日、颁发者、SAN 是否覆盖主机名（含通配符）、协议版本、公钥算法与位数、签名算法、自签或链不完整的具体原因；按剩余天数排序，crit/warn 双阈值，退出码可直接接 CI 与定时巡检。"
description_en: "Zero-dependency bulk TLS certificate inspection: concurrent fetch of the leaf certificate reporting days left and expiry date, issuer, SAN coverage of the hostname (wildcards included), protocol version, key algorithm and size, signature algorithm, and the exact reason a chain is self-signed or incomplete; sorted by days left with crit and warn thresholds and CI-ready exit codes."
examples_zh:
  - "帮我看看这些域名的证书还有多久到期"
  - "批量巡检一下 HTTPS 证书，剩余天数少于 30 天的挑出来"
  - "为什么浏览器说这个证书不安全，是自签还是证书链不完整"
examples_en:
  - "How many days until these certificates expire?"
  - "Bulk-check our HTTPS endpoints and flag anything under 30 days"
  - "Why does the browser say this certificate is not trusted?"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔐" } }
---

# TLS 证书巡检

一条命令扫完一批 HTTPS 站点的证书。适用于证书到期前的例行巡检、上线前确认新证书装对了、排查「浏览器说不安全」、以及把到期告警接进 CI 或定时任务。纯标准库，不需要 openssl 命令，也不需要 curl。

## 用法

```bash
python3 scripts/tls_check.py www.example.com api.example.com:8443
python3 scripts/tls_check.py --file hosts.txt --warn-days 30 --crit-days 7
python3 scripts/tls_check.py --file hosts.txt --json --workers 16 --timeout 5
python3 scripts/tls_check.py --file hosts.txt --strict      # warn 也算失败
```

`hosts.txt` 每行一个 `host[:port]`（默认 443），`#` 开头是注释，行尾也能跟备注。结果按剩余天数升序输出，连不上的排最前；每行给出剩余天数、到期日、颁发者、协议、密钥与签名算法，问题写在 `→` 后面。

## 流程

1. 先跑一遍看 crit。**crit 必须当天处理**：已过期、剩余天数低于 `--crit-days`、SAN 不覆盖该主机名、自签或证书链不完整、连不上或握手失败。
2. **warn 排进本周**：剩余天数低于 `--warn-days`、协议还停在 TLSv1 或 TLSv1.1、RSA 不足 2048 位、SHA-1 弱签名。
3. 链不完整（报 `unable to get local issuer certificate`）多半是只装了叶子证书没装中间证书，重新拼 fullchain 再 reload；自签则确认是不是内部测试域名混进了清单。
4. SAN 不覆盖：看输出里的 SAN 列表，确认签发时漏了域名还是清单里写错了主机名；通配符只匹配一级子域，`*.example.com` 不匹配 `a.b.example.com`，也不匹配 `example.com` 本身。
5. 接自动化：定时任务里跑 `--warn-days 30 --crit-days 7`，退出码非 0 就告警；证书签发后再跑一次确认新证书已经生效（可用 `--json` 把剩余天数喂给监控）。

## 规则一览

| 级别 | 判定 | 说明 |
|---|---|---|
| crit | 已过期 / 剩余 ≤ crit-days / SAN 不覆盖主机名 / 自签或链不完整 / 连接与握手失败 | 退出码 1，需要立刻处理 |
| warn | 剩余 ≤ warn-days / 协议为 TLSv1、TLSv1.1、SSLv3 / RSA < 2048 位 / EC < 256 位 / SHA-1 签名 | 默认不影响退出码，加 `--strict` 后也算失败 |
| 输出字段 | days_left、not_after、issuer、subject、san、tls_version、cipher、key、sig_alg、self_signed、trusted、verify_error | `--json` 里字段名一致，取不到的项留空而不是猜 |

## 边界

- 只看服务端在握手中送出的叶子证书，不做完整链路重建，也不查 CRL 与 OCSP 吊销状态；吊销判断请用 `openssl ocsp` 或 CA 控制台。
- 校验失败时会降级成不校验握手把证书抓回来，这一步只为拿到证书内容做诊断，不代表工具认可该证书；结论以 `trusted` 与 `verify_error` 字段为准。
- 信任判断用的是运行机器的系统信任库，不同机器结论可能不同；容器里跑记得装 ca-certificates。
- 需要 SNI 才能取到正确证书的站点，工具用清单里的主机名作为 SNI；如果目标只认 IP，请在清单里写域名而不是 IP。
- 不做端口扫描、不发 HTTP 请求、不测速；服务可用性用 http-health-check，配置项用 nginx-config-check。
