#!/usr/bin/env python3
"""PPT 体检：只读 .pptx、不改文件，只用 Python 标准库。

按放映顺序列出每页标题（标题串读），并找出：没用标题占位符的页、标题为空或还是母版默认文字、
主题词式标题、过长标题、偏满的页、被自动缩小的文字、低于字号底线的文字；最后统计全套手动指定的字体和颜色。
字号按文字片段、同段落默认值、同文本体对应列表层级的顺序读取；未确定字号会单列，
不解析母版、版式或主题，也不代替实际渲染验收。阈值是经验值，可以按需要改。

用法：
  python3 pptx_check.py 汇报.pptx         字号底线 18 磅（上台投影讲的）
  python3 pptx_check.py 汇报.pptx 14      发出去读的片子，底线放到 14 磅
  python3 pptx_check.py 汇报.pptx --json  标准输出为 JSON，含来源哈希和定位证据

退出码：
  0    检查范围内没发现问题，仍须核对覆盖范围和渲染
  3    发现问题，已逐页列出
  1    参数错误：没给文件，或字号底线不是正数
  2    文件读不了：不存在、不是 .pptx（旧版 .ppt、Keynote、加了密码）、文件损坏
  130  手动中断（Ctrl+C）
"""

import hashlib
import io
import json
import math
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
USAGE = "用法：python3 pptx_check.py 汇报.pptx [字号底线，默认 18] [--json]"
FONT_LIMITATIONS = [
    "仅检查幻灯片 XML 中 a:r 与 a:fld 的非空文字；按 rPr、同段落 pPr/defRPr、同文本体 lstStyle 对应 lvlNpPr/defRPr 取字号。",
    "不解析母版、版式和主题的继承字号；未确定不等于字号合格。",
    "不计算实际渲染字号、字体替换、图表/图片内文字、重叠或裁切；自动缩小另列提示，仍需在演示软件中逐页复核。",
]


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


def xml_locations(root):
    """为元素建立可复核的页内路径（同名兄弟序号从 1 开始）。"""
    prefixes = {A: "a:", P: "p:"}
    paths, parents = {}, {}

    def label(el):
        for namespace, prefix in prefixes.items():
            if el.tag.startswith(namespace):
                return prefix + el.tag[len(namespace):]
        return el.tag

    def visit(el, path):
        paths[el] = path
        counts = Counter()
        for child in el:
            counts[child.tag] += 1
            parents[child] = el
            visit(child, f"{path}/{label(child)}[{counts[child.tag]}]")

    visit(root, label(root) + "[1]")
    return paths, parents


def font_size_records(sld, no, part):
    """每个实际文字片段只记一次；默认样式本身不是文字。"""
    paths, parents = xml_locations(sld)
    records = []
    for paragraph in sld.iter(A + "p"):
        body = parents.get(paragraph)
        while body is not None and body.tag not in (P + "txBody", A + "txBody"):
            body = parents.get(body)
        ppr = paragraph.find(A + "pPr")
        paragraph_default = ppr.find(A + "defRPr") if ppr is not None else None
        level = ppr.get("lvl", "0") if ppr is not None else "0"
        list_default = None
        if body is not None and re.fullmatch(r"[0-8]", level):
            list_default = body.find(f"{A}lstStyle/{A}lvl{int(level) + 1}pPr/{A}defRPr")
        for piece in paragraph:
            if piece.tag not in (A + "r", A + "fld"):
                continue
            text = piece.findtext(A + "t") or ""
            if not text.strip():
                continue
            record = {
                "slide": no, "part": part,
                "kind": "field" if piece.tag == A + "fld" else "run",
                "text": text, "text_path": paths[piece] + "/a:t[1]",
                "font_size_pt": None, "font_source": None, "size_path": None,
                "unresolved_reason": "not_set_in_supported_slide_layers",
            }
            candidates = (("run", piece.find(A + "rPr")),
                          ("paragraph", paragraph_default), ("list_style", list_default))
            for source, props in candidates:
                if props is None or props.get("sz") is None:
                    continue
                record["font_source"] = source
                record["size_path"] = paths[props] + "/@sz"
                try:
                    size = int(props.get("sz"))
                    if size <= 0:
                        raise ValueError
                except ValueError:
                    record["unresolved_reason"] = "invalid_explicit_size"
                else:
                    record["font_size_pt"] = size / 100
                    record["unresolved_reason"] = None
                break
            records.append(record)
    return records


