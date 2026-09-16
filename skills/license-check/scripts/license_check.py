#!/usr/bin/env python3
"""开源协议合规检查：列出项目依赖的许可证并按风险分级。零依赖、不联网。

数据来源（按顺序）：
  npm  : package-lock.json（v2/v3 的 packages[*].license）→ node_modules/**/package.json
  PyPI : --python-site <site-packages> 或自动发现 .venv / venv；读 *.dist-info/METADATA 的 License / Classifier；
         也可 --use-current-python 用当前解释器的 importlib.metadata
  Go   : $GOPATH/pkg/mod/<module>@<ver>/LICENSE* 的文件头（需已 go mod download）
分级：permissive / weak-copyleft / strong-copyleft / restricted / unknown
用法：python3 license_check.py --path . [--python-site .venv/lib/python3.12/site-packages] [--md out/licenses.md] [--out out/licenses.json] [--fail-on strong-copyleft]
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

PERMISSIVE = ["MIT", "BSD", "APACHE", "ISC", "0BSD", "UNLICENSE", "ZLIB", "PSF", "PYTHON", "WTFPL", "CC0", "BLUEOAK", "BOOST", "MIT-0", "X11", "ARTISTIC"]
WEAK = ["LGPL", "MPL", "EPL", "CDDL", "EUPL", "OSL", "CPL", "MS-RL"]
STRONG = ["AGPL", "GPL"]
RESTRICTED = ["SSPL", "BUSL", "BSL", "CC-BY-NC", "NC-", "NONCOMMERCIAL", "UNLICENSED", "PROPRIETARY", "ELASTIC", "SEE LICENSE", "COMMONS CLAUSE", "ALL RIGHTS RESERVED"]
ORDER = {"restricted": 4, "strong-copyleft": 3, "weak-copyleft": 2, "unknown": 1, "permissive": 0}


def classify(text: str) -> str:
    t = (text or "").upper().replace("_", "-")
    if not t.strip():
        return "unknown"
    if any(k in t for k in RESTRICTED):
        return "restricted"
    if any(k in t for k in STRONG) and "LGPL" not in t:
        return "strong-copyleft"
    if "LGPL" in t and not any(k in t for k in ("GPL-2.0-ONLY", "GPL-3.0-ONLY")) and "AGPL" not in t:
        return "weak-copyleft"
    if any(k in t for k in WEAK):
        return "weak-copyleft"
    if any(k in t for k in PERMISSIVE):
        return "permissive"
    return "unknown"


def norm_license(v):
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return str(v.get("type") or v.get("name") or "").strip()
    if isinstance(v, list):
        return " OR ".join(norm_license(x) for x in v if norm_license(x))
    return ""


def npm(path: Path):
    out = {}
    lock = path / "package-lock.json"
    if lock.exists():
        try:
            d = json.loads(lock.read_text("utf-8"))
            for k, v in (d.get("packages") or {}).items():
                if k and "node_modules/" in k and v.get("version"):
                    name = k.split("node_modules/")[-1]
                    out[("npm", name, v["version"])] = norm_license(v.get("license")) or ""
        except Exception as e:
            print(f"  注意：package-lock.json 解析失败 {e}", file=sys.stderr)
    nm = path / "node_modules"
    if nm.exists():
        for pj in nm.rglob("package.json"):
            parts = pj.relative_to(nm).parts
            if len(parts) > 3 or ".bin" in parts:
                continue
            try:
                d = json.loads(pj.read_text("utf-8"))
            except Exception:
                continue
            if d.get("name") and d.get("version"):
                key = ("npm", d["name"], d["version"])
                lic = norm_license(d.get("license") or d.get("licenses"))
                if lic or key not in out:
                    out[key] = lic or out.get(key, "")
    return out


def find_site(path: Path):
    for v in ("venv", ".venv", "env"):
        for sp in (path / v).glob("lib/python*/site-packages"):
            return sp
    return None


def pypi_site(site: Path):
    out = {}
    for meta in site.glob("*.dist-info/METADATA"):
        name = ver = lic = None; cls = []
        for line in meta.read_text("utf-8", errors="ignore").splitlines():
            if line.startswith("Name:"): name = line[5:].strip()
            elif line.startswith("Version:"): ver = line[8:].strip()
            elif line.startswith("License-Expression:"): lic = line[19:].strip()
            elif line.startswith("License:") and not lic: lic = line[8:].strip()
            elif line.startswith("Classifier: License ::"): cls.append(line.split("::")[-1].strip())
            elif line == "":
                break
        if name and ver:
            if (not lic or len(lic) > 60 or lic.upper() in ("UNKNOWN", "LICENSE.TXT", "LICENSE")) and cls:
                lic = " / ".join(cls)
            out[("PyPI", name, ver)] = lic or ""
    return out


def pypi_current():
    out = {}
    try:
        from importlib.metadata import distributions
        for d in distributions():
            m = d.metadata
            cls = [c.split("::")[-1].strip() for c in m.get_all("Classifier", []) if c.startswith("License ::")]
            lic = m.get("License-Expression") or m.get("License") or ""
            if (not lic or len(lic) > 60 or lic.upper() in ("UNKNOWN",)) and cls:
                lic = " / ".join(cls)
            out[("PyPI", m.get("Name", "?"), m.get("Version", "?"))] = lic
    except Exception as e:
        print(f"  注意：importlib.metadata 失败 {e}", file=sys.stderr)
    return out


def go(path: Path):
    out = {}
    mod = path / "go.mod"
    if not mod.exists():
        return out
    gopath = os.environ.get("GOPATH") or str(Path.home() / "go")
    cache = Path(gopath) / "pkg" / "mod"
    for line in mod.read_text("utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*(\S+)\s+(v\S+)", line)
        if not m or line.strip().startswith(("module", "go ", "//", "require", ")")):
            continue
        name, ver = m.group(1), m.group(2)
        lic = ""
        d = cache / f"{name}@{ver}"
        if d.exists():
            for f in list(d.glob("LICENSE*")) + list(d.glob("COPYING*")):
                head = f.read_text("utf-8", errors="ignore")[:600].upper()
                for k in ["APACHE", "MIT", "BSD", "MPL", "LGPL", "AGPL", "GPL", "ISC"]:
                    if k in head:
                        lic = k; break
                break
        out[("Go", name, ver)] = lic
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--python-site")
    ap.add_argument("--use-current-python", action="store_true")
    ap.add_argument("--out"); ap.add_argument("--md")
    ap.add_argument("--fail-on", choices=["unknown", "weak-copyleft", "strong-copyleft", "restricted"])
    a = ap.parse_args()
    root = Path(a.path)
    deps = {}
    deps.update(npm(root))
    site = Path(a.python_site) if a.python_site else find_site(root)
    if site and site.exists():
        deps.update(pypi_site(site))
    if a.use_current_python:
        deps.update(pypi_current())
    deps.update(go(root))
    if not deps:
        sys.exit("没有找到可分析的依赖（需要 package-lock.json / node_modules / Python site-packages / go.mod）")
    rows = []
    for (eco, name, ver), lic in sorted(deps.items()):
        rows.append({"ecosystem": eco, "name": name, "version": ver, "license": lic or "", "risk": classify(lic)})
    counts = Counter(r["risk"] for r in rows)
    rows_sorted = sorted(rows, key=lambda r: (-ORDER[r["risk"]], r["ecosystem"], r["name"]))
    md = ["# 开源协议合规检查", "", f"- 依赖总数：{len(rows)}　" + "　".join(f"{k}: {counts.get(k, 0)}" for k in ("restricted", "strong-copyleft", "weak-copyleft", "unknown", "permissive")), ""]
    flagged = [r for r in rows_sorted if r["risk"] != "permissive"]
    if flagged:
        md += ["| 风险 | 依赖 | 版本 | 许可证 |", "|---|---|---|---|"]
        md += [f"| {r['risk']} | {r['ecosystem']}/{r['name']} | {r['version']} | {r['license'] or '（未声明）'} |" for r in flagged[:200]]
    else:
        md.append("所有依赖均为宽松许可证（MIT/BSD/Apache/ISC 等）。")
    md += ["", "## 说明", "- 分级只看许可证文本关键字：restricted（SSPL/BUSL/NC/未授权）> strong-copyleft（GPL/AGPL）> weak-copyleft（LGPL/MPL/EPL）> unknown（未声明）> permissive。",
           "- 是否构成合规问题取决于你怎么用：静态链接、修改再分发、作为 SaaS 提供（AGPL）。本工具只给清单，不给法律结论。", "- unknown 需要人工打开包主页确认；npm 的 `SEE LICENSE IN` 归为 restricted 需人工确认。"]
    text = "\n".join(md) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps({"counts": counts, "rows": rows_sorted}, ensure_ascii=False, indent=2), "utf-8")
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True); Path(a.md).write_text(text, "utf-8")
        print(f"✓ {a.md}：{len(rows)} 个依赖，非宽松 {len(flagged)} 个")
    else:
        print(text)
    if a.fail_on and max((ORDER[r["risk"]] for r in rows), default=0) >= ORDER[a.fail_on]:
        sys.exit(1)


if __name__ == "__main__":
    main()
