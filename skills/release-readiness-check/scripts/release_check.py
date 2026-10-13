#!/usr/bin/env python3
"""发布前静态证据报告：五类检查聚合；不作上线批准。

用法:
  python3 scripts/release_check.py [目标目录] [--out 报告路径] [--json] [--strict]
                                   [--skip env --skip-reason 'env=单独评审'] [--openapi-base 旧规范]

- 自动发现目标目录里的 Dockerfile*、含 kind: 的 K8s YAML、*.sql、openapi*.json/yaml、.env*；
- 逐项用子进程调用 scripts/checks/ 下的独立脚本（--json），失败不影响其他项；
- 报告默认写到新建系统临时目录；--out 拒绝覆盖任何已有路径。
- high 或证据缺口令 --strict 返回 1；干净的静态结果也不是上线批准。
- 记录有界 SHA-256 收据，检查前后变化及缺哈希均显式标记。
纯 Python 标准库，不联网、不执行构建、不连集群、不连数据库。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS_DIR = os.path.join(HERE, "checks")
SEVS = ("high", "warn", "info")
SEV_ORDER = {"high": 0, "warn": 1, "info": 2}
TOP_N = 10
MAX_SNIFF = 2 * 1024 * 1024  # 超过 2MB 的 YAML 不做内容嗅探
MAX_RECEIPTS = 128
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
CHECK_SCRIPTS = {"dockerfile": "dockerfile_check.py", "k8s": "k8s_check.py",
                 "sql": "sql_migration_check.py", "openapi": "openapi_diff.py",
                 "env": "env_sync_check.py"}
# 与内置 env_sync_check.scan_src 的路径选择一致，仅用于证据收据，不读取内容。
ENV_SOURCE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".go", ".java", ".kt",
                  ".rb", ".php", ".rs", ".sh", ".bash", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".env"}
ENV_SKIP_DIRS = {".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "__pycache__", ".next", "target"}

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "vendor", ".venv", "venv", "__pycache__",
             "dist", "build", "target", ".idea", ".vscode", ".tox", ".mypy_cache",
             ".pytest_cache", "site-packages", ".next", ".terraform"}

ITEM_TITLES = {
    "dockerfile": ("Dockerfile 体检", "dockerfile-check"),
    "k8s": ("K8s 清单体检", "k8s-manifest-check"),
    "sql": ("SQL 迁移风险", "sql-migration-check"),
    "openapi": ("OpenAPI 破坏性变更", "openapi-breaking-diff"),
    "env": (".env 一致性", "env-sync-check"),
}
ITEM_ORDER = ["dockerfile", "k8s", "sql", "openapi", "env"]
SKIP_ALIASES = {"docker": "dockerfile", "dockerfile": "dockerfile", "df": "dockerfile",
                "k8s": "k8s", "kubernetes": "k8s", "manifest": "k8s",
                "sql": "sql", "migration": "sql", "migrations": "sql",
                "openapi": "openapi", "api": "openapi", "swagger": "openapi",
                "env": "env", "dotenv": "env"}

OPENAPI_NAME = re.compile(r"^(openapi|swagger)[\w.\-]*\.(json|ya?ml)$", re.I)
KIND_LINE = re.compile(r"^\s{0,4}kind:\s*\S", re.M)
APIVERSION_LINE = re.compile(r"^\s{0,4}apiVersion:\s*\S", re.M)
OPENAPI_MARK = re.compile(r"^\s*[\"']?(openapi|swagger)[\"']?\s*:\s*[\"']?[23]", re.M)

OPENAPI_FIX = "破坏性变更走新版本路径（如 /v2）或新增字段并保留旧字段过渡，同时在变更日志里逐条列出并通知调用方"


# ---------------------------------------------------------------- 发现

def read_head(path, limit=MAX_SNIFF):
    try:
        if os.path.getsize(path) > limit:
            return ""
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def discover(root):
    """走一遍目标目录，按类型归类文件。返回相对 root 的路径列表。"""
    found = {k: [] for k in ITEM_ORDER}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            low = fn.lower()
            if fn == "Dockerfile" or fn.startswith("Dockerfile.") or low.endswith(".dockerfile"):
                found["dockerfile"].append(rel)
                continue
            if low.endswith(".sql"):
                found["sql"].append(rel)
                continue
            if OPENAPI_NAME.match(fn):
                found["openapi"].append(rel)
                continue
            if low.endswith((".yaml", ".yml", ".json")):
                text = read_head(full)
                if OPENAPI_MARK.search(text):
                    found["openapi"].append(rel)
                elif low.endswith((".yaml", ".yml")) and KIND_LINE.search(text) and APIVERSION_LINE.search(text):
                    found["k8s"].append(rel)
    # .env 只看目标目录根部，env_sync_check.py 本身按 --src 目录找示例与环境文件
    try:
        found["env"] = sorted(f for f in os.listdir(root)
                              if f.startswith(".env") and os.path.isfile(os.path.join(root, f)))
    except OSError:
        found["env"] = []
    return found


# ---------------------------------------------------------------- 子进程

def run_check(script, args, cwd):
    """调用 checks/<script>，返回 (数据, 错误说明)。"""
    path = os.path.join(CHECKS_DIR, script)
    if not os.path.isfile(path):
        return None, f"缺少检查脚本 {script}（技能包不完整）"
    cmd = [sys.executable, path] + list(args) + ["--json"]
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None, f"{script} 执行超过 180 秒，已放弃"
    except OSError as e:
        return None, f"{script} 无法执行：{e}"
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip().splitlines()
    tail = f"：{err[-1]}" if err else ""
    # 调用子脚本时不传 --strict，子脚本正常「发现问题」也是退出码 0；
    # 非 0 只可能是崩溃 / 文件读不出来 / 参数不对 —— 这是「拿不到证据」，不是「通过」。
    if p.returncode != 0:
        return None, f"{script} 以退出码 {p.returncode} 结束（崩溃或文件解析失败，不是「发现问题」）{tail}"
    if not out:
        return None, f"{script} 没有输出（退出码 {p.returncode}）{tail}"
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        return None, f"{script} 输出不是合法 JSON（退出码 {p.returncode}）{tail}"


def finding(sev, code, where, message, fix=""):
    return {"severity": sev if sev in SEVS else "info", "code": str(code or ""),
            "where": where or "", "message": message or "", "fix": fix or ""}


# ---------------------------------------------------------------- 规范校验

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def load_spec(path):
    """读一份 OpenAPI 规范，返回 (文档, 错误说明)。"""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        return None, f"读不出来（{e.strerror or e}）"
    except UnicodeDecodeError:
        return None, "不是 UTF-8 文本"
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml  # noqa: PLC0415
        except ImportError:
            return None, "YAML 规范需要 PyYAML（pip install pyyaml），或先转成 JSON"
        try:
            return yaml.safe_load(text), None
        except Exception as e:  # noqa: BLE001  PyYAML 的异常类型不统一
            return None, f"YAML 解析失败：{str(e).splitlines()[0]}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败：{e}"


def validate_spec(path):
    """能不能拿来比对：必须解析成对象、含 openapi/swagger 版本字段、paths 非空且至少有一个接口。
    不合格返回原因字符串（调用方据此标「无法判断」），合格返回 None。"""
    doc, err = load_spec(path)
    if err:
        return err
    if not isinstance(doc, dict):
        return f"顶层不是对象（解析出 {type(doc).__name__}）"
    if not (doc.get("openapi") or doc.get("swagger")):
        return "缺少 openapi / swagger 版本字段，不像一份 OpenAPI 规范"
    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        return "没有非空的 paths，规范里没有任何接口可比对"
    ops = 0
    for item in paths.values():
        if not isinstance(item, dict):
            continue
        ops += 1 if "$ref" in item else sum(1 for m in HTTP_METHODS if m in item)
    if not ops:
        return "paths 里没有任何 HTTP 方法（get/post/…），没有接口可比对"
    return None


# ---------------------------------------------------------------- 五项检查
# 每个检查返回 (findings, 执行错误, 证据缺口, 备注)；证据缺口 = (代码, 原因)，表示「无法判断」。

def check_dockerfile(root, files):
    data, err = run_check("dockerfile_check.py", files, root)
    if err:
        return [], err, None, []
    out, parsed, blank = [], 0, []
    for r in data or []:
        n = int(r.get("instructions") or 0)
        parsed += n
        if not n:
            blank.append(str(r.get("file", "?")))
        for f in r.get("findings", []):
            line = f.get("line") or 0
            where = f"{r.get('file', '?')}:L{line}" if line else str(r.get("file", "?"))
            out.append(finding(f.get("severity"), f.get("rule"), where, f.get("message"), f.get("fix")))
    if not parsed:
        return out, None, ("empty-input", f"{len(files)} 个 Dockerfile 一条指令都没解析出来"
                           f"（{', '.join(blank[:3]) or '，'.join(files[:3])}），等于没查"), []
    notes = [f"{len(blank)} 个 Dockerfile 没有解析出指令，这部分没被检查：{', '.join(blank[:5])}"] if blank else []
    return out, None, None, notes


def check_k8s(root, files):
    data, err = run_check("k8s_check.py", files, root)
    if err:
        return [], err, None, []
    data = data or {}
    out = []
    for f in data.get("findings", []):
        where = " ".join(x for x in (f.get("file"), f.get("object")) if x and x != "-")
        out.append(finding(f.get("severity"), f.get("rule"), where, f.get("message"), f.get("fix")))
    objects = int(data.get("objects") or 0)
    tmpl = sorted({f.get("file") for f in data.get("findings", []) if f.get("rule") == "K000"} - {None})
    if not objects:
        why = f"{len(files)} 个 YAML 一个对象都没解析出来，等于没查"
        if tmpl:
            why += f"；其中 {len(tmpl)} 个是 Helm/Kustomize 模板（先 helm template 渲染）：{', '.join(tmpl[:3])}"
        return out, None, ("empty-input", why), []
    notes = [f"{len(tmpl)} 个文件是模板（带 {{{{ }}}}），已跳过、没被检查：{', '.join(tmpl[:5])}"] if tmpl else []
    return out, None, None, notes


def check_sql(root, files):
    data, err = run_check("sql_migration_check.py", files, root)
    if err:
        return [], err, None, []
    out, stmts, blank = [], 0, []
    for r in data or []:
        n = int(r.get("statements") or 0)
        stmts += n
        if not n:
            blank.append(str(r.get("file", "?")))
        for f in r.get("findings", []):
            line = f.get("line") or 0
            where = f"{r.get('file', '?')}:L{line}" if line else str(r.get("file", "?"))
            msg = f.get("message", "")
            stmt = (f.get("statement") or "").strip()
            if stmt:
                msg = f"{msg}（语句 `{stmt[:90]}`）"
            out.append(finding(f.get("severity"), f.get("rule"), where, msg, f.get("fix")))
    if not stmts:
        return out, None, ("empty-input", f"{len(files)} 个 .sql 一条语句都没解析出来"
                           f"（{', '.join(blank[:3])}），等于没查"), []
    notes = [f"{len(blank)} 个 .sql 没有解析出语句，这部分没被检查：{', '.join(blank[:5])}"] if blank else []
    return out, None, None, notes


def check_openapi(root, new_spec, base_spec):
    data, err = run_check("openapi_diff.py", [base_spec, new_spec], root)
    if err:
        return [], err, None, []
    out = []
    for x in (data or {}).get("breaking", []):
        out.append(finding("high", x.get("kind"), x.get("where"), x.get("message"), OPENAPI_FIX))
    for x in (data or {}).get("non_breaking", []):
        out.append(finding("info", x.get("kind"), x.get("where"), x.get("message")))
    return out, None, None, []


def check_env(root, files):
    data, err = run_check("env_sync_check.py", ["--src", "."], root)
    if err:
        return [], err, None, []
    data = data or {}
    out = [finding(f.get("severity"), f.get("kind"), f.get("where"), f.get("message"))
           for f in data.get("findings", [])]
    example, envs = data.get("example"), data.get("envs") or []
    if not example:
        return out, None, ("no-baseline",
                           f"找到 {len(files)} 个 .env* 文件（{', '.join(files[:3])}），但没有示例文件"
                           "（.env.example / .env.sample / .env.template / .env.dist），"
                           "无法判断有没有少配变量；补一份示例文件，或用 --skip env 明确豁免"), []
    notes = []
    if not envs:
        notes.append(f"只有示例文件 `{example}`、没有可对比的环境文件，这次只做了「代码 ↔ 示例」对齐；"
                     "要查某个环境少配了什么，把该环境的 .env 放进目标目录，或单独跑 env-sync-check --env")
    return out, None, None, notes


# ---------------------------------------------------------------- 编排

def count(findings):
    return {s: sum(1 for f in findings if f["severity"] == s) for s in SEVS}


NA_REASON = {
    "dockerfile": "没有找到 Dockerfile*",
    "k8s": "没有找到同时含 apiVersion: 与 kind: 的 YAML",
    "sql": "没有找到 .sql 文件",
    "openapi": "没有找到 openapi*/swagger* 规范文件",
    "env": "没有找到 .env* 文件",
}


def run_all(root, found, skip, openapi_base, skip_reasons=None, input_receipts=None):
    skip_reasons = skip_reasons or {}
    items = []
    for key in ITEM_ORDER:
        title, sibling = ITEM_TITLES[key]
        files = found.get(key, [])
        item = {"id": key, "title": title, "skill": sibling, "targets": files,
                "status": "na", "reason_code": "", "reason": "", "notes": [],
                "counts": {s: 0 for s in SEVS}, "findings": []}
        if key in skip:
            if not skip_reasons.get(key):
                item.update(status="unknown", reason_code="missing-skip-reason",
                            reason="按 --skip 跳过但没有理由；用 --skip-reason '" + key + "=具体理由' 补齐记录")
            else:
                item.update(status="skipped", reason_code="user-skip",
                            reason="按用户配置跳过；理由：" + skip_reasons[key],
                            waiver={"reason": skip_reasons[key], "approval_verified": False})
            items.append(item); continue
        if not files:
            item.update(status="na", reason_code="n/a", reason=NA_REASON[key] + "，本项不适用")
            items.append(item); continue
        unsafe = [r for r in (input_receipts or []) if key in r.get("items", [])
                  and r["status"] in ("symlink", "not-regular", "unreadable", "changed-while-hashing")]
        if unsafe:
            item.update(status="unknown", reason_code="unsafe-input",
                        reason=f"{len(unsafe)} 份输入无法安全读取；未执行本项，见文件收据")
            items.append(item); continue
        if key == "openapi":
            res = openapi_item(root, item, files, openapi_base)
            if res is None:
                items.append(item); continue
            findings, err, gap, notes = res
        else:
            findings, err, gap, notes = {"dockerfile": check_dockerfile, "k8s": check_k8s,
                                         "sql": check_sql, "env": check_env}[key](root, files)
        findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["where"], f["code"]))
        item["findings"] = findings
        item["counts"] = count(findings)
        item["notes"] = notes
        if err:
            # 子脚本没跑成 = 拿不到证据，按「无法判断」处理，不能算通过
            item.update(status="unknown", reason_code="check-failed", reason=err)
        elif gap:
            item.update(status="unknown", reason_code=gap[0], reason=gap[1])
        else:
            item["status"] = "ok"
        items.append(item)
    return items


def openapi_item(root, item, files, openapi_base):
    """OpenAPI 项的前置条件：要有旧版规范、两份都要是能比对的规范。
    不满足时直接把 item 标成「无法判断」并返回 None。"""
    def gap(code, reason):
        item.update(status="unknown", reason_code=code, reason=reason)
        return None

    if not openapi_base:
        return gap("no-baseline",
                   f"找到 {len(files)} 份规范（{', '.join(files[:3])}）但没有旧版本可比；"
                   "加 --openapi-base <上一版规范> 才能判断有没有破坏性变更，或用 --skip openapi 明确豁免")
    base_abs = os.path.abspath(openapi_base)
    if not os.path.isfile(base_abs):
        return gap("missing-base", f"--openapi-base 指定的文件不存在：{base_abs}")
    # 旧版规范本身可能就在目标目录里，比对时要把它排掉
    rest = [f for f in files if os.path.realpath(os.path.join(root, f)) != os.path.realpath(base_abs)]
    if not rest:
        return gap("same-file", f"--openapi-base（{base_abs}）和目标目录里唯一的规范是同一个文件，没有可比对的新版本")
    new_abs = os.path.join(root, rest[0])
    bad = [(pth, why) for pth, why in ((base_abs, validate_spec(base_abs)), (new_abs, validate_spec(new_abs))) if why]
    if bad:
        return gap("skipped-invalid",
                   "规范不合格，无法比对（拿不到证据，不计入通过）：" + "；".join(f"`{pth}` {why}" for pth, why in bad))
    item["targets"] = [f"{base_abs} → {rest[0]}"]
    findings, err, _, notes = check_openapi(root, rest[0], base_abs)
    if len(rest) > 1:
        notes.append(f"目标目录里有 {len(rest)} 份规范，只比对了 `{rest[0]}`；"
                     f"其余 {len(rest) - 1} 份没有比对：{', '.join(rest[1:4])}")
    return findings, err, None, notes


# ---------------------------------------------------------------- 报告

STATUS_ZH = {"ok": "已检查", "na": "不适用", "skipped": "已跳过", "unknown": "无法判断"}


def clip(s, n):
    """表格里截断长原因，截了就加省略号（完整原因在「各项问题」与「门禁结论」里）。"""
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n - 1].rstrip("，；、 ") + "…"


def gate(items, total, evidence=None):
    """静态检查门禁；兼容旧 verdict 枚举，但绝不表达生产上线批准。"""
    unknown = [i for i in items if i["status"] == "unknown"]
    concluded = [i for i in items if i["status"] in ("ok", "unknown")]
    ran = [i for i in items if i["status"] == "ok"]
    g = {"unknown": [i["id"] for i in unknown], "checked": [i["id"] for i in ran],
         "high": total["high"], "warn": total["warn"], "info": total["info"],
         "scope": "static_checks_only", "production_readiness": "unknown", "release_approved": False,
         "configured_skips": [i["id"] for i in items if i["status"] == "skipped"],
         "evidence_gaps": (evidence or {}).get("gaps", [])}
    scope_note = "本结果仅为本轮静态检查；运行时、部署、回滚、业务验收与上线批准均未核实。"
    gaps = g["evidence_gaps"]
    if not concluded:
        g.update(verdict="unknown", blocked=True, headline="缺静态检查证据",
                 why="五项检查都没有给出结论——目标目录里没有可检对象，或者全被 --skip 跳过了。"
                     "确认目标目录与检查范围。" + scope_note)
        return g
    if total["high"]:
        why = f"本轮静态规则发现 {total['high']} 个 high；逐项核查规则及输入，修复或按项目流程评审。"
        if unknown:
            why += f"另外还有 {len(unknown)} 项无法判断，一并补齐证据。"
        if gaps:
            why += f"收据另有 {len(gaps)} 项证据缺口。"
        g.update(verdict="no-go", blocked=True, headline=f"发现 high（{total['high']} 项）", why=why + scope_note)
        return g
    if unknown or gaps:
        g.update(verdict="unknown", blocked=True,
                 headline=f"缺静态检查证据（检查 {len(unknown)} 项，收据 {len(gaps)} 项）",
                 why=f"没有发现 high，但有 {len(unknown)} 项（{'、'.join(i['title'] for i in unknown)}）"
                     "没有拿到结论，或收据不完整/检查期间发生变化；`--strict` 退出码 1。"
                     "按报告补齐输入、理由或收据后重跑。" + scope_note)
        return g
    if total["warn"]:
        g.update(verdict="go-with-warn", blocked=False, headline="本轮静态检查未发现 high",
                 why=f"已检查 {len(ran)} 项，有 {total['warn']} 个 warn 待核查。" + scope_note)
        return g
    g.update(verdict="go", blocked=False, headline="本轮静态检查未发现 high",
             why=f"已检查 {len(ran)} 项，未发现 high / warn。" + scope_note)
    return g


def render(root, items, generated, evidence=None):
    total = {s: sum(i["counts"][s] for i in items) for s in SEVS}
    g = gate(items, total, evidence)
    ran = [i for i in items if i["status"] == "ok"]
    unknown = [i for i in items if i["status"] == "unknown"]
    na = [i for i in items if i["status"] == "na"]
    skipped = [i for i in items if i["status"] == "skipped"]
    lines = [f"# 上线体检报告 · {os.path.basename(root.rstrip(os.sep)) or root}", "",
             f"- 目标目录：`{root}`",
             f"- 生成时间：{generated}",
             "- 范围：离线静态规则检查；生产上线资格未知；本报告不作上线批准。",
             f"- 检查项：共 {len(items)} 项，有结论 {len(ran)} 项，无法判断 {len(unknown)} 项，"
             f"不适用 {len(na)} 项，按 --skip 跳过 {len(skipped)} 项", "",
             "## 一、总览", "",
             "| 检查项 | 状态 | high | warn | info | 覆盖 / 原因 |", "|---|---|---:|---:|---:|---|"]
    for i in items:
        c = i["counts"]
        if i["status"] == "ok":
            cover = f"{len(i['targets'])} 个文件" if i["id"] != "openapi" else "1 组对比"
            nums = [str(c["high"]), str(c["warn"]), str(c["info"])]
        elif i["status"] == "unknown":
            cover = f"（{i['reason_code']}）{clip(i['reason'], 70)}"
            nums = [str(c["high"]) if c["high"] else "?", str(c["warn"]) if c["warn"] else "?",
                    str(c["info"]) if c["info"] else "?"]
        else:
            cover = clip(i["reason"], 70) or "-"
            nums = ["-", "-", "-"]
        lines.append(f"| {i['title']} | {STATUS_ZH[i['status']]} | {nums[0]} | {nums[1]} | {nums[2]} | {cover} |")
    lines += [f"| **合计** | | **{total['high']}** | **{total['warn']}** | **{total['info']}** | |", "",
              "「无法判断」是没拿到证据（子脚本没跑成、输入不合格），不是「通过」；"
              "「不适用」仅指本轮未发现该类输入，不证明部署或生产环境无需该项。", "",
              "## 二、各项问题", ""]
    for i in items:
        lines.append(f"### {i['title']}")
        if i["status"] in ("na", "skipped"):
            lines += ["", f"> {STATUS_ZH[i['status']]}：{i['reason']}", ""]
            continue
        if i["status"] == "unknown":
            lines += ["", f"> **无法判断（{i['reason_code']}）**：{i['reason']}", "",
                      "> 这一项没有进入「通过」的判断，门禁按缺证据处理。", ""]
        else:
            lines += ["", "覆盖：" + ", ".join(f"`{t}`" for t in i["targets"][:8])
                      + (f" 等 {len(i['targets'])} 个" if len(i["targets"]) > 8 else ""), ""]
        for note in i["notes"]:
            lines += [f"注意：{note}", ""]
        if not i["findings"]:
            if i["status"] == "ok":
                lines += ["本轮该项静态规则未发现问题。", ""]
            continue
        for f in i["findings"][:TOP_N]:
            head = f"- **[{f['severity'].upper()}]** `{f['code']}`"
            if f["where"]:
                head += f" · `{f['where']}`"
            lines.append(f"{head} — {f['message']}")
            if f["fix"]:
                lines.append(f"  - → 改法：{f['fix']}")
        if len(i["findings"]) > TOP_N:
            lines.append(f"- …… 共 {len(i['findings'])} 条，此处只列前 {TOP_N} 条；"
                         f"跑 `{i['skill']}` 单项技能看全量。")
        lines.append("")
    lines += ["## 三、静态门禁结论", ""]
    if unknown:
        lines.append(f"缺 {len(unknown)} 项证据，逐条原因：")
        for i in unknown:
            lines.append(f"- **{i['title']}**（`{i['reason_code']}`）：{i['reason']}")
        lines.append("")
    lines += [f"**{g['headline']}** — {g['why']}", ""]
    if skipped:
        lines += [f"（{len(skipped)} 项按用户配置跳过："
                  f"{'、'.join(i['title'] for i in skipped)}；理由仅为记录，豁免批准未核实。）", ""]
    if evidence:
        lines += ["## 四、文件与检查器收据", "",
                  f"最多记录 {evidence['limits']['max_files']} 份输入，每份最多哈希 "
                  f"{evidence['limits']['max_file_bytes']} 字节；收据不含文件内容。",
                  "包括发现的检查输入、Dockerfile 同目录 .dockerignore，以及执行 env 项时的代码扫描候选。",
                  "哈希是工作区文件的本轮收据，不是 Git 提交、构建产物或完整生产快照。", "",
                  "| 类别 | 路径 | 状态 | SHA-256 |", "|---|---|---|---|"]
        for category in ("inputs", "checkers"):
            for receipt in evidence[category]:
                path = receipt["path"].replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {category} | `{path}` | {receipt['status']} | {receipt.get('sha256') or '-'} |")
        for gap in evidence["gaps"]:
            lines.append(f"- 证据缺口：{gap}")
        lines += ["", f"检查前后收据一致：{evidence['unchanged_during_checks']}；仅核对有界候选，不能证明无并发改动。", ""]
    lines += ["---", "",
              "本报告由 `release-readiness-check` 生成；每一项都能单独安装成技能用："
              "`dockerfile-check`、`k8s-manifest-check`、`sql-migration-check`、"
              "`openapi-breaking-diff`、`env-sync-check`。"]
    return "\n".join(lines) + "\n"


def pad(s, width):
    """终端列对齐：中日韩字符按两格宽度算。"""
    w = sum(2 if ord(c) > 0x2E7F else 1 for c in s)
    return s + " " * max(1, width - w)


def default_out(root):
    slug = re.sub(r"[^\w.-]+", "-", os.path.basename(root.rstrip(os.sep)) or "project").strip("-") or "project"
    return os.path.join(tempfile.mkdtemp(prefix=f"release-readiness-{slug}-"), "report.md")


# ---------------------------------------------------------------- 有界证据收据

def input_candidates(root, found, openapi_base, skip):
    """列出内置检查器可能使用的输入，去重；不复制文件内容。"""
    candidates = {}

    def add(path, item):
        path = os.path.abspath(path)
        candidates.setdefault(path, set()).add(item)

    for item, paths in found.items():
        for path in paths:
            add(os.path.join(root, path), item)
    for path in found["dockerfile"]:
        ignore = os.path.join(root, os.path.dirname(path), ".dockerignore")
        if os.path.lexists(ignore):
            add(ignore, "dockerfile")
    if openapi_base:
        add(openapi_base, "openapi")
    if found["env"] and "env" not in skip:
        for directory, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in ENV_SKIP_DIRS)
            for name in sorted(files):
                if not name.startswith(".env") and os.path.splitext(name)[1] in ENV_SOURCE_EXT:
                    add(os.path.join(directory, name), "env")
    return [(path, sorted(items)) for path, items in sorted(candidates.items())]


def receipt(path, label, max_bytes, items=None):
    result = {"path": label, "items": items or [], "status": "unreadable", "sha256": None}
    try:
        before = os.lstat(path)
        result["bytes"] = before.st_size
        if stat.S_ISLNK(before.st_mode):
            result["status"] = "symlink"
            return result
        if not stat.S_ISREG(before.st_mode):
            result["status"] = "not-regular"
            return result
        if before.st_size > max_bytes:
            result["status"] = "over-byte-limit"
            return result
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(path, flags), "rb") as source:
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                result["status"] = "changed-while-hashing"
                return result
            body = source.read(max_bytes + 1)
            after = os.fstat(source.fileno())
        if len(body) > max_bytes:
            result["status"] = "over-byte-limit"
        elif (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            result["status"] = "changed-while-hashing"
        else:
            result.update(status="hashed", sha256=hashlib.sha256(body).hexdigest())
    except FileNotFoundError:
        result["status"] = "missing"
    except (OSError, ValueError):
        result["status"] = "unreadable"
    return result


def collect_receipts(root, found, openapi_base, skip, max_files, max_bytes):
    candidates = input_candidates(root, found, openapi_base, skip)
    inputs = []
    for path, items in candidates[:max_files]:
        label = os.path.relpath(path, root)
        if label == ".." or label.startswith(".." + os.sep):
            label = path
        inputs.append(receipt(path, label, max_bytes, items))
    checkers = [receipt(os.path.join(CHECKS_DIR, script), "scripts/checks/" + script, max_bytes, [item])
                for item, script in CHECK_SCRIPTS.items()]
    checkers.append(receipt(__file__, "scripts/release_check.py", max_bytes))
    gaps = [f"{r['path']}: {r['status']}" for r in inputs + checkers if r["status"] != "hashed"]
    omitted = max(0, len(candidates) - max_files)
    if omitted:
        gaps.append(f"另有 {omitted} 份候选输入超过文件数量上限，未生成收据")
    return {"inputs": inputs, "checkers": checkers, "candidate_count": len(candidates),
            "omitted_count": omitted, "gaps": gaps,
            "limits": {"max_files": max_files, "max_file_bytes": max_bytes},
            "scope": "discovered inputs plus dockerignore and env source candidates; no file content"}


def compare_receipts(before, after):
    result = before.copy()
    result["gaps"] = list(before["gaps"])
    result["unchanged_during_checks"] = (
        before["inputs"] == after["inputs"] and before["checkers"] == after["checkers"]
        and before["candidate_count"] == after["candidate_count"])
    if not result["unchanged_during_checks"]:
        result["gaps"].append("检查前后候选文件或有界哈希收据发生变化，重跑后再判读")
    return result


def parse_skip_reasons(raw_reasons, skip):
    reasons = {}
    for raw in raw_reasons:
        if "=" not in raw:
            raise ValueError("--skip-reason 格式应为 'env=具体理由'")
        name, reason = raw.split("=", 1)
        key = SKIP_ALIASES.get(name.strip().lower())
        if key not in skip:
            raise ValueError("--skip-reason 必须对应 --skip 中的一项")
        if not reason.strip() or len(reason) > 500:
            raise ValueError("--skip-reason 理由须为 1–500 字符")
        if key in reasons:
            raise ValueError("同一检查项只能指定一个 --skip-reason")
        reasons[key] = reason.strip().replace("\n", " ").replace("\r", " ")
    return reasons


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description="发布前静态证据报告：五项检查聚合，不作上线批准")
    ap.add_argument("path", nargs="?", default=".", help="目标项目目录，默认当前目录")
    ap.add_argument("--out", default=None, help="Markdown 报告路径，默认写到系统临时目录")
    ap.add_argument("--json", action="store_true", help="同时把汇总结果以 JSON 打到标准输出")
    ap.add_argument("--strict", action="store_true",
                    help="有 high 或有「无法判断」项则退出码 1，用于 CI 门禁")
    ap.add_argument("--skip", default="", help="逗号分隔跳过项：dockerfile,k8s,sql,openapi,env")
    ap.add_argument("--skip-reason", action="append", default=[], help="跳过理由：'env=理由'，每项单独指定")
    ap.add_argument("--openapi-base", default=None, help="上一版 OpenAPI 规范；给了才做破坏性变更比对")
    ap.add_argument("--max-receipts", type=int, default=MAX_RECEIPTS, help="输入收据数量上限，默认 128")
    ap.add_argument("--max-receipt-bytes", type=int, default=MAX_RECEIPT_BYTES, help="每份收据哈希字节上限，默认 4 MiB")
    a = ap.parse_args()

    root = os.path.abspath(a.path)
    if not os.path.isdir(root):
        print(f"目标不是目录：{root}", file=sys.stderr); sys.exit(2)
    skip, unknown = set(), []
    for raw in a.skip.split(","):
        s = raw.strip().lower()
        if not s:
            continue
        (skip.add(SKIP_ALIASES[s]) if s in SKIP_ALIASES else unknown.append(raw.strip()))
    if unknown:
        print(f"--skip 里有不认识的项：{', '.join(unknown)}；可选值 {', '.join(ITEM_ORDER)}", file=sys.stderr)
        sys.exit(2)

    if not (1 <= a.max_receipts <= 10000) or not (1 <= a.max_receipt_bytes <= 64 * 1024 * 1024):
        ap.error("收据上限须为 1–10000 份、每份 1 字节–64 MiB")
    try:
        skip_reasons = parse_skip_reasons(a.skip_reason, skip)
    except ValueError as e:
        ap.error(str(e))
    out_path = os.path.abspath(a.out) if a.out else None
    if out_path and os.path.lexists(out_path):
        print(f"报告路径已存在，拒绝覆盖：{out_path}", file=sys.stderr)
        return 2
    found = discover(root)
    before = collect_receipts(root, found, a.openapi_base, skip, a.max_receipts, a.max_receipt_bytes)
    items = run_all(root, found, skip, a.openapi_base, skip_reasons, before["inputs"])
    after = collect_receipts(root, discover(root), a.openapi_base, skip, a.max_receipts, a.max_receipt_bytes)
    evidence = compare_receipts(before, after)
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        out_path = out_path or default_out(root)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        # 独占创建：同名旧报告、符号链接和并发创建一律拒绝覆盖。
        with open(out_path, "x", encoding="utf-8") as fh:
            fh.write(render(root, items, generated, evidence))
    except OSError as e:
        print(f"报告写入失败：{e.strerror or type(e).__name__}", file=sys.stderr)
        return 2

    total = {s: sum(i["counts"][s] for i in items) for s in SEVS}
    g = gate(items, total, evidence)
    if a.json:
        print(json.dumps({"target": root, "generated": generated, "report": out_path,
                          "total": total, "gate": g, "items": items, "evidence": evidence}, ensure_ascii=False, indent=2))
    else:
        print(f"上线体检 · {root}")
        for i in items:
            c = i["counts"]
            if i["status"] == "ok":
                tail = f"high {c['high']} / warn {c['warn']} / info {c['info']}"
            elif i["status"] == "unknown":
                tail = f"无法判断（{i['reason_code']}）：{i['reason']}"
            else:
                tail = f"{STATUS_ZH[i['status']]}：{i['reason']}"
            print(f"  {pad(i['title'], 24)}{tail}")
        print(f"\n合计：high {total['high']} / warn {total['warn']} / info {total['info']}"
              f"；无法判断 {len(g['unknown'])} 项")
        print(f"门禁：{g['headline']}")
        print(f"报告：{out_path}")
    return 1 if (a.strict and g["blocked"]) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError, KeyError) as error:
        print(f"静态检查失败：{type(error).__name__}；请核对输入与技能包完整性", file=sys.stderr)
        sys.exit(2)
