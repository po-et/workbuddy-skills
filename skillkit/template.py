"""`skillkit new` 用的骨架模板。

模板刻意写成「一上来就能过 lint 的格式校验、但分数不高」的样子：
必填字段一个不少（省得作者去撞平台那几条没写进文档的必填项），
内容全是占位符和注释，逼作者把真实内容填进去 —— 分数是填出来的，不是模板送的。
"""

import re
from typing import Dict

SKILL_MD = '''---
# ───────────────────────────────────────────────────────────────────────
# 下面这些字段全部是平台解析器**强制必填**的。少一个就是解析失败，
# 而失败的上传/发布请求一样消耗你的发布配额 —— 发之前先 `skillkit lint`。
# display_name / display_name_en 官方文档里没写，是实测报错逼出来的。
# ───────────────────────────────────────────────────────────────────────
name: {name}
# description 决定这个技能能不能被搜到、能不能被 Agent 主动调起。
# 写法要点（按实测排序，最重要的在最前面）：
#   1. 先铺「同义说法」：用户会用什么词描述这件事，一次列全，用「、」隔开；
#   2. 再写「什么时候用」：当用户说「…」「…」时使用；
#   3. 最后写技能提供什么（脚本名、输出形态、退出码）。
#   4. 触发面里写进去的每一类场景，正文都必须有对应的处理方法。
#      写不出方法的场景不许写进触发面 —— 那是骗调用，砸的是自己招牌。
description: "{title}、（在这里补 5–10 个同义说法）。当用户说「（典型问法 1）」「（典型问法 2）」「（典型问法 3）」时使用。附纯标准库脚本 scripts/{script_stem}.py：（说清它做什么、输出什么、退出码怎么约定）。"
author: {author}
# 三段式 SemVer，只认 x.y.z。重传同名技能时**必须比线上/草稿版本大**，草稿也算数。
version: 0.1.0
display_name: "{title}"
display_name_en: "{title_en}"
description_zh: "（一句话说清这个技能替用户做完什么事，120 字以内，会显示在市场卡片上）"
description_en: "(One sentence on what this skill gets done for the user.)"
# 每种语言**最多 3 条**，第 4 条会被解析器直接拒掉。显示为「试试这样问我」。
examples_zh:
  - "（用户会怎么问，第 1 条）"
  - "（用户会怎么问，第 2 条）"
  - "（用户会怎么问，第 3 条）"
examples_en:
  - "(How a user would ask, 1)"
  - "(How a user would ask, 2)"
  - "(How a user would ask, 3)"
# tags 建议 6–12 个，中英混合、含缩写；搜索靠它兜底。
tags:
  - {name}
  - （中文标签）
  - （英文标签）
  - （缩写或工具名）
  - （场景词）
  - （同义词）
# 任何未加引号的值里只要出现「: 」，严格 YAML 解析器就会报
# mapping values are not allowed in this context —— 遇到就整体加双引号。
metadata:
  {{ "openclaw": {{ "requires": {{ "bins": ["python3"] }}, "os": ["darwin", "linux", "windows"], "emoji": "🧰" }} }}
---

# {title}

（一句话说清这个技能解决什么问题、不解决什么问题。）

## 何时用

- 当用户（场景 1）
- 当用户（场景 2）
- **不用于**：（明确划出边界，避免误触发把用户带到帮不上忙的地方）

## 用法

```bash
python3 scripts/{script_stem}.py <输入>          # 最常用的一条
python3 scripts/{script_stem}.py --json          # 机器可读，便于串流水线
python3 scripts/{script_stem}.py --strict        # 有问题就退出码 1，用作 CI 门禁
```

## 流程

1. （第 1 步：先做什么，为什么先做这个）
2. （第 2 步：看输出里的哪一部分，怎么判断）
3. （第 3 步：改完怎么复验）

## 输出契约

| 字段 | 含义 | 说明 |
|---|---|---|
| （字段名） | （含义） | （取值范围 / 单位 / 何时为空） |

退出码：0 = 通过；1 = （什么情况）。

## 常见问题

- **（用户最容易踩的坑 1）** —— （怎么办）
- **（用户最容易踩的坑 2）** —— （怎么办）
'''

SCRIPT_PY = '''#!/usr/bin/env python3
"""{title}。

纯 Python 标准库，无第三方依赖 —— 技能脚本跑在别人的机器上，
装依赖这件事本身就是失败率最高的一步。
"""

import argparse
import json
import sys


def run(target):
    """核心逻辑写在这里，返回一个可 JSON 序列化的结果。"""
    return {{"target": target, "findings": [], "ok": True}}


def main(argv=None):
    parser = argparse.ArgumentParser(description="{title}")
    parser.add_argument("target", nargs="?", default=".", help="要处理的文件或目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="有问题时退出码 1，用作 CI 门禁")
    args = parser.parse_args(argv)

    result = run(args.target)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("目标: %s" % result["target"])
        for item in result["findings"]:
            print("  - %s" % item)
        if not result["findings"]:
            print("  没有发现问题")
    return 1 if args.strict and not result["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
'''


def snake(name):
    # type: (str) -> str
    """kebab-case → snake_case，用作脚本文件名。"""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "main"


def title_from(name):
    # type: (str) -> str
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", name) if w) or name


def render(name, author="", title="", title_en=""):
    # type: (str, str, str, str) -> Dict[str, str]
    """渲染骨架文件。返回 {相对路径: 内容}。"""
    script_stem = snake(name)
    title = title or title_from(name)
    title_en = title_en or title_from(name)
    ctx = {
        "name": name,
        "author": author or "（你的开发者昵称）",
        "title": title,
        "title_en": title_en,
        "script_stem": script_stem,
    }
    return {
        "SKILL.md": SKILL_MD.format(**ctx),
        "scripts/%s.py" % script_stem: SCRIPT_PY.format(**ctx),
    }
