---
name: markdown-conversion
description: "Markdown 转换——用 pandoc 在 Markdown 与 Word、HTML、PDF、纯文本间互转并清理乱格式。当用户说「md 转 Word」「md 转 PDF」「Word 转 md」「PDF 中文不显示」「批量转换」时使用。"
author: Captain
version: 0.1.1
display_name: "Markdown 转换"
display_name_en: "Markdown Conversion"
description_zh: "用 pandoc 做 Markdown 与 Word、HTML、PDF、纯文本的互转：常用命令与参数，表格和图片最容易出错的地方，中文字体、行距与分页设置，从网页或 Word 粘贴后的清理规则，批量转换脚本骨架，以及转换前后的检查清单。"
description_en: "Convert between Markdown and Word, HTML, PDF and plain text with pandoc, covering everyday commands, table and image pitfalls, Chinese fonts and page breaks, cleanup rules for text pasted from web pages or Word, a batch conversion script and before-and-after checklists."
tags:
  - "Markdown 转换"
  - "Markdown"
  - "pandoc"
  - "Markdown 转 Word"
  - "Markdown 转 PDF"
  - "Word 转 Markdown"
  - "HTML 转 Markdown"
  - "docx"
  - "格式清理"
  - "document conversion"
examples_zh:
  - "Markdown 转 Word，要交 docx，表格和图片别乱"
  - "md 转 PDF 以后中文全没了，只剩英文和数字"
  - "文件夹里 50 个 md，想批量转换成 Word"
examples_en:
  - "Convert Markdown to Word as a .docx without breaking tables and images"
  - "After converting md to PDF all the Chinese text disappeared; only English and numbers are left"
  - "I have 50 md files in a folder and want to batch convert them to Word"
---

# Markdown 转换

定位一句话：**转换最费时间的不是命令，而是转完的返工；先定谁是母版、目标格式给谁用，再挑参数。**

## 何时使用

用户这样说时用本技能：

- 「md 转 Word，要交 docx，表格和图片别乱」——Markdown 要交成 Word 给人改
- 「md 转 PDF 以后中文全没了」「PDF 报 Unicode character not set up」——转 PDF 定稿
- 「这份 Word / 这个网页想转回 Markdown 维护」
- 「文件夹里 50 个 md，想批量转成 Word」
- 「从网页粘贴过来的格式全乱了，帮我清一下」——粘贴后的清理
- 「md 转成纯文本贴进表单」「转成单文件 HTML 发邮件」

不适用（遇到时这样处理）：

- PDF 要转回 Markdown 并还原版式、扫描件要识别文字 → pandoc 不读 PDF；只能先用 pdftotext 之类工具提取文字再按清理规则整理，版式无法还原；OCR 不在本技能范围。
- 要连接在线文档或内部文档系统、要登录 → 不连接、不登录，请用户导出成 .docx、.md 或 .html 文件再处理。
- Word 本身的排版（目录、页码、题注、论文格式）→ 转「Word 排版」（word-formatting）；公文、合同终稿的格式是否合规，由单位文秘或法务把关。

## 先判断三件事

1. **谁是母版。** 只在一个格式上改，其余都由它生成。Word 版被别人改过，就别再从旧 Markdown 重新生成覆盖：要么把 Word 转回来当新母版，要么让对方批注、你回填。
2. **给谁用。** 要别人改：Word；定稿、打印、审阅：PDF；网页、邮件：HTML；只收纯文本的表单：纯文本。
3. **工具在不在。** `pandoc --version` 记下版本（下文按 pandoc 3.x 写，旧版参数可能不同）；PDF 还要装 xelatex，装不了就走「HTML 加浏览器打印」的流程。转换前先用 `md_check.py` 预检，它不需要 pandoc。

## pandoc 常用命令

