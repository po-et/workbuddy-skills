---
name: sensitive-data-mask
description: 日志脱敏、数据脱敏、对外分享前处理、把手机号和身份证打码、日志里的银行卡与邮箱与 IP 替换掉、URL 里的 token 与 JWT 与 AK 和 SK 与私钥块与连接串密码一起洗掉、给外部同学发日志前先过一遍、提工单附件前去掉个人信息、导出的 CSV 里有手机号怎么办、批量处理这个目录下的日志、脱敏后还要能对上同一个用户。当需要离线处理分享前的日志或文本导出时使用。附纯标准库脱敏脚本，输出独立副本、命中统计与不含原值明文的映射。写前检查输入/输出/报告别名冲突，目录保留层级，逐文件原子写入；--force 不授权覆盖输入。支持 mask/hash/fake、stdin 和仅统计；它不能证明全面匿名化，也不会发送材料。
author: Captain
version: 0.1.1
homepage: https://github.com/po-et/workbuddy-skills
license: CC-BY-4.0 AND MIT
display_name: "日志与数据脱敏"
display_name_en: "Sensitive Data Mask"
description_zh: "日志与导出文本的离线脱敏：输出独立副本和命中统计；保护原文件、保留目录层级、原子写入，失败与跳过显式报告。有限模式识别，不宣称全面匿名化，不自动发送。"
description_en: "Mask local logs and text exports offline while protecting input files, preserving directory structure and writing atomic outputs. Report hits, failures and skipped files; finite patterns do not guarantee anonymization."
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

交付独立的脱敏副本与逐文件处理统计，原始材料默认只读。不发送日志、连接外部系统或修改分享权限。用 Python 3 标准库运行，输入为 UTF-8 文本；其他编码先另存一份 UTF-8 副本。

## 运行与检查

路径相对本技能安装目录；替换为自己的输入路径。

```bash
python3 scripts/mask_sensitive.py examples/logs --dry-run --types phone,email --json
python3 scripts/mask_sensitive.py examples/logs --out-dir /path/to/new-masked --types phone,email --json
python3 scripts/mask_sensitive.py app.log --mode hash --salt local-example --report /path/to/new-map.json --json
```

默认每个文件输出到 `<file>.masked`。目录输入配合 `--out-dir` 会保留子目录，两个模块的 `app.log` 分开保存。多个独立文件如果映射到同一输出会提前报错；可以改成共同父目录输入。

`--json` 返回成功 `files`、`skipped`、`failed`、`batch_status` 和命中统计。stdin 模式结果走 stdout，统计走 stderr。映射只含原值短哈希、替换值与次数，不包含原值明文；默认不生成映射。

- `0`：本轮所有输入完成，或者仅统计完成；不表示已发现全部敏感内容。
- `1`：部分输出已存在而跳过；已经产生的成功输出保留。
- `2`：路径冲突、读取/写入失败等；看逐文件失败原因。命中数仅统计成功处理文件。

完整输出保护约束见 [文件处理契约](references/file-protection.md)。

## 选择替换策略

| 模式 | 行为 | 适用用途 |
|---|---|---|
| `mask` | 保留前后少量字符，中间遮蔽 | 人阅读时保留有限线索 |
| `hash` | 同一 salt 下用 SHA-256 前 8 位关联 | 有限的跨文件关联；有碰撞与穷举风险，不是加密 |
| `fake` | 用确定性的示例形态替换 | 演示、解析器测试；不能保证下游所有格式约束 |

`--keep-format` 保持长度与字符形态；`--keep-subnet` 保留部分网段。`--types` 和 `--skip` 按实际材料收窄识别范围。不同 salt 不应假定可关联，不把共享 salt 当作保密保证。

## 原件与覆盖

先检查独立副本。`--force` 仅允许覆盖与输入无关的输出；同一文件、符号链接路径或硬链接别名与输入冲突仍被拒绝。映射报告也不能覆盖输入或脱敏副本。普通文件成功写完后才提交到目标，读取/写入失败不把已有输出截空。

如果用户明确要求替换原件，才用 `--in-place --yes`；这会替换原文件，不能用 `--force` 代替。它与 `--out-dir` 不可同时使用。新版不使用可预猜的临时文件名，保留原件权限位；处理失败保留原件。没有原地需求时始终交付副本。

## 覆盖范围与使用边界

已覆盖的模式包括手机号、证件/银行卡形态、邮箱、IPv4、部分 URL 凭据参数、JWT、常见密钥前缀、私钥块、连接串密码与明确标注的中文姓名/地址。识别规则有漏报与误报，自由文本姓名、图像和自定义编码不在保证范围内；未命中不能当作安全证明。

按用户的数据范围复核交付，不把脱敏结果等同于全面匿名化。随包样例均为合成内容；本轮只验证脚本与文件保护，未证明第三方使用、企业合规或 WorkBuddy 客户端自动调用。

本版文件保护与样例由本项目原创增强。正文 CC BY 4.0，代码 MIT：https://github.com/po-et/workbuddy-skills
