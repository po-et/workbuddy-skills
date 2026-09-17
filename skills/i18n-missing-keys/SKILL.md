---
name: i18n-missing-keys
description: 国际化文案检查、i18n 缺失 key、多语言文案对齐、locales 翻译漏翻、文案占位符不一致、空翻译、未定义的文案键、没人用的废弃文案。当用户说「检查一下多语言文案是不是缺 key」「英文包比中文包少了哪些文案」「上线前对一遍 locales」「源码里用了但 locales 里没有的 key」「占位符对不上会不会报错」时使用。附纯标准库脚本 scripts/i18n_missing_keys.py：读取 locales 目录下的多语言 JSON（支持嵌套与命名空间子目录）与 .properties，以基准语言为准列出各语言缺失键、多余键、空值、{name} 与 %s 占位符不一致；可选 --src 扫描源码里 t('key')、i18n.t("key")、$t('key')、formatMessage 的用法，找出未定义与未使用的键；支持 --base、--limit、--json 与 --strict 门禁。
author: Captain
version: 0.1.0
display_name: "多语言文案键检查"
display_name_en: "i18n Missing Keys"
description_zh: "一条命令对齐多语言文案：缺失键、多余键、空值、占位符不一致一次列清，还能扫源码找出用了却没定义的键和没人用的废弃键；支持嵌套 JSON 与 properties；纯 Python 标准库，可作发版门禁。"
description_en: "One command to align locale files, listing missing keys, extra keys, empty values and placeholder mismatches, and optionally scanning source code for undefined and unused keys; supports nested JSON and properties; pure Python stdlib, usable as a release gate."
examples_zh:
  - "国际化文案检查，看看各语言缺了哪些 key"
  - "英文包比中文包少了哪些文案"
  - "扫一下源码，占位符对不上会不会报错，顺便找没人用的废弃文案"
examples_en:
  - "Check which keys are missing from each locale file"
  - "Which strings does the English bundle miss compared to Chinese"
  - "Scan the source for undefined and unused i18n keys"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🌐" } }
---

# 多语言文案键检查

翻译漏翻很少在开发环境暴露——界面上要么显示键名，要么显示空白，要么在带参数的文案上直接抛异常。这个技能把各语言的键集合、空值和占位符一次性对齐，再顺手把源码里的使用情况对一遍。

## 用法

```bash
python3 scripts/i18n_missing_keys.py                              # 自动探测 locales/、i18n/、src/locales/ 等常见目录
python3 scripts/i18n_missing_keys.py locales/ --base zh-CN        # 指定基准语言（默认取键最多的那个）
python3 scripts/i18n_missing_keys.py src/main/resources           # Java 的 messages_<lang>.properties
python3 scripts/i18n_missing_keys.py locales/ --src src/ --src app/   # 同时扫源码用法
python3 scripts/i18n_missing_keys.py locales/ --limit 50 --json
python3 scripts/i18n_missing_keys.py locales/ --src src/ --strict # 有缺键或未定义键则退出码 1
```

适用的目录布局：`locales/<lang>.json`（可嵌套，展开成 `cart.title` 这样的键路径）、`locales/<lang>/<命名空间>.json`（键自动加命名空间前缀）、`messages_<lang>.properties`、`<lang>.properties`。

## 流程

1. 先不加 `--src` 跑一次，把 **缺失键** 补齐——这是上线后最容易被用户截图的问题。
2. 再看 **空值**：键在但文案是空串，大多数 i18n 框架不会回退到基准语言，界面直接空白，比缺键更隐蔽。
3. 看 **占位符不一致**：`{name}` 变成 `{username}`、`{count}` 变成 `%d`、少一个参数，运行时不是渲染出 undefined 就是抛异常。
4. 加 `--src` 扫源码：**未定义的键** 按 high 处理（界面会直接显示键名）；**未使用的键** 只作清理参考。
5. 清理完把 `--strict` 挂进 CI，之后谁加了新文案没翻译就会在合并前被拦住。

## 检查项一览

| 级别 | 检查项 | 含义 |
|---|---|---|
| high | 缺失键 | 基准语言有、该语言没有 |
| high | 未定义键 | 源码里 `t('x')` 用到、基准语言里没有（需 `--src`） |
| warn | 空值 | 键存在但文案为空串或空白 |
| warn | 占位符不一致 | 与基准语言的占位符集合不同（`{name}`、`{{name}}`、`{0}`、`%s`、`%d`、`%1$s`、`%(name)s`） |
| info | 多余键 | 该语言有、基准语言没有 |
| info | 未使用键 | 基准语言有、源码里没搜到（需 `--src`） |

## 输出

文本模式先打印语言清单（每种语言的键数与文件位置，基准语言带 `←基准` 标记），再按语言分块列出各类问题，每类给出前 `--limit` 个键和一句改法，最后是 high/warn/info 小计。`--json` 输出 `base`、`languages`（每种语言的 missing/extra/empty/placeholder 明细）、`source`（used_keys、dynamic_calls、undefined、unused）与 `summary`，适合接 CI 注释或翻译平台。

## 边界

- 源码扫描是正则匹配，只能识别字面量键。`t('cart.' + status)` 与模板字符串这类动态拼接会被单独计数并在结果里标出，**不做**求值；所以「未使用键」只能当线索，删之前务必人工确认。
- 只认常见调用形态（`t`、`$t`、`i18n.t`、`tc`、`trans`、`translate`、`formatMessage`、`<FormattedMessage id>`、`getMessage`、`i18nKey`）。自研封装（如 `L('key')`）需要在脚本的 `USE_PATTERNS` 里加一条正则。
- 复数形态（`key_one` / `key_other` / ICU plural）按普通键对待，不做复数规则校验；CLDR 复数类别的完整性请用专门的 i18n 工具。
- 常见问题：基准语言选错会让报告整个反过来。默认取键最多的语言，团队里通常应显式写 `--base zh-CN` 固定下来。
- 不翻译文案、不改文件，只做检查与定位。
