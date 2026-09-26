# 更多场景：网络请求、大文件、SQLite、Windows 定时、测试

三个模板覆盖不到时，从这里取一块拼进骨架。每段都只用标准库；除特别注明外，都在本机（macOS，Python 3.12）实际跑过。

## 1. 调接口：超时、有限次重试、4xx 不重试

```python
import json
import time
import urllib.error
import urllib.request


def get_json(url, token=None, timeout=10, retries=2):
    """GET 一个 JSON 接口：每次最多等 timeout 秒；5xx 和网络错误最多重试 retries 次（间隔 1、2 秒）；4xx 直接抛出。"""
    headers = {"Accept": "application/json"}
    if token:  # token 从环境变量来，只放请求头，不打进日志
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == retries:
                raise  # 4xx 是请求本身的问题（地址、权限、参数），重试没用
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2 ** attempt)
```

- 调用方在 `main()` 里捕获 `(urllib.error.URLError, TimeoutError)`：连不上抛前者，连上了但读超时抛后者（本机实测两种都会出现）；记日志后以非 0 退出，别让报错栈直接甩给用户。
- 批量调接口时每次之间 `time.sleep(1)`，别压垮对方；守网站条款与 robots.txt，不写绕过验证码、登录墙、频率限制的代码。

## 2. 大文件：一行一行读，内存和文件大小无关

```python
import csv


def count_by_column(path, column, encoding="utf-8-sig"):
    """流式统计某一列各取值出现的次数；几 GB 的 CSV 也只占几 MB 内存。"""
    counts = {}
    with open(path, encoding=encoding, newline="") as f:
        for row in csv.DictReader(f):
            k = row.get(column, "")
            counts[k] = counts.get(k, 0) + 1
    return counts
```

- 不要 `f.read()`、`f.readlines()` 整个大文件；二进制大文件用 `shutil.copyfileobj` 或 `f.read(1024 * 1024)` 分块。
- 结果写出前先 dry-run 看条数；大文件处理中途被打断，重跑要能跳过已完成的部分（按输出是否存在、或记一个进度文件）。

## 3. SQLite：参数化、一个事务、重跑不重复

```python
import sqlite3


def upsert_orders(db_path, rows):
    """rows 是 (订单号, 客户, 金额) 的列表。按订单号覆盖写入，重跑不会重复；出错整体回滚。"""
    con = sqlite3.connect(db_path)
    try:
        with con:  # 事务：成功自动提交，异常自动回滚
            con.execute("CREATE TABLE IF NOT EXISTS orders "
                        "(order_id TEXT PRIMARY KEY, customer TEXT, amount TEXT)")
            con.executemany(
                "INSERT INTO orders (order_id, customer, amount) VALUES (?, ?, ?) "
                "ON CONFLICT(order_id) DO UPDATE SET customer = excluded.customer, amount = excluded.amount",
                rows)
        return con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    finally:
        con.close()
```

- 永远用 `?` 占位符传值，不拼接 SQL 字符串。
- `ON CONFLICT … DO UPDATE` 需要 SQLite 3.24 以上（`python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` 查看）；更旧的用 `INSERT OR REPLACE`。
- 动别人的生产数据库不在本技能范围；本地 SQLite 文件动手前先复制一份备份。

## 4. Windows 定时任务（schtasks）

> 以下命令在 Windows 的命令提示符里执行；本机是 macOS，**未实际运行**，交付时照实说明，并让用户先手动跑一次 `/Run` 确认。

```
setx REPORT_TOKEN "你的值"
schtasks /Create /SC DAILY /ST 07:30 /TN "DailyReport" /TR "C:\Python312\python.exe C:\jobs\template_scheduled_job.py"
schtasks /Run /TN "DailyReport"
schtasks /Query /TN "DailyReport"
```

- `setx` 设置的是当前用户的环境变量，只对之后新开的进程生效；凭据不要写进脚本或任务命令行。
- python.exe 和脚本都写全路径；路径里有空格时，`/TR` 里用 `\"` 把路径包起来。
- 手动能跑、定时不跑，先看任务是不是以同一个用户身份运行、环境变量是否在该用户下。

## 5. 测试：给 process() 写两个用例

脚本要反复用、或者逻辑有分支时，在脚本旁边放一个 `test_job.py`，改完跑一次：

```python
import tempfile
import unittest
from pathlib import Path

import template_batch_files as job  # 换成你的脚本名（不带 .py）


class ProcessTest(unittest.TestCase):
    def test_gbk_to_utf8_and_no_leftover(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d, "a.txt"), Path(d, "out.txt")
            src.write_bytes("中文内容".encode("gbk"))
            job.process(src, out)
            self.assertEqual(out.read_text(encoding="utf-8"), "中文内容")
            self.assertFalse(Path(d, "out.txt.part").exists())

    def test_plan_skips_finished_files(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d, "in"), Path(d, "out")
            src.mkdir()
            dst.mkdir()
            Path(src, "a.txt").write_text("x", encoding="utf-8")
            self.assertEqual(len(list(job.plan(src, dst))), 1)
            job.process(Path(src, "a.txt"), Path(dst, "a.txt"))
            self.assertEqual(list(job.plan(src, dst)), [])


if __name__ == "__main__":
    unittest.main()
```

```bash
python3 -m unittest test_job -v
```

最少做到：一个正常样例、一个「坏数据」样例、一个「重跑」样例。一次性脚本不写测试也行，但交付前必须在 3–5 个真实样例上先 `--dry-run` 再真跑，核对计划条数 = 成功 + 失败。
