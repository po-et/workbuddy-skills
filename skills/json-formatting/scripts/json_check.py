#!/usr/bin/env python3
"""JSON 校验、定位与格式化：说清合法不合法、错在第几行第几列、前后是什么、多半是什么原因；
合法时可美化或压缩输出，写文件先写临时文件再替换，不会把原文件清空。只用 Python 标准库（3.6+）。

用法：
  python3 json_check.py a.json                      # 只校验：合法 / 不合法 + 出错位置和常见原因
  python3 json_check.py a.json --pretty             # 美化输出到屏幕：2 空格、中文不转义、保留键顺序
  python3 json_check.py a.json --pretty --out b.json  # 写到文件（先写临时文件再替换）
  python3 json_check.py a.json --compact --out a.min.json
  python3 json_check.py a.jsonl --lines             # JSON Lines：逐行校验
  python3 json_check.py dump.txt --from-python --pretty  # Python 打印结果（单引号、None、True）转成 JSON
  cat a.json | python3 json_check.py -              # 从标准输入读
其它选项：--sort-keys 排序键；--indent N；--ascii 中文转义成 \\uXXXX；
          --encoding auto|utf-8|gbk|gb18030|utf-16（默认 auto：UTF-8 读不了再试 GB18030）；
          --strict 把兼容性风险（NaN/Infinity、重复键、超 2^53 的整数）也当失败。

退出码：0 合法（或已输出）；1 参数错误；2 文件读写失败或解码失败；3 JSON 不合法；
        4 --strict 下发现兼容性风险；130 手动中断。
"""

import argparse
import ast
import json
import os
import sys
import tempfile

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_INVALID, EXIT_RISK, EXIT_INTERRUPT = 0, 1, 2, 3, 4, 130
BIG_FILE = 1024 ** 3  # 上 GB 建议走 jq --stream 流式处理

HINTS = (
    ("Expecting property name enclosed in double quotes", "多余的逗号（如 {\"a\":1,}）、键用了单引号，或有 // 注释"),
    ("Expecting ',' delimiter", "漏了逗号，或字符串里的双引号没转义（写成 \\\" 或改用「」）"),
    ("Expecting ':' delimiter", "键后面缺冒号"),
    ("Invalid \\escape", "反斜杠要写成 \\\\ 或改用 /（如 \"C:\\\\data\"）"),
    ("Invalid \\uXXXX escape", "\\u 后面要跟 4 位十六进制数"),
    ("Invalid control character", "字符串里有真换行或制表符，换成 \\n、\\t"),
    ("Unterminated string", "字符串少了结尾的双引号"),
    ("Extra data", "多个 JSON 首尾相连：包进数组 [ ]，或按 JSON Lines 用 --lines 校验"),
    ("Unexpected UTF-8 BOM", "文件带 BOM：用默认的 --encoding auto，或存成不带 BOM 的 UTF-8"),
    ("Expecting value", "多余的逗号、单引号、注释、空内容，或根本不是 JSON（Python 打印结果用 --from-python）"),
)


def zh(message):
    for en, cn in (("the following arguments are required: ", "缺少必填参数："),
                   ("unrecognized arguments: ", "不认识的参数："),
                   ("invalid int value: ", "不是整数："),
                   ("invalid choice: ", "不在可选范围内："),
                   ("expected one argument", "后面要跟一个值"),
                   ("not allowed with argument", "不能和这个参数同时用：")):
        message = message.replace(en, cn)
    return message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % zh(message))
        sys.exit(EXIT_ARGS)


def note(msg):
    sys.stderr.write("[提醒] %s\n" % msg)


def read_input(path, encoding):
    """返回 (文本, 实际编码)。读不了抛 IOError，消息可直接给用户看。"""
    try:
        if path == "-":
            raw = sys.stdin.buffer.read()
        else:
            if os.path.isdir(path):
                raise IOError("%s 是文件夹，不是 JSON 文件" % path)
            if os.path.getsize(path) >= BIG_FILE:
                note("文件超过 1 GB：整份读进内存会占用数倍内存，吃不消时用 jq --stream 流式拆成 JSON Lines")
            with open(path, "rb") as f:
                raw = f.read()
    except FileNotFoundError:
        raise IOError("找不到文件：%s（检查路径；接口返回的内容先保存成文件）" % path)
    except PermissionError:
        raise IOError("没有权限读取：%s" % path)
    except MemoryError:
        raise IOError("内存不够，读不进整个文件：用 jq --stream 流式处理")
    if encoding != "auto":
        try:
            return raw.decode("utf-8-sig" if encoding.lower() in ("utf-8", "utf8") else encoding), encoding
        except LookupError:
            raise IOError("不认识的编码名：%s（常用 utf-8、gbk、gb18030、utf-16）" % encoding)
        except UnicodeDecodeError as exc:
            raise IOError("按 %s 解码失败（第 %d 个字节）：换一个编码试试，或用默认的 --encoding auto" % (encoding, exc.start))
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), "UTF-16"
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        pass
    try:
        text = raw.decode("gb18030")
    except UnicodeDecodeError:
        raise IOError("既不是 UTF-8 也不是 GBK/GB18030：用 --encoding 指定编码")
    note("文件不是 UTF-8，已按 GB18030（兼容 GBK）读取；输出一律是 UTF-8")
    return text, "GB18030"


