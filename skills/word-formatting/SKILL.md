---
name: word-formatting
description: "Word 排版——把乱糟糟的 Word 文档排成规范、好维护的样子：先样式后内容，编号、目录、页码、题注全自动，附论文、公文、简历三套常见规格。当用户说「论文格式怎么排」「目录页码对不上」「页码从正文开始」「Word排版乱」时使用。"
author: Captain
version: 0.1.0
display_name: "Word 排版"
display_name_en: "Word Formatting"
description_zh: "Word 排版：用「先样式后内容」把乱文档排成规范、好维护的样子。八步做法覆盖清理手动格式、定样式、多级编号绑定标题、题注与交叉引用、分节与页眉页脚页码、自动目录；附毕业论文、单位公文、简历三套常见规格（以学校和单位规定为准）、排查清单和只读体检脚本。"
description_en: "Turn a messy Word document into a clean, maintainable one by setting styles before content, with multilevel heading numbering, automatic TOC, sections and page numbers, captions and cross-references, three common spec sets and a read-only checker script."
tags:
  - "Word 排版"
  - "Word"
  - "论文排版"
  - "公文排版"
  - "简历排版"
  - "自动目录"
  - "页码设置"
  - "样式"
  - "docx"
examples_zh:
  - "毕业论文格式怎么排，目录和页码总是对不上"
  - "页码怎么从正文开始，前面摘要目录用罗马数字"
  - "这份Word全是手动空格和手打编号，帮我排成规范的样子"
---

# Word 排版

定位一句话：**文档乱，根子在格式直接刷在文字上。先定样式、再放内容，改一处样式全文跟着变，加一章时编号、目录、题注自动跟上。**

何时用：要把一份 Word 文档排成规范的样子（毕业论文、单位公文、简历、报告），或者文档已经乱了，满是手动空格、手打编号、回车撑出来的分页，目录页码对不上，改一个标题要改十处。菜单名按 Microsoft Word 中文版写，快捷键按 Windows 版；Mac 版和 WPS 文字都有同名功能，位置略有不同，按菜单名找。

## 先判断：按谁的规范、交付什么、乱在哪

1. **按谁的规范。** 学校的论文模板、单位的公文模板、招聘方的简历要求，有就以它为准；本页的三套规格只在手上没有规定时参考。
2. **交付什么。** 打印稿、PDF，还是 Word 原件交给别人接着改？要给别人接着改的，更要全部走样式。
3. **乱在哪。** 打开「显示编辑标记」（开始 → 段落里的 ¶ 按钮，快捷键 Ctrl+Shift+8）：一串「·」是空格，一串「¶」是空段落，「↵」是手动换行符，分页符和分节符也会显示出来。再跑一遍本页最后的体检脚本，拿到问题清单。

检查点：写下三样东西，依据哪份规范、交付格式、要改的问题清单，再动手。

## 先样式后内容：八步流程

1. **备份并清掉直接格式。** 另存一份「原名_排版」。全选（Ctrl+A）后按 Ctrl+Space 清除文字上的直接格式，再按 Ctrl+Q 清除段落上的直接格式；样式保留，手工刷的字体、字号、缩进被去掉。手工加的加粗、颜色也会一起清掉，先确认有没有要保留的强调。别用「清除所有格式」按钮，它会把标题也打回「正文」。
2. **查找替换清垃圾。** 开始 → 替换（Ctrl+H），点「更多」→「特殊格式」可以插入下面这些代码：
   - 查找 `^l` 替换为 `^p`：手动换行符改成真段落，网页和聊天软件里粘来的文字最常见。
   - 查找 `^p^p` 替换为 `^p`：删空段落，反复点「全部替换」直到替换 0 处。
   - 查找 `^m`：手动分页符，逐个看，换页改用第 3 步的「段前分页」或分节符。
   - 勾「使用通配符」，查找 `[ ]{2,}`：两个以上的连续半角空格；全角空格直接在查找框里输入一个「　」。表格和代码里的空格可能是有意的，用「查找下一处」逐个确认，再替换为空（替换框什么都不填），需要对齐的地方改用制表位。
