#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运动会加油稿投稿清单：读一个文件夹里的加油稿，按项目分组，统计字数与预计朗读时长。

用法：
  python3 cheer_list.py 稿件文件夹
  python3 cheer_list.py 稿件文件夹 --cpm 220 --max-chars 100 --format md --out 投稿清单.md
  python3 cheer_list.py --calibrate 样稿.txt 32

每篇稿子统计：
  字数      = 除空白外的全部字符（含标点），用来对照投稿限字与 50/100/200 字档；
  朗读字数  = 汉字、数字、字母（不含标点、符号与空白），用来估算朗读时长；
  预计时长  = 朗读字数 ÷ 每分钟字数 × 60 秒。

每分钟字数默认 200：这是经验估计值，没有经过测量，不同播音员差别很大。
正式排播音时间前，请让播音员读一篇样稿计时，用 --calibrate 算出实际语速，再传给 --cpm。

项目怎么认（按优先级）：
  1. 文件开头的「项目：xxx」行（同一段还认「班级：」「作者：」「投稿人：」「标题：」「对象：」）；
  2. 文件名或所在子文件夹名里的项目词，如「短跑-高一3班-01.txt」「接力/03.txt」；
  3. 正文里的项目词（如「接力棒」→接力），清单里标「由正文推断，请核对」；
  4. 都认不出 → 「未分组」。
「项目：」写了但不是常见项目名（如「趣味障碍跑」），按原样单独成组。

