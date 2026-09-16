#!/usr/bin/env python3
"""依赖漏洞体检：解析锁文件 → 查询 OSV.dev（免费、无需 API Key）→ 输出漏洞表。

支持：package-lock.json（v1/v2/v3）、requirements.txt、poetry.lock、Pipfile.lock、
go.mod / go.sum、Cargo.lock、Gemfile.lock、composer.lock。零第三方依赖。

用法：
  python3 osv_check.py --path <仓库或锁文件> [--out out/vulns.json] [--md out/vulns.md] [--max-details 80] [--fail-on high|critical]
"""
import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
TIMEOUT = 30
SEV_ORDER = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


# ---------- 锁文件解析：返回 [(ecosystem, name, version, source_file)] ----------
def parse_package_lock(p):
    d = json.loads(p.read_text("utf-8"))
    out = []
    if "packages" in d:  # v2/v3
        for k, v in d["packages"].items():
            if not k or "node_modules/" not in k or not v.get("version"):
                continue
            name = k.split("node_modules/")[-1]
            out.append(("npm", name, v["version"], p.name))
    elif "dependencies" in d:  # v1
        def walk(deps):
            for name, v in deps.items():
                if v.get("version"):
                    out.append(("npm", name, v["version"], p.name))
                if v.get("dependencies"):
                    walk(v["dependencies"])
        walk(d["dependencies"])
    return out


def parse_requirements(p):
    out, skipped = [], 0
    for line in p.read_text("utf-8", errors="ignore").splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith(("-", "git+", "http")):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*==\s*([A-Za-z0-9_.+!-]+)", line)
        if m:
            out.append(("PyPI", re.sub(r"\[.*\]", "", m.group(1)), m.group(2), p.name))
        else:
            skipped += 1
    return out, skipped


def parse_toml_lock(p, ecosystem):  # poetry.lock / Cargo.lock 的 [[package]] 块
    out, name, ver = [], None, None
    for line in p.read_text("utf-8", errors="ignore").splitlines():
        if line.strip() == "[[package]]":
            if name and ver:
                out.append((ecosystem, name, ver, p.name))
            name = ver = None
        m = re.match(r'^\s*name\s*=\s*"([^"]+)"', line)
        if m:
            name = m.group(1)
        m = re.match(r'^\s*version\s*=\s*"([^"]+)"', line)
        if m:
            ver = m.group(1)
    if name and ver:
        out.append((ecosystem, name, ver, p.name))
    return out


def parse_pipfile_lock(p):
    d = json.loads(p.read_text("utf-8"))
    out = []
    for sec in ("default", "develop"):
        for name, v in d.get(sec, {}).items():
            ver = (v.get("version") or "").lstrip("=")
            if ver:
                out.append(("PyPI", name, ver, p.name))
    return out


def parse_go(p):
    out = set()
    for line in p.read_text("utf-8", errors="ignore").splitlines():
        if p.name == "go.sum":
            m = re.match(r"^(\S+)\s+(v[^\s/]+)(/go\.mod)?\s+h1:", line)
        else:
            m = re.match(r"^\s*(\S+)\s+(v\S+)", line) if not line.strip().startswith(("module", "go ", "//", "require (", ")")) else None
        if m:
            out.add(("Go", m.group(1), m.group(2), p.name))
    return sorted(out)


def parse_gemfile_lock(p):
    out, in_specs = [], False
    for line in p.read_text("utf-8", errors="ignore").splitlines():
        if line.strip() == "specs:":
            in_specs = True
            continue
        if in_specs and line and not line.startswith(" "):
            in_specs = False
        m = re.match(r"^    ([A-Za-z0-9_.\-]+) \(([^)]+)\)$", line)
        if in_specs and m:
            out.append(("RubyGems", m.group(1), m.group(2), p.name))
    return out


def parse_composer_lock(p):
    d = json.loads(p.read_text("utf-8"))
    out = []
    for sec in ("packages", "packages-dev"):
        for pkg in d.get(sec, []):
            if pkg.get("name") and pkg.get("version"):
                out.append(("Packagist", pkg["name"], pkg["version"].lstrip("v"), p.name))
    return out


