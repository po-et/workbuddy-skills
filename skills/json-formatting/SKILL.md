---
name: json-formatting
description: "JSON 格式化——把 JSON 美化、压缩成一行、排序键，按报错定位语法错误，并做字段与类型粗校验。当用户说「JSON 格式化」「JSON 报错」「压缩成一行」「JSON 转 CSV」「JSON 转 YAML」时使用。"
author: Captain
version: 0.1.1
display_name: "JSON 格式化"
display_name_en: "JSON Formatting"
description_zh: "JSON 格式化与检查：用 python3 -m json.tool 或 jq 美化、压缩、排序键；按报错信息定位多余逗号、单引号、注释、未转义字符等语法错误；用 jq 做必填字段与类型粗校验；大文件流式拆成 JSON Lines；与 YAML、CSV 互转时守住类型和编码。"
description_en: "Pretty-print, minify and validate JSON with python -m json.tool and jq, pinpoint common syntax errors, run quick schema checks, split large files into JSON Lines, and convert to YAML or CSV without losing types or encoding."
tags:
  - "JSON 格式化"
  - "JSON"
  - "JSON 美化"
  - "JSON 压缩"
  - "JSON 校验"
  - "jq"
  - "json.tool"
  - "JSON 转 CSV"
  - "JSON 转 YAML"
  - "pretty print"
examples_zh:
  - "JSON 格式化一下，接口返回的是一整行，根本看不清"
  - "JSON 报错说第 1 行第 3087 列有问题，文件只有一行，怎么找"
  - "这个 JSON 要转成 CSV 给同事用 Excel 打开，嵌套字段怎么处理"
examples_en:
  - "Format this JSON for me. The API returns everything on a single line"
  - "My JSON fails at line 1 column 3087 and the file is one line. How do I find the problem?"
---

# JSON 格式化

定位一句话：**格式化只是让 JSON 好读；要紧的是确认它合法、改完内容一个字没变。**

## 何时使用

用户在对话里贴 JSON 文本、给本地文件路径，或贴解析报错时用本技能。不连接接口：用户给的是网址，请他先把响应保存成文件。用户这样说时触发：

- 「JSON 格式化一下，接口返回的是一整行，根本看不清」→ 先校验，再美化输出
- 「JSON 报错说第 1 行第 3087 列有问题，文件只有一行，怎么找」→ 跑定位脚本，按报错对照表改
- 「帮我压缩成一行」「键排个序好 diff」→ 压缩或排序键，附 diff 核对
- 「这个 JSON 要转成 CSV 给同事用 Excel 打开」「JSON 转 YAML」→ 先定扁平规则和类型处理，再给命令
- 「检查一下每条记录是不是都有 id、status 取值对不对」→ jq 粗校验
- 「文件几个 GB，编辑器打不开」→ 先看顶层结构，再流式拆成 JSON Lines

不适用：

- JSONC、JSON5（VS Code 设置、tsconfig）里的注释和尾逗号是合法写法：用户没要求转严格 JSON 就不改，直接说明。
- 数据内容对不对（金额、状态该不该必填）、接口契约怎么设计：以接口文档和业务负责人为准，转 API 设计类技能。
- 纯 CSV 或 Excel 表格的清洗、YAML 配置本身的语义：转表格处理类技能；这里只管 JSON 与它们互转时的类型和编码。

## 先判断三件事

1. **是不是 JSON。** JSONC、JSON5（VS Code 设置、tsconfig）允许注释和尾逗号，那不算错；JSON Lines 是一行一个对象，要按行处理；单引号加 None、True 的是 Python 打印结果。
2. **多大、什么编码。** 几十 MB 起别用编辑器，上 GB 走流式。GBK 编码的文件 Python 报解码错误，jq 却不报错、把中文换成 � 照常输出，先转码：`python3 scripts/json_check.py in.json --pretty --out in.utf8.json`（自动识别 GBK，输出一律 UTF-8；装了 iconv 也可以 `iconv -f GBK -t UTF-8`）。含令牌、手机号的数据别贴到在线格式化网站。
3. **给谁用。** 给人看：缩进 2 格、中文不转义；给程序：压缩成一行；要 diff：两边先排序键。项目有 .editorconfig 或 prettier 配置就照它来；格式化和改内容分开提交。

