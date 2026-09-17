#!/usr/bin/env python3
"""cron 表达式 → 中文解释 + 接下来 N 次运行时间。纯标准库。

用法：
  python3 cron_explain.py "0 2 * * 1-5"            # 解释 + 下 5 次
  python3 cron_explain.py "*/15 9-18 * * *" -n 10 --tz Asia/Shanghai
  python3 cron_explain.py @daily
  python3 cron_explain.py --file crontab.txt        # 逐行解释一份 crontab
支持 5 字段标准 cron：分 时 日 月 周；* , - / 名称（jan-dec、sun-sat）、? 视为 *、7 视为周日、@yearly/@monthly/@weekly/@daily/@hourly。
"""
import argparse, datetime as dt, json, re, sys

ALIASES = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
           "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DOWS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
FIELDS = [("分钟", 0, 59), ("小时", 0, 23), ("日", 1, 31), ("月", 1, 12), ("周", 0, 6)]
ZH_DOW = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]


def parse_field(expr, idx):
    name, lo, hi = FIELDS[idx]
    expr = expr.lower()
    if idx == 3:
        for i, m in enumerate(MONTHS):
            expr = expr.replace(m, str(i + 1))
    if idx == 4:
        for i, d in enumerate(DOWS):
            expr = expr.replace(d, str(i))
    if expr == "?":
        expr = "*"
    values, parts_desc = set(), []
    for part in expr.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            if not s.isdigit() or int(s) <= 0:
                raise ValueError(f"{name}字段步长非法：{s}")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise ValueError(f"{name}字段范围非法：{part}")
            a, b = int(a), int(b)
        elif part.isdigit():
            a = int(part); b = hi if step > 1 else a
        else:
            raise ValueError(f"{name}字段无法识别：{part}")
        if idx == 4:
            a, b = (0 if a == 7 else a), (0 if b == 7 else b) if b != 7 else 6
            if a == 0 and b == 0 and part == "7":
                a = b = 0
        if a < lo or b > hi or a > b:
            raise ValueError(f"{name}字段超出范围 {lo}-{hi}：{part}")
        values.update(range(a, b + 1, step))
        parts_desc.append((a, b, step, part))
    return sorted(values), parts_desc, expr


def describe_field(idx, values, parts_desc, expr):
    name, lo, hi = FIELDS[idx]
    full = list(range(lo, hi + 1))
    if values == full:
        return None
    outs = []
    for a, b, step, raw in parts_desc:
        if idx == 4:
            fmt = lambda v: ZH_DOW[v]
        elif idx == 3:
            fmt = lambda v: f"{v}月"
        elif idx == 2:
            fmt = lambda v: f"{v}日"
        elif idx == 1:
            fmt = lambda v: f"{v}点"
        else:
            fmt = lambda v: f"{v}分"
        if raw == "*" and step > 1:
            outs.append(f"每{step}{'分钟' if idx == 0 else '小时' if idx == 1 else '天' if idx == 2 else '个月' if idx == 3 else '天（按周几计）'}")
        elif step > 1:
            outs.append(f"从{fmt(a)}到{fmt(b)}每{step}{'分钟' if idx == 0 else '小时' if idx == 1 else '天' if idx == 2 else '个月' if idx == 3 else '天'}")
        elif a != b:
            outs.append(f"{fmt(a)}到{fmt(b)}")
        else:
            outs.append(fmt(a))
    return "、".join(outs)


def explain(expr):
    raw = expr.strip()
    expr = ALIASES.get(raw.lower(), raw)
    parts = expr.split()
    if len(parts) == 6 and parts[0].isdigit() is False and len(expr.split()) == 6:
        raise ValueError("看起来是 6 字段（含秒）表达式；本工具支持标准 5 字段，请去掉秒字段")
    if len(parts) != 5:
        raise ValueError(f"需要 5 个字段（分 时 日 月 周），实际 {len(parts)} 个")
    parsed = [parse_field(p, i) for i, p in enumerate(parts)]
    minute, hour, dom, month, dow = [p[0] for p in parsed]
    d = [describe_field(i, *parsed[i]) for i in range(5)]
    # 组装中文
    when = []
    if d[3]: when.append(f"{d[3]}")
    dom_restricted, dow_restricted = parts[2] not in ("*", "?"), parts[4] not in ("*", "?")
    if dom_restricted and dow_restricted:
        when.append(f"每月{d[2]}或{d[4]}（两者任一满足即触发）")
    elif dom_restricted:
        when.append(f"每月{d[2]}")
    elif dow_restricted:
        when.append(f"每{d[4]}")
    else:
        when.append("每天")
    if d[1] and d[0]:
        if len(hour) == 1 and len(minute) == 1:
            time_desc = f"{hour[0]:02d}:{minute[0]:02d}"
        else:
            time_desc = f"{d[1]}的{d[0]}"
    elif d[1]:
        time_desc = f"{d[1]}的每分钟"
    elif d[0]:
        time_desc = f"每小时的{d[0]}" if not (parts[0].startswith("*/")) else d[0]
    else:
        time_desc = "每分钟"
    text = "，".join(when) + "，" + time_desc + "运行"
    return {"expression": expr, "alias": raw if raw != expr else None, "fields": {"minute": minute, "hour": hour, "dom": dom, "month": month, "dow": dow},
            "dom_restricted": dom_restricted, "dow_restricted": dow_restricted, "description": text}


