#!/usr/bin/env python3
"""上新文案风险词粗筛：绝对化用语、医疗用语、功效宣称、绝对承诺，外加不违规但空泛的词。

用法：
  python3 risk_words.py copy.txt                      扫描 UTF-8 文本或 .md
  python3 risk_words.py copy.txt --extra 特效,神器     追加自己的词（逗号分隔）
  python3 risk_words.py - < copy.txt                  从标准输入读

退出码：
  0    没有命中
  3    有命中，已逐条列出（只是提醒，不代替人工和合规审核）
  1    参数错误或内容为空
  2    文件读不了：不存在、没有权限、不是 UTF-8 文本
  130  手动中断（Ctrl+C）

只读，不改文件；只用 Python 标准库。没命中不等于合规。
"""

import argparse
import sys
from pathlib import Path

# (类别, 词表, 处理建议)。前四类来自 SKILL.md「合规风险」一节，最后一类来自「常见错误」。
CATEGORIES = (
    ("绝对化用语", ("最佳", "最好", "最强", "最低", "第一", "顶级", "国家级", "100%", "全网"),
     "广告法对绝对化用语有限制：换成具体数字、检测结果或现场演示；需合规审核"),
    ("医疗用语", ("治疗", "治愈", "根治", "药用", "抗癌", "降血压", "降血糖"),
     "普通商品不说治疗、预防疾病，食品不暗示保健或治疗功能；需合规审核"),
    ("功效宣称", ("减肥", "祛斑", "美白", "防脱"),
     "化妆品等功效要有依据，部分类别需注册或备案；需合规审核"),
    ("绝对承诺", ("无副作用", "永久"),
     "删除，或改成有凭据、可兑现的具体说法；需合规审核"),
    ("空泛词", ("极致", "颠覆", "黑科技", "品质生活", "幸福感"),
     "不一定违规，但放在哪个产品上都成立：换成具体数字或现场演示"),
)
BINARY_SUFFIXES = {".docx", ".doc", ".pdf", ".pages", ".wps", ".xlsx", ".pptx"}
EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_HITS, EXIT_INTERRUPTED = 0, 1, 2, 3, 130


class Parser(argparse.ArgumentParser):
    """参数错误时用退出码 1 和中文提示。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用法示例：python3 risk_words.py copy.txt\n" % message)
        sys.exit(EXIT_ARGS)


def read_text(source):
    if source == "-":
        data, label = sys.stdin.buffer.read(), "标准输入"
    else:
        path = Path(source)
        if path.suffix.lower() in BINARY_SUFFIXES:
            raise ValueError("%s 像是 Word、PDF 等二进制文件：请把文案复制进 UTF-8 的 .txt 或 .md 再扫" % source)
        if not path.exists():
            raise OSError("找不到文件：%s（检查路径；文件名有空格时用引号包住）" % source)
        if path.is_dir():
            raise OSError("%s 是文件夹，请给出具体的文案文件" % source)
        try:
            data = path.read_bytes()
        except PermissionError:
            raise OSError("没有读取权限：%s" % source)
        label = source
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("%s 不是 UTF-8 文本：请另存为 UTF-8 编码的 .txt 或 .md 再扫" % label)


def build_rules(extra):
    rules = list(CATEGORIES)
    words = tuple(w.strip() for w in extra.replace("，", ",").split(",") if w.strip()) if extra else ()
    if words:
        rules.append(("自定义", words, "你追加的词：按品类规定和平台规则人工判断"))
    return rules


def scan(text, rules):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for cat, words, tip in rules:
            found = [w for w in words if w in line]
            if found:
                hits.append((lineno, cat, found, line.strip(), tip))
    return hits


def main(argv=None):
    parser = Parser(description="上新文案风险词粗筛（只读；没命中不等于合规）")
    parser.add_argument("file", help="文案文件（UTF-8 文本或 .md），用 - 表示从标准输入读")
    parser.add_argument("--extra", default="", help="追加要查的词，逗号分隔，如「特效,神器」")
    args = parser.parse_args(argv)

    try:
        text = read_text(args.file)
    except (OSError, ValueError) as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE
    if not text.strip():
        sys.stderr.write("内容为空：没有可扫描的文字\n")
        return EXIT_ARGS

    hits = scan(text, build_rules(args.extra))
    total = len(text.splitlines())
    if not hits:
        print("共 %d 行，没有命中风险词表。这只是粗筛，不代替人工和合规审核。" % total)
        return EXIT_OK
    print("共 %d 行，命中 %d 处（只是提醒，不代替人工和合规审核）：" % (total, len(hits)))
    for lineno, cat, found, line, tip in hits:
        excerpt = line if len(line) <= 40 else line[:40] + "……"
        print("第 %d 行［%s］「%s」：%s" % (lineno, cat, "、".join(found), excerpt))
        print("    → %s" % tip)
    return EXIT_HITS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(EXIT_INTERRUPTED)
