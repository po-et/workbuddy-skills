#!/usr/bin/env python3
"""国际化文案键检查：对齐多语言文件的键集合、空值与占位符，可选扫描源码里的使用情况。

用法：
  python3 i18n_missing_keys.py [locales 目录或文件 ...] [--base zh-CN] [--src src/] [--json] [--strict]
  --strict：存在 high（某语言缺键 / 源码用了未定义的键）则退出码 1。
支持 locales/<lang>.json、locales/<lang>/<命名空间>.json（键自动加命名空间前缀）、
messages_<lang>.properties、<lang>.properties。
"""
import argparse, json, os, re, sys

LOCALE_DIRS = ["locales", "locale", "i18n", "lang", "langs", "translations",
               "src/locales", "src/i18n", "public/locales", "app/locales",
               "src/main/resources/i18n", "src/main/resources"]
SRC_EXT = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".java", ".kt",
           ".py", ".php", ".rb", ".go", ".html", ".htm", ".ejs", ".hbs", ".erb"}
SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "target",
             "__pycache__", ".next", ".nuxt", "coverage", ".idea"}
LANG_RE = re.compile(r"^(?:messages?[._-]|strings[._-]|locale[._-])?([A-Za-z]{2}(?:[-_][A-Za-z0-9]{2,4})?)$")

# 占位符形态：{name} {{name}} {0} %s %d %1$s %(name)s
PLACEHOLDER = re.compile(r"\{\{\s*[\w.]+\s*\}\}|\{\s*[\w.]+\s*\}|%\(\w+\)[sdifx]|%\d+\$[sdifx]|%[sdifx]")

# 源码里的取文案调用
USE_PATTERNS = [
    re.compile(r"(?:^|[^\w$.])(?:i18n|intl|this\.\$i18n|\$i18n)?\.?\$?t[cel]?\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"(?:^|[^\w$.])(?:trans|translate|__|gettext)\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"formatMessage\(\s*\{[^{}]*?\bid\s*:\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"<FormattedMessage[^>]*?\bid=[\"']([^\"']+)[\"']"),
    re.compile(r"\bgetMessage\(\s*\"([^\"]+)\""),
    re.compile(r"\bi18nKey=[\"']([^\"']+)[\"']"),
]
DYNAMIC_USE = re.compile(r"(?:^|[^\w$.])\$?t\(\s*(?:`[^`]*\$\{|[A-Za-z_$][\w$]*\s*[,)])")


# ---------------------------------------------------------------- 读取语言文件

def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = ""
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        if not obj and prefix:
            out[prefix] = ""
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def load_properties(text):
    out, buf = {}, ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line[:1] in ("#", "!")):
            continue
        if line.endswith("\\"):
            buf += line[:-1]
            continue
        buf += line
        m = re.match(r"([^=:\s]+)\s*[=:]\s*(.*)$", buf)
        if m:
            out[m.group(1)] = m.group(2).strip()
        buf = ""
    return out


def lang_of(stem):
    m = LANG_RE.match(stem)
    if m:
        return m.group(1).replace("_", "-")
    m = re.search(r"[._-]([A-Za-z]{2}(?:[-_][A-Za-z0-9]{2,4})?)$", stem)
    return m.group(1).replace("_", "-") if m else stem


def read_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if path.lower().endswith(".json"):
        return flatten(json.loads(text))
    return load_properties(text)


