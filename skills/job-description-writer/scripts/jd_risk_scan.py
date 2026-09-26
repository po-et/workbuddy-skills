#!/usr/bin/env python3
"""招聘 JD 风险词粗筛：找出年龄、性别、婚育、户籍地域、外貌健康、学校标签六类高风险表述。

用法：
  python3 jd_risk_scan.py jd.txt          扫描 UTF-8 文本或 .md 文件
  python3 jd_risk_scan.py -  < jd.txt     从标准输入读（可接剪贴板：pbpaste | python3 jd_risk_scan.py -）

退出码：
  0    未命中（仍需人工通读）
  3    有命中，已逐条列出（命中不等于违规，每一处都要人工看）
  1    参数错误或内容为空
  2    文件读不了：不存在、没有权限、不是 UTF-8 文本
  130  手动中断（Ctrl+C）

只读，不改文件；只用 Python 标准库。结果只是风险提示，是否合规由 HR 或法务按现行规定判断。
"""

import argparse
import re
import sys
from pathlib import Path

# (类别, 正则, 改写方向)。词表与 SKILL.md「歧视性表述检查」的对照表一致。
RULES = (
    ("年龄", r"[\d一二三四五六七八九十]+\s*周?岁|年轻", "删除年龄限制，改写经验与能力，如「3–5 年相关经验」"),
    ("性别", r"男|女", "删除性别要求；确有体力要求的写具体条件，如「需搬运 20 公斤货物」"),
    ("婚育", r"已婚|未婚|已育|婚育|生育", "删除，面试中也不要问"),
    ("户籍地域", r"户口|户籍|籍贯", "删除；确因资质或政策需要，请 HR 核实依据后再写具体要求"),
    ("外貌健康", r"身高|形象|长相|乙肝", "删除；岗位确需证照的（如健康证），写证照名称"),
    ("学校标签", r"(?<!\d)(?:985|211)(?!\d)|名校", "改写为能力证据；学校标签缩窄人才池，也容易被视为学历歧视"),
)
COMPILED = tuple((cat, re.compile(pat), tip) for cat, pat, tip in RULES)
BINARY_SUFFIXES = {".docx", ".doc", ".pdf", ".pages", ".wps", ".xlsx", ".pptx"}

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_HITS, EXIT_INTERRUPTED = 0, 1, 2, 3, 130


class Parser(argparse.ArgumentParser):
    """参数错误时用退出码 1 和中文提示，而不是 argparse 默认的 2。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用法示例：python3 jd_risk_scan.py jd.txt\n" % message)
        sys.exit(EXIT_ARGS)


def read_text(source):
    """读取文件或标准输入；出错时抛出带中文说明的 OSError / ValueError。"""
    if source == "-":
        data = sys.stdin.buffer.read()
        label = "标准输入"
    else:
        path = Path(source)
        if path.suffix.lower() in BINARY_SUFFIXES:
            raise ValueError("%s 像是 Word、PDF 等二进制文件：请把 JD 正文复制进 UTF-8 的 .txt 或 .md 再扫" % source)
        if not path.exists():
            raise OSError("找不到文件：%s（检查路径；文件名有空格时用引号包住）" % source)
        if path.is_dir():
            raise OSError("%s 是文件夹，请给出具体的 JD 文件" % source)
        try:
            data = path.read_bytes()
        except PermissionError:
            raise OSError("没有读取权限：%s" % source)
        label = source
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("%s 不是 UTF-8 文本：请另存为 UTF-8 编码的 .txt 或 .md，或把正文粘贴进新文件再扫" % label)


def scan(text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for cat, pattern, tip in COMPILED:
            words = list(dict.fromkeys(m.group(0) for m in pattern.finditer(line)))
            if words:
                hits.append((lineno, cat, words, line.strip(), tip))
    return hits


def main(argv=None):
    parser = Parser(description="招聘 JD 风险词粗筛（只读，命中不等于违规）")
    parser.add_argument("file", help="JD 文件路径（UTF-8 文本或 .md），用 - 表示从标准输入读")
    args = parser.parse_args(argv)

    try:
        text = read_text(args.file)
    except (OSError, ValueError) as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE

    if not text.strip():
        sys.stderr.write("内容为空：没有可扫描的文字，请确认文件里有 JD 正文\n")
        return EXIT_ARGS

    hits = scan(text)
    total = len(text.splitlines())
    if not hits:
        print("共 %d 行，未命中风险词表。仍需人工通读：词表只覆盖常见字面表述。" % total)
        return EXIT_OK

    print("共 %d 行，命中 %d 处（命中不等于违规，逐条人工看）：" % (total, len(hits)))
    for lineno, cat, words, line, tip in hits:
        excerpt = line if len(line) <= 40 else line[:40] + "……"
        print("第 %d 行［%s］「%s」：%s" % (lineno, cat, "、".join(words), excerpt))
        print("    → %s" % tip)
    print("是否合规由 HR 或法务按现行规定判断；误报（如「女装」「品牌形象」）可忽略。")
    return EXIT_HITS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(EXIT_INTERRUPTED)
