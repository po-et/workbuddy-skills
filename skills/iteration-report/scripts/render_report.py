#!/usr/bin/env python3
"""把采集到的数据渲染成报告骨架 + 统计小节。

脚本只负责「事实性」内容：统计、清单、溯源链接、数据缺口。
「判断性」内容（交付价值、风险解读、下期计划）留空标记，由 Agent 填写。

用法:
    python3 render_report.py --git out/git.json [--issues out/issues.json] \
        --template references/report-template.md --out out/report.md
"""
import argparse
import json
import os
from collections import defaultdict

FILL = "<!-- AGENT_FILL -->"


def load(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cluster_by_issue(commits):
    """按工单号聚类；无工单号的归入 __no_issue__。"""
    groups = defaultdict(list)
    for c in commits:
        if c["issues"]:
            for i in c["issues"]:
                groups[i].append(c)
        else:
            groups["__no_issue__"].append(c)
    return groups


def sec_overview(git, issues):
    s = git["summary"]
    lines = [
        f"- 时间窗：{git['window']['since']} 至 {git['window']['until']}",
        f"- 仓库数：{len(git['repos'])}",
        f"- 提交数：{s['commits']}（不含 merge）",
        f"- 参与人数：{s['authors']}　{'、'.join(s['author_list']) if s['author_list'] else '—'}",
        f"- 改动规模：{s['files_changed']} 文件，+{s['added']} / -{s['deleted']} 行",
        f"- 关联工单：{len(s['issues'])} 个",
    ]
    if issues:
        i = issues["summary"]
        lines.append(f"- 工单流转：共 {i['total']}，已关闭 {i['closed']}，未关闭 {i['open']}")
    return "\n".join(lines)


def sec_delivery(git):
    groups = cluster_by_issue(git["commits"])
    out = []
    for key in sorted(k for k in groups if k != "__no_issue__"):
        cs = groups[key]
        refs = " ".join(f"`{c['short']}`" for c in cs[:6])
        more = f" 等 {len(cs)} 个提交" if len(cs) > 6 else ""
        titles = "；".join(dict.fromkeys(c["subject"] for c in cs))[:200]
        poor = any(c["msg_quality"] != "ok" for c in cs)
        flag = "　**（提交信息质量差，需从 diff 反推）**" if poor else ""
        out.append(f"- **[{key}]** {FILL}{flag}\n"
                   f"  - 原始提交标题：{titles}\n"
                   f"  - 溯源：{refs}{more}")
    orphans = groups.get("__no_issue__", [])
    if orphans:
        out.append(f"\n**未关联工单的提交（{len(orphans)} 个，需人工判断是否值得写入）**\n")
        for c in orphans[:20]:
            out.append(f"- `{c['short']}` {c['subject']}　<sub>{c['repo']} / {c['author']}</sub>")
        if len(orphans) > 20:
            out.append(f"- …… 另有 {len(orphans) - 20} 个")
    return "\n".join(out) if out else "_本期无提交记录。_"


def sec_risk(git):
    sig = git.get("risk_signals", [])
    if not sig:
        return "_未命中自动风险信号。仍需人工判断是否存在信号之外的风险。_"
    out = []
    for s in sig:
        out.append(f"- `{s['commit']}`（{s['repo']}）— {s['detail']}\n  - 影响与处置：{FILL}")
    return "\n".join(out)


def sec_pending(issues):
    if not issues:
        return "_未接入工单系统，遗留项无法自动获取。_"
    openi = [i for i in issues["issues"] if not i.get("closed")]
    if not openi:
        return "_本期无未关闭工单。_"
    out = []
    for i in openi:
        who = i.get("assignee") or "未指派"
        url = f"（[{i['id']}]({i['url']})）" if i.get("url") else f"（{i['id']}）"
        out.append(f"- {i['title']} {url}　负责人：{who}\n  - 阻塞原因：{FILL}")
    return "\n".join(out)


def sec_gaps(git, issues):
    gaps = []
    if git.get("errors"):
        for e in git["errors"]:
            gaps.append(f"- 仓库 `{e['repo']}` 采集失败：{e['error']}")
    poor = git["summary"]["poor_messages"]
    if poor:
        gaps.append(f"- {poor} 条提交信息为空或过于通用，相关结论由 diff 推断，准确性下降")
    if not issues:
        gaps.append("- 未接入工单系统，第四、五节数据缺失")
    orphan = sum(1 for c in git["commits"] if not c["issues"])
    if orphan:
        gaps.append(f"- {orphan} 条提交未关联任何工单，无法归因到交付项")
    return "\n".join(gaps) if gaps else "- 无已知数据缺口。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--git", required=True)
    ap.add_argument("--issues")
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", default="out/report.md")
    a = ap.parse_args()

    git, issues = load(a.git), load(a.issues)
    with open(a.template, encoding="utf-8") as f:
        tpl = f.read()

    body = (tpl
            .replace("{{WINDOW}}", f"{git['window']['since']} ~ {git['window']['until']}")
            .replace("{{DELIVERY}}", sec_delivery(git))
            .replace("{{OVERVIEW}}", sec_overview(git, issues))
            .replace("{{RISK}}", sec_risk(git))
            .replace("{{PENDING}}", sec_pending(issues))
            .replace("{{NEXT}}", FILL)
            .replace("{{GAPS}}", sec_gaps(git, issues)))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(body)

    todo = body.count(FILL)
    print(f"✓ {a.out}　待填写判断性内容 {todo} 处（搜索 AGENT_FILL）")


if __name__ == "__main__":
    main()
