#!/usr/bin/env python3
"""合并几个搜索词的 SkillHub 结果，去掉补位条目，附平台安全报告状态（只读）。

只调用 skillhub 的两个只读子命令：search 与 skill reports；不安装、不发布、不评论。
每次调用有超时，失败最多重试 2 次；只用 Python 标准库。

用法：
  python3 skill_candidates.py 请假条 请假申请 请假
  python3 skill_candidates.py 会议纪要 录音转写 --no-reports      # 不查安全报告，更快
  python3 skill_candidates.py 周报 工作汇报 --out 候选.md
退出码：0 成功（含「没找到匹配的技能」）；1 参数错误；2 没装 skillhub 或写文件失败；
        3 所有搜索都失败（网络或平台问题，重试后仍失败）；130 用户中断
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

RETRIES = 2          # 失败后最多再试 2 次
BACKOFF = (2, 4)     # 两次重试前分别等待的秒数
CALL_TIMEOUT = 60    # 单次调用 skillhub 的超时（秒）


class ArgError(Exception):
    pass


class HubError(Exception):
    """重试后仍失败。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgError(message)


def hub(binary, args):
    """调用一次 skillhub 只读子命令，返回解析后的 JSON；「No skills found.」返回空结果。

    超时、社区源请求失败、返回不是 JSON 时重试；HTTP 4xx（如技能不存在）不重试。
    """
    cmd = [binary, "--skip-self-upgrade"] + args + ["--json"]
    last = ""
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(BACKOFF[attempt - 1])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=CALL_TIMEOUT)
        except subprocess.TimeoutExpired:
            last = "超过 %d 秒没有返回" % CALL_TIMEOUT
            continue
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        community_failed = "community: search request failed" in err
        if out.startswith("{"):
            try:
                data = json.loads(out)
            except ValueError:
                last = "返回的 JSON 不完整"
                continue
            warnings = " ".join(str(w) for w in data.get("warnings") or [])
            if "community: search request failed" in warnings:
                last = "社区源搜索请求失败"
                continue
            return data
        if out.startswith("No skills found"):
            if community_failed:
                last = "社区源搜索请求失败"
                continue
            return {"results": []}
        last = (err or out or "退出码 %d" % r.returncode).splitlines()[-1]
        if "(HTTP 4" in last:  # 例如技能不存在：重试也没用
            break
    raise HubError(last or "没有输出")


def report_status(binary, item):
    ns = item.get("namespace") or {}
    handle = ns.get("handle") if isinstance(ns, dict) else None
    name = item.get("publicSlug") or item.get("slug", "").split("/")[-1]
    if not handle:
        return "查不到（不是社区源条目）", False
    try:
        rep = hub(binary, ["skill", "reports", name, "--namespace", handle])
    except HubError as exc:
        return "查不到（%s）" % exc, False
    reports = rep.get("reports") if isinstance(rep, dict) else None
    if not isinstance(reports, dict) or not reports:
        return "查不到", False
    parts = ["%s %s" % (r.get("name", "?"), r.get("status") or "无状态") for r in reports.values()]
    ok = len(reports) >= 2 and all(r.get("status") == "benign" for r in reports.values())
    return "；".join(parts), ok


