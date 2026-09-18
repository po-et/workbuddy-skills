#!/usr/bin/env python3
"""正则表达式中文解释与测试：逐 token 拆解、一句话说明、回溯与陷阱风险提示、VERBOSE 重写、带超时保护的样例测试。纯标准库。

用法：
  python3 regex_explain.py '^(\\d{3})-(\\d{4})$'
  python3 regex_explain.py '(?P<user>\\w+)@(?P<host>[\\w.-]+)' --test 'alice@example.com' --test 'bad@@'
  python3 regex_explain.py '(a+)+b' --test 'aaaaaaaaaaaaaaaaaaaaaaaaac'      # 灾难性回溯，0.5 秒后中断
  python3 regex_explain.py '^\\s*#.*$' --flags i,m --json
  python3 regex_explain.py '(\\d+)-(\\d+)' --verbose-rewrite
"""
import argparse
import json
import re
import signal
import sys
import threading

FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE,
         "a": re.ASCII, "u": re.UNICODE, "l": re.LOCALE}
FLAG_ZH = {"i": "忽略大小写", "m": "多行（^ $ 匹配每行）", "s": "点匹配换行", "x": "忽略空白与注释",
           "a": "ASCII 模式", "u": "Unicode 模式", "l": "本地化"}
ESC_ZH = {"d": "数字 0-9", "D": "非数字", "w": "单词字符（字母、数字、下划线）", "W": "非单词字符",
          "s": "空白字符（空格、制表、换行等）", "S": "非空白字符", "b": "单词边界",
          "B": "非单词边界", "A": "整个字符串的开头", "Z": "整个字符串的结尾",
          "n": "换行符", "t": "制表符", "r": "回车符", "f": "换页符", "v": "垂直制表符", "0": "空字符"}
CLASS_ZH = {"a-z": "小写字母", "A-Z": "大写字母", "0-9": "数字", "a-zA-Z": "字母",
            "a-fA-F0-9": "十六进制数字", "0-9a-fA-F": "十六进制数字", "一-鿿": "中日韩汉字"}


QUANT_BRIEF = {"*": ("0 个或多个", "可重复 0 次或多次"), "+": ("1 个或多个", "可重复 1 次或多次"),
               "?": ("可选的", "可有可无")}


def brief_from_range(q):
    inner = q[1:-1]
    if "," not in inner:
        return f"{inner} 个", f"重复 {inner} 次"
    if inner.endswith(","):
        return f"至少 {inner[:-1]} 个", f"重复至少 {inner[:-1]} 次"
    if inner.startswith(","):
        return f"最多 {inner[1:]} 个", f"重复最多 {inner[1:]} 次"
    a, b = inner.split(",")
    return f"{a} 到 {b} 个", f"重复 {a} 到 {b} 次"


def width(s):
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


def padr(s, n):
    return str(s) + " " * max(0, n - width(s))


# ---------------------------------------------------------------- 分词

def parse_class(body):
    """字符类内部：返回中文描述。"""
    neg = body.startswith("^")
    items, s, i = [], body[1:] if neg else body, 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            items.append(ESC_ZH.get(c, f"字面 {c}")); i += 2; continue
        if s[i : i + 2] == "[:" and ":]" in s[i:]:
            j = s.index(":]", i)
            items.append(f"POSIX 类 {s[i + 2:j]}"); i = j + 2; continue
        if i + 2 < len(s) and s[i + 1] == "-" and s[i + 2] != "]":
            rng = s[i : i + 3]
            items.append(CLASS_ZH.get(rng, f"{s[i]} 到 {s[i + 2]} 之间的字符")); i += 3; continue
        items.append(f"字面 {s[i]}" if s[i] not in " " else "空格"); i += 1
    merged = []
    for it in items:
        if it.startswith("字面 ") and merged and merged[-1].startswith("字面 "):
            merged[-1] += it[3:]
        else:
            merged.append(it)
    joined = "、".join(merged) if merged else "空"
    return ("不是 " if neg else "") + joined + " 中的任一字符"


