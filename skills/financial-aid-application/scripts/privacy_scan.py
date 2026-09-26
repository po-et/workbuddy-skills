#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""助学金申请书隐私自查：找出证件号、联系方式、详细住址等不该出现在正文里的信息，
标出敏感家庭信息的位置；可选生成隐去证件、联系方式和住址的副本，方便请人帮看。

用法：
  python3 scripts/privacy_scan.py 申请书.txt
  python3 scripts/privacy_scan.py 申请书.docx --out 申请书-脱敏版.txt
  python3 scripts/privacy_scan.py - < 申请书.txt

报告里只显示打码后的片段，不回显完整号码。
--out 只隐去证件、联系方式、住址和长数字串；「低保」「离异」这类敏感家庭信息只提示、不改动，
因为交给资助老师的版本可能需要保留，公开版本删不删由你决定。
--out 不会覆盖原文件；写到已存在的文件需要加 --force；先写临时文件再替换，中途失败不留半个文件。

退出码：0 扫描完成（无论有没有发现）；1 参数或输入有误；2 文件问题（读不了或写不了）；130 用户中断。
只用 Python 标准库；不联网。
"""

import argparse
import collections
import io
import os
import re
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FILE = 2
EXIT_INTERRUPT = 130

MAX_BYTES = 5 * 1024 * 1024
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

Hit = collections.namedtuple("Hit", "start end kind label group")

GROUP_CONTACT = 1   # 证件与联系方式
GROUP_ADDRESS = 2   # 住址与长数字

ID_RE = re.compile(r"(?<![0-9A-Za-z])[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])"
                   r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])")
BANK_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){15,18}(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d(?:[- ]?\d{4}){2}(?!\d)")
LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}[- ]\d{7,8}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
SOCIAL_RE = re.compile(r"(?<![A-Za-z])(?:QQ|qq|微信号?|[Vv][Xx]|[Ww][Xx])\s*(?:号|账号)?\s*[:：]?\s*([A-Za-z0-9_-]{5,20})")
ADDRESS_RE = re.compile(r"\d+(?:号楼|栋|幢|单元|室)|(?:路|街|巷|道)\d+号|村[\d一二三四五六七八九十]+组")
ADDRESS_KEEP = set("村组号楼栋幢单元室路街巷道")
PLACE_STOP = set("在住于是的到和及与从往去来我你他她家为向")  # 往前找地名时遇到这些字就停
CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
LONGNUM_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")

# 敏感家庭信息：只提示位置，不隐去
SENSITIVE_RE = re.compile(
    r"最低生活保障|低保|特困|残疾|孤儿|单亲|离异|离婚|去世|病逝|过世|服刑|入狱|"
    r"精神疾病|抑郁|癌|肿瘤|白血病|尿毒症|透析|化疗|欠债|债务")

ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
ID_CODES = "10X98765432"


# argparse 自带的英文报错，换成中文关键词，方便学生看懂
ARGPARSE_ZH = (
    ("unrecognized arguments", "无法识别的参数"),
    ("expected one argument", "缺少取值"),
    ("invalid float value", "不是有效的数字"),
    ("invalid int value", "不是有效的整数"),
    ("invalid choice", "不在可选范围内"),
    ("choose from", "可选"),
    ("argument ", "参数 "),
)

class UsageError(Exception):
    """参数或输入内容不合法，退出码 1。"""


class FileProblem(Exception):
    """文件读写失败或格式无法识别，退出码 2。"""


class Parser(argparse.ArgumentParser):
    """argparse 默认用退出码 2 报参数错，会和「文件问题」撞车，这里统一改成 1。"""

    def error(self, message):
        for en, zh in ARGPARSE_ZH:
            message = message.replace(en, zh)
        raise UsageError("%s（运行 --help 查看用法）" % message)


# ---------------------------------------------------------------- 读取输入

def _docx_text(data, label):
    """从 .docx 里取正文文字（每个段落一行）。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            info = zf.getinfo("word/document.xml")
            if info.file_size > 50 * 1024 * 1024:
                raise FileProblem("%s 的正文部分过大，无法处理" % label)
            root = ET.fromstring(zf.read(info))
    except FileProblem:
        raise
    except (KeyError, zipfile.BadZipFile, ET.ParseError, RuntimeError, ValueError) as exc:
        raise FileProblem("%s 不是可读的 .docx 文件（%s）；可以把文字复制出来另存为 .txt" % (label, exc))
    lines = []
    for para in root.iter(W_NS + "p"):
        parts = []
        for node in para.iter():
            if node.tag == W_NS + "t" and node.text:
                parts.append(node.text)
            elif node.tag == W_NS + "tab":
                parts.append("\t")
            elif node.tag in (W_NS + "br", W_NS + "cr"):
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines)


