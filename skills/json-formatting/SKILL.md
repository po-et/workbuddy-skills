---
name: json-formatting
description: "JSON 格式化——把 JSON 美化、压缩成一行、排序键，按报错定位语法错误，并做字段与类型粗校验。当用户说「JSON 格式化」「JSON 报错」「压缩成一行」「JSON 转 CSV」「JSON 转 YAML」时使用。"
author: Captain
version: 0.1.0
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
---

# JSON 格式化

定位一句话：**格式化只是让 JSON 好读；要紧的是确认它合法、改完内容一个字没变。**
何时用：一整行 JSON 要看清；解析报错要定位；要压缩成一行；要粗查字段和类型；大文件打不开；要转成 YAML 或 CSV。

## 先判断三件事

1. **是不是 JSON。** JSONC、JSON5（VS Code 设置、tsconfig）允许注释和尾逗号，那不算错；JSON Lines 是一行一个对象，要按行处理；单引号加 None、True 的是 Python 打印结果。
2. **多大、什么编码。** 几十 MB 起别用编辑器，上 GB 走流式。GBK 编码的文件 Python 报解码错误，jq 却不报错、把中文换成 � 照常输出，先转码：`iconv -f GBK -t UTF-8 in.json > in.utf8.json`。含令牌、手机号的数据别贴到在线格式化网站。
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

## 最常见的语法错误：按报错定位

报错位置是解析器「发现不对」的地方，真正的错常在它前面，比如多余的逗号报在右括号上。只有一行的文件用这段脚本打印出错处前后：

```bash
python3 - a.json <<'EOF'
import json, sys
s = open(sys.argv[1], encoding='utf-8-sig').read()
try: json.loads(s); print('合法')
except json.JSONDecodeError as e: print(e.msg, e.lineno, e.colno, s[max(0, e.pos-40):e.pos] + ' <<这里>> ' + s[e.pos:e.pos+20])
EOF
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

修复流程：只改第一处报错，改完重跑；一个漏掉的引号会引出一串假错误。更隐蔽的是 `"C:\new"`：不报错，`\n` 被当成了换行。Python 打印结果用 `ast.literal_eval` 读入再 `json.dumps` 输出，比手改引号可靠。

能解析也未必合规：Python 和 jq 都接受 NaN、Infinity，换个解析器就报错；重复键两者都静默只留最后一个。

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

YAML：`yq` 有两个同名工具，先 `yq --version`。Go 版（mikefarah）用 `yq -p json -o yaml a.json`，反向 `yq -o json a.yaml`；Python 版（kislyuk）用 `yq -y . a.json`，反向 `yq . a.yaml`。YAML 1.1 解析器（如 PyYAML）会把 `NO`、`on` 变布尔，`00123` 按八进制变 83，`1.10` 变 1.1，日期变日期对象、转 JSON 报 not JSON serializable；国家代码、邮编、版本号一律加引号，转完抽查。注释会丢，锚点会展开，--- 分隔的多文档逐个转。

CSV：
- 先定扁平规则写进交付说明：嵌套字段用点路径做列名，数组用分号拼成一格或一元素一行。别用 `paths(scalars)` 摊平，它会漏掉 false 和 null：

```bash
jq -c '.items[] | [paths(type != "object" and type != "array") as $p | {($p|map(tostring)|join(".")): getpath($p)}] | add' a.json
```

- 用 @csv 或 csv 模块生成，别手拼：逗号、引号、换行才会正确加引号；数组进 @csv 会报 is not valid in a csv row，先 join。
- 给 Excel：加 UTF-8 BOM，否则中文常乱码；超 15 位的数字（身份证号）会丢末位，该列按文本导入。CSV 转回 JSON 全是字符串，类型要自己转。

```bash
{ printf '\xef\xbb\xbf'; jq -r '["id","name","tags"], (.items[] | [.id, .name, ((.tags // []) | join(";"))]) | @csv' a.json; } > out.csv
```

## 输出契约

1. 先给结论：合法或不合法；不合法给行列位置、原因、改法和改后片段。
2. 美化默认 2 空格、保留键顺序、中文不转义，用户另有要求照办。
3. 只改格式不改内容；确需修复的逐条列出改了哪里，附 diff 核对结果。
4. 命令可直接复制，注明依赖版本（Python 3.9+、jq 1.7）；转 CSV、YAML 写明扁平规则与类型处理。

## 边界与不做什么

- 只处理用户给的文本或文件，不连接任何接口或内部系统；示例地址只用 example.com。
- 数据里有令牌、密码、身份证号，先提醒打码，不在输出里复述。
- 字段该不该必填、数据内容对不对（金额、状态），以接口文档和业务负责人为准，不替业务拍板。
- JSONC、JSON5 的注释和尾逗号是合法写法，用户没要求转严格 JSON 就不改。
