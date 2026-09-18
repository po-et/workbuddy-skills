#!/usr/bin/env python3
"""接口契约回归测试：按用例文件依次或并发发请求，校验状态码、JSON 字段、响应头与耗时。纯标准库。

用法：
  python3 api_contract_test.py cases.json
  python3 api_contract_test.py cases.yaml --base-url https://api.example.com --concurrent 8
  TOKEN=xxx python3 api_contract_test.py cases.json --strict        # 有失败则退出码 1
用例里用 ${TOKEN} 引用环境变量，脚本只从 os.environ 取值，绝不把密钥写进用例文件或输出。
"""
import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MISSING = object()
TYPES = {"string": str, "number": (int, float), "integer": int, "boolean": bool,
         "array": list, "object": dict, "null": type(None)}


# ---------------------------------------------------------------- YAML 子集

def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        body = v[1:-1]
        return body.replace('\\"', '"').replace("\\n", "\n") if v[0] == '"' else body
    if " #" in v:                                   # 未加引号的行内注释
        v = v.split(" #", 1)[0].strip()
    if v in ("true", "True", "yes"):
        return True
    if v in ("false", "False", "no"):
        return False
    if v in ("null", "~", "None", ""):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    if v[:1] in "[{":
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            pass
    return v


def _lines(text):
    out = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        out.append((len(raw) - len(raw.lstrip(" ")), raw.rstrip()))
    return out


def _block(lines, i, indent):
    """解析缩进块，返回 (值, 下一行下标)。支持映射、列表、标量；不支持锚点与块标量。"""
    if lines[i][1].lstrip().startswith("- "):
        items = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].lstrip().startswith("- "):
            rest = lines[i][1].lstrip()[2:]
            child_indent = lines[i][0] + 2
            if re.match(r"^[\w.\-/]+\s*:(\s|$)", rest):      # 列表项本身是映射
                sub = [(child_indent, " " * child_indent + rest)]
                i += 1
                while i < len(lines) and lines[i][0] > indent:
                    sub.append(lines[i]); i += 1
                v, _ = _block(sub, 0, child_indent)
                items.append(v)
            else:
                items.append(_scalar(rest)); i += 1
                while i < len(lines) and lines[i][0] > indent:
                    i += 1
        return items, i
    out = {}
    while i < len(lines) and lines[i][0] == indent:
        s = lines[i][1].strip()
        if ":" not in s:
            raise ValueError(f"YAML 子集解析失败，这一行既不是键值也不是列表项: {s}")
        k, _, v = s.partition(":")
        k, v = k.strip().strip("\"'"), v.strip()
        if v == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                out[k], i = _block(lines, i + 1, lines[i + 1][0])
            else:
                out[k] = None; i += 1
        else:
            out[k] = _scalar(v); i += 1
    return out, i


def load_cases(path):
    text = open(path, encoding="utf-8").read()
    if path.lower().endswith(".json") or text.lstrip()[:1] in "[{":
        return json.loads(text)
    lines = _lines(text)
    if not lines:
        return {}
    doc, _ = _block(lines, 0, lines[0][0])
    return doc


# ---------------------------------------------------------------- 环境变量与 JSON 路径

ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand(obj, missing):
    if isinstance(obj, str):
        def sub(m):
            name = m.group(1)
            if name not in os.environ:
                missing.add(name); return m.group(0)
            return os.environ[name]
        return ENV.sub(sub, obj)
    if isinstance(obj, dict):
        return {k: expand(v, missing) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand(v, missing) for v in obj]
    return obj


SEG = re.compile(r"\.([^.\[\]]+)|\[(\d+)\]|\['([^']*)'\]")


def jpath(doc, expr):
    """最小 JSON 路径子集：$.a.b、$.a[0].b、$['a b']。找不到返回 MISSING。"""
    e = expr.strip()
    if e.startswith("$"):
        e = e[1:]
    if e and e[0] not in ".[":
        e = "." + e
    cur, pos = doc, 0
    while pos < len(e):
        m = SEG.match(e, pos)
        if not m:
            raise ValueError(f"无法解析的 JSON 路径片段 {e[pos:]!r}（只支持点号与 [i]）")
        pos = m.end()
        key = m.group(1) if m.group(1) is not None else m.group(3)
        if key is not None:
            if not isinstance(cur, dict) or key not in cur:
                return MISSING
            cur = cur[key]
        else:
            idx = int(m.group(2))
            if not isinstance(cur, list) or idx >= len(cur):
                return MISSING
            cur = cur[idx]
    return cur