def next_runs(info, n, start, horizon_days=366 * 5):
    minute, hour, dom, month, dow = (set(info["fields"][k]) for k in ("minute", "hour", "dom", "month", "dow"))
    t = start.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    end = start + dt.timedelta(days=horizon_days)
    out = []
    while t < end and len(out) < n:
        if t.month not in month:
            t = (t.replace(day=1, hour=0, minute=0) + dt.timedelta(days=32)).replace(day=1); continue
        day_ok = (t.day in dom) if info["dom_restricted"] and not info["dow_restricted"] else \
                 ((t.weekday() + 1) % 7 in dow) if info["dow_restricted"] and not info["dom_restricted"] else \
                 (t.day in dom or (t.weekday() + 1) % 7 in dow) if info["dom_restricted"] and info["dow_restricted"] else True
        if not day_ok:
            t = t.replace(hour=0, minute=0) + dt.timedelta(days=1); continue
        if t.hour not in hour:
            t = t.replace(minute=0) + dt.timedelta(hours=1); continue
        if t.minute not in minute:
            t += dt.timedelta(minutes=1); continue
        out.append(t); t += dt.timedelta(minutes=1)
    return out


def main():
    ap = argparse.ArgumentParser(description="cron 表达式解释器")
    ap.add_argument("expr", nargs="?", help="cron 表达式或 @别名")
    ap.add_argument("--file", help="逐行解释 crontab 文件（忽略注释与环境变量行）")
    ap.add_argument("-n", type=int, default=5, help="列出接下来 N 次运行时间")
    ap.add_argument("--tz", help="时区，如 Asia/Shanghai（默认本机时区）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tz = None
    if a.tz:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(a.tz)
    now = dt.datetime.now(tz) if tz else dt.datetime.now().astimezone()
    items = []
    if a.file:
        for ln in open(a.file, encoding="utf-8", errors="replace"):
            s = ln.strip()
            if not s or s.startswith("#") or re.match(r"^[A-Za-z_]+=", s):
                continue
            m = re.match(r"^(@\w+|(?:\S+\s+){4}\S+)\s+(.*)$", s)
            if m:
                items.append((m.group(1), m.group(2)))
    elif a.expr:
        items.append((a.expr, ""))
    else:
        ap.error("请给出表达式或 --file")
    results = []
    for expr, cmd in items:
        try:
            info = explain(expr)
            runs = next_runs(info, a.n, now)
            info["next_runs"] = [r.isoformat(timespec="minutes") for r in runs]
            info["command"] = cmd or None
            results.append(info)
        except ValueError as e:
            results.append({"expression": expr, "error": str(e), "command": cmd or None})
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2)); return
    for r in results:
        head = f"{r['expression']}" + (f"（{r['alias']}）" if r.get("alias") else "")
        if r.get("error"):
            print(f"✗ {head}: {r['error']}"); continue
        print(f"{head}" + (f"  → {r['command']}" if r.get("command") else ""))
        print(f"  含义：{r['description']}")
        if r["dom_restricted"] and r["dow_restricted"]:
            print("  提示：日与周同时限定时，cron 取「或」，常与直觉相反；如需「且」请在命令里再判断")
        print(f"  接下来 {len(r['next_runs'])} 次（{now.tzname()}）：")
        for x in r["next_runs"]:
            d = dt.datetime.fromisoformat(x)
            print(f"    {x.replace('T', ' ')} {ZH_DOW[(d.weekday() + 1) % 7]}")
        if not r["next_runs"]:
            print("    （五年内没有匹配的时间，检查日/月组合是否存在，如 2 月 30 日）")


if __name__ == "__main__":
    main()
