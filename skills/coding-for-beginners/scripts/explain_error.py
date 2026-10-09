#!/usr/bin/env python3
"""把 Python 报错翻译成新手能照着做的中文：哪一行、什么错误、最可能的原因、下一步怎么查。

用法：
  python3 scripts/explain_error.py error.txt          # 把完整报错原样存成文本文件
  python3 scripts/explain_error.py - < error.txt      # 或从标准输入读
  python3 shop.py 2> error.txt; python3 scripts/explain_error.py error.txt   # 运行时直接把报错存下来

它只读你给的文字，不运行你的代码、不联网、不改任何文件。
输出里有一行「拿去搜索的版本」：只保留已知报错模板；自定义说明退回错误类型。
原文说明仍供本机定位，可能带有业务数据；对外复制前要人工核对隐私。

退出码：0 找到并解释了报错；1 参数有误；2 文件读不了（或给的是截图）；
        3 输入里没找到 Python 报错的最后一行；130 手动中断（Ctrl+C）。
只用 Python 标准库，Python 3.8 及以上可运行。
"""

import argparse
import keyword
import re
import sys
from pathlib import Path

# 错误类型 → (一句话含义, 最常见的原因, 下一步)
EXPLAIN = {
    "SyntaxError": ("语法不完整，Python 读不懂这一行",
                    "少了冒号、括号或引号；中文标点（，：“”）混进了代码",
                    "看提示的那一行和它的上一行，括号、引号是否成对；把中文标点换成英文标点"),
    "IndentationError": ("缩进不一致",
                         "同一层代码有的缩进 4 个空格、有的不是；if/for/def 下面忘了缩进",
                         "统一用 4 个空格；冒号结尾的行，下一行要多缩进一层"),
    "TabError": ("Tab 和空格混用",
                 "有的行用 Tab 缩进，有的行用空格",
                 "全部改成 4 个空格；编辑器里打开「显示空白字符」看得更清楚"),
    "NameError": ("用了一个没定义的名字",
                  "名字拼错了，或者还没赋值就先用了；字符串忘了加引号也会这样",
                  "对照上面定义的名字逐字比对；确认赋值那一行在使用之前已经运行过"),
    "UnboundLocalError": ("函数里先用后赋值",
                          "函数里给一个外面也有的变量赋值，Python 就把它当成函数内的新变量",
                          "把需要的值当参数传进函数，用 return 把结果传出来"),
    "TypeError": ("类型不匹配",
                  "字符串和数字直接相加；函数传的参数个数不对；对不能调用的东西加了括号",
                  "用 print(type(变量)) 看它到底是什么类型；需要时用 int()、float()、str() 转换"),
    "ValueError": ("类型对了，但值不合法",
                   "int(\"abc\")、int(\"3.5\") 这种转不了的值；输入里混了空格或中文",
                   "先 print(repr(值)) 看清楚真实内容；输入要用 try/except 兜住（第 18 天）"),
    "IndexError": ("下标越界",
                   "列表只有 3 个元素，却取第 4 个；下标从 0 开始算",
                   "print(len(列表)) 看长度；最后一个元素用 列表[-1]"),
    "KeyError": ("字典里没有这个键",
                 "键名拼错、大小写不同，或者这个键还没放进去",
                 "先用 if 键 in 字典 判断，或者用 字典.get(键, 默认值)"),
    "AttributeError": ("这个对象没有这个方法或属性",
                       "方法名拼错；变量其实是 None 或别的类型；自己的文件和要导入的模块同名（如 random.py）",
                       "print(type(变量)) 看类型；检查文件夹里有没有和模块同名的 .py 文件，有就改名"),
    "ZeroDivisionError": ("除数是 0",
                          "分母算出来是 0，或者用户输入了 0",
                          "除之前先判断：if 分母 == 0 就提示，不做除法"),
    "ModuleNotFoundError": ("找不到要导入的模块",
                            "第三方库还没安装；装到了另一个 Python 里；模块名拼错",
                            "用 python3 -m pip install 包名 安装（Windows 用 py -m pip install 包名）；包名和导入名可能不同"),
    "ImportError": ("模块找到了，但里面没有要导入的东西",
                    "名字拼错；库的版本不同；自己的文件和模块同名",
                    "核对导入的名字；检查文件夹里有没有和模块同名的 .py 文件"),
    "FileNotFoundError": ("找不到文件",
                          "文件名或路径写错；程序运行时所在的文件夹不是你以为的那个",
                          "在程序开头加一行 import os; print(os.getcwd()) 看当前文件夹；把文件和 .py 放在同一个文件夹里先跑通"),
    "PermissionError": ("没有权限读写这个文件",
                        "文件正被 Excel 等软件打开；写到了系统保护的文件夹",
                        "关掉占用文件的软件；换到自己的文档文件夹里读写"),
    "UnicodeDecodeError": ("文件编码和读取方式不一致",
                           "文件是 GBK 编码，却按 UTF-8 读",
                           "open(文件, encoding=\"utf-8\") 不行就试 encoding=\"gbk\"；或把文件另存为 UTF-8"),
    "RecursionError": ("函数调用自己停不下来",
                       "递归没有结束条件，或者结束条件永远达不到",
                       "先写清楚「什么时候不再调用自己」，用很小的输入手算一遍"),
    "JSONDecodeError": ("要解析的 JSON 文本格式不对",
                        "键名或字符串用了单引号、末尾多了逗号、文件是空的，或者根本不是 JSON",
                        "先把要解析的文本 print 出来看一眼；键名和字符串一律用双引号"),
    "KeyboardInterrupt": ("程序被你手动停止（按了 Ctrl+C）",
                          "程序卡在死循环或等待输入，你按了 Ctrl+C",
                          "如果是死循环：检查 while 的条件有没有机会变成 False"),
}

