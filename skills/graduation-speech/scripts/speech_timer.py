#!/usr/bin/env python3
"""毕业致辞时长估算：按实测语速数汉字，再加上朗读标注里的停顿时间。

标注记号（与 SKILL.md「朗读标注」一致）：
  /    短停，约 0.5 秒
  //   长停，约 1.5 秒
  ▲    停下等反应（掌声、笑声），约 3 秒
  **词** 重音，不影响时长

用法：
  python3 speech_timer.py speech.txt                 默认语速 200 字/分钟
  python3 speech_timer.py speech.txt 185             用实测语速
  python3 speech_timer.py speech.txt 185 --target 3  和规定时长（分钟）比，超时退出码为 3
  python3 speech_timer.py speech.txt --wpm 110       稿子里有英文时，按实测每分钟词数计入

退出码：
  0    估算完成（给了 --target 时未超时）
  3    给了 --target，估算时长超过规定时长
  1    参数错误：语速或时长不是正数、稿子为空
  2    文件读不了：不存在、没有权限、不是 UTF-8 文本
  130  手动中断（Ctrl+C）

只读，不改文件；只用 Python 标准库。
"""

import argparse
import re
import sys
from pathlib import Path

SHORT_PAUSE, LONG_PAUSE, WAIT_PAUSE = 0.5, 1.5, 3.0
WAIT_MARK = chr(0x25B2)  # ▲
DEFAULT_SPEED = 200.0
EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_OVER, EXIT_INTERRUPTED = 0, 1, 2, 3, 130
CJK_RE = re.compile("[%s-%s]" % (chr(0x4E00), chr(0x9FFF)))  # 基本汉字区
EN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


class Parser(argparse.ArgumentParser):
    """参数错误时用退出码 1 和中文提示。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用法示例：python3 speech_timer.py speech.txt 200 --target 3\n" % message)
        sys.exit(EXIT_ARGS)


def positive(label):
    def convert(text):
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError("%s 必须是数字，收到「%s」" % (label, text))
        if value <= 0:
            raise argparse.ArgumentTypeError("%s 必须是正数，收到「%s」" % (label, text))
        return value
    return convert


def read_text(source):
    if source == "-":
        data, label = sys.stdin.buffer.read(), "标准输入"
    else:
        path = Path(source)
        if path.suffix.lower() in {".docx", ".doc", ".pdf", ".wps", ".pages"}:
            raise ValueError("%s 像是 Word 或 PDF：请把稿子复制进 UTF-8 的 .txt 文件再估算" % source)
        if not path.exists():
            raise OSError("找不到文件：%s（检查路径；文件名有空格时用引号包住）" % source)
        if path.is_dir():
            raise OSError("%s 是文件夹，请给出稿子文件" % source)
        try:
            data = path.read_bytes()
        except PermissionError:
            raise OSError("没有读取权限：%s" % source)
        label = source
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("%s 不是 UTF-8 文本：请另存为 UTF-8 编码的 .txt 再估算" % label)


def fmt(seconds):
    seconds = int(round(seconds))
    return "%d 分 %d 秒" % (seconds // 60, seconds % 60)


def estimate(text, speed, wpm):
    cjk = len(CJK_RE.findall(text))
    words = len(EN_WORD_RE.findall(text))
    long_n = text.count("//")
    short_n = text.count("/") - 2 * long_n
    wait_n = text.count(WAIT_MARK)
    read_s = cjk / speed * 60 + (words / wpm * 60 if wpm else 0)
    pause_s = short_n * SHORT_PAUSE + long_n * LONG_PAUSE + wait_n * WAIT_PAUSE
    return {"cjk": cjk, "words": words, "short": short_n, "long": long_n, "wait": wait_n,
            "read": read_s, "pause": pause_s, "total": read_s + pause_s}


def main(argv=None):
    parser = Parser(description="毕业致辞时长估算（含停顿）")
    parser.add_argument("file", help="标注好的稿子（UTF-8 文本），用 - 表示从标准输入读")
    parser.add_argument("speed", nargs="?", type=positive("语速"), default=DEFAULT_SPEED,
                        help="实测语速，汉字/分钟，默认 200")
    parser.add_argument("--target", type=positive("规定时长"), help="规定时长，分钟，如 3、5、8")
    parser.add_argument("--wpm", type=positive("英文语速"), help="稿子里有英文时，实测每分钟词数")
    args = parser.parse_args(argv)

    try:
        text = read_text(args.file)
    except (OSError, ValueError) as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE

    r = estimate(text, args.speed, args.wpm)
    if r["cjk"] == 0 and r["words"] == 0:
        sys.stderr.write("内容为空：稿子里没有可朗读的文字\n")
        return EXIT_ARGS

    print("汉字 %d | 约 %d 秒（%s）" % (r["cjk"], round(r["total"]), fmt(r["total"])))
    print("朗读约 %d 秒（语速 %g 字/分钟）＋停顿约 %d 秒（/ %d 处，// %d 处，▲ %d 处）"
          % (round(r["read"]), args.speed, round(r["pause"]), r["short"], r["long"], r["wait"]))
    if not 60 <= args.speed <= 500:
        print("提醒：语速 %g 字/分钟 明显偏离常见念稿速度，请确认是不是实测值" % args.speed)
    if r["words"]:
        if args.wpm:
            print("英文 %d 词已按 %g 词/分钟计入" % (r["words"], args.wpm))
        else:
            print("提醒：稿子里有英文 %d 词，未计入时长；加 --wpm <实测每分钟词数> 计入" % r["words"])

    if args.target is None:
        return EXIT_OK
    limit = args.target * 60
    goal_chars = int(round(args.target * args.speed * 0.9))
    print("规定 %g 分钟：目标字数约 %d 字（分钟 × 语速 × 0.9）" % (args.target, goal_chars))
    if args.target > 8:
        print("提醒：本技能按 3、5、8 分钟三档配比，超过 8 分钟请再核对学校规定")
    if r["total"] > limit:
        print("超时约 %d 秒：先删形容词，再按删法删段落（先删第二个故事，再删感谢里的名单）"
              % round(r["total"] - limit))
        return EXIT_OVER
    print("未超时，还余约 %d 秒" % round(limit - r["total"]))
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(EXIT_INTERRUPTED)
