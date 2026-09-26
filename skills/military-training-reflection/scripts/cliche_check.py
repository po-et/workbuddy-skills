#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""军训心得自查：字数（800 / 1500 档）、开头是否落进套话、套话清单命中与替换思路、分段情况。

用法：
  python3 scripts/cliche_check.py 军训心得.txt --tier 800
  python3 scripts/cliche_check.py 军训心得.docx --tier 1500
  python3 scripts/cliche_check.py 军训心得.txt --min-chars 1000 --max-chars 1200
  python3 scripts/cliche_check.py --list          # 只打印套话清单

字数口径：「不含标点」= 汉字 + 数字（每位）+ 英文单词；「含标点」再加上标点符号。
「不少于」按不含标点判断、「不超过」按含标点判断——两种口径下都达标，最稳。
以 # 开头的行、以及第一行的短标题（不超过 20 字且没有句号）视为标题，不计字数；行首的引用符号 > 会被去掉。

退出码：0 正常（无论查出多少问题）；1 参数或输入有误；2 文件问题；130 用户中断。
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
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TIERS = {"800": (800, 1000), "1500": (1500, 1800)}

CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
DIGIT_RE = re.compile(r"[0-9０-９]")
WORD_RE = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]+(?:['’][A-Za-z]+)*")
PUNCT_RE = re.compile(r"[^\w\s]|_")
SENTENCE_END_RE = re.compile(r"[。！？!?]")

# 套话清单：(显示名, 正则, 替换思路)。与 references/cliches.md 同步，改一处要改两处。
CLICHES = (
    ("时光飞逝 / 转眼间 / 不知不觉", r"时光飞逝|光阴似箭|白驹过隙|转眼间|转眼之间|一转眼|不知不觉",
     "开头直接写一个具体瞬间：哪天、什么科目、你在做什么"),
    ("为期 X 天的军训", r"为期[\d一二三四五六七八九十两半]+(?:天|周|个星期|日)",
     "天数放到后文一句带过；开头给一个画面"),
    ("烈日炎炎 / 骄阳似火", r"烈日炎炎|骄阳似火|酷暑难耐|烈日当空|炎炎烈日|火辣辣的太阳",
     "写你身体的具体感受：汗流进眼睛不能擦、帽檐下的汗、晒出来的印子"),
    ("汗水浸湿了衣衫 / 汗流浃背", r"汗水(?:浸湿|湿透|打湿)了?(?:衣衫|衣服|迷彩服|衣背|后背)|汗流浃背|挥汗如雨",
     "写一个只有你注意到的细节（写你真看到、真感觉到的）"),
    ("苦并快乐着", r"[苦痛]并快乐着",
     "拆开写：哪件事苦，哪一刻觉得值"),
    ("教官严厉而又和蔼", r"严厉而又?(?:不失)?(?:和蔼|温柔|亲切)|外冷内热|刀子嘴豆腐心|严中有爱",
     "写教官做过的一件具体的事、说过的一句原话"),
    ("我学会了坚持 / 懂得了团结", r"(?:学会|懂得|明白|体会)(?:了|到了)?(?:什么是)?(?:坚持|坚强|团结|集体的力量|纪律|服从|感恩)",
     "写一个「以前我……，现在我……」的具体变化"),
    ("磨炼了意志", r"(?:磨练|磨炼|锻炼|锤炼)了?(?:我的|我们的)?意志|意志(?:得到了?|受到了?)(?:磨练|磨炼|锻炼)",
     "用一个行为上的变化来证明，不要直接下结论"),
    ("流血流汗不流泪", r"流血流汗不流泪|掉皮掉肉不掉队",
     "口号可以引用一次，后面要接你自己的事"),
    ("不经历风雨怎能见彩虹", r"不经历风雨|怎么?能见彩虹|阳光总在风雨后|宝剑锋从磨砺出|梅花香自苦寒来|吃得苦中苦",
     "名句全文最多一句，别连用"),
    ("难忘的回忆 / 永远铭记", r"难忘的回忆|终生难忘|终身难忘|永远铭记|刻骨铭心|永远留在(?:我的)?(?:心中|心里|记忆)",
     "写一个你以后还会用上的习惯"),
    ("军训虽然结束了，但……", r"军训(?:虽然|虽)?(?:已经)?结束了?[，,]\s*但",
     "结尾写具体的下一步，比如每天几点做什么"),
    ("受益匪浅 / 收获颇丰", r"受益匪浅|收获颇丰|获益良多",
     "直接写收获是什么"),
    ("迷彩青春 / 青春无悔", r"迷彩青春|青春无悔|无悔青春|绿色的梦",
     "口号式短语换成一个具体画面"),
    ("每个人都 / 大家都", r"我们每个人都|每个人都|大家都",
     "个人心得写你自己；班级总结用一个具体场面或具体的人代替"),
)
CLICHE_RES = tuple((name, re.compile(p), hint) for name, p, hint in CLICHES)
OPENING_RE = re.compile(r"时光飞逝|光阴似箭|白驹过隙|转眼|不知不觉|为期|随着.{0,12}(?:结束|落下帷幕|到来)|"
                        r"军训(?:生活)?(?:已经)?结束了|落下(?:了)?帷幕|在这个.{0,8}的(?:季节|日子)")


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
        raise FileProblem("%s 超过 5MB，不像是一篇心得；请只保留正文" % label)
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


# ---------------------------------------------------------------- 检查

def count_words(text):
    """返回 (不含标点, 含标点) 字数。"""
    plain = len(CJK_RE.findall(text)) + len(DIGIT_RE.findall(text)) + len(WORD_RE.findall(text))
    return plain, plain + len(PUNCT_RE.findall(text))


def content_lines(text):
    """返回 [(行号, 行文本)] 与识别出的标题；# 开头的行与首行短标题不计入正文。"""
    lines, title = [], None
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip(">").strip()  # 引用格式「> 」只去掉符号，内容照常检查
        if not line:
            continue
        if title is None and not lines:
            plain, _ = count_words(line)
            if plain <= 20 and not SENTENCE_END_RE.search(line):
                title = line
                continue
        lines.append((no, line))
    return lines, title


def find_cliches(lines):
    hits = []
    for no, line in lines:
        taken = []
        for name, regex, hint in CLICHE_RES:
            for m in regex.finditer(line):
                if any(m.start() < e and s < m.end() for s, e in taken):
                    continue
                taken.append((m.start(), m.end()))
                hits.append((no, m.start(), m.group(0), hint))
    return [(no, phrase, hint) for no, _, phrase, hint in sorted(hits)]


def resolve_range(args):
    if args.tier:
        low, high = TIERS[args.tier]
        return low, high, "%s 字档（建议 %d-%d）" % (args.tier, low, high)
    low, high = args.min_chars, args.max_chars
    if low is None and high is None:
        return None, None, None
    if (low is not None and low < 0) or (high is not None and high <= 0):
        raise UsageError("--min-chars 不能为负，--max-chars 必须大于 0")
    if low is not None and high is not None and low > high:
        raise UsageError("--min-chars（%d）不能大于 --max-chars（%d）" % (low, high))
    desc = "自定义区间（%s-%s）" % (low if low is not None else "不限", high if high is not None else "不限")
    return low, high, desc


def build_report(text, label, low, high, range_desc):
    lines, title = content_lines(text)
    body = "\n".join(line for _, line in lines)
    plain, with_punct = count_words(body)
    if plain == 0:
        raise UsageError("%s 里没有可检查的文字（空文件，或只有标题）" % label)

    out = ["文件：%s" % label, "== 字数 =="]
    if title:
        out.append("标题「%s」不计入字数" % title)
    out.append("不含标点 %d 字；含标点 %d 字（老师按哪种口径算，以老师要求为准）" % (plain, with_punct))
    short_by = over_by = 0
    if range_desc:
        parts = []
        if low is not None:
            short_by = max(0, low - plain)
            parts.append("下限按不含标点计 -> " + ("还差 %d 字" % short_by if short_by else "达到"))
        if high is not None:
            over_by = max(0, with_punct - high)
            parts.append("上限按含标点计 -> " + ("超出 %d 字（老师没限上限可忽略）" % over_by if over_by else "未超"))
        out.append("%s：%s" % (range_desc, "；".join(parts)))
    else:
        out.append("未指定档位；加 --tier 800 或 --tier 1500 可对照字数")

    out.append("== 开头 ==")
    opening_flag = 0
    first = lines[0][1]
    m = OPENING_RE.search(first[:40])
    if m:
        opening_flag = 1
        out.append("  第一段前 40 字里有「%s」：建议直接从一个具体瞬间写起（哪天、什么科目、你在做什么）" % m.group(0))
    else:
        out.append("  通过：第一段从「%s」开始" % (first[:16] + ("……" if len(first) > 16 else "")))

    cliches = find_cliches(lines)
    out.append("== 套话（命中处换成只有你知道的细节）==")
    if cliches:
        out.extend("  第 %d 行「%s」-> %s" % hit for hit in cliches)
    else:
        out.append("  （未发现清单里的套话）")

    out.append("== 结构 ==")
    counts = [count_words(line)[0] for _, line in lines]
    out.append("  正文 %d 段：%s" % (len(lines), " | ".join("第%d段 %d" % (i, n) for i, n in enumerate(counts, 1))))
    if len(lines) < 3:
        out.append("  建议至少分成三段：经历 -> 变化 -> 以后")

    out.append("== 结论 ==")
    length_verdict = "未对照"
    if range_desc:
        if short_by:
            length_verdict = "还差 %d 字" % short_by
        elif over_by:
            length_verdict = "超出 %d 字" % over_by
        else:
            length_verdict = "达标"
    out.append("套话 %d 处 | 开头提示 %d 条 | 字数：%s" % (len(cliches), opening_flag, length_verdict))
    return "\n".join(out)


def list_cliches():
    out = ["军训心得常见套话清单（%d 类）：" % len(CLICHES)]
    for i, (name, _, hint) in enumerate(CLICHES, 1):
        out.append("%2d. %s -> %s" % (i, name, hint))
    return "\n".join(out)


def build_parser():
    p = Parser(prog="cliche_check.py",
               description="军训心得自查：字数（800 / 1500 档）、开头、套话命中与替换思路、分段情况。")
    p.add_argument("file", nargs="?", help="心得文件（.txt / .md / .docx）；省略或写 - 表示从标准输入读取")
    p.add_argument("--tier", choices=sorted(TIERS), help="字数档位：800（建议 800-1000）或 1500（建议 1500-1800）")
    p.add_argument("--min-chars", type=int, help="自定义字数下限（按不含标点计），与 --tier 二选一")
    p.add_argument("--max-chars", type=int, help="自定义字数上限（按含标点计），与 --tier 二选一")
    p.add_argument("--list", action="store_true", help="只打印套话清单与替换思路")
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
        if args.list:
            print(list_cliches())
            return EXIT_OK
        if args.tier and (args.min_chars is not None or args.max_chars is not None):
            raise UsageError("--tier 与 --min-chars/--max-chars 只能二选一")
        low, high, range_desc = resolve_range(args)
        text, label = read_input(args.file)
        print(build_report(text, label, low, high, range_desc))
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
