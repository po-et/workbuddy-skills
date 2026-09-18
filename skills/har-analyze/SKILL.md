---
name: har-analyze
description: HAR 文件分析、前端页面加载慢排查、首屏性能分析、DevTools 网络面板导出的 har 怎么看、找出最慢与最大的请求、瀑布流阶段分解（排队/DNS/握手/等待/下载）、静态资源缓存与压缩体检、第三方脚本拖慢页面、重复请求与重定向链排查。当用户说「这个页面打开太慢帮我看看 HAR」「har 文件分析一下」「哪个接口最慢」「首屏为什么 5 秒」「静态资源有没有开 gzip 和缓存」「第三方脚本是不是拖慢了」时使用。附纯标准库脚本 scripts/har_analyze.py，输出总览与 onLoad、耗时与体积 Top N、按域名与资源类型聚合、9 类问题清单，支持 --slow-ms、--top、--json、--strict。
author: Captain
version: 0.1.0
display_name: "HAR 性能分析"
display_name_en: "HAR Analyze"
description_zh: "一条命令读懂 DevTools 导出的 HAR：总请求数与体积、onLoad 与 DOMContentLoaded、耗时与体积 Top N（含 blocked/DNS/握手/wait/receive 分解）、按域名与类型聚合，再给 9 类问题清单与改法。纯 Python 标准库。"
description_en: "One command to read a DevTools HAR: request count and bytes, onLoad and DOMContentLoaded, slowest and largest Top N with full timing breakdown, aggregation by domain and resource type, plus nine classes of findings with fixes. Pure Python stdlib."
examples_zh:
  - "这个页面打开太慢帮我看看 HAR，到底慢在哪一段"
  - "HAR 里哪个接口最慢，慢在等待还是下载"
  - "分析这份 HAR，静态资源的压缩和缓存头有没有问题"
examples_en:
  - "This page takes 5 seconds, analyze the HAR I exported"
  - "Which request in the HAR is slowest, and is it wait or download?"
  - "Check compression and cache headers for the static assets in this HAR"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📉" } }
---

# HAR 性能分析

把浏览器 DevTools 导出的 HAR 变成一份可执行的优化清单。适用于页面打开慢、接口偶发超时、上线后体积暴涨这类「说不清慢在哪」的问题。

导出方式：Chrome / Edge 打开 DevTools → Network → 勾选 Preserve log → 刷新页面 → 右键任一请求 → **Save all as HAR with content**（不含响应体也能分析）；Firefox 在网络面板右键「全部保存为 HAR」。

## 用法

```bash
python3 scripts/har_analyze.py capture.har                       # 默认慢请求阈值 500ms、各榜单 10 条
python3 scripts/har_analyze.py capture.har --slow-ms 300 --top 15
python3 scripts/har_analyze.py capture.har --img-kb 100 --blocked-ms 50 --third-party-max 10
python3 scripts/har_analyze.py capture.har --json                # 机器可读，便于入库对比
python3 scripts/har_analyze.py capture.har --strict              # 有 high 级问题（4xx/5xx）则退出码 1
cat capture.har | python3 scripts/har_analyze.py -               # 从标准输入读
```

## 流程

1. **先看第一段总览**：请求数、传输体积（含解压后体积）、耗时累计与墙上时间；有 pages 字段时还会给 DOMContentLoaded 与 onLoad。onLoad 远大于最慢请求，说明瓶颈在渲染/脚本执行而不在网络。
2. **看耗时 Top N 的阶段分解**：`wait` 大 → 服务端处理慢，去查那个接口的服务端耗时；`receive` 大 → 响应体太大或带宽不足；`blocked` 大 → 同域连接数排队；`dns`/`connect`/`ssl` 大 → 新域名握手没复用。
3. **看体积 Top N**：传输列与解压后列差距小又是文本类，就是没开压缩；单个资源超过几百 KB 的先拆包或懒加载。
4. **看域名与类型聚合**：判断体积集中在首方还是第三方、集中在脚本还是图片，优化投入按这里排序。
5. **按问题清单逐条修**：先清 high（4xx/5xx），再处理 warn（重复请求、未压缩、缺缓存头、大图、慢请求），info 作为参考。
6. **改完复测**：重新导出 HAR 再跑一次，用 `--json` 存两份做前后对比；接进 CI 用 `--strict` 拦住带 5xx 的录制。

## 输出一览

| 部分 | 内容 |
|---|---|
| 总览 | 请求数、传输/解压后体积、耗时累计、墙上时间、首方域名、DOMContentLoaded / onLoad、命中缓存数 |
| 耗时 Top N | 总耗时 + blocked / dns / connect / ssl / send / wait / receive 七段分解 + 状态码 |
| 体积 Top N | 传输体积、解压后体积、资源类型、content-encoding |
| 按域名 | 请求数、传输体积、耗时合计，标出首方域名 |
| 按资源类型 | 文档 / 脚本 / 样式 / 图片 / 字体 / XHR / 媒体 / 其他 的请求数与体积 |
| 问题清单 | 9 类，按 high / warn / info 排序，每类都带「→ 改法」 |

问题清单的 9 类：

| 编号 | 级别 | 检查点 |
|---|---|---|
| H1 | high | 4xx / 5xx 响应 |
| H2 | warn | 同一 URL 重复请求（组件重复挂载、没做去重） |
| H3 | warn/info | 重定向链（HTTP→HTTPS、斜杠、www），附链路与耗时 |
| H4 | warn | 文本资源未压缩（超过 `--min-compress` 且无 content-encoding），附预计可省体积 |
| H5 | warn | 静态资源缺 cache-control 与 expires，并标出连 ETag 都没有的 |
| H6 | warn/info | 第三方请求数超过 `--third-party-max`，按域名列出请求数与体积 |
| H7 | warn | 图片超过 `--img-kb`（默认 200KB） |
| H8 | warn/info | `blocked` 超过 `--blocked-ms`（默认 100ms），提示连接数限制 |
| H9 | warn | 请求耗时超过 `--slow-ms`（默认 500ms），附 wait 占比 |

## 边界与常见问题

- 只读 HAR，**不做**主动探测、不发请求、不下载资源；HAR 是一次录制的快照，单次结果不能当性能基线，要对比就多录几次。
- 资源类型优先用 Chrome 的 `_resourceType` 字段，Firefox/Safari 的 HAR 缺这个字段时按 MIME 归类，`text/plain` 会被归到 XHR。
- 传输体积优先取 Chrome 的 `_transferSize`；其他工具导出时退化为 `bodySize + headersSize`，与真实上行字节可能有出入。
- `_transferSize` 为 0 且状态 200 的请求按「命中缓存」统计；强缓存命中的请求在很多录制里根本不出现，别用 HAR 算缓存命中率。
- 重定向链靠响应头 Location 在本次录制里回查，跨域或未被录到的跳转只显示一跳。
- HAR 里可能含 Cookie、Authorization 头和响应体明文，**不要**把原始 HAR 提交进仓库或贴到外部工具；本脚本只在本地读取，输出不打印请求头值。
- 时间单位统一毫秒；`timings` 里的 `-1` 表示该阶段不适用，按 0 处理。
