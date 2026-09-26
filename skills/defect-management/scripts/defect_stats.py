#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缺陷导出 CSV 的复盘统计：按严重度 / 模块 / 状态 / 存活天数分布，输出每周复盘摘要（Markdown 或 JSON）。

列名可配置：默认按常见中英文列名自动匹配（TAPD 等工具的实际列名以你所在项目的配置为准），
匹配不到或匹配错了，用 --map 角色=列名 指定。可用角色：
  id title severity priority status module created resolved closed owner reporter reopen
只有 status 是必需的；缺 created 就不算存活天数，缺 severity 就不出严重度分布。

用法：
  python3 defect_stats.py bugs.csv --today 2026-09-26
  python3 defect_stats.py bugs.csv --map severity=严重级别 --map module=所属模块 --since 2026-09-19 --until 2026-09-25
  python3 defect_stats.py bugs.csv --closed-status 已上线 --format json -o review.json

退出码：0 成功；1 参数错误或缺必需列；2 文件读写错误；130 用户中断。
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import tempfile

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_INT = 0, 1, 2, 130

ROLE_ALIASES = {
    "id": ["id", "编号", "缺陷id", "缺陷编号", "bugid", "bug_id", "key", "问题编号", "单号"],
    "title": ["标题", "缺陷标题", "名称", "title", "summary", "概要", "主题", "缺陷名称"],
    "severity": ["严重程度", "严重级别", "严重性", "严重等级", "severity"],
    "priority": ["优先级", "priority"],
    "status": ["状态", "缺陷状态", "status", "state"],
    "module": ["模块", "所属模块", "功能模块", "组件", "module", "component", "components"],
    "created": ["创建时间", "创建日期", "提交时间", "报告时间", "发现时间", "created", "created_at", "createdat", "创建于"],
    "resolved": ["解决时间", "修复时间", "resolved", "resolved_at", "resolutiondate", "解决日期"],
    "closed": ["关闭时间", "关闭日期", "closed", "closed_at"],
    "owner": ["处理人", "当前处理人", "负责人", "经办人", "指派给", "开发人员", "assignee", "owner"],
    "reporter": ["创建人", "报告人", "提交人", "发现人", "reporter", "创建者"],
    "reopen": ["重新打开次数", "重开次数", "reopen", "reopencount", "reopen_count", "reopened"],
}
ROLES = list(ROLE_ALIASES)

STATUS_DEFAULTS = {
    "closed": "已关闭 关闭 closed done 已完成 完成 已验证 verified",
    "resolved": "已解决 resolved 已修复 fixed 待验证 待回归 已处理",
    "invalid": "已拒绝 拒绝 rejected 无效 invalid 重复 duplicate 不予修复 不修复 wontfix won't_fix 设计如此 "
               "bydesign by_design 无法重现 无法复现 cannotreproduce",
    "suspended": "挂起 延期 暂缓 postponed deferred suspended",
    "open": "新 新建 new open 打开 接受 已接受 处理中 进行中 inprogress in_progress 重新打开 reopened reopen "
            "待处理 已分配 assigned 待修复 未处理",
}
STATUS_LABEL = {"open": "处理中/待处理", "resolved": "已解决待验证", "suspended": "挂起/延期",
                "closed": "已关闭", "invalid": "无效/重复/拒绝", "unknown": "未识别状态"}

SEVERITY_RANK = [
    ("致命 阻塞 blocker fatal s0 紧急", 0),
    ("严重 critical s1 高 high", 1),
    ("一般 主要 major normal s2 中 medium", 2),
    ("轻微 次要 minor s3 低 low", 3),
    ("建议 提示 trivial suggestion enhancement s4", 4),
]
AGE_BUCKETS = [(3, "0–3 天"), (7, "4–7 天"), (14, "8–14 天"), (30, "15–30 天"), (90, "31–90 天"), (None, ">90 天")]


class UserError(Exception):
    def __init__(self, message, code=EXIT_ARGS):
        Exception.__init__(self, message)
        self.code = code


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_ARGS)


