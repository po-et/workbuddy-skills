#!/usr/bin/env python3
"""把存量界面文案里的典型坏句捞出来，对应到 20 条自查清单的条目号。
纯标准库，不联网，只读不写。命中不等于一定错，逐条人工判断。

用法：
  python3 scripts/copy_lint.py locales/                      # 扫目录（默认只看常见文案文件）
  python3 scripts/copy_lint.py src/i18n/zh-CN.json           # 扫单个文件
  python3 scripts/copy_lint.py locales/ --ext .json,.yaml    # 只看这些扩展名
  python3 scripts/copy_lint.py locales/ --json               # 机器可读输出

退出码：
  0   没发现典型坏句
  3   发现需要改的文案（不是程序出错），逐条看建议
  1   参数不对
  2   路径不存在或全部文件都读不了
  130 用户按 Ctrl+C 中断
"""
import argparse
import json
import os
import re
import sys

EXIT_OK, EXIT_ARGS, EXIT_IO, EXIT_REVIEW, EXIT_INTERRUPT = 0, 1, 2, 3, 130
DEFAULT_EXT = (".json", ".yaml", ".yml", ".properties", ".strings", ".po", ".xml", ".arb",
               ".xliff", ".xlf", ".resx", ".csv", ".ts", ".tsx", ".js", ".jsx", ".vue",
               ".md", ".txt", ".html")
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "vendor", ".next"}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FINDINGS_SHOWN = 200

# (正则, 自查条目号, 问题, 建议)
RULES = [
    (r"操作成功|Success!", 19, "零信息的成功提示",
     "写出成了什么、结果在哪：已发送给小王，可在「已发送」中查看"),
    (r"操作失败", 19, "只说失败不说原因和办法", "写发生了什么 + 怎么办"),
    (r"系统异常|请稍后再试|Something went wrong|try again later", 19, "零信息的报错",
     "说清发生了什么、用户现在能做什么；拿不到原因就给可执行的下一步"),
    (r"非法|您输入有误|输入有误|违规操作|Invalid\b", 9, "责怪用户 / 系统视角的词",
     "直接说正确格式：请输入 11 位手机号 / Enter an 11-digit phone number"),
    (r"暂无数据|No data\b", 5, "空状态没说为什么、没给出路",
     "原因 + 一个能点的下一步：还没有项目。新建一个……[新建项目]"),
    (r"确定要执行|此操作|Are you sure", 12, "确认弹窗没写具体动作和对象",
     "标题写动作 + 对象：删除「年度预算」？主按钮重复这个动词"),
    (r"点击这里|Click here", 1, "按钮/链接没说点了会发生什么", "动词 + 对象：下载发票 / Download invoice"),
    (r"错误码|Error\s?\d{3}\b", 8, "只有错误码", "错误码之外写发生了什么和怎么办，错误码可放在末尾供客服排查"),
]
COMPILED = [(re.compile(p, re.I), n, what, fix) for p, n, what, fix in RULES]


class Parser(argparse.ArgumentParser):
    """参数错误按约定返回 1（argparse 默认是 2，和「路径读不了」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_ARGS)


def iter_files(root, exts):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if exts is None or os.path.splitext(name)[1].lower() in exts:
                yield os.path.join(dirpath, name)


def read_text(path):
    """返回 (text, 跳过原因)。读不了不抛异常，交给调用方汇总。"""
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None, "超过 2MB，跳过（大文件多半不是文案资源）"
        with open(path, "rb") as f:
            data = f.read()
    except PermissionError:
        return None, "没有读取权限"
    except OSError as e:
        return None, "读取失败：%s" % e
    if b"\x00" in data[:4096]:
        return None, "二进制文件，跳过"
    for enc in ("utf-8-sig", "gbk"):
        try:
            return data.decode(enc), None
        except UnicodeDecodeError:
            continue
    return None, "编码认不出来（不是 UTF-8 也不是 GBK），请转成 UTF-8"


def scan(paths, exts):
    findings, skipped, scanned = [], [], 0
    for root in paths:
        for path in iter_files(root, exts):
            text, why = read_text(path)
            if text is None:
                skipped.append((path, why))
                continue
            scanned += 1
            for no, line in enumerate(text.splitlines(), 1):
                for rx, item, what, fix in COMPILED:
                    m = rx.search(line)
                    if m:
                        snippet = line.strip()
                        if len(snippet) > 80:
                            snippet = snippet[:77] + "..."
                        findings.append({"file": path, "line": no, "item": item, "hit": m.group(0),
                                         "problem": what, "fix": fix, "text": snippet})
    return findings, skipped, scanned


def main(argv=None):
    ap = Parser(description="界面文案坏句扫描（对应 20 条自查清单）")
    ap.add_argument("paths", nargs="+", help="文案目录或文件，如 locales/ 或 zh-CN.json")
    ap.add_argument("--ext", help="只扫这些扩展名，逗号分隔，如 .json,.yaml；写 all 表示不限")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        sys.stderr.write("路径不存在：%s。把 locales/ 换成你们放文案的目录。\n" % "、".join(missing))
        return EXIT_IO
    if args.ext is None:
        exts = set(DEFAULT_EXT)
    elif args.ext.strip().lower() == "all":
        exts = None
    else:
        exts = {e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
                for e in args.ext.split(",") if e.strip()}
        if not exts:
            ap.error("--ext 至少写一个扩展名，如 .json")

    findings, skipped, scanned = scan(args.paths, exts)
    if scanned == 0:
        why = "；".join("%s（%s）" % s for s in skipped[:5]) or "目录里没有匹配扩展名的文件"
        sys.stderr.write("一个文件都没扫到：%s。可用 --ext all 放开扩展名限制。\n" % why)
        return EXIT_IO

    if args.json:
        print(json.dumps({"scanned": scanned, "skipped": skipped, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        print("扫描 %d 个文件，命中 %d 处（跳过 %d 个）" % (scanned, len(findings), len(skipped)))
        for f in findings[:MAX_FINDINGS_SHOWN]:
            print("%s:%d  [自查第 %d 条·%s]「%s」→ %s\n    原文：%s"
                  % (f["file"], f["line"], f["item"], f["problem"], f["hit"], f["fix"], f["text"]))
        if len(findings) > MAX_FINDINGS_SHOWN:
            print("……其余 %d 处用 --json 查看" % (len(findings) - MAX_FINDINGS_SHOWN))
        for path, why in skipped[:10]:
            print("跳过 %s：%s" % (path, why))
        if findings:
            by_item = {}
            for f in findings:
                by_item[f["item"]] = by_item.get(f["item"], 0) + 1
            print("按自查条目汇总：" + "，".join("第 %d 条 %d 处" % kv for kv in sorted(by_item.items())))
            print("命中不等于一定错：先看上下文，再按 references/checklist-20.md 对应条目改。")
    return EXIT_REVIEW if findings else EXIT_OK


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断（Ctrl+C），没有做任何改动。\n")
        sys.exit(EXIT_INTERRUPT)
