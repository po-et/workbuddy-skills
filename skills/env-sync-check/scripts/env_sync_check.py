#!/usr/bin/env python3
"""环境变量配置一致性检查：.env.example 与各环境 .env、代码里实际读取的变量三者对齐。纯标准库。

用法：
  python3 env_sync_check.py                      # 当前目录：.env.example 对比 .env* 并扫描代码
  python3 env_sync_check.py --example .env.example --env .env.production --src src/
  python3 env_sync_check.py --json --strict      # 有缺失必填变量则退出码 1
检查项：示例里有、环境文件缺（缺配置）；环境文件有、示例没有（未登记）；代码读取但示例没有（漏文档）；示例定义但代码从未读取（僵尸变量）；环境文件里的疑似真实密钥；重复定义。
"""
import argparse, json, os, re, sys

ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
READ_PATTERNS = [
    re.compile(r"os\.environ(?:\.get)?\s*[\[\(]\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),   # python
    re.compile(r"os\.getenv\s*\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)"),                                 # node
    re.compile(r"process\.env\[['\"]([A-Z][A-Z0-9_]+)['\"]\]"),
    re.compile(r"import\.meta\.env\.([A-Z][A-Z0-9_]+)"),                            # vite
    re.compile(r"os\.Getenv\s*\(\s*\"([A-Z][A-Z0-9_]+)\""),                         # go
    re.compile(r"os\.LookupEnv\s*\(\s*\"([A-Z][A-Z0-9_]+)\""),
    re.compile(r"System\.getenv\s*\(\s*\"([A-Z][A-Z0-9_]+)\""),                     # java
    re.compile(r"ENV\[['\"]([A-Z][A-Z0-9_]+)['\"]\]|ENV\.fetch\(['\"]([A-Z][A-Z0-9_]+)['\"]"),  # ruby
    re.compile(r"getenv\s*\(\s*['\"]([A-Z][A-Z0-9_]+)['\"]"),                       # php/c
    re.compile(r"\$\{([A-Z][A-Z0-9_]+)(?::-[^}]*)?\}"),                              # shell / compose
    re.compile(r"env::var\s*\(\s*\"([A-Z][A-Z0-9_]+)\""),                            # rust
    re.compile(r"Env\.get\(['\"]([A-Z][A-Z0-9_]+)['\"]"),
]
SECRET_KEY = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|ACCESS_?KEY|CREDENTIAL|DSN|DATABASE_URL)", re.I)
PLACEHOLDER = re.compile(r"^(|\$\{.*\}|<.*>|xxx+|your[-_].*|change[-_]?me|placeholder|todo|\*+|example|dummy|redacted)$", re.I)
SRC_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".go", ".java", ".kt", ".rb", ".php", ".rs", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".env"}


def parse_env(path):
    vars_, dups = {}, []
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = ENV_LINE.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v[:1] in ("'", '"') and v[-1:] == v[:1] and len(v) >= 2:
            v = v[1:-1]
        else:
            v = v.split(" #", 1)[0].strip()
        if k in vars_:
            dups.append((k, i))
        vars_[k] = (v, i)
    return vars_, dups


def scan_src(root):
    found = {}
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "__pycache__", ".next", "target")]
        for fn in files:
            if os.path.splitext(fn)[1] not in SRC_EXT or fn.startswith(".env"):
                continue
            p = os.path.join(r, fn)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for pat in READ_PATTERNS:
                for m in pat.finditer(text):
                    name = next(g for g in m.groups() if g)
                    found.setdefault(name, set()).add(os.path.relpath(p, root))
    return found


def looks_real_secret(k, v):
    if not SECRET_KEY.search(k) or PLACEHOLDER.match(v):
        return False
    return len(v) >= 12 and not v.startswith("${")


def main():
    ap = argparse.ArgumentParser(description=".env 一致性检查")
    ap.add_argument("--example", default=None, help="示例文件，默认自动找 .env.example / .env.sample / .env.template")
    ap.add_argument("--env", action="append", help="要对比的环境文件，可多次；默认自动找 .env、.env.* （排除示例）")
    ap.add_argument("--src", default=".", help="扫描代码的目录")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有「环境文件缺变量」则退出码 1")
    a = ap.parse_args()
    root = a.src
    example = a.example or next((f for f in (".env.example", ".env.sample", ".env.template", ".env.dist") if os.path.exists(os.path.join(root, f))), None)
    envs = a.env or sorted(f for f in os.listdir(root) if f.startswith(".env") and f != example and not f.endswith((".example", ".sample", ".template", ".dist")) and os.path.isfile(os.path.join(root, f)))
    envs = [e if os.path.isabs(e) or os.path.exists(e) else os.path.join(root, e) for e in envs]
    report = {"example": example, "envs": envs, "findings": []}

    def add(sev, kind, msg, where=None):
        report["findings"].append({"severity": sev, "kind": kind, "message": msg, "where": where})

    ex_vars, ex_dups = parse_env(os.path.join(root, example) if example and not os.path.isabs(example) else example) if example else ({}, [])
    for k, ln in ex_dups:
        add("warn", "duplicate", f"示例文件重复定义 {k}（第 {ln} 行）", example)
    code_vars = scan_src(root)
    for env in envs:
        vars_, dups = parse_env(env)
        name = os.path.basename(env)
        for k, ln in dups:
            add("warn", "duplicate", f"{name} 重复定义 {k}（第 {ln} 行，后者生效）", name)
        for k in sorted(set(ex_vars) - set(vars_)):
            add("high", "missing", f"{name} 缺少示例中登记的 {k}", name)
        for k in sorted(set(vars_) - set(ex_vars)) if example else []:
            add("info", "unregistered", f"{name} 定义了示例中没有的 {k}（考虑登记到 {example}）", name)
        for k, (v, ln) in vars_.items():
            if looks_real_secret(k, v):
                add("warn", "secret", f"{name} 第 {ln} 行的 {k} 看起来是真实密钥；确认该文件在 .gitignore 中且未被提交", name)
        for k, (v, ln) in ex_vars.items():
            if looks_real_secret(k, v):
                add("high", "secret-in-example", f"示例文件第 {ln} 行的 {k} 看起来是真实密钥，示例文件会被提交到仓库", example)
    if example:
        for k in sorted(set(code_vars) - set(ex_vars)):
            files = sorted(code_vars[k])[:3]
            add("warn", "undocumented", f"代码读取了 {k} 但示例文件没有登记（{', '.join(files)}）", files[0] if files else None)
        for k in sorted(set(ex_vars) - set(code_vars)):
            add("info", "unused", f"示例登记了 {k} 但代码中没有找到读取处（可能通过框架/配置库间接读取，或已废弃）", example)
    order = {"high": 0, "warn": 1, "info": 2}
    report["findings"].sort(key=lambda f: (order[f["severity"]], f["kind"], f["message"]))
    report["code_vars"] = sorted(code_vars)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"示例文件：{example or '（未找到）'}；环境文件：{', '.join(os.path.basename(e) for e in envs) or '（无）'}；代码中读取 {len(code_vars)} 个变量")
        if not report["findings"]:
            print("  ✓ 三方一致")
        for f in report["findings"]:
            print(f"  [{f['severity'].upper():4}] {f['kind']:18} {f['message']}")
        c = {s: sum(1 for f in report["findings"] if f["severity"] == s) for s in ("high", "warn", "info")}
        print(f"  小计：high {c['high']} / warn {c['warn']} / info {c['info']}")
    bad = any(f["kind"] in ("missing", "secret-in-example") for f in report["findings"])
    sys.exit(1 if (a.strict and bad) else 0)


if __name__ == "__main__":
    main()
