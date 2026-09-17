---
name: config-env-diff
description: 多环境配置对比、配置差异检查、dev/test/预发/生产配置不一致、.env 与 .env.production 对比、YAML/JSON/properties/INI 配置 diff、环境配置漏配排查、上线前配置核对、配置项类型不一致。当用户说「对比一下预发和生产的配置」「这两个环境的配置差在哪」「生产是不是漏配了某个键」「配置文件 diff 一下，密码别显示出来」时使用。附纯标准库脚本 scripts/config_env_diff.py：支持 .env、JSON、YAML 子集、.properties、INI 五种格式混合对比，按扁平键路径分三类差异（仅部分文件有为 high、类型不同为 warn、值不同为 info），密钥类键值自动脱敏，支持 --ignore 键模式、--base 基准、多于两份文件同时对比、--json 与 --strict 门禁。
author: Captain
version: 0.1.0
display_name: "多环境配置对比"
display_name_en: "Config Env Diff"
description_zh: "一条命令把两份或多份配置拉平成键路径逐个对比，分出「只有一方有」「类型不同」「值不同」三类差异，密钥自动脱敏；.env、JSON、YAML、properties、INI 混着比也行；纯 Python 标准库，可作上线前门禁。"
description_en: "One command to flatten two or more config files into key paths and diff them, split into keys present on one side only, type mismatches and value differences, with secret values masked; mixes .env, JSON, YAML, properties and INI; pure Python stdlib, usable as a pre-release gate."
examples_zh:
  - "对比一下预发和生产的配置，看看差在哪"
  - "上线前配置核对，生产是不是漏配了某个键"
  - "把这两份 YAML 配置比一比，密码别显示出来"
examples_en:
  - "Diff the staging and production configs and show what changed"
  - "Check whether production is missing any key before release"
  - "Compare these two YAML configs with passwords masked"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🧩" } }
---

# 多环境配置对比

线上事故里有一大类是「配置在这个环境有、在那个环境没有」。这个技能把任意几份配置拉平成统一的键路径，逐键比出差异，并且默认把密钥类的值脱敏，报告可以直接贴到评审或工单里。

## 用法

```bash
python3 scripts/config_env_diff.py .env.staging .env.production
python3 scripts/config_env_diff.py config/dev.yaml config/prod.yaml --base config/prod.yaml
python3 scripts/config_env_diff.py a.properties b.properties c.properties     # 支持多于两份
python3 scripts/config_env_diff.py app-dev.yml app-prod.yml --ignore 'BUILD_*' --ignore '*.timestamp'
python3 scripts/config_env_diff.py dev.json prod.json --no-mask               # 需要看原值时
python3 scripts/config_env_diff.py dev.json prod.json --json
python3 scripts/config_env_diff.py dev.json prod.json --strict                # 有缺键或类型差异则退出码 1
```

格式按扩展名判断，判断不了就按内容嗅探。适用的输入包括 `.env` 系列、`.json`、`.yaml`/`.yml`、`.properties`、`.ini`/`.cfg`/`.conf`。

## 流程

1. 先跑一次全量对比，只看 **仅部分文件有**——这是最常见的上线事故来源（新环境漏配、老环境残留）。
2. 再看 **类型不同**：`8080` 与 `"8080"`、`true` 与 `"true"` 在强类型配置框架里会直接启动失败，报告会在括号里标出两侧类型。
3. 最后扫 **值不同**：超时、开关、域名、副本数、日志级别这几类要逐条确认；数据库地址、密码本来就该不同，不用管。
4. 确认无关的键（构建号、时间戳、机器名）用 `--ignore` 排除，让报告只剩真正要看的行。
5. 稳定之后把 `--strict` 挂到发布流水线上，缺键与类型不一致就卡住发布。

## 输出

| 级别 | 差异类型 | 含义 | 处理 |
|---|---|---|---|
| high | 仅部分文件有 | 某个键只在部分文件里存在 | 确认是漏配还是有意为之；有意为之就写进 `--ignore` |
| warn | 类型不同 | 同一键在不同文件里类型不一致 | 统一类型，或在配置类里显式做类型转换 |
| info | 值不同 | 键都在、值不同 | 环境差异多数正常，重点看会改变行为的键 |

文本模式输出对齐表格（键 + 每份文件一列，缺失显示「（缺失）」）；`--json` 输出 `files`、`summary`、`diffs` 三段，`diffs` 里带 `kind`、`severity`、`types`、`present`、`missing_in`，便于接门禁或做环境漂移趋势统计。键名含 `password`、`secret`、`token`、`key`、`credential`、`auth` 等字样时，值会脱敏成前 2 后 2 位，差异判定仍然基于原值。

## 边界

- YAML 只支持常见块结构（映射、列表、标量、块字符串），**不做**锚点与合并键（`<<: *base`）展开；Helm 模板请先 `helm template` 渲染再比。
- 列表按下标展开成 `tags[0]`、`tags[1]`，所以列表顺序变化会被报成值不同，这是预期行为。
- `.env`、`.properties`、`.ini` 里的标量会做一次类型推断（数字、布尔、null），这样才能和 JSON/YAML 交叉比较；如果你的配置里 `"true"` 必须当字符串，用 `--ignore` 排除该键。
- 常见问题：跨格式对比时两边命名风格不同（`DB_HOST` 与 `database.host`），会被全部报成「仅部分文件有」。同构文件之间比才有意义，跨格式请先统一键名或分组比。
- 不校验配置取值是否合法（端口范围、URL 合法性等），那是配置校验的事，这里只做差异对比。
