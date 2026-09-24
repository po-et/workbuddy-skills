---
name: video-frame-extract
description: "视频抽帧——用 ffmpeg 从视频里按时间点截图、每隔 N 秒抽一张、只抽关键帧或按场景变化抽帧，还能拼缩略图、转 GIF。当用户说「视频截图」「每隔几秒截一张」「抽关键帧」「做视频封面」「视频转GIF」「让AI看视频」时使用。"
author: Captain
version: 0.1.0
display_name: "视频抽帧"
display_name_en: "Video Frame Extract"
description_zh: "用 ffmpeg/ffprobe 从视频里截图与抽帧：先看时长、帧率、分辨率与旋转，再按时间点、固定间隔、关键帧、场景变化抽取，拼缩略图、用调色板两步法转 GIF；讲清 -ss 位置、每 N 秒取哪一帧、竖屏旋转、文件编号这些常见坑。"
description_en: "Extract stills and frame sequences from video with ffmpeg: single timestamps, fixed intervals, keyframes, scene changes, contact sheets and palette-based GIFs, with seeking, rotation and file-numbering pitfalls covered."
tags:
  - "视频抽帧"
  - "视频截图"
  - "ffmpeg"
  - "关键帧"
  - "缩略图"
  - "视频转GIF"
  - "视频封面"
  - "frame extraction"
examples_zh:
  - "帮我给这段视频截图，要第 1 分 23 秒那一帧做封面"
  - "每隔 5 秒截一张，我想让AI看视频讲了什么"
  - "把录屏第 10 到 13 秒做成动图，视频转GIF 别太大"
---

# 视频抽帧

适用于从视频里拿静态画面：做封面、截素材、给 AI 看内容、做动图。全部用 ffmpeg/ffprobe 完成，命令按 macOS/Linux 终端写，`in.mp4` 换成你的文件名。先跑 `ffmpeg -version` 确认已安装；没装请用户自己从官方渠道安装。

## 先判断什么

| 用户要的 | 抽法 | 关键参数 |
|---|---|---|
| 某一刻的画面、封面 | 时间点截图 | `-ss` 放在 `-i` 前 |
| 不知道哪帧好看的封面 | 让 ffmpeg 挑代表帧 | `thumbnail` |
| 均匀素材、给 AI 看 | 每 N 秒一张 | `fps=1/N:round=up` |
| 快速过一遍长视频 | 只抽关键帧 | `-skip_frame nokey` |
| 按镜头切分、录屏翻页 | 场景变化抽帧 | `gt(scene,0.3)` |
| 一张图看全片 | 缩略图拼图 | `tile` |
| 动图 | 调色板两步法 | `palettegen` + `paletteuse` |

给 AI 看视频：总数控制在 8–16 张，宽度缩到 768 左右，每张都附上时间点；镜头切换多的内容改用场景抽帧；想少传几张图，就交一张 4×3 拼图。