def tokenize(pat):
    toks, i, depth, gnum = [], 0, 0, 0
    group_stack = []                                   # [(起始位置, 序号或名字, 内容起点)]
    lits = []

    def flush():
        if lits:
            raw = "".join(lits)
            toks.append({"pos": lits_pos[0], "raw": raw, "kind": "字面量",
                         "desc": f"字面文本 {raw!r}", "depth": depth, "brief": f"字面 {raw}"})
            lits.clear()

    lits_pos = [0]
    n = len(pat)
    while i < n:
        c = pat[i]
        if c == "(":
            flush()
            rest = pat[i:]
            m = re.match(r"\(\?P<(\w+)>|\(\?<(\w+)>|\(\?P=(\w+)\)|\(\?#([^)]*)\)|"
                         r"\(\?([aiLmsux]+)\)|\(\?([=!])|\(\?<([=!])|\(\?:|\(\?>|\(", rest)
            raw = m.group(0)
            if m.group(1) or m.group(2):
                gnum += 1; name = m.group(1) or m.group(2)
                kind, desc, brief = "命名分组", f"命名捕获组 {name}（第 {gnum} 个捕获组）开始", f"捕获 {name}"
                group_stack.append((i, name, len(toks)))
            elif m.group(3):
                kind, desc, brief = "反向引用", f"再次匹配命名组 {m.group(3)} 已捕获的内容", f"重复 {m.group(3)}"
                group_stack.append(None)
                group_stack.pop()
            elif m.group(4) is not None:
                kind, desc, brief = "注释", f"注释（不参与匹配）：{m.group(4)}", ""
            elif m.group(5):
                kind = "内联标志"
                desc = "内联开启标志 " + "、".join(FLAG_ZH.get(f, f) for f in m.group(5)); brief = ""
            elif m.group(6):
                kind = "断言"
                desc = "向后看（lookahead）：接下来必须" + ("是" if m.group(6) == "=" else "不是") + "以下内容，但不消耗字符"
                brief = "后面" + ("跟着" if m.group(6) == "=" else "不跟着")
                group_stack.append((i, "断言", len(toks)))
            elif m.group(7):
                kind = "断言"
                desc = "向前看（lookbehind）：前面必须" + ("是" if m.group(7) == "=" else "不是") + "以下内容，但不消耗字符"
                brief = "前面" + ("是" if m.group(7) == "=" else "不是")
                group_stack.append((i, "断言", len(toks)))
            elif raw == "(?:":
                kind, desc, brief = "非捕获组", "非捕获分组开始（只分组，不单独取值）", ""
                group_stack.append((i, None, len(toks)))
            elif raw == "(?>":
                kind, desc, brief = "原子组", "原子分组开始（匹配后不再回溯，Python 3.11+）", "原子组"
                group_stack.append((i, None, len(toks)))
            else:
                gnum += 1
                kind, desc, brief = "分组", f"第 {gnum} 个捕获组开始（可用组号 {gnum} 取值）", f"捕获第 {gnum} 组"
                group_stack.append((i, gnum, len(toks)))
            toks.append({"pos": i, "raw": raw, "kind": kind, "desc": desc, "depth": depth, "brief": brief})
            if kind not in ("注释", "内联标志", "反向引用"):
                depth += 1
            i += len(raw); continue
        if c == ")":
            flush()
            depth = max(0, depth - 1)
            start = group_stack.pop() if group_stack else None
            toks.append({"pos": i, "raw": ")", "kind": "分组结束", "desc": "分组结束", "depth": depth,
                         "brief": "", "group_start": start[0] if start else None,
                         "group_tok": start[2] if start else None})
            i += 1; continue
        if c == "[":
            flush()
            j, k = i + 1, i + 1
            if j < n and pat[j] == "^":
                j += 1
            if j < n and pat[j] == "]":
                j += 1
            while j < n and pat[j] != "]":
                j += 2 if pat[j] == "\\" else 1
            raw = pat[i : j + 1]
            toks.append({"pos": i, "raw": raw, "kind": "字符类", "desc": parse_class(raw[1:-1]),
                         "depth": depth, "brief": parse_class(raw[1:-1]).replace(" 中的任一字符", "")})
            i = j + 1; continue
        if c in "*+?" or (c == "{" and re.match(r"\{\d*,?\d*\}", pat[i:])):
            flush()
            m = re.match(r"([*+?]|\{\d*,?\d*\})([?+]?)", pat[i:])
            raw, lazy = m.group(0), m.group(2)
            base = {"*": "出现 0 次或多次", "+": "出现 1 次或多次", "?": "出现 0 次或 1 次（可选）"}.get(m.group(1))
            if base is None:
                inner = m.group(1)[1:-1]
                if "," not in inner:
                    base = f"恰好出现 {inner} 次"
                elif inner.endswith(","):
                    base = f"至少出现 {inner[:-1]} 次"
                elif inner.startswith(","):
                    base = f"最多出现 {inner[1:]} 次"
                else:
                    a, b = inner.split(","); base = f"出现 {a} 到 {b} 次"
            mode = "，非贪婪（尽可能少匹配）" if lazy == "?" else ("，占有式不回溯（Python 3.11+）" if lazy == "+" else
                   ("，贪婪（尽可能多匹配）" if m.group(1) in ("*", "+") else ""))
            pre, post = QUANT_BRIEF.get(m.group(1)) or brief_from_range(m.group(1))
            tail = "（尽量少）" if lazy == "?" else ""
            toks.append({"pos": i, "raw": raw, "kind": "量词", "desc": "前一项" + base + mode,
                         "depth": depth, "brief": pre + tail, "qpre": pre + tail, "qpost": post + tail})
            i += len(raw); continue
        if c == "|":
            flush()
            toks.append({"pos": i, "raw": "|", "kind": "选择分支", "desc": "或：左右两侧任选其一", "depth": depth, "brief": "或"})
            i += 1; continue
        if c in "^$":
            flush()
            d = "匹配开头（多行模式下是每行开头）" if c == "^" else "匹配结尾（多行模式下是每行结尾，默认还允许末尾一个换行）"
            toks.append({"pos": i, "raw": c, "kind": "锚点", "desc": d, "depth": depth,
                         "brief": "开头" if c == "^" else "结尾"})
            i += 1; continue
        if c == ".":
            flush()
            toks.append({"pos": i, "raw": ".", "kind": "任意字符", "desc": "任意一个字符（默认不含换行，加 s 标志才含）",
                         "depth": depth, "brief": "任意字符"})
            i += 1; continue
        if c == "\\" and i + 1 < n:
            flush()
            nx = pat[i + 1]
            if nx.isdigit() and nx != "0":
                m = re.match(r"\\(\d{1,2})", pat[i:])
                toks.append({"pos": i, "raw": m.group(0), "kind": "反向引用",
                             "desc": f"再次匹配第 {m.group(1)} 个捕获组已经捕到的内容", "depth": depth,
                             "brief": f"重复第 {m.group(1)} 组"})
                i += len(m.group(0)); continue
            if nx in "xuU" and re.match(r"\\[xuU][0-9a-fA-F]+", pat[i:]):
                m = re.match(r"\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}", pat[i:])
                if m:
                    toks.append({"pos": i, "raw": m.group(0), "kind": "转义类",
                                 "desc": f"码位 {m.group(0)} 对应的字符", "depth": depth, "brief": m.group(0)})
                    i += len(m.group(0)); continue
            if nx in ESC_ZH:
                toks.append({"pos": i, "raw": "\\" + nx, "kind": "转义类", "desc": ESC_ZH[nx],
                             "depth": depth, "brief": ESC_ZH[nx].split("（")[0]})
            else:
                toks.append({"pos": i, "raw": "\\" + nx, "kind": "转义字面",
                             "desc": f"字面字符 {nx}（这里的 {nx} 已转义，按普通字符匹配）", "depth": depth,
                             "brief": f"字面 {nx}"})
            i += 2; continue
        if not lits:
            lits_pos[0] = i
        lits.append(c); i += 1
    flush()
    return toks


