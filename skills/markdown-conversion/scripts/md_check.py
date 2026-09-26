#!/usr/bin/env python3
"""Markdown 转换前预检与机械清理（只用 Python 标准库，不需要 pandoc）。

用法：
  python3 md_check.py in.md                          只检查，不改任何文件
  python3 md_check.py in.md --fix                    清理后另存为 in.clean.md，原文件不动
  python3 md_check.py in.md --fix -o out.md          清理后写到 out.md
  python3 md_check.py in.md --encoding gbk --fix -o in.utf8.md
                                                     GBK 文件按 GBK 读，清理后存成 UTF-8
  python3 md_check.py docs                           检查整个文件夹（递归找 .md），最后给汇总
  python3 md_check.py - < in.md                      从标准输入读（只检查）

检查项（对应 SKILL.md 的清理规则与转换前检查清单）：
  编码        不是 UTF-8 时停下并给出转换办法
  不可见字符  U+00A0 不间断空格、U+200B 零宽空格、正文中间的 U+FEFF、U+00AD 软连字符、行首 U+3000 全角空格
  行尾空格    两个以上 = Markdown 强制换行
  标题        没从 # 起、跳级；整行加粗冒充标题
  伪列表      「1、」「（1）」「•」开头
  表格        管道表各行列数与表头不一致
  图片        相对路径按 md 所在目录找不到；SVG、WebP 进 PDF 容易失败；替代文字只有「截图」「image」
代码块（``` 或 ~~~ 围起来的部分）里只查不可见字符，不查标题、列表和表格。

--fix 只做「只动格式不动字」的三类清理：不可见字符、行尾空格、行首全角空格。
标题、列表、断行、引号要人工判断，只报告不改。写文件先写临时文件再替换，失败不会留下半截文件。

退出码（多个文件时取最严重的一个）：
  0    没发现问题（--fix 时指清理后已没有要人工处理的问题）
  3    发现问题，已逐条列出
  1    参数错误
  2    文件读写失败，或不是 UTF-8（附转换办法）
  130  手动中断（Ctrl+C）
"""

import argparse
import codecs
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_FOUND, EXIT_INTERRUPTED = 0, 1, 2, 3, 130

# 用 chr() 写不可见字符，源码里不出现它们本身
NBSP, ZWSP, SHY, BOM, IDSP = chr(0x00A0), chr(0x200B), chr(0x00AD), chr(0xFEFF), chr(0x3000)

INVISIBLE = (
    (NBSP, "U+00A0 不间断空格", " "),
    (ZWSP, "U+200B 零宽空格", ""),
    (SHY, "U+00AD 软连字符", ""),
)
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+\S")
BOLD_LINE_RE = re.compile(r"^\s*(\*\*|__)([^*_]{1,40})\1\s*$")
PSEUDO_LIST_RE = re.compile(r"^\s*(\d+、|（\d+）|•)")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
GENERIC_ALT = {"image", "img", "pic", "picture", "图片", "截图", "图"}
LINE_END_RE = re.compile(r"(\r\n|\n|\r)$")


