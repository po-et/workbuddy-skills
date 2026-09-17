#!/usr/bin/env python3
"""拉取 GitHub 仓库里某个技能目录（SKILL.md 及同目录下的 references/scripts/assets）到本地，供复刻阅读。

用法：python3 tools/fetch_skill.py owner/repo path/to/skill/SKILL.md --out scratch/src/<name>
依赖 gh CLI（已登录）与 curl。只下载文本类文件，跳过 >200KB 的文件。
"""
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".csv", ".html", ".css", ".xml", ".sql", ".ini", ".cfg", ".rst", ".mjs", ".ps1"}


def gh(args):
    p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"gh api 失败：{p.stderr.strip()[:200]}")
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo"); ap.add_argument("skill_md"); ap.add_argument("--out", required=True); ap.add_argument("--branch")
    a = ap.parse_args()
    branch = a.branch or gh([f"repos/{a.repo}", "--jq", ".default_branch"]).strip()
    base = str(Path(a.skill_md).parent)
    base = "" if base == "." else base + "/"
    tree = gh([f"repos/{a.repo}/git/trees/{branch}?recursive=1", "--jq", '.tree[] | select(.type=="blob") | "\\(.path)\\t\\(.size)"'])
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    n = 0
    for line in tree.splitlines():
        path, size = line.split("\t")
        if not path.startswith(base) or Path(path).suffix.lower() not in TEXT_EXT or int(size) > 200_000:
            continue
        rel = path[len(base):]
        if rel.count("/") > 3:
            continue
        url = f"https://raw.githubusercontent.com/{a.repo}/{branch}/{path}"
        dst = out / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                dst.write_bytes(r.read()); n += 1
        except Exception as e:
            print(f"  跳过 {rel}: {e}", file=sys.stderr)
    lic = ""
    for cand in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        try:
            with urllib.request.urlopen(f"https://raw.githubusercontent.com/{a.repo}/{branch}/{cand}", timeout=20) as r:
                lic = r.read(600).decode("utf-8", "ignore").strip().splitlines()[0]; break
        except Exception:
            continue
    (out / "_SOURCE.txt").write_text(f"repo: https://github.com/{a.repo}\nbranch: {branch}\npath: {a.skill_md}\nlicense_head: {lic}\n", "utf-8")
    print(f"✓ {a.repo}/{a.skill_md} → {out}（{n} 个文件；许可证首行：{lic or '未找到'}）")


if __name__ == "__main__":
    main()
