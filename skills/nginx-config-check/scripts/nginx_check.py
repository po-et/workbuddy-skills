#!/usr/bin/env python3
"""nginx 配置体检：内置指令解析器（含 include 展开）+ 安全与性能规则检查，纯标准库。

用法：
  python3 nginx_check.py /etc/nginx/nginx.conf [--json] [--strict]
  python3 nginx_check.py conf/nginx.conf --prefix conf     # include 相对路径的解析根
  python3 nginx_check.py sites-enabled/app.conf --no-include
  --strict：存在 high/warn 则退出码 1。
解析器支持：块嵌套 {}、分号语句、# 注释、单双引号、include 通配与相对路径展开、递归保护。
限制：不求值变量与 map/geo 规则，不校验指令是否存在于当前 nginx 版本，请配合 nginx -t 使用。
"""
import argparse, glob, json, os, re, sys

WEAK_TLS = ("TLSv1", "TLSv1.1", "SSLv2", "SSLv3")
SEC_HEADERS = {
    "x-content-type-options": ("nosniff", "warn", "浏览器会按内容猜 MIME 类型，可被用于 XSS"),
    "x-frame-options": ("SAMEORIGIN", "warn", "页面可被任意站点 iframe 嵌套，存在点击劫持风险"),
}
BLOCK_DIRECTIVES = {"http", "server", "location", "upstream", "events", "stream", "mail", "if", "map",
                    "geo", "types", "limit_except", "split_clients", "charset_map", "match", "server_names_hash"}


# ---------------------------------------------------------------- 解析器
class D:
    """一条指令：名字、参数、子块、来源文件与行号。"""
    __slots__ = ("name", "args", "children", "file", "line")

    def __init__(self, name, args, children, file, line):
        self.name, self.args, self.children, self.file, self.line = name, args, children, file, line

    def arg(self, i=0):
        return self.args[i] if i < len(self.args) else ""

    def __repr__(self):
        return f"<{self.name} {' '.join(self.args)}>"


def tokenize(text):
    """切成 (token, line)；处理注释、单双引号、{ } ; 三个特殊符号。"""
    toks, buf, line, quoted = [], [], 1, False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1; i += 1
            if buf: toks.append(("".join(buf), line)); buf = []
            continue
        if ch == "#" and not buf:
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch in "'\"":
            q, i = ch, i + 1
            while i < n and text[i] != q:
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i + 1]); i += 2; continue
                if text[i] == "\n": line += 1
                buf.append(text[i]); i += 1
            i += 1; quoted = True
            continue
        if ch in " \t\r":
            if buf or quoted: toks.append(("".join(buf), line)); buf = []; quoted = False
            i += 1; continue
        if ch in "{};":
            if buf or quoted: toks.append(("".join(buf), line)); buf = []; quoted = False
            toks.append((ch, line)); i += 1; continue
        buf.append(ch); i += 1
    if buf or quoted:
        toks.append(("".join(buf), line))
    return toks


def parse_tokens(toks, i, file, findings):
    out = []
    while i < len(toks):
        tok, line = toks[i]
        if tok == "}":
            return out, i + 1
        if tok == ";":
            i += 1; continue
        words = []
        while i < len(toks) and toks[i][0] not in ("{", ";", "}"):
            words.append(toks[i][0]); i += 1
        if not words:
            i += 1; continue
        if i < len(toks) and toks[i][0] == "{":
            kids, i = parse_tokens(toks, i + 1, file, findings)
            out.append(D(words[0], words[1:], kids, file, line))
        else:
            if i < len(toks) and toks[i][0] == ";":
                i += 1
            out.append(D(words[0], words[1:], None, file, line))
    return out, i


def resolve_include(pattern, cur_file, prefixes):
    if os.path.isabs(pattern):
        cands = [pattern]
    else:
        cands = [os.path.join(os.path.dirname(cur_file), pattern)] + [os.path.join(p, pattern) for p in prefixes]
    for c in cands:
        hits = sorted(glob.glob(c))
        if hits:
            return hits
    return []