## 美化与压缩：python3 与 jq 八招

没装 jq 用 Python 自带模块（需 3.9+，加 --sort-keys 排序键）：

```bash
python3 -m json.tool --indent 2 --no-ensure-ascii in.json  # 美化；不加后一参数中文变成 \uXXXX
python3 -m json.tool --compact in.json  # 压缩成一行
```

json.tool 会重写数字（1.10 变 1.1，1.0e3 变 1000.0）；要保留 1.10 这类写法用 jq 1.7 以上。

```bash
jq . a.json                    # 1 美化，默认 2 空格；--indent 4 改缩进，-S 排序键
jq -c . a.json                 # 2 压缩成一行
jq empty a.json && echo 合法    # 3 只校验：合法退出码 0，语法错为 5
jq 'keys' a.json               # 4 看顶层有哪些键；'.items | length' 数元素
jq -r '.items[].name' a.json   # 5 取字段，-r 去掉引号
jq '.items[] | select(.status == "active")' a.json  # 6 按条件筛
jq --arg u "https://example.com/v2" '.endpoint = $u | del(.debug)' a.json  # 7 改值、删键
jq -r '.items[] | [.id, .name] | @csv' a.json  # 8 转 CSV 行
```

改完证明只动了格式：`diff <(jq -S . old.json) <(jq -S . new.json)` 没有输出即内容一致。两个坑：`jq . a.json > a.json` 会先清空文件，要写到新文件再 mv 回去；Windows 命令提示符不认单引号，把过滤器存成 filter.jq，用 `jq -f filter.jq a.json`。

jq 没装、Python 低于 3.9、或者想一步完成「校验 + 美化 + 写回」，用本技能的脚本（Python 3.6+，只用标准库）：先写临时文件再替换，写回原文件也不会被清空；写完自动核对输出与原数据逐项相等，还会提醒会被改写的数字、超 2^53 的整数、NaN 和重复键。

```bash
python3 scripts/json_check.py a.json                        # 只校验：合法 / 不合法 + 位置 + 常见原因
python3 scripts/json_check.py a.json --pretty --out a.json  # 美化并安全写回；--compact 压缩，--sort-keys 排序键
python3 scripts/json_check.py dump.txt --from-python --pretty  # Python 打印结果（单引号、None、True）转 JSON
```

## 最常见的语法错误：按报错定位

报错位置是解析器「发现不对」的地方，真正的错常在它前面，比如多余的逗号报在右括号上。只有一行的文件，用脚本打印出错处前后 40 个字，并给出这类报错的常见原因：

```bash
python3 scripts/json_check.py a.json       # JSON Lines 加 --lines 逐行校验；从标准输入读用 -
```

对照改（Python 3.12 实测；jq 对单引号、注释都报 Invalid numeric literal）：

| 错误 | 例子 | Python 报错 | 改法 |
|---|---|---|---|
| 多余逗号 | `{"a":1,}` | Expecting property name / Expecting value | 删掉末尾逗号 |
| 单引号 | `{'a':1}` | Expecting property name | 改成双引号 |
| 注释 | `// 说明` | 同上 | 删掉或改成 `"_comment"` 字段 |
| 漏逗号 | `{"a":1 "b":2}` | Expecting ',' delimiter | 在报错处前补逗号 |
| 引号未转义 | `"他说"好""` | Expecting ',' delimiter | 写成 `\"` 或改用「」 |
| 反斜杠 | `"C:\data"` | Invalid \escape | 写成 `\\` 或 `/` |
| 真换行 | 字符串里有回车 | Invalid control character | 换成 `\n` |
| BOM | 记事本另存 | Unexpected UTF-8 BOM | 存成不带 BOM 的 UTF-8 |
| 首尾相连 | `{…}{…}` | Extra data | 包进数组或按 JSON Lines 处理 |

修复流程：只改第一处报错，改完重跑；一个漏掉的引号会引出一串假错误。更隐蔽的是 `"C:\new"`：不报错，`\n` 被当成了换行。Python 打印结果用 `ast.literal_eval` 读入再 `json.dumps` 输出（脚本的 --from-python 就是这么做的），比手改引号可靠。

