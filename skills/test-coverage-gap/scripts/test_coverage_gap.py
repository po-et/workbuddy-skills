#!/usr/bin/env python3
"""测试覆盖缺口：分开报告命名测试线索与覆盖率，遇到路径歧义保留证据。

用法：
  python3 test_coverage_gap.py [目录 ...] [--days 30] [--coverage coverage.xml] [--json] [--strict]
  --strict：存在 high 或提供报告后仍有未知 / 歧义覆盖率，退出码 1。
  --coverage-map REPORT_PREFIX=SOURCE_PREFIX 显式映射路径；--output 保存完整 Markdown。
  git 可执行文件用环境变量 GIT_BIN 覆盖（默认 git）；不在 git 仓库里也能跑，只是没有改动热度排序。
支持 Cobertura（coverage.xml）与 lcov（lcov.info）两种覆盖率格式。
"""
import argparse, json, math, os, posixpath, re, subprocess, sys
from pathlib import Path
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
    """测试文件名按约定可关联的源码 stem 集合；不作为执行证据。"""
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
            dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith("."))
            for fn in sorted(files):
                if os.path.splitext(fn)[1].lower() not in SRC_EXT:
                    continue
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, ".").replace("\\", "/")
                if is_test_path(rel):
                    tests.append((rel, fn))
                elif not SKIP_FILE.match(fn):
                    sources.append(rel)
    return sorted(set(sources)), sorted(set(tests))


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


# ---------------------------------------------------------------- 路径证据

def normalize_path(path):
    """只统一分隔符和点段；不改变大小写、不猜测工作区根目录。"""
    return posixpath.normpath(str(path).strip().replace("\\", "/"))


def match_coverage(rel, cov, index=None):
    """返回匹配证据；最长后缀并列时保留全部候选，绝不取第一条。"""
    rel = normalize_path(rel)
    base = posixpath.basename(rel)
    pool = sorted(index.get(base, ())) if index is not None else sorted(cov)
    candidates = [key for key in pool if normalize_path(key) == rel]
    if len(candidates) == 1:
        return {"confidence": "exact", "matched_path": candidates[0], "candidates": candidates}
    if len(candidates) > 1:
        return {"confidence": "ambiguous", "matched_path": None, "candidates": candidates}
    best, longest = [], 0
    for cand in pool:
        a, b = rel.split("/"), normalize_path(cand).split("/")
        n = 0
        while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
            n += 1
        if n > longest:
            best, longest = [cand], n
        elif n and n == longest:
            best.append(cand)
    confidence = "suffix_unique" if len(best) == 1 else "ambiguous" if best else "unmatched"
    return {"confidence": confidence, "matched_path": best[0] if len(best) == 1 else None,
            "candidates": best, "suffix_components": longest}


def coverage_matches(sources, cov):
    """同一条报告不能默默成为两个源码文件的覆盖证据。精确匹配优先。"""
    index = {}
    for key in cov:
        index.setdefault(posixpath.basename(normalize_path(key)), []).append(key)
    matches = {rel: match_coverage(rel, cov, index) for rel in sorted(sources)}
    claims = {}
    for rel, evidence in matches.items():
        if evidence["matched_path"] is not None:
            claims.setdefault(evidence["matched_path"], []).append(rel)
    for key, owners in claims.items():
        if len(owners) <= 1:
            continue
        exact = [p for p in owners if matches[p]["confidence"] == "exact"]
        for rel in owners:
            if len(exact) == 1 and rel == exact[0]:
                continue
            matches[rel].update(confidence="ambiguous", matched_path=None,
                                source_candidates=sorted(owners))
    return matches


# 命名路径的结构层；模块名、包名保留。这里只生成测试文件线索，不证明执行。
STRUCTURAL_DIRS = TEST_DIRS | {"src", "source", "sources", "lib", "main"}


def test_scope(path):
    return tuple(p for p in normalize_path(path).split("/")[:-1]
                 if p.lower() not in STRUCTURAL_DIRS)


