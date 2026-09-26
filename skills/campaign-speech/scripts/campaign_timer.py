#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竞选稿念稿计时：统计可念字数，按每分钟 200-240 字（经验值）估算时长，对照 1/2/3 分钟档位。

用法：
  python3 scripts/campaign_timer.py 竞选稿.txt --minutes 2
  python3 scripts/campaign_timer.py 竞选稿.docx --minutes 1.5
  python3 scripts/campaign_timer.py - --minutes 3 < 竞选稿.txt

计数规则（近似）：汉字每字计 1，阿拉伯数字每位计 1，英文每个单词计 1；
标点、空白、【】里的提示（如【停顿】）、以 # 开头的行不计；行首的引用符号 > 去掉后照常计数。
以【开场】【为什么是我】【三件事】【结尾】开头的行会被识别为分段标记，用来分段统计。

退出码：0 正常；1 参数或输入有误；2 文件问题（找不到、没权限、格式或编码无法识别）；130 用户中断。
只用 Python 标准库；不联网，不写任何文件。
"""

import argparse
import io
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FILE = 2
EXIT_INTERRUPT = 130

MAX_BYTES = 5 * 1024 * 1024
DEFAULT_RATE = (200, 240)  # 每分钟可念字数：经验值，不是标准

# 各档位的分段建议字数，与 SKILL.md「按限时定字数」表一致
TIER_BUDGET = {
    1: (("开场", 35, 40), ("为什么是我", 55, 60), ("三件事", 90, 110), ("结尾", 20, 30)),
    2: (("开场", 50, 70), ("为什么是我", 110, 130), ("三件事", 200, 230), ("结尾", 40, 50)),
    3: (("开场", 70, 90), ("为什么是我", 170, 200), ("三件事", 300, 350), ("结尾", 60, 80)),
}
SECTION_ALIASES = (
    ("开场", "开场"), ("开头", "开场"), ("为什么", "为什么是我"), ("三件", "三件事"),
    ("要做", "三件事"), ("计划", "三件事"), ("结尾", "结尾"), ("结束语", "结尾"),
)
UNLABELLED = "（未标注）"

CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
DIGIT_RE = re.compile(r"[0-9０-９]")
WORD_RE = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]+(?:['’][A-Za-z]+)*")
BRACKET_RE = re.compile(r"【[^】]*】")
LEADING_TAG_RE = re.compile(r"^\s*【([^】]{1,12})】")
RATE_RE = re.compile(r"^\s*(\d{2,3})\s*[-~–—～]\s*(\d{2,3})\s*$")
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# argparse 自带的英文报错，换成中文关键词，方便学生看懂
ARGPARSE_ZH = (
    ("unrecognized arguments", "无法识别的参数"),
    ("expected one argument", "缺少取值"),
    ("invalid float value", "不是有效的数字"),
    ("invalid int value", "不是有效的整数"),
    ("invalid choice", "不在可选范围内"),
    ("choose from", "可选"),
    ("argument ", "参数 "),
)

class UsageError(Exception):
    """参数或输入内容不合法，退出码 1。"""


class FileProblem(Exception):
    """文件读取失败或格式无法识别，退出码 2。"""


class Parser(argparse.ArgumentParser):
    """argparse 默认用退出码 2 报参数错，会和「文件问题」撞车，这里统一改成 1。"""

    def error(self, message):
        for en, zh in ARGPARSE_ZH:
            message = message.replace(en, zh)
        raise UsageError("%s（运行 --help 查看用法）" % message)


# ---------------------------------------------------------------- 读取输入

def _docx_text(data, label):
    """从 .docx 里取正文文字（每个段落一行）。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            info = zf.getinfo("word/document.xml")
            if info.file_size > 50 * 1024 * 1024:
                raise FileProblem("%s 的正文部分过大，无法处理" % label)
            root = ET.fromstring(zf.read(info))
    except FileProblem:
        raise
    except (KeyError, zipfile.BadZipFile, ET.ParseError, RuntimeError, ValueError) as exc:
        raise FileProblem("%s 不是可读的 .docx 文件（%s）；可以把文字复制出来另存为 .txt" % (label, exc))
    lines = []
    for para in root.iter(W_NS + "p"):
        parts = []
        for node in para.iter():
            if node.tag == W_NS + "t" and node.text:
                parts.append(node.text)
            elif node.tag == W_NS + "tab":
                parts.append("\t")
            elif node.tag in (W_NS + "br", W_NS + "cr"):
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines)


