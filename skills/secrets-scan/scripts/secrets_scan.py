#!/usr/bin/env python3
"""仓库泄密自查：扫描工作树与最近若干个提交，识别常见密钥形态，脱敏后报告。

用法：
  python3 secrets_scan.py [路径 ...] [--history N] [--entropy] [--json] [--strict]
  默认扫描当前目录。--strict 时存在 high/warn 级命中则退出码 1。
  git 可执行文件用环境变量 GIT_BIN 覆盖（默认 git）。
防御性用途：只读扫描，不联网、不上报、不改动任何文件。
"""
import argparse, json, math, os, re, subprocess, sys
from fnmatch import fnmatch

GIT_BIN = os.environ.get("GIT_BIN", "git")

# 拼接而非整段字面量，避免本脚本自身被其它密钥扫描器误报
PEM_HEAD = "-----BEGIN "
PEM_TAIL = "PRIVATE KEY-----"

# (规则号, 级别, 类型名, 正则, 取值分组, 改法)
RULES = [
    ("SEC001", "high", "AWS Access Key ID",
     re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ABIA|ACCA)[0-9A-Z]{16}\b"), 0,
     "去 IAM 立即禁用该 Access Key 并轮换；改用实例角色或环境变量注入"),
    ("SEC002", "high", "AWS Secret Access Key",
     re.compile(r"(?i)aws[_-]?secret[_-]?(?:access[_-]?)?key\s*[:=]\s*[\"']?([A-Za-z0-9/+=]{40})"), 1,
     "同时轮换对应的 Access Key；密钥交给密钥管理服务或 CI 变量保管"),
    ("SEC003", "high", "GitHub Token",
     re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b"), 0,
     "在 GitHub 设置里吊销该 token，改用 Actions secrets 或短时效的 OIDC 凭据"),
    ("SEC004", "high", "GitLab Personal Access Token",
     re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b"), 0,
     "在 GitLab 用户设置里 revoke，改用 CI/CD Variables（masked + protected）"),
    ("SEC005", "high", "Slack Token",
     re.compile(r"\bxox[abprse]-[A-Za-z0-9-]{10,}\b"), 0,
     "在 Slack App 管理页重置 token；机器人凭据放密钥管理服务"),
    ("SEC006", "high", "Slack Incoming Webhook",
     re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_+-]{20,}"), 0,
     "删除该 webhook 并重建；webhook URL 等同于凭据，不能进仓库"),
    ("SEC007", "high", "私钥文件块",
     re.compile(PEM_HEAD + r"(?:[A-Z0-9]+ )*" + PEM_TAIL), 0,
     "把私钥移出仓库并重新签发；旧私钥视为已泄露，需要吊销对应证书/授权"),
    ("SEC008", "high", "Google API Key",
     re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), 0,
     "在云控制台删除该 key 并重建，重建时务必加 referrer/IP 限制"),
    ("SEC009", "high", "Stripe 线上密钥",
     re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}\b"), 0,
     "去 Dashboard roll 掉该密钥；线上密钥只允许存在于服务端密钥管理里"),
    ("SEC010", "high", "npm Token",
     re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), 0,
     "npm token revoke 该令牌，CI 用 NODE_AUTH_TOKEN 从 secrets 注入"),
    ("SEC011", "high", "平台密钥（sk- 前缀）",
     re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{24,}\b"), 0,
     "在对应平台后台吊销并重建，调用方从环境变量读取"),
    ("SEC012", "high", "数据库连接串含明文口令",
     re.compile(r"\b(?:mysql|postgres(?:ql)?|mongodb(?:\+srv)?|redis(?:s)?|amqp(?:s)?|mssql|clickhouse|jdbc:[a-z0-9]+)://"
                r"[^\s:'\"@/]{1,64}:([^\s:'\"@/]{3,})@"), 1,
     "改口令并把连接串拆成 host/user/password 三个环境变量，口令只在运行时注入"),
    ("SEC013", "warn", "URL 内嵌基本认证口令",
     re.compile(r"\bhttps?://[^\s:'\"@/]{1,64}:([^\s:'\"@/]{3,})@[^\s'\"]+"), 1,
     "去掉 URL 里的用户名口令，改用 Authorization 头或凭据助手"),
    ("SEC014", "warn", "JWT",
     re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b"), 0,
     "确认是否真实签发的令牌；是则缩短有效期并轮换签名密钥，测试数据请换成假串"),
    ("SEC015", "warn", "通用密钥赋值",
     re.compile(r"(?i)\b(?:pass(?:word|wd)?|secret|api[_-]?key|apikey|access[_-]?key|app[_-]?secret|"
                r"client[_-]?secret|auth[_-]?token|token|credential)\b\s*[:=]\s*[\"']([^\"'\s]{6,})[\"']"), 1,
     "把值挪到环境变量或密钥管理服务；配置文件里只保留占位符"),
]