class Parser(argparse.ArgumentParser):
    """参数错误时用退出码 1 和中文提示。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用法示例：python3 md_check.py in.md --fix\n" % message)
        sys.exit(EXIT_ARGS)


class InputError(Exception):
    """读不了输入：路径、权限或编码问题。"""


def read_source(source, encoding):
    if source == "-":
        data, label, base = sys.stdin.buffer.read(), "标准输入", Path.cwd()
    else:
        path = Path(source)
        if not path.exists():
            raise InputError("找不到文件：%s（检查路径；文件名有空格时用引号包住）" % source)
        if path.is_dir():
            raise InputError("%s 是文件夹，请给出具体的 .md 文件" % source)
        try:
            data = path.read_bytes()
        except PermissionError:
            raise InputError("没有读取权限：%s" % source)
        label, base = source, path.resolve().parent
    try:
        return data.decode(encoding), label, base
    except UnicodeDecodeError:
        hint = ""
        if encoding.lower().replace("-", "") in ("utf8", "utf8sig"):
            try:
                data.decode("gb18030")
                hint = ("\n看起来是 GBK/GB18030 编码，先转成 UTF-8：\n"
                        "  python3 md_check.py %s --encoding gbk --fix -o 新文件名.md\n"
                        "  或 iconv -f GBK -t UTF-8 %s > 新文件名.md" % (label, label))
            except UnicodeDecodeError:
                hint = "\n也不像 GBK：可能是 Word、PDF 等二进制文件，pandoc 只认 UTF-8 文本"
        shown = "UTF-8" if encoding.lower().replace("-", "") in ("utf8", "utf8sig") else encoding
        raise InputError("%s 不是 %s 文本%s" % (label, shown, hint))


def split_ending(line):
    m = LINE_END_RE.search(line)
    return (line[:m.start()], m.group(1)) if m else (line, "")


def column_count(row):
    row = INLINE_CODE_RE.sub("x", row.strip())
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    return len(re.split(r"(?<!\\)\|", row))


def check(text, base):
    """返回 {类别: [说明, ...]}；类别名带「可自动清理」或「需人工」标记。"""
    found = {}

    def add(kind, msg):
        found.setdefault(kind, []).append(msg)

    lines = text.splitlines()
    if lines and lines[0].startswith(BOM):
        lines[0] = lines[0][1:]
    fence = None
    last_level = 0
    table_cols = None
    table_start = 0
    prev_blank = True
    for no, raw in enumerate(lines, 1):
        for ch, name, _ in INVISIBLE:
            if ch in raw:
                add("可自动清理：" + name, "第 %d 行 ×%d" % (no, raw.count(ch)))
        if BOM in raw:
            add("可自动清理：U+FEFF 正文中间的 BOM", "第 %d 行 ×%d" % (no, raw.count(BOM)))
        if raw.startswith(IDSP):
            add("可自动清理：行首 U+3000 全角空格", "第 %d 行" % no)
        stripped = raw.rstrip(" \t")
        if stripped != raw:
            tail = len(raw) - len(stripped)
            add("可自动清理：行尾空格", "第 %d 行%s" % (no, "（%d 个，等于强制换行）" % tail if tail >= 2 else ""))

        m = FENCE_RE.match(raw)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not raw.strip()[len(m.group(1)):].strip():
                fence = None
            prev_blank = False
            continue
        if m:
            fence = m.group(1)
            table_cols = None
            continue

        h = HEADING_RE.match(raw)
        if h:
            level = len(h.group(1))
            if last_level == 0 and level > 1:
                add("需人工：标题没从 # 起", "第 %d 行第一个标题是 %s" % (no, h.group(1)))
            elif last_level and level > last_level + 1:
                add("需人工：标题跳级", "第 %d 行 %s 前面最近的是 %s" % (no, h.group(1), "#" * last_level))
            last_level = level
        b = BOLD_LINE_RE.match(raw)
        if b and prev_blank:
            add("需人工：加粗的一行冒充标题", "第 %d 行「%s」→ 改成 # 标题" % (no, b.group(2).strip()))
        p = PSEUDO_LIST_RE.match(raw)
        if p:
            want = "- " if p.group(1) == "•" else "1. "
            add("需人工：伪列表", "第 %d 行以「%s」开头 → 改成「%s」" % (no, p.group(1), want))

        if TABLE_SEP_RE.match(raw) and "|" in raw and no >= 2 and "|" in lines[no - 2]:
            table_cols = column_count(lines[no - 2])
            table_start = no - 1
            if column_count(raw) != table_cols:
                add("需人工：表格列数不一致", "第 %d 行分隔行 %d 列，表头 %d 列" % (no, column_count(raw), table_cols))
        elif table_cols is not None:
            if "|" in raw and raw.strip():
                n = column_count(raw)
                if n != table_cols:
                    add("需人工：表格列数不一致", "第 %d 行 %d 列，表头（第 %d 行）%d 列" % (no, n, table_start, table_cols))
            else:
                table_cols = None

        for alt, target in IMAGE_RE.findall(raw):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
                continue
            local = unquote(target)
            path = (base / local).resolve() if not os.path.isabs(local) else Path(local)
            if not path.exists():
                add("需人工：图片找不到", "第 %d 行 %s（按 md 所在目录找）" % (no, target))
            if target.lower().endswith((".svg", ".webp")):
                add("需人工：SVG/WebP 图片", "第 %d 行 %s → 转 PDF 前先转成 PNG" % (no, target))
            if alt.strip().lower() in GENERIC_ALT:
                add("需人工：替代文字太笼统", "第 %d 行「%s」会变成图注 → 写成真正的说明" % (no, alt))
        prev_blank = not raw.strip()
    if fence:
        add("需人工：代码块没有闭合", "文件结尾仍在 %s 代码块里" % fence)
    return found


def clean(text):
    """只做格式清理，返回 (新文本, 统计)。"""
    stats = {"U+00A0 换成普通空格": 0, "删除 U+200B 零宽空格": 0, "删除 U+00AD 软连字符": 0,
             "删除 U+FEFF": 0, "删除行首全角空格": 0, "删除行尾空格（行）": 0, "其中原是强制换行（行）": 0}
    out = []
    for line in text.splitlines(keepends=True):
        body, end = split_ending(line)
        stats["U+00A0 换成普通空格"] += body.count(NBSP)
        stats["删除 U+200B 零宽空格"] += body.count(ZWSP)
        stats["删除 U+00AD 软连字符"] += body.count(SHY)
        stats["删除 U+FEFF"] += body.count(BOM)
        body = body.replace(NBSP, " ").replace(ZWSP, "").replace(SHY, "").replace(BOM, "")
        lead = len(body) - len(body.lstrip(IDSP))
        if lead:
            stats["删除行首全角空格"] += lead
            body = body[lead:]
        stripped = body.rstrip(" \t")
        if stripped != body:
            stats["删除行尾空格（行）"] += 1
            if len(body) - len(stripped) >= 2:
                stats["其中原是强制换行（行）"] += 1
            body = stripped
        out.append(body + end)
    return "".join(out), stats


def atomic_write(target, text):
    target = Path(target)
    if not target.parent.exists():
        raise OSError("输出目录不存在：%s" % target.parent)
    fd, tmp = tempfile.mkstemp(prefix="." + target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(target))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def report(found, label, total_lines):
    auto = {k: v for k, v in found.items() if k.startswith("可自动清理")}
    manual = {k: v for k, v in found.items() if k.startswith("需人工")}
    print("检查 %s（%d 行）" % (label, total_lines))
    if not found:
        print("没发现问题。转换后仍按 SKILL.md 的转换后检查清单核对。")
        return
    for kind, items in list(auto.items()) + list(manual.items()):
        shown = "；".join(items[:5]) + ("；等 %d 处" % len(items) if len(items) > 5 else "")
        print("  [%s] %s" % (kind, shown))
    if auto:
        print("「可自动清理」的几类加 --fix 处理（另存新文件，原文件不动）；「需人工」的要自己改。")
    if any(k == "需人工：图片找不到" for k in manual):
        print("提醒：pandoc 按运行目录找图片，到 md 所在目录运行，或加 --resource-path。")


def process_one(source, args):
    """检查（或清理）一个文件，返回退出码。"""
    try:
        text, label, base = read_source(source, args.encoding)
    except InputError as exc:
        sys.stdout.flush()
        sys.stderr.write("读取失败：%s\n" % exc)
        sys.stderr.flush()
        return EXIT_FILE
    total_lines = len(text.splitlines())
    found = check(text, base)

    if not args.fix:
        report(found, label, total_lines)
        return EXIT_FOUND if found else EXIT_OK

    cleaned, stats = clean(text)
    target = Path(args.output) if args.output else Path(source).with_name(
        Path(source).stem + ".clean" + (Path(source).suffix or ".md"))
    try:
        atomic_write(target, cleaned)
    except PermissionError:
        sys.stderr.write("写入失败：没有权限写入 %s 所在的目录（原文件未改）\n" % target)
        return EXIT_FILE
    except OSError as exc:
        sys.stderr.write("写入失败：%s（原文件未改）\n" % exc)
        return EXIT_FILE
    same = source != "-" and target.resolve() == Path(source).resolve()
    print("已清理并写入 %s%s：" % (target, "（覆盖了原文件）" if same else "（原文件未改）"))
    if args.encoding.lower().replace("-", "") not in ("utf8", "utf8sig"):
        print("  编码：按 %s 读入，已存成 UTF-8" % args.encoding)
    if not any(stats.values()):
        print("  没有需要清理的不可见字符和行尾空格")
    for name, n in stats.items():
        if n:
            print("  %s：%d" % (name, n))
    if stats["其中原是强制换行（行）"]:
        print("  提醒：原来靠行尾两个空格换行的地方，真要换行请在行尾加反斜杠 \\")
    remaining = {k: v for k, v in check(cleaned, base).items() if k.startswith("需人工")}
    if remaining:
        print("仍需人工处理：")
        for kind, items in remaining.items():
            print("  [%s] %s" % (kind, "；".join(items[:5]) + ("；等 %d 处" % len(items) if len(items) > 5 else "")))
        return EXIT_FOUND
    print("清理后没有需要人工处理的问题。")
    return EXIT_OK


def expand(paths):
    """文件夹递归展开成 .md 文件（跳过 --fix 生成的 *.clean.md），按路径排序。"""
    out = []
    for item in paths:
        path = Path(item)
        if item != "-" and path.is_dir():
            out.extend(str(p) for p in sorted(path.rglob("*.md"))
                       if p.is_file() and not p.name.endswith(".clean.md"))
        else:
            out.append(item)
    return out


def main(argv=None):
    parser = Parser(description="Markdown 转换前预检与机械清理（只用标准库）")
    parser.add_argument("files", nargs="+", metavar="file",
                        help="要检查的 .md 文件或文件夹（文件夹递归找 .md）；- 表示从标准输入读（只检查）")
    parser.add_argument("--fix", action="store_true", help="清理不可见字符、行尾空格、行首全角空格后另存")
    parser.add_argument("-o", "--output", help="--fix 的输出文件，默认 原名.clean.md；只能在处理一个文件时用")
    parser.add_argument("--encoding", default="utf-8-sig", help="输入编码，默认 UTF-8；GBK 文件写 gbk")
    args = parser.parse_args(argv)

    try:
        codecs.lookup(args.encoding)
    except LookupError:
        parser.error("不认识的编码「%s」，常用的是 utf-8、gbk" % args.encoding)
    if args.output and not args.fix:
        parser.error("-o 只能和 --fix 一起用")
    if "-" in args.files and len(args.files) > 1:
        parser.error("- （标准输入）只能单独使用")
    if args.files == ["-"] and args.fix and not args.output:
        parser.error("从标准输入读时，--fix 要用 -o 指定输出文件")

    targets = expand(args.files)
    if not targets:
        sys.stderr.write("没找到 .md 文件：%s\n" % "、".join(args.files))
        return EXIT_ARGS
    if args.output and len(targets) > 1:
        parser.error("-o 只能在处理一个文件时用，现在有 %d 个" % len(targets))

    codes = []
    for i, source in enumerate(targets):
        if i:
            print("")
        codes.append(process_one(source, args))
    if len(targets) > 1:
        print("\n共 %d 个文件：没问题 %d 个，有问题 %d 个，读写失败 %d 个"
              % (len(codes), codes.count(EXIT_OK), codes.count(EXIT_FOUND), codes.count(EXIT_FILE)))
    if EXIT_FILE in codes:
        return EXIT_FILE
    return EXIT_FOUND if EXIT_FOUND in codes else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（未写入任何文件）\n")
        sys.exit(EXIT_INTERRUPTED)