def collect(paths, errors):
    """返回 {lang: {"files": [...], "data": {key: value}}}。"""
    langs = {}

    def add(lang, path, prefix=""):
        try:
            data = read_file(path)
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{path} 解析失败：{e}")
            return
        slot = langs.setdefault(lang, {"files": [], "data": {}})
        slot["files"].append(path)
        for k, v in data.items():
            slot["data"][f"{prefix}{k}"] = v

    for p in paths:
        if os.path.isfile(p):
            add(lang_of(os.path.splitext(os.path.basename(p))[0]), p)
            continue
        if not os.path.isdir(p):
            errors.append(f"路径不存在：{p}")
            continue
        for entry in sorted(os.listdir(p)):
            full = os.path.join(p, entry)
            stem, ext = os.path.splitext(entry)
            if os.path.isfile(full) and ext.lower() in (".json", ".properties"):
                add(lang_of(stem), full)
            elif os.path.isdir(full) and entry not in SKIP_DIRS:
                for root, dirs, files in os.walk(full):
                    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                    for fn in sorted(files):
                        if os.path.splitext(fn)[1].lower() not in (".json", ".properties"):
                            continue
                        rel = os.path.relpath(os.path.join(root, fn), full)
                        ns = os.path.splitext(rel)[0].replace(os.sep, ".")
                        add(lang_of(entry), os.path.join(root, fn), f"{ns}." if ns != "index" else "")
    return langs


def find_locale_dirs():
    return [d for d in LOCALE_DIRS if os.path.isdir(d)][:1]


# ---------------------------------------------------------------- 源码扫描

def scan_src(dirs):
    used, dynamic = {}, 0
    for d in dirs:
        for root, subs, files in os.walk(d):
            subs[:] = [s for s in subs if s not in SKIP_DIRS]
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in SRC_EXT:
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    for rx in USE_PATTERNS:
                        for m in rx.finditer(line):
                            key = m.group(1)
                            if key and not key.startswith(("http", "/", "#")) and " " not in key:
                                used.setdefault(key, []).append(f"{fp}:{i}")
                    if DYNAMIC_USE.search(line):
                        dynamic += 1
    return used, dynamic


# ---------------------------------------------------------------- 检查

def placeholders(v):
    return sorted(PLACEHOLDER.findall(str(v))) if isinstance(v, str) else []


def is_empty(v):
    return v is None or (isinstance(v, str) and not v.strip())


def analyse(langs, base):
    bdata = langs[base]["data"]
    report = []
    for lang in sorted(langs):
        data = langs[lang]["data"]
        missing = sorted(k for k in bdata if k not in data)
        extra = sorted(k for k in data if k not in bdata)
        empty = sorted(k for k, v in data.items() if is_empty(v))
        ph = []
        for k, v in sorted(data.items()):
            if k in bdata and not is_empty(v) and not is_empty(bdata[k]):
                a, b = placeholders(bdata[k]), placeholders(v)
                if a != b:
                    ph.append({"key": k, "base": a, "lang": b})
        report.append({"lang": lang, "is_base": lang == base, "files": langs[lang]["files"],
                       "keys": len(data), "missing": missing, "extra": extra,
                       "empty": empty, "placeholder": ph})
    return report


ORDER = {"high": 0, "warn": 1, "info": 2}