class Risks(object):
    """解析时顺手记下「能解析、但换个解析器可能出问题」的地方。"""

    def __init__(self):
        self.items = []
        self.nonstandard = False

    def add(self, msg):
        if msg not in self.items and len(self.items) < 20:
            self.items.append(msg)

    def pairs(self, pairs):
        seen = set()
        for k, _ in pairs:
            if k in seen:
                self.add("重复键「%s」：Python 和 jq 都静默只留最后一个，其它解析器可能报错" % k)
            seen.add(k)
        return dict(pairs)

    def constant(self, name):
        self.nonstandard = True
        self.add("非标准值 %s：Python、jq 接受，换个解析器就报错" % name)
        return float(name.replace("Infinity", "inf"))

    def number_float(self, s):
        v = float(s)
        if repr(v) != s:
            self.add("数字写法会被改写：%s → %s（要保留原写法，用 jq 1.7 及以上格式化）" % (s, json.dumps(v)))
        return v

    def number_int(self, s):
        v = int(s)
        if abs(v) > 2 ** 53:
            self.add("大整数 %s 超过 2^53：经 JavaScript 或 jq 1.6 及更早版本解析会丢精度，拿不准就请上游输出成字符串" % s)
        return v


def parse(text, risks):
    return json.loads(text, object_pairs_hook=risks.pairs, parse_constant=risks.constant,
                      parse_float=risks.number_float, parse_int=risks.number_int)


def hint_for(msg, text):
    if msg.startswith("Expecting value") and text.lstrip()[:1] == "<":
        return "内容以 < 开头，像是 HTML（接口可能返回了错误页），不是 JSON"
    if msg.startswith("Expecting value") and text.strip() == "":
        return "内容是空的"
    for key, hint in HINTS:
        if msg.startswith(key):
            return hint
    return "对照 SKILL.md 里的报错对照表"


def report_error(exc, text, label=""):
    ctx_before = text[max(0, exc.pos - 40):exc.pos].replace("\n", "↵")
    ctx_after = text[exc.pos:exc.pos + 20].replace("\n", "↵")
    print("不合法%s：%s（第 %d 行第 %d 列，第 %d 个字符）" % (label, exc.msg, exc.lineno, exc.colno, exc.pos + 1))
    print("出错处：%s <<这里>> %s" % (ctx_before, ctx_after))
    print("可能原因：%s" % hint_for(exc.msg, text))
    print("修法：只改第一处报错，改完重跑；报错位置是解析器「发现不对」的地方，真正的错常在它前面")


