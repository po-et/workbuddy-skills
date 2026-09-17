#!/usr/bin/env python3
"""依赖过期检查：读取 requirements.txt / pyproject / package.json / go.mod / Cargo.toml / Gemfile / composer.json，查询公共注册表的最新版本，按主/次/补丁落后程度分级。纯标准库（联网）。

用法：
  python3 dep_outdated.py [目录或清单文件 ...] [--json] [--workers 8] [--timeout 8]
  代理：遵循 HTTPS_PROXY 环境变量。私有源：设置 PIP_INDEX_URL / NPM_REGISTRY（仅支持 PyPI/npm 兼容的 JSON API）。
"""
import argparse, concurrent.futures as cf, json, os, re, sys, urllib.request, urllib.parse

PYPI = os.environ.get("PIP_INDEX_URL", "https://pypi.org/simple").rstrip("/")
NPM = os.environ.get("NPM_REGISTRY", "https://registry.npmjs.org").rstrip("/")
HDR = {"User-Agent": "dep-outdated/0.1", "Accept": "application/json"}


def fetch_json(url, timeout, headers=None):
    req = urllib.request.Request(url, headers={**HDR, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def vparse(v):
    v = re.sub(r"^[v=^~>< ]+", "", str(v)).split("+")[0]
    nums = re.findall(r"\d+", v)
    pre = bool(re.search(r"(a|b|rc|alpha|beta|dev|pre|next|canary)\d*", v, re.I))
    return tuple(int(x) for x in nums[:3]) + (0,) * (3 - len(nums[:3])), pre


def gap(cur, latest):
    c, l = vparse(cur)[0], vparse(latest)[0]
    if l <= c:
        return "最新"
    if l[0] > c[0]: return "主版本"
    if l[1] > c[1]: return "次版本"
    return "补丁"


# ---- 各生态的解析与查询 ----
def parse_requirements(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.split("#", 1)[0].strip()
        if not s or s.startswith(("-", "git+", "http")):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==|>=|~=|<=|>|<|!=)?\s*([^;,\s]*)", s)
        if m:
            out.append((m.group(1), m.group(4) or "", "pypi"))
    return out


def parse_pyproject(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for m in re.finditer(r"^\s*\"([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==|>=|~=|<=|>|<)?\s*([^\",;]*)\"", txt, re.M):
        out.append((m.group(1), m.group(4), "pypi"))
    for m in re.finditer(r"^([A-Za-z0-9_.\-]+)\s*=\s*\"([^\"]+)\"", txt.split("[tool.poetry.dependencies]", 1)[-1].split("\n[", 1)[0], re.M) if "[tool.poetry.dependencies]" in txt else []:
        if m.group(1).lower() != "python":
            out.append((m.group(1), m.group(2), "pypi"))
    return out


def parse_package_json(path):
    d = json.load(open(path, encoding="utf-8"))
    out = []
    for key in ("dependencies", "devDependencies"):
        for name, ver in (d.get(key) or {}).items():
            if not re.match(r"^(file:|link:|git|http|workspace:|npm:)", str(ver)):
                out.append((name, ver, "npm"))
    return out


def parse_go_mod(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    body = "\n".join(re.findall(r"require\s*\((.*?)\)", txt, re.S)) + "\n" + "\n".join(re.findall(r"^require\s+(\S+\s+\S+)$", txt, re.M))
    return [(m.group(1), m.group(2), "go") for m in re.finditer(r"^\s*(\S+)\s+(v[\d.]+\S*)\s*(?://.*)?$", body, re.M) if "// indirect" not in m.group(0)]


def parse_cargo(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    sec = re.split(r"^\[", txt, flags=re.M)
    out = []
    for s in sec:
        if s.startswith(("dependencies]", "dev-dependencies]", "build-dependencies]")):
            for m in re.finditer(r"^([A-Za-z0-9_\-]+)\s*=\s*(?:\"([^\"]+)\"|\{[^}]*version\s*=\s*\"([^\"]+)\")", s, re.M):
                out.append((m.group(1), m.group(2) or m.group(3), "crates"))
    return out


def parse_gemfile(path):
    return [(m.group(1), m.group(2) or "", "rubygems") for m in re.finditer(r"^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", open(path, encoding="utf-8", errors="replace").read(), re.M)]


def parse_composer(path):
    d = json.load(open(path, encoding="utf-8"))
    return [(n, v, "packagist") for k in ("require", "require-dev") for n, v in (d.get(k) or {}).items() if "/" in n]


def latest(eco, name, timeout):
    try:
        if eco == "pypi":
            base = PYPI if PYPI.endswith("/simple") else PYPI
            if base.endswith("/simple"):
                d = fetch_json(f"{base}/{name.lower()}/", timeout, {"Accept": "application/vnd.pypi.simple.v1+json"})
                vers = [v for v in d.get("versions", []) if not vparse(v)[1]]
                return max(vers, key=lambda v: vparse(v)[0]) if vers else None
            d = fetch_json(f"https://pypi.org/pypi/{name}/json", timeout); return d["info"]["version"]
        if eco == "npm":
            d = fetch_json(f"{NPM}/{urllib.parse.quote(name, safe='@')}", timeout, {"Accept": "application/vnd.npm.install-v1+json"}); return (d.get("dist-tags") or {}).get("latest")
        if eco == "go":
            d = fetch_json(f"https://proxy.golang.org/{name.lower()}/@latest", timeout); return d.get("Version")
        if eco == "crates":
            d = fetch_json(f"https://crates.io/api/v1/crates/{name}", timeout); return d["crate"]["max_stable_version"]
        if eco == "rubygems":
            d = fetch_json(f"https://rubygems.org/api/v1/versions/{name}/latest.json", timeout); return d.get("version")
        if eco == "packagist":
            d = fetch_json(f"https://repo.packagist.org/p2/{name}.json", timeout)
            vers = [p["version"] for p in d["packages"][name] if not vparse(p["version"])[1]]
            return max(vers, key=lambda v: vparse(v)[0]) if vers else None
    except Exception as e:
        return f"ERR:{type(e).__name__}"
    return None


PARSERS = {"requirements.txt": parse_requirements, "requirements-dev.txt": parse_requirements, "pyproject.toml": parse_pyproject, "package.json": parse_package_json,
           "go.mod": parse_go_mod, "Cargo.toml": parse_cargo, "Gemfile": parse_gemfile, "composer.json": parse_composer}


def main():
    ap = argparse.ArgumentParser(description="依赖过期检查")
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    files = []
    for p in a.paths:
        if os.path.isdir(p):
            for name in PARSERS:
                f = os.path.join(p, name)
                if os.path.exists(f):
                    files.append(f)
            files += [os.path.join(p, f) for f in os.listdir(p) if f.startswith("requirements") and f.endswith(".txt") and os.path.join(p, f) not in files]
        elif os.path.exists(p):
            files.append(p)
    deps = []
    for f in files:
        parser = PARSERS.get(os.path.basename(f)) or (parse_requirements if f.endswith(".txt") else None)
        if parser:
            for name, ver, eco in parser(f):
                deps.append({"file": os.path.basename(f), "name": name, "current": ver or "(未固定)", "eco": eco})
    if not deps:
        sys.exit("没有找到依赖清单（支持 requirements*.txt / pyproject.toml / package.json / go.mod / Cargo.toml / Gemfile / composer.json）")
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for d, lv in zip(deps, ex.map(lambda d: latest(d["eco"], d["name"], a.timeout), deps)):
            d["latest"] = lv
            d["gap"] = "查询失败" if (lv is None or str(lv).startswith("ERR")) else ("未固定" if d["current"] == "(未固定)" else gap(d["current"], lv))
    order = {"主版本": 0, "次版本": 1, "补丁": 2, "未固定": 3, "查询失败": 4, "最新": 5}
    deps.sort(key=lambda d: (order[d["gap"]], d["name"]))
    if a.json:
        print(json.dumps(deps, ensure_ascii=False, indent=2)); return
    c = {k: sum(1 for d in deps if d["gap"] == k) for k in order}
    print(f"共 {len(deps)} 个依赖：主版本落后 {c['主版本']}，次版本 {c['次版本']}，补丁 {c['补丁']}，未固定 {c['未固定']}，最新 {c['最新']}，查询失败 {c['查询失败']}\n")
    print(f"  {'状态':<6} {'依赖':<40} {'当前':<18} {'最新':<14} 来源")
    for d in deps:
        if d["gap"] == "最新":
            continue
        print(f"  {d['gap']:<6} {d['name']:<40} {str(d['current'])[:18]:<18} {str(d['latest'])[:14]:<14} {d['file']}")
    if c["主版本"]:
        print("\n建议：主版本升级逐个来，先读 CHANGELOG 的 breaking 部分；次版本/补丁可批量升级并跑全量测试；「未固定」的依赖请锁定版本或使用 lockfile。")


if __name__ == "__main__":
    main()