# 导入名 → 安装名（常见的几个对不上的）
PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "yaml": "PyYAML", "sklearn": "scikit-learn",
             "bs4": "beautifulsoup4", "docx": "python-docx", "dateutil": "python-dateutil"}

ERROR_LINE = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Interrupt|Exit))(?::\s?(.*))?$")
FRAME = re.compile(r'^\s*File "(.+?)", line (\d+)(?:, in (.+))?')
JS_HINT = re.compile(r"Uncaught|at Object\.<anonymous>|node:internal|is not a function|Cannot read propert")


class InputError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FriendlyParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数有误：%s（例：python3 scripts/explain_error.py error.txt）" % message, file=sys.stderr)
        sys.exit(1)


def read_text(path):
    if path == "-":
        if sys.stdin.isatty():
            print("把完整报错粘贴进来，粘贴完按 Ctrl+D（Windows 按 Ctrl+Z 再回车）：", file=sys.stderr)
        data = sys.stdin.buffer.read()
    else:
        p = Path(path)
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp"):
            raise InputError(2, "这是截图，脚本读不了图片：请在终端里选中报错文字，复制后存成 .txt 或直接粘贴")
        if not p.exists():
            raise InputError(2, "找不到文件 %s：检查路径；也可以用 - 从标准输入粘贴报错" % path)
        if p.is_dir():
            raise InputError(2, "%s 是文件夹，请给出保存报错的文本文件" % path)
        try:
            data = p.read_bytes()
        except OSError as exc:
            raise InputError(2, "读不了 %s（%s）" % (path, exc.strerror or exc))
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise InputError(2, "文字编码认不出来：请把报错复制到记事本，另存为 UTF-8 后再试")


KEEP_QUOTED = set(keyword.kwlist) | {"int", "str", "float", "list", "dict", "tuple", "set", "bool",
                                      "NoneType", "bytes", "function", "module", "object"}


def _mask(m):
    inner = m.group(2)
    if inner in KEEP_QUOTED or not re.search(r"[\w\u4e00-\u9fff]", inner):
        return m.group(0)                       # 类型名、关键字、纯符号（如 '('）不是你起的名字，保留
    return m.group(1) + "..." + m.group(1)


def searchable(err_type, message):
    """只保留完整匹配的已知模板，不猜自定义错误信息里哪些词是个人数据。"""
    msg = re.sub(r"(['\"])(.*?)\1", _mask, message or "")
    msg = re.sub(r"(/|[A-Za-z]:\\)[^\s'\"]+", "...", msg)
    msg = re.sub(r"Did you mean: \S+\?", "", msg).strip().rstrip(".")
    templates = (
        r"name '\.\.\.' is not defined",
        r"No module named '\.\.\.'",
        r"invalid literal for int\(\) with base \d+: '\.\.\.'",
        r"could not convert string to float: '\.\.\.'",
        r"unsupported operand type\(s\) for [^\w\s]+: '(?:int|str|float|list|dict|tuple|set|bool|NoneType)' and '(?:int|str|float|list|dict|tuple|set|bool|NoneType)'",
    )
    if any(re.fullmatch(pattern, msg) for pattern in templates):
        return "%s: %s" % (err_type, msg)
    return err_type


