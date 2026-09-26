---
name: video-frame-extract
description: "视频抽帧——用 ffmpeg 从视频里按时间点截图、每隔 N 秒抽一张、只抽关键帧或按场景变化抽帧，还能拼缩略图、转 GIF。当用户说「视频截图」「每隔几秒截一张」「抽关键帧」「做视频封面」「视频转GIF」「让AI看视频」时使用。"
author: Captain
version: 0.1.1
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
examples_en:
  - "Grab the frame at 1:23 of this video as a cover image"
  - "Take one frame every 5 seconds so an AI can see what the video is about"
  - "Turn seconds 10 to 13 of this screen recording into a GIF that isn't too big"
---

# 视频抽帧

适用于从视频里拿静态画面：做封面、截素材、给 AI 看内容、做动图。全部用 ffmpeg/ffprobe 完成，命令按 macOS/Linux 终端写，`in.mp4` 换成你的文件名。先跑 `ffmpeg -version` 确认已安装；没装请用户自己从官方渠道安装。

## 何时使用

主要场景：

- 「帮我给这段视频截图，要第 1 分 23 秒那一帧做封面」
- 「每隔 5 秒截一张，我想让 AI 看视频讲了什么」
- 「把录屏第 10 到 13 秒做成动图，别太大」
- 「这个视频按镜头切成几张」「给长视频做一张缩略图拼图」

辅助场景（已经在抽，遇到问题）：

- 「截出来的图是躺着的／被压扁了」「抽出来的张数和时间对不上」「ffmpeg 报 Cannot write more than one file」

调用方式：在对话里给出视频路径和用途；在本机终端直接运行下文的 ffmpeg 命令，或用附带脚本 `python3 scripts/frames.py <模式> 视频文件`——同一组命令，外加自动建目录、拒绝悄悄覆盖旧图、核对张数、生成「文件名—时间点」对照表。

不适用（遇到时这样处理）：

- 剪辑、配字幕、整片转码 → 不在本技能范围；只处理声音（提取音轨、剪录音）转「音频剪辑」类技能（如 audio-editing）。
- 绕过 DRM、翻录付费课程或影视内容再传播 → 不做，并说明原因。
- 人脸识别、辨认或跟踪画面里的人 → 不做。

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

看四样：`duration`（总秒数，决定间隔）、`r_frame_rate`（帧率）、`width/height`（存储宽高）、`rotation`（出现 90 或 -90 说明是竖拍，实际画面宽高要对调）。脚本版 `python3 scripts/frames.py probe in.mp4` 会直接算出实际画面宽高，并提示竖拍和 10-bit/HDR。

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

## 一条命令版：scripts/frames.py

`scripts/frames.py` 把上面的命令按模式包好：只用 Python 标准库加 ffmpeg/ffprobe，直接调用程序、不经过 shell（不依赖 `mkdir -p`、`$(...)`、`grep`）；每次都打印实际执行的完整命令。

| 模式 | 等价于 | 示例 |
|---|---|---|
| `probe` | 第 1 步的 ffprobe | `python3 scripts/frames.py probe in.mp4` |
| `shot` | 单张截图 | `python3 scripts/frames.py shot in.mp4 --at 1:23.5` |
| `pick` | thumbnail 挑封面 | `python3 scripts/frames.py pick in.mp4 --start 60 --duration 20` |
| `interval` | 每 N 秒一张，或 `--count` 按总时长均分 | `python3 scripts/frames.py interval in.mp4 --count 12` |
| `keyframes` | 只抽关键帧 | `python3 scripts/frames.py keyframes in.mp4` |
| `scene` | 场景变化抽帧 | `python3 scripts/frames.py scene in.mp4 --threshold 0.3` |
| `sheet` | 缩略图拼图 | `python3 scripts/frames.py sheet in.mp4 --cols 4 --rows 3` |
| `gif` | 调色板两步法 | `python3 scripts/frames.py gif in.mp4 --start 10 --duration 3` |

