#!/usr/bin/env python3
"""接口差分测试：同一批请求打到环境 A 与 B，逐字段对比响应。零依赖。

用例文件 cases.json：
[{"name": "订单详情", "method": "GET", "path": "/api/orders/1", "headers": {}, "body": null, "path_b": null}]
用法：
  API_DIFF_HEADERS='{"Authorization":"Bearer <token>"}' \
  python3 api_diff.py --allow-external --a https://staging.example.com --b https://prod.example.com --cases cases.json \
      --ignore "updated_at,request_id,trace_id,^ts$" --md out/api-diff.md --out out/api-diff.json
默认只访问回环地址、只发 GET/HEAD，不跟随重定向。
外部端点需 --allow-external；写方法需 --allow-write。
凭证只从环境变量 API_DIFF_HEADERS 读，不写进用例文件。
"""
import argparse
from decimal import Decimal
import hashlib
import ipaddress
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

REPORT_SECRETS = []


class InputError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _strict_json(text, *, precise=False):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON number")

    def number(value):
        result = Decimal(value) if precise else float(value)
        if not (result.is_finite() if precise else math.isfinite(result)):
            raise ValueError("unsupported non-finite JSON number")
        return result

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_float=number)


def request(base, case, headers, timeout, path_key="path"):
    path = case.get(path_key) or case["path"]
    url = base.rstrip("/") + path
    h = {"User-Agent": "api-diff/0.1", **headers, **(case.get("headers") or {})}
    body = case.get("body")
    data = None
    if body is not None:
        data = json.dumps(body).encode() if not isinstance(body, str) else body.encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=case.get("method", "GET").upper(), headers=h)
    t0 = time.monotonic()
    # A redirect must be reviewed as another endpoint, especially with auth headers.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read(); status = r.status; ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw = e.read(); status = e.code; ctype = e.headers.get("Content-Type", "")
    except Exception as e:
        # Exception text can contain a server's response or credential-bearing URL.
        return {"status": None, "error": f"request failed ({type(e).__name__})",
                "ms": round((time.monotonic() - t0) * 1000)}
    ms = round((time.monotonic() - t0) * 1000)
    body_hash = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    parsed = None
    is_json = "json" in ctype.lower() or text.lstrip().startswith(("{", "["))
    if not raw and (req.get_method() == "HEAD" or status in (204, 205)):
        is_json = False
    if is_json:
        try:
            parsed = _strict_json(raw.decode("utf-8"), precise=True)
        except (ValueError, UnicodeDecodeError):
            return {"status": status, "error": "invalid JSON response", "ms": ms, "bytes": len(raw)}
    return {"status": status, "content_type": ctype.split(";")[0], "json": parsed,
            "is_json": is_json, "text": None if is_json else text, "ms": ms, "bytes": len(raw),
            "body_sha256": body_hash}


def ignored(key, patterns):
    return any(re.fullmatch(p, key) for p in patterns)


def protected_key(key):
    # A documented heuristic, not a business schema or a universal semantic guard.
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower()
    return bool(set(re.split(r"[^a-z0-9]+", words)) &
                {"amount", "quantity", "qty", "count", "price", "total", "balance"})


def protected_subtree(value):
    if isinstance(value, dict):
        return any(protected_key(k) or protected_subtree(v) for k, v in value.items())
    if isinstance(value, list):
        return any(protected_subtree(v) for v in value)
    return False


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def deep_diff(x, y, patterns, path="$", out=None, limit=200, ignored_paths=None, rejected=None):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if len(out) >= limit:
                break
            p = f"{path}.{k}"
            if ignored(k, patterns):
                if protected_key(k) or protected_subtree(x.get(k)) or protected_subtree(y.get(k)):
                    if rejected is not None:
                        rejected.append(p)
                else:
                    if ignored_paths is not None:
                        ignored_paths.append(p)
                    continue
            if k not in x:
                out.append({"path": p, "kind": "only_in_b", "b": _short(y[k])})
            elif k not in y:
                out.append({"path": p, "kind": "only_in_a", "a": _short(x[k])})
            else:
                deep_diff(x[k], y[k], patterns, p, out, limit, ignored_paths, rejected)
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            out.append({"path": path, "kind": "length", "a": len(x), "b": len(y)})
        for i, (xi, yi) in enumerate(zip(x, y)):
            deep_diff(xi, yi, patterns, f"{path}[{i}]", out, limit, ignored_paths, rejected)
    else:
        if json_type(x) != json_type(y):
            out.append({"path": path, "kind": "type", "a": json_type(x), "b": json_type(y)})
        elif x != y:
            out.append({"path": path, "kind": "value", "a": _short(x), "b": _short(y)})
    return out


