---
name: prometheus-rule-check
description: Prometheus 告警规则体检、录制规则检查、告警规则评审、alert rules lint、告警缺 for 导致瞬时抖动就误报、for 太短、缺 severity 标签、注解缺 summary 与 description、告警内容没有 labels 与 value 上下文、rate 窗口小于抓取间隔 4 倍、rate 与 increase 用在非 counter 指标、没有聚合导致告警风暴、告警名重复、expr 里硬编码实例或 IP、录制规则命名不合三段式、labels 里写 instance 或 job 覆盖原标签、同组规则过多、这条告警为什么老是误报、录制规则命名规范吗。当用户说「帮我看看这些告警规则有没有问题」「上线前评审一下 rules.yml」「把告警规则检查加进 CI」「为什么这条告警半夜乱叫」时使用。附纯标准库脚本 scripts/promrule_check.py，内置最小 YAML 解析不依赖 PyYAML 与 promtool，20 条规则分 high/warn/info 并附改法，支持目录递归、--scrape-interval、--json 与 --strict。
author: Captain
version: 0.1.1
display_name: "Prometheus 规则体检"
display_name_en: "Prometheus Rule Check"
description_zh: "不装依赖、不连 Prometheus 就能给告警与录制规则做评审：查缺 for、for 过短、缺 severity、注解无上下文、rate 窗口与抓取间隔不匹配、rate 作用在非 counter、缺聚合致告警风暴、告警名重复、硬编码实例、labels 覆盖原标签、录制规则命名与单组规则过多，分级输出附改法，可当 CI 门禁。"
description_en: "Review Prometheus alerting and recording rules with zero dependencies and no server access: missing or too-short `for`, missing severity, context-free annotations, rate windows shorter than 4x the scrape interval, rate() on non-counters, missing aggregation (alert storms), duplicate alert names, hardcoded instances, label overrides, recording-rule naming and oversized groups — graded with fixes, CI-gate ready."
examples_zh:
  - "上线前帮我做一次告警规则体检"
  - "这条告警为什么老是误报，帮我看看 for 和聚合"
  - "录制规则命名规范吗，顺便把检查加进 CI"
examples_en:
  - "Review these alerting rules before we ship"
  - "Why does this alert keep firing? Check `for` and aggregation"
  - "Do the recording rules follow the naming convention? Add it to CI"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔔" } }
---

# Prometheus 规则体检

`promtool check rules` 只管语法能不能加载，管不了「这条告警会不会半夜乱叫」。这个技能查的是后者：告警是否有抑制抖动的 `for`、值班同学收到时有没有上下文、表达式会不会一次炸出几百条。

## 用法

```bash
python3 scripts/promrule_check.py rules/                          # 目录递归
python3 scripts/promrule_check.py alerts.yml records.yml
python3 scripts/promrule_check.py rules/ --scrape-interval 30s    # 按实际抓取间隔判断窗口
python3 scripts/promrule_check.py rules/ --max-rules 30
python3 scripts/promrule_check.py rules/ --json > report.json
python3 scripts/promrule_check.py rules/ --strict                 # 有 high/warn 退出码 1
```

## 何时用

- 新增或改动告警规则，上线前要人评审一遍；
- 某条告警反复误报或半夜乱叫，想知道是 `for`、聚合还是窗口的问题；
- 接手别人维护的 rules 目录，先摸清整体质量与命名规范；
- 想把规则质量做成 CI 门禁，而不是靠人记得检查。

## 规则清单