比直接敲命令多做的事：时间点超出视频长度先报错；输出目录自动建；目录里已有同前缀的旧图、或同名输出已存在时先停下（`--overwrite` 才覆盖）；抽完核对张数和分辨率，把「文件名、秒、时间码」写进输出目录的 `index.csv`；场景抽帧只出 1 张或出得太多时给出调阈值的建议；`--dry-run` 只打印命令；单条命令默认 1800 秒超时（`--timeout` 可改）。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（模板） |
|---|---|---|
| 缺关键信息：没给视频路径，或只说「截几张」 | 先要路径和用途（封面／给 AI 看／素材／动图）；间隔、张数、宽度按「先判断什么」的默认值，标 [待确认] | 「把视频文件路径发我，再说一下用途：做封面、给 AI 看，还是做动图？张数我先按给 AI 看的默认 12 张、宽 768 来。」 |
| 输入不对或自相矛盾：时间点超过视频长度；说「每秒一张」又要「总共 10 张」 | 先 probe 看时长，指出冲突，给两种做法 | 「这段只有 32 秒，第 40 秒不存在；你是要最后一帧，还是时间记错了？」「每秒一张会有 32 张，和 10 张冲突：按间隔还是按总数？」 |
| 超出范围：剪辑配字幕、整片转码、DRM 或付费内容翻录、人脸识别 | 说明不做；剪辑类转对应工具；只要声音的转音频剪辑类技能 | 「这段是付费课程的加密视频，我不能帮忙绕过保护；如果是你自己录的屏，可以接着抽。」 |
| 时间紧，只要最小可用版 | 最小版 = 一条命令 + 输出位置 + 张数；对照表和拼图随后补 | 「先给最小版：`python3 scripts/frames.py interval in.mp4 --count 12`，图在 frames/，12 张，时间点在 index.csv 里。」 |
| 坚持越界：要破解 DRM、截取他人隐私画面公开发布、识别画面里的人 | 守住：不做；有证件、聊天记录等隐私画面提醒先打码 | 「这一步我不做。画面里有别人的证件号，发布前请先打码。」 |
| 张数与预期差得多：场景抽帧只出 1 张、关键帧只有几张 | 先说明原因再调参重跑：阈值高或画面变化小就调低阈值；关键帧稀疏就改用每 N 秒一张 | 「只抽到第一帧，说明画面变化没超过 0.3；我把阈值调到 0.2 再跑一次。」 |
| 竖屏、HDR、10-bit | 竖屏缩放只定一边；HDR/10-bit 截图可能发灰时如实说明，不给未经验证的参数 | 「这是 10-bit 视频，截图可能发灰；要校色需要色调映射，我不套用没验证过的参数。」 |

`scripts/frames.py` 退出码与 ffmpeg 常见报错：

| 退出码 / 报错 | 原因 | 修正办法 |
|---|---|---|
| 0 | 成功 | 按输出清单和 index.csv 交付 |
| 1「参数错误」「视频只有 X 秒，--at … 超出范围」 | 时间写法不对或超出时长；阈值不在 0–1 | 先 `probe` 看时长；时间写 83.5、1:23.5 或 00:01:23.5 |
| 2「找不到视频文件」「读不出视频轨」「…已存在」 | 路径不对；不是视频、只有音频或已损坏；输出已存在 | 路径加引号；换文件；换 `--out`/`--out-dir` 或加 `--overwrite` |
| 3「没找到 ffmpeg、ffprobe」 | 没装或不在 PATH | 用户从官方渠道安装，`ffmpeg -version` 能打印版本即可 |
| 4「ffmpeg 执行失败」「超过 N 秒还没跑完」 | 参数被拒、文件损坏、长视频超时 | 看打印的最后几行报错；长视频加大 `--timeout` 或先用 `keyframes` |
| 5「没有产出图片」 | 时间范围里没有帧，或输出被同名文件挡住 | 核对时间范围；换输出位置 |
| 130「已中断」 | 按了 Ctrl+C | 输出目录可能留有部分图片，换目录或加 `--overwrite` 重跑 |
| `Cannot write more than one file with the same name` | 抽多张却写成 out.jpg | 输出写成 `%04d` 编号模板 |
| 写输出时 `No such file or directory` | 输出目录不存在 | 先 `mkdir -p`（脚本会自动建） |
| `Not overwriting - exiting` 或 `File '…' already exists. Exiting.` | 同名文件已存在，非交互环境或加了 `-n`；此时退出码仍是 0（ffmpeg 9.0.1 实测） | 换文件名，或确认后加 `-y`；别只看退出码，要核对输出文件 |
| `Nothing was written into output file` | `-ss` 超过了视频长度 | 先看 duration，时间点要小于它 |

