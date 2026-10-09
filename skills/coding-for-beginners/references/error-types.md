# 新手最常遇到的 Python 报错（扩展版）

SKILL.md 里列了最常见的 7 种；这里是扩展版，和 `scripts/explain_error.py` 里的说明一致。读法不变：**从最后一行往上读**——最后一行是错误类型和说明，往上找 `File "...", line N` 看是哪个文件第几行。

| 错误类型 | 意思 | 最常见的原因 | 先这样查 |
|---|---|---|---|
| SyntaxError | 语法不完整 | 少了冒号、括号或引号；中文标点混进代码 | 提示行和上一行一起看，括号引号是否成对 |
| IndentationError | 缩进不一致 | 冒号结尾的行下面忘了缩进；缩进格数不同 | 统一用 4 个空格 |
| TabError | Tab 和空格混用 | 有的行用 Tab，有的行用空格 | 全部换成 4 个空格 |
| NameError | 名字没定义 | 拼错了，或者还没赋值就用了；字符串忘了加引号 | 和定义处逐字比对 |
| UnboundLocalError | 函数里先用后赋值 | 函数里给外面也有的变量赋值 | 用参数传进去、用 return 传出来 |
| TypeError | 类型不匹配 | 字符串加数字；参数个数不对 | `print(type(变量))`，用 `int()` `str()` 转换 |
| ValueError | 值不合法 | `int("abc")`、`int("3.5")` | `print(repr(值))` 看真实内容，输入用 try/except 兜住 |
| IndexError | 下标越界 | 列表只有 3 个元素，却取第 4 个 | `print(len(列表))`，下标从 0 开始 |
| KeyError | 字典里没有这个键 | 键名拼错、大小写不同 | 先用 `in` 判断，或用 `get()` |
| AttributeError | 对象没有这个方法或属性 | 方法名拼错；变量其实是 None；自己的文件和模块同名（如 random.py） | 看类型；给和模块同名的 .py 改名 |
| ZeroDivisionError | 除数是 0 | 分母算出来是 0，或用户输入了 0 | 除之前先判断 |
| ModuleNotFoundError | 找不到模块 | 第三方库没装；装到了另一个 Python 里 | `python3 -m pip install 包名`（Windows 用 `py -m pip install 包名`）；导入名和安装名可能不同，如 cv2 对应 opencv-python、PIL 对应 pillow |
| ImportError | 模块里没有要导入的东西 | 名字拼错；版本不同；文件和模块同名 | 核对名字，查同名文件 |
| FileNotFoundError | 找不到文件 | 路径写错；程序运行时所在文件夹不是你以为的那个 | `import os; print(os.getcwd())` 看当前文件夹 |
| PermissionError | 没权限读写 | 文件正被 Excel 打开；写到了受保护的文件夹 | 关掉占用的软件，换到自己的文件夹 |
| UnicodeDecodeError | 编码不一致 | 文件是 GBK，却按 UTF-8 读 | 试 `encoding="gbk"`，或把文件另存为 UTF-8 |
| JSONDecodeError | JSON 格式不对 | 单引号、多余逗号、空文件 | 把文本 print 出来看，键名用双引号 |
| RecursionError | 递归停不下来 | 没有结束条件 | 先写清楚「什么时候不再调用自己」 |
| KeyboardInterrupt | 你按了 Ctrl+C | 死循环或在等输入 | 检查 while 条件能不能变成 False |

## 用脚本读报错

```bash
python3 你的程序.py 2> error.txt          # 把报错存进 error.txt
python3 scripts/explain_error.py error.txt
```

输出依次是：错误类型和意思、原文说明、出错的文件和行号、那一行代码、最常见的原因、下一步、一行「拿去搜索的版本」（已去掉你的路径和你自己起的名字）、一行可以抄进报错本的记录。

报错出在别人写的库里（路径里有 site-packages 或 lib/python3）时，脚本会同时指出你自己的代码最后一次调用在哪一行——通常要改的是你自己那一行，而不是库。
