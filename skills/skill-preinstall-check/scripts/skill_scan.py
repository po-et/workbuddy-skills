#!/usr/bin/env python3
"""静态扫描技能目录，列出风险信号（不是安全认证）。

用法：
    python3 skill_scan.py 技能目录 [--max-mb 5]

只读：不运行、不修改、不上传任何文件；不跟随符号链接；只用 Python 标准库（3.7+）。

输出：每行一个信号「[级别] 原因 | 文件:行号 | 原文」，按 高 → 中 → 低 排序，最后一行是汇总。

退出码：
    0    扫描完成，没有高风险信号（不代表安全）
    1    参数错误（没给目录、多给了参数、--max-mb 不是正数）
    2    路径不存在、不是目录、是压缩包，或目录无法读取
    3    扫描完成，发现高风险信号
    130  被 Ctrl+C 中断，结果不完整
"""
import argparse
import os
import re
import stat
import sys

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_IO = 2
EXIT_HIGH = 3
EXIT_INTERRUPTED = 130

DEFAULT_MAX_MB = 5.0
LEVELS = "高中低"
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar", ".skill")

RULES = [  # 顺序即级别：高 → 中 → 低；同一行命中多条时取最高级
    ("高", "下载后直接执行", r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b|\$\(\s*(curl|wget)|\|\s*iex\b|Invoke-Expression"),
    ("高", "解码或拼接后执行", r"\b(eval|exec)\s*\(|b64decode|base64\s+(-d|--decode)"),
    ("高", "读取密钥或凭据", r"\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.netrc|Login Data|keychain"),
    ("高", "递归强制删除", r"rm\s+-[a-zA-Z]*(rf|fr)|shutil\.rmtree|Remove-Item[^\n]*-Recurse"),
    ("高", "要求绕过规则或瞒着用户", r"(忽略|无视)(之前|以上|先前|所有|系统)[^\n]{0,8}(指令|规则|要求|提示)"
     r"|(?i:ignore (all )?(previous|prior|above) instructions)|不要(告诉|让)用户|无需(用户)?确认|悄悄"),
    ("中", "网络请求", r"requests\.|urllib|urlopen|http\.client|fetch\(|socket\.|\b(curl|wget)\b|Invoke-WebRequest"),
    ("中", "读取环境变量", r"os\.environ|getenv\(|process\.env|\$\{?[A-Z_]*(TOKEN|KEY|SECRET|PASSWORD)"),
    ("中", "删除或改写文件", r"os\.(remove|unlink)|\.unlink\(|\brm\s|Remove-Item|open\([^)]*['\"]w|>\s*~/"),
    ("中", "提权或索要过大权限", r"\bsudo\b|chmod\s+(-R\s+)?777|crontab|launchctl|/etc/|\.(bash|zsh)rc"
     r"|管理员权限|root 权限|关闭(杀毒|防火墙|安全)"),
    ("低", "出现网址", r"https?://"),
    ("低", "疑似混淆的长编码串", r"[A-Za-z0-9+/=]{120,}"),
]
COMPILED = [(level, why, re.compile(pattern)) for level, why, pattern in RULES]


class _Parser(argparse.ArgumentParser):
    """参数错误统一走退出码 1，并给出中文的正确用法。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n正确用法：python3 skill_scan.py 技能目录（路径带空格时加引号）\n" % message)
        sys.exit(EXIT_USAGE)


def _positive_mb(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("--max-mb 需要一个大于 0 的数字，收到 %r" % text)
    if value <= 0:
        raise argparse.ArgumentTypeError("--max-mb 需要一个大于 0 的数字，收到 %r" % text)
    return value


def parse_args(argv):
    parser = _Parser(
        prog="skill_scan.py",
        description="静态扫描技能目录，列出风险信号（不是安全认证）。只读，不运行任何文件。",
    )
    parser.add_argument("root", help="待检查的技能目录（先放进隔离文件夹）")
    parser.add_argument("--max-mb", type=_positive_mb, default=DEFAULT_MAX_MB,
                        help="单个文件超过这个大小（MB）就不逐行扫描，只报「文件过大」；默认 5")
    return parser.parse_args(argv)


def _reason(exc):
    return exc.strerror or exc.__class__.__name__


def scan_file(path, rel, max_bytes):
    """扫描一个普通文件，返回信号列表 [(级别, 原因, 位置, 原文)]。读不了的文件记成信号，不中断整体扫描。"""
    try:
        size = os.path.getsize(path)
        if size > max_bytes:
            return [("中", "文件过大（%.1f MB），未逐行扫描" % (size / 1048576.0), rel, "")]
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        return [("中", "无法读取，未检查（%s）" % _reason(exc), rel, "")]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [("中", "非 UTF-8 文本或二进制文件，无法静态检查", rel, "")]
    found = []
    for no, line in enumerate(text.splitlines(), 1):
        hits = [(level, why) for level, why, pattern in COMPILED if pattern.search(line)]
        if hits:
            found.append((hits[0][0], "、".join(why for _, why in hits), "%s:%d" % (rel, no), line.strip()[:80]))
    return found


def scan_dir(root, max_bytes):
    """遍历目录（不跟随符号链接），返回 (已扫描文件数, 符号链接数, 信号列表)。"""
    found = []
    entries = []  # (相对路径, 绝对路径)
    links = 0

    def on_error(exc):
        where = os.path.relpath(exc.filename, root) if getattr(exc, "filename", None) else "?"
        found.append(("中", "目录无法读取，未检查（%s）" % _reason(exc), where, ""))

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_error, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                try:
                    target = os.readlink(full)
                except OSError as exc:
                    target = "无法读取：%s" % _reason(exc)
                found.append(("中", "符号链接，未跟随（指向 %s）" % target, rel, ""))
                links += 1
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                entries.append((os.path.relpath(full, root).replace(os.sep, "/"), full))

    entries.sort()
    scanned = 0
    for rel, full in entries:
        if any(part.startswith(".") for part in rel.split("/")):
            found.append(("低", "隐藏文件", rel, ""))
        try:
            mode = os.lstat(full).st_mode
        except OSError as exc:
            found.append(("中", "无法读取，未检查（%s）" % _reason(exc), rel, ""))
            continue
        if not stat.S_ISREG(mode):
            found.append(("中", "特殊文件（管道、设备等），未读取", rel, ""))
            continue
        scanned += 1
        found.extend(scan_file(full, rel, max_bytes))

    found.sort(key=lambda item: LEVELS.index(item[0]))  # 稳定排序：同级内保持文件与行号顺序
    return scanned, links, found


def check_root(raw):
    """校验待扫描路径；有问题时返回 (None, 提示)，否则返回 (绝对路径, None)。"""
    root = os.path.abspath(os.path.expanduser(raw))
    if not os.path.exists(root):
        return None, "找不到目录：%s（请确认路径；带空格的路径要加引号）" % root
    if not os.path.isdir(root):
        if root.lower().endswith(ARCHIVE_SUFFIXES):
            return None, "这是压缩包：%s。请先解压到单独的隔离文件夹再扫描（解压不会运行里面的脚本）" % root
        return None, "不是目录：%s（请给技能所在的文件夹，而不是其中某个文件）" % root
    try:
        os.listdir(root)
    except OSError as exc:
        return None, "无法读取目录：%s（%s）" % (root, _reason(exc))
    return root, None


def _configure_streams():
    """控制台编码不是 UTF-8（如部分 Windows 终端）时，替换无法显示的字符，而不是崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv):
    _configure_streams()
    args = parse_args(argv)
    root, problem = check_root(args.root)
    if problem:
        sys.stderr.write(problem + "\n")
        return EXIT_IO

    scanned, links, found = scan_dir(root, int(args.max_mb * 1048576))
    counts = dict((level, sum(1 for item in found if item[0] == level)) for level in LEVELS)
    code = EXIT_HIGH if counts["高"] else EXIT_OK

    lines = ["[%s] %s | %s | %s" % item for item in found]
    extra = "（另有 %d 个符号链接未跟随）" % links if links else ""
    lines.append("")
    lines.append("扫描 %d 个文件%s；风险信号（按行计）：高 %d，中 %d，低 %d"
                 % (scanned, extra, counts["高"], counts["中"], counts["低"]))
    lines.append("关键词静态扫描只能提示风险信号，不是安全认证；没有信号也不等于安全。")
    try:
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
    except BrokenPipeError:
        # 输出被管道提前关闭（如接了 head）：静默收尾，退出码照常反映扫描结果
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    return code


def run(argv):
    try:
        return main(argv)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断：扫描结果不完整，请重新运行。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
