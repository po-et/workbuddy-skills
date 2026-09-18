#!/usr/bin/env python3
"""慢查询日志摘要：把 MySQL / PostgreSQL 慢查询日志按 SQL 指纹聚合，按总耗时排序输出 Top N，并给出优化提示。纯标准库。

用法：
  python3 slow_query_digest.py /var/log/mysql/slow.log --top 10
  python3 slow_query_digest.py pg.log --format postgres --json
  zcat slow.log.*.gz | python3 slow_query_digest.py -            # 读 stdin
  python3 slow_query_digest.py slow.log --strict                 # 有 high 提示则退出码 1
"""
import argparse
import collections
import json
import re
import sys

# ---------------------------------------------------------------- 解析

MY_TIME = re.compile(r"^#\s*Time:\s*(.+?)\s*$")
MY_STAT = re.compile(r"^#\s*Query_time:\s*([\d.]+)\s+Lock_time:\s*([\d.]+)"
                     r"(?:\s+Rows_sent:\s*(\d+))?(?:\s+Rows_examined:\s*(\d+))?")
PG_LINE = re.compile(r"duration:\s*([\d.]+)\s*ms\s+(?:statement|execute\s[^:]*|parse\s[^:]*|bind\s[^:]*):\s*(.*)", re.I)
PG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}[ T][\d:.]+)")
PG_HEAD = re.compile(r"^\d{4}-\d{2}-\d{2}[ T][\d:.]+|^\[\d+\]|^\d{4}-\d{2}-\d{2}\s")
NOISE = re.compile(r"^(?:SET\s+timestamp\s*=|SET\s+@@|use\s+\S+\s*;?\s*$|/\*!|Tcp\s+port|Time\s+Id\s+Command|"
                   r"/\S*mysqld\S*,\s*Version|#\s*administrator\s+command)", re.I)


def _flush(sql_lines):
    sql = " ".join(x.strip() for x in sql_lines if x.strip())
    return sql.strip()


def parse_mysql(lines):
    """产出 dict(sql, ms, lock_ms, sent, examined, ts)。"""
    ts, cur, sql = None, None, []
    for raw in lines:
        line = raw.rstrip("\n")
        m = MY_TIME.match(line)
        if m:
            if cur and sql:
                cur["sql"] = _flush(sql); yield cur
                cur, sql = None, []
            ts = m.group(1)
            continue
        if line.startswith("#"):
            m = MY_STAT.match(line)
            if m:
                if cur and sql:
                    cur["sql"] = _flush(sql); yield cur
                sql = []
                cur = {"ms": float(m.group(1)) * 1000, "lock_ms": float(m.group(2)) * 1000,
                       "sent": int(m.group(3) or 0), "examined": int(m.group(4) or 0), "ts": ts}
            continue
        if NOISE.match(line.strip()):
            continue
        if cur is not None and line.strip():
            sql.append(line)
    if cur and sql:
        cur["sql"] = _flush(sql); yield cur


def parse_postgres(lines):
    cur, extra = None, []
    for raw in lines:
        line = raw.rstrip("\n")
        m = PG_LINE.search(line)
        if m:
            if cur:
                cur["sql"] = _flush([cur["sql"]] + extra); yield cur
            t = PG_TS.match(line)
            cur = {"ms": float(m.group(1)), "lock_ms": 0.0, "sent": 0, "examined": 0,
                   "ts": t.group(1) if t else None, "sql": m.group(2)}
            extra = []
            continue
        if cur is not None and line[:1] in ("\t", " ") and not PG_HEAD.match(line.strip()):
            extra.append(line)
            continue
        if cur is not None and (PG_HEAD.match(line) or not line.strip()):
            cur["sql"] = _flush([cur["sql"]] + extra); yield cur
            cur, extra = None, []
    if cur:
        cur["sql"] = _flush([cur["sql"]] + extra); yield cur


def detect(text):
    if re.search(r"^#\s*Query_time:", text, re.M):
        return "mysql"
    if PG_LINE.search(text):
        return "postgres"
    return "mysql"


# ---------------------------------------------------------------- 指纹

