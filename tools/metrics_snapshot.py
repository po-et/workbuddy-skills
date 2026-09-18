#!/usr/bin/env python3
"""SkillHub 每日指标快照。

对 docs/submission-checklist.md 里「## SkillHub」小节记录的所有 slug 逐个查询，把能拿到的
下载/安装/收藏/评论数、是否进入搜索索引、AI 评测分写成一行，追加到
docs/metrics/skillhub-YYYY-MM-DD.csv，并在终端打印本次汇总。

=== 字段来源与边界（2026-09-18 实测确认，详见 docs/metrics/README.md）===

本脚本直接 GET 三个 SkillHub 公开只读接口，均为 GET、不写数据、不带任何鉴权头：

  1. {host}/api/v1/skills/{slug}             -> skill.stats.{downloads,installs,stars,comments,versions}
  2. {host}/api/v1/search?q={slug}&limit=N   -> 用来判断 slug 是否已进入搜索索引（本仓库文档里
     对"可见性/上架"的操作定义：见 docs/skillhub-growth.md "82 个已发布技能 81 个进入搜索索引（=上架）"）
  3. {host}/api/v1/skills/{slug}/evaluation  -> AI 质量评测（5 维度 × 子项 1-5 分），非全部技能都有

这三个接口地址不是猜的，是读 `~/.skillhub/skills_store_cli.py`（已安装的 skillhub CLI 本体）
源码确认的：CLI 的 `skill reports` / `skill evaluation` / `search` 子命令内部分别调用这三个
接口，但 `skill reports` 只透出安全扫描字段、`search` 的 fetch_remote_search_results() 会把
downloads/installs/stars 等字段过滤掉只留 slug/name/description/summary/version/namespace——
所以本脚本绕开这两处过滤，直接调用同一批接口拿完整响应，而不是新发现或绕过鉴权的接口。
CLI 自身对这三个接口发的请求也不带 Authorization（见 cli_request_headers()，只有 User-Agent /
client-id / caller 提示头），本脚本原样复现同款请求头，因此既没有伪造鉴权头，也没有用登录
令牌以外的方式访问——这三个接口对 CLI 而言本来就是匿名可读的。

已确认**拿不到**的：
  - 查看量/浏览量（views）：以上三个接口、以及 `skill rankings --type {hot,newest,...}` 的
    完整字段列表里都没有任何 views/pv/impressions 字段。
  - 单独的 1-5 「用户评分」：不存在。`stats.stars` 是收藏计数（整数，非 1-5），evaluation 里的
    分数是 AI 质量评测分（5 维度、每维度多个子项 1-5 分），二者都不是"用户打的星级评分"。

用法：
  python3 tools/metrics_snapshot.py                        # 查 checklist 里全部 slug
  python3 tools/metrics_snapshot.py --slugs a b c          # 只查指定几个（可逗号或空格分隔）
  python3 tools/metrics_snapshot.py --out docs/metrics/x.csv
  python3 tools/metrics_snapshot.py --limit 5              # 调试：只跑前 5 个
"""
import argparse
import csv
import datetime
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLIST = ROOT / "docs" / "submission-checklist.md"
DEFAULT_HOST = "https://api.skillhub.cn"
# 真实 handle（displayName 是 user_a3a2e24a，两者都由 API 确认，非推测）
DEFAULT_NAMESPACE = "indiv-captain"
USER_AGENT = "workbuddy-skills-metrics-snapshot/1.0 (+read-only)"

SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
NUMID_RE = re.compile(r"^\d{4,8}$")
EMBEDDED_ID_RE = re.compile(r"skillId\D{0,3}(\d{4,8})")

EVAL_DIMENSIONS = ["adaptability", "convention", "effectiveness", "reliability", "trust"]

FIELDNAMES = [
    "date", "queried_at", "slug", "skill_id", "skill_id_source", "found", "http_status",
    "display_name", "category", "created_at", "updated_at", "latest_version",
    "claim_state", "verified", "owner_handle",
    "downloads", "installs", "stars", "comments", "versions_count",
    "in_search_index", "search_checked",
    "has_evaluation", "eval_skill_id",
    "eval_adaptability", "eval_convention", "eval_effectiveness", "eval_reliability", "eval_trust",
    "eval_overall",
    "error",
]


