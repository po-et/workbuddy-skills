---
name: python-script-writer
description: "Python 脚本——写一次性的 Python 小脚本：批量处理文件、合并整理 Excel/CSV、每天定时跑的任务，先问清输入输出，再给能直接运行的骨架。当用户说「写个脚本批量改文件」「帮我合并这些 Excel」「每天定时跑一下」时使用。"
author: Captain
version: 0.1.0
display_name: "Python 脚本"
display_name_en: "Python Script"
description_zh: "写一次性 Python 脚本：先问清输入、输出、失败时怎么办，再给可直接运行的骨架（argparse、日志、dry-run、幂等重跑）；附文件批处理、Excel/CSV 处理、定时任务三个模板。不写绕过反爬的代码，凭据只从环境变量读。"
description_en: "Write one-off Python scripts that run as delivered: settle inputs, outputs and failure handling first, then build on a skeleton with argparse, logging, dry-run and idempotent reruns, with templates for batch file jobs, Excel/CSV processing and scheduled tasks."
tags:
  - "Python脚本"
  - "python"
  - "自动化脚本"
  - "批量处理"
  - "Excel处理"
  - "CSV"
  - "定时任务"
  - "cron"
  - "办公自动化"
  - "script"
examples_zh:
  - "写个脚本批量改文件：把文件夹里 300 个 GBK 编码的 txt 转成 UTF-8"
  - "帮我合并这些 Excel，按订单号去重，出一张总表"
  - "每天定时跑一下这个统计，早上 8 点前要出结果"
---

# Python 脚本

定位一句话：**一次性脚本最怕跑第二遍时把数据弄乱：先问清、先 dry-run、重跑要安全。**
何时用：批量改文件、合并清洗 Excel/CSV、每天定时跑小任务这类「写完跑几次就扔」的活。

## 流程：先问清，再动手

第 1 步只问不写：最多问 3 个，没问到的按括号里的默认值写进脚本开头的文档字符串。

```
输入  在哪、什么格式与编码、多大（10 个文件还是 10 万行）；贴 3 行样例
输出  写到哪、什么格式（默认写新目录，不动原件）
失败  坏一条是跳过还是整批停（默认跳过、记日志、最后非 0 退出）；中断后重跑会不会重复
环境  Windows 还是 macOS/Linux；Python 版本；能否 pip 装包（不能就用标准库）
```
问清后照骨架写：别的批处理（改名、裁图、替换文本）只改 plan 的匹配规则和 process；交付前在 3–5 个样例上先 dry-run 再真跑，核对计划条数 = 成功 + 失败。

## 骨架 = 模板一：文件批处理（可直接运行）

```python
#!/usr/bin/env python3
"""把 SRC 下的 .txt 转成 UTF-8 写到 DST；原件不动，已处理的跳过，失败记日志、最后非 0 退出。
用法：python3 job.py --src in --dst out --dry-run"""
import argparse, logging, os, sys
from pathlib import Path

log = logging.getLogger("job")
FMT = "%(asctime)s %(levelname)s %(message)s"

def plan(src, dst):  # 幂等：输出已存在且比输入新就跳过
    for p in sorted(src.glob("*.txt")):
        out = dst / p.name
        if not (out.exists() and out.stat().st_mtime >= p.stat().st_mtime):
            yield p, out

def process(p, out):  # 先写 .part 再改名，中途失败不留半截
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")  # GBK 的超集；再失败就抛给 main 记日志
    tmp = out.parent / (out.name + ".part")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, out)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--dst", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format=FMT)
    if not a.src.is_dir():
        log.error("输入目录不存在：%s", a.src)
        return 2
    todo = list(plan(a.src, a.dst))
    log.info("待处理 %d 个", len(todo))
    if a.dry_run:
        for p, out in todo:
            log.info("[dry-run] %s -> %s", p, out)
        return 0
    ok = bad = 0
    for p, out in todo:
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            process(p, out)
            ok += 1
        except Exception as e:  # 单条失败不拖垮整批
            bad += 1
            log.error("失败 %s：%s", p, e)
    log.info("完成 %d，失败 %d", ok, bad)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
```

