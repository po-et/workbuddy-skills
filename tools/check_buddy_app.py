#!/usr/bin/env python3
"""校验 Buddy 应用配置包（buddy-apps/<name>/config.json + assets/）。

Buddy 应用是网页表单配置而非上传包，官方导出 JSON 结构未公开；这里校验的是我们自己的
config.json 约定，以及官方设计规范里写明的图片尺寸：
  头像 256×256；精选场景底图 1000×910；模式图标 16×16 SVG（线宽 1.2）。
用法：python3 tools/check_buddy_app.py buddy-apps/devops-buddy
退出码：有 FAIL 为 1，否则 0。
"""
import json
import re
import struct
import sys
from pathlib import Path

ASSET_ID = re.compile(r"^o[secd]_[0-9a-f]{16}$")
MODE_MIN, MODE_MAX = 2, 5          # 文档建议 2–4，表单上限待实测，放宽到 5
CAPSULE_MIN = 3
PROMPT_MIN = 150                   # system prompt 最少字数（字符）


def png_size(p: Path):
    with p.open("rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", head[16:24])


class Report:
    def __init__(self):
        self.fails, self.warns = [], []

    def fail(self, m):
        self.fails.append(m)

    def warn(self, m):
        self.warns.append(m)

    def done(self, title):
        for m in self.fails:
            print(f"  FAIL  {m}")
        for m in self.warns:
            print(f"  WARN  {m}")
        status = "FAIL" if self.fails else ("WARN" if self.warns else "PASS")
        print(f"{status}  {title}  ({len(self.fails)} fail, {len(self.warns)} warn)")
        return not self.fails


def check_ids(r, ids, where, prefix):
    for i in ids:
        if not ASSET_ID.match(i):
            r.fail(f"{where}: 资产 ID 格式不对 {i!r}")
        elif not i.startswith(prefix):
            r.fail(f"{where}: {i} 不是 {prefix}* 类型")


def check(root: Path) -> bool:
    r = Report()
    cfg_path = root / "config.json"
    if not cfg_path.exists():
        r.fail("缺 config.json")
        return r.done(str(root))
    try:
        cfg = json.loads(cfg_path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        r.fail(f"config.json 不是合法 JSON: {e}")
        return r.done(str(root))

    app = cfg.get("app", {})
    for k in ("name_zh", "name_en", "slogan_zh", "description_zh", "description_en", "avatar"):
        if not app.get(k):
            r.fail(f"app.{k} 为空")
    if len(app.get("name_zh", "")) > 20:
        r.warn("app.name_zh 超过 20 字，表单可能截断（限制待实测）")
    if len(app.get("slogan_zh", "")) > 30:
        r.warn("app.slogan_zh 超过 30 字，首页标题可能折行")
    dz = app.get("description_zh", "")
    if not 40 <= len(dz) <= 300:
        r.warn(f"app.description_zh 长度 {len(dz)}，建议 40–300")

    home = cfg.get("home", {})
    modes = home.get("modes", [])
    if not MODE_MIN <= len(modes) <= MODE_MAX:
        r.fail(f"工作模式 {len(modes)} 个，应在 {MODE_MIN}–{MODE_MAX}（文档建议 2–4）")
    seen = set()
    for m in modes:
        mid = m.get("id", "?")
        if mid in seen:
            r.fail(f"模式 id 重复: {mid}")
        seen.add(mid)
        for k in ("name_zh", "name_en", "icon", "system_prompt"):
            if not m.get(k):
                r.fail(f"模式 {mid}: 缺 {k}")
        sp = m.get("system_prompt", "")
        if len(sp) < PROMPT_MIN:
            r.fail(f"模式 {mid}: system_prompt 仅 {len(sp)} 字，少于 {PROMPT_MIN}")
        if "禁止" not in sp and "红线" not in sp:
            r.warn(f"模式 {mid}: system prompt 没有禁止/红线段落（与专家包的输出契约风格不一致）")
        icon = root / m.get("icon", "")
        if not icon.exists():
            r.fail(f"模式 {mid}: 图标不存在 {m.get('icon')}")
        elif icon.suffix == ".svg":
            s = icon.read_text("utf-8")
            if 'viewBox="0 0 16 16"' not in s:
                r.warn(f"模式 {mid}: 图标 viewBox 不是 0 0 16 16")
            if 'stroke-width="1.2"' not in s:
                r.warn(f"模式 {mid}: 图标线宽不是 1.2")
        check_ids(r, m.get("skills", []), f"模式 {mid}.skills", "os_")
        check_ids(r, m.get("experts", []), f"模式 {mid}.experts", "oe_")
        check_ids(r, m.get("connectors", []), f"模式 {mid}.connectors", "oc_")
        if not (m.get("skills") or m.get("experts") or m.get("connectors")):
            r.warn(f"模式 {mid}: 没有绑定任何资产")

    caps = home.get("capsules", [])
    if len(caps) < CAPSULE_MIN:
        r.fail(f"场景胶囊 {len(caps)} 个，少于 {CAPSULE_MIN}")
    for c in caps:
        t = c.get("title", "")
        if not t:
            r.fail("胶囊缺 title")
        elif len(t) > 8:
            r.warn(f"胶囊「{t}」超过 8 字，首页胶囊栏可能显示不全")
        if len(c.get("prompt", "")) < 20:
            r.fail(f"胶囊「{t}」预置指令太短")
        b = c.get("bind", {})
        prefix = {"skill": "os_", "expert": "oe_", "connector": "oc_"}.get(b.get("type"))
        if not prefix:
            r.fail(f"胶囊「{t}」bind.type 不合法: {b.get('type')!r}")
        else:
            check_ids(r, [b.get("id", "")], f"胶囊「{t}」", prefix)
    for k in ("placeholder_zh", "placeholder_en"):
        if not home.get(k):
            r.warn(f"home.{k} 为空")

    market = cfg.get("market", {})
    check_ids(r, market.get("experts", []), "market.experts", "oe_")
    check_ids(r, market.get("skills", []), "market.skills", "os_")
    check_ids(r, market.get("connectors", []), "market.connectors", "oc_")
    listed = set(market.get("experts", []) + market.get("skills", []) + market.get("connectors", []))
    for m in modes:
        for i in m.get("skills", []) + m.get("experts", []) + m.get("connectors", []):
            if i not in listed:
                r.warn(f"模式 {m.get('id')} 绑定了 {i}，但市场配置里没有列出")
    for sc in market.get("featured_scenes", []):
        for key in ("bg_day", "bg_night"):
            p = root / sc.get(key, "")
            if not p.exists():
                r.fail(f"精选场景「{sc.get('title')}」缺 {key}")
            else:
                sz = png_size(p)
                if sz != (1000, 910):
                    r.fail(f"精选场景「{sc.get('title')}」{key} 尺寸 {sz}，应为 1000×910")
        check_ids(r, sc.get("experts", []), f"精选场景「{sc.get('title')}」", "oe_")

    av = root / app.get("avatar", "")
    if not av.exists():
        r.fail("头像文件不存在")
    else:
        sz = png_size(av)
        if sz != (256, 256):
            r.fail(f"头像尺寸 {sz}，应为 256×256")
        if av.stat().st_size > 500 * 1024:
            r.warn("头像超过 500KB")
    return r.done(str(root))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    ok = all(check(Path(p)) for p in sys.argv[1:])
    sys.exit(0 if ok else 1)
