#!/usr/bin/env python3
"""辩论稿计时：按你实测的语速估算立论稿、结辩稿的时长，并指出最该删的段落。

用法：
  python3 scripts/speech_timer.py lilun.txt 250               # 250 = 你实测的每分钟字数
  python3 scripts/speech_timer.py lilun.txt 250 --limit 3:00  # 与主办方时限比较
  python3 scripts/speech_timer.py - 250 --limit 180 < lilun.txt   # 从标准输入读
  python3 scripts/speech_timer.py english.txt 150 --language en --limit 3:00  # 150 词/分钟

中文口径：汉字、阿拉伯数字每个按 1 字，英文单词每个按 2 个等效字；实测语速也要用这个口径。
英文口径（--language en）：英文单词、数字串每个按 1 词；don't、one-size-fits-all 各算 1 词。
中英混合稿用中文口径；英文模式不接受汉字。标点和空格不计，数字读法仍需实读核对。
以【】开头的标题行（如【一辩立论】）只用来分段，不计入字数；[待核]、[待补]、[待确认]
等方括号里的占位也不计入，单独报数——替换成正文后请重新计时。

退出码：0 正常（给了 --limit 时表示没超时）；1 参数或内容有误；2 文件读不了；
        3 超出时限；130 手动中断（Ctrl+C）。
只用 Python 标准库。
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

HAN = re.compile("[\u3400-\u4dbf\u4e00-\u9fff]")
DIGIT = re.compile("[0-9\uff10-\uff19]")
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’\-\u2010\u2011][A-Za-zÀ-ÖØ-öø-ÿ]+)*")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
BRACKET = re.compile(r"\[[^\[\]\n]*\]|［[^［］\n]*］")
HEADER = re.compile(r"^\s*【([^】]*)】\s*(.*)$")
MARKS = ("待核", "待补", "待确认")
RATE_RANGE = {"zh": (100, 450), "en": (50, 400)}
TARGET_RATIO = 0.9            # 写到时限的九成，留出强调和停顿


class InputError(Exception):
    """带退出码的友好报错。"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def count_units(text, language="zh"):
    """中文等效字或英文词；全角字母和数字先转半角，口径与传入语速一致。"""
    text = unicodedata.normalize("NFKC", text)
    if language == "en":
        if HAN.search(text):
            raise InputError(1, "英文模式里有汉字：中英混合稿用 --language zh，按中文等效字口径实测语速")
        return len(WORD.findall(text)) + len(NUMBER.findall(text))
    return len(HAN.findall(text)) + len(DIGIT.findall(text)) + 2 * len(WORD.findall(text))


def parse_limit(raw):
    """把 180、180s、3:00、3分钟、三分钟、两分半、2分30秒、3 等写法换成秒；不大于 20 的纯数字按分钟理解。"""
    s = raw.strip().lower().replace("：", ":").replace(" ", "")
    m = re.fullmatch(r"([一二两三四五六七八九十])分(?:钟)?(半)?", s)   # 口语：三分钟、两分半
    if m:
        return "一二三四五六七八九十".find(m.group(1).replace("两", "二")) * 60 + 60 + (30 if m.group(2) else 0)
    m = re.fullmatch(r"(\d+):([0-5]?\d)", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)(?:分钟|分|min|m))?(?:(\d+)(?:秒|s|sec))?", s)
    if m and (m.group(1) or m.group(2)):
        return round(float(m.group(1) or 0) * 60 + int(m.group(2) or 0))
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        value = float(s)
        return round(value * 60) if value <= 20 else round(value)
    raise InputError(1, "时限「%s」看不懂：写成 3:00、180 或 3分钟 都可以" % raw)


