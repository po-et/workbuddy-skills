"""SKILL.md frontmatter 的切分、解析与改写 —— 全工具只有这一份实现。

支持的 YAML 子集（覆盖平台上技能实际用到的全部写法）::

    key: 标量
    key: "带空格或冒号的标量"
    key: [a, b, c]            # 内联列表
    key:
      - 列表项
    key:
      子键: 值                 # 嵌套映射
    key: { "a": 1 }           # 内联 JSON（单行或跨行，如 metadata.openclaw）

不支持锚点、多行折叠标量（| 与 >）、复杂流式嵌套 —— 平台上的技能都不用，
真需要的时候请直接装 PyYAML 自己解析。

改写类函数（drop_keys / prepend）刻意在**原始文本**上做最小改动，
不做「解析再序列化」，这样注释、字段顺序、缩进风格都能原样保留。
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

#: `---\n ... \n---\n` 形式的 frontmatter
_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)
#: 顶格的 `key:` 或 `key: value`
_KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*)\s*:(.*)$")
#: 未加引号却含 ": " 的值 —— 平台的严格 YAML 解析器会直接报错
_UNQUOTED_COLON_RE = re.compile(r"^\s*[\w-]+:\s+(?![\"'\[{|>])(.+)$")


class FrontmatterError(ValueError):
    """SKILL.md 缺少 frontmatter 或 frontmatter 不可解析。"""


# ---------------------------------------------------------------- 切分

def split(text):
    # type: (str) -> Tuple[str, str]
    """把 SKILL.md 全文切成 (frontmatter 文本, 正文)。没有 frontmatter 就抛错。"""
    parts = try_split(text)
    if parts is None:
        raise FrontmatterError("SKILL.md 缺少 frontmatter（须以 --- 开头，并以单独一行 --- 结束）")
    return parts


def try_split(text):
    # type: (str) -> Optional[Tuple[str, str]]
    """同 split，但没有 frontmatter 时返回 None 而不是抛错。"""
    m = _FM_RE.match(text)
    if not m:
        return None
    return m.group(1), m.group(2)


def join(fm_text, body):
    # type: (str, str) -> str
    """把 frontmatter 文本与正文拼回一份完整的 SKILL.md。"""
    return "---\n%s\n---\n%s" % (fm_text, body)


# ---------------------------------------------------------------- 解析

def parse(fm_text):
    # type: (str) -> Dict[str, Any]
    """把 frontmatter 文本解析成 dict。值可能是 str / bool / list / dict。"""
    lines = fm_text.split("\n")
    root = {}  # type: Dict[str, Any]
    stack = [(-1, root)]  # type: List[Tuple[int, Any]]
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip())
        s = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]

        if s.startswith("- "):
            if isinstance(container, list):
                container.append(scalar(s[2:]))
            i += 1
            continue
        if s in ("-",):
            i += 1
            continue
        if s[0] in "{[}]":          # 归属上一个 key 的 JSON 块，已在 key 分支里消费过
            i += 1
            continue

        m = _KEY_RE.match(s)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()

        if rest:
            if rest[0] in "{[":
                value, i = _consume_block(lines, i, raw.index(rest[0]))
            else:
                value = scalar(rest)
                i += 1
            if isinstance(container, dict):
                container[key] = value
            continue

        # `key:` 后面没有值：向前看一行，决定是列表 / 嵌套映射 / JSON 块 / 空串
        j = i + 1
        while j < n and (not lines[j].strip() or lines[j].lstrip().startswith("#")):
            j += 1
        if j >= n:
            if isinstance(container, dict):
                container[key] = ""
            break
        nxt = lines[j].strip()
        nxt_indent = len(lines[j]) - len(lines[j].lstrip())
        if nxt_indent <= indent:
            if isinstance(container, dict):
                container[key] = ""
            i += 1
            continue
        if nxt[0] in "{[":
            value, i = _consume_block(lines, j, nxt_indent)
            if isinstance(container, dict):
                container[key] = value
            continue
        child = [] if nxt.startswith("- ") else {}  # type: Any
        if isinstance(container, dict):
            container[key] = child
        stack.append((indent, child))
        i += 1
    return root


def _consume_block(lines, start_line, start_col):
    # type: (List[str], int, int) -> Tuple[Any, int]
    """从 lines[start_line][start_col:] 起读一段花括号/方括号平衡的文本。

    返回 (解析结果, 下一行行号)。能 json.loads 就给结构体；只有一行的 `[a, b]`
    这种非 JSON 内联列表按逗号切；都不行就原样返回字符串。
    """
    buf = []
    depth = 0
    in_str = False
    esc = False
    i = start_line
    col = start_col
    while i < len(lines):
        line = lines[i]
        seg = line[col:] if i == start_line else line
        for ch in seg:
            buf.append(ch)
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    text = "".join(buf)
                    return _decode_block(text), i + 1
        buf.append("\n")
        i += 1
        col = 0
    return "".join(buf).strip(), len(lines)


def _decode_block(text):
    # type: (str) -> Any
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    if text.startswith("[") and text.endswith("]"):
        return [scalar(p) for p in text[1:-1].split(",") if p.strip()]
    return text


def scalar(value):
    # type: (str) -> Any
    """标量：去引号、识别 true/false，其余一律按字符串处理（版本号必须保持字符串）。"""
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1].replace('\\"', '"')
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def as_text(value):
    # type: (Any) -> str
    """把解析结果安全地当字符串用（list/dict 原样 json 化，None 变空串）。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def as_list(value):
    # type: (Any) -> List[str]
    """把解析结果当字符串列表用。支持 ["a","b"] 与 "a, b" / "[a, b]" 两种来源。"""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [as_text(v).strip() for v in value if as_text(v).strip()]
    if isinstance(value, str):
        return [p.strip().strip("\"'") for p in value.strip("[]").split(",") if p.strip()]
    return []


