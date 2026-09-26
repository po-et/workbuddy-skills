#!/usr/bin/env python3
"""批量把 Markdown 转成 Word：调用 pandoc，保持目录结构，单个文件失败不影响其余文件。

用法：
  python3 md_batch.py docs build                  docs 下所有 .md → build 下同名 .docx
  python3 md_batch.py docs build --dry-run        只列出会转哪些文件，不调用 pandoc
  python3 md_batch.py docs build --ref ref.docx   指定样式模板（默认用运行目录下的 ref.docx，没有就用 pandoc 默认样式）
  python3 md_batch.py docs build -- --toc         -- 之后的参数原样传给 pandoc

每个文件执行的命令与 SKILL.md 的 bash 版相同：
  pandoc 源文件 -o 目标.docx --resource-path=源文件所在目录 [--reference-doc=ref.docx] [-- 之后的参数]
区别只在：先写到输出目录里的临时文件，成功后再改名，失败、超时或中断都不会留下半截 .docx。

选项：
  --timeout 秒   单个文件的超时，默认 120；超时的 pandoc 进程会被结束
  --retries 次   失败或超时后重试的次数，默认 1，最多 2
  --pandoc 路径  pandoc 不在 PATH 里时指定

退出码：
  0    全部成功
  3    有文件失败或超时（清单见 输出目录/errors.log）
  4    找不到 pandoc
  1    参数错误，或源目录里没有 .md 文件
  2    源目录读不了，或输出目录、日志写不了
  130  手动中断（已完成的文件保留，日志照常写出）

只用 Python 标准库；不联网。
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_FAILED, EXIT_NO_PANDOC, EXIT_INTERRUPTED = 0, 1, 2, 3, 4, 130
MAX_RETRIES = 2


class Parser(argparse.ArgumentParser):
    """参数错误时用退出码 1 和中文提示。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用法示例：python3 md_batch.py docs build\n" % message)
        sys.exit(EXIT_ARGS)