def show(v):
    if v is MISSING:
        return "缺失"
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= 120 else s[:117] + "..."


# ---------------------------------------------------------------- 断言

def check_json(doc, rules, fails):
    for rule in rules or []:
        if not isinstance(rule, dict) or "path" not in rule:
            fails.append(f"json 断言缺少 path 字段 {show(rule)}"); continue
        p = rule["path"]
        try:
            got = jpath(doc, p)
        except ValueError as e:
            fails.append(str(e)); continue
        if "exists" in rule:
            want = bool(rule["exists"])
            if (got is not MISSING) != want:
                fails.append(f"{p} 期望{'存在' if want else '不存在'}，实际{'存在' if got is not MISSING else '缺失'}")
                continue
            if not want:
                continue
        if got is MISSING and any(k in rule for k in ("equals", "type", "contains")):
            fails.append(f"{p} 缺失（无法校验 equals/type/contains）"); continue
        if "equals" in rule and got != rule["equals"]:
            fails.append(f"{p} 期望 equals {show(rule['equals'])}，实际 {show(got)}")
        if "type" in rule:
            want = str(rule["type"]).lower()
            exp = TYPES.get(want)
            if exp is None:
                fails.append(f"{p} 的 type {want!r} 不支持（string/number/integer/boolean/array/object/null）")
            elif (isinstance(got, bool) and want in ("number", "integer")) or not isinstance(got, exp):
                fails.append(f"{p} 期望 type {want}，实际 {type(got).__name__} {show(got)}")
        if "contains" in rule:
            needle = rule["contains"]
            ok = (needle in got) if isinstance(got, (str, list, dict)) else False
            if not ok:
                fails.append(f"{p} 期望包含 {show(needle)}，实际 {show(got)}")


def check_headers(rheaders, rules, fails):
    low = {k.lower(): v for k, v in rheaders.items()}
    for name, rule in (rules or {}).items():
        got = low.get(name.lower())
        if got is None:
            fails.append(f"响应头 {name} 缺失"); continue
        if isinstance(rule, dict):
            if "equals" in rule and got != rule["equals"]:
                fails.append(f"响应头 {name} 期望 {rule['equals']!r}，实际 {got!r}")
            if "contains" in rule and str(rule["contains"]).lower() not in got.lower():
                fails.append(f"响应头 {name} 期望包含 {rule['contains']!r}，实际 {got!r}")
        elif str(rule).lower() not in got.lower():
            fails.append(f"响应头 {name} 期望包含 {rule!r}，实际 {got!r}")


# ---------------------------------------------------------------- 执行

