# 来源与许可

- 上游：[mattpocock/skills — handoff](https://github.com/mattpocock/skills/blob/main/skills/productivity/handoff/SKILL.md)。作者 Matt Pocock；MIT，Copyright (c) 2026 Matt Pocock。
- 原取回日期：2026-09-17；本轮许可与上游原文复核：2026-10-13。完整上游声明保存在 `LICENSE` 和 [references/upstream-license.md](references/upstream-license.md)；后者随 SkillHub 包保留，避免无扩展名上传限制丢失许可文本。

## 逐条增强

1. 中文化流程，保留默认临时目录、建议技能、只引用既有产物与脱敏要求。
2. 新增原创标准库 `scripts/build_handoff.py`：严格状态 JSON 转为 Markdown/JSON；文件 SHA-256、缺失/冲突证据、验证记录时间与未完项检查。
3. 不执行输入中的命令；区分输入报告状态与本轮文件核对。删除无来源的进度百分比模板。
4. 新增输入契约与合成示例；工作区之外落盘、拒绝覆盖旧报告、拒绝父目录穿越、符号链接与疑似凭证。
5. 使用 CLI 退出码表达完整性问题，记录问题仍交付报告，不把未完任务冒充失败的交接。

## 实测与限制

2026-10-13：18 项自动化行为测试通过，覆盖哈希一致/冲突、文件缺失、符号链接、目录穿越、大小限制、重复字段、时间缺失、已完成状态冲突、退出码、产物落盘与工作区不变。

本轮只在本地 Python 脚本运行验证；新版尚未在 WorkBuddy 客户端完成调用验收。合成示例和维护者测试不是独立用户使用。凭证检查是有限模式，不宣称全面脱敏。

新增脚本由 Captain Yang 编写并以 MIT 发布；上游正文改编的许可与署名继续保留。
