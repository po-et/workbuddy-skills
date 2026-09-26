---
name: python-script-writer
description: "Python 脚本——写一次性的 Python 小脚本：批量处理文件、合并整理 Excel/CSV、每天定时跑的任务，先问清输入输出，再给能直接运行的骨架。当用户说「写个脚本批量改文件」「帮我合并这些 Excel」「每天定时跑一下」时使用。"
author: Captain
version: 0.1.1
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
examples_en:
  - "Write a script that converts 300 GBK-encoded txt files in a folder to UTF-8"
  - "Merge these spreadsheets, dedupe by order ID and produce one combined table"
  - "Run this report on a schedule every day so results are ready before 8 a.m."
---

# Python 脚本

定位一句话：**一次性脚本最怕跑第二遍时把数据弄乱：先问清、先 dry-run、重跑要安全。**

## 何时使用

用户这样说时用本技能：

- 「写个脚本批量改文件：把 300 个 GBK 编码的 txt 转成 UTF-8」
- 「帮我合并这些 Excel，按订单号去重，出一张总表」
- 「每天定时跑一下这个统计，早上 8 点前要出结果」
- 「批量改名这批照片」「把几百个文件里的旧公司名全换掉」
- 「脚本跑一半断了，重跑会不会重复写？」

适用场景：批量改文件、合并清洗 Excel/CSV、每天定时跑小任务这类「写完跑几次就扔」的活。

不适用（遇到时这样处理）：

- 长期运行的服务、多人共用的数据管道、生产部署：说明需要监控、测试和交接，建议交给工程团队；可以先写一个一次性的验证脚本。
- 绕过验证码、登录墙、频率限制的抓取，或批量收集他人个人信息：不写，说明原因。
- 只是问某个 Python 语法或报错含义：直接简答，不走下面的完整流程。

## 流程：先问清，再动手

第 1 步只问不写：最多问 3 个，没问到的按括号里的默认值写进脚本开头的文档字符串。

```
输入  在哪、什么格式与编码、多大（10 个文件还是 10 万行）；贴 3 行样例
输出  写到哪、什么格式（默认写新目录，不动原件）
失败  坏一条是跳过还是整批停（默认跳过、记日志、最后非 0 退出）；中断后重跑会不会重复
环境  Windows 还是 macOS/Linux；Python 版本；能否 pip 装包（不能就用标准库）
```

问清后照骨架写：别的批处理（改名、裁图、替换文本）只改 plan 的匹配规则和 process；交付前在 3–5 个样例上先 dry-run 再真跑，核对计划条数 = 成功 + 失败。

## 骨架：六个要点

模板一 `scripts/template_batch_files.py` 就是骨架，其余模板沿用同样的六点：

1. **argparse ＋ `--dry-run`**：先列计划、不写文件，用户看过再真跑。
2. **`plan()` 与 `process()` 分开**：`plan()` 只列出（输入, 输出），`process()` 只处理一个；换任务只改这两处。
3. **幂等**：输出已存在且不比输入旧就跳过；重跑不追加、不重复。
4. **原子写**：先写 `.part` 临时文件，再 `os.replace` 改名，中途失败不留半截。
5. **单条失败不拖垮整批**：逐条 `try/except` 记日志并计数，最后打印「计划 = 成功 + 失败」。
6. **退出码约定**：0 成功；1 参数错误；2 目录或读写问题；3 部分失败；130 被 Ctrl+C 中断。

## 三个模板：各是一个完整可运行的文件

| 模板 | 文件 | 什么时候用 | 先跑这条 |
|---|---|---|---|
| 一 文件批处理 | `scripts/template_batch_files.py` | 改编码、改名、裁图、替换文本 | `python3 scripts/template_batch_files.py --src in --dst out --dry-run` |
| 二 CSV 合并去重 | `scripts/template_merge_csv.py` | 多张表合并、按主键去重、保住前导 0 | `python3 scripts/template_merge_csv.py --src in --dst out --key 订单号 --dry-run` |
| 三 定时任务外壳 | `scripts/template_scheduled_job.py` | 每天、每小时跑的小任务：防重叠、日志落文件、凭据读环境变量 | `. ./job.env && python3 scripts/template_scheduled_job.py --dry-run` |

