#!/usr/bin/env python3
"""模板二：多个 CSV 合并、按主键去重，出一张总表。只用 Python 标准库。

读 SRC 下所有 .csv（跳过 ~$ 开头的临时文件）：先按 UTF-8 读，不行再按 GB18030（GBK 的超集）读；
全部按文本处理，保住订单号、手机号的前导 0；表头去掉首尾空格；加一列「来源文件」；
按主键去重，后读的覆盖先读的（文件按文件名排序）；写成 UTF-8 带 BOM 的 CSV，Excel 直接打开不乱码。
.xlsx 请先在 Excel 里另存为「CSV UTF-8」，或用 references/excel-pandas.md 里的 pandas 版。

用法：
  python3 template_merge_csv.py --src in --dst out --key 订单号 --dry-run
  python3 template_merge_csv.py --src in --dst out --key 订单号

退出码：0 成功；1 参数错误（含所有文件都没有主键列）；2 输入目录不存在或写不了结果；
        3 有文件读失败被跳过（结果已写出，看日志）；130 Ctrl+C 中断。
"""
import argparse
import csv
import io
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("merge")
FMT = "%(asctime)s %(levelname)s %(message)s"
EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_PARTIAL, EXIT_INTERRUPTED = 0, 1, 2, 3, 130
SOURCE_COL = "来源文件"


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n" % message)


def read_rows(path):
    """读一个 CSV，返回 (表头, 行列表)。编码先 UTF-8 后 GB18030；读不了就抛异常。"""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("既不是 UTF-8 也不是 GBK 编码")
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]  # 表头空格合并前清，否则同名列拆成两列
    body = []
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        item = dict(zip(header, r))
        item[SOURCE_COL] = path.name
        body.append(item)
    return header, body


def merge(files, key):
    """合并并去重。返回 (列顺序, 结果行, 统计)。"""
    columns, all_rows, stats = [], [], {"files": 0, "failed": 0, "no_key": 0, "rows": 0}
    for p in files:
        try:
            header, body = read_rows(p)
        except Exception as e:  # 单个文件坏了不拖垮整批
            stats["failed"] += 1
            log.error("跳过 %s：%s", p.name, e)
            continue
        if key not in header:
            stats["failed"] += 1
            stats["no_key"] += 1
            log.error("跳过 %s：没有主键列「%s」，现有列：%s", p.name, key, "、".join(header) or "（空表）")
            continue
        stats["files"] += 1
        for h in header:
            if h not in columns:
                columns.append(h)
        all_rows.extend(body)
    stats["rows"] = len(all_rows)
    columns.append(SOURCE_COL)

    last, blank = {}, 0
    for i, r in enumerate(all_rows):
        k = r.get(key, "").strip()
        if k:
            last[k] = i
        else:
            blank += 1
    keep, changed = [], []
    seen_first = {}
    for i, r in enumerate(all_rows):
        k = r.get(key, "").strip()
        if not k:
            keep.append(r)  # 主键为空的行没法去重，原样保留并在日志里提示
            continue
        first = seen_first.setdefault(k, r)
        if last[k] == i:
            if first is not r and any(first.get(c, "") != r.get(c, "") for c in columns if c != SOURCE_COL):
                changed.append((k, r[SOURCE_COL], first[SOURCE_COL]))
            keep.append(r)
    for k, new_src, old_src in changed[:10]:  # 只列前 10 个，够人工抽查
        log.info("主键 %s 内容不同：保留 %s 的版本，覆盖 %s 的", k, new_src, old_src)
    if len(changed) > 10:
        log.info("……另有 %d 个主键内容不同，未逐条列出", len(changed) - 10)
    stats.update(kept=len(keep), dup=len(all_rows) - len(keep), changed=len(changed), blank=blank)
    return columns, keep, stats


def write_csv(path, columns, rows):
    """先写 .part 再改名：写到一半出错不会留下半截结果。"""
    tmp = path.with_name(path.name + ".part")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 参数错误；2 目录或写文件问题；3 有文件被跳过；130 中断")
    ap.add_argument("--src", type=Path, required=True, help="放 CSV 的目录")
    ap.add_argument("--dst", type=Path, required=True, help="输出目录（不存在会自动建）")
    ap.add_argument("--key", required=True, help="主键列名，例如 订单号")
    ap.add_argument("--out-name", default="合并结果.csv", help="输出文件名（默认 合并结果.csv）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=FMT)

    if not a.src.is_dir():
        log.error("输入目录不存在：%s", a.src)
        return EXIT_IO
    files = [p for p in sorted(a.src.iterdir())
             if p.suffix.lower() == ".csv" and not p.name.startswith("~$")]
    xlsx = [p.name for p in a.src.iterdir() if p.suffix.lower() in (".xlsx", ".xls")]
    if xlsx:
        log.warning("没有处理 %d 个 Excel 文件（%s）：请先另存为「CSV UTF-8」", len(xlsx), "、".join(sorted(xlsx)[:3]))
    if not files:
        log.error("%s 下没有 .csv 文件", a.src)
        return EXIT_ARGS

    columns, rows, st = merge(files, a.key.strip())
    if st["files"] == 0:
        log.error("没有一个文件含主键列「%s」：检查列名（包括空格、全角半角）", a.key)
        return EXIT_ARGS
    log.info("%d 个文件 %d 行，去重后 %d 行（重复 %d 行，其中内容不同 %d 个主键；主键为空 %d 行已原样保留）",
             st["files"], st["rows"], st["kept"], st["dup"], st["changed"], st["blank"])

    if a.dry_run:
        log.info("[dry-run] 将写出 %s", a.dst / a.out_name)
    else:
        try:
            a.dst.mkdir(parents=True, exist_ok=True)
            write_csv(a.dst / a.out_name, columns, rows)
        except OSError as e:
            log.error("写不了结果 %s：%s（文件是否正被 Excel 打开？）", a.dst / a.out_name, e)
            return EXIT_IO
        log.info("已写出 %s", a.dst / a.out_name)
    return EXIT_PARTIAL if st["failed"] else EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        log.warning("已中断：结果文件没有写出半截，重跑即可")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
