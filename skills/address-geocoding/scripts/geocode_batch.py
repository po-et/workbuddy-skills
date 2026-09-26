#!/usr/bin/env python3
"""批量地址解析：CSV 地址列 -> 经纬度（或经纬度 -> 地址），再算到门店的球面距离。

纯 Python 标准库，Python 3.8+。

四个子命令：
  clean     只清洗地址并写出结果供核对（不联网）
  geocode   地址 -> 经纬度（默认预演，加 --run 才真正请求）
  reverse   经纬度 -> 地址（默认预演，加 --run 才真正请求）
  distance  每个点到最近门店的球面距离、是否在配送半径内（不联网）

接口：腾讯位置服务 WebService 的地理编码 / 逆地址解析，路径 /ws/geocoder/v1/，
参数 address=地址 或 location=纬度,经度，外加 key。返回字段、状态码、配额以腾讯位置服务官方文档为准。
key 只从环境变量读取（默认 TENCENT_MAP_KEY），不接受命令行明文，也不会打印出来。

退出码：
  0   完成（个别行失败会写在输出的 geo_status / geo_note 里）
  1   参数或配置错误（列名不存在、缺 key、输出文件已存在等）
  2   文件读写失败（找不到、编码无法识别、写不进去）
  3   请求全部失败，或开头连续几次同样的错误已自动停止（多半是 key、白名单或网络问题）
  130 用户按 Ctrl-C 中断（已处理的部分照常写出）
"""

import argparse
import csv
import json
import math
import os
import re
import socket
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "https://apis.map.qq.com"
GEOCODER_PATH = "/ws/geocoder/v1/"
DEFAULT_KEY_ENV = "TENCENT_MAP_KEY"
EARTH_RADIUS_KM = 6371.0088            # 地球平均半径（千米）
CHINA_BOX = (3.0, 54.0, 73.0, 136.0)   # 纬度下限、上限、经度下限、上限：只做粗筛
SAME_POINT_MIN = 3                     # 至少这么多个不同地址落在同一坐标，判为疑似只解析到区县或城市中心
ABORT_AFTER = 3                        # 开头连续这么多次同样的错误就停下，避免白白消耗配额

GEO_FIELDS = ["geo_clean_address", "geo_clean_note", "geo_lat", "geo_lng", "geo_coord_sys",
              "geo_province", "geo_city", "geo_district", "geo_reliability", "geo_level",
              "geo_status", "geo_note"]
REV_FIELDS = ["geo_address", "geo_recommend", "geo_province", "geo_city", "geo_district",
              "geo_status", "geo_note"]
DIST_FIELDS = ["nearest_store", "distance_km", "within_radius", "dist_note"]

PROVINCES = ("黑龙江", "内蒙古", "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
             "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾", "广西", "西藏", "宁夏", "新疆",
             "香港", "澳门")
MUNICIPALITIES = ("北京", "天津", "上海", "重庆")
PROVINCE_SUFFIX = r"(?:省|市|自治区|壮族自治区|回族自治区|维吾尔自治区|特别行政区)"
CITY_RE = re.compile(r"([\u4e00-\u9fff]{2,4}?)(?:市|自治州|地区|盟)")
AREA_AFTER_PROVINCE_RE = re.compile(r"[\u4e00-\u9fff]{2,4}?(?:市|区|县|自治州|地区|盟)")
BRACKET_RE = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]|【([^【】]*)】|〔([^〔〕]*)〕|\{([^{}]*)\}")
NOTE_HINT = re.compile(r"^(近|靠近|旁|对面|临|附近|电话|手机|联系|收件|收货|放|送|请|备注|门口|快递|代收)")
POI_HINT = re.compile(r"(大厦|广场|中心|小区|花园|园区|公寓|大楼|商场|学校|医院|酒店|市场|写字楼|家园|苑)$")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)|(?<!\d)0\d{2,3}-\d{7,8}(?!\d)")
PREFIX_RE = re.compile(r"^(?:收货地址|收件地址|详细地址|送货地址|地址|住址)\s*[:：]\s*")
CJK_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff])\s+|\s+(?=[\u4e00-\u9fff])")


