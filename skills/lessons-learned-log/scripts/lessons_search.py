#!/usr/bin/env python3
"""按关键词检索踩坑记录；也能列出久未复核的条目、检查条目格式、找疑似重复。只读，不改任何文件。

用法：
  python3 lessons_search.py ~/lessons 路径 交付 周报     # 检索：命中标题、关键词、触发场景的额外加分
  python3 lessons_search.py ~/lessons --stale 90         # 列出 90 天没复核的条目
  python3 lessons_search.py ~/lessons --all 路径         # 连「已过时」的一起列
  python3 lessons_search.py ~/lessons --lint             # 检查必填字段、状态写法、日期格式
  python3 lessons_search.py ~/lessons --dupes            # 按关键词重合度列出疑似重复，供合并

条目格式：一坑一条，以「### 标题」开头，字段各占一行，如「- 关键词：路径, 交付」。
退出码：0 成功（没有命中也是 0）；1 参数错误；2 目录或文件读不了；3 目录里还没有任何条目；
        4 --lint 发现格式问题；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import datetime
import pathlib
import re
import sys

REQUIRED = ["现象", "根因", "正确做法", "触发场景", "验证方式"]
VAGUE = re.compile(r"^(以后|下次)?(要|多|更)?(注意|小心|细心|仔细|认真)")


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def read_text(f):
    data = f.read_bytes()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def entries(root):
    for f in sorted(root.rglob("*.md")):
        try:
            text = read_text(f)
        except OSError as e:
            print("读不了 %s：%s，已跳过" % (f, e.strerror or e), file=sys.stderr)
            continue
        for block in re.split(r"(?m)^(?=### )", text):
            if block.startswith("### "):
                yield f.name, block.strip()


def field(block, name):
    m = re.search(r"(?m)^- %s[：:][ \t]*(.*)$" % name, block)   # 不用 \s*，免得空字段吞掉下一行
    return m.group(1).strip() if m else ""


def title(block):
    return block.splitlines()[0][4:].strip()


def last_checked(block):
    d = re.search(r"\d{4}-\d{2}-\d{2}", field(block, "最后验证"))
    if not d:
        return None
    try:
        return datetime.date.fromisoformat(d.group())
    except ValueError:
        return None


def keywords(block):
    return {w.strip().lower() for w in re.split(r"[,，、;；\s]+", field(block, "关键词")) if w.strip()}


def lint(all_entries):
    problems = []
    for fname, block in all_entries:
        where = "%s | %s" % (fname, title(block))
        miss = [k for k in REQUIRED if not field(block, k)]
        if miss:
            problems.append("%s：缺 %s" % (where, "、".join(miss)))
        if not field(block, "关键词"):
            problems.append("%s：没写关键词，以后很难搜到" % where)
        state = field(block, "状态")
        if not (state in ("有效", "存疑") or state.startswith("已过时")):
            problems.append("%s：状态「%s」应为 有效 / 存疑 / 已过时：原因" % (where, state or "空"))
        elif state.startswith("已过时") and not re.match(r"^已过时[：:]\s*\S", state):
            problems.append("%s：「已过时」后面要写原因" % where)
        if last_checked(block) is None:
            problems.append("%s：最后验证日期缺失或不是 2026-09-19 这种格式" % where)
        fix = field(block, "正确做法")
        if fix and VAGUE.match(fix) and len(fix) < 15:
            problems.append("%s：正确做法「%s」像态度不像动作，写成下次能照做的步骤" % (where, fix))
    return problems


def dupes(all_entries):
    live = [(f, b, keywords(b)) for f, b in all_entries if not field(b, "状态").startswith("已过时")]
    pairs = []
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            a, b = live[i][2], live[j][2]
            shared = a & b
            if len(shared) >= 2 and len(shared) / len(a | b) >= 0.5:
                pairs.append((len(shared) / len(a | b), live[i], live[j], shared))
    return sorted(pairs, key=lambda p: -p[0])


def main(argv=None):
    ap = ArgParser(description="检索 / 复核踩坑记录（只读）")
    ap.add_argument("root", help="记录目录，如 ~/lessons 或 项目/lessons")
    ap.add_argument("words", nargs="*", help="关键词，3–5 个为宜")
    ap.add_argument("--stale", type=int, metavar="N", help="只列最后验证早于 N 天的条目")
    ap.add_argument("--all", action="store_true", help="连「已过时」的一起列")
    ap.add_argument("--lint", action="store_true", help="检查条目格式")
    ap.add_argument("--dupes", action="store_true", help="列出疑似重复的条目对")
    a = ap.parse_args(argv)
    if a.stale is not None and a.stale < 0:
        ap.error("--stale 要给不小于 0 的天数，例如 --stale 90")
    if sum(bool(x) for x in (a.lint, a.dupes, a.stale is not None)) > 1:
        ap.error("--lint、--dupes、--stale 一次只用一个")

    root = pathlib.Path(a.root).expanduser()
    if not root.exists():
        print("找不到记录目录：%s。第一次使用先建目录（个人用 ~/lessons，项目用 项目/lessons）。" % root,
              file=sys.stderr)
        return 2
    if not root.is_dir():
        print("这不是目录：%s" % root, file=sys.stderr)
        return 2
    try:
        all_entries = list(entries(root))
    except OSError as e:
        print("读取目录失败：%s（%s）" % (root, e.strerror or e), file=sys.stderr)
        return 2
    if not all_entries:
        print("%s 里还没有任何条目（以「### 」开头的记录）。" % root)
        return 3

    if a.lint:
        problems = lint(all_entries)
        for p in problems:
            print("- " + p)
        print("检查了 %d 条，%s" % (len(all_entries), "发现 %d 处问题" % len(problems) if problems else "格式都合格"))
        return 4 if problems else 0
    if a.dupes:
        pairs = dupes(all_entries)
        for score, (f1, b1, _), (f2, b2, _), shared in pairs:
            print("[%.0f%%] %s | %s  <->  %s | %s  （共同关键词：%s）"
                  % (score * 100, f1, title(b1), f2, title(b2), "、".join(sorted(shared))))
        print("疑似重复 %d 对；同根因的才合并，只是话题相近的保留两条。" % len(pairs) if pairs else "没有疑似重复的条目")
        return 0

    today = datetime.date.today()
    hits = []
    for fname, block in all_entries:
        if "已过时" in field(block, "状态") and not a.all:
            continue
        if a.stale is not None:
            d = last_checked(block)
            age = (today - d).days if d else 9999
            if age <= a.stale:
                continue
        key = (block.splitlines()[0] + field(block, "关键词") + field(block, "触发场景")).lower()
        score = sum(block.lower().count(w.lower()) + 2 * key.count(w.lower()) for w in a.words)
        if score or not a.words:
            hits.append((score, fname, block))
    for score, fname, block in sorted(hits, key=lambda h: (-h[0], h[1], title(h[2]))):
        print("[%d] %s | %s | %s %s" % (score, fname, title(block), field(block, "状态"), field(block, "最后验证")))
        print("    正确做法：%s" % field(block, "正确做法"))
        print("    验证方式：%s" % field(block, "验证方式"))
    if hits:
        print("共 %d 条" % len(hits))
    elif a.stale is not None:
        print("没有超过 %d 天未复核的条目" % a.stale)
    else:
        print("没有相关记录")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。本脚本只读，没有改动任何文件。", file=sys.stderr)
        sys.exit(130)
