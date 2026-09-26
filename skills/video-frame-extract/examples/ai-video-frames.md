# 示例：给 AI 看视频——均分、拼图与场景抽帧

> 以下为示例。`demo.mp4` 是用 ffmpeg 自带测试图案生成的 32 秒样片（4 段不同画面，每段 8 秒，每 2 秒一个关键帧）；所有输出都是实际运行 `scripts/frames.py`（ffmpeg 9.0.1）的结果，绝对路径截短为 `…/`。

## 1. 用户提问

> 每隔 5 秒截一张，我想让 AI 看看这个视频讲了什么。（附 demo.mp4）

## 2. 先看参数

```bash
python3 scripts/frames.py probe demo.mp4
```

```text
时长 32.000 秒；帧率 25.000；存储宽高 640x360；旋转 0；实际画面 640x360；像素格式 yuv420p；帧数 800
```

助手的判断：32 秒每 5 秒一张只有 7 张，低于给 AI 看建议的 8–16 张；改成按总时长均分 12 张，宽 768 [待确认：一定要每 5 秒就改用 `--every 5`]。

## 3. 均分 12 张

```bash
python3 scripts/frames.py interval demo.mp4 --count 12 --out-dir ai_frames
```

```text
执行：ffmpeg -hide_banner -nostats -n -i demo.mp4 -vf fps=1/2.6667:round=up,scale=768:-2,showinfo -start_number 0 -frames:v 12 -q:v 2 …/ai_frames/f_%04d.jpg

共 12 张，分辨率 768x432，目录：…/ai_frames
对照表：…/ai_frames/index.csv

| 文件 | 时间点（秒） | 时间码 |
|---|---|---|
| f_0000.jpg | 0.000 | 00:00:00.000 |
| f_0001.jpg | 2.667 | 00:00:02.667 |
| f_0002.jpg | 5.333 | 00:00:05.333 |
| f_0003.jpg | 8.000 | 00:00:08.000 |
| f_0004.jpg | 10.667 | 00:00:10.667 |
| f_0005.jpg | 13.334 | 00:00:13.334 |
| f_0006.jpg | 16.000 | 00:00:16.000 |
| f_0007.jpg | 18.667 | 00:00:18.667 |
| f_0008.jpg | 21.334 | 00:00:21.334 |
| f_0009.jpg | 24.000 | 00:00:24.000 |
| f_0010.jpg | 26.667 | 00:00:26.667 |
| f_0011.jpg | 29.334 | 00:00:29.334 |
```

说明：表里是每隔约 2.67 秒的时刻；`round=up` 取的是该时刻或之前最近的一帧，这个 25 帧/秒的样片最多早 0.04 秒（用逐帧校验和比对过：标 2.667 秒的那张，实际是 2.64 秒的画面）。

## 4. 想少传几张图：一张 4×3 拼图

```bash
python3 scripts/frames.py sheet demo.mp4 --out ai_sheet.jpg
```

```text
执行：ffmpeg -hide_banner -nostats -n -i demo.mp4 -vf fps=12/32,scale=320:-2,tile=4x3:padding=4:margin=4 -frames:v 1 -q:v 3 …/ai_sheet.jpg

输出：…/ai_sheet.jpg（1300x556）；按总时长均分 12 张，4×3 拼成一张
```

## 5. 镜头切换多：按场景抽

```bash
python3 scripts/frames.py scene demo.mp4 --out-dir shots
```

```text
执行：ffmpeg -hide_banner -nostats -n -i demo.mp4 -vf 'select=eq(n\,0)+gt(scene\,0.3),showinfo' -fps_mode vfr -q:v 2 …/shots/s_%04d.jpg

共 4 张，分辨率 640x360，目录：…/shots
对照表：…/shots/index.csv

| 文件 | 时间点（秒） | 时间码 |
|---|---|---|
| s_0001.jpg | 0.000 | 00:00:00.000 |
| s_0002.jpg | 8.000 | 00:00:08.000 |
| s_0003.jpg | 16.000 | 00:00:16.000 |
| s_0004.jpg | 24.000 | 00:00:24.000 |
```

4 张正好对应样片的 4 段画面，每段开头一张。

## 6. 助手交付（按输出契约的顺序）

```text
1 命令：见上面三段「执行：」
2 输出：…/ai_frames（12 张，768x432）；…/ai_sheet.jpg（1300x556）；…/shots（4 张，640x360）
3 时间点：ai_frames 每隔约 2.67 秒（实际画面最多早一帧）；shots 为 showinfo 的 pts_time：0、8、16、24 秒
4 对照表：ai_frames/index.csv、shots/index.csv（传给 AI 时把表一起贴上）
5 异常：无；每 5 秒一张只有 7 张，已按用途改为均分 12 张 [待确认]
```

## 7. 这个示例说明了什么

- 先 probe 再定张数：用途决定参数，不照搬用户随口说的间隔，但改动要标 [待确认]。
- 时间点来自 ffmpeg 自己打印的 pts_time，不靠估算；精度写清楚（最多早一帧）。
- 三种抽法各有用处：均分给 AI 看全貌，拼图省张数，场景抽帧按镜头切分。