def read_input(path):
    """读取文件或标准输入，返回 (文本, 来源名)。支持 UTF-8 / GB18030 / UTF-16 文本与 .docx。"""
    if path is None or path == "-":
        if path is None and sys.stdin.isatty():
            raise UsageError("没有输入：请给出文件路径，或用管道传入文本（- 表示标准输入）")
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        label = "标准输入"
    else:
        label = path
        if os.path.isdir(path):
            raise FileProblem("%s 是文件夹，不是文件" % path)
        try:
            with open(path, "rb") as fh:
                data = fh.read(MAX_BYTES + 1)
        except FileNotFoundError:
            raise FileProblem("找不到文件：%s" % path)
        except PermissionError:
            raise FileProblem("没有权限读取：%s" % path)
        except OSError as exc:
            raise FileProblem("读取失败：%s（%s）" % (path, exc.strerror or exc))
    if len(data) > MAX_BYTES:
        raise FileProblem("%s 超过 5MB，不像是一份申请书；请只保留正文" % label)
    if data[:4] == b"PK\x03\x04":
        return _docx_text(data, label), label
    if data[:5] == b"%PDF-":
        raise FileProblem("%s 是 PDF：请把文字复制出来另存为 .txt 再运行" % label)
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise FileProblem("%s 是旧版 Word（.doc）：请另存为 .docx 或 .txt 再运行" % label)
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16"), label
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc), label
        except UnicodeDecodeError:
            continue
    raise FileProblem("%s 的编码无法识别（试过 UTF-8、GB18030、UTF-16）：请另存为 UTF-8 文本" % label)


# ---------------------------------------------------------------- 识别

def id_checksum_ok(value):
    value = value.upper()
    total = sum(int(c) * w for c, w in zip(value[:17], ID_WEIGHTS))
    return ID_CODES[total % 11] == value[17]


def luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect(line):
    """按优先级识别一行里的敏感片段；重叠时保留优先级高的那一个。"""
    found = []
    for m in ID_RE.finditer(line):
        ok = id_checksum_ok(m.group(0))
        found.append(Hit(m.start(), m.end(), "身份证号",
                         "身份证号（校验位通过）" if ok else "疑似身份证号（校验位不符，也可能是别的编号）",
                         GROUP_CONTACT))
    for m in BANK_RE.finditer(line):
        ok = luhn_ok(re.sub(r"\D", "", m.group(0)))
        found.append(Hit(m.start(), m.end(), "银行卡号",
                         "银行卡号（Luhn 校验通过）" if ok else "16-19 位长数字（可能是卡号或账号）",
                         GROUP_CONTACT))
    for regex, kind, label in ((PHONE_RE, "手机号", "手机号"), (LANDLINE_RE, "固定电话", "固定电话"),
                               (EMAIL_RE, "邮箱", "邮箱"), (SOCIAL_RE, "社交账号", "QQ / 微信号")):
        for m in regex.finditer(line):
            found.append(Hit(m.start(), m.end(), kind, label, GROUP_CONTACT))
    for m in ADDRESS_RE.finditer(line):
        start = m.start()
        if line[start] in "路街巷道村":  # 把「河湾村」「人民路」的地名一起算进来，最多往前 4 个字
            steps = 0
            while (start > 0 and steps < 4 and CJK_CHAR_RE.match(line[start - 1])
                   and line[start - 1] not in PLACE_STOP):
                start -= 1
                steps += 1
        found.append(Hit(start, m.end(), "住址", "详细住址（门牌或村组级）", GROUP_ADDRESS))
    for m in LONGNUM_RE.finditer(line):
        found.append(Hit(m.start(), m.end(), "长数字串", "8 位以上数字（学号、证件号还是账号？）", GROUP_ADDRESS))
    kept = []
    for hit in found:  # found 已按优先级排列
        if not any(hit.start < k.end and k.start < hit.end for k in kept):
            kept.append(hit)
    merged = []
    for hit in sorted(kept, key=lambda h: h.start):  # 紧挨着的同类片段（如「5号楼302室」）合成一处
        if merged and merged[-1].kind == hit.kind and merged[-1].end == hit.start:
            merged[-1] = merged[-1]._replace(end=hit.end)
        else:
            merged.append(hit)
    return merged


def mask(kind, text):
    """报告里显示的打码片段：不回显完整号码。"""
    if kind == "住址":
        return "".join(c if c in ADDRESS_KEEP else "*" for c in text)
    if kind == "邮箱":
        local, _, _ = text.partition("@")
        return local[:1] + "***@***"
    if kind == "社交账号":
        m = SOCIAL_RE.match(text)
        account = m.group(1) if m else text
        return text[: len(text) - len(account)] + account[:1] + "*" * (len(account) - 1)
    positions = [i for i, c in enumerate(text) if c.isdigit() or c in "Xx"]
    keep = set(positions[:3] + positions[-2:]) if len(positions) > 6 else set(positions[:1])
    return "".join(c if (i in keep or i not in positions) else "*" for i, c in enumerate(text))


