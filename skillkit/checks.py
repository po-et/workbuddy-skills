"""格式校验：把「会被平台解析器拒掉」的东西找出来。

判级口径：
  FAIL —— 按实测/文档，这样传上去会被拒或解析失败；
  WARN —— 不会被拒，但会影响展示、审核或后续重传；
  PASS —— 通过某一组检查的记号，便于人眼确认检查真的跑过。

规则全部来自 skillkit/rules.py，不在这里内联魔法值。
"""

import re
from typing import List, Optional

from . import frontmatter as fm
from . import rules
from .skillpkg import Skill

FAIL = "FAIL"
WARN = "WARN"
PASS = "PASS"


class Finding(object):
    """一条检查结论。"""

    __slots__ = ("level", "message", "rule")

    def __init__(self, level, message, rule=None):
        # type: (str, str, Optional[str]) -> None
        self.level = level
        self.message = message
        self.rule = rule

    def as_dict(self):
        return {"level": self.level, "message": self.message, "rule": self.rule}

    def __repr__(self):
        return "Finding(%s, %r)" % (self.level, self.message)


def check_skill(skill):
    # type: (Skill) -> List[Finding]
    """对一个技能目录跑完整的格式校验。"""
    out = []  # type: List[Finding]

    def fail(msg, rule=None):
        out.append(Finding(FAIL, msg, rule))

    def warn(msg, rule=None):
        out.append(Finding(WARN, msg, rule))

    if not skill.has_frontmatter:
        fail("SKILL.md 缺少 frontmatter（须以 --- 开头）", "parser-required-fields")
        return out

    # 严格 YAML：未加引号的值里含 ": " 会直接解析失败
    for lineno, text in fm.unquoted_colon_lines(skill.fm_text):
        fail(
            "frontmatter 第 %d 行：未加引号的值含 ': '，严格 YAML 会解析失败，"
            "请用双引号包住整个值 —— %s" % (lineno, text[:60]),
            "strict-yaml-colon",
        )

    # 必填字段
    for key, reason in rules.REQUIRED_FIELDS:
        if not skill.data.get(key):
            fail("缺少 %s（%s）" % (key, reason), "parser-required-fields")
    for key, reason in rules.SOFT_REQUIRED_FIELDS:
        if not skill.data.get(key):
            warn("缺少 %s（%s）" % (key, reason), "parser-required-fields")

    # name 与目录名
    name = skill.field("name")
    if name and name != skill.dirname:
        warn("name=%r 与目录名 %r 不一致" % (name, skill.dirname))
    if name and not rules.KEBAB.match(name):
        fail("name 须小写字母数字加连字符: %r" % name)

    # 版本号
    version = skill.field("version")
    if version and not rules.SEMVER.match(version):
        fail("version 应为 x.y.z: %r" % version, "semver-three-parts")

    # 描述长度
    desc = skill.field("description")
    if len(desc) > rules.DESCRIPTION_MAX:
        fail("description 超过 %d 字符 (%d)" % (rules.DESCRIPTION_MAX, len(desc)))

    # 示例
    for key in rules.EXAMPLE_FIELDS:
        raw = skill.data.get(key)
        if raw is None:
            warn("未提供 %s（可选；会显示为「试试这样问我」，建议 3 条）" % key, "examples-max-3")
        elif not isinstance(raw, list):
            fail("%s 必须是字符串数组" % key, "examples-max-3")
        elif len(raw) > rules.EXAMPLES_MAX:
            fail(
                "%s 最多 %d 条，当前 %d（解析器原文：最多 %d 个示例）"
                % (key, rules.EXAMPLES_MAX, len(raw), rules.EXAMPLES_MAX),
                "examples-max-3",
            )

    out.append(Finding(PASS, "SKILL.md frontmatter 检查完成"))
    out.append(
        Finding(
            WARN,
            "提醒：同名技能已存在于平台时须走草稿「编辑」重传，且 version 必须大于线上/草稿版本",
            "version-must-increase",
        )
    )

    out.extend(check_files(skill))
    return out