3. **定样式。** 开始 → 样式 → 右键 →「修改」。先改「正文」，再改「标题 1/2/3」和「题注」，需要的再新建（如「表格文字」「参考文献」）。在「格式」按钮里设字体（中文字体和西文字体分开设）和段落。首行缩进用「特殊格式 → 首行缩进 2 字符」，不打空格；「标题 1」在「换行和分页」里勾「段前分页」，每章自动另起一页。行距设成「固定值」时，嵌入的图片和大号公式会被裁掉，放图片的段落改用单倍行距。
4. **套样式。** 逐段应用：标题用 Ctrl+Alt+1/2/3，正文用 Ctrl+Shift+N。打开「视图 → 导航窗格」，左边列出完整的标题层级就对了。
5. **多级编号绑定标题。** 开始 → 多级列表 →「定义新的多级列表」→「更多」。级别 1 的「将级别链接到样式」选「标题 1」，在编号格式框里灰底数字的前后打上「第」「章」；级别 2 链接「标题 2」，格式为「1.1」；级别 3 同理。一级用「第一章」这种中文数字、二级想显示成「1.1」时，要在级别 2 勾「正规形式编号」，否则会显示成「一.1」。绑好后删掉原来手打的编号。
6. **题注和交叉引用。** 选中图片 → 引用 →「插入题注」→ 标签选「图」（没有就「新建标签」）→「编号」里勾「包含章节号」，得到「图 2-1」（前提是第 5 步已把标题 1 绑定编号）。图题放图下方，表题放表上方。正文里别手写「见图 3」，用 引用 →「交叉引用」，引用类型选「图」，引用内容选「只有标签和编号」。
7. **分节、页眉页脚、页码。** 在封面后、目录后各插一个 布局 → 分隔符 →「下一页」分节符。双击页眉进入编辑，在要换页眉或换页码的那一节点掉「链接到前一节」，页眉和页脚要分别点。插入 → 页码 →「设置页码格式」：摘要、目录那一节选罗马数字，正文节选「起始页码 1」。封面不要页码，就单独成节，或在该节勾「首页不同」；奇数页和偶数页页眉不一样时，勾「奇偶页不同」，两种页各设一次。页眉要随章变化，用 插入 → 文档部件 → 域 → StyleRef，样式选「标题 1」。
8. **目录，最后更新一遍。** 引用 → 目录 →「自定义目录」，显示级别 3。改完内容后右键目录 →「更新域」→「更新整个目录」。交付前 Ctrl+A 再按 F9，把题注和交叉引用一起更新。

## 三套常见规格（以学校、单位、招聘方的规定为准）

下面是常见要求，不是标准答案。数值与你手上的书面规定冲突时，一律以规定为准。

**毕业论文（常见要求，以学校规定为准）**

| 项目 | 常见要求 |
|---|---|
| 纸张与页边距 | A4；上 2.5–3 cm，下 2.5 cm，左 3 cm（含装订），右 2.5 cm |
| 正文 | 宋体小四，西文 Times New Roman；1.5 倍行距或固定值 20 磅；首行缩进 2 字符 |
| 一级标题 | 黑体三号或小二，居中，段前段后 0.5–1 行，每章另起一页 |
| 二、三级标题 | 黑体四号、小四，左对齐，编号 1.1、1.1.1 |
| 图表题注 | 宋体五号居中；图题在图下，表题在表上；按章编号，如「图 2-1」「表 3-2」 |
| 页眉页码 | 页眉放校名或论文题目；摘要、目录用罗马数字页码，正文从 1 起 |
| 目录与参考文献 | 目录自动生成到三级标题；参考文献五号、悬挂缩进，著录格式按学校指定规则（多数用 GB/T 7714，版本以学校要求为准） |

**单位公文（常见要求，以本单位公文处理办法和 GB/T 9704 原文为准）**