def scan(text):
    """返回 (标识类命中 [(行号, Hit, 原文片段)], 敏感词命中 [(行号, 词)], 隐去后的全文)。"""
    identifiers, sensitive, redacted_lines = [], [], []
    for no, line in enumerate(text.splitlines(), 1):
        hits = detect(line)
        for hit in hits:
            identifiers.append((no, hit, line[hit.start:hit.end]))
        for m in SENSITIVE_RE.finditer(line):
            sensitive.append((no, m.group(0)))
        redacted = line
        for hit in reversed(hits):
            redacted = redacted[:hit.start] + "［已隐去：%s］" % hit.kind + redacted[hit.end:]
        redacted_lines.append(redacted)
    return identifiers, sensitive, "\n".join(redacted_lines) + "\n"


# ---------------------------------------------------------------- 输出

def write_atomic(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise FileProblem("输出目录不存在：%s" % directory)
    try:
        fd, tmp = tempfile.mkstemp(prefix=".privacy_scan-", suffix=".tmp", dir=directory)
    except OSError as exc:
        raise FileProblem(_write_failure(path, exc))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise FileProblem(_write_failure(path, exc))
        raise


def _write_failure(path, exc):
    reason = "没有写入权限" if isinstance(exc, PermissionError) else (exc.strerror or str(exc))
    return "写不了文件：%s（%s）；上面的扫描报告仍然有效，只是副本没有写出" % (path, reason)


def check_out_path(out, source, force):
    if out.lower().endswith((".docx", ".doc", ".pdf")):
        raise UsageError("--out 只能写纯文本，请用 .txt 结尾，例如 --out 申请书-脱敏版.txt")
    if source not in (None, "-") and os.path.exists(out) and os.path.exists(source):
        try:
            if os.path.samefile(out, source):
                raise UsageError("--out 不能和原文件是同一个文件，原文件要保留")
        except OSError:
            pass
    if os.path.isdir(out):
        raise UsageError("--out 指向的是文件夹：%s" % out)
    if os.path.exists(out) and not force:
        raise UsageError("输出文件已存在：%s；确认覆盖请加 --force" % out)


def build_report(label, line_count, identifiers, sensitive):
    out = ["文件：%s（共 %d 行）" % (label, line_count),
           "== 一、证件与联系方式（建议从正文删除；确需提供的，只填在学校指定的表格或系统里）=="]
    contact = [x for x in identifiers if x[1].group == GROUP_CONTACT]
    address = [x for x in identifiers if x[1].group == GROUP_ADDRESS]
    if contact:
        out.extend("  第 %d 行  %s：%s" % (no, hit.label, mask(hit.kind, frag)) for no, hit, frag in contact)
    else:
        out.append("  （未发现）")
    out.append("== 二、住址与长数字（申请书写到县、乡镇一级通常就够，门牌只填在表格里）==")
    if address:
        out.extend("  第 %d 行  %s：%s" % (no, hit.label, mask(hit.kind, frag)) for no, hit, frag in address)
    else:
        out.append("  （未发现）")
    out.append("== 三、敏感家庭信息（只提示，不隐去）==")
    if sensitive:
        out.extend("  第 %d 行「%s」" % item for item in sensitive)
        out.append("  说明：交给辅导员、资助中心的版本按评定需要保留；发到公开群、朋友圈、贴吧的版本要删掉。")
    else:
        out.append("  （未发现）")
    out.append("== 结论 ==")
    out.append("证件与联系方式 %d 处 | 住址与长数字 %d 处 | 敏感家庭信息 %d 处"
               % (len(contact), len(address), len(sensitive)))
    out.append("提醒：脚本认不出人名、学校名和各种病名写法；交出前请再人工读一遍。")
    return "\n".join(out)


def build_parser():
    p = Parser(prog="privacy_scan.py",
               description="助学金申请书隐私自查：证件号、联系方式、住址、长数字与敏感家庭信息；可生成脱敏副本。")
    p.add_argument("file", nargs="?", help="申请书文件（.txt / .md / .docx）；省略或写 - 表示从标准输入读取")
    p.add_argument("--out", help="另存一份隐去证件、联系方式和住址的纯文本副本（.txt），原文件不改")
    p.add_argument("--force", action="store_true", help="--out 指向的文件已存在时允许覆盖")
    return p


def _safe_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _safe_streams()
    try:
        args = build_parser().parse_args(argv)
        if args.out:
            check_out_path(args.out, args.file, args.force)
        text, label = read_input(args.file)
        if not text.strip():
            raise UsageError("%s 里没有文字（空文件）" % label)
        identifiers, sensitive, redacted = scan(text)
        print(build_report(label, len(text.splitlines()), identifiers, sensitive))
        if args.out:
            write_atomic(args.out, redacted)
            print("已写出副本：%s（隐去 %d 处；原文件未改动）" % (args.out, len(identifiers)))
        return EXIT_OK
    except UsageError as exc:
        sys.stderr.write("参数或输入有误：%s\n" % exc)
        return EXIT_USAGE
    except FileProblem as exc:
        sys.stderr.write("文件问题：%s\n" % exc)
        return EXIT_FILE


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）；没写完的副本不会留下。\n")
        sys.exit(EXIT_INTERRUPT)