```bash
pandoc in.md -o out.docx --reference-doc=ref.docx --toc                # Word，套自己的样式，带目录
pandoc -o ref.docx --print-default-data-file reference.docx            # 导出默认样式模板，在 Word 里改样式
pandoc in.md -s --embed-resources -M pagetitle="标题" -o out.html      # 单文件 HTML，图片内嵌
pandoc in.md --pdf-engine=xelatex -V CJKmainfont="SimSun" -o out.pdf   # 中文 PDF，字体换成本机有的
pandoc in.docx -t gfm --wrap=none --extract-media=assets -o out.md     # Word 转 Markdown，图片解到 assets
pandoc page.html -t gfm-raw_html --wrap=none -o page.md                # 网页转 Markdown，丢掉转不了的 HTML
pandoc in.md -t plain --wrap=none -o out.txt                           # 纯文本
```

- pandoc 默认在 72 列处硬换行，转 Markdown 和纯文本加 `--wrap=none`。
- Word 里的目录是域，打开后右键「更新域」；`-N` 给标题编号。
- 带修订的 Word 默认按「全部接受」转，转前先在 Word 里处理完修订。
- 正文里的 `--`、`...` 和直引号会被改成破折号、省略号和弯引号，技术文档加 `-f markdown-smart`。

## 最容易出错的地方：表格、图片、中文与分页

| 地方 | 症状 | 办法 |
|---|---|---|
| 表格 | 多段落、合并单元格转丢；宽表冲出 PDF 版心 | 管道表每格只能一行：多段落用网格表或拆表；宽表减列或拆表；列宽靠分隔行短横线比例 |
| 图片 | Word 里缺图，或图下多一行「截图」 | 到 md 所在目录运行，或加 `--resource-path`；替代文字写成真正的说明；SVG、WebP 进 PDF 先转 PNG |
| 中文编码 | GBK 文件报错或乱码 | pandoc 只认 UTF-8：`iconv -f GBK -t UTF-8`，或用 md_check.py 的 `--encoding gbk --fix` |
| 中文 PDF | 报 Unicode character not set up；或中文整段消失 | 用 `--pdf-engine=xelatex` 并设 `CJKmainfont` 为本机已装的中文字体 |
| Word 样式 | 字体、行距、页边距改了又回去 | 只能在 ref.docx 的样式里改（正文文本、标题 1……），直接刷格式无效 |
| 分页 | 该分页的地方不分页 | PDF 写 `\newpage`；HTML 用 CSS `break-before`；Word 插入 openxml 分页块 |

每一项的完整说明（列宽规则、图注规则、中文字体名怎么查、行距页边距参数、Word 分页块写法）见 [references/pitfalls.md](references/pitfalls.md)。

## 粘贴后的清理与批量转换

从网页、Word、PDF 复制来的内容，按这七条清理，只动格式不动字：

1. 不间断空格（U+00A0）换成普通空格；零宽空格（U+200B）、正文中间的 BOM（U+FEFF）、软连字符（U+00AD）删掉。
2. 行尾空格全删：Markdown 行尾两个空格等于强制换行，真要换行用行尾反斜杠。
3. 行首的全角空格（U+3000）删掉，缩进交给样式。
4. 一行一断的文字合并回段落，中文行之间不加空格。
5. 加粗的一行冒充标题的，改成真正的 `#`、`##`，层级不跳级。
6. 「1、」「（1）」不是 Markdown 列表，要成列表改成「1. 」；「•」改成「- 」。
7. 代码里的弯引号改回直引号，正文的中文引号不动；链接去掉 utm_ 开头的跟踪参数。

预检与机械清理用脚本（只用 Python 标准库，不需要 pandoc）：

```bash
python3 {baseDir}/scripts/md_check.py in.md                    # 只检查：编码、不可见字符、标题、伪列表、表格列数、图片
python3 {baseDir}/scripts/md_check.py in.md --fix              # 清理第 1–3 条，另存为 in.clean.md，原文件不动
python3 {baseDir}/scripts/md_check.py docs                     # 整个文件夹一次查完，最后给汇总
```

第 4–7 条要人工判断，脚本只报告不改。批量转换用 `md_batch.py`：保持目录结构、文件名有空格也不怕、单个文件失败不影响其余文件，每个文件有超时和重试，先写临时文件再改名：

