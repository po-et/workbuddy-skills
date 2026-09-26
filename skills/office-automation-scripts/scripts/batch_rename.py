#!/usr/bin/env python3
"""批量重命名：按「前缀-序号.扩展名」改名。先出对照表，加 --apply 才把改好名的副本放进新文件夹，原件不动。

用法：
  python3 batch_rename.py 待改名 --prefix 2026-09-活动照片                 # 预览，并写 待改名/改名对照表.csv
  python3 batch_rename.py 待改名 --prefix 2026-09-活动照片 --apply         # 副本放进 待改名/已改名/
  python3 batch_rename.py 待改名 --prefix 活动 --sort mtime --digits 4 --ext .jpg,.jpeg

排序：默认按文件名自然排序（IMG_2 排在 IMG_10 前面）；--sort mtime 按修改时间（相机照片常用）。
撤回：原件从不改动，删掉「已改名」文件夹即可。
退出码：0 成功；1 参数错误；2 文件读写失败；3 没有可处理的文件；130 按 Ctrl+C 中断。
只用 Python 标准库，Python 3.8+。
"""
import argparse
import csv
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

BAD_CHARS = re.compile(r'[\\/:*?"<>|]')
MAP_NAME = "改名对照表.csv"


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def atomic_write_csv(path, rows):
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".csv", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(rows)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    ap = ArgParser(description="批量重命名（默认预览；--apply 生成改名后的副本，原件不动）")
    ap.add_argument("folder", help="放待改名文件的文件夹")
    ap.add_argument("--prefix", required=True, help="新文件名前缀，如 2026-09-活动照片")
    ap.add_argument("--start", type=int, default=1, help="起始序号（默认 1）")
    ap.add_argument("--digits", type=int, default=3, help="序号位数，不足补零（默认 3）")
    ap.add_argument("--sort", choices=["name", "mtime"], default="name", help="排序依据（默认 name）")
    ap.add_argument("--ext", help="只处理这些扩展名，逗号分隔，如 .jpg,.png")
    ap.add_argument("--out", help="副本放哪（默认 文件夹/已改名）")
    ap.add_argument("--map", help="对照表路径（默认 文件夹/改名对照表.csv）")
    ap.add_argument("--apply", action="store_true", help="真的生成副本（不加只预览）")
    a = ap.parse_args(argv)

    if BAD_CHARS.search(a.prefix) or not a.prefix.strip():
        ap.error('前缀不能为空，也不能含 \\ / : * ? " < > | 这些字符')
    if not 1 <= a.digits <= 8:
        ap.error("--digits 请给 1 到 8 之间的数")
    if a.start < 0:
        ap.error("--start 不能是负数")

    folder = Path(a.folder).expanduser()
    if not folder.is_dir():
        print("找不到文件夹：%s（检查路径；路径里有空格时用引号包起来）" % folder, file=sys.stderr)
        return 2
    out = Path(a.out).expanduser() if a.out else folder / "已改名"
    map_path = Path(a.map).expanduser() if a.map else folder / MAP_NAME
    exts = None
    if a.ext:
        exts = {e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
                for e in a.ext.split(",") if e.strip()}

    try:
        files = [p for p in folder.iterdir()
                 if p.is_file() and not p.is_symlink() and not p.name.startswith(".")
                 and p.name != map_path.name and not p.name.startswith(".tmp-")
                 and (exts is None or p.suffix.lower() in exts)]
    except PermissionError:
        print("没有权限读取：%s" % folder, file=sys.stderr)
        return 2
    if not files:
        print("文件夹里没有可处理的文件%s。" % ("（扩展名筛选：%s）" % a.ext if a.ext else ""))
        return 3
    if a.sort == "mtime":
        files.sort(key=lambda p: (p.stat().st_mtime, natural_key(p.name)))
    else:
        files.sort(key=lambda p: natural_key(p.name))
    last = a.start + len(files) - 1
    if len(str(last)) > a.digits:
        ap.error("共 %d 个文件，最大序号 %d 超过 %d 位；请改成 --digits %d"
                 % (len(files), last, a.digits, len(str(last))))

    plan = [(p, "%s-%0*d%s" % (a.prefix, a.digits, i, p.suffix)) for i, p in enumerate(files, a.start)]
    try:
        atomic_write_csv(map_path, [("原名", "新名")] + [(p.name, n) for p, n in plan])
    except OSError as e:
        print("对照表写不进去：%s（%s）" % (map_path, e.strerror or e), file=sys.stderr)
        return 2
    for p, n in plan:
        print("%s  ->  %s" % (p.name, n))
    print("\n对照表：%s" % map_path.resolve())
    if not a.apply:
        print("预览：%d 个文件。用表格软件打开对照表核对，确认后加 --apply 生成副本。" % len(plan))
        return 0

    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print("建不了输出文件夹 %s：%s" % (out, e.strerror or e), file=sys.stderr)
        return 2
    copied, skipped, failed = 0, 0, 0
    for p, n in plan:
        target = out / n
        if target.exists():
            skipped += 1
            print("跳过 %s：输出文件夹里已有同名文件" % n)
            continue
        try:
            shutil.copy2(str(p), str(target))
            copied += 1
        except OSError as e:
            failed += 1
            print("复制失败 %s：%s" % (p.name, e.strerror or e), file=sys.stderr)
    print("已生成 %d 个副本，跳过 %d 个，失败 %d 个。副本在：%s" % (copied, skipped, failed, out.resolve()))
    print("原件未改动；要撤回，删掉这个文件夹即可。")
    return 2 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。原件未改动；已生成的副本在输出文件夹里，可整个删掉后重跑。", file=sys.stderr)
        sys.exit(130)