class UsageError(Exception):
    """参数或配置错误 -> 退出码 1"""


class FileError(Exception):
    """文件读写错误 -> 退出码 2"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用 -h 查看用法。\n" % message)
        sys.exit(1)


# ---------------------------------------------------------------- 文件

def read_csv(path):
    """读 CSV：先按 UTF-8（含 BOM）读，失败再按 GB18030（Excel 中文版常见）读。"""
    last = None
    for enc in ("utf-8-sig", "gb18030"):
        try:
            with open(path, newline="", encoding=enc) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fields = reader.fieldnames
        except UnicodeDecodeError as exc:
            last = exc
            continue
        except FileNotFoundError:
            raise FileError("找不到文件：%s" % path)
        except IsADirectoryError:
            raise FileError("这是目录，不是文件：%s" % path)
        except PermissionError:
            raise FileError("没有权限读取：%s" % path)
        except csv.Error as exc:
            raise FileError("CSV 格式有误：%s（%s）" % (path, exc))
        except OSError as exc:
            raise FileError("读取失败：%s（%s）" % (path, exc))
        if not fields:
            raise FileError("%s 是空的或没有表头行" % path)
        return [f.strip() for f in fields], [{(k or "").strip(): v for k, v in r.items()} for r in rows]
    raise FileError("%s 的编码无法识别（%s），请另存为 UTF-8 的 CSV" % (path, last))


def require_columns(fields, needed, path):
    missing = [c for c in needed if c and c not in fields]
    if missing:
        raise UsageError("%s 里没有列 %s。现有的列：%s" % (path, "、".join(missing), "、".join(fields)))


def check_output_path(out, inputs, overwrite):
    for src in inputs:
        if src and os.path.abspath(out) == os.path.abspath(src):
            raise UsageError("输出文件不能和输入文件相同：%s" % out)
    if os.path.exists(out) and not overwrite:
        raise UsageError("输出文件已存在：%s（换个文件名，或加 --overwrite 覆盖）" % out)
    directory = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(directory):
        raise FileError("输出目录不存在：%s" % directory)


def write_atomic(path, writer_fn):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".geocode-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as fh:
            writer_fn(fh)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise FileError("写入失败：%s（%s）" % (path, exc))


def write_csv(path, fields, rows):
    def _w(fh):
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    write_atomic(path, _w)


def load_cache(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise FileError("缓存文件读不了：%s（%s）；删掉它或换一个 --cache 路径" % (path, exc))
    return data if isinstance(data, dict) else {}


def save_cache(path, cache):
    if not path:
        return
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".geocache-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=0, sort_keys=True)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        sys.stderr.write("警告：缓存写入失败（%s），不影响结果文件\n" % exc)


# ---------------------------------------------------------------- 地址清洗

def detect_region(addr):
    """从地址开头识别省、市（返回简称，如 ('广东', '深圳')；识别不到为 None）。"""
    prov, rest = None, addr
    for p in PROVINCES:
        if not addr.startswith(p):
            continue
        m = re.match(re.escape(p) + PROVINCE_SUFFIX, addr)
        if m:
            prov, rest = p, addr[m.end():]
        elif AREA_AFTER_PROVINCE_RE.match(addr[len(p):]):   # 「广东深圳南山区」这类省略了「省」「市」的写法
            prov, rest = p, addr[len(p):]
        break
    m = CITY_RE.match(rest)
    city = m.group(1) if m else None
    if prov in MUNICIPALITIES and not city:
        city = prov
    return prov, city


def _short_city(text):
    """'深圳市' -> '深圳'；'广东省深圳市' -> '深圳'。"""
    text = (text or "").strip()
    if not text:
        return ""
    prov, city = detect_region(text)
    if city:
        return city
    return re.sub(r"(市|自治州|地区|盟|省)$", "", text) or text


def clean_address(raw, city_hint="", region=""):
    """返回 (清洗后地址, 清洗说明列表, 用于核对的城市简称)。"""
    notes = []
    text = unicodedata.normalize("NFKC", raw or "")
    if text != (raw or ""):
        notes.append("全角转半角")
    text = PREFIX_RE.sub("", text.strip())

    def _bracket(m):
        inner = next(g for g in m.groups() if g is not None).strip()
        if not inner:
            return ""
        if NOTE_HINT.match(inner) or PHONE_RE.search(inner) or not POI_HINT.search(inner):
            notes.append("删括号备注「%s」" % inner)
            return ""
        notes.append("保留括号内地标「%s」" % inner)
        return inner

    for _ in range(3):                          # 处理嵌套括号
        new = BRACKET_RE.sub(_bracket, text)
        if new == text:
            break
        text = new
    if PHONE_RE.search(text):
        text = PHONE_RE.sub("", text)
        notes.append("删电话号码")
    text = re.sub(r"\s+", " ", text).strip(" ,，;；")
    text = CJK_SPACE_RE.sub("", text)
    if not text:
        return "", notes + ["清洗后为空"], ""

    hint_city = _short_city(city_hint) or _short_city(region)
    prov, city = detect_region(text)
    if prov or city:
        if city_hint and city and hint_city and city != hint_city:
            notes.append("地址里的城市（%s）与城市列（%s）不一致，按地址原文请求；若前者是后者下辖的县级市可忽略"
                         % (city, hint_city))
        return text, notes, hint_city
    prefix = (city_hint or region).strip()
    if prefix and hint_city and hint_city in text[:12]:
        return text, notes, hint_city            # 地址里已写了城市简称，如「深圳南山区」
    if prefix:
        notes.append("补全「%s」" % prefix)
        return prefix + text, notes, hint_city
    notes.append("缺省市，可能解析到别的城市 [待确认]")
    return text, notes, hint_city


# ---------------------------------------------------------------- 距离

def haversine_km(lat1, lng1, lat2, lng2):
    """球面距离（半正矢公式），单位千米。两点必须是同一坐标系。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def parse_latlng(lat_s, lng_s):
    """返回 ((lat, lng), None) 或 (None, 原因)。"""
    if not str(lat_s or "").strip() and not str(lng_s or "").strip():
        return None, "没有坐标（上一步未成功或未请求）"
    try:
        lat, lng = float(str(lat_s).strip()), float(str(lng_s).strip())
    except (TypeError, ValueError):
        return None, "经纬度不是数字"
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        if -90 <= lng <= 90 and -180 <= lat <= 180:
            return None, "纬度超出 -90～90，疑似经纬度写反"
        return None, "经纬度超出取值范围"
    lo_lat, hi_lat, lo_lng, hi_lng = CHINA_BOX
    if not (lo_lat <= lat <= hi_lat and lo_lng <= lng <= hi_lng):
        if lo_lat <= lng <= hi_lat and lo_lng <= lat <= hi_lng:
            return None, "疑似经纬度写反（纬度在前、经度在后）"
    return (lat, lng), None