PARSERS = {
    "package-lock.json": parse_package_lock, "requirements.txt": None, "poetry.lock": lambda p: parse_toml_lock(p, "PyPI"),
    "Pipfile.lock": parse_pipfile_lock, "go.mod": parse_go, "go.sum": parse_go, "Cargo.lock": lambda p: parse_toml_lock(p, "crates.io"),
    "Gemfile.lock": parse_gemfile_lock, "composer.lock": parse_composer_lock,
}


def discover(path: Path):
    if path.is_file():
        return [path]
    files = []
    for name in PARSERS:
        files += [f for f in path.rglob(name) if "node_modules" not in f.parts and ".venv" not in f.parts and "vendor" not in f.parts]
    files += [f for f in path.rglob("requirements*.txt") if ".venv" not in f.parts and f.name != "requirements.txt"]
    return sorted(set(files))


# ---------- OSV ----------
def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "User-Agent": "dep-vuln-check/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dep-vuln-check/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def query_batch(pkgs):
    results = []
    for i in range(0, len(pkgs), 500):
        chunk = pkgs[i:i + 500]
        resp = post_json(OSV_BATCH, {"queries": [{"package": {"name": n, "ecosystem": e}, "version": v} for e, n, v, _ in chunk]})
        for pkg, res in zip(chunk, resp.get("results", [])):
            ids = [x["id"] for x in res.get("vulns", [])]
            if ids:
                results.append({"ecosystem": pkg[0], "name": pkg[1], "version": pkg[2], "file": pkg[3], "vuln_ids": ids})
    return results


def severity_of(v):
    sev = "UNKNOWN"
    for s in v.get("severity", []) or []:
        score = s.get("score", "")
        m = re.search(r"CVSS:3\.\d/", score)
        if m:
            try:
                # 粗略：从向量算不了分，退回 database_specific
                pass
            except Exception:
                pass
    ds = v.get("database_specific", {}) or {}
    if ds.get("severity"):
        sev = str(ds["severity"]).upper()
    for aff in v.get("affected", []) or []:
        eds = aff.get("database_specific", {}) or {}
        if eds.get("severity"):
            sev = str(eds["severity"]).upper()
    return sev if sev in SEV_ORDER else "UNKNOWN"


def fixed_versions(v, ecosystem, name):
    fixed = set()
    for aff in v.get("affected", []) or []:
        pkg = aff.get("package", {})
        if pkg.get("ecosystem") != ecosystem or pkg.get("name", "").lower() != name.lower():
            continue
        for rg in aff.get("ranges", []) or []:
            for ev in rg.get("events", []) or []:
                if ev.get("fixed"):
                    fixed.add(ev["fixed"])
    return sorted(fixed)


def enrich(results, max_details):
    # 轮转取 id：先保证每个包至少拿到一条详情（严重度/修复版本），再补其余
    ids, seen, k = [], set(), 0
    while True:
        progressed = False
        for r in results:
            if k < len(r["vuln_ids"]):
                i = r["vuln_ids"][k]
                if i not in seen:
                    seen.add(i); ids.append(i)
                progressed = True
        if not progressed:
            break
        k += 1
    details = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for vid, data in zip(ids[:max_details], ex.map(lambda i: _safe_get(OSV_VULN + i), ids[:max_details])):
            if data:
                details[vid] = data
    for r in results:
        r["vulns"] = []
        for vid in r["vuln_ids"]:
            d = details.get(vid)
            if not d:
                r["vulns"].append({"id": vid, "severity": "UNKNOWN", "summary": "（未取详情）", "fixed": [], "aliases": []})
                continue
            r["vulns"].append({"id": vid, "severity": severity_of(d), "summary": (d.get("summary") or d.get("details") or "")[:160].replace("\n", " "),
                               "fixed": fixed_versions(d, r["ecosystem"], r["name"]), "aliases": d.get("aliases", [])[:3]})
        r["max_severity"] = max((v["severity"] for v in r["vulns"]), key=lambda s: SEV_ORDER[s], default="UNKNOWN")
        r["upgrade_to"] = max((f for v in r["vulns"] for f in v["fixed"]), default=None, key=_verkey)
    return len(ids), len(details)


