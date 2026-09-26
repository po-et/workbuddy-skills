#!/usr/bin/env python3
"""文件整理：按扩展名把一个文件夹里的文件分进子文件夹。默认只预览，加 --apply 才移动。

用法：
  python3 organize_files.py ~/Downloads                  # 预览：打印每个文件会去哪
  python3 organize_files.py ~/Downloads --apply          # 执行，并在该文件夹里写一份「移动记录-时间.csv」
  python3 organize_files.py --undo ~/Downloads/移动记录-20260926-101500.csv           # 预览撤回
  python3 organize_files.py --undo ~/Downloads/移动记录-20260926-101500.csv --apply   # 按记录移回原处

规则：只处理这一层的普通文件；跳过隐藏文件、快捷方式（符号链接）和移动记录本身；
目标位置已有同名文件的不动；任何情况下都不删除文件。
退出码：0 成功；1 参数错误；2 文件读写失败；3 没有可处理的文件；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import csv
import datetime as dt
import os
import shutil
import sys
import tempfile
from pathlib import Path

LOG_PREFIX = "移动记录-"
LOG_HEADER = ["原位置", "新位置"]


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


class UserError(Exception):
    """带退出码的友好错误。"""

    def __init__(self, message, code):
        Exception.__init__(self, message)
        self.code = code


def atomic_write_csv(path, rows):
    """先写同目录临时文件，再 os.replace，避免写到一半留下残缺文件。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".csv", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(rows)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def plan_moves(src):
    plan, skipped = [], []
    for f in sorted(src.iterdir(), key=lambda p: p.name.lower()):
        if f.name.startswith(".") or f.is_symlink() or not f.is_file():
            continue
        if f.name.startswith(LOG_PREFIX) and f.suffix.lower() == ".csv":
            continue
        folder = f.suffix.lower().lstrip(".") or "其他"
        dest_dir = src / folder
        dest = dest_dir / f.name
        if dest_dir.exists() and not dest_dir.is_dir():
            skipped.append((f.name, "已有同名文件「%s」，无法建同名文件夹" % folder))
        elif dest.exists():
            skipped.append((f.name, "目标位置已有同名文件，未移动"))
        else:
            plan.append((f, dest))
    return plan, skipped


def organize(src, apply, log_path):
    src = src.resolve()
    if not src.exists():
        raise UserError("找不到文件夹：%s（检查路径；路径里有空格时用引号包起来）" % src, 2)
    if not src.is_dir():
        raise UserError("这不是文件夹：%s" % src, 2)
    try:
        plan, skipped = plan_moves(src)
    except PermissionError:
        raise UserError("没有权限读取：%s（macOS 可能要在「隐私与安全性」里给终端授权）" % src, 2)
    for f, dest in plan:
        print("%s  ->  %s/" % (f.name, dest.parent.name))
    for name, why in skipped:
        print("跳过 %s：%s" % (name, why))
    if not plan:
        print("没有需要移动的文件（共跳过 %d 个）。" % len(skipped))
        return 3
    if not apply:
        print("\n预览：%d 个文件会被移动，%d 个跳过。确认无误后加 --apply 执行。" % (len(plan), len(skipped)))
        return 0
    done = []
    failed = []
    try:
        for f, dest in plan:
            try:
                dest.parent.mkdir(exist_ok=True)
                shutil.move(str(f), str(dest))
                done.append((str(f), str(dest)))
            except OSError as e:
                failed.append((f.name, e.strerror or str(e)))
    finally:
        if done:
            log = Path(log_path).expanduser() if log_path else src / (
                LOG_PREFIX + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".csv")
            try:
                atomic_write_csv(log, [LOG_HEADER] + done)
                print("\n已移动 %d 个文件。移动记录：%s" % (len(done), log.resolve()))
                print("要撤回：python3 \"%s\" --undo \"%s\" --apply" % (Path(__file__).resolve(), log.resolve()))
            except OSError as e:
                print("注意：文件已移动，但移动记录没写成（%s）。请截图上面的清单留底。" % e, file=sys.stderr)
    for name, why in failed:
        print("移动失败 %s：%s" % (name, why), file=sys.stderr)
    return 2 if failed else 0


def undo(log_path, apply):
    log = Path(log_path)
    try:
        with open(log, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except FileNotFoundError:
        raise UserError("找不到移动记录：%s" % log, 2)
    except (OSError, UnicodeDecodeError) as e:
        raise UserError("读不了移动记录 %s：%s" % (log, e), 2)
    if not rows or rows[0] != LOG_HEADER:
        raise UserError("这不是本脚本生成的移动记录（第一行应为：原位置,新位置）", 1)
    back, skipped = [], []
    for row in rows[1:]:
        if len(row) != 2:
            continue
        orig, now = Path(row[0]), Path(row[1])
        if not now.exists():
            skipped.append((now.name, "新位置已经没有这个文件"))
        elif orig.exists():
            skipped.append((now.name, "原位置已有同名文件，未移回"))
        else:
            back.append((now, orig))
    for now, orig in back:
        print("%s  ->  %s" % (now, orig.parent))
    for name, why in skipped:
        print("跳过 %s：%s" % (name, why))
    if not back:
        print("没有可以移回的文件。")
        return 3
    if not apply:
        print("\n预览：%d 个文件会被移回原处。确认无误后加 --apply 执行。" % len(back))
        return 0
    failed = 0
    for now, orig in back:
        try:
            shutil.move(str(now), str(orig))
        except OSError as e:
            failed += 1
            print("移回失败 %s：%s" % (now.name, e.strerror or e), file=sys.stderr)
    for d in sorted({now.parent for now, _ in back}):
        try:
            d.rmdir()  # 只删空文件夹；非空会抛错，直接忽略
        except OSError:
            pass
    print("已移回 %d 个文件。" % (len(back) - failed))
    return 2 if failed else 0


def main(argv=None):
    ap = ArgParser(description="按扩展名整理文件（默认预览，加 --apply 才执行）")
    ap.add_argument("folder", nargs="?", help="要整理的文件夹")
    ap.add_argument("--apply", action="store_true", help="真的移动文件（不加只预览）")
    ap.add_argument("--log", help="移动记录保存位置（默认写在要整理的文件夹里）")
    ap.add_argument("--undo", metavar="移动记录.csv", help="按移动记录把文件移回原处")
    a = ap.parse_args(argv)
    if a.undo and a.folder:
        ap.error("--undo 和文件夹参数不能同时给")
    if not a.undo and not a.folder:
        ap.error("请给出要整理的文件夹，例如：python3 organize_files.py ~/Downloads")
    try:
        if a.undo:
            return undo(Path(a.undo).expanduser(), a.apply)
        return organize(Path(a.folder).expanduser(), a.apply, a.log)
    except UserError as e:
        print(str(e), file=sys.stderr)
        return e.code
    except OSError as e:
        print("文件读写失败：%s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。已完成的移动已写入移动记录，可用 --undo 撤回。", file=sys.stderr)
        sys.exit(130)