def in_china_box(lat, lng):
    lo_lat, hi_lat, lo_lng, hi_lng = CHINA_BOX
    return lo_lat <= lat <= hi_lat and lo_lng <= lng <= hi_lng


# ---------------------------------------------------------------- 请求

def get_key(env_name):
    key = os.environ.get(env_name, "").strip()
    if not key:
        raise UsageError("没有读到环境变量 %s。请先在终端执行 export %s=你的key"
                         "（不要把 key 写进脚本、贴进对话或提交进仓库）" % (env_name, env_name))
    return key


def check_base_url(base):
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise UsageError("--base-url 不是合法的 http(s) 地址：%s" % base)
    if parts.scheme == "http" and parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise UsageError("非本机地址必须用 https，否则 key 会明文传输：%s" % base)


def redact(url):
    return re.sub(r"(key=)[^&]+", r"\1***", url)


def fetch_json(url, timeout, retries, retry_status):
    """GET 一个 JSON。返回 (data, None) 或 (None, 错误说明)。网络错误、HTTP 5xx/429 与指定状态码会重试。"""
    last = ""
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(min(2 ** (attempt - 1), 8))       # 1s、2s……
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geocode-batch/0.1 (+stdlib)"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            last = "HTTP %d" % exc.code
            if exc.code == 429 or 500 <= exc.code < 600:
                continue
            return None, last
        except (socket.timeout, TimeoutError):
            last = "请求超时（%s 秒）" % timeout
            continue
        except urllib.error.URLError as exc:
            reason = exc.reason
            last = "请求超时（%s 秒）" % timeout if isinstance(reason, socket.timeout) else "网络错误：%s" % reason
            continue
        except (ConnectionError, OSError) as exc:
            last = "网络错误：%s" % exc
            continue
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None, "返回的不是 JSON（检查 --base-url 是否正确）"
        if not isinstance(data, dict):
            return None, "返回的 JSON 结构不对"
        status = data.get("status")
        if status in retry_status and attempt < retries:
            last = "status=%s %s" % (status, data.get("message", ""))
            continue
        return data, None
    return None, "%s（已重试 %d 次）" % (last, retries)