def run_case(case, g):
    name = case.get("name") or f"{case.get('method', 'GET')} {case.get('path') or case.get('url')}"
    res = {"name": name, "status": None, "ms": 0, "ok": False, "failures": [], "error": None}
    missing = set()
    case = expand(case, missing)
    headers = {**expand(g.get("headers") or {}, missing), **(case.get("headers") or {})}
    if missing:
        res["error"] = f"环境变量未设置 {', '.join(sorted(missing))}（用例里的 ${{...}} 只从环境变量取值）"
        return res
    url = case.get("url") or urllib.parse.urljoin((g.get("base_url") or "").rstrip("/") + "/",
                                                  str(case.get("path") or "").lstrip("/"))
    if case.get("query"):
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(case["query"], doseq=True)
    data, body = None, case.get("body")
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode()
            headers.setdefault("Content-Type", "application/json")
        else:
            data = str(body).encode()
    method = str(case.get("method") or ("POST" if data else "GET")).upper()
    timeout = float(case.get("timeout_ms") or g.get("timeout_ms") or 10000) / 1000
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw, rh = r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        status, raw, rh = e.code, e.read(), dict(e.headers)
    except Exception as e:  # noqa: BLE001  网络错误、超时、DNS
        res["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        res["error"] = f"{type(e).__name__}: {e}"
        return res
    res["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    res["status"] = status
    exp = case.get("expect") or {}
    fails = res["failures"]
    want = exp.get("status")
    if want is not None:
        allow = want if isinstance(want, list) else [want]
        if status not in allow:
            fails.append(f"状态码期望 {allow if len(allow) > 1 else allow[0]}，实际 {status}")
    if exp.get("max_ms") and res["ms"] > float(exp["max_ms"]):
        fails.append(f"耗时 {res['ms']}ms 超过上限 {exp['max_ms']}ms")
    check_headers(rh, exp.get("headers"), fails)
    text = raw.decode("utf-8", "replace")
    if exp.get("body_contains") and exp["body_contains"] not in text:
        fails.append(f"响应体不含 {exp['body_contains']!r}")
    if exp.get("json"):
        try:
            doc = json.loads(text) if text.strip() else None
        except json.JSONDecodeError as e:
            fails.append(f"响应不是合法 JSON（{e}），前 120 字符 {text[:120]!r}")
        else:
            check_json(doc, exp["json"], fails)
    res["ok"] = not fails
    return res


def main():
    ap = argparse.ArgumentParser(description="接口契约回归测试")
    ap.add_argument("casefile", help="用例文件（.json 或 YAML 子集）")
    ap.add_argument("--base-url", help="覆盖用例文件里的 base_url")
    ap.add_argument("--filter", help="只跑名字含该子串的用例")
    ap.add_argument("--concurrent", type=int, default=1, help="并发数，默认 1（顺序执行）")
    ap.add_argument("--timeout-ms", type=float, help="覆盖全局超时")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有失败或错误则退出码 1（CI 门禁）")
    a = ap.parse_args()

    doc = load_cases(a.casefile)
    cases = doc.get("cases") if isinstance(doc, dict) else doc
    if not cases:
        sys.exit("用例文件里没有 cases 数组")
    g = {k: v for k, v in (doc.items() if isinstance(doc, dict) else []) if k != "cases"}
    if a.base_url:
        g["base_url"] = a.base_url
    if a.timeout_ms:
        g["timeout_ms"] = a.timeout_ms
    if a.filter:
        cases = [c for c in cases if a.filter in str(c.get("name", "")) or a.filter in str(c.get("path", ""))]

    t0 = time.perf_counter()
    if a.concurrent > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrent) as ex:
            results = list(ex.map(lambda c: run_case(c, g), cases))
    else:
        results = [run_case(c, g) for c in cases]
    wall = time.perf_counter() - t0

    passed = sum(1 for r in results if r["ok"])
    errored = sum(1 for r in results if r["error"])
    failed = len(results) - passed - errored
    times = sorted(r["ms"] for r in results)
    summary = {"total": len(results), "passed": passed, "failed": failed, "errored": errored,
               "wall_ms": round(wall * 1000, 1),
               "p50_ms": times[len(times) // 2] if times else 0, "max_ms": times[-1] if times else 0}
    if a.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"接口契约回归 · 用例 {len(results)} · 并发 {a.concurrent} · 基础地址 {g.get('base_url') or '（用例内绝对 URL）'}")
        for r in results:
            mark = "✓" if r["ok"] else ("!" if r["error"] else "✗")
            print(f"  {mark} [{r['status'] or '--'}] {r['ms']:>7.0f}ms  {r['name']}")
            if r["error"]:
                print(f"        错误 {r['error']}")
            for f in r["failures"]:
                print(f"        {f}")
        print(f"\n汇总：通过 {passed} / 失败 {failed} / 错误 {errored}；"
              f"耗时 p50 {summary['p50_ms']:.0f}ms、最大 {summary['max_ms']:.0f}ms、总墙钟 {wall:.1f}s")
        if failed or errored:
            print("排查顺序：先看『错误』（网络、超时、环境变量），再看状态码，最后看字段断言；"
                  "字段对不上时先确认是不是接口真的改了契约，再决定改用例还是回滚接口。")
    sys.exit(1 if (a.strict and (failed or errored)) else 0)


if __name__ == "__main__":
    main()