def parse_file(path, findings, prefixes, seen, follow=True):
    real = os.path.realpath(path)
    if real in seen:
        findings.append(mk("N000", "warn", path, 0, "-", f"include 形成循环引用：{path}", "去掉重复 include"))
        return []
    seen = seen | {real}
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        findings.append(mk("N000", "warn", path, 0, "-", f"读不到文件：{e.__class__.__name__}", "检查路径与权限"))
        return []
    nodes, _ = parse_tokens(tokenize(text), 0, path, findings)
    return expand(nodes, path, findings, prefixes, seen, follow)


def expand(nodes, cur_file, findings, prefixes, seen, follow):
    out = []
    for d in nodes:
        if d.name == "include" and d.args:
            if not follow:
                continue
            hits = resolve_include(d.arg(), cur_file, prefixes)
            if not hits:
                if not d.arg().endswith(("mime.types", "fastcgi_params", "uwsgi_params", "scgi_params", "proxy_params")):
                    findings.append(mk("N015", "info", cur_file, d.line, "-", f"include 的目标不存在或匹配为空：{d.arg()}",
                                       "本机没有这些文件属正常；要完整检查请加 --prefix 指向真实的 nginx 配置根目录"))
                continue
            for h in hits:
                out += parse_file(h, findings, prefixes, seen, follow)
            continue
        if d.children is not None:
            d.children = expand(d.children, cur_file, findings, prefixes, seen, follow)
        out.append(d)
    return out


# ---------------------------------------------------------------- 规则
def mk(rule, sev, file, line, ctx, msg, fix):
    return {"rule": rule, "severity": sev, "file": file, "line": line, "context": ctx, "message": msg, "fix": fix}


def find_all(nodes, name):
    return [d for d in nodes if d.name == name]


def own(kids, name):
    """只看当前块自己写的指令（同名多次取最后一条）。"""
    hits = find_all(kids, name)
    return hits[-1] if hits else None


def lookup(chain, name):
    """按 nginx 继承语义从内层往外层找一条指令。"""
    for scope in reversed(chain):
        hits = find_all(scope, name)
        if hits:
            return hits[-1]
    return None


def lookup_all(chain, name):
    """add_header 这类数组型指令：内层出现就整体覆盖外层。"""
    for scope in reversed(chain):
        hits = find_all(scope, name)
        if hits:
            return hits
    return []


def server_label(srv):
    names = [d for d in (srv.children or []) if d.name == "server_name"]
    return ("server " + " ".join(names[0].args)) if names and names[0].args else "server"


def listen_info(srv):
    """返回 (端口集合, 是否 TLS, listen 指令列表)。"""
    ports, tls, ls = set(), False, []
    for d in srv.children or []:
        if d.name != "listen":
            continue
        ls.append(d)
        a = d.arg()
        m = re.search(r"(?:^|:)(\d+)$", a) or re.fullmatch(r"(\d+)", a)
        if m:
            ports.add(m.group(1))
        elif a.endswith(".sock") or a.startswith("unix:"):
            ports.add("unix")
        if "ssl" in d.args or "443" in ports:
            tls = True
    return ports, tls, ls


