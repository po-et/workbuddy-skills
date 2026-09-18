#!/usr/bin/env python3
"""Prometheus 告警规则与录制规则体检：内置最小 YAML 解析（不依赖 PyYAML、promtool），检查 for/severity/注解上下文、
rate 窗口与抓取间隔、counter 命名、聚合缺失、重名、硬编码实例、录制规则命名、labels 覆盖等，分 high/warn/info 并给改法。

用法：
  python3 promrule_check.py rules/ alerts.yml [--scrape-interval 15s] [--json] [--strict]
  --strict：存在 high/warn 则退出码 1，可直接当 CI 门禁。
"""
import argparse
import json
import os
import re
import sys

RE_DUR = re.compile(r"^(?:\d+(?:ms|[smhdwy]))+$")
UNIT = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}
RE_RANGE = re.compile(r"\b(rate|irate|increase|delta|idelta|deriv|predict_linear)\s*\(\s*"
                      r"([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(?:\{[^{}]*\})?\s*\[([0-9]+(?:ms|[smhdwy]))\]")
RE_AGG = re.compile(r"\b(sum|avg|min|max|count|count_values|stddev|stdvar|topk|bottomk|quantile|group)\s*(?:by|without)?\s*\(")
RE_BY = re.compile(r"\b(?:by|without)\s*\(")
RE_METRIC = re.compile(r"(?<![\w:.])([a-z_][a-z0-9_]*(?::[a-z0-9_:]+)*)\s*(?:\{|\[|\s*[<>=!]|\s*\))")
RE_IPLIT = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
RE_HARDLBL = re.compile(r'\b(instance|pod|node|host|hostname|container_id)\s*=\s*"([^"]*[^"*])"')
RE_CAMEL = re.compile(r"^[A-Z][A-Za-z0-9]*$")
RE_RECNAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z0-9_]+:[a-zA-Z0-9_]+$")
COUNTER_SUFFIX = ("_total", "_count", "_sum", "_bucket")
HIGH_CARD = re.compile(r"(request|http|grpc|rpc|query|sql|latency|duration|_bucket|session|trace)")
SEVERITIES = {"critical", "warning", "info", "page", "ticket", "p0", "p1", "p2", "p3", "disaster", "high", "low"}
PROM_FUNCS = {"rate", "irate", "increase", "sum", "avg", "min", "max", "count", "delta", "idelta", "by", "without",
              "on", "ignoring", "group_left", "group_right", "and", "or", "unless", "offset", "bool", "histogram_quantile",
              "quantile", "topk", "bottomk", "absent", "absent_over_time", "clamp_max", "clamp_min", "time", "vector",
              "changes", "resets", "predict_linear", "deriv", "stddev", "stdvar", "label_replace", "label_join",
              "abs", "ceil", "floor", "round", "sqrt", "exp", "ln", "log2", "log10", "sgn", "scalar", "sort", "sort_desc",
              "max_over_time", "min_over_time", "avg_over_time", "sum_over_time", "count_over_time", "last_over_time",
              "quantile_over_time", "stddev_over_time", "present_over_time", "if", "unless"}


# ---------- 最小 YAML 解析（与 k8s-manifest-check 同一套实现） ----------
def scalar(s):
    s = s.strip()
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s[:1] in ("'", '"') and s[-1:] == s[:1] and len(s) >= 2:
        return s[1:-1]
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [scalar(x) for x in inner.split(",")] if inner else []
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for kv in s[1:-1].split(","):
            if ":" in kv:
                k, v = kv.split(":", 1)
                out[k.strip()] = scalar(v)
        return out
    return s


def split_kv(line):
    """把 'key: value' 切开；忽略引号内的冒号（PromQL 里冒号很多）。"""
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
        elif ch == ":" and (i + 1 == len(line) or line[i + 1] in " \t"):
            return line[:i].strip(), line[i + 1:].strip()
    return None, None


