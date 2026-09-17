#!/usr/bin/env python3
"""上线前五分钟体检：把 Dockerfile / K8s 清单 / SQL 迁移 / OpenAPI / .env 五项检查串起来，汇总成一份报告。

用法:
  python3 scripts/release_check.py [目标目录] [--out 报告路径] [--json] [--strict]
                                   [--skip dockerfile,k8s] [--openapi-base 旧规范]

- 自动发现目标目录里的 Dockerfile*、含 kind: 的 K8s YAML、*.sql、openapi*.json/yaml、.env*；
- 逐项用子进程调用 scripts/checks/ 下的独立脚本（--json），失败不影响其他项；
- 产出 Markdown 报告：总览表 → 各项 top 问题 → 门禁结论；默认写到系统临时目录并打印绝对路径。
纯 Python 标准库，不联网、不执行构建、不连集群、不连数据库。
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS_DIR = os.path.join(HERE, "checks")
SEVS = ("high", "warn", "info")
SEV_ORDER = {"high": 0, "warn": 1, "info": 2}
TOP_N = 10
MAX_SNIFF = 2 * 1024 * 1024  # 超过 2MB 的 YAML 不做内容嗅探

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
    if not out:
        err = (p.stderr or "").strip().splitlines()
        return None, f"{script} 没有输出（退出码 {p.returncode}）" + (f"：{err[-1]}" if err else "")
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        err = (p.stderr or "").strip().splitlines()
        return None, f"{script} 输出不是合法 JSON（退出码 {p.returncode}）" + (f"：{err[-1]}" if err else "")


def finding(sev, code, where, message, fix=""):
    return {"severity": sev if sev in SEVS else "info", "code": str(code or ""),
            "where": where or "", "message": message or "", "fix": fix or ""}


# ---------------------------------------------------------------- 五项检查

def check_dockerfile(root, files):
    data, err = run_check("dockerfile_check.py", files, root)
    if err:
        return None, err
    out = []
    for r in data or []:
        for f in r.get("findings", []):
            line = f.get("line") or 0
            where = f"{r.get('file', '?')}:L{line}" if line else str(r.get("file", "?"))
            out.append(finding(f.get("severity"), f.get("rule"), where, f.get("message"), f.get("fix")))
    return out, None


def check_k8s(root, files):
    data, err = run_check("k8s_check.py", files, root)
    if err:
        return None, err
    out = []
    for f in (data or {}).get("findings", []):
        where = " ".join(x for x in (f.get("file"), f.get("object")) if x and x != "-")
        out.append(finding(f.get("severity"), f.get("rule"), where, f.get("message"), f.get("fix")))
    return out, None


def check_sql(root, files):
    data, err = run_check("sql_migration_check.py", files, root)
    if err:
        return None, err
    out = []
    for r in data or []:
        for f in r.get("findings", []):
            line = f.get("line") or 0
            where = f"{r.get('file', '?')}:L{line}" if line else str(r.get("file", "?"))
            msg = f.get("message", "")
            stmt = (f.get("statement") or "").strip()
            if stmt:
                msg = f"{msg}（语句 `{stmt[:90]}`）"
            out.append(finding(f.get("severity"), f.get("rule"), where, msg, f.get("fix")))
    return out, None


def check_openapi(root, new_spec, base_spec):
    data, err = run_check("openapi_diff.py", [base_spec, new_spec], root)
    if err:
        return None, err
    out = []
    for x in (data or {}).get("breaking", []):
        out.append(finding("high", x.get("kind"), x.get("where"), x.get("message"), OPENAPI_FIX))
    for x in (data or {}).get("non_breaking", []):
        out.append(finding("info", x.get("kind"), x.get("where"), x.get("message")))
    return out, None


def check_env(root, _files):
    data, err = run_check("env_sync_check.py", ["--src", "."], root)
    if err:
        return None, err
    out = []
    for f in (data or {}).get("findings", []):
        out.append(finding(f.get("severity"), f.get("kind"), f.get("where"), f.get("message")))
    return out, None


# ---------------------------------------------------------------- 编排

def count(findings):
    return {s: sum(1 for f in findings if f["severity"] == s) for s in SEVS}


def run_all(root, found, skip, openapi_base):
    items = []
    for key in ITEM_ORDER:
        title, sibling = ITEM_TITLES[key]
        files = found.get(key, [])
        item = {"id": key, "title": title, "skill": sibling, "targets": files,
                "status": "skipped", "reason": "", "counts": {s: 0 for s in SEVS}, "findings": []}
        if key in skip:
            item["reason"] = "按 --skip 跳过"
            items.append(item); continue
        if not files:
            item["reason"] = {
                "dockerfile": "没有找到 Dockerfile*",
                "k8s": "没有找到同时含 apiVersion: 与 kind: 的 YAML",
                "sql": "没有找到 .sql 文件",
                "openapi": "没有找到 openapi*/swagger* 规范文件",
                "env": "没有找到 .env* 文件",
            }[key]
            items.append(item); continue
        if key == "openapi":
            if not openapi_base:
                item["reason"] = (f"找到 {len(files)} 份规范（{', '.join(files[:3])}），但没有旧版本可比；"
                                  "加 --openapi-base <上一版规范> 才能判断是否有破坏性变更")
                items.append(item); continue
            base_abs = os.path.abspath(openapi_base)
            if not os.path.isfile(base_abs):
                item["status"] = "error"
                item["reason"] = f"--openapi-base 指定的文件不存在：{openapi_base}"
                items.append(item); continue
            # 旧版规范本身可能就在目标目录里，比对时要把它排掉
            rest = [f for f in files if os.path.realpath(os.path.join(root, f)) != os.path.realpath(base_abs)]
            if not rest:
                item["status"] = "error"
                item["reason"] = "--openapi-base 和目标目录里唯一的规范是同一个文件，没有可比对的新版本"
                items.append(item); continue
            findings, err = check_openapi(root, rest[0], base_abs)
            item["targets"] = [f"{base_abs} → {rest[0]}"]
        else:
            findings, err = {"dockerfile": check_dockerfile, "k8s": check_k8s,
                             "sql": check_sql, "env": check_env}[key](root, files)
        if err:
            item["status"], item["reason"] = "error", err
        else:
            item["status"] = "ok"
            findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["where"], f["code"]))
            item["findings"] = findings
            item["counts"] = count(findings)
        items.append(item)
    return items


# ---------------------------------------------------------------- 报告

STATUS_ZH = {"ok": "已检查", "skipped": "跳过", "error": "执行失败"}


def render(root, items, generated):
    total = {s: sum(i["counts"][s] for i in items) for s in SEVS}
    ran = [i for i in items if i["status"] == "ok"]
    errs = [i for i in items if i["status"] == "error"]
    lines = [f"# 上线体检报告 · {os.path.basename(root.rstrip(os.sep)) or root}", "",
             f"- 目标目录：`{root}`",
             f"- 生成时间：{generated}",
             f"- 检查项：共 {len(items)} 项，实际执行 {len(ran)} 项，"
             f"跳过 {len(items) - len(ran) - len(errs)} 项，失败 {len(errs)} 项", "",
             "## 一、总览", "",
             "| 检查项 | 状态 | high | warn | info | 覆盖 |", "|---|---|---:|---:|---:|---|"]
    for i in items:
        c = i["counts"]
        if i["status"] == "ok":
            cover = f"{len(i['targets'])} 个文件" if i["id"] != "openapi" else "1 组对比"
            nums = [str(c["high"]), str(c["warn"]), str(c["info"])]
        else:
            cover = i["reason"][:60] or "-"
            nums = ["-", "-", "-"]
        lines.append(f"| {i['title']} | {STATUS_ZH[i['status']]} | {nums[0]} | {nums[1]} | {nums[2]} | {cover} |")
    lines += [f"| **合计** | | **{total['high']}** | **{total['warn']}** | **{total['info']}** | |", "",
              "## 二、各项问题", ""]
    for i in items:
        lines.append(f"### {i['title']}")
        if i["status"] != "ok":
            lines += ["", f"> {STATUS_ZH[i['status']]}：{i['reason']}", ""]
            continue
        lines += ["", "覆盖：" + ", ".join(f"`{t}`" for t in i["targets"][:8])
                  + (f" 等 {len(i['targets'])} 个" if len(i["targets"]) > 8 else ""), ""]
        if not i["findings"]:
            lines += ["✓ 没有发现问题。", ""]
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
    lines += ["## 三、门禁结论", ""]
    if errs:
        lines.append(f"注意：{len(errs)} 项检查没跑起来（{'、'.join(i['title'] for i in errs)}），"
                     "结论只覆盖跑通的部分。")
        lines.append("")
    if not ran:
        lines += ["**无法判断** — 五项检查都没有找到可检对象（目录里既没有 Dockerfile、K8s 清单、"
                  ".sql 迁移，也没有 OpenAPI 规范和 .env）。确认一下目标目录是不是选错了。", ""]
    elif total["high"]:
        lines += [f"**不建议上线** — 有 {total['high']} 个 high 级问题（密钥泄露、锁表迁移、"
                  "接口破坏性变更、配置缺失这类会直接打到线上的问题）。先把 high 清零，再跑一次本体检。", ""]
    elif total["warn"]:
        lines += [f"**可以上线，但先看一眼 warn** — 没有 high，{total['warn']} 个 warn "
                  "多是可复现性、资源限制、探针、密钥疑似这类问题，确认一遍风险再发。", ""]
    else:
        lines += [f"**可以上线** — 实际执行的 {len(ran)} 项检查没有 high / warn 级问题。", ""]
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
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^\w.-]+", "-", os.path.basename(root.rstrip(os.sep)) or "project").strip("-") or "project"
    return os.path.join(tempfile.gettempdir(), f"release-readiness-{slug}-{stamp}.md")


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description="上线前五分钟体检：五项检查一次跑完并汇总成报告")
    ap.add_argument("path", nargs="?", default=".", help="目标项目目录，默认当前目录")
    ap.add_argument("--out", default=None, help="Markdown 报告路径，默认写到系统临时目录")
    ap.add_argument("--json", action="store_true", help="同时把汇总结果以 JSON 打到标准输出")
    ap.add_argument("--strict", action="store_true", help="有 high 则退出码 1，用于 CI 门禁")
    ap.add_argument("--skip", default="", help="逗号分隔跳过项：dockerfile,k8s,sql,openapi,env")
    ap.add_argument("--openapi-base", default=None, help="上一版 OpenAPI 规范；给了才做破坏性变更比对")
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

    found = discover(root)
    items = run_all(root, found, skip, a.openapi_base)
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_path = os.path.abspath(a.out or default_out(root))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render(root, items, generated))

    total = {s: sum(i["counts"][s] for i in items) for s in SEVS}
    if a.json:
        print(json.dumps({"target": root, "generated": generated, "report": out_path,
                          "total": total, "items": items}, ensure_ascii=False, indent=2))
    else:
        print(f"上线体检 · {root}")
        for i in items:
            c = i["counts"]
            tail = (f"high {c['high']} / warn {c['warn']} / info {c['info']}"
                    if i["status"] == "ok" else f"{STATUS_ZH[i['status']]}：{i['reason']}")
            print(f"  {pad(i['title'], 24)}{tail}")
        print(f"\n合计：high {total['high']} / warn {total['warn']} / info {total['info']}")
        print("门禁：" + ("无法判断（没有任何可检对象）" if not any(i["status"] == "ok" for i in items)
                         else "不建议上线（有 high）" if total["high"]
                         else "可以上线，但先看 warn" if total["warn"] else "可以上线"))
        print(f"报告：{out_path}")
    sys.exit(1 if (a.strict and total["high"]) else 0)


if __name__ == "__main__":
    main()
