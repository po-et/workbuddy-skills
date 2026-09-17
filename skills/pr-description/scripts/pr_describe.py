#!/usr/bin/env python3
"""从 git 分支差异生成 PR / MR 描述草稿（Markdown）。纯标准库，只读 git。

用法：
  python3 pr_describe.py                      # 自动找基线分支（main/master/develop）
  python3 pr_describe.py --base origin/main --out PR.md
  python3 pr_describe.py --format gitlab
"""
import argparse, collections, os, re, subprocess, sys

GIT = os.environ.get("GIT_BIN", "git")
ISSUE = re.compile(r"(?:#|[A-Z][A-Z0-9]+-)(\d+)|(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#?(\d+)", re.I)
CC = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?(!)?:\s*(.+)$", re.I)


def git(*args, check=True):
    r = subprocess.run([GIT, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} 失败：{r.stderr.strip()}")
    return r.stdout.strip()


def detect_base(explicit):
    if explicit:
        return explicit
    for cand in ("origin/main", "origin/master", "origin/develop", "main", "master", "develop"):
        if subprocess.run([GIT, "rev-parse", "--verify", "-q", cand], capture_output=True).returncode == 0:
            return cand
    sys.exit("找不到基线分支，请用 --base 指定")


def area(path):
    p = path.lower()
    if re.search(r"(^|/)(test|tests|__tests__|spec|specs)(/|$)|_test\.|\.test\.|\.spec\.|test_", p): return "测试"
    if re.search(r"(^|/)(migrations?|alembic|db/migrate)(/|$)|\.sql$", p): return "数据库迁移"
    if re.search(r"(^|/)(\.github|\.gitlab-ci|jenkinsfile|\.circleci|azure-pipelines|\.drone)", p) or p.endswith((".gitlab-ci.yml",)): return "CI/CD"
    if re.search(r"(package(-lock)?\.json|yarn\.lock|pnpm-lock|requirements.*\.txt|pyproject|poetry\.lock|go\.(mod|sum)|cargo\.(toml|lock)|gemfile|pom\.xml|build\.gradle)", p): return "依赖"
    if re.search(r"\.(md|rst|txt|adoc)$|(^|/)docs?/", p): return "文档"
    if re.search(r"(dockerfile|docker-compose|helm|k8s|kubernetes|deploy|infra|terraform)", p): return "部署/基础设施"
    if re.search(r"\.(ya?ml|toml|ini|cfg|env|json|properties)$|(^|/)config/", p): return "配置"
    if re.search(r"\.(css|scss|less|html|vue|jsx|tsx)$|(^|/)(ui|components|views|pages)/", p): return "前端/界面"
    if re.search(r"(^|/)(api|routes|controllers|handlers|endpoints)/", p): return "接口"
    return "核心代码"


def main():
    ap = argparse.ArgumentParser(description="生成 PR 描述草稿")
    ap.add_argument("--base", help="基线分支，如 origin/main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--format", choices=["github", "gitlab"], default="github")
    ap.add_argument("--out", help="写入文件而不是打印")
    a = ap.parse_args()
    base = detect_base(a.base)
    merge_base = git("merge-base", base, a.head)
    rng = f"{merge_base}..{a.head}"
    log = git("log", "--reverse", "--format=%H%x01%s%x01%b%x02", rng)
    commits = []
    for chunk in log.split("\x02"):
        if chunk.strip():
            h, s, b = (chunk.strip("\n").split("\x01") + ["", ""])[:3]
            body = "\n".join(l for l in b.strip().splitlines() if not re.match(r"^(Co-Authored-By|Signed-off-by|Reviewed-by|Change-Id|Refs?):", l, re.I)).strip()
            commits.append({"hash": h[:8], "subject": s.strip(), "body": body})
    if not commits:
        sys.exit(f"{base}..{a.head} 没有提交")
    numstat = git("diff", "--numstat", rng)
    files, add_, del_ = [], 0, 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            ad, de, path = parts
            ad, de = (int(ad) if ad.isdigit() else 0), (int(de) if de.isdigit() else 0)
            add_ += ad; del_ += de; files.append((path, ad, de))
    status = dict()
    for line in git("diff", "--name-status", rng).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status[parts[-1]] = parts[0][0]
    by_area = collections.defaultdict(list)
    for path, ad, de in files:
        by_area[area(path)].append((path, ad, de, status.get(path, "M")))
    issues = sorted({(g[0] or g[1]) for c in commits for g in ISSUE.findall(c["subject"] + "\n" + c["body"]) if (g[0] or g[1])}, key=int)
    types = collections.Counter()
    breaking = False
    for c in commits:
        m = CC.match(c["subject"])
        if m:
            types[m.group(1).lower()] += 1
            if m.group(3): breaking = True
        if "BREAKING CHANGE" in c["body"]:
            breaking = True
    main_type = types.most_common(1)[0][0] if types else "feat"
    scope = collections.Counter(p.split("/")[0] for p, *_ in files).most_common(1)[0][0] if files else ""
    title = commits[-1]["subject"] if len(commits) == 1 else f"{main_type}({scope}): " + (commits[-1]["subject"].split(": ", 1)[-1])
    has_tests = "测试" in by_area
    has_migration = "数据库迁移" in by_area
    has_deps = "依赖" in by_area
    has_ci = "CI/CD" in by_area or "部署/基础设施" in by_area
    has_config = "配置" in by_area
    risk = []
    if breaking: risk.append("包含破坏性变更（提交信息标注了 `!` 或 BREAKING CHANGE），需要版本号与迁移说明")
    if has_migration: risk.append("包含数据库迁移：确认可回滚、大表锁时长、是否需要停机窗口")
    if has_deps: risk.append("依赖有变化：确认许可证与漏洞扫描通过、lockfile 已更新")
    if has_ci: risk.append("CI/部署配置有变化：先在非生产环境验证流水线")
    if has_config: risk.append("配置有变化：确认各环境的配置项已同步")
    if not has_tests: risk.append("没有测试文件改动：说明为何不需要，或补充测试")
    if add_ + del_ > 800: risk.append(f"改动较大（+{add_} / -{del_}）：考虑拆分为多个 PR 便于评审")
    L = []
    L.append(f"<!-- 标题建议：{title} -->")
    L.append("## 背景 / 动机\n")
    bodies = [c["body"] for c in commits if c["body"]]
    L.append((bodies[0].splitlines()[0] if bodies else "<!-- 一两句话：为什么要做这个改动，解决什么问题 -->") + "\n")
    L.append("## 改动内容\n")
    for ar in ("核心代码", "接口", "前端/界面", "数据库迁移", "配置", "依赖", "测试", "CI/CD", "部署/基础设施", "文档"):
        if ar in by_area:
            L.append(f"**{ar}**")
            for path, ad, de, st in sorted(by_area[ar])[:12]:
                tag = {"A": "新增", "D": "删除", "R": "重命名"}.get(st, "修改")
                L.append(f"- {tag} `{path}`（+{ad} / -{de}）")
            if len(by_area[ar]) > 12:
                L.append(f"- … 共 {len(by_area[ar])} 个文件")
            L.append("")
    L.append("提交记录：")
    for c in commits:
        L.append(f"- {c['hash']} {c['subject']}")
    L.append("")
    L.append("## 测试\n")
    if has_tests:
        L.append("- [x] 新增/修改了测试：" + "、".join(f"`{p}`" for p, *_ in by_area["测试"][:5]))
    else:
        L.append("- [ ] 单元测试 <!-- 无测试改动，请说明原因 -->")
    L.append("- [ ] 本地/预发验证步骤：<!-- 怎么验证，附命令或截图 -->")
    L.append("- [ ] 回归范围：<!-- 受影响的功能 -->\n")
    L.append("## 风险与回滚\n")
    for r in risk or ["低风险：无迁移、无依赖变化、无配置变化"]:
        L.append(f"- {r}")
    L.append("- 回滚方式：<!-- revert 本 PR / 回退部署 / 数据修复脚本 -->\n")
    if issues:
        L.append("## 关联\n")
        L.append("、".join(("Closes #" if a.format == "github" else "Closes #") + i for i in issues) + "\n")
    L.append("## 评审清单\n")
    L.append("- [ ] 已自测通过　- [ ] 文档/变更日志已更新　- [ ] 新增环境变量已登记　- [ ] 无敏感信息提交")
    L.append(f"\n<!-- 基线 {base}，{len(commits)} 个提交，{len(files)} 个文件，+{add_} / -{del_} -->")
    out = "\n".join(L)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out); print(f"已写入 {os.path.abspath(a.out)}")
    else:
        print(out)


if __name__ == "__main__":
    main()