## 输出契约

交付物按以下顺序：

1. **实际执行的完整命令**（脚本会逐条打印「执行：…」）。
2. **输出清单**：绝对路径、张数、分辨率——用 `ls` 和 ffprobe 或脚本的输出核对，不凭估算。
3. **每张的时间点**：固定间隔按 k×N 秒算（`round=up` 取的是该时刻或之前最近的一帧，最多早一帧），场景抽帧和关键帧取 showinfo 打印的 pts_time；脚本写在 `index.csv`。
4. **给 AI 用时附「文件名—时间点」对照表**（Markdown 表或 index.csv）。
5. **异常说明**：张数与预期差得多（例如场景抽帧只出 1 张），先说明原因和调整办法再重跑。

占位符：只有用户知道的（视频路径、要的时间点）写 [待补]；按默认值定的参数（间隔、张数、宽度、阈值）写 [待确认：默认值]。

交付前自检（逐条答是/否）：

- [ ] 截图命令的 `-ss` 在 `-i` 前？每 N 秒的用了 `round=up`？
- [ ] 张数、分辨率是实际核对过的，不是估算？
- [ ] 竖屏视频的缩放只定了一边，没有写死宽高、没加 `-noautorotate`？
- [ ] 输出目录是新的或确认过可以覆盖，没有混进上次的旧图？
- [ ] 给 AI 用时附了对照表，总数 8–16 张、宽 768 左右？
- [ ] 视频是用户有权使用的；画面里有证件、聊天记录等隐私时提醒了打码？

## 示例

以下为示例：视频是用 ffmpeg 自带测试图案生成的 32 秒样片，输出是实际运行脚本的结果，绝对路径截短为 `…/`。

**用户**：每隔 5 秒截一张，我想让 AI 看视频讲了什么。（附：demo.mp4）

**助手**：先看参数——32 秒、640x360、不旋转。每 5 秒一张只有 7 张，给 AI 看建议 8–16 张，所以改成按总时长均分 12 张 [待确认：如果一定要每 5 秒，就用 `--every 5`]。

```bash
python3 scripts/frames.py interval demo.mp4 --count 12 --out-dir ai_frames
```

**助手交付**：

```text
执行：ffmpeg -hide_banner -nostats -n -i demo.mp4 -vf fps=1/2.6667:round=up,scale=768:-2,showinfo -start_number 0 -frames:v 12 -q:v 2 …/ai_frames/f_%04d.jpg
输出：…/ai_frames，共 12 张，768x432；对照表 …/ai_frames/index.csv
| 文件 | 时间点（秒） | 时间码 |
|---|---|---|
| f_0000.jpg | 0.000 | 00:00:00.000 |
| f_0001.jpg | 2.667 | 00:00:02.667 |
| f_0002.jpg | 5.333 | 00:00:05.333 |
| …（共 12 行，见 index.csv） | | |
| f_0011.jpg | 29.334 | 00:00:29.334 |
说明：时间点是每隔约 2.67 秒的时刻，实际画面是该时刻或之前最近的一帧（最多早 0.04 秒）
```

更多完整示例：[给 AI 看视频：均分、拼图与场景抽帧](examples/ai-video-frames.md)、[封面、竖屏截图与 GIF](examples/cover-and-gif.md)。

## 常见问题（FAQ）

**Q：`-ss` 放在 `-i` 前面会不会截不准？**
A：截图不会。放在前面是先跳到附近关键帧、再解码到准确位置，又快又准；老教程说「放前面不准」，说的是 `-c copy` 剪片。

**Q：每 5 秒一张，为什么第一张不是第 0 秒？**
A：`fps=1/5` 默认取每段中间那帧（实测第 1、2 张在 2.48、7.48 秒）；加 `:round=up` 才正好是 0、5、10 秒。

