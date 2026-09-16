#!/usr/bin/env python3
"""生成 SkillHub（skillhub.cn）发布副本。

SkillHub 的 SKILL.md frontmatter 必填 slug / version / displayName，建议 summary / description /
tags / license / homepage（来源：skillhub.cn/tutorials 与 skillhub.cn/ai/release.md）。
开放平台版本用的是 name / display_name / description_zh 等字段，两套字段并存未验证是否互相干扰，
所以不改 skills/ 源文件，而是生成一份带 SkillHub 字段的副本到 dist/skillhub/<slug>/。

用法：python3 tools/skillhub_prep.py --out dist/skillhub [skill-name ...]
之后：skillhub publish dist/skillhub/<slug> --host https://api.skillhub.cn --dry-run
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOMEPAGE = "https://github.com/po-et/workbuddy-skills"
LICENSE = "MIT"

# slug 全网唯一，带用途后缀降低 409 冲突概率；冲突时改这里即可
SLUGS = {
    "iteration-report": "iteration-report-git",
    "release-checklist": "release-checklist-git",
    "incident-brief": "incident-brief-sre",
    "build-workbuddy-connector": "build-workbuddy-connector",
}
TAGS = {
    "iteration-report": ["周报", "迭代汇报", "Git", "研发效能"],
    "release-checklist": ["上线检查", "发布评审", "回滚", "研发效能"],
    "incident-brief": ["故障排查", "SRE", "复盘", "研发效能"],
    "build-workbuddy-connector": ["连接器", "WorkBuddy", "脚手架", "开发者工具"],
}


def split_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        sys.exit("SKILL.md 没有 frontmatter")
    return m.group(1), m.group(2)


def get(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    if v[:1] in "\"'" and v[-1:] == v[:1]:
        v = v[1:-1]
    return v


def yaml_list(key: str, items):
    return key + ":\n" + "".join(f"  - {i}\n" for i in items)


def prep(name: str, out: Path) -> Path:
    src = ROOT / "skills" / name
    fm, body = split_frontmatter((src / "SKILL.md").read_text("utf-8"))
    slug = SLUGS.get(name, name)
    summary = get(fm, "description_zh") or get(fm, "description")
    if len(summary) > 200:
        summary = summary[:197] + "…"
    head = "\n".join([
        f"slug: {slug}",
        f'displayName: "{get(fm, "display_name") or name}"',
        f"version: {get(fm, 'version') or '1.0.0'}",
        f'summary: "{summary}"',
        f"license: {LICENSE}",
        f"homepage: {HOMEPAGE}",
        yaml_list("tags", TAGS.get(name, [])).rstrip(),
    ])
    dst = out / slug
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc"))
    fm_rest = re.sub(r"^version:.*\n?", "", fm, flags=re.M)  # 避免与 SkillHub 头部的 version 重复
    (dst / "SKILL.md").write_text(f"---\n{head}\n{fm_rest}\n---\n{body}", "utf-8")
    # SkillHub 上传拒绝无扩展名文件（实测 400「不允许的文件类型: LICENSE」），许可证只写 frontmatter 的 license 字段
    for junk in ("LICENSE", "NOTICE", "ATTRIBUTION"):
        if (dst / junk).exists():
            (dst / junk).unlink()
    return dst


def check(dst: Path) -> list:
    fm, _ = split_frontmatter((dst / "SKILL.md").read_text("utf-8"))
    errs = []
    slug = get(fm, "slug")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) or not 2 <= len(slug) <= 128:
        errs.append(f"slug 不是 kebab-case 或长度越界: {slug!r}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", get(fm, "version")):
        errs.append(f"version 不是 SemVer: {get(fm, 'version')!r}")
    if not get(fm, "displayName"):
        errs.append("缺 displayName")
    for k in ("summary", "license", "homepage"):
        if not get(fm, k):
            errs.append(f"建议字段缺失: {k}")
    return errs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/skillhub")
    ap.add_argument("names", nargs="*", default=list(SLUGS))
    a = ap.parse_args()
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for n in a.names:
        d = prep(n, out)
        errs = check(d)
        bad += bool(errs)
        print(("FAIL " if errs else "OK   ") + str(d.relative_to(ROOT) if d.is_relative_to(ROOT) else d))
        for e in errs:
            print("     -", e)
    sys.exit(1 if bad else 0)
