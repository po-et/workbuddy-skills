#!/usr/bin/env python3
"""把答案代回原题验算：按分数精确计算，不受小数误差影响。纯标准库，不联网，不读写文件。

用法：
  python3 scripts/check_answer.py "2(x-3)=x+5" x=11                 # 一个方程、一个未知数
  python3 scripts/check_answer.py "j+t=35" "2j+4t=94" j=23 t=12     # 方程组：鸡兔同笼代回原题
  python3 scripts/check_answer.py "2x+1>7" x=5                      # 不等式也能验
  python3 scripts/check_answer.py "1/10+1/15=1/6"                   # 没有未知数：核对一步算术
  python3 scripts/check_answer.py "(1-20%)(1+20%)"                  # 只有算式：直接算出精确值

支持：+ - * / 和整数次幂（^ 或 **）、括号、隐含乘号（2x、2(x-3)、(a+b)(a-b)）、
      百分数（20%）、小数与分数（都按分数精确算）、全角符号（× ÷ － ＝ （ ） ≤ ≥ ≠）。
关系：= 或 ==、!= 或 ≠、< > <= >=（≤ ≥），可以连写如 1<x<5。
未知数：一个字母，后面可带数字（x、y、a1）；赋值写成 x=11、x=-3/4、x=0.5。
不支持：根号、三角函数、对数——把两边平方或换成等价形式再验，或者手算。

退出码：
  0   全部成立（或只是算出了算式的值）
  3   至少一条不成立——会打出是哪条、两边各是多少；分母为 0 也算不成立（常见于增根）
  1   输入看不懂：符号不认识、少了某个未知数的值、括号不配对、次幂太大等
  130 用户按 Ctrl+C 中断
"""
import argparse
import ast
import re
import sys
from fractions import Fraction

EXIT_OK, EXIT_INPUT, EXIT_FAIL, EXIT_INTERRUPT = 0, 1, 3, 130

NORMALIZE = {
    "（": "(", "）": ")", "＝": "=", "×": "*", "·": "*", "÷": "/", "－": "-", "−": "-",
    "＋": "+", "≤": "<=", "≥": ">=", "≠": "!=", "＜": "<", "＞": ">", "^": "**", "％": "%",
    "［": "(", "］": ")", "[": "(", "]": ")", "{": "(", "}": ")",
}
TOKEN_RE = re.compile(r"\s*(?:(\d+(?:\.\d+)?%?)|([A-Za-z]\d*)|(\*\*|<=|>=|!=|==|[-+*/()=<>]))")
ASSIGN_RE = re.compile(r"^([A-Za-z]\d*)\s*=\s*([-+]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?%?)$")
REL_WORDS = {ast.Eq: "=", ast.NotEq: "≠", ast.Lt: "<", ast.LtE: "≤", ast.Gt: ">", ast.GtE: "≥"}
MAX_POW = 64
MAX_BITS = 20000


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class InputProblem(Exception):
    """算式或赋值看不懂 → 退出码 1。"""


class ZeroDenominator(Exception):
    """代入后分母为 0 → 这一条不成立。"""


def normalize(text):
    for a, b in NORMALIZE.items():
        text = text.replace(a, b)
    return text.strip()


def to_fraction(num_text):
    """'0.5' → 1/2，'20%' → 1/5，'-3/4' → -3/4；都是精确分数。"""
    t = num_text.strip()
    pct = t.endswith("%")
    if pct:
        t = t[:-1]
    if "/" in t:
        a, b = t.split("/", 1)
        if Fraction(b) == 0:
            raise InputProblem("赋值里分母为 0：%s" % num_text)
        value = Fraction(a) / Fraction(b)
    else:
        value = Fraction(t)
    return value / 100 if pct else value


def to_python(expr):
    """把学生写法翻成只含白名单节点的 Python 表达式；数字换成占位名，保证按分数算。"""
    text = normalize(expr)
    pos, out, numbers, prev = 0, [], {}, None
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            bad = text[pos:].strip()[:1] or text[pos:pos + 1]
            raise InputProblem(
                "看不懂的符号「%s」（在「%s」里）。本脚本只认四则运算、括号、整数次幂和百分数；"
                "含根号、三角函数的，把两边平方或化成等价形式再验，或手算。" % (bad, expr))
        pos = m.end()
        num, name, op = m.groups()
        kind = "num" if num else "name" if name else op
        # 隐含乘号：2x、2(x-3)、(a+b)(a-b)、x(x+1)、)2
        if prev in ("num", "name", ")") and (kind in ("name", "(") or (prev == ")" and kind == "num")):
            out.append("*")
        if num:
            key = "_n%d" % len(numbers)
            numbers[key] = to_fraction(num)
            out.append(key)
        elif name:
            out.append(name)
        elif op == "=":
            out.append("==")
        else:
            out.append(op)
        prev = kind
    if not out:
        raise InputProblem("有一个空算式，检查引号是不是多打了。")
    return " ".join(out), numbers