def check_location(loc, chain, srv_label, out, tls):
    where = f"{srv_label} / location {' '.join(loc.args)}"
    kids = loc.children or []
    chain = chain + [kids]
    pref = loc.args[-1] if loc.args else ""
    for d in find_all(kids, "if"):
        cond = " ".join(d.args)
        out.append(mk("N010", "warn", d.file, d.line, where, f"location 内使用 if（{cond}）",
                      "if is evil：能被 try_files、return、map、独立 location 替代的一律替换，只有 if + return/rewrite 是安全用法"))
    alias = own(kids, "alias")
    if alias:
        path = alias.arg()
        if pref.endswith("/") and not path.endswith("/"):
            out.append(mk("N009", "high", alias.file, alias.line, where,
                          f"location 以 / 结尾但 alias {path} 没有以 / 结尾",
                          f"改成 alias {path}/;否则 /x../ 这类请求会拼出上级目录，等于目录穿越"))
        if loc.arg(0) in ("~", "~*") and "$" not in path:
            out.append(mk("N009", "info", alias.file, alias.line, where, "正则 location 里用 alias 但没有引用捕获组",
                          "正则 location 建议用 root，或在 alias 里写 $1 明确拼接规则"))
    root = own(kids, "root")
    if root:
        base = pref.rstrip("/")
        if base.startswith("/") and root.arg().rstrip("/").endswith(base):
            out.append(mk("N009", "warn", root.file, root.line, where,
                          f"location {base} 与 root {root.arg()} 尾部重复，实际路径会变成 {root.arg().rstrip('/')}{base}",
                          "root 会把 location 前缀再拼一次；想直接指向该目录请改用 alias"))
    ai = own(kids, "autoindex")
    if ai and ai.arg() == "on":
        out.append(mk("N014", "high", ai.file, ai.line, where, "autoindex on 会列出目录内容",
                      "关掉（autoindex off）；确需目录浏览就限定到单独 location 并加访问控制"))
    al = own(kids, "access_log")
    if al and al.arg() == "off":
        out.append(mk("N011", "warn", al.file, al.line, where, "access_log off，这段流量没有访问日志",
                      "生产保留访问日志用于排障与审计；只想降噪就用 buffer=32k flush=5s 或按状态码抽样"))
    pp = own(kids, "proxy_pass")
    if pp:
        for t, why in (("proxy_connect_timeout", "连不上上游时会按默认 60s 挂着"),
                       ("proxy_read_timeout", "上游不返回时默认等 60s，容易把 worker 连接耗尽")):
            if not lookup(chain, t):
                out.append(mk("N006", "warn", pp.file, pp.line, where, f"proxy_pass 没有设置 {t}",
                              f"{why}；显式写 {t} 3s（按上游 SLA 取值），同时配 proxy_send_timeout"))
        if not lookup(chain, "proxy_set_header"):
            out.append(mk("N016", "info", pp.file, pp.line, where, "反向代理没有透传 Host / X-Forwarded-For",
                          "补 proxy_set_header Host $host 与 X-Forwarded-For $proxy_add_x_forwarded_for、X-Forwarded-Proto $scheme"))
    for sub in find_all(kids, "location"):
        check_location(sub, chain, where, out, tls)