# ---------------------------------------------------------------- 一句话说明

OPEN_KINDS = ("分组", "命名分组", "非捕获组", "断言", "原子组")


def build_tree(toks):
    root = {"children": []}
    stack, i = [root], 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if t["kind"] in OPEN_KINDS:
            node = {"label": t["brief"], "children": [], "q": ""}
            stack[-1]["children"].append(node); stack.append(node); i += 1
        elif t["kind"] == "分组结束":
            node = stack.pop() if len(stack) > 1 else None
            if nxt and nxt["kind"] == "量词" and node is not None:
                node["q"] = nxt.get("qpost", ""); i += 2
            else:
                i += 1
        elif t["kind"] == "量词":
            i += 1                                     # 落单的量词（上一项已消费）忽略
        else:
            leaf = {"text": t["brief"], "q": "", "alt": t["kind"] == "选择分支"}
            if nxt and nxt["kind"] == "量词":
                leaf["q"] = nxt.get("qpre", ""); i += 2
            else:
                i += 1
            if leaf["text"]:
                stack[-1]["children"].append(leaf)
    return root


def render_tree(node):
    out = []
    for c in node["children"]:
        if "children" in c:
            inner = render_tree(c)
            s = (f"{c['label']}（{inner}）" if c["label"] else f"（{inner}）") + (f"，{c['q']}" if c["q"] else "")
        elif c.get("alt"):
            out.append(("SEP", "，或者")); continue
        else:
            s = f"{c['q']}{c['text']}" if c["q"] else c["text"]
        out.append(("ITEM", s))
    parts, i = [], 0
    while i < len(out):
        kind, val = out[i]
        if kind == "SEP":
            if parts:
                parts[-1] += val
            i += 1
            if i < len(out):
                parts[-1] += out[i][1]; i += 1
            continue
        parts.append(val); i += 1
    return "，".join(parts)