def norm(s):
    return re.sub(r"[\s_\-/（）()]", "", str(s or "")).lower()


def words(s):
    """内置词表：空格分隔（多词状态在表里用下划线连写）。"""
    return set(norm(w) for w in re.split(r"[\s,，、]+", s or "") if w.strip())


def user_words(s):
    """用户传入的列表：只按逗号/顿号分隔，允许「Ready for QA」这种带空格的值。"""
    return set(norm(w) for w in re.split(r"[,，、]+", s or "") if w.strip())


# ---------------------------------------------------------------- 读取

def read_csv(path, encoding=None):
    try:
        raw = open(path, "rb").read()
    except FileNotFoundError:
        raise UserError("找不到文件：%s" % path, EXIT_FILE)
    except OSError as exc:
        raise UserError("读取失败：%s（%s）" % (path, exc), EXIT_FILE)
    text, enc = None, encoding
    if encoding:
        try:
            text = raw.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise UserError("按 %s 解码失败：%s" % (encoding, exc), EXIT_FILE)
    else:
        for enc in ("utf-8-sig", "gb18030"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise UserError("无法识别编码，请用 --encoding 指定（常见 utf-8 / gb18030）", EXIT_FILE)
    if not text.strip():
        raise UserError("文件是空的：%s" % path, EXIT_FILE)
    sample = text[:4096]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        delim = ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise UserError("只有表头没有数据行（或文件不是 CSV）：%s" % path, EXIT_FILE)
    header = [h.strip() for h in rows[0]]
    seen = {}
    for i, h in enumerate(header):
        if h in seen:
            seen[h] += 1
            header[i] = "%s_%d" % (h, seen[h])
        else:
            seen[h] = 1
    data = []
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        data.append(dict(zip(header, [c.strip() for c in r[:len(header)]])))
    return header, data, enc.replace("-sig", ""), delim


def map_columns(header, overrides):
    mapping = {}
    by_norm = {norm(h): h for h in header}
    for role, col in overrides.items():
        if col not in header:
            raise UserError("--map %s=%s：CSV 里没有这一列。现有列：%s" % (role, col, "、".join(header)))
        mapping[role] = col
    used = set(mapping.values())
    for role in ROLES:
        if role in mapping:
            continue
        for alias in ROLE_ALIASES[role]:
            col = by_norm.get(norm(alias))
            if col and col not in used:
                mapping[role] = col
                used.add(col)
                break
    return mapping


def parse_date(value):
    v = (value or "").strip()
    if not v:
        return None
    m = re.match(r"^(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", v) or re.match(r"^(\d{4})(\d{2})(\d{2})$", v)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if re.match(r"^\d{5}(\.\d+)?$", v) and 30000 <= float(v) <= 60000:  # Excel 序列日期
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(float(v)))
    return None


def severity_rank(value):
    n = norm(value)
    for names, rank in SEVERITY_RANK:
        if n in words(names):
            return rank
    m = re.match(r"^(?:s|p|sev|level)?(\d)$", n)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- 统计

def classify_status(value, sets):
    n = norm(value)
    for cat in ("closed", "invalid", "resolved", "suspended", "open"):
        if n in sets[cat]:
            return cat
    return "unknown"


def bucket(days):
    for limit, label in AGE_BUCKETS:
        if limit is None or days <= limit:
            return label
    return AGE_BUCKETS[-1][1]


def pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def percentile(values, q):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


