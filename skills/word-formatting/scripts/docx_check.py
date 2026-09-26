#!/usr/bin/env python3
"""Word 排版体检：只读 .docx、不改文件，只用 Python 标准库（3.6+）。

统计样式使用、标题样式、自动目录、题注域、交叉引用、分节和页码，并找出手打编号、手打题注、
手打目录行、连续空格、像标题却没用标题样式的段落、连续空段落。表格、文本框和目录条目里的段落不查。
它是启发式检查，结果逐条人工确认。

用法：
  python3 docx_check.py 论文.docx
.doc 老格式、.wps、PDF 不支持：先在 Word 或 WPS 里另存为 .docx。

退出码：0 体检跑完（有没有问题看输出）；1 参数错误；2 文件读不了或不是有效的 .docx；130 手动中断。
"""

import argparse
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_INTERRUPT = 0, 1, 2, 130
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUM = re.compile(r"\s*(第[一二三四五六七八九十百\d]+[章节条]|[一二三四五六七八九十]+、|[（(][一二三四五六七八九十\d]+[）)]"
                 r"|\d{1,2}(\.\d{1,2})*(?:[.、．]|\s+(?=[一-鿿])))")


def zh(message):
    for en, cn in (("the following arguments are required: ", "缺少必填参数："),
                   ("unrecognized arguments: ", "不认识的参数：")):
        message = message.replace(en, cn)
    return message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % zh(message))
        sys.exit(EXIT_ARGS)


class DocError(Exception):
    """读不了文件或文件不是有效的 .docx；消息可直接给用户看。"""


def has(el, tag):
    return el.find(".//" + W + tag) is not None


def fields(el):
    """域代码：自动目录 TOC、题注 SEQ、页码 PAGE、交叉引用 REF 都是域"""
    return " ".join([t.text or "" for t in el.iter(W + "instrText")]
                    + [f.get(W + "instr", "") for f in el.iter(W + "fldSimple")])