def one_liner(toks, pat):
    s = render_tree(build_tree(toks))
    if len(s) > 220:
        s = s[:216] + "……"
    return s or f"匹配字面文本 {pat}"


# ---------------------------------------------------------------- 风险提示

def risks(pat, toks, flags_str):
    out = []

    def add(level, title, hint):
        out.append({"level": level, "title": title, "hint": hint})

    # 1 嵌套量词 / 灾难性回溯（星高 > 1）
    def open_quant(tok):
        """会把匹配次数放开的量词：* + {n,}"""
        if not tok or tok["kind"] != "量词":
            return False
        return tok["raw"][0] in "*+" or (tok["raw"].startswith("{") and "," in tok["raw"])

    for i, t in enumerate(toks):
        if t["kind"] != "分组结束" or t.get("group_tok") is None:
            continue
        outer = toks[i + 1] if i + 1 < len(toks) else None
        if not open_quant(outer):
            continue
        body = toks[t["group_tok"] + 1 : i]
        inner_q = [b for j, b in enumerate(body) if open_quant(b)]
        alt = [b for b in body if b["kind"] == "选择分支"]
        seg = (pat[t["group_start"] : t["pos"] + 1] if t.get("group_start") is not None else "(...)") + outer["raw"]
        first = body[0] if body else None
        first_q = open_quant(body[1]) if len(body) > 1 else False
        single = len(body) <= 2 and bool(inner_q)       # 分组里只有「一个元素 + 量词」
        if inner_q and single:
            add("high", f"嵌套量词 {seg}：灾难性回溯风险",
                "这是经典的 (a+)+ / (.*)* 形态：同一段文本有指数级多种拆分方式，匹配失败时回溯爆炸，"
                "二三十个字符就能把 CPU 打满。改法：内层量词去掉（(a+)+ → a+）、外层换成 {1,10} 这类有界量词，"
                "或用原子组 (?>...)（Python 3.11+）")
        elif inner_q and first and first["kind"] in ("字面量", "转义字面") and not first_q:
            add("info", f"星高 2 的写法 {seg}（一般安全）",
                f"分组外层有量词、内层也有量词，但每次重复都以固定字符 {first['raw']!r} 开头，拆分方式唯一，"
                "实际不会指数回溯。仍建议用 --test 喂一条「几十个字符且结尾不匹配」的样例压一下")
        elif inner_q:
            add("high", f"嵌套量词 {seg}：灾难性回溯风险",
                "分组内已有量词，分组外又套一层量词，且内层没有固定字符做分隔，回溯路径按指数级增长。"
                "改法同上：去掉一层量词、改有界量词，或用原子组 (?>...)")
        elif alt:
            add("warn", f"量词套在含分支的分组上 {seg}",
                "(a|ab)* 这类分支之间有重叠时同样会指数回溯；把分支改成互斥写法，或用字符类代替分支")

    # 2 点与 DOTALL
    if "." in [t["raw"] for t in toks] and "s" not in flags_str:
        add("info", "`.` 默认不匹配换行",
            "跨多行的文本（HTML 片段、日志堆栈）用 `.*` 会在第一个换行处停下。要跨行加 re.DOTALL（或 (?s)），"
            "只想跨行取一段更推荐 `[\\s\\S]*?`")
    # 3 未转义的点
    for i, t in enumerate(toks):
        if t["kind"] != "任意字符":
            continue
        prev, nxt = toks[i - 1] if i else None, toks[i + 1] if i + 1 < len(toks) else None
        if prev and prev["kind"] == "字面量" and nxt and nxt["kind"] == "字面量" and nxt["raw"][:1].isalnum():
            add("warn", f"`{prev['raw'][-1]}.{nxt['raw'][0]}` 里的点是「任意字符」",
                "想匹配字面小数点/域名点要写 `\\.`，否则 exampleXcom 这种也会被匹配上")
            break
    # 4 过度转义的斜杠
    if "\\/" in pat:
        add("info", "`\\/` 在 Python 里不需要转义",
            "这是从 JavaScript 的 /.../ 字面量里抄来的写法，Python 直接写 `/` 即可，留着也不影响匹配")
    # 5 ^ $ 与多行
    if any(t["kind"] == "锚点" for t in toks):
        if "m" in flags_str:
            add("info", "多行模式下 ^ $ 匹配的是每一行",
                "整串首尾请用 \\A 与 \\Z；按行处理时注意 $ 不含换行符本身")
        else:
            add("info", "默认模式下 ^ $ 只匹配整串首尾",
                "逐行匹配要加 re.MULTILINE（或 (?m)）；另外 $ 默认还允许结尾有一个换行，严格结尾请用 \\Z")
    # 6 贪婪吞过头
    for i, t in enumerate(toks[:-1]):
        if t["kind"] in ("任意字符", "转义类") and t["raw"] in (".", "\\w", "\\S"):
            q = toks[i + 1]
            if q["kind"] == "量词" and q["raw"] in ("*", "+") and i + 2 < len(toks):
                k = i + 2
                while k < len(toks) and toks[k]["kind"] == "分组结束":
                    k += 1                             # `(.*)"` 里真正跟在后面的是引号
                after = toks[k] if k < len(toks) else {"kind": "", "raw": ""}
                if after["kind"] in ("字面量", "转义字面", "字符类"):
                    add("warn", f"贪婪的 `{t['raw']}{q['raw']}` 会一直吃到最后一个 `{after['raw']}`",
                        f"想停在第一个 `{after['raw']}` 就写 `{t['raw']}{q['raw']}?`（非贪婪），"
                        f"更快的写法是用排除型字符类，例如 `[^{after['raw'][:1]}]{q['raw']}`")
                    break
    # 7 复杂到该用 VERBOSE
    if len(pat) >= 40 or len([t for t in toks if t["kind"] not in ("字面量",)]) >= 12:
        add("info", "表达式较长，建议用 re.VERBOSE 拆行加注释",
            "见下方「VERBOSE 重写」；维护成本降一半，代价是模式里的空白需要写成 \\s 或 [ ]")
    # 8 其它常见坑
    if re.search(r"\[[^\]]*[a-z]-[A-Z][^\]]*\]", pat):
        add("warn", "字符类里出现 `a-Z` 式跨段范围", "按码位算会把 [ \\ ] ^ _ ` 也包进来，应写成 [a-zA-Z]")
    names = re.findall(r"\(\?P<(\w+)>", pat)
    if len(names) != len(set(names)):
        add("high", "命名分组重名", "Python 会直接报 redefinition of group name，改成不同名字")
    if re.search(r"\((?!\?)", pat) and not re.search(r"\(\?", pat) and len(re.findall(r"\((?!\?)", pat)) >= 4:
        add("info", "捕获组较多，按组号取值容易错位",
            "只为分组不取值时用 (?:...)，需要取值时用 (?P<name>...) 按名字取")
    return out


