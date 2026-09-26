# 示例：约美国供应商开视频会，时区写清楚

回到 [SKILL.md](../SKILL.md)。以下为虚构场景，公司、人名均为演示；邮箱域名只用 example.com。

## 用户原话

> 想约美国供应商开个视频会，帮我写邀约并把时区写清楚。

## 助手的澄清问题（一次三个）

1. 对方在哪个城市（决定时区）？怎么称呼？
2. 会议聊什么、大概多长？
3. 你方便的时间段（北京时间）？

用户补充：对方是芝加哥的 Mark Davis（邮箱 mark.davis@example.com），第一次开会；聊试产计划，30 分钟；我晚上 9 点到 11 点都可以，下周二或周三（10 月 13、14 日）。

## 换算时间（不心算）

```bash
python3 -c "from datetime import datetime as D; from zoneinfo import ZoneInfo as Z; [print(D(2026,10,d,h,0,tzinfo=Z('America/Chicago')).astimezone(Z('Asia/Shanghai'))) for d,h in ((13,9),(14,8))]"
```

输出 `2026-10-13 22:00:00+08:00` 与 `2026-10-14 21:00:00+08:00`：芝加哥周二上午 9 点 = 北京周二晚 10 点；周三上午 8 点 = 北京周三晚 9 点，都落在用户方便的时段。注意：美国夏令时结束后（按 zoneinfo 计算，2026 年是 11 月 1 日），同样的芝加哥时间对应的北京时间会晚一小时，改期到那之后要重新换算。

## 最终交付

```text
状态：签名 2 处 [待补]，补齐即可发送

Subject: Meeting request: 30-min call on the pilot production plan

Dear Mr. Davis,

I'd like to set up a 30-minute video call to walk through our pilot production plan and agree on the next steps.

Would either of these times work for you?
1. Tue 13 Oct, 9:00–9:30 am Chicago time (10:00–10:30 pm Beijing time)
2. Wed 14 Oct, 8:00–8:30 am Chicago time (9:00–9:30 pm Beijing time)

Once you confirm, I'll send a calendar invite with the video link. If neither slot suits you, please suggest a time that does.

Best regards,
[待补：你的姓名]
[待补：职位 | 公司 | 带国家区号的电话]

需要你确认的点：第一次联系、对方是供应商，称呼用了 Mr. Davis（姓）；如果你们已经互称名字，可改成 Hi Mark。
```

## 这个示例对应的自检

- 第一段说清目的和时长：是。
- 每个候选时间都带两边的城市时间：是。
- 期限：会议邀约没有硬期限，用「Once you confirm」给出下一步：是。
- 跑脚本：`python3 scripts/email_check.py draft.txt` 退出码 3，只有签名处 2 个 [待补]（按设计会报出来，补齐后为 0）。