def check_details(path, min_pt):
    """返回可序列化报告；只读输入，使用同一份字节计算哈希和检查内容。"""
    if not math.isfinite(min_pt) or min_pt <= 0:
        raise ValueError("字号底线必须是有限正数")
    fonts, colors, issues, titles, records = Counter(), Counter(), [], [], []
    unreadable_slides = 0
    data = Path(path).read_bytes()

    def issue(code, no, message, evidence=None):
        issues.append({"code": code, "slide": no, "message": message,
                       "evidence": evidence or []})

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        order = slide_order(z)
        if not order:
            raise CheckError("%s 里没有找到任何幻灯片，确认它是 PowerPoint 或 WPS 演示文稿" % path)
        for no, name in enumerate(order, 1):
            try:
                sld = ET.fromstring(z.read(name))
            except (ET.ParseError, KeyError):
                unreadable_slides += 1
                titles.append({"slide": no, "part": name, "text": "（这一页读不了）"})
                issue("unreadable_slide", no, f"第 {no} 页：内容读不了（XML 损坏或缺失），已跳过，建议另存一份再查")
                continue
            title, body = None, []
            for sp in sld.iter(P + "sp"):
                ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                kind = ph.get("type") if ph is not None else None
                if kind in ("title", "ctrTitle"):
                    title = text_of(sp)
                elif kind not in ("dt", "ftr", "sldNum") and sp.find(P + "txBody") is not None:   # 日期、页脚、页码不算正文
                    body += [t for t in (text_of(p) for p in sp.iter(A + "p")) if t]
            titles.append({"slide": no, "part": name,
                           "text": title if title else ("（标题是空的）" if title == "" else "（没有标题占位符）")})
            if title is None:
                issue("missing_title_placeholder", no, f"第 {no} 页：没用标题占位符，各页标题位置会跳，大纲视图里也看不到")
            elif title == "":
                issue("empty_title", no, f"第 {no} 页：标题占位符是空的，写一句带判断的结论")
            elif title.strip() in DEFAULT_TITLES:
                issue("default_title", no, f"第 {no} 页：标题还是母版的默认文字，写一句带判断的结论")
            elif len(re.sub(r"\s", "", title)) <= 8 and not re.search(r"\d", title):
                issue("topic_title", no, f"第 {no} 页：标题「{title}」像主题词，改成一句带判断的结论")
            elif sum(1 if ord(ch) > 0x2E7F else 0.5 for ch in title) > 30:           # 汉字按 1、英文数字按半个字算
                issue("long_title", no, f"第 {no} 页：标题太长（约 {len(title)} 字符），可能超过两行")
            chars = sum(len(re.sub(r"\s", "", t)) for t in body)
            if len(body) > 6 or chars > 120:
                issue("dense_body", no, f"第 {no} 页：正文 {len(body)} 段、{chars} 字，偏满，考虑拆页或挪进备注")
            for fit in sld.iter(A + "normAutofit"):
                scale = fit.get("fontScale")
                if scale and scale.isdigit():
                    issue("auto_shrink", no, f"第 {no} 页：文字被自动缩小到 {int(scale) / 1000:g}%，内容放不下了")
            slide_records = font_size_records(sld, no, name)
            records.extend(slide_records)
            small = [r for r in slide_records if r["font_size_pt"] is not None and r["font_size_pt"] < min_pt]
            if small:
                sizes = sorted({r["font_size_pt"] for r in small})
                issue("small_font", no,
                      f"第 {no} 页：{len(small)} 处文字小于 {min_pt:g} 磅（{'、'.join(f'{s:g}' for s in sizes)} 磅），"
                      f"例「{small[0]['text'][:12]}」", small)
            for f in sld.iter():
                if f.tag in (A + "latin", A + "ea") and not f.get("typeface", "+").startswith("+"):
                    fonts[f.get("typeface")] += 1
            colors.update(c.get("val") for c in sld.iter(A + "srgbClr") if c.get("val"))
    resolved = [r for r in records if r["font_size_pt"] is not None]
    counts = Counter(r["font_source"] for r in resolved)
    return {
        "schema_version": 1,
        "source": {"name": Path(path).name, "sha256": hashlib.sha256(data).hexdigest()},
        "min_font_pt": min_pt, "slide_count": len(titles), "titles": titles,
        "status": "issues_found" if issues else "no_issues_in_checked_scope",
        "issues": issues,
        "font_size_coverage": {
            "text_piece_count": len(records), "resolved_count": len(resolved),
            "unresolved_count": len(records) - len(resolved),
            "small_count": sum(r["font_size_pt"] < min_pt for r in resolved),
            "unreadable_slide_count": unreadable_slides,
            "source_counts": {key: counts[key] for key in ("run", "paragraph", "list_style")},
            "text_pieces": records,
        },
        "fonts": dict(fonts), "colors": dict(colors), "limitations": FONT_LIMITATIONS,
    }


