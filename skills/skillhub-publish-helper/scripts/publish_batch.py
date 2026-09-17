#!/usr/bin/env python3
"""SkillHub 批量发布助手：校验 → 清理 → dry-run → 按间隔发布 → 记录 skillId。

实测规则（2026-09 SkillHub CLI 2026.8.x）：
  - frontmatter 必填 slug（kebab，全网唯一）、version（SemVer）、displayName；建议 summary/description/tags/license/homepage
  - 无扩展名文件（LICENSE、NOTICE…）会被 400 拒绝；把许可证写进 frontmatter 的 license
  - 连续 3 次请求后触发限频，发布间隔 ≥ 75 秒
  - 发布后进入机器审核，通过前搜索索引里查不到
用法：
  python3 publish_batch.py --dirs skills/a skills/b --out publish-log.csv [--interval 75] [--changelog "首次发布"] [--no-publish]
  python3 publish_batch.py --status --handle <你的 handle> --slugs a b   # 查是否已进搜索索引
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CLI = shutil.which("skillhub") or str(Path.home() / ".local/bin/skillhub")
HOST = "https://api.skillhub.cn"
JUNK_NAMES = {"LICENSE", "NOTICE", "ATTRIBUTION", "COPYING", "Makefile", "Dockerfile"}


def frontmatter(p: Path):
    m = re.match(r"^---\n(.*?)\n---\n", p.read_text("utf-8"), re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if mm:
            v = mm.group(2).strip()
            if v[:1] in "\"'" and v[-1:] == v[:1]:
                v = v[1:-1]
            fm[mm.group(1)] = v
    return fm


def lint(d: Path):
    errs, warns = [], []
    sk = d / "SKILL.md"
    if not sk.exists():
        return ["缺 SKILL.md"], []
    fm = frontmatter(sk)
    slug = fm.get("slug", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) or not 2 <= len(slug) <= 128:
        errs.append(f"slug 不合法: {slug!r}（kebab-case，2–128）")
    if not re.fullmatch(r"\d+\.\d+\.\d+", fm.get("version", "")):
        errs.append(f"version 不是 SemVer: {fm.get('version')!r}")
    if not fm.get("displayName"):
        errs.append("缺 displayName")
    for k in ("summary", "license", "tags"):
        if k not in fm and not re.search(rf"^{k}:", sk.read_text("utf-8"), re.M):
            warns.append(f"建议补 {k}")
    for f in d.rglob("*"):
        if f.is_file() and (f.suffix == "" or f.name in JUNK_NAMES):
            errs.append(f"无扩展名文件会被平台拒绝: {f.relative_to(d)}")
        if f.is_dir() and f.name in ("__pycache__", ".git", "node_modules"):
            errs.append(f"请删除目录: {f.relative_to(d)}")
    return errs, warns


def run(args, timeout=180):
    p = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def status(handle, slugs):
    for s in slugs:
        rc, out = run(["search", s, "--json", "--search-limit", "5"], 60)
        try:
            d = json.loads(out[out.index("{"):])
            hit = [r for r in d.get("results", []) if (r.get("namespace") or {}).get("handle") == handle and (r.get("publicSlug") == s)]
            print(f"{s:36s} {'已上架' if hit else '未上架（审核中或未发布）'}")
        except Exception:
            print(f"{s:36s} 查询失败")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="*", default=[])
    ap.add_argument("--out", default="publish-log.csv")
    ap.add_argument("--interval", type=int, default=75)
    ap.add_argument("--changelog", default="首次发布")
    ap.add_argument("--no-publish", action="store_true", help="只校验 + dry-run")
    ap.add_argument("--status", action="store_true"); ap.add_argument("--handle"); ap.add_argument("--slugs", nargs="*")
    a = ap.parse_args()
    if a.status:
        if not a.handle or not a.slugs:
            sys.exit("--status 需要 --handle 与 --slugs")
        status(a.handle, a.slugs); return
    if not a.dirs:
        sys.exit("请用 --dirs 指定技能目录")
    if not Path(CLI).exists():
        sys.exit("找不到 skillhub CLI，请先安装：curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only")
    rows, ready = [], []
    for ds in a.dirs:
        d = Path(ds)
        errs, warns = lint(d)
        for w in warns:
            print(f"  WARN {d.name}: {w}")
        if errs:
            for e in errs:
                print(f"  FAIL {d.name}: {e}")
            rows.append({"dir": ds, "slug": frontmatter(d / "SKILL.md").get("slug", ""), "step": "lint", "result": "; ".join(errs), "skillId": "", "time": datetime.now().isoformat(timespec="seconds")})
            continue
        rc, out = run(["publish", ds, "--host", HOST, "--dry-run"])
        if "Dry-run passed" not in out:
            print(f"  FAIL {d.name}: dry-run 未通过 → {out.splitlines()[-1] if out else rc}")
            rows.append({"dir": ds, "slug": frontmatter(d / "SKILL.md").get("slug", ""), "step": "dry-run", "result": out[-200:], "skillId": "", "time": datetime.now().isoformat(timespec="seconds")})
            continue
        print(f"  OK   {d.name}: dry-run 通过")
        ready.append(ds)
    if a.no_publish:
        print(f"\n{len(ready)}/{len(a.dirs)} 个可发布（--no-publish 未发布）")
    else:
        for i, ds in enumerate(ready):
            if i:
                print(f"  等待 {a.interval} 秒避免限频…"); time.sleep(a.interval)
            rc, out = run(["publish", ds, "--host", HOST, "--changelog", a.changelog])
            m = re.search(r"skillId=(\d+)", out)
            ok = "Published" in out
            print(f"  {'✓' if ok else '✗'} {Path(ds).name}: {out.splitlines()[-1] if out else rc}")
            rows.append({"dir": ds, "slug": frontmatter(Path(ds) / "SKILL.md").get("slug", ""), "step": "publish", "result": "ok" if ok else out[-200:], "skillId": m.group(1) if m else "", "time": datetime.now().isoformat(timespec="seconds")})
    exists = Path(a.out).exists()
    with open(a.out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dir", "slug", "step", "result", "skillId", "time"])
        if not exists:
            w.writeheader()
        w.writerows(rows)
    print(f"✓ 记录写入 {a.out}")


if __name__ == "__main__":
    main()
