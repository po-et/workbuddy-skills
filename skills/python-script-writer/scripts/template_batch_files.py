#!/usr/bin/env python3
"""模板一：文件批处理。把 SRC 下的 .txt 转成 UTF-8 写到 DST；原件不动，已处理的跳过，
单个文件失败记日志、不拖垮整批。只用 Python 标准库。

用法：
  python3 template_batch_files.py --src in --dst out --dry-run   # 先看计划，不写任何文件
  python3 template_batch_files.py --src in --dst out             # 真跑；中断后重跑会跳过已完成的

改成别的批处理（改名、裁图、替换文本）：只改 plan() 的匹配规则和 process()。
退出码：0 全部成功；1 参数错误；2 输入目录不存在或输出目录建不了；3 有文件处理失败（看日志）；130 Ctrl+C 中断。
"""
import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("job")
FMT = "%(asctime)s %(levelname)s %(message)s"
EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_PARTIAL, EXIT_INTERRUPTED = 0, 1, 2, 3, 130


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1，和「文件错误」分开
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n" % message)


def plan(src, dst):
    """列出要处理的 (输入, 输出)。幂等：输出已存在且不比输入旧就跳过。"""
    for p in sorted(src.glob("*.txt")):
        out = dst / p.name
        if not (out.exists() and out.stat().st_mtime >= p.stat().st_mtime):
            yield p, out


def process(p, out):
    """处理一个文件：先写 .part 再改名，中途失败不留半截文件。"""
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")  # GBK 的超集；再失败就抛给 main 记日志
    tmp = out.parent / (out.name + ".part")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 全部成功；1 参数错误；2 目录问题；3 部分失败；130 中断")
    ap.add_argument("--src", type=Path, required=True, help="输入目录")
    ap.add_argument("--dst", type=Path, required=True, help="输出目录（不存在会自动建）")
    ap.add_argument("--dry-run", action="store_true", help="只列计划，不写任何文件")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=FMT)

    if not a.src.is_dir():
        log.error("输入目录不存在：%s（检查路径拼写，或先 ls 看一眼）", a.src)
        return EXIT_IO
    if a.src.resolve() == a.dst.resolve():
        log.error("--src 和 --dst 不能是同一个目录：原件要保持不动")
        return EXIT_ARGS

    todo = list(plan(a.src, a.dst))
    log.info("待处理 %d 个", len(todo))
    if a.dry_run:
        for p, out in todo:
            log.info("[dry-run] %s -> %s", p, out)
        return EXIT_OK

    try:
        a.dst.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.error("建不了输出目录 %s：%s（检查权限或磁盘空间）", a.dst, e)
        return EXIT_IO

    ok = bad = 0
    for p, out in todo:
        try:
            process(p, out)
            ok += 1
        except Exception as e:  # 单条失败不拖垮整批，但一定记下来
            bad += 1
            log.error("失败 %s：%s", p, e)
    log.info("计划 %d = 成功 %d + 失败 %d", len(todo), ok, bad)
    return EXIT_PARTIAL if bad else EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        log.warning("已中断：已完成的文件保留，重跑会自动跳过它们")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