def _safe_get(url):
    try:
        return get_json(url)
    except Exception:
        return None


def _verkey(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", str(v))[:4])


def render_md(results, summary):
    lines = [f"# 依赖漏洞体检", "", f"- 扫描文件：{summary['files']}", f"- 依赖总数：{summary['packages']}，有漏洞的依赖：{len(results)}，漏洞条目：{summary['vuln_count']}（取详情 {summary['detailed']} 条）", ""]
    if not results:
        lines.append("未发现 OSV 收录的已知漏洞。（不等于安全：未收录 ≠ 不存在；也不检查你自己的代码。）")
        return "\n".join(lines) + "\n"
    lines += ["| 严重度 | 依赖 | 当前版本 | 漏洞 | 建议升级到 | 来源文件 |", "|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: -SEV_ORDER[r["max_severity"]]):
        ids = ", ".join(f"{v['id']}" + (f"({', '.join(v['aliases'])})" if v["aliases"] else "") for v in r["vulns"][:4])
        if len(r["vulns"]) > 4:
            ids += f" …共 {len(r['vulns'])}"
        lines.append(f"| {r['max_severity']} | {r['ecosystem']}/{r['name']} | {r['version']} | {ids} | {r['upgrade_to'] or '—'} | {r['file']} |")
    lines += ["", "## 说明", "- 严重度来自 OSV/GHSA 的 database_specific.severity，缺失时为 UNKNOWN，需人工看链接。",
              "- 「建议升级到」取所有漏洞 fixed 版本的最大值，升级前仍需看变更日志确认兼容。", "- 未解析的依赖（无固定版本、git 依赖）不会被查。"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--max-details", type=int, default=200)
    ap.add_argument("--fail-on", choices=["low", "moderate", "high", "critical"])
    a = ap.parse_args()

    files = discover(Path(a.path))
    if not files:
        print("没找到支持的锁文件（package-lock.json / requirements*.txt / poetry.lock / Pipfile.lock / go.mod / go.sum / Cargo.lock / Gemfile.lock / composer.lock）", file=sys.stderr)
        sys.exit(2)
    pkgs, notes = [], []
    for f in files:
        try:
            if f.name.startswith("requirements") and f.suffix == ".txt":
                got, skipped = parse_requirements(f)
                if skipped:
                    notes.append(f"{f.name}: {skipped} 行没有固定版本（==），未查询")
            else:
                got = PARSERS[f.name](f)
        except Exception as e:
            notes.append(f"{f}: 解析失败 {e}")
            continue
        pkgs += got
    pkgs = sorted(set(pkgs))
    if not pkgs:
        print("锁文件里没有可查询的固定版本依赖", file=sys.stderr)
        sys.exit(2)
    try:
        results = query_batch(pkgs)
    except Exception as e:
        print(f"查询 OSV 失败（需要能访问 api.osv.dev）：{e}", file=sys.stderr)
        sys.exit(3)
    vuln_count, detailed = enrich(results, a.max_details)
    summary = {"files": ", ".join(str(f) for f in files), "packages": len(pkgs), "vuln_count": vuln_count, "detailed": detailed, "notes": notes}
    md = render_md(results, summary)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), "utf-8")
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True)
        Path(a.md).write_text(md, "utf-8")
    print(md if not a.md else f"✓ {a.md}：{len(pkgs)} 个依赖，{len(results)} 个有漏洞，{vuln_count} 条漏洞")
    for n in notes:
        print("  注意：" + n)
    if a.fail_on:
        worst = max((SEV_ORDER[r["max_severity"]] for r in results), default=0)
        if worst >= SEV_ORDER[a.fail_on.upper() if a.fail_on != "moderate" else "MODERATE"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
