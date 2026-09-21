"""五维质量打分（各 20 分，总分 100）。

口径与 skills/skill-lint/scripts/skill_lint.py 完全一致 —— 那份脚本给仓库里 81 个技能
打过分、也被用在真实发布前的自检里，所以这里是**按它的行为复刻**，而不是重新设计一套。
任何想改分数口径的念头，先去改 skill-lint 或者明确说明为什么要分叉。

  1 可发现性：description 是否写清「什么时候用」、触发词/同义词覆盖、长度；tags 数量
  2 结构    ：何时用 / 流程 / 产出 / 边界 四节是否齐；正文篇幅
  3 可执行性：有没有命令块；引用的脚本是否真的存在
  4 合规    ：frontmatter 必填、无扩展名文件、复刻作品有 ATTRIBUTION、正文无密钥
  5 示例    ：examples 数量，以及示例与 description 关键词是否对得上
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from . import rules
from .skillpkg import Skill

_CODE_BLOCK_RE = re.compile(r"```(?:bash|sh|shell|python|json|yaml)?\n(.*?)```", re.S)
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.M)
_BASEDIR_REF_RE = re.compile(r"\{baseDir\}/([\w./-]+)")
_SCRIPTS_REF_RE = re.compile(r"(?:^|\s)scripts/([\w./-]+\.py)")
_RUNTIME_RE = re.compile(r"\b(python3|node|bash)\b")
_ATTRIB_RE = re.compile(r"改编自|Adapted from|来源：|Source:")
_QUOTE_RE = re.compile("[「」“”]")
_CJK_WORD_RE = re.compile(r"[一-鿿]{2,}")


def score_skill(skill):
    # type: (Skill) -> Dict[str, Any]
    """给一个技能打分。返回 {name, total, scores, tips}。"""
    d = skill.dir
    body = skill.body
    desc = skill.field("description") or skill.field("summary")
    tags = skill.tags
    tips = []  # type: List[str]

    s1 = _discoverability(desc, tags, tips)
    s2 = _structure(body, tips)
    s3 = _executability(body, d, tips)
    s4 = _compliance(skill, body, d, tips)
    s5 = _examples(skill, desc, tips)

    total = max(0, min(100, s1 + s2 + s3 + s4 + s5))
    return {
        "name": skill.name,
        "path": str(skill.skill_md),
        "total": total,
        "scores": dict(zip(rules.SCORE_DIMENSIONS, (s1, s2, s3, s4, s5))),
        "tips": tips,
    }


def empty_score(name, path, reason):
    # type: (str, str, str) -> Dict[str, Any]
    """连 SKILL.md 都没有时的零分结果。"""
    return {
        "name": name,
        "path": path,
        "total": 0,
        "scores": dict((k, 0) for k in rules.SCORE_DIMENSIONS),
        "tips": [reason],
    }


# ---------------------------------------------------------------- 1 可发现性

def _discoverability(desc, tags, tips):
    # type: (str, List[str], List[str]) -> int
    s = 0
    if desc:
        s += 4
        if any(w in desc for w in rules.TRIGGER_WORDS):
            s += 5
        else:
            tips.append("description 里写清『什么时候用』（当用户说…时使用）")
        syn = len(_QUOTE_RE.findall(desc)) // 2 + desc.count("、") + desc.count("/")
        if syn >= 6:
            s += 5
        elif syn >= 3:
            s += 3
        else:
            tips.append("description 补充触发词与同义词（用户会怎么说这件事）")
        lo, hi = rules.DESC_LEN_OK
        length = len(desc)
        if lo <= length <= hi:
            s += 3
        elif length > hi:
            tips.append("description %d 字偏长，超过 %d 会被截断/降权（估）" % (length, hi))
        else:
            tips.append("description 只有 %d 字，太短难以命中搜索" % length)
    else:
        tips.append("缺 description/summary")
    if len(tags) >= rules.TAGS_GOOD:
        s += 3
    elif len(tags) >= rules.TAGS_OK:
        s += 2
    else:
        tips.append("tags 建议 6–12 个，中英混合含缩写")
    return s


# ---------------------------------------------------------------- 2 结构

def _structure(body, tips):
    # type: (str, List[str]) -> int
    s = 0
    heads = _HEADING_RE.findall(body)
    found = {}
    for section, hints in rules.SECTION_HINTS.items():
        in_head = any(
            any(hint.lower() in h.lower() for hint in hints) for h in heads
        )
        found[section] = in_head or any(hint in body for hint in hints)
    s += 4 * sum(1 for v in found.values() if v)
    for section, ok in found.items():
        if not ok:
            tips.append("正文缺『%s』一节" % section)
    lo, hi = rules.BODY_LEN_OK
    n = len(body)
    if lo <= n <= hi:
        s += 4
    elif n < lo:
        tips.append("正文仅 %d 字符，可能太薄" % n)
        s += 1
    else:
        tips.append("正文 %d 字符，考虑把参考内容拆到 references/" % n)
        s += 2
    return s


# ---------------------------------------------------------------- 3 可执行性

def _executability(body, d, tips):
    # type: (str, Path, List[str]) -> int
    s = 0
    if _CODE_BLOCK_RE.findall(body):
        s += 8
    else:
        tips.append("没有任何命令/代码块，Agent 难以按图索骥")
    refs = set(_BASEDIR_REF_RE.findall(body)) | set(_SCRIPTS_REF_RE.findall(body))
    missing = sorted(
        r for r in refs
        if not (d / r).exists() and not (d / "scripts" / Path(r).name).exists()
    )
    if refs and not missing:
        s += 8
    elif refs:
        s += 3
        tips.append("引用了不存在的文件: " + ", ".join(missing[:5]))
    else:
        s += 4
    if _RUNTIME_RE.search(body):
        s += 4
    return s


# ---------------------------------------------------------------- 4 合规

def _compliance(skill, body, d, tips):
    # type: (Skill, str, Path, List[str]) -> int
    s = 0
    if skill.data.get("name") or skill.data.get("slug"):
        s += 5
    else:
        tips.append("frontmatter 缺 name（或 SkillHub 的 slug）")
    if skill.data.get("version"):
        s += 3

    junk = [p.name for p in skill.files() if p.suffix == ""]
    if not junk:
        s += 4
    else:
        tips.append("无扩展名文件会被 SkillHub 拒绝: " + ", ".join(sorted(junk)[:5]))

    attribution = d / "ATTRIBUTION.md"
    has_attrib = attribution.is_file()
    haystack = body
    if has_attrib:
        haystack = body + attribution.read_text(encoding="utf-8", errors="ignore")
    if _ATTRIB_RE.search(haystack):
        s += 4 if has_attrib else 2
        if not has_attrib:
            tips.append("复刻作品建议附 ATTRIBUTION.md（来源、许可证、改动）")
    else:
        s += 4

    if rules.SCORE_SECRET_RE.search(body):
        tips.append("正文疑似包含密钥样字符串！")
        s -= 10
    else:
        s += 4
    return s


# ---------------------------------------------------------------- 5 示例

def _examples(skill, desc, tips):
    # type: (Skill, str, List[str]) -> int
    s = 0
    examples = skill.list_field("examples_zh") + skill.list_field("examples_en")
    if 2 <= len(examples) <= 6:
        s += 10
    elif examples:
        s += 6
        tips.append("examples_zh/en 各 1–3 条为宜")
    elif re.search(r"示例|例子|Example", skill.body):
        s += 5
        tips.append("frontmatter 补 examples_zh/examples_en（客户端会展示为『试试这样问我』）")
    else:
        tips.append("没有示例；加 2–3 条用户会怎么问")
    if examples and desc:
        keywords = set(_CJK_WORD_RE.findall(desc))
        hit = sum(1 for e in examples if any(k in e for k in keywords))
        need = max(1, len(examples) // 2)
        s += 10 if hit >= need else 5
        if hit < need:
            tips.append("示例与 description 关键词对不上，容易误触发")
    return s