# 占位符与示例值，命中即跳过
PLACEHOLDER = re.compile(
    r"(?i)^(?:x{3,}|y{3,}|\*{3,}|\.{3,}|-{3,}|_{3,}|0{6,}|1234\d*|"
    r"(?:your|my|the)[-_]?\w*|change[-_]?me|placeholder|example\w*|sample\w*|dummy\w*|fake\w*|"
    r"test\w*|demo\w*|redacted|masked|hidden|secret|password|token|api[-_]?key|none|null|empty|todo)$")
PLACEHOLDER_SUB = re.compile(r"(?i)(example|placeholder|changeme|xxxxx|your[-_]|dummy|<[a-z_ -]{2,}>)")
INTERPOLATION = re.compile(r"^(?:\$\{|\$\(|\{\{|<%|%\(|#\{|\$[A-Za-z_])")
ALLOW_COMMENT = re.compile(r"(?i)(secrets-scan:\s*ignore|pragma:\s*allowlist\s+secret|noqa:\s*secret)")

DEFAULT_EXCLUDES = [".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "target",
                    "__pycache__", ".mypy_cache", ".pytest_cache", ".idea", ".gradle", ".terraform",
                    "coverage", ".next", ".nuxt"]
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz", ".tgz", ".bz2",
              ".xz", ".jar", ".war", ".class", ".so", ".dylib", ".dll", ".exe", ".bin", ".pyc", ".woff",
              ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".wav", ".svg"}
ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/=_\-]{24,}")
WORDY = re.compile(r"(?i)^(?:[a-z]+[-_/.][a-z0-9-_/.]+|[a-z]{4,}\d{0,4})$")


# ---------------------------------------------------------------- 工具

def mask(value):
    """只保留前 4 后 4 位，中间以 * 代替。"""
    v = value.strip()
    if len(v) <= 8:
        return "*" * len(v)
    return f"{v[:4]}{'*' * min(8, len(v) - 8)}{v[-4:]}"


def entropy(s):
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def is_placeholder(value):
    v = value.strip().strip("\"'")
    if not v or INTERPOLATION.match(v) or PLACEHOLDER.match(v) or PLACEHOLDER_SUB.search(v):
        return True
    return len(set(v)) <= 2


