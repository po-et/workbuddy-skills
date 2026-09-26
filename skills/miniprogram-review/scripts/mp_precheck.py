#!/usr/bin/env python3
"""小程序提审前扫描：读项目目录里的 app.json 与页面的 .json/.wxml/.js/.ts 文本，列出常见的被驳回风险信号。

只读、不联网、不改任何文件。纯 Python 标准库，Python 3.8+。
扫描结果是「风险信号」，不是审核结论；规则以《微信小程序运营规范》及官方平台通知的最新版本为准。

检查项：
  页面    app.json 能否解析；pages / 分包页面的 .wxml 与 .js(.ts) 是否存在；重复页面；tabBar、entryPagePath、
          跳转目标（wx.navigateTo 等与 <navigator url>）是否指向已注册页面；存在但未注册的页面文件
  隐私    代码里调用的涉及用户信息的接口（与 --declared 声明清单比对）；位置类接口是否写进 requiredPrivateInfos；
          scope.userLocation 等用途说明；启动时就调用隐私接口；getUserProfile/getUserInfo
  网络    http:// 明文地址、IP 地址、本机地址；用到的域名清单；project.config.json 关闭了合法域名校验
  内容    诱导分享、关注、拉好友的文案关键词；测试或未完成内容；虚拟商品支付、用户发布内容的提示

用法：
  python3 mp_precheck.py ./my-miniprogram
  python3 mp_precheck.py ./my-miniprogram --declared declared.txt --format md --out precheck.md
  --declared：你在《用户隐私保护指引》里已声明的接口名或信息类型，每行一个（如 getLocation、位置信息）

退出码：0 完成；1 参数错误；2 目录或 app.json 读不了、报告写不进去；3 加了 --strict 且有「高」；130 中断。
"""

import argparse
import json
import os
import posixpath
import re
import sys
import tempfile

SEVERITIES = ("高", "中", "提示")
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
CATEGORY_RANK = {"APP": 0, "PAGE": 1, "TABBAR": 1, "ENTRY": 1, "NAV": 1, "PRIV": 2, "LOC": 2, "AUTH": 2,
                 "USERINFO": 2, "NET": 3, "CFG": 3, "INDUCE": 4, "TESTCONTENT": 4, "PAY": 5, "UGC": 5,
                 "LOGIN": 5, "ORPHAN": 6}
SKIP_DIRS = {"node_modules", "miniprogram_npm", ".git", "dist", "unpackage", ".idea", ".vscode", "__pycache__"}
SCAN_EXT = (".js", ".ts", ".wxml", ".json")

# 常见的涉及用户信息的接口 -> 信息类型（清单以官方文档为准）
PRIVACY_APIS = {
    "getLocation": "位置信息", "getFuzzyLocation": "位置信息", "chooseLocation": "位置信息",
    "choosePoi": "位置信息", "onLocationChange": "位置信息", "startLocationUpdate": "位置信息",
    "startLocationUpdateBackground": "位置信息",
    "chooseImage": "相册或拍摄", "chooseMedia": "相册或拍摄", "chooseVideo": "相册或拍摄",
    "saveImageToPhotosAlbum": "保存到相册", "saveVideoToPhotosAlbum": "保存到相册",
    "startRecord": "麦克风", "getRecorderManager": "麦克风", "joinVoIPChat": "麦克风",
    "getClipboardData": "剪切板", "setClipboardData": "剪切板",
    "chooseAddress": "通讯地址", "chooseInvoice": "发票信息", "chooseInvoiceTitle": "发票信息",
    "getWeRunData": "微信运动步数", "openBluetoothAdapter": "蓝牙", "createBLEConnection": "蓝牙",
    "addPhoneContact": "通讯录", "addPhoneCalendar": "日历", "addPhoneRepeatCalendar": "日历",
    "chooseMessageFile": "聊天中的文件", "createCameraContext": "摄像头",
    "getUserProfile": "用户信息", "getUserInfo": "用户信息",
}
WXML_PRIVACY = (   # (正则, 代号, 显示名, 信息类型)
    (re.compile(r"open-type\s*=\s*[\"']getPhoneNumber[\"']"), "getPhoneNumber", "button open-type=getPhoneNumber", "手机号"),
    (re.compile(r"open-type\s*=\s*[\"']getRealtimePhoneNumber[\"']"), "getRealtimePhoneNumber",
     "button open-type=getRealtimePhoneNumber", "手机号"),
    (re.compile(r"open-type\s*=\s*[\"']chooseAvatar[\"']"), "chooseAvatar", "button open-type=chooseAvatar", "头像"),
    (re.compile(r"type\s*=\s*[\"']nickname[\"']"), "nickname", "input type=nickname", "昵称"),
    (re.compile(r"<camera[\s>/]"), "camera", "<camera> 组件", "摄像头"),
    (re.compile(r"<live-pusher[\s>/]"), "live-pusher", "<live-pusher> 组件", "摄像头与麦克风"),
)
# 需要写进 app.json requiredPrivateInfos 的位置类接口（常见要求，以官方文档为准）
REQUIRED_PRIVATE_INFOS = {"getLocation", "getFuzzyLocation", "onLocationChange", "startLocationUpdate",
                          "startLocationUpdateBackground", "chooseLocation", "choosePoi", "chooseAddress"}
