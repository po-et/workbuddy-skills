#!/usr/bin/env python3
"""采集 GitHub 上的变更事件：releases / deployments / 合并的 PR。

需要环境变量 GITHUB_TOKEN（只读权限即可）。

用法:
    python3 collect_changes.py --repo owner/name \
        --since 2026-09-14T13:50:00Z --until 2026-09-14T14:40:00Z \
        --out out/changes.json
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
# 变更类型风险权重，供第 4 步排序参考（配置生效快、回滚记录少，风险最高）
RISK = {"config": 3, "release": 2, "deployment": 2, "pull_request": 2, "commit": 1}


def parse_ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def gh(path, token, params=None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {path}: {e.read().decode()[:200]}") from e


def in_window(ts, since, until):
    t = parse_ts(ts)
    return bool(t and since <= t <= until)


def collect(repo, since, until, token):
    events, errors = [], []

    def add(kind, ts, title, url, extra=None):
        events.append({
            "repo": repo, "kind": kind, "time": ts, "title": title,
            "url": url, "risk_weight": RISK.get(kind, 1), **(extra or {}),
        })

    try:
        for r in gh(f"/repos/{repo}/releases", token, {"per_page": 50}):
            if in_window(r.get("published_at"), since, until):
                add("release", r["published_at"],
                    f"发布 {r.get('tag_name') or r.get('name')}", r["html_url"],
                    {"author": (r.get("author") or {}).get("login")})
    except Exception as e:                                   # noqa: BLE001
        errors.append({"source": "releases", "error": str(e)})

    try:
        for d in gh(f"/repos/{repo}/deployments", token, {"per_page": 50}):
            if in_window(d.get("created_at"), since, until):
                add("deployment", d["created_at"],
                    f"部署到 {d.get('environment', '?')}",
                    d.get("url", ""), {"author": (d.get("creator") or {}).get("login"),
                                       "ref": d.get("ref")})
    except Exception as e:                                   # noqa: BLE001
        errors.append({"source": "deployments", "error": str(e)})

    try:
        prs = gh(f"/repos/{repo}/pulls", token,
                 {"state": "closed", "sort": "updated", "direction": "desc",
                  "per_page": 50})
        for p in prs:
            if p.get("merged_at") and in_window(p["merged_at"], since, until):
                add("pull_request", p["merged_at"],
                    f"合并 PR #{p['number']}: {p['title']}", p["html_url"],
                    {"author": (p.get("user") or {}).get("login")})
    except Exception as e:                                   # noqa: BLE001
        errors.append({"source": "pulls", "error": str(e)})

    return events, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", required=True, help="owner/name，可重复")
    ap.add_argument("--since", required=True, help="ISO8601，如 2026-09-14T13:50:00Z")
    ap.add_argument("--until", required=True)
    ap.add_argument("--token-env", default="GITHUB_TOKEN")
    ap.add_argument("--out", default="out/changes.json")
    a = ap.parse_args()

    token = os.environ.get(a.token_env)
    if not token:
        sys.exit(f"环境变量 {a.token_env} 未设置。只需 repo 只读权限。")

    since, until = parse_ts(a.since), parse_ts(a.until)
    if not since or not until:
        sys.exit("--since / --until 需为 ISO8601，例如 2026-09-14T13:50:00Z")
    if since >= until:
        sys.exit("--since 必须早于 --until")

    all_events, all_errors = [], []
    for repo in a.repo:
        ev, err = collect(repo, since, until, token)
        all_events += ev
        all_errors += [{**e, "repo": repo} for e in err]

    all_events.sort(key=lambda e: e["time"])
    payload = {
        "window": {"since": a.since, "until": a.until},
        "repos": a.repo,
        "errors": all_errors,
        "summary": {"total": len(all_events),
                    "by_kind": {k: sum(1 for e in all_events if e["kind"] == k)
                                for k in {e["kind"] for e in all_events}}},
        "events": all_events,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✓ {a.out}: {len(all_events)} 个变更事件 {payload['summary']['by_kind'] or ''}")
    for e in all_errors:
        print(f"[warn] {e['repo']}/{e['source']} 采集失败: {e['error']}", file=sys.stderr)
    if all_errors:
        print("[warn] 上述数据源缺失必须写进简报的「数据缺口」一节", file=sys.stderr)


if __name__ == "__main__":
    main()
