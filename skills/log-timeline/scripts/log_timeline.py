#!/usr/bin/env python3
"""多文件日志时间线重建：识别每行时间戳（ISO8601 / `2026-09-18 10-00-00.123` 形态 / syslog / Nginx / Unix 毫秒），
归一到同一时区后按时间排序合并，输出对齐的时间线 + 每桶事件密度柱状图 + 各文件首末事件 + 错误爆发点。纯标准库。

用法：
  python3 log_timeline.py app.log nginx.log syslog.log --tz +08:00
  python3 log_timeline.py logs/*.log --from "10:00" --to "10:10" --level ERROR --bucket 10s
  python3 log_timeline.py a.log b.log --grep "timeout|refused" --json
"""
import argparse
import collections
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

PATS = [
    ("iso", re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})[T ](\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,9}))?\s?(Z|[+-]\d{2}:?\d{2})?")),
    ("slash", re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})[ T](\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,9}))?")),
    ("nginx", re.compile(r"\[(\d{1,2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})\s?([+-]\d{4})?\]")),
    ("syslog", re.compile(r"(?:^|[\s\[])([A-Z][a-z]{2})\s{1,2}(\d{1,2})\s(\d{2}):(\d{2}):(\d{2})(?:[.,](\d{1,9}))?")),
    ("epoch_ms", re.compile(r"(?<![\d.])(1[5-9]\d{11})(?![\d.])")),
    ("epoch_s", re.compile(r"(?<![\d.])(1[5-9]\d{8})(?![\d.])")),
]
LV_ALT = r"TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR|FATAL|CRIT(?:ICAL)?|PANIC|EMERG|SEVERE"
RE_LEVEL = re.compile(rf"\b({LV_ALT})\b", re.I)
RE_LEADLVL = re.compile(rf"^[\[(]?({LV_ALT})[\])]?\s*[:\-]?\s*", re.I)
RE_HTTP5XX = re.compile(r"\"[A-Z]+ [^\"]*HTTP/[\d.]+\"\s+(5\d\d)\b")
STRIPPABLE = {"iso", "slash", "nginx", "syslog"}      # 行首时间戳可以去掉；epoch 多半嵌在 JSON 里，原样保留
LEVEL_MAP = {"WARNING": "WARN", "ERR": "ERROR", "SEVERE": "ERROR", "CRIT": "FATAL", "CRITICAL": "FATAL",
             "PANIC": "FATAL", "EMERG": "FATAL", "NOTICE": "INFO"}
RANK = {"TRACE": 0, "DEBUG": 1, "INFO": 2, "WARN": 3, "ERROR": 4, "FATAL": 5}
STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 21600, 86400]
COLORS = [36, 32, 33, 35, 34, 91, 92, 93, 94, 95, 96, 31]


def alias_of(i):
    return chr(65 + i) if i < 26 else chr(65 + i // 26 - 1) + chr(65 + i % 26)


def tzinfo_of(spec):
    s = (spec or "").strip()
    if not s or s.lower() == "local":
        return datetime.now().astimezone().tzinfo
    if s.upper() in ("Z", "UTC", "GMT"):
        return timezone.utc
    m = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})?", s)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(s)
    except Exception:                                     # noqa: BLE001
        sys.exit(f"无法解析时区 {spec!r}；用 +08:00 / UTC / local / Asia/Shanghai")


def _micro(frac):
    return int((frac or "0").ljust(6, "0")[:6])


def _off(text):
    if not text or text == "Z":
        return timezone.utc if text == "Z" else None
    t = text.replace(":", "")
    sign = 1 if t[0] == "+" else -1
    return timezone(sign * timedelta(hours=int(t[1:3]), minutes=int(t[3:5])))


def parse_ts(line, year, assume, prefix):
    """返回 (aware datetime, 命中的原文, 格式名)；没识别到返回 (None, None, None)。取位置最靠前的匹配。"""
    seg = line[:prefix]
    best = None
    for name, pat in PATS:
        m = pat.search(seg)
        if m and (best is None or m.start() < best[1].start()):
            best = (name, m)
    if not best:
        return None, None, None
    name, m = best
    g = m.groups()
    try:
        if name == "iso" or name == "slash":
            tz = _off(g[7]) if name == "iso" else None
            dt = datetime(int(g[0]), int(g[1]), int(g[2]), int(g[3]), int(g[4]), int(g[5]), _micro(g[6]),
                          tzinfo=tz or assume)
        elif name == "nginx":
            dt = datetime(int(g[2]), MONTHS[g[1].lower()], int(g[0]), int(g[3]), int(g[4]), int(g[5]),
                          tzinfo=_off(g[6]) or assume)
        elif name == "syslog":
            mo = MONTHS.get(g[0].lower())
            if not mo:
                return None, None, None
            dt = datetime(year, mo, int(g[1]), int(g[2]), int(g[3]), int(g[4]), _micro(g[5]), tzinfo=assume)
        else:
            v = int(g[0])
            dt = datetime.fromtimestamp(v / 1000 if name == "epoch_ms" else v, timezone.utc)
    except (ValueError, KeyError):
        return None, None, None
    return dt, m.group(0), name


