#!/usr/bin/env python3
"""测试覆盖缺口：按命名约定找出没有对应测试的源码文件，并解析覆盖率报告找最薄弱的文件。

用法：
  python3 test_coverage_gap.py [目录 ...] [--days 30] [--coverage coverage.xml] [--json] [--strict]
  --strict：存在 high（最近改动过却没有测试、或覆盖率为 0 的文件）则退出码 1。
  git 可执行文件用环境变量 GIT_BIN 覆盖（默认 git）；不在 git 仓库里也能跑，只是没有改动热度排序。
支持 Cobertura（coverage.xml）与 lcov（lcov.info）两种覆盖率格式。
"""
import argparse, json, os, re, subprocess, sys
import xml.etree.ElementTree as ET

GIT_BIN = os.environ.get("GIT_BIN", "git")

SRC_EXT = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".go", ".java", ".kt",
           ".rb", ".php", ".cs", ".scala"}
SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "target", "out",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".next", ".nuxt", "coverage", ".idea",
             "migrations", "node_modules", "bin", "obj", "gen", "generated", "testdata", ".gradle"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e", "cypress", "it"}
SKIP_FILE = re.compile(r"(?i)^(?:__init__\.py|conftest\.py|setup\.py|index\.[jt]sx?|main\.[jt]sx?|"
                       r".*\.d\.ts|.*\.config\.[jt]s|.*\.min\.js|.*_pb2?\.py|.*\.pb\.go|"
                       r".*_generated\..*|.*\.generated\..*|Program\.cs|AssemblyInfo\.cs)$")
TEST_FILE = [
    re.compile(r"^test_(?P<stem>.+)\.py$"), re.compile(r"^(?P<stem>.+)_test\.py$"),
    re.compile(r"^(?P<stem>.+)_test\.go$"),
    re.compile(r"^(?P<stem>.+)\.(?:test|spec|cy)\.[jt]sx?$"),
    re.compile(r"^(?P<stem>.+)(?:Test|Tests|IT|ITCase|TestCase)\.(?:java|kt|cs|php)$"),
    re.compile(r"^Test(?P<stem>.+)\.(?:java|kt|cs)$"),
    re.compile(r"^(?P<stem>.+)_(?:test|spec)\.rb$"), re.compile(r"^(?P<stem>.+)Spec\.(?:scala|kt)$"),
    re.compile(r"^(?P<stem>.+)\.test\.vue$"),
]


# ---------------------------------------------------------------- 扫描

def is_test_path(rel):
    parts = rel.replace("\\", "/").split("/")
    if any(p.lower() in TEST_DIRS for p in parts[:-1]):
        return True
    return any(rx.match(parts[-1]) for rx in TEST_FILE)


def test_stems(name):
    """测试文件名能覆盖到的源码 stem 集合。"""
    out = {os.path.splitext(name)[0]}
    for rx in TEST_FILE:
        m = rx.match(name)
        if m:
            out.add(m.group("stem"))
    stem = os.path.splitext(name)[0]
    for pre in ("test_", "test", "Test"):
        if stem.startswith(pre) and len(stem) > len(pre):
            out.add(stem[len(pre):])
    for suf in ("_test", "Test", "Tests", "_spec", "Spec", ".test", ".spec", "IT"):
        if stem.endswith(suf) and len(stem) > len(suf):
            out.add(stem[: -len(suf)])
    return {s for s in out if s}


def loc(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for l in f if l.strip())
    except OSError:
        return 0


def walk(roots, excludes):
    sources, tests = [], []
    skip = SKIP_DIRS | set(excludes)
    for root in roots:
        for dp, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in SRC_EXT:
                    continue
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, ".").replace("\\", "/")
                if is_test_path(rel):
                    tests.append((rel, fn))
                elif not SKIP_FILE.match(fn):
                    sources.append(rel)
    return sources, tests


def git_churn(repo, days):
    """返回 {相对路径: 提交次数}；不是 git 仓库时返回 ({}, 原因)。"""
    cmd = [GIT_BIN, "log", f"--since={days} days ago", "--name-only", "--pretty=format:", "--no-merges"]
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return {}, f"无法执行 {GIT_BIN}：{e}"
    if r.returncode != 0:
        msg = (r.stderr or "").strip().splitlines()
        return {}, msg[0] if msg else "git log 执行失败（当前目录可能不是 git 仓库）"
    churn = {}
    for line in r.stdout.splitlines():
        p = line.strip()
        if p:
            churn[p] = churn.get(p, 0) + 1
    return churn, f"最近 {days} 天有 {len(churn)} 个文件被改动"


# ---------------------------------------------------------------- 覆盖率

