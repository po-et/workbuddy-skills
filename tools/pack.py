#!/usr/bin/env python3
"""把仓库里的技能 / 专家 / 连接器打成开放平台可提交的 zip，并自动跑校验。

用法:
    python3 tools/pack.py --out dist            # 全部
    python3 tools/pack.py --out dist skill:iteration-report expert:devops-team connector:mermaid

规则：
- 技能：skills/<name>/ → <name>.zip，剔除 __pycache__/.pyc/.DS_Store/.keep/LICENSE
- 专家：experts/<name>/ → <name>.zip；agents/*.md 里 `skills:` 引用到的仓库技能会复制进包内 skills/
- 连接器：ported/connectors/<name>/ → <name>-connector.zip（保留 LICENSE / ATTRIBUTION，连接器包需要）
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "__MACOSX"}
EXCLUDE_FILES = {".DS_Store", ".keep"}


def copytree(src, dst, drop_license):
    for dp, dns, fns in os.walk(src):
        dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(dp, src)
        os.makedirs(os.path.join(dst, rel) if rel != "." else dst, exist_ok=True)
        for fn in fns:
            if fn in EXCLUDE_FILES or fn.endswith(".pyc"):
                continue
            if drop_license and fn.upper().startswith("LICENSE"):
                continue
            shutil.copy2(os.path.join(dp, fn), os.path.join(dst, rel, fn) if rel != "." else os.path.join(dst, fn))


def referenced_skills(expert_dir):
    names = set()
    for fn in os.listdir(os.path.join(expert_dir, "agents")):
        if not fn.endswith(".md"):
            continue
        fm = open(os.path.join(expert_dir, "agents", fn), encoding="utf-8").read().split("\n---", 1)[0]
        m = re.search(r"^skills:\s*\[(.*?)\]", fm, re.M)
        if m:
            names.update(x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip())
    return sorted(names)


def zipdir(stage, name, out):
    path = os.path.join(out, f"{name}.zip")
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dns, fns in os.walk(stage):
            for fn in sorted(fns):
                full = os.path.join(dp, fn)
                z.write(full, os.path.relpath(full, os.path.dirname(stage)))
    return path


def build(kind, name, out):
    stage_root = tempfile.mkdtemp(prefix="pack_")
    if kind == "skill":
        src = os.path.join(ROOT, "skills", name); stage = os.path.join(stage_root, name)
        copytree(src, stage, drop_license=True); zipname = name
    elif kind == "expert":
        src = os.path.join(ROOT, "experts", name); stage = os.path.join(stage_root, name)
        copytree(src, stage, drop_license=True)
        for sk in referenced_skills(src):
            sksrc = os.path.join(ROOT, "skills", sk)
            if os.path.isdir(sksrc):
                copytree(sksrc, os.path.join(stage, "skills", sk), drop_license=True)
                print(f"    + 内置技能 {sk}")
            else:
                print(f"    ! agent 引用的技能 {sk} 不在仓库 skills/ 下，未内置", file=sys.stderr)
        zipname = name
    elif kind == "connector":
        src = os.path.join(ROOT, "ported", "connectors", name); stage = os.path.join(stage_root, f"{name}-connector")
        copytree(src, stage, drop_license=False); zipname = f"{name}-connector"
    else:
        sys.exit(f"未知类型 {kind}")
    if not os.path.isdir(src):
        sys.exit(f"不存在: {src}")
    path = zipdir(stage, zipname, out)
    size = os.path.getsize(path) // 1024
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_package.py"), path],
                       capture_output=True, text=True)
    verdict = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()
    print(f"  {os.path.basename(path):34} {size:5}KB  {verdict}")
    shutil.rmtree(stage_root, ignore_errors=True)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("targets", nargs="*", help="kind:name；留空则打包全部")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    targets = a.targets or (
        [f"skill:{d}" for d in sorted(os.listdir(os.path.join(ROOT, "skills"))) if os.path.isfile(os.path.join(ROOT, "skills", d, "SKILL.md"))]
        + [f"expert:{d}" for d in sorted(os.listdir(os.path.join(ROOT, "experts"))) if os.path.isdir(os.path.join(ROOT, "experts", d))]
        + [f"connector:{d}" for d in sorted(os.listdir(os.path.join(ROOT, "ported", "connectors"))) if os.path.isdir(os.path.join(ROOT, "ported", "connectors", d))])
    ok = True
    for t in targets:
        kind, _, name = t.partition(":")
        print(f"{kind}:{name}")
        ok = build(kind, name, a.out) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