# ---------------------------------------------------------------- VERBOSE 重写

def verbose_rewrite(toks, flags_str):
    lines, indent = [], 1
    for i, t in enumerate(toks):
        if t["kind"] == "分组结束":
            indent = max(1, indent - 1)
        raw = t["raw"]
        if t["kind"] in ("字面量", "转义字面"):
            raw = raw.replace(" ", "\\ ").replace("#", "\\#")
        pad = "    " * indent
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if nxt and nxt["kind"] == "量词" and t["kind"] != "分组结束":
            pass
        lines.append((pad + raw, t["desc"]))
        if t["kind"] in ("分组", "命名分组", "非捕获组", "断言", "原子组"):
            indent += 1
    w = max((width(a) for a, _ in lines), default=0)
    body = "\n".join(f"{padr(a, w + 2)}# {d}" for a, d in lines)
    extra = "".join(sorted(set(flags_str) - {"x"}))
    flag_expr = " | ".join(["re.VERBOSE"] + [f"re.{ {'i': 'IGNORECASE', 'm': 'MULTILINE', 's': 'DOTALL', 'a': 'ASCII'}.get(f, f.upper()) }" for f in extra])
    return 'pattern = re.compile(r"""\n' + body + f'\n""", {flag_expr})'


# ---------------------------------------------------------------- 测试