# ---------------------------------------------------------------- 原文读取

def get_raw(fm_text, key):
    # type: (str, str) -> str
    """从原始文本里取一个顶格单行标量。解析器读不到的极端写法也能兜住。"""
    m = re.search(r"^%s:\s*(.+)$" % re.escape(key), fm_text, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def unquoted_colon_lines(fm_text):
    # type: (str) -> List[Tuple[int, str]]
    """找出会被严格 YAML 解析器拒掉的行：未加引号的值里含「: 」。"""
    bad = []
    for lineno, raw in enumerate(fm_text.split("\n"), 1):
        m = _UNQUOTED_COLON_RE.match(raw)
        if m and ": " in m.group(1):
            bad.append((lineno, raw.strip()))
    return bad


# ---------------------------------------------------------------- 改写

def drop_keys(fm_text, keys):
    # type: (str, Any) -> str
    """从 frontmatter 原文里删掉若干顶格字段（块式列表与单行两种写法都删）。

    注意：值为嵌套映射或 JSON 块的字段不要用这个函数删 —— 只会删掉 `key:` 那一行，
    留下孤儿缩进行。本工具只用它删 version / tags 这类简单字段。
    """
    out = fm_text
    for key in keys:
        esc = re.escape(key)
        out = re.sub(r"^%s:[ \t]*\n(?:[ \t]*-[ \t]*.+\n?)+" % esc, "", out, flags=re.M)
        out = re.sub(r"^%s:.*\n?" % esc, "", out, flags=re.M)
    return out


def fmt_scalar(key, value, quote=False):
    # type: (str, Any, bool) -> str
    """序列化一行 `key: value`。quote=True 时给值加双引号（含冒号/空格的值必须加）。"""
    text = as_text(value)
    if quote:
        return '%s: "%s"' % (key, text.replace('"', '\\"'))
    return "%s: %s" % (key, text)


def fmt_list(key, items):
    # type: (str, Any) -> str
    """序列化块式列表。空列表返回 `key: []`，避免产出一个悬空的 `key:`。"""
    items = list(items)
    if not items:
        return "%s: []" % key
    return key + ":\n" + "".join("  - %s\n" % i for i in items).rstrip("\n")
