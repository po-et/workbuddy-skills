# 示例：英文三分钟立论的词数与计时

这是备赛演示，不是真实用户案例。辩题为“Universities should publish clear deadlines for student funding applications”，持方正方；时限三分钟，假设已按同口径实测 150 词/分钟。下面只有逻辑论证和假设场景，没有调查、学校政策或统计数字。

把代码块正文单独存成 `english.txt`，不要把说明一起计时。

```text
【Constructive speech】
Thank you, chair. Our side supports the motion that universities should publish clear deadlines for student funding applications. By a clear deadline, we mean a date announced before applications open, visible in the same place as the application requirements. We do not mean a promise that every application will succeed.

Our criterion is whether the application process gives students a fair opportunity to prepare. A fair process should reward the quality of an application, rather than a student's ability to discover an unwritten rule.

First, a visible deadline makes planning possible. Imagine two students preparing the same application. One hears about a closing date from a friend; the other receives no such message. Their different outcomes would say little about the merits of their applications. Publishing the date removes that avoidable difference.

Second, a clear deadline makes the process easier to check. If an application is rejected for being late, both the student and the administrator can refer to the same published date. This does not settle every dispute, but it gives both sides a common starting point.

The opposition may argue that emergencies require flexibility. We agree that exceptions can be necessary. The answer is to publish an exception procedure alongside the deadline, rather than leave everyone guessing. A visible rule and a stated exception can work together.

Therefore, our proposal does not guarantee funding or eliminate every difficulty. It makes preparation and explanation more transparent. Under the criterion of a fair opportunity to prepare, publishing clear deadlines is the better choice. Thank you.
```

运行：

```bash
python3 scripts/speech_timer.py english.txt 150 --language en --limit 3:00
```

实际脚本输出（节选，演示文本）：

```text
全文 255 词，约 1 分 42 秒
时限 3 分 00 秒：上限 450 词，写到九成是 405 词
  → 在九成线以内，余量约 1 分 18 秒
```

`--language en` 把英文词速和中文等效字速分开。脚本估算后仍要实读核对停顿；“对方可能认为”的段落是赛前预判，结辩时必须替换成对方实际论点，不能当成对方已经说过的话。