class Requester(object):
    """按固定间隔发请求，统计开头的连续失败，必要时中止。"""

    def __init__(self, args, key):
        self.args, self.key = args, key
        self.base = args.base_url.rstrip("/") + GEOCODER_PATH
        self.last_at = 0.0
        self.sent = 0
        self.first_errors = []

    def get(self, params):
        wait = self.args.interval - (time.monotonic() - self.last_at)
        if wait > 0:
            time.sleep(wait)
        q = dict(params)
        q["key"] = self.key
        url = self.base + "?" + urllib.parse.urlencode(q)
        data, err = fetch_json(url, self.args.timeout, self.args.retries, self.args.retry_status)
        self.last_at = time.monotonic()
        self.sent += 1
        if err is None and data.get("status") != 0:
            err = "status=%s %s" % (data.get("status"), data.get("message", ""))
            data = None
        if self.sent <= ABORT_AFTER:
            self.first_errors.append(err)
            if (len(self.first_errors) == ABORT_AFTER and all(self.first_errors)
                    and len(set(self.first_errors)) == 1):
                raise AbortRun("开头连续 %d 次都返回同样的错误：%s。已停止，避免浪费配额；"
                               "请检查 key、key 的调用来源限制与网络，官方状态码含义以腾讯位置服务文档为准"
                               % (ABORT_AFTER, err))
        return data, err


class AbortRun(Exception):
    """开头连续同样错误 -> 退出码 3"""