- 三个文件都只用标准库，都在本机实际跑通过（含出错路径）。
- 模板二只读 CSV：Excel 先另存为 CSV UTF-8 格式；能装包、又必须直接读写 `.xlsx` 时，用 [references/excel-pandas.md](references/excel-pandas.md) 里的原 pandas 版（依赖 pandas 与 openpyxl，本机未安装、未实际运行）。
- 模板三的 crontab（PATH 很短，解释器写绝对路径；时间按机器时区，先用 `date` 确认）：`30 7 * * * . /home/you/jobs/job.env && /usr/bin/python3 /home/you/jobs/template_scheduled_job.py`。Windows 用任务计划程序，`schtasks` 写法见 [references/more-scenarios.md](references/more-scenarios.md)。手动能跑、定时不跑，多半是定时环境缺变量。
- 调接口（超时＋有限重试）、大文件逐行处理、SQLite、写测试用例，见 [references/more-scenarios.md](references/more-scenarios.md)。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（一句模板） |
|---|---|---|
| 缺关键信息（输入在哪、什么格式、写到哪） | 最多问 3 个；其余按默认值写进脚本开头的文档字符串，交付时标 [待确认] | 「先确认三件事：文件在哪个目录、什么格式（贴 3 行样例）、结果写到哪。其余我按默认值写，标了待确认。」 |
| 样例和描述对不上（说 GBK 样例却是 UTF-8；说按订单号去重，表头却叫「单号」） | 指出矛盾，给两种理解让用户选 | 「你说主键是『订单号』，样例表头是『单号』：是同一列改过名，还是另有一列？」 |
| 超出本技能范围（生产服务、绕过反爬、收集个人信息） | 不写；说明原因和该找谁 | 「长期运行的服务需要监控和交接，建议交给工程团队；我可以先写个一次性的验证脚本。」 |
| 时间紧，只要最小可用版 | 直接用对应模板，只改匹配规则和 `process()`；保留 `--dry-run` 与日志，测试和定时之后再加 | 「先给你最小可用版：一个文件、两条命令，先 dry-run 再真跑，跑通了再补别的。」 |
| 用户坚持越界（把 token 写进脚本、跳过 dry-run 直接删） | 守住：凭据只从环境变量读；删除覆盖类操作必须先 dry-run，由用户看过计划后自己去掉开关 | 「token 写进脚本会跟着文件和日志到处走，我改成从环境变量读；删之前先看 dry-run 的清单。」 |
| 不能装包 | 全部用标准库：CSV 用 csv 模块，Excel 先另存为 CSV | 「装不了 pandas 就用标准库版，Excel 先另存成 CSV UTF-8。」 |
| 运行报错、结果不对 | 请用户贴退出码和日志最后 20 行，按下表定位，不猜 | 「把退出码和日志最后 20 行贴给我，我按退出码对一下是哪一类问题。」 |

三个模板的退出码与常见报错：

| 退出码 / 报错 | 原因 | 修正办法 |
|---|---|---|
| 0 | 全部成功；模板三也包括「上轮没跑完、本轮跳过」 | 模板三看日志里有没有「本轮跳过」 |
| 1「参数错误」 | 少了参数或拼错；模板一 `--src` 与 `--dst` 相同；模板二所有文件都没有主键列 | 看 `--help`；核对列名里的空格、全角半角 |
| 2 | 输入目录不存在、输出目录建不了、结果文件写不了（常见：正被 Excel 打开）；模板三缺环境变量 | 检查路径和权限、关掉 Excel、先 `. ./job.env` |
| 3 | 部分失败：模板一有文件转码失败；模板二有文件被跳过；模板三任务本身报错 | 看日志里的「失败」「跳过」「任务失败」行，修好数据后重跑，已完成的会自动跳过 |
| 130 | 按了 Ctrl+C | 直接重跑，不会留下半截文件 |
| `UnicodeDecodeError` | 文件既不是 UTF-8 也不是 GBK | 请用户贴 3 行样例，确认真实编码后改 `process()` |
| `PermissionError` | 文件被占用或没有权限 | 关掉占用它的程序，或换一个有权限的输出目录 |