退出码：0 成功；1 参数错误；2 文件读写错误；130 被 Ctrl+C 中断。
只用 Python 标准库；不联网；除 --out 指定的文件外不写任何文件（先写临时文件再替换）。
"""

import argparse
import csv
import io
import os
import re
import sys
import tempfile
import unicodedata

DEFAULT_CPM = 200.0              # 经验估计值（未经测量）；用 --calibrate 实测后改用 --cpm
MAX_FILE_BYTES = 1024 * 1024     # 超过 1MB 的 .txt 不像加油稿，跳过
TEXT_SUFFIX = ".txt"
UNSUPPORTED_SUFFIXES = (".docx", ".doc", ".wps", ".pdf", ".rtf", ".pages", ".odt")
CALIBRATE_SANE = (60.0, 450.0)   # 实测语速落在这个范围外时提醒核对计时（只是提醒，不拦）

EVENT_ORDER = ("短跑", "中长跑", "接力", "跳远跳高", "投掷", "拔河", "团体操", "串场")
UNGROUPED = "未分组"

# 按顺序匹配，先匹配到的优先：「4×100米接力」要先认成接力，「八百米」要先认成中长跑。
EVENT_KEYWORDS = (
    ("接力", ("接力", "交接棒", "4×100", "4x100", "4*100", "4×400", "4x400", "4*400",
             "四乘一百", "四乘四百")),
    ("拔河", ("拔河",)),
    ("团体操", ("团体操", "广播操", "广播体操", "健身操", "韵律操")),
    ("投掷", ("投掷", "铅球", "实心球", "标枪", "铁饼", "垒球")),
    ("跳远跳高", ("跳远", "跳高", "三级跳", "撑竿跳", "横杆", "沙坑")),
    ("中长跑", ("中长跑", "长跑", "800米", "800m", "1000米", "1000m", "1500米", "1500m",
               "3000米", "3000m", "5000米", "5000m", "八百米", "一千米", "一千五百米",
               "三千米", "五千米")),
    ("短跑", ("短跑", "百米", "60米", "60m", "100米", "100m", "200米", "200m", "400米",
             "400m", "六十米", "一百米", "二百米", "两百米", "四百米")),
    ("串场", ("串场", "检录", "颁奖", "开幕", "闭幕", "入场式", "成绩播报")),
)

META_KEYS = {"项目": "event", "班级": "klass", "作者": "author", "投稿人": "author",
             "标题": "title", "对象": "target"}
META_RE = re.compile(r"^\s*(项目|班级|作者|投稿人|标题|对象)\s*[:：]\s*(.*?)\s*$")


class UserError(Exception):
    """带退出码的、给用户看的错误。"""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message


def error_text(exc):
    """把常见的系统错误翻成中文，其余保留原文。"""
    if isinstance(exc, PermissionError):
        return "没有读写权限"
    if isinstance(exc, FileNotFoundError):
        return "文件或目录不存在"
    if isinstance(exc, IsADirectoryError):
        return "这是文件夹，不是文件"
    if isinstance(exc, OSError):
        return exc.strerror or str(exc)
    return str(exc)


def inside(path, folder):
    """path 是否在 folder 里面（含子文件夹）。"""
    base = os.path.realpath(folder)
    try:
        return os.path.commonpath([base, os.path.realpath(path)]) == base
    except ValueError:
        return False


# ---------------------------------------------------------------- 参数

class ChineseArgumentParser(argparse.ArgumentParser):
    """参数错误统一退出码 1（argparse 默认是 2，和「文件错误」撞车）。"""

    _TRANSLATE = (
        ("unrecognized arguments", "不认识的参数"),
        ("the following arguments are required", "缺少必需的参数"),
        ("expected one argument", "后面缺少取值"),
        ("expected 2 arguments", "后面需要两个取值"),
        ("invalid choice", "取值不在可选范围内"),
        ("choose from", "可选"),
        ("argument ", "参数 "),
    )

    def error(self, message):
        for en, zh in self._TRANSLATE:
            message = message.replace(en, zh)
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用 --help 查看完整用法。\n" % message)
        sys.exit(1)


def positive_number(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("需要大于 0 的数字，收到 %r" % text)
    if not value > 0 or value == float("inf"):
        raise argparse.ArgumentTypeError("需要大于 0 的数字，收到 %r" % text)
    return value


def non_negative_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("需要 0 或正整数，收到 %r" % text)
    if value < 0:
        raise argparse.ArgumentTypeError("需要 0 或正整数，收到 %r" % text)
    return value


def build_parser():
    p = ChineseArgumentParser(
        prog="cheer_list.py",
        usage="python3 cheer_list.py 稿件文件夹 [选项]  |  python3 cheer_list.py --calibrate 样稿.txt 秒数",
        add_help=False,
        description="读一个文件夹里的运动会加油稿（.txt），按项目分组，统计字数与预计朗读时长，输出投稿清单。",
        epilog="退出码：0 成功；1 参数错误；2 文件读写错误；130 被 Ctrl+C 中断。",
    )
    p.add_argument("folder", nargs="?", help="放加油稿 .txt 的文件夹")
    p.add_argument("-h", "--help", action="help", help="显示帮助并退出")
    p.add_argument("--cpm", type=positive_number, default=None,
                   help="每分钟朗读字数；不填按 200（经验估计值，未经测量）")
    p.add_argument("--max-chars", type=non_negative_int, default=0,
                   help="投稿字数上限（含标点），超出的标出来；0 表示不检查")
    p.add_argument("--min-chars", type=non_negative_int, default=0,
                   help="投稿字数下限（含标点），不足的标出来；0 表示不检查")
    p.add_argument("--format", choices=("text", "md", "csv"), default="text",
                   help="输出格式：text 终端表格（默认）、md 表格、csv（Excel 可直接打开）")
    p.add_argument("--out", default="", help="写到这个文件（先写临时文件再替换）；不填就打印到屏幕")
    p.add_argument("--recursive", action="store_true", help="连子文件夹一起读（子文件夹名可作项目名）")
    p.add_argument("--calibrate", nargs=2, metavar=("样稿", "秒数"),
                   help="用一篇样稿的实际朗读秒数算每分钟字数")
    return p


# ---------------------------------------------------------------- 文本处理

def norm(text):
    """全角转半角、去空白、转小写，用于匹配项目词与查重。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).lower()


