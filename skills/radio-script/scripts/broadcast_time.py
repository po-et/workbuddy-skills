#!/usr/bin/env python3
"""广播稿时长工具。只用 Python 标准库（3.6+），只读稿子，不改文件。

两个子命令：
  plan   写之前：按总时长、音乐、语速算出正文该写多少字
         python3 broadcast_time.py plan --total 10m --intro-outro 60 --pads 40 --rate 220
  check  写完后：数稿子的汉字、估念稿时长，顺便找出还没改成念法的数字和符号、太长的句子
         python3 broadcast_time.py check script.txt --rate 220 --music 100 --target 10m

时长写法：10m、10分钟、8m20s、8分20秒、500s、1:30（分:秒）。
不带单位的数字：--total、--target 按分钟算，--intro-outro、--pads、--songs、--music 按秒算。
稿子约定：音乐和动作提示单独一行、以括号「（」开头，不计入字数；行首的「甲：」「乙：」这类角色标记和
          方括号占位（如 [待补]）也不计入，占位会单独列出，提醒播出前补齐。
语速：请念稿人按播音速度念一分钟数字数；测不了先按每分钟 200–240 字估（经验值），不给 --rate 时按 220 算并提示。

退出码：0 正常；1 参数不合理（如时长为负、音乐比总时长还长）；2 稿子文件读不了；
        3 check 给了 --target 且念稿时长超出目标；130 手动中断。
"""

import argparse
import math
import re
import sys

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_OVER, EXIT_INTERRUPT = 0, 1, 2, 3, 130
DEFAULT_RATE = 220
CUE_PREFIX = ("（", "(")
HAN = re.compile("[一-鿿]")
# 书面写法：念稿人得临场换算的东西（按顺序匹配，已被前面规则覆盖的片段不重复报）
UNIT = r"(?:km|kg|cm|mm|ml|m²|㎡|℃|%|％)"
WRITTEN = (
    (re.compile(r"\d{1,2}[:：]\d{2}"), "时间写成念法，如「下午三点半」"),
    (re.compile(r"(?i)\d+(?:\.\d+)?\s*[~～\-–—]\s*\d+(?:\.\d+)?\s*" + UNIT + "?"), "范围写成「十到十五」，单位一并写成字"),
    (re.compile(r"\d+(?:\.\d+)?\s*[%％]"), "写成「百分之……」"),
    (re.compile(r"(?i)\d+(?:\.\d+)?\s*" + UNIT), "单位写成字，如「公里」「摄氏度」"),
    (re.compile(r"\d+"), "数字写成念的样子（年份、电话逐位念，大数写中文）"),
    (re.compile(r"[/&%％℃#＃]"), "符号换成字（3# 楼写成「三号楼」）"),
)
SENTENCE_END = re.compile(r"[。！？!?；;]")
LONG_SENTENCE = 20
ROLE = re.compile(r"^(?:甲乙|甲|乙|丙|丁|男|女|合)[:：]")       # 对播角色标记，不念
PLACEHOLDER = re.compile(r"[\[［][^\]］]*[\]］]")              # [待补] 之类的占位，不念


def zh(message):
    for en, cn in (("the following arguments are required: ", "缺少必填参数："),
                   ("unrecognized arguments: ", "不认识的参数："),
                   ("invalid choice: ", "不在可选范围内："),
                   ("expected one argument", "后面要跟一个值"),
                   ("invalid float value: ", "不是数字：")):
        message = message.replace(en, cn)
    return message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % zh(message))
        sys.exit(EXIT_ARGS)


class BadInput(ValueError):
    pass


