---
name: curl-to-code
description: curl 命令转代码、把 curl 翻译成 Python/Go/Java/JS、浏览器 Copy as cURL 转请求代码、接口联调脚本生成、把抓包的请求改成可复用代码、curl 转 requests/fetch/axios/net-http/HttpClient/PHP curl。当用户说「这条 curl 怎么用 Python 写」「把这个 curl 转成 Go」「从 Chrome 复制的 curl 帮我改成代码」「照这个接口写个调用示例」「curl 里的 token 别写死在代码里」时使用。附纯标准库脚本 scripts/curl_to_code.py，解析 -X/-H/-d/-F/-u/-b/-G/-L/-k/--compressed/--max-time 与单双引号、反斜杠续行、ANSI-C 引用，输出 8 种语言代码，Authorization/Cookie/token 类请求头自动改读环境变量，支持标准输入、--all、--json。
author: Captain
version: 0.1.0
display_name: "curl 转代码"
display_name_en: "curl to Code"
description_zh: "一条命令把 curl 翻译成 8 种语言的请求代码（requests/urllib/fetch/axios/net-http/HttpClient/PHP curl/可读 curl），凭据自动改读环境变量；支持从浏览器 Copy as cURL 直接粘贴。纯 Python 标准库。"
description_en: "One command turns a curl invocation into request code in 8 languages (requests, urllib, fetch, axios, net/http, HttpClient, PHP curl, readable curl), with credentials rewritten to read from env vars; paste straight from Copy as cURL. Pure Python stdlib."
examples_zh:
  - "把这条 curl 转成 Python 代码，token 别写死在代码里"
  - "从 Chrome 复制的 curl 帮我改成 Go 的请求代码"
  - "这个上传接口的 curl，输出全部语言版本给我挑"
examples_en:
  - "Convert this curl to Python without hardcoding the token"
  - "Turn the curl I copied from Chrome into Go request code"
  - "Show every language version of this upload curl"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔁" } }
---

# curl 转代码

把一条 curl 命令翻译成目标语言的请求代码。适用于三种场景：拿到接口文档里的 curl 示例要写调用方、从浏览器 DevTools「Copy as cURL」复制的请求要变成可复用脚本、把手工调试的 curl 固化成自动化用例。凭据默认不落到代码里。

## 用法

```bash
python3 scripts/curl_to_code.py "curl -X POST https://api.example.com/v2/issues -H 'Content-Type: application/json' -d '{\"title\":\"bug\"}'"
python3 scripts/curl_to_code.py "curl ..." --lang go-nethttp     # 指定语言
python3 scripts/curl_to_code.py "curl ..." --all                 # 8 种语言全出
pbpaste | python3 scripts/curl_to_code.py -                      # 从剪贴板/标准输入读（Copy as cURL 直接粘）
python3 scripts/curl_to_code.py "curl ..." --json                 # 机器可读（含解析结果与环境变量清单）
python3 scripts/curl_to_code.py "curl ..." --no-env               # 不做环境变量替换（不推荐）
```

`--lang` 可选值：`python-requests`（默认）、`python-stdlib`、`javascript-fetch`、`node-axios`、`go-nethttp`、`java-httpclient`、`php-curl`、`shell`。

## 流程

1. **拿到 curl**：用户贴命令就直接传参；很长或带大量请求头时让用户用管道喂给 `-`，避免 shell 二次转义把引号吃掉。
2. **先看摘要行**：脚本第一行输出 `方法 URL`，第二行是请求头个数、请求体类型、超时、是否跟随重定向。与用户预期不一致时说明是原命令写法问题，不要改代码兜。
3. **选语言**：用户没说就按仓库主语言给；拿不准用 `--all` 让用户挑。`shell` 是把原命令重排成多行可读 curl，适合写进文档。
4. **处理凭据**：输出末尾的「环境变量」表列出哪些请求头被换成了 `os.environ[...]` / `process.env` / `os.Getenv` / `System.getenv` / `getenv()`，原值只显示前 4 位。把导出命令一并给用户，并提醒放进密钥管理而不是提交进仓库。
5. **读「说明」与「注意」**：`-k`、无 `-L`、`-G` 编码、JSON 体缺 Content-Type 这些行为差异都在这里，转述给用户。

## 输出一览

| 部分 | 内容 |
|---|---|
| 摘要 | 方法、URL、请求头数量、请求体类型（json / form / multipart / raw / 无）、超时、重定向与 TLS 校验开关 |
| 代码块 | 目标语言完整可运行片段：URL、请求头字典、请求体、超时、重定向策略、状态码与响应体打印 |
| 环境变量 | 命中的请求头 → 环境变量名 → 原值掩码与长度；附 `export` 提示 |
| 说明 | 与原 curl 的行为差异（未带 `-L` 时显式关闭跟随、`-G` 参数重新编码、补 Content-Type） |
| 注意 | 解析告警（未识别选项、cookie 文件、`-d @file`、多个 URL、`-k` 关闭证书校验） |

支持的 curl 选项：`-X/--request`、`-H/--header`、`-d/--data/--data-raw/--data-binary/--data-ascii`、`--data-urlencode`、`-F/--form/--form-string`、`-u/--user`、`--oauth2-bearer`、`-b/--cookie`、`-A/--user-agent`、`-e/--referer`、`--url`、`-G/--get`、`-L`、`-k`、`--compressed`、`-m/--max-time`、`-I/--head`；`-sS`、`-kL` 这类短选项簇会自动展开，`-o`、`-w`、`-x` 等与代码无关的选项被吃掉。

被判定为敏感的请求头（值改读环境变量）：名字里含 authorization、cookie、token、api-key、secret、password、access-key、private-token、session、csrf、signature、x-auth；`Bearer` / `Basic` / `Token` 这类前缀会保留在代码里，只有凭据本体进环境变量。

## 边界与常见问题

- **不发请求**，只做静态转换，不校验接口是否可达；要验证连通性用 http-health-check 这类技能。
- 只转第一个 URL；`--next` 串起来的多请求 curl 需要拆开分别转。
- `-d @file` / `-b cookies.txt` / `-T` 从文件读取的场景只给占位路径并告警，不去读文件。
- 多行 multipart 二进制上传在 `java-httpclient` 与 `python-stdlib` 里给的是字符串拼装骨架，二进制文件请改用 byte 数组或 `MultipartBodyPublisher`。
- `-k` 生成的代码会关闭证书校验，仅用于本地调试，**不要**带进生产；`javascript-fetch` 无法表达，只给注释。
- 环境变量名由请求头名推导（`Authorization` → `API_TOKEN`，`Cookie` → `COOKIE`，其余大写下划线化），同名冲突自动加后缀；要换名字直接改生成的代码。
- 请求体里的凭据（例如 form 字段里的 password）不会被替换，只处理请求头与 `-u`，这种情况请手工挪进环境变量。