def parse_cobertura(path):
    root = ET.parse(path).getroot()
    out = {}
    for cls in root.iter("class"):
        fn = cls.get("filename")
        if not fn:
            continue
        lines = [l for l in cls.iter("line") if l.get("number")]
        total = len(lines)
        hit = sum(1 for l in lines if (l.get("hits") or "0") not in ("0", ""))
        if not total:
            rate = float(cls.get("line-rate") or 0)
            total, hit = 1, (1 if rate > 0 else 0)
        prev = out.get(fn)
        if prev:
            total, hit = prev["lines"] + total, prev["covered"] + hit
        out[fn] = {"lines": total, "covered": hit, "rate": hit / total if total else 0.0}
    return out


def parse_lcov(path):
    out, cur = {}, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("SF:"):
                cur = line[3:]
                out.setdefault(cur, {"lines": 0, "covered": 0, "rate": 0.0})
            elif line.startswith("DA:") and cur:
                part = line[3:].split(",")
                if len(part) >= 2:
                    out[cur]["lines"] += 1
                    out[cur]["covered"] += 1 if part[1].strip() not in ("0", "") else 0
            elif line.startswith("LF:") and cur and not out[cur]["lines"]:
                out[cur]["lines"] = int(line[3:] or 0)
            elif line.startswith("LH:") and cur and not out[cur]["covered"]:
                out[cur]["covered"] = int(line[3:] or 0)
            elif line == "end_of_record" and cur:
                d = out[cur]
                d["rate"] = d["covered"] / d["lines"] if d["lines"] else 0.0
                cur = None
    for d in out.values():
        if d["lines"] and not d["rate"]:
            d["rate"] = d["covered"] / d["lines"]
    return out


def load_coverage(path):
    if not os.path.isfile(path):
        raise ValueError(f"覆盖率文件不存在：{path}")
    head = open(path, encoding="utf-8", errors="replace").read(4096)
    if head.lstrip().startswith("<") or path.lower().endswith(".xml"):
        try:
            return parse_cobertura(path), "cobertura"
        except ET.ParseError as e:
            raise ValueError(f"Cobertura XML 解析失败：{e}") from e
    if "SF:" in head or path.lower().endswith((".info", ".lcov")):
        return parse_lcov(path), "lcov"
    raise ValueError(f"无法识别覆盖率格式（既不像 Cobertura XML 也不像 lcov）：{path}")


