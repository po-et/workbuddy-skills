#!/usr/bin/env python3
"""转写稿候选句粗筛：按关键词标出可能的决议、待办、未决、数字、分歧，供人工逐条核对。

关键词只能召回候选，不等于结论；没命中的行照样要通读。
只读原稿、不改原稿、不联网，只用 Python 标准库。

用法：
  python3 tag_candidates.py transcript.txt
  python3 tag_candidates.py meeting.srt --out candidates.md

支持 .txt / .md / .srt / .vtt；编码依次尝试 UTF-8、UTF-16（带 BOM）、GB18030。
退出码：0 成功；1 参数错误；2 读写文件失败；3 文件里没有可读文字；130 用户中断。
"""

import argparse
import os
import re
import sys
import tempfile
from collections import Counter

# 标签 -> (说明, 关键词)。关键词沿用原一行命令，并补了几个常见说法。
TAGS = (
    ("决", "决议候选", r"定了|就这么|拍板|就按|决定|确定下来"),
    ("办", "待办候选", r"负责|我来|你来|跟进|盯一下|截止|之前|下周|月底|周[一二三四五六日天]|明天"),
    ("疑", "未决候选", r"先不|先放|回头|再议|再说|待定|请示|问一下|没定"),
    ("数", "数字待核", r"\d|百分之|[零一二两三四五六七八九十]+点[零一二两三四五六七八九十]+"
                       r"|(?:[两三四五六七八九十百千万]|[零一二两三四五六七八九十百千万]{2,})"
                       r"(?:个|条|项|次|页|份|台|名|位|天|周|月|号|点|小时|分钟|秒|万|千|元|块|人|倍)"),
    ("争", "分歧候选", r"不同意|反对|顾虑|不太行|风险"),
)
TAG_RE = [(tag, label, re.compile(pat)) for tag, label, pat in TAGS]

TS_RE = re.compile(r"^\s*\[?(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\]?\s*")
CUE_RE = re.compile(r"^\s*(\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3}\s*-->\s*")
SPEAKER_RE = re.compile(r"^((?:说话人|发言人|讲话人|Speaker|SPEAKER|speaker)\s*\d+"
                        r"|[^\s：:，,。！？!?]{1,12})[：:]\s*(.*)$")
NUMBERED_SPEAKER_RE = re.compile(r"^(说话人|发言人|讲话人|Speaker|SPEAKER|speaker)\s*\d+$")