def check_server(srv, chain, out, seen_names):
    kids = srv.children or []
    chain = chain + [kids]
    label = server_label(srv)
    ports, tls, listens = listen_info(srv)
    for d in find_all(kids, "server_name"):
        for nm in d.args:
            if nm in ("_", "*"):
                continue
            for p in (ports or {"80"}):
                seen_names.setdefault((p, nm), []).append((d.file, d.line))

    st = own(kids, "server_tokens")
    if st and st.arg() != "off":
        out.append(mk("N001", "warn", st.file, st.line, label,
                      f"这个 server 把 server_tokens 覆盖成 {st.arg()}，响应头会带 nginx 版本号",
                      "改成 server_tokens off;（要完全去掉 Server 头需要 headers-more 模块或网关层改写）"))
    if tls:
        for d in listens:
            if "443" in " ".join(d.args) or "ssl" in d.args:
                has2 = "http2" in d.args or "quic" in d.args
                h2 = lookup(chain, "http2")
                if not has2 and not (h2 and h2.arg() == "on"):
                    out.append(mk("N003", "warn", d.file, d.line, label, "listen 443 没有启用 HTTP/2",
                                  "nginx ≥ 1.25.1 写 http2 on;（旧版写 listen 443 ssl http2;），多路复用能明显降首屏延迟"))
        sp = lookup(chain, "ssl_protocols")
        if not sp:
            out.append(mk("N004", "warn", srv.file, srv.line, label, "TLS server 没有显式设置 ssl_protocols",
                          "写 ssl_protocols TLSv1.2 TLSv1.3;，别依赖不同版本 nginx 的默认值"))
        else:
            weak = [p for p in sp.args if p in WEAK_TLS]
            if weak:
                out.append(mk("N004", "high", sp.file, sp.line, label, f"ssl_protocols 仍允许 {' '.join(weak)}",
                              "只保留 TLSv1.2 TLSv1.3；TLSv1/1.1 已被主流浏览器与合规基线淘汰"))
        hsts = [h for h in lookup_all(chain, "add_header") if h.arg().lower() == "strict-transport-security"]
        if not hsts:
            out.append(mk("N005", "warn", srv.file, srv.line, label, "HTTPS server 没有 Strict-Transport-Security 头",
                          'add_header Strict-Transport-Security "max-age=31536000" always;（确认全站 HTTPS 后再加，先小 max-age 灰度）'))
    headers = {h.arg().lower() for h in lookup_all(chain, "add_header")}
    for name, (val, sev, why) in SEC_HEADERS.items():
        if name not in headers:
            out.append(mk("N005", sev, srv.file, srv.line, label, f"缺少安全响应头 {name}",
                          f"{why}；加 add_header {name} {val} always;"))
    if not lookup(chain, "client_max_body_size"):
        out.append(mk("N007", "info", srv.file, srv.line, label, "没有设置 client_max_body_size",
                      "默认 1m，上传类接口会返回 413；显式写成业务上限（如 20m），别靠默认值"))
    al = own(kids, "access_log")
    if al and al.arg() == "off":
        out.append(mk("N011", "warn", al.file, al.line, label, "整个 server 的 access_log 被关掉",
                      "生产保留访问日志；只想降噪用 buffer=32k flush=5s 或对静态资源单独关"))
    ai = own(kids, "autoindex")
    if ai and ai.arg() == "on":
        out.append(mk("N014", "high", ai.file, ai.line, label, "server 级 autoindex on，整站可被列目录",
                      "关掉（autoindex off）；确需目录浏览就限定到单独 location 并加访问控制"))
    for d in find_all(kids, "if"):
        out.append(mk("N010", "info", d.file, d.line, label, f"server 块内使用 if（{' '.join(d.args)}）",
                      "server 层的 if 相对安全，但仍建议用独立 server + return 301 替代域名跳转写法"))
    pp = own(kids, "proxy_pass")
    if pp:
        for t in ("proxy_connect_timeout", "proxy_read_timeout"):
            if not lookup(chain, t):
                out.append(mk("N006", "warn", pp.file, pp.line, label, f"proxy_pass 没有设置 {t}",
                              f"显式写 {t}，默认 60s 会在上游卡住时拖垮连接池"))
    for loc in find_all(kids, "location"):
        check_location(loc, chain, label, out, tls)