| 项目 | 常见要求 |
|---|---|
| 版心与页边距 | A4，版心 156 mm × 225 mm，天头 37 mm、订口 28 mm；折算成 Word 页边距约为上 3.7 cm、下 3.5 cm、左 2.8 cm、右 2.6 cm |
| 行和字 | 一般每页 22 行、每行 28 字：布局 → 页面设置 → 文档网格 →「指定行和字符网格」 |
| 标题与正文 | 标题 2 号小标宋体居中；正文 3 号仿宋 |
| 层次序数 | 「一、」黑体，「（一）」楷体，「1.」和「（1）」仿宋 |
| 页码 | 4 号半角宋体阿拉伯数字，左右各加一条一字线；单页居右空一字，双页居左空一字 |
| 成文日期 | 阿拉伯数字，年月日写全，月、日不编虚位（1 月不写成 01 月） |

公文常用的仿宋_GB2312、方正小标宋等字体，对方电脑没装就会被替换，版面跟着变，交付前导出 PDF 核对一遍。

**简历（常见做法，以招聘方要求为准）**

| 项目 | 常见做法 |
|---|---|
| 篇幅与边距 | 应届生 1 页，有工作经验一般不超过 2 页；页边距 1.5–2 cm |
| 字体字号 | 全文一种中文字体加一种西文字体；姓名 18–22 磅，模块标题 12–14 磅加粗，正文 10.5–11 磅 |
| 行距 | 单倍到 1.15 倍，段后 0–6 磅 |
| 左右对齐 | 左边写经历、右边写时间，用右对齐制表位（段落 → 制表位，位置填版心宽度）或无框线表格，不用空格顶 |
| 交付 | 日期写法全文统一（如 2024.09–2026.06），导出 PDF，文件名「姓名-应聘岗位.pdf」 |

规定里「号」和「磅」混着用时，照这张表换算：

```
初号 42   小初 36   一号 26   小一 24   二号 22   小二 18
三号 16   小三 15   四号 14   小四 12   五号 10.5 小五 9    （单位：磅）
```

## 排查清单与体检脚本

| 痕迹 | 怎么认 | 改成 |
|---|---|---|
| 手动空格对齐、缩进 | 显示编辑标记后是一串「·」 | 首行缩进、制表位或表格 |
| 手打编号 | 点一下编号，整列编号不会一起变灰 | 多级列表绑定标题样式，或列表编号 |
| 硬回车分页 | 页尾一串「¶」，前面加一行字后面全乱 | 标题 1 勾「段前分页」，或分页符 Ctrl+Enter、分节符 |
| 空段落撑间距 | 段落之间单独一个「¶」 | 样式里的段前段后间距 |
| 手打目录 | 目录里的点线是打上去的，点了不跳转 | 引用 → 目录 |
| 手打题注和「见图 3」 | 「图1」是普通文字，调了图序编号不变 | 插入题注、交叉引用 |
| 直接格式 | 同级标题大小不一，样式检查器里显示「直接格式」 | 改样式，Ctrl+Space、Ctrl+Q 清掉 |
| 手动换行符 | 行尾是「↵」不是「¶」 | 查找 `^l` 替换为 `^p` |
| 页码不对 | 封面有页码，正文不从 1 起 | 分节，点掉「链接到前一节」，设起始页码 |
| 表格跨页没表头 | 第二页的表格没有标题行 | 表格属性 → 行 →「在各页顶端以标题行形式重复出现」 |
| 图片乱跑 | 图片是「浮于文字上方」 | 改成「嵌入型」，单独一段居中 |

体检脚本只读 .docx、不改文件，只用 python3 标准库（.doc 老格式先另存为 .docx）。它统计样式使用、标题样式、自动目录、题注域、交叉引用、分节和页码，并找出手打编号、手打题注、手打目录行、连续空格、像标题却没用标题样式的段落、连续空段落。表格、文本框和目录条目里的段落不查。它是启发式检查，结果逐条人工确认。