**Q：给 AI 看视频抽多少张合适？**
A：总数 8–16 张，宽度 768 左右，每张附时间点；镜头切换多的用场景抽帧；想少传几张就交一张 4×3 拼图。

**Q：竖屏视频截出来是躺着的，或者被压扁了？**
A：别加 `-noautorotate`，让 ffmpeg 自动转正；缩放只定一边，如 `scale=-2:720`。

**Q：GIF 太大怎么办？**
A：按顺序减：缩短时长 → 8–10 帧/秒 → 宽度 320 → `dither=none`。

**Q：HDR 视频截图发灰怎么办？**
A：HDR、10-bit 视频截图可能发灰；需要色调映射时如实说明，不套用未经验证的参数。

**Q：能帮我截网站上的视频或付费课程吗？**
A：只处理你有权使用的视频文件；不绕过 DRM，不翻录付费课程或影视内容再传播。

**Q：没有 Python 能用吗？**
A：能，直接用第 2 步的 ffmpeg 命令；脚本只是多做了建目录、防覆盖、核对张数和对照表。

## 常见错误（反模式）

| 错误做法 | 为什么错 | 正确做法 |
|---|---|---|
| 截图时把 `-ss` 放在 `-i` 后面，或以为放前面不准 | 放后面要从头解码，越靠后越慢：实测 10 分钟视频取第 512.36 秒，放前 0.04 秒、放后 0.42 秒，两张画面逐像素一致；「放前面不准」说的是 `-c copy` 剪片（只能从关键帧起拷数据） | 截图一律 `-ss` 放在 `-i` 前 |
| 每 N 秒用 `fps=1/N`，不加 `round=up` | 默认取每段中间那帧，实测第 1、2 张在 2.48、7.48 秒，文件名和时间对不上 | `fps=1/N:round=up` 加 `-start_number 0`，第 k 张 = 第 k×N 秒 |
| 竖屏写死 `scale=1280:720`，或加 `-noautorotate` | 手机竖拍常以横向存储、靠 rotation 元数据竖过来；ffmpeg 默认自动转正，但 ffprobe 报的 width/height 仍是横向数值——写死宽高会压扁，关掉自动旋转画面会躺着 | 只定一边：`scale=-2:720` |
| 抽多张写成 `out.jpg`、编号不补零、不先建目录 | 报 `Cannot write more than one file with the same name`；编号默认从 1 开始、不补零就排序错乱；目录不存在报 `No such file or directory` | 用 `%04d` 模板，需要时 `-start_number 0`，先 `mkdir -p` |
| 重跑时不想清楚覆盖策略，只看退出码 | 同名文件已存在时，非交互环境下 ffmpeg 直接放弃（Not overwriting - exiting），退出码却是 0（ffmpeg 9.0.1 实测） | 想覆盖加 `-y`，想跳过加 `-n`；跑完用 `ls` 核对产出 |
| 以为 `-n` 能保护上次抽的编号图片 | `-n` 只检查模板名本身，`f_0000.jpg` 这类编号文件照样被悄悄重写（ffmpeg 9.0.1 实测） | 每次抽到新目录，或确认后再覆盖；脚本发现旧图会先停下 |
| 给 AI 一次塞几百张原尺寸截图 | 张数太多、图太大，重点反而淹没 | 8–16 张、宽 768 左右、附时间点；镜头多用场景抽帧 |
| 场景抽帧只出 1 张就直接交付 | 说明阈值太高或画面变化小，结果没法用 | 先说明原因，调低阈值再跑；抽太多就调到 0.4–0.5 |

## 边界与不做什么

- 只处理用户有权使用的视频；不帮忙绕过 DRM、翻录付费课程或影视内容再传播；截图要公开发布时，提醒注意版权与肖像权。
- 不做人脸识别、身份辨认或跟踪他人；画面里有证件、聊天记录等隐私信息，提醒先打码。
- 只负责抽帧与做动图；剪辑、配字幕、整片转码不在本技能范围。
- 不代装软件；HDR、10-bit 视频截图可能发灰，需要色调映射时如实说明，不给未经验证的参数。
