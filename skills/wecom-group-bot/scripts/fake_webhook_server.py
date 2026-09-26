#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机假 webhook 接收端：只监听 127.0.0.1，用来在不碰企业微信接口的前提下验证请求体。

它不是企业微信的模拟器：返回的 errcode 只是你用参数指定的数字，
errmsg 一律带 "fake receiver" 字样，免得和真实返回混淆。

用法（终端 A 起接收端，终端 B 发送）：
  python3 fake_webhook_server.py --port 8765                  # 每次都回 errcode 0
  python3 fake_webhook_server.py --port 8765 --fail-first 1   # 前 1 次回 HTTP 503，用来看重试
  python3 fake_webhook_server.py --port 8765 --errcode 45009  # 每次都回指定 errcode
  python3 fake_webhook_server.py --port 8765 --delay 3        # 每次先等 3 秒，用来看超时
  python3 fake_webhook_server.py --port 8765 --max-requests 2 # 回复完 2 个请求后自动退出

  WECOM_BOT_KEY=local-test-key python3 wecom_bot_send.py --content "hi" \
      --endpoint http://127.0.0.1:8765/cgi-bin/webhook/send --send

退出码：0 正常结束；1 参数错误；2 端口被占用或无法监听；130 Ctrl+C 中断。
"""

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

EXIT_OK, EXIT_ARGS, EXIT_LISTEN, EXIT_INT = 0, 1, 2, 130
FAKE_BAD_PAYLOAD_ERRCODE = 99999  # 假接收端自用，不是企业微信的错误码


def mask(value):
    """只露最后 4 位，假 key 也不完整打印，养成习惯。"""
    value = value or ""
    return "****" + value[-4:] if len(value) > 4 else "****"


def check_payload(query, body):
    """返回 (是否合格, 说明, 解析后的 JSON)。只检查结构，不评判内容。"""
    keys = parse_qs(query).get("key") or []
    if not keys or not keys[0].strip():
        return False, "URL 里没有 key 参数", None
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return False, "请求体不是 UTF-8 JSON：%s" % exc, None
    if not isinstance(data, dict):
        return False, "请求体顶层不是对象", None
    msgtype = data.get("msgtype")
    if msgtype not in ("text", "markdown"):
        return False, "msgtype 不是 text/markdown：%r" % msgtype, data
    part = data.get(msgtype)
    if not isinstance(part, dict) or not str(part.get("content", "")).strip():
        return False, "%s.content 为空" % msgtype, data
    mobiles = part.get("mentioned_mobile_list")
    if mobiles is not None and not (isinstance(mobiles, list) and all(isinstance(m, str) for m in mobiles)):
        return False, "mentioned_mobile_list 必须是字符串数组", data
    return True, "ok", data


class FakeHandler(BaseHTTPRequestHandler):
    server_version = "FakeWebhook/1.0"

    def log_message(self, fmt, *args):  # 关掉默认的访问日志，改成下面自己的中文日志
        return

    def do_POST(self):
        srv = self.server
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        parsed = urlparse(self.path)
        ok, why, data = check_payload(parsed.query, body)
        with srv.lock:
            srv.count += 1
            index = srv.count
            action = srv.plan[index - 1] if index - 1 < len(srv.plan) else srv.default_action
            srv.received.append({"path": parsed.path, "query": parsed.query, "ok": ok, "why": why, "json": data})
        delay = float(action.get("delay", 0) or 0)
        if delay > 0:
            time.sleep(delay)
        if not ok:
            status, reply = 200, {"errcode": FAKE_BAD_PAYLOAD_ERRCODE, "errmsg": "fake receiver: " + why}
        elif action.get("status", 200) != 200:
            status, reply = int(action["status"]), None
        else:
            code = int(action.get("errcode", 0))
            status, reply = 200, {"errcode": code, "errmsg": "ok" if code == 0 else "fake receiver: simulated errcode %d" % code}
        key = (parse_qs(parsed.query).get("key") or [""])[0]
        msgtype = data.get("msgtype") if isinstance(data, dict) else "?"
        if not srv.silent:
            sys.stderr.write("[fake] #%d POST %s key=%s msgtype=%s 字节=%d 检查=%s → HTTP %d%s\n" % (
                index, parsed.path, mask(key), msgtype, len(body), why, status,
                "" if reply is None else " errcode=%s" % reply["errcode"]))
            sys.stderr.flush()
        payload = b"" if reply is None else json.dumps(reply, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端已超时断开，属于预期情况
        with srv.lock:
            srv.done += 1

    def do_GET(self):
        self.send_response(405)
        self.end_headers()


def make_server(port=0, plan=None, default_action=None, silent=False):
    """起一个只监听 127.0.0.1 的假接收端。plan 是按请求顺序生效的动作列表。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), FakeHandler)
    srv.daemon_threads = True
    srv.lock = threading.Lock()
    srv.count = 0
    srv.done = 0
    srv.plan = list(plan or [])
    srv.default_action = dict(default_action or {"errcode": 0})
    srv.received = []
    srv.silent = silent
    return srv


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_ARGS)


def main(argv=None):
    ap = ArgParser(description="本机假 webhook 接收端（只监听 127.0.0.1，不访问外网）")
    ap.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765；0 表示随机")
    ap.add_argument("--fail-first", type=int, default=0, help="前 N 次请求回 HTTP 503")
    ap.add_argument("--errcode", type=int, default=0, help="正常请求回的 errcode，默认 0")
    ap.add_argument("--delay", type=float, default=0.0, help="每次回复前等待的秒数")
    ap.add_argument("--max-requests", type=int, default=0, help="回复完 N 个请求后退出；0 表示一直运行")
    args = ap.parse_args(argv)
    if not (0 <= args.port <= 65535):
        ap.error("--port 须在 0–65535 之间")
    if args.fail_first < 0 or args.max_requests < 0 or args.delay < 0:
        ap.error("--fail-first / --max-requests / --delay 不能为负数")

    plan = [{"status": 503, "delay": args.delay} for _ in range(args.fail_first)]
    default = {"errcode": args.errcode, "delay": args.delay}
    try:
        srv = make_server(args.port, plan, default)
    except OSError as exc:
        sys.stderr.write("无法监听 127.0.0.1:%d：%s（端口被占用就换一个 --port）\n" % (args.port, exc))
        return EXIT_LISTEN
    host, port = srv.server_address[:2]
    sys.stderr.write("[fake] 假接收端已启动：http://%s:%d/cgi-bin/webhook/send （Ctrl+C 结束）\n" % (host, port))
    sys.stderr.flush()
    worker = threading.Thread(target=srv.serve_forever, daemon=True)
    worker.start()
    try:
        while True:
            time.sleep(0.2)
            if args.max_requests and srv.done >= args.max_requests:
                break
    except KeyboardInterrupt:
        sys.stderr.write("\n[fake] 已中断\n")
        srv.shutdown()
        srv.server_close()
        return EXIT_INT
    srv.shutdown()
    srv.server_close()
    sys.stderr.write("[fake] 共收到 %d 个请求，退出\n" % srv.count)
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(EXIT_INT)
