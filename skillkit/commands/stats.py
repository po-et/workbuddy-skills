"""skillkit stats —— 查询已上架技能的真实指标。

为什么要自己发请求，而不是用官方 CLI：
`skillhub search` 的客户端函数会把结果里的 downloads / installs / stars **过滤掉**，
只留 slug/name/description/summary/version/namespace；`skill reports` 拿到了完整响应体，
却只打印安全扫描字段。也就是说这些数字本来就在响应里，是 CLI 打印前筛掉的。
本命令直接 GET 同一批只读接口，请求头与 CLI 对这几个接口的请求方式一致（不带任何鉴权头）：

  1. GET {host}/api/v1/skills/{slug}              -> skill.stats.{downloads,installs,stars,comments,versions}
  2. GET {host}/api/v1/search?q={slug}            -> 判断是否已进入搜索索引（= 上架可见）
  3. GET {host}/api/v1/skills/{slug}/evaluation   -> AI 质量评测（5 维度 × 子项 1–5 分），未评测时 404

已确认**拿不到**的：浏览量/PV（三个接口、排行榜字段表、网页详情页都没有这个字段），
以及「用户 1–5 星评分」（不存在；stars 是收藏计数，evaluation 是 AI 打的质量分）。

这些接口不在任何公开 API 文档里，是从已安装 CLI 的实现里读出来的，
平台没有对字段和稳定性做任何承诺 —— 大面积报错时先怀疑接口变了。
"""

from __future__ import print_function

import csv
import datetime
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .. import __version__, output, rules

HELP = "查询上架技能的真实指标（downloads / stars / 评测分，走详情接口）"

FIELDNAMES = [
    "queried_at", "slug", "found", "http_status", "display_name", "category",
    "latest_version", "owner_handle", "created_at", "updated_at",
    "downloads", "installs", "stars", "comments", "versions_count",
    "in_search_index", "has_evaluation", "eval_overall", "error",
] + ["eval_%s" % d for d in rules.STATS_EVAL_DIMENSIONS]

_last_request = [0.0]


def add_parser(subparsers):
    p = subparsers.add_parser(
        "stats",
        help=HELP,
        description="按 slug 查询 SkillHub 上的真实指标。只读、不带鉴权头、不写任何数据。",
        epilog="例：skillkit stats dockerfile-check json-config-diff --namespace your-handle",
    )
    p.add_argument("slugs", nargs="+", help="要查询的 slug（可多个，也可用逗号分隔）")
    p.add_argument("--namespace", default="", help="账号 handle；不填则按全局 slug 查")
    p.add_argument("--host", default=rules.STATS_HOST_DEFAULT,
                   help="接口域名，默认 %s" % rules.STATS_HOST_DEFAULT)
    p.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    p.add_argument("--csv", default="", dest="csv_out", help="同时把结果追加写入这个 CSV 文件")
    p.add_argument("--no-search", action="store_true", dest="no_search", help="跳过搜索索引检查，少发一次请求")
    p.add_argument("--no-eval", action="store_true", dest="no_eval", help="跳过 AI 评测查询，少发一次请求")
    p.add_argument("--sleep", type=float, default=rules.STATS_SLEEP_MIN,
                   help="相邻两次请求的最小间隔秒数，默认 %.1f（更低容易被读限频）" % rules.STATS_SLEEP_MIN)
    p.add_argument("--retries", type=int, default=2, help="疑似限流/网络失败时的重试次数，默认 2")
    p.add_argument("--timeout", type=float, default=10.0, help="单次请求超时秒数，默认 10")
    return p


# ---------------------------------------------------------------- HTTP

def http_get_json(url, timeout=10.0):
    # type: (str, float) -> Tuple[int, Any, Optional[str]]
    """GET url，返回 (状态码, 响应体, 异常字符串或 None)。

    只发 Accept 与 User-Agent，不带 Cookie / Authorization —— 与官方 CLI 对这几个
    只读接口的请求方式一致。测试里 monkeypatch 这个函数即可完全离线。
    """
    req = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json",
                 "User-Agent": rules.STATS_USER_AGENT.format(version=__version__)},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:  # noqa: BLE001 - 错误响应体不是 JSON 是常态
            body = {}
        return exc.code, body, None
    except Exception as exc:  # noqa: BLE001 - 网络层什么都可能抛
        return 0, {}, str(exc)


def _looks_rate_limited(body):
    if not isinstance(body, dict):
        return False
    text = json.dumps(body, ensure_ascii=False).lower()
    return "频率过高" in text or "rate limit" in text or "too many" in text


