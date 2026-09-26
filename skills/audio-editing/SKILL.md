---
name: audio-editing
description: "音频剪辑——不开专业软件，用 ffmpeg 裁剪、拼接、转格式、调音量、淡入淡出、去首尾静音、从视频提取音轨。当用户说「剪一段录音」「几段音频合成一个」「转成mp3」「声音太小」「去掉开头的静音」「提取视频里的声音」时使用。"
author: Captain
version: 0.1.1
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
examples_en:
  - "Cut this recording down to just seconds 5 through 20"
  - "Merge three audio clips into one MP3 and keep them in order"
  - "The meeting recording is too quiet and starts with a dozen seconds of silence; please fix it"
---

# 音频剪辑

适用于不开专业软件、在终端里剪短、拼接、转格式、调音量。全部用 ffmpeg/ffprobe，命令按 macOS/Linux 终端写，文件名换成你的。**原文件不覆盖**：输出另起名字（输入输出同名 ffmpeg 会拒绝，报 `same as Input`）。

## 何时使用

手上有录音、音乐或视频，想做简单的剪、拼、转、调，又不想装专业软件时。用户通常这样说：

- 「帮我剪一段录音，只要第 5 秒到第 20 秒」
- 「把三段音频合成一个 mp3，顺序别乱」
- 「这个 wav 太大了，转成 mp3」
- 「会议录音声音太小，开头还有十几秒静音」
- 「把这个视频里的声音提取出来」
- 「开头结尾加个淡入淡出」

不适用（遇到时直接说明并转交）：

