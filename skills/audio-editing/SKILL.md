---
name: audio-editing
description: "音频剪辑——不开专业软件，用 ffmpeg 裁剪、拼接、转格式、调音量、淡入淡出、去首尾静音、从视频提取音轨。当用户说「剪一段录音」「几段音频合成一个」「转成mp3」「声音太小」「去掉开头的静音」「提取视频里的声音」时使用。"
author: Captain
version: 0.1.0
display_name: "音频剪辑"
display_name_en: "Audio Editing"
description_zh: "不装专业软件，用 ffmpeg 处理录音和音乐：按时间裁剪（无损或重编码）、列表法拼接、格式与码率转换、音量检测与响度标准化、淡入淡出、去首尾静音、从视频提取音轨；命令逐条实测，讲清 -to 位置、混格式拼接丢段、loudnorm 升采样等坑。"
description_en: "Trim, join, convert, level, fade, de-silence and extract audio on the command line with ffmpeg, using tested commands and explaining the usual traps."
tags:
  - "音频剪辑"
  - "录音剪辑"
  - "音频拼接"
  - "转mp3"
  - "音量调整"
  - "去静音"
  - "提取音轨"
  - "ffmpeg"
  - "audio editing"
examples_zh:
  - "帮我剪一段录音，只要第 5 秒到第 20 秒"
  - "把三段音频合成一个 mp3，顺序别乱"
  - "会议录音声音太小，开头还有十几秒静音，帮我处理一下"
---

# 音频剪辑

适用于不开专业软件、在终端里剪短、拼接、转格式、调音量。全部用 ffmpeg/ffprobe，命令按 macOS/Linux 终端写，文件名换成你的。**原文件不覆盖**：输出另起名字（输入输出同名 ffmpeg 会拒绝，报 `same as Input`）。

## 先判断什么

1. **要不要重编码**：只掐头去尾、拼同格式文件 → `-c copy` 无损、秒完成；要改音量、淡入淡出、换格式、精确到毫秒 → 必须重编码。MP3/AAC 每压一次损失一点，多步处理先转 WAV 做完，最后再压一次。
2. **原文件是什么**：先跑第 1 步的 ffprobe。
3. **给谁用**，决定输出格式：

| 用途 | 格式 | 参数 |
|---|---|---|
| 到处能播、发给别人 | MP3 | `-c:a libmp3lame -q:a 2`（可变码率，0–9 越小越好） |
| 苹果设备、视频配乐 | M4A（AAC） | `-c:a aac -b:a 192k` |
| 语音识别、转文字 | WAV 16 kHz 单声道 | `-ar 16000 -ac 1` |
| 存档、继续编辑 | WAV 或 FLAC | `-c:a pcm_s16le` / `-c:a flac` |
| 纯人声、要很小 | Opus | `-c:a libopus -b:a 48k` |

## 第 1 步：先看文件

```bash
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels:format=duration,bit_rate -of default=nw=1 in.mp3
```

记下总时长（剪切起点不能超过它）、编码、采样率、声道，拼接和选格式都要用。

## 第 2 步：按需求选命令（均用 ffmpeg 生成的测试音频实测）

```bash
# 裁剪第 5–20 秒：无损，边界落在音频帧上（实测 15.02 秒）
ffmpeg -ss 5 -to 20 -i in.mp3 -c copy clip.mp3
# 裁剪并重编码：时长精确（实测 15.000 秒）
ffmpeg -ss 5 -to 20 -i in.mp3 -c:a libmp3lame -q:a 2 clip_exact.mp3
# 拼接同格式文件：列表法，按行序拼
printf "file '%s'\n" part1.mp3 part2.mp3 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy joined.mp3
# 格式不同（如 MP3 + WAV）：concat 滤镜，自动统一采样率和声道
ffmpeg -i part1.mp3 -i voice.wav -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[a]" -map "[a]" -c:a libmp3lame -q:a 2 mixed.mp3
# 转格式；-vn 顺手丢掉可能内嵌的封面图
ffmpeg -i voice.wav -vn -c:a aac -b:a 192k voice.m4a
# 批量：当前目录所有 WAV 转 MP3，已存在的跳过（-n）
for f in *.wav; do ffmpeg -n -i "$f" -vn -c:a libmp3lame -q:a 2 "${f%.*}.mp3"; done
```

调音量先测再调：