```python
# 保存为 docx_check.py；只读 .docx，不改文件，只用标准库
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUM = re.compile(r"\s*(第[一二三四五六七八九十百\d]+[章节条]|[一二三四五六七八九十]+、|[（(][一二三四五六七八九十\d]+[）)]"
                 r"|\d{1,2}(\.\d{1,2})*(?:[.、．]|\s+(?=[\u4e00-\u9fff])))")


def has(el, tag):
    return el.find(".//" + W + tag) is not None


def fields(el):
    """域代码：自动目录 TOC、题注 SEQ、页码 PAGE、交叉引用 REF 都是域"""
    return " ".join([t.text or "" for t in el.iter(W + "instrText")]
                    + [f.get(W + "instr", "") for f in el.iter(W + "fldSimple")])


with zipfile.ZipFile(sys.argv[1]) as z:
    doc = ET.fromstring(z.read("word/document.xml"))
    names = {}
    if "word/styles.xml" in z.namelist():
        for s in ET.fromstring(z.read("word/styles.xml")).iter(W + "style"):
            n = s.find(W + "name")
            names[s.get(W + "styleId")] = n.get(W + "val") if n is not None else s.get(W + "styleId")
    margins = " ".join(fields(ET.fromstring(z.read(n))) for n in z.namelist() if re.match(r"word/(header|footer)\d*\.xml$", n))

styles, issues, blank = Counter(), {}, 0
boxed = {id(q) for tag in ("tbl", "txbxContent") for box in doc.iter(W + tag) for q in box.iter(W + "p")}
for p in doc.iter(W + "p"):
    ppr = p.find(W + "pPr")
    sid = ppr.find(W + "pStyle") if ppr is not None else None
    style = names.get(sid.get(W + "val"), sid.get(W + "val")) if sid is not None else "Normal"
    text = "".join(t.text or "" for t in p.iter(W + "t"))
    if not text.strip():
        blank = 0 if has(p, "drawing") or has(p, "br") or has(p, "sectPr") else blank + 1
        if blank == 3:
            issues.setdefault("连续 3 个以上空段落（用回车撑版面或分页）", []).append("空行")
        continue
    blank = 0
    styles[style] += 1
    if style.lower().startswith("toc") or id(p) in boxed:   # 目录条目、表格和文本框里的段落不查
        continue
    found = []
    if re.search(r"(…{2,}|\.{4,}|·{4,})\s*\d+\s*$", text):
        found.append("手打目录行（点线加页码）")
    else:
        if NUM.match(text) and (ppr is None or ppr.find(W + "numPr") is None):
            found.append("手打编号（编号是打上去的字，不会自动更新）")
        if re.match(r"\s*[图表]\s*\d", text) and not re.search(r"\bSEQ\s", fields(p)):
            found.append("手打题注（顺序一变编号就错）")
        bold = all(r.find(W + "rPr/" + W + "b") is not None for r in p.iter(W + "r")
                   if "".join(t.text or "" for t in r.iter(W + "t")).strip())
        if (not re.match(r"(?i)heading|标题|title", style) and len(text) <= 30
                and not re.search(r"[。；，：.;,:]$", text.strip()) and (bold or NUM.match(text))):
            found.append("像标题却没用标题样式（导航窗格和自动目录里看不到）")
    if re.search(r"[ 　]{2,}|^[ 　]", text):
        found.append("连续空格或行首空格（手动对齐、手动缩进）")
    for kind in found:
        issues.setdefault(kind, []).append(text.strip()[:20])

all_fields = fields(doc)
runs = [r for r in doc.iter(W + "r") if has(r, "t")]
direct = sum(1 for r in runs if r.find(W + "rPr/" + W + "rFonts") is not None or r.find(W + "rPr/" + W + "sz") is not None)
sects = list(doc.iter(W + "sectPr"))
restart = sum(1 for s in sects if s.find(W + "pgNumType") is not None and s.find(W + "pgNumType").get(W + "start"))
heads = sum(n for s, n in styles.items() if re.match(r"(?i)heading|标题", s))
print("样式使用（段落数）：" + " | ".join(f"{s} {n}" for s, n in styles.most_common(8)))
print(f"标题样式段落 {heads}；自动目录 {'有' if 'TOC' in all_fields else '没有'}；"
      f"题注域 {all_fields.count('SEQ')} 个；交叉引用 {len(re.findall(r'(?<![A-Z])REF', all_fields))} 个")
print(f"分节 {len(sects)} 个（页码重新起算 {restart} 个，首页不同 {sum(has(s, 'titlePg') for s in sects)} 个）；"
      f"手动分页符 {sum(1 for b in doc.iter(W + 'br') if b.get(W + 'type') == 'page')} 个；"
      f"页眉页脚里有页码域：{'是' if re.search(r'(?<![A-Z])PAGE(?![A-Z])', margins) else '否'}")
print(f"直接设了字体或字号的文字段 {direct}/{len(runs)}（比例高，说明格式没走样式）")
for kind, hits in issues.items():
    print(f"[{kind}] {len(hits)} 处，例：" + "、".join(f"「{h}」" for h in hits[:3]))
if not issues:
    print("没发现手动排版的痕迹")
```

