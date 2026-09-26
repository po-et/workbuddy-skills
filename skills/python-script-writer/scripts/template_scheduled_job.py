#!/usr/bin/env python3
"""模板三：定时任务外壳。防重叠（锁文件）、日志落文件、凭据只从环境变量读、失败非 0 退出。
只用 Python 标准库。把 run_job() 换成你自己的任务，其余不用动。

示例任务：统计 WORKDIR/in 下每个 .csv 的数据行数，写到 WORKDIR/out/daily_count.csv。

用法（凭据放在只有你能读的 job.env 里：一行 export REPORT_TOKEN=...，chmod 600）：
  . ./job.env && python3 template_scheduled_job.py --dry-run          # 先手动试一次
  . ./job.env && python3 template_scheduled_job.py --workdir /home/you/jobs
crontab（PATH 很短，解释器和脚本都写绝对路径；时间按机器时区，先用 date 确认）：
  30 7 * * * . /home/you/jobs/job.env && /usr/bin/python3 /home/you/jobs/template_scheduled_job.py
Windows 任务计划程序的写法见 references/more-scenarios.md。

退出码：0 成功，或上轮未结束本轮跳过；1 参数错误；2 缺环境变量或读写失败；3 任务本身失败；130 中断。
"""
import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger("job")
FMT = "%(asctime)s %(levelname)s %(message)s"
EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_JOB, EXIT_INTERRUPTED = 0, 1, 2, 3, 130
TOKEN_ENV = "REPORT_TOKEN"  # 凭据只从环境变量读，不写进脚本、不打进日志


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n" % message)


def run_job(workdir, token, dry_run):
    """示例任务，换成你的逻辑。要调接口时 token 从参数拿，别再读一遍环境变量。"""
    src, dst = workdir / "in", workdir / "out"
    if not src.is_dir():
        raise FileNotFoundError("输入目录不存在：%s" % src)
    counts = []
    for p in sorted(src.glob("*.csv")):
        with open(p, encoding="utf-8-sig", newline="") as f:
            counts.append((p.name, max(0, sum(1 for _ in csv.reader(f)) - 1)))  # 减去表头
    log.info("统计了 %d 个文件", len(counts))
    if dry_run:
        for name, n in counts:
            log.info("[dry-run] %s %d 行", name, n)
        return
    dst.mkdir(parents=True, exist_ok=True)
    out = dst / "daily_count.csv"
    tmp = out.with_name(out.name + ".part")  # 先写临时文件再改名，重跑覆盖、不追加
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["文件", "行数", "统计时间"])
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            w.writerows([(name, n, now) for name, n in counts])
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()
    log.info("已写出 %s", out)


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功或跳过；1 参数错误；2 缺变量或读写失败；3 任务失败；130 中断")
    ap.add_argument("--workdir", type=Path, default=Path(__file__).resolve().parent,
                    help="放 in/、out/、job.log、job.lock 的目录（默认脚本所在目录；cron 的工作目录不是它）")
    ap.add_argument("--dry-run", action="store_true", help="只统计、只写日志，不写结果")
    a = ap.parse_args(argv)

    workdir = a.workdir.resolve()
    if not workdir.is_dir():
        sys.stderr.write("工作目录不存在：%s\n" % workdir)
        return EXIT_IO
    try:
        logging.basicConfig(filename=str(workdir / "job.log"), level=logging.INFO, format=FMT)
    except OSError as e:
        sys.stderr.write("写不了日志 %s：%s\n" % (workdir / "job.log", e))
        return EXIT_IO
    logging.getLogger().addHandler(logging.StreamHandler())  # 手动跑时屏幕上也能看到

    token = os.environ.get(TOKEN_ENV)
    if not token:
        log.error("缺少环境变量 %s：先在 job.env 里 export 再运行（crontab 行里先 . job.env），不要写进脚本", TOKEN_ENV)
        return EXIT_IO

    lock = workdir / "job.lock"
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        age = (time.time() - lock.stat().st_mtime) / 60
        log.warning("%s 已存在 %.0f 分钟，上轮可能还没跑完，本轮跳过；确认上轮已被强杀后手动删除它", lock, age)
        return EXIT_OK
    except OSError as e:
        log.error("建不了锁文件 %s：%s", lock, e)
        return EXIT_IO
    try:
        os.write(fd, str(os.getpid()).encode())  # 锁里记下进程号，方便排查
        run_job(workdir, token, a.dry_run)
        return EXIT_OK
    except Exception:  # 定时任务没人盯着：完整报错栈写进日志，再以非 0 退出
        log.exception("任务失败")
        return EXIT_JOB
    finally:
        os.close(fd)
        lock.unlink()


def run():
    try:
        return main()
    except KeyboardInterrupt:
        log.warning("已中断：锁文件已清理，结果没有写出半截")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