def evaluate(node, env):
    if isinstance(node, ast.Expression):
        return evaluate(node.body, env)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise InputProblem("未知数 %s 没给值：在命令最后加上 %s=数值。" % (node.id, node.id))
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = evaluate(node.operand, env)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        a, b = evaluate(node.left, env), evaluate(node.right, env)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            if b == 0:
                raise ZeroDenominator()
            return a / b
        if isinstance(node.op, ast.Pow):
            if b.denominator != 1:
                raise InputProblem("只支持整数次幂；分数次幂（开方）请手算或两边平方后再验。")
            if abs(b) > MAX_POW or max(abs(a.numerator), a.denominator).bit_length() * abs(b) > MAX_BITS:
                raise InputProblem("次幂太大（上限 %d 次），中小学题用不到，检查是不是输错了。" % MAX_POW)
            if a == 0 and b < 0:
                raise ZeroDenominator()
            return a ** int(b)
    raise InputProblem("算式里有不支持的写法（%s）。" % type(node).__name__)


def check_one(expr, env):
    """返回 (ok, 说明行列表)。ok 为 None 表示只是算式求值。"""
    py, numbers = to_python(expr)
    try:
        tree = ast.parse(py, mode="eval")
    except SyntaxError:
        raise InputProblem("「%s」写法不完整：检查括号是否配对、运算符前后是否都有数。" % expr)
    body = tree.body
    scope = dict(env)
    scope.update(numbers)
    try:
        if not isinstance(body, ast.Compare):
            value = evaluate(body, scope)
            return None, ["值 = %s" % show(value)]
        values = [evaluate(body.left, scope)] + [evaluate(c, scope) for c in body.comparators]
    except ZeroDenominator:
        return False, ["代入后出现分母为 0 → 不成立。分式方程里这样的值是增根，要舍去。"]
    ok, parts = True, []
    for op, left, right in zip(body.ops, values, values[1:]):
        if type(op) not in REL_WORDS:
            raise InputProblem("不支持的关系符号，只认 = ≠ < ≤ > ≥。")
        holds = {ast.Eq: left == right, ast.NotEq: left != right, ast.Lt: left < right,
                 ast.LtE: left <= right, ast.Gt: left > right, ast.GtE: left >= right}[type(op)]
        ok = ok and holds
        parts.append("%s %s %s" % (show(left, False), REL_WORDS[type(op)], show(right, False)))
    sides = "；".join("第%d部分 = %s" % (i + 1, show(v)) for i, v in enumerate(values))
    if len(values) == 2:
        sides = "左边 = %s；右边 = %s" % (show(values[0]), show(values[1]))
    return ok, [sides, "要求 %s → %s" % ("，".join(parts), "成立 ✓" if ok else "不成立 ✗")]


def show(v, approx=True):
    if v.denominator == 1:
        return str(v.numerator)
    return "%s（≈%.4g）" % (v, float(v)) if approx else str(v)


def main(argv=None):
    ap = Parser(description="把答案代回原题验算（分数精确计算）")
    ap.add_argument("items", nargs="*", metavar="算式或赋值",
                    help='方程/不等式/算式，如 "2(x-3)=x+5"；赋值如 x=11；以负号开头的算式也可以直接写')
    # 不交给 argparse 解析位置参数：像 "-3+x=0" 这种负号开头的算式会被它当成未知选项
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if any(a in ("-h", "--help") for a in raw_args):
        ap.print_help()
        return EXIT_OK
    items = [a for a in raw_args if a != "--"]
    if not items:
        ap.error('至少给一个要验的算式，例如 "2(x-3)=x+5" x=11')

    env, exprs = {}, []
    for raw in items:
        item = normalize(raw)
        m = ASSIGN_RE.match(item)
        if m:
            try:
                env[m.group(1)] = to_fraction(m.group(2))
            except (InputProblem, ValueError, ZeroDivisionError) as e:
                sys.stderr.write("输入看不懂：赋值「%s」有问题（%s）\n" % (raw, e))
                return EXIT_INPUT
        else:
            exprs.append(raw)
    if not exprs:
        sys.stderr.write("输入看不懂：只给了赋值，没给要验的原题算式。例：\"2(x-3)=x+5\" x=11\n")
        return EXIT_INPUT

    all_ok, checked = True, 0
    given = "，".join("%s=%s" % (k, show(v)) for k, v in env.items())
    for i, expr in enumerate(exprs, 1):
        try:
            ok, lines = check_one(expr, env)
        except InputProblem as e:
            sys.stderr.write("输入看不懂：%s\n" % e)
            return EXIT_INPUT
        except RecursionError:
            sys.stderr.write("输入看不懂：括号嵌套太深，检查是不是输错了。\n")
            return EXIT_INPUT
        head = "%d) %s" % (i, expr) + ("（代入 %s）" % given if given and ok is not None else "")
        print(head)
        for line in lines:
            print("   " + line)
        if ok is not None:
            checked += 1
        if ok is False:
            all_ok = False
    unused = [k for k in env if not any(re.search(r"(?<![A-Za-z])%s(?!\d)" % k, normalize(e)) for e in exprs)]
    if unused:
        print("提示：%s 给了值但算式里没用到，检查字母是否写对。" % "、".join(unused))
    if not checked:
        print("结论：已算出精确值（没有等号或不等号，不做成立判断）。")
    else:
        print("结论：%s" % ("全部成立。" if all_ok else "有不成立的，回到原题逐步找错在哪一行。"))
    return EXIT_OK if all_ok else EXIT_FAIL


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）。\n")
        sys.exit(EXIT_INTERRUPT)
