#!/usr/bin/env python3
"""采集工单数据。适配器模式，provider 由 config.yaml 决定。

内置 provider:
    file    —— 读本地导出的 JSON/CSV。**内网系统一律走这个**，不要把内网地址写进仓库。
    github  —— GitHub Issues API
    gitlab  —— GitLab Issues API（支持自建实例，但 base_url 放在本地 config，不入库）
    jira    —— Jira Cloud/Server search API

新增内部系统：实现一个 fetch_<name>(cfg, since, until) -> list[dict]，注册进 PROVIDERS。
返回字段契约见 normalize()。

用法:
    python3 collect_issues.py --config config.yaml --out out/issues.json
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

FIELDS = ["id", "title", "status", "assignee", "created", "updated",
          "closed", "url", "labels", "reopened_count"]


def normalize(raw):
    """统一字段契约。缺失一律 None，不要填假值。"""
    out = {k: raw.get(k) for k in FIELDS}
    out["labels"] = out["labels"] or []
    out["reopened_count"] = out["reopened_count"] or 0
    return out


def load_config(path):
    """极简 YAML 子集解析器，避免引入 pyyaml 依赖。

    支持: key: value / 嵌套映射 / 列表项 '- x' / # 注释。
    需要完整 YAML 时 pip install pyyaml 即可自动走 yaml.safe_load。
    """
    try:
        import yaml  # noqa: PLC0415
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass

    root = {}
    # stack 元素: (indent, node, last_key)
    stack = [[-1, root, None]]

    with open(path, encoding="utf-8") as f:
        for raw in f:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip())
            line = raw.split("#")[0].rstrip()
            s = line.strip()
            if not s:
                continue

            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
            node, last_key = stack[-1][1], stack[-1][2]

            if s.startswith("- "):
                if last_key is not None:
                    node.setdefault(last_key, [])
                    if isinstance(node[last_key], list):
                        node[last_key].append(_coerce(s[2:].strip()))
                continue

            if ":" not in s:
                continue
            k, _, v = s.partition(":")
            k, v = k.strip(), v.strip()

            if v == "":
                child = {}
                node[k] = child
                stack[-1][2] = k
                stack.append([indent, child, None])
            else:
                node[k] = _coerce(v)
                stack[-1][2] = k
    return root


def _coerce(v):
    v = v.strip().strip("'\"")
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def http_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {url}: {e.read().decode()[:300]}") from e


def env(cfg, key):
    """凭证只从环境变量读，绝不从配置文件读。"""
    name = cfg.get(key)
    if not name:
        raise RuntimeError(f"config 缺少 {key}（应填环境变量名，不是凭证本身）")
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"环境变量 {name} 未设置")
    return val


def fetch_file(cfg, since, until):
    path = cfg["path"]
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return [normalize(x) for x in json.load(f)]
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [normalize(row) for row in csv.DictReader(f)]


def fetch_github(cfg, since, until):
    repo = cfg["repo"]
    tok = env(cfg, "token_env")
    url = (f"https://api.github.com/repos/{repo}/issues"
           f"?state=all&since={since}T00:00:00Z&per_page=100")
    data = http_json(url, {"Authorization": f"Bearer {tok}",
                           "Accept": "application/vnd.github+json"})
    return [normalize({
        "id": f"#{i['number']}", "title": i["title"], "status": i["state"],
        "assignee": (i.get("assignee") or {}).get("login"),
        "created": i["created_at"], "updated": i["updated_at"],
        "closed": i.get("closed_at"), "url": i["html_url"],
        "labels": [l["name"] for l in i.get("labels", [])],
    }) for i in data if "pull_request" not in i]


def fetch_gitlab(cfg, since, until):
    base = cfg["base_url"].rstrip("/")
    pid = urllib.parse.quote_plus(str(cfg["project"]))
    tok = env(cfg, "token_env")
    url = f"{base}/api/v4/projects/{pid}/issues?updated_after={since}T00:00:00Z&per_page=100"
    data = http_json(url, {"PRIVATE-TOKEN": tok})
    return [normalize({
        "id": f"#{i['iid']}", "title": i["title"], "status": i["state"],
        "assignee": (i.get("assignee") or {}).get("name"),
        "created": i["created_at"], "updated": i["updated_at"],
        "closed": i.get("closed_at"), "url": i["web_url"],
        "labels": i.get("labels", []),
    }) for i in data]


def fetch_jira(cfg, since, until):
    base = cfg["base_url"].rstrip("/")
    user, tok = cfg["user"], env(cfg, "token_env")
    jql = cfg.get("jql") or f'project = {cfg["project"]} AND updated >= "{since}"'
    url = (f"{base}/rest/api/2/search?jql={urllib.parse.quote(jql)}"
           f"&maxResults=100&fields=summary,status,assignee,created,updated,resolutiondate,labels")
    auth = base64.b64encode(f"{user}:{tok}".encode()).decode()
    data = http_json(url, {"Authorization": f"Basic {auth}"})
    return [normalize({
        "id": i["key"], "title": i["fields"]["summary"],
        "status": i["fields"]["status"]["name"],
        "assignee": (i["fields"].get("assignee") or {}).get("displayName"),
        "created": i["fields"]["created"], "updated": i["fields"]["updated"],
        "closed": i["fields"].get("resolutiondate"),
        "url": f"{base}/browse/{i['key']}", "labels": i["fields"].get("labels", []),
    }) for i in data.get("issues", [])]


PROVIDERS = {"file": fetch_file, "github": fetch_github,
             "gitlab": fetch_gitlab, "jira": fetch_jira}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--out", default="out/issues.json")
    a = ap.parse_args()

    cfg = load_config(a.config)
    provider = cfg.get("provider")
    if provider not in PROVIDERS:
        sys.exit(f"未知 provider: {provider}；可选 {', '.join(PROVIDERS)}")

    since = a.since or cfg.get("since")
    until = a.until or cfg.get("until")
    if not since:
        sys.exit("缺少 --since 或 config.since")

    try:
        issues = PROVIDERS[provider](cfg.get(provider, cfg), since, until)
    except Exception as e:                          # noqa: BLE001
        sys.exit(f"采集失败: {e}")

    payload = {
        "provider": provider,
        "window": {"since": since, "until": until},
        "summary": {
            "total": len(issues),
            "closed": sum(1 for i in issues if i.get("closed")),
            "open": sum(1 for i in issues if not i.get("closed")),
        },
        "issues": issues,
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    s = payload["summary"]
    print(f"✓ {a.out}: {s['total']} 工单（已关闭 {s['closed']} / 未关闭 {s['open']}）")


if __name__ == "__main__":
    main()
