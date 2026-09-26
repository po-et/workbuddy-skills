#!/usr/bin/env python3
"""视频抽帧：把 SKILL.md 里的 ffmpeg/ffprobe 命令包成一条命令，并自动做三件事——
建输出目录、拒绝悄悄覆盖旧图、核对张数并生成「文件名—时间点」对照表（index.csv）。

用法：
  python3 frames.py probe in.mp4                                  # 时长、帧率、宽高、旋转、是否 10-bit/HDR
  python3 frames.py shot in.mp4 --at 00:01:23.5                   # 单张（-ss 放在 -i 前），默认 cover.jpg
  python3 frames.py pick in.mp4 --start 60 --duration 20          # 在一段里挑代表帧做封面
  python3 frames.py interval in.mp4 --every 5                     # 每 5 秒一张，宽 768，第 k 张 = 第 k×5 秒
  python3 frames.py interval in.mp4 --count 12                    # 按总时长均分 12 张（给 AI 看常用）
  python3 frames.py keyframes in.mp4                              # 只抽关键帧
  python3 frames.py scene in.mp4 --threshold 0.3                  # 场景变化抽帧（连第一帧）
  python3 frames.py sheet in.mp4 --cols 4 --rows 3                # 缩略图拼图
  python3 frames.py gif in.mp4 --start 10 --duration 3            # 调色板两步法转 GIF
通用选项：--overwrite 允许覆盖同名输出；--dry-run 只打印命令不执行；--timeout 秒（默认 1800）。

退出码：0 成功；1 参数错误（含时间点超出视频长度）；2 输入或输出文件问题（不存在、不是视频、输出已存在、
        目录建不了）；3 找不到 ffmpeg/ffprobe；4 ffmpeg 执行失败或超时；5 执行完但没有产出图片；130 Ctrl+C 中断。
只用 Python 标准库（Python 3.8+），外加本技能本来就依赖的 ffmpeg/ffprobe。
"""
import argparse
import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SEQ = {"interval": ("frames", "f_"), "keyframes": ("key", "k_"), "scene": ("scene", "s_")}


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(1)


class Fail(Exception):
    def __init__(self, message, code):
        Exception.__init__(self, message)
        self.code = code


def parse_time(text):
    """83.5、1:23.5、00:01:23.5 都认，返回秒数。"""
    if not re.match(r"^\d+(:\d{1,2}){0,2}(\.\d+)?$", text or ""):
        raise ValueError(text)
    sec = 0.0
    for part in text.split(":"):
        sec = sec * 60 + float(part)
    return sec


def timecode(sec):
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return "%02d:%02d:%06.3f" % (h, m, s)


def need_tools(names):
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        raise Fail("没找到 %s。请用户从官方渠道安装后重试（本工具不代装）；装好后 `ffmpeg -version` 能打印版本即可。"
                   % "、".join(missing), 3)


def run(cmd, timeout, dry):
    print("执行：" + shlex.join(cmd))
    if dry:
        return ""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Fail("超过 %d 秒还没跑完，已停止。长视频可以先用 keyframes 模式，或加大 --timeout。" % timeout, 4)
    err = p.stderr.decode("utf-8", errors="replace")
    if p.returncode != 0:
        tail = [l for l in err.splitlines() if l.strip()][-8:]
        raise Fail("ffmpeg 执行失败（返回码 %d），最后几行报错：\n  %s" % (p.returncode, "\n  ".join(tail)), 4)
    return err


