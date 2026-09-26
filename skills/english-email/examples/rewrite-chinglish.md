# 示例：中文直译稿改成地道英文

回到 [SKILL.md](../SKILL.md)。以下为虚构场景，人名、价格均为演示。

## 用户原话

> 这封英文邮件是我从中文直译的，帮我看看有没有中式英语。对方是合作两年的采购 John，美国人，我们平时叫他 John。

```text
Subject: Hello

Dear Mr. John,

Please kindly noted that we have updated our price list. Last time you said the price is too expensive, so we discussed about it and decided to reduce 5%. The new price list is attached.
If any question, please contact with me ASAP. Hope you can understand.

Best regards,
Li Ming
```

## 助手的澄清问题

只问了一个：「降价从哪天开始生效？」——用户答「6 月 1 日」。其余信息都在原稿里，不再追问。

## 先跑自查脚本（真实输出）

```text
$ python3 scripts/email_check.py draft.txt
检查 draft.txt：问题 8 处，提醒 1 处
L1    [问题] 主题行「Hello」→ 主题只写了问候语：写「类型 + 对象 + 期限或状态」
L5    [问题] 中式英语#1「Please kindly」→ Please confirm … / Could you confirm …?（please 和 kindly 叠用，读着生硬）
L5    [问题] 中式英语#2「Please kindly noted」→ Please note that …（please 后面接动词原形）
L5    [问题] 中式英语#3「discussed about」→ discuss the plan（discuss 直接带宾语）
L5    [问题] 中式英语#6「price is too expensive」→ The price is too high.（price 说高低，不说贵）
L6    [问题] 中式英语#4「contact with」→ contact me（contact 作动词不加 with）
L6    [问题] 中式英语#9「Hope you can understand」→ Thank you for your understanding.（原句听着像「你该理解」）
L6    [问题] 没写期限「ASAP」→ 写成具体日期，如 by Friday, 15 May
L5    [提醒] 附件「attached」→ 正文提到附件：发送前确认真的附上了
命中不等于一定错：逐条对照 references/chinglish-10.md 判断。
第 7 条（Mr./Ms. 后面接的是姓还是名）脚本判断不了，请人工看称呼。
```

退出码 3：有 8 处要人工看。第 7 条人工判断：John 是名，平时直呼其名，改成 Dear John。

## 最终交付

```text
状态：可直接发送（附件：新价目表，发送前确认已附上）

Subject: Updated price list: 5% lower from 1 June

Dear John,

We have updated our price list: prices will be 5% lower from 1 June. The new list is attached.

We made this change after reviewing your feedback that our previous prices were too high.

If you have any questions, please let me know.

Best regards,
Li Ming
```

改动清单：

| # | 原文 | 改成 | 为什么 |
|---|---|---|---|
| 1 | Subject: Hello | Updated price list: 5% lower from 1 June | 主题行写类型 + 对象 + 状态，对方不点开也知道是降价 |
| 2 | Dear Mr. John | Dear John | Mr. 后面接姓；你们平时直呼其名 |
| 3 | Please kindly noted that … | 删掉，直接说事 | 第 1、2 条；第一句就说目的 |
| 4 | the price is too expensive | our previous prices were too high | 第 6 条；price 说高低 |
| 5 | we discussed about it and decided to reduce 5% | prices will be 5% lower from 1 June | 第 3 条；补上生效日期，对方最关心的是哪天起算 |
| 6 | please contact with me ASAP | If you have any questions, please let me know. | 第 4 条；降价通知不需要对方赶时间回复，ASAP 删掉 |
| 7 | Hope you can understand. | 删掉 | 第 9 条；降价是好消息，不需要请求理解 |

改完再跑一次脚本：问题 0 处，只剩「记得附上附件」一条提醒，退出码 0。

需要你确认的点：无。