def read_input(path):
    """读取文件或标准输入，返回 (文本, 来源名)。支持 UTF-8 / GB18030 / UTF-16 文本与 .docx。"""
    if path is None or path == "-":
        if path is None and sys.stdin.isatty():
            raise UsageError("没有输入：请给出文件路径，或用管道传入文本（- 表示标准输入）")
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        label = "标准输入"
    else:
        label = path
        if os.path.isdir(path):
            raise FileProblem("%s 是文件夹，不是文件" % path)
        try:
            with open(path, "rb") as fh:
                data = fh.read(MAX_BYTES + 1)
        except FileNotFoundError:
            raise FileProblem("找不到文件：%s" % path)
        except PermissionError:
            raise FileProblem("没有权限读取：%s" % path)
        except OSError as exc:
            raise FileProblem("读取失败：%s（%s）" % (path, exc.strerror or exc))
    if len(data) > MAX_BYTES:
        raise FileProblem("%s 超过 5MB，不像是一篇稿子；请只保留正文" % label)
    if data[:4] == b"PK\x03\x04":
        return _docx_text(data, label), label
    if data[:5] == b"%PDF-":
        raise FileProblem("%s 是 PDF：请把文字复制出来另存为 .txt 再运行" % label)
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise FileProblem("%s 是旧版 Word（.doc）：请另存为 .docx 或 .txt 再运行" % label)
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16"), label
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc), label
        except UnicodeDecodeError:
            continue
    raise FileProblem("%s 的编码无法识别（试过 UTF-8、GB18030、UTF-16）：请另存为 UTF-8 文本" % label)


# ---------------------------------------------------------------- 计数与分段

def count_spoken(text):
    """可念字数：汉字 + 数字（每位）+ 英文单词；【】里的提示不计。"""
    text = BRACKET_RE.sub("", text)
    return len(CJK_RE.findall(text)) + len(DIGIT_RE.findall(text)) + len(WORD_RE.findall(text))


def section_of(tag):
    for key, name in SECTION_ALIASES:
        if key in tag:
            return name
    return None


def split_sections(text):
    """返回 (按段名合并的 [(段名, 字数)], 每个非空段落的字数列表)。"""
    order, counts, paras = [], {}, []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip(">").strip()  # 引用格式「> 」只去掉符号，内容照常计数
        if not line:
            continue
        match = LEADING_TAG_RE.match(line)
        if match:
            name = section_of(match.group(1))
            if name:  # 【停顿】之类的舞台提示不当作段落标记
                current = name
        n = count_spoken(line)
        if n == 0:
            continue
        paras.append(n)
        key = current or UNLABELLED
        if key not in counts:
            order.append(key)
            counts[key] = 0
        counts[key] += n
    return [(k, counts[k]) for k in order], paras


# ---------------------------------------------------------------- 输出