def probe(path, timeout=60):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=width,height,r_frame_rate,nb_frames,pix_fmt,color_transfer:stream_side_data=rotation"
           ":format=duration", "-of", "json", str(path)]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Fail("ffprobe 超过 %d 秒没有返回，文件可能损坏或在网络盘上" % timeout, 4)
    try:
        data = json.loads(p.stdout.decode("utf-8", errors="replace") or "{}")
    except ValueError:
        data = {}
    streams = data.get("streams") or []
    if p.returncode != 0 or not streams:
        raise Fail("读不出视频轨：%s 可能不是视频文件、已损坏或只有音频" % path, 2)
    s = streams[0]
    rotation = 0
    for sd in s.get("side_data_list") or []:
        if "rotation" in sd:
            rotation = int(float(sd["rotation"]))
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError):
        raise Fail("读不出时长（常见于直播录制的裸流）：先转封装成 mp4 再抽帧", 2)
    num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    w, h = int(s.get("width") or 0), int(s.get("height") or 0)
    shown = (h, w) if abs(rotation) in (90, 270) else (w, h)
    return {"duration": duration, "fps": fps, "width": w, "height": h, "rotation": rotation,
            "shown": shown, "pix_fmt": s.get("pix_fmt") or "", "transfer": s.get("color_transfer") or "",
            "nb_frames": s.get("nb_frames") or "?"}


