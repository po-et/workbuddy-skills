---
name: markdown-conversion
description: "Markdown 转换——用 pandoc 在 Markdown 与 Word、HTML、PDF、纯文本间互转并清理乱格式。当用户说「md 转 Word」「md 转 PDF」「Word 转 md」「PDF 中文不显示」「批量转换」时使用。"
author: Captain
version: 0.1.0
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
---

# Markdown 转换

定位一句话：**转换最费时间的不是命令，而是转完的返工；先定谁是母版、目标格式给谁用，再挑参数。**
何时用：Markdown 要交成 Word 给人改、转 PDF 定稿、转 HTML 发网页、转纯文本贴进表单；Word 或网页要转回 Markdown 维护；一批文件要批量转换；粘贴过来的格式乱了要清理。

## 先判断三件事

1. **谁是母版。** 只在一个格式上改，其余都由它生成。Word 版被别人改过，就别再从旧 Markdown 重新生成覆盖：要么把 Word 转回来当新母版，要么让对方批注、你回填。
2. **给谁用。** 要别人改：Word；定稿、打印、审阅：PDF；网页、邮件：HTML；只收纯文本的表单：纯文本。
3. **工具在不在。** `pandoc --version` 记下版本（下文按 pandoc 3.x 写，旧版参数可能不同）；PDF 还要装 xelatex，装不了就走「HTML 加浏览器打印」的流程。

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

**表格。** 管道表每格只能写一行，也不能合并单元格；要多段落就用网格表或拆表。Word 里带合并单元格的表转成 Markdown 会被拆开或变成一段 HTML，要逐张对照。表里有一行超过 72 字符时，pandoc 按分隔行 `|---|------|` 的短横线比例分配列宽，想让哪列宽就多写横线。Word 表格的边框底纹由 ref.docx 里名为 Table 的表格样式决定。宽表进 PDF 会冲出版心，减列或拆表。

**图片。** 相对路径按运行 pandoc 的目录找，不按 md 所在目录：到 md 目录下运行，或加 `--resource-path=docs:docs/img`（Windows 用分号分隔）。单独成段、带替代文字的图会变成带图注的图，`![截图](a.png)` 在 Word 里图下会多一行「截图」，替代文字要写成真正的说明。尺寸写 `{width=14cm}` 跟在图片后面，GitHub 不认这个写法。SVG、WebP 走 LaTeX 容易失败，先转成 PNG。Word 转 Markdown 不加 `--extract-media`，图片会丢。

**中文。** pandoc 只认 UTF-8，GBK 文件先 `iconv -f GBK -t UTF-8 in.md > in.utf8.md`。段落里的单个换行夹在两个汉字之间会变成多余空格，加 `-f markdown+east_asian_line_breaks`。Word 的字体、行距、页边距、页眉页脚只能在 ref.docx 的样式里改，直接刷格式无效：正文用的是 Body Text（中文 Word 叫「正文文本」）和 First Paragraph，标题是「标题 1」起；中文字体在样式的「中文字体」一栏，和西文字体分开设。PDF 默认的 pdflatex 遇到中文报 Unicode character not set up for use with LaTeX；换了 xelatex 没设 CJKmainfont，中文会整段消失，日志里有 Missing character。字体名要写本机已装的：Windows 如 SimSun、Microsoft YaHei，macOS 在「字体册」里查，Linux 用 `fc-list :lang=zh family`。版式用 `-V geometry:margin=2.5cm -V linestretch=1.5 -V papersize=a4`。

**分页。** PDF 在要分页处写 `\newpage`；HTML 打印用 CSS `h1 { break-before: page; }`；Word 插入这段原始块：

~~~
```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```
~~~

## 粘贴后的清理与批量转换

从网页、Word、PDF 复制来的内容，按这七条清理，只动格式不动字：

1. 不间断空格（U+00A0）换成普通空格；零宽空格（U+200B）、正文中间的 BOM（U+FEFF）、软连字符（U+00AD）删掉。
2. 行尾空格全删：Markdown 行尾两个空格等于强制换行，真要换行用行尾反斜杠。
3. 行首的全角空格（U+3000）删掉，缩进交给样式。
4. 一行一断的文字合并回段落，中文行之间不加空格。
5. 加粗的一行冒充标题的，改成真正的 `#`、`##`，层级不跳级。
6. 「1、」「（1）」不是 Markdown 列表，要成列表改成「1. 」；「•」改成「- 」。
7. 代码里的弯引号改回直引号，正文的中文引号不动；链接去掉 utm_ 开头的跟踪参数。

先查有哪些不可见字符：

```bash
python3 -c "import sys;t=open(sys.argv[1],encoding='utf-8').read();[print(hex(ord(c)),t.count(c)) for c in ' ​﻿­　' if c in t]" in.md
```

批量转换骨架（macOS 自带的 bash 也能跑，Windows 用 Git Bash 或 WSL），保持目录结构，文件名有空格也不怕，失败不静默：

```bash
#!/usr/bin/env bash
# 用法：bash md2docx.sh 源目录 输出目录；ref.docx 放在运行目录
set -u
src=${1:-docs}; out=${2:-build}; fail=0
mkdir -p "$out"; : >"$out/errors.log"
while IFS= read -r -d '' f; do
  rel=${f#"$src"/}; dst="$out/${rel%.md}.docx"
  mkdir -p "$(dirname "$dst")"; echo "== $rel" >>"$out/errors.log"
  if pandoc "$f" -o "$dst" --resource-path="$(dirname "$f")" --reference-doc=ref.docx 2>>"$out/errors.log"
  then echo "OK   $rel"; else echo "FAIL $rel"; fail=$((fail + 1)); fi
done < <(find "$src" -name '*.md' -print0)
echo "失败 $fail 个，警告与报错见 $out/errors.log"; exit $((fail > 0))
```

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

## 输出契约

1. 先确认方向、母版和目标格式，再给命令。
2. 命令可直接复制，写明依赖（pandoc 版本、xelatex、字体名）和在哪个目录运行。
3. 交付时附检查清单结果：哪些通过，哪些要人工核对（合并单元格、图注、分页）。
4. 清理只动格式不动内容，删了什么、替换了多少处逐项报出。

## 边界与不做什么

- 只处理用户提供的文件和文本，不登录、不连接任何在线文档或内部文档系统，不经手账号、密码、令牌等凭据。
- pandoc 不读 PDF：PDF 转 Markdown 只能先用 pdftotext 之类工具提取文字，再按清理规则整理，版式无法还原；扫描件要 OCR，不在本技能范围。
- 文本框、分栏、页眉页脚、批注等 Word 版式转 Markdown 会丢失或错位，不承诺原样还原。
- 公文、合同等有格式要求的终稿，以单位模板或对方要求为准，是否合规由单位文秘或法务把关。
