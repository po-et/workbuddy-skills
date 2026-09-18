---
name: regex-explain
description: 正则表达式中文解释、正则拆解逐段翻译、正则测试与分组取值、灾难性回溯与 ReDoS 风险检查、正则改写加注释、regex 看不懂、正则匹配不上怎么排查。当用户说「这个正则是什么意思」「帮我解释一下这段正则」「这个正则为什么匹配不上」「这条正则会不会有性能问题」「把这个正则拆开加中文注释」「验证一下这个正则能不能匹配这几个字符串」时使用。附纯标准库脚本 scripts/regex_explain.py，把正则拆成字符类、量词、分组与命名分组、锚点、断言、反向引用、选择分支等 token 逐条中文解释，给一句话说明、8 类风险提示与 re.VERBOSE 注释版重写，--test 带 0.5 秒超时保护。
author: Captain
version: 0.1.0
display_name: "正则中文解释"
display_name_en: "Regex Explain"
description_zh: "一条命令把正则翻译成中文：逐 token 拆解加一句话说明，8 类风险提示（灾难性回溯、点不跨行、未转义的点、贪婪吞过头等），输出 re.VERBOSE 注释版重写，--test 验证匹配与分组并带超时保护。纯 Python 标准库。"
description_en: "One command to read a regex in plain Chinese: token-by-token breakdown plus a one-line summary, eight risk classes (catastrophic backtracking, dot not crossing newlines, unescaped dots, over-greedy quantifiers), a commented re.VERBOSE rewrite, and --test with a timeout guard. Pure Python stdlib."
examples_zh:
  - "这个正则是什么意思，顺便拿两个样例测一下"
  - "这个正则为什么匹配不上我的日志行"
  - "帮我看看这条正则会不会有性能问题"
examples_en:
  - "What does this regex mean? Test it with two samples"
  - "Why doesn't this regex match my log lines?"
  - "Check whether this regex has a performance problem"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🔍" } }
---

# 正则中文解释

把一段正则翻译成人话，顺手查出踩坑点。适用于读别人写的正则、自己写完要验证、线上 CPU 被正则打满要定位、把复杂正则改成可维护写法这四种场合。

## 用法

```bash
python3 scripts/regex_explain.py '^(\d{3})-(\d{4})$'
python3 scripts/regex_explain.py '(?P<user>[\w.+-]+)@(?P<host>[\w-]+(?:\.[\w-]+)+)' --test 'alice@mail.example.com' --test 'bad@@'
python3 scripts/regex_explain.py '^\s*(DEBUG|INFO|WARN|ERROR)\s+(.*)$' --flags i,m
python3 scripts/regex_explain.py '(a+)+b' --test 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaac'   # 0.5s 超时后判定回溯爆炸
python3 scripts/regex_explain.py '(\d{4})-(\d{2})-(\d{2})' --verbose-rewrite         # 只要注释版
python3 scripts/regex_explain.py '<pattern>' --json                                  # 机器可读
python3 scripts/regex_explain.py '<pattern>' --strict                                # 有 high 风险则退出码 1
```

用**单引号**包住正则，否则 shell 会把反斜杠和 `$` 吃掉。`--flags` 支持 `i,m,s,x,a`（也识别写在正则里的 `(?i)` 这类内联标志），`--test` 可以重复多次，`--timeout` 改超时秒数（默认 0.5）。

## 流程

1. **先读「一句话」**：按分组结构渲染成一句中文，先确认整体意图是否与用户理解一致，再看细节。
2. **逐项解释对照**：表格给出每个 token 的位置、片段、类型、说明，缩进反映分组嵌套层级；「匹配不上」的问题九成能在这一步指出来（少了 `m` 标志、`.` 不跨行、锚点位置不对、字符类里少了连字符）。
3. **看风险提示**：`high` 必须改（回溯爆炸、命名组重名），`warn` 大概率是 bug（未转义的点、贪婪吞过头、`a-Z` 跨段范围），`info` 是行为提醒。
4. **用 `--test` 验证**：把用户真实样例都喂进去，正例要匹配、反例要不匹配；输出会显示匹配片段、是否整串匹配、每个分组（含命名组）的取值。
5. **复杂表达式给重写版**：长度超过 40 字符或结构超过 12 项时自动附 `re.VERBOSE` 注释版，可直接贴进代码替换原写法（等价，仅多了空白与注释）。
6. **接 CI**：`--strict` 在存在 high 风险时返回 1，可以拦住把 ReDoS 写进代码的提交。

## 输出一览

| 部分 | 内容 |
|---|---|
| 头部 | 原正则、生效标志（含内联标志）与各标志的中文含义；编译失败时给出错误原文与位置 |
| 一句话 | 按分组结构渲染的整体说明，如「开头，捕获第 1 组（3 个数字），字面 -，捕获第 2 组（4 个数字），结尾」 |
| 逐项解释 | 位置 / 片段 / 类型 / 说明；类型含字符类、量词、分组、命名分组、非捕获组、断言、原子组、反向引用、锚点、转义类、选择分支、内联标志、注释 |
| 风险提示 | high / warn / info 三级，每条都带「→ 改法」 |
| VERBOSE 重写 | 逐行拆开并对齐注释的 `re.compile(r"""…""", re.VERBOSE)`，字面空格与 `#` 已自动转义 |
| 测试 | 每个样例的匹配结果、匹配片段与字符区间、是否整串匹配、各分组取值；超时会标 ⏱ |

风险提示的 8 类：嵌套量词导致的灾难性回溯（区分 `(a+)+` 这种真危险与 `(?:\.[\w-]+)+` 这种有固定分隔符、实际安全的写法）；量词套在含重叠分支的分组上；`.` 默认不跨行；把 `.` 当字面小数点用；从 JavaScript 抄来的多余 `\/`；`^ $` 在多行模式下的差异；贪婪量词吞到最后一个分隔符；表达式过长建议改 `re.VERBOSE`。另有字符类 `a-Z` 跨段范围、命名分组重名、捕获组过多按组号易错位这几条附加检查。

## 边界与常见问题

- 按 **Python `re`** 的语法解释。PCRE / JavaScript / Go RE2 的差异（`\p{...}`、条件匹配、递归、possessive 量词的支持程度）不在本脚本判断范围内，跨语言移植要另行验证。
- 回溯风险用的是「星高 > 1」启发式加一层固定前缀判断，**不做**形式化分析：报了 high 要用 `--test` 喂一条「长且结尾不匹配」的样例实测确认，没报也不等于绝对安全。
- 超时保护在 macOS / Linux 上用 SIGALRM，能真正打断正在回溯的匹配；Windows 没有 SIGALRM，退化为线程守护，只能报超时而拦不住 CPU 占用，压测请在类 Unix 环境做。
- RE2 / Rust regex 这类线性时间引擎不存在回溯问题，用它们时 high 提示可忽略。
- `--test` 用的是 `search`（部分匹配）语义，会额外标注是否整串匹配；需要严格整串请在正则里写 `^ $` 或改用 `fullmatch`。
- 正则里的敏感内容（内网域名、密钥格式）不要贴进公共渠道；脚本只在本地解析，不做任何网络请求。