def image_size(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return p.stdout.decode().strip().replace(",", "x") or "?"


def ensure_new(path, overwrite, dry=False):
    if path.exists() and not overwrite:
        raise Fail("%s 已存在。ffmpeg 遇到同名文件会直接放弃且返回 0，所以先停下：换个 --out，或加 --overwrite。"
                   % path, 2)
    if dry:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise Fail("建不了输出目录 %s：%s" % (path.parent, e.strerror or e), 2)


def write_index(out_dir, rows):
    index = out_dir / "index.csv"
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".csv", dir=str(out_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows([("文件", "秒", "时间码")] + rows)
        os.replace(tmp, str(index))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return index


def sequence(a, info):
    default_dir, prefix = SEQ[a.cmd]
    out_dir = Path(a.out_dir or default_dir).expanduser().resolve()
    old = sorted(out_dir.glob(prefix + "*.jpg")) if out_dir.is_dir() else []
    if old and not a.overwrite:
        raise Fail("%s 里已有 %d 张 %s*.jpg（上次的结果？）。ffmpeg 的 -n 挡不住覆盖编号图片，所以先停下："
                   "换一个 --out-dir，或加 --overwrite。" % (out_dir, len(old), prefix), 2)
    if not a.dry_run:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise Fail("建不了输出目录 %s：%s" % (out_dir, e.strerror or e), 2)
    scale = ["scale=%d:-2" % a.width] if a.width else []
    pre, extra = [], []
    if a.cmd == "interval":
        every = info["duration"] / a.count if a.count else a.every
        if every >= info["duration"]:
            print("注意：间隔 %.3g 秒不短于视频时长 %.3g 秒，只会得到 1 张。" % (every, info["duration"]))
        chain = ["fps=1/%s:round=up" % _num(every)] + scale
        extra = ["-start_number", "0"] + (["-frames:v", str(a.count)] if a.count else [])
    elif a.cmd == "keyframes":
        pre = ["-skip_frame", "nokey"]
        chain = scale
        extra = ["-fps_mode", "vfr"]
    else:
        chain = ["select=eq(n\\,0)+gt(scene\\,%s)" % _num(a.threshold)] + scale   # 表达式里的逗号用反斜杠转义，免得再套一层引号
        extra = ["-fps_mode", "vfr"]
    pattern = out_dir / (prefix + "%04d.jpg")
    cmd = (["ffmpeg", "-hide_banner", "-nostats", "-y" if a.overwrite else "-n"] + pre + ["-i", str(a.video),
           "-vf", ",".join(chain + ["showinfo"])] + extra + ["-q:v", "2", str(pattern)])
    err = run(cmd, a.timeout, a.dry_run)
    if a.dry_run:
        return 0
    times = [float(t) for t in re.findall(r"Parsed_showinfo.*?pts_time:\s*([0-9.]+)", err)]
    start = 0 if a.cmd == "interval" else 1
    names = [prefix + "%04d.jpg" % (start + i) for i in range(len(times))]
    made = [n for n in names if (out_dir / n).exists()]
    if not made:
        raise Fail("ffmpeg 跑完了但没有产出图片。检查时间范围和参数；场景抽帧可把 --threshold 调低一些再试。", 5)
    rows = [(n, "%.3f" % t, timecode(t)) for n, t in zip(names, times) if (out_dir / n).exists()]
    index = write_index(out_dir, rows)
    stale = len(sorted(out_dir.glob(prefix + "*.jpg"))) - len(made)
    print("\n共 %d 张，分辨率 %s，目录：%s" % (len(made), image_size(out_dir / made[0]), out_dir))
    print("对照表：%s" % index)
    print("\n| 文件 | 时间点（秒） | 时间码 |\n|---|---|---|")
    for n, t, tc in rows[:30]:
        print("| %s | %s | %s |" % (n, t, tc))
    if len(rows) > 30:
        print("| …共 %d 行，见 index.csv | | |" % len(rows))
    if stale > 0:
        print("\n注意：目录里另有 %d 张同前缀的旧图不是这次生成的，交付前请清理或换目录。" % stale)
    if a.cmd == "scene" and len(made) == 1:
        print("\n只抽到第一帧：画面变化没超过阈值 %s。把 --threshold 调低一些（如 0.2）再试。" % _num(a.threshold))
    elif a.cmd == "scene" and len(made) > 60:
        print("\n抽到 %d 张偏多：把 --threshold 调到 0.4–0.5 再试。" % len(made))
    return 0


def _num(x):
    return ("%.4f" % x).rstrip("0").rstrip(".")


def single(a, info):
    if a.cmd == "shot":
        out = Path(a.out or "cover.jpg").expanduser().resolve()
        at = parse_time(a.at)
        if at >= info["duration"]:
            raise Fail("视频只有 %.2f 秒，--at %s 超出范围" % (info["duration"], a.at), 1)
        ensure_new(out, a.overwrite, a.dry_run)
        q = [] if out.suffix.lower() == ".png" else ["-q:v", "2"]
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y" if a.overwrite else "-n", "-ss", a.at, "-i", str(a.video),
               "-frames:v", "1"] + q + [str(out)]
        note = "时间点 %s（%.3f 秒）" % (a.at, at)
    elif a.cmd == "pick":
        out = Path(a.out or "cover_pick.jpg").expanduser().resolve()
        _check_range(a, info)
        ensure_new(out, a.overwrite, a.dry_run)
        n = max(2, int(round(a.duration * a.rate)))
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y" if a.overwrite else "-n", "-ss", _num(a.start),
               "-t", _num(a.duration), "-i", str(a.video), "-vf", "fps=%s,thumbnail=%d" % (_num(a.rate), n),
               "-frames:v", "1", "-q:v", "2", str(out)]
        note = "从 %s 秒起 %s 秒内按每秒 %s 帧取 %d 帧，挑最有代表性的一张" % (_num(a.start), _num(a.duration), _num(a.rate), n)
    else:
        out = Path(a.out or "sheet.jpg").expanduser().resolve()
        ensure_new(out, a.overwrite, a.dry_run)
        n = a.cols * a.rows
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y" if a.overwrite else "-n", "-i", str(a.video), "-vf",
               "fps=%d/%s,scale=%d:-2,tile=%dx%d:padding=4:margin=4" % (n, _num(info["duration"]), a.width, a.cols, a.rows),
               "-frames:v", "1", "-q:v", "3", str(out)]
        note = "按总时长均分 %d 张，%d×%d 拼成一张" % (n, a.cols, a.rows)
    run(cmd, a.timeout, a.dry_run)
    if a.dry_run:
        return 0
    if not out.exists() or out.stat().st_size == 0:
        raise Fail("ffmpeg 返回成功但没有写出 %s（输出同名文件已存在时就会这样）" % out, 5)
    print("\n输出：%s（%s）；%s" % (out, image_size(out), note))
    return 0


