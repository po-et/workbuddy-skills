#!/usr/bin/env python3
"""WorkBuddy 开放平台提交前校验：技能 / 专家 / 连接器 三种包，目录或 .zip 均可。

规则来源：官方文档（/docs/skill、/docs/expert、/docs/connector）+ 2026-09-15/16 五个包上传实测
（解析器报错原文见 docs/platform-notes.md）。文档没写但解析器强制的规则单独标注。

用法:  python3 tools/check_package.py <dir-or-zip> [--type skill|expert|connector]
退出码: 0 无 FAIL；1 有 FAIL。WARN 不影响退出码。
"""
import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
JUNK = {".git", ".DS_Store", "__pycache__", "node_modules", ".venv", "__MACOSX"}
SECRETS = [(r"ghp_[A-Za-z0-9]{20,}", "GitHub token"), (r"sk-[A-Za-z0-9]{20,}", "API key"),
           (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"), (r"AKIA[0-9A-Z]{16}", "AWS key"),
           (r"-----BEGIN [A-Z ]*PRIVATE KEY", "私钥"),
           (r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b", "私有 IP"),
           (r"\.(?:corp|internal|intranet)\.", "内网域名")]
CATEGORY_IDS = {"01-ProductDesign", "02-Engineering", "03-GameSpatial", "04-DataAI", "05-MarketingGrowth",
                "06-ContentCreative", "07-SalesCommerce", "08-FinanceInvestment", "09-OperationsHR",
                "10-ProjectQuality", "11-SecurityCompliance", "12-IndustryConsultant", "13-TencentZone",
                "14-WorldWise", "15-Education"}
SKILL_ZIP_MAX, CONNECTOR_ZIP_MAX, AVATAR_MAX = 3 * 1024 * 1024, 20 * 1024 * 1024, 500 * 1024

issues = []
def fail(m): issues.append(("FAIL", m))
def warn(m): issues.append(("WARN", m))
def ok(m):   issues.append(("PASS", m))


# ---------------------------------------------------------------- 工具

def parse_frontmatter(text):
    """YAML 子集：标量 / 引号标量 / 嵌套映射 / '- ' 列表。够用即可，复杂 YAML 请装 pyyaml。"""
    if not text.startswith("---"):
        return None
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return None
    body = parts[0][3:].lstrip("\n")
    try:
        import yaml  # noqa: PLC0415
        return yaml.safe_load(body) or {}
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        fail(f"frontmatter 不是合法 YAML: {e}"); return {}
    root = {}; stack = [[-1, root, None]]
    lines = [l for l in body.split("\n") if l.strip() and not l.lstrip().startswith("#")]
    for i, raw in enumerate(lines):
        indent = len(raw) - len(raw.lstrip()); s = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        node, last = stack[-1][1], stack[-1][2]
        if s.startswith("- "):
            if isinstance(node, list):
                node.append(_scalar(s[2:]))
            continue
        if s.startswith("{") or s.startswith("[") or s.startswith("}"):   # 内联 JSON 块（metadata）跳过
            continue
        if ":" not in s:
            continue
        k, _, v = s.partition(":"); k, v = k.strip(), v.strip()
        if v == "":
            # 向前看一行决定是列表还是映射
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            child = [] if nxt.startswith("- ") else {}
            if isinstance(node, dict):
                node[k] = child
            stack[-1][2] = k; stack.append([indent, child, None])
        else:
            if isinstance(node, dict):
                node[k] = _scalar(v)
            stack[-1][2] = k
    return root


def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1].replace('\\"', '"')
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def image_dims(path):
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", head[16:24]); return "png", w, h
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return "jpg", None, None
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    f.read(3); h, w = struct.unpack(">HH", f.read(4)); return "jpg", w, h
                (seg,) = struct.unpack(">H", f.read(2)); f.seek(seg - 2, 1)
    return None, None, None


def scan_junk_secrets(root):
    for dp, dns, fns in os.walk(root):
        for j in list(dns):
            if j in JUNK:
                fail(f"不应包含 {os.path.relpath(os.path.join(dp, j), root)}"); dns.remove(j)
        for fn in fns:
            if fn in JUNK or fn.endswith(".pyc"):
                fail(f"不应包含 {os.path.relpath(os.path.join(dp, fn), root)}"); continue
            p = os.path.join(dp, fn)
            try:
                txt = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for pat, label in SECRETS:
                if re.search(pat, txt):
                    fail(f"{os.path.relpath(p, root)} 疑似含 {label}")


# ---------------------------------------------------------------- 技能

def check_skill(root):
    p = os.path.join(root, "SKILL.md")
    if not os.path.isfile(p):
        fail("缺少 SKILL.md"); return
    fm = parse_frontmatter(open(p, encoding="utf-8").read())
    if fm is None:
        fail("SKILL.md 缺少 frontmatter（须以 --- 开头）"); return
    # 官方文档必填
    for k in ("description", "version", "description_zh", "description_en"):
        if not fm.get(k):
            fail(f"缺少 {k}（官方文档必填，解析器强制）")
    if not fm.get("author"):
        warn("缺少 author（官方文档必填；实测解析器未强制，建议填开发者昵称）")
    # 文档未写、解析器强制
    for k in ("display_name", "display_name_en"):
        if not fm.get(k):
            fail(f"缺少 {k}（文档未记载，但平台解析器强制：「缺少 Skill 中/英文展示名」）")
    name = fm.get("name")
    if name and name != os.path.basename(root.rstrip("/")):
        warn(f"name={name!r} 与目录名 {os.path.basename(root)!r} 不一致")
    if name and not KEBAB.match(str(name)):
        fail(f"name 须小写字母数字加连字符: {name!r}")
    v = str(fm.get("version", ""))
    if v and not SEMVER.match(v):
        fail(f"version 应为 x.y.z: {v!r}")
    d = str(fm.get("description", ""))
    if len(d) > 1024:
        fail(f"description 超过 1024 字符 ({len(d)})")
    for k in ("examples_zh", "examples_en"):
        ex = fm.get(k)
        if ex is None:
            warn(f"未提供 {k}（可选；会显示为「试试这样问我」，建议 3 条）")
        elif not isinstance(ex, list):
            fail(f"{k} 必须是字符串数组")
        elif len(ex) > 3:
            fail(f"{k} 最多 3 条，当前 {len(ex)}（解析器原文：最多 3 个示例）")
    ok("SKILL.md frontmatter 检查完成")
    warn("提醒：同名技能已存在于平台时须走草稿「编辑」重传，且 version 必须大于线上/草稿版本")


# ---------------------------------------------------------------- 专家

def _bilingual(obj, key, required=True):
    v = obj.get(key)
    if v is None:
        (fail if required else warn)(f"plugin.json 缺少 {key}"); return None
    if not isinstance(v, dict) or not v.get("en") or not v.get("zh"):
        fail(f"plugin.json {key} 必须是 {{en, zh}} 且两者非空"); return None
    return v


def check_expert(root):
    mp = None
    for d in (".codebuddy-plugin", ".workbuddy-plugin", ".claude-plugin"):
        cand = os.path.join(root, d, "plugin.json")
        if os.path.isfile(cand):
            mp = cand; break
    if not mp:
        fail("缺少 .codebuddy-plugin/plugin.json"); return
    try:
        pj = json.load(open(mp, encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"plugin.json 不是合法 JSON: {e}"); return

    for k in ("name", "version", "description", "author", "agents", "expertType"):
        if k not in pj:
            fail(f"plugin.json 缺少必填 {k}")
    n = pj.get("name", "")
    if n and not KEBAB.match(n):
        fail(f"name 须小写字母加连字符: {n!r}")
    if pj.get("version") and not SEMVER.match(str(pj["version"])):
        fail(f"version 应为语义化版本: {pj['version']!r}")
    if pj.get("expertType") not in ("agent", "team"):
        fail(f"expertType 必须为 agent 或 team: {pj.get('expertType')!r}")
    au = pj.get("author")
    if not isinstance(au, dict) or not au.get("name"):
        fail("author 必须是含 name 的对象")

    _bilingual(pj, "displayName"); _bilingual(pj, "profession")
    dd = _bilingual(pj, "displayDescription")
    if dd:
        zl = len(dd["zh"])
        if not 40 <= zl <= 50:
            fail(f"displayDescription.zh 须 40–50 字，当前 {zl}")
    if pj.get("categoryId") not in CATEGORY_IDS:
        fail(f"categoryId 不在 15 个预设值内: {pj.get('categoryId')!r}")
    tags = pj.get("tags")
    if not isinstance(tags, list) or len(tags) != 3:
        fail(f"tags 必须恰好 3 个，当前 {len(tags) if isinstance(tags, list) else '非数组'}")
    else:
        for t in tags:
            if not isinstance(t, dict) or not t.get("en") or not t.get("zh"):
                fail("每个 tag 必须是 {en, zh}")
    qp = pj.get("quickPrompts")
    if not isinstance(qp, list) or len(qp) != 3:
        fail(f"quickPrompts 必须恰好 3 条，当前 {len(qp) if isinstance(qp, list) else '非数组'}")
    else:
        for q in qp:
            if not isinstance(q, dict) or not q.get("en") or not q.get("zh"):
                fail("每条 quickPrompt 必须是 {en, zh}")
        dip = pj.get("defaultInitPrompt")
        if not dip:
            warn("缺少 defaultInitPrompt（模板中存在，且 quickPrompts[0] 应与之一致）")
        elif isinstance(dip, dict) and (dip.get("zh") != qp[0].get("zh") or dip.get("en") != qp[0].get("en")):
            warn("quickPrompts[0] 与 defaultInitPrompt 不一致（文档要求一致）")

    av = pj.get("avatar")
    if not av:
        fail("缺少 avatar")
    else:
        ap = os.path.join(root, av)
        if not os.path.isfile(ap):
            fail(f"avatar 文件不存在: {av}")
        else:
            size = os.path.getsize(ap)
            if size > AVATAR_MAX:
                fail(f"avatar 超过 500KB ({size // 1024}KB)")
            kind, w, h = image_dims(ap)
            if kind not in ("png", "jpg"):
                fail("avatar 须为 PNG/JPG")
            elif w and (w != 512 or h != 512):
                fail(f"avatar 须 512×512，当前 {w}×{h}")

    agents = pj.get("agents") or []
    names = set()
    if not isinstance(agents, list) or not agents:
        fail("agents 必须是非空数组")
    else:
        for rel in agents:
            p = os.path.join(root, rel)
            if not os.path.isfile(p):
                fail(f"agent 文件不存在: {rel}"); continue
            fm = parse_frontmatter(open(p, encoding="utf-8").read())
            if fm is None:
                fail(f"{rel} 缺少 frontmatter"); continue
            for k in ("name", "description"):
                if not fm.get(k):
                    fail(f"{rel} frontmatter 缺少 {k}")
            for k in ("displayName", "profession"):
                v = fm.get(k)
                if not isinstance(v, dict) or not v.get("en") or not v.get("zh"):
                    fail(f"{rel} frontmatter {k} 必须是 en/zh 两项")
            if fm.get("name"):
                names.add(fm["name"])
            body = open(p, encoding="utf-8").read().split("\n---", 1)[-1].strip()
            if len(body) < 200:
                warn(f"{rel} 系统提示正文过短 ({len(body)} 字符)，质量检测可能不过")
    if pj.get("expertType") == "agent":
        an = pj.get("agentName")
        if not an:
            fail("expertType=agent 时须有 agentName")
        elif names and an not in names:
            fail(f"agentName={an!r} 不在 agents 的 name 集合中 {sorted(names)}")
    if pj.get("expertType") == "team":
        ti = pj.get("teamInfo") or {}
        lead, mem = ti.get("leadAgent"), ti.get("memberAgents") or []
        if not lead:
            fail("expertType=team 时须有 teamInfo.leadAgent")
        elif names and lead not in names:
            fail(f"leadAgent={lead!r} 不在 agents 的 name 集合中")
        if not mem:
            fail("teamInfo.memberAgents 不能为空")
        for m in mem:
            if names and m not in names:
                fail(f"memberAgent={m!r} 不在 agents 的 name 集合中")
        if not pj.get("agentName"):
            fail("expertType=team 时须有 agentName（主理人 agent 名）")
        elif lead and pj["agentName"] != lead:
            warn("agentName 与 teamInfo.leadAgent 不一致")
        # 解析器要求的 members 数组（/docs/expert-team）：Go 结构 upload.teamMemberJSON
        members = pj.get("members")
        if not isinstance(members, list) or not members:
            fail("members 为必填数组（解析器原文：members 为必填数组；元素为对象，字符串会报 cannot unmarshal）")
        else:
            leads = 0
            for i, m in enumerate(members):
                if not isinstance(m, dict):
                    fail(f"members[{i}] 必须是对象 {{id,name,profession,avatar,role}}"); continue
                for k in ("id", "name", "profession", "avatar", "role"):
                    if k not in m:
                        fail(f"members[{i}] 缺少 {k}")
                for k in ("name", "profession"):
                    v = m.get(k)
                    if not isinstance(v, dict) or not v.get("en") or not v.get("zh"):
                        fail(f"members[{i}].{k} 必须是 {{en, zh}}")
                if m.get("role") not in ("lead", "member"):
                    fail(f"members[{i}].role 须为 lead 或 member: {m.get('role')!r}")
                leads += m.get("role") == "lead"
                if names and m.get("id") not in names:
                    fail(f"members[{i}].id={m.get('id')!r} 不在 agents 的 name 集合中（id = agent 文件名去 .md）")
                av2 = m.get("avatar")
                if av2 and not os.path.isfile(os.path.join(root, av2)):
                    fail(f"members[{i}].avatar 文件不存在: {av2}")
            if leads != 1:
                fail(f"members 中 role=lead 须恰好 1 个，当前 {leads}")
        # 主理人文件名须含专家团前缀，且不可用通用 team-lead（/docs/expert-team）
        if lead:
            if lead == "team-lead":
                fail("主理人不可用通用名 team-lead")
            elif n and not lead.startswith(n.split("-")[0]):
                warn(f"主理人 {lead!r} 建议以专家团前缀开头（文档：名称须加专家团前缀）")
    ok("专家 plugin.json 与 agents 检查完成")


# ---------------------------------------------------------------- 连接器（复用现有校验器）

def check_connector(root):
    here = os.path.dirname(os.path.abspath(__file__))
    vc = os.path.join(here, "..", "skills", "build-workbuddy-connector", "scripts", "validate_connector.py")
    if not os.path.isfile(vc):
        fail("找不到 validate_connector.py"); return
    r = subprocess.run([sys.executable, vc, root], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        for lv in ("FAIL", "WARN", "PASS"):
            if line.startswith(f"[{lv}]"):
                issues.append((lv, line[len(lv) + 3:]))


# ---------------------------------------------------------------- 入口

def detect(root):
    if os.path.isfile(os.path.join(root, "connector-meta.json")):
        return "connector"
    for d in (".codebuddy-plugin", ".workbuddy-plugin", ".claude-plugin"):
        p = os.path.join(root, d, "plugin.json")
        if os.path.isfile(p):
            try:
                if "expertType" in json.load(open(p, encoding="utf-8")):
                    return "expert"
            except Exception:  # noqa: BLE001
                pass
    if os.path.isfile(os.path.join(root, "SKILL.md")):
        return "skill"
    return None


def unwrap(root):
    """zip 常见布局：顶层只有一个目录时进入该目录。"""
    entries = [e for e in os.listdir(root) if e not in JUNK]
    if len(entries) == 1 and os.path.isdir(os.path.join(root, entries[0])):
        return os.path.join(root, entries[0])
    return root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path"); ap.add_argument("--type", choices=["skill", "expert", "connector"])
    a = ap.parse_args()
    path = os.path.abspath(a.path)
    tmp = None
    if path.endswith(".zip"):
        size = os.path.getsize(path)
        tmp = tempfile.mkdtemp(prefix="wbcheck_")
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        root = unwrap(tmp)
    else:
        root, size = path, None
    kind = a.type or detect(root)
    if not kind:
        sys.exit("无法识别包类型：需有 SKILL.md（技能）/ .codebuddy-plugin/plugin.json 含 expertType（专家）/ connector-meta.json（连接器）")
    if size is not None:
        limit = CONNECTOR_ZIP_MAX if kind == "connector" else SKILL_ZIP_MAX
        (fail if size > limit else ok)(f"zip {size // 1024}KB（上限 {limit // 1024 // 1024}MB）")
    {"skill": check_skill, "expert": check_expert, "connector": check_connector}[kind](root)
    if kind != "connector":
        scan_junk_secrets(root)
        for lic in ("LICENSE", "LICENSE.txt"):
            if kind == "skill" and os.path.exists(os.path.join(root, lic)):
                warn(f"技能包内含 {lic}（SkillHub 规则不建议放入技能包）")
    counts = {"FAIL": 0, "WARN": 0, "PASS": 0}
    for lv, msg in issues:
        counts[lv] += 1; print(f"[{lv}] {msg}")
    print(f"\n{kind} · {os.path.basename(path)}: {counts['FAIL']} FAIL / {counts['WARN']} WARN / {counts['PASS']} PASS")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
