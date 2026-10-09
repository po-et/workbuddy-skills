# 先用一个技能完成一件事

选一个你正在做的任务，给 WorkBuddy 可公开的样本或本机文件路径。安装时保留 `--namespace indiv-captain`，确保拿到本仓库维护的版本。

在 WorkBuddy 里，可以直接复制下方任务并让它调用已安装的技能。手动安装需本机已有 SkillHub CLI；下方脚本命令按本仓库的根目录写，使用安装包时请按实际位置调整脚本路径。

| 当前任务 | 技能与安装命令 | 可以检查的结果 |
|---|---|---|
| 周报全是数字，看不出重点 | [报表制作](https://skillhub.cn/skills/@indiv-captain/report-making)：`skillhub install report-making --namespace indiv-captain` | 指标口径、缺失数据说明、异常标注、一页报表 |
| 三分钟辩论稿总是超时 | [辩论稿](https://skillhub.cn/skills/@indiv-captain/debate-speech)：`skillhub install debate-speech --namespace indiv-captain` | 立论稿、攻辩链、字数与时间估算；以自己的朗读计时为准 |
| 录屏太长，想用少量画面复盘 | [视频抽帧](https://skillhub.cn/skills/@indiv-captain/video-frame-extract)：`skillhub install video-frame-extract --namespace indiv-captain` | 截图、时间点对照表、联系表；原视频保持不变 |
| 多个 Excel 明细列顺序不同 | [Excel 处理](https://skillhub.cn/skills/@indiv-captain/excel-processing)：`skillhub install excel-processing --namespace indiv-captain` | 按表头对齐的合并表、来源行、运行摘要；原件只读、结果防覆盖 |
| 买车报价说不清总成本 | [买车](https://skillhub.cn/skills/@indiv-captain/car-buying-checklist)：`skillhub install car-buying-checklist --namespace indiv-captain` | 用户提供费用的预算表，缺项留待补，政策口径待核实 |

## 可以直接复制的任务

**业务报表**

> 用报表制作处理我提供的销售汇总 CSV。读者是销售负责人，问题是下周资源应该投向哪个区域。先体检，再按我给的20%变化阈值和绝对变化10标注；缺失不补零，原因未确认写待查，最后给一页报表。

先在本机验证工具：

```bash
python3 skills/report-making/scripts/csv_profile.py 我的汇总.csv --key 区域,周
python3 skills/report-making/scripts/anomaly_flag.py 我的汇总.csv --period 周 --value 销售额 --by 区域 --pct 20 --min-abs 10 --out 汇总_标注.csv
```

列名按你实际表头填写，阈值由业务问题决定。脚本提供标注，异常原因需要你核实。[完整示例](../skills/report-making/examples/monthly-report-region-channel.md)使用演示数据；示例不代表真实客户案例。

**辩论准备**

> 使用辩论稿帮我准备正方一辩。辩题是“校园活动应优先广泛参与还是精品质量”，时限三分钟。我倾向广泛参与。请先明确判断标准，给两条可质询的论证和攻辩链，再检查稿长；没有来源的数字不要补。

**会议录屏素材**

> 使用视频抽帧处理我有权使用的本机录屏，抽12张均匀画面并生成联系表，每张保留时间点。图片用于我自己整理会议复盘，不上传或发送。提取后核对原视频未改动。

需要本机已有 `ffmpeg` 和 `ffprobe`。[视频技能说明](../skills/video-frame-extract/SKILL.md)包含具体命令。画面和时间点能辅助复盘，不能代替音频转写或自动证明会议决议。

**Excel 明细合并**

> 使用 Excel 处理合并我提供的两个 .xlsx，工作表都叫“明细”。列顺序不同，请按表头对齐并保留来源行。原件只读，保存到新的结果文件；发现公式先停止并让我选择处理方式，缺字段或重复表头就报错。

```bash
python3 skills/excel-processing/scripts/merge_xlsx.py east.xlsx west.xlsx --sheet 明细 --out combined.xlsx
```

需要已有 `openpyxl`。默认拒绝公式；选择读取已有缓存时也会检查缓存缺失。[完整合成示例](../skills/excel-processing/examples/header-aligned-merge.md)可先复跑，不代表真实业务使用。

## 用完后反馈一件具体的事

有帮助、失败、需要改进都可以通过[技能反馈入口](https://github.com/po-et/workbuddy-skills/issues/new?template=skill-feedback.md)提交：技能slug与版本、要完成的任务、可公开的最小输入、实际结果和期望结果。如果愿意记录用时，请写实际测量，不必估一个节省比例。

收藏表示你愿意以后再用；是否解决了任务，需要实际输入与结果来确认。这里提供试用入口，没有预先计入真实用户或成功案例。