## 模板二、三：只换骨架的一块

**模板二 Excel/CSV：多表合并、按主键去重**——加上两个函数，main 里 `todo = …` 起换成 `return merge(a)`。
```python
import pandas as pd  # pip install pandas openpyxl

def read(p):  # dtype=str 保住前导 0；表头空格合并前清，否则同名列拆成两列
    df = pd.read_csv(p, dtype=str, encoding="utf-8-sig") if p.suffix == ".csv" else pd.read_excel(p, dtype=str)
    df.columns = df.columns.str.strip()
    return df.assign(来源文件=p.name)

def merge(a, key="订单号"):  # 跳过 ~$ 开头的 Excel 临时文件
    files = [p for p in sorted(a.src.iterdir()) if p.suffix in (".csv", ".xlsx") and not p.name.startswith("~$")]
    df = pd.concat(map(read, files), ignore_index=True)
    n = len(df)
    df = df.drop_duplicates(subset=[key], keep="last")  # 后读的覆盖先读的：先问用户哪份算准
    log.info("%d 个文件 %d 行，去重后 %d 行", len(files), n, len(df))
    if not a.dry_run:
        a.dst.mkdir(parents=True, exist_ok=True)
        df.to_excel(a.dst / "合并结果.xlsx", index=False)
    return 0
```

**模板三 定时任务：防重叠、日志落文件、凭据读环境变量**——加上这段，末行改调 `scheduled_main()`。
```python
BASE = Path(__file__).resolve().parent  # cron 的工作目录不是脚本目录
LOCK = BASE / "job.lock"

def scheduled_main():
    logging.basicConfig(filename=BASE / "job.log", level=logging.INFO, format=FMT)
    if not os.environ.get("REPORT_TOKEN"):  # 凭据只从环境变量读
        log.error("缺少环境变量 REPORT_TOKEN")
        return 2
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:  # 上轮没跑完就跳过；强杀残留的锁需手动删
        log.warning("%s 存在，本轮跳过", LOCK)
        return 0
    try:
        return main()
    finally:
        os.close(fd)
        LOCK.unlink()
```
crontab（PATH 很短，解释器写绝对路径；时间按机器时区，先用 date 确认）：
```
30 7 * * * /usr/bin/python3 /home/you/job.py --src /home/you/in --dst /home/you/out
```
Windows 用「任务计划程序」建每日任务，程序填 python.exe 全路径。手动能跑、定时不跑，多半是定时环境缺变量。

## 输出契约

1. **先复述假设**：输入、输出、失败、环境各一行，默认值标出来。
2. **一个文件 + 两条命令**：脚本完整可运行、依赖只列真用到的；先 `--dry-run` 再真跑，附核对方法（条数、抽查几行）与回退方式。
3. **避开最常见的错误**：不用 `except: pass` 吞错；重跑不追加写重复行；给 Excel 的 CSV 用 `utf-8-sig` 免得中文乱码；大文件逐行或分块读。
4. **如实说明是否运行过**：跑过贴输出摘要，没跑过写「未实际运行」。

## 边界与不做什么

- 不写绕过验证码、登录墙、频率限制等反爬机制的代码；抓公开数据也要守网站条款与 robots.txt。
- 不经手凭据：密码、token、密钥不写进脚本和日志，也不让用户贴进对话；只从环境变量读，缺了就报错退出。
- 删除、覆盖等不可逆操作先 dry-run，由用户看过计划后自己去掉开关。
- 含他人个人信息的表格先脱敏再给样例；不写批量收集个人信息的脚本。
- 长期运行的服务、多人共用的数据管道、生产部署不在范围内，请交给工程团队。
