#!/usr/bin/env python3
"""把发布日志（skillhub publish 的输出）里的 slug/skillId 追加到 docs/submission-checklist.md，按 skillId 去重。
用法：python3 tools/record_skillids.py <日志文件...> [--title "第 N 批"]
"""
import re, sys, pathlib, datetime
import argparse
_ap = argparse.ArgumentParser(); _ap.add_argument("files", nargs="+"); _ap.add_argument("--title", default="增量记录")
_a = _ap.parse_args(); args, title = _a.files, _a.title
p = pathlib.Path(__file__).resolve().parents[1] / "docs" / "submission-checklist.md"
existing = set(re.findall(r"\|\s*(\d{6})\s*\|", p.read_text()))
rows, conflicts = [], []
for f in args:
    txt = pathlib.Path(f).read_text(errors="replace")
    for m in re.finditer(r"^--- (\S+)\s+(\d\d:\d\d:\d\d) ---\n(.*?)(?=^--- |\Z)", txt, re.M | re.S):
        slug, t, body = m.groups()
        sid = re.search(r"skillId=(\d+)", body)
        if sid and sid.group(1) not in existing:
            rows.append((slug, sid.group(1), t)); existing.add(sid.group(1))
        elif "slug 冲突" in body:
            conflicts.append(slug)
if rows:
    today = datetime.date.today().isoformat()
    block = [f"\n### SkillHub {title}（{today}，{len(rows)} 个，机器审核中）\n", "| slug | skillId | 发布时间 |", "|---|---|---|"] + [f"| {s} | {i} | {t} |" for s, i, t in rows]
    if conflicts:
        block.append(f"\n冲突（需换 slug 重发）：{', '.join(conflicts)}")
    p.write_text(p.read_text().rstrip("\n") + "\n" + "\n".join(block) + "\n")
print(f"新增 {len(rows)} 条：{[r[1] for r in rows]}；冲突：{conflicts}")