def check(path, min_pt):
    """兼容原 API：返回 (标题列表, 问题列表, 字体计数, 颜色计数)。"""
    report = check_details(path, min_pt)
    return ([t["text"] for t in report["titles"]], [i["message"] for i in report["issues"]],
            Counter(report["fonts"]), Counter(report["colors"]))


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
        if not math.isfinite(min_pt) or min_pt <= 0:
            raise ValueError("字号底线必须是有限正数，收到「%s」" % argv[1])
    return argv[0], min_pt


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in args
    if json_mode:
        args.remove("--json")
    try:
        source, min_pt = parse_args(args)
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
        report = check_details(path, min_pt)
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

    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return EXIT_FOUND if report["issues"] else EXIT_OK
    titles = [t["text"] for t in report["titles"]]
    problems = [i["message"] for i in report["issues"]]
    fonts, colors = Counter(report["fonts"]), Counter(report["colors"])
    print(f"共 {len(titles)} 页；字号底线 {min_pt:g} 磅\n\n标题串读（只看这一列，应该能读懂整个故事）：")
    for no, title in enumerate(titles, 1):
        print(f"  {no:>2}. {title}")
    print("\n问题：" if problems else "\n检查范围内未发现问题；仍需人工核对未确定字号与渲染。")
    for line in problems:
        print("  " + line)
    coverage = report["font_size_coverage"]
    print(f"\n字号覆盖：{coverage['text_piece_count']} 处非空文字片段；"
          f"已确定 {coverage['resolved_count']} 处，未确定 {coverage['unresolved_count']} 处，"
          f"低于底线 {coverage['small_count']} 处；读不了 {coverage['unreadable_slide_count']} 页。")
    print("字号来源：" + "、".join(f"{label} {coverage['source_counts'][key]} 处" for key, label in
                                    (("run", "文字片段"), ("paragraph", "段落默认"), ("list_style", "列表层级默认"))))
    for limitation in report["limitations"]:
        print("范围：" + limitation)
    print(f"\n全套手动指定的字体 {len(fonts)} 种：{'、'.join(fonts) or '无（都跟主题走）'}")
    print(f"全套手动指定的颜色 {len(colors)} 种：{'、'.join(c for c, _ in colors.most_common(8)) or '无（都跟主题走）'}")
    return EXIT_FOUND if problems else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(EXIT_INTERRUPTED)
