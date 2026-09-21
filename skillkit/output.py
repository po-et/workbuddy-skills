"""输出小工具：JSON 打印、分隔线、宽字符对齐。

全部输出到 stdout，不带颜色转义 —— 技能作者经常把结果重定向进文件或管道，
颜色只会变成一堆乱码。要高亮请自己接 `| less -R` 之类的工具。
"""

from __future__ import print_function

import json
import sys
import unicodedata
from typing import Any


def emit_json(obj, stream=None):
    # type: (Any, Any) -> None
    print(json.dumps(obj, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def hr(char="-", width=64):
    # type: (str, int) -> str
    return char * width


def width(text):
    # type: (str) -> int
    """显示宽度：中文/全角算 2 列。"""
    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def pad(text, columns):
    # type: (str, int) -> str
    """按显示宽度左对齐补空格（超宽就原样返回）。"""
    gap = columns - width(text)
    return text + " " * gap if gap > 0 else text


def truncate(text, columns):
    # type: (str, int) -> str
    """按显示宽度截断，超出的用 … 结尾。"""
    if width(text) <= columns:
        return text
    out = []
    used = 0
    for ch in text:
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + w > columns - 1:
            break
        out.append(ch)
        used += w
    return "".join(out) + "…"


def truncate_path(text, columns):
    # type: (str, int) -> str
    """路径专用：从左边砍，保留尾部 —— 尾部才是技能名，才是人要看的那一段。"""
    if width(text) <= columns:
        return text
    out = []
    used = 0
    for ch in reversed(text):
        w = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + w > columns - 1:
            break
        out.append(ch)
        used += w
    return "…" + "".join(reversed(out))
