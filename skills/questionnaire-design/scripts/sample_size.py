#!/usr/bin/env python3
"""问卷样本量粗算：比例类结论需要多少份、总体只有几百人时的有限总体修正、按回收率算发放量，
以及两组比较时多大的差异可能只是抽样误差。只用 Python 标准库（3.6+），不读写任何文件。

用法：
  python3 sample_size.py --margin 0.05 --population 500 --response-rate 0.3
  python3 sample_size.py --margin 5% --confidence 95
  python3 sample_size.py --compare 100 100
参数：
  --margin / -e        允许误差，写 0.05 或 5%（默认 0.05）
  --confidence / -c    置信水平 90、95、99（默认 95）
  --p                  预估比例，不知道就用 0.5（最保守，默认）
  --population / -N    总体人数；给了就做有限总体修正
  --response-rate / -r 预计回收率，写 0.3 或 30%（默认 1，即全部回收）
  --compare n1 n2      两组各收回多少份时，比例相差多少以内可能只是抽样误差（按 p=0.5）
前提：公式只对随机或接近随机的样本成立；方便样本（朋友圈转发、自愿填写）份数再多也修不了偏差。

退出码：0 正常；1 参数不合理（会说明哪里不对、怎么改）；130 手动中断。
"""

import argparse
import math
import sys

EXIT_OK, EXIT_ARGS, EXIT_INTERRUPT = 0, 1, 130
Z = {90: 1.645, 95: 1.96, 99: 2.576}


def zh(message):
    """把 argparse 的英文报错换成中文。"""
    for en, cn in (("the following arguments are required: ", "缺少必填参数："),
                   ("unrecognized arguments: ", "不认识的参数："),
                   ("invalid float value: ", "不是数字："),
                   ("invalid int value: ", "不是整数："),
                   ("invalid choice: ", "不在可选范围内："),
                   ("expected one argument", "后面要跟一个值"),
                   ("expected 2 arguments", "后面要跟两个数")):
        message = message.replace(en, cn)
    return message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % zh(message))
        sys.exit(EXIT_ARGS)


class BadInput(ValueError):
    pass


def ratio(text, name, allow_one=False, example="0.05 或 5%"):
    """把 0.05 / 5% / ５％ 统一成 0–1 之间的小数。"""
    s = str(text).strip().replace("％", "%")
    pct = s.endswith("%")
    try:
        v = float(s.rstrip("%"))
    except ValueError:
        raise BadInput("%s「%s」不是数字，写成 %s" % (name, text, example))
    if pct:
        v /= 100.0
    upper_ok = v <= 1 if allow_one else v < 1
    if v <= 0 or not upper_ok:
        hint = ""
        if not pct and 1 <= v <= 100:
            hint = "；如果你想写 %g%%，请写 %g 或 %g%%" % (v, v / 100.0, v)
        raise BadInput("%s应在 0 到 1 之间，你写的是 %s%s" % (name, text, hint))
    return v


def confidence(text):
    s = str(text).strip().rstrip("%％")
    try:
        v = float(s)
    except ValueError:
        raise BadInput("置信水平「%s」不是数字，可选 90、95、99" % text)
    if v < 1:
        v *= 100
    key = int(round(v))
    if key not in Z or abs(v - key) > 1e-6:
        raise BadInput("置信水平只支持 90、95、99（你写的是 %s）" % text)
    return key


def positive_int(text, name):
    try:
        v = float(str(text).strip())
    except ValueError:
        raise BadInput("%s「%s」不是数字" % (name, text))
    if v < 1 or v != int(v):
        raise BadInput("%s应是正整数，你写的是 %s" % (name, text))
    return int(v)


def main(argv=None):
    ap = Parser(description="问卷样本量粗算。退出码：0 正常，1 参数不合理，130 中断")
    ap.add_argument("-e", "--margin", default="0.05", help="允许误差，0.05 或 5%%（默认 0.05）")
    ap.add_argument("-c", "--confidence", default="95", help="置信水平 90/95/99（默认 95）")
    ap.add_argument("--p", default="0.5", help="预估比例（默认 0.5，最保守）")
    ap.add_argument("-N", "--population", default=None, help="总体人数（可选）")
    ap.add_argument("-r", "--response-rate", default="1", help="预计回收率，0.3 或 30%%（默认 1）")
    ap.add_argument("--compare", nargs=2, metavar=("N1", "N2"), default=None,
                    help="两组各收回多少份，算比例差异的抽样误差范围")
    args = ap.parse_args(argv)

    try:
        level = confidence(args.confidence)
        z = Z[level]
        if args.compare:
            n1 = positive_int(args.compare[0], "第一组份数")
            n2 = positive_int(args.compare[1], "第二组份数")
            diff = z * math.sqrt(0.25 * (1.0 / n1 + 1.0 / n2)) * 100
            print("前提：置信水平 %d%%（z=%s），按最保守的 p=0.5" % (level, z))
            print("两组各收回 %d、%d 份：比例相差不到约 %.1f 个百分点，就可能只是抽样误差" % (n1, n2, diff))
            print("想分辨更小的差异，每组都要更多份数；每个要单独下结论的组，各按公式算一次")
            return EXIT_OK
        e = ratio(args.margin, "允许误差")
        p = ratio(args.p, "预估比例", example="0.5 或 50%")
        r = ratio(args.response_rate, "回收率", allow_one=True, example="0.3 或 30%")
        N = positive_int(args.population, "总体人数") if args.population is not None else None
    except BadInput as exc:
        sys.stderr.write("参数不合理：%s\n" % exc)
        return EXIT_ARGS

    n0 = z * z * p * (1 - p) / (e * e)
    print("前提：置信水平 %d%%（z=%s），预估比例 p=%g，允许误差 ±%g%%" % (level, z, p, round(e * 100, 4)))
    print("总体很大时需要：%d 份" % math.ceil(n0))
    n = n0
    if N is not None:
        n = n0 / (1 + (n0 - 1) / N)
        print("总体 %d 人（有限总体修正）：%d 份" % (N, math.ceil(n)))
    if r < 1:
        send = math.ceil(n / r)
        print("预计回收率 %g%%：至少发放 %d 份" % (round(r * 100, 4), send))
        if N is not None and send > N:
            print("注意：要发 %d 份，超过总体 %d 人。可以全员发放（普查），或放宽允许误差，或想办法提高回收率" % (send, N))
    print("提醒：公式只对随机或接近随机的样本成立；方便样本份数再多也修不了偏差，报告里只能写「本次填答者中」")
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