## 输出契约

交付物按这个顺序，不增不减：

1. **假设清单**：输入、输出、失败、环境各一行，默认值标 [待确认]。
2. **脚本**：一个完整可运行的文件；写明基于哪个模板、改了哪几处；依赖只列真用到的。
3. **两条命令**：先 `--dry-run`，再真跑。
4. **核对方法**：计划条数 = 成功 + 失败；抽查几行、几个文件。
5. **回退方式**：原件不动、输出在新目录；删掉输出目录即回到原样。
6. **运行说明**：跑过就贴输出摘要，没跑过写「未实际运行」。

占位符规则：用户没给的路径、列名写成脚本顶部的常量，并在假设清单里标 `[待确认：输入目录，默认 ./in]`；需要用户提供的数据或样例写 `[待补：……]`；不编造文件内容和运行结果。

交付前自检（逐条答「是」才交）：

- [ ] 在 3–5 个样例上先 dry-run 再真跑，计划条数 = 成功 + 失败？
- [ ] 重跑一次不会重复写，也不会覆盖原件？
- [ ] 没有 `except: pass`，失败会记日志并以非 0 退出？
- [ ] 凭据只从环境变量读，脚本和日志里没有密码、token？
- [ ] 给 Excel 用的 CSV 是 `utf-8-sig`，大文件逐行或分块读？
- [ ] 如实写明了哪些跑过、哪些没跑过？

## 示例

示例（文件内容为虚构；日志是在 3 个示例文件上实际运行的输出，去掉了时间戳）：

**用户**：写个脚本批量改文件：把文件夹里 300 个 GBK 编码的 txt 转成 UTF-8。

**助手**（先问）：三件事：文件在哪个目录、转完写到哪（默认写新目录，原件不动）？文件里有没有混着本来就是 UTF-8 的？在 Windows 还是 Mac 上跑？

**用户**：都在 txt_gbk 里，写到 txt_utf8，可能混了几个 UTF-8 的，Mac。

**助手**（交付）：

```
假设  输入 txt_gbk/*.txt；输出 txt_utf8/ 同名文件；本来就是 UTF-8 的照样输出（先按 UTF-8 读，失败再按 GB18030 读）
      坏文件跳过、记日志、最后以退出码 3 提示；重跑自动跳过已完成的 [待确认：子目录里的 txt 不处理]
脚本  scripts/template_batch_files.py 原样可用，不用改
```

```bash
python3 template_batch_files.py --src txt_gbk --dst txt_utf8 --dry-run
python3 template_batch_files.py --src txt_gbk --dst txt_utf8
```

```
INFO 待处理 3 个
INFO [dry-run] txt_gbk/001.txt -> txt_utf8/001.txt
INFO [dry-run] txt_gbk/002.txt -> txt_utf8/002.txt
INFO [dry-run] txt_gbk/003.txt -> txt_utf8/003.txt
INFO 待处理 3 个
INFO 计划 3 = 成功 3 + 失败 0
```

- 核对：真跑时「计划 300 = 成功 + 失败」两边对得上；`file txt_utf8/001.txt` 显示 UTF-8；随手打开两三个看中文正常。
- 回退：原件没动，删掉 `txt_utf8` 即可；再跑一次显示「待处理 0 个」，说明重跑安全。
- 运行说明：在 3 个示例文件上实际跑过；你的 300 个文件没跑过，先 dry-run 看条数。

