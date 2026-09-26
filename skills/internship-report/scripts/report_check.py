#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实习报告提交前自查：字数、四段结构、疑似敏感信息、没填完的占位符。

只用 Python 标准库，不联网，只读不写。

  python3 report_check.py 实习报告.docx --target 5000 --words "客户甲,项目代号X"

支持 .docx（直接读，不用另存）、.txt、.md；.doc 请先另存为 .docx 或 .txt。
检查只做提醒：疑似敏感不等于一定敏感，最终由你和单位指导人确认。
退出码：0 检查完成（结果看输出）；1 参数有误；2 文件读不了；130 手动中断。
"""

import argparse
import html
import os
import re
import sys
import zipfile

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_INTERRUPT = 0, 1, 2, 130

SECTIONS = (
    ("一、实习单位与岗位", ("岗位",)),
    ("二、实习内容", ("实习内容", "工作内容", "主要工作")),
    ("三、收获与反思", ("收获", "体会", "反思")),
    ("四、问题与建议", ("建议",)),
)
PATTERNS = (
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("邮箱", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("金额", re.compile(r"\d+(?:\.\d+)?\s*[万亿]?元")),
)
BUSINESS_WORDS = ("营收", "收入", "销售额", "利润", "成本", "毛利", "GMV", "转化率",
                  "日活", "月活", "用户数", "会员数", "客单价", "订单量")
PLACEHOLDER = re.compile(r"\[(?:待补|待确认)[^\]]*\]")
CJK = re.compile(r"[一-鿿]")
MAX_HITS_SHOWN = 30
NEAR_DIGIT = 15


class InputError(Exception):
    """参数有误，退出码 1。"""


def read_docx(path):
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError):
        raise IOError("%s 不是有效的 .docx（.doc 或 WPS 格式请先另存为 .docx 或 .txt）" % path)
    except OSError as exc:
        raise IOError("读不了 %s：%s" % (path, exc.strerror or exc))
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def read_text(path):
    if not os.path.isfile(path):
        raise IOError("找不到文件：%s" % path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".doc":
        raise IOError("不支持老式 .doc：请在 Word 或 WPS 里另存为 .docx 或 .txt 再检查")
    if ext == ".docx":
        return read_docx(path)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IOError("读不了 %s：%s" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise IOError("文件编码认不出来：请另存为 UTF-8 的 .txt")


def mask(kind, value):
    """等长打码，保证打码后原来的位置不变。"""
    if kind == "手机号":
        return value[:3] + "****" + value[-4:]
    if kind == "身份证号":
        return value[:3] + "*" * (len(value) - 5) + value[-2:]
    if kind == "邮箱":
        name, _, domain = value.partition("@")
        return name[:1] + "*" * (len(name) - 1) + "@" + domain
    return value


def mask_line(line):
    for kind in ("手机号", "身份证号", "邮箱"):
        pattern = dict(PATTERNS)[kind]
        line = pattern.sub(lambda m, k=kind: mask(k, m.group(0)), line)
    return line


def excerpt(masked, start, end, width=18):
    return masked[max(0, start - width):end + width].strip()


def scan(text, words):
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        masked = mask_line(line)
        for kind, pattern in PATTERNS:
            for m in pattern.finditer(line):
                hits.append((no, kind, excerpt(masked, m.start(), m.end())))
        biz = None
        for w in BUSINESS_WORDS:  # 经营数据字样后面 15 个字以内跟着数字才算
            for m in re.finditer(re.escape(w), line):
                if re.search(r"\d", line[m.end():m.end() + NEAR_DIGIT]):
                    biz = (w, m.start())
                    break
            if biz:
                break
        if biz:
            hits.append((no, "经营数据（%s）" % biz[0], excerpt(masked, biz[1], biz[1] + len(biz[0]))))
        for w in words:
            idx = line.find(w)
            if idx >= 0:
                hits.append((no, "自定义敏感词", excerpt(masked, idx, idx + len(w))))
    return hits


def build_report(path, text, target, words):
    out = []
    add = out.append
    cjk = len(CJK.findall(text))
    visible = len(re.sub(r"\s", "", text))
    add("实习报告自查：%s" % os.path.basename(path))
    add("")
    add("字数")
    add("- 汉字 {:,} 个；不含空白的字符 {:,} 个（学校按 Word「字数统计」算的，以 Word 为准）".format(cjk, visible))
    if target:
        diff = cjk - target
        pct = diff * 100.0 / target
        flag = "✓ 在 ±10% 内" if abs(pct) <= 10 else "⚠ 超出 ±10%"
        add("- 目标 {:,}：{}{:,}（{:+.0f}%）{}".format(target, "多 " if diff >= 0 else "差 ", abs(diff), pct, flag))
    add("")
    add("结构（按学校常见四段式；学校有模板就以模板为准）")
    for title, keys in SECTIONS:
        ok = any(k in text for k in keys)
        add("- %s %s" % ("✓" if ok else "✗", title) + ("" if ok else "（没找到「%s」）" % "」「".join(keys)))
    add("")
    hits = scan(text, words)
    add("疑似敏感信息（逐条确认：能删就删，要留就脱敏或先问单位指导人）")
    if not hits:
        add("- 没扫到手机号、身份证号、邮箱、金额和经营数据字样；客户名、项目代号请用 --words 自查")
    for no, kind, snippet in hits[:MAX_HITS_SHOWN]:
        add("- 第 %d 段 %s：%s" % (no, kind, snippet))
    if len(hits) > MAX_HITS_SHOWN:
        add("- ……另有 %d 处" % (len(hits) - MAX_HITS_SHOWN))
    add("")
    holes = PLACEHOLDER.findall(text)
    add("没填完的占位符")
    if holes:
        for h in sorted(set(holes), key=holes.index):
            add("- %s ×%d" % (h, holes.count(h)))
    else:
        add("- 没有 [待补] / [待确认]")
    return "\n".join(out) + "\n"


def build_parser():
    p = argparse.ArgumentParser(
        description="实习报告提交前自查：字数、四段结构、疑似敏感信息、没填完的占位符（只读）。",
        epilog="退出码：0 检查完成；1 参数有误；2 文件读不了；130 手动中断。")
    p.add_argument("file", help="报告文件：.docx、.txt 或 .md")
    p.add_argument("--target", type=int, help="学校要求的字数，如 5000")
    p.add_argument("--words", default="", help="自己要查的敏感词，逗号分隔，如 客户甲,项目代号X")
    return p


def run(argv):
    args = build_parser().parse_args(argv)
    if args.target is not None and not 100 <= args.target <= 100000:
        raise InputError("--target 应在 100–100000 之间，收到 %d" % args.target)
    words = [w.strip() for w in re.split(r"[,，、]", args.words) if w.strip()]
    text = read_text(args.file)
    if not text.strip():
        raise InputError("%s 里没有读到文字（是不是扫描件或图片？）" % args.file)
    sys.stdout.write(build_report(args.file, text, args.target, words))
    return EXIT_OK


def main(argv=None):
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except InputError as exc:
        print("输入有误：%s" % exc, file=sys.stderr)
        return EXIT_INPUT
    except IOError as exc:
        print("文件读不了：%s" % exc, file=sys.stderr)
        return EXIT_IO
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(main())