def level_of(line):
    m = RE_LEVEL.search(line)
    if not m:
        return None
    v = m.group(1).upper()
    return LEVEL_MAP.get(v, v)


def parse_bound(s, tz, ref):
    if not s:
        return None
    dt, _, _ = parse_ts(s, ref.year if ref else datetime.now().year, tz, len(s) + 1)
    if dt:
        return dt.astimezone(tz)
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?(?:[.,](\d{1,6}))?", s.strip())
    if m and ref:
        return ref.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=int(m.group(3) or 0),
                           microsecond=_micro(m.group(4)))
    sys.exit(f"无法解析时间 {s!r}；用 '2026-09-18 10:00:00' 或 '10:00'（日期取首个事件当天）")


def load(files, a, assume):
    """逐行读入并解析时间戳；没有时间戳的行按续行并入上一条（堆栈、SQL 多行都靠这个不丢）。"""
    events, metas = [], []
    for i, path in enumerate(files):
        al = alias_of(i)
        meta = {"alias": al, "file": path, "lines": 0, "parsed": 0, "unparsed": 0, "continuation": 0,
                "formats": collections.Counter(), "levels": collections.Counter(), "first": None, "last": None}
        fh = sys.stdin if path == "-" else open(path, encoding="utf-8", errors="replace")
        last_dt = None
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            meta["lines"] += 1
            dt, hit, fmt = parse_ts(line, a.year, assume, a.prefix)
            if dt is None:
                if last_dt is None or a.no_cont:
                    meta["unparsed"] += 1
                    continue
                meta["continuation"] += 1
                dt, hit, fmt, cont = last_dt, "", "cont", True
            else:
                cont = False
                meta["parsed"] += 1
                meta["formats"][fmt] += 1
                last_dt = dt
            lv = level_of(line) or ""
            if not lv and a.http_5xx and RE_HTTP5XX.search(line):
                lv = "ERROR"
            if hit and fmt in STRIPPABLE:
                msg = RE_LEADLVL.sub("", line.replace(hit, "", 1).strip(" \t-|"), count=1)
            else:
                msg = line.strip()
            if lv:
                meta["levels"][lv] += 1
            if meta["first"] is None or dt < meta["first"]:
                meta["first"] = dt
            if meta["last"] is None or dt > meta["last"]:
                meta["last"] = dt
            events.append({"ts": dt, "alias": al, "file": path, "level": lv, "msg": msg, "cont": cont, "raw": line})
        if fh is not sys.stdin:
            fh.close()
        metas.append(meta)
    events.sort(key=lambda e: (e["ts"], e["alias"]))
    return events, metas


def pick_step(span, want):
    for s in STEPS:
        if span / s <= want:
            return s
    return 86400