def extract_slugs_from_checklist(path: Path):
    """解析 submission-checklist.md「## SkillHub」小节之后的表格行，取 slug 与（若有）skillId。

    只看该小节之后的内容：文件前半部分是「开放平台」(open.workbuddy.cn) 的技能/连接器/专家表格，
    用的是完全不同的 ID 体系（os_ / oc_ / oe_ 前缀），不是本脚本要查的 SkillHub（skillhub.cn）。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## SkillHub"):
            start = i
            break
    if start is None:
        raise SystemExit(f"未在 {path} 找到 '## SkillHub' 分节标题，无法定位 SkillHub 表格范围")

    found = {}  # slug -> skillId|None，保留出现顺序
    for line in lines[start:]:
        s = line.strip()
        if not s.startswith("|") or not s.endswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0].lower() == "slug":
            continue
        if all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
            continue
        first = cells[0]
        slug_candidates = [t.strip() for t in re.split(r"\s*/\s*", first) if t.strip()]
        slug_candidates = [t for t in slug_candidates if SLUG_RE.match(t)]
        if not slug_candidates:
            continue
        skill_id = None
        for c in cells[1:]:
            if NUMID_RE.match(c):
                skill_id = c
                break
        if skill_id is None:
            m = EMBEDDED_ID_RE.search(" | ".join(cells))
            if m:
                skill_id = m.group(1)
        for slug in slug_candidates:
            if slug not in found or (found.get(slug) is None and skill_id):
                found[slug] = skill_id
    return found


_last_request_ts = [0.0]


def _looks_rate_limited(body):
    if not isinstance(body, dict):
        return False
    text = json.dumps(body, ensure_ascii=False)
    return "频率过高" in text or "rate limit" in text.lower() or "too many" in text.lower()


def _throttled_get_json(url: str, min_interval: float, timeout: float = 10.0):
    """GET url，返回 (status_code, body_dict, exception_str|None)。

    不附带任何鉴权头/Cookie，只发 Accept + User-Agent —— 与 skillhub CLI 对这几个只读接口的
    请求方式一致（见文件头注释）。调用前保证与上一次请求间隔 >= min_interval 秒。
    """
    wait = min_interval - (time.monotonic() - _last_request_ts[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            status = resp.status
            body = json.loads(data) if data else {}
        _last_request_ts[0] = time.monotonic()
        return status, body, None
    except urllib.error.HTTPError as e:
        _last_request_ts[0] = time.monotonic()
        try:
            body = json.loads(e.read())
        except Exception:
            body = {}
        return e.code, body, None
    except Exception as e:
        _last_request_ts[0] = time.monotonic()
        return 0, {}, str(e)


def _get_with_retry(url, sleep_s, retries):
    status, body, err = 0, {}, None
    for attempt in range(retries + 1):
        status, body, err = _throttled_get_json(url, sleep_s)
        transient = (status == 0) or (status == 429) or _looks_rate_limited(body)
        if not transient:
            break
        if attempt < retries:
            time.sleep(sleep_s * (attempt + 2))
    return status, body, err


def _ms_to_iso(ms):
    if not ms:
        return ""
    try:
        dt = datetime.datetime.fromtimestamp(int(ms) / 1000, tz=datetime.timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(statistics.mean(vals), 2) if vals else None


def query_skill(slug: str, host: str, namespace: str, sleep_s: float, retries: int):
    row = {k: "" for k in FIELDNAMES}
    row["slug"] = slug
    row["found"] = False
    row["search_checked"] = False
    row["has_evaluation"] = False

    # 1) 详情接口：downloads/installs/stars/comments/versions 的唯一来源
    detail_url = f"{host}/api/v1/skills/{urllib.parse.quote(slug, safe='')}"
    if namespace:
        detail_url += "?" + urllib.parse.urlencode({"namespace": namespace})
    status, body, err = _get_with_retry(detail_url, sleep_s, retries)
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
        row["claim_state"] = skill.get("claim_state") or ""
        row["verified"] = skill.get("verified")
        row["downloads"] = stats.get("downloads")
        row["installs"] = stats.get("installs")
        row["stars"] = stats.get("stars")
        row["comments"] = stats.get("comments")
        row["versions_count"] = stats.get("versions")
        row["owner_handle"] = ns.get("handle") or ""
    elif status == 404:
        row["error"] = (body or {}).get("error") or "not found"
    else:
        row["error"] = row["error"] or (body or {}).get("error") or f"HTTP {status}"

    if not row["found"]:
        return row  # 详情都拿不到（404/超时），后面两个接口大概率同样查不到，省配额不再查

    # 2) 搜索接口（未过滤版）：判断是否已进入搜索索引 = 本仓库对"可见性/上架"的操作定义
    search_url = f"{host}/api/v1/search?" + urllib.parse.urlencode({"q": slug, "limit": 5})
    s_status, s_body, _s_err = _get_with_retry(search_url, sleep_s, retries)
    if s_status == 200 and isinstance(s_body, dict):
        row["search_checked"] = True
        results = s_body.get("results") or []
        hit = any(
            isinstance(r, dict)
            and (r.get("slug") or "").strip() == slug
            and ((r.get("namespace") or {}).get("handle") or "") == namespace
            for r in results
        )
        row["in_search_index"] = hit
    else:
        row["search_checked"] = False
        row["in_search_index"] = ""

    # 3) AI 评测接口：质量分（不是下载/浏览量，但属于任务要求的"评分字段"）
    eval_url = f"{host}/api/v1/skills/{urllib.parse.quote(slug, safe='')}/evaluation"
    if namespace:
        eval_url += "?" + urllib.parse.urlencode({"namespace": namespace})
    e_status, e_body, _e_err = _get_with_retry(eval_url, sleep_s, retries)
    # 注意：这里直接调用的是原始接口，响应体本身就是评测对象（dimensions/skillId/summary 在顶层）。
    # skillhub CLI 的 `skill evaluation --json` 会把它包一层 {"slug":..., "evaluation": {...}}，
    # 那是 CLI 自己的输出格式（build_skill_evaluation_output()），不是接口原始形状。
    if e_status == 200 and isinstance(e_body, dict) and isinstance(e_body.get("dimensions"), dict):
        ev = e_body
        row["has_evaluation"] = True
        row["eval_skill_id"] = ev.get("skillId") or ""
        all_scores = []
        for d in EVAL_DIMENSIONS:
            dim = (ev.get("dimensions") or {}).get(d) or {}
            items = dim.get("items") or {}
            scores = [it.get("score") for it in items.values() if isinstance(it, dict)]
            m = _mean(scores)
            row[f"eval_{d}"] = m if m is not None else ""
            all_scores.extend(scores)
        # 网页上显示的"AI 评分"星级，实测等于全部子项分数的平铺均值（用 commit-message-cc 核对：
        # 15 个子项平铺均值 = 4.5，页面显示星级也是 4.5；不是先按维度取均值再对 5 个维度取均值），
        # 所以这里复现同一种算法，而不是自创一种加权方式。
        row["eval_overall"] = _mean(all_scores) if all_scores else ""
    # 404 "evaluation not found" -> 该技能还没被评测，has_evaluation 保持 False，不算错误

    return row


def num(v):
    try:
        return int(v)
    except Exception:
        return 0


def print_summary(rows, out_path, elapsed):
    n = len(rows)
    found = [r for r in rows if r["found"]]
    not_found = [r for r in rows if not r["found"]]
    visible = [r for r in found if r.get("in_search_index") is True]
    search_unchecked = [r for r in found if not r.get("search_checked")]
    evaluated = [r for r in found if r.get("has_evaluation")]

    total_downloads = sum(num(r.get("downloads")) for r in found)
    total_installs = sum(num(r.get("installs")) for r in found)
    total_stars = sum(num(r.get("stars")) for r in found)
    total_comments = sum(num(r.get("comments")) for r in found)

    print("\n================ SkillHub 指标快照汇总 ================")
    print(f"输出文件: {out_path}")
    print(f"耗时: {elapsed:.0f}s")
    print(f"查询 slug 总数: {n}；详情可查到: {len(found)}；查不到(404/异常): {len(not_found)}")
    print(f"已进入搜索索引（可见/上架）: {len(visible)}/{len(found)}"
          f"（另有 {len(search_unchecked)} 个搜索检查本身失败，未计入判定）")
    print(f"下载量合计: {total_downloads}  安装量合计: {total_installs}  "
          f"收藏(stars)合计: {total_stars}  评论合计: {total_comments}")
    print(f"有 AI 评测报告: {len(evaluated)}/{len(found)}")
    if evaluated:
        overalls = [r["eval_overall"] for r in evaluated if r.get("eval_overall") not in ("", None)]
        avg_overall = _mean(overalls)
        print(f"AI 评测总分（全部子项打平取均值，口径同页面「AI 评分」星级）平均: {avg_overall}")

    if not_found:
        print("\n查不到详情的 slug（可能从未成功创建 / 平台侧已变化，具体原因未确认，需人工核实）:")
        for r in not_found:
            print(f"  - {r['slug']}  (http={r['http_status']}, error={r['error']})")

    top = sorted(found, key=lambda r: num(r.get("downloads")), reverse=True)[:10]
    print("\nTop 10（按下载量）:")
    for r in top:
        print(f"  downloads={num(r.get('downloads')):>6}  installs={num(r.get('installs')):<4}  "
              f"stars={num(r.get('stars')):<3}  {r['slug']:42s} {r.get('display_name', '')}")

    zero_dl = [r for r in found if num(r.get("downloads")) == 0]
    print(f"\n下载量为 0 的技能数: {len(zero_dl)}/{len(found)}")
    print("=========================================================\n")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--slugs", nargs="*", help="只查这些 slug（可逗号或空格分隔），默认查 checklist 里的全部")
    ap.add_argument("--checklist", default=str(DEFAULT_CHECKLIST), help="submission-checklist.md 路径")
    ap.add_argument("--out", default=None, help="输出 CSV 路径，默认 docs/metrics/skillhub-<今天>.csv")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    ap.add_argument("--sleep", type=float, default=1.3, help="相邻两次 HTTP 请求的最小间隔秒数（默认 1.3）")
    ap.add_argument("--retries", type=int, default=2, help="单次请求失败/疑似限流时的重试次数")
    ap.add_argument("--limit", type=int, default=0, help="调试用：只跑前 N 个 slug")
    args = ap.parse_args()

    if args.sleep < 1.3:
        print(f"警告：--sleep {args.sleep} 低于建议的 1.3 秒，可能触发平台限频", file=sys.stderr)

    checklist_path = Path(args.checklist)
    doc_slugs = extract_slugs_from_checklist(checklist_path)

    if args.slugs:
        wanted = []
        for token in args.slugs:
            wanted.extend(t.strip() for t in token.split(",") if t.strip())
        slugs = wanted
    else:
        slugs = list(doc_slugs.keys())

    if args.limit:
        slugs = slugs[: args.limit]

    if not slugs:
        raise SystemExit("没有要查询的 slug")

    today = datetime.date.today().isoformat()
    out_path = Path(args.out) if args.out else ROOT / "docs" / "metrics" / f"skillhub-{today}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not out_path.exists()
    rows_out = []
    print(f"共 {len(slugs)} 个 slug，开始查询（每次 HTTP 请求间隔 >= {args.sleep}s，"
          f"每个 slug 最多 3 次请求：详情/搜索/评测）…", file=sys.stderr)
    t0 = time.time()
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        for i, slug in enumerate(slugs, 1):
            row = query_skill(slug, args.host, args.namespace, args.sleep, args.retries)
            doc_id = doc_slugs.get(slug)
            if doc_id:
                row["skill_id"] = doc_id
                row["skill_id_source"] = "doc"
            elif row.get("eval_skill_id"):
                row["skill_id"] = row["eval_skill_id"]
                row["skill_id_source"] = "evaluation"
            else:
                row["skill_id"] = ""
                row["skill_id_source"] = ""
            row["date"] = today
            row["queried_at"] = datetime.datetime.now().astimezone().isoformat()
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
            f.flush()
            rows_out.append(row)
            if i % 10 == 0 or i == len(slugs):
                print(f"  {i}/{len(slugs)}  最近: {slug}  found={row['found']}  "
                      f"downloads={row.get('downloads')}", file=sys.stderr)

    elapsed = time.time() - t0
    print_summary(rows_out, out_path, elapsed)


if __name__ == "__main__":
    main()
