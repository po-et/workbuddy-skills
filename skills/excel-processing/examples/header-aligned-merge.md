# 合成示例：列顺序不同的 Excel 明细合并

> 本例所有订单、日期和金额均为人工合成测试数据；2026-10-09 用 Python 3.12、openpyxl 3.1.5 和技能 0.1.1 实跑。没有真实业务记录、真实用户、腾讯账号或线上服务调用。

目标：将两个文件中明确叫 `明细` 的工作表合并，列顺序不同也能对齐；保留日期类型，附原文件和行号；输入不变，输出另存。

例如用户从腾讯文档获得有权处理的本地 `.xlsx` 后，可以用同一流程准备合并结果，再由用户核对。本技能只做本地整理，不登录或上传，也不证明真实材料的业务正确性。

## 1. 生成两个合成输入

在技能目录中新建 `make_synthetic_inputs.py`，然后运行它。目录已有文件时先报错，不覆盖。

```python
from datetime import date
from pathlib import Path
from openpyxl import Workbook

folder = Path("synthetic-inputs")
folder.mkdir(exist_ok=True)
demo = {
    "east.xlsx": [
        ["订单号", "日期", "金额"],
        ["DEMO-001", date(2026, 10, 1), 120],
        [None, None, None],
        ["DEMO-002", date(2026, 10, 2), 150],
    ],
    "west.xlsx": [
        ["金额", "订单号", "日期"],
        [80, "DEMO-003", date(2026, 10, 3)],
        [60, "DEMO-004", date(2026, 10, 4)],
    ],
}
if any((folder / name).exists() for name in demo):
    raise SystemExit("合成输入已存在，请使用新目录；不覆盖。")
for name, rows in demo.items():
    book = Workbook()
    sheet = book.active
    sheet.title = "明细"
    for row in rows:
        sheet.append(row)
    # 这个额外的工作表不会被合并。
    book.create_sheet("汇总").append(["不是要合并的工作表"])
    book.save(folder / name)
    book.close()
print("已生成两个合成 .xlsx，非真实业务数据。")
```

```bash
python3 make_synthetic_inputs.py
python3 scripts/merge_xlsx.py synthetic-inputs/east.xlsx synthetic-inputs/west.xlsx \
  --sheet 明细 --out combined.xlsx
```

实际运行摘要（文件路径依所在目录而变）：

```json
{
  "sheet": "合并明细",
  "columns": ["订单号", "日期", "金额", "来源文件", "来源工作表", "来源行"],
  "formulas": "reject",
  "rows_read": 5,
  "rows_written": 4,
  "blank_rows_skipped": 1,
  "cached_formula_cells": 0
}
```

完整 JSON 还含每个来源文件的行数与绝对路径。输入 east 的空白行被跳过；另一个工作表 `汇总` 不参与。此脚本保留所有非空明细行，不自动去重。

## 2. 打开新结果抽查

| 订单号 | 日期 | 金额 | 来源文件尾名 | 来源工作表 | 来源行 |
|---|---|---:|---|---|---:|
| DEMO-001 | 2026-10-01 | 120 | east.xlsx | 明细 | 2 |
| DEMO-002 | 2026-10-02 | 150 | east.xlsx | 明细 | 4 |
| DEMO-003 | 2026-10-03 | 80 | west.xlsx | 明细 | 2 |
| DEMO-004 | 2026-10-04 | 60 | west.xlsx | 明细 | 3 |

结果是 4 条明细、6 列（另有表头）；日期读回为 datetime，数字格式保留；表头冻结为 A2 并带筛选。本例实测执行前后两个输入 SHA256 完全一致。

可自行复核原件：执行前后分别运行并比较两个摘要。

```bash
python3 -c 'from pathlib import Path; import hashlib; print({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("synthetic-inputs").glob("*.xlsx")})'
```

同一合并命令再次运行：退出码 **2**，提示 `输出已存在，拒绝覆盖`，原结果 hash 不变。要再处理一批，换新的 `--out`；不直接覆盖原件。

## 3. 两个会主动拦住的错误

**字段不一致**：某文件将 `金额` 改为 `金额(元)` 后，退出码 1，指出缺少 `金额`、多出 `金额(元)`。先确认单位并人工统一，不猜字段，不生成部分结果。

**公式没缓存**：将金额写成 `=SUM(2,3)` 后，默认返回 1 并指出公式所在坐标；即使加 `--formulas cached`，刚由 openpyxl 写入的公式通常没有计算缓存，会报缺缓存。先用 Excel/WPS 计算保存并核对，不能把 None 当成 0。

回归测试另含人工写入 OOXML 缓存值的合成夹具，用于验证 cached 模式确实读取值；这不代表 Excel 已计算过，也不代表真实材料缓存新鲜或正确。

## 4. 源码回归命令

在 workbuddy-skills 源码仓库根目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_excel_processing.py -v
```

覆盖表头重排与严格校验、原件及已有输出不变、明确工作表与表头行、公式缓存策略、日期格式、以 `=` 开头的纯文本、来源坐标、空行、缺文件和损坏文件。详细范围与 [官方文档依据](../references/merge-contract.md) 一起交付。
