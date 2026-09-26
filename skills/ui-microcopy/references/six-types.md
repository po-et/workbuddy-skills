# 六类文案：模板、中英对照与反例

回到 [SKILL.md](../SKILL.md)。事实（上限、天数、能否恢复）从产品规则取，拿不到写【待确认】；[ ] 表示按钮。

## 按钮

```
正例  保存草稿 Save draft  发送邀请 Send invite  删除项目 Delete project
反例  删除弹窗里的「确定 OK」  其实是付款的「提交 Submit」  「点击这里 Click here」
```

## 空状态

```
首次使用  还没有项目。新建一个，邀请同事一起编辑。[新建项目]
          No projects yet. Create one and invite your team to edit it together. [New project]
搜索无果  没有找到与「季度报表」相关的文件。试试更短的关键词，或检查拼写。
          No files match "quarterly report". Try a shorter keyword or check the spelling.
反例      暂无数据 / No data    ← 没说为什么，也没给出路
```

## 错误提示

```
模板  发生了什么 +（能说的话）为什么 + 怎么办；用户已填的内容保留
正例  文件超过 20 MB，无法上传。压缩后重试，或拆成几个小文件。
      This file is larger than 20 MB. Compress it or split it into smaller files, then try again.
字段  请输入 11 位手机号 / Enter an 11-digit phone number  ← 说正确格式，贴在出错的字段旁
反例  上传失败（错误码 413）/ Error 413     输入非法 / Invalid input     系统异常，请稍后再试
```

## 确认弹窗

```
标题  删除「年度预算」？ / Delete "Annual budget"?
正文  表内 12 个工作表会一起删除，30 天内可在回收站恢复。【天数按产品规则填】
      All 12 sheets will be deleted. You can restore them from Trash within 30 days.
按钮  [删除] [取消] / [Delete] [Cancel]          ← 主按钮重复标题里的动词
反例  确定要执行此操作吗？[确定][取消] / Are you sure? [OK] [Cancel]
```

能撤销的操作不弹确认，直接执行并给「撤销 / Undo」；确认弹窗留给不可逆、或会影响别人的动作。

## 加载与成功反馈

```
加载  1 秒内不提示；1–10 秒写正在做什么「正在导入… / Importing…」；超过 10 秒给进度，并允许取消或先离开：
      正在导入 3/12 个文件，完成后会通知你。 / Importing 3 of 12 files. We'll notify you when it's done.
成功  已发送给小王，可在「已发送」中查看。 / Sent to Xiao Wang. You can find it in Sent.
反例  操作成功！/ Success!        ← 没说成了什么、结果在哪
```

1 秒、10 秒取自 Jakob Nielsen 总结的响应时间经验值，团队有规范按规范。勾选、切换开关这类显而易见的操作不弹成功提示，界面状态的变化本身就是反馈。

## 表单标签与占位符

```
标签    手机号 / Phone number                        ← 名词短语，始终可见
占位符  例：138 0000 0000 / e.g., 138 0000 0000      ← 只放格式示例，一输入就消失，不能代替标签
说明    仅用于接收验证码，不会公开 / Only used for verification codes. Never shown publicly.
必填    只标少数的那一类：多数字段必填时，只给少数标「选填 / Optional」
反例    标签写成「请输入您的手机号码」；格式要求只写在占位符里
```