```bash
python3 {baseDir}/scripts/md_batch.py docs build --dry-run     # 先看会转哪些文件，不需要 pandoc
python3 {baseDir}/scripts/md_batch.py docs build               # 运行目录有 ref.docx 就自动套用
python3 {baseDir}/scripts/md_batch.py docs build -- --toc      # -- 之后的参数原样传给 pandoc
```

只有 bash、没有 Python 的环境，用 [references/batch-bash.md](references/batch-bash.md) 里的 bash 版骨架。

## 转换前后检查清单

转换前：
- [ ] 文件是 UTF-8；标题从 `#` 起、不跳级；每张表列数一致、有表头
- [ ] 图片路径都存在，母版、目标格式、ref.docx 和字体名已定

转换后：
- [ ] Word 导航窗格能看到完整标题层级（说明用的是标题样式，不是加粗正文）
- [ ] 表格列数、合并单元格、表头与原文一致；图片张数一致、没被拉伸、图注不多不少
- [ ] PDF 没有缺字和方框，能搜到中文，表格没冲出页面
- [ ] 链接能点、脚注连续、目录已更新；纯文本里链接地址还在
- [ ] 抽三段与原文逐字比对：引号、破折号、省略号和代码没被改

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（模板） |
|---|---|---|
| E1 缺关键信息：只说「帮我转一下」 | 只问 3 个：从什么转成什么、谁是母版、转出来给谁用；pandoc 版本、字体名、ref.docx 先按默认写并标 [待确认] | 「先确认三件事：从什么格式转成什么？以后在哪个文件上改？转出来给谁用？」 |
| E2 要求自相矛盾：Word 和 Markdown 都在改、都要当母版 | 指出会互相覆盖，给两个选项 | 「Word 被别人改过，再从旧 Markdown 生成会覆盖掉他们的修改。你想①把 Word 转回来当新母版，还是②让对方批注、你回填？」 |
| E3 输入不对：GBK 编码、拿 PDF 当源文件、扫描件 | GBK 先转 UTF-8；PDF 只能提取文字再清理，版式不还原；扫描件的 OCR 不在范围 | 「这份 PDF pandoc 读不了，只能先提取文字再整理，版式没法还原；扫描件要先做 OCR。」 |
| E4 环境缺工具：没有 pandoc 或 xelatex | 没 pandoc：先安装，预检和清理照做（md_check.py 不需要 pandoc）；没 xelatex：走「HTML 加浏览器打印」 | 「这台机器还没有 pandoc，转换这一步做不了；我先把预检和清理做完，装好后一条命令就能转。」 |
| E5 超出范围：连在线文档、要登录、要经手账号密码；公文合同终稿格式合规 | 不连接、不登录、不经手凭据；请用户导出文件；合规交单位文秘或法务 | 「我不连接在线文档，也不经手账号密码。请把文档导出成 .docx 或 .md 发我。」 |
| E6 坚持要「原样还原」文本框、分栏、页眉页脚、批注 | 说明转 Markdown 会丢失或错位，不承诺；给替代：先转正文，版式用 ref.docx 在 Word 里重建 | 「这些版式转 Markdown 会丢失或错位，我没法保证原样。先把正文转好，版式在 Word 里用 ref.docx 重建。」 |
| E7 时间紧，只要能交的最小版 | 最小可用版：一条命令＋三项必查（表格列数、图片张数、中文不缺字）；样式模板和其余清单项随后补 | 「先给你一条能直接跑的命令和三项必查，其余的随后补。」 |

pandoc 常见报错与现象：

| 报错 / 现象 | 原因 | 修正办法 |
|---|---|---|
| `pandoc: command not found`，或提示「不是内部或外部命令」 | 没装 pandoc 或不在 PATH | 安装后 `pandoc --version` 确认；md_batch.py 可用 `--pandoc 路径` |
| Unicode character not set up for use with LaTeX | 默认的 pdflatex 不支持中文 | 加 `--pdf-engine=xelatex` |
| 换了 xelatex，中文整段消失，日志有 Missing character | 没设 CJKmainfont | `-V CJKmainfont="本机已装的中文字体"` |
| Word 里缺图 | 按运行目录找相对路径 | 到 md 目录运行，或加 `--resource-path=docs:docs/img`（Windows 用分号） |
| 汉字之间多出空格 | 段落里的单个换行夹在两个汉字之间 | 加 `-f markdown+east_asian_line_breaks` |
| 转出的 Markdown 每 72 列硬换行 | 默认换行宽度 | 加 `--wrap=none` |

