# 与 YAML、CSV 互转

SKILL.md 里只留了两条原则；这里是完整做法与坑。

## YAML

`yq` 有两个同名工具，先 `yq --version`：

- Go 版（mikefarah）：`yq -p json -o yaml a.json`，反向 `yq -o json a.yaml`。
- Python 版（kislyuk）：`yq -y . a.json`，反向 `yq . a.yaml`。

YAML 1.1 解析器（如 PyYAML）会把 `NO`、`on` 变布尔，`00123` 按八进制变 83，`1.10` 变 1.1，日期变日期对象、转 JSON 报 not JSON serializable；国家代码、邮编、版本号一律加引号，转完抽查。注释会丢，锚点会展开，--- 分隔的多文档逐个转。

## CSV

先定扁平规则，写进交付说明：嵌套字段用点路径做列名，数组用分号拼成一格或一元素一行。别用 `paths(scalars)` 摊平，它会漏掉 false 和 null：

```bash
jq -c '.items[] | [paths(type != "object" and type != "array") as $p | {($p|map(tostring)|join(".")): getpath($p)}] | add' a.json
```

- 用 @csv 或 csv 模块生成，别手拼：逗号、引号、换行才会正确加引号；数组进 @csv 会报 is not valid in a csv row，先 join。
- 给 Excel：加 UTF-8 BOM，否则中文常乱码；超 15 位的数字（身份证号）会丢末位，该列按文本导入。CSV 转回 JSON 全是字符串，类型要自己转。

jq 写法（指定列，数组用分号拼成一格，开头加 BOM）：

```bash
{ printf '\xef\xbb\xbf'; jq -r '["id","name","tags"], (.items[] | [.id, .name, ((.tags // []) | join(";"))]) | @csv' a.json; } > out.csv
```

没有 jq 时的纯 Python 写法（只用标准库；嵌套自动摊平成点路径列名，数组用分号拼成一格，true/false 保持小写，null 写成空格子，自动加 BOM）：

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

把 `["items"]` 换成你数据里记录数组所在的键；顶层就是数组时去掉它。数组里是对象（而不是字符串、数字）时，拼成一格会变成难读的文本，改成「一元素一行」更合适。

## 转完核对

- 行数：CSV 数据行数 = 记录数（`jq '.items | length' a.json`）。
- 抽查三类值：带逗号或引号的文本、空值、长编号。
- YAML 转回 JSON 后与原文件比：`diff <(jq -S . a.json) <(jq -S . back.json)`。
