#!/usr/bin/env python3
"""英文邮件发送前自查：中式英语常见 10 处、没替换的占位符、ASAP 不写日期、
时间不带时区、主题行、重复道歉、提到附件。纯标准库，不联网，只读不写。

用法：
  python3 scripts/email_check.py draft.txt            # 检查一份草稿
  python3 scripts/email_check.py - < draft.txt        # 从标准输入读
  python3 scripts/email_check.py draft.txt --json     # 机器可读输出

退出码：
  0   没发现「问题」级命中（可能仍有「提醒」，比如记得附上附件）
  3   发现需要人工看的地方——不是程序出错，逐条对照判断
  1   参数不对，或草稿为空 / 过大（不像一封邮件）
  2   文件读不了（不存在、是目录、没权限、编码无法识别）
  130 用户按 Ctrl+C 中断
"""
import argparse
import json
import re
import sys

EXIT_OK, EXIT_INPUT, EXIT_IO, EXIT_REVIEW, EXIT_INTERRUPT = 0, 1, 2, 3, 130
MAX_BYTES = 1024 * 1024  # 超过 1MB 基本不是一封邮件草稿

# (编号, 正则, 常见写法, 改成, 为什么)；编号对应 references/chinglish-10.md
CHINGLISH = [
    (1, r"\bplease\s+kindly\b", "Please kindly confirm …",
     "Please confirm … / Could you confirm …?", "please 和 kindly 叠用，读着生硬"),
    (2, r"\bplease\s+(?:kindly\s+)?noted\b", "Please noted that …", "Please note that …",
     "please 后面接动词原形"),
    (3, r"\bdiscuss(?:ed|es|ing)?\s+about\b", "discuss about the plan", "discuss the plan",
     "discuss 直接带宾语"),
    (4, r"\bcontact(?:ed|s|ing)?\s+with\b", "contact with me", "contact me",
     "contact 作动词不加 with"),
    (5, r"\bopen(?:ed|s|ing)?\s+a\s+meeting\b", "open a meeting", "hold / have a meeting",
     "开会不用 open"),
    (6, r"\bprices?\s+(?:is|are|was|were)\s+(?:too\s+|very\s+|so\s+)?expensive\b",
     "The price is too expensive.", "The price is too high.", "price 说高低，不说贵"),
    (8, r"\bwelcome\s+to\s+contact\b", "Welcome to contact me.", "Feel free to contact me.",
     "welcome to 后面不接动词"),
    (9, r"\bhope\s+you\s+can\s+understand\b", "Hope you can understand.",
     "Thank you for your understanding.", "原句听着像「你该理解」"),
    (10, r"\bI\s+want\s+to\b", "I want to know …",
     "Could you let me know …? / I'd like to know …", "want 在商务邮件里偏冲"),
]
TZ_WORDS = re.compile(
    r"\b(time|GMT|UTC|CET|CEST|EST|EDT|CST|PST|PDT|ET|PT|BST|JST|KST|SGT|HKT|IST|AEST|AEDT)\b"
    r"|北京|上海|时间|时区",
    re.I,
)
TIME_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)(?![a-z])|\b\d{1,2}:\d{2}\b", re.I)
ASAP_RE = re.compile(r"\b(asap|a\.s\.a\.p\.|as soon as possible)\b", re.I)
ATTACH_RE = re.compile(r"\b(attached|attachments?|enclosed|attach)\b|附件", re.I)
SORRY_RE = re.compile(r"\b(sorry|apologi[sz]e|apologies)\b", re.I)
PLACEHOLDER_RE = re.compile(r"\[(待补|待确认)[^\]\n]*\]|\[\s*\]|\[[^\[\]\n]{1,40}\](?!\()")
SUBJECT_RE = re.compile(r"^\s*(subject|主题)\s*[:：]\s*(.*)$", re.I)
BODY_WORDS_SOFT_MAX = 250  # 经验阈值：再长就考虑编号列表或放附件


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「文件读不了」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_INPUT)


class InputProblem(Exception):
    """输入内容有问题（空、过大）→ 退出码 1。"""


class ReadProblem(Exception):
    """文件层面读不了 → 退出码 2。"""


def read_draft(path):
    if path == "-":
        data = sys.stdin.buffer.read()
        where = "标准输入"
    else:
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_BYTES + 1)
        except FileNotFoundError:
            raise ReadProblem("找不到文件：%s。确认路径，或直接把草稿粘到对话里。" % path)
        except IsADirectoryError:
            raise ReadProblem("%s 是目录，请给一个具体的草稿文件。" % path)
        except PermissionError:
            raise ReadProblem("没有权限读取 %s。换个目录保存草稿再试。" % path)
        except OSError as e:
            raise ReadProblem("读取 %s 失败：%s" % (path, e))
        where = path
    if len(data) > MAX_BYTES:
        raise InputProblem("%s 超过 1MB，不像一封邮件草稿，确认是不是传错了文件。" % where)
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ReadProblem("%s 的编码认不出来（不是 UTF-8 也不是 GBK）。请另存为 UTF-8 再试。" % where)
    if not text.strip():
        raise InputProblem("%s 是空的：先把草稿全文保存进去再检查。" % where)
    return text


