---
name: sensitive-data-mask
description: 日志脱敏、数据脱敏、对外分享前处理、把手机号和身份证打码、日志里的银行卡与邮箱与 IP 替换掉、URL 里的 token 与 JWT 与 AK 和 SK 与私钥块与连接串密码一起洗掉、给外部同学发日志前先过一遍、提工单附件前去掉个人信息、导出的 CSV 里有手机号怎么办、批量处理这个目录下的日志、脱敏后还要能对上同一个用户。当用户说「这份日志要发给外部，帮我脱敏」「把手机号和身份证打码」「保留可关联性但不要明文」「这个目录下的日志都洗一遍」「脱敏完给我一份命中统计」时使用。附纯标准库脚本 scripts/mask_sensitive.py，三种策略（mask 保留前后若干位、hash 取 sha256 前 8 位保持可关联、fake 用稳定假值），可 --keep-format 保持长度与格式，支持文件与目录与 stdin、--in-place 需显式确认、输出命中统计与 --report 映射清单。这是防御性工具，脱敏不等于合规。
author: Captain
version: 0.1.0
display_name: "日志与数据脱敏"
display_name_en: "Sensitive Data Mask"
description_zh: "对外分享日志或数据前的脱敏工具：识别手机号、身份证、银行卡、邮箱、IP、URL 凭据参数、JWT、AK/SK、私钥块、连接串密码与明确标注的中文 PII，按 mask/hash/fake 三种策略替换，可保持长度格式与跨文件可关联性，输出命中统计与不含明文的映射清单。纯 Python 标准库。"
description_en: "Defensive masking for logs and data you are about to share: detects phone numbers, national IDs, bank cards, emails, IPs, URL credential params, JWTs, AK/SK keys, private-key blocks, DSN passwords and explicitly labelled Chinese PII, then replaces them via mask/hash/fake — optionally format-preserving and correlatable across files — with a hit summary and a plaintext-free mapping report. Pure stdlib."
examples_zh:
  - "这份日志要发给外部客户，帮我日志脱敏"
  - "把手机号和身份证打码，但同一个用户还要能对上"
  - "批量处理这个目录下的日志，给我一份命中统计"
examples_en:
  - "Mask this log before I send it to an external partner"
  - "Hide phone numbers and IDs but keep the same user correlatable"
  - "Process every log under this directory and show the hit counts"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🛡️" } }
---

# 日志与数据脱敏

**这是一个防御性工具**：用于把自己手里的日志、导出数据在对外分享前洗一遍，降低误泄露个人信息与凭据的概率。它不是绕过审计的手段，也不产生「合规豁免」。

## 用法

```bash
python3 scripts/mask_sensitive.py app.log                          # 写到 app.log.masked
python3 scripts/mask_sensitive.py app.log --dry-run                # 只看命中统计，不写文件
python3 scripts/mask_sensitive.py logs/ --mode hash --salt team-2026 --report map.tsv
python3 scripts/mask_sensitive.py dump.csv --mode fake --keep-format
python3 scripts/mask_sensitive.py app.log --keep-subnet 2          # IP 只保留前两段网段
python3 scripts/mask_sensitive.py app.log --types phone,idcard,email
cat app.log | python3 scripts/mask_sensitive.py - > shared.log      # 统计走 stderr
python3 scripts/mask_sensitive.py logs/ --in-place --yes            # 原地覆盖，需显式确认
```

## 三种策略怎么选

| 策略 | 效果 | 适合 |
| --- | --- | --- |
| `mask`（默认） | `199****0001`、`110000********0011` | 人要看的日志，保留前后若干位便于对照工单 |
| `hash` | `<PHONE:cdbe2eb6>`，同一 salt 下同值同结果 | 要做统计、去重、跨文件关联，但不需要还原 |
| `fake` | `19965617353`、`user0a1b2c3d@example.com` | 要喂给解析器或演示环境，格式必须仍然合法 |

`--keep-format` 让替换值保持原值的长度与字符形态（数字对数字、字母对字母、汉字对「某」），IP 会保证每段仍 ≤ 255；适合字段有长度校验的场景。

## 流程

1. 先 `--dry-run` 跑一遍看命中统计，确认该命中的都命中了（尤其是自定义字段名里的密码、内部 ID 形态）。
2. 没命中的形态用 `--types` 之外的办法补：先 `sed` 替换掉特有格式，再跑本工具。
3. 选策略与 salt。需要跨文件、跨批次对上同一个人时，必须固定同一个 `--salt`；换 salt 等于换映射。
4. 输出到 `<file>.masked`（默认）或 `--out-dir`；确认无误再考虑 `--in-place --yes`，原地覆盖不可撤销。
5. `--report map.tsv` 留一份映射清单（只含原值哈希、替换值、命中次数，**不含原值明文**），排查时用来确认「这两条记录是不是同一个人」。
6. **人工抽样复核**几段再发出，并按公司流程走数据外发审批。

## 覆盖的形态

手机号（11 位）、身份证号（18 位含出生日期校验）、银行卡号（16–19 位过 Luhn，`--loose-card` 可放宽）、邮箱、IPv4（可 `--keep-subnet` 保留网段）、URL query 里的凭据参数（token/api_key/secret/sig/session/code 等）、JWT、AK 与 SK 类密钥（AWS/GitHub/Slack/OpenAI 常见前缀）、私钥块（BEGIN 到 END 整段替换）、连接串与配置里的密码（`scheme://user:pass@` 与 `password=`）、中文 PII 里**明确标注**的字段（`收货人`/`联系人`/`姓名`/`收货地址`/`住址` 等后面跟的内容）。

中文姓名与地址采取保守策略：**只处理有字段名标注的内容**，自由文本里的人名地名一律不动 —— 宁可漏掉让人工复核，也不把正常业务词误伤成 `某某`。

## 边界与常见问题

- **脱敏不等于合规**。敏感数据外发仍需按公司流程申请与审批；本工具只降低误泄露概率，不替代审批，也不改变数据的密级。
- **hash 模式不是加密**。手机号空间只有约 10 亿，不加 salt 时可被穷举反推；跨团队共享时请用只有己方知道的 `--salt`，并把映射清单当敏感文件保管。
- **漏报一定存在**。自定义编码的用户 ID、拼接过的证件号、图片里的信息、自由文本中的地址都识别不到；发出前必须人工抽样。
- **误报也存在**。16–19 位且恰好过 Luhn 的流水号会被当银行卡，`1.2.3.4` 这类版本号会被当 IP，`password=` 后面的占位符也会被替换；用 `--types` / `--skip` 收窄范围。
- 多行私钥块靠 BEGIN/END 成对识别，按块读取时不会被切断；单独出现 BEGIN 的残缺片段可能漏掉。
- 目录模式默认只处理常见文本扩展名（log/txt/csv/tsv/json/md/yaml/sql/conf 等），`--ext` 可改；已存在的输出文件默认跳过，`--force` 才覆盖。
- 不处理二进制、压缩包与数据库；压缩日志请先 `zcat` 再用 stdin 模式。
