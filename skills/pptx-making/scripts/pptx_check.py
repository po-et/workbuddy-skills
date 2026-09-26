#!/usr/bin/env python3
"""PPT 体检：只读 .pptx、不改文件，只用 Python 标准库。

按放映顺序列出每页标题（标题串读），并找出：没用标题占位符的页、标题为空或还是母版默认文字、
主题词式标题、过长标题、偏满的页、被自动缩小的文字、低于字号底线的文字；最后统计全套手动指定的字体和颜色。
只统计页面上显式设置的字号，从母版继承的不算；阈值是经验值，可以按需要改。

用法：
  python3 pptx_check.py 汇报.pptx         字号底线 18 磅（上台投影讲的）
  python3 pptx_check.py 汇报.pptx 14      发出去读的片子，底线放到 14 磅

退出码：
  0    没发现问题
  3    发现问题，已逐页列出
  1    参数错误：没给文件，或字号底线不是正数
  2    文件读不了：不存在、不是 .pptx（旧版 .ppt、Keynote、加了密码）、文件损坏
  130  手动中断（Ctrl+C）
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_MIN_PT = 18.0   # 字号底线：投影讲的 18，发出去读的可放到 14
DEFAULT_TITLES = ("Click to edit Master title style", "单击此处编辑母版标题样式")
EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_FOUND, EXIT_INTERRUPTED = 0, 1, 2, 3, 130
USAGE = "用法：python3 pptx_check.py 汇报.pptx [字号底线，默认 18]"


class CheckError(Exception):
    """文件读不了时抛出，带中文说明。"""


def slide_order(z):
    """按 presentation.xml 里的顺序排页；文件名里的编号不一定等于放映顺序。"""
    names = z.namelist()
    by_number = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                       key=lambda n: int(re.findall(r"\d+", n)[-1]))
    if "ppt/presentation.xml" in names and "ppt/_rels/presentation.xml.rels" in names:
        try:
            rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))}
            ids = [s.get(R + "id") for s in ET.fromstring(z.read("ppt/presentation.xml")).iter(P + "sldId")]
            order = [rels[i].lstrip("/") if rels[i].startswith("/") else "ppt/" + rels[i] for i in ids]
            if all(n in names for n in order):
                return order
        except (ET.ParseError, KeyError, AttributeError):
            pass  # 目录信息坏了就按文件名编号排，并照常体检
    return by_number


def text_of(el):
    return " ".join("".join(t.text or "" for t in p.iter(A + "t")) for p in el.iter(A + "p")).strip()


def check(path, min_pt):
    """返回 (标题列表, 问题列表, 字体计数, 颜色计数)。"""
    fonts, colors, problems, titles = Counter(), Counter(), [], []
    with zipfile.ZipFile(path) as z:
        order = slide_order(z)
        if not order:
            raise CheckError("%s 里没有找到任何幻灯片，确认它是 PowerPoint 或 WPS 演示文稿" % path)
        for no, name in enumerate(order, 1):
            try:
                sld = ET.fromstring(z.read(name))
            except (ET.ParseError, KeyError):
                titles.append("（这一页读不了）")
                problems.append(f"第 {no} 页：内容读不了（XML 损坏或缺失），已跳过，建议另存一份再查")
                continue
            title, body = None, []
            for sp in sld.iter(P + "sp"):
                ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                kind = ph.get("type") if ph is not None else None
                if kind in ("title", "ctrTitle"):
                    title = text_of(sp)
                elif kind not in ("dt", "ftr", "sldNum") and sp.find(P + "txBody") is not None:   # 日期、页脚、页码不算正文
                    body += [t for t in (text_of(p) for p in sp.iter(A + "p")) if t]
            titles.append(title if title else ("（标题是空的）" if title == "" else "（没有标题占位符）"))
            if title is None:
                problems.append(f"第 {no} 页：没用标题占位符，各页标题位置会跳，大纲视图里也看不到")
            elif title == "":
                problems.append(f"第 {no} 页：标题占位符是空的，写一句带判断的结论")
            elif title.strip() in DEFAULT_TITLES:
                problems.append(f"第 {no} 页：标题还是母版的默认文字，写一句带判断的结论")
            elif len(re.sub(r"\s", "", title)) <= 8 and not re.search(r"\d", title):
                problems.append(f"第 {no} 页：标题「{title}」像主题词，改成一句带判断的结论")
            elif sum(1 if ord(ch) > 0x2E7F else 0.5 for ch in title) > 30:           # 汉字按 1、英文数字按半个字算
                problems.append(f"第 {no} 页：标题太长（约 {len(title)} 字符），可能超过两行")
            chars = sum(len(re.sub(r"\s", "", t)) for t in body)
            if len(body) > 6 or chars > 120:
                problems.append(f"第 {no} 页：正文 {len(body)} 段、{chars} 字，偏满，考虑拆页或挪进备注")
            for fit in sld.iter(A + "normAutofit"):
                scale = fit.get("fontScale")
                if scale and scale.isdigit():
                    problems.append(f"第 {no} 页：文字被自动缩小到 {int(scale) / 1000:g}%，内容放不下了")
            small = []
            for r in sld.iter(A + "r"):
                rpr = r.find(A + "rPr")
                sz = rpr.get("sz") if rpr is not None else None
                if sz and sz.isdigit() and int(sz) / 100 < min_pt:
                    small.append((r, int(sz) / 100))
            if small:
                sizes = sorted({s for _, s in small})
                problems.append(f"第 {no} 页：{len(small)} 处文字小于 {min_pt:g} 磅（{'、'.join(f'{s:g}' for s in sizes)} 磅），"
                                f"例「{(small[0][0].findtext(A + 't') or '')[:12]}」")
            for f in sld.iter():
                if f.tag in (A + "latin", A + "ea") and not f.get("typeface", "+").startswith("+"):
                    fonts[f.get("typeface")] += 1
            colors.update(c.get("val") for c in sld.iter(A + "srgbClr"))
    return titles, problems, fonts, colors


def parse_args(argv):
    if not argv:
        raise ValueError("没给要检查的 .pptx 文件。" + USAGE)
    if argv[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(EXIT_OK)
    if len(argv) > 2:
        raise ValueError("参数太多。" + USAGE)
    min_pt = DEFAULT_MIN_PT
    if len(argv) == 2:
        try:
            min_pt = float(argv[1])
        except ValueError:
            raise ValueError("字号底线要写数字，收到「%s」。%s" % (argv[1], USAGE))
        if min_pt <= 0:
            raise ValueError("字号底线必须是正数，收到「%s」" % argv[1])
    return argv[0], min_pt


def main(argv=None):
    try:
        source, min_pt = parse_args(sys.argv[1:] if argv is None else argv)
    except ValueError as exc:
        sys.stderr.write("参数错误：%s\n" % exc)
        return EXIT_ARGS

    path = Path(source)
    suffix = path.suffix.lower()
    try:
        if not path.exists():
            raise CheckError("找不到文件：%s（检查路径；文件名有空格时用引号包住）" % source)
        if path.is_dir():
            raise CheckError("%s 是文件夹，请给出具体的 .pptx 文件" % source)
        if suffix == ".ppt":
            raise CheckError("%s 是旧版 .ppt：先在 PowerPoint 或 WPS 演示里另存为 .pptx 再查" % source)
        if suffix == ".key":
            raise CheckError("%s 是 Keynote 文件：先导出为 .pptx 再查" % source)
        titles, problems, fonts, colors = check(path, min_pt)
    except CheckError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE
    except zipfile.BadZipFile:
        sys.stderr.write("读取失败：%s 不是有效的 .pptx（可能是旧版 .ppt 改了扩展名、加了打开密码，或文件已损坏）；"
                         "另存为 .pptx、取消密码后再查\n" % source)
        return EXIT_FILE
    except PermissionError:
        sys.stderr.write("读取失败：没有读取权限：%s\n" % source)
        return EXIT_FILE
    except OSError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE

    print(f"共 {len(titles)} 页；字号底线 {min_pt:g} 磅\n\n标题串读（只看这一列，应该能读懂整个故事）：")
    for no, title in enumerate(titles, 1):
        print(f"  {no:>2}. {title}")
    print("\n问题：" if problems else "\n没发现问题。")
    for line in problems:
        print("  " + line)
    print(f"\n全套手动指定的字体 {len(fonts)} 种：{'、'.join(fonts) or '无（都跟主题走）'}")
    print(f"全套手动指定的颜色 {len(colors)} 种：{'、'.join(c for c, _ in colors.most_common(8)) or '无（都跟主题走）'}")
    return EXIT_FOUND if problems else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(EXIT_INTERRUPTED)