def _short(v):
    v = redact(v)
    s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v
    return s if len(s) <= 80 else s[:77] + "…"


def redact(value):
    if isinstance(value, str):
        for secret in REPORT_SECRETS:
            value = value.replace(secret, "[hidden]")
        return value
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {redact(key): redact(item) for key, item in value.items()}
    return value


def set_report_secrets(headers):
    REPORT_SECRETS.clear()
    for key, value in headers.items():
        if not re.search(r"authorization|cookie|token|secret|api[-_]?key", key, re.I) or not value:
            continue
        REPORT_SECRETS.append(value)
        auth = re.match(r"^(?:Bearer|Basic)\s+(.+)$", value, re.I)
        if auth:
            REPORT_SECRETS.append(auth.group(1))
        if "cookie" in key.lower():
            REPORT_SECRETS.extend(pair.split("=", 1)[1].strip() for pair in value.split(";")
                                  if "=" in pair and pair.split("=", 1)[1].strip())
    REPORT_SECRETS.sort(key=len, reverse=True)


def _headers(value, label, *, cases=False):
    if not isinstance(value, dict):
        raise InputError(f"{label} 必须是 JSON 对象")
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, str) or not key or any(
                char in key + val for char in "\r\n"):
            raise InputError(f"{label} 必须由合法字符串头组成")
        if cases and re.search(r"authorization|cookie|token|secret|api[-_]?key", key, re.I):
            raise InputError("用例不能存放认证头；请使用 API_DIFF_HEADERS 环境变量")
    return value