def _check_range(a, info):
    if a.start >= info["duration"]:
        raise Fail("视频只有 %.2f 秒，--start %s 超出范围" % (info["duration"], _num(a.start)), 1)
    if a.start + a.duration > info["duration"]:
        print("注意：%s + %s 秒超过视频结尾，只会取到 %.2f 秒为止。"
              % (_num(a.start), _num(a.duration), info["duration"]))


def gif(a, info):
    out = Path(a.out or "out.gif").expanduser().resolve()
    _check_range(a, info)
    ensure_new(out, a.overwrite, a.dry_run)
    head = ["ffmpeg", "-hide_banner", "-nostats", "-ss", _num(a.start), "-t", _num(a.duration), "-i", str(a.video)]
    base = "fps=%d,scale=%d:-1:flags=lanczos" % (a.fps, a.width)
    use = "paletteuse=dither=bayer:bayer_scale=5" if a.dither == "bayer" else "paletteuse=dither=none"
    with tempfile.TemporaryDirectory(prefix="gif-palette-") as tmp:
        palette = str(Path(tmp) / "palette.png")
        run(head + ["-y", "-vf", base + ",palettegen=stats_mode=diff", palette], a.timeout, a.dry_run)
        run(head[:-2] + ["-i", str(a.video), "-i", palette, "-lavfi", "%s[x];[x][1:v]%s" % (base, use),
            "-y" if a.overwrite else "-n", str(out)], a.timeout, a.dry_run)
    if a.dry_run:
        return 0
    if not out.exists() or out.stat().st_size == 0:
        raise Fail("没有写出 %s" % out, 5)
    print("\n输出：%s（%s，%.0f KB）" % (out, image_size(out), out.stat().st_size / 1024))
    print("太大就按这个顺序减：缩短 --duration → --fps 8 到 10 → --width 320 → --dither none")
    return 0


def show_probe(info):
    w, h = info["width"], info["height"]
    print("时长 %.3f 秒；帧率 %.3f；存储宽高 %dx%d；旋转 %d；实际画面 %dx%d；像素格式 %s；帧数 %s"
          % (info["duration"], info["fps"], w, h, info["rotation"], info["shown"][0], info["shown"][1],
             info["pix_fmt"] or "?", info["nb_frames"]))
    if abs(info["rotation"]) in (90, 270):
        print("提示：竖拍视频。ffmpeg 默认自动转正；缩放只定一边（如 scale=-2:720），不要写死宽高，也别加 -noautorotate。")
    if "10" in info["pix_fmt"] or info["transfer"] in ("smpte2084", "arib-std-b67"):
        print("提示：10-bit 或 HDR 视频，截图可能发灰；需要色调映射时如实告诉用户，不套用未经验证的参数。")