脚本退出码：

| 脚本 | 退出码 | 含义 | 下一步 |
|---|---|---|---|
| md_check.py | 0 / 3 | 没问题 / 有问题（分「可自动清理」「需人工」） | 3 时先 `--fix`，再按「需人工」逐条改 |
| md_check.py | 2 | 找不到文件、不是 UTF-8、输出目录不存在或没权限 | 按提示转编码或换输出路径 |
| md_batch.py | 0 / 3 | 全部成功 / 有文件失败或超时 | 3 时看 输出目录/errors.log，改完同一命令重跑 |
| md_batch.py | 4 | 找不到 pandoc | 安装或 `--pandoc` 指定；`--dry-run` 不需要 pandoc |
| md_batch.py | 2 | 源目录读不了，输出目录或日志写不了 | 换有写权限的输出目录 |
| 两者 | 1 | 参数错误（如 `--retries` 超过 2、`-o` 没配 `--fix`、源目录里没有 .md） | 按提示改参数 |
| 两者 | 130 | 按了 Ctrl+C | 已完成的文件保留，没有半截文件，重跑即可 |

## 输出契约

交付物按下面的固定顺序给出，缺哪部分就在原位置写「待补：原因」，不调换顺序：

1. **方向与母版一行**：源格式 → 目标格式｜母版是哪个文件｜转出来给谁用。
2. **依赖与运行目录**：pandoc 版本（用户 `pandoc --version` 的结果，没有就标 [待确认]）、要不要 xelatex、中文字体名、ref.docx、在哪个目录运行。
3. **可直接复制的命令**：一条一行，行尾注释写用途。
4. **预检结果**：md_check.py 的输出摘要；做了清理的，逐项报删了什么、替换了多少处。
5. **转换后检查清单结果**：逐条「通过」或「需人工核对」（合并单元格、图注、分页一律需人工核对）。
6. **待补 / 待确认清单**。

占位符规则：[待确认] ＝要在用户本机确认的值（字体名、pandoc 版本、ref.docx 路径）；[待补] ＝用户还没提供的文件或内容（样式模板、图片、图注说明）。

交付前自检（逐条答「是 / 否」，有一条「否」就先改再交）：

- [ ] 命令里的文件名、字体名、目录都来自用户，或标了 [待确认]
- [ ] 写明了 pandoc 版本假设（按 3.x）和是否需要 xelatex
- [ ] 转 Markdown 或纯文本的命令带了 `--wrap=none`；中文 PDF 带了 xelatex 和 CJKmainfont
- [ ] 清理只动格式不动字，删了什么、替换了多少处都报了
- [ ] 附了检查清单结果，合并单元格、图注、分页标为「需人工核对」

## 示例

以下为示例，文件名为虚构。

**用户：** md 转 PDF 以后中文全没了，只剩英文和数字。我用的是 `pandoc report.md -o report.pdf --pdf-engine=xelatex`，Mac。

**助手（交付，信息够了不追问）：**

```
方向与母版  report.md → report.pdf（定稿、打印）｜母版：report.md
原因        用了 xelatex 但没设 CJKmainfont，中文会整段消失（日志里有 Missing character）
依赖        pandoc 3.x [待确认：pandoc --version]；xelatex 已能生成 PDF；中文字体名 [待确认]
命令        pandoc report.md --pdf-engine=xelatex -V CJKmainfont="[待确认：本机中文字体名]" -o report.pdf
            版式按需加：-V geometry:margin=2.5cm -V linestretch=1.5 -V papersize=a4
字体名      macOS 在「字体册」里查，只写本机已装的中文字体
预检        python3 {baseDir}/scripts/md_check.py report.md   （有图片、表格时先跑）
转换后检查  □ 没有缺字和方框，能搜到中文   □ 表格没冲出页面   □ 链接能点、脚注连续
待确认      字体名；pandoc 版本
```