def write_atomic(path, content):
    """先写同目录临时文件再 os.replace：写到一半出错，原文件原样保留。"""
    target = os.path.abspath(path)
    folder = os.path.dirname(target) or "."
    if not os.path.isdir(folder):
        raise OSError("目录不存在：%s" % folder)
    fd, tmp = tempfile.mkstemp(prefix=".json_check-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def summarize(obj):
    if isinstance(obj, dict):
        return "对象，%d 个键" % len(obj)
    if isinstance(obj, list):
        return "数组，%d 个元素" % len(obj)
    return "单个值（%s）" % type(obj).__name__


def check_lines(text, strict):
    bad, good, risks = [], 0, Risks()
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parse(line, risks)
            good += 1
        except json.JSONDecodeError as exc:
            bad.append((n, exc, line))
    for n, exc, line in bad[:5]:
        print("第 %d 行不合法：%s（第 %d 列）；可能原因：%s" % (n, exc.msg, exc.colno, hint_for(exc.msg, line)))
    if len(bad) > 5:
        print("……另有 %d 行不合法" % (len(bad) - 5))
    for r in risks.items:
        note(r)
    print("JSON Lines：合法 %d 行，不合法 %d 行" % (good, len(bad)))
    if bad:
        return EXIT_INVALID
    return EXIT_RISK if strict and risks.items else EXIT_OK


def main(argv=None):
    ap = Parser(description="JSON 校验、定位与格式化。退出码：0 合法，1 参数错误，2 读写失败，3 不合法，4 --strict 下有兼容风险，130 中断")
    ap.add_argument("file", help="JSON 文件；- 表示从标准输入读")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--pretty", action="store_true", help="美化输出")
    mode.add_argument("--compact", action="store_true", help="压缩成一行")
    ap.add_argument("--indent", type=int, default=2, help="美化时的缩进空格数（默认 2）")
    ap.add_argument("--sort-keys", action="store_true", help="排序键（要 diff 时用）")
    ap.add_argument("--ascii", action="store_true", help="中文转义成 \\uXXXX（默认不转义）")
    ap.add_argument("--out", help="输出到文件（先写临时文件再替换）；不给就输出到屏幕")
    ap.add_argument("--encoding", default="auto", help="输入编码，默认 auto")
    ap.add_argument("--lines", action="store_true", help="按 JSON Lines 逐行校验")
    ap.add_argument("--from-python", action="store_true", help="输入是 Python 打印结果（单引号、None、True）")
    ap.add_argument("--strict", action="store_true", help="兼容性风险也算失败（退出码 4）")
    args = ap.parse_args(argv)

    if args.indent < 0 or args.indent > 8:
        ap.error("--indent 应在 0 到 8 之间")
    if args.lines and (args.pretty or args.compact or args.out or args.from_python):
        ap.error("--lines 只做逐行校验，不能和 --pretty、--compact、--out、--from-python 同时用")
    if args.out and not (args.pretty or args.compact or args.from_python):
        ap.error("--out 要和 --pretty 或 --compact 一起用（只校验时不写文件）")

    try:
        text, enc = read_input(args.file, args.encoding)
    except IOError as exc:
        sys.stderr.write("读取失败：%s\n" % exc)
        return EXIT_FILE

    if args.lines:
        return check_lines(text, args.strict)

    risks = Risks()
    if args.from_python:
        try:
            obj = ast.literal_eval(text.strip())
        except (ValueError, SyntaxError, MemoryError, RecursionError) as exc:
            print("不合法：不是合法的 Python 字面量（%s）；只支持 dict、list、字符串、数字、True/False/None" % exc.__class__.__name__)
            return EXIT_INVALID
        try:
            json.dumps(obj)
        except (TypeError, ValueError) as exc:
            print("不合法：里面有 JSON 表示不了的值（%s），例如集合、元组的键或字节串" % exc)
            return EXIT_INVALID
    else:
        try:
            obj = parse(text, risks)
        except json.JSONDecodeError as exc:
            report_error(exc, text)
            if "'" in text and ("None" in text or "True" in text or "False" in text):
                print("另外：内容里有单引号和 None/True/False，像是 Python 打印结果，可加 --from-python 转换")
            return EXIT_INVALID
        except RecursionError:
            print("不合法：嵌套层数太深，Python 解析不了；用 jq 处理")
            return EXIT_INVALID

    for r in risks.items:
        note(r)

    if not (args.pretty or args.compact or args.from_python):
        print("合法：%s（编码 %s）" % (summarize(obj), enc))
        return EXIT_RISK if args.strict and risks.items else EXIT_OK

    if args.compact:
        out = json.dumps(obj, ensure_ascii=args.ascii, sort_keys=args.sort_keys, separators=(",", ":"))
    else:
        out = json.dumps(obj, ensure_ascii=args.ascii, sort_keys=args.sort_keys, indent=args.indent)
    verified = not args.from_python and not risks.nonstandard
    if verified:
        if json.loads(out) != obj:
            sys.stderr.write("内部核对失败：输出与原数据不一致，已停止，没有写文件\n")
            return EXIT_INVALID

    if args.out:
        try:
            write_atomic(args.out, out + "\n")
        except OSError as exc:
            sys.stderr.write("写文件失败：%s（检查目录是否存在、有没有写权限、磁盘是否已满）；原文件没有改动\n" % exc)
            return EXIT_FILE
        same = args.file != "-" and os.path.abspath(args.file) == os.path.abspath(args.out)
        sys.stderr.write("已写入 %s%s%s\n" % (
            args.out, "（原地替换：先写临时文件再替换，原文件不会被清空）" if same else "",
            "；核对：输出与原数据逐项相等（只改了格式）" if verified else ""))
    else:
        sys.stdout.write(out + "\n")
    return EXIT_RISK if args.strict and risks.items else EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        return EXIT_INTERRUPT


if __name__ == "__main__":
    sys.exit(run())
