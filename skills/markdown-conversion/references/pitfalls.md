# 最容易出错的地方：表格、图片、中文与分页（详版）

SKILL.md 里是一张「症状 → 原因 → 办法」的速查表，这里是完整说明。命令按 pandoc 3.x 写，旧版参数可能不同。

## 表格

管道表每格只能写一行，也不能合并单元格；要多段落就用网格表或拆表。Word 里带合并单元格的表转成 Markdown 会被拆开或变成一段 HTML，要逐张对照。表里有一行超过 72 字符时，pandoc 按分隔行 `|---|------|` 的短横线比例分配列宽，想让哪列宽就多写横线。Word 表格的边框底纹由 ref.docx 里名为 Table 的表格样式决定。宽表进 PDF 会冲出版心，减列或拆表。

## 图片

相对路径按运行 pandoc 的目录找，不按 md 所在目录：到 md 目录下运行，或加 `--resource-path=docs:docs/img`（Windows 用分号分隔）。单独成段、带替代文字的图会变成带图注的图，`![截图](a.png)` 在 Word 里图下会多一行「截图」，替代文字要写成真正的说明。尺寸写 `{width=14cm}` 跟在图片后面，GitHub 不认这个写法。SVG、WebP 走 LaTeX 容易失败，先转成 PNG。Word 转 Markdown 不加 `--extract-media`，图片会丢。

## 中文

pandoc 只认 UTF-8，GBK 文件先 `iconv -f GBK -t UTF-8 in.md > in.utf8.md`（没有 iconv 时用 `python3 {baseDir}/scripts/md_check.py in.md --encoding gbk --fix -o in.utf8.md`）。段落里的单个换行夹在两个汉字之间会变成多余空格，加 `-f markdown+east_asian_line_breaks`。

Word 的字体、行距、页边距、页眉页脚只能在 ref.docx 的样式里改，直接刷格式无效：正文用的是 Body Text（中文 Word 叫「正文文本」）和 First Paragraph，标题是「标题 1」起；中文字体在样式的「中文字体」一栏，和西文字体分开设。

PDF 默认的 pdflatex 遇到中文报 Unicode character not set up for use with LaTeX；换了 xelatex 没设 CJKmainfont，中文会整段消失，日志里有 Missing character。字体名要写本机已装的：Windows 如 SimSun、Microsoft YaHei，macOS 在「字体册」里查，Linux 用 `fc-list :lang=zh family`。版式用 `-V geometry:margin=2.5cm -V linestretch=1.5 -V papersize=a4`。

## 分页

PDF 在要分页处写 `\newpage`；HTML 打印用 CSS `h1 { break-before: page; }`；Word 插入这段原始块：

~~~
```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```
~~~
