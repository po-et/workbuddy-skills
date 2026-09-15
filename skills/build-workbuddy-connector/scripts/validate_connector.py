#!/usr/bin/env python3
"""按 WorkBuddy 开放平台连接器规范校验一个连接器目录。

用法:  python3 validate_connector.py <connector-dir>
退出码: 0 = 无 FAIL；1 = 有 FAIL。WARN 不影响退出码。
规范来源: https://open.workbuddy.cn/docs/connector
"""
import json
import os
import re
import sys

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+")
PLATFORMS = ("darwin", "linux", "win32")
SECRET_PATTERNS = [
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"sk-[A-Za-z0-9]{20,}", "API key (sk-)"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY", "私钥"),
    (r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b", "私有 IP"),
    (r"\.(?:corp|internal|intranet)\.", "内网域名"),
]
JUNK = {".git", ".DS_Store", "__pycache__", "node_modules", ".venv"}

issues = []


def fail(msg): issues.append(("FAIL", msg))
def warn(msg): issues.append(("WARN", msg))
def ok(msg):   issues.append(("PASS", msg))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        fail(f"{os.path.basename(path)} 不是合法 JSON: {e}")
    except OSError:
        fail(f"缺少 {os.path.basename(path)}")
    return None


def check_meta(root):
    meta = load_json(os.path.join(root, "connector-meta.json"))
    if meta is None:
        return None
    for k in ("name", "name_zh", "name_en", "description", "description_zh",
              "description_en", "source", "type", "version", "examples_zh", "examples_en"):
        if k not in meta:
            fail(f"connector-meta.json 缺少必填字段 {k}")
    src = meta.get("source", "")
    if src and not KEBAB.match(src):
        fail(f"source 必须 kebab-case: {src!r}")
    if meta.get("type") not in ("cli", "mcp"):
        fail(f"type 必须为 cli 或 mcp: {meta.get('type')!r}")
    if meta.get("version") and not SEMVER.match(str(meta["version"])):
        fail(f"version 应为 semver: {meta['version']!r}")
    mv = meta.get("minWorkbuddyVersion")
    if mv is not None and not SEMVER.match(str(mv)):
        fail(f"minWorkbuddyVersion 应为 semver: {mv!r}")
    for k in ("examples_zh", "examples_en"):
        v = meta.get(k)
        if v is None:
            continue
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            fail(f"{k} 必须是字符串数组")
        elif not 2 <= len(v) <= 5:
            fail(f"{k} 需 2–5 条，当前 {len(v)}")
    for k in ("description", "description_zh", "description_en"):
        v = meta.get(k, "")
        if v and not 20 <= len(v) <= 100:
            warn(f"{k} 建议 20–100 字，当前 {len(v)}")
    ok("connector-meta.json 字段检查完成")
    return meta


def check_platform_map(obj, key, required):
    v = obj.get(key)
    if v is None:
        if required:
            fail(f"cli.json 缺少 {key}")
        return
    if not isinstance(v, dict):
        fail(f"cli.json {key} 必须是对象 {{darwin,linux,win32}}")
        return
    for p in PLATFORMS:
        if p not in v:
            (fail if required else warn)(f"cli.json {key} 缺少平台 {p}")
        elif not isinstance(v[p], str):
            fail(f"cli.json {key}.{p} 必须是单个字符串命令")


def check_cli(root):
    cli = load_json(os.path.join(root, "cli.json"))
    if cli is None:
        return
    check_platform_map(cli, "init", required=True)
    has_auth = "auth" in cli
    check_platform_map(cli, "auth", required=False)
    check_platform_map(cli, "unAuth", required=has_auth)
    check_platform_map(cli, "status", required=has_auth)
    sm, smj = "statusMatch" in cli, "statusMatchJson" in cli
    if "status" in cli and not (sm or smj):
        fail("有 status 时需 statusMatch 或 statusMatchJson 之一")
    if sm and smj:
        fail("statusMatch 与 statusMatchJson 只能二选一")
    if sm:
        try:
            re.compile(cli["statusMatch"])
        except re.error as e:
            fail(f"statusMatch 不是合法正则: {e}")
    rt = cli.get("runtime")
    if rt is not None:
        if not isinstance(rt, dict) or "type" not in rt or "version" not in rt:
            fail("runtime 必须是 {type, version} 对象")
    if has_auth and "authUrlDomain" not in cli:
        warn("有鉴权但未设置 authUrlDomain（官方建议设置以限制可提取域名）")
    ok("cli.json 结构检查完成")


def check_mcp(root):
    mcp = load_json(os.path.join(root, "mcp.json"))
    if mcp is None:
        return
    servers = mcp.get("mcpServers")
    if not isinstance(servers, dict) or len(servers) != 1:
        fail("mcp.json 的 mcpServers 必须且只能有一个 server")
        return
    name, srv = next(iter(servers.items()))
    t = srv.get("type")
    if t in ("sse", "streamableHttp"):
        url = srv.get("url", "")
        if not url:
            fail(f"远程 server {name} 缺少 url")
        elif not url.startswith("https://"):
            fail(f"远程 url 必须 HTTPS: {url}")
    elif t == "stdio":
        if "command" not in srv:
            fail(f"stdio server {name} 缺少 command")
    else:
        fail(f"server.type 必须为 sse / streamableHttp / stdio: {t!r}")
    raw = json.dumps(mcp)
    placeholders = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", raw))
    if placeholders:
        ts = load_json(os.path.join(root, "token-schema.json"))
        if ts:
            keys = {f.get("key") for f in ts.get("fields", []) if isinstance(f, dict)}
            for p in placeholders - keys:
                fail(f"mcp.json 占位符 ${{{p}}} 在 token-schema.json fields 中无对应 key")
            for f in ts.get("fields", []):
                if isinstance(f, dict) and re.search(r"token|secret|password|key", f.get("key", ""), re.I) \
                        and f.get("type") != "password":
                    warn(f"token-schema 字段 {f.get('key')} 疑似敏感但 type 不是 password")
    ok("mcp.json 结构检查完成")


def check_icon(root):
    for n in ("icon.svg", "icon.png", "icon.jpg"):
        if os.path.exists(os.path.join(root, n)):
            ok(f"图标 {n} 存在")
            return
    fail("缺少 icon.svg / icon.png / icon.jpg")


def check_skills(root, ctype):
    sk = os.path.join(root, "skills")
    if not os.path.isdir(sk):
        (warn if ctype == "cli" else ok)("无 skills/ 目录" + ("（CLI 连接器强烈建议提供）" if ctype == "cli" else ""))
        return
    found = 0
    for d in sorted(os.listdir(sk)):
        p = os.path.join(sk, d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        found += 1
        with open(p, encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("---"):
            fail(f"skills/{d}/SKILL.md 缺少 frontmatter")
            continue
        fm = content.split("---", 2)[1]
        name = re.search(r"^name:\s*(.+)$", fm, re.M)
        desc = re.search(r"^description:\s*(.+)$", fm, re.M | re.S)
        if not name:
            fail(f"skills/{d}/SKILL.md 缺少 name")
        elif name.group(1).strip().strip("\"'") != d:
            warn(f"skills/{d}/SKILL.md 的 name 与目录名不一致")
        if not desc:
            fail(f"skills/{d}/SKILL.md 缺少 description")
        else:
            dl = len(desc.group(1).split("\n---")[0])
            if dl > 1024:
                fail(f"skills/{d}/SKILL.md description 超过 1024 字符 ({dl})")
    (ok if found else warn)(f"skills/ 下找到 {found} 个 SKILL.md")


def check_junk_and_secrets(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for j in list(dirnames):
            if j in JUNK:
                fail(f"不应包含 {os.path.relpath(os.path.join(dirpath, j), root)}")
                dirnames.remove(j)
        for fn in filenames:
            if fn in JUNK:
                fail(f"不应包含 {os.path.relpath(os.path.join(dirpath, fn), root)}")
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            for pat, label in SECRET_PATTERNS:
                if re.search(pat, text):
                    fail(f"{os.path.relpath(p, root)} 疑似含 {label}")
    ok("垃圾文件与凭证扫描完成")


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    root = os.path.abspath(sys.argv[1])
    meta = check_meta(root)
    ctype = (meta or {}).get("type")
    if ctype == "cli":
        check_cli(root)
        if os.path.exists(os.path.join(root, "mcp.json")):
            warn("type=cli 但存在 mcp.json")
    elif ctype == "mcp":
        check_mcp(root)
        if os.path.exists(os.path.join(root, "cli.json")):
            warn("type=mcp 但存在 cli.json")
    check_icon(root)
    check_skills(root, ctype)
    check_junk_and_secrets(root)

    counts = {"FAIL": 0, "WARN": 0, "PASS": 0}
    for level, msg in issues:
        counts[level] += 1
        print(f"[{level}] {msg}")
    print(f"\n{os.path.basename(root)}: {counts['FAIL']} FAIL / {counts['WARN']} WARN / {counts['PASS']} PASS")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