def load(path):
    """返回 (document 根节点, 样式 id→名称, 页眉页脚里的域代码)。"""
    base = os.path.basename(path)
    if not os.path.exists(path):
        raise DocError("找不到文件：%s（检查路径和文件名）" % path)
    if os.path.isdir(path):
        raise DocError("%s 是文件夹，不是 .docx 文件" % path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".doc":
        raise DocError("不支持 .doc 老格式：在 Word 里「另存为」.docx 再体检")
    if ext in (".wps", ".pdf", ".odt", ".rtf", ".txt"):
        raise DocError("只支持 .docx：%s 文件先在 Word 或 WPS 里另存为 .docx" % ext)
    if base.startswith("~$"):
        raise DocError("%s 是 Word 打开文档时生成的临时锁文件，不是文档本身；请选不带 ~$ 的那个文件" % base)
    try:
        with zipfile.ZipFile(path) as z:
            doc = ET.fromstring(z.read("word/document.xml"))
            names = {}
            if "word/styles.xml" in z.namelist():
                for s in ET.fromstring(z.read("word/styles.xml")).iter(W + "style"):
                    n = s.find(W + "name")
                    names[s.get(W + "styleId")] = n.get(W + "val") if n is not None else s.get(W + "styleId")
            margins = " ".join(fields(ET.fromstring(z.read(n))) for n in z.namelist()
                               if re.match(r"word/(header|footer)\d*\.xml$", n))
    except PermissionError:
        raise DocError("没有权限读取：%s（文件是否正在被别的程序独占？）" % path)
    except zipfile.BadZipFile:
        raise DocError("%s 不是有效的 .docx：可能是 .doc 改了扩展名、文件已损坏，或设了打开密码；"
                       "在 Word 里另存为新的 .docx（有密码先取消）再试" % path)
    except KeyError:
        raise DocError("%s 里没有 word/document.xml，不像 Word 文档" % path)
    except ET.ParseError as exc:
        raise DocError("%s 的 XML 解析失败（%s）：在 Word 里另存一份新的 .docx 再试" % (path, exc))
    return doc, names, margins


def analyze(doc, names, margins):
    styles, issues, blank = Counter(), {}, 0
    boxed = {id(q) for tag in ("tbl", "txbxContent") for box in doc.iter(W + tag) for q in box.iter(W + "p")}
    for p in doc.iter(W + "p"):
        ppr = p.find(W + "pPr")
        sid = ppr.find(W + "pStyle") if ppr is not None else None
        style = names.get(sid.get(W + "val"), sid.get(W + "val")) if sid is not None else "Normal"
        text = "".join(t.text or "" for t in p.iter(W + "t"))
        if not text.strip():
            blank = 0 if has(p, "drawing") or has(p, "br") or has(p, "sectPr") else blank + 1
            if blank == 3:
                issues.setdefault("连续 3 个以上空段落（用回车撑版面或分页）", []).append("空行")
            continue
        blank = 0
        styles[style] += 1
        if style.lower().startswith("toc") or id(p) in boxed:   # 目录条目、表格和文本框里的段落不查
            continue
        found = []
        if re.search(r"(…{2,}|\.{4,}|·{4,})\s*\d+\s*$", text):
            found.append("手打目录行（点线加页码）")
        else:
            if NUM.match(text) and (ppr is None or ppr.find(W + "numPr") is None):
                found.append("手打编号（编号是打上去的字，不会自动更新）")
            if re.match(r"\s*[图表]\s*\d", text) and not re.search(r"\bSEQ\s", fields(p)):
                found.append("手打题注（顺序一变编号就错）")
            bold = all(r.find(W + "rPr/" + W + "b") is not None for r in p.iter(W + "r")
                       if "".join(t.text or "" for t in r.iter(W + "t")).strip())
            if (not re.match(r"(?i)heading|标题|title", style) and len(text) <= 30
                    and not re.search(r"[。；，：.;,:]$", text.strip()) and (bold or NUM.match(text))):
                found.append("像标题却没用标题样式（导航窗格和自动目录里看不到）")
        if re.search(r"[ 　]{2,}|^[ 　]", text):
            found.append("连续空格或行首空格（手动对齐、手动缩进）")
        for kind in found:
            issues.setdefault(kind, []).append(text.strip()[:20])

    all_fields = fields(doc)
    runs = [r for r in doc.iter(W + "r") if has(r, "t")]
    direct = sum(1 for r in runs if r.find(W + "rPr/" + W + "rFonts") is not None or r.find(W + "rPr/" + W + "sz") is not None)
    sects = list(doc.iter(W + "sectPr"))
    restart = sum(1 for s in sects if s.find(W + "pgNumType") is not None and s.find(W + "pgNumType").get(W + "start"))
    heads = sum(n for s, n in styles.items() if re.match(r"(?i)heading|标题", s))
    out = []
    out.append("样式使用（段落数）：" + " | ".join("%s %d" % (s, n) for s, n in styles.most_common(8)))
    out.append("标题样式段落 %d；自动目录 %s；题注域 %d 个；交叉引用 %d 个"
               % (heads, "有" if "TOC" in all_fields else "没有", all_fields.count("SEQ"),
                  len(re.findall(r"(?<![A-Z])REF", all_fields))))
    out.append("分节 %d 个（页码重新起算 %d 个，首页不同 %d 个）；手动分页符 %d 个；页眉页脚里有页码域：%s"
               % (len(sects), restart, sum(has(s, "titlePg") for s in sects),
                  sum(1 for b in doc.iter(W + "br") if b.get(W + "type") == "page"),
                  "是" if re.search(r"(?<![A-Z])PAGE(?![A-Z])", margins) else "否"))
    out.append("直接设了字体或字号的文字段 %d/%d（比例高，说明格式没走样式）" % (direct, len(runs)))
    for kind, hits in issues.items():
        out.append("[%s] %d 处，例：" % (kind, len(hits)) + "、".join("「%s」" % h for h in hits[:3]))
    if not issues:
        out.append("没发现手动排版的痕迹")
    return out


def main(argv=None):
    ap = Parser(description="Word 排版体检（只读 .docx）。退出码：0 跑完，1 参数错误，2 文件读不了，130 中断")
    ap.add_argument("docx", help="要体检的 .docx 文件")
    args = ap.parse_args(argv)
    try:
        doc, names, margins = load(args.docx)
    except DocError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE
    for line in analyze(doc, names, margins):
        print(line)
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