def test_matches(sources, tests):
    matches, claims = {}, {}
    for rel in sorted(sources):
        stem = posixpath.splitext(posixpath.basename(rel))[0]
        candidates = sorted(t for t, name in tests
                            if stem in test_stems(name) and test_scope(rel) == test_scope(t))
        matches[rel] = {"confidence": "convention_unique" if len(candidates) == 1
                       else "convention_multiple" if candidates else "unmatched",
                       "candidates": candidates,
                       "execution_proven": False}
        for t in candidates:
            claims.setdefault(t, []).append(rel)
    for test, owners in claims.items():
        if len(owners) > 1:
            for rel in owners:
                matches[rel].update(confidence="ambiguous", source_candidates=sorted(owners))
    return matches


# ---------------------------------------------------------------- 覆盖率解析

def nonnegative_int(value, label, positive=False):
    text = str(value)
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"{label} 必须是非负整数：{text!r}")
    number = int(text)
    if positive and number == 0:
        raise ValueError(f"{label} 必须大于 0")
    return number


def checked_rate(value, label):
    try:
        rate = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} 不是有效覆盖率：{value!r}") from exc
    if not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError(f"{label} 必须在 0 到 1 之间")
    return rate


def merge_lines(existing, incoming, filename):
    for number, hits in incoming.items():
        if number in existing and existing[number] != hits:
            raise ValueError(f"重复覆盖率条目冲突：{filename}:{number}")
        existing[number] = hits


def line_stats(lines):
    total = len(lines)
    hit = sum(1 for value in lines.values() if value > 0)
    return {"lines": total, "covered": hit, "rate": hit / total if total else None}


def parse_cobertura(path):
    data = Path(path).read_bytes()
    # ElementTree.fromstring 不取外部 DTD。允许常见 Cobertura 的外部声明，
    # 拒绝内部子集与实体声明，防止内部实体展开；从不请求声明中的 URL。
    if b"\x00" in data:
        raise ValueError("覆盖率 XML 须使用 UTF-8 等 ASCII 兼容编码，不接受含空字节的 XML")
    doctypes = re.findall(br"<!\s*DOCTYPE\b[^>]*>", data, re.I)
    if re.search(br"<!\s*ENTITY\b", data, re.I) or any(b"[" in declaration for declaration in doctypes):
        raise ValueError("覆盖率 XML 不接受 DTD 内部子集或实体声明")
    root = ET.fromstring(data)
    tag = lambda element: element.tag.rsplit("}", 1)[-1]
    if tag(root) != "coverage":
        raise ValueError("不是 Cobertura coverage 根节点")
    all_lines, summaries = {}, {}
    for cls in root.iter():
        if tag(cls) != "class":
            continue
        fn = cls.get("filename")
        if not fn or not fn.strip():
            raise ValueError("Cobertura class 缺少 filename")
        fn = normalize_path(fn)
        rate_value = cls.get("line-rate")
        rate = checked_rate(rate_value, f"{fn} line-rate") if rate_value is not None else None
        entries = {}
        for line in cls.iter():
            if tag(line) != "line":
                continue
            number = nonnegative_int(line.get("number"), f"{fn} line number", positive=True)
            hits = nonnegative_int(line.get("hits"), f"{fn}:{number} hits")
            merge_lines(entries, {number: hits}, fn)
        if entries:
            if fn in summaries:
                raise ValueError(f"重复覆盖率条目冲突（明细与摘要混用）：{fn}")
            merge_lines(all_lines.setdefault(fn, {}), entries, fn)
        else:
            if fn in all_lines:
                raise ValueError(f"重复覆盖率条目冲突（摘要与明细混用）：{fn}")
            # 摘要没有可执行行数量，保留百分比但不虚构 1 行 / 100%。
            item = {"lines": None, "covered": None, "rate": rate}
            if fn in summaries and summaries[fn] != item:
                raise ValueError(f"重复覆盖率摘要冲突：{fn}")
            summaries[fn] = item
    out = {fn: line_stats(lines) for fn, lines in all_lines.items()}
    out.update(summaries)
    if not out:
        raise ValueError("Cobertura 没有文件覆盖率条目")
    return dict(sorted(out.items()))


