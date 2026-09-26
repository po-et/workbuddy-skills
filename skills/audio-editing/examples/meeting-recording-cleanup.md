# 示例：会议录音声音太小、开头十几秒静音

> 示例：测试音频由 ffmpeg 生成（12 秒静音 + 60 秒粉红噪声代替说话声 + 3 秒静音，AAC 单声道），下面每一段输出都是脚本对这份测试音频的真实输出。真实录音的数字会不同。

## 用户原话

> 会议录音声音太小，开头还有十几秒静音，帮我处理一下。

## 助手先问一个问题

> 处理完要发给别人听，还是拿去转文字？发给别人听我输出 M4A，转文字我输出 16 kHz 单声道 WAV。

用户：「发群里给大家听。」

## 先看文件、测音量、找静音

```bash
python3 scripts/audio_tool.py probe meeting.m4a
python3 scripts/audio_tool.py volume meeting.m4a
python3 scripts/audio_tool.py silence meeting.m4a
```

```
meeting.m4a｜75 秒｜aac｜44100 Hz｜1 声道
meeting.m4a｜平均音量 -45.9 dB｜峰值 -31.4 dB｜最多还能加 31.4 dB（到 0 dB 为止）
要「听起来和别的节目一样响」，用 loudnorm 子命令，而不是一味加分贝
meeting.m4a｜总长 75 秒｜阈值 -50 dB、至少 0.5 秒算静音
静音 1：0 → 12 秒（12 秒）
静音 2：72 → 75 秒（3 秒）
```

判断：开头 12 秒、结尾 3 秒是静音；平均音量 -45.9 dB 偏小。要做三步（去静音、响度标准化、压回 M4A），所以先转成 WAV 做完，最后只压一次。

## 处理

```bash
python3 scripts/audio_tool.py convert meeting.m4a -o meeting.wav
python3 scripts/audio_tool.py trim-silence meeting.wav -o trimmed.wav
python3 scripts/audio_tool.py loudnorm trimmed.wav -o normalized.wav --two-pass
python3 scripts/audio_tool.py convert normalized.wav -o meeting_clean.m4a
```

后三步的输出：

```
完成：trimmed.wav
处理前：meeting.wav｜75 秒｜pcm_s16le｜44100 Hz｜1 声道
处理后：trimmed.wav｜60.39 秒｜pcm_s16le｜44100 Hz｜1 声道
重编码：否（WAV / FLAC）
去掉了约 14.61 秒首尾静音；反转处理会把整段读进内存，超长录音先分段

完成：normalized.wav
处理前：trimmed.wav｜60.39 秒｜pcm_s16le｜44100 Hz｜1 声道
处理后：normalized.wav｜60.39 秒｜pcm_s16le｜44100 Hz｜1 声道
重编码：是（响度处理会改变采样值）
第 1 遍测量：I -45.71｜TP -31.32｜LRA 0.10｜thresh -55.71｜offset -0.02
核对：处理后综合响度 I = -15.9 LUFS（目标 -16）

完成：meeting_clean.m4a
处理前：normalized.wav｜60.39 秒｜pcm_s16le｜44100 Hz｜1 声道
处理后：meeting_clean.m4a｜60.39 秒｜aac｜44100 Hz｜1 声道
重编码：是（有损编码会损失一点音质，多步处理先转 WAV，最后再压一次）
等效命令：ffmpeg -i normalized.wav -vn -c:a aac -b:a 192k meeting_clean.m4a
```

（每一步的「等效命令」行这里只保留了最后一步，其余同理。）

## 交付

```
音频处理结果｜状态：完成｜[待确认] 0 项
① 执行的命令：见上面四条（每条的等效 ffmpeg 命令脚本已打印）
② 输出文件：meeting_clean.m4a（原文件 meeting.m4a 未改动；中间文件 meeting.wav、trimmed.wav、normalized.wav 可以删）
③ 处理前后：75 秒 → 60.39 秒；aac、44100 Hz、1 声道不变
④ 响度：综合响度 I 从 -45.71 到 -15.9 LUFS（目标 -16）；最终文件峰值 -1.8 dB
⑤ 有损重编码：有一次，发生在最后压回 M4A 时
```

最终文件的峰值用 `python3 scripts/audio_tool.py volume meeting_clean.m4a` 核对（输出：平均音量 -15.4 dB，峰值 -1.8 dB）。