def analyze(data, mapping, args, sets):
    g = lambda row, role: row.get(mapping[role], "").strip() if role in mapping else ""
    today = args.today
    issues = {"no_created": 0, "bad_date": 0, "unknown_status": {}, "unknown_severity": {}, "dup_ids": [],
              "dup_removed": 0}
    counts = {}
    for row in data:
        bid = g(row, "id")
        if bid:
            counts[bid] = counts.get(bid, 0) + 1
    issues["dup_ids"] = sorted(k for k, v in counts.items() if v > 1)
    if issues["dup_ids"] and not args.keep_duplicates:
        kept, seen = [], set()
        for row in data:
            bid = g(row, "id")
            if bid and bid in seen:
                issues["dup_removed"] += 1
                continue
            seen.add(bid)
            kept.append(row)
        data = kept
    total = len(data)
    high_names = user_words(args.high_severity) if args.high_severity else None
    bugs = []
    for row in data:
        status_raw = g(row, "status")
        cat = classify_status(status_raw, sets)
        if cat == "unknown":
            key = status_raw or "（空）"
            issues["unknown_status"][key] = issues["unknown_status"].get(key, 0) + 1
        sev = g(row, "severity") or "（未填）"
        rank = severity_rank(sev) if sev != "（未填）" else None
        if "severity" in mapping and rank is None and sev != "（未填）":
            issues["unknown_severity"][sev] = issues["unknown_severity"].get(sev, 0) + 1
        high = (norm(sev) in high_names) if high_names is not None else (rank is not None and rank <= 1)
        created_raw = g(row, "created")
        created = parse_date(created_raw)
        if "created" in mapping:
            if not created_raw:
                issues["no_created"] += 1
            elif created is None:
                issues["bad_date"] += 1
        done_date = parse_date(g(row, "resolved")) or parse_date(g(row, "closed"))
        closed_date = parse_date(g(row, "closed")) or (done_date if cat in ("closed", "invalid") else None)
        bid = g(row, "id")
        reopen_raw = g(row, "reopen")
        reopened = False
        if reopen_raw:
            reopened = reopen_raw.lower() in ("是", "yes", "true", "y") or (reopen_raw.isdigit() and int(reopen_raw) > 0)
        active = cat in ("open", "resolved", "suspended", "unknown")
        bugs.append({
            "id": bid, "title": g(row, "title"), "status": status_raw or "（空）", "cat": cat, "severity": sev,
            "rank": rank, "high": high, "module": g(row, "module") or "（未填）", "owner": g(row, "owner") or "（未指派）",
            "created": created, "done": done_date, "closed": closed_date, "reopened": reopened, "active": active,
            "age": (today - created).days if (created and active) else None,
            "cycle": (done_date - created).days if (created and done_date and cat == "closed" and done_date >= created)
            else None,
        })
    def dist(key, subset):
        out = {}
        for b in subset:
            out[b[key]] = out.get(b[key], 0) + 1
        return out

    active = [b for b in bugs if b["active"]]
    sev_all, sev_active = dist("severity", bugs), dist("severity", active)
    sev_rows = sorted(sev_all, key=lambda s: (severity_rank(s) if severity_rank(s) is not None else 99, s))
    mod_all, mod_active = dist("module", bugs), dist("module", active)
    mod_high = dist("module", [b for b in active if b["high"]])
    mod_rows = sorted(mod_all, key=lambda m: (-mod_all[m], m))
    status_rows = sorted(dist("status", bugs).items(), key=lambda kv: (-kv[1], kv[0]))
    cat_counts = dist("cat", bugs)
    ages = [b["age"] for b in active if b["age"] is not None]
    age_dist = {}
    for a in ages:
        age_dist[bucket(a)] = age_dist.get(bucket(a), 0) + 1
    cycles = [b["cycle"] for b in bugs if b["cycle"] is not None]
    stale = sorted([b for b in active if b["high"] and b["age"] is not None and b["age"] > args.stale_days],
                   key=lambda b: (-b["age"], b["id"]))
    owner_active = sorted(dist("owner", active).items(), key=lambda kv: (-kv[1], kv[0]))

    period = None
    if args.since or args.until:
        lo = args.since or dt.date.min
        hi = args.until or today
        new = [b for b in bugs if b["created"] and lo <= b["created"] <= hi]
        closed = [b for b in bugs if b["closed"] and lo <= b["closed"] <= hi]
        period = {"since": str(args.since or "不限"), "until": str(hi), "new": len(new),
                  "new_high": sum(1 for b in new if b["high"]), "closed": len(closed),
                  "closed_invalid": sum(1 for b in closed if b["cat"] == "invalid"),
                  "net": len(new) - len(closed), "closed_basis": "关闭时间" if "closed" in mapping else
                  ("解决时间（无关闭时间列）" if "resolved" in mapping else "无时间列，无法统计")}

    return {
        "total": total, "active": len(active), "cat_counts": cat_counts,
        "invalid_rate": pct(cat_counts.get("invalid", 0), total),
        "reopen_rate": pct(sum(1 for b in bugs if b["reopened"]), total) if "reopen" in mapping else None,
        "severity": [{"value": s, "total": sev_all[s], "active": sev_active.get(s, 0), "share": pct(sev_all[s], total)}
                     for s in sev_rows] if "severity" in mapping else [],
        "modules": [{"value": m, "total": mod_all[m], "active": mod_active.get(m, 0), "active_high": mod_high.get(m, 0),
                     "share": pct(mod_all[m], total)} for m in mod_rows],
        "status": [{"value": s, "count": c, "category": STATUS_LABEL[classify_status(s if s != "（空）" else "", sets)]}
                   for s, c in status_rows],
        "age": [{"bucket": label, "count": age_dist.get(label, 0)} for _, label in AGE_BUCKETS] if ages else [],
        "age_known": len(ages),
        "cycle": {"count": len(cycles), "median": percentile(cycles, 0.5), "p90": percentile(cycles, 0.9),
                  "mean": round(sum(cycles) / len(cycles), 1) if cycles else None},
        "stale_high": [{"id": b["id"], "title": b["title"], "severity": b["severity"], "module": b["module"],
                        "owner": b["owner"], "age": b["age"], "status": b["status"]} for b in stale],
        "owners_active": [{"owner": o, "active": c} for o, c in owner_active],
        "period": period,
        "issues": issues,
    }