def parse_lcov(path):
    line_data, summaries, current = {}, {}, None
    def finish(record):
        fn, entries = record["file"], record["entries"]
        lf, lh = record.get("LF"), record.get("LH")
        if (lf is None) != (lh is None):
            raise ValueError(f"{fn} 的 LF / LH 必须同时提供")
        if lf is not None and lh > lf:
            raise ValueError(f"{fn} 的 LH 不能大于 LF")
        if entries:
            stats = line_stats(entries)
            if lf is not None and (lf != stats["lines"] or lh != stats["covered"]):
                raise ValueError(f"{fn} 的 LF / LH 与 DA 明细冲突")
            if fn in summaries:
                raise ValueError(f"重复覆盖率条目冲突（摘要与明细混用）：{fn}")
            merge_lines(line_data.setdefault(fn, {}), entries, fn)
        elif lf is not None:
            item = {"lines": lf, "covered": lh, "rate": lh / lf if lf else None}
            if fn in line_data or (fn in summaries and summaries[fn] != item):
                raise ValueError(f"重复覆盖率摘要冲突：{fn}")
            summaries[fn] = item
        else:
            raise ValueError(f"{fn} 没有 DA 明细或 LF / LH 摘要")

    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("TN:"):
            continue
        if line.startswith("SF:"):
            if current is not None:
                raise ValueError(f"lcov 第 {number} 行：上一记录缺少 end_of_record")
            filename = line[3:].strip()
            if not filename:
                raise ValueError(f"lcov 第 {number} 行：SF 路径为空")
            current = {"file": normalize_path(filename), "entries": {}}
        elif line == "end_of_record":
            if current is None:
                raise ValueError(f"lcov 第 {number} 行：没有对应的 SF")
            finish(current)
            current = None
        elif line.startswith(("DA:", "LF:", "LH:")):
            if current is None:
                raise ValueError(f"lcov 第 {number} 行：覆盖率数据前缺少 SF")
            key, value = line.split(":", 1)
            if key == "DA":
                parts = value.split(",")
                if len(parts) not in (2, 3):
                    raise ValueError(f"lcov 第 {number} 行：DA 格式错误")
                line_no = nonnegative_int(parts[0], "DA 行号", positive=True)
                hits = nonnegative_int(parts[1], "DA 命中次数")
                merge_lines(current["entries"], {line_no: hits}, current["file"])
            else:
                count = nonnegative_int(value, key)
                if key in current and current[key] != count:
                    raise ValueError(f"lcov 第 {number} 行：重复 {key} 冲突")
                current[key] = count
        elif not line.startswith(("FN:", "FNDA:", "FNF:", "FNH:", "BRDA:", "BRF:", "BRH:")):
            raise ValueError(f"lcov 第 {number} 行：无法识别记录")
    if current is not None:
        raise ValueError("lcov 最后一条记录缺少 end_of_record")
    out = {fn: line_stats(lines) for fn, lines in line_data.items()}
    out.update(summaries)
    if not out:
        raise ValueError("lcov 没有文件覆盖率条目")
    return dict(sorted(out.items()))


def load_coverage(path):
    if not os.path.isfile(path):
        raise ValueError(f"覆盖率文件不存在：{path}")
    try:
        head = Path(path).read_bytes()[:4096].lstrip()
        if head.startswith(b"<") or path.lower().endswith(".xml"):
            return parse_cobertura(path), "cobertura"
        if b"SF:" in head or path.lower().endswith((".info", ".lcov")):
            return parse_lcov(path), "lcov"
    except (OSError, UnicodeError, ET.ParseError) as exc:
        raise ValueError(f"覆盖率报告读取或解析失败：{exc}") from exc
    raise ValueError(f"无法识别覆盖率格式（Cobertura XML / lcov）：{path}")


def map_prefixes(cov, mappings):
    parsed = []
    for mapping in mappings:
        if "=" not in mapping:
            raise ValueError("--coverage-map 格式为 报告路径前缀=源码路径前缀")
        report, source = mapping.split("=", 1)
        if not report.strip() or not source.strip():
            raise ValueError("--coverage-map 两侧都必须是路径；仓库根目录请用 .")
        parsed.append((normalize_path(report), normalize_path(source)))
    out = {}
    for filename, item in cov.items():
        alternatives = []
        for report, source in parsed:
            relative_root = report == "." and not filename.startswith("/") and not re.match(r"^[A-Za-z]:/", filename)
            if relative_root or filename == report or filename.startswith(report.rstrip("/") + "/"):
                suffix = filename if relative_root else filename[len(report):].lstrip("/")
                alternatives.append((len(report), normalize_path(posixpath.join(source, suffix))))
        key = filename
        if alternatives:
            maximum = max(size for size, _ in alternatives)
            targets = {target for size, target in alternatives if size == maximum}
            if len(targets) != 1:
                raise ValueError(f"路径前缀映射冲突：{filename}")
            key = targets.pop()
        if key in out and out[key] != item:
            raise ValueError(f"路径前缀映射后覆盖率冲突：{key}")
        out[key] = item
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- 输出与门禁