def fmt_seconds(sec):
    sec = int(round(sec))
    return "%d 分 %02d 秒" % (sec // 60, sec % 60) if sec >= 60 else "%d 秒" % sec


def read_text(path):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        p = Path(path)
        if not p.exists():
            raise InputError(2, "找不到文件 %s：检查路径，或把正文另存成 .txt 再试" % path)
        if p.is_dir():
            raise InputError(2, "%s 是文件夹，请给出稿子文件的路径" % path)
        if p.suffix.lower() in (".doc", ".docx", ".pages", ".pdf", ".wps"):
            raise InputError(2, "%s 是 Word/PDF 等文档，脚本只读纯文本：请另存为 .txt（UTF-8），"
                                "或把正文粘贴进一个 .txt 文件" % p.name)
        try:
            data = p.read_bytes()
        except OSError as exc:
            raise InputError(2, "读不了 %s（%s）：检查文件权限，或换个位置另存一份" % (path, exc.strerror or exc))
    if data[:2] == b"PK":
        raise InputError(2, "这是压缩格式的文档（多半是 .docx），请另存为纯文本 .txt 再计时")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise InputError(2, "文件编码认不出来：请在编辑器里「另存为」UTF-8 编码的 .txt")


def split_paragraphs(text):
    """按行切段；【】标题行开启新的小节。返回 [(小节名, 段落原文)]。"""
    section, out = "全文", []
    for line in text.splitlines():
        m = HEADER.match(line)
        if m:
            section = m.group(1).strip() or section
            line = m.group(2)
        if line.strip():
            out.append((section, line.strip()))
    return out


def analyse(text, rate, limit, language="zh"):
    paragraphs = split_paragraphs(text)
    placeholders = {k: 0 for k in MARKS}
    other = 0
    rows = []
    for section, para in paragraphs:
        for item in BRACKET.findall(para):
            hit = next((k for k in MARKS if k in item), None)
            if hit:
                placeholders[hit] += 1
            else:
                other += 1
        spoken = BRACKET.sub("", para)
        rows.append((section, para, count_units(spoken, language)))
    total = sum(n for _, _, n in rows)
    if total == 0:
        raise InputError(1, "没有可计时的正文（方括号占位和【】标题不计入）：请先把稿子写出来再计时")

    unit = "词" if language == "en" else "字"
    rule = ("英文单词和数字串各算 1 词，撇号或连字符词不拆开，标点不计" if language == "en" else
            "汉字和数字各算 1 字，英文单词算 2 个等效字，标点不计")
    print("按 %g %s/分钟估算（%s）" % (rate, unit, rule))
    if language == "en":
        print("  数字串按 1 词近似：年份、数字和缩写先按实际读法展开，再计时并实读核对")
    elif not any(HAN.search(BRACKET.sub("", para)) for _, para, _ in rows) and any(
            WORD.search(BRACKET.sub("", para)) for _, para, _ in rows):
        print("  [待确认] 正文是英文，当前用中文等效字：若语速是词/分钟，请加 --language en 后重跑")
    print("全文 %d %s，约 %s" % (total, unit, fmt_seconds(total / rate * 60)))

    code = 0
    if limit:
        cap = int(limit / 60 * rate)
        target = int(cap * TARGET_RATIO)
        print("时限 %s：上限 %d %s，写到九成是 %d %s" % (fmt_seconds(limit), cap, unit, target, unit))
        if total > cap:
            over = total - cap
            print("  → 超出上限 %d %s（约 %s），至少删到 %d %s，最好删到 %d %s"
                  % (over, unit, fmt_seconds(over / rate * 60), cap, unit, target, unit))
            print("  → 删稿顺序：修饰和排比 → 重复的例子 → 第三论点（改到攻辩里用）；"
                  "定义、标准和每个论点「回到标准」那句不删")
            code = 3
        elif total > target:
            print("  → 在时限内，但超过九成线 %d %s：建议再删 %d %s，给强调和停顿留余量"
                  % (total - target, unit, total - target, unit))
        else:
            print("  → 在九成线以内，余量约 %s" % fmt_seconds((cap - total) / rate * 60))

    print("分段（原文顺序；超时先从标了「最长」的段落删修饰）：")
    longest = sorted(range(len(rows)), key=lambda i: rows[i][2], reverse=True)[:2]
    multi = len(set(r[0] for r in rows)) > 1
    last_section = None
    for i, (section, para, n) in enumerate(rows, start=1):
        if multi and section != last_section:
            print("  【%s】" % section)
            last_section = section
        plain = BRACKET.sub("", para)
        head = plain if len(plain) <= 16 else plain[:16] + "…"
        flag = "  ← 最长" if (i - 1) in longest and len(rows) > 2 else ""
        print("  第 %d 段  %d %s  约 %s  占 %d%%  %s%s"
              % (i, n, unit, fmt_seconds(n / rate * 60), round(n * 100 / total), head, flag))

    marks = "、".join("[%s] %d 处" % (k, v) for k, v in placeholders.items())
    if any(placeholders.values()) or other:
        print("方括号占位：%s、其他 %d 处——不计入字数，替换成正文后请重新计时" % (marks, other))
        if placeholders["待核"]:
            print("  [待核] 的论据上场前必须查到出处；查不到就换成逻辑论证或删掉，不能硬说")
    return code


class FriendlyParser(argparse.ArgumentParser):
    """参数写错时按约定用退出码 1，而不是 argparse 默认的 2（2 留给文件问题）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/speech_timer.py lilun.txt 250 --limit 3:00）" % message,
              file=sys.stderr)
        sys.exit(1)


def build_parser():
    p = FriendlyParser(
        description="辩论稿计时：按实测语速估算时长，给出九成线和每段字数。",
        epilog="退出码：0 正常；1 参数或内容有误；2 文件读不了；3 超出时限；130 手动中断。")
    p.add_argument("file", help="稿子的 .txt 文件路径；写 - 表示从标准输入读")
    p.add_argument("rate", nargs="?", help="实测语速（每分钟字数），如 250；也可以用 --rate")
    p.add_argument("--rate", dest="rate_opt", help="实测语速（每分钟字数）")
    p.add_argument("--limit", help="主办方给的时限，如 3:00、180、3分钟")
    p.add_argument("--language", choices=("zh", "en"), default="zh",
                   help="zh 中文等效字/分钟（默认，也用于混合稿）；en 英文词/分钟")
    return p


def resolve_rate(args):
    raw = args.rate or args.rate_opt
    if args.rate and args.rate_opt and args.rate != args.rate_opt:
        raise InputError(1, "语速写了两次且不一致（%s 和 %s），只保留一个" % (args.rate, args.rate_opt))
    if raw is None:
        default = 150 if args.language == "en" else 250
        unit = "词" if args.language == "en" else "字"
        print("[待确认] 没给语速，先按 %d %s/分钟估算；请拿稿子读一分钟、按同口径计数后再跑一次" % (default, unit))
        return default
    try:
        rate = float(raw)
    except ValueError:
        raise InputError(1, "语速「%s」不是数字：填每分钟实读计数；中文用字数，英文模式用词数" % raw)
    lo, hi = RATE_RANGE[args.language]
    if not lo <= rate <= hi:
        unit = "词" if args.language == "en" else "字"
        raise InputError(1, "语速 %s %s/分钟超出接受范围 %d–%d：确认模式和单位，拿稿子实读一分钟后重填" % (raw, unit, lo, hi))
    return rate


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        rate = resolve_rate(args)
        limit = parse_limit(args.limit) if args.limit else None
        if limit is not None and not 10 <= limit <= 1800:
            raise InputError(1, "时限 %s 秒不合常理：一般是 60–480 秒，检查单位" % limit)
        text = read_text(args.file)
        return analyse(text, rate, limit, args.language)
    except InputError as exc:
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有改动任何文件", file=sys.stderr)
        sys.exit(130)
