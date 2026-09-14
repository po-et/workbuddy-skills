#!/usr/bin/env python3
"""按规则把文件改动映射成上线检查清单。

脚本只做确定性的事实与规则匹配；判断性内容留 AGENT_FILL 标记。

用法:
    python3 render_checklist.py --diff out/diff.json \
        --rules references/rules.example.yaml --out out/checklist.md
"""
import argparse
import fnmatch
import json
import os
import re
import sys
from collections import defaultdict

FILL = "<!-- AGENT_FILL -->"
STATUS_LABEL = {"A": "新增", "M": "修改", "D": "删除", "R": "重命名"}


def load_rules(path):
    """读规则。有 pyyaml 用 pyyaml，否则用内置的极简解析器。"""
    try:
        import yaml  # noqa: PLC0415
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass
    return _mini_yaml(path)


def _mini_yaml(path):
    """只解析本文件需要的结构: rules 列表 + thresholds 映射。"""
    rules, thresholds, cur, section = [], {}, None, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            line = raw.rstrip()
            s = line.strip()
            indent = len(line) - len(line.lstrip())

            if indent == 0 and s.endswith(":"):
                section = s[:-1]
                if cur:
                    rules.append(cur)
                    cur = None
                continue

            if section == "rules":
                if s.startswith("- "):
                    if cur:
                        rules.append(cur)
                    cur = {}
                    s = s[2:].strip()
                if ":" in s and cur is not None:
                    k, _, v = s.partition(":")
                    cur[k.strip()] = v.strip().strip("'\"")
            elif section == "thresholds" and ":" in s:
                k, _, v = s.partition(":")
                v = v.strip()
                thresholds[k.strip()] = int(v) if v.isdigit() else v
    if cur:
        rules.append(cur)
    return {"rules": rules, "thresholds": thresholds}


def match(files, rules):
    """返回 规则 -> 命中文件列表。一个文件可命中多条规则。"""
    hits = defaultdict(list)
    for f in files:
        for idx, r in enumerate(rules):
            want = r.get("status")
            if want and f["status"] != want:
                continue
            if fnmatch.fnmatch(f["path"], r["pattern"]):
                hits[idx].append(f)
    return hits


def render(diff, cfg):
    rules = cfg.get("rules", [])
    th = cfg.get("thresholds", {})
    s = diff["summary"]
    hits = match(diff["files"], rules)

    L = [f"# 上线检查清单　{diff['repo']}　{diff['base']} → {diff['head']}\n"]

    L.append("## 变更概要\n")
    L += [
        f"- 提交数：{s['commits']}",
        f"- 作者：{'、'.join(s['authors']) if s['authors'] else '—'}",
        f"- 改动文件：{s['files_changed']}（新增 {s['added_files']} / "
        f"删除 {s['deleted_files']} / 重命名 {s['renamed_files']}）",
        f"- 增删行：+{s['added']} / -{s['deleted']}",
        f"- 关联工单：{'、'.join(s['issues']) if s['issues'] else '无'}",
    ]

    L.append("\n## 影响面\n")
    L.append(f"{FILL}　（填写：影响哪些功能、哪些用户、哪些上下游服务）")

    high = [(i, r) for i, r in enumerate(rules)
            if r.get("level") == "high" and hits.get(i)]
    L.append("\n## 高风险项\n")
    if not high:
        L.append("_规则未命中高风险项。注意这不等于没有风险——见「未覆盖」一节。_")
    for i, r in high:
        fs = hits[i]
        L.append(f"\n### {r.get('category', '未分类')}　"
                 f"（规则 `{r['pattern']}`，命中 {len(fs)} 个文件）\n")
        for f in fs[:10]:
            L.append(f"- `{f['path']}`　{STATUS_LABEL.get(f['status'], f['status'])}")
        if len(fs) > 10:
            L.append(f"- …… 另有 {len(fs) - 10} 个")
        L += [
            f"\n- **为什么有风险**：{r.get('why', FILL)}",
            f"- [ ] **验证方式**：{r.get('verify', FILL)}",
            f"- [ ] **回滚方案**：{r.get('rollback', FILL)}",
        ]

    L.append("\n## 常规检查项\n")
    normal = [(i, r) for i, r in enumerate(rules)
              if r.get("level") != "high" and hits.get(i)]
    if normal:
        for i, r in normal:
            fs = hits[i]
            L.append(f"- [ ] **{r.get('category', '检查')}**：{r.get('verify', FILL)}"
                     f"　<sub>命中 {len(fs)} 个文件，如 `{fs[0]['path']}`</sub>")
    else:
        L.append("- [ ] 规则未命中常规项")

    # 阈值告警
    over = []
    if th.get("files_changed") and s["files_changed"] > th["files_changed"]:
        over.append(f"改动 {s['files_changed']} 个文件，超过阈值 {th['files_changed']}"
                    f"　→ 考虑拆分批次发布")
    if th.get("deleted_files") and s["deleted_files"] > th["deleted_files"]:
        over.append(f"删除 {s['deleted_files']} 个文件，超过阈值 {th['deleted_files']}"
                    f"　→ 逐个确认无引用")
    if over:
        L.append("\n### 规模告警\n")
        L += [f"- [ ] {o}" for o in over]

    L.append("\n## 需要通知\n")
    L.append(f"{FILL}　（具体到人或组，不要写「相关方」）")

    L.append("\n## 未覆盖\n")
    L += [
        "- 规则只按**文件路径**匹配，识别不出纯逻辑风险（并发、幂等、状态机迁移等）",
        f"- {FILL}　（填写：规则之外你判断出的风险）",
    ]
    unmatched = [f for f in diff["files"]
                 if not any(f in v for v in hits.values())]
    if unmatched:
        L.append(f"- {len(unmatched)} 个改动文件未命中任何规则，"
                 f"未纳入本清单。若其中含关键路径，请补规则")

    L.append("\n---\n_清单由规则生成，不代表完备。**让人误以为清单完备，比没有清单更危险。**_")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--out", default="out/checklist.md")
    a = ap.parse_args()

    with open(a.diff, encoding="utf-8") as f:
        diff = json.load(f)
    cfg = load_rules(a.rules)
    if not cfg.get("rules"):
        sys.exit(f"规则文件未解析出任何规则: {a.rules}")

    body = render(diff, cfg)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(body + "\n")

    print(f"✓ {a.out}　规则 {len(cfg['rules'])} 条，"
          f"待填写 {body.count(FILL)} 处（搜索 AGENT_FILL）")


if __name__ == "__main__":
    main()
