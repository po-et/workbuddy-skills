---
name: dns-check
description: 域名解析巡检、DNS 切换验证、换了解析记录多久生效、多个 DNS 服务器结果对比、查 A / AAAA / CNAME / MX / TXT / NS 记录、看 TTL、CNAME 链太长、SPF 与 DMARC 有没有配、域名解析到哪个 IP、解析不一致排查。当用户说「帮我查一下这个域名解析到哪」「改了 DNS 生效了吗」「为什么有的地方能访问有的不行」「对比一下 8.8.8.8 和 223.5.5.5 的结果」「这个域名的 MX 和 SPF 配了吗」「解析超时怎么排查」时使用。附纯标准库脚本 scripts/dns_check.py：自己构造 DNS 报文走 UDP 查询（处理压缩指针、TC 截断自动转 TCP），支持多解析器并列对比、显示 TTL、串出 CNAME 链、用 --expect 校验 A 记录、检查 MX/SPF/DMARC 存在性、超时重试与 --json；解析失败或与 --expect 不一致退出码 1。
author: Captain
version: 0.1.0
display_name: "域名解析巡检"
display_name_en: "DNS Check"
description_zh: "不依赖 dig / nslookup，自己拼 DNS 报文查 A/AAAA/CNAME/MX/TXT/NS，并把多个解析器的结果并排对比，用来验证改完解析后各地是否生效；带 TTL、CNAME 链、SPF/DMARC 体检与 --expect 断言。纯 Python 标准库。"
description_en: "Query A/AAAA/CNAME/MX/TXT/NS by speaking DNS on the wire - no dig or nslookup needed - and compare answers from several resolvers side by side to confirm a record change has propagated; includes TTL, CNAME chain, SPF/DMARC review and an --expect assertion. Pure Python stdlib."
examples_zh:
  - "这个域名解析到哪个 IP，TTL 还剩多少"
  - "我改完解析记录了，对比一下 8.8.8.8 和 223.5.5.5 生效了吗"
  - "查一下这个域名的 MX 和 SPF、DMARC 配了吗"
examples_en:
  - "Which IP does this domain resolve to, and what is the TTL?"
  - "I changed the record — compare two resolvers to see if it propagated"
  - "Check whether example.com has MX, SPF and DMARC records"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"] , "emoji": "🌐" } }
---

# 域名解析巡检

自己拼 DNS 报文发 UDP 查询，不依赖 dig / nslookup（容器里常常没有）。主力场景是**切换验证**：改完解析记录后，同时问多个解析器，看各家是不是都换过来了。

## 何时用

- 改了 A 记录 / 换了 CDN / 切了机房，需要确认解析是否已经生效、还要等多久（看 TTL）。
- 有人反馈"我这边打不开，同事那边正常"，怀疑是不同解析器拿到的结果不一样。
- 上线前巡检域名：A 记录对不对、CNAME 链有几跳、NS 是不是预期的那家。
- 邮件发不出去或进垃圾箱，要看 MX、SPF、DMARC 是否配齐。
- 容器 / 跳板机里没有 dig、nslookup、host，只有 python3。

## 用法

```bash
python3 scripts/dns_check.py www.example.com                                  # 用本机解析器查 A
python3 scripts/dns_check.py example.com --type A,AAAA,CNAME,MX,TXT,NS         # 多类型
python3 scripts/dns_check.py www.example.com --server 8.8.8.8 --server 223.5.5.5   # 多解析器对比
python3 scripts/dns_check.py www.example.com --expect 203.0.113.10 --fail-on-diff  # 切换验证断言
python3 scripts/dns_check.py example.com --type MX,TXT                         # 顺带体检 SPF / DMARC
python3 scripts/dns_check.py www.example.com --tcp --timeout 5 --retry 3        # 走 TCP、加超时重试
python3 scripts/dns_check.py www.example.com --server 127.0.0.1#5353 --json     # 指定端口、机器可读
```

支持类型：A、AAAA、CNAME、MX、TXT、NS、SOA、PTR、CAA，或 `--type all`。解析器可写 `IP` 或 `IP#端口`（dig 语法）；不指定时读 `/etc/resolv.conf`，读不到则退到公共解析器。

## 流程

1. **先问一个解析器拿事实**：看记录值与 TTL。TTL 小意味着改动很快能扩散，TTL 大（如 3600 以上）说明要等一个周期。
2. **再并列多个解析器做切换验证**：至少挑两家不同厂商的公共解析器，加自己机器的解析器。全部一致 = 基本扩散完成；不一致 = 要么还在 TTL 窗口里，要么是 CDN / GeoDNS 按来源返回不同 IP（这属正常）。
3. **断言**：切换预期明确时用 `--expect` 把目标 IP 写进命令，不一致直接退出码 1，可以塞进发布流水线当验证步骤；要求各解析器完全一致时再加 `--fail-on-diff`。
4. **看 CNAME 链**：脚本会把 CNAME 串成一条链并数跳数。超过两跳就该压平，每一跳都是一次额外解析往返。
5. **排查解析失败**：`NXDOMAIN` 是域名不存在（拼错或记录被删）；`SERVFAIL` 多为权威服务器或 DNSSEC 出问题；超时先换一个解析器试，能区分是网络不通还是这家解析器有问题。
6. **改解析前的标准动作**：提前 24 小时把 TTL 调到 60–300 秒，切换后用本脚本确认各解析器都更新了，再把 TTL 调回去。

## 输出与退出码

- 文本模式：按解析器分组列出每种记录的 rcode、耗时、走的是 UDP 还是 TCP、每条记录的值与 TTL；随后是解析器一致性、期望值校验、邮件相关（MX / SPF / DMARC）、最小 TTL 与结论。
- `--json` 输出 `ok` / `results`（逐解析器逐类型，含 `records`、`ms`、`attempts`、`rcode_text`、`truncated`）/ `consistency` / `expect` / `mail` / `cname_chain` / `failures`，适合入库做解析漂移监控。
- 退出码：0 全部正常；1 解析失败（超时、NXDOMAIN、SERVFAIL）、与 `--expect` 不一致，或加了 `--fail-on-empty`（NODATA 也算失败）、`--fail-on-diff`（解析器结果不一致也算失败）时命中条件。

## 实现说明与边界

- 自己构造报文：12 字节头（ID / 标志 / 各段计数）+ 问题段，标志位置 `0x0100` 请求递归；解析响应时处理 `0xC0` 压缩指针（带成环保护）。响应带 TC 截断位时自动改走 TCP 重查。
- 只做递归查询，不自己从根域逐级迭代，所以看到的是**解析器缓存里的结果**，不是权威服务器的当前值；要看权威值请用 `--type NS` 找到权威服务器后直接 `--server` 指向它。
- 不校验 DNSSEC、不支持 DoH / DoT、不查 EDNS Client Subnet；因此看不出"某个省份解析到哪"，跨地域验证请在目标地域的机器上跑，或换用当地解析器。
- 认不出的记录类型会按十六进制原样输出，不臆造解析结果；同理，畸形 rdata 也退化成十六进制而不是猜。
- 公共解析器有频率限制，不要拿它做秒级轮询；巡检建议分钟级，并优先用自己的解析器。
- 不做反向解析批量扫描，也不要拿它去枚举别人的子域名。文档与示例一律只用 example.com 等保留域名。