def load_ignore(root):
    """读取 .secretsignore：每行一个路径 glob；re: 开头的行是值白名单正则；# 注释。"""
    globs, values = [], []
    p = os.path.join(root, ".secretsignore")
    if not os.path.isfile(p):
        return globs, values
    with open(p, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("re:"):
                try:
                    values.append(re.compile(line[3:].strip()))
                except re.error:
                    pass
            else:
                globs.append(line.rstrip("/"))
    return globs, values


def ignored(rel, globs):
    parts = rel.split(os.sep)
    for g in globs:
        if fnmatch(rel, g) or fnmatch(os.path.basename(rel), g):
            return True
        if any(fnmatch(p, g) for p in parts):
            return True
        if g.endswith("/*") and rel.startswith(g[:-1]):
            return True
    return False


# ---------------------------------------------------------------- 扫描

def scan_text(text, where, opts, line_offset=0):
    """在文本上跑全部规则，返回命中列表；line_offset 用于把片段行号还原成文件行号。"""
    out = []
    for idx, line in enumerate(text.splitlines(), 1):
        if ALLOW_COMMENT.search(line):
            continue
        lineno = idx + line_offset
        if len(line) > 4096:
            line = line[:4096]
        for rid, sev, kind, rx, gi, fix in RULES:
            for m in rx.finditer(line):
                value = m.group(gi) if gi and m.group(gi) else m.group(0)
                if is_placeholder(value):
                    continue
                if any(rx2.search(value) for rx2 in opts["allow_values"]):
                    continue
                out.append({"rule": rid, "severity": sev, "type": kind, "where": where,
                            "line": lineno, "masked": mask(value), "length": len(value), "fix": fix})
        if opts["entropy"]:
            for m in ENTROPY_TOKEN.finditer(line):
                tok = m.group(0)
                if is_placeholder(tok) or WORDY.match(tok):
                    continue
                e = entropy(tok)
                hex_like = re.fullmatch(r"[0-9a-fA-F]{32,}", tok)
                if e >= 4.2 or (hex_like and e >= 3.2):
                    out.append({"rule": "SEC016", "severity": "info", "type": f"高熵字符串（熵 {e:.1f}）",
                                "where": where, "line": lineno, "masked": mask(tok), "length": len(tok),
                                "fix": "人工确认是不是密钥；是哈希/校验和可加进 .secretsignore 的 re: 白名单"})
    # 同一行同一值只报一次，保留级别最高的那条规则
    out.sort(key=lambda f: ORDER[f["severity"]])
    seen, uniq = set(), []
    for f in out:
        k = (f["where"], f["line"], f["masked"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def iter_files(paths, opts):
    excludes = set(DEFAULT_EXCLUDES) | set(opts["exclude"])
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in excludes and not ignored(os.path.relpath(os.path.join(root, d), p), opts["globs"])]
            for fn in files:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, p)
                if ignored(rel, opts["globs"]) or os.path.splitext(fn)[1].lower() in BINARY_EXT:
                    continue
                try:
                    if os.path.getsize(fp) > opts["max_bytes"]:
                        continue
                except OSError:
                    continue
                yield fp


def scan_tree(paths, opts):
    findings, scanned = [], 0
    for fp in iter_files(paths, opts):
        try:
            with open(fp, "rb") as f:
                blob = f.read()
        except OSError:
            continue
        if b"\x00" in blob[:8192]:
            continue
        scanned += 1
        text = blob.decode("utf-8", errors="replace")
        findings += scan_text(text, os.path.relpath(fp), opts)
    return findings, scanned


def scan_history(repo, n, opts):
    """用 git log -p 扫最近 n 个提交里新增的行。"""
    cmd = [GIT_BIN, "log", "-p", "-n", str(n), "--no-color", "--no-merges",
           "--unified=0", "--format=%x01%H%x1f%an%x1f%ad", "--date=short"]
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as e:
        return [], f"无法执行 {GIT_BIN}：{e}"
    if r.returncode != 0:
        msg = (r.stderr or "").strip().splitlines()
        return [], msg[0] if msg else "git log 执行失败（当前目录可能不是 git 仓库）"
    findings, commit, author, date, path, lineno, commits = [], "", "", "", "", 0, 0
    for line in r.stdout.splitlines():
        if line.startswith("\x01"):
            parts = line[1:].split("\x1f")
            commit, author, date = (parts + ["", "", ""])[:3]
            commits += 1
            continue
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("@@"):
            m = re.match(r"@@ -\S+ \+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            body = line[1:]
            if path and path != "/dev/null" and not ignored(path, opts["globs"]):
                where = f"{commit[:8]} {path}"
                for f in scan_text(body, where, opts, line_offset=lineno - 1):
                    f["commit"], f["author"], f["date"], f["path"] = commit[:8], author, date, path
                    findings.append(f)
            lineno += 1
    return findings, f"扫描了 {commits} 个提交"


# ---------------------------------------------------------------- 输出

ORDER = {"high": 0, "warn": 1, "info": 2}


def render(work, hist, scanned, hist_note, opts):
    def block(title, items):
        print(f"== {title}")
        if not items:
            print("  ✓ 没有命中")
            return
        for f in sorted(items, key=lambda x: (ORDER[x["severity"]], x["where"], x["line"])):
            print(f"  [{f['severity'].upper():4}] {f['rule']} {f['where']}:{f['line']}  {f['type']}")
            print(f"         值 {f['masked']}（长度 {f['length']}）")
            print(f"         → {f['fix']}")
    block(f"工作树（扫描 {scanned} 个文件）", work)
    if hist is not None:
        print()
        block(f"提交历史（{hist_note}）", hist)
    allf = work + (hist or [])
    c = {s: sum(1 for f in allf if f["severity"] == s) for s in ORDER}
    print(f"\n小计：high {c['high']} / warn {c['warn']} / info {c['info']}")
    if c["high"]:
        print("处置顺序：先吊销轮换密钥 → 再清理仓库与历史 → 最后补 .gitignore 与 CI 门禁")


def main():
    ap = argparse.ArgumentParser(description="仓库泄密自查（防御性只读扫描）")
    ap.add_argument("paths", nargs="*", help="文件或目录，默认当前目录")
    ap.add_argument("--history", type=int, metavar="N", help="额外扫描最近 N 个提交的新增行")
    ap.add_argument("--exclude", action="append", default=[], help="额外排除的目录名，可重复")
    ap.add_argument("--entropy", action="store_true", help="启用高熵字符串检测（info 级，噪声较多）")
    ap.add_argument("--min-severity", choices=["high", "warn", "info"], default="info", help="只显示不低于该级别的命中")
    ap.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024, help="跳过大于该字节数的文件")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 high/warn 则退出码 1")
    a = ap.parse_args()

    paths = a.paths or ["."]
    root = paths[0] if os.path.isdir(paths[0]) else os.path.dirname(os.path.abspath(paths[0])) or "."
    globs, allow_values = load_ignore(root)
    opts = {"exclude": a.exclude, "globs": globs, "allow_values": allow_values,
            "entropy": a.entropy, "max_bytes": a.max_bytes}

    work, scanned = scan_tree(paths, opts)
    hist, hist_note = (None, "")
    if a.history:
        hist, hist_note = scan_history(root, a.history, opts)

    keep = lambda fs: [f for f in fs if ORDER[f["severity"]] <= ORDER[a.min_severity]]
    work = keep(work)
    hist = keep(hist) if hist is not None else None

    if a.json:
        print(json.dumps({"scanned_files": scanned, "worktree": work,
                          "history": hist, "history_note": hist_note,
                          "summary": {s: sum(1 for f in work + (hist or []) if f["severity"] == s) for s in ORDER}},
                         ensure_ascii=False, indent=2))
    else:
        render(work, hist, scanned, hist_note, opts)
    bad = any(f["severity"] in ("high", "warn") for f in work + (hist or []))
    sys.exit(1 if (a.strict and bad) else 0)


if __name__ == "__main__":
    main()