能解析也未必合规：Python 和 jq 都接受 NaN、Infinity，换个解析器就报错；重复键两者都静默只留最后一个。脚本会把这几类单独提醒，加 --strict 时退出码为 4，可当门禁用。

## 粗校验与大文件

把「必须有哪些键、什么类型、取值范围」写成 jq 表达式，`-e` 让结果决定退出码，可直接当脚本门禁；不通过时把 all(条件) 换成 .items[] | select(条件 | not) 列出坏数据：

```bash
jq -e '.items | all(has("id") and (.id|type == "number") and (.status|IN("active","off")))' a.json  # 0 通过 1 不通过
```

规则以接口文档为准，不从样例倒推；正式校验用 JSON Schema 加校验库（如 Python 的 jsonschema，需另装）。

jq 和 Python 默认整个读进内存，占用是文件的数倍。吃不消时先 `head -c 300 big.json` 看顶层结构；顶层是大数组就流式拆成一行一条，抽样调好命令再跑全量：

```bash
jq -cn --stream 'fromstream(1|truncate_stream(inputs))' big.json > big.jsonl
```

超过 2^53 的整数（如 19 位订单号）经 JavaScript 解析会丢精度，jq 1.6 及更早也丢，jq 1.7 只在参与运算时丢；拿不准就请上游输出成字符串。

## 与 YAML、CSV 互转

- 先定规则再转：CSV 的扁平规则（嵌套用点路径做列名，数组用分号拼成一格或一元素一行）写进交付说明；YAML 先 `yq --version` 分清是 Go 版还是 Python 版。
- 守住类型和编码：YAML 1.1 会把 `NO`、`on` 变布尔、`00123` 当八进制；给 Excel 的 CSV 加 UTF-8 BOM，超 15 位的数字列按文本导入；CSV 转回 JSON 全是字符串。

两种 yq 的命令、各类坑、jq 与纯 Python（标准库 csv 模块）两种转 CSV 写法，见 [references/yaml-csv.md](references/yaml-csv.md)。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（模板） |
|---|---|---|
| 只说「报错了」，没贴内容或报错原文 | 只要两样：报错原文（含行列号）和出错处前后一段；文件大就给路径跑脚本。其余按默认（2 空格、中文不转义、保留键顺序）处理 | 「请贴两样：完整的报错原文（带第几行第几列），和报错位置前后一两行；文件太大就把路径给我，我用脚本定位。」 |
| 贴来的不是 JSON（JSONC、JSON5、Python 打印结果、HTML 报错页、JSON Lines） | 先说它是什么，给两种处理：保留原格式，或转成严格 JSON | 「这是 Python 打印出来的字典（单引号、None），不是 JSON。两种办法：用 --from-python 转成 JSON；或者让上游直接输出 JSON。」 |
| 需求自相矛盾（既要「压缩成一行」又要「好读」；要排序键又要保留原顺序） | 指出冲突，给两个可选理解 | 「压缩和美化不能同时要：给程序用我出一行版，给人看我出 2 空格版，或者两份都给？」 |
| 数据里有令牌、密码、身份证号 | 先提醒打码，不在输出里复述；示例地址只用 example.com | 「里面有看起来像令牌的字段，我在结果里用 *** 代替了，你分享前也请打码。」 |
| 超出范围（字段该不该必填、金额对不对、设计接口） | 说明以接口文档和业务负责人为准，只做格式与类型检查 | 「status 该不该允许 null 要看接口文档，我先把现在的取值分布列出来，你拿去和负责人确认。」 |
| 时间紧，只要最小可用版 | 最小版：一句结论（合法/不合法、第几行第几列、原因）+ 改好的那一段 + 一条可复制的校验命令；其余注意事项标 [待补] | 「先给结论和改好的片段，用 python3 scripts/json_check.py 文件 自己复核一遍；类型和编码的注意事项我随后补。」 |
| 用户坚持越界（要我直接调接口取数据、把含密码的数据原样美化后发出去） | 守住边界，给替代 | 「我不连接接口；你把响应保存成文件给我，我来格式化。含密码的字段先打码再发。」 |
| 修复有两种可能（`"C:\new"` 是路径还是换行？重复键留哪个？） | 不猜，列出两种理解，标 [待确认] | 「`"C:\new"` 现在被读成『C: 加换行加 ew』。如果它是路径，应写成 `"C:\\new"`；如果本来就要换行就不用改。我先按路径改了，标 [待确认]。」 |

