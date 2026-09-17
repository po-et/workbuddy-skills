---
name: skill-lint
description: 技能体检、SKILL.md 质量打分、给 Skill 提可发现性与结构建议。当用户说「帮我看看这个技能写得怎么样」「为什么我的技能没人下载」「SKILL.md 怎么写才容易被搜到」「检查一下技能的 frontmatter」「发布前体检」「批量给技能打分」时使用。脚本从五个维度各 20 分打分：可发现性（description 是否说清什么时候用、触发词与同义词、tags）、结构（何时用/流程/产出/边界四节、篇幅）、可执行性（命令块、引用的脚本存在）、合规（frontmatter 必填、无扩展名文件、复刻有 ATTRIBUTION、无密钥）、示例（examples 数量与描述一致性），并给出逐条修改建议。零依赖。
author: Captain
version: 0.1.0
display_name: "技能体检（SKILL.md 打分）"
display_name_en: "Skill Lint"
description_zh: "五维度给 SKILL.md 打分并给修改建议：可发现性、结构、可执行性、合规、示例；适合发布前自检与批量体检。"
description_en: "Score a SKILL.md on discoverability, structure, executability, compliance and examples, with concrete fix suggestions; for pre-publish checks and batch audits."
examples_zh:
  - "给 skills/ 下所有技能打个分，看哪个最需要改"
  - "这个技能为什么搜不到，帮我体检一下描述"
  - "发布前检查这个 SKILL.md 有没有问题"
examples_en:
  - "Score every skill under skills/ and show which needs work"
  - "Why can't this skill be found, audit its description"
  - "Pre-publish check this SKILL.md"
metadata:
  { "openclaw": { "requires": { "bins": ["python3"] }, "os": ["darwin", "linux", "windows"], "emoji": "🩻" } }
---

# 技能体检

一份 SKILL.md 有没有人用，七成取决于**能不能被搜到、Agent 能不能照着做**。这个技能把经验变成可重复的打分。

## 五个维度（各 20 分）
1. **可发现性**：description 写清"什么时候用"（当用户说…时使用）；覆盖用户会用的同义词与触发词；长度 80–600 字；tags 6–12 个中英混合。
2. **结构**：正文有 何时用 / 流程 / 产出（输出契约或验收）/ 边界（禁止、红灯、常见问题）四类小节；篇幅 1500–12000 字符，超出的参考内容拆到 `references/`。
3. **可执行性**：有命令或代码块；`{baseDir}/scripts/...` 引用的文件真实存在。
4. **合规**：frontmatter 有 name（或 SkillHub 的 slug）与 version；没有无扩展名文件（SkillHub 会 400 拒绝）；复刻作品有 `ATTRIBUTION.md`；正文没有密钥样字符串（一票否决）。
5. **示例**：examples_zh/en 各 1–3 条，且与 description 的关键词一致（不一致会误触发）。

## 执行流程

```bash
python3 {baseDir}/scripts/skill_lint.py skills/my-skill            # 单个
python3 {baseDir}/scripts/skill_lint.py skills/* --min 70          # 批量并设及格线（CI 可用）
python3 {baseDir}/scripts/skill_lint.py skills/my-skill --json     # 机器可读
```

输出：总分、五维得分、逐条建议（按影响排序）。然后由你把建议落到文件里：改 description 时先写"什么时候用"，再列同义词；补 examples 时用用户的口吻；缺小节就按本仓库其他技能的骨架补。

## 分数怎么读
- **≥ 85**：可发布。
- **70–84**：改建议里的前三条再发。
- **< 70**：通常是 description 没说清用途、没有流程或没有示例；先补这三样。
- 合规扣到负分：立刻处理（密钥、无扩展名文件）。

## 不做什么
不评判内容是否正确（那是评审的事），不替你改文件（改动要过你的眼）。分数是启发式，平台的 AI 评分口径不公开，两者相关但不等同。

---
本技能与脚本开源：https://github.com/po-et/workbuddy-skills
