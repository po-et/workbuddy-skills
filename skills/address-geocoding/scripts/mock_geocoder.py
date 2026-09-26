#!/usr/bin/env python3
"""本地假地理编码服务：只用于离线演练 geocode_batch.py，不连接任何外部服务。

模拟 /ws/geocoder/v1/ 的两种调用（返回结构仿照常见的地理编码 JSON，字段以腾讯位置服务官方文档为准）：
  ?address=地址&key=...           地理编码：坐标由「近似城市中心 + 地址哈希偏移」生成，是假数据
  ?location=纬度,经度&key=...      逆地址解析：返回「模拟区模拟路 N 号」

为了演练脚本的容错，内置几种故障（status 都是本地模拟值，不代表真实接口的状态码）：
  地址含「查无此地」   -> status 9002「查询无结果」
  地址含「超时」       -> 延迟 3 秒再返回（配合客户端 --timeout 1 演练超时重试）
  地址含「偶发故障」   -> 该地址第一次请求返回 HTTP 500，之后正常
  地址含「限频」       -> 该地址第一次请求返回 status 9001「请求过快」（配合客户端 --retry-status 9001 演练重试）
  缺 key               -> status 9003
  地址里没有门牌、道路或地标 -> 返回区县中心点、可信度 3（演练「多个地址落在同一点」）

用法：python3 mock_geocoder.py --port 8765        （Ctrl-C 停止）
退出码：0 正常停止；1 参数错误；2 端口被占用或无法监听；130 Ctrl-C 中断。
"""

import argparse
import hashlib
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

# 近似的城市中心，仅作模拟
CITIES = {
    "深圳": ("广东省", "深圳市", 22.5431, 114.0579),
    "广州": ("广东省", "广州市", 23.1291, 113.2644),
    "北京": ("北京市", "北京市", 39.9042, 116.4074),
    "上海": ("上海市", "上海市", 31.2304, 121.4737),
    "杭州": ("浙江省", "杭州市", 30.2741, 120.1551),
    "成都": ("四川省", "成都市", 30.5728, 104.0668),
}
DETAIL_RE = re.compile(r"(\d+号|大厦|广场|中心|小区|花园|园区|公寓|大楼|商场|学校|医院|酒店)")
ROAD_RE = re.compile(r"(路|街|道|巷|大道)")

LOCK = threading.Lock()
STATE = {"seen_flaky": set(), "seen_throttle": set()}


def _offset(text, span):
    h = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
    return ((h % 1000) / 1000.0 - 0.5) * span, (((h // 1000) % 1000) / 1000.0 - 0.5) * span


def geocode(address):
    city_key = next((k for k in CITIES if k in address), None)
    if not city_key:
        return {"status": 9002, "message": "模拟：查询无结果（地址里没有可识别的城市）"}
    prov, city, lat, lng = CITIES[city_key]
    after_city = re.sub(r"^市", "", address.split(city_key, 1)[1])
    m = re.search(r"([\u4e00-\u9fff]{1,4}?(?:区|县))", after_city)
    district = m.group(1) if m else ""
    if DETAIL_RE.search(address):
        dlat, dlng = _offset(address, 0.1)
        rel, level = 8, 9
    elif ROAD_RE.search(address):
        dlat, dlng = _offset(address, 0.1)
        rel, level = 6, 6
    else:
        dlat, dlng = _offset(district or city, 0.08)      # 同一区县的笼统地址落在同一点
        rel, level = 3, 4
    return {
        "status": 0,
        "message": "query ok（模拟）",
        "result": {
            "title": address,
            "location": {"lat": round(lat + dlat, 6), "lng": round(lng + dlng, 6)},
            "address_components": {"province": prov, "city": city, "district": district,
                                   "street": "", "street_number": ""},
            "reliability": rel,
            "level": level,
        },
    }


def reverse(location):
    try:
        lat, lng = [float(x) for x in location.split(",")]
    except ValueError:
        return {"status": 9004, "message": "模拟：location 格式应为 纬度,经度"}
    key = min(CITIES, key=lambda k: (CITIES[k][2] - lat) ** 2 + (CITIES[k][3] - lng) ** 2)
    prov, city = CITIES[key][0], CITIES[key][1]
    n = int(abs(lat * 1000 + lng * 1000)) % 200 + 1
    return {
        "status": 0,
        "message": "query ok（模拟）",
        "result": {
            "location": {"lat": lat, "lng": lng},
            "address": "%s%s模拟区模拟路%d号" % (prov if prov != city else "", city, n),
            "formatted_addresses": {"recommend": "模拟地标附近"},
            "address_component": {"nation": "中国", "province": prov, "city": city, "district": "模拟区"},
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MockGeocoder/0.1"

    def _send(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _first(bucket, address):
        with LOCK:
            first = address not in STATE[bucket]
            STATE[bucket].add(address)
        return first

    def do_GET(self):
        parts = urlsplit(self.path)
        if parts.path != "/ws/geocoder/v1/":
            return self._send(404, {"status": 404, "message": "模拟：路径不存在"})
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if not q.get("key"):
            return self._send(200, {"status": 9003, "message": "模拟：缺少 key"})
        address = q.get("address", "")
        if "location" in q:
            return self._send(200, reverse(q["location"]))
        if not address:
            return self._send(200, {"status": 9004, "message": "模拟：缺少 address 或 location"})
        if "偶发故障" in address and self._first("seen_flaky", address):
            return self._send(500, {"status": 500, "message": "模拟：服务端错误"})
        if "限频" in address and self._first("seen_throttle", address):
            return self._send(200, {"status": 9001, "message": "模拟：请求过快"})
        if "超时" in address:
            time.sleep(3)
        if "查无此地" in address:
            return self._send(200, {"status": 9002, "message": "模拟：查询无结果"})
        return self._send(200, geocode(address))

    def log_message(self, fmt, *args):
        line = fmt % args
        sys.stderr.write("[mock] %s\n" % re.sub(r"(key=)[^&\s]+", r"\1***", line))


def main(argv=None):
    p = argparse.ArgumentParser(description="本地假地理编码服务（只用于离线演练）")
    p.add_argument("--port", type=int, default=8765, help="监听端口（默认 8765，只监听 127.0.0.1）")
    args = p.parse_args(argv)
    if not 0 < args.port < 65536:
        sys.stderr.write("参数错误：--port 需在 1–65535 之间\n")
        return 1
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        sys.stderr.write("无法监听 127.0.0.1:%d（%s）；端口可能被占用，换一个 --port\n" % (args.port, exc))
        return 2
    sys.stderr.write("模拟服务已启动：http://127.0.0.1:%d/ws/geocoder/v1/ （Ctrl-C 停止）\n" % args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n模拟服务已停止。\n")
        return 130
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