def find_sources(src, out):
    """递归找 .md，跳过输出目录本身，按路径排序保证每次顺序一致。"""
    out_resolved = out.resolve()
    files = []
    for path in sorted(src.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(out_resolved)
            continue  # 输出目录在源目录里面时，不把它当源文件
        except ValueError:
            files.append(path)
    return files


def write_log(path, lines):
    """日志也先写临时文件再替换。"""
    fd, tmp = tempfile.mkstemp(prefix=".errors.", suffix=".log.tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def convert_one(pandoc, src_file, dst, ref, extra, timeout, retries, log):
    """转一个文件；返回 "OK" / "FAIL" / "TIMEOUT"。"""
    tmp = dst.with_name(".%s.part-%d%s" % (dst.stem, os.getpid(), dst.suffix))
    cmd = [pandoc, str(src_file), "-o", str(tmp), "--resource-path=%s" % src_file.resolve().parent]
    if ref:
        cmd.append("--reference-doc=%s" % ref)
    cmd.extend(extra)
    status = "FAIL"
    try:
        for attempt in range(1, retries + 2):
            try:
                proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                log.append("   第 %d 次：超过 %g 秒，已结束 pandoc 进程" % (attempt, timeout))
                status = "TIMEOUT"
                continue
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            if err:
                log.extend("   " + line for line in err.splitlines())
            if proc.returncode == 0 and tmp.exists():
                os.replace(str(tmp), str(dst))
                return "OK"
            log.append("   第 %d 次：pandoc 退出码 %d" % (attempt, proc.returncode))
            status = "FAIL"
        return status
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv:
        cut = argv.index("--")
        argv, extra = argv[:cut], argv[cut + 1:]

    parser = Parser(description="批量把 Markdown 转成 Word（调用 pandoc，失败不中断）")
    parser.add_argument("src", help="源目录，递归找 .md")
    parser.add_argument("out", help="输出目录，保持源目录的层级")
    parser.add_argument("--ref", help="样式模板 .docx；默认用运行目录下的 ref.docx（有的话）")
    parser.add_argument("--timeout", type=float, default=120.0, help="单个文件超时秒数，默认 120")
    parser.add_argument("--retries", type=int, default=1, help="失败或超时后的重试次数，默认 1，最多 2")
    parser.add_argument("--pandoc", default="", help="pandoc 可执行文件路径，默认从 PATH 找")
    parser.add_argument("--dry-run", action="store_true", help="只列出会转换的文件")
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0 秒")
    if not 0 <= args.retries <= MAX_RETRIES:
        parser.error("--retries 只能是 0 到 %d" % MAX_RETRIES)
    ref, ref_shown = None, "无（用 pandoc 默认样式）"
    if args.ref:
        if not Path(args.ref).is_file():
            parser.error("找不到样式模板：%s" % args.ref)
        ref, ref_shown = str(Path(args.ref).resolve()), args.ref
    elif Path("ref.docx").is_file():
        ref, ref_shown = str(Path("ref.docx").resolve()), "ref.docx（运行目录）"

    src, out = Path(args.src), Path(args.out)
    if not src.is_dir():
        sys.stderr.write("读取失败：源目录不存在或不是文件夹：%s\n" % src)
        return EXIT_FILE
    try:
        sources = find_sources(src, out)
    except OSError as exc:
        sys.stderr.write("读取失败：遍历 %s 时出错：%s\n" % (src, exc))
        return EXIT_FILE
    if not sources:
        sys.stderr.write("%s 里没有 .md 文件，检查源目录是否写对\n" % src)
        return EXIT_ARGS

    pairs = [(f, out / f.relative_to(src).with_suffix(".docx")) for f in sources]
    if args.dry_run:
        print("将转换 %d 个文件（--dry-run，未调用 pandoc）：" % len(pairs))
        for f, dst in pairs:
            print("  %s → %s" % (f, dst))
        print("样式模板：%s" % ref_shown)
        return EXIT_OK

    pandoc = args.pandoc or shutil.which("pandoc")
    if not pandoc or not (Path(pandoc).is_file() or shutil.which(pandoc)):
        sys.stderr.write("找不到 pandoc：先安装 pandoc，或用 --pandoc 指定路径；"
                         "装好后运行 pandoc --version 确认。本脚本的 --dry-run 不需要 pandoc。\n")
        return EXIT_NO_PANDOC

    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("写入失败：建不了输出目录 %s：%s\n" % (out, exc))
        return EXIT_FILE

    log = ["# md_batch.py %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
           "# 样式模板：%s；超时 %g 秒；重试 %d 次" % (ref_shown, args.timeout, args.retries)]
    counts = {"OK": 0, "FAIL": 0, "TIMEOUT": 0}
    failed = []
    code = EXIT_OK
    try:
        for f, dst in pairs:
            rel = f.relative_to(src)
            log.append("== %s" % rel)
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                result = convert_one(pandoc, f, dst, ref, extra, args.timeout, args.retries, log)
            except OSError as exc:
                log.append("   读写出错：%s" % exc)
                result = "FAIL"
            counts[result] += 1
            log.append("   结果：%s" % result)
            print("%-7s %s" % (result, rel))
            if result != "OK":
                failed.append(str(rel))
    except KeyboardInterrupt:
        log.append("== 手动中断：已完成的文件保留，未完成的没有留下半截文件")
        code = EXIT_INTERRUPTED
    log_path = out / "errors.log"
    try:
        write_log(log_path, log)
    except OSError as exc:
        sys.stderr.write("写入失败：日志 %s 写不了：%s\n" % (log_path, exc))
        return EXIT_FILE if code == EXIT_OK else code
    if code == EXIT_INTERRUPTED:
        sys.stderr.write("\n已中断：成功 %d 个，日志见 %s\n" % (counts["OK"], log_path))
        return code
    print("共 %d 个：成功 %d，失败 %d，超时 %d；警告与报错见 %s"
          % (len(pairs), counts["OK"], counts["FAIL"], counts["TIMEOUT"], log_path))
    if failed:
        print("没转成的：%s" % "、".join(failed))
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(EXIT_INTERRUPTED)