脚本与工具报错对照：

| 退出码 / 报错 | 原因 | 修正办法 |
|---|---|---|
| 0，「合法：…」 | 通过；有「[提醒]」的是兼容性风险 | 需要门禁时加 --strict |
| 3，「不合法：…（第 L 行第 C 列）」 | JSON 语法错误 | 按「可能原因」和上面的对照表改第一处，改完重跑 |
| 4 | 加了 --strict，且有 NaN、重复键、超 2^53 整数或会被改写的数字 | 按提醒逐条处理，或去掉 --strict |
| 2，「找不到文件」「没有权限」「解码失败」「目录不存在」 | 路径、权限、编码或输出目录的问题 | 核对路径；编码用默认 auto 或 --encoding gbk；先建好输出目录 |
| 1，「参数错误：…」 | 参数组合不对（--pretty 和 --compact 同时用、--out 没配 --pretty） | 看 python3 scripts/json_check.py -h |
| 130，「已中断」 | 手动按了 Ctrl+C | 重新运行 |
| 提示找不到 jq 命令（command not found） | 没装 jq | 用 python3 -m json.tool 或上面的脚本；jq 从其官方渠道安装 |
| json.tool 报 `unrecognized arguments: --indent` | Python 低于 3.9，没有 --indent、--compact 这些参数 | 用脚本（3.6+）或 jq |
| yq 命令对不上 | 装的是另一个同名 yq | 先 yq --version，按 references/yaml-csv.md 选对应写法 |
| 内存不够、进程被杀 | 文件太大，整份读入内存 | 用 jq --stream 拆成 JSON Lines，再用 --lines 逐行校验 |

## 输出契约

交付物按下面的顺序，每次都一样：

1. **结论**：合法或不合法；不合法给行列位置、原因、改法。
2. **结果**：改后的片段，或美化、压缩后的全文（太长就给命令和前几行）。
3. **改动清单**：只改格式不改内容；确需修复的逐条列出改了哪里，附 diff 或脚本核对结果。
4. **命令**：可直接复制，注明依赖版本（Python 3.9+ 的 json.tool、jq 1.7、或本技能脚本 Python 3.6+）。
5. **注意事项**：转 CSV、YAML 时的扁平规则与类型处理；精度、编码、兼容性风险。

占位符规则：[待确认] = 有两种理解、我先按其中一种改了的地方；[待补] = 需要用户提供的内容（接口文档里的字段规则、完整报错）。美化默认 2 空格、保留键顺序、中文不转义，用户另有要求照办。

交付前自检（每条都答「是」才交）：

- [ ] 结论里写了合法与否，不合法的写了行列号和原因？
- [ ] 改后的内容用脚本或 jq 重新校验过，内容与原数据一致（只动了格式）？
- [ ] 命令可直接复制，写回文件的命令不会先清空原文件？
- [ ] 数字精度、编码、NaN、重复键这类风险有就写了，没有就没提？
- [ ] 令牌、密码、身份证号已打码，示例地址只用 example.com？

## 示例

（示例，数据虚构；输出为本机实测）

> 用户：JSON 报错说第 1 行第 3087 列有问题，文件只有一行，怎么找？文件是 resp.json。

助手：信息够用，不追问，直接定位：

```
$ python3 scripts/json_check.py resp.json
不合法：Expecting ',' delimiter（第 1 行第 3087 列，第 3087 个字符）
出错处：","amount":537.5,"remark":"客户下单时在电话里一再说" <<这里>> 尽快发货""},{"id":1044,"
可能原因：漏了逗号，或字符串里的双引号没转义（写成 \" 或改用「」）
修法：只改第一处报错，改完重跑；报错位置是解析器「发现不对」的地方，真正的错常在它前面
```

**结论**：不合法。第 3087 列前面，remark 字段里的「尽快发货」用了英文双引号，没转义，字符串在「一再说」后面就被提前结束了。

**改法**（二选一，内容不变）：`"remark":"客户下单时在电话里一再说\"尽快发货\""`，或改用中文引号 `"remark":"客户下单时在电话里一再说「尽快发货」"`。

