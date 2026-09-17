---
name: to-questionnaire-zh
description: 把自己答不了的决策变成一份给别人填的问卷、异步收集信息、向领域专家或上游团队提问、需求澄清问卷、访谈提纲、调研问卷、会前问题清单。当用户说「这个我自己定不了，得问 XX」「帮我列一份要问产品/后端/运维的问题」「做一份问卷让对方填」「写个访谈提纲」时使用。核心：只拷问「发送」本身（发给谁、要拿回什么），不拷问用户答不了的主题；问题瞄准「对方知道而用户不知道」的缺口；最重要的问题放最前（异步可能只有一轮）；每题一个意思、带答案占位，必要时一行「为什么问」；输出 to-questionnaire-<slug>.md。改编自 Matt Pocock 的 to-questionnaire（MIT）。
author: Captain
version: 0.1.0
display_name: "决策问卷生成"
display_name_en: "To Questionnaire (zh)"
description_zh: "把用户独自答不了的决策变成一份 Markdown 问卷，交给掌握信息的那个人异步填写或开会一起过：先问清发给谁、要拿回什么，再把问题对准双方的信息差。"
description_en: "Turn a decision the user can't answer alone into a Markdown questionnaire for the person who holds the knowledge, to fill in async or walk through in a meeting: settle who it goes to and what must come back, then aim questions at the gap."
examples_zh:
  - "这个接口的限流策略我定不了，得问网关团队，帮我列问题"
  - "做一份问卷给客户成功经理填，我想知道客户实际怎么用导出功能"
  - "明天和 DBA 开会，帮我准备要问的问题"
examples_en:
  - "I can't decide the rate-limit policy, help me ask the gateway team"
  - "Make a questionnaire for the CSM about how customers use export"
  - "Meeting the DBA tomorrow, prep my questions"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "📋" } }
---

# 决策问卷生成

把用户独自答不了的事变成一份**问卷**：一份 Markdown 文档，交给一个人异步填写，或在会上一起过。收件人掌握用户缺的知识，问卷负责把它掏出来。

**拷问「发送」，不拷问「主题」。** 只就*发送*本身采访用户——这他总能答：发给谁、要拿回什么。文档里的问题则对准**收件人知道的**与**用户需要的**之间的缺口。

1. **发给谁？** 一次交流问清收件人的角色、专长、与用户的关系。这决定问卷的语气和要带多少背景。知道了收件人是谁、他知道什么用户不知道的，这一步就完成。
2. **要拿回什么？** 一次交流问清用户自己解决不了、需要此人给出的具体决策或事实。得到一份「用户拿到答案后必须能做/能决定的事」清单，这一步就完成。
3. **写问卷。** 按下方文档结构，围绕第 1–2 步的缺口拟题。写到当前目录的 `to-questionnaire-<slug>.md`（slug 取自主题），报告路径。文件存在、且第 2 步用户点名的每一项都有对应问题，这一步就完成。

## 文档结构

把文档定位为**发现型问卷**：用户缺上下文，收件人有。问题按重要性从高到低排——异步可能只有一轮机会；超过几个问题就按主题分 `##` 小节。按下面的模板写。

```
# <问卷标题>

**目的：** 这份问卷为什么存在、背后压着什么决策。

**发件人：** <用户>　**收件人：** <收件人>　**答案用途：** <会用到哪里>

## 背景

一段话，让不在用户脑子里的收件人能进入状态。够答好即可，不写一页。

## 怎么答

截止时间和大致工作量。部分回答和「不知道」都有用：拿不准的标出来，别跳过。

## <主题小节>

每个主题一个 `##`。下面是该主题的问题，重要的在前。每题只问一件事，不复合；题下直接放答案占位；只在可能被误读或容易敷衍的题目下加一行「为什么问」。

### 系统上线时预期承载多大负载？

_为什么问：决定我们现在就为突发流量做容量，还是往后推。_

>

## 还有什么？

收尾兜底：有没有我们没问但你觉得该知道的？
```

## 写题的手感

- 「你们的服务能扛多少 QPS？」比「性能怎么样？」好：前者有数、后者只能得到形容词。
- 复合题拆开：「用不用 Kafka、分几个分区」是两题。
- 让对方能用「不知道」交卷：问卷是发现工具，不是考试。

---
改编自 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `to-questionnaire`（MIT）。改动见 ATTRIBUTION.md。
