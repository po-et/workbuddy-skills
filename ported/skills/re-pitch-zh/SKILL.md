---
name: re-pitch-zh
description: 没听懂、重新讲一遍、把上一条回复用大白话再说、简化技术表达、去术语、一句话说清、给非技术同事解释。当用户说「等等我没懂」「你重新讲一下」「说人话」「用大白话解释」「太绕了再来一遍」「刚才那段是什么意思」时使用。规则：先给两三句背景把人带回来；按 ASD-STE100 简化技术英语的精神写中文——短句（≤20 字）、一句一个意思、主动语态、一个概念只用一个词；术语只用项目 CONTEXT.md 里的统一语言（多上下文时按 CONTEXT-MAP.md 找对的那份）；不加新信息，只重讲；结尾用一句话复述结论。改编自 Matt Pocock 的 wait-what（MIT），补充了简化写作的具体规则。
author: Captain
version: 0.1.0
display_name: "没听懂，重讲一遍"
display_name_en: "Wait, What? Re-pitch (zh)"
description_zh: "上一条没讲明白时，用简化技术表达重新讲：先补背景，短句、一句一意、主动语态，只用项目术语表里的词，不加新信息，末尾一句话复述结论。"
description_en: "When the last message didn't land, re-pitch it in simplified technical language: brief context first, short sentences, one idea each, active voice, only glossary terms, no new information, one-line takeaway at the end."
examples_zh:
  - "等等，我没懂你刚才说的，重新讲一下"
  - "说人话，这个方案到底改了什么"
  - "把刚才那段用大白话讲给产品经理听"
examples_en:
  - "Wait, I don't follow. Re-pitch that."
  - "Plain words: what does this change?"
  - "Explain that last part for a PM"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🙋" } }
---

# 没听懂，重讲一遍

上一条回复没有落地。停下来，**重新讲**——不是接着讲。

## 怎么重讲

1. **先带回背景。** 两三句：我们在解决什么、刚才讲到哪。读者可能已经掉线。
2. **用简化技术表达。** 借 ASD-STE100（简化技术英语）的精神写中文：
   - 一句不超过 20 字；一句只说一件事。
   - 主动语态：「网关拒绝了请求」，不是「请求被拒绝了」。
   - 一个概念只用一个词，全程不换说法。
   - 先说结论，再说原因；先说做什么，再说怎么做。
   - 能举一个具体例子就举，不堆抽象。
3. **只用项目的统一语言。** 术语以仓库 `CONTEXT.md` 为准；仓库有多个上下文时，先按 `CONTEXT-MAP.md` 找到对的那份。术语表没有的词，用日常语言解释，不发明新词。
4. **不加新信息。** 重讲的是同一件事。想补充的留到之后。
5. **收尾一句话。** 用一句话复述结论，让读者能直接转述给别人。

## 例子

原话：「鉴于当前的幂等键在重试语义下存在竞态，建议将去重下沉到存储层并结合乐观锁保证一致性。」

重讲：「我们在修重复扣款。现在同一笔请求重试两次，两次都可能成功。原因是去重检查和写入不是一步完成的。我建议把去重放进数据库那一层。数据库用版本号判断：第二次写入发现版本变了，就拒绝。**一句话：让数据库来拦第二次写入，而不是靠应用代码。**」

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `wait-what`（MIT）。改动见 ATTRIBUTION.md。