def _get(url, sleep_s, retries, timeout):
    # type: (str, float, int, float) -> Tuple[int, Any, Optional[str]]
    """带节流与重试的 GET。"""
    status, body, err = 0, {}, None
    for attempt in range(retries + 1):
        wait = sleep_s - (time.monotonic() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        status, body, err = http_get_json(url, timeout)
        _last_request[0] = time.monotonic()
        if not (status == 0 or status == 429 or _looks_rate_limited(body)):
            break
        if attempt < retries:
            time.sleep(sleep_s * (attempt + 2))
    return status, body, err


# ---------------------------------------------------------------- 查询

def _ms_to_iso(ms):
    if not ms:
        return ""
    try:
        dt = datetime.datetime.fromtimestamp(int(ms) / 1000, tz=datetime.timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return round(statistics.mean(nums), 2) if nums else None


def query_slug(slug, host, namespace="", sleep_s=rules.STATS_SLEEP_MIN, retries=2,
               timeout=10.0, want_search=True, want_eval=True):
    # type: (str, str, str, float, int, float, bool, bool) -> Dict[str, Any]
    """查一个 slug。返回一行扁平的指标字典。"""
    row = dict((k, "") for k in FIELDNAMES)
    row["slug"] = slug
    row["found"] = False
    row["in_search_index"] = ""
    row["has_evaluation"] = False

    qs = ("?" + urllib.parse.urlencode({"namespace": namespace})) if namespace else ""
    detail = "%s/api/v1/skills/%s%s" % (host, urllib.parse.quote(slug, safe=""), qs)
    status, body, err = _get(detail, sleep_s, retries, timeout)
    row["http_status"] = status
    if err:
        row["error"] = err
    if status == 200 and isinstance(body, dict):
        row["found"] = True
        skill = body.get("skill") or {}
        stats = skill.get("stats") or {}
        latest = body.get("latestVersion") or {}
        ns = body.get("namespace") or {}
        row["display_name"] = skill.get("displayName") or ""
        row["category"] = skill.get("category") or ""
        row["created_at"] = _ms_to_iso(skill.get("createdAt"))
        row["updated_at"] = _ms_to_iso(skill.get("updatedAt"))
        row["latest_version"] = latest.get("version") or ""
        row["owner_handle"] = ns.get("handle") or ""
        for key, field in (("downloads", "downloads"), ("installs", "installs"),
                           ("stars", "stars"), ("comments", "comments"),
                           ("versions", "versions_count")):
            row[field] = stats.get(key)
    elif status == 404:
        row["error"] = (body or {}).get("error") or "not found"
    else:
        row["error"] = row["error"] or (body or {}).get("error") or "HTTP %s" % status

    if not row["found"]:
        # 详情都拿不到，后面两个接口大概率同样查不到，别浪费请求
        return row

    if want_search:
        url = "%s/api/v1/search?%s" % (host, urllib.parse.urlencode({"q": slug, "limit": 5}))
        s_status, s_body, _ = _get(url, sleep_s, retries, timeout)
        if s_status == 200 and isinstance(s_body, dict):
            results = s_body.get("results") or []
            row["in_search_index"] = any(
                isinstance(r, dict)
                and (r.get("slug") or "").strip() == slug
                and (not namespace or ((r.get("namespace") or {}).get("handle") or "") == namespace)
                for r in results
            )

    if want_eval:
        url = "%s/api/v1/skills/%s/evaluation%s" % (host, urllib.parse.quote(slug, safe=""), qs)
        e_status, e_body, _ = _get(url, sleep_s, retries, timeout)
        if e_status == 200 and isinstance(e_body, dict) and isinstance(e_body.get("dimensions"), dict):
            row["has_evaluation"] = True
            all_scores = []  # type: List[Any]
            for dim_name in rules.STATS_EVAL_DIMENSIONS:
                dim = (e_body.get("dimensions") or {}).get(dim_name) or {}
                items = dim.get("items") or {}
                scores = [it.get("score") for it in items.values() if isinstance(it, dict)]
                mean = _mean(scores)
                row["eval_%s" % dim_name] = mean if mean is not None else ""
                all_scores.extend(scores)
            # 网页顶部的「AI 评分」星级 = 全部子项打平的算术均值（已用真实技能核对过），
            # 不是先按维度取均值再平均 —— 这里复现同一种算法，不自创加权。
            row["eval_overall"] = _mean(all_scores) if all_scores else ""
    return row


# ---------------------------------------------------------------- 入口

def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def run(args):
    slugs = []
    for token in args.slugs:
        slugs.extend(t.strip() for t in token.split(",") if t.strip())
    if not slugs:
        print("没有要查询的 slug", file=sys.stderr)
        return 2
    if args.sleep < rules.STATS_SLEEP_MIN:
        print("警告：--sleep %.2f 低于建议的 %.1f 秒，可能触发平台读限频"
              % (args.sleep, rules.STATS_SLEEP_MIN), file=sys.stderr)

    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    rows = []
    for slug in slugs:
        row = query_slug(slug, args.host, args.namespace, args.sleep, args.retries,
                         args.timeout, not args.no_search, not args.no_eval)
        row["queried_at"] = now
        rows.append(row)

    if args.csv_out:
        _write_csv(args.csv_out, rows)

    if args.as_json:
        output.emit_json({"host": args.host, "namespace": args.namespace, "skills": rows})
    else:
        _render(rows, args)
    return 1 if any(not r["found"] for r in rows) else 0


def _write_csv(path, rows):
    import os

    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(dict((k, row.get(k, "")) for k in FIELDNAMES))


def _render(rows, args):
    print("%-38s %9s %9s %7s %9s %7s %s"
          % ("slug", "downloads", "installs", "stars", "comments", "AI分", "搜索索引"))
    print(output.hr("-", 96))
    for r in rows:
        if not r["found"]:
            print("%-38s  查不到（http=%s, %s）" % (r["slug"], r["http_status"], r["error"]))
            continue
        index = {True: "已收录", False: "未收录", "": "未检查"}[r["in_search_index"]]
        print("%-38s %9s %9s %7s %9s %7s %s"
              % (r["slug"][:38], _num(r["downloads"]), _num(r["installs"]),
                 _num(r["stars"]), _num(r["comments"]),
                 r["eval_overall"] if r["eval_overall"] != "" else "-", index))
    found = [r for r in rows if r["found"]]
    print(output.hr("-", 96))
    print("查到 %d/%d；下载合计 %d，收藏合计 %d"
          % (len(found), len(rows),
             sum(_num(r["downloads"]) for r in found),
             sum(_num(r["stars"]) for r in found)))
    if args.csv_out:
        print("已追加写入 %s" % args.csv_out)
    print("说明：downloads 是平台抓取与榜单曝光的计数，不是用户行为（实测：全员约 +4/天，在榜技能另加数百/天）；"
          "真实采用看 installs；stars 是收藏计数，不是 1–5 星评分；浏览量平台不提供。")