def build(binary, words, limit, with_reports):
    found = {}
    failed, empty = [], []
    for word in words:
        try:
            data = hub(binary, ["search", word, "--search-limit", str(limit)])
        except HubError as exc:
            failed.append("%s（%s）" % (word, exc))
            continue
        hits = 0
        for item in data.get("results", []) if isinstance(data, dict) else []:
            text = (item.get("name", "") + item.get("description", "")).lower()
            if word.lower() not in text:  # 名字和描述都不含搜索词的是补位条目
                continue
            hits += 1
            found.setdefault(item.get("slug", ""), [item, []])[1].append(word)
        if not hits:
            empty.append(word)
    if failed and len(failed) == len(words):
        raise HubError("所有搜索词都没搜成功：" + "；".join(failed))

    out = ["# 技能候选（搜索词：%s）" % " / ".join(words), ""]
    out.append("去掉补位条目后共 %d 个候选；安全报告：%s" % (len(found), "已查" if with_reports else "未查（--no-reports）"))
    authors = {}
    def in_name(item, word):
        return word.lower() in (item.get("name") or "").lower()

    # 排序：命中的词多的在前；同样多时，名字里就含搜索词的（专做这件事）排在只在描述里提到的前面
    ranked = sorted(found.items(), key=lambda kv: (-len(kv[1][1]),
                                                    -sum(in_name(kv[1][0], w) for w in kv[1][1]),
                                                    kv[1][0].get("name", "")))
    for i, (slug, (item, hit_words)) in enumerate(ranked, 1):
        desc = " ".join((item.get("description") or "").split())
        if len(desc) > 150:
            desc = desc[:150] + "…"
        marks = "/".join("%s（%s）" % (w, "名字" if in_name(item, w) else "描述") for w in hit_words)
        out.append("")
        out.append("%d. %s｜%s｜v%s｜命中：%s" % (i, slug, item.get("name", ""), item.get("version", "?"), marks))
        if with_reports:
            status, ok = report_status(binary, item)
            out.append("   安全报告：%s → %s" % (status, "两项都是 benign，可以做首选" if ok else "不进首选"))
        out.append("   描述：%s" % desc)
        ns = item.get("namespace") or {}
        handle = ns.get("handle") if isinstance(ns, dict) else None
        if handle:
            authors.setdefault(handle, []).append(slug)
    tips = []
    if not found:
        tips.append("没找到匹配的技能：换同义词、上位词再搜一轮；仍然没有就如实告诉用户")
    for w in empty:
        if found:
            tips.append("「%s」只剩补位条目，可以换同义词或上位词" % w)
    for w in failed:
        tips.append("这个词没搜成功，稍后重试：%s" % w)
    for handle, slugs in authors.items():
        if len(slugs) > 1:
            tips.append("同一作者 %s 有 %d 个候选（%s），几乎相同的只取一个比较" % (handle, len(slugs), "、".join(slugs)))
    if tips:
        out += ["", "提示："] + ["- " + t for t in tips]
    return "\n".join(out) + "\n"


def write_atomic(path, content):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".md", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None):
    p = Parser(description="合并几个搜索词的 SkillHub 候选，去掉补位条目，附安全报告状态（只读）。")
    p.add_argument("words", nargs="*", help="2–4 个名词搜索词，如：请假条 请假申请 请假")
    p.add_argument("--limit", type=int, default=10, help="每个词取多少条结果，默认 10")
    p.add_argument("--no-reports", action="store_true", help="不查平台安全报告")
    p.add_argument("--out", help="写入这个 Markdown 文件（默认打印到屏幕）")
    try:
        a = p.parse_args(argv)
        words = [w.strip() for w in a.words if w.strip()]
        if not words:
            raise ArgError("至少给一个搜索词（名词，不要动词短语），例如：请假条 请假申请 请假")
        if len(words) > 6:
            raise ArgError("搜索词最多 6 个，建议 2–4 个")
        if not 1 <= a.limit <= 50:
            raise ArgError("--limit 要在 1 到 50 之间")
    except ArgError as exc:
        print("参数错误：%s\n用法：python3 skill_candidates.py 请假条 请假申请 请假 [--no-reports]" % exc,
              file=sys.stderr)
        return 1
    binary = shutil.which("skillhub")
    if not binary:
        print("找不到 skillhub 命令：请先按 SkillHub 官方说明安装 CLI，或确认它在 PATH 里。", file=sys.stderr)
        return 2
    try:
        report = build(binary, words, a.limit, not a.no_reports)
    except HubError as exc:
        print("搜索失败（已重试 %d 次）：%s。检查网络后稍后再试。" % (RETRIES, exc), file=sys.stderr)
        return 3
    if a.out:
        try:
            write_atomic(a.out, report)
        except OSError as exc:
            print("写不了输出文件 %s：%s" % (a.out, exc.strerror or exc), file=sys.stderr)
            return 2
        print("已写入 %s" % a.out)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断，没有安装或改动任何东西。", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
