#!/usr/bin/env python3
"""降 AI 味自检：统计六类套话的命中次数与每千字密度、句长分布（平均、中位、变异系数、
相邻两句长度接近的比例）、破折号、冒号小标题、顿号三连和排比候选。只用 Python 标准库。

它量的是表面信号，不是「AI 检测器」：人写的文字也可能命中很多，数字低也证明不了任何事。
提示里的阈值（变异系数低于 0.35、破折号每千字超过 3 处、冒号小标题 3 行以上）是经验值，只供参考。
词表按自己的领域增删，PATTERNS 里一类一行，写的是正则。

用法：
  python3 ai_tone_check.py draft.txt
  python3 ai_tone_check.py revised.txt
  cat draft.txt | python3 ai_tone_check.py -
退出码：0 成功；1 参数有误或没有正文；2 读不了文件；130 被 Ctrl+C 中断。
"""
import argparse
import re
import statistics
import sys

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130

PATTERNS = {
    "空泛开头": r"在当今[^，。]{0,8}|随着[^，。]{1,15}的(?:发展|普及|进步|到来)|在[^，。]{1,15}的(?:大)?背景下|众所周知",
    "过渡套话": r"值得注意的是|需要指出的是|不难看出|由此可见|与此同时|事实上|首先|其次|此外",
    "总结升华": r"总而言之|总的来说|综上所述|总之|让我们|携手|共同(?:开创|创造|书写|迎接)|未来可期|美好未来",
    "无源引用": r"研究(?:表明|显示|发现)|数据(?:表明|显示)|专家(?:指出|认为)|有调查显示",
    "空洞大词": r"赋能|抓手|闭环|打造|全方位|多维度|深度融合|至关重要|不可或缺|举足轻重",
    "对举保险": r"不是[^。！？]{1,20}而是|不仅[^。！？]{1,20}(?:而且|更|还)|在一定程度上|某种意义上|一方面",
}

# 冒号小标题：加粗标签、列表项标签、行首 6 字以内的标签
HEAD = (r"(?m)^\s*(?:[-*+]\s+)?\*\*[^*\n]{1,12}(?:[：:]\*\*|\*\*[：:])"
        r"|^\s*(?:[-*+]|\d+[.、])\s*[^\s：:，。*]{1,8}[：:]|^[^\s：:，。*#]{1,6}[：:]")


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 ai_tone_check.py --help\n" % message)


def read_text(path):
    """读输入：文件路径，或 - 表示标准输入。读不了抛 OSError，没有输入抛 ValueError。"""
    if path == "-":
        if sys.stdin.isatty():
            raise ValueError("没有输入：给一个文件路径，或用管道传入，例如 cat draft.txt | python3 ai_tone_check.py -")
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except FileNotFoundError:
        raise OSError("找不到文件：%s" % path)
    except IsADirectoryError:
        raise OSError("%s 是目录，请给一个文本文件" % path)
    except UnicodeDecodeError:
        raise OSError("%s 不是 UTF-8 文本：用编辑器另存为 UTF-8 再试" % path)


def report(text):
    size = len(re.sub(r"\s", "", text))
    per_k = lambda n: n * 1000 / max(size, 1)
    print(f"正文 {size} 字（不含空白）\n\n[套话]    次数  每千字  命中")
    found = False
    for name, pat in PATTERNS.items():
        hits = re.findall(pat, text)
        if hits:
            detail = "、".join(f"{h}×{hits.count(h)}" for h in dict.fromkeys(hits))
            print(f"  {name}  {len(hits):>4}  {per_k(len(hits)):>6.1f}  {detail[:50]}")
            found = True
    if not found:
        print("  （无）")

    sents = [s for s in (re.sub(r"\s", "", x) for x in re.split(r"[。！？!?；;…\n]+", text)) if len(s) >= 2]
    lens = [len(s) for s in sents]
    cv = 0.0
    if len(lens) >= 2:
        mean = statistics.mean(lens)
        cv = statistics.pstdev(lens) / mean
        near = sum(abs(a - b) <= 3 for a, b in zip(lens, lens[1:])) / (len(lens) - 1)
        print(f"\n[句长] {len(lens)} 句  平均 {mean:.1f}  中位 {statistics.median(lens):.0f}  "
              f"最短 {min(lens)}  最长 {max(lens)}  变异系数 {cv:.2f}  相邻两句长度差≤3字 {near:.0%}")
        for lo, hi in ((1, 10), (11, 20), (21, 30), (31, 45), (46, 999)):
            n = sum(lo <= x <= hi for x in lens)
            print(f"  {lo:>2}-{hi if hi < 999 else '':<3}字 {'█' * n} {n}")
    else:
        print("\n[句长] 不到 2 句，不统计句长分布")

    dash = text.count("——")
    heads = len(re.findall(HEAD, text))
    stacks = re.findall(r"(?:[^\s，。、；：！？]{1,4}、){2,}[^\s，。、；：！？]{1,4}", text)
    print(f"\n[其他] 破折号 {dash} 处（{per_k(dash):.1f}/千字）  冒号小标题 {heads} 行  "
          f"加粗 {text.count('**') // 2} 处  顿号三连 {len(stacks)} 处  {' / '.join(stacks[:3])}".rstrip())

    rows = []
    for s in re.split(r"[。！？!?\n]+", text):
        parts = [p.strip() for p in re.split(r"[，、；,;]", s) if p.strip()]
        for a, b, c in zip(parts, parts[1:], parts[2:]):
            if len(b) == len(c) >= 3 and any(x == y == z for x, y, z in zip(a[-len(b):], b, c)):
                rows.append(f"{a}，{b}，{c}")
                break
    if rows:
        print("\n[排比候选]（三个并列小句，逐条人工判断）")
        for r in rows[:5]:
            print("  ·", r)

    tips = []
    if len(lens) >= 5 and cv < 0.35:
        tips.append("句长偏整齐：拆一两个长句，把几个短句并成一句")
    if per_k(dash) > 3:
        tips.append("破折号偏多：多数可以换成逗号或句号")
    if heads >= 3:
        tips.append("冒号小标题多：想想哪些可以写成完整句子")
    if tips:
        print("\n[提示]（经验阈值，只供参考）\n  " + "\n  ".join(tips))


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数有误或没有正文；2 读不了文件；130 中断")
    ap.add_argument("file", nargs="?", default="-", help="要检查的文本文件；- 或不写表示从标准输入读")
    a = ap.parse_args(argv)
    try:
        text = read_text(a.file)
    except ValueError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS
    except OSError as e:
        sys.stderr.write("文件错误：%s\n" % e)
        return EXIT_IO
    if not re.sub(r"\s", "", text):
        sys.stderr.write("输入有误：没有正文（文件是空的或只有空白）\n")
        return EXIT_ARGS
    report(text)
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
