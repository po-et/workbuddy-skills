#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业微信群机器人发送脚本：默认只预览（dry-run），加 --send 才真正发送。

- key 只从环境变量读（默认 WECOM_BOT_KEY；可以存 key 本身，也可以存完整 webhook 地址）；
  任何输出都只显示 key 的最后 4 位。
- 支持 text（可 @手机号）与 markdown 两种消息；超时 + 最多 2 次重试；解析 errcode 并给中文解释。
- --selftest 在本机起假接收端（fake_webhook_server.py）跑一遍全部分支，不访问外网。

示例：
  python3 wecom_bot_send.py --type text --content "今晚 22:00 发布" --at-mobile 13800000000
  python3 wecom_bot_send.py --type markdown --file daily.md          # 先看预览
  python3 wecom_bot_send.py --type markdown --file daily.md --send   # 确认后再发
  python3 wecom_bot_send.py --selftest

退出码：0 成功或预览完成；1 参数错误；2 文件读写错误；3 网络失败/超时/HTTP 非 200（已按规则重试）；
        4 接口返回 errcode≠0 或返回非 JSON；5 自测未通过；130 用户中断。
"""

import argparse
import http.client
import io
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True  # --selftest 会导入同目录模块，不留 __pycache__

DEFAULT_ENDPOINT = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
OFFICIAL_HOST = "qyapi.weixin.qq.com"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
DEFAULT_KEY_ENV = "WECOM_BOT_KEY"
# 据公开文档的内容长度上限（UTF-8 字节）；以官方文档为准。超出只提示，不拦截。
SOFT_LIMIT_BYTES = {"text": 2048, "markdown": 4096}
MAX_RETRIES = 2

EXIT_OK, EXIT_ARGS, EXIT_FILE, EXIT_NET, EXIT_API, EXIT_SELFTEST, EXIT_INT = 0, 1, 2, 3, 4, 5, 130

# 只收录含义确定的通用错误码；其余一律提示以官方文档为准。
ERRCODE_HINTS = {
    0: "成功",
    -1: "系统繁忙（通用含义）：稍后重试；持续出现就暂停发送",
    45009: "调用频率超限：合并消息、降低频率，稍等再发；具体限额以官方文档为准",
    93000: "webhook 地址无效：常见于 key 抄错或不完整、机器人已被移除；核对环境变量，必要时重新添加机器人",
}
RETRY_ERRCODES = (-1,)  # 45009 不自动重试：立刻重发只会继续超限


class UserError(Exception):
    def __init__(self, message, code=EXIT_ARGS):
        Exception.__init__(self, message)
        self.code = code


class HttpStatusError(Exception):
    def __init__(self, status):
        Exception.__init__(self, "HTTP %d" % status)
        self.status = status


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_ARGS)


def mask(value):
    value = value or ""
    return "****" + value[-4:] if len(value) > 4 else "****"


def resolve_key(raw):
    """环境变量里可以是 key，也可以是完整 webhook 地址；返回 key 本身。"""
    raw = (raw or "").strip().strip("'\"")
    if not raw:
        return ""
    if raw.lower().startswith(("http://", "https://")):
        keys = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("key") or []
        if not keys or not keys[0].strip():
            raise UserError("环境变量里是一个网址，但没有 key= 参数；请复制完整的 webhook 地址或只放 key")
        raw = keys[0].strip()
    if not re.match(r"^[A-Za-z0-9_-]{8,128}$", raw):
        raise UserError("环境变量里的 key 格式不对（含空格、中文、引号或长度异常），请重新复制")
    return raw


def parse_mobiles(values):
    out = []
    for chunk in values or []:
        for item in re.split(r"[,，、;；\s]+", chunk):
            item = item.strip()
            if not item:
                continue
            if item.lower() == "@all":
                item = "@all"
            else:
                raw_item = item
                item = re.sub(r"[-\s]", "", item)
                if not re.match(r"^\+?\d{5,20}$", item):
                    raise UserError("手机号格式不对：%r（只写数字，多个用逗号分隔；@all 表示所有人，慎用）" % raw_item)
            if item not in out:
                out.append(item)
    return out


def read_content(args):
    if args.content is not None and args.file:
        raise UserError("--content 和 --file 只能二选一")
    if args.file:
        try:
            if args.file == "-":
                text = sys.stdin.read()
            else:
                with open(args.file, "r", encoding="utf-8-sig") as fh:
                    text = fh.read()
        except FileNotFoundError:
            raise UserError("找不到文件：%s" % args.file, EXIT_FILE)
        except UnicodeDecodeError:
            raise UserError("文件不是 UTF-8 编码：%s（用编辑器另存为 UTF-8 再试）" % args.file, EXIT_FILE)
        except OSError as exc:
            raise UserError("读取文件失败：%s（%s）" % (args.file, exc), EXIT_FILE)
    elif args.content is not None:
        text = args.content
    else:
        raise UserError("缺少消息内容：用 --content \"...\" 或 --file 路径（多行内容建议用 --file）")
    text = text.replace("\r\n", "\n").strip("\n")
    if not text.strip():
        raise UserError("消息内容为空")
    return text


def check_endpoint(endpoint):
    """只允许官方地址或本机地址，防止把 key 发到别处。返回是否本机。"""
    u = urllib.parse.urlparse(endpoint)
    host = (u.hostname or "").lower()
    if u.query:
        raise UserError("--endpoint 不要带 ?key=，key 只从环境变量读")
    if u.scheme == "https" and host == OFFICIAL_HOST:
        return False
    if u.scheme in ("http", "https") and host in LOCAL_HOSTS:
        return True
    raise UserError("--endpoint 只允许企业微信官方地址或本机地址（127.0.0.1/localhost，用于假接收端测试）")


def build_payload(msg_type, content, mobiles):
    if msg_type == "text":
        body = {"content": content}
        if mobiles:
            body["mentioned_mobile_list"] = mobiles
        return {"msgtype": "text", "text": body}
    return {"msgtype": "markdown", "markdown": {"content": content}}


def explain(errcode):
    if errcode in ERRCODE_HINTS:
        return ERRCODE_HINTS[errcode]
    return "未收录的错误码：含义以官方文档为准（企业微信开发者中心「全局错误码」）"


def do_post(opener, url, data, timeout):
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read()
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        finally:
            exc.close()
        raise HttpStatusError(exc.code)
    if status != 200:
        raise HttpStatusError(status)
    return body


def describe_net_error(exc):
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason):
        return "超时"
    return "网络错误：%s" % reason


def print_preview(out, args, key, key_env, endpoint, payload, content, mobiles):
    limit = SOFT_LIMIT_BYTES[args.type]
    size = len(content.encode("utf-8"))
    title = "预览（DRY-RUN，未发送；确认无误后加 --send）" if not args.send else "即将发送"
    out.write("== %s ==\n" % title)
    out.write("目标地址：%s?key=%s\n" % (endpoint, mask(key) if key else "（未设置）"))
    out.write("key 来源：环境变量 %s%s\n" % (key_env, "" if key else "（未设置，预览可继续，真正发送前需要设置）"))
    out.write("消息类型：%s\n" % args.type)
    if mobiles:
        out.write("@手机号：%s（%d 个）\n" % ("、".join(mobiles), len(mobiles)))
    out.write("内容字节：%d / 参考上限 %d（据公开文档，以官方文档为准）\n" % (size, limit))
    if size > limit:
        out.write("! 注意：内容可能超出上限被拒绝或截断，建议拆成多条或精简\n")
    out.write("正文：\n")
    for line in content.split("\n"):
        out.write("  │ %s\n" % line)
    out.write("请求体：\n%s\n" % json.dumps(payload, ensure_ascii=False, indent=2))


def send_flow(args, env, out, err):
    key_env = args.key_env
    key = resolve_key(env.get(key_env, ""))
    content = read_content(args)
    mobiles = parse_mobiles(args.at_mobile)
    if args.type == "markdown" and mobiles:
        raise UserError("据官方文档，markdown 消息只有 content 字段、不支持 @手机号（以文档为准）。"
                        "需要 @ 人：改用 --type text，或先发 markdown 再补一条带 --at-mobile 的 text")
    local = check_endpoint(args.endpoint)
    if not (0 <= args.retries <= MAX_RETRIES):
        raise UserError("--retries 只能是 0–%d" % MAX_RETRIES)
    if not (0.1 <= args.timeout <= 60):
        raise UserError("--timeout 取 0.1–60 秒")
    if not (0 <= args.backoff <= 10):
        raise UserError("--backoff 取 0–10 秒")

    payload = build_payload(args.type, content, mobiles)
    print_preview(out, args, key, key_env, args.endpoint, payload, content, mobiles)
    if not args.send:
        out.write("DRY-RUN：没有发送任何请求。\n")
        return EXIT_OK
    if not key:
        raise UserError("没有找到环境变量 %s。请先在终端执行：export %s='<群机器人的 key 或完整 webhook 地址>'"
                        "（不要写进代码、不要贴到对话里）" % (key_env, key_env))

    url = "%s?key=%s" % (args.endpoint, urllib.parse.quote(key, safe=""))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handlers = [urllib.request.ProxyHandler({})] if local else []  # 本机测试绕过代理
    opener = urllib.request.build_opener(*handlers)

    attempt = 0
    while True:
        attempt += 1
        left = args.retries - (attempt - 1)
        try:
            body = do_post(opener, url, data, args.timeout)
        except HttpStatusError as exc:
            if exc.status >= 500 and left > 0:
                _wait(err, attempt, "HTTP %d" % exc.status, args.backoff, left)
                continue
            out.write("发送失败：HTTP %d（共 %d 次请求）。5xx 已按规则重试；4xx 多为地址写错，核对 --endpoint\n"
                      % (exc.status, attempt))
            return EXIT_NET
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                http.client.HTTPException, OSError) as exc:
            why = describe_net_error(exc)
            if left > 0:
                _wait(err, attempt, why, args.backoff, left)
                continue
            out.write("发送失败：%s（共 %d 次请求）。检查网络/代理，或加大 --timeout；"
                      "注意超时的请求可能其实已送达，重发前先看群里有没有收到\n" % (why, attempt))
            return EXIT_NET

        try:
            result = json.loads(body.decode("utf-8"))
            errcode = int(result.get("errcode"))
        except (UnicodeDecodeError, ValueError, TypeError, AttributeError):
            snippet = body[:200].decode("utf-8", "replace").replace(key, mask(key))
            out.write("发送结果无法解析：返回内容不是预期的 JSON（前 200 字）：%s\n" % snippet)
            return EXIT_API
        if errcode in RETRY_ERRCODES and left > 0:
            _wait(err, attempt, "errcode %d" % errcode, args.backoff, left)
            continue
        errmsg = str(result.get("errmsg", "")).replace(key, mask(key))
        if errcode == 0:
            out.write("结果：errcode=0（成功），共 %d 次请求\n" % attempt)
            return EXIT_OK
        out.write("发送失败：errcode=%d —— %s\nerrmsg 原文：%s\n共 %d 次请求\n"
                  % (errcode, explain(errcode), errmsg, attempt))
        return EXIT_API


def _wait(err, attempt, why, backoff, left):
    delay = backoff * attempt
    err.write("第 %d 次请求失败（%s），%.1f 秒后重试（还可重试 %d 次）\n" % (attempt, why, delay, left))
    err.flush()
    time.sleep(delay)


def build_parser():
    ap = ArgParser(description="企业微信群机器人发送：默认只预览，加 --send 才发送。key 从环境变量读。")
    ap.add_argument("--type", choices=("text", "markdown"), default="text", help="消息类型，默认 text")
    ap.add_argument("--content", help="消息内容（多行建议用 --file）")
    ap.add_argument("--file", help="从 UTF-8 文件读内容；写 - 表示从标准输入读")
    ap.add_argument("--at-mobile", action="append", default=[],
                    help="要 @ 的手机号，多个用逗号分隔，可重复传；仅 text 支持")
    ap.add_argument("--key-env", default=DEFAULT_KEY_ENV, help="存 key 的环境变量名，默认 WECOM_BOT_KEY")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="默认官方地址；只允许改成本机地址做测试")
    ap.add_argument("--send", action="store_true", help="真正发送；不加就只预览")
    ap.add_argument("--timeout", type=float, default=10.0, help="单次请求超时秒数，默认 10")
    ap.add_argument("--retries", type=int, default=MAX_RETRIES, help="失败重试次数 0–2，默认 2")
    ap.add_argument("--backoff", type=float, default=1.0, help="重试等待基数（秒），第 n 次等 n×基数，默认 1")
    ap.add_argument("--selftest", action="store_true", help="本机假接收端自测，不访问外网")
    return ap


def main(argv=None, env=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args = build_parser().parse_args(argv)
    if args.selftest:
        return run_selftest(out)
    try:
        return send_flow(args, os.environ if env is None else env, out, err)
    except UserError as exc:
        err.write("错误：%s\n" % exc)
        return exc.code


# ---------------------------------------------------------------- 自测

def run_selftest(out):
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import fake_webhook_server as fake
    except ImportError as exc:
        out.write("自测需要同目录的 fake_webhook_server.py：%s\n" % exc)
        return EXIT_SELFTEST

    env = {"WECOM_BOT_KEY": "selftest-key-0001"}
    cases = [
        ("text + @手机号：首个请求 HTTP 503 → 自动重试 → errcode 0",
         [{"status": 503}], ["--type", "text", "--content", "【自测】今晚 22:00 发布", "--at-mobile", "13800000000"],
         EXIT_OK, 2, {"msgtype": "text", "text": {"content": "【自测】今晚 22:00 发布",
                                                 "mentioned_mobile_list": ["13800000000"]}}),
        ("markdown：返回 errcode 93000 → 退出码 4 + 中文解释",
         [{"errcode": 93000}], ["--type", "markdown", "--content", "## 自测\n> 一切正常"],
         EXIT_API, 1, {"msgtype": "markdown", "markdown": {"content": "## 自测\n> 一切正常"}}),
        ("返回 errcode 45009：不自动重试，退出码 4",
         [{"errcode": 45009}], ["--content", "频率自测"], EXIT_API, 1, None),
        ("返回 errcode -1：重试 1 次后成功",
         [{"errcode": -1}, {"errcode": 0}], ["--content", "繁忙自测"], EXIT_OK, 2, None),
        ("超时：0.5 秒超时，共 3 次请求后放弃，退出码 3",
         [{"delay": 1.2}, {"delay": 1.2}, {"delay": 1.2}], ["--content", "超时自测", "--timeout", "0.5"],
         EXIT_NET, 3, None),
    ]
    passed = 0
    out.write("[selftest] 本机假接收端，只监听 127.0.0.1，不访问外网\n")
    for idx, (title, plan, extra, want_code, want_requests, want_json) in enumerate(cases, 1):
        srv = fake.make_server(0, plan, {"errcode": 0}, silent=True)
        worker = threading.Thread(target=srv.serve_forever, daemon=True)
        worker.start()
        endpoint = "http://127.0.0.1:%d/cgi-bin/webhook/send" % srv.server_address[1]
        buf_out, buf_err = io.StringIO(), io.StringIO()
        code = main(extra + ["--endpoint", endpoint, "--send", "--backoff", "0.05"], env, buf_out, buf_err)
        time.sleep(0.1)
        srv.shutdown()
        srv.server_close()
        got = srv.received
        problems = []
        if code != want_code:
            problems.append("退出码 %s，期望 %s" % (code, want_code))
        if len(got) != want_requests:
            problems.append("收到 %d 个请求，期望 %d" % (len(got), want_requests))
        if got and not all(r["ok"] for r in got):
            problems.append("请求体检查未通过：%s" % got[0]["why"])
        if want_json is not None and got and got[-1]["json"] != want_json:
            problems.append("请求体与预期不一致：%s" % json.dumps(got[-1]["json"], ensure_ascii=False))
        if got and "key=selftest-key-0001" not in got[-1]["query"]:
            problems.append("URL 里的 key 不对")
        text = buf_out.getvalue() + buf_err.getvalue()
        if "selftest-key-0001" in text:
            problems.append("输出里出现了完整 key")
        if want_code == EXIT_API and "errcode=" not in text:
            problems.append("没有打印 errcode 解释")
        if problems:
            out.write("FAIL %d %s\n     %s\n" % (idx, title, "；".join(problems)))
        else:
            passed += 1
            out.write("PASS %d %s（共 %d 次请求）\n" % (idx, title, len(got)))
    out.write("自测结果：%d/%d 通过\n" % (passed, len(cases)))
    return EXIT_OK if passed == len(cases) else EXIT_SELFTEST


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断，没有继续发送。\n")
        sys.exit(EXIT_INT)
