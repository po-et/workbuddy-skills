---
name: json-diff
description: JSON 语义对比、配置文件差异、两个环境的配置对比、生产和预发配置不一致排查、接口返回的 JSON 前后对比、配置漂移检测、JSON 结构差异、比对两份 JSON 哪里不一样。当用户说「这两份配置有什么区别」「生产和预发的配置对比一下」「接口返回变了帮我看看差在哪」「把 JSON 差异列出来」「配置漂移检查加进 CI」时使用。附纯标准库脚本 scripts/json_diff.py，按扁平路径输出仅左有、仅右有、值不同、类型不同、数组长度变化；数组可按 id 等字段配对而不是按下标；支持路径通配忽略、密钥类路径脱敏、--summary-only，有差异退出码 1。
author: Captain
version: 0.1.0
display_name: "JSON 语义对比"
display_name_en: "JSON Diff"
description_zh: "一条命令对比两份 JSON 或配置：按 a.b[0].c 扁平路径列出仅左有、仅右有、值不同（旧→新）、类型不同、数组长度变化；数组可按业务键配对避免整体位移误报，密钥类路径自动脱敏，有差异返回退出码 1。纯 Python 标准库。"
description_en: "One command to diff two JSON or config files by flattened a.b[0].c paths: left-only, right-only, changed values (old to new), type changes, array length changes; arrays can be matched by a business key instead of index, secret-looking paths are masked, and any difference exits 1. Pure Python stdlib."
examples_zh:
  - "这两份配置有什么区别，密码别打出来"
  - "生产和预发的配置对比一下，忽略时间戳字段"
  - "接口返回变了帮我看看差在哪，数组按 id 对齐"
examples_en:
  - "Diff these two configs and keep secrets masked"
  - "Compare prod and staging configs, ignoring timestamp fields"
  - "The API response changed, show the diff with arrays matched by id"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧮" } }
---

# JSON 语义对比

按语义而不是按文本行比两份 JSON。适用于「同一个服务在两个环境表现不同」「昨天还好今天报错」「接口返回悄悄变了」这类问题，也可以当 CI 里的配置漂移门禁。`diff` 会被键顺序和缩进干扰，这个脚本只看结构与值。

## 用法

```bash
python3 scripts/json_diff.py old.json new.json
python3 scripts/json_diff.py prod.json staging.json --ignore '*.updatedAt' --ignore 'meta.*'
python3 scripts/json_diff.py a.json b.json --array-key id                  # 数组按元素的 id 配对
python3 scripts/json_diff.py a.json b.json --array-key 'spec.containers=name'   # 只对某条路径指定键
python3 scripts/json_diff.py a.json b.json --summary-only                  # 只要统计
python3 scripts/json_diff.py a.json b.json --json                          # 机器可读
python3 scripts/json_diff.py a.json b.json --no-mask                       # 关掉密钥脱敏（默认开）
curl -s https://api.example.com/v1/config | python3 scripts/json_diff.py - baseline.json
```

退出码：**0** 无差异、**1** 有差异、**2** 读取或解析失败。左右两个文件都可以是 JSON 或 JSONL（JSONL 只取第一条记录，并在输出里标注）。

## 流程

1. **先跑默认对比**：差异条数与五类统计在第一行，量大就先 `--summary-only` 看规模。
2. **数组噪音大就加 `--array-key`**：一旦数组元素顺序变了，按下标对比会把整段报成「值不同」。用 `--array-key id`（或元素里真实的业务键，如 `name`、`host`、`appId`）后，输出会变成 `upstreams[id=coupon]` 这样的定位，新增/删除/修改一眼可辨。
3. **忽略无意义字段**：`--ignore` 支持通配，常用 `'*.updatedAt'`、`'*.revision'`、`'meta.*'`、`'*.timestamp'`。写不带通配的路径（如 `image`）会连同它的子树一起忽略。
4. **按类型定位问题**：`类型不同`（`6` 变成 `"2"`）几乎一定是配置写错或序列化变更，优先看；`仅左有`/`仅右有` 往下是新老版本字段增删；`数组长度变化` 关注白名单、副本数、路由表这类。
5. **接 CI**：在流水线里对比线上快照与仓库里的基线文件，退出码 1 即拦住配置漂移；要留档就用 `--json` 存起来。

## 输出一览

| 部分 | 内容 |
|---|---|
| 首行 | 左右文件名；JSONL 会额外提示只对比了第一条记录 |
| 统计 | 差异总数与五类分项（仅左有、仅右有、值不同、类型不同、数组长度变化），以及被忽略的处数 |
| 提示行 | 数组缺少键字段退回按下标、键值重复只取第一个这类说明 |
| 仅左侧有 | `- 路径 = 值` |
| 仅右侧有 | `+ 路径 = 值` |
| 值不同 | `~ 路径` 加一行 `旧值  →  新值` |
| 类型不同 | `! 路径` 加一行 `整数 6  →  字符串 "2"` |
| 数组长度变化 | `# 路径  3 项  →  4 项` |

路径写法：对象用 `.key`（key 含点或特殊字符时写成 `["k.v"]`），数组按下标是 `[0]`，按业务键配对后是 `[id=coupon]`，根节点显示为 `(根)`。容器值折叠成 `{…4 个键}` / `[…3 项]`，过长的标量截断显示。

**脱敏**：路径里含 password / passwd / secret / token / apikey / accesskey / privatekey / credential / key 的值默认不打印原文，只显示 `***（23 字符）`，长度变化仍可见，方便判断「是不是真换了」。要看原文加 `--no-mask`（别在共享终端或 CI 日志里这么做）。

## 边界与常见问题

- 只比**语义**，不比键顺序、缩进、注释；JSON 本身不支持注释，带注释的 JSON5 / JSONC 请先转成标准 JSON。
- 数值按 Python 的相等语义比，`1` 与 `1.0` 视为同值不报类型不同；`true` 与 `1` 会报类型不同。
- `--array-key` 只在数组元素**全是对象且都含该字段**时生效，否则打印提示并退回按下标对比；键值重复时只对比第一个。
- JSONL 只取第一条记录，**不做**整文件的行级配对；要比整份 JSONL 请先按业务键拆或转成一个数组再比。
- 不做类型宽容（不会把 `"6"` 和 `6` 当相等），这正是它能抓出配置串类型的原因。
- 忽略规则用 fnmatch 语义，`*` 会跨 `.` 匹配；`meta.*` 同时匹配 `meta.a` 与 `meta.a.b`，需要精确匹配就写完整路径。
- YAML 配置请先用你手上的工具转成 JSON 再比（本脚本不引入第三方依赖，不解析 YAML）。