class ArgError(Exception):
    """参数问题，退出码 1。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认退出码是 2，这里统一改成 1
        raise ArgError(message)


def read_text(path):
    """按常见编码依次尝试读取；都失败就抛 OSError，由调用方给友好提示。"""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",)
    else:
        encodings = ("utf-8-sig", "gb18030")
    for enc in encodings:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise OSError("无法识别文件编码（试过 %s）" % " / ".join(encodings))


def parse_lines(text):
    """逐行拆出 (行号, 时间戳, 说话人, 正文)。SRT/VTT 的时间轴行、序号行不算正文。"""
    rows = []
    cue_ts = ""
    lines = text.splitlines()
    subtitle = any(CUE_RE.match(x) for x in lines)  # 字幕格式才把纯数字行当序号跳过
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s == "WEBVTT" or (subtitle and s.isdigit()):
            continue
        if CUE_RE.match(s):
            cue_ts = s.split("-->")[0].strip().replace(",", ".")
            continue
        ts = cue_ts
        m = TS_RE.match(s)
        if m:
            ts = m.group(1)
            s = s[m.end():]
        speaker = ""
        m = SPEAKER_RE.match(s)
        if m and not m.group(1).isdigit():
            speaker, s = m.group(1), m.group(2)
        if s:
            rows.append((no, ts, speaker, s))
    return rows


def build_report(path, rows, encoding):
    speakers = Counter(sp for _, _, sp, _ in rows if sp)
    has_ts = any(ts for _, ts, _, _ in rows)
    counts = Counter()
    hits = []
    for no, ts, sp, body in rows:
        tags = [tag for tag, _, rx in TAG_RE if rx.search(body)]
        if tags:
            counts.update(tags)
            hits.append((no, ts, sp, body, tags))

    out = ["# 候选句粗筛：%s" % os.path.basename(path), ""]
    spk_text = "、".join("%s ×%d" % kv for kv in speakers.most_common()) or "未识别到"
    out.append("有文字的行 %d｜时间戳：%s｜编码：%s｜说话人：%s"
               % (len(rows), "有" if has_ts else "无", encoding, spk_text))
    out.append("> 关键词只召回候选，不是结论：每条回原稿核对；没命中的 %d 行靠通读。"
               % (len(rows) - len(hits)))
    out.append("")
    out.append("按类计数：" + "　".join(
        "【%s】%s %d" % (tag, label, counts.get(tag, 0)) for tag, label, _ in TAG_RE))
    out.append("")
    for no, ts, sp, body, tags in hits:
        head = "L%d" % no + (" [%s]" % ts if ts else "")
        mark = "".join("【%s】" % t for t in tags)
        who = "%s：" % sp if sp else ""
        out.append("- %s %s %s%s" % (head, mark, who, body))

    tips = []
    numbered = [sp for sp in speakers if NUMBERED_SPEAKER_RE.match(sp)]
    if numbered:
        tips.append("说话人是编号（%s），先请用户确认各编号对应谁；确认前保留原标签，不猜。"
                    % "、".join(sorted(numbered)))
    if not speakers:
        tips.append("没识别到说话人标签：负责人只能从称呼与应答推断，推断依据要列给用户确认。")
    if not has_ts:
        tips.append("原稿没有时间戳：每条决议、待办改附一句原文关键短语，方便回查。")
    if counts.get("数"):
        tips.append("【数】行逐个和上下文核对，「十五/五十」「一点五/一五」这类对不上的标【?】。")
    if tips:
        out += ["", "## 下一步提示"] + ["- " + t for t in tips]
    return "\n".join(out) + "\n"


def write_atomic(path, content):
    """先写同目录临时文件，再 os.replace，避免中断时留下半截文件。"""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".md", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    parser = Parser(description="转写稿候选句粗筛（决议/待办/未决/数字/分歧），只读原稿。")
    parser.add_argument("transcript", help="转写稿文件：.txt / .md / .srt / .vtt")
    parser.add_argument("--out", help="把结果写进这个 Markdown 文件（默认打印到屏幕）")
    try:
        args = parser.parse_args(argv)
    except ArgError as exc:
        print("参数错误：%s\n用法：python3 tag_candidates.py 转写稿.txt [--out 结果.md]" % exc,
              file=sys.stderr)
        return 1

    if args.out and os.path.abspath(args.out) == os.path.abspath(args.transcript):
        print("参数错误：--out 不能和原稿是同一个文件（本脚本不改原稿）", file=sys.stderr)
        return 1
    try:
        text, encoding = read_text(args.transcript)
    except FileNotFoundError:
        print("读不到文件：%s（检查路径和文件名）" % args.transcript, file=sys.stderr)
        return 2
    except IsADirectoryError:
        print("%s 是文件夹，请指定其中的转写稿文件" % args.transcript, file=sys.stderr)
        return 2
    except OSError as exc:
        print("读取失败：%s。请把转写稿另存为 UTF-8 文本后重试。" % exc, file=sys.stderr)
        return 2

    rows = parse_lines(text)
    if not rows:
        print("文件里没有可读的文字（可能只有时间轴或导出失败），请重新导出转写稿。", file=sys.stderr)
        return 3

    report = build_report(args.transcript, rows, encoding)
    if args.out:
        try:
            write_atomic(args.out, report)
        except OSError as exc:
            print("写不了输出文件 %s：%s（换一个存在且有写权限的目录）"
                  % (args.out, exc.strerror or exc), file=sys.stderr)
            return 2
        print("已写入 %s（候选 %s 行）" % (args.out, report.count("\n- L")))
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，原稿未改动。", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:  # 例如输出被 head 截断
        sys.exit(0)
