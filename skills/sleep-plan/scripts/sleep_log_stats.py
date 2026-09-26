#!/usr/bin/env python3
"""睡眠日志统计：读 sleep_log.csv，算平均卧床、平均睡着、睡眠效率、起床时间最早与最晚之差，
逐条对照第 14 天复盘规则，并列出睡得最差的三晚供复盘。只算数、对规则，不做任何诊断。只用标准库。

用法：
  python3 sleep_log_stats.py sleep_log.csv
表头（前 6 列必填）：date,bed,latency,waso,wake,up,nap,caffeine_last,screen_off,energy
  时间写 24 小时制 HH:MM；latency、waso、nap 是分钟数；energy 是白天精神 1–5 分。

退出码：0 成功；1 表头或内容有误（没有一行能算）；2 读不了文件；130 被 Ctrl+C 中断。
"""
import argparse
import csv
import io
import re
import sys

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_INTERRUPTED = 0, 1, 2, 130
REQUIRED = ("date", "bed", "latency", "waso", "wake", "up")
TIME_RE = re.compile(r"^\s*(\d{1,2})[:：](\d{2})\s*$")


class RowError(Exception):
    """某一行数据有问题：跳过这一行并说明原因。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse 默认用退出码 2，这里统一成 1
        self.print_usage(sys.stderr)
        self.exit(EXIT_ARGS, "参数错误：%s\n完整用法：python3 sleep_log_stats.py --help\n" % message)


def mins(value, field):
    m = TIME_RE.match(value or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise RowError("%s=%r 不是 24 小时制 HH:MM" % (field, value))
    return int(m.group(1)) * 60 + int(m.group(2))


def number(value, field, lo=0, hi=24 * 60):
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise RowError("%s=%r 不是数字" % (field, value))
    if not lo <= n <= hi:
        raise RowError("%s=%r 超出合理范围 %g–%g" % (field, value, lo, hi))
    return n


def parse_row(r):
    bed = mins(r["bed"], "bed")
    wake = mins(r["wake"], "wake")
    up = mins(r["up"], "up")
    latency = number(r["latency"], "latency")
    waso = number(r["waso"], "waso")
    wake_abs = wake + (1440 if wake < bed else 0)
    up_abs = up + (1440 if up < bed else 0)
    if up_abs < wake_abs:
        raise RowError("下床时间 up 早于最终醒来 wake")
    tib = up_abs - bed
    tst = wake_abs - bed - latency - waso
    if tib > 16 * 60:
        raise RowError("卧床超过 16 小时，可能把上午下午写反了")
    if tst <= 0:
        raise RowError("入睡用时加夜里醒着的时间，超过了从上床到最终醒来的时间")
    energy = None
    if (r.get("energy") or "").strip():
        energy = number(r["energy"], "energy", 1, 5)
    return {"date": r["date"], "tib": tib, "tst": tst, "up": up, "latency": latency,
            "nap": (r.get("nap") or "").strip() or "—",
            "caffeine_last": (r.get("caffeine_last") or "").strip() or "—",
            "screen_off": (r.get("screen_off") or "").strip() or "—",
            "energy": energy}


def read_rows(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except FileNotFoundError:
        raise OSError("找不到文件：%s（日志要先存成 CSV，第一行是表头）" % path)
    except UnicodeDecodeError:
        raise OSError("%s 不是 UTF-8 文本：用表格软件另存为「CSV UTF-8」再试" % path)
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ValueError("表头缺少 %s；第一行应为 date,bed,latency,waso,wake,up,nap,caffeine_last,screen_off,energy"
                         % "、".join(missing))
    rows = []
    for r in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in r.items()})
    return rows


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0],
                epilog="退出码：0 成功；1 表头或内容有误；2 读不了文件；130 中断")
    ap.add_argument("csv", help="睡眠日志 CSV，例如 sleep_log.csv")
    a = ap.parse_args(argv)

    try:
        raw = read_rows(a.csv)
    except ValueError as e:
        sys.stderr.write("输入有误：%s\n" % e)
        return EXIT_ARGS
    except OSError as e:
        sys.stderr.write("文件错误：%s\n" % e)
        return EXIT_IO

    rows, skipped = [], []
    for no, r in enumerate(raw, 2):  # 第 1 行是表头
        if not any(r.values()):
            continue
        try:
            rows.append(parse_row(r))
        except RowError as e:
            skipped.append("第 %d 行（%s）已跳过：%s" % (no, r.get("date") or "无日期", e))
    for s in skipped:
        print("注意：" + s)
    if not rows:
        sys.stderr.write("输入有误：没有一行能计算，按上面的提示改好再运行\n")
        return EXIT_ARGS

    n = len(rows)
    tib = sum(r["tib"] for r in rows)
    tst = sum(r["tst"] for r in rows)
    eff = 100.0 * tst / tib
    ups = [r["up"] for r in rows]
    spread = max(ups) - min(ups)
    energies = [r["energy"] for r in rows if r["energy"] is not None]
    avg_energy = sum(energies) / len(energies) if energies else None

    print("有效记录 %d 天%s" % (n, "（跳过 %d 行）" % len(skipped) if skipped else ""))
    print("平均卧床 %.1f 小时，平均睡着 %.1f 小时" % (tib / n / 60, tst / n / 60))
    print("睡眠效率 %.0f%%，起床时间最早与最晚相差 %d 分钟" % (eff, spread))
    if avg_energy is not None:
        print("白天精神平均 %.1f 分（1–5）" % avg_energy)
    if n < 7:
        print("记录只有 %d 天，下面的对照只作参考；记满 14 天再下结论" % n)

    print("\n对照第 14 天复盘规则（睡眠效率 = 睡着时间 ÷ 卧床时间；85% 是常用参考线，不是诊断标准）")
    hits = []
    if spread > 60:
        hits.append("第 1 条：起床时间相差超过 60 分钟 → 下两周只做一件事：把起床时间钉住")
    if avg_energy is None:
        hits.append("没有白天精神（energy）数据：第 2、4 条要看白天精神，请自己对照")
    if eff >= 85 and (avg_energy is None or avg_energy >= 3):
        hits.append("第 2 条：效率 ≥ 85%%%s → 保持；想多睡就把上床提前 15 分钟，观察一周再动"
                    % ("，白天精神 ≥ 3 分" if avg_energy is not None else ""))
    if eff < 85:
        hits.append("第 3 条：效率 < 85%，躺着清醒的时间多 → 不提前上床，严格执行「困了再上床」「睡不着就起来」")
    if tst / n >= 7 * 60 and avg_energy is not None and avg_energy < 3:
        hits.append("第 4 条：平均睡着已够 7 小时，白天精神仍低于 3 分（按「常犯困」近似）→ 这不是作息能解决的，建议就医")
    if not any(h.startswith("第") for h in hits):
        hits.append("四条规则都没有完全对上，不硬套：下两周继续钉住起床时间、照常记日志，再复盘一次；"
                    "白天控制不住地犯困，请就医")
    for h in hits:
        print("  · " + h)

    worst = sorted(rows, key=lambda r: r["tst"] / r["tib"])[:3]
    print("\n睡得最差的 %d 晚（按当晚效率），看当天有没有破例：" % len(worst))
    print("  日期      效率  入睡  午睡  最后咖啡因  放下手机")
    for r in worst:
        print("  %-8s %4.0f%%  %4.0f  %4s  %-10s  %s" % (r["date"], 100.0 * r["tst"] / r["tib"], r["latency"],
                                                      r["nap"], r["caffeine_last"], r["screen_off"]))
    print("\n只算数、对规则，不判断是不是失眠症或别的疾病；持续失眠、打鼾憋气、白天控制不住地睡着，请就医。")
    return EXIT_OK


def run():
    try:
        return main()
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C）。\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(run())