```bash
# max_volume 离 0 dB 还差多少，最多就加多少
ffmpeg -i voice.wav -af volumedetect -f null - 2>&1 | grep -E 'mean_volume|max_volume'
ffmpeg -i voice.wav -af "volume=6dB" louder.wav
# 响度标准化到 -16 LUFS（口播、播客常用），一遍法，-ar 必须写
ffmpeg -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 normalized.wav
# 核对结果：看 Summary 里的 I 值
ffmpeg -nostats -i normalized.wav -af ebur128 -f null - 2>&1 | grep -A1 'Integrated loudness'
```

一遍法实测 -15.7（目标 -16），日常够用。要更准跑两遍：第 1 遍只测量，把 JSON 里的 input_i、input_tp、input_lra、input_thresh、target_offset 填进第 2 遍（下面是实测样例值，结果 -16.0）：

```bash
ffmpeg -nostats -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p'
ffmpeg -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-36.10:measured_TP=-32.04:measured_LRA=4.80:measured_thresh=-46.10:offset=-0.32:linear=true" -ar 48000 normalized2.wav
```

淡入淡出、静音、提取音轨：

```bash
# 淡入 2 秒、淡出 3 秒；淡出起点 = 总时长 - 3
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 in.mp3)
ffmpeg -i in.mp3 -af "afade=t=in:st=0:d=2,afade=t=out:st=$(awk -v d="$D" 'BEGIN{print d-3}'):d=3" -c:a libmp3lame -q:a 2 faded.mp3
# 静音在哪：打印每段静音的起止秒数；底噪大就把 -50dB 提到 -40dB
ffmpeg -i voice.wav -af "silencedetect=noise=-50dB:d=0.5" -f null - 2>&1 | grep -oE 'silence_(start|end): [0-9.]+'
# 去首尾静音、两头各留 0.2 秒：反转一次处理尾部，再反转回来（整段进内存，超长录音先分段）
ffmpeg -i voice.wav -af "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.2,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.2,areverse" trimmed.wav
# 从视频提取音轨：原样拷出（AAC 放 .m4a），或转成 MP3
ffmpeg -i video.mp4 -vn -c:a copy track.m4a
ffmpeg -i video.mp4 -vn -c:a libmp3lame -q:a 2 track.mp3
```

## 最常见的坑

1. **`-to` 放在 `-i` 后意思就变了**：`-ss 5 -i in.mp3 -to 20` 实测得 20 秒而不是 15 秒，因为 `-ss` 在前时输出时间从 0 重算。要么两个都放 `-i` 前，要么改写时长 `-t 15`。
2. **起点超过总长不报错**：退出码照样是 0，只得到一个空壳文件。剪之前先看时长。
3. **列表法混格式会悄悄丢段**：MP3 和 WAV 写进同一个 list.txt，就算重编码，实测也只剩第一段，退出码仍是 0。格式不同用 concat 滤镜，或先统一转成同参数 WAV。同格式 MP3 用 `-c copy` 拼时可能打印 `non monotonically increasing dts`，文件能用；介意就去掉 `-c copy` 重编码。
4. **loudnorm 会升采样到 192 kHz**：不写 `-ar`，实测输出 192000 Hz，WAV 体积变成 48 kHz 的 4 倍。
5. **带封面的 MP3 转 M4A 失败**：封面被当成视频流去编码，报 `codec not currently supported in container`，加 `-vn` 即可。
6. **容器与编码对不上**：AAC 音轨 `-c copy` 进 `.mp3` 会报 `Exactly one MP3 audio stream is required`。拷贝前看编码，AAC 放 .m4a，要 MP3 就重编码。
7. **加音量不看余量**：超过 volumedetect 测出的余量就会削波破音；要「听起来一样响」用 loudnorm，别一味加分贝。

## 输出契约

交付：① 执行的完整命令；② 输出文件路径；③ 处理前后的时长、编码、采样率、声道（用第 1 步的 ffprobe 核对，不凭估算）；④ 调音量或响度时附处理后的 max_volume 或 I 值；⑤ 注明是否发生了有损重编码。原文件不动。

## 边界与不做什么

- 只处理用户有权使用的音频；不帮忙翻录、拆分付费音频或受版权保护的音乐再传播。
- 录音涉及他人（会议、电话、课堂）时，公开或转发前提醒先征得当事人同意；不做变声冒充、声音克隆。
- 这是命令行剪辑，不是多轨混音或专业降噪；需要逐段精修、修复严重噪声、做母带时，建议用专业软件或找音频工程师。
- 不代装软件，不把用户音频上传到任何在线服务。