```bash
python3 docx_check.py 论文.docx
```

在一份故意排乱的测试文档上，本机跑出的结果：

```
样式使用（段落数）：Normal 14 | heading 1 2
标题样式段落 2；自动目录 没有；题注域 1 个；交叉引用 0 个
分节 2 个（页码重新起算 1 个，首页不同 1 个）；手动分页符 1 个；页眉页脚里有页码域：是
直接设了字体或字号的文字段 4/18（比例高，说明格式没走样式）
[手打编号（编号是打上去的字，不会自动更新）] 5 处，例：「2 研究设计」、「第一章 绪论」、「1.1 研究背景」
[像标题却没用标题样式（导航窗格和自动目录里看不到）] 5 处，例：「2 研究设计」、「目录」、「第一章 绪论」
[手打目录行（点线加页码）] 1 处，例：「第一章 绪论……………………1」
[连续空格或行首空格（手动对齐、手动缩进）] 2 处，例：「近年来，这一问题受到关注。这一段用全角空」、「本章用了三种方法。    这里有连续空格」
[手打题注（顺序一变编号就错）] 1 处，例：「图1 系统结构」
[连续 3 个以上空段落（用回车撑版面或分页）] 1 处，例：「空行」
```

## 输出契约

1. **规格表**：这份文档采用的规格，每一项注明来源（学校或单位的文件，还是本页的常见要求）。
2. **体检结果**：脚本输出加人工看到的问题，按排查清单归类，写明在第几章、哪一段。
3. **操作步骤**：按八步流程写出这份文档要做的具体操作，菜单路径和每一项设的值都写全。
4. **验收清单**：导航窗格层级完整；目录能点击跳转、页码正确；题注和交叉引用已更新；每一节页码正确；导出 PDF 后字体没有被替换。
5. 本技能不带写 .docx 的工具，排版操作由用户在 Word 或 WPS 里完成；脚本只读文件做体检。

## 边界与不做什么

- 文中的菜单路径与快捷键按常见的 Word 桌面版写，未在每个版本里逐一点验；WPS、Word 网页版或旧版本的名称和位置可能不同，以你所用版本为准。
- 规格数值都是常见要求，以学校、期刊、单位、招聘方最新的书面规定为准，有冲突时以规定为准，拿不准就问导师、教务或单位办公室。
- 只管版式，不代写论文、公文、简历的内容。
- 不处理 .doc 老格式的体检、PDF 转 Word、扫描件识别，也不做 LaTeX 排版。
- 查重、学术规范、公文的密级和签发流程不在本技能范围，找导师、教务或单位办公室。
- 不处理涉密文件；含个人信息的文档只在本机检查，不上传到别处。
