#!/usr/bin/env python3
"""音频剪辑小工具：把 SKILL.md 里实测过的 ffmpeg 命令包成带检查的子命令，常见的坑在动手前拦下。

依赖 ffmpeg / ffprobe（本技能原本就依赖）；其余只用 Python 标准库，不联网。
原文件从不覆盖：输出先写到同目录的临时文件，成功后再改名；中断或失败时删掉临时文件。
输出只含音轨（相当于 -vn），封面图和视频画面不保留。

子命令：
  probe        FILE                                   看时长、编码、采样率、声道
  trim         IN -o OUT --start 5 --end 20 [--exact]  裁剪；默认无损拷贝，--exact 重编码、时长精确
  join         A B [C ...] -o OUT                     拼接；格式一致用列表法无损，不一致自动改用 concat 滤镜
  convert      IN -o OUT [--asr]                      转格式，按输出扩展名选编码；--asr 出 16 kHz 单声道 WAV
  volume       IN [-o OUT --gain 6] [--force]         不给 --gain 只检测音量；给了先查余量，超出会削波就拒绝
  loudnorm     IN -o OUT [--target -16] [--two-pass]  响度标准化，保持原采样率，结束后核对综合响度 I 值
  fade         IN -o OUT [--fade-in 2] [--fade-out 3] 淡入淡出，淡出起点按总时长自动算
  silence      IN [--noise -50] [--min 0.5]           列出每段静音的起止秒数
  trim-silence IN -o OUT [--noise -50] [--keep 0.2]   去首尾静音，两头各留一点
  extract      VIDEO -o OUT                           从视频提取音轨；AAC 放 .m4a 可无损拷贝
  batch        DIR --to mp3                           目录里的 WAV 全部转格式，已存在的跳过
退出码：0 成功；1 参数错误；2 文件问题或没装 ffmpeg；3 输入不适合这样处理（如起点超过总长、余量不够）；
        4 ffmpeg 执行失败或超时；130 用户中断
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

PRESETS = {  # 输出扩展名 -> 编码参数（与 SKILL.md「给谁用」表一致）
    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    ".m4a": ["-c:a", "aac", "-b:a", "192k"],
    ".aac": ["-c:a", "aac", "-b:a", "192k"],
    ".wav": ["-c:a", "pcm_s16le"],
    ".flac": ["-c:a", "flac"],
    ".opus": ["-c:a", "libopus", "-b:a", "48k"],
    ".ogg": ["-c:a", "libopus", "-b:a", "48k"],
}
COPY_OK = {  # 编码 -> 能无损拷贝进去的扩展名
    "mp3": (".mp3",), "aac": (".m4a", ".aac"), "flac": (".flac",),
    "opus": (".opus", ".ogg"), "vorbis": (".ogg",),
}


class ArgError(Exception):
    code = 1


class FileProblem(Exception):
    code = 2


class ContentError(Exception):
    code = 3


class FFError(Exception):
    code = 4


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)


def tools():
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ff or not fp:
        raise FileProblem("找不到 ffmpeg 或 ffprobe：macOS 可用 Homebrew 安装，Linux 用系统包管理器安装")
    return ff, fp


def seconds(text):
    """5、5.5、1:05、00:01:05.5 都认。"""
    try:
        parts = [float(p) for p in str(text).split(":")]
    except ValueError:
        raise ArgError("时间「%s」看不懂，写成 5、5.5 或 00:01:05 这样" % text)
    if len(parts) > 3 or any(p < 0 for p in parts):
        raise ArgError("时间「%s」看不懂，写成 5、5.5 或 00:01:05 这样" % text)
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def fmt(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


def probe(fp, path, timeout):
    if not os.path.exists(path):
        raise FileProblem("找不到文件：%s" % path)
    if os.path.isdir(path):
        raise FileProblem("%s 是文件夹，请指定音频或视频文件" % path)
    cmd = [fp, "-v", "error", "-show_entries",
           "format=duration,bit_rate:stream=codec_type,codec_name,sample_rate,channels", "-of", "json", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FFError("ffprobe 超过 %d 秒没有返回" % timeout)
    if r.returncode != 0:
        raise ContentError("读不出 %s 的音视频信息，文件可能损坏或不是音视频：%s"
                           % (path, (r.stderr.strip().splitlines() or ["?"])[-1]))
    data = json.loads(r.stdout or "{}")
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    info = {"path": path, "duration": float(data.get("format", {}).get("duration") or 0),
            "has_audio": bool(audio), "has_video": any(s.get("codec_type") == "video" for s in data.get("streams", []))}
    if audio:
        a = audio[0]
        info.update(codec=a.get("codec_name", "?"), rate=int(a.get("sample_rate") or 0),
                    channels=int(a.get("channels") or 0))
    return info


def need_audio(info):
    if not info["has_audio"]:
        raise ContentError("%s 里没有音轨" % info["path"])
    return info


def describe(info):
    if not info.get("has_audio"):
        return "%s｜%s 秒｜没有音轨" % (info["path"], fmt(info["duration"]))
    return "%s｜%s 秒｜%s｜%d Hz｜%d 声道" % (info["path"], fmt(info["duration"]), info["codec"],
                                          info["rate"], info["channels"])


def check_out(out, inputs, force):
    ext = os.path.splitext(out)[1].lower()
    if ext not in PRESETS:
        raise ArgError("输出扩展名 %s 不支持，用 %s 之一" % (ext or "（没有）", " ".join(sorted(PRESETS))))
    for i in inputs:
        if os.path.abspath(i) == os.path.abspath(out):
            raise ArgError("输出不能和输入同名（原文件不覆盖），换个名字，例如 %s" % out.replace(ext, "_new" + ext))
    if os.path.exists(out) and not force:
        raise ArgError("%s 已存在；换个名字，或加 --force 覆盖" % out)
    folder = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(folder):
        raise FileProblem("输出目录不存在：%s" % folder)
    return ext


def run_ff(ff, args, out, timeout):
    """在同目录临时文件上跑 ffmpeg，成功后改名为 out；返回 (显示用命令, stderr)。"""
    ext = os.path.splitext(out)[1]
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=ext, dir=os.path.dirname(os.path.abspath(out)))
    os.close(fd)
    cmd = [ff, "-hide_banner", "-nostdin", "-y"] + args + [tmp]
    shown = "ffmpeg " + " ".join(shlex.quote(a) for a in args + [out])
    try:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise FFError("ffmpeg 超过 %d 秒没有结束（可用 --timeout 调大）" % timeout)
        if r.returncode != 0:
            tail = [l for l in r.stderr.strip().splitlines() if l.strip()][-3:]
            raise FFError("ffmpeg 失败（退出码 %d）：%s" % (r.returncode, " / ".join(tail)))
        os.replace(tmp, out)
        return shown, r.stderr
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def analyze(ff, path, afilter, timeout):
    """只分析不输出（-f null），返回 stderr。"""
    cmd = [ff, "-hide_banner", "-nostdin", "-nostats", "-i", path, "-af", afilter, "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FFError("ffmpeg 分析超过 %d 秒没有结束" % timeout)
    if r.returncode != 0:
        raise FFError("ffmpeg 分析失败：%s" % (r.stderr.strip().splitlines() or ["?"])[-1])
    return r.stderr


def volumes(ff, path, timeout):
    err = analyze(ff, path, "volumedetect", timeout)
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", err)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", err)
    if not mean or not peak:
        raise FFError("没读到音量检测结果")
    return float(mean.group(1)), float(peak.group(1))


def integrated(ff, path, timeout):
    err = analyze(ff, path, "ebur128", timeout)
    found = re.findall(r"I:\s*(-?[\d.]+) LUFS", err)
    return float(found[-1]) if found else None


def report(before, after, shown, lossy, extra=()):
    lines = ["完成：%s" % after["path"]]
    for b in before:
        lines.append("处理前：" + describe(b))
    lines.append("处理后：" + describe(after))
    lines.append("重编码：" + ("是（有损编码会损失一点音质，多步处理先转 WAV，最后再压一次）" if lossy is True
                              else "否（无损拷贝）" if lossy is False else lossy))
    lines += list(extra)
    lines.append("等效命令：" + shown)
    print("\n".join(lines))


def encode_args(ext, info_codec, want_copy):
    """能无损拷贝就拷贝，否则按扩展名选编码。返回 (参数, 是否重编码, 说明)。"""
    if want_copy and ext in COPY_OK.get(info_codec, ()):
        return ["-c:a", "copy"], False, None
    note = None
    if want_copy:
        note = "%s 编码不能直接拷进 %s，已改为重编码" % (info_codec, ext)
    return list(PRESETS[ext]), True, note


def cmd_probe(a, ff, fp):
    info = probe(fp, a.file, a.timeout)
    print(describe(info))
    if info.get("has_video"):
        print("另有视频或封面图流；本工具的输出只保留音轨")
    return 0


def cmd_trim(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    ext = check_out(a.out, [a.input], a.force)
    start = seconds(a.start)
    if start >= info["duration"]:
        raise ContentError("起点 %s 秒超过或等于总时长 %s 秒；ffmpeg 遇到这种情况不报错，只会输出一个空壳文件"
                           % (fmt(start), fmt(info["duration"])))
    if a.end is None and a.length is None:
        raise ArgError("给 --end（终点）或 --length（时长）其中一个")
    end = seconds(a.end) if a.end is not None else start + seconds(a.length)
    if end <= start:
        raise ArgError("终点 %s 秒要大于起点 %s 秒" % (fmt(end), fmt(start)))
    extra = []
    if end > info["duration"]:
        extra.append("提示：终点超过总时长，已按总时长 %s 秒截止" % fmt(info["duration"]))
        end = info["duration"]
    enc, lossy, note = encode_args(ext, info["codec"], not a.exact)
    if note:
        extra.append("提示：" + note)
    if not lossy:
        extra.append("提示：无损裁剪的边界落在音频帧上，时长可能多出几十毫秒；要精确到毫秒加 --exact")
    # -ss 与 -to 都放在 -i 前面：放在后面时 -to 的意思会变（见 SKILL.md 反模式第 1 条）
    shown, _ = run_ff(ff, ["-ss", fmt(start), "-to", fmt(end), "-i", a.input, "-vn"] + enc, a.out, a.timeout)
    report([info], probe(fp, a.out, a.timeout), shown, lossy, extra)
    return 0


def cmd_join(a, ff, fp):
    if len(a.inputs) < 2:
        raise ArgError("至少给两个要拼接的文件")
    infos = [need_audio(probe(fp, p, a.timeout)) for p in a.inputs]
    ext = check_out(a.out, a.inputs, a.force)
    first = infos[0]
    same = all((i["codec"], i["rate"], i["channels"]) == (first["codec"], first["rate"], first["channels"])
               for i in infos) and ext in COPY_OK.get(first["codec"], ())
    extra = []
    listdir = tempfile.mkdtemp(prefix="audio-join-")
    try:
        if same:
            lst = os.path.join(listdir, "list.txt")
            with open(lst, "w", encoding="utf-8") as fh:
                for p in a.inputs:
                    fh.write("file '%s'\n" % os.path.abspath(p).replace("'", "'\\''"))
            shown, _ = run_ff(ff, ["-f", "concat", "-safe", "0", "-i", lst, "-vn", "-c:a", "copy"], a.out, a.timeout)
            shown = shown.replace(lst, "list.txt")
            lossy = False
            extra.append("方式：列表法（格式、采样率、声道一致），按给出的顺序拼接")
        else:
            args = []
            for p in a.inputs:
                args += ["-i", p]
            labels = "".join("[%d:a]" % i for i in range(len(a.inputs)))
            args += ["-filter_complex", "%sconcat=n=%d:v=0:a=1[a]" % (labels, len(a.inputs)), "-map", "[a]"]
            shown, _ = run_ff(ff, args + list(PRESETS[ext]), a.out, a.timeout)
            lossy = True
            extra.append("方式：concat 滤镜（各段格式、采样率或声道不一致；列表法在这种情况下会悄悄丢段）")
    finally:
        shutil.rmtree(listdir, ignore_errors=True)
    after = probe(fp, a.out, a.timeout)
    expect = sum(i["duration"] for i in infos)
    if abs(after["duration"] - expect) > 0.1 * len(infos) + 0.2:
        extra.append("警告：拼接后 %s 秒，各段之和 %s 秒，对不上，请检查是否丢段" % (fmt(after["duration"]), fmt(expect)))
    else:
        extra.append("核对：拼接后 %s 秒，各段之和 %s 秒" % (fmt(after["duration"]), fmt(expect)))
    report(infos, after, shown, lossy, extra)
    return 0


def cmd_convert(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    ext = check_out(a.out, [a.input], a.force)
    args = ["-i", a.input, "-vn"] + list(PRESETS[ext])
    extra = []
    if a.asr:
        if ext != ".wav":
            raise ArgError("--asr 输出语音识别用的 16 kHz 单声道 WAV，输出文件请用 .wav")
        args += ["-ar", "16000", "-ac", "1"]
        extra.append("用途：语音识别、转文字（16 kHz 单声道）")
    if info.get("has_video"):
        extra.append("提示：输入里的封面图或视频画面已去掉（-vn）")
    shown, _ = run_ff(ff, args, a.out, a.timeout)
    lossy = True if ext not in (".wav", ".flac") else "否（WAV / FLAC 是无损格式）"
    report([info], probe(fp, a.out, a.timeout), shown, lossy, extra)
    return 0


def cmd_volume(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    mean, peak = volumes(ff, a.input, a.timeout)
    head = -peak
    if a.gain is None:
        print("%s｜平均音量 %s dB｜峰值 %s dB｜最多还能加 %s dB（到 0 dB 为止）"
              % (a.input, fmt(mean), fmt(peak), fmt(max(head, 0))))
        print("要「听起来和别的节目一样响」，用 loudnorm 子命令，而不是一味加分贝")
        return 0
    if not a.out:
        raise ArgError("给了 --gain 就要用 -o 指定输出文件")
    ext = check_out(a.out, [a.input], a.force)
    if a.gain > head and not a.force:
        raise ContentError("要加 %s dB，但峰值 %s dB 只剩 %s dB 余量，会削波破音；把 --gain 降到 %s 以内，"
                           "或改用 loudnorm（确实要加就带 --force）" % (fmt(a.gain), fmt(peak), fmt(head), fmt(head)))
    shown, _ = run_ff(ff, ["-i", a.input, "-vn", "-af", "volume=%sdB" % fmt(a.gain)] + list(PRESETS[ext]),
                      a.out, a.timeout)
    _, new_peak = volumes(ff, a.out, a.timeout)
    report([info], probe(fp, a.out, a.timeout), shown, ext not in (".wav", ".flac") or "否（WAV / FLAC）",
           ["音量：峰值 %s dB → %s dB" % (fmt(peak), fmt(new_peak))])
    return 0


def cmd_loudnorm(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    ext = check_out(a.out, [a.input], a.force)
    base = "loudnorm=I=%s:TP=%s:LRA=%s" % (fmt(a.target), fmt(a.tp), fmt(a.lra))
    extra = []
    if a.two_pass:
        err = analyze(ff, a.input, base + ":print_format=json", a.timeout)
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
        if not m:
            raise FFError("第 1 遍没读到测量结果")
        j = json.loads(m.group(0))
        base += (":measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true"
                 % (j["input_i"], j["input_tp"], j["input_lra"], j["input_thresh"], j["target_offset"]))
        extra.append("第 1 遍测量：I %s｜TP %s｜LRA %s｜thresh %s｜offset %s"
                     % (j["input_i"], j["input_tp"], j["input_lra"], j["input_thresh"], j["target_offset"]))
    # loudnorm 内部按 192 kHz 处理，不写 -ar 输出就是 192 kHz；这里保持原采样率
    rate = str(info["rate"] or 48000)
    shown, _ = run_ff(ff, ["-i", a.input, "-vn", "-af", base, "-ar", rate] + list(PRESETS[ext]), a.out, a.timeout)
    loud = integrated(ff, a.out, a.timeout)
    extra.append("核对：处理后综合响度 I = %s LUFS（目标 %s）" % (fmt(loud) if loud is not None else "?", fmt(a.target)))
    report([info], probe(fp, a.out, a.timeout), shown, ext not in (".wav", ".flac") or "是（响度处理会改变采样值）",
           extra)
    return 0


def cmd_fade(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    ext = check_out(a.out, [a.input], a.force)
    if a.fade_in <= 0 and a.fade_out <= 0:
        raise ArgError("--fade-in 和 --fade-out 至少给一个大于 0 的秒数")
    if a.fade_in + a.fade_out > info["duration"]:
        raise ContentError("淡入 %s 秒加淡出 %s 秒，超过了总时长 %s 秒"
                           % (fmt(a.fade_in), fmt(a.fade_out), fmt(info["duration"])))
    parts = []
    if a.fade_in > 0:
        parts.append("afade=t=in:st=0:d=%s" % fmt(a.fade_in))
    if a.fade_out > 0:
        parts.append("afade=t=out:st=%s:d=%s" % (fmt(info["duration"] - a.fade_out), fmt(a.fade_out)))
    shown, _ = run_ff(ff, ["-i", a.input, "-vn", "-af", ",".join(parts)] + list(PRESETS[ext]), a.out, a.timeout)
    report([info], probe(fp, a.out, a.timeout), shown, ext not in (".wav", ".flac") or "否（WAV / FLAC）",
           ["淡出起点 = 总时长 %s − %s = %s 秒" % (fmt(info["duration"]), fmt(a.fade_out),
                                               fmt(info["duration"] - a.fade_out))] if a.fade_out > 0 else [])
    return 0


def cmd_silence(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    err = analyze(ff, a.input, "silencedetect=noise=%sdB:d=%s" % (fmt(a.noise), fmt(a.min)), a.timeout)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", err)]
    print("%s｜总长 %s 秒｜阈值 %s dB、至少 %s 秒算静音" % (a.input, fmt(info["duration"]), fmt(a.noise), fmt(a.min)))
    if not starts:
        print("没有找到静音段；底噪大的录音把 --noise 调高（如 -40）再试")
        return 0
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else info["duration"]
        print("静音 %d：%s → %s 秒（%s 秒）" % (i + 1, fmt(max(s, 0)), fmt(e), fmt(e - max(s, 0))))
    return 0


def cmd_trim_silence(a, ff, fp):
    info = need_audio(probe(fp, a.input, a.timeout))
    ext = check_out(a.out, [a.input], a.force)
    one = "silenceremove=start_periods=1:start_threshold=%sdB:start_silence=%s" % (fmt(a.noise), fmt(a.keep))
    chain = ",".join([one, "areverse", one, "areverse"])
    shown, _ = run_ff(ff, ["-i", a.input, "-vn", "-af", chain] + list(PRESETS[ext]), a.out, a.timeout)
    after = probe(fp, a.out, a.timeout)
    extra = ["去掉了约 %s 秒首尾静音；反转处理会把整段读进内存，超长录音先分段" % fmt(info["duration"] - after["duration"])]
    if after["duration"] < 0.5:
        extra.append("警告：处理后几乎没剩内容，阈值可能太高，把 --noise 调低（如 -60）再试")
    report([info], after, shown, ext not in (".wav", ".flac") or "否（WAV / FLAC）", extra)
    return 0


def cmd_extract(a, ff, fp):
    info = probe(fp, a.input, a.timeout)
    if not info["has_audio"]:
        raise ContentError("%s 里没有音轨，提取不出声音" % a.input)
    ext = check_out(a.out, [a.input], a.force)
    enc, lossy, note = encode_args(ext, info["codec"], True)
    shown, _ = run_ff(ff, ["-i", a.input, "-vn"] + enc, a.out, a.timeout)
    report([info], probe(fp, a.out, a.timeout), shown, lossy, ["提示：" + note] if note else [])
    return 0


def cmd_batch(a, ff, fp):
    if not os.path.isdir(a.folder):
        raise FileProblem("找不到文件夹：%s" % a.folder)
    ext = "." + a.to.lower().lstrip(".")
    if ext not in PRESETS:
        raise ArgError("--to 只能是 %s" % " ".join(sorted(e[1:] for e in PRESETS)))
    src = "." + a.src.lower().lstrip(".")
    if src == ext:
        raise ArgError("--from 和 --to 相同，不用转")
    files = sorted(f for f in os.listdir(a.folder) if f.lower().endswith(src))
    if not files:
        print("%s 里没有 %s 文件" % (a.folder, src))
        return 0
    done, skipped, failed = [], [], []
    for name in files:
        path = os.path.join(a.folder, name)
        out = os.path.splitext(path)[0] + ext
        if os.path.exists(out):
            skipped.append(name)
            continue
        try:
            run_ff(ff, ["-i", path, "-vn"] + list(PRESETS[ext]), out, a.timeout)
            done.append(name)
        except FFError as exc:
            failed.append("%s（%s）" % (name, exc))
    print("转换 %d 个，跳过已存在的 %d 个，失败 %d 个" % (len(done), len(skipped), len(failed)))
    for f in failed:
        print("失败：" + f)
    print("等效命令（每个文件）：ffmpeg -n -i 原文件%s -vn %s 同名%s" % (src, " ".join(PRESETS[ext]), ext))
    return 4 if failed else 0


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=int, default=1800, help="单次 ffmpeg 的超时秒数，默认 1800")
    outp = argparse.ArgumentParser(add_help=False)
    outp.add_argument("-o", "--out", required=True, help="输出文件，扩展名决定格式")
    outp.add_argument("--force", action="store_true", help="输出已存在时覆盖（原文件永远不覆盖）")
    p = Parser(description="音频剪辑小工具（ffmpeg 包装，带检查）。")
    sub = p.add_subparsers(dest="cmd", parser_class=Parser)
    s = sub.add_parser("probe", parents=[common], help="看文件信息")
    s.add_argument("file")
    s = sub.add_parser("trim", parents=[common, outp], help="裁剪")
    s.add_argument("input")
    s.add_argument("--start", required=True)
    s.add_argument("--end")
    s.add_argument("--length")
    s.add_argument("--exact", action="store_true", help="重编码，时长精确")
    s = sub.add_parser("join", parents=[common, outp], help="拼接")
    s.add_argument("inputs", nargs="+")
    s = sub.add_parser("convert", parents=[common, outp], help="转格式")
    s.add_argument("input")
    s.add_argument("--asr", action="store_true", help="16 kHz 单声道 WAV，给语音识别用")
    s = sub.add_parser("volume", parents=[common], help="检测或调整音量")
    s.add_argument("input")
    s.add_argument("-o", "--out")
    s.add_argument("--gain", type=float, help="要加多少 dB")
    s.add_argument("--force", action="store_true", help="超出余量也照加；输出已存在时覆盖")
    s = sub.add_parser("loudnorm", parents=[common, outp], help="响度标准化")
    s.add_argument("input")
    s.add_argument("--target", type=float, default=-16.0, help="目标综合响度 LUFS，默认 -16")
    s.add_argument("--tp", type=float, default=-1.5, help="真峰值上限，默认 -1.5")
    s.add_argument("--lra", type=float, default=11.0, help="响度范围，默认 11")
    s.add_argument("--two-pass", action="store_true", help="先测量再处理，更准")
    s = sub.add_parser("fade", parents=[common, outp], help="淡入淡出")
    s.add_argument("input")
    s.add_argument("--fade-in", type=float, default=0.0)
    s.add_argument("--fade-out", type=float, default=0.0)
    s = sub.add_parser("silence", parents=[common], help="列出静音段")
    s.add_argument("input")
    s.add_argument("--noise", type=float, default=-50.0, help="静音阈值 dB，默认 -50；底噪大改 -40")
    s.add_argument("--min", type=float, default=0.5, help="至少多少秒算一段静音，默认 0.5")
    s = sub.add_parser("trim-silence", parents=[common, outp], help="去首尾静音")
    s.add_argument("input")
    s.add_argument("--noise", type=float, default=-50.0)
    s.add_argument("--keep", type=float, default=0.2, help="两头各留多少秒，默认 0.2")
    s = sub.add_parser("extract", parents=[common, outp], help="从视频提取音轨")
    s.add_argument("input")
    s = sub.add_parser("batch", parents=[common], help="批量转格式")
    s.add_argument("folder")
    s.add_argument("--to", required=True, help="目标格式，如 mp3")
    s.add_argument("--from", dest="src", default="wav", help="源格式，默认 wav")
    return p


HANDLERS = {"probe": cmd_probe, "trim": cmd_trim, "join": cmd_join, "convert": cmd_convert,
            "volume": cmd_volume, "loudnorm": cmd_loudnorm, "fade": cmd_fade, "silence": cmd_silence,
            "trim-silence": cmd_trim_silence, "extract": cmd_extract, "batch": cmd_batch}


def main(argv=None):
    try:
        a = build_parser().parse_args(argv)
        if not a.cmd:
            raise ArgError("要先写子命令，例如：probe、trim、join、convert、volume、loudnorm、fade")
        if a.timeout <= 0:
            raise ArgError("--timeout 要大于 0")
        ff, fp = tools()
        return HANDLERS[a.cmd](a, ff, fp)
    except (ArgError, FileProblem, ContentError, FFError) as exc:
        label = {1: "参数错误", 2: "文件问题", 3: "不能这样处理", 4: "ffmpeg 出错"}[exc.code]
        print("%s：%s" % (label, exc), file=sys.stderr)
        if exc.code == 1:
            print("用法：python3 audio_tool.py <子命令> -h 查看某个子命令的参数", file=sys.stderr)
        return exc.code
    except OSError as exc:
        print("文件问题：%s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断：临时文件已清理，原文件没有改动。", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