def match_coverage(rel, cov, index):
    """按路径后缀匹配覆盖率条目，最长后缀优先。"""
    if rel in cov:
        return rel
    base = os.path.basename(rel)
    best, best_len = None, -1
    for cand in index.get(base, ()):
        a, b = rel.split("/"), cand.replace("\\", "/").split("/")
        n = 0
        while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
            n += 1
        if n > best_len:
            best, best_len = cand, n
    return best


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="测试覆盖缺口")
    ap.add_argument("paths", nargs="*", default=["."], help="源码目录，默认当前目录")
    ap.add_argument("--days", type=int, default=30, help="统计最近多少天的 git 改动做优先级排序")
    ap.add_argument("--coverage", help="coverage.xml（Cobertura）或 lcov.info")
    ap.add_argument("--min-cov", type=float, default=50.0, help="低于该行覆盖率算 warn（百分比）")
    ap.add_argument("--min-lines", type=int, default=10, help="小于该行数的源码文件不算缺口")
    ap.add_argument("--exclude", action="append", default=[], help="额外排除的目录名，可重复")
    ap.add_argument("--limit", type=int, default=30, help="每类最多列出多少个文件")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 high 则退出码 1")
    a = ap.parse_args()

    roots = a.paths or ["."]
    for p in roots:
        if not os.path.isdir(p):
            print(f"目录不存在：{p}", file=sys.stderr)
            sys.exit(2)
    sources, tests = walk(roots, a.exclude)
    covered_stems = {}
    for rel, name in tests:
        for s in test_stems(name):
            covered_stems.setdefault(s, []).append(rel)

    cov, cov_kind, cov_index = {}, None, {}
    if a.coverage:
        try:
            cov, cov_kind = load_coverage(a.coverage)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
        for k in cov:
            cov_index.setdefault(os.path.basename(k), []).append(k)

    churn, churn_note = ({}, "未统计 git 改动")
    if a.days > 0:
        churn, churn_note = git_churn(roots[0] if os.path.isdir(roots[0]) else ".", a.days)

    gaps = []
    for rel in sources:
        stem = os.path.splitext(os.path.basename(rel))[0]
        if stem in covered_stems:
            continue
        n = loc(rel)
        if n < a.min_lines:
            continue
        key = match_coverage(rel, cov, cov_index)
        rate = cov[key]["rate"] * 100 if key else None
        hits = churn.get(rel, 0) or churn.get(os.path.normpath(rel), 0)
        if rate is not None and rate > 0:
            sev, why = "info", f"无同名测试，但覆盖率报告显示被间接覆盖 {rate:.0f}%"
        elif hits:
            sev, why = "high", f"最近 {a.days} 天改动 {hits} 次且没有任何测试"
        else:
            sev, why = "warn", "没有对应测试文件"
        gaps.append({"file": rel, "lines": n, "churn": hits, "coverage": rate,
                     "severity": sev, "reason": why})
    gaps.sort(key=lambda g: (-g["churn"], -g["lines"]))

    low, zero = [], []
    if cov:
        used = set()
        for rel in sources:
            key = match_coverage(rel, cov, cov_index)
            if not key or key in used:
                continue
            used.add(key)
            rate = cov[key]["rate"] * 100
            item = {"file": rel, "coverage": rate, "lines": cov[key]["lines"],
                    "covered": cov[key]["covered"], "churn": churn.get(rel, 0)}
            (zero if rate <= 0 else low).append(item)
        zero.sort(key=lambda x: (-x["churn"], -x["lines"]))
        low = sorted([x for x in low if x["coverage"] < a.min_cov], key=lambda x: x["coverage"])
    total_lines = sum(v["lines"] for v in cov.values()) or 0
    total_cov = (sum(v["covered"] for v in cov.values()) / total_lines * 100) if total_lines else None

    # 覆盖率为 0 算 high、偏低算 warn，与上面的缺口去重，避免同一个文件被数两次
    high_set = {g["file"] for g in gaps if g["severity"] == "high"} | {z["file"] for z in zero}
    warn_set = ({g["file"] for g in gaps if g["severity"] == "warn"} | {x["file"] for x in low}) - high_set
    info_set = {g["file"] for g in gaps if g["severity"] == "info"} - high_set - warn_set
    counts = {"high": len(high_set), "warn": len(warn_set), "info": len(info_set)}

    if a.json:
        print(json.dumps({
            "sources": len(sources), "tests": len(tests), "untested": len(gaps),
            "days": a.days, "churn_note": churn_note,
            "coverage_format": cov_kind, "total_coverage": total_cov,
            "gaps": gaps, "zero_coverage": zero, "low_coverage": low,
            "summary": counts}, ensure_ascii=False, indent=2))
        sys.exit(1 if (a.strict and counts["high"]) else 0)

    pct = f"{len(gaps) / len(sources) * 100:.0f}%" if sources else "0%"
    print(f"== 测试覆盖缺口（{', '.join(roots)}）")
    print(f"  源码文件 {len(sources)} 个 · 测试文件 {len(tests)} 个 · 无对应测试 {len(gaps)} 个（{pct}）")
    print(f"  {churn_note}")
    if cov_kind:
        tc = f"{total_cov:.1f}%" if total_cov is not None else "未知"
        print(f"  覆盖率报告 {a.coverage}（{cov_kind}）总行覆盖率 {tc}，{len(cov)} 个文件有数据")

    since = f"最近 {a.days} 天改动过、" if a.days > 0 else ""
    for sev, title, tip in (
            ("high", f"{since}没有任何测试且不在覆盖率里",
             "改动频繁又没测试＝下次故障的高发区，优先补；先补一条覆盖主路径的用例，别追求一次到位"),
            ("warn", "没有对应测试文件",
             "存量缺口，按业务重要性排期；纯数据类、常量类文件可以用 --min-lines 或 --exclude 过滤掉"),
            ("info", "无同名测试但被间接覆盖",
             "有覆盖率兜底，风险较低；如果是核心逻辑仍建议补直接的单元测试")):
        sub = [g for g in gaps if g["severity"] == sev]
        print(f"\n[{sev.upper()}] {title}（{len(sub)}）")
        if not sub:
            print("  ✓ 无")
            continue
        print(f"  {'改动':>4}  {'行数':>5}  文件")
        for g in sub[:a.limit]:
            extra = f"  （覆盖 {g['coverage']:.0f}%）" if g["coverage"] else ""
            print(f"  {g['churn']:>4}  {g['lines']:>5}  {g['file']}{extra}")
        if len(sub) > a.limit:
            print(f"  … 还有 {len(sub) - a.limit} 个")
        print(f"  → {tip}")

    if cov_kind:
        print(f"\n[HIGH] 覆盖率为 0 的文件（{len(zero)}）")
        if zero:
            for x in zero[:a.limit]:
                ratio = f"{x['covered']}/{x['lines']}"
                print(f"  {x['coverage']:5.1f}%  {ratio:>9} 行  {x['file']}")
            print("  → 这些文件一行都没被执行过，要么是死代码可以删，要么是完全没测，二选一")
        else:
            print("  ✓ 无")
        print(f"\n[WARN] 行覆盖率低于 {a.min_cov:.0f}% 的文件（{len(low)}）")
        if low:
            for x in low[:a.limit]:
                ratio = f"{x['covered']}/{x['lines']}"
                print(f"  {x['coverage']:5.1f}%  {ratio:>9} 行  {x['file']}")
            if len(low) > a.limit:
                print(f"  … 还有 {len(low) - a.limit} 个")
            print("  → 看未覆盖的是不是异常分支与边界条件，那里通常才是 bug 藏身处")
        else:
            print("  ✓ 无")

    print(f"\n小计：high {counts['high']} / warn {counts['warn']} / info {counts['info']}")
    sys.exit(1 if (a.strict and counts["high"]) else 0)


if __name__ == "__main__":
    main()