# ---------------------------------------------------------------- 输出

def cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_md(r, mapping, meta, args):
    L = ["# 缺陷复盘摘要", ""]
    L.append("- 数据：%s（编码 %s，参与统计 %d 行）；统计日 %s；长期未关闭阈值 %d 天" % (
        meta["source"], meta["encoding"], r["total"], args.today, args.stale_days))
    L.append("- 列对应：" + "；".join("%s←「%s」" % (k, v) for k, v in sorted(mapping.items())))
    missing = [k for k in ("severity", "module", "created", "closed", "resolved") if k not in mapping]
    if missing:
        L.append("- 未找到的列（相关统计跳过，可用 --map 指定）：%s" % "、".join(missing))
    cc = r["cat_counts"]
    L += ["", "## 一、总体", ""]
    L.append("共 %d 个缺陷：未关闭 %d（待处理/处理中 %d、已解决待验证 %d、挂起 %d、未识别状态 %d），已关闭 %d，无效/重复/拒绝 %d（占 %.1f%%）。" % (
        r["total"], r["active"], cc.get("open", 0), cc.get("resolved", 0), cc.get("suspended", 0), cc.get("unknown", 0),
        cc.get("closed", 0), cc.get("invalid", 0), r["invalid_rate"]))
    if r["reopen_rate"] is not None:
        L.append("重开过的缺陷占 %.1f%%。" % r["reopen_rate"])
    p = r["period"]
    if p:
        L.append("区间 %s ~ %s：新增 %d（其中高严重度 %d），关闭 %d（其中无效/重复/拒绝 %d；按%s），净增 %+d。" % (
            p["since"], p["until"], p["new"], p["new_high"], p["closed"], p["closed_invalid"], p["closed_basis"],
            p["net"]))
    if r["severity"]:
        L += ["", "## 二、严重度分布", "", "| 严重度 | 总数 | 占比 | 未关闭 |", "|---|---|---|---|"]
        L += ["| %s | %d | %.1f%% | %d |" % (cell(s["value"]), s["total"], s["share"], s["active"]) for s in r["severity"]]
    top = r["modules"][:args.top]
    L += ["", "## 三、模块分布（前 %d）" % len(top), "", "| 模块 | 总数 | 占比 | 未关闭 | 未关闭中高严重度 |", "|---|---|---|---|---|"]
    L += ["| %s | %d | %.1f%% | %d | %d |" % (cell(m["value"]), m["total"], m["share"], m["active"], m["active_high"]) for m in top]
    rest = r["modules"][args.top:]
    if rest:
        L.append("| 其余 %d 个模块 | %d | %.1f%% | %d | %d |" % (len(rest), sum(m["total"] for m in rest),
                                                            sum(m["share"] for m in rest), sum(m["active"] for m in rest),
                                                            sum(m["active_high"] for m in rest)))
    L += ["", "## 四、状态分布", "", "| 状态 | 数量 | 归类 |", "|---|---|---|"]
    L += ["| %s | %d | %s |" % (cell(s["value"]), s["count"], s["category"]) for s in r["status"]]
    L += ["", "## 五、未关闭缺陷存活天数", ""]
    if r["age"]:
        L += ["| 存活 | 数量 |", "|---|---|"] + ["| %s | %d |" % (a["bucket"], a["count"]) for a in r["age"]]
        L.append("")
        L.append("存活天数 = 统计日 − 创建日期；共 %d 个未关闭缺陷有创建日期。" % r["age_known"])
    else:
        L.append("没有可用的创建日期，跳过。")
    c = r["cycle"]
    L += ["", "## 六、已关闭缺陷的解决周期", ""]
    if c["count"]:
        L.append("%d 个（不含无效/重复/拒绝）：中位数 %s 天，平均 %s 天，P90 %s 天（创建 → 解决时间；没有解决时间则用关闭时间；按日期计，同日为 0）。" % (
            c["count"], c["median"], c["mean"], c["p90"]))
    else:
        L.append("没有同时具备创建与解决/关闭时间的缺陷，跳过。")
    L += ["", "## 七、需要关注", ""]
    if r["stale_high"]:
        L.append("未关闭且存活超过 %d 天的高严重度缺陷 %d 个：" % (args.stale_days, len(r["stale_high"])))
        L += ["", "| ID | 标题 | 严重度 | 模块 | 处理人 | 存活天数 | 状态 |", "|---|---|---|---|---|---|---|"]
        L += ["| %s | %s | %s | %s | %s | %d | %s |" % (cell(b["id"] or "—"), cell(b["title"] or "—"), cell(b["severity"]),
                                                    cell(b["module"]), cell(b["owner"]), b["age"], cell(b["status"]))
              for b in r["stale_high"][:20]]
    else:
        L.append("没有存活超过 %d 天的高严重度未关闭缺陷。" % args.stale_days)
    if r["modules"]:
        m = r["modules"][0]
        L.append("")
        L.append("缺陷最多的模块：%s（%d 个，占 %.1f%%，未关闭 %d）。" % (m["value"], m["total"], m["share"], m["active"]))
    if r["owners_active"]:
        L.append("未关闭缺陷按处理人（用于排负载，不用于排名）：" + "，".join(
            "%s %d" % (o["owner"], o["active"]) for o in r["owners_active"][:args.top]) + "。")
    iss = r["issues"]
    L += ["", "## 八、数据问题（需确认）", ""]
    notes = []
    if iss["unknown_status"]:
        notes.append("未识别的状态（按未关闭计）：" + "、".join("%s×%d" % kv for kv in sorted(iss["unknown_status"].items()))
                     + "；用 --closed-status / --open-status 等补充归类")
    if iss["unknown_severity"]:
        notes.append("未识别的严重度取值（排在最后，不计入高严重度）：" + "、".join(
            "%s×%d" % kv for kv in sorted(iss["unknown_severity"].items())) + "；可用 --high-severity 指定")
    if iss["no_created"]:
        notes.append("%d 行缺创建时间" % iss["no_created"])
    if iss["bad_date"]:
        notes.append("%d 行创建时间无法解析（支持 2026-09-26、2026/9/26、2026年9月26日、Excel 序列日期）" % iss["bad_date"])
    if iss["dup_ids"]:
        notes.append("重复的 ID：%s（可能重复导出）；%s" % ("、".join(iss["dup_ids"][:10]),
                     "已去掉 %d 行，只保留首次出现" % iss["dup_removed"] if iss["dup_removed"]
                     else "按 --keep-duplicates 保留，统计里会重复计数"))
    L += ["- " + n for n in notes] or ["（无）"]
    return "\n".join(L) + "\n"