def main():
    ap = argparse.ArgumentParser(description="国际化文案键检查")
    ap.add_argument("paths", nargs="*", help="locales 目录或语言文件，默认自动探测 locales/ 等常见目录")
    ap.add_argument("--base", help="基准语言（如 zh-CN），默认取键最多的那个")
    ap.add_argument("--src", action="append", default=[], help="扫描源码目录找未定义/未使用的键，可重复")
    ap.add_argument("--limit", type=int, default=20, help="每类问题最多列出多少个键")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 high（缺键/未定义键）则退出码 1")
    a = ap.parse_args()

    errors = []
    paths = a.paths or find_locale_dirs()
    if not paths:
        print("没找到语言文件目录，请显式传入，如 python3 i18n_missing_keys.py locales/", file=sys.stderr)
        sys.exit(2)
    langs = collect(paths, errors)
    if not langs:
        print(f"在 {', '.join(paths)} 下没找到 .json / .properties 语言文件", file=sys.stderr)
        sys.exit(2)
    base = a.base or max(langs, key=lambda l: len(langs[l]["data"]))
    if base not in langs:
        print(f"基准语言 {base} 不存在，可选：{', '.join(sorted(langs))}", file=sys.stderr)
        sys.exit(2)

    report = analyse(langs, base)
    used, dynamic, undefined, unused = {}, 0, [], []
    if a.src:
        used, dynamic = scan_src(a.src)
        bdata = langs[base]["data"]
        undefined = sorted(k for k in used if k not in bdata)
        unused = sorted(k for k in bdata if k not in used)

    high = sum(len(r["missing"]) for r in report) + len(undefined)
    warn = sum(len(r["empty"]) + len(r["placeholder"]) for r in report)
    info = sum(len(r["extra"]) for r in report) + len(unused)

    if a.json:
        print(json.dumps({"base": base, "languages": report,
                          "source": {"scanned": bool(a.src), "used_keys": len(used),
                                     "dynamic_calls": dynamic, "undefined": undefined,
                                     "unused": unused} if a.src else None,
                          "summary": {"high": high, "warn": warn, "info": info},
                          "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1 if (a.strict and high) else 0)

    def listing(items, tail=""):
        for k in items[:a.limit]:
            print(f"      - {k}{tail}")
        if len(items) > a.limit:
            print(f"      … 还有 {len(items) - a.limit} 个")

    print(f"== 语言文件（基准 {base}，{len(langs[base]['data'])} 个键）")
    for r in report:
        flag = " ←基准" if r["is_base"] else ""
        where = os.path.commonpath(r["files"]) if len(r["files"]) > 1 else r["files"][0]
        print(f"  {r['lang']:10s} {r['keys']:5d} 键  {where}{flag}")
    for e in errors:
        print(f"  ! {e}")
    for r in report:
        if r["is_base"]:
            continue
        if not (r["missing"] or r["extra"] or r["empty"] or r["placeholder"]):
            print(f"\n  ✓ {r['lang']} 与基准完全对齐")
            continue
        print(f"\n-- {r['lang']}")
        if r["missing"]:
            print(f"  [HIGH] 缺失 {len(r['missing'])} 个键（基准有、该语言没有）")
            listing(r["missing"])
            print("      → 补齐翻译；确实不需要的键从基准语言里删掉，不要留半套")
        if r["empty"]:
            print(f"  [WARN] 空值 {len(r['empty'])} 个（键在但文案为空）")
            listing(r["empty"])
            print("      → 空值通常比缺键更危险，界面会显示空白而不是回退到基准语言")
        if r["placeholder"]:
            print(f"  [WARN] 占位符不一致 {len(r['placeholder'])} 个")
            for p in r["placeholder"][:a.limit]:
                print(f"      - {p['key']}  基准 {p['base'] or '无'} / {r['lang']} {p['lang'] or '无'}")
            if len(r["placeholder"]) > a.limit:
                print(f"      … 还有 {len(r['placeholder']) - a.limit} 个")
            print("      → 占位符数量或名字对不上，运行时要么渲染出 undefined，要么直接抛异常")
        if r["extra"]:
            print(f"  [INFO] 多余 {len(r['extra'])} 个键（基准没有）")
            listing(r["extra"])
            print("      → 多半是基准语言删键时漏删，或该语言先行加了新文案")

    if a.src:
        print(f"\n-- 源码使用情况（扫描 {', '.join(a.src)}，识别到 {len(used)} 个静态键，{dynamic} 处动态拼接调用）")
        if undefined:
            print(f"  [HIGH] 源码用了但基准语言没有的键 {len(undefined)} 个")
            for k in undefined[:a.limit]:
                print(f"      - {k}   {used[k][0]}")
            if len(undefined) > a.limit:
                print(f"      … 还有 {len(undefined) - a.limit} 个")
            print("      → 界面上会直接显示键名；补进基准语言或修正拼写")
        if unused:
            print(f"  [INFO] 基准语言有、源码里没搜到的键 {len(unused)} 个")
            listing(unused)
            print("      → 动态拼接的键搜不到，删之前先确认；确认无用再清理，避免文案膨胀")
        if not undefined and not unused:
            print("  ✓ 源码与基准语言完全对得上")

    print(f"\n小计：high {high} / warn {warn} / info {info}")
    sys.exit(1 if (a.strict and high) else 0)


if __name__ == "__main__":
    main()
