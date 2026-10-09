#!/usr/bin/env python3
"""主持稿体检：按每分钟约 220 字估算每段时长，对照段落标题里写的时长，并找出念不顺的长句和空串词。

用法：
  python3 scripts/host_timer.py script.txt                  # 默认 220 字/分钟
  python3 scripts/host_timer.py script.txt --rate 200       # 庄重场合语速更慢
  python3 scripts/host_timer.py script.txt --total 8:00     # 主持人说话总时间的上限
  python3 scripts/host_timer.py - < script.txt              # 从标准输入读

稿子格式：每段以【段落名 · 约 1 分钟】这样的标题行开头（标题里写了时长就会自动对照）；
「A：」「B：」「男：」「女：」等角色标记、（停两秒）这类括号里的舞台提示、[姓名] 这类方括号占位都不计入字数。

退出码：0 体检完成且没有超时；1 参数或内容有误；2 文件读不了；
        3 有段落超出标题里写的时长，或全稿超出 --total；130 手动中断（Ctrl+C）。
只用 Python 标准库。
"""

import argparse
import math
import re
import sys
from pathlib import Path

HAN = re.compile("[\u3400-\u4dbf\u4e00-\u9fff]")
DIGIT = re.compile("[0-9\uff10-\uff19]")
WORD = re.compile(r"[A-Za-z]+")
BRACKET = re.compile(r"\[[^\[\]\n]*\]|［[^［］\n]*］")
STAGE = re.compile(r"（[^（）\n]*）|\([^()\n]*\)")
ROLE = re.compile(r"(?:(?<=^)|(?<=\s))(?:主持人)?[A-DＡ-Ｄ甲乙丙丁男女合]\s*[：:]")
HEADER = re.compile(r"^\s*【([^】]*)】\s*(.*)$")
BREATH_SPLIT = re.compile(r"[，,。！？!?；;：:、…—\n]+")
DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(?:[–\-~～至到]\s*(\d+(?:\.\d+)?))?\s*(分钟|分|秒)")
EMPTY_LINES = ("下面有请下一个节目", "感谢精彩表演", "感谢精彩的表演", "让我们欢迎下一个节目")
TOLERANCE = 1.10              # 超出标注时长 10% 以内不算超时


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FriendlyParser(argparse.ArgumentParser):
    """参数写错时用退出码 1（2 留给文件问题）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/host_timer.py script.txt --total 8:00）" % message,
              file=sys.stderr)
        sys.exit(1)


def spoken(text):
    """去掉占位、舞台提示和角色标记，只留要念出来的字。"""
    return ROLE.sub(" ", STAGE.sub("", BRACKET.sub("", text)))


def count_units(text):
    return len(HAN.findall(text)) + len(DIGIT.findall(text)) + 2 * len(WORD.findall(text))


def fmt_seconds(sec):
    sec = int(round(sec))
    return "%d 分 %02d 秒" % (sec // 60, sec % 60) if sec >= 60 else "%d 秒" % sec


def parse_time(raw):
    """解析并拒绝零、负数、非有限或溢出的总时长。"""
    try:
        seconds = _parse_time(raw)
        valid = math.isfinite(seconds) and seconds > 0
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise InputError(1, "总时长必须是大于 0 的有限时长：写成 8:00、480、8分钟 或 八分钟")
    return seconds


def _parse_time(raw):
    """8:00、480、8分钟、八分钟、90秒 → 秒；不大于 30 的纯数字按分钟理解。"""
    s = raw.strip().lower().replace("：", ":").replace(" ", "")
    m = re.fullmatch(r"([一二两三四五六七八九十])分(?:钟)?(半)?", s)   # 口语：八分钟、两分半
    if m:
        return ("一二三四五六七八九十".find(m.group(1).replace("两", "二")) + 1) * 60 + (30 if m.group(2) else 0)
    m = re.fullmatch(r"(\d+):([0-5]?\d)", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)(?:分钟|分|min|m))?(?:(\d+)(?:秒|s|sec))?", s)
    if m and (m.group(1) or m.group(2)):
        return round(float(m.group(1) or 0) * 60 + int(m.group(2) or 0))
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        v = float(s)
        return round(v * 60) if v <= 30 else round(v)
    raise InputError(1, "时长「%s」看不懂：写成 8:00、480、8分钟 或 八分钟" % raw)


def declared_seconds(title):
    """从段落标题里读出标注的时长上限（秒）。「1 分 30 秒」「1:30」「1–2 分钟」（取 2 分钟）；没写就返回 None。"""
    m = re.search(r"(\d+)\s*[:：]\s*([0-5]\d)", title)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.search(r"(\d+)\s*分(?:钟)?\s*(\d+)\s*秒", title)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = DURATION.search(title)
    if not m:
        return None
    upper = float(m.group(2) or m.group(1))
    return upper * 60 if m.group(3) in ("分钟", "分") else upper


def read_text(path):
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        p = Path(path)
        if not p.exists():
            raise InputError(2, "找不到文件 %s：检查路径，或把稿子另存成 .txt 再试" % path)
        if p.is_dir():
            raise InputError(2, "%s 是文件夹，请给出稿子文件的路径" % path)
        if p.suffix.lower() in (".doc", ".docx", ".pages", ".pdf", ".wps", ".ppt", ".pptx"):
            raise InputError(2, "%s 不是纯文本：请另存为 .txt（UTF-8），或把正文粘贴进一个 .txt 文件" % p.name)
        try:
            data = p.read_bytes()
        except OSError as exc:
            raise InputError(2, "读不了 %s（%s）：检查文件权限，或换个位置另存一份" % (path, exc.strerror or exc))
    if data[:2] == b"PK":
        raise InputError(2, "这是压缩格式的文档（多半是 .docx），请另存为纯文本 .txt")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise InputError(2, "文件编码认不出来：请在编辑器里「另存为」UTF-8 编码的 .txt")


def analyse(text, rate, total_limit, breath):
    segments = []                    # [标题, 起始行号, [(行号, 行文本)]]
    for no, line in enumerate(text.splitlines(), start=1):
        m = HEADER.match(line)
        if m:
            segments.append([m.group(1).strip(), no, []])
            line = m.group(2)
        if line.strip():
            if not segments:
                segments.append(["开头（没有【】标题）", no, []])
            segments[-1][2].append((no, line))

    total = sum(count_units(spoken(l)) for _, _, lines in segments for _, l in lines)
    if total == 0:
        raise InputError(1, "没有要念的正文（占位、舞台提示和【】标题不计入）：请先把稿子写出来")

    code = 0
    print("按 %d 字/分钟估算（汉字和数字各算 1 字；角色标记、括号里的舞台提示、[ ] 占位不计入）" % rate)
    print("全稿 %d 字，主持人开口约 %s" % (total, fmt_seconds(total / rate * 60)))
    if total_limit is not None:
        cap = int(total_limit / 60 * rate)
        if total > cap:
            print("  → 超出给定的 %s（上限 %d 字）%d 字：先删主持人自己的串词和可选互动，不压缩核心环节"
                  % (fmt_seconds(total_limit), cap, total - cap))
            code = 3
        else:
            print("  → 在给定的 %s 以内，还能容纳约 %d 字" % (fmt_seconds(total_limit), cap - total))

    print("分段：")
    for title, _, lines in segments:
        n = sum(count_units(spoken(l)) for _, l in lines)
        est = n / rate * 60
        want = declared_seconds(title)
        verdict = ""
        if want:
            if est > want * TOLERANCE:
                verdict = "  → 标注 %s，超出 %s，删约 %d 字" % (
                    fmt_seconds(want), fmt_seconds(est - want), n - int(want / 60 * rate))
                code = 3
            elif est < want * 0.5:
                verdict = "  → 标注 %s，实际不到一半：补内容，或把标注改短" % fmt_seconds(want)
            else:
                verdict = "  → 标注 %s，合适" % fmt_seconds(want)
        print("  【%s】 %d 字，约 %s%s" % (title, n, fmt_seconds(est), verdict))

    notes = []
    for _, _, lines in segments:
        for no, line in lines:
            for piece in BREATH_SPLIT.split(spoken(line)):
                k = count_units(piece)
                if k > breath:
                    notes.append("第 %d 行 一口气 %d 字：「%s」→ 中间加停顿，或拆成两句" % (no, k, piece.strip()[:24]))
            for phrase in EMPTY_LINES:
                if phrase in line:
                    notes.append("第 %d 行 空串词「%s」→ 补一句承上（上个环节的具体亮点）、一句看点、一个人名" % (no, phrase))
    if notes:
        print("需要处理：")
        for n in notes:
            print("  " + n)
    holes = sum(len(BRACKET.findall(l)) for _, _, lines in segments for _, l in lines)
    if holes:
        print("方括号占位 %d 处：姓名、职务、奖项等交付前按主办方名单逐字替换，替换后再跑一次" % holes)
    return code


def main(argv=None):
    p = FriendlyParser(description="主持稿体检：分段计时、对照标注时长、找长句和空串词。",
                       epilog="退出码：0 完成且没超时；1 参数或内容有误；2 文件读不了；3 有超时；130 手动中断。")
    p.add_argument("file", help="主持稿 .txt 路径；写 - 表示从标准输入读")
    p.add_argument("--rate", type=float, default=220, help="每分钟字数，默认 220；庄重场合可设 200")
    p.add_argument("--total", help="主持人开口总时间的上限，如 8:00")
    p.add_argument("--breath", type=int, default=20, help="两个停顿之间超过多少字提醒拆开，默认 20")
    args = p.parse_args(argv)
    try:
        if not 120 <= args.rate <= 360:
            raise InputError(1, "语速 %g 字/分钟不合常理（主持一般 180–260）：先掐表试读一分钟" % args.rate)
        if not 8 <= args.breath <= 60:
            raise InputError(1, "--breath 建议 15–30，现在是 %s" % args.breath)
        total_limit = parse_time(args.total) if args.total is not None else None
        return analyse(read_text(args.file), args.rate, total_limit, args.breath)
    except InputError as exc:
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有改动任何文件", file=sys.stderr)
        sys.exit(130)
