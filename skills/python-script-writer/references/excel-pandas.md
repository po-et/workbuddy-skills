# Excel 版合并模板（pandas）

`scripts/template_merge_csv.py` 只用标准库，处理 CSV。要直接读写 `.xlsx`，用下面这段 pandas 版：把两个函数加进模板一（`scripts/template_batch_files.py`），`main()` 里从 `todo = …` 那一行起换成 `return merge(a)`。

> 依赖 `pandas` 与 `openpyxl`（`pip install pandas openpyxl`）。本仓库的测试机没有安装 pandas，这段代码**未在本机实际运行**；交付给用户时照实说明，并让用户先 `--dry-run`。

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

## 和标准库版的差别

| 项目 | 标准库版 `template_merge_csv.py` | pandas 版（本页） |
|---|---|---|
| 能读的格式 | 只读 CSV（UTF-8 或 GBK） | CSV 和 `.xlsx` |
| 前导 0 | 全部按文本读，天然保住 | 靠 `dtype=str` |
| 去重规则 | 后读的覆盖先读的，内容不同的主键逐条写日志（前 10 个） | `drop_duplicates(keep="last")`，不报告哪些主键内容不同 |
| 主键为空的行 | 原样保留并计数 | 会被当成同一个空主键去重，只留最后一行，要先问用户 |
| 写结果 | 先写 `.part` 再改名，UTF-8 带 BOM 的 CSV | 直接写 `.xlsx`；要防半截文件，同样先写临时文件再 `os.replace` |
| 安装 | 不用装任何东西 | 需要 `pip install pandas openpyxl` |

用户不能装包时用标准库版，Excel 文件先另存为「CSV UTF-8」；能装包、又必须保留 Excel 格式时用 pandas 版。