def check(text):
    """返回 findings 列表：每条 {line, level, kind, hit, fix}。"""
    findings = []
    lines = text.splitlines()

    def add(line, level, kind, hit, fix):
        findings.append({"line": line, "level": level, "kind": kind, "hit": hit, "fix": fix})

    subject_seen = False
    sorry_lines = []
    body_words = 0
    for no, line in enumerate(lines, 1):
        m = SUBJECT_RE.match(line)
        if m and not subject_seen:
            subject_seen = True
            subj = m.group(2).strip()
            words = subj.split()
            if not subj:
                add(no, "问题", "主题行", line.strip(), "主题行是空的：写「类型 + 对象 + 期限或状态」")
            elif subj.lower().rstrip("!.,") in ("hello", "hi", "hey", "dear"):
                add(no, "问题", "主题行", subj, "主题只写了问候语：写「类型 + 对象 + 期限或状态」")
            if "!!!" in subj or re.search(r"\bURGENT\b", subj):
                add(no, "问题", "主题行", subj, "别用 URGENT / !!!：把期限写进主题，如 by Fri 15 May")
            if len(words) > 12:
                add(no, "提醒", "主题行", subj, "主题行 %d 个词，偏长；约六到十个词为宜" % len(words))
        else:
            body_words += len(re.findall(r"[A-Za-z]+", line))
        for num, pat, wrong, right, why in CHINGLISH:
            for hit in re.finditer(pat, line, re.I):
                add(no, "问题", "中式英语#%d" % num, hit.group(0), "%s（%s）" % (right, why))
        for hit in PLACEHOLDER_RE.finditer(line):
            add(no, "问题", "占位符", hit.group(0), "发送前换成真实内容；不知道的先问清，别编")
        for hit in ASAP_RE.finditer(line):
            add(no, "问题", "没写期限", hit.group(0), "写成具体日期，如 by Friday, 15 May")
        if TIME_RE.search(line) and not TZ_WORDS.search(line):
            add(no, "问题", "时区", TIME_RE.search(line).group(0),
                "写了钟点但没写时区：写成「时间 + 城市/时区」，如 9 am New York time；换算北京时间用日历工具或 zoneinfo 核对，夏令时前后差一小时")
        if ATTACH_RE.search(line):
            add(no, "提醒", "附件", ATTACH_RE.search(line).group(0), "正文提到附件：发送前确认真的附上了")
        sorry_lines.extend([no] * len(SORRY_RE.findall(line)))
    if not subject_seen:
        add(0, "提醒", "主题行", "（未找到 Subject 行）", "交付时第一行写 Subject: …，主题行公式见 SKILL.md")
    if len(sorry_lines) >= 2:
        add(sorry_lines[1], "提醒", "道歉",
            "sorry/apologize 出现 %d 次" % len(sorry_lines), "道歉只说一次，后面讲补救和防再犯")
    if body_words > BODY_WORDS_SOFT_MAX:
        add(0, "提醒", "篇幅", "正文约 %d 个英文词" % body_words,
            "超过一屏：把细节改成编号列表或放进附件（经验阈值 %d 词）" % BODY_WORDS_SOFT_MAX)
    return findings


def render(findings, source):
    problems = [f for f in findings if f["level"] == "问题"]
    tips = [f for f in findings if f["level"] == "提醒"]
    out = ["检查 %s：问题 %d 处，提醒 %d 处" % (source, len(problems), len(tips))]
    for f in problems + tips:
        where = "L%d" % f["line"] if f["line"] else "全文"
        out.append("%-5s [%s] %s「%s」→ %s" % (where, f["level"], f["kind"], f["hit"], f["fix"]))
    if findings:
        out.append("命中不等于一定错：逐条对照 references/chinglish-10.md 判断。")
    out.append("第 7 条（Mr./Ms. 后面接的是姓还是名）脚本判断不了，请人工看称呼。")
    return "\n".join(out)


def main(argv=None):
    ap = Parser(description="英文邮件发送前自查（中式英语、占位符、期限、时区、主题行、附件）")
    ap.add_argument("draft", help="草稿文件路径；用 - 表示从标准输入读")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    try:
        text = read_draft(args.draft)
    except InputProblem as e:
        sys.stderr.write("输入有问题：%s\n" % e)
        return EXIT_INPUT
    except ReadProblem as e:
        sys.stderr.write("读取失败：%s\n" % e)
        return EXIT_IO
    findings = check(text)
    source = "标准输入" if args.draft == "-" else args.draft
    if args.json:
        print(json.dumps({"source": source, "findings": findings}, ensure_ascii=False, indent=2))
    else:
        print(render(findings, source))
    return EXIT_REVIEW if any(f["level"] == "问题" for f in findings) else EXIT_OK


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有做任何改动。\n")
        sys.exit(EXIT_INTERRUPT)