SCOPE_NEEDS = {"getLocation": "scope.userLocation", "onLocationChange": "scope.userLocation",
               "startLocationUpdate": "scope.userLocation", "getFuzzyLocation": "scope.userFuzzyLocation"}

INDUCE_STRONG = [re.compile(p) for p in (
    r"分享(到|至|给)?\s*\d*\s*个?\s*(微信)?群",
    r"(分享|转发)[^，。！!\n]{0,8}(后|才)[^，。！!\n]{0,6}(解锁|查看|领取|获得|使用|复活|继续|抽奖)",
    r"(邀请|拉)\s*\d*\s*(位|个|名)?\s*好友[^，。！!\n]{0,8}(解锁|领取|获得|免费|助力|才能)",
    r"(关注|加)[^，。！!\n]{0,4}公众号[^，。！!\n]{0,8}(解锁|查看|使用|领取|才能)",
    r"集赞",
    r"不(转|分享)[^，。！!\n]{0,6}(不是|就是|后悔)",
    r"转发[^，。！!\n]{0,6}(领|得)[^，。！!\n]{0,3}红包",
)]
INDUCE_WEAK = [re.compile(p) for p in (r"好友助力", r"帮我砍", r"砍一刀", r"助力得")]
TEST_CONTENT = [re.compile(p, re.I) for p in (
    r"敬请期待", r"开发中", r"测试数据", r"待完善", r"暂未开放", r"coming soon", r"lorem ipsum", r"\bTODO\b",
)]
VIRTUAL_GOODS = re.compile(r"(会员|VIP|课程|充值|金币|钻石|点券|虚拟|解锁全集)", re.I)
UGC_WORDS = re.compile(r"(发布|评论|留言|发帖|上传)")
URL_RE = re.compile(r"[\"'`](https?://[^\"'`\s]+)[\"'`]")
IP_HOST = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
NAV_CALL = re.compile(r"wx\.(navigateTo|redirectTo|reLaunch|switchTab)\s*\(")
NAV_URL = re.compile(r"url\s*:\s*([\"'`])(.*?)\1")
NAVIGATOR_URL = re.compile(r"<navigator\b[^>]*?\surl\s*=\s*[\"']([^\"'{}]+)[\"']")
STRING_LIT = re.compile(r"([\"'`])((?:\\.|(?!\1)[^\\\n])*)\1")


class InputError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("参数错误：%s\n用 -h 查看用法。\n" % message)
        sys.exit(1)


class Finding(object):
    __slots__ = ("sev", "code", "title", "evidence", "advice")

    def __init__(self, sev, code, title, evidence, advice):
        self.sev, self.code, self.title, self.evidence, self.advice = sev, code, title, evidence, advice

    def as_dict(self):
        return {"severity": self.sev, "code": self.code, "title": self.title,
                "evidence": self.evidence, "advice": self.advice}


