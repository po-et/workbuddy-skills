---
name: office-automation-scripts
description: "自动化办公——用单次耗时×每周频率算清重复活值不值得自动化，按表格公式、宏、Python 脚本逐级选工具，附文件整理、批量重命名、表格合并、定时提醒模板。当用户说「这个活能不能自动化」「批量重命名文件」「几十个表格怎么合并」时使用。"
author: Captain
version: 0.1.0
display_name: "自动化办公"
display_name_en: "Office Automation"
description_zh: "单次耗时×每周频率算成本、对比搭建维护时间算回本周数；按公式、宏、Python 脚本由低到高选工具；附文件整理、批量重命名、表格合并、到期提醒模板。不碰内部系统与账号密码。"
description_en: "Decide whether a repetitive office task is worth automating and adapt four preview-first script templates."
tags:
  - "自动化办公"
  - "办公自动化"
  - "批量重命名"
  - "表格合并"
  - "文件整理"
  - "定时提醒"
  - "Excel"
  - "Python"
  - "office automation"
examples_zh:
  - "每周要把 20 个门店的表合成一张，这个活能不能自动化"
  - "帮我批量重命名文件，几百张活动照片要改成日期加序号"
  - "几十个表格怎么合并，还想标出每行来自哪个文件"
---

# 自动化办公

**先算账再动手**：多数重复活一个公式就能解决，值得写脚本的是量大、规则稳、出错代价高的几件。
适用：每周都在复制粘贴、合并表格、改文件名、整理文件夹、盯到期日。

## 先判断：值不值得做

```
每周耗时 = 单次耗时 × 每周频率
回本周数 = （搭建耗时 + 一年维护耗时）÷ 每周省下的时间
例：每周合并 20 个门店表，单次 40 分钟；写脚本 3 小时、维护 1 小时、跑完核对 5 分钟
    回本 = 240 ÷（40 − 5）≈ 7 周 → 做
经验线：回本不到一个季度、规则半年不变 → 做；每周不到 15 分钟或格式每月都变 → 先写操作清单
加分：手工易错且错了代价高（发错数、漏人），回本慢些也值得
先问：这一步能不能删掉，或让上游直接给对格式
```

## 选工具：能用低一层就不上高一层

- 第 1 层 表格公式：数据在一两个文件里。匹配用 XLOOKUP／VLOOKUP，汇总用数据透视表，同结构多表合并用 Power Query（版本间有差异）。
- 第 2 层 快捷指令／宏：单个软件里的固定操作。macOS「快捷指令」、Windows 的 Power Automate Desktop、表格软件的「录制宏」。
- 第 3 层 Python 脚本：跨文件夹、上百个文件、要预览和留底，用下面的标准库模板。
- 选层三问：数据在不在一个文件里？步骤会不会常变？你走后谁维护？最后一问答不上就选低一层。

## 四个模板：先预览，再执行

`python3 脚本名.py` 运行；会动文件的模板不加 `--apply` 只预览。原件一律不删不改。

1 文件整理：按扩展名分进子文件夹，重名的留在原处

```python
import sys, shutil
from pathlib import Path
src = Path.home() / "Downloads"   # 要整理的目录
for f in sorted(src.iterdir()):
    dest = src / (f.suffix.lower().lstrip(".") or "其他") / f.name
    if f.is_file() and not f.name.startswith(".") and not dest.exists():
        print(f.name, "->", dest.parent.name)
        if "--apply" in sys.argv:
            dest.parent.mkdir(exist_ok=True); shutil.move(str(f), str(dest))
```

2 批量重命名：前缀加三位序号，先出对照表，改名副本放进新文件夹

```python
import sys, csv, shutil
from pathlib import Path
folder, prefix = Path("待改名"), "2026-09-活动照片"
files = sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
plan = [(p, f"{prefix}-{i:03d}{p.suffix}") for i, p in enumerate(files, 1)]
with open("改名对照表.csv", "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows([("原名", "新名")] + [(p.name, n) for p, n in plan])
out = folder / "已改名"
for p, n in plan:
    print(p.name, "->", n)
    if "--apply" in sys.argv:
        out.mkdir(exist_ok=True); shutil.copy2(p, out / n)
```

3 表格合并：同表头的 CSV 合成一张，末列标来源文件

```python
import csv
from pathlib import Path
header, rows = [], []
for p in sorted(Path("门店报表").glob("*.csv")):
    with open(p, encoding="utf-8-sig", newline="") as f:   # 报编码错改 gbk
        r = csv.reader(f); h = next(r, [])
        header = header or h
        if not h or h != header: print("跳过（空表或表头不一致）", p.name); continue
        rows += [row + [p.name] for row in r]
with open("合并结果.csv", "w", encoding="utf-8-sig", newline="") as f:
    csv.writer(f).writerows([header + ["来源文件"]] + rows)
print("共", len(rows), "行")
```

xlsx 优先用第 1 层 Power Query；非要脚本就装 pandas、openpyxl，用 `pd.read_excel` 逐个读、`pd.concat` 合并。

4 定时提醒：到期日批量变成日历提醒，导入后到期前三天 9:00 弹出

```python
import csv, datetime as dt
EVENT = """BEGIN:VEVENT
UID:{i}-{day}@example.com
DTSTAMP:{now}
DTSTART;VALUE=DATE:{day}
SUMMARY:{name}到期
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:{name}
TRIGGER:-P2DT15H
END:VALARM
END:VEVENT"""
now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//example.com//reminder//CN"]
with open("到期清单.csv", encoding="utf-8-sig") as f:   # 两列：事项,到期日；事项别含英文逗号分号
    for i, row in enumerate(csv.DictReader(f)):
        day = dt.datetime.strptime(row["到期日"].replace("/", "-"), "%Y-%m-%d").strftime("%Y%m%d")
        out.append(EVENT.format(i=i, day=day, now=now, name=row["事项"]))
with open("到期提醒.ics", "w", encoding="utf-8", newline="") as f:
    f.write(("\n".join(out + ["END:VCALENDAR"]) + "\n").replace("\n", "\r\n"))
```

固定周期的提醒直接在日历建重复事件。导入后抽查一条的提醒时间，个别日历应用会忽略导入的提醒。脚本要定时跑，用 crontab 或 Windows「任务计划程序」。

## 最常见的错误

- 没算账就写：一年做两次的活，写了一下午脚本。
- 上来就全自动：没预览、没对照表，改错了回不去。
- 跑完不核对：少合并一个文件没人发现——对一遍行数再抽查。

## 输出契约

1. 先回算账表：单次耗时、每周频率、搭建与维护估时、回本周数、结论（做／写清单／不做）。
2. 写明选哪一层和理由；公式能解决的直接给公式与步骤，不写脚本。
3. 脚本只用标准库或写明要装的包，默认预览，附「怎么运行、怎么核对、怎么撤回」三行。

## 边界与不做什么

- 不接触公司内部系统：不写登录、抓取或批量提交内部系统的脚本，不绕过审批，这类需求找公司 IT。
- 不处理凭据：脚本里不写账号、密码、密钥、验证码，也不教怎么存取；不做自动登录、自动发邮件。
- 公司电脑能不能装 Python、跑脚本、设定时任务，以公司 IT 规定为准。
- 含个人信息、工资、客户数据的表格只在本机处理，不上传任何网站。