def atomic_write(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=folder)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError as exc:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise UserError("写文件失败：%s（%s）" % (path, exc), EXIT_FILE)


def parse_day(value, flag):
    if value is None:
        return None
    d = parse_date(value)
    if d is None:
        raise UserError("%s 的日期写法不对：%r（用 2026-09-26）" % (flag, value))
    return d


def main(argv=None):
    ap = ArgParser(description="缺陷导出 CSV 复盘统计：严重度 / 模块 / 状态 / 存活天数分布 + 复盘摘要")
    ap.add_argument("path", help="缺陷工具导出的 CSV（Excel 请先另存为 CSV）")
    ap.add_argument("--map", action="append", default=[], metavar="角色=列名",
                    help="手动指定列，如 severity=严重级别；角色：" + " ".join(ROLES))
    ap.add_argument("--today", help="统计日，默认今天；复盘报告建议显式给出，保证可复现")
    ap.add_argument("--since", help="区间开始日（统计新增/关闭），如 2026-09-19")
    ap.add_argument("--until", help="区间结束日，默认统计日")
    ap.add_argument("--stale-days", type=int, default=7, help="高严重度缺陷存活超过几天算长期未关闭，默认 7")
    ap.add_argument("--high-severity", help="哪些严重度算「高」，逗号分隔；默认按内置等级取前两档（如 致命、严重）")
    for cat in ("closed", "resolved", "invalid", "suspended", "open"):
        ap.add_argument("--%s-status" % cat, default="", help="追加归为「%s」的状态值，逗号分隔" % STATUS_LABEL[cat])
    ap.add_argument("--top", type=int, default=10, help="模块/处理人最多列几项，默认 10")
    ap.add_argument("--keep-duplicates", action="store_true", help="保留重复 ID 的行（默认只保留首次出现）")
    ap.add_argument("--encoding", help="文件编码；默认先试 utf-8 再试 gb18030")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("-o", "--output", help="写入文件（先写临时文件再替换）；不给就打印")
    args = ap.parse_args(argv)
    try:
        args.today = parse_day(args.today, "--today") or dt.date.today()
        args.since = parse_day(args.since, "--since")
        args.until = parse_day(args.until, "--until")
        if args.since and args.until and args.since > args.until:
            raise UserError("--since 晚于 --until")
        if args.stale_days < 0 or args.top < 1:
            raise UserError("--stale-days 不能为负，--top 至少为 1")
        overrides = {}
        for item in args.map:
            if "=" not in item:
                raise UserError("--map 的写法是 角色=列名，收到：%r" % item)
            role, col = [x.strip() for x in item.split("=", 1)]
            if role not in ROLE_ALIASES:
                raise UserError("未知角色 %r，可用：%s" % (role, " ".join(ROLES)))
            overrides[role] = col
        sets = {}
        for cat in STATUS_DEFAULTS:
            sets[cat] = words(STATUS_DEFAULTS[cat]) | user_words(getattr(args, "%s_status" % cat))
        header, data, enc, delim = read_csv(args.path, args.encoding)
        mapping = map_columns(header, overrides)
        if "status" not in mapping:
            raise UserError("找不到「状态」列。CSV 现有列：%s。请用 --map status=列名 指定" % "、".join(header))
        result = analyze(data, mapping, args, sets)
        meta = {"source": os.path.basename(args.path), "encoding": enc, "delimiter": delim}
        if args.format == "json":
            doc = {"meta": meta, "today": str(args.today), "mapping": mapping, "result": result}
            text = json.dumps(doc, ensure_ascii=False, indent=2, default=str) + "\n"
        else:
            text = render_md(result, mapping, meta, args)
        if args.output:
            atomic_write(args.output, text)
            sys.stderr.write("已写入 %s\n" % args.output)
        else:
            sys.stdout.write(text)
        return EXIT_OK
    except UserError as exc:
        sys.stderr.write("错误：%s\n" % exc)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(EXIT_INT)