def strip_comment(line):
    q, out = None, []
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_block(lines, i, indent):
    while i < len(lines) and not lines[i][1].strip():
        i += 1
    if i >= len(lines):
        return None, i
    ind, text = lines[i]
    if ind < indent:
        return None, i
    if text.startswith("- ") or text == "-":
        out = []
        while i < len(lines):
            ind, text = lines[i]
            if not text.strip():
                i += 1
                continue
            if ind != indent or not (text.startswith("- ") or text == "-"):
                break
            body = text[1:].strip()
            if not body:
                val, i = parse_block(lines, i + 1, indent + 1)
                out.append(val)
                continue
            k, v = split_kv(body)
            if k is not None and not body.startswith(("'", '"', "[", "{")):
                lines[i] = (indent + 2, body)
                val, i = parse_block(lines, i, indent + 2)
                out.append(val)
            else:
                out.append(scalar(body))
                i += 1
        return out, i
    out = {}
    while i < len(lines):
        ind, text = lines[i]
        if not text.strip():
            i += 1
            continue
        if ind < indent or (ind == indent and (text.startswith("- ") or text == "-")):
            break
        if ind > indent:
            i += 1
            continue
        k, v = split_kv(text)
        if k is None:
            i += 1
            continue
        if v in ("|", "|-", "|+", ">", ">-", ">+"):
            block, j = [], i + 1
            while j < len(lines) and (not lines[j][1].strip() or lines[j][0] > indent):
                block.append(lines[j][1])
                j += 1
            out[k] = "\n".join(block)
            i = j
            continue
        if v == "":
            j = i + 1
            while j < len(lines) and not lines[j][1].strip():
                j += 1
            if j < len(lines) and (lines[j][0] > indent or (lines[j][0] == indent and lines[j][1].startswith("- "))):
                out[k], i = parse_block(lines, j, lines[j][0])
            else:
                out[k] = None
                i = j
            continue
        if v.startswith("&"):
            v = v.split(" ", 1)[1] if " " in v else ""
        out[k] = scalar(v)
        i += 1
    return out, i


def load_yaml(text):
    docs = []
    for chunk in re.split(r"^---\s*$", text, flags=re.M):
        raw = [strip_comment(l.replace("\t", "  ")) for l in chunk.splitlines()]
        lines = [(len(l) - len(l.lstrip(" ")), l.strip()) for l in raw if l.strip() and not l.strip().startswith("%")]
        if not lines:
            continue
        doc, _ = parse_block(lines, 0, lines[0][0])
        if isinstance(doc, dict):
            docs.append(doc)
    return docs