**复核**：改后重跑，结果为「合法：对象，3 个键（编码 UTF-8）」；需要好读的版本就 `python3 scripts/json_check.py resp.json --pretty --out resp.pretty.json`。

**注意**：这是接口返回的数据，根子在上游没做转义，请上游修，否则下次还会出现 [待确认：由谁通知上游]。

完整示例（嵌套 JSON 转成 Excel 能直接打开的 CSV，含扁平规则、两种命令和结果预览）见 [examples/json-to-csv-for-excel.md](examples/json-to-csv-for-excel.md)。

## 常见问题（FAQ）

**没装 jq 怎么办？** 用 Python 自带的 `python3 -m json.tool`（需 3.9+），或本技能的 scripts/json_check.py（3.6+，只用标准库）。

**为什么格式化后 1.10 变成了 1.1？** json.tool 和 Python 会重写数字写法，数值不变；要保留原写法用 jq 1.7 以上。

**中文变成了 \uXXXX 怎么办？** json.tool 加 --no-ensure-ascii；jq 和本技能脚本默认就不转义。

**能直接帮我调接口拿 JSON 吗？** 不能，本技能不连接任何接口；把响应保存成文件或贴出来就行。

**文件几个 GB，打不开怎么办？** 先 `head -c 300` 看顶层结构，再用 `jq --stream` 拆成 JSON Lines，抽样调好命令再跑全量。

**转成 CSV 后长编号末尾变成 0 了？** Excel 超过 15 位的数字会丢精度，这一列按文本导入；源头最好把长编号输出成字符串。

**VS Code 的 settings.json 有注释，报错了要不要删？** 那是 JSONC，注释和尾逗号合法；只有要交给严格 JSON 解析器时才删。

**在线格式化网站能用吗？** 数据里有令牌、手机号、身份证号的别用；本地用 jq、json.tool 或脚本一样快。

## 常见错误（反模式）

每条：错误做法 → 为什么错 → 正确做法。

1. **`jq . a.json > a.json` 原地改** → shell 先清空文件，数据直接没了 → 写到新文件再 mv 回去，或用脚本的 --out（先写临时文件再替换）。
2. **一次改完所有报错** → 一个漏掉的引号会引出一串假错误 → 只改第一处，改完重跑。
3. **手动把单引号换成双引号**来修 Python 打印结果 → 字符串里的撇号、None、True 会越改越乱 → `ast.literal_eval` 读入再 `json.dumps`（脚本 --from-python）。
4. **Windows 命令提示符里用单引号写 jq 过滤器** → cmd 不认单引号，报语法错 → 过滤器存成 filter.jq，用 `jq -f filter.jq`。
5. **以为「能解析」就是合规** → Python、jq 接受 NaN、Infinity，重复键静默只留最后一个，换个解析器就出错 → 脚本加 --strict 当门禁。
6. **长整数当数字传** → 超过 2^53 经 JavaScript、jq 1.6 解析会丢精度 → 请上游输出成字符串。
7. **用 `paths(scalars)` 摊平转 CSV** → 会漏掉 false 和 null → 用 `paths(type != "object" and type != "array")`。
8. **手拼 CSV** → 逗号、引号、换行不会正确加引号 → 用 jq 的 @csv 或 Python 的 csv 模块。
9. **给 Excel 的 CSV 不加 BOM** → 中文常乱码 → 加 UTF-8 BOM；超 15 位的数字列按文本导入。
10. **格式化和改内容混在一次提交** → diff 里看不出改了什么 → 分开提交，并用 `diff <(jq -S . old.json) <(jq -S . new.json)` 证明只动了格式。
11. **把含令牌、手机号的数据贴到在线格式化网站** → 数据外泄 → 本地处理，分享前打码。

## 边界与不做什么

- 只处理用户给的文本或文件，不连接任何接口或内部系统；示例地址只用 example.com。
- 数据里有令牌、密码、身份证号，先提醒打码，不在输出里复述。
- 字段该不该必填、数据内容对不对（金额、状态），以接口文档和业务负责人为准，不替业务拍板。
- JSONC、JSON5 的注释和尾逗号是合法写法，用户没要求转严格 JSON 就不改。
