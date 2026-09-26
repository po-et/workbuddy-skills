# 示例：文件夹里一批 md，批量转成 Word

以下为示例，目录和文件名均为虚构。

## 1. 用户原话

> 文件夹里 50 个 md，想批量转换成 Word。

## 2. 助手先问（3 个）

1. 源目录和输出目录叫什么？子文件夹要不要保持原来的层级？
2. 有没有公司的样式模板（ref.docx）？没有就先用 pandoc 默认样式。
3. 图片放在哪里，md 里写的是相对路径吗？

> 用户：源目录 docs，输出到 build，保持层级；有 ref.docx，放在运行目录；图片都在各章自己的 img 文件夹里，相对路径。

## 3. 助手交付

### ① 方向与依赖

Markdown → Word（docx）｜母版：docs 里的 .md｜依赖：pandoc [待确认：`pandoc --version` 的结果，下文按 3.x 写]、Python 3；在 docs 的上一级目录运行，ref.docx 放在这里。

### ② 先预检（整个文件夹一次查完，只报告不改）

```bash
python3 {baseDir}/scripts/md_check.py docs
```

最后一行是汇总（没问题几个、有问题几个、读写失败几个）。退出码 3 的先按提示处理，尤其是「图片找不到」和「表格列数不一致」；退出码 2 多半是有 GBK 编码的文件，按提示转成 UTF-8。

### ③ 先看会转哪些文件（不需要 pandoc，本机实际输出，示例目录里 4 个文件）

```
$ python3 {baseDir}/scripts/md_batch.py docs build --dry-run
将转换 4 个文件（--dry-run，未调用 pandoc）：
  docs/前言.md → build/前言.docx
  docs/第一章 背景.md → build/第一章 背景.docx
  docs/第二章 数据/数据说明.md → build/第二章 数据/数据说明.docx
  docs/附录/术语表.md → build/附录/术语表.docx
样式模板：ref.docx（运行目录）
```

### ④ 正式转换

```bash
python3 {baseDir}/scripts/md_batch.py docs build                 # 默认：单个文件超时 120 秒，失败重试 1 次
python3 {baseDir}/scripts/md_batch.py docs build -- --toc        # 每份 Word 都带目录
```

每个文件执行的是：`pandoc 源文件 -o 目标.docx --resource-path=源文件所在目录 --reference-doc=ref.docx`。输出的样子如下（本机没有装 pandoc，这是用一个模拟成功、失败和警告的假 pandoc 跑通脚本时的实际输出，只用来说明格式；真实的警告内容以你机器上的 pandoc 为准）：

```
OK      前言.md
OK      第一章 背景.md
OK      第二章 数据/数据说明.md
FAIL    附录/术语表.md
共 4 个：成功 3，失败 1，超时 0；警告与报错见 build/errors.log
没转成的：附录/术语表.md
```

build/errors.log 里逐个文件记录 pandoc 的警告与报错、每次重试的结果：

```
# 样式模板：ref.docx（运行目录）；超时 120 秒；重试 1 次
== 前言.md
   结果：OK
== 第一章 背景.md
   结果：OK
== 第二章 数据/数据说明.md
   （假 pandoc 模拟的警告）
   结果：OK
== 附录/术语表.md
   （假 pandoc 模拟的报错）
   第 1 次：pandoc 退出码 64
   （假 pandoc 模拟的报错）
   第 2 次：pandoc 退出码 64
   结果：FAIL
```

### ⑤ 有文件失败时

- 退出码 3：看 errors.log 里对应文件的报错，改好源文件后用同一条命令重跑（已成功的文件会被重新生成，不影响结果）。
- 退出码 4：找不到 pandoc，先安装，或用 `--pandoc 路径` 指定。
- 某个文件总是超时：先单独转它，看是不是图片太大或表格太复杂；需要时加大 `--timeout`。

### ⑥ 转换后抽查（至少抽 3 个文件）

- [ ] Word 导航窗格能看到完整标题层级
- [ ] 表格列数、合并单元格、表头与原文一致；图片张数一致、没被拉伸、图注不多不少
- [ ] 目录已更新（Word 里右键「更新域」）
- [ ] 抽三段与原文逐字比对：引号、破折号、省略号和代码没被改

### ⑦ 待确认

- pandoc 版本；ref.docx 里的样式名是否是 Body Text、「标题 1」这一套