LIB_PATH = re.compile(r"site-packages|dist-packages|[/\\]lib[/\\]python3|[/\\]Lib[/\\]|^<frozen", re.I)


def _where(fname, lineno, func):
    return "第 %d 行（文件 %s%s）" % (lineno, Path(fname).name,
                                  "" if not func or func == "<module>" else "，函数 %s" % func)


def explain(text):
    lines = [l.rstrip() for l in text.splitlines()]
    hit = None
    for i in range(len(lines) - 1, -1, -1):
        m = ERROR_LINE.match(lines[i].strip())
        if m:
            hit = (i, m.group(1), m.group(2) or "")
            break
    if hit is None:
        if JS_HINT.search(text):
            raise InputError(3, "这看起来是 JavaScript 的报错，本脚本只认 Python。读法相同：找错误类型和说明那一行，"
                                "再找文件名和行号（格式多为 文件:行:列）")
        raise InputError(3, "没找到 Python 报错的最后一行（形如 NameError: ...）。请把终端里从 Traceback "
                            "开头到最后一行的全部文字原样粘贴，不要截图、不要只挑一段")
    idx, err_type, message = hit
    short = err_type.split(".")[-1]
    frames = [(m.group(1), int(m.group(2)), m.group(3)) for m in (FRAME.match(l) for l in lines[:idx]) if m]
    meaning, cause, step = EXPLAIN.get(short, ("这个错误类型不在常见清单里",
                                               "看最后一行冒号后面的说明",
                                               "把「拿去搜索的版本」复制去搜，或按求助模板提问"))

    print("错误类型：%s —— %s" % (short, meaning))
    if message:
        print("原文说明：%s" % message)
    if frames:
        fname, lineno, func = frames[-1]
        print("出错位置：%s" % _where(fname, lineno, func))
        code_line = next((lines[j].strip() for j in range(idx - 1, -1, -1)
                          if lines[j].strip() and not FRAME.match(lines[j])
                          and not set(lines[j].strip()) <= set("^~ ")), "")
        if code_line and not ERROR_LINE.match(code_line):
            print("那一行是：%s" % code_line)
        mine = [f for f in frames if not LIB_PATH.search(f[0])]
        if LIB_PATH.search(fname) and mine:
            print("  这一行在别人写的库里，通常不用改它；你自己的代码最后一次调用在：%s" % _where(*mine[-1]))
        if short in ("SyntaxError", "IndentationError"):
            print("  注意：这类错误常常出在提示行的上一行，两行一起看")
        if len(frames) > 1:
            print("  调用经过 %d 层，最下面一层最接近出错的地方；先看属于你自己文件的那一层" % len(frames))
    print("最常见的原因：%s" % cause)
    tip = re.search(r"Did you mean: '?([^'?]+)'?\?", message)
    if tip:
        print("Python 猜你想写：%s" % tip.group(1))
    if short == "ModuleNotFoundError":
        mod = re.search(r"No module named '([^'.]+)", message)
        if mod and mod.group(1) in PIP_NAMES:
            print("注意：导入名 %s 对应的安装名是 %s" % (mod.group(1), PIP_NAMES[mod.group(1)]))
    print("下一步：%s" % step)
    print("拿去搜索的版本：%s" % searchable(short, message))
    print("外发前核对：原文说明、代码和文件名可能仍含个人或业务数据；只复制核对过的搜索行或公开样例")
    print("记进报错本：%s | 原因：[待补：查明后写] | 怎么改的：[待补：改好后写]" % short)
    print("还没解决：按求助模板提问（目标、环境、最小复现代码、完整报错、期望与实际、已经试过）")
    return 0


def main(argv=None):
    p = FriendlyParser(description="把 Python 报错翻译成中文：哪一行、什么错误、最可能的原因、下一步。",
                       epilog="退出码：0 已解释；1 参数有误；2 文件读不了；3 没找到报错；130 手动中断。")
    p.add_argument("file", help="保存完整报错的文本文件；写 - 表示从标准输入粘贴")
    args = p.parse_args(argv)
    try:
        return explain(read_text(args.file))
    except InputError as exc:
        print("出错：%s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有改动任何文件", file=sys.stderr)
        sys.exit(130)
