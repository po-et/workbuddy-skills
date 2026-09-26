#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奖学金申请书自查：字数、残留占位符、空泛表述、需要和证明材料逐条核对的事实。

用法：
  python3 scripts/claim_check.py 申请书.txt --limit 1500
  python3 scripts/claim_check.py 申请书.docx
  python3 scripts/claim_check.py - < 申请书.txt

字数口径：「不含标点」= 汉字 + 数字（每位）+ 英文单词；「含标点」再加上标点符号。
学校按哪种口径算，以通知为准；判断是否超出上限时按「含标点」计，更稳。
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

CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
DIGIT_RE = re.compile(r"[0-9０-９]")
WORD_RE = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]+(?:['’][A-Za-z]+)*")
PUNCT_RE = re.compile(r"[^\w\s]|_")
SENTENCE_END_RE = re.compile(r"[。！？!?]")

# 残留占位符：[待补：…] [待确认：…] [学院] [ ]、空的【】、XXX、某某、下划线空格
BRACKET_RE = re.compile(r"\[([^\]\n]{0,40})\]")
OTHER_PLACEHOLDER_RE = re.compile(r"【\s*】|【待[补确][^】]*】|[Xx×]{2,}|某某|_{3,}|＿{2,}")

# 空泛表述 → 替换思路。与 references/fact-inventory.md「空话替换表」同步，改一处要改两处。
VAGUE = (
    (r"成绩优异|成绩优秀|成绩优良", "写绩点或平均分、专业排名（名次/总人数）"),
    (r"名列前茅", "写具体名次和总人数"),
    (r"积极参[加与]", "挑一两项写清：你负责什么、做了什么、结果如何"),
    (r"取得了?(?:一定|优异|良好|较好|不错)的?(?:成绩|成果)", "写奖项全称、级别、名次和时间"),
    (r"多次获得|多次荣获|屡获", "写次数，并列出每一项的名称"),
    (r"认真负责|吃苦耐劳|乐于助人|踏实肯干|勤奋好学", "用一件具体的事体现，不要直接下结论"),
    (r"德智体美劳全面发展|全面发展", "删掉，分别用事实体现"),
    (r"具有较强的[一-鿿]{1,6}能力", "用一个项目说明你具体做成了什么"),
    (r"各类|各种|诸多|等等", "列出具体的两三项"),
    (r"受益匪浅|收获颇丰|获益良多", "写收获是什么：学会了哪个方法、改掉了什么习惯"),
    (r"不断提高|进一步加强|努力提升", "写下一学年可以检验的目标"),
)
VAGUE_RES = tuple((re.compile(p), hint) for p, hint in VAGUE)

# 含这些内容的句子，需要和成绩单、证书、证明逐条核对：数字、奖项、排名、级别、职务、时长，
# 以及「六周」「十八组」这类中文数字加量词
CLAIM_RE = re.compile(
    r"\d|奖|证书|称号|评为|获评|结题|认定|排名|名次|第[一二三四五六七八九十]+名|绩点|GPA|平均分|"
    r"论文|期刊|专利|发表|作者|四级|六级|CET|雅思|托福|国家级|省级|市级|校级|院级|"
    r"部长|主席|班长|委员|负责人|志愿|时长|"
    r"(?:[二三四五六七八九十百千两]|[一二三四五六七八九]十)[一二三四五六七八九十百千]*"
    r"(?:周|次|组|场|份|篇|项|名|人|小时|天|届|期)",
    re.I,
)
# 匹配前先去掉的噪声：申请的奖项名本身、「评审委员会」、学年写法、占位符
CLAIM_NOISE_RE = re.compile(r"奖学金|委员会|\d{4}\s*[-\u2013\u2014~至]\s*\d{4}\s*学年|\[[^\]\n]*\]")
PLAN_RE = re.compile(r"计划|打算|争取|希望|准备")          # 打算做的事不是待核对的事实
HEADING_RE = re.compile(r"^[一二三四五六七八九十]+[、.．]")  # 「三、竞赛：……」这类小标题
DATE_ONLY_RE = re.compile(r"^\s*\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?\s*$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")


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
        raise FileProblem("%s 超过 5MB，不像是一份申请书；请只保留正文" % label)
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
            if plain <= 20 and not SENTENCE_END_RE.search(line) and not line.endswith(("：", ":")):
                title = line
                continue
        lines.append((no, line))
    return lines, title


def find_placeholders(lines):
    hits = []
    for no, line in lines:
        for m in BRACKET_RE.finditer(line):
            inner = m.group(1).strip()
            if inner.isdigit():  # [1] 这类引用编号不算
                continue
            hits.append((no, m.start(), m.group(0)))
        for m in OTHER_PLACEHOLDER_RE.finditer(line):
            hits.append((no, m.start(), m.group(0)))
    return [(no, text) for no, _, text in sorted(hits)]


def find_vague(lines):
    hits = []
    for no, line in lines:
        taken = []
        for regex, hint in VAGUE_RES:
            for m in regex.finditer(line):
                if any(m.start() < e and s < m.end() for s, e in taken):
                    continue  # 与已命中的短语重叠，不重复报
                taken.append((m.start(), m.end()))
                hits.append((no, m.start(), m.group(0), hint))
    return [(no, phrase, hint) for no, _, phrase, hint in sorted(hits)]


def find_claims(lines):
    hits = []
    for no, line in lines:
        if HEADING_RE.match(line) and "。" not in line:
            continue
        for sentence in SENTENCE_SPLIT_RE.split(line):
            s = sentence.strip()
            if len(s) < 4 or s.endswith(("：", ":")) or PLAN_RE.search(s):
                continue
            core = CLAIM_NOISE_RE.sub("", s)
            if DATE_ONLY_RE.match(core) or not CLAIM_RE.search(core):
                continue
            hits.append((no, s if len(s) <= 60 else s[:58] + "……"))
    return hits


def build_report(text, label, limit):
    lines, title = content_lines(text)
    body = "\n".join(line for _, line in lines)
    plain, with_punct = count_words(body)
    if plain == 0:
        raise UsageError("%s 里没有可检查的文字（空文件，或只有标题）" % label)

    out = ["文件：%s" % label, "== 字数 =="]
    if title:
        out.append("标题「%s」不计入字数" % title)
    out.append("不含标点 %d 字；含标点 %d 字（学校按哪种口径算，以通知为准）" % (plain, with_punct))
    if limit:
        if with_punct > limit:
            out.append("上限 %d（按含标点计）：超出 %d 字，需要删减" % (limit, with_punct - limit))
        else:
            out.append("上限 %d（按含标点计）：未超出，还可写约 %d 字" % (limit, limit - with_punct))
    else:
        out.append("未给上限；有字数要求时加 --limit，例如 --limit 1500")

    placeholders = find_placeholders(lines)
    out.append("== 1. 残留占位符（交之前必须清零）==")
    if placeholders:
        out.extend("  第 %d 行：%s" % hit for hit in placeholders)
    else:
        out.append("  （未发现）")

    vague = find_vague(lines)
    out.append("== 2. 空泛表述（建议换成事实）==")
    if vague:
        out.extend("  第 %d 行「%s」-> %s" % hit for hit in vague)
    else:
        out.append("  （未发现）")

    claims = find_claims(lines)
    out.append("== 3. 需与证明材料逐条核对的事实（名称、级别、数字以材料为准）==")
    if claims:
        out.extend("  [ ] 第 %d 行：%s -> 对应材料：________" % hit for hit in claims)
    else:
        out.append("  （未发现带数字、奖项、排名、项目的句子——评审很可能看不到硬事实）")

    out.append("== 结论 ==")
    out.append("占位符 %d 处 | 空泛表述 %d 处 | 待核对事实 %d 条"
               % (len(placeholders), len(vague), len(claims)))
    return "\n".join(out)


def build_parser():
    p = Parser(prog="claim_check.py",
               description="奖学金申请书自查：字数、残留占位符、空泛表述、需与证明材料核对的事实。")
    p.add_argument("file", nargs="?", help="申请书文件（.txt / .md / .docx）；省略或写 - 表示从标准输入读取")
    p.add_argument("--limit", type=int, help="字数上限（按含标点计），如 1500；以学校通知为准")
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
        if args.limit is not None and not (0 < args.limit <= 100000):
            raise UsageError("--limit 应为 1 到 100000 之间的整数，例如 --limit 1500")
        text, label = read_input(args.file)
        print(build_report(text, label, args.limit))
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
