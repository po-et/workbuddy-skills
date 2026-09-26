# 原始 ffmpeg 命令（不用脚本时照抄）

`scripts/audio_tool.py` 的每个子命令都会打印「等效命令」；这里是同样的操作不经脚本、直接在 macOS / Linux 终端里写的版本。文件名换成你的，输出另起名字，原文件不覆盖。

## 看文件

```bash
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate,channels:format=duration,bit_rate -of default=nw=1 in.mp3
```

## 裁剪、拼接、转格式（均用 ffmpeg 生成的测试音频实测）

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

## 音量与响度

```bash
# max_volume 离 0 dB 还差多少，最多就加多少
ffmpeg -i voice.wav -af volumedetect -f null - 2>&1 | grep -E 'mean_volume|max_volume'
ffmpeg -i voice.wav -af "volume=6dB" louder.wav
# 响度标准化到 -16 LUFS（口播、播客常用），一遍法，-ar 必须写
ffmpeg -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 normalized.wav
# 核对结果：看 Summary 里的 I 值
ffmpeg -nostats -i normalized.wav -af ebur128 -f null - 2>&1 | grep -A1 'Integrated loudness'
```

要更准跑两遍：第 1 遍只测量，把 JSON 里的 input_i、input_tp、input_lra、input_thresh、target_offset 填进第 2 遍（下面是实测样例值，结果 -16.0）：

```bash
ffmpeg -nostats -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p'
ffmpeg -i voice.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-36.10:measured_TP=-32.04:measured_LRA=4.80:measured_thresh=-46.10:offset=-0.32:linear=true" -ar 48000 normalized2.wav
```

脚本的 `loudnorm --two-pass` 会自动完成这两步，不用手抄数值；`-ar` 默认保持原采样率。

## 淡入淡出、静音、提取音轨

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

## 复核记录

2026-09-26 在 ffmpeg 9.0.1 上用 lavfi 生成的测试音频复核：无损裁剪 15.02 秒、重编码裁剪 15.000 秒；`-to` 放在 `-i` 后得 20.01 秒；起点超过总长时退出码 0、只得到 356 字节的空壳文件；MP3 加 WAV 写进同一个列表重编码，8 秒只剩第一段 5 秒且退出码 0；同格式 MP3 列表法拷贝打印 `non monotonically increasing dts`，文件可用；loudnorm 不写 `-ar` 输出 192000 Hz；带封面的 MP3 不加 `-vn` 转 M4A 报 `codec not currently supported in container`；AAC 音轨拷进 `.mp3` 报 `Exactly one MP3 audio stream is required`。