更多完整示例：

- [examples/merge-orders.md](examples/merge-orders.md)：12 个月订单表合并去重，公司电脑不能装包。
- [examples/daily-report-job.md](examples/daily-report-job.md)：每天 7:30 自动统计，cron 定时，含改模板的 diff。

## 常见问题（FAQ）

**Q：我不会 Python，拿到脚本怎么跑？**
A：装好 Python 3，把脚本存成 `.py`，在终端里照给的两条命令跑，先 `--dry-run`。Windows 上一般用 `python` 或 `py` 代替 `python3`。

**Q：能不能直接帮我在我的电脑上跑？**
A：我只能在示例数据上跑并贴出输出；你的真实文件由你自己执行，删除、覆盖类操作一定先看 dry-run 的清单。

**Q：跑到一半断了怎么办？**
A：直接重跑：模板会跳过已完成的，不会重复写，也不会留下半截文件；日志里「失败」的那几条单独看。

**Q：Excel 文件能直接合并吗？**
A：标准库版只读 CSV，先另存为 CSV UTF-8；能装包就用 [references/excel-pandas.md](references/excel-pandas.md) 的 pandas 版。

**Q：定时任务手动能跑、定时不跑？**
A：多半是定时环境缺变量或路径：解释器和脚本写绝对路径，凭据放 job.env 并在命令里先加载，先用 `date` 确认机器时区。

**Q：一次性脚本也要写测试吗？**
A：至少在 3–5 个真实样例上先 dry-run 再真跑；要反复用的，照 [references/more-scenarios.md](references/more-scenarios.md) 第 5 节写两三个用例。

**Q：这和正式的程序有什么区别？**
A：一次性脚本只求跑对、重跑安全、看得懂；要长期运行、多人共用，就需要监控、测试和部署，交给工程团队。

## 常见错误（反模式）

| 错误做法 | 为什么错 | 正确做法 |
|---|---|---|
| `except: pass` 吞掉错误 | 整批显示「成功」，缺了哪些没人知道 | 逐条 `try/except` 记日志、计数，有失败就以非 0 退出 |
| 重跑时追加写（`open(out, "a")`） | 每重跑一次多一份重复行 | 输出存在就跳过；或整份写临时文件再 `os.replace` 覆盖 |
| 直接往目标文件里写 | 中途断了留下半截文件，下次还被当成已完成 | 先写 `.part`，写完再 `os.replace` |
| `open()` 不写 `encoding` | Windows 默认编码不是 UTF-8，中文乱码或报错 | 读写都写 `encoding`；给 Excel 的 CSV 用 `utf-8-sig` |
| 表格按数字读 | 订单号 00123 变成 123 | 按文本读：csv 模块天然是文本，pandas 用 `dtype=str` |
| token 写进脚本或打进日志 | 脚本一转发、日志一上传就泄露 | 只从环境变量读，缺了就报错退出 |
| crontab 里用相对路径、裸 `python3` | cron 的 PATH 很短，工作目录也不是脚本目录 | 解释器、脚本、数据都写绝对路径 |
| 大文件 `f.read()` 一次读完 | 内存爆掉 | 逐行或分块读 |
| 删除、覆盖不先 dry-run | 不可逆，删错了没法挽回 | 默认 dry-run，用户看过计划后自己去掉开关 |

## 边界与不做什么

- 不写绕过验证码、登录墙、频率限制等反爬机制的代码；抓公开数据也要守网站条款与 robots.txt。
- 不经手凭据：密码、token、密钥不写进脚本和日志，也不让用户贴进对话；只从环境变量读，缺了就报错退出。
- 删除、覆盖等不可逆操作先 dry-run，由用户看过计划后自己去掉开关。
- 含他人个人信息的表格先脱敏再给样例；不写批量收集个人信息的脚本。
- 长期运行的服务、多人共用的数据管道、生产部署不在范围内，请交给工程团队。