def check_tree(nodes, out):
    main = nodes
    wp = lookup([main], "worker_processes")
    if not wp:
        out.append(mk("N012", "info", nodes[0].file if nodes else "-", 0, "main", "没有设置 worker_processes",
                      "写 worker_processes auto;，让 nginx 按 CPU 核数起 worker"))
    elif wp.arg() != "auto":
        out.append(mk("N012", "info", wp.file, wp.line, "main", f"worker_processes 写死为 {wp.arg()}",
                      "改成 auto；写死的值在换机型或容器限核后就不对了"))
    https = find_all(main, "http")
    for http in https:
        hk = http.children or []
        chain = [main, hk]
        gz = lookup(chain, "gzip")
        if not gz or gz.arg() != "on":
            out.append(mk("N002", "info", http.file, http.line, "http", "没有开启 gzip",
                          "gzip on; gzip_types text/css application/json application/javascript; gzip_min_length 1k;（静态资源更推荐预压缩或 brotli）"))
        st = lookup(chain, "server_tokens")
        if not st or st.arg() != "off":
            out.append(mk("N001", "warn", (st or http).file, (st or http).line, "http",
                          "server_tokens 没有关闭，404/50x 页面与响应头会暴露 nginx 版本号",
                          "在 http 块写 server_tokens off;（要完全去掉 Server 头需要 headers-more 模块或网关层改写）"))
        for up in find_all(hk, "upstream"):
            uk = up.children or []
            if not find_all(uk, "keepalive"):
                out.append(mk("N013", "info", up.file, up.line, f"upstream {up.arg()}", "upstream 没有配 keepalive",
                              "加 keepalive 32; 并在 location 里写 proxy_http_version 1.1; proxy_set_header Connection \"\";，否则每个请求都新建到上游的 TCP 连接"))
        al = lookup(chain, "access_log")
        if al and al.arg() == "off":
            out.append(mk("N011", "warn", al.file, al.line, "http", "http 级 access_log off，全站没有访问日志",
                          "生产必须留访问日志，排障与安全审计都依赖它"))
        seen_names = {}
        for srv in find_all(hk, "server"):
            check_server(srv, chain, out, seen_names)
        for (port, nm), spots in sorted(seen_names.items()):
            if len(spots) > 1:
                where = "；".join(f"{os.path.basename(f)}:{l}" for f, l in spots)
                out.append(mk("N008", "warn", spots[0][0], spots[0][1], f"server_name {nm}",
                              f"端口 {port} 上有 {len(spots)} 个 server 声明了同一个 server_name（{where}）",
                              "nginx 只会用第一个匹配的 server，后面的静默失效；合并它们或改成不同的 server_name"))
    if not https:
        out.append(mk("N000", "info", nodes[0].file if nodes else "-", 0, "-", "没有解析到 http 块",
                      "只检查片段文件时属正常；完整检查请传 nginx.conf 主文件"))


def main():
    ap = argparse.ArgumentParser(description="nginx 配置体检")
    ap.add_argument("paths", nargs="+", help="nginx.conf 或 conf 片段")
    ap.add_argument("--prefix", action="append", default=[], help="include 相对路径的解析根，可多次指定")
    ap.add_argument("--no-include", action="store_true", help="不展开 include")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="有 high/warn 时退出码 1")
    a = ap.parse_args()
    findings, nodes = [], []
    for p in a.paths:
        if not os.path.isfile(p):
            sys.exit(f"文件不存在：{p}")
        d = os.path.dirname(os.path.abspath(p)) or "."
        prefixes = [os.path.abspath(x) for x in a.prefix] + [d, os.path.dirname(d), "/etc/nginx", "/usr/local/nginx/conf"]
        nodes += parse_file(p, findings, prefixes, set(), follow=not a.no_include)
    if nodes:
        check_tree(nodes, findings)
    files = sorted({d.file for d in walk(nodes)})
    for f in findings:
        if os.path.abspath(str(f["file"])).startswith(os.getcwd()):
            f["file"] = os.path.relpath(str(f["file"]))
    order = {"high": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda x: (order[x["severity"]], str(x["file"]), x["line"], x["rule"]))
    counts = {s: sum(1 for x in findings if x["severity"] == s) for s in ("high", "warn", "info")}
    if a.json:
        print(json.dumps({"files": [os.path.relpath(f) if os.path.abspath(f).startswith(os.getcwd()) else f for f in files],
                          "directives": sum(1 for _ in walk(nodes)), "summary": counts, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        print(f"解析 {len(files)} 个配置文件、{sum(1 for _ in walk(nodes))} 条指令")
        if not findings:
            print("  ✓ 没有发现问题")
        cur = None
        for x in findings:
            if x["context"] != cur:
                print(f"\n== {x['context']}"); cur = x["context"]
            print(f"  [{x['severity'].upper():4}] {x['rule']}: {x['message']}")
            print(f"         {x['file']}:{x['line']} → {x['fix']}")
        print(f"\n小计：high {counts['high']} / warn {counts['warn']} / info {counts['info']}")
    sys.exit(1 if (a.strict and (counts["high"] or counts["warn"])) else 0)


def walk(nodes):
    for d in nodes:
        yield d
        if d.children:
            yield from walk(d.children)


if __name__ == "__main__":
    main()
