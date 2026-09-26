# 示例：封面、竖屏截图与 GIF

> 以下为示例。`demo.mp4`、`vertical.mp4` 是用 ffmpeg 自带测试图案生成的样片（后者只加了 90 度旋转元数据，模拟手机竖拍）；所有输出都是实际运行 `scripts/frames.py`（ffmpeg 9.0.1）的结果，绝对路径截短为 `…/`。

## 1. 指定时间点做封面

**用户**：帮我截第 12.5 秒那一帧做封面。

```bash
python3 scripts/frames.py shot demo.mp4 --at 0:12.5 --out cover.jpg
```

```text
执行：ffmpeg -hide_banner -nostats -n -ss 0:12.5 -i demo.mp4 -frames:v 1 -q:v 2 …/cover.jpg

输出：…/cover.jpg（640x360）；时间点 0:12.5（12.500 秒）
```

再跑一次同样的命令，脚本会先停下，而不是让 ffmpeg 悄悄放弃（ffmpeg 遇到同名文件放弃时退出码也是 0）：

```text
…/cover.jpg 已存在。ffmpeg 遇到同名文件会直接放弃且返回 0，所以先停下：换个 --out，或加 --overwrite。
```

退出码 2。时间点写错时也会先报错，不会跑出一张空图：

```text
视频只有 32.00 秒，--at 0:40 超出范围
```

退出码 1。

## 2. 不知道哪一帧好看：让 ffmpeg 挑

```bash
python3 scripts/frames.py pick demo.mp4 --start 8 --duration 8 --out cover_pick.jpg
```

```text
执行：ffmpeg -hide_banner -nostats -n -ss 8 -t 8 -i demo.mp4 -vf fps=2,thumbnail=16 -frames:v 1 -q:v 2 …/cover_pick.jpg

输出：…/cover_pick.jpg（640x360）；从 8 秒起 8 秒内按每秒 2 帧取 16 帧，挑最有代表性的一张
```

## 3. 竖拍视频

```bash
python3 scripts/frames.py probe vertical.mp4
python3 scripts/frames.py shot vertical.mp4 --at 3 --out vertical_cover.jpg
```

```text
时长 32.000 秒；帧率 25.000；存储宽高 640x360；旋转 90；实际画面 360x640；像素格式 yuv420p；帧数 800
提示：竖拍视频。ffmpeg 默认自动转正；缩放只定一边（如 scale=-2:720），不要写死宽高，也别加 -noautorotate。
执行：ffmpeg -hide_banner -nostats -n -ss 3 -i vertical.mp4 -frames:v 1 -q:v 2 …/vertical_cover.jpg

输出：…/vertical_cover.jpg（360x640）；时间点 3（3.000 秒）
```

ffprobe 报的存储宽高是 640x360，截出来的图却是 360x640——这就是「宽高要对调」的意思。需要缩放时写 `scale=-2:720`（实测得到 406x720），不要写死 `scale=1280:720`。

## 4. 第 10 到 13 秒转 GIF

**用户**：把第 10 到 13 秒做成动图，别太大。

```bash
python3 scripts/frames.py gif demo.mp4 --start 10 --duration 3 --out clip.gif
```

```text
执行：ffmpeg -hide_banner -nostats -ss 10 -t 3 -i demo.mp4 -y -vf fps=12,scale=480:-1:flags=lanczos,palettegen=stats_mode=diff …/palette.png
执行：ffmpeg -hide_banner -nostats -ss 10 -t 3 -i demo.mp4 -i …/palette.png -lavfi 'fps=12,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5' -n …/clip.gif

输出：…/clip.gif（480x270，12 KB）
太大就按这个顺序减：缩短 --duration → --fps 8 到 10 → --width 320 → --dither none
```

（调色板写在系统临时目录，用完自动删除；上面把临时路径也截短了。）

按提示减一档帧率和宽度：

```bash
python3 scripts/frames.py gif demo.mp4 --start 10 --duration 3 --fps 8 --width 320 --out clip_small.gif
```

```text
输出：…/clip_small.gif（320x180，9 KB）
```

样片画面简单，所以文件很小；真实录屏会大得多，按同样的顺序往下减即可。

## 5. 助手交付（按输出契约的顺序）

```text
1 命令：见上面各段「执行：」
2 输出：…/cover.jpg（640x360）、…/cover_pick.jpg（640x360）、…/vertical_cover.jpg（360x640）、
        …/clip.gif（480x270，12 KB）、…/clip_small.gif（320x180，9 KB）
3 时间点：cover 12.5 秒；cover_pick 在 8–16 秒内挑选；GIF 为 10–13 秒
4 对照表：单张不需要
5 异常：无；竖拍视频已自动转正
```
