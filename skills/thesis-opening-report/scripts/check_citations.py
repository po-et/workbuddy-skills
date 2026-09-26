#!/usr/bin/env python3
"""开题报告引用核对（顺序编码制）：正文引了、表里没有；表里有、正文没引；表里重复编号、缺号；
编号是否按正文首次引用的顺序排。只读，不改文件，只用 Python 标准库（3.6+）。

用法：
  python3 check_citations.py 开题报告.txt
  python3 check_citations.py 开题报告.docx
约定：正文用 [1]、[2-4]、[1,3] 标注（全角括号、逗号、连接号也认）；参考文献表放在最后，
以单独一行「参考文献」开头（前面可带「六、」「6」这类序号），每条以 [序号] 开头。
方括号里 1000 以上的数字按年份处理，不当作引用编号。

退出码：0 编号全部对上；1 参数错误；2 文件读不了；3 发现不一致；4 没找到参考文献表；130 手动中断。
"""

import argparse
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_FOUND, EXIT_NOREFS, EXIT_INTERRUPT = 0, 1, 2, 3, 4, 130
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DASH = "-–—~～－"
GROUP = re.compile(r"[\[［]\s*(\d+(?:\s*[" + DASH + r"]\s*\d+)?(?:\s*[,，、]\s*\d+(?:\s*[" + DASH + r"]\s*\d+)?)*)\s*[\]］]")
HEADING = re.compile(r"^\s*(?:[0-9一二三四五六七八九十]+\s*[、.．]?\s*)?参考文献\s*(?:[（(][^）)]*[）)])?\s*[:：]?\s*$")
ENTRY = re.compile(r"^\s*[\[［]\s*(\d+)\s*[\]］]")


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


def read_docx(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
    except zipfile.BadZipFile:
        raise IOError("%s 不是有效的 .docx（可能是 .doc 改了扩展名、文件损坏或设了打开密码）；"
                      "在 Word 里另存为 .docx 或纯文本 .txt 再试" % path)
    except KeyError:
        raise IOError("%s 里没有正文（word/document.xml），不像 Word 文档" % path)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise IOError("%s 的正文 XML 解析失败（%s）；另存为纯文本 .txt 再试" % (path, exc))
    lines = []
    for p in root.iter(W + "p"):
        parts = []
        for node in p.iter():
            if node.tag == W + "t":
                parts.append(node.text or "")
            elif node.tag == W + "tab":
                parts.append("\t")
            elif node.tag in (W + "br", W + "cr"):
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines), "docx"


def read_text(path):
    if path.lower().endswith(".doc"):
        raise IOError("不支持 .doc 老格式：在 Word 里另存为 .docx 或纯文本 .txt 再试")
    try:
        if path.lower().endswith(".docx"):
            return read_docx(path)
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise IOError("找不到文件：%s（检查路径和文件名）" % path)
    except IsADirectoryError:
        raise IOError("%s 是文件夹，不是文件" % path)
    except PermissionError:
        raise IOError("没有权限读取：%s（文件是否正在被 Word 占用？）" % path)
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), "UTF-16"
    for enc, label in (("utf-8-sig", "UTF-8"), ("gb18030", "GB18030/GBK")):
        try:
            return raw.decode(enc), label
        except UnicodeDecodeError:
            continue
    raise IOError("无法识别 %s 的编码：在 Word 里另存为纯文本并选 UTF-8 编码再试" % path)


def expand(group, ignored):
    """把「2-4,7」展开成 [2,3,4,7]；按出现顺序返回。"""
    out = []
    for piece in re.split(r"[,，、]", group):
        piece = piece.strip()
        if not piece:
            continue
        m = re.match(r"^(\d+)\s*[" + DASH + r"]\s*(\d+)$", piece)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a >= 1000 or b >= 1000:
                ignored.append(piece)
                continue
            if a > b:
                ignored.append(piece + "（起止颠倒）")
                continue
            out.extend(range(a, b + 1))
        else:
            n = int(piece)
            if n >= 1000:
                ignored.append(piece)
                continue
            out.append(n)
    return out


def check(text):
    lines = text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if HEADING.match(line):
            idx = i
    if idx is None:
        return None
    body = "\n".join(lines[:idx])
    refs = lines[idx + 1:]

    ignored, order = [], []
    for g in GROUP.findall(body):
        order.extend(expand(g, ignored))
    cited = set(order)
    listed_seq = [int(m.group(1)) for m in (ENTRY.match(l) for l in refs) if m]
    listed = set(listed_seq)
    dup = sorted(n for n in listed if listed_seq.count(n) > 1)
    gaps = sorted(set(range(1, max(listed) + 1)) - listed) if listed else []

    jumps, seen_max, seen = [], 0, set()
    for n in order:
        if n in seen:
            continue
        seen.add(n)
        if n > seen_max + 1:
            jumps.append((n, seen_max))
        seen_max = max(seen_max, n)

    return {
        "hanzi": len(re.findall("[一-龥]", body)),
        "cited": cited, "listed": listed, "entries": len(listed_seq),
        "missing": sorted(cited - listed), "uncited": sorted(listed - cited),
        "dup": dup, "gaps": gaps, "jumps": jumps, "ignored": ignored,
    }


def fmt(nums):
    return "无" if not nums else "、".join("[%d]" % n for n in nums)


def main(argv=None):
    ap = Parser(description="开题报告引用核对（顺序编码制，只读）。退出码：0 对上，1 参数错误，2 读不了，3 不一致，4 没找到参考文献表，130 中断")
    ap.add_argument("file", help="稿子：纯文本 .txt 或 .docx")
    args = ap.parse_args(argv)

    try:
        text, enc = read_text(args.file)
    except IOError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE

    res = check(text)
    if res is None:
        sys.stderr.write("没找到参考文献表：在参考文献列表前单独起一行，只写「参考文献」四个字（可带「六、」这类序号），再跑一次\n")
        return EXIT_NOREFS
    if not res["entries"]:
        sys.stderr.write("找到了「参考文献」标题，但下面没有以 [序号] 开头的条目；本脚本只核对顺序编码制（[1] 作者. 题名…）\n")
        return EXIT_NOREFS

    print("读取 %s（%s）" % (args.file, enc))
    print("正文汉字数: %d" % res["hanzi"])
    print("正文引用编号 %d 个，参考文献表 %d 条" % (len(res["cited"]), res["entries"]))
    print("正文引了、表里没有: " + fmt(res["missing"]))
    print("表里有、正文没引: " + fmt(res["uncited"]))
    print("表里编号重复: " + fmt(res["dup"]))
    print("表里缺号: " + fmt(res["gaps"]))
    if res["jumps"]:
        shown = "；".join("[%d] 首次出现时，最大只引到 [%d]" % j for j in res["jumps"][:5])
        print("没按首次引用顺序编号: %s（学院用著者-出版年制的忽略这一条）" % shown)
    else:
        print("没按首次引用顺序编号: 无")
    if res["ignored"]:
        print("[提示] 这些方括号内容没当作引用：%s（年份或起止颠倒的范围）" % "、".join(res["ignored"][:5]))
    bad = res["missing"] or res["uncited"] or res["dup"] or res["gaps"] or res["jumps"]
    print("结论：" + ("编号全部对上" if not bad else "有不一致，逐条改完再跑一次"))
    return EXIT_FOUND if bad else EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
