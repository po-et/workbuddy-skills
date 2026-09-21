"""skillkit build —— 生成 SkillHub 发布副本。

为什么是「副本」而不是就地改：
开放平台用的是 name / display_name / description_zh 这套字段，SkillHub 用的是
slug / displayName / summary 这套。两套并存在同一份 frontmatter 里目前没出过事，
但把 SkillHub 专用字段写回源技能，等于让源目录同时伺候两个平台的口径。
所以这里始终产出一份独立副本，源目录一个字节都不动。

副本里自动处理掉的已知拒收规则：
  * 删掉 LICENSE / NOTICE / ATTRIBUTION / COPYING —— 无扩展名文件实测 400；
  * 清掉 __pycache__ 与 .pyc/.pyo/.pyd —— SkillHub 不需要，ClawHub 直接拒收；
  * 去掉源 frontmatter 里重复的 version / tags，避免副本里同名键出现两次。
"""

from __future__ import print_function

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import checks, frontmatter as fm, output, rules
from ..skillpkg import Skill, SkillError, relpath_for_display, resolve_targets

HELP = "生成发布副本（补齐 SkillHub 字段、自动处理已知的拒收规则）"

DEFAULT_LICENSE = "MIT"


def add_parser(subparsers):
    p = subparsers.add_parser(
        "build",
        help=HELP,
        description="把技能目录转成 SkillHub 能接受的发布副本：补 slug / displayName / version / "
                    "summary / license / homepage / tags，去重字段，删掉会被拒收的文件。源目录不动。",
        epilog="例：skillkit build skills/dockerfile-check --out dist/skillhub "
               "--homepage https://github.com/you/your-repo",
    )
    p.add_argument("paths", nargs="+", help="技能目录、SKILL.md，或包含若干技能的上层目录")
    p.add_argument("--out", required=True, help="发布副本的输出目录，每个技能占一个 <out>/<slug>/")
    p.add_argument("--slug", default="", help="指定 slug（只在恰好一个技能时可用）；默认取 frontmatter 的 slug，再退回目录名")
    p.add_argument("--tags", default="", help="逗号分隔的 tags，覆盖 frontmatter 里的")
    p.add_argument("--license", default=DEFAULT_LICENSE, dest="license_", help="license 字段，默认 MIT")
    p.add_argument("--homepage", default="", help="homepage 字段（建议填，审核与溯源都看它）")
    p.add_argument("--map", default="", dest="map_file",
                   help='JSON 映射文件：{"<目录名>": {"slug": "...", "tags": ["..."]}}，批量改名时用')
    p.add_argument("--dry-run", action="store_true", dest="dry_run", help="只算不写，用于发布前预检")
    p.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    return p


# ---------------------------------------------------------------- 核心

def _load_map(path):
    # type: (str) -> Dict[str, Dict[str, Any]]
    if not path:
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for key, value in raw.items():
        out[key] = {"slug": value} if isinstance(value, str) else dict(value)
    return out


def resolve_meta(skill, overrides=None, license_=DEFAULT_LICENSE, homepage=""):
    # type: (Skill, Optional[Dict[str, Any]], str, str) -> Dict[str, Any]
    """算出副本 frontmatter 头部要写的七个字段。"""
    over = overrides or {}
    slug = over.get("slug") or skill.field("slug") or skill.dirname
    tags = over.get("tags")
    if tags is None:
        tags = skill.tags
    tags = [str(t) for t in tags]

    summary = skill.field("description_zh") or skill.field("description")
    if len(summary) > rules.SUMMARY_MAX:
        summary = summary[: rules.SUMMARY_MAX - 3] + "…"

    display = (over.get("displayName") or skill.field("display_name")
               or skill.field("displayName") or skill.dirname)
    version = skill.field("version") or "1.0.0"
    return {
        "slug": slug,
        "displayName": display,
        "version": version,
        "summary": over.get("summary") or summary,
        "license": license_,
        "homepage": homepage,
        "tags": tags,
    }


def render_frontmatter(skill, meta):
    # type: (Skill, Dict[str, Any]) -> str
    """拼出副本的 frontmatter 文本：SkillHub 头部 + 去重后的原字段。"""
    head = [
        fm.fmt_scalar("slug", meta["slug"]),
        fm.fmt_scalar("displayName", meta["displayName"], quote=True),
        fm.fmt_scalar("version", meta["version"]),
        fm.fmt_scalar("summary", meta["summary"], quote=True),
    ]
    if meta["license"]:
        head.append(fm.fmt_scalar("license", meta["license"]))
    if meta["homepage"]:
        head.append(fm.fmt_scalar("homepage", meta["homepage"]))
    if meta["tags"]:
        head.append(fm.fmt_list("tags", meta["tags"]))
    rest = fm.drop_keys(skill.fm_text, ("version", "tags"))
    return "\n".join(head) + "\n" + rest