def progress(done, total):
    if total >= 20 and (done == total or done % max(1, total // 10) == 0):
        sys.stderr.write("进度 %d/%d\n" % (done, total))


# ---------------------------------------------------------------- 子命令：clean / geocode

def plan_rows(args):
    fields, rows = read_csv(args.input)
    require_columns(fields, [args.column, args.city_column], args.input)
    if args.limit:
        rows = rows[:args.limit]
    for r in rows:
        hint = r.get(args.city_column, "") if args.city_column else ""
        clean, notes, city = clean_address(r.get(args.column, ""), hint, args.region)
        r["geo_clean_address"] = clean
        r["geo_clean_note"] = "；".join(notes)
        r["_city"] = city
        r["_hint_given"] = bool(hint.strip())
    return fields, rows


def preview(rows, unique, show, what):
    empty = sum(1 for r in rows if not r["geo_clean_address"])
    print("预演（没有发出任何请求）：共 %d 行，去重后需请求 %d 次，空地址 %d 行不请求。" % (len(rows), len(unique), empty))
    print("配额与费用以腾讯位置服务控制台和官方说明为准。")
    print("前 %d 行清洗结果：" % min(show, len(rows)))
    for i, r in enumerate(rows[:show], 1):
        note = r["geo_clean_note"] or "无改动"
        print("  %d. %s  →  %s（%s）" % (i, r.get(what, ""), r["geo_clean_address"] or "（空，不请求）", note))
    print("确认无误后加 --run 执行；建议先加 --limit 20 小批量试跑。")


def cmd_clean(args):
    check_output_path(args.out, [args.input], args.overwrite)
    fields, rows = plan_rows(args)
    unique = sorted({r["geo_clean_address"] for r in rows if r["geo_clean_address"]})
    write_csv(args.out, fields + ["geo_clean_address", "geo_clean_note"], rows)
    changed = sum(1 for r in rows if r["geo_clean_note"])
    print("已写出 %s：%d 行，其中 %d 行有清洗动作，去重后 %d 个地址。" % (args.out, len(rows), changed, len(unique)))
    return 0


def assess(r, result):
    """根据返回内容填 geo_ 列并判定状态。"""
    loc = result.get("location") or {}
    comps = result.get("address_components") or result.get("address_component") or {}
    lat, lng = loc.get("lat"), loc.get("lng")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        r["geo_status"], r["geo_note"] = "失败", "返回里没有坐标"
        return
    r["geo_lat"], r["geo_lng"], r["geo_coord_sys"] = "%.6f" % lat, "%.6f" % lng, "GCJ-02"
    r["geo_province"] = comps.get("province", "")
    r["geo_city"] = comps.get("city", "")
    r["geo_district"] = comps.get("district", "")
    rel, level = result.get("reliability"), result.get("level")
    r["geo_reliability"] = "" if rel is None else str(rel)
    r["geo_level"] = "" if level is None else str(level)
    flags = []
    if isinstance(rel, (int, float)) and rel < r["_min_rel"]:
        flags.append("可信度 %s 低于 %s" % (rel, r["_min_rel"]))
    if r["_hint_given"] and r["_city"] and r["geo_city"] and r["_city"] not in r["geo_city"]:
        flags.append("结果城市（%s）与城市列（%s）不一致" % (r["geo_city"], r["_city"]))
    if not in_china_box(lat, lng):
        flags.append("坐标不在中国大致范围内")
    r["geo_status"] = "低可信" if flags else "成功"
    r["geo_note"] = "；".join(flags)


def flag_same_point(rows):
    groups = {}
    for r in rows:
        if r.get("geo_status") in ("成功", "低可信") and r.get("geo_lat"):
            groups.setdefault((r["geo_lat"], r["geo_lng"]), set()).add(r["geo_clean_address"])
    for r in rows:
        addrs = groups.get((r.get("geo_lat"), r.get("geo_lng")))
        if addrs and len(addrs) >= SAME_POINT_MIN:
            r["geo_status"] = "低可信"
            extra = "%d 个不同地址落在同一点，疑似只解析到区县或城市中心" % len(addrs)
            r["geo_note"] = "；".join(x for x in (r.get("geo_note"), extra) if x)


def summarize(rows, sent, out, extra=""):
    counts = {}
    for r in rows:
        counts[r.get("geo_status", "")] = counts.get(r.get("geo_status", ""), 0) + 1
    order = ["成功", "低可信", "失败", "未请求", "未处理"]
    parts = ["%s %d" % (k, counts[k]) for k in order if counts.get(k)]
    print("完成：共 %d 行｜实际请求 %d 次｜%s → %s%s" % (len(rows), sent, "｜".join(parts), out, extra))
    errors = {}
    for r in rows:
        if r.get("geo_status") == "失败":
            errors[r["geo_note"]] = errors.get(r["geo_note"], 0) + 1
    for msg, n in sorted(errors.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
        print("  失败原因：%s ×%d" % (msg, n))
    return counts


def run_requests(args, keys, make_params, cache, cache_prefix):
    """对去重后的 keys 逐个请求。返回 ({key: (data, err)}, 已请求次数, 是否中断, 中止原因)。"""
    results, interrupted, aborted = {}, False, None
    todo = [k for k in keys if cache_prefix + k not in cache]
    for k in keys:
        if cache_prefix + k in cache:
            results[k] = (cache[cache_prefix + k], None)
    requester = Requester(args, get_key(args.key_env)) if todo else None
    try:
        for i, k in enumerate(todo, 1):
            data, err = requester.get(make_params(k))
            results[k] = (data, err)
            if data is not None:
                cache[cache_prefix + k] = data
            progress(i, len(todo))
    except KeyboardInterrupt:
        interrupted = True
    except AbortRun as exc:
        aborted = str(exc)
    return results, (requester.sent if requester else 0), interrupted, aborted


def cmd_geocode(args):
    check_output_path(args.out, [args.input, args.cache], args.overwrite)
    check_base_url(args.base_url)
    fields, rows = plan_rows(args)
    unique = []
    for r in rows:
        if r["geo_clean_address"] and r["geo_clean_address"] not in unique:
            unique.append(r["geo_clean_address"])
    if not args.run:
        preview(rows, unique, args.show, args.column)
        return 0
    cache = load_cache(args.cache)
    results, sent, interrupted, aborted = run_requests(
        args, unique, lambda a: {"address": a}, cache, "geocode|")
    for r in rows:
        r["_min_rel"] = args.min_reliability
        addr = r["geo_clean_address"]
        if not addr:
            r["geo_status"], r["geo_note"] = "未请求", "地址为空"
        elif addr not in results:
            r["geo_status"], r["geo_note"] = "未处理", "已中断" if interrupted else "已中止"
        else:
            data, err = results[addr]
            if err:
                r["geo_status"], r["geo_note"] = "失败", err
            else:
                assess(r, data.get("result") or {})
    flag_same_point(rows)
    write_csv(args.out, fields + GEO_FIELDS, rows)
    save_cache(args.cache, cache)
    counts = summarize(rows, sent, args.out)
    return finish(counts, sent, interrupted, aborted)


def finish(counts, sent, interrupted, aborted):
    if interrupted:
        sys.stderr.write("已中断：处理过的行已写出，未处理的标为「未处理」；带同一个 --cache 重跑可跳过已成功的地址。\n")
        return 130
    if aborted:
        sys.stderr.write(aborted + "\n")
        return 3
    if sent and not counts.get("成功") and not counts.get("低可信"):
        sys.stderr.write("所有请求都失败了：先看上面的失败原因（多为 key、调用来源限制、配额或网络问题）。\n")
        return 3
    return 0


# ---------------------------------------------------------------- 子命令：reverse

def cmd_reverse(args):
    check_output_path(args.out, [args.input, args.cache], args.overwrite)
    check_base_url(args.base_url)
    fields, rows = read_csv(args.input)
    require_columns(fields, [args.lat_column, args.lng_column], args.input)
    if args.limit:
        rows = rows[:args.limit]
    unique = []
    for r in rows:
        point, why = parse_latlng(r.get(args.lat_column), r.get(args.lng_column))
        r["_loc"] = "%.6f,%.6f" % point if point else ""
        r["_why"] = why or ""
        if point and r["_loc"] not in unique:
            unique.append(r["_loc"])
    if not args.run:
        bad = sum(1 for r in rows if not r["_loc"])
        print("预演（没有发出任何请求）：共 %d 行，去重后需请求 %d 次，坐标有问题 %d 行不请求。" % (len(rows), len(unique), bad))
        print("提醒：请确认坐标是 GCJ-02（腾讯位置服务的坐标体系，以官方文档为准）；GPS 设备的 WGS-84 坐标需先转换。")
        for i, r in enumerate(rows[:args.show], 1):
            print("  %d. %s,%s  →  %s" % (i, r.get(args.lat_column), r.get(args.lng_column), r["_loc"] or r["_why"]))
        print("确认无误后加 --run 执行。")
        return 0
    cache = load_cache(args.cache)
    results, sent, interrupted, aborted = run_requests(
        args, unique, lambda loc: {"location": loc}, cache, "reverse|")
    for r in rows:
        if not r["_loc"]:
            r["geo_status"], r["geo_note"] = "未请求", r["_why"]
            continue
        if r["_loc"] not in results:
            r["geo_status"], r["geo_note"] = "未处理", "已中断" if interrupted else "已中止"
            continue
        data, err = results[r["_loc"]]
        if err:
            r["geo_status"], r["geo_note"] = "失败", err
            continue
        res = data.get("result") or {}
        comps = res.get("address_component") or res.get("address_components") or {}
        r["geo_address"] = res.get("address", "")
        r["geo_recommend"] = (res.get("formatted_addresses") or {}).get("recommend", "")
        r["geo_province"], r["geo_city"] = comps.get("province", ""), comps.get("city", "")
        r["geo_district"] = comps.get("district", "")
        r["geo_status"] = "成功" if r["geo_address"] else "失败"
        r["geo_note"] = "" if r["geo_address"] else "返回里没有地址"
    write_csv(args.out, fields + REV_FIELDS, rows)
    save_cache(args.cache, cache)
    counts = summarize(rows, sent, args.out)
    return finish(counts, sent, interrupted, aborted)


# ---------------------------------------------------------------- 子命令：distance

def cmd_distance(args):
    check_output_path(args.out, [args.input, args.stores], args.overwrite)
    if args.radius_km is not None and args.radius_km <= 0:
        raise UsageError("--radius-km 必须大于 0")
    fields, rows = read_csv(args.input)
    require_columns(fields, [args.lat_column, args.lng_column], args.input)
    s_fields, s_rows = read_csv(args.stores)
    require_columns(s_fields, [args.store_name_column, args.store_lat_column, args.store_lng_column], args.stores)
    stores = []
    for i, s in enumerate(s_rows, 2):
        point, why = parse_latlng(s.get(args.store_lat_column), s.get(args.store_lng_column))
        if not point:
            raise UsageError("门店表第 %d 行坐标有问题：%s" % (i, why))
        stores.append((s.get(args.store_name_column, "").strip() or "门店%d" % (i - 1), point))
    if not stores:
        raise UsageError("门店表是空的")
    per_store, inside, inside_low, bad = {}, 0, 0, 0
    for r in rows:
        point, why = parse_latlng(r.get(args.lat_column), r.get(args.lng_column))
        if not point:
            r["dist_note"], bad = why, bad + 1
            continue
        name, dist = min(((n, haversine_km(point[0], point[1], p[0], p[1])) for n, p in stores),
                         key=lambda x: (x[1], x[0]))
        low = r.get("geo_status") == "低可信"
        r["nearest_store"], r["distance_km"] = name, "%.3f" % dist
        r["dist_note"] = "直线距离，不是路网距离" + ("；坐标低可信，先人工复核" if low else "")
        if args.radius_km is not None:
            ok = dist <= args.radius_km
            r["within_radius"] = "是" if ok else "否"
            if ok:
                inside += 1
                inside_low += 1 if low else 0
                per_store[name] = per_store.get(name, 0) + 1
    write_csv(args.out, fields + DIST_FIELDS, rows)
    msg = "完成：%d 个点，%d 家门店，没有可用坐标 %d 行" % (len(rows), len(stores), bad)
    if args.radius_km is not None:
        msg += "；半径 %s 千米内 %d 个（%s；其中坐标低可信 %d 个）" % (args.radius_km, inside, "、".join(
            "%s %d" % kv for kv in sorted(per_store.items())) or "无", inside_low)
    print(msg + " → " + args.out)
    return 0


# ---------------------------------------------------------------- 入口

def _status_list(text):
    out = set()
    for part in (text or "").split(","):
        part = part.strip()
        if part:
            try:
                out.add(int(part))
            except ValueError:
                raise argparse.ArgumentTypeError("--retry-status 要写成逗号分隔的整数，例如 9001,9004")
    return out


def _positive(kind):
    def conv(text):
        try:
            v = kind(text)
        except ValueError:
            raise argparse.ArgumentTypeError("需要一个数字：%r" % text)
        if v < 0:
            raise argparse.ArgumentTypeError("不能是负数：%r" % text)
        return v
    return conv


def add_request_options(p):
    p.add_argument("--run", action="store_true", help="真正发请求（不加则只预演，不联网）")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help="接口地址（默认 %(default)s；本地演练用 http://127.0.0.1:端口）")
    p.add_argument("--key-env", default=DEFAULT_KEY_ENV, help="存放 key 的环境变量名（默认 %(default)s）")
    p.add_argument("--interval", type=_positive(float), default=0.5, help="两次请求的最小间隔秒数（默认 0.5）")
    p.add_argument("--timeout", type=_positive(float), default=8.0, help="单次请求超时秒数（默认 8）")
    p.add_argument("--retries", type=int, choices=(0, 1, 2), default=2, help="失败重试次数，最多 2（默认 2）")
    p.add_argument("--retry-status", type=_status_list, default=set(),
                   help="返回这些 status 时也重试，逗号分隔（限频类状态码请查官方状态码表后填写）")
    p.add_argument("--cache", help="缓存文件（JSON）；带同一个缓存重跑会跳过已成功的请求")
    p.add_argument("--show", type=int, default=10, help="预演时显示前几行（默认 10）")


def build_parser():
    p = Parser(description="批量地址解析（腾讯位置服务 WebService）：清洗、地址转坐标、坐标转地址、到门店距离。",
               epilog="默认只预演不联网；key 从环境变量读取。退出码：0 完成；1 参数/配置；2 文件；3 请求全部失败或已中止；130 中断。")
    sub = p.add_subparsers(dest="cmd")
    sub.required = True

    def common(sp):
        sp.add_argument("input", help="输入 CSV（UTF-8 或 Excel 另存的 GBK 均可）")
        sp.add_argument("--out", required=True, help="输出 CSV（UTF-8 带 BOM，Excel 可直接打开）")
        sp.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的输出文件")
        sp.add_argument("--limit", type=int, help="只处理前 N 行（小批量试跑）")

    for name, helptext in (("clean", "只清洗地址，写出结果供核对（不联网）"),
                           ("geocode", "地址 -> 经纬度")):
        sp = sub.add_parser(name, help=helptext)
        common(sp)
        sp.add_argument("--column", required=True, help="地址所在的列名")
        sp.add_argument("--city-column", help="城市所在的列名（用于补全与核对）")
        sp.add_argument("--region", default="", help="地址缺省市时统一补上的前缀，如 广东省深圳市")
        if name == "geocode":
            add_request_options(sp)
            sp.add_argument("--min-reliability", type=float, default=7,
                            help="返回里的可信度低于它就标「低可信」（默认 7；阈值含义以官方文档为准）")
        else:
            sp.add_argument("--show", type=int, default=10, help=argparse.SUPPRESS)

    sp = sub.add_parser("reverse", help="经纬度 -> 地址")
    common(sp)
    sp.add_argument("--lat-column", default="lat", help="纬度列名（默认 lat）")
    sp.add_argument("--lng-column", default="lng", help="经度列名（默认 lng）")
    add_request_options(sp)

    sp = sub.add_parser("distance", help="到最近门店的球面距离（不联网）")
    common(sp)
    sp.add_argument("--stores", required=True, help="门店 CSV")
    sp.add_argument("--lat-column", default="geo_lat", help="点的纬度列（默认 geo_lat，可直接接 geocode 的输出）")
    sp.add_argument("--lng-column", default="geo_lng", help="点的经度列（默认 geo_lng）")
    sp.add_argument("--store-name-column", default="name", help="门店名列（默认 name）")
    sp.add_argument("--store-lat-column", default="lat", help="门店纬度列（默认 lat）")
    sp.add_argument("--store-lng-column", default="lng", help="门店经度列（默认 lng）")
    sp.add_argument("--radius-km", type=float, help="配送半径（千米），给了就输出是否在半径内")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    handler = {"clean": cmd_clean, "geocode": cmd_geocode, "reverse": cmd_reverse, "distance": cmd_distance}[args.cmd]
    try:
        return handler(args)
    except UsageError as exc:
        sys.stderr.write("参数错误：%s\n" % exc)
        return 1
    except FileError as exc:
        sys.stderr.write("文件错误：%s\n" % exc)
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(130)