- **录音转文字**：本技能只把音频转成适合识别的 16 kHz 单声道 WAV；转文字交给转写工具，整理成纪要再交给会议录音整理类技能。
- **多轨混音、专业降噪、修复严重噪声、做母带**：建议用专业软件或找音频工程师。
- **翻录、拆分付费音频或受版权保护的音乐再传播，变声冒充、声音克隆**：不做，见「边界与不做什么」。

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
python3 {baseDir}/scripts/audio_tool.py probe in.mp3        # 同样的信息，一行中文
```

记下总时长（剪切起点不能超过它）、编码、采样率、声道，拼接和选格式都要用。

## 第 2 步：按需求选命令（均用 ffmpeg 生成的测试音频实测）

优先用脚本 `scripts/audio_tool.py`：它把下面这些实测过的 ffmpeg 命令包成子命令，动手前先做检查（起点是否超过总长、拼接的几段格式是否一致、加音量会不会削波），输出先写临时文件、成功才改名，结束时打印处理前后的时长、编码、采样率、声道和等效的 ffmpeg 命令。只用 Python 标准库加 ffmpeg，不联网；输出只含音轨（相当于 `-vn`）。

```bash
python3 {baseDir}/scripts/audio_tool.py trim in.mp3 -o clip.mp3 --start 5 --end 20            # 无损裁剪；加 --exact 重编码、时长精确
python3 {baseDir}/scripts/audio_tool.py join part1.mp3 part2.mp3 voice.wav -o joined.mp3       # 格式一致用列表法，不一致自动改用 concat 滤镜
python3 {baseDir}/scripts/audio_tool.py convert voice.wav -o voice.m4a                         # 按输出扩展名选编码；--asr 出 16 kHz 单声道 WAV
python3 {baseDir}/scripts/audio_tool.py volume voice.wav                                       # 只检测：平均音量、峰值、还能加多少
python3 {baseDir}/scripts/audio_tool.py volume voice.wav -o louder.wav --gain 6                # 超过余量会拒绝，避免削波
python3 {baseDir}/scripts/audio_tool.py loudnorm voice.wav -o normalized.wav --two-pass        # 响度标准化到 -16 LUFS，保持原采样率，自动核对 I 值
python3 {baseDir}/scripts/audio_tool.py fade in.mp3 -o faded.mp3 --fade-in 2 --fade-out 3      # 淡出起点按总时长自动算
python3 {baseDir}/scripts/audio_tool.py silence voice.wav                                      # 列出每段静音的起止秒数
python3 {baseDir}/scripts/audio_tool.py trim-silence voice.wav -o trimmed.wav                  # 去首尾静音，两头各留 0.2 秒
python3 {baseDir}/scripts/audio_tool.py extract video.mp4 -o track.m4a                         # AAC 放 .m4a 无损拷出，要 MP3 就自动重编码
python3 {baseDir}/scripts/audio_tool.py batch . --to mp3                                       # 当前目录的 WAV 全转 MP3，已存在的跳过
```

每个子命令对应的原始 ffmpeg 写法（不经脚本时照抄）：

```bash
ffmpeg -ss 5 -to 20 -i in.mp3 -c copy clip.mp3                                   # 无损裁剪（实测 15.02 秒）
ffmpeg -ss 5 -to 20 -i in.mp3 -c:a libmp3lame -q:a 2 clip_exact.mp3              # 重编码裁剪（实测 15.000 秒）
ffmpeg -f concat -safe 0 -i list.txt -c copy joined.mp3                          # 同格式拼接，list.txt 每行 file '文件名'
ffmpeg -i part1.mp3 -i voice.wav -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[a]" -map "[a]" -c:a libmp3lame -q:a 2 mixed.mp3
ffmpeg -i voice.wav -vn -c:a aac -b:a 192k voice.m4a                             # 转格式，-vn 丢掉封面图
ffmpeg -i voice.wav -af volumedetect -f null -                                   # 看 mean_volume 与 max_volume
ffmpeg -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 normalized.wav  # 一遍法，-ar 必须写
ffmpeg -i voice.wav -af "silencedetect=noise=-50dB:d=0.5" -f null -              # 找静音；底噪大就把 -50dB 提到 -40dB
ffmpeg -i video.mp4 -vn -c:a copy track.m4a                                      # 提取音轨
```

响度标准化到 -16 LUFS 是口播、播客常用的目标。一遍法实测 -15.7 与 -16.0（两段不同的测试音频，目标 -16），日常够用；要更准用 `--two-pass`，脚本自动先测量、再把测量值填进第 2 遍。批量转换、淡出起点计算、两遍法手抄测量值等带 shell 拼接的完整原始写法，以及这些坑在 ffmpeg 9.0.1 上的复核记录，见 [references/ffmpeg-commands.md](references/ffmpeg-commands.md)。

## 信息不全或出错时

| 情况 | 怎么处理 | 对用户说的话（一句模板） |
|---|---|---|
| E1 缺关键信息：没说剪哪段、输出给谁用、要不要精确到毫秒 | 最多问三个：起止时间、用途（发给别人 / 苹果设备 / 转文字 / 存档）、要无损快剪还是精确；其余默认：输出与原格式相同、无损优先，默认值标 [待确认] | 「从第几秒剪到第几秒？剪完发给别人还是拿去转文字？要精确到毫秒还是无损快剪（边界可能差几十毫秒）？」 |
| E2 输入不对或自相矛盾：起点超过总时长；终点早于起点；时间写成「一分半」；要「无损」又要「精确到毫秒」；输入输出同名 | 先跑 probe 拿总时长再核对；时间统一换成秒或 00:01:30 复述确认；无损和精确二选一并说明代价；输出另起名字 | 「文件总长 30 秒，起点 40 秒已经超出了；是不是看错了文件，或者起点其实是 4 秒？」 |
| E3 超出范围：转文字、降噪修复、多轨混音、翻录付费内容、变声或声音克隆 | 转文字交给转写工具；降噪混音建议专业软件或音频工程师；版权与冒充类不做 | 「严重的噪声修复命令行做不好，建议用专业软件；我可以先帮你把音量和首尾静音处理好。」 |
| E4 时间紧，只要最小可用版 | 只做一步最关键的：只剪不调、只转不修；用无损拷贝最快出结果，交付时只列输出文件和前后时长 | 「先给你无损快剪版，秒出；要精确到毫秒或调音量，回头再做一遍。」 |
| E5 用户坚持越界：覆盖原文件、超过余量硬加音量、拆分付费音频传播、把别人的录音公开 | 原文件不覆盖，另起名字；加音量先说清削波的代价，确需才加 `--force`；版权和他人隐私的要求不做 | 「原文件我不覆盖，输出另起名字，确认没问题你再自己替换；这样出错了还能回头。」 |
| 没装 ffmpeg，或文件损坏读不出信息 | 说明安装方式（macOS 用 Homebrew，Linux 用系统包管理器）；损坏的文件请用户重新导出 | 「这台电脑还没装 ffmpeg，装好后我再处理；命令都给你准备好了。」 |

脚本的退出码与 ffmpeg 常见报错：

| 退出码 / 报错 | 原因 | 修正办法 |
|---|---|---|
| 0 | 处理完成，已打印前后信息和等效命令 | 按输出契约交付 |
| 1「参数错误」 | 缺子命令、时间写法不对、终点早于起点、输出与输入同名、输出已存在、扩展名不支持 | 按提示改；输出已存在时换名或加 `--force` |
| 2「文件问题」 | 找不到输入、给的是文件夹、输出目录不存在、没装 ffmpeg / ffprobe | 核对路径；先安装 ffmpeg |
| 3「不能这样处理」 | 起点超过总长、没有音轨、淡入淡出比总长还长、加音量超过余量、文件损坏 | 先 probe 看总长；超过余量改用 loudnorm |
| 4「ffmpeg 出错」 | ffmpeg 返回非 0 或超时；报错原文附在后面 | 按原文排查；长文件用 `--timeout` 调大 |
| 130「已中断」 | 按了 Ctrl+C | 临时文件已删，原文件未动，直接重跑 |
| `same as Input` | ffmpeg 的输入输出同名 | 输出另起名字 |
| `codec not currently supported in container` | 带封面的 MP3 转 M4A，封面被当成视频流 | 加 `-vn` |
| `Exactly one MP3 audio stream is required` | AAC 音轨 `-c copy` 进 .mp3 | AAC 放 .m4a；要 MP3 就重编码 |
| `non monotonically increasing dts` | 同格式 MP3 用 `-c copy` 拼接时的提示 | 文件能用；介意就去掉 `-c copy` 重编码 |

## 输出契约

交付按固定顺序，某项不涉及写「无」：

```
0 标题行：音频处理结果｜状态：完成 / 最小版 / 未处理（原因）｜[待确认] N 项
① 执行的完整命令（脚本打印的等效 ffmpeg 命令也算）
② 输出文件路径；原文件未改动
③ 处理前后的时长、编码、采样率、声道（用 ffprobe 或脚本核对，不凭估算）
④ 调音量或响度时，处理后的 max_volume 或 I 值
⑤ 是否发生了有损重编码
```

原文件不动。占位符：[待确认]——没问到、先按默认处理的项（如输出格式、无损还是精确），数量写进标题行；[待补]——要用户补的信息（如起止时间没给全时的具体秒数）。

交付前自检（每条答「是」才交）：

- [ ] 动手前看过总时长，起止时间都在范围内？
- [ ] 原文件没被覆盖，输出另起了名字？
- [ ] 前后的时长、编码、采样率、声道是用 ffprobe 或脚本核对的，不是估算？
- [ ] 调过音量或响度的，附了处理后的峰值或 I 值？
- [ ] 写明了有没有有损重编码、发生在哪一步？
- [ ] 拼接的，处理后的总时长和各段之和对得上？

## 示例

> 示例：「录音.mp3」是用 ffmpeg 生成的 30 秒测试音频，输出为脚本真实输出。

用户：「帮我剪一段录音，只要第 5 秒到第 20 秒。」

助手先问：「要精确到毫秒（重编码，音质损失很小），还是无损快剪（秒出，但边界可能多出几十毫秒）？」用户答：「精确一点。」

```bash
python3 scripts/audio_tool.py trim 录音.mp3 -o 录音_5-20秒.mp3 --start 5 --end 20 --exact
```

```
完成：录音_5-20秒.mp3
处理前：录音.mp3｜30 秒｜mp3｜44100 Hz｜2 声道
处理后：录音_5-20秒.mp3｜15 秒｜mp3｜44100 Hz｜2 声道
重编码：是（有损编码会损失一点音质，多步处理先转 WAV，最后再压一次）
等效命令：ffmpeg -ss 5 -to 20 -i '录音.mp3' -vn -c:a libmp3lame -q:a 2 '录音_5-20秒.mp3'
```

交付：

```
音频处理结果｜状态：完成｜[待确认] 0 项
① 命令：ffmpeg -ss 5 -to 20 -i '录音.mp3' -vn -c:a libmp3lame -q:a 2 '录音_5-20秒.mp3'
② 输出：录音_5-20秒.mp3；原文件 录音.mp3 未改动
③ 前后：30 秒 → 15 秒；mp3、44100 Hz、2 声道不变
④ 音量：无（没有调音量）
⑤ 有损重编码：有一次（按你要的精确裁剪）
```

更完整的示例（会议录音：找静音、去首尾静音、两遍响度标准化、先转 WAV 最后只压一次）见 [examples/meeting-recording-cleanup.md](examples/meeting-recording-cleanup.md)。

## 常见问题（FAQ）

**问：剪出来的时长比我要的多了一点点，为什么？**
答：无损裁剪（`-c copy`）的边界只能落在音频帧上，实测 15 秒会剪出 15.02 秒；要精确到毫秒就重编码（脚本加 `--exact`）。

**问：MP3 转来转去会不会越来越差？**
答：会，MP3/AAC 每压一次都损失一点。多步处理先转 WAV 做完，最后只压一次。

**问：声音太小，直接加 20 dB 行不行？**
答：先测余量：峰值离 0 dB 还差多少，最多就加多少，超过会削波破音。想「听起来和别的节目一样响」，用 loudnorm 标准化到 -16 LUFS。

**问：几段格式不一样的音频能直接拼吗？**
答：能，但不能用列表法：MP3 和 WAV 写进同一个列表，实测只剩第一段、而且不报错。用 concat 滤镜，脚本的 join 会自动判断。

**问：能帮我把录音转成文字吗？**
答：本技能不转文字；可以先转成 16 kHz 单声道 WAV（`convert --asr`），再交给转写工具。

**问：能不能直接覆盖原文件，省得多一个文件？**
答：不覆盖。输出另起名字，你确认没问题后再自己替换原文件，出错了还能回头。

**问：Windows 能用吗？**
答：ffmpeg 有 Windows 版，脚本只用 Python 标准库，按设计不依赖 shell（本技能只在 macOS 上实测过）。本页的原始命令按 macOS/Linux 终端写，其中批量转换、淡出起点计算用到了 shell 语法；Windows 上优先用脚本的 batch、fade 子命令。

## 常见错误（反模式）

最佳实践先记三条：动手前先看总时长；原文件不覆盖；多步处理先转 WAV、最后只压一次。

| 错误做法 | 为什么错 | 正确做法 |
|---|---|---|
| 把 `-to` 放在 `-i` 后面：`-ss 5 -i in.mp3 -to 20` | `-ss` 在前时输出时间从 0 重算，实测得 20 秒而不是 15 秒 | 两个都放 `-i` 前，或改写时长 `-t 15` |
| 不看总时长就剪 | 起点超过总长不报错，退出码照样是 0，只得到一个空壳文件 | 先 ffprobe 看时长；脚本会直接拦下 |
| MP3 和 WAV 写进同一个 list.txt 拼接 | 就算重编码，实测也只剩第一段，退出码仍是 0 | 格式不同用 concat 滤镜，或先统一转成同参数 WAV |
| loudnorm 不写 `-ar` | 输出被升到 192 kHz，WAV 体积变成 48 kHz 的 4 倍 | 写上 `-ar`；脚本默认保持原采样率 |
| 带封面的 MP3 转 M4A 不加 `-vn` | 封面被当成视频流去编码，报 `codec not currently supported in container` | 加 `-vn` |
| AAC 音轨 `-c copy` 进 `.mp3` | 容器与编码对不上，报 `Exactly one MP3 audio stream is required` | 拷贝前看编码：AAC 放 .m4a，要 MP3 就重编码 |
| 加音量不看余量 | 超过 volumedetect 测出的余量就会削波破音 | 先测再加；要「听起来一样响」用 loudnorm |
| 同格式 MP3 列表法拷贝，看到 `non monotonically increasing dts` 就以为失败 | 这只是提示，文件能用 | 介意就去掉 `-c copy` 重编码 |
| 输出和输入同名，或直接覆盖原文件 | ffmpeg 会拒绝（`same as Input`）；强行覆盖出错就回不去 | 输出另起名字 |

## 边界与不做什么

- 只处理用户有权使用的音频；不帮忙翻录、拆分付费音频或受版权保护的音乐再传播。
- 录音涉及他人（会议、电话、课堂）时，公开或转发前提醒先征得当事人同意；不做变声冒充、声音克隆。
- 这是命令行剪辑，不是多轨混音或专业降噪；需要逐段精修、修复严重噪声、做母带时，建议用专业软件或找音频工程师。
- 不代装软件，不把用户音频上传到任何在线服务。