def build_one(directory, out_dir, overrides=None, license_=DEFAULT_LICENSE,
              homepage="", dry_run=False):
    # type: (Any, Any, Optional[Dict[str, Any]], str, str, bool) -> Dict[str, Any]
    """构建一个技能的发布副本。dry_run=True 时不落盘，但一样跑完校验。"""
    skill = Skill.load(directory)
    meta = resolve_meta(skill, overrides, license_, homepage)
    new_fm = render_frontmatter(skill, meta)
    dst = Path(out_dir) / meta["slug"]

    removed = []  # type: List[str]
    if dry_run:
        # 只算不写：校验跑在内存里的 frontmatter 上，结论与真写一遍等价
        findings = list(checks.check_publish_text(new_fm))
        for name in rules.EXTENSIONLESS_DROP:
            if (skill.dir / name).exists():
                removed.append(name)
    else:
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(
            str(skill.dir), str(dst),
            ignore=shutil.ignore_patterns(*rules.COPY_IGNORE_GLOBS),
        )
        (dst / "SKILL.md").write_text(fm.join(new_fm, skill.body), encoding="utf-8")
        removed = _strip_rejected(dst)
        findings = list(checks.check_publish_copy(dst))

    counts = checks.counts(findings)
    return {
        "name": skill.dirname,
        "source": relpath_for_display(skill.dir),
        "slug": meta["slug"],
        "out": str(dst),
        "version": meta["version"],
        "displayName": meta["displayName"],
        "tags": meta["tags"],
        "removed": sorted(set(removed)),
        "findings": [f.as_dict() for f in findings],
        "counts": counts,
        "ok": counts[checks.FAIL] == 0,
        "written": not dry_run,
    }


def _strip_rejected(dst):
    # type: (Path) -> List[str]
    """删掉平台会拒收的文件，返回删掉了什么。"""
    removed = []
    for name in rules.EXTENSIONLESS_DROP:
        path = dst / name
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(name)
    for path in sorted(dst.rglob("*"), reverse=True):
        if path.is_dir() and path.name == "__pycache__":
            shutil.rmtree(str(path), ignore_errors=True)
            removed.append(str(path.relative_to(dst)))
        elif path.is_file() and path.suffix in (".pyc", ".pyo", ".pyd"):
            path.unlink()
            removed.append(str(path.relative_to(dst)))
    return removed


# ---------------------------------------------------------------- 入口

def run(args):
    try:
        targets = resolve_targets(args.paths)
    except SkillError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.slug and len(targets) != 1:
        print("--slug 只能在恰好一个技能时使用，当前匹配到 %d 个" % len(targets), file=sys.stderr)
        return 2
    try:
        mapping = _load_map(args.map_file)
    except (OSError, ValueError) as exc:
        print("--map 读取失败: %s" % exc, file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    seen = {}  # type: Dict[str, str]
    for d in targets:
        over = dict(mapping.get(d.name, {}))
        if args.slug:
            over["slug"] = args.slug
        if args.tags:
            over["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
        try:
            r = build_one(d, out_dir, over, args.license_, args.homepage, args.dry_run)
        except SkillError as exc:
            results.append({
                "name": d.name, "source": relpath_for_display(d), "slug": "", "out": "",
                "removed": [], "findings": [checks.Finding(checks.FAIL, str(exc)).as_dict()],
                "counts": {checks.FAIL: 1, checks.WARN: 0, checks.PASS: 0},
                "ok": False, "written": False,
            })
            continue
        if r["slug"] in seen:
            r["findings"].append(
                checks.Finding(checks.FAIL,
                               "slug %r 与 %s 撞车，同一次 build 里两个技能不能用同一个 slug"
                               % (r["slug"], seen[r["slug"]]), "slug-global-unique").as_dict())
            r["counts"][checks.FAIL] += 1
            r["ok"] = False
        else:
            seen[r["slug"]] = r["name"]
        results.append(r)

    if args.as_json:
        output.emit_json({"skills": results, "out": str(out_dir), "dry_run": args.dry_run})
        return 1 if any(not r["ok"] for r in results) else 0

    for r in results:
        flag = "FAIL" if not r["ok"] else ("DRY " if args.dry_run else "OK  ")
        print("%s %s  ->  %s" % (flag, output.pad(r["source"], 38), r["out"]))
        for f in r["findings"]:
            if f["level"] != checks.PASS:
                print("       [%s] %s" % (f["level"], f["message"]))
        if r["removed"]:
            verb = "将删除" if args.dry_run else "已删除"
            print("       %s（平台会拒收）：%s" % (verb, "、".join(r["removed"])))
    bad = sum(1 for r in results if not r["ok"])
    print("")
    print("%d 个技能，%d 个有 FAIL%s" % (len(results), bad, "（dry-run，未落盘）" if args.dry_run else ""))
    if not args.dry_run and results:
        print("发布前先跑一次 `skillkit doctor`；失败的发布请求一样消耗配额。")
    return 1 if bad else 0