| 规则 | 级别 | 现象 |
| --- | --- | --- |
| P000 | high | 规则既无 alert 也无 record、两者都有、或不是映射（缩进写错） |
| P009 | high | 告警名重复（Alertmanager 的分组、静默、抑制会互相串台） |
| P014 | high | `labels` 里写了 `instance`/`job`/`__name__`，覆盖原始标签 |
| P016 | high | 缺 `expr` |
| P017 | high | `expr` 里出现 `{{ }}` 模板 |
| P020 | high | 解析不出 `groups`，或 group 缺 name |
| P001 | warn | 告警没有 `for`，指标瞬时抖动即告警 |
| P002 | warn | `for` 短于 1m（或不是合法时长，high） |
| P003 | warn | `labels` 里没有 `severity` |
| P004 | warn | 注解既无 `summary` 也无 `description`（缺其一为 info） |
| P006 | warn | `rate()`/`increase()` 窗口小于抓取间隔的 4 倍 |
| P007 | warn | `rate()`/`increase()` 作用在名字不像 counter 的指标 |
| P010 | warn | `expr` 里硬编码 IP 或 `instance="..."` |
| P011 | warn | 录制规则名不合 `level:metric:operation` 三段式 |
| P012 | warn | 告警名含空格或非驼峰 |
| P021 | warn | 规则组名重复 |
| P022 | warn | group 的 `interval` 不是合法时长（如写成 `30`、`1minute`） |
| P005 | info | 注解里没用到 `{{ $labels }}` 或 `{{ $value }}` |
| P008 | info | 表达式无聚合且指标疑似高基数（告警风暴风险） |
| P013 | info | 同组规则超过 20 条 |

## 流程

1. 先把实际抓取间隔传进来（`--scrape-interval`，默认 15s），P006 的判断才准；不同 job 间隔不同时，按最慢的那个跑一遍。
2. 清 high：这类问题会让规则加载失败，或让告警指向错误的实例 —— 尤其 P014，`labels` 覆盖 `instance` 后告警里显示的机器是假的。
3. 清 warn：`for` 与 `severity` 决定会不会误报与能不能路由到人；P006/P007 决定表达式算出来的数有没有意义。
4. info 按情况处理。P005 的性价比最高 —— 注解里加上 `{{ $labels.instance }}` 与 `{{ $value }}`，值班同学不用翻大盘就知道是谁、多严重。
5. 改完加进 CI：`python3 scripts/promrule_check.py rules/ --strict`，再配 `promtool check rules` 做语法兜底，两者互补。

## 输出

文件数、规则组数、规则数与告警数的概览，按 high → warn → info 分组列出「规则号 + 现象 + 改法」，末尾给小计。`--json` 输出 `{files, rules, alerts, groups, summary, findings[]}`，findings 每项含 rule/severity/file/object/message/fix，便于接入门禁或做趋势统计。

## 写好一条告警的参考

```yaml
- alert: PayApiHighErrorRate
  expr: |
    sum(rate(http_requests_total{job="pay-api",status=~"5.."}[5m])) by (job)
      / sum(rate(http_requests_total{job="pay-api"}[5m])) by (job) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "pay-api 5xx 错误率超过 5%"
    description: "{{ $labels.job }} 近 5 分钟错误率 {{ $value | humanizePercentage }}，先看支付网关与下游依赖"
```

要点：按 job 聚合（一个服务一条告警，而不是每实例一条）、窗口 5m 远大于抓取间隔、`for` 抑制抖动、severity 可路由、注解带上下文与处理入口。

## 边界与常见问题

- 内置最小 YAML 解析器，不支持锚点合并（`<<: *x`）与多行 flow 集合；Helm/Jsonnet 模板请先渲染成纯 YAML 再检查。
- 不做 PromQL 语法校验，也不连 Prometheus 验证指标是否存在与基数多大；`promtool check rules` 与 `promtool query` 仍然要跑。
- counter 判断是启发式（名字是否以 `_total`/`_count`/`_sum`/`_bucket` 结尾），老项目里不守命名规范的 counter 会被误报为 P007，确认后忽略即可。
- 高基数判断也是启发式（指标名含 request/http/latency/duration 等且表达式无聚合），只当提醒。
- `up == 0` 这类「服务全挂」告警确实可以不配 `for`，P001 对它属于预期误报。
- 不检查 Alertmanager 路由与静默配置，也不评估告警是否该存在（那属于 SLO 设计）。