def check_files(skill):
    # type: (Skill) -> List[Finding]
    """包内文件检查：脏文件、密钥、无扩展名文件、体积。"""
    out = []  # type: List[Finding]

    for rel in skill.junk_paths():
        out.append(Finding(FAIL, "不应包含 %s" % rel))

    for path in skill.files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in rules.SECRET_RE:
            if pattern.search(text):
                out.append(Finding(FAIL, "%s 疑似含 %s" % (skill.rel(path), label)))

    for rel in skill.extensionless_files():
        base = rel.split("/")[-1]
        if base in rules.EXTENSIONLESS_DROP or base.upper().startswith("LICENSE"):
            out.append(
                Finding(
                    WARN,
                    "技能包内含 %s（SkillHub 实测拒收无扩展名文件；"
                    "skillkit build 会自动删掉它，许可证写进 frontmatter 的 license 字段）" % rel,
                    "extensionless-file",
                )
            )
        else:
            out.append(
                Finding(
                    WARN,
                    "无扩展名文件 %s 会被 SkillHub 拒收（400 不允许的文件类型）；"
                    "请加扩展名或删除 —— build 不会自动处理它" % rel,
                    "extensionless-file",
                )
            )

    # LICENSE.txt 有扩展名，不会被 400 拦，但 SkillHub 规则不建议放进技能包
    for path in skill.files():
        if path.parent == skill.dir and path.name.upper().startswith("LICENSE") and path.suffix:
            out.append(
                Finding(WARN, "技能包内含 %s（SkillHub 规则不建议放入技能包）" % path.name,
                        "extensionless-file")
            )

    size = skill.total_size()
    if size > rules.SKILL_ZIP_MAX:
        out.append(
            Finding(
                FAIL,
                "目录未压缩已有 %dKB，超过技能包 %dMB 上限（压缩后可能仍超）"
                % (size // 1024, rules.SKILL_ZIP_MAX // 1024 // 1024),
            )
        )
    return out


def check_publish_copy(directory):
    # type: (object) -> List[Finding]
    """校验 build 已落盘的 SkillHub 发布副本。"""
    from pathlib import Path

    md = Path(str(directory)) / "SKILL.md"
    if not md.is_file():
        return [Finding(FAIL, "发布副本缺少 SKILL.md")]
    parts = fm.try_split(md.read_text(encoding="utf-8"))
    if parts is None:
        return [Finding(FAIL, "发布副本的 SKILL.md 缺少 frontmatter")]
    return check_publish_text(parts[0])


def check_publish_text(fm_text):
    # type: (str) -> List[Finding]
    """校验发布副本的 frontmatter 文本（slug / version / displayName / 建议字段 / 重复键）。"""
    out = []  # type: List[Finding]
    slug = fm.get_raw(fm_text, "slug")
    if not rules.KEBAB.match(slug or "") or not (
        rules.SLUG_MIN_LEN <= len(slug) <= rules.SLUG_MAX_LEN
    ):
        out.append(Finding(FAIL, "slug 不是 kebab-case 或长度越界: %r" % slug, "slug-global-unique"))
    version = fm.get_raw(fm_text, "version")
    if not rules.SEMVER.match(version or ""):
        out.append(Finding(FAIL, "version 不是 SemVer: %r" % version, "semver-three-parts"))
    if not fm.get_raw(fm_text, "displayName"):
        out.append(Finding(FAIL, "缺 displayName"))
    for key in rules.SKILLHUB_RECOMMENDED:
        if not fm.get_raw(fm_text, key):
            out.append(Finding(WARN, "建议字段缺失: %s" % key))

    dup = []
    for key in ("version", "tags", "slug", "displayName", "summary"):
        hits = len(re.findall(r"^%s:" % re.escape(key), fm_text, re.M))
        if hits > 1:
            dup.append("%s x%d" % (key, hits))
    if dup:
        out.append(Finding(FAIL, "发布副本 frontmatter 有重复键: %s" % "、".join(dup)))
    return out


def counts(findings):
    # type: (List[Finding]) -> dict
    c = {FAIL: 0, WARN: 0, PASS: 0}
    for f in findings:
        c[f.level] = c.get(f.level, 0) + 1
    return c