def render_markdown(report, limit=None):
    esc = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["# 测试覆盖缺口", "", f"源码 {report['sources']} 个；测试文件 {report['tests']} 个；"
             f"缺少明确命名测试线索 {report['untested']} 个。", "", report["churn_note"], "",
             "命名映射仅提供测试文件线索；覆盖率来自输入报告，均不证明测试质量或当前执行。", ""]
    for note in report["notes"]:
        lines += [f"- {note}"]
    sections = [("命名测试线索缺口", report["gaps"]),
                ("报告零覆盖", report["zero_coverage"]),
                ("报告低覆盖", report["low_coverage"]),
                ("覆盖率未知 / 路径歧义", report["coverage_unknown"])]
    for title, items in sections:
        lines += ["", f"## {title}（{len(items)}）", "", "| 文件 | 覆盖率 | 依据 / 待确认 |",
                  "|---|---|---|"]
        if not items:
            lines += ["| — | — | 无该类条目 |"]
        for item in items[:limit] if limit is not None else items:
            rate = item.get("coverage")
            evidence = item.get("reason") or item.get("confidence", "输入报告")
            if item.get("candidates"):
                evidence += "；候选：" + ", ".join(item["candidates"])
            lines += [f"| {esc(item['file'])} | {'未知' if rate is None else f'{rate:.1f}%'} | {esc(evidence)} |"]
        if limit is not None and len(items) > limit:
            lines += ["", f"还有 {len(items) - limit} 项；完整清单见 --json 或 --output。"]
    counts = report["summary"]
    lines += ["", f"high {counts['high']} / warn {counts['warn']} / info {counts['info']} / "
              f"coverage_unknown {counts['unknown']}", "", f"门禁：{report['gate']['status']}；"
              "0=通过，1=严格门禁未通过，2=输入错误。", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="测试覆盖缺口（命名线索与执行覆盖率分开）")
    ap.add_argument("paths", nargs="*", default=["."], help="源码目录，默认当前目录")
    ap.add_argument("--days", type=int, default=30, help="git 改动统计天数；0 跳过")
    ap.add_argument("--coverage", help="Cobertura coverage.xml 或 lcov.info")
    ap.add_argument("--coverage-map", action="append", default=[], metavar="REPORT=SOURCE",
                    help="显式报告路径前缀=源码路径前缀；可重复，最长前缀优先")
    ap.add_argument("--min-cov", type=float, default=50.0, help="低覆盖阈值，百分比")
    ap.add_argument("--min-lines", type=int, default=10, help="命名缺口最少源码行数")
    ap.add_argument("--exclude", action="append", default=[], help="额外排除目录名")
    ap.add_argument("--limit", type=int, default=30, help="屏幕每类最多条数；JSON / 输出文件不截断")
    ap.add_argument("--json", action="store_true", help="标准输出 JSON")
    ap.add_argument("--output", help="额外保存完整 Markdown 报告；不允许覆盖扫描输入")
    ap.add_argument("--strict", action="store_true", help="有 high 或覆盖率未知 / 歧义则退出 1")
    a = ap.parse_args()
    if a.days < 0 or a.min_lines < 0 or a.limit < 1 or not math.isfinite(a.min_cov) or not 0 <= a.min_cov <= 100:
        ap.error("days / min-lines 须非负；limit 至少为 1；min-cov 在 0 到 100 之间")
    if a.coverage_map and not a.coverage:
        ap.error("--coverage-map 需要 --coverage")
    roots = a.paths or ["."]
    for path in roots:
        if not os.path.isdir(path):
            ap.error(f"目录不存在：{path}")
    sources, tests = walk(roots, a.exclude)
    tm = test_matches(sources, tests)
    cov, cov_kind = {}, None
    try:
        if a.coverage:
            cov, cov_kind = load_coverage(a.coverage)
            cov = map_prefixes(cov, a.coverage_map)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    cm = coverage_matches(sources, cov)
    churn, churn_note = ({}, "未统计 git 改动")
    if a.days > 0:
        churn, churn_note = git_churn(roots[0], a.days)
    gaps, low, zero, unknown, findings = [], [], [], [], []
    for rel in sources:
        n = loc(rel)
        key = cm[rel]["matched_path"]
        stats = cov[key] if key is not None else {}
        rate = stats["rate"] * 100 if stats.get("rate") is not None else None
        hits = churn.get(rel, 0)
        findings.append({"file": rel, "source_lines": n, "test_mapping": tm[rel],
                         "coverage_mapping": cm[rel], "coverage": rate})
        if a.coverage and rate is None:
            unknown.append({"file": rel, "coverage": None, **cm[rel],
                            "reason": "路径匹配歧义" if cm[rel]["confidence"] == "ambiguous"
                            else "报告没有可用于该文件的覆盖率；未知不等于 0%"})
        if rate is not None:
            item = {"file": rel, "coverage": rate, "lines": stats["lines"],
                    "covered": stats["covered"], "churn": hits,
                    "confidence": cm[rel]["confidence"], "candidates": cm[rel]["candidates"]}
            if rate == 0:
                zero.append(item)
            elif rate < a.min_cov:
                low.append(item)
        if tm[rel]["confidence"] in ("convention_unique", "convention_multiple") or n < a.min_lines:
            continue
        if rate is not None and rate > 0:
            severity, reason = "info", f"没有明确同名测试线索；输入报告覆盖率 {rate:.1f}%"
        elif hits:
            severity, reason = "high", f"最近 {a.days} 天改动 {hits} 次，缺少明确命名测试线索"
        else:
            severity, reason = "warn", "没有明确对应测试文件（不代表没有执行测试）"
        gaps.append({"file": rel, "lines": n, "churn": hits, "coverage": rate,
                     "severity": severity, "reason": reason, "test_mapping": tm[rel],
                     "coverage_mapping": cm[rel]})
    gaps.sort(key=lambda item: (-item["churn"], -item["lines"], item["file"]))
    zero.sort(key=lambda item: (-item["churn"], -(item["lines"] or 0), item["file"]))
    low.sort(key=lambda item: (item["coverage"], item["file"]))
    high_set = {g["file"] for g in gaps if g["severity"] == "high"} | {z["file"] for z in zero}
    warn_set = ({g["file"] for g in gaps if g["severity"] == "warn"} | {x["file"] for x in low}) - high_set
    info_set = {g["file"] for g in gaps if g["severity"] == "info"} - high_set - warn_set
    counts = {"high": len(high_set), "warn": len(warn_set), "info": len(info_set), "unknown": len(unknown)}
    complete_counts = all(item["lines"] is not None and item["covered"] is not None for item in cov.values())
    total_lines = sum(item["lines"] or 0 for item in cov.values())
    total_cov = sum(item["covered"] or 0 for item in cov.values()) / total_lines * 100 if complete_counts and total_lines else None
    blocked = bool(a.strict and (counts["high"] or (a.coverage and unknown)))
    report = {"sources": len(sources), "tests": len(tests), "untested": len(gaps),
              "days": a.days, "churn_note": churn_note, "coverage_format": cov_kind,
              "total_coverage": total_cov, "gaps": gaps, "zero_coverage": zero,
              "low_coverage": low, "coverage_unknown": unknown, "source_findings": findings,
              "summary": counts, "gate": {"status": "blocked" if blocked else "passed",
                                           "strict": a.strict, "exit_code": 1 if blocked else 0},
              "notes": ["测试文件名匹配是线索，不证明执行或质量。",
                        "覆盖率依赖用户提供报告的运行范围与新鲜度；脚本不运行测试、不修改源码。",
                        "total_coverage 为整份报告的可计算行覆盖率，可能包含扫描范围外文件。",
                        "suffix_unique 仅表示候选唯一；请检查候选路径，优先用 --coverage-map 建立精确匹配。"]}
    if a.output:
        output = Path(a.output)
        inputs = {Path(p).resolve() for p in sources + [t for t, _ in tests]}
        if a.coverage:
            inputs.add(Path(a.coverage).resolve())
        if output.resolve() in inputs:
            print("--output 不能覆盖源码、测试或覆盖率输入文件", file=sys.stderr)
            return 2
        try:
            output.write_text(render_markdown(report), encoding="utf-8")
        except OSError as exc:
            print(f"无法写入 Markdown 报告：{exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else render_markdown(report, a.limit))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
