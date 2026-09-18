#!/usr/bin/env python3
"""生成 ClawHub（clawhub.ai）发布副本。

和 tools/skillhub_prep.py 的关键差异（细节与来源见 docs/clawhub-notes.md）：

- ClawHub 的 SKILL.md frontmatter 官方文档（github.com/openclaw/clawhub docs/skill-format.md）
  称"整体可选"，服务端强依赖的只有 name（1-64 位小写字母/数字/连字符，建议与目录同名）和
  description（UI/搜索摘要，ClawHub 用 embedding 语义检索，不是关键词匹配）。slug 默认取
  文件夹名，也可以发布时用 --slug 覆盖——**不需要像 SkillHub 那样在 frontmatter 里加一个
  slug: 字段**。version 由服务端自动管理（新技能 1.0.0 起步，之后自动升 patch），frontmatter
  里现成的 version 是否会被读取，官方文档没写清楚，本脚本保留原值不动，发布时用 --version
  显式传，避免各平台版本号错位。
- 本仓库技能已经在用 metadata.openclaw 这个 ClawHub 原生字段名（requires.bins / os / emoji），
  结构基本兼容，**不需要注入新的头字段**。本脚本对 frontmatter 唯一做的修改是：如果
  metadata.openclaw（或别名 clawdbot/clawdis）块里还没有 homepage，就顺手补一个，指向本仓库
  真实地址，方便安全扫描/人工审核时溯源（skill-format.md 建议"link to source when possible"）。
- ClawHub 官方文档明确"接受任意扩展名的常规文件"，所以 SkillHub 那种"无扩展名文件会被拒
  （实测 400）"的顾虑本身不成立；但 ClawHub 有 SkillHub 没有的规则：**发布前会直接拒收
  .pyc/.pyo/.pyd 文件**（腾讯朱雀 A.I.G 扫描器暂时解析不了 Python 字节码，CVE-2026-84809
  修复前的临时限制，见 docs/security-audits.md）。所以 __pycache__ 必须清，这不是防御性
  动作而是硬要求；--strip-extensionless 依旧提供（默认关闭），仅为和 skillhub_prep.py
  保持一致，只删 LICENSE/NOTICE/ATTRIBUTION/COPYING 这几个已知文件名，不做"任何无扩展名
  文件都删"的通用扫描，避免误删技能内容里本来就该没有扩展名的文件。

用法：
  python3 tools/clawhub_prep.py --out dist/clawhub [skill-name ...]
  python3 tools/clawhub_prep.py --out dist/clawhub --strip-extensionless dockerfile-check

之后（需要用户本人先 `npx clawhub login`；ClawHub 没有单独的 skill 校验命令，--dry-run 是
最接近本地校验的手段，但它不检查 --categories/--topics 是否合法——这两个只有真正发布时才校验）：
  npx clawhub skill publish dist/clawhub/<slug> --slug <slug> --categories <...> --topics "<...>" --dry-run
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 和 tools/skillhub_prep.py 用同一个真实仓库地址（已核实存在：github.com/po-et/workbuddy-skills）
HOMEPAGE = "https://github.com/po-et/workbuddy-skills"

# 目前只试跑这 3 个技能（任务范围）。后续要发布更多技能时，照这个格式往三个字典里加就行——
# 结构上刻意和 skillhub_prep.py 的 SLUGS/TAGS 字典保持同一种"每个技能一行"的风格，方便对照。
# slug：默认等于技能名（2026-09-18 用 `npx clawhub inspect <slug>` 核实过，三个都未被占用；
#       注册表状态会变，正式发布前建议再查一次）。
SLUGS = {
    "dockerfile-check": "dockerfile-check",
    "iteration-report": "iteration-report",
    "handoff-doc-zh": "handoff-doc-zh",
}

# --categories：最多 3 个，必须是 docs/publishing.md 给出的 14 个固定 slug 之一，其余值发布会
# 直接失败（dry-run 不查这个）。合法枚举：integrations/automation/research/development/
# productivity/communication/creative/knowledge/agents/operations/security/finance/lifestyle/other
CATEGORIES = {
    "dockerfile-check": ["development", "security", "operations"],
    "iteration-report": ["productivity", "development"],
    "handoff-doc-zh": ["agents", "productivity"],
}

# --topics：最多 5 个自由词，每个 ≤48 字符，不能是保留词（approved/audited/certified/clawhub/
# community/curated/endorsed/featured/official/officials/openclaw/recommended/staff-pick/
# trusted/trusted-publisher/verified）。这里选的词都是我们自己编的，不是 ClawHub 规定的内容。
TOPICS = {
    "dockerfile-check": ["dockerfile", "docker", "container-security", "lint", "ci-gate"],
    "iteration-report": ["sprint-report", "git", "changelog", "standup"],
    "handoff-doc-zh": ["session-handoff", "agent-handoff", "context-management", "chinese"],
}


def source_dir(name: str) -> Path:
    for base in (ROOT / "skills", ROOT / "ported" / "skills"):
        if (base / name / "SKILL.md").exists():
            return base / name
    sys.exit(f"找不到技能目录: {name}")


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


def inject_homepage(fm: str, homepage: str) -> str:
    """在 metadata.openclaw（或别名 clawdbot/clawdis）的 flow-style JSON 块里补一个 homepage。

    只处理 `metadata:` 后面紧跟 `{` 的写法（本仓库现有技能都是这种写法）；块式 YAML
    （metadata:\\n  openclaw:\\n    ...）或解析失败一律原样返回，不强行改写、不报错。
    """
    m = re.search(r"^metadata:[ \t]*\n?[ \t]*(\{)", fm, re.M)
    if not m:
        return fm
    idx = m.start(1)
    depth = 0
    end = None
    for i in range(idx, len(fm)):
        if fm[i] == "{":
            depth += 1
        elif fm[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return fm
    try:
        obj = json.loads(fm[idx : end + 1])
    except json.JSONDecodeError:
        return fm
    for key in ("openclaw", "clawdbot", "clawdis"):
        if key in obj and isinstance(obj[key], dict):
            obj[key].setdefault("homepage", homepage)
            break
    else:
        return fm
    new_json = json.dumps(obj, ensure_ascii=False, indent=2)
    return fm[:idx] + new_json + fm[end + 1 :]


def prep(name: str, out: Path, strip_extensionless: bool = False) -> Path:
    src = source_dir(name)
    slug = SLUGS.get(name, name)
    dst = out / slug
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc", "*.pyo", "*.pyd"),
    )
    # 防御性二次清理：上面的 ignore_patterns 已经够用了，这里再扫一遍确保没有漏网的字节码文件
    # ——ClawHub 发布前会直接拒收 .pyc/.pyo/.pyd，这一步不是可选项。
    for p in list(dst.rglob("*")):
        if p.is_dir() and p.name == "__pycache__":
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file() and p.suffix in (".pyc", ".pyo", ".pyd"):
            p.unlink()
    if strip_extensionless:
        # 注意：ClawHub 官方文档明确"接受任意扩展名的常规文件"（docs/skill-format.md「Skill
        # files」节），这一步不是 ClawHub 要求的，只是为了和 skillhub_prep.py 的处理方式保持
        # 一致，默认关闭。只删这几个已知的许可证类文件名，不做通用的"无扩展名就删"扫描。
        for junk in ("LICENSE", "NOTICE", "ATTRIBUTION", "COPYING"):
            f = dst / junk
            if f.exists():
                f.unlink()
    fm, body = split_frontmatter((dst / "SKILL.md").read_text("utf-8"))
    fm = inject_homepage(fm, HOMEPAGE)
    (dst / "SKILL.md").write_text(f"---\n{fm}\n---\n{body}", "utf-8")
    return dst


def check(dst: Path):
    errs, warns = [], []
    fm, _ = split_frontmatter((dst / "SKILL.md").read_text("utf-8"))
    name = get(fm, "name")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or "") or not 1 <= len(name or "") <= 64:
        errs.append(f"name 不是 1-64 位小写字母/数字/连字符: {name!r}")
    if not get(fm, "description"):
        errs.append("缺 description（ClawHub 用它做 UI/搜索摘要，也是语义检索的主要输入）")
    version = get(fm, "version")
    if version and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        warns.append(f"version 存在但不是 SemVer: {version!r}（发布时可用 --version 覆盖）")
    total = 0
    bad_ext = []
    has_pycache = False
    for p in dst.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
            if p.suffix in (".pyc", ".pyo", ".pyd"):
                bad_ext.append(str(p.relative_to(dst)))
        elif p.is_dir() and p.name == "__pycache__":
            has_pycache = True
    if total > 50 * 1024 * 1024:
        errs.append(f"打包体积 {total / 1024 / 1024:.1f}MB 超过 ClawHub 单包 50MB 上限")
    if bad_ext:
        errs.append(f"含 ClawHub 会拒收的字节码文件: {bad_ext}")
    if has_pycache:
        errs.append("含 __pycache__ 目录")
    if '"windows"' in fm:
        warns.append(
            'metadata 里 os 值写的是 "windows"；ClawHub 文档示例给的是 "macos"/"linux"，本仓库'
            '另一个技能（iteration-report）用的是 "win32"，三种写法没有在同一份文档里同时确认过'
            "，具体校验规则需确认（见 docs/clawhub-notes.md），本脚本未自动改写"
        )
    return errs, warns


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/clawhub")
    ap.add_argument(
        "--strip-extensionless",
        action="store_true",
        help="额外删除 LICENSE/NOTICE/ATTRIBUTION/COPYING；ClawHub 并不要求，只是和 "
        "skillhub_prep.py 保持一致，默认关闭",
    )
    ap.add_argument("names", nargs="*", default=list(SLUGS))
    a = ap.parse_args()
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for n in a.names:
        d = prep(n, out, strip_extensionless=a.strip_extensionless)
        errs, warns = check(d)
        bad += bool(errs)
        print(("FAIL " if errs else "OK   ") + str(d.relative_to(ROOT) if d.is_relative_to(ROOT) else d))
        for e in errs:
            print("     -", e)
        for w in warns:
            print("     ! ", w)
    print()
    print("建议的发布命令（需要先手动 `npx clawhub login`；--dry-run 不校验 --categories/--topics"
          "是否合法，那部分只在真正发布时才会报错）：")
    for n in a.names:
        slug = SLUGS.get(n, n)
        d = out / slug
        cats = ",".join(CATEGORIES.get(n, []))
        tops = ",".join(TOPICS.get(n, []))
        cmd = f"npx clawhub skill publish {d} --slug {slug} --version {get(split_frontmatter((d / 'SKILL.md').read_text('utf-8'))[0], 'version') or '0.1.0'}"
        if cats:
            cmd += f" --categories {cats}"
        if tops:
            cmd += f' --topics "{tops}"'
        cmd += " --dry-run"
        print(f"  {cmd}")
    sys.exit(1 if bad else 0)