# ---------- 工具 ----------
def dur_seconds(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not RE_DUR.match(s):
        return None
    total = 0.0
    for num, unit in re.findall(r"(\d+)(ms|[smhdwy])", s):
        total += int(num) * UNIT[unit]
    return total


def metrics_in(expr):
    out = []
    for m in RE_METRIC.finditer(expr):
        n = m.group(1)
        if n in PROM_FUNCS or n.isdigit():
            continue
        out.append(n)
    return out


def check_rule(r, gname, where, idx, findings, seen_alerts, a):
    def add(rule, sev, msg, fix, obj=None):
        rr = r if isinstance(r, dict) else {}
        findings.append({"rule": rule, "severity": sev, "file": where,
                         "object": obj or f"{gname}/{rr.get('alert') or rr.get('record') or f'#{idx}'}",
                         "message": msg, "fix": fix})

    if not isinstance(r, dict):
        add("P000", "high", f"第 {idx} 条规则不是映射（YAML 缩进写错了）", "每条规则形如 '- alert: Name' 后跟同级缩进的 expr/for/labels")
        return
    alert, record = r.get("alert"), r.get("record")
    expr = r.get("expr")
    if alert and record:
        add("P000", "high", "同一条规则里既有 alert 又有 record", "一条规则只能是告警或录制，拆成两条")
    if not alert and not record:
        add("P000", "high", "规则既没有 alert 也没有 record", "补上 alert（告警名）或 record（录制指标名）")
    if not expr or not str(expr).strip():
        add("P016", "high", "缺少 expr", "补上 PromQL 表达式；promtool check rules 也会直接报错")
        return
    expr = str(expr)
    if "{{" in expr:
        add("P017", "high", "expr 里出现了 {{ }} 模板", "模板只能写在 annotations/labels，expr 必须是纯 PromQL")
    # ---- 告警规则 ----
    if alert:
        name = str(alert)
        if name in seen_alerts:
            add("P009", "high", f"告警名 {name} 重复（另一处在 {seen_alerts[name]}）",
                "告警名应全局唯一，否则 Alertmanager 的分组、静默、抑制规则会互相串台")
        else:
            seen_alerts[name] = f"{where}:{gname}"
        if not RE_CAMEL.match(name):
            why = "含空格" if " " in name else "不是驼峰"
            add("P012", "warn", f"告警名 {name!r} {why}", "用驼峰无空格命名，如 ApiHighErrorRate；空格会让静默与路由表达式难写")
        fv = r.get("for")
        if fv is None:
            add("P001", "warn", "没有 for，指标瞬时抖动就会告警",
                "按指标波动周期加 for（常见 2m–10m）；只有「服务全挂」这类才适合立即触发")
        else:
            secs = dur_seconds(fv)
            if secs is None:
                add("P002", "high", f"for 值 {fv!r} 不是合法时长", "写成 30s / 5m / 1h 这种形式")
            elif secs < 60:
                add("P002", "warn", f"for 只有 {fv}，比抓取间隔的几倍还短，等于瞬时抖动即告警",
                    f"至少给到 {a.scrape_interval} 的 4 倍以上，一般 2m 起")
        labels = r.get("labels") or {}
        if not isinstance(labels, dict):
            labels = {}
        if not labels.get("severity"):
            add("P003", "warn", "labels 里没有 severity", "补 severity（如 critical/warning/info），Alertmanager 靠它分级路由与升级")
        elif str(labels["severity"]).lower() not in SEVERITIES:
            add("P003", "info", f"severity={labels['severity']!r} 不是常见取值", "与团队路由表里的取值对齐，否则路由不到人")
        for bad in ("instance", "job", "__name__"):
            if bad in labels:
                add("P014", "high", f"labels 里写了 {bad}，会覆盖原始标签",
                    f"删掉 {bad}；它由抓取目标自动带入，覆盖后告警内容会指向错误的实例")
        ann = r.get("annotations") or {}
        if not isinstance(ann, dict):
            ann = {}
        miss = [k for k in ("summary", "description") if not ann.get(k)]
        if len(miss) == 2:
            add("P004", "warn", "annotations 里既没有 summary 也没有 description",
                "summary 一句话说清「什么坏了」，description 写清影响面与处理入口")
        elif miss:
            add("P004", "info", f"annotations 缺 {miss[0]}", "summary 给标题，description 给细节，两者都填值班同学才看得懂")
        blob = " ".join(str(v) for v in ann.values())
        if blob and "$labels" not in blob and "$value" not in blob:
            add("P005", "info", "注解里没用到 {{ $labels }} 或 {{ $value }}，告警内容没有上下文",
                "写成「{{ $labels.instance }} 错误率 {{ $value | humanizePercentage }}」这类，收到就知道是谁、多严重")
    # ---- 录制规则 ----
    if record:
        name = str(record)
        if not RE_RECNAME.match(name):
            add("P011", "warn", f"录制规则名 {name!r} 不符 level:metric:operation 三段式约定",
                "用 level:metric:operation 三段式，如 job:http_requests:rate5m，一眼看出聚合层级与算子")
        if r.get("for") is not None:
            add("P011", "info", "录制规则上写了 for（对录制无意义）", "删掉 for，它只对 alert 生效")
    # ---- 表达式通用检查 ----
    scrape = dur_seconds(a.scrape_interval) or 15.0
    for fn, metric, win in RE_RANGE.findall(expr):
        w = dur_seconds(win) or 0
        if w < scrape * 4:
            add("P006", "warn", f"{fn}({metric}[{win}]) 的窗口小于抓取间隔 {a.scrape_interval} 的 4 倍",
                f"窗口内至少要有 4 个采样点，改成 {int(scrape * 4 // 60 + 1)}m 以上；窗口太短会出现空洞与毛刺")
        if fn in ("rate", "irate", "increase") and not metric.endswith(COUNTER_SUFFIX):
            add("P007", "warn", f"{fn}() 作用在 {metric}，名字不像 counter（不以 _total/_count/_sum/_bucket 结尾）",
                "rate/increase 只能用于 counter；gauge 请用 delta()/deriv() 或 *_over_time()，否则结果没有意义")
    if not RE_AGG.search(expr) and not RE_BY.search(expr):
        ms = metrics_in(expr)
        if any(HIGH_CARD.search(m) for m in ms):
            add("P008", "info", f"表达式没有任何聚合，指标 {ms[0]} 疑似高基数",
                "加 sum(...) by (job, …) 收敛维度，否则每个实例/Pod/接口各触发一条，值班同学会被刷屏")
    if RE_IPLIT.search(expr):
        add("P010", "warn", "expr 里硬编码了 IP", "改用 job/service 等稳定标签筛选；机器一换告警就失效")
    for lbl, val in RE_HARDLBL.findall(expr):
        add("P010", "warn", f"expr 里硬编码了 {lbl}=\"{val}\"", f"用服务级标签替代 {lbl}；实例重建、扩缩容后这条告警就成了哑规则")


def check_file(path, findings, seen_alerts, seen_groups, a):
    text = open(path, encoding="utf-8", errors="replace").read()
    docs = load_yaml(text)
    n = 0
    if not docs or not any(isinstance(d.get("groups"), list) for d in docs):
        findings.append({"rule": "P020", "severity": "high", "file": path, "object": "-",
                         "message": "没有解析出 groups 列表（不是 Prometheus 规则文件或缩进有误）",
                         "fix": "规则文件顶层必须是 groups: 后跟 - name/rules 列表；Helm 模板请先渲染"})
        return 0
    for d in docs:
        for g in d.get("groups") or []:
            if not isinstance(g, dict):
                findings.append({"rule": "P020", "severity": "high", "file": path, "object": "-",
                                 "message": "groups 下有非映射条目", "fix": "每个 group 形如 '- name: xxx' 加 rules 列表"})
                continue
            gname = str(g.get("name") or "?")
            if not g.get("name"):
                findings.append({"rule": "P020", "severity": "high", "file": path, "object": "-",
                                 "message": "group 缺少 name", "fix": "补 name；Prometheus 加载时会直接报错"})
            elif gname in seen_groups:
                findings.append({"rule": "P021", "severity": "warn", "file": path, "object": gname,
                                 "message": f"规则组名 {gname} 与 {seen_groups[gname]} 重复",
                                 "fix": "同一 Prometheus 实例内组名需唯一，否则后加载的会被拒绝"})
            else:
                seen_groups[gname] = path
            iv = g.get("interval")
            if iv is not None and dur_seconds(iv) is None:
                findings.append({"rule": "P022", "severity": "warn", "file": path, "object": gname,
                                 "message": f"group interval {iv!r} 不是合法时长", "fix": "写成 30s / 1m"})
            rules = g.get("rules") or []
            if not rules:
                findings.append({"rule": "P020", "severity": "warn", "file": path, "object": gname,
                                 "message": "规则组是空的", "fix": "删掉空组，或补上 rules"})
            if len(rules) > a.max_rules:
                findings.append({"rule": "P013", "severity": "info", "file": path, "object": gname,
                                 "message": f"同组 {len(rules)} 条规则（超过 {a.max_rules}）",
                                 "fix": "按业务/服务拆分成多个组：同组规则串行求值，一组过大会拖慢整体并让 interval 难调"})
            for i, r in enumerate(rules, 1):
                n += 1
                check_rule(r, gname, path, i, findings, seen_alerts, a)
    return n


def main():
    ap = argparse.ArgumentParser(description="Prometheus 告警/录制规则体检")
    ap.add_argument("paths", nargs="+", help="规则文件或目录")
    ap.add_argument("--scrape-interval", default="15s", help="抓取间隔，用于判断 rate 窗口是否过短，默认 15s")
    ap.add_argument("--max-rules", type=int, default=20, help="单组规则数上限，超过给建议，默认 20")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="存在 high/warn 时退出码 1")
    a = ap.parse_args()
    if dur_seconds(a.scrape_interval) is None:
        sys.exit(f"--scrape-interval {a.scrape_interval!r} 不是合法时长，写成 15s / 30s / 1m")
    files = []
    for p in a.paths:
        if os.path.isdir(p):
            for root, dirs, fns in os.walk(p):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
                files += sorted(os.path.join(root, f) for f in fns if f.endswith((".yml", ".yaml")))
        elif os.path.isfile(p):
            files.append(p)
        else:
            sys.exit(f"路径不存在：{p}")
    if not files:
        sys.exit("没有找到 .yml/.yaml 规则文件")
    findings, seen_alerts, seen_groups, n_rules = [], {}, {}, 0
    for f in files:
        n_rules += check_file(f, findings, seen_alerts, seen_groups, a)
    order = {"high": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda x: (order[x["severity"]], x["file"], x["object"], x["rule"]))
    c = {s: sum(1 for x in findings if x["severity"] == s) for s in ("high", "warn", "info")}
    if a.json:
        print(json.dumps({"files": len(files), "rules": n_rules, "alerts": len(seen_alerts),
                          "groups": len(seen_groups), "summary": c, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        print(f"检查 {len(files)} 个文件 · {len(seen_groups)} 个规则组 · {n_rules} 条规则（告警 {len(seen_alerts)} 条）")
        if not findings:
            print("  ✓ 没有发现问题")
        cur = None
        for x in findings:
            key = (x["file"], x["object"])
            if key != cur:
                print(f"\n== {x['file']}  {x['object']}")
                cur = key
            print(f"  [{x['severity'].upper():4}] {x['rule']}: {x['message']}\n         → {x['fix']}")
        print(f"\n小计：high {c['high']} / warn {c['warn']} / info {c['info']}")
        if c["high"] or c["warn"]:
            print("建议：先清 high（加载失败或告警指向错误），再按 warn 补 for/severity/注解上下文")
    sys.exit(1 if (a.strict and (c["high"] or c["warn"])) else 0)


if __name__ == "__main__":
    main()