def main(argv=None):
    ap = ArgParser(description="视频抽帧（ffmpeg 包装）：建目录、防覆盖、核对张数、出对照表")
    sub = ap.add_subparsers(dest="cmd")

    def add(name, helptext):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("video", help="视频文件")
        p.add_argument("--overwrite", action="store_true", help="允许覆盖同名输出")
        p.add_argument("--dry-run", action="store_true", help="只打印要执行的命令")
        p.add_argument("--timeout", type=int, default=1800, help="单条 ffmpeg 的超时秒数（默认 1800）")
        return p

    add("probe", "看时长、帧率、宽高、旋转")
    p = add("shot", "某一时间点单张")
    p.add_argument("--at", required=True, help="时间点：83.5、1:23.5 或 00:01:23.5")
    p.add_argument("--out", help="输出文件（默认 cover.jpg；写 .png 为无损）")
    p = add("pick", "在一段里挑代表帧做封面")
    p.add_argument("--start", type=float, required=True, help="起点秒数")
    p.add_argument("--duration", type=float, default=20, help="挑选范围秒数（默认 20）")
    p.add_argument("--rate", type=float, default=2, help="每秒取几帧来挑（默认 2）")
    p.add_argument("--out", help="输出文件（默认 cover_pick.jpg）")
    p = add("interval", "每 N 秒一张，或均分 N 张")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--every", type=float, help="间隔秒数")
    g.add_argument("--count", type=int, help="按总时长均分成几张")
    p.add_argument("--width", type=int, default=768, help="缩放宽度（默认 768；0 表示不缩放）")
    p.add_argument("--out-dir", help="输出目录（默认 frames）")
    p = add("keyframes", "只抽关键帧")
    p.add_argument("--width", type=int, default=0, help="缩放宽度（默认不缩放）")
    p.add_argument("--out-dir", help="输出目录（默认 key）")
    p = add("scene", "场景变化抽帧")
    p.add_argument("--threshold", type=float, default=0.3, help="场景变化阈值 0–1（默认 0.3；抽太多调到 0.4–0.5）")
    p.add_argument("--width", type=int, default=0, help="缩放宽度（默认不缩放）")
    p.add_argument("--out-dir", help="输出目录（默认 scene）")
    p = add("sheet", "缩略图拼图")
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--rows", type=int, default=3)
    p.add_argument("--width", type=int, default=320, help="每格宽度（默认 320）")
    p.add_argument("--out", help="输出文件（默认 sheet.jpg）")
    p = add("gif", "调色板两步法转 GIF")
    p.add_argument("--start", type=float, required=True, help="起点秒数")
    p.add_argument("--duration", type=float, required=True, help="时长秒数")
    p.add_argument("--fps", type=int, default=12, help="帧率（默认 12）")
    p.add_argument("--width", type=int, default=480, help="宽度（默认 480）")
    p.add_argument("--dither", choices=["bayer", "none"], default="bayer")
    p.add_argument("--out", help="输出文件（默认 out.gif）")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.error("请选择子命令，例如：python3 frames.py probe in.mp4")

    if getattr(a, "at", None) is not None:
        try:
            parse_time(a.at)
        except ValueError:
            ap.error("--at「%s」认不出，写成 83.5、1:23.5 或 00:01:23.5" % a.at)
    if getattr(a, "every", None) is not None and a.every <= 0:
        ap.error("--every 要大于 0")
    if getattr(a, "count", None) is not None and not 1 <= a.count <= 1000:
        ap.error("--count 要在 1 到 1000 之间")
    if getattr(a, "threshold", None) is not None and not 0 < a.threshold < 1:
        ap.error("--threshold 要在 0 和 1 之间，常用 0.3–0.5")
    if getattr(a, "width", None) and not 16 <= a.width <= 7680:
        ap.error("--width 要在 16 到 7680 之间（0 表示不缩放）")
    for name in ("start", "duration"):
        v = getattr(a, name, None)
        if v is not None and (v < 0 or (name == "duration" and v <= 0)):
            ap.error("--%s 要是正数" % name)
    if a.cmd == "sheet" and not (1 <= a.cols <= 20 and 1 <= a.rows <= 20):
        ap.error("--cols、--rows 要在 1 到 20 之间")
    if a.cmd == "gif" and not 1 <= a.fps <= 50:
        ap.error("--fps 要在 1 到 50 之间")
    if a.timeout < 10:
        ap.error("--timeout 至少 10 秒")

    try:
        need_tools(["ffmpeg", "ffprobe"])
        a.video = Path(a.video).expanduser()
        if not a.video.is_file():
            raise Fail("找不到视频文件：%s（检查路径；路径里有空格时用引号包起来）" % a.video, 2)
        info = probe(a.video)
        if a.cmd == "probe":
            show_probe(info)
            return 0
        if a.cmd in SEQ:
            return sequence(a, info)
        if a.cmd == "gif":
            return gif(a, info)
        return single(a, info)
    except Fail as e:
        print(str(e), file=sys.stderr)
        return e.code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断（Ctrl+C）。输出目录里可能留有部分图片，重跑前换目录或加 --overwrite。", file=sys.stderr)
        sys.exit(130)
