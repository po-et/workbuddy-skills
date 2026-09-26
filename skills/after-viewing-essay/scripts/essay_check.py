#!/usr/bin/env python3
"""观后感草稿自查：每段字数与占比、合计字数、对照目标字数，并提示复述、口号、
情绪词没有原因、开头套话、首尾没回扣这几类常见问题。只用 Python 标准库。

用法（草稿一段一行，存成 UTF-8 文本）：
  python3 essay_check.py draft.txt
  python3 essay_check.py draft.txt --target 600          # 对照 600 字，默认允许上下一成
  cat draft.txt | python3 essay_check.py - --target 1000

提示是按字面规则找的线索，不是评分；改不改由写的人判断。
退出码：0 成功；1 参数或输入有误（如没有正文）；2 读不了文件；130 被 Ctrl+C 中断。
"""
import argparse
import re
import sys

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130
PLAN = (("细节", 15), ("感受", 25), ("联系自身", 35), ("观点与结尾", 25))
OPENING = re.compile(r"^(今天|昨天|前几天|周末)?[，,]?我(们)?(观看|看)了|^(影片|电影|这部电影|纪录片|这部纪录片)讲述了")
RETELL = re.compile(r"讲述了|讲的是|故事发生在|剧情是")
STEPS = re.compile(r"后来|接着|然后|最后")
EMOTION = re.compile(r"感动|震撼|难忘|触动|深受启发|热泪盈眶|心潮澎湃|受益匪浅|感慨万千")
SLOGAN = re.compile(r"我们(一定)?要|我们应该|为社会做贡献|为祖国|珍惜(今天|现在)的幸福生活|长大(以后)?要")
STOP = set("我们 一个 这个 那个 自己 时候 没有 什么 因为 所以 但是 还是 已经 就是 他们 她们 我的 他的 "
           "她的 起来 出来 一样 这样 那样 这些 那些 看到 知道 觉得 现在 以后 一直 不是 可以 我想".split())


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 essay_check.py --help\n" % message)


def read_text(path):
    if path == "-":
        if sys.stdin.isatty():
            raise ValueError("没有输入：给一个文件路径，或用管道传入，例如 cat draft.txt | python3 essay_check.py -")
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except FileNotFoundError:
        raise OSError("找不到文件：%s" % path)
    except UnicodeDecodeError:
        raise OSError("%s 不是 UTF-8 文本：用记事本或编辑器另存为 UTF-8 再试" % path)


def bigrams(text):
    cjk = re.sub(r"[^一-鿿]", " ", text)
    grams = set()
    for run in cjk.split():
        grams.update(run[i:i + 2] for i in range(len(run) - 1))
    return grams - STOP


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数或输入有误；2 读不了文件；130 中断")
    ap.add_argument("file", nargs="?", default="-", help="草稿文件，一段一行；- 或不写表示从标准输入读")
    ap.add_argument("--target", type=int, help="目标字数，如 600")
    ap.add_argument("--tolerance", type=int, default=10, help="允许偏差的百分比（默认 10）")
    a = ap.parse_args(argv)

    if a.target is not None and a.target <= 0:
        sys.stderr.write("输入有误：--target 要大于 0\n")
        return EXIT_ARGS
    if not 0 <= a.tolerance <= 50:
        sys.stderr.write("输入有误：--tolerance 应在 0–50 之间\n")
        return EXIT_ARGS
    try:
        text = read_text(a.file)
    except ValueError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS
    except OSError as e:
        sys.stderr.write("文件错误：%s\n" % e)
        return EXIT_IO

    ps = [p.strip() for p in text.splitlines() if p.strip()]
    if not ps:
        sys.stderr.write("输入有误：没有正文。草稿一段一行，存成 UTF-8 文本\n")
        return EXIT_ARGS
    n = sum(len(p) for p in ps)

    print("段  字数  占比  开头")
    for i, p in enumerate(ps, 1):
        print("%-3d %4d  %3d%%  %s" % (i, len(p), 100 * len(p) // n, p[:10]))
    line = "合计 %d 字" % n
    if a.target:
        lo = a.target * (100 - a.tolerance) // 100
        hi = a.target * (100 + a.tolerance) // 100
        if n < lo:
            verdict = "偏少 %d 字：补联系自身的细节，不加口号" % (lo - n)
        elif n > hi:
            verdict = "偏多 %d 字：先删复述情节的句子" % (n - hi)
        else:
            verdict = "在范围内"
        line += "（目标 %d，允许 %d–%d：%s）" % (a.target, lo, hi, verdict)
    print(line)

    if len(ps) == 4:
        print("\n四段结构对照（参考占比：细节约15% / 感受约25% / 联系自身约35% / 观点与结尾约25%）")
        for idx, ((name, ref), p) in enumerate(zip(PLAN, ps), 1):
            share = 100 * len(p) // n
            gap = share - ref
            note = "" if abs(gap) <= 10 else ("  偏多：压缩到必要的内容" if gap > 0 else "  偏少：再写具体一点")
            print("  第%d段 %s %d%%（参考 %d%%）%s" % (idx, name, share, ref, note))

    tips = []
    if OPENING.search(ps[0]):
        tips.append("开头是「今天我观看了……」或「影片讲述了……」：换成你记住的那个画面或声音")
    for i, p in enumerate(ps, 1):
        if RETELL.search(p) or len(STEPS.findall(p)) >= 3:
            tips.append("第%d段像在复述情节（%s）：剧情介绍全篇不超过五分之一" %
                        (i, "、".join(sorted(set(RETELL.findall(p) + STEPS.findall(p))))))
        emo = EMOTION.findall(p)
        if emo and "因为" not in p:
            tips.append("第%d段有情绪词「%s」，同段没有「因为」：给它配一个原因，或换成一个动作" %
                        (i, "、".join(sorted(set(emo)))))
        slogan = [m.group(0) for m in SLOGAN.finditer(p)]
        if slogan:
            tips.append("第%d段有口号式说法「%s」：后面接得上「比如我……」吗？接不上就删" %
                        (i, "、".join(sorted(set(slogan)))))
    if len(ps) >= 2:
        shared = sorted(bigrams(ps[0]) & bigrams(ps[-1]))
        if shared:
            tips.append("首尾共有的词：%s（结尾有没有回到开头的那个细节，自己再读一遍确认）" % "、".join(shared[:6]))
        else:
            tips.append("首段和末段没有共同的词：结尾可能没有回扣开头的细节")
    print("\n提示（按字面规则找的线索，只作参考，不是评分）")
    for t in tips or ["没有发现明显的套话线索；再读一遍，看每个感受后面有没有「因为」"]:
        print("  · " + t)
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
