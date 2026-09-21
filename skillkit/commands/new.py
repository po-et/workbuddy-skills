"""skillkit new —— 从模板生成一个技能骨架。"""

from __future__ import print_function

import sys
from pathlib import Path

from .. import rules, template

HELP = "从模板生成技能骨架（必填 frontmatter 一个不少，坑点写在注释里）"


def add_parser(subparsers):
    p = subparsers.add_parser(
        "new",
        help=HELP,
        description="生成一个技能骨架目录。模板里的 frontmatter 已经把平台解析器强制必填、"
                    "但官方文档没写的字段补齐了，注释里标了每个字段的踩坑点。",
        epilog="例：skillkit new my-log-triage --dir skills --author Captain",
    )
    p.add_argument("name", help="技能名（kebab-case，将作为目录名与 frontmatter 的 name）")
    p.add_argument("--dir", default=".", help="在哪个父目录下创建，默认当前目录")
    p.add_argument("--author", default="", help="frontmatter 的 author（开发者昵称）")
    p.add_argument("--title", default="", help="中文展示名 display_name，默认按技能名生成")
    p.add_argument("--title-en", default="", dest="title_en", help="英文展示名 display_name_en")
    p.add_argument("--no-script", action="store_true", help="不生成 scripts/ 示例脚本")
    p.add_argument("--force", action="store_true", help="目标目录已存在时覆盖同名文件")
    return p


def run(args):
    name = args.name.strip()
    if not rules.KEBAB.match(name):
        print("技能名必须是 kebab-case（小写字母数字加连字符）: %r" % name, file=sys.stderr)
        return 2
    if not (rules.SLUG_MIN_LEN <= len(name) <= rules.SLUG_MAX_LEN):
        print("技能名长度须在 %d–%d 之间" % (rules.SLUG_MIN_LEN, rules.SLUG_MAX_LEN), file=sys.stderr)
        return 2

    target = Path(args.dir) / name
    files = template.render(name, author=args.author, title=args.title, title_en=args.title_en)
    if args.no_script:
        files = {k: v for k, v in files.items() if not k.startswith("scripts/")}

    existing = [rel for rel in files if (target / rel).exists()]
    if existing and not args.force:
        print("这些文件已存在，加 --force 才会覆盖：%s" % "、".join(sorted(existing)), file=sys.stderr)
        return 1

    for rel in sorted(files):
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(files[rel], encoding="utf-8")
        if rel.startswith("scripts/"):
            path.chmod(0o755)
        print("创建 %s" % path)

    print("")
    print("注意：骨架刚生成就能拿到不低的 lint 分数 —— 那是**结构分**，说明模板形状对，"
          "不代表内容写好了。占位符不换掉，分数是假的。")
    print("")
    print("接下来：")
    print("  1. 把 SKILL.md 里所有「（…）」占位符换成真内容，注释可以留着也可以删")
    print("  2. skillkit lint %s        # 看格式有没有 FAIL、五维分多少" % target)
    print("  3. skillkit doctor %s      # 发布前最后一道：能不能发" % target)
    print("  4. skillkit build %s --out dist/skillhub --slug <全网唯一的 slug>" % target)
    return 0