def bucketize(events, step):
    """按 step 秒分桶；桶区间对齐到整点边界，中间的空桶也保留（看得见断流）。"""
    if not events:
        return []
    base = events[0]["ts"].replace(microsecond=0)
    base -= timedelta(seconds=base.timestamp() % step)
    agg = {}
    for e in events:
        k = int((e["ts"] - base).total_seconds() // step)
        b = agg.setdefault(k, {"count": 0, "errors": 0, "sample": None})
        b["count"] += 1
        if RANK.get(e["level"], 0) >= 4:
            b["errors"] += 1
            if b["sample"] is None:
                b["sample"] = f"{e['alias']} {e['msg'][:80]}"
    lo, hi = min(agg), max(agg)
    keys = range(lo, hi + 1) if hi - lo <= 2000 else sorted(agg)   # 桶太多就只列有事件的
    empty = {"count": 0, "errors": 0, "sample": None}
    return [dict(agg.get(k, empty), start=base + timedelta(seconds=k * step)) for k in keys]


def bursts(buckets, step):
    errs = [b["errors"] for b in buckets]
    nz = [e for e in errs if e]
    if not nz:
        return []
    mean = sum(errs) / len(errs)
    var = sum((e - mean) ** 2 for e in errs) / len(errs)
    sd = var ** 0.5
    thr = max(3, mean + 2 * sd)
    out = [{"start": b["start"], "errors": b["errors"], "count": b["count"], "sample": b["sample"],
            "baseline": round(mean, 2)} for b in buckets if b["errors"] >= thr]
    out.sort(key=lambda x: -x["errors"])
    return out[:5]


def hstep(step):
    if step < 60:
        return f"{step}s"
    if step < 3600:
        return f"{step // 60}m"
    if step < 86400:
        return f"{step // 3600}h"
    return f"{step // 86400}d"


def main():
    ap = argparse.ArgumentParser(description="多文件日志时间线重建")
    ap.add_argument("files", nargs="+", help="日志文件（可多个、可不同格式），- 表示标准输入")
    ap.add_argument("--tz", default="+08:00", help="输出时区，如 +08:00 / UTC / local / Asia/Shanghai")
    ap.add_argument("--assume-tz", help="行内没写时区时按哪个时区解读，默认同 --tz")
    ap.add_argument("--year", type=int, default=datetime.now().year, help="syslog 格式没有年份，用它补全")
    ap.add_argument("--from", dest="t_from", help="起始时间，如 '2026-09-18 10:00:00' 或 '10:00'")
    ap.add_argument("--to", dest="t_to", help="结束时间")
    ap.add_argument("--grep", help="只保留匹配该正则的行（默认忽略大小写）")
    ap.add_argument("--exclude", help="排除匹配该正则的行")
    ap.add_argument("--case", action="store_true", help="--grep/--exclude 区分大小写")
    ap.add_argument("--level", help="只看该级别及以上：TRACE/DEBUG/INFO/WARN/ERROR/FATAL")
    ap.add_argument("--http-5xx", action="store_true", help="访问日志没有级别字段时，把 HTTP 5xx 的行当 ERROR")
    ap.add_argument("--bucket", default="auto", help="密度桶大小：auto / 1s / 10s / 1m / 5m / 1h")
    ap.add_argument("--buckets", type=int, default=48, help="auto 模式下最多多少个桶")
    ap.add_argument("--width", type=int, default=120, help="时间线每行消息截断宽度")
    ap.add_argument("--limit", type=int, default=0, help="时间线最多打印多少条，0 为不限")
    ap.add_argument("--prefix", type=int, default=200, help="只在每行前 N 个字符里找时间戳")
    ap.add_argument("--no-cont", action="store_true", help="丢弃没有时间戳的续行（默认并入上一条的时间）")
    ap.add_argument("--no-timeline", action="store_true", help="只要密度图与统计，不打印合并时间线")
    ap.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tz = tzinfo_of(a.tz)
    assume = tzinfo_of(a.assume_tz) if a.assume_tz else tz
    missing = [f for f in a.files if f != "-" and not os.path.isfile(f)]
    if missing:
        sys.exit(f"文件不存在：{missing}")
    events, metas = load(a.files, a, assume)
    events = [dict(e, ts=e["ts"].astimezone(tz)) for e in events]
    total_read = len(events)
    ref = events[0]["ts"] if events else None
    t0, t1 = parse_bound(a.t_from, tz, ref), parse_bound(a.t_to, tz, ref)
    flags = 0 if a.case else re.I
    rg = re.compile(a.grep, flags) if a.grep else None
    ex = re.compile(a.exclude, flags) if a.exclude else None
    minr = RANK.get((a.level or "").upper(), -1)
    if a.level and minr < 0:
        sys.exit(f"未知级别 {a.level!r}；可选 {list(RANK)}")

    def keep(e):
        if t0 and e["ts"] < t0:
            return False
        if t1 and e["ts"] > t1:
            return False
        if minr >= 0 and RANK.get(e["level"], -1) < minr:
            return False
        if rg and not rg.search(e["raw"]):
            return False
        if ex and ex.search(e["raw"]):
            return False
        return True

    ev = [e for e in events if keep(e)]
    span = (ev[-1]["ts"] - ev[0]["ts"]).total_seconds() if len(ev) > 1 else 1
    if a.bucket == "auto":
        step = pick_step(max(span, 1), max(a.buckets, 4))
    else:
        m = re.fullmatch(r"(\d+)([smhd])", a.bucket)
        if not m:
            sys.exit("--bucket 形如 10s / 1m / 1h / auto")
        step = int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    bk = bucketize(ev, step)
    bs = bursts(bk, step)
    use_color = a.color == "always" or (a.color == "auto" and sys.stdout.isatty())
    cmap = {m["alias"]: COLORS[i % len(COLORS)] for i, m in enumerate(metas)}

    def col(al, s):
        return f"\033[{cmap.get(al, 37)}m{s}\033[0m" if use_color else s

    if a.json:
        print(json.dumps({
            "tz": str(tz), "bucket_seconds": step, "events_total": total_read, "events_shown": len(ev),
            "files": [{"alias": m["alias"], "file": m["file"], "lines": m["lines"], "parsed": m["parsed"],
                       "unparsed": m["unparsed"], "continuation": m["continuation"],
                       "formats": dict(m["formats"]), "levels": dict(m["levels"]),
                       "first": m["first"].astimezone(tz).isoformat() if m["first"] else None,
                       "last": m["last"].astimezone(tz).isoformat() if m["last"] else None} for m in metas],
            "timeline": [{"ts": e["ts"].isoformat(), "alias": e["alias"], "file": e["file"], "level": e["level"],
                          "message": e["msg"][:1000], "continuation": e["cont"]}
                         for e in (ev[:a.limit] if a.limit else ev)],
            "density": [{"start": b["start"].isoformat(), "count": b["count"], "errors": b["errors"]} for b in bk],
            "bursts": [{"start": b["start"].isoformat(), "errors": b["errors"], "count": b["count"],
                        "baseline": b["baseline"], "sample": b["sample"]} for b in bs],
        }, ensure_ascii=False, indent=2))
        return

    print(f"## 输入文件（时区统一到 {tz}）")
    for m in metas:
        fm = ",".join(f"{k}" for k, _ in m["formats"].most_common(2)) or "-"
        lv = " ".join(f"{k}:{v}" for k, v in sorted(m["levels"].items(), key=lambda kv: -RANK.get(kv[0], 0))[:3])
        fs = m["first"].astimezone(tz).strftime("%m-%d %H:%M:%S") if m["first"] else "-"
        ls = m["last"].astimezone(tz).strftime("%m-%d %H:%M:%S") if m["last"] else "-"
        print(f" {col(m['alias'], m['alias'])}  {os.path.basename(m['file']):<22} {m['lines']:>7} 行"
              f"（识别 {m['parsed']}，续行 {m['continuation']}，未识别 {m['unparsed']}）  {fs} → {ls}  [{fm}] {lv}")
    print(f"\n共 {total_read} 条事件，过滤后 {len(ev)} 条"
          + (f"，时间窗 {ev[0]['ts'].strftime('%H:%M:%S')} → {ev[-1]['ts'].strftime('%H:%M:%S')}" if ev else ""))
    if not ev:
        print("（没有事件落在当前过滤条件里；放宽 --from/--to/--level/--grep 再试）")
        return
    if not a.no_timeline:
        shown = ev[:a.limit] if a.limit else ev
        print(f"\n## 合并时间线（{len(shown)}/{len(ev)} 条）")
        day = None
        for e in shown:
            d = e["ts"].date()
            if d != day:
                print(f" ---- {d} ----")
                day = d
            t = e["ts"].strftime("%H:%M:%S.") + f"{e['ts'].microsecond // 1000:03d}"
            lv = ("»" if e["cont"] else e["level"] or "-")
            print(f" {t} {col(e['alias'], e['alias'])} {lv:<5} {e['msg'][:a.width]}")
        if a.limit and len(ev) > a.limit:
            print(f" …… 还有 {len(ev) - a.limit} 条，去掉 --limit 或缩小时间窗查看")
    print(f"\n## 事件密度（每 {hstep(step)}，{len(bk)} 桶）")
    mx = max(b["count"] for b in bk)
    for b in bk:
        bar = "█" * max(1, round(b["count"] / mx * 40)) if b["count"] else ""
        err = f"  err {b['errors']}" if b["errors"] else ""
        print(f" {b['start'].strftime('%m-%d %H:%M:%S')} {b['count']:>6} {bar}{err}")
    if bs:
        print("\n## 错误爆发点")
        for b in bs:
            print(f" {b['start'].strftime('%m-%d %H:%M:%S')} 起 {hstep(step)} 内 ERROR/FATAL {b['errors']} 条"
                  f"（全程均值 {b['baseline']}）")
            if b["sample"]:
                print(f"    示例 {b['sample']}")
    else:
        print("\n## 错误爆发点\n （没有明显突增：ERROR/FATAL 数未超过均值 + 2σ 且未达 3 条）")


if __name__ == "__main__":
    main()
