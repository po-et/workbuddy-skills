#!/usr/bin/env python3
"""生成 WorkBuddy 连接器骨架。两种模式：

手动:
  scaffold_connector.py --out DIR --type cli|mcp --source X --name-zh .. --name-en .. \
      --desc-zh .. --desc-en .. [--install CMD] [--status CMD --status-match RE] \
      [--runtime python:3.10] [--mcp-url https://..] [--example-zh ..]* [--example-en ..]*

CLI-Anything 桥:
  scaffold_connector.py --from-cli-anything registry.json <name> [--harness-root DIR] --out DIR

生成后务必手改并运行 validate_connector.py。
"""
import argparse
import json
import os
import shutil
import sys

ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" '
        'fill="none" stroke="#3B82F6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="10" y="14" width="44" height="36" rx="6"/><path d="M20 30h24M20 38h14"/></svg>\n')

SKILL_TPL = """---
name: {skill}
description: 当用户要{what}时使用。触发词：{triggers}。通过 {entry} 命令行完成。
---

# {name_zh}

## 前置条件

- 命令 `{entry}` 已由连接器安装
- {requires}

## 固定工作流

所有命令加 `--json`，用绝对路径，检查返回码。

```bash
{entry} --json --help
# TODO: 补 3–5 条 Agent 真会用到的命令，给一条完整可跑的序列
```

## 常见错误

| 现象 | 处理 |
|---|---|
| 命令返回非 0 | 读 stderr；确认前置条件 |

## 出处

TODO：若封装第三方项目，写明原项目、协议、作者，并在连接器根目录放 LICENSE 与 ATTRIBUTION.md。
"""


def platform_map(cmd, win=None):
    return {"darwin": cmd, "linux": cmd, "win32": win or cmd}


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2) + "\n")
    print("  +", os.path.relpath(path))


def build(a):
    meta = {
        "name": a.name_zh, "name_zh": a.name_zh, "name_en": a.name_en,
        "description": a.desc_zh, "description_zh": a.desc_zh, "description_en": a.desc_en,
        "source": a.source, "type": a.type, "version": a.version,
        "examples_zh": a.example_zh or [f"用{a.name_zh}帮我处理一下这个", f"列出{a.name_zh}里最近的内容"],
        "examples_en": a.example_en or [f"Use {a.name_en} to handle this", f"List recent items in {a.name_en}"],
    }
    if a.min_version:
        meta["minWorkbuddyVersion"] = a.min_version
    write(os.path.join(a.out, "connector-meta.json"), meta)

    if a.type == "cli":
        cli = {}
        if a.runtime:
            t, _, v = a.runtime.partition(":")
            cli["runtime"] = {"type": t, "version": v or ""}
        cli["init"] = platform_map(a.install or "TODO: install command", a.install_win)
        if a.status:
            cli["status"] = platform_map(a.status)
            cli["statusMatch"] = a.status_match or "TODO"
        write(os.path.join(a.out, "cli.json"), cli)
    else:
        write(os.path.join(a.out, "mcp.json"), {"mcpServers": {a.source: {
            "type": "streamableHttp", "url": a.mcp_url or "https://TODO/mcp", "timeout": 30000}}})

    write(os.path.join(a.out, "icon.svg"), ICON)

    skill_dir = os.path.join(a.out, "skills", a.skill_name or a.source)
    if a.copy_skill and os.path.isfile(a.copy_skill):
        os.makedirs(skill_dir, exist_ok=True)
        shutil.copy(a.copy_skill, os.path.join(skill_dir, "SKILL.md"))
        print("  +", os.path.relpath(os.path.join(skill_dir, "SKILL.md")), "(copied; 需中文化并核对命令)")
    else:
        write(os.path.join(skill_dir, "SKILL.md"), SKILL_TPL.format(
            skill=a.skill_name or a.source, what=a.desc_zh.rstrip("。"), triggers=a.name_zh,
            entry=a.entry or a.source, name_zh=a.name_zh, requires=a.requires or "无额外依赖"))


def from_cli_anything(a):
    with open(a.from_cli_anything[0], encoding="utf-8") as f:
        reg = json.load(f)
    name = a.from_cli_anything[1]
    entry = next((c for c in reg.get("clis", []) if c.get("name") == name), None)
    if not entry:
        sys.exit(f"registry 中没有 {name!r}。可用: {', '.join(c['name'] for c in reg.get('clis', []))}")
    disp = entry.get("display_name") or name
    a.source = a.source or f"cli-anything-{name}"
    a.name_zh = a.name_zh or disp
    a.name_en = a.name_en or disp
    desc = (entry.get("description") or "")[:100]
    a.desc_en = a.desc_en or desc
    a.desc_zh = a.desc_zh or f"TODO 中文化：{desc}"
    a.type = "cli"
    a.install = a.install or entry.get("install_cmd") or "TODO"
    a.entry = entry.get("entry_point") or name
    a.status = a.status or f"{a.entry} --help"
    a.status_match = a.status_match or "Usage"
    a.runtime = a.runtime or "python:3.10"
    a.requires = entry.get("requires") or None
    a.skill_name = a.skill_name or name
    a.version = a.version or "0.1.0"
    if a.harness_root and entry.get("skill_md"):
        p = os.path.join(a.harness_root, entry["skill_md"])
        if os.path.isfile(p):
            a.copy_skill = p
    contributors = ", ".join(c.get("name", "?") for c in entry.get("contributors", []))
    print(f"registry: {name} v{entry.get('version')}  contributors: {contributors or '—'}")
    print("提醒: 核实 install_cmd 是否已发 PyPI（pip index versions cli-anything-%s）；署名 contributors。" % name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-cli-anything", nargs=2, metavar=("REGISTRY_JSON", "NAME"))
    ap.add_argument("--harness-root", help="CLI-Anything 仓库根，用于复制 harness 自带 SKILL.md")
    ap.add_argument("--type", choices=["cli", "mcp"])
    ap.add_argument("--source"); ap.add_argument("--name-zh"); ap.add_argument("--name-en")
    ap.add_argument("--desc-zh"); ap.add_argument("--desc-en")
    ap.add_argument("--version", default=None); ap.add_argument("--min-version")
    ap.add_argument("--install"); ap.add_argument("--install-win")
    ap.add_argument("--status"); ap.add_argument("--status-match")
    ap.add_argument("--runtime", help="如 python:3.10 / node:20")
    ap.add_argument("--mcp-url")
    ap.add_argument("--example-zh", action="append"); ap.add_argument("--example-en", action="append")
    ap.add_argument("--skill-name"); ap.add_argument("--entry"); ap.add_argument("--requires")
    ap.add_argument("--copy-skill")
    a = ap.parse_args()

    if a.from_cli_anything:
        from_cli_anything(a)
    else:
        missing = [k for k in ("type", "source", "name_zh", "name_en", "desc_zh", "desc_en") if not getattr(a, k)]
        if missing:
            sys.exit("手动模式缺少: " + ", ".join("--" + m.replace("_", "-") for m in missing))
        a.version = a.version or "0.1.0"

    os.makedirs(a.out, exist_ok=True)
    print(f"生成到 {a.out}/")
    build(a)
    print("\n下一步: 手改 TODO → python3 validate_connector.py", a.out)


if __name__ == "__main__":
    main()
