---
name: http-bench-lite
description: 轻量 HTTP 压测、自测接口性能、看 QPS 与 p99、ab / wrk 的精简替代、本地服务扛不扛得住、接口延迟分位统计、发压后看成功率与状态码分布、并发下的长尾排查。当用户说「帮我压一下这个接口」「本地服务能跑多少 QPS」「p95 p99 延迟是多少」「并发 10 跑 200 个请求看看」「没装 ab / wrk 有没有替代」「压测一下我刚写的这个服务」时使用。附纯标准库脚本 scripts/http_bench.py：线程池 + urllib 发压，-c 并发（默认 10、上限 50）、-n 总请求数或 -d 时长（上限 120 秒）、--method/--header/--body/--timeout，输出成功率、状态码分布、QPS、min/avg/p50/p90/p95/p99/max 延迟与传输字节；开跑前回显目标与参数，非本地目标必须显式 --yes；支持 --json，成功率不达标退出码 1。仅用于自有服务与测试环境。
author: Captain
version: 0.1.0
display_name: "轻量 HTTP 压测"
display_name_en: "HTTP Bench Lite"
description_zh: "没装 ab / wrk 也能压：一条命令对自己的服务发压，给出成功率、状态码分布、QPS 与 p50/p90/p95/p99 延迟分位；并发与时长都有硬上限，非本地目标必须显式确认。纯 Python 标准库。"
description_en: "A stand-in for ab or wrk when neither is installed - one command loads your own service and reports success rate, status distribution, QPS and p50/p90/p95/p99 latency; concurrency and duration are hard-capped and non-local targets require explicit confirmation. Pure Python stdlib."
examples_zh:
  - "压一下本地这个接口，并发 10 跑 200 个请求"
  - "我这个服务的 p95 p99 延迟是多少，QPS 能到多少"
  - "持续压 30 秒看看成功率和状态码分布"
examples_en:
  - "Load my local endpoint with 10 concurrent workers and 200 requests"
  - "What are the p95 and p99 latencies of this service?"
  - "Run a 30-second load test and show the status code distribution"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "📈" } }
---

# 轻量 HTTP 压测

机器上没有 ab / wrk / hey，又想知道自己刚写的接口能跑多快、长尾有多长时用它。目标定位是**自测**：并发上限 50、时长上限 120 秒，够回答"改完之后是快了还是慢了"，不够也不该拿来做大流量压测。

## 何时用

- 本地或测试环境刚起了服务，想拿一组基线数字（QPS、p95、p99）。
- 改了一处实现（加缓存、换序列化、调连接池），需要前后各压一次对比。
- 联调时接口偶发超时，想看并发上来之后成功率与状态码分布怎么变。
- 写 CI 冒烟：跑一小轮，成功率低于阈值就让流水线失败。

## 用法

```bash
python3 scripts/http_bench.py http://127.0.0.1:8000/ -n 200 -c 10         # 200 个请求，并发 10
python3 scripts/http_bench.py http://localhost:8080/health -d 30 -c 20     # 持续 30 秒
python3 scripts/http_bench.py http://127.0.0.1:8000/api -n 500 -c 20 \
    --method POST --body '{"id":1}' --header "Content-Type: application/json"
python3 scripts/http_bench.py https://staging.example.com/health -n 300 -c 10 --yes --json > bench.json
python3 scripts/http_bench.py http://127.0.0.1:8000/ -n 200 --min-success 99.9  # CI 卡成功率
```

常用参数：`--timeout` 单请求超时（默认 10s）、`--body-file` 从文件读请求体、`--insecure` 跳过自签证书校验、`--min-success` 成功率阈值（默认 99）。

## 流程

1. **先确认目标是自己的**：脚本会解析主机名，回环 / 私网 / `localhost` 直接放行；公网目标会拒绝执行，必须加 `--yes` 明示"这是我有权压测的服务"。
2. **开跑前回显**：目标、方法、并发、请求数或时长、超时、是否跳过证书校验都会先打印一遍，确认无误再看结果，避免压错环境。
3. **先看成功率，再看性能**：成功率不是 100% 时，性能数字没有意义——先看状态码分布（5xx 是服务端崩了，4xx 多半是参数或鉴权）与错误类型（`TimeoutError` 超时、`ConnectionRefusedError` 端口没开、`gaierror` 域名解析不了）。
4. **看分位不要看平均**：avg 会被少数极慢请求拖走。p50 代表典型体验，p99 代表最差那批用户；脚本发现 p99 超过 p50 五倍会提示长尾，通常指向 GC、连接池打满、慢依赖或冷启动。
5. **对比要同条件**：并发、请求数、机器、是否开日志都要一致，只改一个变量；每次压测前先跑几十个请求预热，避免把冷启动算进基线。

## 输出与退出码

- 文本模式：请求数 / 成功数 / 成功率 / 耗时、QPS（总量与仅成功）、传输字节与带宽、状态码分布、错误类型分布、延迟 min/avg/p50/p90/p95/p99/max。
- `--json` 输出同样的字段（`success_rate`、`qps`、`ok_qps`、`status_dist`、`errors`、`latency_ms`、`bytes`、`target_is_local`），便于入库做趋势对比。
- 退出码：0 成功率达标；1 成功率低于 `--min-success` 或一个请求都没发出去；2 参数错误或被安全闸门拦下。

## 边界与红线

- **只压自己的服务与测试环境。** 未经授权对他人服务施压属于攻击行为，后果自负；脚本的非本地确认闸门与并发/时长上限就是为了防止误用，不要去改常量绕开它。
- 生产环境压测必须走正式流程（提前报备、避开高峰、限流兜底、有人盯监控），不要用这个脚本对线上服务发压。
- 单机单进程发压，客户端本身会成为瓶颈：本机 CPU 打满或 QPS 上不去时，先怀疑压测端而不是被测服务。
- 每次请求都是新连接，不做 keep-alive 复用，测出来的延迟含建连成本，比 wrk 这类带连接复用的工具偏高；横向对比请用同一工具。
- 不支持 HTTP/2、不做响应内容校验、不跟随认证流程；需要这些能力时该上专业压测工具。
- 延迟分位用最近秩法计算，样本太少（几十个请求）时 p99 只由一两个样本决定，别当精确值用。
