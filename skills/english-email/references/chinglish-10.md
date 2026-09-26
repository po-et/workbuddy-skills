# 中式英语最常见的 10 处

回到 [SKILL.md](../SKILL.md)。脚本 `scripts/email_check.py` 的编号与本表一致；第 7 条脚本判断不了，要人工看。

| # | 常见写法 | 改成 |
|---|---|---|
| 1 | Please kindly confirm … | Please confirm … / Could you confirm …? |
| 2 | Please noted that … | Please note that … |
| 3 | discuss about the plan | discuss the plan |
| 4 | contact with me | contact me |
| 5 | open a meeting | hold / have a meeting |
| 6 | The price is too expensive. | The price is too high. |
| 7 | Dear Mr. John（Mr. 加名） | Dear Mr. Smith（Mr. 加姓）或 Dear John |
| 8 | Welcome to contact me. | Feel free to contact me. |
| 9 | Hope you can understand. | Thank you for your understanding.（原句听着像「你该理解」） |
| 10 | I want to know … | Could you let me know …? / I'd like to know … |

## 比用词更伤的是结构

- 请求埋在第三段：把目的挪到第一句。
- 一封塞三件事：拆开，或编号。
- 只写 ASAP 不写日期：写 by Friday, 15 May。
- 约会议不写时区：候选时间带城市或时区。
- 正文说有附件却没附：发送前核对。

## 自查命令

首选脚本（逐条给改法，退出码见 SKILL.md）：

```bash
python3 scripts/email_check.py draft.txt
```

没有 python3 时的替代（只找命中行，不给改法）。命中不等于一定错，逐条对照上表判断：

```bash
grep -n -i -E "please kindly|please noted|discuss about|contact with|open a meeting|too expensive|welcome to contact|hope you can understand|i want to|asap" draft.txt
```