def validate_input(args):
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise InputError("--timeout 必须是有限的正数")
    for base in (args.a, args.b):
        try:
            url = urllib.parse.urlsplit(base)
            port = url.port
        except ValueError:
            raise InputError("端点 URL 格式无效") from None
        if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment or "\\" in base):
            raise InputError("端点必须是无凭证、无查询或片段的 HTTP(S) URL")
        try:
            local = ipaddress.ip_address(url.hostname).is_loopback
        except ValueError:
            local = url.hostname.lower() == "localhost"
        if not local and not args.allow_external:
            raise InputError("默认只访问回环地址；外部端点需明确添加 --allow-external")
    try:
        patterns = [re.compile(p.strip()) for p in args.ignore.split(",") if p.strip()]
    except re.error:
        raise InputError("--ignore 正则无效") from None
    try:
        cases = _strict_json(Path(args.cases).read_text("utf-8"))
    except (OSError, ValueError):
        raise InputError("用例文件必须是可读的合法 JSON，不能有重复键或非有限数字") from None
    if not isinstance(cases, list) or not cases:
        raise InputError("用例必须是非空 JSON 数组")
    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            raise InputError(f"用例 {index} 必须是对象")
        for field in ("path", "path_b"):
            path = case.get(field)
            if field == "path_b" and path is None:
                continue
            if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or "\\" in path:
                raise InputError(f"用例 {index} 的 {field} 必须是以单个 / 开始的相对路径")
        method = case.get("method", "GET")
        if not isinstance(method, str) or not re.fullmatch(r"[A-Za-z]+", method):
            raise InputError(f"用例 {index} 的 method 无效")
        if method.upper() not in ("GET", "HEAD") and not args.allow_write:
            raise InputError("写方法默认禁用；获准使用测试数据后才添加 --allow-write")
        _headers(case.get("headers", {}), "用例 headers", cases=True)
        if "name" in case and not isinstance(case["name"], str):
            raise InputError(f"用例 {index} 的 name 必须是字符串")
    try:
        headers = _strict_json(os.environ.get("API_DIFF_HEADERS", "{}"))
    except ValueError:
        raise InputError("API_DIFF_HEADERS 不是合法 JSON") from None
    _headers(headers, "API_DIFF_HEADERS")
    paths = [Path(path).resolve() for path in (args.cases, args.out, args.md) if path]
    if len(paths) != len(set(paths)):
        raise InputError("用例文件与两份报告必须使用不同路径")
    return cases, patterns, headers


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("`", "'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--ignore", default="", help="字段名全匹配正则，逗号分隔；金额/数量等常见业务字段受保护")
    ap.add_argument("--allow-external", action="store_true", help="明确允许访问已核对的外部 A/B 端点")
    ap.add_argument("--allow-write", action="store_true", help="明确允许使用测试数据发送 GET/HEAD 以外的方法")
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    try:
        cases, patterns, headers = validate_input(a)
    except InputError as error:
        ap.error(str(error))
    set_report_secrets(headers)
    results = []
    for c in cases:
        ra = request(a.a, c, headers, a.timeout)
        rb = request(a.b, c, headers, a.timeout, "path_b")
        diffs, skipped, rejected, verdict = [], [], [], "same"
        if ra.get("error") or rb.get("error"):
            verdict = "error"
        elif ra["status"] != rb["status"]:
            verdict = "status"
        elif not 200 <= ra["status"] < 300:
            verdict = "http_error"
        elif ra["is_json"] != rb["is_json"]:
            verdict = "diff"
            diffs = [{"path": "$", "kind": "format", "a": "JSON" if ra["is_json"] else "text",
                      "b": "JSON" if rb["is_json"] else "text"}]
        elif ra["is_json"] and rb["is_json"]:
            diffs = deep_diff(ra["json"], rb["json"], patterns, ignored_paths=skipped, rejected=rejected)
            verdict = "same" if not diffs else "diff"
        elif ra["body_sha256"] != rb["body_sha256"]:
            verdict = "diff"; diffs = [{"path": "$", "kind": "text", "a": _short(ra.get("text") or ""), "b": _short(rb.get("text") or "")}]
        if rejected:
            verdict = "ignore_error"
        # Redact only untrusted display data; schema keys and verdicts control execution.
        for diff in diffs:
            diff["path"] = redact(diff["path"])
        results.append({"name": redact(c.get("name") or c["path"]), "method": c.get("method", "GET").upper(),
                        "path": redact(c["path"]), "path_b": redact(c.get("path_b") or c["path"]), "verdict": verdict,
                        "a": {k: ra.get(k) for k in ("status", "ms", "bytes", "error", "body_sha256")},
                        "b": {k: rb.get(k) for k in ("status", "ms", "bytes", "error", "body_sha256")}, "diffs": diffs[:50]})
        results[-1].update(ignored_paths=redact(skipped), ignore_rejected=redact(rejected),
                           diff_count=len(diffs), diffs_truncated=len(diffs) > 50 or len(diffs) >= 200)
    n = len(results); same = sum(r["verdict"] == "same" for r in results)
    md = [f"# 接口差分：{redact(a.a)} ↔ {redact(a.b)}", "", f"- 用例 {n}，一致 {same}，有差异 {sum(r['verdict']=='diff' for r in results)}，状态码不同 {sum(r['verdict']=='status' for r in results)}，请求失败 {sum(r['verdict']=='error' for r in results)}",
          f"- 同码非 2xx {sum(r['verdict']=='http_error' for r in results)}，忽略规则被拒 {sum(r['verdict']=='ignore_error' for r in results)}",
          f"- 忽略规则（字段名全匹配）：{', '.join(redact(p.pattern) for p in patterns) or '无'}", "", "| 用例 | 方法 路径 | 结论 | A 状态/耗时 | B 状态/耗时 | 差异数 |", "|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {_cell(r['name'])} | {r['method']} {_cell(r['path'])} | {r['verdict']} | {r['a']['status']} / {r['a']['ms']}ms | {r['b']['status']} / {r['b']['ms']}ms | {r['diff_count']}{'（截断）' if r['diffs_truncated'] else ''} |")
    for r in results:
        if r["diffs"]:
            md += ["", f"## {r['name']}"]
            for d in r["diffs"][:30]:
                md.append(f"- `{_cell(d['path'])}` {d['kind']}：A=`{_cell(d.get('a', ''))}` B=`{_cell(d.get('b', ''))}`")
            if len(r["diffs"]) > 30 or r["diffs_truncated"]:
                md.append("- 此处仅显示前 30 条；JSON 最多保留 50 条，比较最多收集 200 条，详见截断标记。")
        elif r["verdict"] == "error":
            md += ["", f"## {r['name']}", f"- A: {r['a'].get('error') or 'ok'}；B: {r['b'].get('error') or 'ok'}"]
        if r["ignored_paths"]:
            md += ["", f"### {_cell(r['name'])}：实际忽略路径", *[f"- `{_cell(p)}`" for p in r["ignored_paths"]]]
        if r["ignore_rejected"]:
            md += ["", "### 忽略规则被拒：含受保护的金额或数量字段", *[f"- `{_cell(p)}`" for p in r["ignore_rejected"]]]
    text = "\n".join(md) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True); Path(a.md).write_text(text, "utf-8"); print(f"✓ {redact(a.md)}：{n} 用例，{same} 一致")
    else:
        print(text)
    sys.exit(2 if any(r["ignore_rejected"] for r in results) else 0 if same == n else 1)


if __name__ == "__main__":
    main()