def read_text(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        raise InputError("读取失败：%s（%s）" % (path, exc))


def blank_comments(text, kind):
    """把注释替换成空白（保留换行，行号不变）。JS 只去整行 // 注释和 /* */ 块，避免误伤字符串里的 URL。"""
    keep_newlines = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    if kind == "wxml":
        return re.sub(r"<!--.*?-->", keep_newlines, text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", keep_newlines, text, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*", keep_newlines, text)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def snippet(text, pos, width=40):
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    line = text[start:end if end != -1 else len(text)].strip()
    return line if len(line) <= width else line[:width] + "…"


def locate_root(project):
    if not os.path.isdir(project):
        raise InputError("目录不存在：%s" % project)
    notes, url_check = [], None
    root = project
    cfg_path = os.path.join(project, "project.config.json")
    if os.path.isfile(cfg_path):
        try:
            cfg = json.loads(read_text(cfg_path))
            sub = cfg.get("miniprogramRoot")
            if isinstance(sub, str) and sub.strip():
                root = os.path.join(project, sub)
            setting = cfg.get("setting") or {}
            url_check = setting.get("urlCheck")
        except ValueError as exc:
            notes.append("project.config.json 不是合法 JSON，已忽略（%s）" % exc)
    private_path = os.path.join(project, "project.private.config.json")
    if os.path.isfile(private_path):
        try:
            private = json.loads(read_text(private_path))
            if "urlCheck" in (private.get("setting") or {}):
                url_check = private["setting"]["urlCheck"]
        except ValueError:
            notes.append("project.private.config.json 不是合法 JSON，已忽略")
    if not os.path.isfile(os.path.join(root, "app.json")):
        candidates = sorted(d for d in os.listdir(project)
                            if os.path.isfile(os.path.join(project, d, "app.json")))
        if not candidates:
            raise InputError("在 %s 里找不到 app.json：请传小程序根目录（含 app.json 的那一层）" % project)
        root = os.path.join(project, candidates[0])
        notes.append("在子目录 %s 里找到了 app.json" % candidates[0])
    return root, url_check, notes


def collect_files(root, max_bytes):
    files, notes = {}, []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if not name.endswith(SCAN_EXT):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                if os.path.getsize(full) > max_bytes:
                    notes.append("跳过过大的文件：%s" % rel)
                    continue
            except OSError:
                continue
            files[rel] = read_text(full)
    return files, notes


def page_list(app):
    main = [p for p in (app.get("pages") or []) if isinstance(p, str)]
    subs = []
    for pkg in (app.get("subPackages") or app.get("subpackages") or []):
        if not isinstance(pkg, dict):
            continue
        root = str(pkg.get("root", "")).strip("/")
        for p in pkg.get("pages") or []:
            if isinstance(p, str):
                subs.append(posixpath.join(root, p.strip("/")))
    return main, subs


def check_pages(app, files, out):
    main, subs = page_list(app)
    if not main:
        out.append(Finding("高", "PAGE-EMPTY", "app.json 的 pages 为空或格式不对", "pages 字段", "至少注册一个页面，第一个即首页"))
    seen = set()
    for p in main + subs:
        if p in seen:
            out.append(Finding("中", "PAGE-DUP", "页面重复注册", p, "删除重复项"))
            continue
        seen.add(p)
        missing = []
        if p + ".wxml" not in files:
            missing.append(".wxml")
        if p + ".js" not in files and p + ".ts" not in files:
            missing.append(".js/.ts")
        if missing:
            out.append(Finding("高", "PAGE-MISSING", "已注册的页面缺文件，审核打开会报错或白屏",
                               "%s 缺 %s" % (p, "、".join(missing)), "补齐文件或从 app.json 删除该页面"))
    all_pages = set(main) | set(subs)
    tab = (app.get("tabBar") or {}).get("list") or []
    tab_pages = set()
    for item in tab:
        path = str((item or {}).get("pagePath", "")).strip("/")
        tab_pages.add(path)
        if path not in main:
            out.append(Finding("高", "TABBAR", "tabBar 指向的页面不在主包 pages 里", path,
                               "把该页面加入主包 pages，或修改 tabBar 配置"))
    entry = app.get("entryPagePath")
    if isinstance(entry, str) and entry.strip("/") not in all_pages:
        out.append(Finding("高", "ENTRY", "entryPagePath 指向未注册的页面", entry, "改成已注册的页面路径"))
    return main, subs, all_pages, tab_pages


def resolve_url(url, current_file):
    url = url.split("?", 1)[0].strip()
    if not url or "${" in url or "{{" in url:
        return None
    if url.startswith("/"):
        return posixpath.normpath(url.lstrip("/"))
    base = posixpath.dirname(current_file)
    return posixpath.normpath(posixpath.join(base, url))


def check_navigation(files, all_pages, tab_pages, out):
    for rel, raw in sorted(files.items()):
        if rel.endswith((".js", ".ts")):
            text = blank_comments(raw, "js")
            for m in NAV_CALL.finditer(text):
                window = text[m.end():m.end() + 300]
                cut = min([i for i in (window.find("})"), window.find(");")) if i != -1] or [len(window)])
                u = NAV_URL.search(window[:cut])
                if not u:
                    continue
                target = resolve_url(u.group(2), rel)
                if target is None:
                    continue
                pos = m.start()
                ev = "%s:%d  %s" % (rel, line_of(text, pos), snippet(text, pos))
                if target not in all_pages:
                    out.append(Finding("高", "NAV-TARGET", "跳转目标页面未注册：%s" % target, ev,
                                       "改成已注册的页面路径（分包页面要带分包 root）"))
                elif m.group(1) == "switchTab" and target not in tab_pages:
                    out.append(Finding("中", "NAV-SWITCHTAB", "switchTab 只能跳 tabBar 页面：%s" % target, ev,
                                       "非 tabBar 页面改用 navigateTo"))
        elif rel.endswith(".wxml"):
            text = blank_comments(raw, "wxml")
            for m in NAVIGATOR_URL.finditer(text):
                target = resolve_url(m.group(1), rel)
                if target and target not in all_pages:
                    out.append(Finding("高", "NAV-TARGET", "navigator 跳转目标未注册：%s" % target,
                                       "%s:%d  %s" % (rel, line_of(text, m.start()), snippet(text, m.start())),
                                       "改成已注册的页面路径"))


def load_declared(path):
    items = set()
    for line in read_text(path).splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            items.add(s.replace("wx.", ""))
    return items


def check_privacy(app, files, main, declared, out):
    used = {}   # 接口 -> [证据]
    for rel, raw in sorted(files.items()):
        if rel.endswith((".js", ".ts")):
            text = blank_comments(raw, "js")
            for m in re.finditer(r"\bwx\.(%s)\b" % "|".join(sorted(PRIVACY_APIS, key=len, reverse=True)), text):
                used.setdefault(m.group(1), []).append("%s:%d" % (rel, line_of(text, m.start())))
        elif rel.endswith(".wxml"):
            text = blank_comments(raw, "wxml")
            for pat, code, _, _ in WXML_PRIVACY:
                for m in pat.finditer(text):
                    used.setdefault(code, []).append("%s:%d" % (rel, line_of(text, m.start())))
    wxml_info = {code: (label, kind) for _, code, label, kind in WXML_PRIVACY}
    for api in sorted(used):
        kind = PRIVACY_APIS.get(api) or wxml_info.get(api, ("", ""))[1]
        where = "；".join(used[api][:3]) + ("（共 %d 处）" % len(used[api]) if len(used[api]) > 3 else "")
        name = wxml_info[api][0] if api in wxml_info else "wx." + api
        if declared is None:
            out.append(Finding("中", "PRIV-%s" % api, "用到涉及「%s」的接口 %s：核对是否已在《用户隐私保护指引》中声明"
                               % (kind, name), where, "逐项对照后台的隐私保护指引；用不到的调用直接删掉"))
        elif api not in declared and kind not in declared:
            out.append(Finding("高", "PRIV-%s" % api, "用到 %s（%s），但声明清单里没有" % (name, kind), where,
                               "在《用户隐私保护指引》里补充声明，或删除这处调用"))
    rpi = app.get("requiredPrivateInfos") or []
    for api in sorted(set(used) & REQUIRED_PRIVATE_INFOS):
        if api not in rpi:
            out.append(Finding("高", "LOC-RPI-%s" % api, "接口 %s 没写进 app.json 的 requiredPrivateInfos" % api,
                               "；".join(used[api][:3]), "在 app.json 的 requiredPrivateInfos 里加上 %s（常见要求，以官方文档为准）" % api))
    perm = app.get("permission") or {}
    for api in sorted(set(used) & set(SCOPE_NEEDS)):
        scope = SCOPE_NEEDS[api]
        if not ((perm.get(scope) or {}).get("desc")):
            out.append(Finding("中", "LOC-DESC-%s" % api, "调用 %s 但 app.json 的 permission 里没有 %s 的用途说明" % (api, scope),
                               "；".join(used[api][:3]), "在 permission.%s.desc 写清用途（常见要求，以官方文档为准）" % scope))
    for api in ("getUserProfile", "getUserInfo"):
        if api in used:
            out.append(Finding("中", "USERINFO-%s" % api, "调用了 wx.%s：官方调整过头像昵称的获取方式，可能拿不到真实信息" % api,
                               "；".join(used[api][:3]), "改用头像昵称填写能力，并按需收集（以官方文档为准）"))
    app_js = files.get("app.js") or files.get("app.ts") or ""
    if app_js:
        text = blank_comments(app_js, "js")
        hits = sorted(set(m.group(1) for m in re.finditer(r"\bwx\.(%s|authorize)\b" % "|".join(PRIVACY_APIS), text)))
        if hits:
            out.append(Finding("中", "AUTH-TIMING", "小程序启动时（app.js）就调用了 %s" % "、".join(hits),
                               "app.js", "改到用户使用对应功能时再请求；拒绝授权后基础功能仍要能用"))
    if main:
        first = main[0]
        first_js = blank_comments(files.get(first + ".js") or files.get(first + ".ts") or "", "js")
        if re.search(r"\bwx\.(authorize|getUserProfile)\b", first_js):
            out.append(Finding("提示", "AUTH-FIRSTPAGE", "首页脚本里有授权相关调用", first,
                               "确认是用户点击后才触发，而不是一进首页就弹窗"))
        if "login" in first.lower():
            out.append(Finding("提示", "LOGIN-FIRST", "首页是登录页", first,
                               "尽量允许先浏览再登录；提审时在说明里提供测试账号和体验路径"))


def check_network(files, url_check, out):
    domains = {}
    for rel, raw in sorted(files.items()):
        if not rel.endswith((".js", ".ts")):
            continue
        text = blank_comments(raw, "js")
        for m in URL_RE.finditer(text):
            url = m.group(1)
            host = re.sub(r"^https?://", "", url).split("/", 1)[0].split(":", 1)[0].lower()
            ev = "%s:%d  %s" % (rel, line_of(text, m.start()), url[:60])
            if host in ("localhost", "127.0.0.1") or host.endswith(".local"):
                out.append(Finding("高", "NET-LOCAL", "代码里有本机地址，审核和用户都访问不到", ev, "换成线上 HTTPS 域名"))
            elif IP_HOST.match(host):
                out.append(Finding("高", "NET-IP", "请求地址用的是 IP", ev, "换成已备案并配置到后台的 HTTPS 域名（常见要求）"))
            elif url.startswith("http://"):
                out.append(Finding("高", "NET-HTTP", "请求地址是 http 明文", ev, "改为 HTTPS（常见要求）"))
            else:
                domains.setdefault(host, rel)
    if domains:
        out.append(Finding("提示", "NET-DOMAINS", "代码里用到的 HTTPS 域名", "、".join(sorted(domains)),
                           "确认它们已配置为服务器域名（request 合法域名等，入口以小程序后台为准）"))
    if url_check is False:
        out.append(Finding("提示", "CFG-URLCHECK", "开发者工具关闭了合法域名校验（urlCheck: false）",
                           "project.config.json", "打开校验再真机测一遍，避免「开发时能用、线上白屏」"))


def visible_texts(rel, raw):
    """WXML 取标签之间的文字，JS 取字符串字面量；返回 [(行号, 文本)]。"""
    out = []
    if rel.endswith(".wxml"):
        text = blank_comments(raw, "wxml")
        for m in re.finditer(r">([^<]+)<|\bplaceholder\s*=\s*[\"']([^\"']+)[\"']", text):
            s = re.sub(r"\{\{.*?\}\}", "", m.group(1) or m.group(2) or "").strip()
            if s:
                out.append((line_of(text, m.start()), s))
    elif rel.endswith((".js", ".ts")):
        text = blank_comments(raw, "js")
        for m in STRING_LIT.finditer(text):
            if m.group(2).strip():
                out.append((line_of(text, m.start()), m.group(2)))
    elif rel.endswith(".json"):
        for m in re.finditer(r"\"navigationBarTitleText\"\s*:\s*\"([^\"]*)\"", raw):
            if m.group(1).strip():
                out.append((line_of(raw, m.start()), m.group(1)))
    return out


def check_content(files, out):
    has_pay = has_ugc_input = has_upload = False
    virtual, ugc_words = [], []
    for rel, raw in sorted(files.items()):
        if rel.endswith((".js", ".ts")):
            code = blank_comments(raw, "js")
            has_pay = has_pay or bool(re.search(r"\bwx\.requestPayment\b", code))
            has_upload = has_upload or bool(re.search(r"\bwx\.(uploadFile|request)\b", code))
        if rel.endswith(".wxml") and re.search(r"<(textarea|input)\b", raw):
            has_ugc_input = True
        for ln, s in visible_texts(rel, raw):
            ev = "%s:%d  %s" % (rel, ln, s if len(s) <= 40 else s[:40] + "…")
            if any(p.search(s) for p in INDUCE_STRONG):
                out.append(Finding("高", "INDUCE", "疑似诱导分享、关注或拉好友的文案", ev,
                                   "去掉以分享、关注、拉好友换取功能或奖励的设计；分享只作为可选操作"))
            elif any(p.search(s) for p in INDUCE_WEAK):
                out.append(Finding("中", "INDUCE", "助力、砍价类文案，需人工判断是否构成诱导", ev,
                                   "确认不以分享作为获得功能或奖励的条件"))
            if any(p.search(s) for p in TEST_CONTENT):
                out.append(Finding("中", "TESTCONTENT", "疑似测试或未完成内容", ev, "补齐功能或删掉入口，替换测试数据"))
            if VIRTUAL_GOODS.search(s):
                virtual.append(ev)
            if UGC_WORDS.search(s):
                ugc_words.append(ev)
    if has_pay and virtual:
        out.append(Finding("提示", "PAY-VIRTUAL", "有支付调用，且文案涉及会员、课程、充值等虚拟商品或服务",
                           "；".join(virtual[:2]), "虚拟商品或服务的支付（尤其 iOS 端）有额外限制，以官方最新说明为准"))
    elif has_pay:
        out.append(Finding("提示", "PAY", "有支付调用", "wx.requestPayment", "确认已开通支付能力，且所选类目允许交易"))
    if has_ugc_input and has_upload and ugc_words:
        out.append(Finding("提示", "UGC", "用户可以发布内容（有输入框、上传或提交，且有发布、评论类文案）",
                           "；".join(ugc_words[:2]), "常见要求：有内容安全审核机制、举报入口与相应类目资质（以官方为准）"))


def check_orphans(files, all_pages, out):
    for rel in sorted(files):
        if not rel.endswith(".wxml"):
            continue
        base = rel[:-5]
        if base in all_pages or "/components/" in "/" + rel or rel.startswith("custom-tab-bar/"):
            continue
        cfg = files.get(base + ".json", "")
        if re.search(r"\"component\"\s*:\s*true", cfg):
            continue
        if base + ".js" in files or base + ".ts" in files:
            out.append(Finding("提示", "ORPHAN", "有页面文件但没在 app.json 注册（可能是废弃页面）", base,
                               "确认不用就删掉，避免残留测试内容被带进包里"))


MANUAL = (
    "服务类目与资质：所选类目与实际功能一致，需要资质的已上传（以官方类目表为准）",
    "《用户隐私保护指引》的填写内容与实际收集的信息一致",
    "需要登录的功能：提审说明里给了可用的测试账号与体验路径，审核期间不改密码",
    "服务器域名已在后台配置；真机从首页点遍所有入口，不白屏",
    "支付、营销活动的规则写清楚；用户协议与隐私政策可点开",
)


def render(report, fmt):
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    md = fmt == "md"
    L = ["# 小程序提审前扫描" if md else "小程序提审前扫描", ""]
    L.append("## 输入" if md else "【输入】")
    for s in report["inputs"]:
        L.append(("- " if md else "  ") + s)
    L.append("")
    L.append("## 风险清单" if md else "【风险清单】（高 → 中 → 提示；是风险信号，不是审核结论）")
    if md:
        L += ["| 严重度 | 编号 | 问题 | 证据 | 建议 |", "|---|---|---|---|---|"]
    for f in report["findings"]:
        if md:
            L.append("| %s | %s | %s | %s | %s |" % (f["severity"], f["code"], f["title"],
                                                   f["evidence"].replace("|", "/"), f["advice"]))
        else:
            L.append("[%s] %s %s" % (f["severity"], f["code"], f["title"]))
            L.append("      位置：%s" % f["evidence"])
            L.append("      建议：%s" % f["advice"])
    if not report["findings"]:
        L.append("（没有扫到风险信号）")
    if report["notes"]:
        L += ["", "## 说明" if md else "【说明】"]
        L += [("- " if md else "  ") + n for n in report["notes"]]
    L += ["", "## 脚本看不到、需要人工核对" if md else "【脚本看不到、需要人工核对】"]
    L += [("- [ ] " if md else "  □ ") + m for m in MANUAL]
    s = report["summary"]
    L += ["", "汇总：高 %d / 中 %d / 提示 %d。规则以《微信小程序运营规范》及官方平台通知的最新版本为准。"
          % (s["高"], s["中"], s["提示"])]
    return "\n".join(L) + "\n"


def write_atomic(path, content):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        raise InputError("输出目录不存在：%s" % directory)
    fd, tmp = tempfile.mkstemp(prefix=".precheck-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise InputError("报告写入失败：%s（%s）" % (path, exc))


def run(args):
    root, url_check, notes = locate_root(args.project)
    files, more = collect_files(root, args.max_file_kb * 1024)
    notes += more
    declared = load_declared(args.declared) if args.declared else None
    findings = []
    try:
        app = json.loads(files.get("app.json", ""))
        if not isinstance(app, dict):
            raise ValueError("顶层不是对象")
    except ValueError as exc:
        app = None
        findings.append(Finding("高", "APP-JSON", "app.json 不是合法 JSON（注释、多余逗号都会导致编译失败）",
                                "app.json：%s" % exc, "修正为严格 JSON 后重跑；页面与跳转检查已跳过"))
    main, all_pages, tab_pages = [], set(), set()
    if app is not None:
        main, _, all_pages, tab_pages = check_pages(app, files, findings)
        check_navigation(files, all_pages, tab_pages, findings)
        check_privacy(app, files, main, declared, findings)
        check_orphans(files, all_pages, findings)
    check_network(files, url_check, findings)
    check_content(files, findings)
    uniq, seen = [], set()
    for f in findings:
        key = (f.code, f.evidence)
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    uniq.sort(key=lambda f: (SEV_RANK[f.sev], CATEGORY_RANK.get(f.code.split("-")[0], 9), f.code, f.evidence))
    summary = {s: sum(1 for f in uniq if f.sev == s) for s in SEVERITIES}
    inputs = ["项目：%s（小程序根目录 %s）" % (args.project, os.path.relpath(root, args.project)),
              "扫描文件：%d 个（.js/.ts/.wxml/.json，跳过 node_modules 等目录）" % len(files),
              "页面：%d 个已注册" % len(all_pages)]
    inputs.append("隐私声明清单：%s（%d 项）" % (args.declared, len(declared)) if declared is not None
                  else "隐私声明清单：未提供（涉及用户信息的接口只标「待核对」）")
    return {"inputs": inputs, "findings": [f.as_dict() for f in uniq], "notes": notes, "summary": summary}


def main(argv=None):
    p = Parser(description="小程序提审前扫描（只读）：页面、隐私接口、网络地址、诱导与测试文案。",
               epilog="退出码：0 完成；1 参数错误；2 读写失败；3 --strict 且有高风险；130 中断。")
    p.add_argument("project", help="小程序项目目录（含 app.json 或 project.config.json 的那一层）")
    p.add_argument("--declared", help="已在《用户隐私保护指引》中声明的接口名或信息类型清单，每行一个")
    p.add_argument("--format", choices=("text", "md", "json"), default="text", help="输出格式（默认 text）")
    p.add_argument("--out", help="写入文件（先写临时文件再替换）")
    p.add_argument("--strict", action="store_true", help="有「高」时退出码为 3")
    p.add_argument("--max-file-kb", type=int, default=1024, help="跳过超过这个大小的文件（默认 1024 KB）")
    args = p.parse_args(argv)
    if args.max_file_kb <= 0:
        sys.stderr.write("参数错误：--max-file-kb 必须大于 0\n")
        return 1
    try:
        report = run(args)
        content = render(report, args.format)
        if args.out:
            write_atomic(args.out, content)
            s = report["summary"]
            print("报告已写入 %s（高 %d / 中 %d / 提示 %d）" % (args.out, s["高"], s["中"], s["提示"]))
        else:
            sys.stdout.write(content)
    except InputError as exc:
        sys.stderr.write("输入/输出错误：%s\n" % exc)
        return 2
    if args.strict and report["summary"]["高"]:
        return 3
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断。\n")
        sys.exit(130)