def fmt_seconds(sec):
    sec = int(round(sec))
    if sec < 60:
        return "%d 秒" % sec
    if sec % 60 == 0:
        return "%d 分钟" % (sec // 60)
    return "%d 分 %d 秒" % (sec // 60, sec % 60)


def fmt_span(fast, slow):
    a, b = fmt_seconds(fast), fmt_seconds(slow)
    return a if a == b else "%s - %s" % (a, b)


def seconds_range(n, rate):
    """n 字在 rate=(慢, 快) 字/分钟 下的 (最短, 最长) 秒数。"""
    return n * 60.0 / rate[1], n * 60.0 / rate[0]


def parse_rate(value):
    match = RATE_RE.match(value or "")
    if not match:
        raise UsageError("--rate 应写成「200-240」这样的区间，当前是 %r" % value)
    low, high = int(match.group(1)), int(match.group(2))
    if not (60 <= low <= high <= 600):
        raise UsageError("--rate 区间不合理：%s（应在 60-600 之间，且下限不大于上限）" % value)
    return low, high


def build_report(text, label, minutes, rate):
    sections, paras = split_sections(text)
    total = sum(paras)
    if total == 0:
        raise UsageError("%s 里没有可计数的文字（空文件，或只有【】提示和 # 标题）" % label)
    fast, slow = seconds_range(total, rate)
    out = ["文件：%s" % label,
           "可念字数：%d 字（汉字、数字按位、英文按词计；标点、【】内提示、# 开头的行不计）" % total,
           "估算时长：%s（按每分钟 %d-%d 字，经验值；紧张时会变快或卡壳，以出声计时为准）"
           % (fmt_span(fast, slow), rate[0], rate[1])]
    budget = {}
    if minutes:
        low, high = int(round(minutes * rate[0])), int(round(minutes * rate[1]))
        head = "目标 %s 分钟：建议 %d-%d 字 -> " % ("%g" % minutes, low, high)
        if total < low:
            out.append(head + "偏短，比下限少 %d 字。可在「为什么是我」补一个细节，或给三件事各加一个时间点。"
                       % (low - total))
        elif total > high:
            over = total - high
            out.append(head + "偏长，比上限多 %d 字（约 %s）。先删形容词和重复的表态，再压缩三件事里的解释。"
                       % (over, fmt_seconds(over * 60.0 / rate[1])))
        else:
            out.append(head + "在区间内。限时严格的话按下限准备，出声计时练两遍。")
        if minutes in (1, 2, 3) and rate == DEFAULT_RATE:
            budget = dict((name, (a, b)) for name, a, b in TIER_BUDGET[int(minutes)])
    else:
        out.append("对照档位（经验值）：1 分钟 200-240 字 | 2 分钟 400-480 字 | 3 分钟 600-720 字")

    out.append("分段：")
    if any(name != UNLABELLED for name, _ in sections):
        for name, n in sections:
            f, s = seconds_range(n, rate)
            note = ""
            if name in budget:
                a, b = budget[name]
                verdict = "" if a <= n <= b else ("，偏少" if n < a else "，偏多")
                note = "（建议 %d-%d%s）" % (a, b, verdict)
            out.append("  %s：%d 字，约 %s%s" % (name, n, fmt_span(f, s), note))
    else:
        for i, n in enumerate(paras, 1):
            f, s = seconds_range(n, rate)
            out.append("  第 %d 段：%d 字，约 %s" % (i, n, fmt_span(f, s)))
        if minutes in (1, 2, 3):
            out.append("  提示：给段落加上【开场】【为什么是我】【三件事】【结尾】标记，可对照每段建议字数。")
    return "\n".join(out)


def build_parser():
    p = Parser(prog="campaign_timer.py",
               description="竞选稿念稿计时：可念字数、估算时长、与 1/2/3 分钟档位对照（每分钟 200-240 字为经验值）。")
    p.add_argument("file", nargs="?", help="稿件文件（.txt / .md / .docx）；省略或写 - 表示从标准输入读取")
    p.add_argument("--minutes", type=float, help="目标时长（分钟），如 1、2、3，或 1.5 表示 90 秒")
    p.add_argument("--rate", default="200-240", help="每分钟字数区间，默认 200-240（经验值）")
    return p


def _safe_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _safe_streams()
    try:
        args = build_parser().parse_args(argv)
        if args.minutes is not None and not (0 < args.minutes <= 30):
            raise UsageError("--minutes 应在 0 到 30 之间，例如 --minutes 2")
        rate = parse_rate(args.rate)
        text, label = read_input(args.file)
        print(build_report(text, label, args.minutes, rate))
        return EXIT_OK
    except UsageError as exc:
        sys.stderr.write("参数或输入有误：%s\n" % exc)
        return EXIT_USAGE
    except FileProblem as exc:
        sys.stderr.write("文件问题：%s\n" % exc)
        return EXIT_FILE


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）。\n")
        sys.exit(EXIT_INTERRUPT)
