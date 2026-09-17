#!/usr/bin/env python3
"""技能体检：给一个或多个 SKILL.md 打分并给出具体修改建议。零依赖。

维度（各 0–20，总分 100）：
  1 可发现性：description 是否写"什么时候用"、触发词/同义词覆盖、长度合理；tags 数量
  2 结构：有 何时用/流程/输出契约(或验收)/常见问题(或红线) 等小节；正文长度适中
  3 可执行性：有具体命令或步骤；引用的 scripts/ 文件存在；{baseDir} 引用正确
  4 合规：frontmatter 完整（name/description 或 SkillHub 的 slug/version/displayName）；无无扩展名文件；复刻作品有 ATTRIBUTION；无密钥样字符串
  5 示例：examples_zh/en 各 1–3 条或正文有示例；示例与描述一致（含描述中的关键词）
用法：python3 skill_lint.py <技能目录或 SKILL.md>... [--json] [--min 70]
"""
import argparse
import json
import re
import sys
from pathlib import Path

CJK = re.compile(r"[一-鿿]")
SECRET = re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|skh_[0-9a-f]{40,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
TRIGGER_WORDS = ["当用户", "用于", "适用", "使用", "Use when", "when the user", "触发", "时使用"]
SECTION_HINTS = {
    "何时用": ["何时", "什么时候", "适用", "When to Use", "用于"],
    "流程": ["流程", "步骤", "第 1 步", "第1步", "Process", "Step"],
    "产出": ["输出契约", "输出", "产出", "交付", "Output", "验收", "Verification"],
    "边界": ["禁止", "红线", "红灯", "不做", "不用", "Red Flags", "Common Mistakes", "常见问题"],
}


def parse(p: Path):
    text = p.read_text("utf-8", errors="ignore")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    fm, body = {}, text
    lists = {}
    if m:
        body = m.group(2)
        cur = None
        for line in m.group(1).splitlines():
            mm = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
            if mm:
                k, v = mm.group(1), mm.group(2).strip()
                if v[:1] in "\"'" and v[-1:] == v[:1]:
                    v = v[1:-1]
                fm[k] = v; cur = k if v == "" else None
                if v == "":
                    lists[k] = []
            elif cur and line.strip().startswith("- "):
                lists[cur].append(line.strip()[2:].strip().strip('"'))
    return fm, lists, body


def score(dir_or_file: Path):
    sk = dir_or_file / "SKILL.md" if dir_or_file.is_dir() else dir_or_file
    d = sk.parent
    if not sk.exists():
        return {"path": str(sk), "name": d.name, "total": 0, "scores": {"可发现性": 0, "结构": 0, "可执行性": 0, "合规": 0, "示例": 0}, "tips": ["缺 SKILL.md（目录为空或未完成）"]}
    fm, lists, body = parse(sk)
    desc = fm.get("description", "") or fm.get("summary", "")
    tags = lists.get("tags", []) or [t.strip() for t in fm.get("tags", "").strip("[]").split(",") if t.strip()]
    tips = []
    # 1 可发现性
    s1 = 0
    if desc:
        s1 += 4
        if any(w in desc for w in TRIGGER_WORDS): s1 += 5
        else: tips.append("description 里写清『什么时候用』（当用户说…时使用）")
        syn = len(re.findall(r"[「」“”]", desc)) // 2 + desc.count("、") + desc.count("/")
        if syn >= 6: s1 += 5
        elif syn >= 3: s1 += 3
        else: tips.append("description 补充触发词与同义词（用户会怎么说这件事）")
        L = len(desc)
        if 80 <= L <= 600: s1 += 3
        elif L > 600: tips.append(f"description {L} 字偏长，超过 600 会被截断/降权（估）")
        else: tips.append(f"description 只有 {L} 字，太短难以命中搜索")
    else:
        tips.append("缺 description/summary")
    if len(tags) >= 6: s1 += 3
    elif len(tags) >= 3: s1 += 2
    else: tips.append("tags 建议 6–12 个，中英混合含缩写")
    # 2 结构
    s2 = 0
    heads = re.findall(r"^#{1,3}\s+(.+)$", body, re.M)
    found = {k: any(h for h in heads if any(x.lower() in h.lower() for x in v)) or any(x in body for x in v) for k, v in SECTION_HINTS.items()}
    s2 += 4 * sum(found.values())
    for k, ok in found.items():
        if not ok: tips.append(f"正文缺『{k}』一节")
    n = len(body)
    if 1500 <= n <= 12000: s2 += 4
    elif n < 1500: tips.append(f"正文仅 {n} 字符，可能太薄"); s2 += 1
    else: tips.append(f"正文 {n} 字符，考虑把参考内容拆到 references/"); s2 += 2
    # 3 可执行性
    s3 = 0
    cmds = re.findall(r"```(?:bash|sh|shell|python|json|yaml)?\n(.*?)```", body, re.S)
    if cmds: s3 += 8
    else: tips.append("没有任何命令/代码块，Agent 难以按图索骥")
    refs = set(re.findall(r"\{baseDir\}/([\w./-]+)", body)) | set(re.findall(r"(?:^|\s)scripts/([\w./-]+\.py)", body))
    missing = [r for r in refs if not (d / r).exists() and not (d / "scripts" / Path(r).name).exists()]
    if refs and not missing: s3 += 8
    elif refs: s3 += 3; tips.append("引用了不存在的文件: " + ", ".join(missing[:5]))
    else: s3 += 4
    if re.search(r"\b(python3|node|bash)\b", body): s3 += 4
    # 4 合规
    s4 = 0
    if fm.get("name") or fm.get("slug"): s4 += 5
    else: tips.append("frontmatter 缺 name（或 SkillHub 的 slug）")
    if fm.get("version"): s4 += 3
    junk = [f.name for f in d.rglob("*") if f.is_file() and f.suffix == ""]
    if not junk: s4 += 4
    else: tips.append("无扩展名文件会被 SkillHub 拒绝: " + ", ".join(junk[:5]))
    if re.search(r"改编自|Adapted from|来源：|Source:", body + (d / "ATTRIBUTION.md").read_text("utf-8", errors="ignore") if (d / "ATTRIBUTION.md").exists() else body):
        s4 += 4 if (d / "ATTRIBUTION.md").exists() else 2
        if not (d / "ATTRIBUTION.md").exists(): tips.append("复刻作品建议附 ATTRIBUTION.md（来源、许可证、改动）")
    else:
        s4 += 4
    if SECRET.search(body): tips.append("正文疑似包含密钥样字符串！"); s4 -= 10
    else: s4 += 4
    # 5 示例
    s5 = 0
    ex = lists.get("examples_zh", []) + lists.get("examples_en", [])
    if 2 <= len(ex) <= 6: s5 += 10
    elif ex: s5 += 6; tips.append("examples_zh/en 各 1–3 条为宜")
    elif re.search(r"示例|例子|Example", body): s5 += 5; tips.append("frontmatter 补 examples_zh/examples_en（客户端会展示为『试试这样问我』）")
    else: tips.append("没有示例；加 2–3 条用户会怎么问")
    if ex and desc:
        key = set(re.findall(r"[一-鿿]{2,}", desc))
        hit = sum(1 for e in ex if any(k in e for k in key))
        s5 += 10 if hit >= max(1, len(ex) // 2) else 5
        if hit < max(1, len(ex) // 2): tips.append("示例与 description 关键词对不上，容易误触发")
    total = max(0, min(100, s1 + s2 + s3 + s4 + s5))
    return {"path": str(sk), "name": fm.get("name") or fm.get("slug") or d.name, "total": total,
            "scores": {"可发现性": s1, "结构": s2, "可执行性": s3, "合规": s4, "示例": s5}, "tips": tips}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+"); ap.add_argument("--json", action="store_true"); ap.add_argument("--min", type=int, default=0)
    a = ap.parse_args()
    results = [score(Path(p)) for p in a.paths]
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in sorted(results, key=lambda r: -r["total"]):
            sc = "  ".join(f"{k} {v}" for k, v in r["scores"].items())
            print(f"{r['total']:3d}  {r['name']:36s} {sc}")
            for t in r["tips"][:6]:
                print(f"       → {t}")
    sys.exit(0 if all(r["total"] >= a.min for r in results) else 1)


if __name__ == "__main__":
    main()