STR_LIT = re.compile(r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?:--|#)[^\n]*")
NUM = re.compile(r"\b0x[0-9a-f]+\b|(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
IN_LIST = re.compile(r"\bin\s*\(\s*\?(?:\s*,\s*\?)*\s*\)")
VALUES = re.compile(r"\bvalues\s*\(\s*\?(?:\s*,\s*\?)*\s*\)(?:\s*,\s*\(\s*\?(?:\s*,\s*\?)*\s*\))*")


def fingerprint(sql):
    s = BLOCK_COMMENT.sub(" ", sql)
    s = LINE_COMMENT.sub(" ", s)
    s = s.lower()
    s = STR_LIT.sub("?", s)
    s = NUM.sub("?", s)
    s = IN_LIST.sub("in (?)", s)
    s = VALUES.sub("values (?)", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(";").strip()
    return s


# ---------------------------------------------------------------- 提示规则

def hints(fp, sample, st):
    out = []
    verb = fp.split(" ", 1)[0] if fp else ""
    avg_sent = st["sent"] / st["n"]
    avg_exam = st["examined"] / st["n"]
    if avg_exam >= 1000 and avg_exam / max(avg_sent, 1) >= 100:
        out.append(("high", f"扫描 {avg_exam:,.0f} 行只返回 {avg_sent:,.1f} 行（比值 {avg_exam / max(avg_sent, 1):,.0f}:1）",
                    "几乎可以断定没走对索引；用 EXPLAIN 看 type 是否为 ALL/index，按 WHERE 与 ORDER BY 列建联合索引"))
    if verb in ("select", "update", "delete") and " where " not in f" {fp} " and " where" not in fp:
        lv = "high" if verb in ("update", "delete") else "warn"
        out.append((lv, f"{verb.upper()} 没有 WHERE 条件",
                    "全表操作；SELECT 至少加 LIMIT，UPDATE/DELETE 必须带主键或索引条件并分批执行"))
    if re.search(r"select\s+\*", fp):
        out.append(("warn", "SELECT * 取回全部列",
                    "只列出真正需要的列，减少回表与网络传输，也更容易走覆盖索引"))
    if re.search(r"like\s+'%", sample, re.I):
        out.append(("warn", "LIKE 以 % 开头", "前导通配符用不上 B+ 树索引；改成前缀匹配或换全文/搜索引擎"))
    if " order by " in fp and " limit " not in fp:
        out.append(("info", "ORDER BY 没有 LIMIT", "确认是否需要全量排序；大结果集排序会落磁盘临时表"))
    if re.search(r"\blimit\s+\?\s*,\s*\?", fp) or re.search(r"\blimit\s+\?\s+offset\s+\?", fp):
        out.append(("info", "深分页 LIMIT offset", "offset 大时会丢弃前 N 行；改成按上次最大主键游标翻页"))
    if st["lock_ms"] / st["n"] >= 100:
        out.append(("warn", f"平均锁等待 {st['lock_ms'] / st['n']:.0f}ms", "存在锁竞争；缩短事务、避免长事务里做慢查询或外部调用"))
    if re.search(r"\b(count\(\*\)|count\(\?\))", fp) and " where " not in fp:
        out.append(("info", "无条件 COUNT(*)", "大表全表计数很贵；用估算值或维护计数表"))
    if " join " in fp and st["examined"] / st["n"] >= 100000:
        out.append(("info", "JOIN 扫描行数大", "确认驱动表是小表、被驱动表的关联列有索引"))
    return [{"level": lv, "issue": msg, "fix": fix} for lv, msg, fix in out]


# ---------------------------------------------------------------- 主流程

def digest(entries, top, min_count, sort_key):
    agg = {}
    for e in entries:
        sql = (e.get("sql") or "").strip()
        if not sql or NOISE.match(sql):
            continue
        fp = fingerprint(sql)
        if not fp:
            continue
        st = agg.setdefault(fp, {"n": 0, "ms": 0.0, "max_ms": 0.0, "lock_ms": 0.0, "sent": 0,
                                 "examined": 0, "first": None, "last": None, "sample": sql})
        st["n"] += 1
        st["ms"] += e["ms"]
        st["max_ms"] = max(st["max_ms"], e["ms"])
        st["lock_ms"] += e.get("lock_ms", 0.0)
        st["sent"] += e.get("sent", 0)
        st["examined"] += e.get("examined", 0)
        if e["ms"] >= st["max_ms"]:
            st["sample"] = sql
        ts = e.get("ts")
        if ts:
            st["first"] = ts if st["first"] is None or ts < st["first"] else st["first"]
            st["last"] = ts if st["last"] is None or ts > st["last"] else st["last"]
    total_ms = sum(s["ms"] for s in agg.values()) or 1.0
    rows = []
    for fp, st in agg.items():
        if st["n"] < min_count:
            continue
        rows.append({
            "fingerprint": fp, "count": st["n"], "total_ms": round(st["ms"], 1),
            "share": round(st["ms"] / total_ms * 100, 1), "avg_ms": round(st["ms"] / st["n"], 1),
            "max_ms": round(st["max_ms"], 1), "avg_lock_ms": round(st["lock_ms"] / st["n"], 1),
            "avg_rows_sent": round(st["sent"] / st["n"], 1), "avg_rows_examined": round(st["examined"] / st["n"], 1),
            "first_seen": st["first"], "last_seen": st["last"], "sample": st["sample"],
            "hints": hints(fp, st["sample"], st)})
    key = {"total": lambda r: -r["total_ms"], "avg": lambda r: -r["avg_ms"],
           "max": lambda r: -r["max_ms"], "count": lambda r: -r["count"]}[sort_key]
    rows.sort(key=key)
    return rows[:top], len(agg), total_ms


def read_all(files):
    for f in files:
        fh = sys.stdin if f == "-" else open(f, encoding="utf-8", errors="replace")
        try:
            yield from fh.readlines()
        finally:
            if f != "-":
                fh.close()


def main():
    ap = argparse.ArgumentParser(description="慢查询日志摘要（MySQL / PostgreSQL）")
    ap.add_argument("files", nargs="*", default=["-"], help="日志文件；- 表示 stdin")
    ap.add_argument("--format", choices=["auto", "mysql", "postgres"], default="auto")
    ap.add_argument("--top", type=int, default=10, help="输出前 N 个指纹（默认 10）")
    ap.add_argument("--min-count", type=int, default=1, help="出现次数低于该值的指纹不输出")
    ap.add_argument("--sort", choices=["total", "avg", "max", "count"], default="total")
    ap.add_argument("--sample-len", type=int, default=300, help="示例原句截断长度")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="存在 high 提示则退出码 1（CI 门禁）")
    a = ap.parse_args()

    lines = list(read_all(a.files or ["-"]))
    fmt = a.format if a.format != "auto" else detect("".join(lines[:4000]))
    entries = list(parse_mysql(lines) if fmt == "mysql" else parse_postgres(lines))
    rows, n_fp, total_ms = digest(entries, a.top, a.min_count, a.sort)

    high = sum(1 for r in rows for h in r["hints"] if h["level"] == "high")
    if a.json:
        print(json.dumps({"format": fmt, "queries": len(entries), "fingerprints": n_fp,
                          "total_ms": round(total_ms, 1), "high": high, "top": rows},
                         ensure_ascii=False, indent=2))
        sys.exit(1 if (a.strict and high) else 0)

    if not entries:
        print(f"没有解析到慢查询（按 {fmt} 格式解析 {len(lines)} 行）。"
              "MySQL 需要 slow_query_log=ON 且日志含 # Query_time 块；"
              "PostgreSQL 需要 log_min_duration_statement 打开（日志含 duration ... ms statement 行）。")
        sys.exit(0)
    print(f"格式 {fmt} · 慢查询 {len(entries)} 条 · 指纹 {n_fp} 个 · 总耗时 {total_ms / 1000:.1f}s")
    dist = collections.Counter((r["fingerprint"].split(" ", 1) or [""])[0] for r in rows)
    print("语句类型：" + "，".join(f"{k or '?'} {v}" for k, v in dist.most_common()))
    print(f"\n## Top {len(rows)}（按{ {'total': '总耗时', 'avg': '平均耗时', 'max': '最大耗时', 'count': '次数'}[a.sort] }排序）")
    for i, r in enumerate(rows, 1):
        print(f"\n#{i}  总耗时 {r['total_ms'] / 1000:.2f}s（{r['share']}%）  次数 {r['count']}  "
              f"平均 {r['avg_ms']:.0f}ms  最大 {r['max_ms']:.0f}ms")
        if r["avg_rows_examined"] or r["avg_rows_sent"]:
            print(f"    平均扫描 {r['avg_rows_examined']:,.0f} 行 / 返回 {r['avg_rows_sent']:,.1f} 行"
                  + (f"  平均锁等待 {r['avg_lock_ms']:.0f}ms" if r["avg_lock_ms"] else ""))
        if r["first_seen"] or r["last_seen"]:
            print(f"    首次 {r['first_seen'] or '-'}  末次 {r['last_seen'] or '-'}")
        print(f"    指纹 {r['fingerprint'][:a.sample_len]}")
        print(f"    示例 {r['sample'][:a.sample_len]}")
        for h in r["hints"]:
            print(f"    [{h['level']}] {h['issue']}")
            print(f"        → {h['fix']}")
    print(f"\n合计 high 提示 {high} 条。先治总耗时占比最高的前 3 个指纹，"
          "一般能吃掉大部分数据库负载；改完用同一份脚本再跑一次对比。")
    sys.exit(1 if (a.strict and high) else 0)


if __name__ == "__main__":
    main()