def classify(text):
    """把一段文字归到标准项目；认不出返回 None。"""
    t = norm(text)
    if not t:
        return None
    for group, words in EVENT_KEYWORDS:
        if t == group or any(w.lower() in t for w in words):
            return group
    return None


def split_meta(text):
    """拆出文件开头的「项目：」「班级：」等行，返回 (meta, body)。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    meta = {}
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines):
        m = META_RE.match(lines[i])
        if not m:
            break
        key = META_KEYS[m.group(1)]
        if key not in meta:
            meta[key] = m.group(2)
        i += 1
    return meta, "\n".join(lines[i:]).strip()


def count_chars(body):
    """字数（含标点，不含空白）。"""
    return sum(1 for ch in body if not ch.isspace())


def count_spoken(body):
    """朗读字数：汉字、数字、字母；不含标点、符号与空白。"""
    return sum(1 for ch in body if ch.isalnum())


def tier(chars):
    if chars == 0:
        return "-"
    if chars <= 75:
        return "50字档"
    if chars <= 150:
        return "100字档"
    if chars <= 300:
        return "200字档"
    return "长稿"


def seconds_for(spoken, cpm):
    return int(spoken * 60.0 / cpm + 0.5)


def mmss(seconds):
    return "%d:%02d" % (seconds // 60, seconds % 60)


def natural_key(text):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]


def read_text(path):
    """读文本：UTF-16（有 BOM 时）→ UTF-8（可带 BOM）→ GB18030。返回 (文本, 编码)。"""
    size = os.path.getsize(path)
    if size > MAX_FILE_BYTES:
        raise ValueError("文件超过 1MB，不像加油稿，已跳过")
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16"), "UTF-16"
        except UnicodeDecodeError:
            raise ValueError("UTF-16 文本不完整或已损坏，请用记事本另存为 UTF-8")
    try:
        return data.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("gb18030"), "GB18030"
    except UnicodeDecodeError:
        raise ValueError("既不是 UTF-8 也不是 GB18030 文本，请用记事本另存为 UTF-8")


# ---------------------------------------------------------------- 收集

def collect(folder, recursive, skip_path):
    """返回 (txt 相对路径列表, 不支持格式的相对路径列表)，都按自然顺序排好。"""
    txt, unsupported = [], []

    def consider(rel, full):
        name = os.path.basename(rel)
        if name.startswith(".") or name.startswith("~$"):
            return
        if skip_path and os.path.realpath(full) == skip_path:
            return
        suffix = os.path.splitext(name)[1].lower()
        if suffix == TEXT_SUFFIX:
            txt.append(rel)
        elif suffix in UNSUPPORTED_SUFFIXES:
            unsupported.append(rel)

    if recursive:
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__MACOSX")
            for name in files:
                full = os.path.join(root, name)
                consider(os.path.relpath(full, folder), full)
    else:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.is_file():
                    consider(entry.name, entry.path)
    txt.sort(key=natural_key)
    unsupported.sort(key=natural_key)
    return txt, unsupported


def analyze(folder, rels, cpm, max_chars, min_chars):
    records = []
    seen = {}
    for rel in rels:
        rec = {"file": rel, "event": UNGROUPED, "source": "", "klass": "", "author": "",
               "title": "", "target": "", "chars": 0, "spoken": 0, "seconds": 0,
               "tier": "-", "notes": [], "error": ""}
        try:
            text, encoding = read_text(os.path.join(folder, rel))
        except (OSError, ValueError) as exc:
            rec["error"] = error_text(exc)
            records.append(rec)
            continue
        meta, body = split_meta(text)
        for key in ("klass", "author", "title", "target"):
            rec[key] = meta.get(key, "")
        if encoding != "UTF-8":
            rec["notes"].append("按 %s 读取" % encoding)

        declared = meta.get("event", "")
        by_name = classify(os.path.splitext(rel)[0])
        by_body = classify(body)
        if declared and classify(declared):
            rec["event"], rec["source"] = classify(declared), "文件头"
        elif declared:
            rec["event"], rec["source"] = declared, "文件头"
            rec["notes"].append("项目名不常见，按原样分组")
        elif by_name:
            rec["event"], rec["source"] = by_name, "文件名"
        elif by_body:
            rec["event"], rec["source"] = by_body, "正文推断"
            rec["notes"].append("项目由正文推断，请核对")
        elif body:
            rec["notes"].append("认不出项目，请加一行「项目：」")

        rec["chars"] = count_chars(body)
        rec["spoken"] = count_spoken(body)
        rec["seconds"] = seconds_for(rec["spoken"], cpm)
        rec["tier"] = tier(rec["chars"])
        if rec["chars"] == 0:
            rec["notes"].append("空文件")
        if max_chars and rec["chars"] > max_chars:
            rec["notes"].append("超出上限 %d 字" % (rec["chars"] - max_chars))
        if min_chars and 0 < rec["chars"] < min_chars:
            rec["notes"].append("不足下限 %d 字" % (min_chars - rec["chars"]))
        key = "".join(ch for ch in norm(body) if ch.isalnum())
        if key:
            if key in seen:
                rec["notes"].append("与 %s 内容相同" % seen[key])
            else:
                seen[key] = rel
        records.append(rec)
    return records


def group_records(records):
    groups = {}
    for rec in records:
        if rec["error"]:
            continue
        groups.setdefault(rec["event"], []).append(rec)
    custom = sorted((g for g in groups if g not in EVENT_ORDER and g != UNGROUPED), key=natural_key)
    order = [g for g in EVENT_ORDER if g in groups] + custom
    if UNGROUPED in groups:
        order.append(UNGROUPED)
    return [(g, groups[g]) for g in order]


# ---------------------------------------------------------------- 输出

COLUMNS = ("序号", "文件", "班级", "作者", "字数", "朗读字数", "时长", "档位", "提示")


def row_cells(i, rec):
    return (str(i), rec["file"], rec["klass"] or "-", rec["author"] or "-", str(rec["chars"]),
            str(rec["spoken"]), mmss(rec["seconds"]), rec["tier"], "；".join(rec["notes"]))


def width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text, w):
    return text + " " * max(0, w - width(text))


def header_lines(folder, records, unsupported, cpm, cpm_given, max_chars, min_chars):
    ok = [r for r in records if not r["error"]]
    lines = ["稿件文件夹：%s（读到 %d 篇%s）" % (
        folder, len(ok),
        "，%d 篇读取失败" % (len(records) - len(ok)) if len(records) != len(ok) else "")]
    if cpm_given:
        lines.append("预计时长：按每分钟 %g 字估算（你指定的语速）" % cpm)
    else:
        lines.append("预计时长：按每分钟 %g 字估算（默认经验值，未经测量；可用 --calibrate 实测后用 --cpm 指定）" % cpm)
    limits = []
    if max_chars:
        limits.append("上限 %d 字" % max_chars)
    if min_chars:
        limits.append("下限 %d 字" % min_chars)
    lines.append("字数口径：含标点、不含空白；%s" % ("，".join(limits) if limits else "未设上下限"))
    if unsupported:
        lines.append("未读取（请另存为 .txt）：%s" % "、".join(unsupported))
    return lines


def todo_lines(records):
    out = []
    for rec in records:
        if rec["error"]:
            out.append("读取失败：%s（%s）" % (rec["file"], rec["error"]))
    for rec in records:
        if rec["error"]:
            continue
        flags = [n for n in rec["notes"] if not n.startswith("按 ")]
        if flags:
            out.append("%s：%s" % (rec["file"], "；".join(flags)))
    return out


def totals(recs):
    return len(recs), sum(r["chars"] for r in recs), sum(r["seconds"] for r in recs)


def render_text(folder, records, unsupported, cpm, cpm_given, max_chars, min_chars):
    lines = ["运动会加油稿投稿清单"]
    lines += header_lines(folder, records, unsupported, cpm, cpm_given, max_chars, min_chars)
    for group, recs in group_records(records):
        n, chars, secs = totals(recs)
        lines.append("")
        lines.append("【%s】%d 篇，合计 %d 字，约 %s" % (group, n, chars, mmss(secs)))
        rows = [COLUMNS] + [row_cells(i, r) for i, r in enumerate(recs, 1)]
        widths = [max(width(row[c]) for row in rows) for c in range(len(COLUMNS))]
        for row in rows:
            cells = [pad(row[c], widths[c]) for c in range(len(COLUMNS) - 1)] + [row[-1]]
            lines.append(("  " + "  ".join(cells)).rstrip())
    n, chars, secs = totals([r for r in records if not r["error"]])
    lines.append("")
    lines.append("合计：%d 篇，%d 字，预计朗读约 %s" % (n, chars, mmss(secs)))
    todo = todo_lines(records)
    lines.append("需要处理：%s" % ("无" if not todo else ""))
    lines += ["  - " + t for t in todo]
    return "\n".join(lines) + "\n"


def md_cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def render_md(folder, records, unsupported, cpm, cpm_given, max_chars, min_chars):
    lines = ["# 运动会加油稿投稿清单", ""]
    lines += ["- " + t for t in header_lines(folder, records, unsupported, cpm, cpm_given,
                                             max_chars, min_chars)]
    for group, recs in group_records(records):
        n, chars, secs = totals(recs)
        lines += ["", "## %s（%d 篇，合计 %d 字，约 %s）" % (group, n, chars, mmss(secs)), ""]
        lines.append("| " + " | ".join(COLUMNS) + " |")
        lines.append("|" + "---|" * len(COLUMNS))
        for i, rec in enumerate(recs, 1):
            lines.append("| " + " | ".join(md_cell(c) for c in row_cells(i, rec)) + " |")
    n, chars, secs = totals([r for r in records if not r["error"]])
    lines += ["", "**合计**：%d 篇，%d 字，预计朗读约 %s" % (n, chars, mmss(secs)), ""]
    todo = todo_lines(records)
    lines.append("**需要处理**：%s" % ("无" if not todo else ""))
    lines += ["- " + md_cell(t) for t in todo]
    return "\n".join(lines) + "\n"


def render_csv(records):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("项目", "序号", "文件", "标题", "班级", "作者", "对象", "字数", "朗读字数",
                     "预计秒数", "档位", "项目来源", "提示"))
    for group, recs in group_records(records):
        for i, r in enumerate(recs, 1):
            writer.writerow((group, i, r["file"], r["title"], r["klass"], r["author"], r["target"],
                             r["chars"], r["spoken"], r["seconds"], r["tier"], r["source"],
                             "；".join(r["notes"])))
    for r in records:
        if r["error"]:
            writer.writerow(("读取失败", "", r["file"], "", "", "", "", "", "", "", "", "",
                             r["error"]))
    return buf.getvalue()


def write_atomic(path, text, encoding):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise UserError(2, "输出目录不存在：%s" % directory)
    try:
        fd, tmp = tempfile.mkstemp(prefix=".cheer_list-", suffix=".tmp", dir=directory)
    except OSError as exc:
        raise UserError(2, "写不了输出文件 %s：%s" % (path, error_text(exc)))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise UserError(2, "写不了输出文件 %s：%s" % (path, error_text(exc)))
        raise


# ---------------------------------------------------------------- 主流程

def run_calibrate(sample, seconds_text):
    try:
        seconds = positive_number(seconds_text)
    except argparse.ArgumentTypeError as exc:
        raise UserError(1, "--calibrate 的秒数%s" % exc)
    if not os.path.isfile(sample):
        raise UserError(2, "找不到样稿文件：%s" % sample)
    try:
        text, _ = read_text(sample)
    except (OSError, ValueError) as exc:
        raise UserError(2, "读不了样稿 %s：%s" % (sample, error_text(exc)))
    _, body = split_meta(text)
    spoken = count_spoken(body)
    if spoken == 0:
        raise UserError(1, "样稿里没有可朗读的文字：%s" % sample)
    cpm = spoken * 60.0 / seconds
    print("样稿 %s：朗读字数 %d，用时 %g 秒 → 每分钟约 %.0f 字" % (sample, spoken, seconds, cpm))
    print("之后统计时加上：--cpm %.0f" % cpm)
    lo, hi = CALIBRATE_SANE
    if cpm < lo or cpm > hi:
        print("提醒：这个语速偏离常见朗读速度较多，请确认秒数没有填成分钟数、计时没有漏掉或多算停顿。")
    return 0


def run(argv):
    args = build_parser().parse_args(argv)
    if args.calibrate:
        if args.folder:
            raise UserError(1, "--calibrate 单独使用，不要同时给稿件文件夹")
        return run_calibrate(*args.calibrate)
    if not args.folder:
        raise UserError(1, "缺少稿件文件夹。例：python3 cheer_list.py 稿件/ --max-chars 100")
    if args.max_chars and args.min_chars and args.min_chars > args.max_chars:
        raise UserError(1, "--min-chars（%d）不能大于 --max-chars（%d）" % (args.min_chars, args.max_chars))

    folder = args.folder
    if not os.path.exists(folder):
        raise UserError(2, "找不到文件夹：%s" % folder)
    if not os.path.isdir(folder):
        raise UserError(2, "%s 不是文件夹；请给放稿件的文件夹路径" % folder)

    skip = os.path.realpath(args.out) if args.out else ""
    if skip and os.path.splitext(skip)[1].lower() == TEXT_SUFFIX and inside(skip, folder):
        raise UserError(1, "--out 不能是稿件文件夹里的 .txt，会覆盖或混进稿件；换个位置或用 .md/.csv")

    try:
        rels, unsupported = collect(folder, args.recursive, skip)
    except OSError as exc:
        raise UserError(2, "读不了文件夹 %s：%s" % (folder, error_text(exc)))
    if not rels:
        hint = "；发现 %d 个 Word/PDF 等文件，请另存为 .txt" % len(unsupported) if unsupported else ""
        raise UserError(2, "文件夹里没有 .txt 稿件：%s%s" % (folder, hint))

    cpm = args.cpm or DEFAULT_CPM
    records = analyze(folder, rels, cpm, args.max_chars, args.min_chars)
    if all(r["error"] for r in records):
        for r in records:
            sys.stderr.write("读取失败：%s（%s）\n" % (r["file"], r["error"]))
        raise UserError(2, "%d 篇稿件都读不了，没有生成清单" % len(records))

    if args.format == "csv":
        text = render_csv(records)
    elif args.format == "md":
        text = render_md(folder, records, unsupported, cpm, bool(args.cpm),
                         args.max_chars, args.min_chars)
    else:
        text = render_text(folder, records, unsupported, cpm, bool(args.cpm),
                           args.max_chars, args.min_chars)

    if args.out:
        write_atomic(args.out, text, "utf-8-sig" if args.format == "csv" else "utf-8")
        ok = sum(1 for r in records if not r["error"])
        print("已写入 %s（%d 篇）" % (args.out, ok))
    else:
        sys.stdout.write(text)
    failed = sum(1 for r in records if r["error"])
    if failed:
        sys.stdout.flush()
        sys.stderr.write("注意：%d 篇读取失败，已列在清单末尾。\n" % failed)
    return 0


def main(argv=None):
    try:
        return run(argv)
    except UserError as exc:
        sys.stderr.write("错误：%s\n" % exc.message)
        return exc.code
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）；未完成的临时文件已清理。\n")
        return 130
    except BrokenPipeError:
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