## 第 1 步：先看视频参数

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,nb_frames:stream_side_data=rotation:format=duration -of default=nw=1 in.mp4
```

看四样：`duration`（总秒数，决定间隔）、`r_frame_rate`（帧率）、`width/height`（存储宽高）、`rotation`（出现 90 或 -90 说明是竖拍，实际画面宽高要对调）。

## 第 2 步：按用途抽（均在 ffmpeg 9.0 实测）

```bash
# 单张：第 1 分 23.5 秒；-q:v 2 是 JPG 高质量（2 最好、31 最差），要无损就把输出改成 .png
ffmpeg -ss 00:01:23.5 -i in.mp4 -frames:v 1 -q:v 2 cover.jpg
# 封面候选：第 60–80 秒每秒取 2 帧共 40 帧，挑最有代表性的一张，通常能避开黑场和转场
# （thumbnail 会把整批帧放进内存：实测 720p 直接挑 500 帧，ffmpeg 占 812 MB；先降帧只占 144 MB）
ffmpeg -ss 60 -t 20 -i in.mp4 -vf "fps=2,thumbnail=40" -frames:v 1 cover_pick.jpg
# 每 5 秒一张并缩到 768 宽，编号从 0 起：第 k 张 = 第 k×5 秒
mkdir -p frames && ffmpeg -i in.mp4 -vf "fps=1/5:round=up,scale=768:-2" -start_number 0 -q:v 2 frames/f_%04d.jpg
# 只要关键帧：先列时间点，再抽图（解码器直接跳过非关键帧，长视频最快）
ffprobe -v error -select_streams v:0 -skip_frame nokey -show_entries frame=pts_time -of default=nw=1:nk=1 in.mp4
mkdir -p key && ffmpeg -skip_frame nokey -i in.mp4 -fps_mode vfr -q:v 2 key/k_%04d.jpg
# 场景变化：连第一帧一起抽，并打印每张的秒数；抽太多就把 0.3 调到 0.4–0.5
mkdir -p scene && ffmpeg -i in.mp4 -vf "select='eq(n,0)+gt(scene,0.3)',showinfo" -fps_mode vfr -q:v 2 scene/s_%03d.jpg 2>&1 | grep -o 'pts_time:[0-9.]*'
# 4×3 缩略图拼图：按总时长均分 12 张
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 in.mp4)
ffmpeg -i in.mp4 -vf "fps=12/$D,scale=320:-2,tile=4x3:padding=4:margin=4" -frames:v 1 -q:v 3 sheet.jpg
```

转 GIF 分两步：先为这一段画面生成专属 256 色调色板，再按它上色。一步直转用的是通用色表，真实画面容易出现色带和噪点。

```bash
ffmpeg -ss 10 -t 3 -i in.mp4 -vf "fps=12,scale=480:-1:flags=lanczos,palettegen=stats_mode=diff" palette.png
ffmpeg -ss 10 -t 3 -i in.mp4 -i palette.png -lavfi "fps=12,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" out.gif
```

GIF 太大按这个顺序减：缩短时长 → 降到 8–10 帧/秒 → 宽度降到 320 → 改 `dither=none`。

## 最常见的坑

1. **`-ss` 放哪**：放在 `-i` 前，先跳到附近关键帧再解码到准确位置，又快又准。实测 10 分钟视频取第 512.36 秒：放前 0.04 秒、放后 0.42 秒，两张画面逐像素一致；越靠后差距越大。老教程说「放前面不准」，说的是不解码的 `-c copy` 剪片（只能从关键帧起拷数据），截图不受影响。
2. **每 N 秒取的不是整点**：`fps=1/5` 默认取每段中间那帧，实测第 1、2 张在 2.48、7.48 秒；加 `:round=up` 才正好是 0、5、10 秒，文件名才能和时间对上。
3. **竖屏旋转**：手机竖拍常以横向存储、靠 rotation 元数据竖过来。ffmpeg 默认自动转正，截图是竖的，但 ffprobe 报的 width/height 仍是横向数值。缩放别写死 `scale=1280:720`（竖片会被压扁），用 `scale=-2:720` 只定一边；别加 `-noautorotate`，否则画面是躺着的。
4. **文件名与编号**：抽多张必须写 `%04d` 这类编号模板，写成 `out.jpg` 会报 `Cannot write more than one file with the same name`；编号默认从 1 开始，`-start_number 0` 改成从 0；补零到四位才能按文件名正确排序；输出目录不存在会报 `No such file or directory`，先 `mkdir -p`。
5. **覆盖**：同名文件已存在时，非交互环境下 ffmpeg 直接放弃（Not overwriting - exiting）；批量重跑加 `-y` 覆盖或 `-n` 跳过，先想清楚要哪个。

## 输出契约

交付四样：① 实际执行的完整命令；② 输出清单（路径、张数、分辨率，用 `ls` 和 ffprobe 核对，不凭估算）；③ 每张的时间点（固定间隔按 k×N 秒算，场景抽帧取 showinfo 打印的 pts_time）；④ 给 AI 用时附「文件名—时间点」对照表。张数与预期差得多（例如场景抽帧只出 1 张），先说明原因和调整办法再重跑。

## 边界与不做什么

- 只处理用户有权使用的视频；不帮忙绕过 DRM、翻录付费课程或影视内容再传播；截图要公开发布时，提醒注意版权与肖像权。
- 不做人脸识别、身份辨认或跟踪他人；画面里有证件、聊天记录等隐私信息，提醒先打码。
- 只负责抽帧与做动图；剪辑、配字幕、整片转码不在本技能范围。
- 不代装软件；HDR、10-bit 视频截图可能发灰，需要色调映射时如实说明，不给未经验证的参数。