def seconds(text, name, bare_unit):
    """把 10m / 8分20秒 / 1:30 / 500s / 500 解析成秒数；bare_unit 是不带单位时的单位（'min' 或 's'）。"""
    s = str(text).strip().lower().replace(" ", "")
    s = s.replace("分钟", "m").replace("分", "m").replace("秒", "s").replace("min", "m").replace("：", ":")
    if s.startswith("-"):
        raise BadInput("%s不能为负数（你写的是 %s）" % (name, text))
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m:
        v = float(m.group(1))
        return v * 60 if bare_unit == "min" else v
    m = re.match(r"^(\d+):(\d{1,2})$", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"^(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?$", s)
    if m and (m.group(1) or m.group(2)):
        return float(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    raise BadInput("%s「%s」看不懂，写成 10m、8分20秒、500s 或 1:30" % (name, text))


def rate_of(value):
    if value is None:
        sys.stderr.write("[提示] 没给语速，按每分钟 %d 字估算（经验值 200–240，以念稿人实测为准）\n" % DEFAULT_RATE)
        return float(DEFAULT_RATE)
    try:
        r = float(value)
    except ValueError:
        raise BadInput("语速「%s」不是数字，写每分钟念多少字，如 220" % value)
    if r <= 0:
        raise BadInput("语速必须大于 0（每分钟念多少字）")
    if r < 100 or r > 400:
        sys.stderr.write("[提示] 语速 %g 字/分钟不太常见，确认是「每分钟」而不是「每秒」或「每小时」\n" % r)
    return r


def mmss(sec):
    sec = int(round(sec))
    return "%d 分 %d 秒" % (sec // 60, sec % 60) if sec >= 60 else "%d 秒" % sec


def cmd_plan(args):
    total = seconds(args.total, "总时长", "min")
    if total <= 0:
        raise BadInput("总时长必须大于 0")
    io = seconds(args.intro_outro, "片头片尾", "s")
    pads = seconds(args.pads, "垫乐", "s")
    songs = seconds(args.songs, "整首播放的歌曲或录音", "s")
    rate = rate_of(args.rate)
    music = io + pads + songs
    if music >= total:
        raise BadInput("音乐加起来 %s，不少于总时长 %s，没有留给念稿的时间：检查是不是把分钟写成了秒"
                       % (mmss(music), mmss(total)))
    usable = total - music
    words = usable / 60.0 * rate * 0.9
    print("总时长 %s − 片头片尾 %s − 垫乐 %s − 整首播放 %s = 可用 %s"
          % (mmss(total), mmss(io), mmss(pads), mmss(songs), mmss(usable)))
    print("语速每分钟 %g 字，留一成给停顿和换气" % rate)
    print("正文约 %d 字" % int(round(words)))
    return EXIT_OK


def read_script(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise IOError("找不到稿子：%s（把稿子另存为 .txt 再试）" % path)
    except IsADirectoryError:
        raise IOError("%s 是文件夹，不是稿子文件" % path)
    except PermissionError:
        raise IOError("没有权限读取：%s" % path)
    if path.lower().endswith((".doc", ".docx", ".pdf")):
        raise IOError("只读纯文本：把稿子另存为 .txt（UTF-8）再试")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise IOError("无法识别 %s 的编码：另存为 UTF-8 的 .txt 再试" % path)


def cmd_check(args):
    rate = rate_of(args.rate)
    music = seconds(args.music, "音乐", "s")
    target = seconds(args.target, "目标时长", "min") if args.target else None
    if target is not None and target <= 0:
        raise BadInput("目标时长必须大于 0")
    text = read_script(args.script)

    spoken, written, long_ones, holes = [], [], [], []
    for n, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(CUE_PREFIX):
            continue
        stripped = ROLE.sub("", stripped)
        found = PLACEHOLDER.findall(stripped)
        if found:
            holes.extend((n, h) for h in found)
            stripped = PLACEHOLDER.sub("", stripped)
        spoken.append(stripped)
        covered, frags, fixes = [], [], []
        for pattern, fix in WRITTEN:
            for m in pattern.finditer(stripped):
                a, b = m.span()
                if any(a < y and x < b for x, y in covered):
                    continue
                covered.append((a, b))
                frags.append((a, m.group(0).strip()))
                if fix not in fixes:
                    fixes.append(fix)
        if frags:
            written.append((n, [f for _, f in sorted(frags)], fixes))
        for sent in SENTENCE_END.split(stripped):
            hz = len(HAN.findall(sent))
            if hz > LONG_SENTENCE:
                long_ones.append((n, hz, sent.strip()[:18]))

    count = sum(len(HAN.findall(l)) for l in spoken)
    read_s = count / rate * 60
    print("汉字 %d | 念稿约 %d 秒 | 连音乐约 %d 秒" % (count, round(read_s), round(read_s + music)))
    if written:
        total = sum(len(f) for _, f, _ in written)
        print("还没改成念法的写法 %d 处（%d 行）：" % (total, len(written)))
        for n, frags, fixes in written[:5]:
            shown = "".join("「%s」" % f for f in frags[:6]) + ("等" if len(frags) > 6 else "")
            print("  第 %d 行 %s → %s" % (n, shown, "；".join(fixes)))
    if holes:
        print("还有 %d 处方括号占位（[待补] 等，不计入字数），播出前必须补齐：%s"
              % (len(holes), "、".join("第 %d 行" % n for n, _ in holes[:5])))
    if long_ones:
        print("超过 %d 字的句子 %d 句（念前试读，卡壳就拆短）：" % (LONG_SENTENCE, len(long_ones)))
        for n, hz, head in long_ones[:3]:
            print("  第 %d 行，%d 字：「%s……」" % (n, hz, head))
    if target is not None:
        gap = read_s + music - target
        if gap > 0:
            cut = int(math.ceil(gap / 60.0 * rate))
            print("比目标 %s 多 %s，约需删 %d 字" % (mmss(target), mmss(gap), cut))
            return EXIT_OVER
        spare = int(-gap / 60.0 * rate * 0.9)
        print("比目标 %s 少 %s，还可加约 %d 字" % (mmss(target), mmss(-gap), spare))
    return EXIT_OK


def main(argv=None):
    ap = Parser(description="广播稿时长工具。退出码：0 正常，1 参数不合理，2 稿子读不了，3 超出目标时长，130 中断")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan", help="写之前：算正文该写多少字")
    p.add_argument("--total", required=True, help="播出总时长，如 10m、3分钟")
    p.add_argument("--intro-outro", default="0", help="片头片尾合计，默认按秒，如 60")
    p.add_argument("--pads", default="0", help="栏目间垫乐合计，默认按秒，如 40")
    p.add_argument("--songs", default="0", help="要整首播放的歌曲或录音合计，默认按秒")
    p.add_argument("--rate", default=None, help="语速：每分钟念多少字（实测）")
    c = sub.add_parser("check", help="写完后：数字数、估时长、找书面写法")
    c.add_argument("script", help="稿子 .txt；音乐提示单独一行、以「（」开头")
    c.add_argument("--rate", default=None, help="语速：每分钟念多少字（实测）")
    c.add_argument("--music", default="0", help="音乐总时长，默认按秒")
    c.add_argument("--target", default=None, help="目标总时长，如 10m；超出时退出码 3")
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.error("请指定子命令 plan 或 check，例：broadcast_time.py plan --total 10m --rate 220")

    try:
        if args.cmd == "plan":
            return cmd_plan(args)
        return cmd_check(args)
    except BadInput as exc:
        sys.stderr.write("参数不合理：%s\n" % exc)
        return EXIT_ARGS
    except IOError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
