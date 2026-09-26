# 示例：嵌套 JSON 转成 Excel 能直接打开的 CSV

（示例：数据是虚构的，邮箱只用 example.com；命令与输出为本机实测，jq 1.7.1、Python 3.12。）

## 第 1 轮：用户开口

> 用户：这个 JSON 要转成 CSV 给同事用 Excel 打开，嵌套字段怎么处理？
>
> ```json
> {"items":[{"id":1,"name":"张三","contact":{"city":"北京","email":"zhang@example.com"},"tags":["vip","新客"],"order_no":"202609010000012345","active":true},{"id":2,"name":"李四, 王五","contact":{"city":"上海","email":null},"tags":[],"order_no":"202609010000012346","active":false},{"id":3,"name":"赵\"六\"","contact":{"city":"广州"},"order_no":"202609010000012347","active":true}]}
> ```

## 第 2 轮：助手只问两件事，其余用默认

> 助手：两件事确认一下，不回复我就按括号里的默认做、标 [待确认]：
> 1. 要哪些列？（默认全部字段，嵌套字段用点路径做列名，如 contact.city）
> 2. tags 这类数组：拼成一格，还是一个元素一行？（默认用分号拼成一格）

> 用户：全要，数组拼一格就行。

## 第 3 轮：助手交付（按输出契约的固定顺序）

**1 结论**：合法，3 条记录；有嵌套对象 contact、数组 tags、18 位长编号 order_no，第 3 条缺 email 和 tags。

```
$ python3 scripts/json_check.py a.json
合法：对象，1 个键（编码 UTF-8）
```

**2 扁平规则**（写进交付说明，同事一看就懂）：

- 嵌套字段用点路径做列名：contact.city、contact.email。
- 数组用分号拼成一格：vip;新客。空数组、缺失字段、null 都写成空格子。
- true / false 保持小写原样。
- 文件开头加 UTF-8 BOM，Excel 双击打开中文不乱码。

**3 命令**（纯 Python 标准库写法，没装 jq 也能用；更多写法和坑见 [references/yaml-csv.md](../references/yaml-csv.md)）：

```bash
python3 - a.json out.csv <<'EOF'
import csv, json, sys

def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = prefix + k
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        elif isinstance(v, list):
            out[key] = ";".join(str(x) for x in v)
        elif isinstance(v, bool):
            out[key] = "true" if v else "false"
        else:
            out[key] = "" if v is None else v
    return out

rows = [flat(r) for r in json.load(open(sys.argv[1], encoding="utf-8-sig"))["items"]]
cols = list(dict.fromkeys(k for r in rows for k in r))
with open(sys.argv[2], "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, restval="")
    w.writeheader()
    w.writerows(rows)
print("写出 %d 行、%d 列：%s" % (len(rows), len(cols), "、".join(cols)))
EOF
```

运行输出：

```
写出 3 行、7 列：id、name、contact.city、contact.email、tags、order_no、active
```

**4 结果预览**（out.csv，前面有 BOM，看不见）：

```
id,name,contact.city,contact.email,tags,order_no,active
1,张三,北京,zhang@example.com,vip;新客,202609010000012345,true
2,"李四, 王五",上海,,,202609010000012346,false
3,"赵""六""",广州,,,202609010000012347,true
```

带逗号的「李四, 王五」和带引号的「赵"六"」都被正确加了引号，这就是不手拼 CSV 的原因。

**5 注意事项**

- order_no 是 18 位：Excel 双击打开会把超过 15 位的数字丢掉末几位。请同事用 Excel 的导入功能（不要双击打开）把这一列设为文本 [待确认：同事用的 Excel 版本]；最稳的做法是源头就把长编号当字符串给。
- 这份 CSV 再转回 JSON 时所有值都是字符串，id、active 的类型要自己转回来。
- 只挑几列时用 jq 写法更短：

```bash
{ printf '\xef\xbb\xbf'; jq -r '["id","name","city","tags","order_no"], (.items[] | [.id, .name, .contact.city, ((.tags // []) | join(";")), .order_no]) | @csv' a.json; } > out.csv
```

它的输出（jq 1.7.1 实测）：

```
"id","name","city","tags","order_no"
1,"张三","北京","vip;新客","202609010000012345"
2,"李四, 王五","上海","","202609010000012346"
3,"赵""六""","广州","","202609010000012347"
```

**待确认**：数组确认拼成一格；同事的 Excel 版本与导入方式。
