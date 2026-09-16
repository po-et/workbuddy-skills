#!/usr/bin/env python3
"""CI 配置审查（GitHub Actions / GitLab CI）：基于文本模式的安全与可靠性检查。零依赖、不联网。

不做完整 YAML 解析（避免第三方依赖），所以结论是"疑似"，需人工确认。
用法：python3 ci_lint.py --path . [--out out/ci.json] [--md out/ci.md]
"""
import argparse
import json
import re
import sys
from pathlib import Path

SHA40 = re.compile(r"@[0-9a-f]{40}\b")
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
RUN_START = re.compile(r"^\s*-?\s*run:\s*(\|?|>?)\s*(.*)$")
INJECT = re.compile(r"\$\{\{\s*github\.(event\.(issue|pull_request|comment|review|discussion|commit|head_commit)\.[a-z_.]*(title|body|message|name|ref|label)|head_ref)\s*\}\}")
SECRET_ECHO = re.compile(r"\b(echo|printf|cat)\b.*\$\{\{\s*secrets\.")
CHECKOUT_OLD = re.compile(r"actions/checkout@v[12]\b")
OFFICIAL = ("actions/", "github/", "docker/", "aws-actions/", "azure/", "google-github-actions/")


def lint_gha(p: Path):
    text = p.read_text("utf-8", errors="ignore")
    lines = text.splitlines()
    f = []
    top_perms = re.search(r"^permissions:", text, re.M) is not None
    pr_target = "pull_request_target" in text
    checkout_head = re.search(r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head\.(sha|ref)", text) is not None
    if pr_target and checkout_head:
        f.append(("high", 0, "pull_request_target 且检出 PR head：外部 PR 可在带 secrets 的上下文执行代码"))
    if not top_perms and re.search(r"^\s+permissions:", text, re.M) is None:
        f.append(("medium", 0, "未声明 permissions：GITHUB_TOKEN 使用仓库默认权限，建议显式最小权限"))
    jobs_block = text.split("\njobs:", 1)[1] if "\njobs:" in text else ""
    if jobs_block and "timeout-minutes:" not in jobs_block:
        f.append(("low", 0, "没有 timeout-minutes：卡死的 job 会跑满 6 小时"))
    if re.search(r"^on:\s*$|^on:\s*\[", text, re.M) and "pull_request" in text and "concurrency:" not in text:
        f.append(("info", 0, "PR 工作流没有 concurrency：连续推送会排队跑旧提交"))
    for i, line in enumerate(lines, 1):
        m = USES.match(line)
        if m:
            ref = m.group(1)
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            if not SHA40.search(ref):
                sev = "low" if ref.startswith(OFFICIAL) else "high"
                f.append((sev, i, f"action 未固定到 commit SHA：{ref}（tag 可被覆盖，供应链风险）"))
            if CHECKOUT_OLD.search(ref):
                f.append(("low", i, f"过旧的 checkout 版本：{ref}"))
        if INJECT.search(line):
            f.append(("high", i, "脚本注入风险：把 github.event 里的用户可控文本直接放进表达式/命令，应先赋给 env 再引用"))
        if SECRET_ECHO.search(line):
            f.append(("medium", i, "疑似把 secret 打印到日志"))
        if re.search(r"continue-on-error:\s*true", line):
            f.append(("info", i, "continue-on-error: true —— 确认不是在掩盖测试失败"))
        if re.search(r"curl[^|\n]*\|\s*(sudo\s+)?(ba)?sh\b", line):
            f.append(("medium", i, "curl | sh 远程脚本直接执行，建议固定版本并校验哈希"))
    return f


def lint_gitlab(p: Path):
    text = p.read_text("utf-8", errors="ignore"); lines = text.splitlines(); f = []
    for i, line in enumerate(lines, 1):
        if re.search(r"^\s*image:\s*[^\s#]+:latest\b", line) or re.search(r"^\s*image:\s*[A-Za-z0-9_./-]+\s*$", line):
            f.append(("low", i, "镜像未固定版本（latest 或无 tag）"))
        if re.search(r"\b(echo|printf)\b.*\$(CI_JOB_TOKEN|CI_REGISTRY_PASSWORD|CI_DEPLOY_PASSWORD)", line):
            f.append(("medium", i, "疑似打印 CI 凭证"))
        if re.search(r"curl[^|\n]*\|\s*(sudo\s+)?(ba)?sh\b", line):
            f.append(("medium", i, "curl | sh 远程脚本直接执行"))
    if "timeout:" not in text:
        f.append(("low", 0, "没有 timeout：卡死的 job 使用项目默认上限"))
    if "interruptible: true" not in text:
        f.append(("info", 0, "没有 interruptible: true：新推送不会取消旧流水线"))
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    root = Path(a.path)
    files = sorted(list((root / ".github" / "workflows").glob("*.y*ml")) + ([root / ".gitlab-ci.yml"] if (root / ".gitlab-ci.yml").exists() else []))
    if not files:
        sys.exit("没找到 .github/workflows/*.yml 或 .gitlab-ci.yml")
    report = []
    for p in files:
        fs = lint_gitlab(p) if p.name == ".gitlab-ci.yml" else lint_gha(p)
        report.append({"file": str(p.relative_to(root)), "findings": [{"severity": s, "line": l, "message": m} for s, l, m in fs]})
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    total = sum(len(r["findings"]) for r in report)
    md = ["# CI 配置审查", "", f"- 文件 {len(files)} 个，发现 {total} 项（high {sum(1 for r in report for x in r['findings'] if x['severity']=='high')} / medium {sum(1 for r in report for x in r['findings'] if x['severity']=='medium')}）", ""]
    for r in report:
        md.append(f"## {r['file']}")
        if not r["findings"]:
            md.append("- 未发现模式级问题"); md.append(""); continue
        for x in sorted(r["findings"], key=lambda x: (order[x["severity"]], x["line"])):
            md.append(f"- **{x['severity']}**{(' L' + str(x['line'])) if x['line'] else ''}：{x['message']}")
        md.append("")
    md += ["## 说明", "- 基于文本模式匹配，不是完整 YAML 解析；每条都需要人工确认。", "- 未覆盖：矩阵、复用工作流、自托管 runner 的隔离、OIDC 配置。"]
    text = "\n".join(md) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    if a.md:
        Path(a.md).parent.mkdir(parents=True, exist_ok=True); Path(a.md).write_text(text, "utf-8"); print(f"✓ {a.md}：{total} 项")
    else:
        print(text)


if __name__ == "__main__":
    main()