更多完整示例：

- [examples/paste-cleanup.md](examples/paste-cleanup.md)：网页粘贴来的乱格式，预检 → 自动清理 → 人工处理 → 清理后全文，输出均为本机实际运行结果；练习用的输入文件是 [examples/messy-input.md](examples/messy-input.md)
- [examples/batch-docx.md](examples/batch-docx.md)：一批 md 批量转 Word，含 `--dry-run`、errors.log 与失败后的处理

## 常见问题（FAQ）

**问：没装 pandoc，能转吗？**
答：转换这一步需要 pandoc。没装时可以先用 md_check.py 做预检和清理（不需要 pandoc），装好后一条命令就能转。

**问：PDF 里中文显示成方框或者整段不见了？**
答：换 `--pdf-engine=xelatex`，并用 `-V CJKmainfont` 指定本机已装的中文字体；字体名写错也会缺字。

**问：Word 里的字体、行距怎么统一？**
答：在 ref.docx 的样式里改（正文文本、标题 1……），生成时用 `--reference-doc` 套上；直接在 Word 里刷格式，下次生成又会回去。

**问：PDF 能转回 Markdown 吗？**
答：pandoc 不读 PDF。只能先用 pdftotext 之类工具提取文字，再按清理规则整理，版式无法还原；扫描件要先 OCR。

**问：批量转换时有几个文件失败了，怎么办？**
答：md_batch.py 不会因为一个文件失败就停下，失败清单和 pandoc 报错都在 输出目录/errors.log；改好源文件后用同一条命令重跑。

**问：能直接帮我把在线文档转好吗？**
答：不连接在线文档、不登录，也不经手账号密码；请导出成 .docx、.md 或 .html 文件，命令在你的电脑上运行。

**问：清理会不会改掉我的内容？**
答：`--fix` 只处理不可见字符、行尾空格和行首全角空格，另存新文件、原文件不动；标题、列表、断行、引号只报告，由你决定。

## 常见错误（反模式）

| 错误做法 | 为什么错 | 正确做法 |
|---|---|---|
| Word 和 Markdown 两边都在改 | 下次生成互相覆盖，别人的修改丢了 | 只在母版上改，其余由它生成 |
| 在 Word 里直接刷字体、行距 | 下次生成全部回到默认样式 | 改 ref.docx 的样式，用 `--reference-doc` 套上 |
| 转 Markdown、纯文本不加 `--wrap=none` | 72 列硬换行，段落被切碎 | 加 `--wrap=none` |
| 技术文档不加 `-f markdown-smart` | 引号、破折号、省略号被改，代码跟着坏 | 加 `-f markdown-smart` |
| 在别的目录运行 pandoc | 相对路径的图片找不到 | 到 md 所在目录运行，或加 `--resource-path` |
| 带修订的 Word 直接转 | 默认按「全部接受」转，没定的修改也进了正文 | 先在 Word 里处理完修订 |
| SVG、WebP 直接进 PDF | 走 LaTeX 容易失败 | 先转成 PNG |
| Word 转 Markdown 不加 `--extract-media` | 图片全丢 | 加 `--extract-media=assets` |
| 用加粗一行冒充标题 | 导航窗格看不到层级，目录也生成不出来 | 改成 `#`、`##`，层级不跳级 |
| 粘贴来的内容不清理就转 | 不可见字符造成奇怪的空格和断行 | 先跑 md_check.py，再 `--fix` |

## 边界与不做什么

- 只处理用户提供的文件和文本，不登录、不连接任何在线文档或内部文档系统，不经手账号、密码、令牌等凭据。
- pandoc 不读 PDF：PDF 转 Markdown 只能先用 pdftotext 之类工具提取文字，再按清理规则整理，版式无法还原；扫描件要 OCR，不在本技能范围。
- 文本框、分栏、页眉页脚、批注等 Word 版式转 Markdown 会丢失或错位，不承诺原样还原。
- 公文、合同等有格式要求的终稿，以单位模板或对方要求为准，是否合规由单位文秘或法务把关。