def timed_search(rx, s, timeout):
    """带超时的 search。POSIX 上用 SIGALRM（能真正打断回溯中的匹配），其它平台退化为线程守护。"""
    if timeout and timeout > 0 and hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread():
        def onalarm(signum, frame):
            raise TimeoutError
        old = signal.signal(signal.SIGALRM, onalarm)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            m = rx.search(s)
            return ("match", m) if m else ("nomatch", None)
        except TimeoutError:
            return "timeout", None
        except Exception as e:                          # noqa: BLE001
            return "error", str(e)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    box = {}

    def run():
        try:
            box["m"] = rx.search(s)
        except Exception as e:                          # noqa: BLE001
            box["err"] = str(e)
    th = threading.Thread(target=run, daemon=True)
    th.start(); th.join(timeout if timeout and timeout > 0 else None)
    if th.is_alive():
        return "timeout", None
    if "err" in box:
        return "error", box["err"]
    return ("match", box["m"]) if box["m"] else ("nomatch", None)


def run_tests(rx, samples, timeout):
    results = []
    for s in samples:
        state, m = timed_search(rx, s, timeout)
        r = {"input": s, "state": state}
        if state == "match":
            r["span"] = list(m.span()); r["matched"] = m.group(0)
            r["full"] = m.span() == (0, len(s))
            r["groups"] = {str(i): m.group(i) for i in range(1, (m.re.groups or 0) + 1)}
            r["named"] = {k: v for k, v in (m.groupdict() or {}).items()}
        elif state == "error":
            r["error"] = m
        results.append(r)
    return results


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(description="正则表达式中文解释与测试")
    ap.add_argument("pattern", help="正则表达式（用单引号包住，避免 shell 吃掉反斜杠）")
    ap.add_argument("--test", action="append", default=[], metavar="样例字符串", help="可重复：对样例做匹配测试")
    ap.add_argument("--flags", default="", help="标志，逗号或直接连写，如 i,m,s,x")
    ap.add_argument("--timeout", type=float, default=0.5, help="单个样例的匹配超时秒数，默认 0.5")
    ap.add_argument("--verbose-rewrite", action="store_true", help="只输出 re.VERBOSE 重写版")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="存在 high 级风险时退出码 1")
    a = ap.parse_args()

    pat = a.pattern
    flags_str = "".join(ch for ch in a.flags.lower() if ch in FLAGS)
    flags_str += "".join(f for f in re.findall(r"\(\?([aiLmsux]+)\)", pat) for f in f)
    flags = 0
    for f in set(flags_str):
        flags |= FLAGS[f]

    err = None
    try:
        rx = re.compile(pat, flags)
    except re.error as e:
        rx, err = None, f"{e.msg}（位置 {e.pos}）" if e.pos is not None else str(e)

    toks = tokenize(pat)
    rk = risks(pat, toks, flags_str)
    summary = one_liner(toks, pat)
    rewrite = verbose_rewrite(toks, flags_str)
    tests = run_tests(rx, a.test, a.timeout) if (rx and a.test) else []

    if a.json:
        print(json.dumps({"pattern": pat, "flags": sorted(set(flags_str)), "valid": rx is not None,
                          "error": err, "summary": summary,
                          "tokens": [{k: t[k] for k in ("pos", "raw", "kind", "desc")} for t in toks],
                          "risks": rk, "verbose_rewrite": rewrite, "tests": tests},
                         ensure_ascii=False, indent=2))
    elif a.verbose_rewrite:
        print(rewrite)
    else:
        print(f"正则：{pat}")
        print("标志：" + ("、".join(f"{f}（{FLAG_ZH[f]}）" for f in sorted(set(flags_str))) or "无"))
        if err:
            print(f"\n[编译失败] {err}\n下面的拆解仅供参考，先把语法错误改掉。")
        print(f"一句话：{summary}")

        print(f"\n## 逐项解释（{len(toks)} 项）")
        w = max([width(t["raw"]) for t in toks] + [4])
        print("  " + padr("位置", 6) + padr("片段", w + 2) + padr("类型", 10) + "说明")
        for t in toks:
            ind = "  " * t["depth"]
            print("  " + padr(t["pos"], 6) + padr(ind + t["raw"], w + 2) + padr(t["kind"], 10) + t["desc"])

        if rk:
            hi = sum(1 for r in rk if r["level"] == "high")
            print(f"\n## 风险提示（{hi} high / {sum(1 for r in rk if r['level'] == 'warn')} warn / "
                  f"{sum(1 for r in rk if r['level'] == 'info')} info）")
            for r in rk:
                print(f"  [{r['level']}] {r['title']}")
                print(f"      → {r['hint']}")

        if any(r["level"] == "info" and "VERBOSE" in r["title"] for r in rk):
            print("\n## VERBOSE 重写")
            print("\n".join("  " + l for l in rewrite.splitlines()))

        if a.test:
            print(f"\n## 测试（{len(a.test)} 个样例，单例超时 {a.timeout}s）")
            for r in tests:
                if r["state"] == "match":
                    tail = "（整串匹配）" if r["full"] else f"（第 {r['span'][0]}–{r['span'][1]} 个字符）"
                    print(f"  ✓ {r['input']!r} → 匹配 {r['matched']!r}{tail}")
                    for k, v in r["groups"].items():
                        nm = next((n for n, val in r["named"].items() if val == v), None)
                        print(f"      组 {k}{'（' + nm + '）' if nm else ''} = {v!r}")
                elif r["state"] == "nomatch":
                    print(f"  ✗ {r['input']!r} → 不匹配")
                elif r["state"] == "timeout":
                    print(f"  ⏱ {r['input']!r} → 超过 {a.timeout}s 未返回，已放弃（典型的灾难性回溯，按上面的改法重写）")
                else:
                    print(f"  ! {r['input']!r} → 匹配出错：{r.get('error')}")
        elif rx is None:
            pass
        else:
            print("\n提示：加 --test '样例字符串' 可以直接验证匹配结果与各分组取值（可重复多次）。")

    if err:
        sys.exit(2)
    if a.strict and any(r["level"] == "high" for r in rk):
        sys.exit(1)


if __name__ == "__main__":
    main()
