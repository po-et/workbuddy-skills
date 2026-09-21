"""技能目录的装载与遍历。

一个「技能」= 一个含 SKILL.md 的目录。所有子命令都通过 Skill 对象拿到
frontmatter / 正文 / 文件清单，而不是各自 open() 一遍。
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import frontmatter as fm
from .rules import JUNK_NAMES


class SkillError(Exception):
    """技能目录不存在、缺 SKILL.md、或 SKILL.md 不可解析。"""


class Skill(object):
    """一个技能目录的只读视图。"""

    def __init__(self, directory, text):
        # type: (Path, str) -> None
        self.dir = directory
        self.text = text
        parts = fm.try_split(text)
        self.has_frontmatter = parts is not None
        if parts is None:
            self.fm_text, self.body = "", text
            self.data = {}  # type: Dict[str, Any]
        else:
            self.fm_text, self.body = parts
            self.data = fm.parse(self.fm_text)

    # -------------------------------------------------- 构造

    @classmethod
    def load(cls, path):
        # type: (Any) -> "Skill"
        """path 可以是技能目录，也可以直接是某个 SKILL.md。"""
        p = Path(path)
        if p.is_dir():
            directory, md = p, p / "SKILL.md"
        elif p.name == "SKILL.md":
            directory, md = p.parent, p
        elif p.exists():
            raise SkillError("%s 不是技能目录，也不是 SKILL.md" % p)
        else:
            raise SkillError("路径不存在: %s" % p)
        if not md.is_file():
            raise SkillError("缺少 SKILL.md: %s" % md)
        return cls(directory, md.read_text(encoding="utf-8", errors="replace"))

    # -------------------------------------------------- 常用字段

    @property
    def skill_md(self):
        # type: () -> Path
        return self.dir / "SKILL.md"

    @property
    def dirname(self):
        # type: () -> str
        return self.dir.name

    def field(self, key, default=""):
        # type: (str, str) -> str
        return fm.as_text(self.data.get(key, default)) or default

    def list_field(self, key):
        # type: (str) -> List[str]
        return fm.as_list(self.data.get(key))

    @property
    def name(self):
        # type: () -> str
        """展示用名字：name → slug → 目录名。"""
        return self.field("name") or self.field("slug") or self.dirname

    @property
    def description(self):
        # type: () -> str
        return self.field("description") or self.field("summary")

    @property
    def tags(self):
        # type: () -> List[str]
        return self.list_field("tags")

    # -------------------------------------------------- 文件遍历

    def files(self):
        # type: () -> List[Path]
        """目录下的全部文件（含 JUNK），相对路径排序后返回。"""
        out = []
        for p in sorted(self.dir.rglob("*")):
            if p.is_file():
                out.append(p)
        return out

    def rel(self, path):
        # type: (Path) -> str
        try:
            return str(path.relative_to(self.dir))
        except ValueError:
            return str(path)

    def junk_paths(self):
        # type: () -> List[str]
        """包内不该出现的目录/文件（__pycache__、.DS_Store、*.pyc …）。"""
        found = []
        for dirpath, dirnames, filenames in os.walk(str(self.dir)):
            for d in list(dirnames):
                if d in JUNK_NAMES:
                    found.append(os.path.relpath(os.path.join(dirpath, d), str(self.dir)))
                    dirnames.remove(d)
            for f in filenames:
                if f in JUNK_NAMES or f.endswith((".pyc", ".pyo", ".pyd")):
                    found.append(os.path.relpath(os.path.join(dirpath, f), str(self.dir)))
        return sorted(found)

    def extensionless_files(self):
        # type: () -> List[str]
        """无扩展名文件 —— SkillHub 实测直接 400 拒收。"""
        return sorted(self.rel(p) for p in self.files() if p.suffix == "")

    def total_size(self):
        # type: () -> int
        return sum(p.stat().st_size for p in self.files())


def find_skills(root):
    # type: (Any) -> List[Path]
    """在 root 下找出所有含 SKILL.md 的目录（root 自己也算）。"""
    root = Path(root)
    hits = []  # type: List[Path]
    if (root / "SKILL.md").is_file():
        hits.append(root)
    for p in sorted(root.rglob("SKILL.md")):
        d = p.parent
        if d not in hits and not any(part in JUNK_NAMES for part in d.parts):
            hits.append(d)
    return hits


def resolve_targets(paths):
    # type: (List[str]) -> List[Path]
    """把命令行传进来的一堆路径展开成技能目录列表。

    给一个含 SKILL.md 的目录就是它自己；给一个上层目录（例如 skills/）就递归找。
    """
    out = []  # type: List[Path]
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            raise SkillError("路径不存在: %s" % raw)
        if p.is_file():
            out.append(p.parent if p.name == "SKILL.md" else p)
            continue
        found = find_skills(p)
        if not found:
            raise SkillError("%s 下没有找到任何 SKILL.md" % raw)
        for d in found:
            if d not in out:
                out.append(d)
    return out


def relpath_for_display(path, base=None):
    # type: (Path, Optional[Path]) -> str
    """打印用的相对路径；不在 base 下就打全路径。"""
    base = base or Path.cwd()
    try:
        return str(Path(path).resolve().relative_to(Path(base).resolve()))
    except ValueError:
        return str(path)
